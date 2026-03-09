/**
 * Realtime Broadcast Engine
 * 
 * Provides channel-level broadcast functions.
 * broadcast("chart", payload) → sends to all clients subscribed to "chart" channel
 */

import { realtimeHub } from './realtime.hub.js';
import { RealtimeEvent, RealtimeEventType } from './realtime.types.js';
import { ChannelName, CHANNEL_EVENT_MAP } from './realtime.channels.js';

/**
 * Broadcast an event through the hub (goes to all matching subscribers)
 */
export function broadcast(event: RealtimeEvent): void {
  realtimeHub.publish(event);
}

/**
 * Get which channel an event belongs to
 */
export function getChannelForEvent(eventType: RealtimeEventType): ChannelName | null {
  for (const [channel, types] of Object.entries(CHANNEL_EVENT_MAP)) {
    if (types.includes(eventType)) {
      return channel as ChannelName;
    }
  }
  return null;
}

/**
 * Get broadcast stats per channel
 */
export function getChannelStats(): Record<ChannelName, number> {
  const stats = realtimeHub.getStats();
  const result: Record<string, number> = {};

  for (const channel of Object.keys(CHANNEL_EVENT_MAP)) {
    const types = CHANNEL_EVENT_MAP[channel as ChannelName];
    const count = stats.topEventTypes
      .filter(t => types.includes(t.type))
      .reduce((sum, t) => sum + t.count, 0);
    result[channel] = count;
  }

  return result as Record<ChannelName, number>;
}
