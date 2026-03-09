/**
 * MetaBrain v1 — Risk Mode Engine
 * 
 * Determines system risk mode based on context
 */

import {
  MetaBrainContext,
  MetaRiskMode,
  MetaBrainConfig,
  DEFAULT_METABRAIN_CONFIG
} from './metabrain.types.js';

// ═══════════════════════════════════════════════════════════════
// RISK MODE DETERMINATION
// ═══════════════════════════════════════════════════════════════

/**
 * Compute risk mode from context
 */
export function computeRiskMode(
  context: MetaBrainContext,
  config: MetaBrainConfig = DEFAULT_METABRAIN_CONFIG
): { mode: MetaRiskMode; reasons: string[] } {
  const reasons: string[] = [];
  
  // ─────────────────────────────────────────────────────────────
  // CHECK FOR CONSERVATIVE CONDITIONS
  // ─────────────────────────────────────────────────────────────
  
  // High drawdown
  if (context.drawdownPct > config.conservativeDrawdownThreshold) {
    reasons.push(`High drawdown: ${(context.drawdownPct * 100).toFixed(1)}%`);
    return { mode: 'CONSERVATIVE', reasons };
  }
  
  // Extreme volatility
  if (context.volatility === 'EXTREME') {
    reasons.push('Extreme market volatility');
    return { mode: 'CONSERVATIVE', reasons };
  }
  
  // Governance frozen
  if (context.governanceFrozen) {
    reasons.push('Governance system frozen');
    return { mode: 'CONSERVATIVE', reasons };
  }
  
  // Weak edge health
  if (context.edgeHealth < config.conservativeEdgeHealthThreshold) {
    reasons.push(`Weak edge health: ${(context.edgeHealth * 100).toFixed(0)}%`);
    return { mode: 'CONSERVATIVE', reasons };
  }
  
  // Unfavorable market
  if (context.marketCondition === 'UNFAVORABLE') {
    reasons.push('Unfavorable market conditions');
    return { mode: 'CONSERVATIVE', reasons };
  }
  
  // ─────────────────────────────────────────────────────────────
  // CHECK FOR AGGRESSIVE CONDITIONS
  // ─────────────────────────────────────────────────────────────
  
  const aggressiveConditions: boolean[] = [
    context.drawdownPct < config.aggressiveDrawdownThreshold,
    context.edgeHealth > config.aggressiveEdgeHealthThreshold,
    context.bestStrategyScore > config.aggressiveStrategyScoreThreshold,
    ['TREND_EXPANSION', 'BREAKOUT_PREP', 'TREND_CONTINUATION'].includes(context.regime)
  ];
  
  const aggressiveCount = aggressiveConditions.filter(Boolean).length;
  
  if (aggressiveCount >= 3) {
    if (context.drawdownPct < config.aggressiveDrawdownThreshold) {
      reasons.push(`Low drawdown: ${(context.drawdownPct * 100).toFixed(1)}%`);
    }
    if (context.edgeHealth > config.aggressiveEdgeHealthThreshold) {
      reasons.push(`Strong edge: ${(context.edgeHealth * 100).toFixed(0)}%`);
    }
    if (context.bestStrategyScore > config.aggressiveStrategyScoreThreshold) {
      reasons.push(`High strategy score: ${context.bestStrategyScore.toFixed(2)}`);
    }
    if (['TREND_EXPANSION', 'BREAKOUT_PREP'].includes(context.regime)) {
      reasons.push(`Favorable regime: ${context.regime}`);
    }
    return { mode: 'AGGRESSIVE', reasons };
  }
  
  // ─────────────────────────────────────────────────────────────
  // DEFAULT TO NORMAL
  // ─────────────────────────────────────────────────────────────
  
  reasons.push('Standard market conditions');
  return { mode: 'NORMAL', reasons };
}

// ═══════════════════════════════════════════════════════════════
// RISK MODE TRANSITION VALIDATION
// ═══════════════════════════════════════════════════════════════

/**
 * Validate if mode transition is allowed
 */
export function validateModeTransition(
  currentMode: MetaRiskMode,
  newMode: MetaRiskMode,
  modeChangesToday: number,
  lastChangeTime: Date | null,
  config: MetaBrainConfig = DEFAULT_METABRAIN_CONFIG
): { allowed: boolean; reason?: string } {
  
  // Always allow transition to CONSERVATIVE (safety first)
  if (newMode === 'CONSERVATIVE') {
    return { allowed: true };
  }
  
  // Check daily limit
  if (modeChangesToday >= config.maxModeChangesPerDay) {
    return { 
      allowed: false, 
      reason: `Max mode changes per day reached: ${modeChangesToday}` 
    };
  }
  
  // Check time between changes
  if (lastChangeTime) {
    const minutesSinceLastChange = (Date.now() - lastChangeTime.getTime()) / (1000 * 60);
    if (minutesSinceLastChange < config.minTimeBetweenChanges) {
      return { 
        allowed: false, 
        reason: `Too soon since last change: ${Math.round(minutesSinceLastChange)}min < ${config.minTimeBetweenChanges}min` 
      };
    }
  }
  
  // Prevent direct CONSERVATIVE -> AGGRESSIVE
  if (currentMode === 'CONSERVATIVE' && newMode === 'AGGRESSIVE') {
    return { 
      allowed: false, 
      reason: 'Cannot jump directly from CONSERVATIVE to AGGRESSIVE' 
    };
  }
  
  return { allowed: true };
}

// ═══════════════════════════════════════════════════════════════
// RISK MODE SCORE (for gradual transitions)
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate a continuous risk score for smoother transitions
 */
export function calculateRiskScore(context: MetaBrainContext): number {
  let score = 50;  // Base: neutral
  
  // Drawdown impact (-30 to 0)
  score -= Math.min(30, context.drawdownPct * 300);
  
  // Volatility impact (-20 to +5)
  switch (context.volatility) {
    case 'LOW': score += 5; break;
    case 'NORMAL': score += 0; break;
    case 'HIGH': score -= 10; break;
    case 'EXTREME': score -= 20; break;
  }
  
  // Edge health impact (-15 to +20)
  score += (context.edgeHealth - 0.5) * 40;
  
  // Strategy score impact (0 to +15)
  score += Math.min(15, context.bestStrategyScore * 10);
  
  // Market condition impact (-10 to +10)
  switch (context.marketCondition) {
    case 'FAVORABLE': score += 10; break;
    case 'NEUTRAL': score += 0; break;
    case 'UNFAVORABLE': score -= 10; break;
  }
  
  // Governance frozen (-30)
  if (context.governanceFrozen) score -= 30;
  
  return Math.max(0, Math.min(100, score));
}

/**
 * Convert risk score to mode
 */
export function riskScoreToMode(score: number): MetaRiskMode {
  if (score < 35) return 'CONSERVATIVE';
  if (score > 70) return 'AGGRESSIVE';
  return 'NORMAL';
}
