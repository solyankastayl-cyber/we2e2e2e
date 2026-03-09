/**
 * D1 — Structure-Aware Decision Engine
 * 
 * Integrates all market intelligence layers into scoring:
 * - Context Engine (25%)
 * - Market State Engine (20%)
 * - Liquidity Engine (20%)
 * - Pattern Quality (20%)
 * - ML (15%)
 * 
 * Pipeline:
 * patterns → context → market_state → liquidity → geometry → gates → graph → ML → EDGE → ranking
 */

import { Db } from 'mongodb';

// Types for structure-aware scoring
export interface StructureBoostConfig {
  weights: {
    context: number;      // 0.25
    marketState: number;  // 0.20
    liquidity: number;    // 0.20
    patternQuality: number; // 0.20
    ml: number;           // 0.15
  };
  boostClamp: {
    min: number;  // 0.5
    max: number;  // 1.5
  };
}

export const DEFAULT_STRUCTURE_CONFIG: StructureBoostConfig = {
  weights: {
    context: 0.25,
    marketState: 0.20,
    liquidity: 0.20,
    patternQuality: 0.20,
    ml: 0.15,
  },
  boostClamp: {
    min: 0.5,
    max: 1.5,
  },
};

export interface ContextScore {
  trendAlignment: number;     // Pattern aligns with trend
  impulseAlignment: number;   // Recent impulse supports direction
  structureAlignment: number; // Breakout/retest context
  overallScore: number;       // 0-1
}

export interface MarketStateScore {
  stateAlignment: number;     // Pattern fits current state
  volatilityFit: number;      // Pattern fits volatility
  trendStrengthFit: number;   // Pattern fits trend strength
  overallScore: number;       // 0-1
}

export interface LiquidityScore {
  sweepConfluence: number;    // Sweep supports direction
  zoneDistance: number;       // Distance from liquidity zones
  liquidityBias: number;      // Bias from liquidity analysis
  overallScore: number;       // 0-1
}

export interface StructureBoostResult {
  contextScore: ContextScore;
  marketStateScore: MarketStateScore;
  liquidityScore: LiquidityScore;
  patternQualityScore: number;
  mlScore: number;
  
  // Weighted boost
  structureBoost: number;
  
  // Debug
  breakdown: {
    contextContribution: number;
    marketStateContribution: number;
    liquidityContribution: number;
    patternContribution: number;
    mlContribution: number;
  };
}

/**
 * Compute context alignment score
 */
export function computeContextScore(
  patternDirection: 'LONG' | 'SHORT',
  contextData: {
    trendDirection?: 'UP' | 'DOWN' | 'NEUTRAL';
    trendStrength?: number;
    impulseRecent?: boolean;
    structureContext?: string;
    bullishScore?: number;
    bearishScore?: number;
  }
): ContextScore {
  const isBullish = patternDirection === 'LONG';
  const isBearish = patternDirection === 'SHORT';
  
  // Trend alignment
  let trendAlignment = 0.5;
  if (contextData.trendDirection) {
    if (isBullish && contextData.trendDirection === 'UP') {
      trendAlignment = 0.8 + (contextData.trendStrength || 0) * 0.2;
    } else if (isBearish && contextData.trendDirection === 'DOWN') {
      trendAlignment = 0.8 + (contextData.trendStrength || 0) * 0.2;
    } else if (contextData.trendDirection === 'NEUTRAL') {
      trendAlignment = 0.5;
    } else {
      trendAlignment = 0.2; // Counter-trend
    }
  }
  
  // Impulse alignment
  let impulseAlignment = 0.5;
  if (contextData.impulseRecent) {
    impulseAlignment = 0.85; // Recent impulse is positive
  }
  
  // Structure alignment
  let structureAlignment = 0.5;
  if (contextData.structureContext) {
    if (contextData.structureContext === 'RETEST' && isBullish) {
      structureAlignment = 0.9;
    } else if (contextData.structureContext === 'BREAKOUT') {
      structureAlignment = 0.75;
    } else if (contextData.structureContext === 'RANGE') {
      structureAlignment = 0.4;
    }
  }
  
  // Use bullish/bearish scores if available
  if (contextData.bullishScore !== undefined && contextData.bearishScore !== undefined) {
    if (isBullish) {
      trendAlignment = Math.max(trendAlignment, contextData.bullishScore);
    } else {
      trendAlignment = Math.max(trendAlignment, contextData.bearishScore);
    }
  }
  
  const overallScore = (trendAlignment + impulseAlignment + structureAlignment) / 3;
  
  return {
    trendAlignment,
    impulseAlignment,
    structureAlignment,
    overallScore: Math.min(1, Math.max(0, overallScore)),
  };
}

/**
 * Compute market state alignment score
 */
export function computeMarketStateScore(
  patternDirection: 'LONG' | 'SHORT',
  patternType: string,
  stateData: {
    state?: string;
    confidence?: number;
    trendStrength?: number;
    volatilityRegime?: string;
    rangeScore?: number;
  }
): MarketStateScore {
  const isBullish = patternDirection === 'LONG';
  
  // Patterns that work well in trends
  const trendPatterns = [
    'BULL_FLAG', 'BEAR_FLAG', 'ASC_TRIANGLE', 'DESC_TRIANGLE',
    'BULL_PENNANT', 'BEAR_PENNANT', 'CHANNEL_UP', 'CHANNEL_DOWN'
  ];
  
  // Patterns that work well in ranges
  const rangePatterns = [
    'DOUBLE_BOTTOM', 'DOUBLE_TOP', 'HEAD_SHOULDERS', 'INV_HEAD_SHOULDERS',
    'RECTANGLE', 'SYM_TRIANGLE'
  ];
  
  // Patterns that work well in volatile markets
  const volatilePatterns = [
    'WEDGE_FALLING', 'WEDGE_RISING', 'BROADENING'
  ];
  
  let stateAlignment = 0.5;
  let volatilityFit = 0.5;
  let trendStrengthFit = 0.5;
  
  const state = stateData.state || 'RANGE';
  const confidence = stateData.confidence || 0.5;
  
  // State alignment
  if (state === 'TRENDING_UP' || state === 'TREND_UP') {
    if (isBullish && trendPatterns.includes(patternType)) {
      stateAlignment = 0.9;
    } else if (!isBullish) {
      stateAlignment = 0.3;
    } else {
      stateAlignment = 0.6;
    }
  } else if (state === 'TRENDING_DOWN' || state === 'TREND_DOWN') {
    if (!isBullish && trendPatterns.includes(patternType)) {
      stateAlignment = 0.9;
    } else if (isBullish) {
      stateAlignment = 0.3;
    } else {
      stateAlignment = 0.6;
    }
  } else if (state === 'RANGE') {
    if (rangePatterns.includes(patternType)) {
      stateAlignment = 0.85;
    } else {
      stateAlignment = 0.5;
    }
  } else if (state === 'VOLATILE') {
    if (volatilePatterns.includes(patternType)) {
      stateAlignment = 0.8;
    } else {
      stateAlignment = 0.4;
    }
  } else if (state === 'COMPRESSING') {
    // Compression often leads to breakouts
    stateAlignment = 0.75;
  }
  
  // Volatility fit
  const volRegime = stateData.volatilityRegime || 'NORMAL';
  if (volRegime === 'HIGH' && volatilePatterns.includes(patternType)) {
    volatilityFit = 0.8;
  } else if (volRegime === 'LOW' && trendPatterns.includes(patternType)) {
    volatilityFit = 0.75;
  } else {
    volatilityFit = 0.5;
  }
  
  // Trend strength fit
  const ts = stateData.trendStrength || 0;
  if (Math.abs(ts) > 0.5 && trendPatterns.includes(patternType)) {
    trendStrengthFit = 0.8 + Math.abs(ts) * 0.2;
  } else {
    trendStrengthFit = 0.5;
  }
  
  // Apply confidence
  const overallScore = (stateAlignment * 0.5 + volatilityFit * 0.25 + trendStrengthFit * 0.25) * confidence;
  
  return {
    stateAlignment,
    volatilityFit,
    trendStrengthFit,
    overallScore: Math.min(1, Math.max(0, overallScore)),
  };
}

/**
 * Compute liquidity alignment score
 */
export function computeLiquidityScore(
  patternDirection: 'LONG' | 'SHORT',
  liquidityData: {
    recentSweepUp?: boolean;
    recentSweepDown?: boolean;
    liquidityBias?: string;
    zonesAbove?: number;
    zonesBelow?: number;
    distanceToNearestZoneATR?: number;
  }
): LiquidityScore {
  const isBullish = patternDirection === 'LONG';
  
  // Sweep confluence
  let sweepConfluence = 0.5;
  if (isBullish && liquidityData.recentSweepDown) {
    sweepConfluence = 0.9; // Swept lows = bullish
  } else if (!isBullish && liquidityData.recentSweepUp) {
    sweepConfluence = 0.9; // Swept highs = bearish
  } else if (isBullish && liquidityData.recentSweepUp) {
    sweepConfluence = 0.3; // Counter signal
  } else if (!isBullish && liquidityData.recentSweepDown) {
    sweepConfluence = 0.3; // Counter signal
  }
  
  // Zone distance
  let zoneDistance = 0.5;
  const dist = liquidityData.distanceToNearestZoneATR || 2;
  if (dist > 2) {
    zoneDistance = 0.8; // Good room to move
  } else if (dist > 1) {
    zoneDistance = 0.6;
  } else {
    zoneDistance = 0.3; // Close to resistance/support
  }
  
  // Liquidity bias
  let liquidityBias = 0.5;
  if (liquidityData.liquidityBias === 'BULLISH' && isBullish) {
    liquidityBias = 0.85;
  } else if (liquidityData.liquidityBias === 'BEARISH' && !isBullish) {
    liquidityBias = 0.85;
  } else if (liquidityData.liquidityBias === 'NEUTRAL') {
    liquidityBias = 0.5;
  } else if (liquidityData.liquidityBias) {
    liquidityBias = 0.3; // Counter bias
  }
  
  // Consider zone imbalance
  const above = liquidityData.zonesAbove || 0;
  const below = liquidityData.zonesBelow || 0;
  if (isBullish && above > below * 2) {
    liquidityBias *= 0.8; // Heavy liquidity above
  } else if (!isBullish && below > above * 2) {
    liquidityBias *= 0.8; // Heavy liquidity below
  }
  
  const overallScore = (sweepConfluence * 0.4 + zoneDistance * 0.3 + liquidityBias * 0.3);
  
  return {
    sweepConfluence,
    zoneDistance,
    liquidityBias,
    overallScore: Math.min(1, Math.max(0, overallScore)),
  };
}

/**
 * Compute structure-aware boost combining all layers
 */
export function computeStructureBoost(
  patternDirection: 'LONG' | 'SHORT',
  patternType: string,
  patternQuality: number,
  mlScore: number,
  contextData: any,
  marketStateData: any,
  liquidityData: any,
  config: StructureBoostConfig = DEFAULT_STRUCTURE_CONFIG
): StructureBoostResult {
  // Compute individual scores
  const contextScore = computeContextScore(patternDirection, contextData);
  const marketStateScore = computeMarketStateScore(patternDirection, patternType, marketStateData);
  const liquidityScore = computeLiquidityScore(patternDirection, liquidityData);
  
  // Normalize pattern quality and ML score to 0-1
  const patternQualityScore = Math.min(1, Math.max(0, patternQuality));
  const normalizedMlScore = Math.min(1, Math.max(0, mlScore));
  
  // Compute weighted contributions
  const contextContribution = contextScore.overallScore * config.weights.context;
  const marketStateContribution = marketStateScore.overallScore * config.weights.marketState;
  const liquidityContribution = liquidityScore.overallScore * config.weights.liquidity;
  const patternContribution = patternQualityScore * config.weights.patternQuality;
  const mlContribution = normalizedMlScore * config.weights.ml;
  
  // Total weighted score (0-1 range)
  const totalScore = contextContribution + marketStateContribution + 
                    liquidityContribution + patternContribution + mlContribution;
  
  // Convert to boost multiplier (centered at 1.0)
  // Score of 0.5 = boost of 1.0
  // Score of 1.0 = boost of 1.5
  // Score of 0.0 = boost of 0.5
  const structureBoost = 0.5 + totalScore;
  
  // Clamp
  const clampedBoost = Math.min(
    config.boostClamp.max,
    Math.max(config.boostClamp.min, structureBoost)
  );
  
  return {
    contextScore,
    marketStateScore,
    liquidityScore,
    patternQualityScore,
    mlScore: normalizedMlScore,
    structureBoost: clampedBoost,
    breakdown: {
      contextContribution,
      marketStateContribution,
      liquidityContribution,
      patternContribution,
      mlContribution,
    },
  };
}

/**
 * Service class for structure-aware scoring
 */
export class StructureAwareScoringService {
  private db: Db;
  private config: StructureBoostConfig;

  constructor(db: Db, config?: Partial<StructureBoostConfig>) {
    this.db = db;
    this.config = { ...DEFAULT_STRUCTURE_CONFIG, ...config };
  }

  /**
   * Fetch context data for asset/timeframe
   */
  async getContextData(asset: string, timeframe: string): Promise<any> {
    // Try to fetch from context API or cache
    try {
      const response = await fetch(
        `http://localhost:8001/api/ta/context/analyze?asset=${asset}&tf=${timeframe}`
      );
      if (response.ok) {
        const data = await response.json();
        return {
          trendDirection: data.trend?.direction,
          trendStrength: data.trend?.strength,
          impulseRecent: data.trend?.impulseRecent,
          structureContext: data.structure?.rangebound ? 'RANGE' : 
                          data.structure?.breakingUp ? 'BREAKOUT' : 'NEUTRAL',
          bullishScore: data.score?.bullish,
          bearishScore: data.score?.bearish,
        };
      }
    } catch (e) {
      // Fallback to neutral
    }
    return {};
  }

  /**
   * Fetch market state data for asset/timeframe
   */
  async getMarketStateData(asset: string, timeframe: string): Promise<any> {
    try {
      const response = await fetch(
        `http://localhost:8001/api/ta/marketState/state?asset=${asset}&tf=${timeframe}`
      );
      if (response.ok) {
        const data = await response.json();
        return {
          state: data.state,
          confidence: data.confidence,
          trendStrength: data.trendStrength,
          volatilityRegime: data.volatilityRegime,
          rangeScore: data.rangeScore,
        };
      }
    } catch (e) {
      // Fallback
    }
    return {};
  }

  /**
   * Fetch liquidity data for asset/timeframe
   */
  async getLiquidityData(asset: string, timeframe: string): Promise<any> {
    try {
      const response = await fetch(
        `http://localhost:8001/api/ta/liquidity/analyze?asset=${asset}&tf=${timeframe}`
      );
      if (response.ok) {
        const data = await response.json();
        return {
          recentSweepUp: data.metrics?.recentSweepUp,
          recentSweepDown: data.metrics?.recentSweepDown,
          liquidityBias: data.metrics?.liquidityBias,
          zonesAbove: data.metrics?.zonesAbove,
          zonesBelow: data.metrics?.zonesBelow,
          distanceToNearestZoneATR: data.metrics?.distanceToNearestZoneATR,
        };
      }
    } catch (e) {
      // Fallback
    }
    return {};
  }

  /**
   * Compute full structure-aware boost
   */
  async computeBoost(
    asset: string,
    timeframe: string,
    patternType: string,
    patternDirection: 'LONG' | 'SHORT',
    patternQuality: number,
    mlScore: number = 0.5
  ): Promise<StructureBoostResult> {
    // Fetch all data in parallel
    const [contextData, marketStateData, liquidityData] = await Promise.all([
      this.getContextData(asset, timeframe),
      this.getMarketStateData(asset, timeframe),
      this.getLiquidityData(asset, timeframe),
    ]);

    return computeStructureBoost(
      patternDirection,
      patternType,
      patternQuality,
      mlScore,
      contextData,
      marketStateData,
      liquidityData,
      this.config
    );
  }

  getConfig(): StructureBoostConfig {
    return { ...this.config };
  }

  updateConfig(update: Partial<StructureBoostConfig>): void {
    if (update.weights) {
      this.config.weights = { ...this.config.weights, ...update.weights };
    }
    if (update.boostClamp) {
      this.config.boostClamp = { ...this.config.boostClamp, ...update.boostClamp };
    }
  }
}
