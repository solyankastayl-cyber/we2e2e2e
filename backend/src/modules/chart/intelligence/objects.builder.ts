/**
 * Chart Intelligence — Objects Builder
 * ======================================
 * Builds graphical objects for the frontend chart to draw.
 *
 * Pipeline:
 *   TA patterns → Liquidity zones → Memory markers → Scenario paths → Objects
 *
 * Object types:
 *   trendline, channel, triangle, liquidity_zone, support, resistance,
 *   scenario, memory
 */

import type {
  ChartObject,
  ObjectsResponse,
  TrendLine,
  LiquidityZone,
  SupportLevel,
  ResistanceLevel,
  ScenarioPath,
  MemoryMarker,
  Candle,
  Scenario,
  LevelsResponse,
} from './types.js';
import { getMongoDb } from '../../../db/mongoose.js';

/**
 * Try to fetch detected patterns from TA engine
 */
async function fetchPatternsFromDB(symbol: string): Promise<ChartObject[]> {
  try {
    const db = getMongoDb();
    const doc = await db.collection('ta_analysis_results')
      .findOne(
        { asset: symbol },
        { projection: { _id: 0 }, sort: { createdAt: -1 } }
      );

    if (!doc?.patterns?.length) return [];

    const objects: ChartObject[] = [];
    for (const p of doc.patterns) {
      if (p.type === 'triangle' && p.points?.length) {
        objects.push({ type: 'triangle', points: p.points });
      }
      if ((p.type === 'trendline' || p.type === 'trend') && p.points?.length >= 2) {
        objects.push({
          type: 'trendline',
          direction: p.direction || 'up',
          points: p.points,
        });
      }
    }
    return objects;
  } catch {
    return [];
  }
}

/**
 * Build objects from levels data
 */
function buildLevelObjects(levels: LevelsResponse): ChartObject[] {
  const objects: ChartObject[] = [];

  for (const price of levels.support) {
    objects.push({ type: 'support', price });
  }
  for (const price of levels.resistance) {
    objects.push({ type: 'resistance', price });
  }

  // Group adjacent liquidity levels into zones
  const sorted = [...levels.liquidity].sort((a, b) => a - b);
  for (let i = 0; i < sorted.length; i += 2) {
    if (i + 1 < sorted.length) {
      objects.push({
        type: 'liquidity_zone',
        bottom: sorted[i],
        top: sorted[i + 1],
      });
    }
  }

  return objects;
}

/**
 * Build trendline objects from candle data
 */
function buildTrendlinesFromCandles(candles: Candle[]): ChartObject[] {
  if (candles.length < 20) return [];

  const objects: ChartObject[] = [];
  const recent = candles.slice(-60);

  // Find swing lows for uptrend line
  const lows: { t: number; p: number }[] = [];
  for (let i = 2; i < recent.length - 2; i++) {
    if (
      recent[i].l < recent[i - 1].l &&
      recent[i].l < recent[i - 2].l &&
      recent[i].l < recent[i + 1].l &&
      recent[i].l < recent[i + 2].l
    ) {
      lows.push({ t: recent[i].t, p: recent[i].l });
    }
  }

  if (lows.length >= 2) {
    // Take two most significant swing lows
    const sorted = lows.sort((a, b) => a.p - b.p);
    const picked = sorted.slice(0, 2).sort((a, b) => a.t - b.t);
    if (picked[1].p >= picked[0].p) {
      objects.push({
        type: 'trendline',
        direction: 'up',
        points: picked,
      });
    }
  }

  // Find swing highs for downtrend line
  const highs: { t: number; p: number }[] = [];
  for (let i = 2; i < recent.length - 2; i++) {
    if (
      recent[i].h > recent[i - 1].h &&
      recent[i].h > recent[i - 2].h &&
      recent[i].h > recent[i + 1].h &&
      recent[i].h > recent[i + 2].h
    ) {
      highs.push({ t: recent[i].t, p: recent[i].h });
    }
  }

  if (highs.length >= 2) {
    const sorted = highs.sort((a, b) => b.p - a.p);
    const picked = sorted.slice(0, 2).sort((a, b) => a.t - b.t);
    if (picked[1].p <= picked[0].p) {
      objects.push({
        type: 'trendline',
        direction: 'down',
        points: picked,
      });
    }
  }

  return objects;
}

/**
 * Build scenario path objects
 */
function buildScenarioPaths(scenarios: Scenario[], basePrice: number, baseTime: number): ChartObject[] {
  const dayMs = 86_400_000;
  const objects: ChartObject[] = [];

  for (const s of scenarios) {
    if (!s.target) continue;

    const steps = 10;
    const path: { t: number; p: number }[] = [];
    const priceStep = (s.target - basePrice) / steps;

    for (let i = 0; i <= steps; i++) {
      const t = baseTime + i * 9 * dayMs; // ~90 days spread
      const noise = (Math.random() - 0.5) * Math.abs(priceStep) * 0.3;
      const p = Math.round((basePrice + priceStep * i + noise) * 100) / 100;
      path.push({ t, p });
    }

    objects.push({
      type: 'scenario',
      probability: s.probability,
      path,
    });
  }

  return objects;
}

/**
 * Build memory marker objects
 */
async function buildMemoryMarkers(symbol: string): Promise<ChartObject[]> {
  try {
    const db = getMongoDb();
    const docs = await db.collection('ta_memory_snapshots')
      .find(
        { asset: symbol },
        { projection: { _id: 0, similarity: 1, price: 1, ts: 1 } }
      )
      .sort({ similarity: -1 })
      .limit(5)
      .toArray();

    return docs
      .filter((d: any) => d.price && d.similarity)
      .map((d: any) => ({
        type: 'memory' as const,
        similarity: d.similarity,
        price: d.price,
        t: d.ts || Date.now(),
      }));
  } catch {
    return [];
  }
}

/**
 * Generate mock objects for fallback
 */
function generateMockObjects(symbol: string): ChartObject[] {
  const basePrices: Record<string, number> = {
    BTCUSDT: 87000,
    ETHUSDT: 3200,
    SOLUSDT: 145,
    BNBUSDT: 620,
  };

  const base = basePrices[symbol] || 100;
  const now = Date.now();
  const dayMs = 86_400_000;

  return [
    {
      type: 'trendline',
      direction: 'up',
      points: [
        { t: now - 30 * dayMs, p: Math.round(base * 0.88) },
        { t: now - 5 * dayMs, p: Math.round(base * 0.97) },
      ],
    },
    {
      type: 'trendline',
      direction: 'down',
      points: [
        { t: now - 25 * dayMs, p: Math.round(base * 1.06) },
        { t: now - 3 * dayMs, p: Math.round(base * 1.01) },
      ],
    },
    {
      type: 'liquidity_zone',
      top: Math.round(base * 1.04),
      bottom: Math.round(base * 1.02),
    },
    {
      type: 'liquidity_zone',
      top: Math.round(base * 0.96),
      bottom: Math.round(base * 0.94),
    },
    {
      type: 'support',
      price: Math.round(base * 0.92),
    },
    {
      type: 'resistance',
      price: Math.round(base * 1.05),
    },
    {
      type: 'scenario',
      probability: 0.42,
      path: [
        { t: now, p: base },
        { t: now + 15 * dayMs, p: Math.round(base * 1.03) },
        { t: now + 30 * dayMs, p: Math.round(base * 1.06) },
        { t: now + 60 * dayMs, p: Math.round(base * 1.1) },
        { t: now + 90 * dayMs, p: Math.round(base * 1.15) },
      ],
    },
    {
      type: 'scenario',
      probability: 0.33,
      path: [
        { t: now, p: base },
        { t: now + 15 * dayMs, p: Math.round(base * 1.01) },
        { t: now + 30 * dayMs, p: Math.round(base * 0.99) },
        { t: now + 60 * dayMs, p: Math.round(base * 1.02) },
        { t: now + 90 * dayMs, p: Math.round(base * 1.03) },
      ],
    },
    {
      type: 'memory',
      similarity: 0.87,
      price: Math.round(base * 0.78),
      t: now - 180 * dayMs,
    },
  ];
}

/**
 * Main entry point — build all chart objects
 */
export async function buildChartObjects(
  symbol: string,
  candles?: Candle[],
  levels?: LevelsResponse,
  scenarios?: Scenario[]
): Promise<ObjectsResponse> {
  const objects: ChartObject[] = [];

  // 1. Fetch pattern objects from DB
  const patternObjects = await fetchPatternsFromDB(symbol);
  objects.push(...patternObjects);

  // 2. Build level objects
  if (levels) {
    objects.push(...buildLevelObjects(levels));
  }

  // 3. Build trendlines from candles
  if (candles && candles.length >= 20) {
    objects.push(...buildTrendlinesFromCandles(candles));
  }

  // 4. Build scenario paths
  if (scenarios && scenarios.length > 0 && candles && candles.length > 0) {
    const lastCandle = candles[candles.length - 1];
    objects.push(...buildScenarioPaths(scenarios, lastCandle.c, lastCandle.t));
  }

  // 5. Memory markers
  const memoryMarkers = await buildMemoryMarkers(symbol);
  objects.push(...memoryMarkers);

  // If no objects were built, use mock
  if (objects.length === 0) {
    return { objects: generateMockObjects(symbol) };
  }

  return { objects };
}
