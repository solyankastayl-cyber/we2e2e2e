/**
 * Phase 5.1 — Backtest Harness Module
 * 
 * Research engine for validating trading strategies.
 * - Deterministic backtesting (B1)
 * - Async job system (B2)
 * - NO lookahead bias
 * - Full trade simulation
 * - Comprehensive metrics
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';

// Export types
export * from './domain/types.js';

// Export core modules
export * from './trade.simulator.js';
export * from './decision.adapter.js';
export * from './backtest.metrics.js';
export * from './backtest.storage.js';
export * from './backtest.runner.js';

// B2: Export job system
export * from './jobs/backtest.job.schema.js';
export * from './jobs/backtest.queue.js';
export * from './jobs/backtest.worker.js';

// Export routes
export { registerBacktestRoutes } from './backtest.routes.js';
export { registerBacktestJobRoutes } from './jobs/backtest.controller.js';

/**
 * Register Backtest Module with Fastify
 */
export async function registerBacktestModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Backtest] Registering Backtest Harness Module v5.1 (B1+B2)...');
  
  const { registerBacktestRoutes } = await import('./backtest.routes.js');
  const { registerBacktestJobRoutes } = await import('./jobs/backtest.controller.js');
  const { startBacktestWorker } = await import('./jobs/backtest.worker.js');
  
  // Register routes at /api/ta/backtest/*
  await app.register(async (instance) => {
    await registerBacktestRoutes(instance, { db });
    // B2: Job routes
    await registerBacktestJobRoutes(instance, { db });
  }, { prefix: '/backtest' });
  
  // B2: Start worker
  await startBacktestWorker(db);
  
  console.log('[Backtest] ✅ Backtest Harness Module registered at /api/ta/backtest/*');
  console.log('[Backtest] ✅ Job worker started');
}
