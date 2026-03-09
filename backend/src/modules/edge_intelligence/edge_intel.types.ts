/**
 * Phase 7 — Edge Intelligence Types
 * 
 * Edge analysis and attribution system
 */

// ═══════════════════════════════════════════════════════════════
// EDGE DIMENSIONS
// ═══════════════════════════════════════════════════════════════

export type EdgeDimension =
  | 'PATTERN'
  | 'STATE'
  | 'FRACTAL'
  | 'SCENARIO'
  | 'LIQUIDITY'
  | 'MARKET_STATE'
  | 'TIMEFRAME'
  | 'ASSET';

// ═══════════════════════════════════════════════════════════════
// TRADE EDGE RECORD
// ═══════════════════════════════════════════════════════════════

export interface EdgeRecord {
  tradeId: string;
  
  // Trade info
  asset: string;
  timeframe: string;
  entryTime: Date;
  exitTime?: Date;
  
  // Dimensions
  pattern: string;
  patternFamily?: string;
  fractal?: string;
  scenario?: string;
  state: string;
  liquidity: string;
  marketState?: string;
  physicsState?: string;
  
  // Trade result
  resultR: number;
  outcome: 'WIN' | 'LOSS' | 'BREAKEVEN';
  
  // Entry conditions
  entryScore: number;
  entryConfidence: number;
  
  // Additional context
  energyScore?: number;
  graphBoost?: number;
  stateBoost?: number;
}

// ═══════════════════════════════════════════════════════════════
// EDGE STATISTICS
// ═══════════════════════════════════════════════════════════════

export interface EdgeStats {
  dimension: EdgeDimension;
  key: string;
  
  // Sample
  sampleSize: number;
  wins: number;
  losses: number;
  breakevens: number;
  
  // Performance
  winRate: number;
  avgR: number;
  medianR: number;
  profitFactor: number;
  sharpe: number;
  maxDD: number;
  
  // Edge metrics
  edgeScore: number;
  edgeShrunk: number;  // Shrunk toward global baseline
  
  // Confidence
  confidence: number;
  statisticalSignificance: number;
  
  // Time
  updatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// EDGE ATTRIBUTION
// ═══════════════════════════════════════════════════════════════

export interface EdgeAttribution {
  attributionId: string;
  
  // What combination has edge
  dimensions: {
    dimension: EdgeDimension;
    value: string;
  }[];
  
  // Edge contribution
  individualEdges: {
    dimension: EdgeDimension;
    value: string;
    pfAlone: number;
    contributionPct: number;
  }[];
  
  // Combined effect
  combinedPF: number;
  synergy: number;  // > 1 means dimensions work better together
  
  // Sample
  sampleSize: number;
  confidence: number;
  
  // Updated
  calculatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// EDGE INTELLIGENCE RESULT
// ═══════════════════════════════════════════════════════════════

export interface EdgeIntelligenceResult {
  asset?: string;
  timeframe?: string;
  
  // Global baseline
  globalBaseline: {
    winRate: number;
    avgR: number;
    profitFactor: number;
    totalTrades: number;
  };
  
  // By dimension
  byPattern: EdgeStats[];
  byState: EdgeStats[];
  byFractal: EdgeStats[];
  byScenario: EdgeStats[];
  byLiquidity: EdgeStats[];
  
  // Top performers
  topEdges: EdgeStats[];
  worstEdges: EdgeStats[];
  
  // Attributions
  topAttributions: EdgeAttribution[];
  
  // Recommendations
  recommendations: {
    tradeDimension: string;
    tradeValue: string;
    reason: string;
    edgeBoost: number;
  }[];
  
  // Meta
  calculatedAt: Date;
  dataWindow: {
    from: Date;
    to: Date;
  };
}

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

export interface EdgeIntelligenceConfig {
  minSampleSize: number;
  shrinkageStrength: number;
  significanceThreshold: number;
  topPerformersCount: number;
  attributionDepth: number;
  dataWindowDays: number;
}

export const DEFAULT_EDGE_CONFIG: EdgeIntelligenceConfig = {
  minSampleSize: 30,
  shrinkageStrength: 0.5,
  significanceThreshold: 0.7,
  topPerformersCount: 10,
  attributionDepth: 3,
  dataWindowDays: 180
};

// ═══════════════════════════════════════════════════════════════
// EDGE MULTIPLIER (for Decision Engine)
// ═══════════════════════════════════════════════════════════════

export interface EdgeMultiplier {
  pattern: string;
  state: string;
  scenario?: string;
  liquidity?: string;
  
  multiplier: number;
  confidence: number;
  basedOn: string;  // e.g., "PATTERN+STATE"
}
