/**
 * Outcomes Coverage Checker (P5.0.9 - O1)
 * 
 * Проверяет покрытие свечами для оценки outcomes
 */

import { Db } from 'mongodb';

const CANDLES_COLLECTION = 'candles_binance';

export interface CoveragePeriod {
  asset: string;
  timeframe: string;
  from: number;
  to: number;
}

export interface CoverageResult {
  asset: string;
  timeframe: string;
  from: Date;
  to: Date;
  totalBars: number;
  existingBars: number;
  coverage: number;
  gaps: Array<{ from: Date; to: Date; barsGap: number }>;
  ok: boolean;
}

/**
 * Check candle coverage for a period
 */
export async function checkCandleCoverage(
  db: Db,
  params: CoveragePeriod
): Promise<CoverageResult> {
  const { asset, timeframe, from, to } = params;
  
  // Get candles in range
  const candles = await db.collection(CANDLES_COLLECTION)
    .find({
      symbol: asset.toUpperCase(),
      interval: timeframe.toLowerCase(),
      openTime: { $gte: from, $lte: to }
    })
    .sort({ openTime: 1 })
    .project({ openTime: 1 })
    .toArray();

  // Calculate expected bars
  const tfMultiplier = getTimeframeMs(timeframe);
  const expectedBars = Math.floor((to - from) / tfMultiplier) + 1;
  const existingBars = candles.length;
  const coverage = expectedBars > 0 ? existingBars / expectedBars : 0;

  // Find gaps
  const gaps: Array<{ from: Date; to: Date; barsGap: number }> = [];
  
  for (let i = 1; i < candles.length; i++) {
    const prev = candles[i - 1].openTime;
    const curr = candles[i].openTime;
    const expectedNext = prev + tfMultiplier;
    
    if (curr > expectedNext + tfMultiplier * 0.5) {
      const barsGap = Math.floor((curr - prev) / tfMultiplier) - 1;
      if (barsGap > 0) {
        gaps.push({
          from: new Date(prev),
          to: new Date(curr),
          barsGap
        });
      }
    }
  }

  return {
    asset,
    timeframe,
    from: new Date(from),
    to: new Date(to),
    totalBars: expectedBars,
    existingBars,
    coverage,
    gaps,
    ok: coverage >= 0.95 && gaps.length === 0
  };
}

/**
 * Get timeframe in milliseconds
 */
function getTimeframeMs(tf: string): number {
  const map: Record<string, number> = {
    '1m': 60 * 1000,
    '3m': 3 * 60 * 1000,
    '5m': 5 * 60 * 1000,
    '15m': 15 * 60 * 1000,
    '30m': 30 * 60 * 1000,
    '1h': 60 * 60 * 1000,
    '2h': 2 * 60 * 60 * 1000,
    '4h': 4 * 60 * 60 * 1000,
    '6h': 6 * 60 * 60 * 1000,
    '8h': 8 * 60 * 60 * 1000,
    '12h': 12 * 60 * 60 * 1000,
    '1d': 24 * 60 * 60 * 1000,
    '3d': 3 * 24 * 60 * 60 * 1000,
    '1w': 7 * 24 * 60 * 60 * 1000,
    '1M': 30 * 24 * 60 * 60 * 1000,
  };
  
  return map[tf.toLowerCase()] || 24 * 60 * 60 * 1000;  // default 1d
}

/**
 * Check coverage for all assets/timeframes in outcomes
 */
export async function checkAllCoverage(
  db: Db
): Promise<{
  summary: {
    total: number;
    ok: number;
    needsFill: number;
  };
  details: CoverageResult[];
}> {
  // Get distinct asset/timeframe combinations from scenarios
  const scenarios = db.collection('ta_scenarios');
  
  const combinations = await scenarios.aggregate([
    {
      $group: {
        _id: { asset: '$asset', timeframe: '$timeframe' },
        minTs: { $min: '$anchorTs' },
        maxTs: { $max: '$anchorTs' }
      }
    }
  ]).toArray();

  const details: CoverageResult[] = [];
  
  for (const combo of combinations) {
    if (!combo._id.asset || !combo._id.timeframe) continue;
    
    // Add timeout period (40 bars) to maxTs
    const tfMs = getTimeframeMs(combo._id.timeframe);
    const from = combo.minTs || Date.now() - 90 * 24 * 60 * 60 * 1000;
    const to = (combo.maxTs || Date.now()) + 40 * tfMs;
    
    const coverage = await checkCandleCoverage(db, {
      asset: combo._id.asset,
      timeframe: combo._id.timeframe,
      from,
      to
    });
    
    details.push(coverage);
  }

  const ok = details.filter(d => d.ok).length;
  
  return {
    summary: {
      total: details.length,
      ok,
      needsFill: details.length - ok
    },
    details
  };
}
