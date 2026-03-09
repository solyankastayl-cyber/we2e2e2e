/**
 * MetaBrain v1 — Context Builder
 * 
 * Collects global context from all system modules
 */

import {
  MetaBrainContext,
  VolatilityLevel
} from './metabrain.types.js';

// ═══════════════════════════════════════════════════════════════
// CONTEXT SOURCES (interfaces for loose coupling)
// ═══════════════════════════════════════════════════════════════

export interface RegimeSource {
  regime: string;
  confidence: number;
}

export interface StateSource {
  state: string;
}

export interface PhysicsSource {
  volatility: number;
  atrRatio: number;
}

export interface PortfolioSource {
  accountSize: number;
  unrealizedPnL: number;
  realizedPnL: number;
  totalRisk: number;
  openPositions: number;
}

export interface EdgeSource {
  avgProfitFactor: number;
  recentWinRate: number;
  edgeTrend: number;  // -1 to 1
}

export interface StrategySource {
  bestScore: number;
  activeCount: number;
}

export interface GovernanceSource {
  frozen: boolean;
}

// ═══════════════════════════════════════════════════════════════
// VOLATILITY CLASSIFICATION
// ═══════════════════════════════════════════════════════════════

export function classifyVolatility(atrRatio: number): VolatilityLevel {
  if (atrRatio < 0.7) return 'LOW';
  if (atrRatio < 1.3) return 'NORMAL';
  if (atrRatio < 2.0) return 'HIGH';
  return 'EXTREME';
}

// ═══════════════════════════════════════════════════════════════
// EDGE HEALTH CALCULATION
// ═══════════════════════════════════════════════════════════════

export function calculateEdgeHealth(edge: EdgeSource): number {
  // Combine metrics into 0-1 score
  let health = 0.5;  // Base
  
  // Profit factor contribution (PF 1.0 -> 0, PF 1.5 -> 0.25, PF 2.0 -> 0.5)
  const pfContrib = Math.min(0.5, (edge.avgProfitFactor - 1) * 0.5);
  health += pfContrib;
  
  // Win rate contribution (WR 50% -> 0, WR 60% -> 0.2, WR 70% -> 0.4)
  const wrContrib = Math.min(0.4, (edge.recentWinRate - 0.5) * 2);
  health += wrContrib;
  
  // Trend adjustment
  health += edge.edgeTrend * 0.1;
  
  return Math.max(0, Math.min(1, health));
}

// ═══════════════════════════════════════════════════════════════
// MARKET CONDITION ASSESSMENT
// ═══════════════════════════════════════════════════════════════

export function assessMarketCondition(
  regime: string,
  volatility: VolatilityLevel,
  edgeHealth: number
): 'FAVORABLE' | 'NEUTRAL' | 'UNFAVORABLE' {
  const favorableRegimes = ['TREND_EXPANSION', 'TREND_CONTINUATION', 'BREAKOUT_PREP'];
  const unfavorableRegimes = ['VOLATILITY_EXPANSION', 'LIQUIDITY_HUNT'];
  
  let score = 0;
  
  // Regime contribution
  if (favorableRegimes.includes(regime)) score += 2;
  else if (unfavorableRegimes.includes(regime)) score -= 2;
  
  // Volatility contribution
  if (volatility === 'NORMAL') score += 1;
  else if (volatility === 'EXTREME') score -= 2;
  else if (volatility === 'HIGH') score -= 1;
  
  // Edge health contribution
  if (edgeHealth > 0.6) score += 2;
  else if (edgeHealth < 0.4) score -= 1;
  
  if (score >= 3) return 'FAVORABLE';
  if (score <= -2) return 'UNFAVORABLE';
  return 'NEUTRAL';
}

// ═══════════════════════════════════════════════════════════════
// MAIN CONTEXT BUILDER
// ═══════════════════════════════════════════════════════════════

export function buildMetaBrainContext(
  regimeSource: RegimeSource,
  stateSource: StateSource,
  physicsSource: PhysicsSource,
  portfolioSource: PortfolioSource,
  edgeSource: EdgeSource,
  strategySource: StrategySource,
  governanceSource: GovernanceSource
): MetaBrainContext {
  // Classify volatility
  const volatility = classifyVolatility(physicsSource.atrRatio);
  
  // Calculate edge health
  const edgeHealth = calculateEdgeHealth(edgeSource);
  
  // Calculate drawdown
  const drawdownPct = portfolioSource.unrealizedPnL < 0
    ? Math.abs(portfolioSource.unrealizedPnL / portfolioSource.accountSize)
    : 0;
  
  // Portfolio risk %
  const portfolioRiskPct = portfolioSource.totalRisk;
  
  // Assess market condition
  const marketCondition = assessMarketCondition(
    regimeSource.regime,
    volatility,
    edgeHealth
  );
  
  return {
    regime: regimeSource.regime,
    regimeConfidence: regimeSource.confidence,
    state: stateSource.state,
    volatility,
    volatilityValue: physicsSource.atrRatio,
    drawdownPct,
    portfolioRiskPct,
    openPositions: portfolioSource.openPositions,
    edgeHealth,
    bestStrategyScore: strategySource.bestScore,
    activeStrategiesCount: strategySource.activeCount,
    governanceFrozen: governanceSource.frozen,
    marketCondition,
    computedAt: new Date()
  };
}

// ═══════════════════════════════════════════════════════════════
// DEFAULT CONTEXT (for testing/fallback)
// ═══════════════════════════════════════════════════════════════

export function getDefaultContext(): MetaBrainContext {
  return {
    regime: 'COMPRESSION',
    regimeConfidence: 0.5,
    state: 'NEUTRAL',
    volatility: 'NORMAL',
    volatilityValue: 1.0,
    drawdownPct: 0,
    portfolioRiskPct: 0,
    openPositions: 0,
    edgeHealth: 0.5,
    bestStrategyScore: 0,
    activeStrategiesCount: 0,
    governanceFrozen: false,
    marketCondition: 'NEUTRAL',
    computedAt: new Date()
  };
}
