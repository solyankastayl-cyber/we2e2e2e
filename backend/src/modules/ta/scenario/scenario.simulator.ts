/**
 * P3.1 — Market Scenario Simulator
 * 
 * Monte Carlo simulation of future price paths.
 * Calculates probability distribution of outcomes.
 */

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface SimulatorConfig {
  numPaths: number;           // Number of Monte Carlo paths
  maxBars: number;            // Maximum bars to simulate
  volatilityRegimes: boolean; // Use regime-specific volatility
}

export const DEFAULT_SIMULATOR_CONFIG: SimulatorConfig = {
  numPaths: 1000,
  maxBars: 50,
  volatilityRegimes: true,
};

export interface SimulationInput {
  currentPrice: number;
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  direction: 'LONG' | 'SHORT';
  volatility: number;         // Daily volatility (e.g., 0.02 for 2%)
  drift?: number;             // Expected drift
  regime?: 'LOW' | 'MEDIUM' | 'HIGH';
}

export interface PathResult {
  hitTarget1: boolean;
  hitTarget2: boolean;
  hitStop: boolean;
  timeout: boolean;
  exitPrice: number;
  exitBar: number;
  rMultiple: number;
  mfe: number;                // Max favorable excursion
  mae: number;                // Max adverse excursion
}

export interface SimulationResult {
  numPaths: number;
  
  // Probabilities
  pTarget1: number;
  pTarget2: number;
  pStop: number;
  pTimeout: number;
  
  // Expected values
  expectedR: number;
  expectedRGivenEntry: number;
  
  // Distribution
  rDistribution: {
    percentile: number;
    value: number;
  }[];
  
  // Path statistics
  medianExitBar: number;
  avgMFE: number;
  avgMAE: number;
  
  // Confidence
  confidence: number;
  
  // Scenario EV
  scenarioEV: number;
}

// ═══════════════════════════════════════════════════════════════
// SIMULATOR
// ═══════════════════════════════════════════════════════════════

export class ScenarioSimulator {
  private config: SimulatorConfig;
  
  constructor(config: SimulatorConfig = DEFAULT_SIMULATOR_CONFIG) {
    this.config = config;
  }
  
  /**
   * Simulate scenario and return probability distribution
   */
  simulate(input: SimulationInput): SimulationResult {
    const { numPaths, maxBars } = this.config;
    const paths: PathResult[] = [];
    
    // Adjust volatility for regime
    const volatility = this.adjustVolatility(input.volatility, input.regime);
    
    // Run Monte Carlo simulation
    for (let i = 0; i < numPaths; i++) {
      const path = this.simulatePath(input, volatility, maxBars);
      paths.push(path);
    }
    
    return this.aggregateResults(paths, input);
  }
  
  /**
   * Simulate single price path
   */
  private simulatePath(
    input: SimulationInput,
    volatility: number,
    maxBars: number
  ): PathResult {
    const { currentPrice, entry, stop, target1, target2, direction, drift = 0 } = input;
    
    let price = currentPrice;
    const risk = Math.abs(entry - stop);
    let mfe = 0;
    let mae = 0;
    let exitBar = maxBars;
    let exitPrice = price;
    let hitTarget1 = false;
    let hitTarget2 = false;
    let hitStop = false;
    let timeout = true;
    
    // Simulate bar by bar
    for (let bar = 0; bar < maxBars; bar++) {
      // Generate random return using GBM
      const returns = this.generateReturn(volatility, drift);
      price = price * (1 + returns);
      
      // Generate high/low within bar
      const barRange = Math.abs(returns) + volatility * Math.abs(this.normalRandom()) * 0.5;
      const high = price * (1 + barRange * 0.5);
      const low = price * (1 - barRange * 0.5);
      
      // Track MFE/MAE
      if (direction === 'LONG') {
        const favorable = (high - entry) / risk;
        const adverse = (entry - low) / risk;
        if (favorable > mfe) mfe = favorable;
        if (adverse > mae) mae = adverse;
        
        // Check stop
        if (low <= stop) {
          hitStop = true;
          exitPrice = stop;
          exitBar = bar;
          timeout = false;
          break;
        }
        
        // Check targets
        if (target2 && high >= target2) {
          hitTarget2 = true;
          hitTarget1 = true;
          exitPrice = target2;
          exitBar = bar;
          timeout = false;
          break;
        }
        
        if (high >= target1) {
          hitTarget1 = true;
          // Partial exit, continue with trailing
          if (!target2) {
            exitPrice = target1;
            exitBar = bar;
            timeout = false;
            break;
          }
        }
      } else {
        // SHORT
        const favorable = (entry - low) / risk;
        const adverse = (high - entry) / risk;
        if (favorable > mfe) mfe = favorable;
        if (adverse > mae) mae = adverse;
        
        // Check stop
        if (high >= stop) {
          hitStop = true;
          exitPrice = stop;
          exitBar = bar;
          timeout = false;
          break;
        }
        
        // Check targets
        if (target2 && low <= target2) {
          hitTarget2 = true;
          hitTarget1 = true;
          exitPrice = target2;
          exitBar = bar;
          timeout = false;
          break;
        }
        
        if (low <= target1) {
          hitTarget1 = true;
          if (!target2) {
            exitPrice = target1;
            exitBar = bar;
            timeout = false;
            break;
          }
        }
      }
    }
    
    // Calculate R multiple
    const rMultiple = direction === 'LONG'
      ? (exitPrice - entry) / risk
      : (entry - exitPrice) / risk;
    
    return {
      hitTarget1,
      hitTarget2,
      hitStop,
      timeout,
      exitPrice,
      exitBar,
      rMultiple,
      mfe,
      mae,
    };
  }
  
  /**
   * Generate return using Geometric Brownian Motion
   */
  private generateReturn(volatility: number, drift: number): number {
    const dt = 1; // Daily
    const z = this.normalRandom();
    return drift * dt + volatility * Math.sqrt(dt) * z;
  }
  
  /**
   * Normal distribution random using Box-Muller
   */
  private normalRandom(): number {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
  }
  
  /**
   * Adjust volatility based on regime
   */
  private adjustVolatility(baseVol: number, regime?: 'LOW' | 'MEDIUM' | 'HIGH'): number {
    if (!this.config.volatilityRegimes) return baseVol;
    
    switch (regime) {
      case 'LOW': return baseVol * 0.7;
      case 'HIGH': return baseVol * 1.5;
      default: return baseVol;
    }
  }
  
  /**
   * Aggregate path results
   */
  private aggregateResults(
    paths: PathResult[],
    input: SimulationInput
  ): SimulationResult {
    const n = paths.length;
    
    // Count outcomes
    const target1Hits = paths.filter(p => p.hitTarget1).length;
    const target2Hits = paths.filter(p => p.hitTarget2).length;
    const stopHits = paths.filter(p => p.hitStop).length;
    const timeouts = paths.filter(p => p.timeout).length;
    
    // Probabilities
    const pTarget1 = target1Hits / n;
    const pTarget2 = target2Hits / n;
    const pStop = stopHits / n;
    const pTimeout = timeouts / n;
    
    // Expected R
    const rValues = paths.map(p => p.rMultiple).sort((a, b) => a - b);
    const expectedR = rValues.reduce((a, b) => a + b, 0) / n;
    
    // Expected R given entry (exclude no-entry scenarios)
    const entryPaths = paths.filter(p => !p.timeout || p.hitTarget1 || p.hitStop);
    const expectedRGivenEntry = entryPaths.length > 0
      ? entryPaths.reduce((s, p) => s + p.rMultiple, 0) / entryPaths.length
      : expectedR;
    
    // R distribution percentiles
    const percentiles = [5, 10, 25, 50, 75, 90, 95];
    const rDistribution = percentiles.map(p => ({
      percentile: p,
      value: rValues[Math.floor(p / 100 * n)] || 0,
    }));
    
    // Path statistics
    const exitBars = paths.map(p => p.exitBar);
    const medianExitBar = exitBars.sort((a, b) => a - b)[Math.floor(n / 2)];
    const avgMFE = paths.reduce((s, p) => s + p.mfe, 0) / n;
    const avgMAE = paths.reduce((s, p) => s + p.mae, 0) / n;
    
    // Confidence based on convergence
    const stdR = Math.sqrt(
      rValues.reduce((s, r) => s + Math.pow(r - expectedR, 2), 0) / n
    );
    const confidence = Math.max(0, Math.min(1, 1 - stdR / 3));
    
    // Scenario EV
    const risk = Math.abs(input.entry - input.stop);
    const reward1 = Math.abs(input.target1 - input.entry);
    const rr1 = reward1 / risk;
    
    const scenarioEV = pTarget1 * rr1 - pStop * 1 + pTimeout * (expectedR * 0.5);
    
    return {
      numPaths: n,
      pTarget1,
      pTarget2,
      pStop,
      pTimeout,
      expectedR,
      expectedRGivenEntry,
      rDistribution,
      medianExitBar,
      avgMFE,
      avgMAE,
      confidence,
      scenarioEV,
    };
  }
  
  /**
   * Generate probability bands for projection
   */
  generateProjectionBands(
    currentPrice: number,
    volatility: number,
    bars: number,
    regime?: 'LOW' | 'MEDIUM' | 'HIGH'
  ): {
    bar: number;
    median: number;
    p10: number;
    p90: number;
    p25: number;
    p75: number;
  }[] {
    const vol = this.adjustVolatility(volatility, regime);
    const bands: {
      bar: number;
      median: number;
      p10: number;
      p90: number;
      p25: number;
      p75: number;
    }[] = [];
    
    // Generate paths
    const paths: number[][] = [];
    for (let i = 0; i < 500; i++) {
      const path: number[] = [currentPrice];
      let price = currentPrice;
      
      for (let b = 0; b < bars; b++) {
        price = price * (1 + this.generateReturn(vol, 0));
        path.push(price);
      }
      
      paths.push(path);
    }
    
    // Calculate percentiles at each bar
    for (let b = 0; b <= bars; b++) {
      const prices = paths.map(p => p[b]).sort((a, b) => a - b);
      const n = prices.length;
      
      bands.push({
        bar: b,
        median: prices[Math.floor(n * 0.5)],
        p10: prices[Math.floor(n * 0.1)],
        p90: prices[Math.floor(n * 0.9)],
        p25: prices[Math.floor(n * 0.25)],
        p75: prices[Math.floor(n * 0.75)],
      });
    }
    
    return bands;
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createScenarioSimulator(
  config?: Partial<SimulatorConfig>
): ScenarioSimulator {
  return new ScenarioSimulator({
    ...DEFAULT_SIMULATOR_CONFIG,
    ...config,
  });
}
