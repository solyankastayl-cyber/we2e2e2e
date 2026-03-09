/**
 * P1.6.1 — Batch Simulation Runner
 * 
 * Fills ta_ml_rows_v4 dataset with 30k-60k rows
 * for LightGBM training (P1.7)
 * 
 * Pipeline per bar:
 * candles → patterns → geometry → gates → graph → regime → decision → simulate → outcome → dataset_writer_v4
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuid } from 'uuid';
import { createDecisionEngine, DecisionContext, CandleData, ScenarioInput, DecisionPack } from '../decision/decision.engine.js';
import { writeDatasetRowV4Direct } from '../decision/dataset_writer_v4.js';
import { evaluateOutcomeSimple, OutcomeInput, OutcomeResult } from '../decision/outcome_evaluator.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface BatchConfig {
  assets: string[];
  timeframes: string[];
  from: string;  // '2017-01-01'
  to: string;    // '2024-12-31'
  windowSize: number;  // Default 300
}

export interface BatchProgress {
  runId: string;
  asset: string;
  timeframe: string;
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  barsProcessed: number;
  totalBars: number;
  tradesGenerated: number;
  datasetRows: number;
  startedAt: Date;
  updatedAt: Date;
  error?: string;
}

export interface BatchRunResult {
  runId: string;
  status: 'RUNNING' | 'DONE' | 'FAILED';
  totalAssets: number;
  totalTimeframes: number;
  totalRows: number;
  startedAt: Date;
  finishedAt?: Date;
}

// ═══════════════════════════════════════════════════════════════
// COLLECTIONS
// ═══════════════════════════════════════════════════════════════

const COLLECTION_CANDLES = 'ta_candles';
const COLLECTION_PROGRESS = 'batch_simulation_progress';
const COLLECTION_DATASET_V4 = 'ta_ml_rows_v4';

// ═══════════════════════════════════════════════════════════════
// BATCH SIMULATION SERVICE
// ═══════════════════════════════════════════════════════════════

export class BatchSimulationService {
  private db: Db;
  private candlesCol: Collection;
  private progressCol: Collection;
  private datasetCol: Collection;

  constructor(db: Db) {
    this.db = db;
    this.candlesCol = db.collection(COLLECTION_CANDLES);
    this.progressCol = db.collection(COLLECTION_PROGRESS);
    this.datasetCol = db.collection(COLLECTION_DATASET_V4);
  }

  /**
   * Run batch simulation for all assets/timeframes
   */
  async runBatchSimulation(config: BatchConfig): Promise<BatchRunResult> {
    const runId = uuid();
    const startedAt = new Date();
    
    console.log(`[BatchSim] Starting batch simulation ${runId}`);
    console.log(`[BatchSim] Assets: ${config.assets.join(', ')}`);
    console.log(`[BatchSim] Timeframes: ${config.timeframes.join(', ')}`);
    console.log(`[BatchSim] Period: ${config.from} to ${config.to}`);
    
    let totalRows = 0;
    
    // Process each asset/timeframe combination
    for (const asset of config.assets) {
      for (const tf of config.timeframes) {
        try {
          const rows = await this.processAssetTimeframe(runId, asset, tf, config);
          totalRows += rows;
          console.log(`[BatchSim] ${asset}/${tf}: ${rows} rows written`);
        } catch (error) {
          console.error(`[BatchSim] Error processing ${asset}/${tf}:`, error);
          // Continue with other combinations
        }
      }
    }
    
    return {
      runId,
      status: 'DONE',
      totalAssets: config.assets.length,
      totalTimeframes: config.timeframes.length,
      totalRows,
      startedAt,
      finishedAt: new Date(),
    };
  }

  /**
   * Process single asset/timeframe combination
   */
  private async processAssetTimeframe(
    runId: string,
    asset: string,
    tf: string,
    config: BatchConfig
  ): Promise<number> {
    // Initialize progress
    const progress: BatchProgress = {
      runId,
      asset,
      timeframe: tf,
      status: 'RUNNING',
      barsProcessed: 0,
      totalBars: 0,
      tradesGenerated: 0,
      datasetRows: 0,
      startedAt: new Date(),
      updatedAt: new Date(),
    };
    
    await this.progressCol.insertOne(progress);
    
    try {
      // Load candles for the period
      const fromTs = new Date(config.from).getTime();
      const toTs = new Date(config.to).getTime();
      
      const candles = await this.candlesCol
        .find({
          asset,
          timeframe: tf,
          openTime: { $gte: fromTs, $lte: toTs }
        })
        .sort({ openTime: 1 })
        .toArray() as any[];
      
      if (candles.length < config.windowSize + 50) {
        console.log(`[BatchSim] Not enough candles for ${asset}/${tf}: ${candles.length}`);
        await this.updateProgress(runId, asset, tf, {
          status: 'FAILED',
          error: `Not enough candles: ${candles.length}`
        });
        return 0;
      }
      
      progress.totalBars = candles.length - config.windowSize;
      await this.updateProgress(runId, asset, tf, { totalBars: progress.totalBars });
      
      // Create decision engine
      const decisionEngine = createDecisionEngine(this.db);
      
      let rowsWritten = 0;
      let tradesGenerated = 0;
      
      // Step through candles (replay without lookahead)
      for (let t = config.windowSize; t < candles.length; t++) {
        // Get window of candles (no future data!)
        const windowCandles = candles.slice(t - config.windowSize, t + 1);
        const currentCandle = candles[t];
        
        // Convert to CandleData format
        const candleData: CandleData[] = windowCandles.map(c => ({
          openTime: c.openTime,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume || 0,
        }));
        
        // Calculate ATR (simplified)
        const atr = this.calculateATR(candleData, 14);
        
        // Generate mock scenarios from patterns (simplified for batch)
        const scenarios = await this.detectPatterns(candleData, asset, tf, atr, currentCandle.close);
        
        if (scenarios.length === 0) {
          // No patterns detected, skip this bar
          if (t % 500 === 0) {
            await this.updateProgress(runId, asset, tf, {
              barsProcessed: t - config.windowSize,
              updatedAt: new Date(),
            });
          }
          continue;
        }
        
        // Build decision context
        const ctx: DecisionContext = {
          asset,
          timeframe: tf,
          timestamp: new Date(currentCandle.openTime),
          candles: candleData,
          currentPrice: currentCandle.close,
          atr,
          scenarios,
        };
        
        // Compute decision
        const decisionPack = await decisionEngine.computeDecision(ctx);
        
        // Process scenarios that passed the gate
        for (const processedScenario of decisionPack.scenarios) {
          tradesGenerated++;
          
          // Simulate trade outcome (look forward to evaluate)
          const futureCandles = candles.slice(t + 1, Math.min(t + 101, candles.length));
          
          if (futureCandles.length < 10) continue;
          
          const outcomeInput: OutcomeInput = {
            entry: processedScenario.entry,
            stop: processedScenario.stop,
            target1: processedScenario.target1,
            target2: processedScenario.target2,
            direction: processedScenario.direction,
            entryTs: currentCandle.openTime,
            futureCandles: futureCandles.map(c => ({
              ts: c.openTime,
              open: c.open,
              high: c.high,
              low: c.low,
              close: c.close,
            })),
            maxBars: 100,
          };
          
          const outcome = evaluateOutcomeSimple(outcomeInput);
          
          // Write dataset row
          await writeDatasetRowV4Direct(this.db, {
            scenario: processedScenario,
            decisionPack,
            outcome,
            split: this.determineSplit(currentCandle.openTime),
          });
          
          rowsWritten++;
        }
        
        // Update progress periodically
        if (t % 100 === 0) {
          await this.updateProgress(runId, asset, tf, {
            barsProcessed: t - config.windowSize,
            tradesGenerated,
            datasetRows: rowsWritten,
            updatedAt: new Date(),
          });
        }
      }
      
      // Final progress update
      await this.updateProgress(runId, asset, tf, {
        status: 'DONE',
        barsProcessed: candles.length - config.windowSize,
        tradesGenerated,
        datasetRows: rowsWritten,
        updatedAt: new Date(),
      });
      
      return rowsWritten;
      
    } catch (error) {
      await this.updateProgress(runId, asset, tf, {
        status: 'FAILED',
        error: (error as Error).message,
        updatedAt: new Date(),
      });
      throw error;
    }
  }

  /**
   * Detect patterns from candles (simplified version for batch processing)
   */
  private async detectPatterns(
    candles: CandleData[],
    asset: string,
    tf: string,
    atr: number,
    currentPrice: number
  ): Promise<ScenarioInput[]> {
    const scenarios: ScenarioInput[] = [];
    
    // Find pivot points
    const pivots = this.findPivots(candles);
    
    if (pivots.highs.length < 2 || pivots.lows.length < 2) {
      return scenarios;
    }
    
    // Detect simple triangle patterns
    const triangleScenario = this.detectTriangle(candles, pivots, atr, currentPrice);
    if (triangleScenario) {
      scenarios.push(triangleScenario);
    }
    
    // Detect channel patterns
    const channelScenario = this.detectChannel(candles, pivots, atr, currentPrice);
    if (channelScenario) {
      scenarios.push(channelScenario);
    }
    
    // Detect support/resistance flip
    const srScenario = this.detectSRFlip(candles, pivots, atr, currentPrice);
    if (srScenario) {
      scenarios.push(srScenario);
    }
    
    return scenarios;
  }

  /**
   * Find pivot highs and lows
   */
  private findPivots(candles: CandleData[]): {
    highs: number[];
    lows: number[];
    highIdxs: number[];
    lowIdxs: number[];
  } {
    const highs: number[] = [];
    const lows: number[] = [];
    const highIdxs: number[] = [];
    const lowIdxs: number[] = [];
    
    const lookback = 5;
    
    for (let i = lookback; i < candles.length - lookback; i++) {
      let isHigh = true;
      let isLow = true;
      
      for (let j = i - lookback; j <= i + lookback; j++) {
        if (j === i) continue;
        if (candles[j].high >= candles[i].high) isHigh = false;
        if (candles[j].low <= candles[i].low) isLow = false;
      }
      
      if (isHigh) {
        highs.push(candles[i].high);
        highIdxs.push(i);
      }
      if (isLow) {
        lows.push(candles[i].low);
        lowIdxs.push(i);
      }
    }
    
    return { highs, lows, highIdxs, lowIdxs };
  }

  /**
   * Detect triangle pattern
   */
  private detectTriangle(
    candles: CandleData[],
    pivots: { highs: number[]; lows: number[]; highIdxs: number[]; lowIdxs: number[] },
    atr: number,
    currentPrice: number
  ): ScenarioInput | null {
    if (pivots.highs.length < 2 || pivots.lows.length < 2) return null;
    
    const lastHighs = pivots.highs.slice(-3);
    const lastLows = pivots.lows.slice(-3);
    
    // Check for converging pattern
    const highSlope = (lastHighs[lastHighs.length - 1] - lastHighs[0]) / lastHighs.length;
    const lowSlope = (lastLows[lastLows.length - 1] - lastLows[0]) / lastLows.length;
    
    // Ascending triangle: flat highs, rising lows
    if (Math.abs(highSlope) < atr * 0.1 && lowSlope > atr * 0.05) {
      const resistance = Math.max(...lastHighs);
      const support = lastLows[lastLows.length - 1];
      const riskR = (currentPrice - support) / atr;
      
      if (riskR > 0.5 && riskR < 3) {
        return {
          scenarioId: uuid(),
          patternType: 'TRIANGLE_ASC',
          direction: 'LONG',
          entry: currentPrice,
          stop: support - atr * 0.5,
          target1: resistance + (resistance - currentPrice) * 0.5,
          target2: resistance + (resistance - currentPrice),
          score: 0.65,
          confidence: 0.6,
          touches: lastHighs.length,
          pivotHighs: lastHighs,
          pivotLows: lastLows,
          pivotHighIdxs: pivots.highIdxs.slice(-3),
          pivotLowIdxs: pivots.lowIdxs.slice(-3),
        };
      }
    }
    
    // Descending triangle: falling highs, flat lows
    if (highSlope < -atr * 0.05 && Math.abs(lowSlope) < atr * 0.1) {
      const support = Math.min(...lastLows);
      const resistance = lastHighs[lastHighs.length - 1];
      const riskR = (resistance - currentPrice) / atr;
      
      if (riskR > 0.5 && riskR < 3) {
        return {
          scenarioId: uuid(),
          patternType: 'TRIANGLE_DESC',
          direction: 'SHORT',
          entry: currentPrice,
          stop: resistance + atr * 0.5,
          target1: support - (currentPrice - support) * 0.5,
          target2: support - (currentPrice - support),
          score: 0.65,
          confidence: 0.6,
          touches: lastLows.length,
          pivotHighs: lastHighs,
          pivotLows: lastLows,
          pivotHighIdxs: pivots.highIdxs.slice(-3),
          pivotLowIdxs: pivots.lowIdxs.slice(-3),
        };
      }
    }
    
    return null;
  }

  /**
   * Detect channel pattern
   */
  private detectChannel(
    candles: CandleData[],
    pivots: { highs: number[]; lows: number[]; highIdxs: number[]; lowIdxs: number[] },
    atr: number,
    currentPrice: number
  ): ScenarioInput | null {
    if (pivots.highs.length < 2 || pivots.lows.length < 2) return null;
    
    const lastHighs = pivots.highs.slice(-4);
    const lastLows = pivots.lows.slice(-4);
    
    // Check for parallel channel (both slopes similar)
    const highSlope = (lastHighs[lastHighs.length - 1] - lastHighs[0]) / lastHighs.length;
    const lowSlope = (lastLows[lastLows.length - 1] - lastLows[0]) / lastLows.length;
    
    const slopeDiff = Math.abs(highSlope - lowSlope);
    
    if (slopeDiff < atr * 0.2) {
      const avgSlope = (highSlope + lowSlope) / 2;
      const channelWidth = Math.max(...lastHighs) - Math.min(...lastLows);
      
      // Upward channel
      if (avgSlope > atr * 0.03) {
        const support = Math.min(...lastLows);
        const resistance = Math.max(...lastHighs);
        
        // Long at channel bottom
        if (currentPrice < support + channelWidth * 0.3) {
          return {
            scenarioId: uuid(),
            patternType: 'CHANNEL_UP',
            direction: 'LONG',
            entry: currentPrice,
            stop: support - atr * 0.5,
            target1: currentPrice + channelWidth * 0.5,
            target2: resistance,
            score: 0.6,
            confidence: 0.55,
            touches: lastHighs.length + lastLows.length,
            pivotHighs: lastHighs,
            pivotLows: lastLows,
          };
        }
      }
      
      // Downward channel
      if (avgSlope < -atr * 0.03) {
        const support = Math.min(...lastLows);
        const resistance = Math.max(...lastHighs);
        
        // Short at channel top
        if (currentPrice > resistance - channelWidth * 0.3) {
          return {
            scenarioId: uuid(),
            patternType: 'CHANNEL_DOWN',
            direction: 'SHORT',
            entry: currentPrice,
            stop: resistance + atr * 0.5,
            target1: currentPrice - channelWidth * 0.5,
            target2: support,
            score: 0.6,
            confidence: 0.55,
            touches: lastHighs.length + lastLows.length,
            pivotHighs: lastHighs,
            pivotLows: lastLows,
          };
        }
      }
    }
    
    return null;
  }

  /**
   * Detect S/R flip pattern
   */
  private detectSRFlip(
    candles: CandleData[],
    pivots: { highs: number[]; lows: number[]; highIdxs: number[]; lowIdxs: number[] },
    atr: number,
    currentPrice: number
  ): ScenarioInput | null {
    if (pivots.highs.length < 2 || pivots.lows.length < 2) return null;
    
    // Find recent resistance that was broken
    const recentHighs = pivots.highs.slice(-5);
    const avgResistance = recentHighs.reduce((a, b) => a + b, 0) / recentHighs.length;
    
    // Price is now above previous resistance (which becomes support)
    if (currentPrice > avgResistance && currentPrice < avgResistance + atr * 2) {
      return {
        scenarioId: uuid(),
        patternType: 'SR_FLIP_LONG',
        direction: 'LONG',
        entry: currentPrice,
        stop: avgResistance - atr * 0.5,
        target1: currentPrice + (currentPrice - avgResistance) * 2,
        target2: currentPrice + (currentPrice - avgResistance) * 3,
        score: 0.55,
        confidence: 0.5,
        touches: recentHighs.length,
        pivotHighs: recentHighs,
        pivotLows: pivots.lows.slice(-3),
      };
    }
    
    // Find recent support that was broken
    const recentLows = pivots.lows.slice(-5);
    const avgSupport = recentLows.reduce((a, b) => a + b, 0) / recentLows.length;
    
    // Price is now below previous support (which becomes resistance)
    if (currentPrice < avgSupport && currentPrice > avgSupport - atr * 2) {
      return {
        scenarioId: uuid(),
        patternType: 'SR_FLIP_SHORT',
        direction: 'SHORT',
        entry: currentPrice,
        stop: avgSupport + atr * 0.5,
        target1: currentPrice - (avgSupport - currentPrice) * 2,
        target2: currentPrice - (avgSupport - currentPrice) * 3,
        score: 0.55,
        confidence: 0.5,
        touches: recentLows.length,
        pivotHighs: pivots.highs.slice(-3),
        pivotLows: recentLows,
      };
    }
    
    return null;
  }

  /**
   * Calculate ATR
   */
  private calculateATR(candles: CandleData[], period: number = 14): number {
    if (candles.length < period + 1) {
      return (candles[candles.length - 1].high - candles[candles.length - 1].low);
    }
    
    let atr = 0;
    for (let i = candles.length - period; i < candles.length; i++) {
      const c = candles[i];
      const prevC = candles[i - 1];
      const tr = Math.max(
        c.high - c.low,
        Math.abs(c.high - prevC.close),
        Math.abs(c.low - prevC.close)
      );
      atr += tr;
    }
    
    return atr / period;
  }

  /**
   * Determine data split based on timestamp
   */
  private determineSplit(ts: number): 'train' | 'val' | 'test' {
    const date = new Date(ts);
    const year = date.getFullYear();
    
    if (year <= 2022) return 'train';
    if (year === 2023) return 'val';
    return 'test'; // 2024+
  }

  /**
   * Update progress in database
   */
  private async updateProgress(
    runId: string,
    asset: string,
    timeframe: string,
    update: Partial<BatchProgress>
  ): Promise<void> {
    await this.progressCol.updateOne(
      { runId, asset, timeframe },
      { $set: update }
    );
  }

  /**
   * Get progress for a run
   */
  async getProgress(runId: string): Promise<BatchProgress[]> {
    return this.progressCol.find({ runId }).toArray() as any;
  }

  /**
   * Get dataset stats
   */
  async getDatasetStats(): Promise<{
    totalRows: number;
    bySplit: Record<string, number>;
    byAsset: Record<string, number>;
    byPattern: Record<string, number>;
    entryHitRate: number;
    avgR: number;
  }> {
    const totalRows = await this.datasetCol.countDocuments();
    
    // By split
    const splitAgg = await this.datasetCol.aggregate([
      { $group: { _id: '$split', count: { $sum: 1 } } }
    ]).toArray();
    const bySplit: Record<string, number> = {};
    for (const s of splitAgg) {
      bySplit[s._id || 'unknown'] = s.count;
    }
    
    // By asset
    const assetAgg = await this.datasetCol.aggregate([
      { $group: { _id: '$asset', count: { $sum: 1 } } }
    ]).toArray();
    const byAsset: Record<string, number> = {};
    for (const a of assetAgg) {
      byAsset[a._id || 'unknown'] = a.count;
    }
    
    // By pattern
    const patternAgg = await this.datasetCol.aggregate([
      { $group: { _id: '$patternType', count: { $sum: 1 } } }
    ]).toArray();
    const byPattern: Record<string, number> = {};
    for (const p of patternAgg) {
      byPattern[p._id || 'unknown'] = p.count;
    }
    
    // Entry hit rate
    const entryHitAgg = await this.datasetCol.aggregate([
      { $group: { 
        _id: null, 
        totalEntryHit: { $sum: '$labels.label_entry_hit' },
        total: { $sum: 1 },
        avgR: { $avg: '$labels.label_r_multiple' }
      }}
    ]).toArray();
    
    const entryHitRate = entryHitAgg[0] ? 
      (entryHitAgg[0].totalEntryHit / entryHitAgg[0].total) : 0;
    const avgR = entryHitAgg[0]?.avgR || 0;
    
    return {
      totalRows,
      bySplit,
      byAsset,
      byPattern,
      entryHitRate,
      avgR,
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createBatchSimulationService(db: Db): BatchSimulationService {
  return new BatchSimulationService(db);
}
