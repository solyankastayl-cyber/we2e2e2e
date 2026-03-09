/**
 * MetaBrain v3 — Self-Optimizing System Types
 * 
 * Global system control layer that manages:
 * - Analysis depth
 * - Risk mode
 * - Strategy activation
 * - Module enablement
 * - Safe mode
 */

import { AnalysisModule } from '../metabrain_learning/module_attribution.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';

// ═══════════════════════════════════════════════════════════════
// ANALYSIS MODE
// ═══════════════════════════════════════════════════════════════

export type AnalysisMode = 'CLASSIC_TA' | 'DEEP_MARKET';

// ═══════════════════════════════════════════════════════════════
// RISK MODE
// ═══════════════════════════════════════════════════════════════

export type MetaBrainRiskMode = 'SAFE' | 'CONSERVATIVE' | 'NORMAL' | 'AGGRESSIVE';

// ═══════════════════════════════════════════════════════════════
// GLOBAL CONTEXT
// ═══════════════════════════════════════════════════════════════

export interface MetaBrainV3Context {
  // Market state
  regime: MarketRegime;
  state: MarketStateNode;
  
  // Volatility & uncertainty
  volatility: number;
  treeUncertainty: number;
  treeRisk: number;
  
  // Memory state
  memoryConfidence: number;
  memoryBias: 'BULL' | 'BEAR' | 'NEUTRAL';
  memoryMatches: number;
  
  // System health
  edgeHealth: number;
  drawdownPct: number;
  portfolioRiskPct: number;
  
  // Module state
  activeStrategies: number;
  gatedModules: number;
  gatePressure: number;
  
  // Scenario state
  dominantScenario: string;
  dominantScenarioProbability: number;
  
  // Timestamp
  ts: number;
}

// ═══════════════════════════════════════════════════════════════
// METABRAIN V3 DECISION
// ═══════════════════════════════════════════════════════════════

export interface StrategyPolicy {
  enabledStrategies: string[];
  disabledStrategies: string[];
  strategyMultiplier: number;
}

export interface ModulePolicy {
  enabledModules: AnalysisModule[];
  disabledModules: AnalysisModule[];
}

export interface ExecutionPolicy {
  riskMultiplier: number;
  maxRiskPerTrade: number;
  maxPortfolioRisk: number;
}

export interface ConfidencePolicy {
  minSignalConfidence: number;
  minScenarioProbability: number;
}

export interface MetaBrainV3Decision {
  // Analysis depth
  analysisMode: AnalysisMode;
  
  // Risk mode
  riskMode: MetaBrainRiskMode;
  
  // Policies
  strategyPolicy: StrategyPolicy;
  modulePolicy: ModulePolicy;
  executionPolicy: ExecutionPolicy;
  confidencePolicy: ConfidencePolicy;
  
  // Safe mode flag
  safeMode: boolean;
  
  // Decision reasons
  reasons: string[];
  
  // Confidence in decision
  decisionConfidence: number;
  
  // Timestamp
  decidedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// SAFE MODE TRIGGERS
// ═══════════════════════════════════════════════════════════════

export interface SafeModeConfig {
  // Drawdown threshold
  maxDrawdownPct: number;
  
  // Uncertainty thresholds
  maxTreeUncertainty: number;
  maxTreeRisk: number;
  
  // Memory confidence
  minMemoryConfidence: number;
  
  // Module health
  maxGatedModules: number;
  maxGatePressure: number;
  
  // Edge health
  minEdgeHealth: number;
}

export const DEFAULT_SAFE_MODE_CONFIG: SafeModeConfig = {
  maxDrawdownPct: 0.10,           // 10% drawdown
  maxTreeUncertainty: 0.65,
  maxTreeRisk: 0.50,
  minMemoryConfidence: 0.35,
  maxGatedModules: 3,
  maxGatePressure: 0.40,
  minEdgeHealth: 0.30
};

// ═══════════════════════════════════════════════════════════════
// ANALYSIS DEPTH CONFIG
// ═══════════════════════════════════════════════════════════════

export interface AnalysisDepthConfig {
  // DEEP_MARKET triggers
  deepMarketTreeUncertaintyThreshold: number;
  deepMarketMemoryConfidenceThreshold: number;
  deepMarketGatedModulesThreshold: number;
  
  // Complex regime list
  complexRegimes: MarketRegime[];
}

export const DEFAULT_ANALYSIS_DEPTH_CONFIG: AnalysisDepthConfig = {
  deepMarketTreeUncertaintyThreshold: 0.40,
  deepMarketMemoryConfidenceThreshold: 0.60,
  deepMarketGatedModulesThreshold: 1,
  
  complexRegimes: [
    'VOLATILITY_EXPANSION',
    'LIQUIDITY_HUNT',
    'DISTRIBUTION',
    'ACCUMULATION'
  ]
};

// ═══════════════════════════════════════════════════════════════
// STRATEGY CONFIG
// ═══════════════════════════════════════════════════════════════

export interface StrategyConfig {
  // Strategy sets by regime
  trendStrategies: string[];
  rangeStrategies: string[];
  breakoutStrategies: string[];
  reversalStrategies: string[];
}

export const DEFAULT_STRATEGY_CONFIG: StrategyConfig = {
  trendStrategies: ['TREND_FOLLOW', 'MOMENTUM', 'CONTINUATION'],
  rangeStrategies: ['MEAN_REVERSION', 'RANGE_BOUND', 'FADE'],
  breakoutStrategies: ['BREAKOUT', 'EXPANSION', 'MOMENTUM_BURST'],
  reversalStrategies: ['REVERSAL', 'EXHAUSTION', 'DIVERGENCE']
};

// ═══════════════════════════════════════════════════════════════
// STORAGE TYPES
// ═══════════════════════════════════════════════════════════════

export interface MetaBrainV3State {
  context: MetaBrainV3Context;
  decision: MetaBrainV3Decision;
  
  asset?: string;
  timeframe?: string;
  
  createdAt: Date;
}

export interface MetaBrainV3Action {
  type: 'SAFE_MODE_ENTER' | 'SAFE_MODE_EXIT' | 'RISK_MODE_CHANGE' | 
        'ANALYSIS_MODE_CHANGE' | 'STRATEGY_CHANGE' | 'MODULE_CHANGE';
  
  previousValue: string;
  newValue: string;
  reason: string;
  
  triggeredAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// API TYPES
// ═══════════════════════════════════════════════════════════════

export interface MetaBrainV3StateResponse {
  success: boolean;
  data?: MetaBrainV3State;
  error?: string;
}

export interface MetaBrainV3DecisionResponse {
  success: boolean;
  data?: MetaBrainV3Decision;
  error?: string;
}

export interface MetaBrainV3HistoryResponse {
  success: boolean;
  data?: {
    states: MetaBrainV3State[];
    actions: MetaBrainV3Action[];
  };
  error?: string;
}
