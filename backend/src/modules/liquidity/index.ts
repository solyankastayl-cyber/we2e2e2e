/**
 * Liquidity Engine Module
 * 
 * Detects and analyzes liquidity zones:
 * - Equal Highs/Lows (stop clusters)
 * - Swing Points
 * - Range boundaries
 * - Liquidity Sweeps (stop hunts)
 * 
 * Provides boost factors for pattern scoring
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';
import { registerLiquidityRoutes } from './liquidity.routes.js';

export * from './liquidity.types.js';
export * from './liquidity.detector.js';
export * from './liquidity.service.js';

export async function registerLiquidityModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Liquidity] Registering Liquidity Engine...');
  
  await app.register(async (instance) => {
    await registerLiquidityRoutes(instance, { db });
  }, { prefix: '/liquidity' });
  
  console.log('[Liquidity] ✅ Liquidity Engine registered at /api/ta/liquidity/*');
}
