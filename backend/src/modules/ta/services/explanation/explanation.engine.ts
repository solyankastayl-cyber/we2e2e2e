/**
 * Explanation Engine (P4.3)
 * 
 * Main engine that builds ExplanationPack
 */

import type { 
  ExplanationPack, 
  BuildExplanationInput 
} from './explanation.types.js';
import {
  buildExplanationNodes,
  calculateTotalScore,
  getDominantDrivers,
  getRiskFactors,
  calculateNetDirection,
  generateSummary
} from './explanation.attribution.js';

/**
 * Build complete explanation pack
 */
export function buildExplanation(input: BuildExplanationInput): ExplanationPack {
  // Build nodes
  const nodes = buildExplanationNodes(input);
  
  // Calculate aggregates
  const totalScore = calculateTotalScore(nodes);
  const dominantDrivers = getDominantDrivers(nodes, 5);
  const riskFactors = getRiskFactors(nodes);
  const direction = calculateNetDirection(nodes);
  
  // Generate summary
  const summary = generateSummary(nodes, totalScore, direction);
  
  // Calculate overall confidence
  let confidence = 0.5;
  if (nodes.length > 0) {
    // More nodes with consistent direction = higher confidence
    const directionCounts = nodes.reduce((acc, n) => {
      acc[n.direction] = (acc[n.direction] || 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    
    const maxDirection = Math.max(...Object.values(directionCounts));
    const consistency = maxDirection / nodes.length;
    
    confidence = Math.min(0.9, 0.3 + consistency * 0.6);
  }
  
  return {
    totalScore,
    nodes,
    dominantDrivers,
    riskFactors,
    summary,
    confidence
  };
}

/**
 * Build explanation with debug info
 */
export function buildExplanationDebug(input: BuildExplanationInput): {
  pack: ExplanationPack;
  debug: {
    inputSummary: {
      patternsCount: number;
      indicatorsCount: number;
      hasML: boolean;
      hasScenario: boolean;
      hasStability: boolean;
    };
    rulesApplied: number;
    contributionBreakdown: Record<string, number>;
  };
} {
  const pack = buildExplanation(input);
  
  // Calculate contribution breakdown by type
  const contributionBreakdown: Record<string, number> = {};
  for (const node of pack.nodes) {
    contributionBreakdown[node.type] = (contributionBreakdown[node.type] || 0) + node.contribution;
  }
  
  return {
    pack,
    debug: {
      inputSummary: {
        patternsCount: input.patterns.length,
        indicatorsCount: input.indicators?.length || 0,
        hasML: !!input.ml,
        hasScenario: !!input.scenario,
        hasStability: !!input.stability
      },
      rulesApplied: pack.nodes.length,
      contributionBreakdown
    }
  };
}

/**
 * Quick explanation for a single pattern
 */
export function explainPattern(
  patternType: string,
  score: number,
  confidence: number
): string {
  const direction = patternType.includes('BULL') || patternType.includes('ASC') || patternType.includes('BOTTOM')
    ? 'bullish'
    : patternType.includes('BEAR') || patternType.includes('DESC') || patternType.includes('TOP')
    ? 'bearish'
    : 'neutral';
  
  return `${patternType}: ${direction} signal with ${Math.round(score * 100)}% strength, ${Math.round(confidence * 100)}% confidence`;
}
