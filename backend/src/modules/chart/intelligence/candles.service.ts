/**
 * Chart Intelligence — Candles Service
 * =====================================
 * Provides OHLCV candle data for the chart.
 * Uses real data from MongoDB when available, falls back to mock.
 */

import type { Candle, CandlesResponse } from './types.js';
import { getMongoDb } from '../../../db/mongoose.js';

/**
 * Generate realistic OHLCV mock candles for a given symbol
 */
function generateMockCandles(symbol: string, interval: string, limit: number): Candle[] {
  const basePrices: Record<string, number> = {
    BTCUSDT: 87000,
    ETHUSDT: 3200,
    SOLUSDT: 145,
    BNBUSDT: 620,
  };

  const intervalMs: Record<string, number> = {
    '5m': 5 * 60_000,
    '15m': 15 * 60_000,
    '1h': 3_600_000,
    '4h': 4 * 3_600_000,
    '1d': 86_400_000,
  };

  const step = intervalMs[interval] || 3_600_000;
  const basePrice = basePrices[symbol] || 100;
  const now = Date.now();
  const candles: Candle[] = [];

  let price = basePrice * (1 - 0.08); // start 8% lower for uptrend feel

  for (let i = 0; i < limit; i++) {
    const t = now - (limit - i) * step;
    const volatility = basePrice * 0.012; // 1.2% per candle
    const drift = (basePrice - price) * 0.003; // mean-revert slowly

    const change = drift + (Math.random() - 0.48) * volatility;
    const o = price;
    const c = o + change;
    const h = Math.max(o, c) + Math.random() * volatility * 0.5;
    const l = Math.min(o, c) - Math.random() * volatility * 0.5;
    const v = Math.round(800 + Math.random() * 2400);

    candles.push({
      t,
      o: Math.round(o * 100) / 100,
      h: Math.round(h * 100) / 100,
      l: Math.round(l * 100) / 100,
      c: Math.round(c * 100) / 100,
      v,
    });

    price = c;
  }

  return candles;
}

/**
 * Try to fetch real candles from MongoDB
 */
async function fetchRealCandles(symbol: string, interval: string, limit: number): Promise<Candle[]> {
  try {
    const db = getMongoDb();
    const collName = `candles_${symbol.toLowerCase()}_${interval}`;
    const docs = await db.collection(collName)
      .find({}, { projection: { _id: 0 } })
      .sort({ t: -1 })
      .limit(limit)
      .toArray();

    if (docs.length === 0) return [];

    return docs.reverse().map((d: any) => ({
      t: d.t || d.openTime || d.timestamp,
      o: d.o || d.open,
      h: d.h || d.high,
      l: d.l || d.low,
      c: d.c || d.close,
      v: d.v || d.volume || 0,
    }));
  } catch {
    return [];
  }
}

/**
 * Main entry point — get candles
 */
export async function getCandles(
  symbol: string,
  interval: string = '1d',
  limit: number = 500
): Promise<CandlesResponse> {
  // Try real data first
  let candles = await fetchRealCandles(symbol, interval, limit);

  if (candles.length === 0) {
    candles = generateMockCandles(symbol, interval, limit);
  }

  return { symbol, interval, candles };
}
