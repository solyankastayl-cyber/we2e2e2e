/**
 * Phase 5.5 — Portfolio Intelligence Types
 * ==========================================
 * Portfolio state, exposure, correlation, risk management
 */

// ═══════════════════════════════════════════════════════════════
// POSITION
// ═══════════════════════════════════════════════════════════════

export interface Position {
  id: string;
  symbol: string;
  side: 'LONG' | 'SHORT';
  size: number;           // In base currency
  entryPrice: number;
  currentPrice: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  leverage: number;
  marginUsed: number;
  strategyId: string;
  openedAt: number;
}

// ═══════════════════════════════════════════════════════════════
// PORTFOLIO STATE
// ═══════════════════════════════════════════════════════════════

export interface PortfolioState {
  totalValue: number;         // Total portfolio value
  availableMargin: number;    // Free margin
  usedMargin: number;         // Margin in positions
  unrealizedPnl: number;      // Total unrealized P&L
  realizedPnl: number;        // Today's realized P&L
  
  positions: Position[];
  positionCount: number;
  
  lastUpdated: number;
}

// ═══════════════════════════════════════════════════════════════
// EXPOSURE
// ═══════════════════════════════════════════════════════════════

export interface AssetExposure {
  symbol: string;
  netExposure: number;        // Positive = long, negative = short
  grossExposure: number;      // Absolute value
  weight: number;             // % of portfolio
  positions: number;          // Number of positions
}

export interface SectorExposure {
  sector: string;             // 'MAJOR', 'DEFI', 'L1', 'MEME'
  netExposure: number;
  weight: number;
  assets: string[];
}

export interface ExposureState {
  totalGrossExposure: number;
  totalNetExposure: number;   // Can be negative (net short)
  leverageRatio: number;      // Gross / Portfolio Value
  
  byAsset: AssetExposure[];
  bySector: SectorExposure[];
  
  direction: 'LONG_BIASED' | 'SHORT_BIASED' | 'NEUTRAL';
  
  lastUpdated: number;
}

// ═══════════════════════════════════════════════════════════════
// CORRELATION
// ═══════════════════════════════════════════════════════════════

export interface CorrelationPair {
  asset1: string;
  asset2: string;
  correlation: number;        // -1 to 1
  period: string;             // '7d', '30d', '90d'
}

export interface CorrelationMatrix {
  assets: string[];
  matrix: number[][];         // NxN correlation matrix
  period: string;
  
  highCorrelations: CorrelationPair[];   // > 0.7
  negativeCorrelations: CorrelationPair[]; // < -0.3
  
  portfolioCorrelation: number; // Average correlation
  diversificationScore: number; // 0-1, higher = more diversified
  
  lastUpdated: number;
}

// ═══════════════════════════════════════════════════════════════
// RISK
// ═══════════════════════════════════════════════════════════════

export interface PortfolioRisk {
  // Value at Risk
  var95: number;              // 95% VaR (daily)
  var99: number;              // 99% VaR (daily)
  
  // Drawdown
  currentDrawdown: number;
  maxDrawdown: number;        // Historical max
  drawdownDuration: number;   // Days in drawdown
  
  // Concentration
  concentrationRisk: number;  // Herfindahl index
  largestPosition: number;    // % of portfolio
  
  // Leverage
  effectiveLeverage: number;
  maxAllowedLeverage: number;
  leverageUtilization: number;
  
  // Overall
  riskScore: number;          // 0-1, composite risk
  riskLevel: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  
  warnings: RiskWarning[];
  
  lastUpdated: number;
}

export interface RiskWarning {
  type: 'CONCENTRATION' | 'LEVERAGE' | 'CORRELATION' | 'DRAWDOWN' | 'EXPOSURE';
  severity: 'INFO' | 'WARNING' | 'CRITICAL';
  message: string;
  value: number;
  threshold: number;
}

// ═══════════════════════════════════════════════════════════════
// ALLOCATION
// ═══════════════════════════════════════════════════════════════

export interface StrategyAllocationView {
  strategyId: string;
  strategyName: string;
  
  targetAllocation: number;   // Configured %
  actualAllocation: number;   // Current %
  deviation: number;          // Actual - Target
  
  positions: number;
  exposure: number;
  pnl: number;
}

export interface AllocationState {
  strategies: StrategyAllocationView[];
  
  totalAllocated: number;
  unallocated: number;
  
  rebalanceNeeded: boolean;
  maxDeviation: number;
  
  lastUpdated: number;
}

// ═══════════════════════════════════════════════════════════════
// PORTFOLIO LIMITS
// ═══════════════════════════════════════════════════════════════

export interface PortfolioLimits {
  maxPositions: number;
  maxLeverage: number;
  maxDrawdown: number;
  maxSingleAssetExposure: number;
  maxSectorExposure: number;
  maxCorrelatedExposure: number;
}

// ═══════════════════════════════════════════════════════════════
// POSITION CHECK
// ═══════════════════════════════════════════════════════════════

export interface PositionCheckResult {
  allowed: boolean;
  reason?: string;
  
  checks: {
    positionLimit: boolean;
    leverageLimit: boolean;
    exposureLimit: boolean;
    correlationLimit: boolean;
    drawdownLimit: boolean;
  };
  
  suggestedSize?: number;     // If partially allowed
}
