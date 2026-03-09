/**
 * Phase 5.2 B4 — Calibration Module
 */

import { FastifyInstance } from 'fastify';
import { Db } from 'mongodb';

export * from './calibration.types.js';
export * from './calibration.train.js';
export * from './calibration.service.js';
export { registerCalibrationRoutes } from './calibration.routes.js';

export async function registerCalibrationModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Calibration] Registering Calibration Engine v5.2...');
  
  const { registerCalibrationRoutes } = await import('./calibration.routes.js');
  
  await app.register(async (instance) => {
    await registerCalibrationRoutes(instance, { db });
  }, { prefix: '/calibration' });
  
  console.log('[Calibration] ✅ Calibration Engine registered at /api/ta/calibration/*');
}
