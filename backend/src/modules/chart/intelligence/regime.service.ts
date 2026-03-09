/**
 * Chart Intelligence — Regime Service
 * =====================================
 * Provides current market regime data for chart overlay.
 */

import type { RegimeResponse } from './types.js';
import { getMongoDb } from '../../../db/mongoose.js';

/**
 * Try to fetch regime from DB
 */
async function fetchRegimeFromDB(symbol: string): Promise<RegimeResponse | null> {
  try {
    const db = getMongoDb();

    // Try regime engine results
    const doc = await db.collection('ta_regime_results')
      .findOne(
        { asset: symbol },
        { projection: { _id: 0 }, sort: { createdAt: -1 } }
      );

    if (doc?.regime) {
      return {
        regime: doc.regime,
        bias: doc.bias || doc.direction || 'NEUTRAL',
        volatility: doc.volatility ?? doc.vol ?? 0.5,
      };
    }

    // Try market state
    const stateDoc = await db.collection('ta_market_state_results')
      .findOne(
        { asset: symbol },
        { projection: { _id: 0 }, sort: { createdAt: -1 } }
      );

    if (stateDoc?.state) {
      return {
        regime: stateDoc.state,
        bias: stateDoc.bias || 'NEUTRAL',
        volatility: stateDoc.volatility ?? 0.5,
      };
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Generate mock regime
 */
function generateMockRegime(): RegimeResponse {
  const regimes = ['TREND', 'COMPRESSION', 'RANGE', 'BREAKOUT', 'ACCUMULATION'];
  const biases = ['BULL', 'BEAR', 'NEUTRAL'];

  return {
    regime: regimes[Math.floor(Math.random() * regimes.length)],
    bias: biases[Math.floor(Math.random() * biases.length)],
    volatility: Math.round((0.2 + Math.random() * 0.6) * 100) / 100,
  };
}

/**
 * Main entry point — get regime
 */
export async function getRegime(symbol: string): Promise<RegimeResponse> {
  const dbResult = await fetchRegimeFromDB(symbol);
  if (dbResult) return dbResult;

  return generateMockRegime();
}
