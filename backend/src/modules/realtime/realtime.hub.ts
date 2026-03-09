/**
 * Real-time WebSocket Layer — Event Hub
 * 
 * Central hub for publishing and routing events
 */

import { EventEmitter } from 'events';
import {
  RealtimeEvent,
  RealtimeEventType,
  SubscriptionFilter,
  Subscription,
  ClientConnection,
  RealtimeStats,
  BaseRealtimeEvent
} from './realtime.types.js';

// ═══════════════════════════════════════════════════════════════
// EVENT HUB
// ═══════════════════════════════════════════════════════════════

class RealtimeEventHub extends EventEmitter {
  private connections: Map<string, ClientConnection> = new Map();
  private subscriptions: Map<string, Subscription> = new Map();
  private eventCounts: Map<RealtimeEventType, number> = new Map();
  private recentEvents: RealtimeEvent[] = [];
  private maxRecentEvents = 1000;

  constructor() {
    super();
    this.setMaxListeners(100);
  }

  // ─────────────────────────────────────────────────────────────
  // CONNECTION MANAGEMENT
  // ─────────────────────────────────────────────────────────────

  addConnection(connection: ClientConnection): void {
    this.connections.set(connection.id, connection);
    console.log(`[RealtimeHub] Client connected: ${connection.id}`);
    this.emit('connection', connection);
  }

  removeConnection(clientId: string): void {
    const connection = this.connections.get(clientId);
    if (connection) {
      // Remove all subscriptions for this client
      connection.subscriptions.forEach(sub => {
        this.subscriptions.delete(sub.id);
      });
      this.connections.delete(clientId);
      console.log(`[RealtimeHub] Client disconnected: ${clientId}`);
      this.emit('disconnection', clientId);
    }
  }

  getConnection(clientId: string): ClientConnection | undefined {
    return this.connections.get(clientId);
  }

  updatePing(clientId: string): void {
    const connection = this.connections.get(clientId);
    if (connection) {
      connection.lastPing = new Date();
    }
  }

  // ─────────────────────────────────────────────────────────────
  // SUBSCRIPTION MANAGEMENT
  // ─────────────────────────────────────────────────────────────

  subscribe(clientId: string, filter: SubscriptionFilter): Subscription | null {
    const connection = this.connections.get(clientId);
    if (!connection) return null;

    const subscription: Subscription = {
      id: `sub_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      clientId,
      filter,
      createdAt: new Date()
    };

    connection.subscriptions.push(subscription);
    this.subscriptions.set(subscription.id, subscription);

    console.log(`[RealtimeHub] Subscription created: ${subscription.id} for client ${clientId}`);
    return subscription;
  }

  unsubscribe(subscriptionId: string): boolean {
    const subscription = this.subscriptions.get(subscriptionId);
    if (!subscription) return false;

    const connection = this.connections.get(subscription.clientId);
    if (connection) {
      connection.subscriptions = connection.subscriptions.filter(s => s.id !== subscriptionId);
    }

    this.subscriptions.delete(subscriptionId);
    return true;
  }

  // ─────────────────────────────────────────────────────────────
  // EVENT PUBLISHING
  // ─────────────────────────────────────────────────────────────

  publish(event: RealtimeEvent): void {
    // Store event
    this.recentEvents.push(event);
    if (this.recentEvents.length > this.maxRecentEvents) {
      this.recentEvents.shift();
    }

    // Update counts
    const count = this.eventCounts.get(event.type) || 0;
    this.eventCounts.set(event.type, count + 1);

    // Emit for internal listeners
    this.emit('event', event);
    this.emit(event.type, event);

    // Route to subscribed clients
    this.routeToClients(event);
  }

  private routeToClients(event: RealtimeEvent): void {
    for (const [clientId, connection] of this.connections) {
      for (const subscription of connection.subscriptions) {
        if (this.matchesFilter(event, subscription.filter)) {
          this.sendToClient(connection, event);
          break; // Only send once per client
        }
      }
    }
  }

  private matchesFilter(event: RealtimeEvent, filter: SubscriptionFilter): boolean {
    // Check asset filter
    if (filter.assets && filter.assets.length > 0) {
      if (!filter.assets.includes(event.asset)) return false;
    }

    // Check timeframe filter
    if (filter.timeframes && filter.timeframes.length > 0) {
      if (!filter.timeframes.includes(event.timeframe)) return false;
    }

    // Check event type filter
    if (filter.eventTypes && filter.eventTypes.length > 0) {
      if (!filter.eventTypes.includes(event.type)) return false;
    }

    // Check priority filter
    if (filter.minPriority) {
      const priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
      const eventPriorityIndex = priorities.indexOf(event.priority);
      const minPriorityIndex = priorities.indexOf(filter.minPriority);
      if (eventPriorityIndex < minPriorityIndex) return false;
    }

    return true;
  }

  private sendToClient(connection: ClientConnection, event: RealtimeEvent): void {
    try {
      if (connection.socket && connection.socket.readyState === 1) { // OPEN
        connection.socket.send(JSON.stringify(event));
      }
    } catch (err) {
      console.error(`[RealtimeHub] Error sending to client ${connection.id}:`, err);
    }
  }

  // ─────────────────────────────────────────────────────────────
  // STATS & QUERIES
  // ─────────────────────────────────────────────────────────────

  getStats(): RealtimeStats {
    const now = Date.now();
    const oneMinuteAgo = now - 60 * 1000;
    const oneHourAgo = now - 60 * 60 * 1000;

    const eventsLastMinute = this.recentEvents.filter(e => e.timestamp > oneMinuteAgo).length;
    const eventsLastHour = this.recentEvents.filter(e => e.timestamp > oneHourAgo).length;

    // Top event types
    const typeCounts = Array.from(this.eventCounts.entries())
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    return {
      activeConnections: this.connections.size,
      totalSubscriptions: this.subscriptions.size,
      eventsPublishedLastMinute: eventsLastMinute,
      eventsPublishedLastHour: eventsLastHour,
      topEventTypes: typeCounts,
      avgLatencyMs: 0 // Would be calculated from actual measurements
    };
  }

  getRecentEvents(limit: number = 50, filter?: SubscriptionFilter): RealtimeEvent[] {
    let events = [...this.recentEvents].reverse();

    if (filter) {
      events = events.filter(e => this.matchesFilter(e, filter));
    }

    return events.slice(0, limit);
  }

  getConnectionCount(): number {
    return this.connections.size;
  }

  getAllConnections(): ClientConnection[] {
    return Array.from(this.connections.values());
  }
}

// Singleton instance
export const realtimeHub = new RealtimeEventHub();

// ═══════════════════════════════════════════════════════════════
// EVENT FACTORIES
// ═══════════════════════════════════════════════════════════════

export function createBaseEvent(
  type: RealtimeEventType,
  asset: string,
  timeframe: string,
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' = 'MEDIUM'
): BaseRealtimeEvent {
  return {
    type,
    asset,
    timeframe,
    timestamp: Date.now(),
    priority
  };
}

export function publishEvent(event: RealtimeEvent): void {
  realtimeHub.publish(event);
}
