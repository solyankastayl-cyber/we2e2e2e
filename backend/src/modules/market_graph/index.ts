/**
 * G1 + G2 + G3 — Market Structure Graph Module
 * 
 * Represents market as a sequence of events and transitions:
 * - Pattern detected
 * - Liquidity sweep
 * - Breakout/breakdown
 * - Retest
 * - Expansion/compression
 * - Target hit/failure
 * 
 * Provides:
 * - Event extraction from existing TA data
 * - Transition probability computation
 * - Graph-based scoring boost
 * - Path forecasting
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';
import { registerMarketGraphRoutes } from './market_graph.routes.js';

export * from './market_graph.types.js';
export * from './market_graph.extractor.js';
export * from './market_graph.storage.js';
export * from './market_graph.transitions.js';
export * from './market_graph.service.js';

export async function registerMarketGraphModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[MarketGraph] Registering Market Structure Graph (G1-G3)...');
  
  await app.register(async (instance) => {
    await registerMarketGraphRoutes(instance, { db });
  }, { prefix: '/market_graph' });
  
  console.log('[MarketGraph] ✅ Market Structure Graph registered at /api/ta/market_graph/*');
}
