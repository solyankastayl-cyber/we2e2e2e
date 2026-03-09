/**
 * Phase 2.5 — Market Map Timeline
 * =================================
 * Generates expected event sequence timeline
 * Shows what events are likely to happen and when
 */

import { TimelineResponse, TimelineEvent } from './market_map.types.js';
import { MarketState } from './market_map.types.js';

// ═══════════════════════════════════════════════════════════════
// EVENT DEFINITIONS
// ═══════════════════════════════════════════════════════════════

interface EventTemplate {
  event: string;
  baseProbability: number;
  impact: 'HIGH' | 'MEDIUM' | 'LOW';
  description: string;
  fromStates: MarketState[];
  hoursFromNow: number;  // expected time
}

const EVENT_TEMPLATES: EventTemplate[] = [
  // Compression events
  {
    event: 'compression',
    baseProbability: 0.72,
    impact: 'MEDIUM',
    description: 'Volatility squeeze, preparing for breakout',
    fromStates: ['COMPRESSION', 'RANGE'],
    hoursFromNow: 2,
  },
  {
    event: 'liquidity_sweep',
    baseProbability: 0.48,
    impact: 'HIGH',
    description: 'Stop hunt below/above key level',
    fromStates: ['COMPRESSION', 'RANGE', 'LIQUIDITY_SWEEP'],
    hoursFromNow: 4,
  },
  {
    event: 'breakout',
    baseProbability: 0.63,
    impact: 'HIGH',
    description: 'Price breaks out of range/compression',
    fromStates: ['COMPRESSION', 'BREAKOUT'],
    hoursFromNow: 6,
  },
  {
    event: 'expansion',
    baseProbability: 0.57,
    impact: 'HIGH',
    description: 'Trend acceleration after breakout',
    fromStates: ['BREAKOUT', 'EXPANSION', 'CONTINUATION'],
    hoursFromNow: 12,
  },
  // Reversal events
  {
    event: 'exhaustion',
    baseProbability: 0.42,
    impact: 'MEDIUM',
    description: 'Momentum fading, potential top/bottom',
    fromStates: ['EXPANSION', 'EXHAUSTION'],
    hoursFromNow: 18,
  },
  {
    event: 'reversal',
    baseProbability: 0.35,
    impact: 'HIGH',
    description: 'Trend reversal signal',
    fromStates: ['EXHAUSTION', 'REVERSAL'],
    hoursFromNow: 24,
  },
  // Continuation events
  {
    event: 'retest',
    baseProbability: 0.55,
    impact: 'MEDIUM',
    description: 'Price returns to test breakout level',
    fromStates: ['BREAKOUT', 'EXPANSION', 'RETEST'],
    hoursFromNow: 8,
  },
  {
    event: 'continuation',
    baseProbability: 0.51,
    impact: 'MEDIUM',
    description: 'Trend resumes after pullback',
    fromStates: ['RETEST', 'CONTINUATION'],
    hoursFromNow: 16,
  },
  // Range events
  {
    event: 'range_bound',
    baseProbability: 0.38,
    impact: 'LOW',
    description: 'Price oscillates in defined range',
    fromStates: ['RANGE', 'REVERSAL'],
    hoursFromNow: 10,
  },
  {
    event: 'false_breakout',
    baseProbability: 0.28,
    impact: 'HIGH',
    description: 'Breakout fails and price reverses',
    fromStates: ['BREAKOUT'],
    hoursFromNow: 5,
  },
];

// ═══════════════════════════════════════════════════════════════
// STATE DETECTION (simplified)
// ═══════════════════════════════════════════════════════════════

function detectCurrentState(symbol: string): MarketState {
  const states: MarketState[] = [
    'COMPRESSION', 'BREAKOUT', 'EXPANSION', 'RANGE',
    'RETEST', 'CONTINUATION', 'EXHAUSTION'
  ];
  
  const hour = new Date().getHours();
  return states[hour % states.length];
}

// ═══════════════════════════════════════════════════════════════
// TIMELINE GENERATION
// ═══════════════════════════════════════════════════════════════

/**
 * Generate event timeline for a symbol
 */
export async function getTimeline(
  symbol: string,
  timeframe: string = '1d',
  maxEvents: number = 8
): Promise<TimelineResponse> {
  const currentState = detectCurrentState(symbol);
  const now = Date.now();
  const hourMs = 60 * 60 * 1000;
  
  // Filter events applicable to current state
  const applicableEvents = EVENT_TEMPLATES.filter(
    e => e.fromStates.includes(currentState)
  );
  
  // If few applicable, use all events
  const eventPool = applicableEvents.length >= 3 
    ? applicableEvents 
    : EVENT_TEMPLATES;
  
  // Generate timeline events with adjusted probabilities
  const events: TimelineEvent[] = [];
  
  for (const template of eventPool) {
    // Adjust probability based on current state
    let adjustedProb = template.baseProbability;
    
    if (template.fromStates.includes(currentState)) {
      adjustedProb *= 1.2;  // Boost if directly applicable
    }
    
    // Add randomness
    adjustedProb *= (0.85 + Math.random() * 0.3);
    adjustedProb = Math.min(0.95, Math.max(0.1, adjustedProb));
    
    const expectedTime = now + template.hoursFromNow * hourMs;
    
    events.push({
      event: template.event,
      probability: Math.round(adjustedProb * 100) / 100,
      expectedTime,
      impact: template.impact,
      description: template.description,
    });
  }
  
  // Sort by expected time
  events.sort((a, b) => (a.expectedTime || 0) - (b.expectedTime || 0));
  
  // Take top N events
  const topEvents = events.slice(0, maxEvents);
  
  // Build most probable sequence
  const sortedByProb = [...topEvents].sort((a, b) => b.probability - a.probability);
  const sequence = sortedByProb.slice(0, 4).map(e => e.event);
  
  return {
    symbol,
    timeframe,
    ts: now,
    events: topEvents,
    sequence,
  };
}

/**
 * Get most probable next event
 */
export function getMostProbableNextEvent(
  currentState: MarketState
): TimelineEvent | null {
  const applicable = EVENT_TEMPLATES.filter(
    e => e.fromStates.includes(currentState)
  );
  
  if (applicable.length === 0) return null;
  
  const best = applicable.reduce((max, e) => 
    e.baseProbability > max.baseProbability ? e : max
  );
  
  return {
    event: best.event,
    probability: best.baseProbability,
    expectedTime: Date.now() + best.hoursFromNow * 60 * 60 * 1000,
    impact: best.impact,
    description: best.description,
  };
}
