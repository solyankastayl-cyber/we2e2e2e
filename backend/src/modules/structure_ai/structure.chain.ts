/**
 * Phase 7 — Market Structure AI: Chain Analyzer
 * 
 * Analyzes event chains and predicts next events
 */

import {
  MarketEvent,
  MarketEventType,
  EventChain,
  EventDirection,
  StructureType,
  EVENT_CHAINS,
  EVENT_TRANSITIONS
} from './structure.types.js';

/**
 * Find matching event chain
 */
export function findMatchingChain(
  events: MarketEvent[]
): { chain: string; progress: number; expectedNext: MarketEventType[] } | null {
  if (events.length === 0) return null;
  
  const eventTypes = events.map(e => e.type);
  
  let bestMatch: { chain: string; progress: number; expectedNext: MarketEventType[] } | null = null;
  let bestScore = 0;
  
  for (const [chainName, chainEvents] of Object.entries(EVENT_CHAINS)) {
    // Check how many events from this chain are present
    let matchedCount = 0;
    let lastMatchIndex = -1;
    
    for (const eventType of eventTypes) {
      const index = chainEvents.indexOf(eventType);
      if (index !== -1 && index > lastMatchIndex) {
        matchedCount++;
        lastMatchIndex = index;
      }
    }
    
    const progress = matchedCount / chainEvents.length;
    const score = progress * (matchedCount / eventTypes.length);
    
    if (score > bestScore && matchedCount > 0) {
      bestScore = score;
      
      // Find expected next events
      const nextIndex = lastMatchIndex + 1;
      const expectedNext = nextIndex < chainEvents.length 
        ? chainEvents.slice(nextIndex, nextIndex + 2)
        : [];
      
      bestMatch = {
        chain: chainName,
        progress,
        expectedNext
      };
    }
  }
  
  return bestMatch;
}

/**
 * Build event chain from detected events
 */
export function buildEventChain(events: MarketEvent[]): EventChain | null {
  if (events.length === 0) return null;
  
  const matchedChain = findMatchingChain(events);
  if (!matchedChain) return null;
  
  const chainTemplate = EVENT_CHAINS[matchedChain.chain];
  const eventTypes = events.map(e => e.type);
  
  // Find completed and expected
  const completed: MarketEventType[] = [];
  let currentIndex = 0;
  
  for (const event of chainTemplate) {
    if (eventTypes.includes(event)) {
      completed.push(event);
      currentIndex++;
    } else {
      break;
    }
  }
  
  const expected = chainTemplate.slice(currentIndex);
  
  // Calculate chain probability
  const avgProbability = events.reduce((sum, e) => sum + e.probability, 0) / events.length;
  const avgStrength = events.reduce((sum, e) => sum + e.strength, 0) / events.length;
  
  // Determine direction
  let direction: EventDirection = 'NEUTRAL';
  const lastDirectionalEvent = events.find(e => e.direction !== 'NEUTRAL');
  if (lastDirectionalEvent) {
    direction = lastDirectionalEvent.direction;
  }
  
  return {
    id: `chain_${Date.now()}`,
    events: chainTemplate,
    currentIndex,
    completed,
    expected,
    probability: avgProbability * matchedChain.progress,
    strength: avgStrength,
    direction
  };
}

/**
 * Get expected next events based on current event
 */
export function getExpectedNextEvents(
  currentEvent: MarketEventType,
  topN: number = 3
): { event: MarketEventType; probability: number }[] {
  const transitions = EVENT_TRANSITIONS[currentEvent];
  if (!transitions) return [];
  
  const sorted = Object.entries(transitions)
    .map(([event, prob]) => ({ event: event as MarketEventType, probability: prob }))
    .sort((a, b) => b.probability - a.probability)
    .slice(0, topN);
  
  return sorted;
}

/**
 * Calculate chain completion probability
 */
export function calculateChainProbability(
  events: MarketEvent[],
  chain: EventChain
): number {
  if (events.length === 0) return 0;
  
  // Base probability from events
  const eventProbability = events.reduce((sum, e) => sum + e.probability, 0) / events.length;
  
  // Chain progress boost
  const progressBoost = chain.completed.length / chain.events.length;
  
  // Transition probability
  let transitionProb = 1;
  for (let i = 0; i < chain.completed.length - 1; i++) {
    const from = chain.completed[i];
    const to = chain.completed[i + 1];
    const prob = EVENT_TRANSITIONS[from]?.[to] || 0.3;
    transitionProb *= prob;
  }
  
  // Weighted combination
  const finalProb = (eventProbability * 0.4) + (progressBoost * 0.3) + (transitionProb * 0.3);
  
  return Math.min(finalProb, 0.95);
}

/**
 * Determine structure type from events
 */
export function determineStructureType(events: MarketEvent[]): StructureType {
  if (events.length === 0) return 'RANGE_EXPANSION';
  
  const eventTypes = new Set(events.map(e => e.type));
  
  // Check for specific patterns
  if (eventTypes.has('LIQUIDITY_SWEEP') && eventTypes.has('COMPRESSION')) {
    return 'SWEEP_REVERSAL';
  }
  
  if (eventTypes.has('ACCUMULATION') && eventTypes.has('BREAKOUT')) {
    return 'ACCUMULATION_BREAKOUT';
  }
  
  if (eventTypes.has('DISTRIBUTION') && eventTypes.has('BREAKOUT')) {
    return 'DISTRIBUTION_BREAKDOWN';
  }
  
  if (eventTypes.has('FAKE_BREAKOUT') && eventTypes.has('REVERSAL')) {
    return 'FALSE_BREAKOUT_REVERSAL';
  }
  
  if (eventTypes.has('EXHAUSTION') && eventTypes.has('REVERSAL')) {
    return 'EXHAUSTION_REVERSAL';
  }
  
  if (eventTypes.has('COMPRESSION') && eventTypes.has('BREAKOUT')) {
    return 'COMPRESSION_BREAKOUT';
  }
  
  if (eventTypes.has('EXPANSION') || eventTypes.has('TREND_CONTINUATION')) {
    return 'TREND_CONTINUATION';
  }
  
  return 'RANGE_EXPANSION';
}

/**
 * Generate narrative from events
 */
export function generateNarrative(
  events: MarketEvent[],
  chain: EventChain | null,
  structureType: StructureType
): string {
  if (events.length === 0) {
    return 'No significant market events detected.';
  }
  
  const parts: string[] = [];
  
  // Structure type description
  const structureDescriptions: Record<StructureType, string> = {
    'SWEEP_REVERSAL': 'Market shows sweep reversal pattern',
    'COMPRESSION_BREAKOUT': 'Market in compression, preparing for breakout',
    'ACCUMULATION_BREAKOUT': 'Accumulation phase with potential bullish breakout',
    'DISTRIBUTION_BREAKDOWN': 'Distribution phase with potential bearish breakdown',
    'TREND_CONTINUATION': 'Trend continuation setup',
    'RANGE_EXPANSION': 'Range bound with expansion potential',
    'FALSE_BREAKOUT_REVERSAL': 'False breakout leading to reversal',
    'EXHAUSTION_REVERSAL': 'Exhaustion pattern suggesting reversal'
  };
  
  parts.push(structureDescriptions[structureType]);
  
  // Current events
  if (events.length > 0) {
    const topEvents = events.slice(0, 3).map(e => e.type.replace(/_/g, ' ').toLowerCase());
    parts.push(`Current events: ${topEvents.join(', ')}`);
  }
  
  // Chain progress
  if (chain && chain.expected.length > 0) {
    const nextEvents = chain.expected.slice(0, 2).map(e => e.replace(/_/g, ' ').toLowerCase());
    parts.push(`Expected next: ${nextEvents.join(' → ')}`);
  }
  
  // Direction
  if (chain && chain.direction !== 'NEUTRAL') {
    parts.push(`Direction bias: ${chain.direction}`);
  }
  
  return parts.join('. ') + '.';
}
