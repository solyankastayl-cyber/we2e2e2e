/**
 * Phase 2.5 — Market Map Service
 * ================================
 * Main service for generating probabilistic market maps
 * 
 * Pipeline:
 *   Digital Twin → Scenario Engine → State Machine → Market Map
 */

import {
  MarketMapResponse,
  MarketBranch,
  MarketMapStats,
  MarketState,
  PathPoint,
} from './market_map.types.js';
import { buildMarketTree, getMainPath } from './market_map.tree.js';

// ═══════════════════════════════════════════════════════════════
// BASE PRICES (for realistic path generation)
// ═══════════════════════════════════════════════════════════════

const BASE_PRICES: Record<string, number> = {
  BTCUSDT: 87000,
  ETHUSDT: 3200,
  SOLUSDT: 145,
  BNBUSDT: 620,
  XRPUSDT: 0.52,
  ADAUSDT: 0.45,
};

// ═══════════════════════════════════════════════════════════════
// STATE DETECTION
// ═══════════════════════════════════════════════════════════════

/**
 * Detect current market state (simplified version)
 * In production, this would integrate with State Engine
 */
export function detectCurrentState(symbol: string): MarketState {
  // Rotate through states based on timestamp for demo
  const states: MarketState[] = [
    'COMPRESSION', 'BREAKOUT', 'EXPANSION', 'RANGE',
    'RETEST', 'CONTINUATION', 'EXHAUSTION'
  ];
  
  const hour = new Date().getHours();
  return states[hour % states.length];
}

// ═══════════════════════════════════════════════════════════════
// SCENARIO DEFINITIONS
// ═══════════════════════════════════════════════════════════════

interface ScenarioTemplate {
  name: string;
  baseProb: number;
  direction: 'BULL' | 'BEAR' | 'NEUTRAL';
  moveMultiplier: number;  // multiplier for ATR
  events: string[];
  fromStates: MarketState[];
}

const SCENARIO_TEMPLATES: ScenarioTemplate[] = [
  {
    name: 'breakout',
    baseProb: 0.35,
    direction: 'BULL',
    moveMultiplier: 2.5,
    events: ['compression_exit', 'momentum_surge', 'expansion'],
    fromStates: ['COMPRESSION', 'RANGE', 'RETEST'],
  },
  {
    name: 'range',
    baseProb: 0.30,
    direction: 'NEUTRAL',
    moveMultiplier: 0.8,
    events: ['oscillation', 'mean_reversion'],
    fromStates: ['COMPRESSION', 'RANGE', 'EXHAUSTION'],
  },
  {
    name: 'fakeout',
    baseProb: 0.15,
    direction: 'BEAR',
    moveMultiplier: 1.5,
    events: ['false_breakout', 'liquidity_sweep', 'reversal'],
    fromStates: ['BREAKOUT', 'EXPANSION'],
  },
  {
    name: 'continuation',
    baseProb: 0.12,
    direction: 'BULL',
    moveMultiplier: 1.8,
    events: ['retest_hold', 'trend_resume'],
    fromStates: ['RETEST', 'CONTINUATION', 'EXPANSION'],
  },
  {
    name: 'reversal',
    baseProb: 0.08,
    direction: 'BEAR',
    moveMultiplier: 2.0,
    events: ['exhaustion_signal', 'trend_break', 'capitulation'],
    fromStates: ['EXHAUSTION', 'EXPANSION'],
  },
];

// ═══════════════════════════════════════════════════════════════
// PATH GENERATION
// ═══════════════════════════════════════════════════════════════

/**
 * Generate price path for a scenario
 */
function generatePath(
  currentPrice: number,
  direction: 'BULL' | 'BEAR' | 'NEUTRAL',
  moveATR: number,
  points: number = 5
): PathPoint[] {
  const path: PathPoint[] = [];
  const now = Date.now();
  const hourMs = 60 * 60 * 1000;
  
  // ATR approximation (2% of price)
  const atr = currentPrice * 0.02;
  const totalMove = atr * moveATR;
  
  let price = currentPrice;
  
  for (let i = 0; i < points; i++) {
    const t = now + (i + 1) * 4 * hourMs;  // 4h intervals
    
    // Calculate step move
    const progress = (i + 1) / points;
    let stepMove: number;
    
    switch (direction) {
      case 'BULL':
        stepMove = totalMove * progress * (1 + Math.random() * 0.2 - 0.1);
        price = currentPrice + stepMove;
        break;
      case 'BEAR':
        stepMove = totalMove * progress * (1 + Math.random() * 0.2 - 0.1);
        price = currentPrice - stepMove;
        break;
      case 'NEUTRAL':
        // Oscillate around current price
        stepMove = atr * Math.sin(progress * Math.PI * 2) * 0.5;
        price = currentPrice + stepMove;
        break;
    }
    
    path.push({
      t,
      price: Math.round(price * 100) / 100,
    });
  }
  
  return path;
}

/**
 * Calculate target price from path
 */
function calculateTarget(
  currentPrice: number,
  direction: 'BULL' | 'BEAR' | 'NEUTRAL',
  moveATR: number
): number {
  const atr = currentPrice * 0.02;
  const move = atr * moveATR;
  
  switch (direction) {
    case 'BULL':
      return Math.round((currentPrice + move) * 100) / 100;
    case 'BEAR':
      return Math.round((currentPrice - move) * 100) / 100;
    default:
      return currentPrice;
  }
}

// ═══════════════════════════════════════════════════════════════
// BRANCH GENERATION
// ═══════════════════════════════════════════════════════════════

/**
 * Generate market branches from current state
 */
function generateBranches(
  symbol: string,
  currentState: MarketState,
  currentPrice: number
): MarketBranch[] {
  const branches: MarketBranch[] = [];
  
  // Filter scenarios applicable to current state
  const applicableScenarios = SCENARIO_TEMPLATES.filter(
    s => s.fromStates.includes(currentState)
  );
  
  // If no scenarios match, use all
  const scenarios = applicableScenarios.length > 0 
    ? applicableScenarios 
    : SCENARIO_TEMPLATES;
  
  // Normalize probabilities
  const totalProb = scenarios.reduce((sum, s) => sum + s.baseProb, 0);
  
  for (const scenario of scenarios) {
    const probability = scenario.baseProb / totalProb;
    
    // Add some randomness for realism
    const adjustedProb = probability * (0.9 + Math.random() * 0.2);
    const adjustedMove = scenario.moveMultiplier * (0.8 + Math.random() * 0.4);
    
    const path = generatePath(
      currentPrice,
      scenario.direction,
      adjustedMove
    );
    
    branches.push({
      scenario: scenario.name,
      probability: Math.round(adjustedProb * 100) / 100,
      path,
      target: calculateTarget(currentPrice, scenario.direction, adjustedMove),
      direction: scenario.direction,
      expectedMoveATR: Math.round(adjustedMove * 10) / 10,
      confidence: Math.round((0.5 + adjustedProb * 0.5) * 100) / 100,
      events: scenario.events,
    });
  }
  
  // Sort by probability descending
  branches.sort((a, b) => b.probability - a.probability);
  
  return branches;
}

// ═══════════════════════════════════════════════════════════════
// STATS CALCULATION
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate market map statistics
 */
function calculateStats(branches: MarketBranch[]): MarketMapStats {
  if (branches.length === 0) {
    return {
      dominantScenario: 'unknown',
      dominantProbability: 0,
      uncertainty: 1,
      totalBranches: 0,
      bullishBias: 0,
      avgExpectedMove: 0,
    };
  }
  
  const dominant = branches[0];
  
  // Calculate entropy (uncertainty)
  const probs = branches.map(b => b.probability);
  const entropy = -probs.reduce((sum, p) => {
    if (p > 0) sum += p * Math.log2(p);
    return sum;
  }, 0);
  
  // Normalize entropy to 0..1 (max entropy = log2(n))
  const maxEntropy = Math.log2(branches.length);
  const normalizedEntropy = maxEntropy > 0 ? entropy / maxEntropy : 0;
  
  // Calculate bullish bias
  let bullWeight = 0;
  let bearWeight = 0;
  let totalWeight = 0;
  
  for (const branch of branches) {
    if (branch.direction === 'BULL') {
      bullWeight += branch.probability;
    } else if (branch.direction === 'BEAR') {
      bearWeight += branch.probability;
    }
    totalWeight += branch.probability;
  }
  
  const bullishBias = totalWeight > 0 
    ? (bullWeight - bearWeight) / totalWeight 
    : 0;
  
  // Average expected move
  const avgMove = branches.reduce((sum, b) => sum + b.expectedMoveATR * b.probability, 0);
  
  return {
    dominantScenario: dominant.scenario,
    dominantProbability: dominant.probability,
    uncertainty: Math.round(normalizedEntropy * 100) / 100,
    totalBranches: branches.length,
    bullishBias: Math.round(bullishBias * 100) / 100,
    avgExpectedMove: Math.round(avgMove * 10) / 10,
  };
}

// ═══════════════════════════════════════════════════════════════
// MAIN SERVICE
// ═══════════════════════════════════════════════════════════════

/**
 * Get market map for a symbol
 * Main entry point for the Market Map service
 */
export async function getMarketMap(
  symbol: string,
  timeframe: string = '1d'
): Promise<MarketMapResponse> {
  // Get current price
  const currentPrice = BASE_PRICES[symbol] || 100;
  
  // Detect current state
  const currentState = detectCurrentState(symbol);
  
  // Generate branches
  const branches = generateBranches(symbol, currentState, currentPrice);
  
  // Calculate stats
  const stats = calculateStats(branches);
  
  return {
    symbol,
    timeframe,
    ts: Date.now(),
    currentState,
    currentPrice,
    branches,
    stats,
  };
}

/**
 * Get multiple market maps at once
 */
export async function getBatchMarketMaps(
  symbols: string[],
  timeframe: string = '1d'
): Promise<MarketMapResponse[]> {
  return Promise.all(
    symbols.map(symbol => getMarketMap(symbol, timeframe))
  );
}
