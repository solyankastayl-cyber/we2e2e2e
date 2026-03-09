/**
 * G1 — Transition Statistics Calculator
 * 
 * Computes transition probabilities between market events
 */

import { MarketEvent, EventTransition, MarketEventType } from './market_graph.types.js';

export interface TransitionStats {
  transitions: EventTransition[];
  totalPairs: number;
  uniqueTransitions: number;
}

/**
 * Compute transition statistics from event sequence
 */
export function computeTransitions(events: MarketEvent[]): TransitionStats {
  if (events.length < 2) {
    return { transitions: [], totalPairs: 0, uniqueTransitions: 0 };
  }
  
  // Count transitions
  const transitionCounts = new Map<string, {
    from: MarketEventType;
    fromPattern?: string;
    to: MarketEventType;
    toPattern?: string;
    count: number;
    barsBetweenSum: number;
  }>();
  
  // Count total occurrences of each "from" event
  const fromCounts = new Map<string, number>();
  
  let totalPairs = 0;
  
  for (let i = 0; i < events.length - 1; i++) {
    const from = events[i];
    const to = events[i + 1];
    
    // Key includes pattern type for more specific transitions
    const key = `${from.type}|${from.patternType || ''}|${to.type}|${to.patternType || ''}`;
    const fromKey = `${from.type}|${from.patternType || ''}`;
    
    // Update from counts
    fromCounts.set(fromKey, (fromCounts.get(fromKey) || 0) + 1);
    
    // Update transition counts
    const existing = transitionCounts.get(key);
    const barsBetween = to.barIndex - from.barIndex;
    
    if (existing) {
      existing.count++;
      existing.barsBetweenSum += Math.max(0, barsBetween);
    } else {
      transitionCounts.set(key, {
        from: from.type,
        fromPattern: from.patternType,
        to: to.type,
        toPattern: to.patternType,
        count: 1,
        barsBetweenSum: Math.max(0, barsBetween),
      });
    }
    
    totalPairs++;
  }
  
  // Convert to transitions with probabilities
  const transitions: EventTransition[] = [];
  
  for (const [key, data] of transitionCounts) {
    const fromKey = `${data.from}|${data.fromPattern || ''}`;
    const fromTotal = fromCounts.get(fromKey) || 1;
    
    transitions.push({
      from: data.from,
      fromPattern: data.fromPattern,
      to: data.to,
      toPattern: data.toPattern,
      count: data.count,
      probability: data.count / fromTotal,
      avgBarsBetween: data.count > 0 ? data.barsBetweenSum / data.count : 0,
    });
  }
  
  // Sort by probability
  transitions.sort((a, b) => b.probability - a.probability);
  
  return {
    transitions,
    totalPairs,
    uniqueTransitions: transitions.length,
  };
}

/**
 * Get most likely next events given a current event type
 */
export function predictNextEvents(
  currentType: MarketEventType,
  currentPattern: string | undefined,
  transitions: EventTransition[],
  topN: number = 5
): Array<{ event: MarketEventType; pattern?: string; probability: number; avgBarsAhead: number }> {
  // Find matching transitions
  let matching = transitions.filter(t => t.from === currentType);
  
  // If pattern specified, prefer pattern-specific transitions
  if (currentPattern) {
    const patternMatches = matching.filter(t => t.fromPattern === currentPattern);
    if (patternMatches.length > 0) {
      matching = patternMatches;
    }
  }
  
  // Sort by probability and take top N
  return matching
    .sort((a, b) => b.probability - a.probability)
    .slice(0, topN)
    .map(t => ({
      event: t.to,
      pattern: t.toPattern,
      probability: t.probability,
      avgBarsAhead: t.avgBarsBetween,
    }));
}

/**
 * Find the most likely path from current state
 */
export function findBestPath(
  startType: MarketEventType,
  transitions: EventTransition[],
  maxDepth: number = 5,
  endEvents: MarketEventType[] = ['TARGET_HIT', 'STOP_HIT', 'FAILURE']
): { path: MarketEventType[]; probability: number } {
  let bestPath: MarketEventType[] = [];
  let bestProb = 0;
  
  function dfs(
    current: MarketEventType,
    path: MarketEventType[],
    cumProb: number,
    depth: number
  ): void {
    if (depth >= maxDepth || endEvents.includes(current)) {
      if (cumProb > bestProb) {
        bestProb = cumProb;
        bestPath = [...path];
      }
      return;
    }
    
    const nextOptions = transitions
      .filter(t => t.from === current)
      .sort((a, b) => b.probability - a.probability)
      .slice(0, 3); // Limit branching
    
    for (const option of nextOptions) {
      dfs(
        option.to,
        [...path, option.to],
        cumProb * option.probability,
        depth + 1
      );
    }
  }
  
  dfs(startType, [startType], 1, 0);
  
  return { path: bestPath, probability: bestProb };
}

/**
 * Compute chain score for a sequence of events
 */
export function computeChainScore(
  chain: MarketEvent[],
  transitions: EventTransition[]
): { score: number; confidence: number; matchedTransitions: number } {
  if (chain.length < 2) {
    return { score: 0.5, confidence: 0, matchedTransitions: 0 };
  }
  
  let totalProb = 0;
  let matchedTransitions = 0;
  
  for (let i = 0; i < chain.length - 1; i++) {
    const from = chain[i];
    const to = chain[i + 1];
    
    // Find matching transition
    const transition = transitions.find(t => 
      t.from === from.type && t.to === to.type &&
      (!t.fromPattern || t.fromPattern === from.patternType)
    );
    
    if (transition) {
      totalProb += transition.probability;
      matchedTransitions++;
    }
  }
  
  const score = matchedTransitions > 0 ? totalProb / matchedTransitions : 0.5;
  const confidence = matchedTransitions / (chain.length - 1);
  
  return { score, confidence, matchedTransitions };
}
