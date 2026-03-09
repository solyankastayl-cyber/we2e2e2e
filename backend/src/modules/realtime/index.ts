/**
 * Real-time WebSocket Layer — Module Index
 */

// Types
export * from './realtime.types.js';

// Hub
export { realtimeHub, createBaseEvent, publishEvent } from './realtime.hub.js';

// Server
export { setupWebSocketServer, broadcastToAll, getWebSocketStats, closeWebSocketServer } from './realtime.server.js';

// Channels
export { resolveChannelFilter, ALL_CHANNELS, CHANNEL_EVENT_MAP } from './realtime.channels.js';
export type { ChannelName } from './realtime.channels.js';

// Broadcast
export { broadcast, getChannelForEvent, getChannelStats } from './realtime.broadcast.js';

// Simulator
export { startSimulator, stopSimulator, getSimulatorStatus } from './realtime.simulator.js';

// Publishers
export {
  publishRegimeUpdate,
  publishStateUpdate,
  publishScenarioUpdate,
  publishTreeUpdate,
  publishMemoryMatch,
  publishMetaBrainUpdate,
  publishSignalUpdate,
  publishSafeModeTrigger,
  publishModuleGateChange,
  publishEdgeAlert,
  publishTwinUpdate,
  publishSystemHealth,
  publishCandleUpdate,
  publishPatternDetected,
  publishSignalCreated
} from './realtime.publishers.js';

// Routes
export { registerRealtimeRoutes } from './realtime.routes.js';
