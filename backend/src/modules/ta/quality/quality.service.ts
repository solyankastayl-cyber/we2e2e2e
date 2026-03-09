/**
 * P2.0 — Quality Service
 * 
 * Aggregates trade data and computes quality metrics for patterns
 */

import { Db, Collection } from 'mongodb';
import { PatternQualityDoc, QualityKey, QualityRebuildConfig, Regime } from './quality.types.js';
import { QualityRepo, createQualityRepo } from './quality.repo.js';
import { computeQualityScore, decayWeight, calculateStability, WindowMetrics } from './quality.score.js';

// Source collections
const COLLECTION_BACKTEST_TRADES = 'ta_backtest_trades';
const COLLECTION_OUTCOMES = 'ta_outcomes_v3';

interface TradeData {
  patternTypes: string[];
  asset: string;
  timeframe: string;
  openTs: number;
  closeTs: number;
  entryHit: boolean;
  rMultiple: number;
  p_entry: number;
  regime?: Regime;
}

export class QualityService {
  private db: Db;
  private repo: QualityRepo;
  private tradesCol: Collection;
  private outcomesCol: Collection;
  
  constructor(db: Db) {
    this.db = db;
    this.repo = createQualityRepo(db);
    this.tradesCol = db.collection(COLLECTION_BACKTEST_TRADES);
    this.outcomesCol = db.collection(COLLECTION_OUTCOMES);
  }
  
  /**
   * Initialize indexes
   */
  async init(): Promise<void> {
    await this.repo.ensureIndexes();
  }
  
  /**
   * Rebuild quality scores for given config
   */
  async rebuildQuality(config: QualityRebuildConfig): Promise<{
    processed: number;
    written: number;
  }> {
    const halfLifeDays = config.halfLifeDays || 120;
    const minN = config.minN || 60;
    const nowTs = Date.now();
    
    console.log(`[Quality] Rebuilding quality scores...`);
    console.log(`[Quality] Config: ${JSON.stringify(config)}`);
    
    // 1. Fetch all trades in range
    const trades = await this.fetchTrades(config);
    console.log(`[Quality] Fetched ${trades.length} trades`);
    
    if (trades.length === 0) {
      return { processed: 0, written: 0 };
    }
    
    // 2. Group by (patternType, asset, tf, regime)
    const groups = this.groupTrades(trades, config.regimes);
    console.log(`[Quality] Created ${groups.size} groups`);
    
    // 3. Calculate metrics and quality for each group
    let written = 0;
    
    for (const [key, groupTrades] of groups) {
      if (groupTrades.length < minN) {
        console.log(`[Quality] Skipping ${key} (n=${groupTrades.length} < minN=${minN})`);
        continue;
      }
      
      const [patternType, asset, tf, regime] = key.split('|');
      
      // Calculate weighted metrics
      const metrics = this.calculateMetrics(groupTrades, nowTs, halfLifeDays);
      
      // Calculate stability
      const windows = this.calculateWindowMetrics(groupTrades, nowTs);
      const stability = calculateStability(windows);
      
      // Calculate calibration
      const { ece, brier } = this.calculateCalibration(groupTrades);
      
      // Calculate quality score
      const { qualityScore, multiplier } = computeQualityScore({
        winRate: metrics.winRate,
        profitFactor: metrics.profitFactor,
        avgR: metrics.avgR,
        ece,
        stability,
      });
      
      // Build document
      const doc: PatternQualityDoc = {
        patternType,
        asset,
        tf,
        regime: regime as Regime,
        n: groupTrades.length,
        winRate: metrics.winRate,
        avgR: metrics.avgR,
        profitFactor: metrics.profitFactor,
        maxDrawdownR: metrics.maxDrawdownR,
        ece,
        brier,
        stability,
        decayHalfLifeDays: halfLifeDays,
        qualityScore,
        multiplier,
        updatedAt: new Date().toISOString(),
      };
      
      // Upsert to database
      await this.repo.upsert(doc);
      written++;
    }
    
    console.log(`[Quality] Written ${written} quality documents`);
    
    return { processed: trades.length, written };
  }
  
  /**
   * Get quality for a pattern
   */
  async getPatternQuality(key: QualityKey): Promise<PatternQualityDoc | null> {
    return this.repo.get(key);
  }
  
  /**
   * Get top patterns by quality
   */
  async getTopPatterns(params: {
    asset?: string;
    tf?: string;
    regime?: Regime;
    limit?: number;
  }): Promise<PatternQualityDoc[]> {
    return this.repo.top(params);
  }
  
  /**
   * Get quality multiplier for a scenario
   * Uses geometric mean of all pattern multipliers
   */
  async getScenarioMultiplier(
    patternTypes: string[],
    asset: string,
    tf: string,
    regime: Regime
  ): Promise<{ multiplier: number; patternMultipliers: Record<string, number> }> {
    const patternMultipliers: Record<string, number> = {};
    const multipliers: number[] = [];
    
    for (const patternType of patternTypes) {
      const quality = await this.repo.get({ patternType, asset, tf, regime });
      
      if (quality) {
        patternMultipliers[patternType] = quality.multiplier;
        multipliers.push(quality.multiplier);
      } else {
        // Default multiplier for unknown patterns
        patternMultipliers[patternType] = 1.0;
        multipliers.push(1.0);
      }
    }
    
    // Geometric mean
    const product = multipliers.reduce((a, b) => a * b, 1);
    const multiplier = Math.pow(product, 1 / multipliers.length);
    
    return { multiplier, patternMultipliers };
  }
  
  // ═══════════════════════════════════════════════════════════════
  // PRIVATE METHODS
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * Fetch trades from database
   */
  private async fetchTrades(config: QualityRebuildConfig): Promise<TradeData[]> {
    const filter: Record<string, any> = {};
    
    if (config.assets.length > 0) {
      filter.asset = { $in: config.assets };
    }
    
    if (config.timeframes.length > 0) {
      filter.timeframe = { $in: config.timeframes };
    }
    
    if (config.fromTs) {
      filter.openTs = { $gte: config.fromTs };
    }
    
    if (config.toTs) {
      filter.closeTs = { $lte: config.toTs };
    }
    
    // Try backtest trades first, then outcomes
    let trades = await this.tradesCol.find(filter).toArray() as any[];
    
    if (trades.length === 0) {
      // Try outcomes collection
      const outcomes = await this.outcomesCol.find(filter).toArray() as any[];
      trades = outcomes.map(o => ({
        patternTypes: o.patternTypes || [o.patternType],
        asset: o.asset,
        timeframe: o.timeframe || o.tf,
        openTs: o.openTs || o.timestamp,
        closeTs: o.closeTs || o.timestamp + 86400000,
        entryHit: o.entryHit ?? (o.outcomeClass !== 'NO_ENTRY'),
        rMultiple: o.rMultiple ?? o.r ?? 0,
        p_entry: o.p_entry ?? o.pEntry ?? 0.5,
        regime: o.regime,
      }));
    }
    
    // Expand trades by pattern types
    const expanded: TradeData[] = [];
    for (const trade of trades) {
      const patternTypes = trade.patternTypes || [trade.patternType || 'UNKNOWN'];
      for (const pt of patternTypes) {
        expanded.push({
          ...trade,
          patternTypes: [pt],
        });
      }
    }
    
    return expanded;
  }
  
  /**
   * Group trades by (patternType, asset, tf, regime)
   */
  private groupTrades(
    trades: TradeData[],
    regimes: Regime[]
  ): Map<string, TradeData[]> {
    const groups = new Map<string, TradeData[]>();
    
    for (const trade of trades) {
      const patternType = trade.patternTypes[0];
      const regime = trade.regime || 'RANGE';
      
      // Only include if regime matches config
      if (!regimes.includes(regime)) continue;
      
      const key = `${patternType}|${trade.asset}|${trade.timeframe}|${regime}`;
      
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key)!.push(trade);
    }
    
    return groups;
  }
  
  /**
   * Calculate weighted metrics
   */
  private calculateMetrics(
    trades: TradeData[],
    nowTs: number,
    halfLifeDays: number
  ): {
    winRate: number;
    avgR: number;
    profitFactor: number;
    maxDrawdownR: number;
  } {
    let totalWeight = 0;
    let weightedEntryHits = 0;
    let weightedWins = 0;
    let weightedR = 0;
    let positiveR = 0;
    let negativeR = 0;
    
    // Calculate weighted metrics
    for (const trade of trades) {
      const ageDays = (nowTs - trade.closeTs) / (24 * 60 * 60 * 1000);
      const weight = decayWeight(ageDays, halfLifeDays);
      
      totalWeight += weight;
      
      if (trade.entryHit) {
        weightedEntryHits += weight;
        weightedR += trade.rMultiple * weight;
        
        if (trade.rMultiple > 0) {
          weightedWins += weight;
          positiveR += trade.rMultiple * weight;
        } else {
          negativeR += Math.abs(trade.rMultiple) * weight;
        }
      }
    }
    
    const winRate = weightedEntryHits > 0 ? weightedWins / weightedEntryHits : 0;
    const avgR = weightedEntryHits > 0 ? weightedR / weightedEntryHits : 0;
    const profitFactor = negativeR > 0 ? positiveR / negativeR : (positiveR > 0 ? 3.0 : 0);
    
    // Max drawdown
    let equity = 0;
    let peak = 0;
    let maxDD = 0;
    for (const trade of trades.filter(t => t.entryHit)) {
      equity += trade.rMultiple;
      if (equity > peak) peak = equity;
      const dd = peak - equity;
      if (dd > maxDD) maxDD = dd;
    }
    
    return {
      winRate,
      avgR,
      profitFactor: Math.min(profitFactor, 3.0), // Cap at 3.0
      maxDrawdownR: maxDD,
    };
  }
  
  /**
   * Calculate metrics for rolling windows
   */
  private calculateWindowMetrics(trades: TradeData[], nowTs: number): WindowMetrics[] {
    const windows: WindowMetrics[] = [];
    const windowDays = [30, 90, 180];
    
    for (const days of windowDays) {
      const cutoff = nowTs - days * 24 * 60 * 60 * 1000;
      const windowTrades = trades.filter(t => t.closeTs >= cutoff);
      
      if (windowTrades.length < 10) {
        windows.push({ windowDays: days, winRate: 0.5, avgR: 0 });
        continue;
      }
      
      const entryHits = windowTrades.filter(t => t.entryHit);
      const wins = entryHits.filter(t => t.rMultiple > 0);
      
      const winRate = entryHits.length > 0 ? wins.length / entryHits.length : 0.5;
      const avgR = entryHits.length > 0
        ? entryHits.reduce((s, t) => s + t.rMultiple, 0) / entryHits.length
        : 0;
      
      windows.push({ windowDays: days, winRate, avgR });
    }
    
    return windows;
  }
  
  /**
   * Calculate calibration metrics (ECE, Brier)
   */
  private calculateCalibration(trades: TradeData[]): { ece: number; brier: number } {
    if (trades.length === 0) return { ece: 0, brier: 0 };
    
    // Brier score
    let brierSum = 0;
    for (const trade of trades) {
      const actual = trade.entryHit ? 1 : 0;
      brierSum += Math.pow(trade.p_entry - actual, 2);
    }
    const brier = brierSum / trades.length;
    
    // ECE with 10 bins
    const binEdges = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
    let ece = 0;
    
    for (let i = 0; i < binEdges.length - 1; i++) {
      const binTrades = trades.filter(
        t => t.p_entry >= binEdges[i] && t.p_entry < binEdges[i + 1]
      );
      
      if (binTrades.length === 0) continue;
      
      const weight = binTrades.length / trades.length;
      const predicted = binTrades.reduce((s, t) => s + t.p_entry, 0) / binTrades.length;
      const actual = binTrades.filter(t => t.entryHit).length / binTrades.length;
      
      ece += weight * Math.abs(predicted - actual);
    }
    
    return { ece, brier };
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createQualityService(db: Db): QualityService {
  return new QualityService(db);
}
