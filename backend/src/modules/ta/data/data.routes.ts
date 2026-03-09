/**
 * Data routes for market data backfill
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';
import { createMarketDataBackfillService } from './backfill.service.js';
import { createSyntheticDataGenerator } from './synthetic.generator.js';

interface RouteOptions {
  db: Db;
}

export async function registerDataRoutes(
  app: FastifyInstance,
  options: RouteOptions
): Promise<void> {
  const { db } = options;
  const backfillService = createMarketDataBackfillService(db);
  const syntheticGen = createSyntheticDataGenerator(db);
  
  /**
   * POST /api/ta/data/backfill
   * 
   * Start market data backfill from Binance
   */
  app.post('/data/backfill', async (
    request: FastifyRequest<{
      Body: {
        assets?: string[];
        timeframes?: string[];
        startDate?: string;
        endDate?: string;
      }
    }>
  ) => {
    const config = {
      assets: request.body?.assets || ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT'],
      timeframes: request.body?.timeframes || ['1d', '4h', '1h'],
      startDate: request.body?.startDate || '2017-01-01',
      endDate: request.body?.endDate || '2024-12-31',
    };
    
    console.log('[Data] Starting backfill with config:', config);
    
    const result = await backfillService.backfill(config);
    
    return {
      ok: true,
      ...result,
    };
  });
  
  /**
   * POST /api/ta/data/generate
   * 
   * Generate synthetic market data (fallback when API unavailable)
   */
  app.post('/data/generate', async (
    request: FastifyRequest<{
      Body: {
        assets?: string[];
        timeframes?: string[];
        startDate?: string;
        endDate?: string;
      }
    }>
  ) => {
    const config = {
      assets: request.body?.assets || ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT', 'DOGEUSDT'],
      timeframes: request.body?.timeframes || ['1d', '4h', '1h'],
      startDate: request.body?.startDate || '2017-01-01',
      endDate: request.body?.endDate || '2024-12-31',
    };
    
    console.log('[Data] Starting synthetic generation with config:', config);
    
    const result = await syntheticGen.generate(config);
    
    return {
      ok: true,
      source: 'synthetic',
      ...result,
    };
  });
  
  /**
   * GET /api/ta/data/stats
   * 
   * Get candle statistics
   */
  app.get('/data/stats', async () => {
    const stats = await syntheticGen.getCandleCount();
    
    return {
      ok: true,
      ...stats,
    };
  });
}
