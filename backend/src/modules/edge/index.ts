/**
 * Edge Attribution Module (Phase 5.0 + P5.0.9)
 * 
 * Analyzes historical trades and attributes profit (edge) to various factors:
 * - Pattern types and families
 * - Market regimes
 * - Geometry quality
 * - ML confidence buckets
 * 
 * P5.0.9: Edge Multiplier Integration
 * - EdgeMultiplierService for decision ranking adjustment
 * - Admin routes for flag control
 * 
 * @version 5.0.9
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';

// Export domain types
export * from './domain/types.js';

// Export core modules
export * from './edge.datasource.js';
export * from './edge.metrics.js';
export * from './edge.buckets.js';
export * from './edge.aggregator.js';
export * from './edge.storage.js';
export * from './edge.rebuild.job.js';

// P5.0.9: Export multiplier service
export * from './edge.multiplier.service.js';

// Export routes
export { registerEdgeRoutes } from './edge.routes.js';
export { registerEdgeAdminRoutes } from './edge.admin.routes.js';

/**
 * Register Edge Attribution Module with Fastify
 */
export async function registerEdgeModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Edge] Registering Edge Attribution Module v5.0.9...');
  
  const { registerEdgeRoutes } = await import('./edge.routes.js');
  const { registerEdgeAdminRoutes } = await import('./edge.admin.routes.js');
  
  // Register routes at /api/ta/edge/*
  await app.register(async (instance) => {
    await registerEdgeRoutes(instance, { db });
    // P5.0.9: Admin routes for flag control
    await registerEdgeAdminRoutes(instance, { db });
  }, { prefix: '/edge' });
  
  console.log('[Edge] ✅ Edge Attribution Module v5.0.9 registered at /api/ta/edge/*');
}
