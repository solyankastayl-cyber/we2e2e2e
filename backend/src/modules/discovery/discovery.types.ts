/**
 * Phase 9 — Strategy Discovery Engine
 * 
 * Automatically discovers profitable trading strategies by:
 * 1. Analyzing historical signals and outcomes
 * 2. Finding feature combinations with edge
 * 3. Clustering similar setups
 * 4. Generating new strategy hypotheses
 * 5. Filtering strategies by performance
 */

// ==============================================
// Feature Types
// ==============================================

export type PatternFeature = 
  | 'BREAKOUT' | 'COMPRESSION' | 'LIQUIDITY_SWEEP' | 'RETEST'
  | 'DOUBLE_TOP' | 'DOUBLE_BOTTOM' | 'HEAD_SHOULDERS'
  | 'TRIANGLE' | 'FLAG' | 'WEDGE' | 'CHANNEL'
  | 'HARMONIC' | 'DIVERGENCE' | 'ENGULFING';

export type IndicatorFeature = 
  | 'RSI_OVERSOLD' | 'RSI_OVERBOUGHT' | 'RSI_DIVERGENCE'
  | 'MACD_CROSSOVER' | 'MACD_DIVERGENCE'
  | 'VOLUME_SPIKE' | 'VOLUME_DRY'
  | 'ATR_HIGH' | 'ATR_LOW';

export type StructureFeature = 
  | 'SWEEP' | 'COMPRESSION' | 'EXPANSION'
  | 'ACCUMULATION' | 'DISTRIBUTION'
  | 'HIGHER_HIGHS' | 'LOWER_LOWS';

export type MTFFeature = 
  | 'MTF_ALIGNED' | 'MTF_CONFLICT'
  | 'HIGHER_TF_BULL' | 'HIGHER_TF_BEAR'
  | 'LOWER_TF_CONFIRMS';

export type RegimeFeature = 
  | 'TREND_UP' | 'TREND_DOWN' | 'RANGE'
  | 'VOL_HIGH' | 'VOL_LOW' | 'TRANSITION';

export type MemoryFeature = 
  | 'MEMORY_MATCH' | 'MEMORY_WEAK'
  | 'HISTORICAL_WIN' | 'HISTORICAL_LOSS';

export type AnyFeature = 
  | PatternFeature | IndicatorFeature | StructureFeature 
  | MTFFeature | RegimeFeature | MemoryFeature;

// ==============================================
// Signal Record (Training Data)
// ==============================================

/**
 * Historical signal record for analysis
 */
export interface SignalRecord {
  id: string;
  symbol: string;
  timeframe: string;
  timestamp: number;
  
  // Features
  pattern: PatternFeature | null;
  structure: StructureFeature | null;
  indicator: IndicatorFeature | null;
  mtf: MTFFeature | null;
  regime: RegimeFeature;
  memory: MemoryFeature | null;
  
  // Additional features
  features: AnyFeature[];
  
  // Signal details
  direction: 'LONG' | 'SHORT';
  entry: number;
  stop: number;
  target: number;
  confidence: number;
  
  // Outcome
  outcome: {
    result: 'WIN' | 'LOSS' | 'BREAKEVEN' | 'PENDING';
    pnl: number;           // Percentage
    rMultiple: number;     // R-multiple achieved
    holdTime: number;      // Candles
    exitReason: 'TARGET' | 'STOP' | 'TRAILING' | 'TIME' | 'MANUAL';
  };
  
  // Scores
  scenarioScore: number;
  decisionScore: number;
  
  // Metadata
  createdAt: number;
}

// ==============================================
// Feature Combination
// ==============================================

/**
 * A combination of features that may have edge
 */
export interface FeatureCombination {
  id: string;
  features: AnyFeature[];
  
  // Statistics
  sampleSize: number;
  winRate: number;
  avgRMultiple: number;
  profitFactor: number;
  maxDrawdown: number;
  sharpeRatio: number;
  
  // Edge analysis
  edge: number;           // Expected value
  edgeConfidence: number; // Statistical confidence
  
  // Regime breakdown
  regimePerformance: Record<RegimeFeature, {
    winRate: number;
    sampleSize: number;
  }>;
  
  // Direction breakdown
  directionPerformance: {
    LONG: { winRate: number; sampleSize: number };
    SHORT: { winRate: number; sampleSize: number };
  };
  
  // Timestamps
  firstSeen: number;
  lastSeen: number;
}

// ==============================================
// Cluster Types
// ==============================================

/**
 * Cluster of similar setups
 */
export interface SetupCluster {
  id: string;
  name: string;
  description: string;
  
  // Core features
  coreFeatures: AnyFeature[];
  optionalFeatures: AnyFeature[];
  
  // Statistics
  sampleSize: number;
  winRate: number;
  avgRMultiple: number;
  profitFactor: number;
  
  // Members
  memberSignals: string[];  // SignalRecord IDs
  
  // Quality
  coherence: number;       // How similar are cluster members
  stability: number;       // Performance consistency over time
}

// ==============================================
// Generated Strategy
// ==============================================

/**
 * Auto-generated trading strategy
 */
export interface GeneratedStrategy {
  id: string;
  name: string;
  
  // Rules
  rules: {
    required: AnyFeature[];      // Must have
    preferred: AnyFeature[];     // Boost if present
    excluded: AnyFeature[];      // Cannot have
    direction?: 'LONG' | 'SHORT' | 'BOTH';
    regimes?: RegimeFeature[];   // Only in these regimes
  };
  
  // Performance
  metrics: {
    winRate: number;
    avgRMultiple: number;
    profitFactor: number;
    maxDrawdown: number;
    sharpeRatio: number;
    trades: number;
    inSampleWinRate: number;
    outOfSampleWinRate: number;
  };
  
  // Quality scores
  confidence: number;        // 0-1
  robustness: number;        // 0-1, consistency across regimes
  stability: number;         // 0-1, consistency over time
  
  // Regime breakdown
  regimeBreakdown: Record<RegimeFeature, {
    winRate: number;
    profitFactor: number;
    trades: number;
  }>;
  
  // Status
  status: 'CANDIDATE' | 'TESTING' | 'APPROVED' | 'PAUSED' | 'REJECTED';
  
  // Source
  sourceCluster?: string;
  sourceCombination?: string;
  
  // Timestamps
  discoveredAt: number;
  lastTestedAt: number;
  approvedAt?: number;
}

// ==============================================
// Discovery Engine Configuration
// ==============================================

export interface DiscoveryConfig {
  enabled: boolean;
  
  // Feature combination thresholds
  minSampleSize: number;         // Min trades to consider
  minWinRate: number;            // Min win rate (e.g., 0.55)
  minProfitFactor: number;       // Min profit factor (e.g., 1.3)
  minEdge: number;               // Min expected value
  
  // Strategy approval thresholds
  strategyMinTrades: number;
  strategyMinWinRate: number;
  strategyMinRobustness: number;
  strategyMinConfidence: number;
  
  // Clustering
  maxFeatureCombinationSize: number;  // Max features per combo
  clusterSimilarityThreshold: number;
  
  // Auto-generation
  autoGenerateStrategies: boolean;
  maxAutoStrategies: number;
}

export const DEFAULT_DISCOVERY_CONFIG: DiscoveryConfig = {
  enabled: true,
  
  minSampleSize: 30,
  minWinRate: 0.55,
  minProfitFactor: 1.3,
  minEdge: 0.05,
  
  strategyMinTrades: 50,
  strategyMinWinRate: 0.58,
  strategyMinRobustness: 0.6,
  strategyMinConfidence: 0.7,
  
  maxFeatureCombinationSize: 4,
  clusterSimilarityThreshold: 0.7,
  
  autoGenerateStrategies: true,
  maxAutoStrategies: 20
};

// ==============================================
// Discovery Results
// ==============================================

export interface DiscoveryResult {
  runId: string;
  startedAt: number;
  completedAt: number;
  
  // Input
  datasetSize: number;
  symbolsAnalyzed: string[];
  timeframesAnalyzed: string[];
  
  // Discoveries
  combinationsFound: number;
  combinationsWithEdge: number;
  clustersFormed: number;
  strategiesGenerated: number;
  
  // Top discoveries
  topCombinations: FeatureCombination[];
  topStrategies: GeneratedStrategy[];
  
  // Insights
  insights: string[];
}

// ==============================================
// API Types
// ==============================================

export interface DiscoveryStatusResponse {
  enabled: boolean;
  version: string;
  datasetSize: number;
  combinationsAnalyzed: number;
  strategiesGenerated: number;
  lastRun: number | null;
}

export interface AnalyzeRequest {
  symbols?: string[];
  timeframes?: string[];
  startDate?: string;
  endDate?: string;
  minSampleSize?: number;
}

export interface StrategyListResponse {
  strategies: GeneratedStrategy[];
  total: number;
  approved: number;
  testing: number;
  candidates: number;
}
