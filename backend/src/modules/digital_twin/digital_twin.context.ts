/**
 * DT1 — Twin Context Builder
 * 
 * Collects data from all modules to build unified twin context
 */

import { TwinContext, LiquidityStateType } from './digital_twin.types.js';
import { MarketRegime, RegimeFeatures } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';
import { PhysicsState } from '../market_physics/physics.types.js';
import { MarketBehaviorState, ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// CONTEXT BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Build twin context from module data
 */
export function buildTwinContext(
  asset: string,
  timeframe: string,
  moduleData: {
    regime?: {
      regime: MarketRegime;
      confidence: number;
      probabilities?: Record<MarketRegime, number>;
    };
    state?: {
      currentState: MarketStateNode;
      stateConfidence: number;
      nextStateProbabilities?: Array<{ state: MarketStateNode; probability: number }>;
      stateBoost: number;
    };
    physics?: {
      physicsState: PhysicsState;
      energyScore: number;
      compressionScore: number;
      releaseProbability: number;
      exhaustionScore: number;
      physicsBoost: number;
    };
    liquidity?: {
      liquidityBias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
      recentSweepUp: boolean;
      recentSweepDown: boolean;
      zonesAbove: number;
      zonesBelow: number;
    };
    scenarios?: Array<{
      scenarioId: string;
      direction: ScenarioDirection;
      probability: number;
      confidence: number;
      path: MarketBehaviorState[];
      expectedMoveATR: number;
    }>;
    metabrain?: {
      riskMode: 'CONSERVATIVE' | 'NORMAL' | 'AGGRESSIVE';
      confidenceThreshold: number;
      metaRiskMultiplier: number;
    };
    execution?: {
      portfolioExposure: number;
      openPositions: number;
      portfolioStress: number;
    };
  }
): TwinContext {
  return {
    asset,
    timeframe,
    ts: Date.now(),
    regime: moduleData.regime,
    state: moduleData.state,
    physics: moduleData.physics,
    liquidity: moduleData.liquidity,
    scenarios: moduleData.scenarios,
    metabrain: moduleData.metabrain,
    execution: moduleData.execution
  };
}

// ═══════════════════════════════════════════════════════════════
// MOCK CONTEXT (for testing without live modules)
// ═══════════════════════════════════════════════════════════════

/**
 * Generate mock context for testing
 */
export function buildMockTwinContext(
  asset: string,
  timeframe: string,
  options?: {
    regime?: MarketRegime;
    state?: MarketStateNode;
    physicsState?: PhysicsState;
    direction?: ScenarioDirection;
  }
): TwinContext {
  const regime = options?.regime || 'COMPRESSION';
  const state = options?.state || 'COMPRESSION';
  const physicsState = options?.physicsState || 'COMPRESSION';
  const direction = options?.direction || 'BULL';
  
  return {
    asset,
    timeframe,
    ts: Date.now(),
    
    regime: {
      regime,
      confidence: 0.72,
      probabilities: {
        'COMPRESSION': 0.35,
        'BREAKOUT_PREP': 0.25,
        'TREND_EXPANSION': 0.15,
        'RANGE_ROTATION': 0.10,
        'TREND_CONTINUATION': 0.05,
        'VOLATILITY_EXPANSION': 0.04,
        'LIQUIDITY_HUNT': 0.03,
        'ACCUMULATION': 0.02,
        'DISTRIBUTION': 0.01
      }
    },
    
    state: {
      currentState: state,
      stateConfidence: 0.68,
      nextStateProbabilities: [
        { state: 'BREAKOUT_ATTEMPT', probability: 0.45 },
        { state: 'BALANCE', probability: 0.35 },
        { state: 'COMPRESSION', probability: 0.20 }
      ],
      stateBoost: 1.15
    },
    
    physics: {
      physicsState,
      energyScore: 0.74,
      compressionScore: 0.68,
      releaseProbability: 0.52,
      exhaustionScore: 0.18,
      physicsBoost: 1.12
    },
    
    liquidity: {
      liquidityBias: direction === 'BULL' ? 'BULLISH' : direction === 'BEAR' ? 'BEARISH' : 'NEUTRAL',
      recentSweepUp: false,
      recentSweepDown: direction === 'BULL',
      zonesAbove: 3,
      zonesBelow: 2
    },
    
    scenarios: [
      {
        scenarioId: 'SCN_001',
        direction,
        probability: 0.52,
        confidence: 0.68,
        path: ['COMPRESSION', 'BREAKOUT', 'RETEST', 'EXPANSION'],
        expectedMoveATR: 2.3
      },
      {
        scenarioId: 'SCN_002',
        direction: 'NEUTRAL',
        probability: 0.31,
        confidence: 0.55,
        path: ['COMPRESSION', 'FALSE_BREAKOUT', 'RANGE'],
        expectedMoveATR: 0.8
      },
      {
        scenarioId: 'SCN_003',
        direction: direction === 'BULL' ? 'BEAR' : 'BULL',
        probability: 0.17,
        confidence: 0.42,
        path: ['COMPRESSION', 'BREAKOUT', 'REVERSAL'],
        expectedMoveATR: 1.5
      }
    ],
    
    metabrain: {
      riskMode: 'NORMAL',
      confidenceThreshold: 0.6,
      metaRiskMultiplier: 1.0
    },
    
    execution: {
      portfolioExposure: 0.35,
      openPositions: 2,
      portfolioStress: 0.22
    }
  };
}

// ═══════════════════════════════════════════════════════════════
// CONTEXT VALIDATION
// ═══════════════════════════════════════════════════════════════

/**
 * Validate context has minimum required data
 */
export function validateContext(context: TwinContext): {
  valid: boolean;
  missingModules: string[];
} {
  const missingModules: string[] = [];
  
  if (!context.regime) missingModules.push('regime');
  if (!context.state) missingModules.push('state');
  if (!context.physics) missingModules.push('physics');
  if (!context.liquidity) missingModules.push('liquidity');
  if (!context.scenarios || context.scenarios.length === 0) missingModules.push('scenarios');
  
  return {
    valid: missingModules.length === 0,
    missingModules
  };
}

// ═══════════════════════════════════════════════════════════════
// LIQUIDITY STATE DERIVATION
// ═══════════════════════════════════════════════════════════════

/**
 * Derive strongest liquidity state from context
 */
export function deriveLiquidityState(context: TwinContext): LiquidityStateType {
  if (!context.liquidity) return 'NEUTRAL';
  
  const { recentSweepUp, recentSweepDown, zonesAbove, zonesBelow, liquidityBias } = context.liquidity;
  
  // Recent sweep takes priority
  if (recentSweepDown) return 'SWEEP_LOW';
  if (recentSweepUp) return 'SWEEP_HIGH';
  
  // Equal levels based on zone density
  if (zonesAbove >= 3 && zonesAbove > zonesBelow) return 'EQUAL_HIGHS';
  if (zonesBelow >= 3 && zonesBelow > zonesAbove) return 'EQUAL_LOWS';
  
  return 'NEUTRAL';
}

// ═══════════════════════════════════════════════════════════════
// CONTEXT NORMALIZATION
// ═══════════════════════════════════════════════════════════════

/**
 * Normalize context values to standard ranges
 */
export function normalizeContext(context: TwinContext): TwinContext {
  const normalized = { ...context };
  
  // Normalize physics scores (ensure 0-1)
  if (normalized.physics) {
    normalized.physics = {
      ...normalized.physics,
      energyScore: clamp(normalized.physics.energyScore, 0, 1),
      compressionScore: clamp(normalized.physics.compressionScore, 0, 1),
      releaseProbability: clamp(normalized.physics.releaseProbability, 0, 1),
      exhaustionScore: clamp(normalized.physics.exhaustionScore, 0, 1)
    };
  }
  
  // Normalize scenario probabilities
  if (normalized.scenarios && normalized.scenarios.length > 0) {
    const totalProb = normalized.scenarios.reduce((sum, s) => sum + s.probability, 0);
    if (totalProb > 0 && totalProb !== 1) {
      normalized.scenarios = normalized.scenarios.map(s => ({
        ...s,
        probability: s.probability / totalProb
      }));
    }
  }
  
  return normalized;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
