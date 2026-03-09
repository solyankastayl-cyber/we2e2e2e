/**
 * Explanation Attribution (P4.3)
 * 
 * Core attribution logic for calculating contributions
 */

import type { 
  ExplanationNode, 
  BuildExplanationInput,
  SignalDirection 
} from './explanation.types.js';
import { getApplicableRules } from './explanation.rules.js';

/**
 * Build explanation nodes from input
 */
export function buildExplanationNodes(input: BuildExplanationInput): ExplanationNode[] {
  const nodes: ExplanationNode[] = [];
  const rules = getApplicableRules(input);
  
  for (const rule of rules) {
    const contribution = rule.contribution(input);
    const direction = rule.direction(input);
    const description = rule.description(input);
    
    // Only add meaningful contributions
    if (Math.abs(contribution) >= 0.01) {
      nodes.push({
        type: rule.type,
        name: rule.name,
        contribution,
        direction,
        confidence: Math.min(1, Math.abs(contribution) * 5), // Scale to confidence
        description
      });
    }
  }
  
  // Sort by absolute contribution
  nodes.sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution));
  
  return nodes;
}

/**
 * Calculate total score from nodes
 */
export function calculateTotalScore(nodes: ExplanationNode[]): number {
  return nodes.reduce((sum, node) => {
    // Bullish adds, bearish subtracts
    const sign = node.direction === 'bearish' ? -1 : 1;
    return sum + node.contribution * sign;
  }, 0);
}

/**
 * Get dominant drivers (top positive contributors)
 */
export function getDominantDrivers(nodes: ExplanationNode[], limit: number = 3): string[] {
  return nodes
    .filter(n => n.contribution > 0 && n.direction !== 'bearish')
    .slice(0, limit)
    .map(n => n.name);
}

/**
 * Get risk factors (negative or warning signals)
 */
export function getRiskFactors(nodes: ExplanationNode[]): string[] {
  return nodes
    .filter(n => n.contribution < 0 || n.direction === 'bearish')
    .map(n => n.name);
}

/**
 * Calculate net direction
 */
export function calculateNetDirection(nodes: ExplanationNode[]): SignalDirection {
  let bullishScore = 0;
  let bearishScore = 0;
  
  for (const node of nodes) {
    if (node.direction === 'bullish') {
      bullishScore += Math.abs(node.contribution);
    } else if (node.direction === 'bearish') {
      bearishScore += Math.abs(node.contribution);
    }
  }
  
  if (bullishScore > bearishScore + 0.05) return 'bullish';
  if (bearishScore > bullishScore + 0.05) return 'bearish';
  return 'neutral';
}

/**
 * Generate summary text
 */
export function generateSummary(
  nodes: ExplanationNode[],
  totalScore: number,
  direction: SignalDirection
): string {
  const topDrivers = nodes.slice(0, 3).map(n => n.name.replace(/_/g, ' ').toLowerCase());
  const riskFactors = nodes.filter(n => n.contribution < 0);
  
  let summary = '';
  
  if (direction === 'bullish') {
    summary = `Bullish signal (score: ${totalScore.toFixed(2)})`;
  } else if (direction === 'bearish') {
    summary = `Bearish signal (score: ${totalScore.toFixed(2)})`;
  } else {
    summary = `Neutral/mixed signal (score: ${totalScore.toFixed(2)})`;
  }
  
  if (topDrivers.length > 0) {
    summary += `. Main drivers: ${topDrivers.join(', ')}`;
  }
  
  if (riskFactors.length > 0) {
    summary += `. Risk factors: ${riskFactors.length}`;
  }
  
  return summary;
}
