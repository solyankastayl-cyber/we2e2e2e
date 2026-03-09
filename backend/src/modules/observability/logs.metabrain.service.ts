/**
 * Phase 4 — MetaBrain Logs Service
 * ==================================
 * Logs MetaBrain state changes and decisions
 */

import { v4 as uuidv4 } from 'uuid';
import { MetaBrainLog } from './observability.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY STORAGE
// ═══════════════════════════════════════════════════════════════

const metabrainLogs: MetaBrainLog[] = [];

// Seed demo data
const seedMetaBrainLogs = () => {
  const events: MetaBrainLog['event'][] = ['RISK_MODE_CHANGE', 'SAFE_MODE_TOGGLE', 'MODULE_GATE', 'WEIGHT_ADJUST', 'RECOMPUTE'];
  const triggers: MetaBrainLog['trigger'][] = ['AUTO', 'MANUAL', 'REGIME', 'VOLATILITY'];
  const reasons = [
    'volatility spike detected',
    'regime change to RANGE',
    'memory similarity drop',
    'scheduled recomputation',
    'manual override activated',
    'risk threshold exceeded',
  ];
  
  const now = Date.now();
  
  for (let i = 0; i < 20; i++) {
    const event = events[Math.floor(Math.random() * events.length)];
    
    metabrainLogs.push({
      id: `mb_${uuidv4().slice(0, 8)}`,
      timestamp: now - (20 - i) * 7200000,
      event,
      previousState: { riskMode: 'NORMAL', safeMode: false },
      newState: { riskMode: event === 'RISK_MODE_CHANGE' ? 'CONSERVATIVE' : 'NORMAL', safeMode: event === 'SAFE_MODE_TOGGLE' },
      reason: reasons[Math.floor(Math.random() * reasons.length)],
      trigger: triggers[Math.floor(Math.random() * triggers.length)],
    });
  }
};

seedMetaBrainLogs();

// ═══════════════════════════════════════════════════════════════
// LOG FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Log MetaBrain event
 */
export function logMetaBrainEvent(
  event: MetaBrainLog['event'],
  previousState: Record<string, any>,
  newState: Record<string, any>,
  reason: string,
  trigger: MetaBrainLog['trigger']
): MetaBrainLog {
  const log: MetaBrainLog = {
    id: `mb_${uuidv4().slice(0, 8)}`,
    timestamp: Date.now(),
    event,
    previousState,
    newState,
    reason,
    trigger,
  };
  
  metabrainLogs.push(log);
  
  if (metabrainLogs.length > 200) {
    metabrainLogs.shift();
  }
  
  return log;
}

/**
 * Get MetaBrain logs
 */
export function getMetaBrainLogs(options: {
  event?: MetaBrainLog['event'];
  trigger?: MetaBrainLog['trigger'];
  limit?: number;
} = {}): MetaBrainLog[] {
  let filtered = [...metabrainLogs];
  
  if (options.event) {
    filtered = filtered.filter(l => l.event === options.event);
  }
  
  if (options.trigger) {
    filtered = filtered.filter(l => l.trigger === options.trigger);
  }
  
  filtered.sort((a, b) => b.timestamp - a.timestamp);
  
  return filtered.slice(0, options.limit || 50);
}

/**
 * Get MetaBrain stats
 */
export function getMetaBrainStats(): {
  total: number;
  byEvent: Record<string, number>;
  byTrigger: Record<string, number>;
  lastEvent: MetaBrainLog | null;
} {
  const byEvent: Record<string, number> = {};
  const byTrigger: Record<string, number> = {};
  
  for (const log of metabrainLogs) {
    byEvent[log.event] = (byEvent[log.event] || 0) + 1;
    byTrigger[log.trigger] = (byTrigger[log.trigger] || 0) + 1;
  }
  
  return {
    total: metabrainLogs.length,
    byEvent,
    byTrigger,
    lastEvent: metabrainLogs.length > 0 
      ? metabrainLogs.sort((a, b) => b.timestamp - a.timestamp)[0] 
      : null,
  };
}
