/**
 * D4 — State Computation
 * 
 * Determines current market state based on all intelligence layers
 */

import { 
  MarketStateNode, 
  StateTransitionResult,
  StateEngineConfig,
  DEFAULT_STATE_CONFIG,
  ALLOWED_TRANSITIONS,
} from './state.types.js';

interface ContextData {
  trendDirection?: string;
  trendStrength?: number;
  bullishScore?: number;
  bearishScore?: number;
}

interface MarketStateData {
  state?: string;
  confidence?: number;
}

interface LiquidityData {
  recentSweepUp?: boolean;
  recentSweepDown?: boolean;
  liquidityBias?: string;
}

interface PhysicsData {
  compressionScore?: number;
  pressureScore?: number;
  energyScore?: number;
  releaseProbability?: number;
  exhaustionScore?: number;
  physicsState?: string;
}

interface GraphData {
  currentChain?: Array<{ type: string }>;
  predictedNext?: Array<{ event: string; probability: number }>;
}

/**
 * Determine current market state from all intelligence layers
 */
export function computeCurrentState(
  context: ContextData,
  marketState: MarketStateData,
  liquidity: LiquidityData,
  physics: PhysicsData,
  graph: GraphData,
  config: StateEngineConfig = DEFAULT_STATE_CONFIG
): { state: MarketStateNode; confidence: number; reason: string } {
  const scores: Record<MarketStateNode, number> = {
    BALANCE: 0,
    COMPRESSION: 0,
    BREAKOUT_ATTEMPT: 0,
    EXPANSION: 0,
    EXHAUSTION: 0,
    REVERSAL_ATTEMPT: 0,
  };
  
  let reason = '';
  
  // Check for COMPRESSION
  if (physics.compressionScore && physics.compressionScore > config.compressionThreshold) {
    scores.COMPRESSION += physics.compressionScore * 0.4;
    if (physics.energyScore && physics.energyScore > 0.5) {
      scores.COMPRESSION += 0.2;
    }
    reason = 'high compression + energy buildup';
  }
  
  // Check for BREAKOUT_ATTEMPT
  if (physics.releaseProbability && physics.releaseProbability > config.breakoutThreshold) {
    scores.BREAKOUT_ATTEMPT += physics.releaseProbability * 0.4;
    if (liquidity.recentSweepUp || liquidity.recentSweepDown) {
      scores.BREAKOUT_ATTEMPT += 0.2;
      reason = 'high release probability + liquidity sweep';
    }
  }
  
  // Check for EXPANSION (physics state RELEASE or EXPANSION)
  if (physics.physicsState === 'RELEASE' || physics.physicsState === 'EXPANSION') {
    scores.EXPANSION += 0.5;
    if (context.trendStrength && context.trendStrength > 0.6) {
      scores.EXPANSION += 0.2;
    }
    reason = 'energy release in progress';
  }
  
  // Check for EXHAUSTION
  if (physics.exhaustionScore && physics.exhaustionScore > config.exhaustionThreshold) {
    scores.EXHAUSTION += physics.exhaustionScore * 0.5;
    reason = 'momentum exhaustion detected';
  }
  
  // Check for REVERSAL_ATTEMPT
  if (physics.exhaustionScore && physics.exhaustionScore > 0.5) {
    const hasSweep = liquidity.recentSweepUp || liquidity.recentSweepDown;
    if (hasSweep) {
      scores.REVERSAL_ATTEMPT += 0.4;
      reason = 'exhaustion + liquidity sweep = reversal attempt';
    }
  }
  
  // BALANCE as default/fallback
  scores.BALANCE = 0.3;  // Base score
  if (marketState.state === 'RANGE') {
    scores.BALANCE += 0.3;
  }
  if (!physics.compressionScore || physics.compressionScore < 0.3) {
    scores.BALANCE += 0.2;
  }
  
  // Find highest scoring state
  let maxState: MarketStateNode = 'BALANCE';
  let maxScore = 0;
  
  for (const [state, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score;
      maxState = state as MarketStateNode;
    }
  }
  
  const confidence = Math.min(1, maxScore);
  
  return { state: maxState, confidence, reason: reason || `Default state: ${maxState}` };
}

/**
 * Calculate transition probabilities from current state
 */
export function computeTransitionProbabilities(
  currentState: MarketStateNode,
  physics: PhysicsData,
  liquidity: LiquidityData,
  historicalTransitions?: Map<string, { count: number; probability: number; avgBars: number }>
): Array<{ state: MarketStateNode; probability: number; avgBarsAhead: number }> {
  const allowed = ALLOWED_TRANSITIONS[currentState];
  const results: Array<{ state: MarketStateNode; probability: number; avgBarsAhead: number }> = [];
  
  for (const nextState of allowed) {
    let probability = 0.2;  // Base probability
    let avgBarsAhead = 10;  // Default estimate
    
    // Check historical data
    const key = `${currentState}->${nextState}`;
    if (historicalTransitions?.has(key)) {
      const hist = historicalTransitions.get(key)!;
      probability = hist.probability;
      avgBarsAhead = hist.avgBars;
    } else {
      // Estimate from physics
      switch (nextState) {
        case 'COMPRESSION':
          if (currentState === 'BALANCE') {
            probability = 0.4;
          }
          break;
        case 'BREAKOUT_ATTEMPT':
          if (physics.energyScore && physics.energyScore > 0.6) {
            probability = physics.energyScore * 0.8;
          }
          break;
        case 'EXPANSION':
          if (physics.releaseProbability) {
            probability = physics.releaseProbability * 0.9;
          }
          break;
        case 'EXHAUSTION':
          probability = 0.3;  // Natural progression
          if (physics.exhaustionScore && physics.exhaustionScore > 0.3) {
            probability = physics.exhaustionScore;
          }
          break;
        case 'REVERSAL_ATTEMPT':
          if (liquidity.recentSweepUp || liquidity.recentSweepDown) {
            probability = 0.5;
          }
          break;
        case 'BALANCE':
          probability = 0.25;  // Can always return to balance
          break;
      }
    }
    
    results.push({
      state: nextState,
      probability: Math.min(1, Math.max(0, probability)),
      avgBarsAhead,
    });
  }
  
  // Normalize probabilities
  const total = results.reduce((sum, r) => sum + r.probability, 0);
  if (total > 0) {
    for (const r of results) {
      r.probability = r.probability / total;
    }
  }
  
  // Sort by probability
  results.sort((a, b) => b.probability - a.probability);
  
  return results;
}

/**
 * Find most likely path through states
 */
export function findLikelyPath(
  currentState: MarketStateNode,
  nextProbs: Array<{ state: MarketStateNode; probability: number }>,
  depth: number = 3
): { path: MarketStateNode[]; probability: number } {
  if (depth === 0 || nextProbs.length === 0) {
    return { path: [currentState], probability: 1 };
  }
  
  const bestNext = nextProbs[0];
  if (!bestNext) {
    return { path: [currentState], probability: 1 };
  }
  
  // Simple greedy path (follow highest probability)
  const path: MarketStateNode[] = [currentState];
  let probability = 1;
  let state = currentState;
  
  for (let i = 0; i < depth; i++) {
    const allowed = ALLOWED_TRANSITIONS[state];
    if (allowed.length === 0) break;
    
    // Pick most likely next (simplified)
    const next = allowed[0];
    path.push(next);
    probability *= 0.5;  // Simplified probability decay
    state = next;
  }
  
  return { path, probability };
}

/**
 * Calculate state boost for decision engine
 */
export function computeStateBoost(
  currentState: MarketStateNode,
  patternDirection: 'BULL' | 'BEAR',
  physics: PhysicsData,
  liquidity: LiquidityData
): number {
  let boost = 1.0;
  
  // State-based adjustments
  switch (currentState) {
    case 'COMPRESSION':
      // Compression + high energy = boost continuation patterns
      if (physics.energyScore && physics.energyScore > 0.6) {
        boost = 1.15;
      }
      break;
      
    case 'BREAKOUT_ATTEMPT':
      // Breakout attempt = boost if liquidity aligns
      if (patternDirection === 'BULL' && liquidity.recentSweepDown) {
        boost = 1.2;
      } else if (patternDirection === 'BEAR' && liquidity.recentSweepUp) {
        boost = 1.2;
      }
      break;
      
    case 'EXPANSION':
      // During expansion, continuation patterns are strong
      boost = 1.1;
      break;
      
    case 'EXHAUSTION':
      // Exhaustion = penalize continuation, boost reversal
      boost = 0.85;
      break;
      
    case 'REVERSAL_ATTEMPT':
      // Reversal = depends heavily on direction
      if (physics.exhaustionScore && physics.exhaustionScore > 0.6) {
        boost = 0.9;
      }
      break;
      
    case 'BALANCE':
    default:
      boost = 1.0;
  }
  
  return Math.min(1.3, Math.max(0.7, boost));
}
