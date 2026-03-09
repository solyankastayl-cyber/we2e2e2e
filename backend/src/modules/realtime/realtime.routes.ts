/**
 * Real-time WebSocket Layer — HTTP Routes
 * 
 * REST API for realtime status, event querying, and simulator control
 * 
 * Routes:
 *   GET  /api/ta/realtime/status      — Hub + WebSocket status
 *   GET  /api/ta/realtime/events      — Recent events
 *   GET  /api/ta/realtime/connections  — Active WS connections
 *   GET  /api/ta/realtime/stats       — Detailed stats
 *   POST /api/ta/realtime/test        — Publish test event
 *
 *   GET  /api/realtime/health         — Health check
 *   GET  /api/realtime/status         — Connection & channel stats
 *   POST /api/realtime/simulate/start — Start event simulator
 *   POST /api/realtime/simulate/stop  — Stop event simulator
 *   GET  /api/realtime/simulate/status — Simulator status
 *   POST /api/realtime/publish        — Publish arbitrary event
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { realtimeHub } from './realtime.hub.js';
import { getWebSocketStats } from './realtime.server.js';
import { SubscriptionFilter, RealtimeEventType } from './realtime.types.js';
import { ALL_CHANNELS, CHANNEL_EVENT_MAP } from './realtime.channels.js';
import { getChannelStats } from './realtime.broadcast.js';
import { startSimulator, stopSimulator, getSimulatorStatus } from './realtime.simulator.js';
import {
  publishMetaBrainUpdate,
  publishSignalUpdate,
  publishTreeUpdate,
  publishMemoryMatch,
  publishCandleUpdate,
  publishPatternDetected,
  publishSignalCreated,
  publishScenarioUpdate,
  publishRegimeUpdate
} from './realtime.publishers.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerRealtimeRoutes(fastify: FastifyInstance): Promise<void> {

  // ─────────────────────────────────────────────────────────────
  // EXISTING ROUTES (under /api/ta/realtime/)
  // ─────────────────────────────────────────────────────────────

  fastify.get('/api/ta/realtime/status', async () => {
    const stats = realtimeHub.getStats();
    const wsStats = getWebSocketStats();
    return {
      success: true,
      data: { websocket: wsStats, hub: stats, uptime: process.uptime() }
    };
  });

  fastify.get('/api/ta/realtime/events', async (
    req: FastifyRequest<{
      Querystring: { limit?: string; asset?: string; tf?: string; types?: string; priority?: string }
    }>
  ) => {
    const { limit, asset, tf, types, priority } = req.query;
    const filter: SubscriptionFilter = {};
    if (asset) filter.assets = [asset];
    if (tf) filter.timeframes = [tf];
    if (types) filter.eventTypes = types.split(',') as RealtimeEventType[];
    if (priority) filter.minPriority = priority as any;

    const events = realtimeHub.getRecentEvents(limit ? parseInt(limit, 10) : 50, filter);
    return { success: true, data: { events, count: events.length } };
  });

  fastify.get('/api/ta/realtime/connections', async () => {
    const connections = realtimeHub.getAllConnections();
    return {
      success: true,
      data: {
        count: connections.length,
        connections: connections.map(c => ({
          id: c.id,
          connectedAt: c.connectedAt,
          lastPing: c.lastPing,
          subscriptionCount: c.subscriptions.length,
          metadata: c.metadata
        }))
      }
    };
  });

  fastify.get('/api/ta/realtime/stats', async () => {
    const stats = realtimeHub.getStats();
    return { success: true, data: stats };
  });

  fastify.post('/api/ta/realtime/test', async (
    req: FastifyRequest<{ Body: { type?: string; asset?: string; tf?: string } }>
  ) => {
    const { type = 'METABRAIN_UPDATE', asset = 'BTCUSDT', tf = '1d' } = req.body ?? {};

    switch (type) {
      case 'METABRAIN_UPDATE':
        publishMetaBrainUpdate(asset, tf, 'DEEP_MARKET', 'NORMAL', false, 1.0,
          ['TREND_FOLLOW', 'BREAKOUT'], ['MEAN_REVERSION'], ['Test event']);
        break;
      case 'SIGNAL_UPDATE':
        publishSignalUpdate(asset, tf, 'ENTRY', 'LONG', 0.75, 0.8,
          'ASCENDING_TRIANGLE', 'BREAKOUT', 45000, 43000);
        break;
      case 'TREE_UPDATE':
        publishTreeUpdate(asset, tf, 0.72, 0.35, 0.28, 5, 'EXPANSION');
        break;
      case 'MEMORY_MATCH':
        publishMemoryMatch(asset, tf, 28, 0.68, 'BULL', 0.82, 0.63);
        break;
      case 'CANDLE_UPDATE':
        publishCandleUpdate(asset, '1m', {
          t: Date.now(), o: 87000, h: 87500, l: 86800, c: 87300, v: 1200
        });
        break;
      case 'PATTERN_DETECTED':
        publishPatternDetected(asset, tf, 'ascending_triangle', 'BULLISH', 0.78, 87000, 'Test pattern');
        break;
      case 'SIGNAL_CREATED':
        publishSignalCreated(asset, tf, 'LONG', 87500, 84200, 94000, 0.72, 'BREAKOUT', 'Test signal');
        break;
      case 'SCENARIO_UPDATE':
        publishScenarioUpdate(asset, tf, 'bullish_breakout', 0.62,
          [{ scenario: 'range', probability: 0.28 }], 0.15);
        break;
      case 'REGIME_CHANGE':
        publishRegimeUpdate(asset, tf, 'COMPRESSION' as any, 'TREND' as any, 0.75, 'Test regime change');
        break;
      default:
        return { success: false, error: `Unknown event type: ${type}` };
    }

    return {
      success: true,
      data: { type, asset, timeframe: tf, publishedAt: new Date().toISOString() }
    };
  });

  // ─────────────────────────────────────────────────────────────
  // NEW ROUTES (under /api/realtime/)
  // ─────────────────────────────────────────────────────────────

  /**
   * GET /api/realtime/health — Health check
   */
  fastify.get('/api/realtime/health', async () => {
    return { ok: true, status: 'healthy', ts: Date.now() };
  });

  /**
   * GET /api/realtime/status — Connection & channel stats
   */
  fastify.get('/api/realtime/status', async () => {
    const wsStats = getWebSocketStats();
    const hubStats = realtimeHub.getStats();
    const channelStats = getChannelStats();

    return {
      ok: true,
      data: {
        connections: wsStats.connected,
        readyConnections: wsStats.ready,
        channels: channelStats,
        availableChannels: ALL_CHANNELS,
        channelEventMap: CHANNEL_EVENT_MAP,
        eventsLastMinute: hubStats.eventsPublishedLastMinute,
        eventsLastHour: hubStats.eventsPublishedLastHour,
        totalSubscriptions: hubStats.totalSubscriptions,
        simulator: getSimulatorStatus(),
      }
    };
  });

  /**
   * POST /api/realtime/simulate/start — Start event simulator
   */
  fastify.post('/api/realtime/simulate/start', async (
    req: FastifyRequest<{ Body: { intervalMs?: number } }>
  ) => {
    const intervalMs = req.body?.intervalMs || 2000;
    startSimulator(intervalMs);
    return { ok: true, data: { started: true, intervalMs } };
  });

  /**
   * POST /api/realtime/simulate/stop — Stop event simulator
   */
  fastify.post('/api/realtime/simulate/stop', async () => {
    stopSimulator();
    return { ok: true, data: { stopped: true } };
  });

  /**
   * GET /api/realtime/simulate/status — Simulator status
   */
  fastify.get('/api/realtime/simulate/status', async () => {
    return { ok: true, data: getSimulatorStatus() };
  });

  /**
   * POST /api/realtime/publish — Publish arbitrary event
   */
  fastify.post('/api/realtime/publish', async (
    req: FastifyRequest<{
      Body: {
        event: string;
        symbol?: string;
        data?: Record<string, any>;
      }
    }>
  ) => {
    const { event, symbol = 'BTCUSDT', data = {} } = req.body ?? {};

    if (!event) {
      return { ok: false, error: 'Missing "event" field' };
    }

    switch (event) {
      case 'CANDLE_UPDATE':
        publishCandleUpdate(symbol, data.interval || '1m', {
          t: Date.now(),
          o: data.o || 87000,
          h: data.h || 87500,
          l: data.l || 86800,
          c: data.c || 87300,
          v: data.v || 1200,
        });
        break;
      case 'PATTERN_DETECTED':
        publishPatternDetected(symbol, data.timeframe || '1h',
          data.pattern || 'ascending_triangle',
          data.direction || 'BULLISH',
          data.confidence || 0.75,
          data.price || 87000,
          data.description);
        break;
      case 'SIGNAL_CREATED':
        publishSignalCreated(symbol, data.timeframe || '1d',
          data.direction || 'LONG',
          data.entry || 87500,
          data.stop || 84200,
          data.target || 94000,
          data.confidence || 0.72,
          data.strategy,
          data.reason);
        break;
      case 'SCENARIO_UPDATE':
        publishScenarioUpdate(symbol, data.timeframe || '1d',
          data.scenario || 'bullish_breakout',
          data.probability || 0.62,
          data.alternatives || [],
          data.breakRisk || 0.15);
        break;
      case 'REGIME_CHANGE':
        publishRegimeUpdate(symbol, data.timeframe || '1d',
          data.previousRegime || 'COMPRESSION',
          data.newRegime || 'TREND',
          data.confidence || 0.75,
          data.reason || 'Published via API');
        break;
      case 'METABRAIN_UPDATE':
        publishMetaBrainUpdate(symbol, data.timeframe || '1d',
          data.analysisMode || 'DEEP_MARKET',
          data.riskMode || 'NORMAL',
          data.safeMode || false,
          data.riskMultiplier || 1.0,
          data.enabledStrategies || [],
          data.disabledStrategies || [],
          data.reasons || []);
        break;
      default:
        return { ok: false, error: `Unknown event: ${event}` };
    }

    return { ok: true, data: { event, symbol, publishedAt: Date.now() } };
  });

  console.log('[Realtime Routes] Registered:');
  console.log('  - GET  /api/ta/realtime/status');
  console.log('  - GET  /api/ta/realtime/events');
  console.log('  - GET  /api/ta/realtime/connections');
  console.log('  - GET  /api/ta/realtime/stats');
  console.log('  - POST /api/ta/realtime/test');
  console.log('  - GET  /api/realtime/health');
  console.log('  - GET  /api/realtime/status');
  console.log('  - POST /api/realtime/simulate/start');
  console.log('  - POST /api/realtime/simulate/stop');
  console.log('  - GET  /api/realtime/simulate/status');
  console.log('  - POST /api/realtime/publish');
  console.log('  - WebSocket: /ws');
}
