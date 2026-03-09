/**
 * Phase 6.5 — MTF Context Builder
 * 
 * Builds context from 3 timeframes:
 * - Higher TF for direction/regime/structure
 * - Anchor TF for main scenario
 * - Lower TF for momentum/entry confirmation
 */

import { Bias, TFContext, MTFContextInput, MTF_MAP, Timeframe } from './mtf.types.js';

/**
 * Extract bias from decision pack
 */
function extractBias(pack: any): Bias {
  // Try multiple paths
  const topBias = pack?.topBias || 
                  pack?.summary?.topBias || 
                  pack?.topScenario?.intent ||
                  pack?.scenarios?.[0]?.direction;
  
  if (topBias === 'LONG' || topBias === 'BULL' || topBias === 'BULLISH') return 'BULL';
  if (topBias === 'SHORT' || topBias === 'BEAR' || topBias === 'BEARISH') return 'BEAR';
  return 'NEUTRAL';
}

/**
 * Extract direction from pack
 */
function extractDirection(pack: any): 'LONG' | 'SHORT' | 'WAIT' {
  const bias = extractBias(pack);
  if (bias === 'BULL') return 'LONG';
  if (bias === 'BEAR') return 'SHORT';
  return 'WAIT';
}

/**
 * Extract regime from pack
 */
function extractRegime(pack: any): string {
  return pack?.regime?.market ||
         pack?.snapshot?.marketRegime ||
         pack?.meta?.marketRegime ||
         pack?.topScenario?.regime?.market ||
         'UNKNOWN';
}

/**
 * Extract volatility regime
 */
function extractVolRegime(pack: any): string {
  return pack?.regime?.volatility ||
         pack?.snapshot?.volRegime ||
         pack?.meta?.volRegime ||
         'NORMAL';
}

/**
 * Extract structure from pack
 */
function extractStructure(pack: any): { structure: string; strength: number } {
  const struct = pack?.structure?.direction ||
                 pack?.snapshot?.structure ||
                 pack?.topScenario?.structure ||
                 'NEUTRAL';
  
  const strength = pack?.structure?.strength ||
                   pack?.snapshot?.structureStrength ||
                   0.5;
  
  return { structure: struct, strength };
}

/**
 * Extract top scenario
 */
function extractTopScenario(pack: any): TFContext['topScenario'] | undefined {
  const scenario = pack?.topScenario || pack?.scenarios?.[0];
  if (!scenario) return undefined;
  
  return {
    id: scenario.scenarioId || scenario.id,
    direction: scenario.direction || scenario.intent,
    probability: scenario.probability || scenario.finalScore || 0.5,
    type: scenario.patternType || scenario.type || 'unknown'
  };
}

/**
 * Extract momentum indicators (mainly for lower TF)
 */
function extractMomentum(pack: any): TFContext['momentum'] | undefined {
  const indicators = pack?.indicators || pack?.momentum;
  if (!indicators) return undefined;
  
  const rsiValue = indicators.rsi?.value || indicators.rsiValue || 50;
  
  let rsiBias: Bias = 'NEUTRAL';
  if (rsiValue > 60) rsiBias = 'BULL';
  else if (rsiValue < 40) rsiBias = 'BEAR';
  
  let macdBias: Bias = 'NEUTRAL';
  const macdHist = indicators.macd?.histogram || indicators.macdHistogram || 0;
  if (macdHist > 0) macdBias = 'BULL';
  else if (macdHist < 0) macdBias = 'BEAR';
  
  // Overall momentum bias
  let overallBias: Bias = 'NEUTRAL';
  if (rsiBias === 'BULL' && macdBias === 'BULL') overallBias = 'BULL';
  else if (rsiBias === 'BEAR' && macdBias === 'BEAR') overallBias = 'BEAR';
  else if (rsiBias === 'BULL' || macdBias === 'BULL') overallBias = 'BULL';
  else if (rsiBias === 'BEAR' || macdBias === 'BEAR') overallBias = 'BEAR';
  
  return {
    rsiValue,
    rsiBias,
    macdBias,
    overallBias
  };
}

/**
 * Build TF Context from decision pack
 */
export function buildTFContext(tf: string, pack: any): TFContext {
  const { structure, strength } = extractStructure(pack);
  
  return {
    tf,
    bias: extractBias(pack),
    direction: extractDirection(pack),
    regime: extractRegime(pack),
    volRegime: extractVolRegime(pack),
    structure,
    structureStrength: strength,
    topScenario: extractTopScenario(pack),
    momentum: extractMomentum(pack),
    pack
  };
}

/**
 * Get timeframe hierarchy for anchor TF
 */
export function getTFHierarchy(anchorTf: string): { higher: string; lower: string } {
  const tfKey = anchorTf.toLowerCase() as Timeframe;
  const mapping = MTF_MAP[tfKey];
  
  if (mapping) {
    return {
      higher: mapping.higher,
      lower: mapping.lower
    };
  }
  
  // Default fallback
  return {
    higher: '1d',
    lower: '1h'
  };
}

/**
 * Build full MTF context from 3 TF packs
 */
export interface MTFContext {
  symbol: string;
  anchorTf: string;
  higherTf: string;
  lowerTf: string;
  
  higher: TFContext;
  anchor: TFContext;
  lower: TFContext;
}

export async function buildMTFContext(
  input: MTFContextInput,
  fetchDecisionPack?: (symbol: string, tf: string) => Promise<any>
): Promise<MTFContext> {
  const { symbol, anchorTf } = input;
  const { higher: higherTf, lower: lowerTf } = getTFHierarchy(anchorTf);
  
  // Get packs (from input or fetch)
  let higherPack = input.higherTfPack;
  let anchorPack = input.anchorTfPack;
  let lowerPack = input.lowerTfPack;
  
  // Fetch missing packs if fetcher provided
  if (fetchDecisionPack) {
    if (!higherPack) higherPack = await fetchDecisionPack(symbol, higherTf);
    if (!anchorPack) anchorPack = await fetchDecisionPack(symbol, anchorTf);
    if (!lowerPack) lowerPack = await fetchDecisionPack(symbol, lowerTf);
  }
  
  return {
    symbol,
    anchorTf,
    higherTf,
    lowerTf,
    higher: buildTFContext(higherTf, higherPack || {}),
    anchor: buildTFContext(anchorTf, anchorPack || {}),
    lower: buildTFContext(lowerTf, lowerPack || {})
  };
}

/**
 * Create mock context for testing
 */
export function createMockMTFContext(
  symbol: string,
  anchorTf: string,
  overrides?: Partial<{
    higherBias: Bias;
    higherRegime: string;
    lowerMomentum: Bias;
    anchorDirection: 'LONG' | 'SHORT' | 'WAIT';
  }>
): MTFContext {
  const { higher: higherTf, lower: lowerTf } = getTFHierarchy(anchorTf);
  
  return {
    symbol,
    anchorTf,
    higherTf,
    lowerTf,
    higher: {
      tf: higherTf,
      bias: overrides?.higherBias || 'BULL',
      direction: overrides?.higherBias === 'BEAR' ? 'SHORT' : 'LONG',
      regime: overrides?.higherRegime || 'TREND_UP',
      volRegime: 'NORMAL',
      structure: overrides?.higherBias === 'BEAR' ? 'BEARISH' : 'BULLISH',
      structureStrength: 0.7
    },
    anchor: {
      tf: anchorTf,
      bias: overrides?.anchorDirection === 'SHORT' ? 'BEAR' : 'BULL',
      direction: overrides?.anchorDirection || 'LONG',
      regime: 'TREND_UP',
      volRegime: 'NORMAL',
      structure: 'BULLISH',
      structureStrength: 0.65,
      topScenario: {
        id: 'test_scenario',
        direction: overrides?.anchorDirection || 'LONG',
        probability: 0.68,
        type: 'BREAKOUT'
      }
    },
    lower: {
      tf: lowerTf,
      bias: overrides?.lowerMomentum || 'BULL',
      direction: overrides?.lowerMomentum === 'BEAR' ? 'SHORT' : 'LONG',
      regime: 'TREND_UP',
      volRegime: 'NORMAL',
      structure: 'BULLISH',
      structureStrength: 0.6,
      momentum: {
        rsiValue: overrides?.lowerMomentum === 'BEAR' ? 35 : 65,
        rsiBias: overrides?.lowerMomentum || 'BULL',
        macdBias: overrides?.lowerMomentum || 'BULL',
        overallBias: overrides?.lowerMomentum || 'BULL'
      }
    }
  };
}
