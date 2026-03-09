/**
 * Explanation Rules (P4.3)
 * 
 * Attribution rules for different signal components
 */

import type { 
  AttributionRule, 
  BuildExplanationInput, 
  SignalDirection 
} from './explanation.types.js';

/**
 * Pattern direction mapping
 */
const BULLISH_PATTERNS = [
  'ASC', 'ASCENDING', 'BULL', 'BOTTOM', 'IHS', 'RISING'
];

const BEARISH_PATTERNS = [
  'DESC', 'DESCENDING', 'BEAR', 'TOP', 'HS', 'FALLING'
];

function getPatternDirection(type: string): SignalDirection {
  const upper = type.toUpperCase();
  if (BULLISH_PATTERNS.some(p => upper.includes(p))) return 'bullish';
  if (BEARISH_PATTERNS.some(p => upper.includes(p))) return 'bearish';
  return 'neutral';
}

/**
 * Core attribution rules
 */
export const ATTRIBUTION_RULES: AttributionRule[] = [
  // === PATTERN RULES ===
  {
    type: 'pattern',
    name: 'PRIMARY_PATTERN',
    condition: (input) => input.patterns.length > 0,
    contribution: (input) => {
      const top = input.patterns[0];
      return (top.score || 0.5) * 0.25;
    },
    description: (input) => {
      const top = input.patterns[0];
      return `${top.type} pattern detected with ${Math.round((top.confidence || 0.5) * 100)}% confidence`;
    },
    direction: (input) => getPatternDirection(input.patterns[0]?.type || '')
  },
  
  {
    type: 'pattern',
    name: 'PATTERN_CONFLUENCE',
    condition: (input) => input.patterns.length >= 2,
    contribution: (input) => {
      const count = Math.min(input.patterns.length, 5);
      return count * 0.03;
    },
    description: (input) => `${input.patterns.length} patterns in confluence`,
    direction: (input) => {
      const bullish = input.patterns.filter(p => getPatternDirection(p.type) === 'bullish').length;
      const bearish = input.patterns.filter(p => getPatternDirection(p.type) === 'bearish').length;
      if (bullish > bearish) return 'bullish';
      if (bearish > bullish) return 'bearish';
      return 'neutral';
    }
  },
  
  // === INDICATOR RULES ===
  {
    type: 'indicator',
    name: 'RSI_DIVERGENCE',
    condition: (input) => {
      const rsi = input.indicators?.find(i => i.name.includes('RSI') && i.signal === 'DIVERGENCE');
      return !!rsi;
    },
    contribution: (input) => {
      const rsi = input.indicators?.find(i => i.name.includes('RSI'));
      return (rsi?.strength || 0.5) * 0.08;
    },
    description: () => 'RSI divergence detected',
    direction: (input) => {
      const rsi = input.indicators?.find(i => i.name.includes('RSI'));
      if (rsi?.value && rsi.value < 30) return 'bullish';
      if (rsi?.value && rsi.value > 70) return 'bearish';
      return 'neutral';
    }
  },
  
  {
    type: 'indicator',
    name: 'MACD_CROSSOVER',
    condition: (input) => {
      const macd = input.indicators?.find(i => i.name.includes('MACD'));
      return !!macd && macd.signal === 'CROSSOVER';
    },
    contribution: (input) => {
      const macd = input.indicators?.find(i => i.name.includes('MACD'));
      return (macd?.strength || 0.5) * 0.06;
    },
    description: () => 'MACD crossover signal',
    direction: (input) => {
      const macd = input.indicators?.find(i => i.name.includes('MACD'));
      return macd?.value && macd.value > 0 ? 'bullish' : 'bearish';
    }
  },
  
  {
    type: 'indicator',
    name: 'BB_SQUEEZE',
    condition: (input) => {
      const bb = input.indicators?.find(i => i.name.includes('BB') || i.name.includes('BOLLINGER'));
      return !!bb && bb.signal === 'SQUEEZE';
    },
    contribution: () => 0.05,
    description: () => 'Bollinger Band squeeze detected - breakout imminent',
    direction: () => 'neutral'
  },
  
  // === ML RULES ===
  {
    type: 'ml',
    name: 'ML_PROBABILITY',
    condition: (input) => !!input.ml && input.ml.pEntry > 0.55,
    contribution: (input) => {
      const p = input.ml?.pEntry || 0.5;
      return (p - 0.5) * 0.4;
    },
    description: (input) => `ML model predicts ${Math.round((input.ml?.pEntry || 0.5) * 100)}% entry probability`,
    direction: (input) => {
      const p = input.ml?.pEntry || 0.5;
      return p > 0.55 ? 'bullish' : p < 0.45 ? 'bearish' : 'neutral';
    }
  },
  
  {
    type: 'ml',
    name: 'ML_EXPECTED_R',
    condition: (input) => !!input.ml && input.ml.expectedR > 1.0,
    contribution: (input) => {
      const r = input.ml?.expectedR || 0;
      return Math.min(0.15, r * 0.05);
    },
    description: (input) => `Expected R-multiple: ${(input.ml?.expectedR || 0).toFixed(2)}`,
    direction: (input) => (input.ml?.expectedR || 0) > 0 ? 'bullish' : 'bearish'
  },
  
  // === SCENARIO RULES ===
  {
    type: 'scenario',
    name: 'MC_PROBABILITY',
    condition: (input) => !!input.scenario && input.scenario.pTarget > 0.5,
    contribution: (input) => {
      const p = input.scenario?.pTarget || 0.5;
      return (p - 0.5) * 0.3;
    },
    description: (input) => `Monte Carlo simulation: ${Math.round((input.scenario?.pTarget || 0.5) * 100)}% target probability`,
    direction: (input) => (input.scenario?.pTarget || 0.5) > 0.5 ? 'bullish' : 'bearish'
  },
  
  {
    type: 'scenario',
    name: 'SCENARIO_PROJECTION',
    condition: (input) => !!input.scenario && input.scenario.p50 > 0,
    contribution: (input) => {
      const p50 = input.scenario?.p50 || 0;
      return Math.min(0.1, p50 * 0.03);
    },
    description: (input) => `Median projection: ${(input.scenario?.p50 || 0).toFixed(2)}R`,
    direction: (input) => (input.scenario?.p50 || 0) > 0 ? 'bullish' : 'bearish'
  },
  
  // === STABILITY RULES ===
  {
    type: 'stability',
    name: 'STABILITY_BOOST',
    condition: (input) => !!input.stability && input.stability.multiplier > 1.0,
    contribution: (input) => (input.stability?.multiplier || 1) - 1,
    description: (input) => `Stability boost: ${Math.round((input.stability?.multiplier || 1) * 100 - 100)}%`,
    direction: () => 'bullish'
  },
  
  {
    type: 'stability',
    name: 'STABILITY_WARNING',
    condition: (input) => !!input.stability && input.stability.degrading,
    contribution: () => -0.05,
    description: () => 'Pattern stability degrading - reduced confidence',
    direction: () => 'bearish'
  },
  
  // === REGIME RULES ===
  {
    type: 'regime',
    name: 'TREND_REGIME',
    condition: (input) => !!input.regime && input.regime.type.includes('TREND'),
    contribution: (input) => (input.regime?.confidence || 0.5) * 0.05,
    description: (input) => `${input.regime?.type} regime with ${Math.round((input.regime?.confidence || 0.5) * 100)}% confidence`,
    direction: (input) => input.regime?.type.includes('UP') ? 'bullish' : 'bearish'
  },
  
  // === GEOMETRY RULES ===
  {
    type: 'geometry',
    name: 'GEOMETRY_FIT',
    condition: (input) => !!input.geometry && input.geometry.fitError < 0.1,
    contribution: (input) => 0.05 * (1 - (input.geometry?.fitError || 0.1)),
    description: () => 'High geometry fit quality',
    direction: () => 'bullish'
  },
  
  {
    type: 'geometry',
    name: 'GEOMETRY_MATURITY',
    condition: (input) => !!input.geometry && input.geometry.maturity > 0.7,
    contribution: (input) => (input.geometry?.maturity || 0) * 0.05,
    description: (input) => `Pattern ${Math.round((input.geometry?.maturity || 0) * 100)}% mature`,
    direction: () => 'neutral'
  },
  
  {
    type: 'geometry',
    name: 'COMPRESSION_SIGNAL',
    condition: (input) => !!input.geometry && input.geometry.compression > 0.6,
    contribution: (input) => (input.geometry?.compression || 0) * 0.04,
    description: () => 'High compression - breakout likely',
    direction: () => 'neutral'
  }
];

/**
 * Get applicable rules for input
 */
export function getApplicableRules(input: BuildExplanationInput): AttributionRule[] {
  return ATTRIBUTION_RULES.filter(rule => rule.condition(input));
}
