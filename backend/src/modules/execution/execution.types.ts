/**
 * Phase 10 — Execution Intelligence Types
 * 
 * Position sizing, risk allocation, portfolio management
 */

// ═══════════════════════════════════════════════════════════════
// POSITION SIZING
// ═══════════════════════════════════════════════════════════════

export interface PositionSizeRequest {
  // Account
  accountSize: number;
  baseRiskPct: number;  // e.g., 0.5 = 0.5%
  
  // Trade
  asset: string;
  direction: 'LONG' | 'SHORT';
  entryPrice: number;
  stopPrice: number;
  atr: number;
  
  // Signal quality
  confidence: number;      // 0-1
  edgeScore: number;       // Edge multiplier
  regimeBoost: number;     // Regime alignment
  strategyScore?: number;  // Strategy quality
  
  // MetaBrain integration (Phase 11)
  metaRiskMultiplier?: number;  // From MetaBrain policy layer
  
  // P0: Memory risk adjustment
  memoryRiskAdjustment?: number;  // From Market Memory Engine (0.8-1.1)
  
  // Phase 6.5: MTF Execution Adjustment
  mtfExecutionAdjustment?: number;  // From MTF Confirmation Layer (0.85-1.0)
}

export interface PositionSizeResult {
  // Core
  positionSizePct: number;     // % of account
  positionSizeAbsolute: number; // In base currency
  riskPct: number;             // Actual risk %
  riskAbsolute: number;        // In base currency
  
  // Levels
  entryPrice: number;
  stopPrice: number;
  stopDistanceATR: number;
  
  // Multipliers applied
  multipliers: {
    base: number;
    confidence: number;
    edge: number;
    regime: number;
    portfolio: number;
    metaBrain?: number;  // MetaBrain risk multiplier (Phase 11)
    memory?: number;     // P0: Memory risk adjustment
    mtf?: number;        // Phase 6.5: MTF execution adjustment
  };
  
  // Constraints
  cappedBy?: string;
  originalSize?: number;
}

// ═══════════════════════════════════════════════════════════════
// RISK MANAGEMENT
// ═══════════════════════════════════════════════════════════════

export interface RiskLimits {
  maxRiskPerTrade: number;      // Max risk % per trade
  maxPortfolioRisk: number;     // Max total portfolio risk %
  maxCorrelatedRisk: number;    // Max risk in correlated assets
  maxDrawdown: number;          // Max allowed drawdown %
  maxOpenTrades: number;        // Max concurrent trades
  maxExposurePerAsset: number;  // Max exposure % per asset
}

export const DEFAULT_RISK_LIMITS: RiskLimits = {
  maxRiskPerTrade: 1.0,
  maxPortfolioRisk: 6.0,
  maxCorrelatedRisk: 3.0,
  maxDrawdown: 15.0,
  maxOpenTrades: 10,
  maxExposurePerAsset: 20.0
};

export interface RiskStatus {
  currentPortfolioRisk: number;
  currentDrawdown: number;
  openTradesCount: number;
  
  // By asset
  exposureByAsset: Record<string, number>;
  
  // By correlation group
  correlatedExposure: Record<string, number>;
  
  // Available
  availableRisk: number;
  canOpenTrade: boolean;
  
  // Warnings
  warnings: string[];
}

// ═══════════════════════════════════════════════════════════════
// PORTFOLIO
// ═══════════════════════════════════════════════════════════════

export interface PortfolioPosition {
  positionId: string;
  asset: string;
  direction: 'LONG' | 'SHORT';
  strategyId: string;
  
  // Size
  entryPrice: number;
  currentPrice: number;
  positionSize: number;
  riskPct: number;
  
  // Levels
  stopPrice: number;
  target1Price: number;
  target2Price?: number;
  
  // Status
  unrealizedR: number;
  unrealizedPnL: number;
  
  // Time
  entryTime: Date;
  barsInTrade: number;
}

export interface Portfolio {
  portfolioId: string;
  accountSize: number;
  
  // Positions
  positions: PortfolioPosition[];
  
  // Aggregates
  totalRisk: number;
  totalExposure: number;
  unrealizedPnL: number;
  
  // Performance
  realizedPnL: number;
  winCount: number;
  lossCount: number;
  
  // Meta
  updatedAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// EXECUTION PLAN
// ═══════════════════════════════════════════════════════════════

export interface ExecutionPlan {
  planId: string;
  
  // Target
  asset: string;
  direction: 'LONG' | 'SHORT';
  strategyId: string;
  
  // Entry
  entryType: 'MARKET' | 'LIMIT' | 'STOP';
  entryPrice: number;
  entryCondition?: string;
  
  // Position
  positionSizePct: number;
  positionSizeUnits: number;
  
  // Risk
  stopPrice: number;
  stopATR: number;
  riskPct: number;
  riskAbsolute: number;
  
  // Targets
  target1Price: number;
  target1ATR: number;
  target2Price?: number;
  target2ATR?: number;
  
  // Trailing (optional)
  useTrailingStop: boolean;
  trailingActivation?: number;
  trailingDistance?: number;
  
  // Timing
  validUntil?: Date;
  maxBarsInTrade?: number;
  
  // Reasoning
  signalQuality: {
    confidence: number;
    edgeScore: number;
    regimeBoost: number;
    scenarioProbability: number;
  };
  
  // Status
  status: 'PENDING' | 'ACTIVE' | 'FILLED' | 'CANCELLED' | 'EXPIRED';
  createdAt: Date;
}

// ═══════════════════════════════════════════════════════════════
// ALLOCATION
// ═══════════════════════════════════════════════════════════════

export interface StrategyAllocation {
  strategyId: string;
  allocationPct: number;  // % of capital allocated
  
  // Based on
  strategyScore: number;
  profitFactor: number;
  trades: number;
  
  // Current
  activePositions: number;
  currentExposure: number;
}

export interface AllocationPlan {
  totalCapital: number;
  allocations: StrategyAllocation[];
  
  // Constraints
  reserveCash: number;  // % kept as cash
  maxSingleStrategy: number;  // Max % per strategy
}

// ═══════════════════════════════════════════════════════════════
// CORRELATION
// ═══════════════════════════════════════════════════════════════

export interface AssetCorrelation {
  asset1: string;
  asset2: string;
  correlation: number;  // -1 to 1
  correlationGroup?: string;
}

// Default correlation groups
export const CORRELATION_GROUPS: Record<string, string[]> = {
  'MAJOR_CRYPTO': ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
  'ALT_L1': ['SOLUSDT', 'AVAXUSDT', 'ADAUSDT', 'DOTUSDT'],
  'DEFI': ['UNIUSDT', 'AAVEUSDT', 'MKRUSDT'],
  'MEME': ['DOGEUSDT', 'SHIBUSDT', 'PEPEUSDT']
};

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

export interface ExecutionConfig {
  // Sizing
  baseRiskPct: number;
  confidenceMultiplierMin: number;
  confidenceMultiplierMax: number;
  edgeMultiplierMin: number;
  edgeMultiplierMax: number;
  
  // Portfolio
  maxCorrelation: number;
  reserveCashPct: number;
  
  // Execution
  defaultSlippagePct: number;
  useTrailingByDefault: boolean;
}

export const DEFAULT_EXECUTION_CONFIG: ExecutionConfig = {
  baseRiskPct: 0.5,
  confidenceMultiplierMin: 0.7,
  confidenceMultiplierMax: 1.3,
  edgeMultiplierMin: 0.75,
  edgeMultiplierMax: 1.35,
  maxCorrelation: 0.7,
  reserveCashPct: 10,
  useTrailingByDefault: false
};
