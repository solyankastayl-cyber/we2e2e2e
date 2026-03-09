/**
 * Realtime Channels — Channel-based subscription mapping
 * 
 * Channels provide a simplified subscription interface:
 *   subscribe("chart", "BTCUSDT") → auto-subscribes to CANDLE_UPDATE, PATTERN_DETECTED, SCENARIO_UPDATE
 *   subscribe("signals") → auto-subscribes to SIGNAL_UPDATE, SIGNAL_CREATED
 */

import { RealtimeEventType } from './realtime.types.js';

// ═══════════════════════════════════════════════════════════════
// CHANNEL DEFINITIONS
// ═══════════════════════════════════════════════════════════════

export type ChannelName = 'chart' | 'signals' | 'system' | 'regime' | 'metabrain';

export const CHANNEL_EVENT_MAP: Record<ChannelName, RealtimeEventType[]> = {
  chart: [
    'CANDLE_UPDATE',
    'PATTERN_DETECTED',
    'SCENARIO_UPDATE',
    'MARKET_MAP_UPDATE',
  ],
  signals: [
    'SIGNAL_UPDATE',
    'SIGNAL_CREATED',
  ],
  system: [
    'SYSTEM_HEALTH',
    'SAFE_MODE_TRIGGER',
    'MODULE_GATE_CHANGE',
  ],
  regime: [
    'REGIME_UPDATE',
    'STATE_UPDATE',
  ],
  metabrain: [
    'METABRAIN_UPDATE',
    'EDGE_ALERT',
    'TWIN_UPDATE',
    'MEMORY_MATCH',
    'TREE_UPDATE',
  ],
};

export const ALL_CHANNELS: ChannelName[] = ['chart', 'signals', 'system', 'regime', 'metabrain'];

/**
 * Resolve a channel name to event type filters
 */
export function resolveChannelFilter(channel: ChannelName, symbol?: string) {
  const eventTypes = CHANNEL_EVENT_MAP[channel];
  if (!eventTypes) return null;

  return {
    eventTypes,
    assets: symbol ? [symbol] : undefined,
  };
}
