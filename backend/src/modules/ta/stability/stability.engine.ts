/**
 * P2.7 — Signal Stability Engine
 * 
 * Tracks signal performance over time and adjusts weights.
 * Detects degradation and disables underperforming signals.
 */

import { Db, Collection } from 'mongodb';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface SignalPerformance {
  signalKey: string;         // patternType_asset_tf_regime
  patternType: string;
  asset: string;
  timeframe: string;
  regime?: string;
  
  // Lifetime metrics
  nTrades: number;
  winRate: number;
  avgR: number;
  profitFactor: number;
  sharpe: number;
  maxDrawdown: number;
  
  // Rolling metrics (recent)
  recent30: RollingMetrics;
  recent100: RollingMetrics;
  recent300: RollingMetrics;
  
  // Stability
  stabilityScore: number;      // 0..1
  stabilityMultiplier: number; // 0.5..1.5
  trend: 'IMPROVING' | 'STABLE' | 'DEGRADING';
  
  // Status
  status: 'ACTIVE' | 'WARNING' | 'DISABLED';
  lastTradeAt: Date;
  updatedAt: Date;
}

export interface RollingMetrics {
  n: number;
  winRate: number;
  avgR: number;
  profitFactor: number;
}

export interface StabilityConfig {
  warningThreshold: number;   // PF below this → WARNING
  disableThreshold: number;   // PF below this + low winrate → DISABLED
  revivalThreshold: number;   // PF above this → re-enable
  minTradesForStatus: number; // Min trades to change status
  decayHalfLife: number;      // Days for decay weighting
}

export const DEFAULT_STABILITY_CONFIG: StabilityConfig = {
  warningThreshold: 1.0,
  disableThreshold: 0.8,
  revivalThreshold: 1.3,
  minTradesForStatus: 50,
  decayHalfLife: 90,
};

// ═══════════════════════════════════════════════════════════════
// STABILITY ENGINE
// ═══════════════════════════════════════════════════════════════

const COLLECTION_PERFORMANCE = 'ta_signal_performance';
const COLLECTION_TRADES = 'ta_backtest_trades';

export class SignalStabilityEngine {
  private db: Db;
  private config: StabilityConfig;
  private perfCol: Collection;
  private tradesCol: Collection;
  
  constructor(db: Db, config: StabilityConfig = DEFAULT_STABILITY_CONFIG) {
    this.db = db;
    this.config = config;
    this.perfCol = db.collection(COLLECTION_PERFORMANCE);
    this.tradesCol = db.collection(COLLECTION_TRADES);
  }
  
  /**
   * Recompute all signal performance
   */
  async recomputeAll(): Promise<{
    processed: number;
    active: number;
    warning: number;
    disabled: number;
  }> {
    console.log('[Stability] Recomputing all signal performance...');
    
    // Get all unique signal keys
    const signalKeys = await this.tradesCol.aggregate([
      {
        $group: {
          _id: {
            patternType: { $arrayElemAt: ['$patternTypes', 0] },
            asset: '$asset',
            timeframe: '$timeframe',
          }
        }
      }
    ]).toArray();
    
    let processed = 0;
    let active = 0;
    let warning = 0;
    let disabled = 0;
    
    for (const key of signalKeys) {
      const { patternType, asset, timeframe } = key._id;
      if (!patternType || !asset || !timeframe) continue;
      
      const perf = await this.computeSignalPerformance(patternType, asset, timeframe);
      
      if (perf) {
        await this.perfCol.updateOne(
          { signalKey: perf.signalKey },
          { $set: perf },
          { upsert: true }
        );
        
        processed++;
        if (perf.status === 'ACTIVE') active++;
        else if (perf.status === 'WARNING') warning++;
        else if (perf.status === 'DISABLED') disabled++;
      }
    }
    
    console.log(`[Stability] Processed ${processed}: active=${active}, warning=${warning}, disabled=${disabled}`);
    
    return { processed, active, warning, disabled };
  }
  
  /**
   * Compute performance for single signal
   */
  async computeSignalPerformance(
    patternType: string,
    asset: string,
    timeframe: string
  ): Promise<SignalPerformance | null> {
    const signalKey = `${patternType}_${asset}_${timeframe}`;
    
    // Get all trades for this signal
    const trades = await this.tradesCol
      .find({
        patternTypes: patternType,
        asset,
        timeframe,
      })
      .sort({ openTs: 1 })
      .toArray() as any[];
    
    if (trades.length < 10) return null;
    
    // Compute lifetime metrics
    const entryHits = trades.filter(t => t.entryHit);
    const wins = entryHits.filter(t => t.rMultiple > 0);
    const losses = entryHits.filter(t => t.rMultiple < 0);
    
    const winRate = entryHits.length > 0 ? wins.length / entryHits.length : 0;
    const avgR = entryHits.length > 0 
      ? entryHits.reduce((s, t) => s + t.rMultiple, 0) / entryHits.length 
      : 0;
    
    const grossProfit = wins.reduce((s, t) => s + t.rMultiple, 0);
    const grossLoss = Math.abs(losses.reduce((s, t) => s + t.rMultiple, 0));
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 3 : 0;
    
    // Compute rolling metrics
    const recent30 = this.computeRolling(entryHits, 30);
    const recent100 = this.computeRolling(entryHits, 100);
    const recent300 = this.computeRolling(entryHits, 300);
    
    // Compute stability score
    const { stabilityScore, stabilityMultiplier, trend } = this.computeStability(
      profitFactor,
      recent30,
      recent100,
      recent300
    );
    
    // Compute sharpe and drawdown
    const sharpe = this.computeSharpe(entryHits);
    const maxDrawdown = this.computeMaxDrawdown(entryHits);
    
    // Determine status
    const status = this.determineStatus(recent30, recent100, entryHits.length);
    
    const lastTrade = trades[trades.length - 1];
    
    return {
      signalKey,
      patternType,
      asset,
      timeframe,
      nTrades: trades.length,
      winRate,
      avgR,
      profitFactor,
      sharpe,
      maxDrawdown,
      recent30,
      recent100,
      recent300,
      stabilityScore,
      stabilityMultiplier,
      trend,
      status,
      lastTradeAt: new Date(lastTrade?.closeTs || Date.now()),
      updatedAt: new Date(),
    };
  }
  
  /**
   * Compute rolling metrics
   */
  private computeRolling(trades: any[], n: number): RollingMetrics {
    const recent = trades.slice(-n);
    
    if (recent.length === 0) {
      return { n: 0, winRate: 0.5, avgR: 0, profitFactor: 1 };
    }
    
    const wins = recent.filter(t => t.rMultiple > 0);
    const losses = recent.filter(t => t.rMultiple < 0);
    
    const winRate = wins.length / recent.length;
    const avgR = recent.reduce((s, t) => s + t.rMultiple, 0) / recent.length;
    
    const grossProfit = wins.reduce((s, t) => s + t.rMultiple, 0);
    const grossLoss = Math.abs(losses.reduce((s, t) => s + t.rMultiple, 0));
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 3 : 0;
    
    return { n: recent.length, winRate, avgR, profitFactor };
  }
  
  /**
   * Compute stability metrics
   */
  private computeStability(
    lifetimePF: number,
    recent30: RollingMetrics,
    recent100: RollingMetrics,
    recent300: RollingMetrics
  ): {
    stabilityScore: number;
    stabilityMultiplier: number;
    trend: 'IMPROVING' | 'STABLE' | 'DEGRADING';
  } {
    // Compare recent to historical
    const recentPF = recent30.n >= 20 ? recent30.profitFactor : recent100.profitFactor;
    const historicalPF = recent300.n >= 100 ? recent300.profitFactor : lifetimePF;
    
    const ratio = historicalPF > 0 ? recentPF / historicalPF : 1;
    
    // Stability score: how consistent is performance
    const stabilityScore = Math.max(0, Math.min(1, 
      0.5 + (ratio - 1) * 0.5
    ));
    
    // Multiplier for EV adjustment
    const stabilityMultiplier = Math.max(0.5, Math.min(1.5, 
      0.5 + stabilityScore
    ));
    
    // Trend detection
    let trend: 'IMPROVING' | 'STABLE' | 'DEGRADING';
    if (ratio > 1.2) {
      trend = 'IMPROVING';
    } else if (ratio < 0.8) {
      trend = 'DEGRADING';
    } else {
      trend = 'STABLE';
    }
    
    return { stabilityScore, stabilityMultiplier, trend };
  }
  
  /**
   * Compute Sharpe ratio
   */
  private computeSharpe(trades: any[]): number {
    if (trades.length < 2) return 0;
    
    const returns = trades.map(t => t.rMultiple);
    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    const variance = returns.reduce((s, r) => s + Math.pow(r - mean, 2), 0) / returns.length;
    const std = Math.sqrt(variance);
    
    return std > 0 ? mean / std : 0;
  }
  
  /**
   * Compute max drawdown
   */
  private computeMaxDrawdown(trades: any[]): number {
    let equity = 0;
    let peak = 0;
    let maxDD = 0;
    
    for (const trade of trades) {
      equity += trade.rMultiple;
      if (equity > peak) peak = equity;
      const dd = peak - equity;
      if (dd > maxDD) maxDD = dd;
    }
    
    return maxDD;
  }
  
  /**
   * Determine signal status
   */
  private determineStatus(
    recent30: RollingMetrics,
    recent100: RollingMetrics,
    totalTrades: number
  ): 'ACTIVE' | 'WARNING' | 'DISABLED' {
    const { warningThreshold, disableThreshold, minTradesForStatus } = this.config;
    
    if (totalTrades < minTradesForStatus) {
      return 'ACTIVE'; // Not enough data to judge
    }
    
    const recentPF = recent30.n >= 20 ? recent30.profitFactor : recent100.profitFactor;
    const recentWR = recent30.n >= 20 ? recent30.winRate : recent100.winRate;
    
    // Kill switch
    if (recentPF < disableThreshold && recentWR < 0.4 && recent100.n >= minTradesForStatus) {
      return 'DISABLED';
    }
    
    // Warning
    if (recentPF < warningThreshold) {
      return 'WARNING';
    }
    
    return 'ACTIVE';
  }
  
  /**
   * Get stability multiplier for a signal
   */
  async getMultiplier(
    patternType: string,
    asset: string,
    timeframe: string
  ): Promise<{
    multiplier: number;
    status: string;
    trend: string;
  }> {
    const signalKey = `${patternType}_${asset}_${timeframe}`;
    
    const perf = await this.perfCol.findOne({ signalKey }) as SignalPerformance | null;
    
    if (!perf) {
      return { multiplier: 1.0, status: 'UNKNOWN', trend: 'STABLE' };
    }
    
    return {
      multiplier: perf.status === 'DISABLED' ? 0 : perf.stabilityMultiplier,
      status: perf.status,
      trend: perf.trend,
    };
  }
  
  /**
   * Get all signals by status
   */
  async getSignalsByStatus(status?: string): Promise<SignalPerformance[]> {
    const filter = status ? { status } : {};
    return this.perfCol.find(filter).sort({ stabilityScore: -1 }).toArray() as any;
  }
  
  /**
   * Get degrading signals
   */
  async getDegradingSignals(): Promise<SignalPerformance[]> {
    return this.perfCol.find({ trend: 'DEGRADING' }).sort({ stabilityScore: 1 }).toArray() as any;
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createSignalStabilityEngine(
  db: Db,
  config?: Partial<StabilityConfig>
): SignalStabilityEngine {
  return new SignalStabilityEngine(db, {
    ...DEFAULT_STABILITY_CONFIG,
    ...config,
  });
}
