/**
 * P1.9 — Metrics Engine
 * 
 * Calculate backtest metrics:
 * - win rate, avg R, profit factor
 * - expectancy
 * - drawdown
 * - EV correlation
 */

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface TradeForMetrics {
  entryHit: boolean;
  rMultiple: number;
  ev_after_ml: number;
  ev_before_ml: number;
}

export interface MetricsResult {
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
}

// ═══════════════════════════════════════════════════════════════
// METRICS ENGINE
// ═══════════════════════════════════════════════════════════════

export class MetricsEngine {
  /**
   * Calculate all metrics from trades
   */
  calculate(trades: TradeForMetrics[]): MetricsResult {
    if (trades.length === 0) {
      return this.emptyMetrics();
    }
    
    const entryHits = trades.filter(t => t.entryHit);
    const wins = entryHits.filter(t => t.rMultiple > 0);
    const losses = entryHits.filter(t => t.rMultiple < 0);
    
    // Entry hit rate
    const entryHitRate = entryHits.length / trades.length;
    
    // Win rate (among entry hits)
    const winRate = entryHits.length > 0 ? wins.length / entryHits.length : 0;
    
    // R statistics
    const rValues = entryHits.map(t => t.rMultiple).sort((a, b) => a - b);
    const avgR = rValues.length > 0 
      ? rValues.reduce((a, b) => a + b, 0) / rValues.length 
      : 0;
    const medianR = this.median(rValues);
    const p90R = this.percentile(rValues, 90);
    
    // Profit factor
    const profitFactor = this.profitFactor(wins, losses);
    
    // Expectancy
    const expectancy = this.expectancy(avgR, winRate);
    
    // Max drawdown
    const maxDrawdown = this.maxDrawdown(entryHits);
    
    // EV correlation
    const evCorrelation = this.correlation(
      trades.map(t => t.ev_after_ml),
      trades.map(t => t.rMultiple)
    );
    
    return {
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
    };
  }
  
  /**
   * Calculate profit factor
   */
  private profitFactor(wins: TradeForMetrics[], losses: TradeForMetrics[]): number {
    const positiveR = wins.reduce((sum, t) => sum + t.rMultiple, 0);
    const negativeR = Math.abs(losses.reduce((sum, t) => sum + t.rMultiple, 0));
    
    if (negativeR === 0) {
      return positiveR > 0 ? 999 : 0;
    }
    
    return positiveR / negativeR;
  }
  
  /**
   * Calculate expectancy
   * E = avgR * winRate - (1 - winRate)
   */
  private expectancy(avgR: number, winRate: number): number {
    return avgR * winRate - (1 - winRate);
  }
  
  /**
   * Calculate max drawdown in R
   */
  private maxDrawdown(trades: TradeForMetrics[]): number {
    let equity = 0;
    let peak = 0;
    let maxDD = 0;
    
    for (const trade of trades) {
      equity += trade.rMultiple;
      if (equity > peak) {
        peak = equity;
      }
      const dd = peak - equity;
      if (dd > maxDD) {
        maxDD = dd;
      }
    }
    
    return maxDD;
  }
  
  /**
   * Calculate Pearson correlation
   */
  private correlation(x: number[], y: number[]): number {
    if (x.length !== y.length || x.length < 2) return 0;
    
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
   * Calculate median
   */
  private median(values: number[]): number {
    if (values.length === 0) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 0
      ? (sorted[mid - 1] + sorted[mid]) / 2
      : sorted[mid];
  }
  
  /**
   * Calculate percentile
   */
  private percentile(values: number[], p: number): number {
    if (values.length === 0) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const idx = Math.floor((p / 100) * sorted.length);
    return sorted[Math.min(idx, sorted.length - 1)];
  }
  
  /**
   * Empty metrics
   */
  private emptyMetrics(): MetricsResult {
    return {
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
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// CALIBRATION ENGINE
// ═══════════════════════════════════════════════════════════════

export interface CalibrationInput {
  pEntry: number;
  entryHit: boolean;
  rMultiple: number;
  evAfterML: number;
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

export interface CalibrationReport {
  bins: CalibrationBin[];
  ece: number;      // Expected Calibration Error
  brier: number;    // Brier score
  isCalibrated: boolean;
}

export class CalibrationEngine {
  private binEdges = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
  
  /**
   * Calculate calibration report
   */
  calculate(inputs: CalibrationInput[]): CalibrationReport {
    if (inputs.length === 0) {
      return {
        bins: [],
        ece: 0,
        brier: 0,
        isCalibrated: false,
      };
    }
    
    const bins = this.binData(inputs);
    const ece = this.calculateECE(bins, inputs.length);
    const brier = this.calculateBrier(inputs);
    
    return {
      bins,
      ece,
      brier,
      isCalibrated: ece < 0.1, // Good calibration if ECE < 0.1
    };
  }
  
  /**
   * Bin data by p_entry
   */
  private binData(inputs: CalibrationInput[]): CalibrationBin[] {
    const bins: CalibrationBin[] = [];
    
    for (let i = 0; i < this.binEdges.length - 1; i++) {
      const binMin = this.binEdges[i];
      const binMax = this.binEdges[i + 1];
      
      const binInputs = inputs.filter(
        inp => inp.pEntry >= binMin && inp.pEntry < binMax
      );
      
      if (binInputs.length === 0) {
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
      
      const predictedEntry = binInputs.reduce((s, i) => s + i.pEntry, 0) / binInputs.length;
      const actualEntry = binInputs.filter(i => i.entryHit).length / binInputs.length;
      const avgRealizedR = binInputs.reduce((s, i) => s + i.rMultiple, 0) / binInputs.length;
      const avgEV = binInputs.reduce((s, i) => s + i.evAfterML, 0) / binInputs.length;
      
      bins.push({
        binMin,
        binMax,
        count: binInputs.length,
        predictedEntry,
        actualEntry,
        avgRealizedR,
        avgEV,
      });
    }
    
    return bins;
  }
  
  /**
   * Calculate Expected Calibration Error
   * ECE = Σ (binWeight * |predicted - actual|)
   */
  private calculateECE(bins: CalibrationBin[], totalCount: number): number {
    let ece = 0;
    
    for (const bin of bins) {
      if (bin.count === 0) continue;
      const weight = bin.count / totalCount;
      const error = Math.abs(bin.predictedEntry - bin.actualEntry);
      ece += weight * error;
    }
    
    return ece;
  }
  
  /**
   * Calculate Brier score
   * Brier = mean((pEntry - entryHit)^2)
   */
  private calculateBrier(inputs: CalibrationInput[]): number {
    if (inputs.length === 0) return 0;
    
    const sum = inputs.reduce((s, i) => {
      const entryHitNum = i.entryHit ? 1 : 0;
      return s + Math.pow(i.pEntry - entryHitNum, 2);
    }, 0);
    
    return sum / inputs.length;
  }
}

// ═══════════════════════════════════════════════════════════════
// SINGLETON INSTANCES
// ═══════════════════════════════════════════════════════════════

export const metricsEngine = new MetricsEngine();
export const calibrationEngine = new CalibrationEngine();
