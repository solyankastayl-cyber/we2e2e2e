/**
 * Phase 9.5 — Edge Validation for Discovery
 * 
 * Protects against false edge in discovered strategies:
 * - Minimum evidence rule
 * - Regime robustness 
 * - Cross-market robustness
 * - Similarity penalty
 * - Confidence scoring
 * - Extended lifecycle (LIMITED status)
 */

// ==============================================
// Robustness Types
// ==============================================

export type RegimeType = 
  | 'TREND_EXPANSION'
  | 'TREND_DECAY'
  | 'COMPRESSION'
  | 'RANGE'
  | 'VOLATILITY_SPIKE';

export type MarketType = 
  | 'BTC' | 'ETH' | 'SOL' | 'BNB'
  | 'SPX' | 'NASDAQ' | 'GOLD';

export type StrategyLifecycle = 
  | 'CANDIDATE'
  | 'TESTING'
  | 'LIMITED'
  | 'APPROVED'
  | 'REJECTED';

// ==============================================
// Core Types
// ==============================================

/**
 * Regime performance breakdown
 */
export interface RegimePerformance {
  regime: RegimeType;
  trades: number;
  winRate: number;
  profitFactor: number;
  edge: number;
  isStrong: boolean;  // winRate > threshold
}

/**
 * Cross-market performance
 */
export interface MarketPerformance {
  market: MarketType;
  trades: number;
  winRate: number;
  profitFactor: number;
  edge: number;
  isValid: boolean;  // trades > minTrades
}

/**
 * Robustness scores
 */
export interface RobustnessScore {
  // Regime analysis
  regimeScore: number;           // 0-1, consistency across regimes
  strongRegimes: RegimeType[];   // Regimes where strategy works
  weakRegimes: RegimeType[];     // Regimes where strategy fails
  
  // Cross-market analysis
  crossMarketScore: number;      // 0-1, consistency across markets
  validMarkets: MarketType[];    // Markets where strategy works
  failedMarkets: MarketType[];   // Markets where strategy fails
  
  // Stability analysis
  stabilityScore: number;        // 0-1, performance consistency over time
  walkForwardResults?: number[]; // Walk-forward test results
  
  // Overall
  overallRobustness: number;     // 0-1, combined score
}

/**
 * Similarity analysis
 */
export interface SimilarityAnalysis {
  strategyId: string;
  similarStrategies: {
    id: string;
    similarity: number;      // 0-1, feature overlap
    cooccurrence: number;    // How often they fire together
  }[];
  
  maxSimilarity: number;
  similarityPenalty: number;   // 0-0.6
  
  isRedundant: boolean;        // Should be filtered out
}

/**
 * Confidence score breakdown
 */
export interface ConfidenceScore {
  // Components
  sampleScore: number;         // Based on trade count
  regimeRobustness: number;    // From robustness analysis
  crossMarketRobustness: number;
  stabilityScore: number;
  
  // Penalties
  similarityPenalty: number;
  sampleSizePenalty: number;   // If trades < optimal
  
  // Final score
  rawConfidence: number;       // Before penalties
  adjustedConfidence: number;  // After penalties
  
  // Risk flags
  riskFlags: string[];
}

/**
 * Full edge validation result
 */
export interface EdgeValidationResult {
  strategyId: string;
  strategyName: string;
  
  // Original metrics
  metrics: {
    winRate: number;
    profitFactor: number;
    sharpe: number;
    maxDrawdown: number;
    trades: number;
  };
  
  // Validation scores
  robustness: RobustnessScore;
  similarity: SimilarityAnalysis;
  confidence: ConfidenceScore;
  
  // Lifecycle recommendation
  recommendedStatus: StrategyLifecycle;
  statusReason: string;
  
  // Limitations (for LIMITED status)
  limitations?: {
    regimesOnly?: RegimeType[];
    marketsOnly?: MarketType[];
    timeframesOnly?: string[];
  };
  
  // Validation timestamp
  validatedAt: number;
}

// ==============================================
// Configuration
// ==============================================

export interface EdgeValidationConfig {
  enabled: boolean;
  
  // Minimum evidence thresholds
  minTrades: number;                    // 80
  optimalTrades: number;                // 150
  minTradesPerRegime: number;           // 15
  minTradesPerMarket: number;           // 20
  
  // Performance thresholds
  minWinRate: number;                   // 0.52
  strongWinRate: number;                // 0.58
  minProfitFactor: number;              // 1.15
  strongProfitFactor: number;           // 1.4
  maxDrawdown: number;                  // 0.35
  
  // Robustness thresholds
  minRegimeScore: number;               // 0.5
  minCrossMarketScore: number;          // 0.4
  minStabilityScore: number;            // 0.5
  
  // Similarity thresholds
  similarityThreshold: number;          // 0.7 = 70% overlap
  maxSimilarityPenalty: number;         // 0.5
  
  // Confidence weights
  confidenceWeights: {
    sample: number;        // 0.35
    regime: number;        // 0.25
    crossMarket: number;   // 0.20
    stability: number;     // 0.20
  };
  
  // Approval thresholds
  approvalConfidence: number;           // 0.75
  limitedConfidence: number;            // 0.55
  testingConfidence: number;            // 0.40
}

export const DEFAULT_EDGE_CONFIG: EdgeValidationConfig = {
  enabled: true,
  
  minTrades: 80,
  optimalTrades: 150,
  minTradesPerRegime: 15,
  minTradesPerMarket: 20,
  
  minWinRate: 0.52,
  strongWinRate: 0.58,
  minProfitFactor: 1.15,
  strongProfitFactor: 1.4,
  maxDrawdown: 0.35,
  
  minRegimeScore: 0.5,
  minCrossMarketScore: 0.4,
  minStabilityScore: 0.5,
  
  similarityThreshold: 0.7,
  maxSimilarityPenalty: 0.5,
  
  confidenceWeights: {
    sample: 0.35,
    regime: 0.25,
    crossMarket: 0.20,
    stability: 0.20
  },
  
  approvalConfidence: 0.75,
  limitedConfidence: 0.55,
  testingConfidence: 0.40
};

// ==============================================
// Constants
// ==============================================

export const ALL_REGIMES: RegimeType[] = [
  'TREND_EXPANSION',
  'TREND_DECAY',
  'COMPRESSION',
  'RANGE',
  'VOLATILITY_SPIKE'
];

export const ALL_MARKETS: MarketType[] = [
  'BTC', 'ETH', 'SOL', 'BNB',
  'SPX', 'NASDAQ', 'GOLD'
];

// ==============================================
// Risk Flags
// ==============================================

export const RISK_FLAGS = {
  SMALL_SAMPLE: 'Insufficient trade count (<80)',
  SINGLE_REGIME: 'Works only in one regime',
  SINGLE_MARKET: 'Works only on one market',
  HIGH_DRAWDOWN: 'Maximum drawdown exceeds threshold',
  LOW_PROFIT_FACTOR: 'Profit factor below minimum',
  HIGH_SIMILARITY: 'High overlap with existing strategy',
  UNSTABLE: 'Performance inconsistent over time',
  REGIME_DECAY: 'Performance declining in recent periods'
};
