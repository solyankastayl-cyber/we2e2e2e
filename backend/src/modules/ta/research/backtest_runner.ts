/**
 * P1.9 — Backtest Runner (Research Layer)
 * 
 * No lookahead backtest with full metrics:
 * - win rate, avg R, profit factor
 * - drawdown
 * - EV correlation
 * - calibration
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuid } from 'uuid';
import { createDecisionEngine, DecisionContext, CandleData, ScenarioInput } from '../decision/decision.engine.js';
import { evaluateOutcomeSimple, OutcomeInput } from '../decision/outcome_evaluator.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface BacktestConfig {
  assets: string[];
  timeframes: string[];
  from: string;
  to: string;
  windowSize?: number;
}

export interface BacktestRun {
  runId: string;
  assets: string[];
  timeframes: string[];
  from: string;
  to: string;
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  createdAt: Date;
  finishedAt?: Date;
  error?: string;
}

export interface BacktestTrade {
  runId: string;
  tradeId: string;
  asset: string;
  timeframe: string;
  openTs: number;
  closeTs: number;
  scenarioId: string;
  patternTypes: string[];
  direction: 'LONG' | 'SHORT';
  p_entry: number;
  r_expected: number;
  ev_before_ml: number;
  ev_after_ml: number;
  entryHit: boolean;
  exitReason: string;
  rMultiple: number;
  mfeR: number;
  maeR: number;
}

export interface BacktestMetrics {
  runId: string;
  trades: number;
  entryHitRate: number;
  winRate: number;
  avgR: number;
  medianR: number;
  p90R: number;
  profitFactor: number;
  expectancy: number;
  maxDrawdown: number;
  evCorrelation: number;
  evUplift: number;
}

export interface CalibrationBin {
  binMin: number;
  binMax: number;
  count: number;
  predictedEntry: number;
  actualEntry: number;
  avgRealizedR: number;
  avgEV: number;
}

export interface BacktestReport {
  runId: string;
  metrics: BacktestMetrics;
  calibration: CalibrationBin[];
  patternBreakdown: Record<string, {
    count: number;
    winRate: number;
    avgR: number;
    profitFactor: number;
  }>;
  regimeBreakdown: Record<string, {
    count: number;
    winRate: number;
    avgR: number;
  }>;
}

// ═══════════════════════════════════════════════════════════════
// COLLECTIONS
// ═══════════════════════════════════════════════════════════════

const COLLECTION_CANDLES = 'ta_candles';
const COLLECTION_RUNS = 'ta_backtest_runs';
const COLLECTION_TRADES = 'ta_backtest_trades';
const COLLECTION_METRICS = 'ta_backtest_metrics';

// ═══════════════════════════════════════════════════════════════
// BACKTEST RUNNER SERVICE
// ═══════════════════════════════════════════════════════════════

export class BacktestRunnerService {
  private db: Db;
  private candlesCol: Collection;
  private runsCol: Collection;
  private tradesCol: Collection;
  private metricsCol: Collection;

  constructor(db: Db) {
    this.db = db;
    this.candlesCol = db.collection(COLLECTION_CANDLES);
    this.runsCol = db.collection(COLLECTION_RUNS);
    this.tradesCol = db.collection(COLLECTION_TRADES);
    this.metricsCol = db.collection(COLLECTION_METRICS);
  }

  /**
   * Run backtest
   */
  async runBacktest(config: BacktestConfig): Promise<{ runId: string; status: string }> {
    const runId = uuid();
    const windowSize = config.windowSize || 300;
    
    // Create run record
    const run: BacktestRun = {
      runId,
      assets: config.assets,
      timeframes: config.timeframes,
      from: config.from,
      to: config.to,
      status: 'RUNNING',
      createdAt: new Date(),
    };
    
    await this.runsCol.insertOne(run);
    
    console.log(`[Backtest] Starting run ${runId}`);
    
    try {
      const trades: BacktestTrade[] = [];
      const decisionEngine = createDecisionEngine(this.db);
      
      for (const asset of config.assets) {
        for (const tf of config.timeframes) {
          console.log(`[Backtest] Processing ${asset}/${tf}`);
          
          // Load candles
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
          
          if (candles.length < windowSize + 50) {
            console.log(`[Backtest] Not enough candles for ${asset}/${tf}`);
            continue;
          }
          
          // Step through candles
          for (let t = windowSize; t < candles.length - 50; t++) {
            const windowCandles = candles.slice(t - windowSize, t + 1);
            const currentCandle = candles[t];
            
            const candleData: CandleData[] = windowCandles.map(c => ({
              openTime: c.openTime,
              open: c.open,
              high: c.high,
              low: c.low,
              close: c.close,
              volume: c.volume || 0,
            }));
            
            const atr = this.calculateATR(candleData, 14);
            const scenarios = await this.detectPatterns(candleData, atr, currentCandle.close);
            
            if (scenarios.length === 0) continue;
            
            const ctx: DecisionContext = {
              asset,
              timeframe: tf,
              timestamp: new Date(currentCandle.openTime),
              candles: candleData,
              currentPrice: currentCandle.close,
              atr,
              scenarios,
            };
            
            const decisionPack = await decisionEngine.computeDecision(ctx);
            
            // Take top scenario only
            const topScenario = decisionPack.topScenario;
            if (!topScenario) continue;
            
            // Evaluate outcome
            const futureCandles = candles.slice(t + 1, Math.min(t + 101, candles.length));
            if (futureCandles.length < 10) continue;
            
            const outcomeInput: OutcomeInput = {
              entry: topScenario.entry,
              stop: topScenario.stop,
              target1: topScenario.target1,
              target2: topScenario.target2,
              direction: topScenario.direction,
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
            
            const trade: BacktestTrade = {
              runId,
              tradeId: uuid(),
              asset,
              timeframe: tf,
              openTs: currentCandle.openTime,
              closeTs: outcome.closeTs,
              scenarioId: topScenario.scenarioId,
              patternTypes: [topScenario.patternType],
              direction: topScenario.direction,
              p_entry: topScenario.pEntry,
              r_expected: topScenario.rExpected,
              ev_before_ml: topScenario.evBeforeML,
              ev_after_ml: topScenario.evAfterML,
              entryHit: outcome.entryHit,
              exitReason: outcome.exitReason,
              rMultiple: outcome.rMultiple,
              mfeR: outcome.mfeR,
              maeR: outcome.maeR,
            };
            
            trades.push(trade);
            
            // Skip ahead to avoid overlapping trades
            t += 10;
          }
        }
      }
      
      // Store trades
      if (trades.length > 0) {
        await this.tradesCol.insertMany(trades);
      }
      
      // Calculate and store metrics
      const metrics = this.calculateMetrics(runId, trades);
      await this.metricsCol.insertOne(metrics);
      
      // Update run status
      await this.runsCol.updateOne(
        { runId },
        { $set: { status: 'DONE', finishedAt: new Date() } }
      );
      
      console.log(`[Backtest] Completed ${runId}: ${trades.length} trades`);
      
      return { runId, status: 'DONE' };
      
    } catch (error) {
      await this.runsCol.updateOne(
        { runId },
        { $set: { status: 'FAILED', error: (error as Error).message, finishedAt: new Date() } }
      );
      throw error;
    }
  }

  /**
   * Get backtest status
   */
  async getStatus(runId: string): Promise<BacktestRun | null> {
    return this.runsCol.findOne({ runId }) as any;
  }

  /**
   * Get backtest report
   */
  async getReport(runId: string): Promise<BacktestReport | null> {
    const run = await this.runsCol.findOne({ runId });
    if (!run) return null;
    
    const trades = await this.tradesCol.find({ runId }).toArray() as unknown as BacktestTrade[];
    
    if (trades.length === 0) {
      return {
        runId,
        metrics: this.emptyMetrics(runId),
        calibration: [],
        patternBreakdown: {},
        regimeBreakdown: {},
      };
    }
    
    const metrics = this.calculateMetrics(runId, trades);
    const calibration = this.calculateCalibration(trades);
    const patternBreakdown = this.calculatePatternBreakdown(trades);
    const regimeBreakdown = {}; // TODO: Add regime info to trades
    
    return {
      runId,
      metrics,
      calibration,
      patternBreakdown,
      regimeBreakdown,
    };
  }

  /**
   * Calculate metrics from trades
   */
  private calculateMetrics(runId: string, trades: BacktestTrade[]): BacktestMetrics {
    if (trades.length === 0) return this.emptyMetrics(runId);
    
    const entryHits = trades.filter(t => t.entryHit);
    const wins = entryHits.filter(t => t.rMultiple > 0);
    const losses = entryHits.filter(t => t.rMultiple < 0);
    
    const entryHitRate = entryHits.length / trades.length;
    const winRate = entryHits.length > 0 ? wins.length / entryHits.length : 0;
    
    const rValues = entryHits.map(t => t.rMultiple).sort((a, b) => a - b);
    const avgR = rValues.length > 0 ? rValues.reduce((a, b) => a + b, 0) / rValues.length : 0;
    const medianR = rValues.length > 0 ? rValues[Math.floor(rValues.length / 2)] : 0;
    const p90R = rValues.length > 0 ? rValues[Math.floor(rValues.length * 0.9)] : 0;
    
    // Profit factor
    const positiveR = wins.reduce((sum, t) => sum + t.rMultiple, 0);
    const negativeR = Math.abs(losses.reduce((sum, t) => sum + t.rMultiple, 0));
    const profitFactor = negativeR > 0 ? positiveR / negativeR : (positiveR > 0 ? 999 : 0);
    
    // Expectancy
    const expectancy = avgR * winRate - (1 - winRate);
    
    // Max drawdown
    let equity = 0;
    let peak = 0;
    let maxDrawdown = 0;
    for (const trade of entryHits) {
      equity += trade.rMultiple;
      if (equity > peak) peak = equity;
      const dd = peak - equity;
      if (dd > maxDrawdown) maxDrawdown = dd;
    }
    
    // EV correlation
    const evCorrelation = this.calculateCorrelation(
      trades.map(t => t.ev_after_ml),
      trades.map(t => t.rMultiple)
    );
    
    // EV uplift (comparing ML vs no ML)
    const evUplift = this.calculateCorrelation(
      trades.map(t => t.ev_after_ml),
      trades.map(t => t.rMultiple)
    ) - this.calculateCorrelation(
      trades.map(t => t.ev_before_ml),
      trades.map(t => t.rMultiple)
    );
    
    return {
      runId,
      trades: trades.length,
      entryHitRate,
      winRate,
      avgR,
      medianR,
      p90R,
      profitFactor,
      expectancy,
      maxDrawdown,
      evCorrelation,
      evUplift,
    };
  }

  /**
   * Calculate calibration bins
   */
  private calculateCalibration(trades: BacktestTrade[]): CalibrationBin[] {
    const bins: CalibrationBin[] = [];
    const binEdges = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
    
    for (let i = 0; i < binEdges.length - 1; i++) {
      const binMin = binEdges[i];
      const binMax = binEdges[i + 1];
      
      const binTrades = trades.filter(
        t => t.p_entry >= binMin && t.p_entry < binMax
      );
      
      if (binTrades.length === 0) {
        bins.push({
          binMin,
          binMax,
          count: 0,
          predictedEntry: (binMin + binMax) / 2,
          actualEntry: 0,
          avgRealizedR: 0,
          avgEV: 0,
        });
        continue;
      }
      
      const predictedEntry = binTrades.reduce((s, t) => s + t.p_entry, 0) / binTrades.length;
      const actualEntry = binTrades.filter(t => t.entryHit).length / binTrades.length;
      const avgRealizedR = binTrades.reduce((s, t) => s + t.rMultiple, 0) / binTrades.length;
      const avgEV = binTrades.reduce((s, t) => s + t.ev_after_ml, 0) / binTrades.length;
      
      bins.push({
        binMin,
        binMax,
        count: binTrades.length,
        predictedEntry,
        actualEntry,
        avgRealizedR,
        avgEV,
      });
    }
    
    return bins;
  }

  /**
   * Calculate pattern breakdown
   */
  private calculatePatternBreakdown(trades: BacktestTrade[]): Record<string, {
    count: number;
    winRate: number;
    avgR: number;
    profitFactor: number;
  }> {
    const breakdown: Record<string, {
      count: number;
      winRate: number;
      avgR: number;
      profitFactor: number;
    }> = {};
    
    // Group by pattern type
    const byPattern = new Map<string, BacktestTrade[]>();
    for (const trade of trades) {
      for (const pt of trade.patternTypes) {
        if (!byPattern.has(pt)) byPattern.set(pt, []);
        byPattern.get(pt)!.push(trade);
      }
    }
    
    for (const [pattern, patternTrades] of byPattern) {
      const entryHits = patternTrades.filter(t => t.entryHit);
      const wins = entryHits.filter(t => t.rMultiple > 0);
      const losses = entryHits.filter(t => t.rMultiple < 0);
      
      const winRate = entryHits.length > 0 ? wins.length / entryHits.length : 0;
      const avgR = entryHits.length > 0 
        ? entryHits.reduce((s, t) => s + t.rMultiple, 0) / entryHits.length 
        : 0;
      
      const positiveR = wins.reduce((s, t) => s + t.rMultiple, 0);
      const negativeR = Math.abs(losses.reduce((s, t) => s + t.rMultiple, 0));
      const profitFactor = negativeR > 0 ? positiveR / negativeR : (positiveR > 0 ? 999 : 0);
      
      breakdown[pattern] = {
        count: patternTrades.length,
        winRate,
        avgR,
        profitFactor,
      };
    }
    
    return breakdown;
  }

  /**
   * Calculate Pearson correlation
   */
  private calculateCorrelation(x: number[], y: number[]): number {
    if (x.length !== y.length || x.length === 0) return 0;
    
    const n = x.length;
    const sumX = x.reduce((a, b) => a + b, 0);
    const sumY = y.reduce((a, b) => a + b, 0);
    const sumXY = x.reduce((sum, xi, i) => sum + xi * y[i], 0);
    const sumX2 = x.reduce((sum, xi) => sum + xi * xi, 0);
    const sumY2 = y.reduce((sum, yi) => sum + yi * yi, 0);
    
    const num = n * sumXY - sumX * sumY;
    const den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
    
    return den === 0 ? 0 : num / den;
  }

  /**
   * Empty metrics
   */
  private emptyMetrics(runId: string): BacktestMetrics {
    return {
      runId,
      trades: 0,
      entryHitRate: 0,
      winRate: 0,
      avgR: 0,
      medianR: 0,
      p90R: 0,
      profitFactor: 0,
      expectancy: 0,
      maxDrawdown: 0,
      evCorrelation: 0,
      evUplift: 0,
    };
  }

  /**
   * Simple pattern detection (reuse from batch_simulation)
   */
  private async detectPatterns(
    candles: CandleData[],
    atr: number,
    currentPrice: number
  ): Promise<ScenarioInput[]> {
    const scenarios: ScenarioInput[] = [];
    const pivots = this.findPivots(candles);
    
    if (pivots.highs.length < 2 || pivots.lows.length < 2) return scenarios;
    
    // Detect ascending triangle
    const lastHighs = pivots.highs.slice(-3);
    const lastLows = pivots.lows.slice(-3);
    
    const highSlope = (lastHighs[lastHighs.length - 1] - lastHighs[0]) / lastHighs.length;
    const lowSlope = (lastLows[lastLows.length - 1] - lastLows[0]) / lastLows.length;
    
    if (Math.abs(highSlope) < atr * 0.1 && lowSlope > atr * 0.05) {
      const resistance = Math.max(...lastHighs);
      const support = lastLows[lastLows.length - 1];
      
      scenarios.push({
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
      });
    }
    
    return scenarios;
  }

  private findPivots(candles: CandleData[]): {
    highs: number[];
    lows: number[];
  } {
    const highs: number[] = [];
    const lows: number[] = [];
    const lookback = 5;
    
    for (let i = lookback; i < candles.length - lookback; i++) {
      let isHigh = true;
      let isLow = true;
      
      for (let j = i - lookback; j <= i + lookback; j++) {
        if (j === i) continue;
        if (candles[j].high >= candles[i].high) isHigh = false;
        if (candles[j].low <= candles[i].low) isLow = false;
      }
      
      if (isHigh) highs.push(candles[i].high);
      if (isLow) lows.push(candles[i].low);
    }
    
    return { highs, lows };
  }

  private calculateATR(candles: CandleData[], period: number = 14): number {
    if (candles.length < period + 1) {
      return candles[candles.length - 1].high - candles[candles.length - 1].low;
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
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createBacktestRunnerService(db: Db): BacktestRunnerService {
  return new BacktestRunnerService(db);
}
