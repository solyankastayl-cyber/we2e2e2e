/**
 * Phase 4 — Explain Engine
 * ==========================
 * Generates human-readable explanations for decisions
 */

import { ExplainResponse, ExplainFactor, ScoreBreakdown } from './observability.types.js';
import { getDecisionById, getRecentDecisions } from './logs.decision.service.js';

// ═══════════════════════════════════════════════════════════════
// FACTOR DESCRIPTIONS
// ═══════════════════════════════════════════════════════════════

const FACTOR_DESCRIPTIONS: Record<string, string> = {
  pattern: 'Technical pattern detected with structural analysis',
  liquidity: 'Liquidity sweep or absorption zone identified',
  scenario: 'Scenario engine probability for this outcome',
  memory: 'Historical similarity from memory engine',
  regime: 'Market regime alignment with signal direction',
  graph: 'Graph neural network edge boost',
  physics: 'Physics engine pressure calculation',
};

// ═══════════════════════════════════════════════════════════════
// NARRATIVE GENERATION
// ═══════════════════════════════════════════════════════════════

function generateNarrative(
  signal: string,
  score: number,
  breakdown: ScoreBreakdown,
  regime: string,
  scenario: string,
  memoryMatches: number
): string {
  const parts: string[] = [];
  
  // Signal strength
  if (score >= 0.7) {
    parts.push(`Strong ${signal} signal detected (score: ${score.toFixed(2)}).`);
  } else if (score >= 0.5) {
    parts.push(`Moderate ${signal} signal (score: ${score.toFixed(2)}).`);
  } else {
    parts.push(`Weak ${signal} indication (score: ${score.toFixed(2)}).`);
  }
  
  // Main contributors
  const sorted = Object.entries(breakdown)
    .filter(([_, v]) => v > 0)
    .sort(([, a], [, b]) => b - a);
  
  if (sorted.length > 0) {
    const [topFactor, topValue] = sorted[0];
    parts.push(`Primary driver: ${topFactor} (${(topValue * 100).toFixed(0)}% contribution).`);
  }
  
  // Regime context
  parts.push(`Market regime: ${regime}.`);
  
  // Scenario
  parts.push(`Active scenario: ${scenario}.`);
  
  // Memory
  if (memoryMatches > 10) {
    parts.push(`Strong historical support with ${memoryMatches} similar patterns found.`);
  } else if (memoryMatches > 5) {
    parts.push(`Moderate historical support (${memoryMatches} matches).`);
  }
  
  return parts.join(' ');
}

// ═══════════════════════════════════════════════════════════════
// EXPLAIN FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Explain a specific decision by ID
 */
export function explainDecision(decisionId: string): ExplainResponse | null {
  const decision = getDecisionById(decisionId);
  if (!decision) return null;
  
  const factors: ExplainFactor[] = [];
  const totalWeight = Object.values(decision.breakdown).reduce((s, v) => s + v, 0);
  
  for (const [name, contribution] of Object.entries(decision.breakdown)) {
    if (contribution > 0) {
      factors.push({
        name,
        contribution,
        weight: totalWeight > 0 ? Math.round((contribution / totalWeight) * 100) / 100 : 0,
        description: FACTOR_DESCRIPTIONS[name] || 'Unknown factor',
      });
    }
  }
  
  factors.sort((a, b) => b.contribution - a.contribution);
  
  return {
    symbol: decision.symbol,
    timestamp: decision.timestamp,
    decision: {
      signal: decision.signal,
      score: decision.score,
      confidence: decision.confidence,
    },
    scoreBreakdown: decision.breakdown,
    factors,
    narrative: generateNarrative(
      decision.signal,
      decision.score,
      decision.breakdown,
      decision.regime,
      decision.scenario,
      decision.memoryMatches
    ),
  };
}

/**
 * Explain the most recent decision for a symbol
 */
export function explainLatestDecision(symbol: string): ExplainResponse | null {
  const recent = getRecentDecisions(50);
  const forSymbol = recent.find(d => d.symbol === symbol && d.signal !== 'NO_TRADE');
  
  if (!forSymbol) return null;
  return explainDecision(forSymbol.id);
}

/**
 * Get decision factors summary
 */
export function getFactorsSummary(): {
  avgContributions: Record<string, number>;
  topFactors: string[];
} {
  const contributions: Record<string, number[]> = {};
  const decisions = getRecentDecisions(100);
  
  for (const decision of decisions) {
    for (const [factor, value] of Object.entries(decision.breakdown)) {
      if (!contributions[factor]) contributions[factor] = [];
      contributions[factor].push(value);
    }
  }
  
  const avgContributions: Record<string, number> = {};
  for (const [factor, values] of Object.entries(contributions)) {
    avgContributions[factor] = Math.round((values.reduce((s, v) => s + v, 0) / values.length) * 100) / 100;
  }
  
  const topFactors = Object.entries(avgContributions)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3)
    .map(([f]) => f);
  
  return { avgContributions, topFactors };
}
