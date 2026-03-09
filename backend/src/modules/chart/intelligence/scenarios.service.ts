/**
 * Chart Intelligence — Scenarios Service
 * ========================================
 * Provides probable market scenarios from the Scenario Engine.
 */

import type { Scenario, ScenariosResponse } from './types.js';
import { getMongoDb } from '../../../db/mongoose.js';

/**
 * Try to fetch scenarios from the scenario engine results
 */
async function fetchScenariosFromDB(symbol: string): Promise<ScenariosResponse | null> {
  try {
    const db = getMongoDb();
    const doc = await db.collection('ta_scenarios')
      .findOne(
        { asset: symbol },
        { projection: { _id: 0 }, sort: { createdAt: -1 } }
      );

    if (!doc?.scenarios?.length) return null;

    const scenarios: Scenario[] = doc.scenarios.map((s: any) => ({
      type: s.type || s.name || 'unknown',
      probability: s.probability ?? s.prob ?? 0.5,
      target: s.target,
      stopLoss: s.stopLoss,
      description: s.description,
    }));

    return { scenarios };
  } catch {
    return null;
  }
}

/**
 * Generate mock scenarios
 */
function generateMockScenarios(symbol: string): ScenariosResponse {
  const basePrices: Record<string, number> = {
    BTCUSDT: 87000,
    ETHUSDT: 3200,
    SOLUSDT: 145,
    BNBUSDT: 620,
  };

  const base = basePrices[symbol] || 100;

  return {
    scenarios: [
      {
        type: 'bullish_breakout',
        probability: 0.42,
        target: Math.round(base * 1.15),
        stopLoss: Math.round(base * 0.95),
        description: 'Breakout above resistance with momentum continuation',
      },
      {
        type: 'range_consolidation',
        probability: 0.33,
        target: Math.round(base * 1.03),
        stopLoss: Math.round(base * 0.97),
        description: 'Sideways movement within current range',
      },
      {
        type: 'bearish_rejection',
        probability: 0.18,
        target: Math.round(base * 0.88),
        stopLoss: Math.round(base * 1.03),
        description: 'Rejection at resistance with pullback to support',
      },
      {
        type: 'liquidity_sweep',
        probability: 0.07,
        target: Math.round(base * 0.82),
        description: 'Deep sweep of stop liquidity below support',
      },
    ],
  };
}

/**
 * Main entry point — get scenarios
 */
export async function getScenarios(symbol: string): Promise<ScenariosResponse> {
  const dbResult = await fetchScenariosFromDB(symbol);
  if (dbResult) return dbResult;

  return generateMockScenarios(symbol);
}
