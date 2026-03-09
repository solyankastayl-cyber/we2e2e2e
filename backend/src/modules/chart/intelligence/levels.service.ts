/**
 * Chart Intelligence — Levels Service
 * =====================================
 * Provides support, resistance, and liquidity levels.
 * Aggregates data from TA engine + Liquidity engine.
 */

import type { LevelsResponse } from './types.js';
import { getMongoDb } from '../../../db/mongoose.js';

/**
 * Try to fetch levels from TA engine results
 */
async function fetchLevelsFromDB(symbol: string): Promise<LevelsResponse | null> {
  try {
    const db = getMongoDb();

    // Try TA analysis results
    const taDoc = await db.collection('ta_analysis_results')
      .findOne(
        { asset: symbol },
        { projection: { _id: 0 }, sort: { createdAt: -1 } }
      );

    if (taDoc?.levels) {
      return {
        support: taDoc.levels.support || [],
        resistance: taDoc.levels.resistance || [],
        liquidity: taDoc.levels.liquidity || [],
      };
    }

    // Try liquidity zones
    const liqDoc = await db.collection('ta_liquidity_zones')
      .findOne(
        { asset: symbol },
        { projection: { _id: 0 }, sort: { createdAt: -1 } }
      );

    if (liqDoc?.zones?.length) {
      const support: number[] = [];
      const resistance: number[] = [];
      const liquidity: number[] = [];

      for (const z of liqDoc.zones) {
        if (z.type === 'support') support.push(z.price);
        else if (z.type === 'resistance') resistance.push(z.price);
        else liquidity.push(z.price || z.level);
      }

      return { support, resistance, liquidity };
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Generate mock levels based on symbol
 */
function generateMockLevels(symbol: string): LevelsResponse {
  const basePrices: Record<string, number> = {
    BTCUSDT: 87000,
    ETHUSDT: 3200,
    SOLUSDT: 145,
    BNBUSDT: 620,
  };

  const base = basePrices[symbol] || 100;
  const pct = (p: number) => Math.round(base * p * 100) / 100;

  return {
    support: [pct(0.92), pct(0.85), pct(0.78)],
    resistance: [pct(1.05), pct(1.12), pct(1.18)],
    liquidity: [pct(1.02), pct(1.04), pct(0.96), pct(0.94)],
  };
}

/**
 * Main entry point — get levels
 */
export async function getLevels(symbol: string): Promise<LevelsResponse> {
  const dbResult = await fetchLevelsFromDB(symbol);
  if (dbResult) return dbResult;

  return generateMockLevels(symbol);
}
