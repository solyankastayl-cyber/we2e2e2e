/**
 * Phase 6.5 — Multi-Timeframe Confirmation Layer
 * 
 * Types for MTF alignment checking across 3 timeframes:
 * - Higher TF (1D) — direction and context
 * - Anchor TF (4H) — main scenario  
 * - Lower TF (1H) — entry precision and momentum
 */

export type Bias = 'BULL' | 'BEAR' | 'NEUTRAL';

export type Timeframe = '15m' | '1h' | '4h' | '1d' | '1w';

/**
 * MTF Timeframe Map — defines higher/lower TF for each anchor TF
 */
export const MTF_MAP: Record<Timeframe, { higher: Timeframe; lower: Timeframe }> = {
  '15m': { higher: '1h', lower: '5m' as Timeframe },
  '1h': { higher: '4h', lower: '15m' },
  '4h': { higher: '1d', lower: '1h' },
  '1d': { higher: '1w', lower: '4h' },
  '1w': { higher: '1w', lower: '1d' }  // weekly has no higher
};

/**
 * Core MTF State — the main output
 */
export interface MTFState {
  symbol: string;
  
  // Timeframes
  anchorTf: string;
  higherTf: string;
  lowerTf: string;
  
  // Higher TF analysis
  higherBias: Bias;
  higherRegime: string;
  higherStructure: string;
  higherScenarioBias?: string;
  
  // Lower TF analysis  
  lowerMomentum: Bias;
  lowerStructure: string;
  
  // Alignment results (4 key checks)
  regimeAligned: boolean;       // Does higher TF regime support setup?
  structureAligned: boolean;    // Does higher TF structure align?
  scenarioAligned: boolean;     // Does higher TF scenario support?
  momentumAligned: boolean;     // Does lower TF momentum confirm?
  
  // Conflict detection
  higherConflict: boolean;      // Is higher TF opposing current direction?
  
  // Final boost factor
  mtfBoost: number;             // 0.88 - 1.15
  
  // Execution adjustment (for position sizing)
  mtfExecutionAdjustment: number;  // 0.85 - 1.00
  
  // Human-readable notes
  notes: string[];
  
  // Metadata
  computedAt: number;
}

/**
 * Input for MTF Context Building
 */
export interface MTFContextInput {
  symbol: string;
  anchorTf: string;
  
  // Optional: provide packs if already available
  higherTfPack?: any;
  anchorTfPack?: any;
  lowerTfPack?: any;
}

/**
 * Raw context from each timeframe
 */
export interface TFContext {
  tf: string;
  
  // Bias/Direction
  bias: Bias;
  direction: 'LONG' | 'SHORT' | 'WAIT';
  
  // Market regime
  regime: string;  // TREND_UP, TREND_DOWN, RANGE, TRANSITION
  volRegime: string;  // LOW, NORMAL, HIGH, EXTREME
  
  // Structure
  structure: string;  // BULLISH, BEARISH, NEUTRAL
  structureStrength: number;
  
  // Scenario (if available)
  topScenario?: {
    id: string;
    direction: string;
    probability: number;
    type: string;
  };
  
  // Momentum (mainly for lower TF)
  momentum?: {
    rsiValue: number;
    rsiBias: Bias;
    macdBias: Bias;
    overallBias: Bias;
  };
  
  // Raw pack reference
  pack?: any;
}

/**
 * MTF Alignment Input for boost calculation
 */
export interface MTFAlignmentInput {
  anchorDirection: 'LONG' | 'SHORT';
  
  higherBiasAligned: boolean;
  regimeAligned: boolean;
  structureAligned: boolean;
  scenarioAligned: boolean;
  lowerMomentumAligned: boolean;
  
  higherConflict: boolean;
}

/**
 * Config for MTF Layer
 */
export interface MTFConfig {
  enabled: boolean;
  
  // Boost weights
  weights: {
    higherBiasAligned: number;      // +0.06
    regimeAligned: number;          // +0.05
    structureAligned: number;       // +0.05
    scenarioAligned: number;        // +0.04
    lowerMomentumAligned: number;   // +0.04
    higherConflict: number;         // -0.10
  };
  
  // Clamp bounds
  boostMin: number;   // 0.88
  boostMax: number;   // 1.15
  
  // Execution adjustment
  executionStrong: number;    // 1.00
  executionMixed: number;     // 0.92
  executionConflict: number;  // 0.85
}

export const DEFAULT_MTF_CONFIG: MTFConfig = {
  enabled: true,
  
  weights: {
    higherBiasAligned: 0.06,
    regimeAligned: 0.05,
    structureAligned: 0.05,
    scenarioAligned: 0.04,
    lowerMomentumAligned: 0.04,
    higherConflict: -0.10
  },
  
  boostMin: 0.88,
  boostMax: 1.15,
  
  executionStrong: 1.00,
  executionMixed: 0.92,
  executionConflict: 0.85
};

/**
 * MTF Explain block for Decision API
 */
export interface MTFExplain {
  anchorTf: string;
  higherTf: string;
  lowerTf: string;
  
  higherBias: Bias;
  lowerMomentum: Bias;
  
  regimeAligned: boolean;
  structureAligned: boolean;
  scenarioAligned: boolean;
  momentumAligned: boolean;
  
  mtfBoost: number;
  mtfExecutionAdjustment: number;
  
  notes: string[];
}
