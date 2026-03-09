/**
 * D2 — Fractal Engine Module
 * 
 * Analyzes market SHAPE, not just patterns
 * - Extracts fractal signatures from price movement
 * - Clusters similar shapes
 * - Discovers patterns with statistical edge
 * - Matches current market to discovered fractals
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';
import { registerFractalRoutes } from './fractal.routes.js';

export * from './fractal.types.js';
export * from './fractal.signature.js';
export * from './fractal.storage.js';
export * from './fractal.discovery.js';
export * from './fractal.service.js';

export async function registerFractalModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[FractalEngine] Registering Fractal Engine (D2)...');
  
  await app.register(async (instance) => {
    await registerFractalRoutes(instance, { db });
  }, { prefix: '/fractal' });
  
  console.log('[FractalEngine] ✅ Fractal Engine registered at /api/ta/fractal/*');
}
