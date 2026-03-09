/**
 * Central Route Registry
 * ======================
 * 
 * Single source of truth for all API route prefixes.
 * Prevents duplicate route conflicts across modules.
 */

export const ROUTE_PREFIX = {
  // Core TA Engine
  TA: '/api/ta',
  
  // Phase 2.5: Market Map
  CHART: '/api/chart',
  
  // Phase 3: Admin Control
  ADMIN: '/api/admin',
  
  // Phase 4: Observability
  LOGS: '/api/logs',
  REPLAY: '/api/replay',
  DECISION: '/api/decision',
  
  // Phase 5: Strategy Platform
  STRATEGY: '/api/strategy',
  
  // Phase 5.5: Portfolio Intelligence
  PORTFOLIO: '/api/portfolio',
  
  // Phase 8: Strategy Builder (legacy module)
  STRATEGY_BUILDER: '/api/ta/strategies',
  
  // Real-time
  REALTIME: '/api/realtime',
  WS: '/ws',
  
  // System
  HEALTH: '/api/health',
  SYSTEM: '/api/system',
} as const;

export type RoutePrefix = typeof ROUTE_PREFIX[keyof typeof ROUTE_PREFIX];
