/**
 * Chart Intelligence — State Service
 * ====================================
 * Aggregates ALL chart intelligence data into a single response.
 * Frontend makes 1 request → draws entire screen.
 */

import type { ChartStateResponse, MarketMapSummary } from './types.js';
import { getCandles } from './candles.service.js';
import { getPrediction } from './prediction.service.js';
import { getLevels } from './levels.service.js';
import { getScenarios } from './scenarios.service.js';
import { buildChartObjects } from './objects.builder.js';
import { getRegime } from './regime.service.js';
import { getSystemState } from './system.service.js';
import { getMarketMap } from '../../market_map/market_map.service.js';

/**
 * Get full chart state — all data in one call
 */
export async function getChartState(
  symbol: string,
  interval: string = '1d',
  limit: number = 500,
  horizon: string = '90d'
): Promise<ChartStateResponse> {
  // Fetch all data in parallel (including market map)
  const [candlesRes, prediction, levels, scenariosRes, regime, system, marketMapData] = await Promise.all([
    getCandles(symbol, interval, limit),
    getPrediction(symbol, horizon),
    getLevels(symbol),
    getScenarios(symbol),
    getRegime(symbol),
    getSystemState(),
    getMarketMap(symbol, interval),
  ]);

  // Build objects using other data
  const objectsRes = await buildChartObjects(
    symbol,
    candlesRes.candles,
    levels,
    scenariosRes.scenarios
  );

  // Extract market map summary
  const marketMap: MarketMapSummary = {
    currentState: marketMapData.currentState,
    dominantScenario: marketMapData.stats.dominantScenario,
    dominantProbability: marketMapData.stats.dominantProbability,
    bullishBias: marketMapData.stats.bullishBias,
    branchCount: marketMapData.stats.totalBranches,
  };

  return {
    symbol,
    interval,
    ts: Date.now(),
    candles: candlesRes.candles,
    prediction,
    levels,
    scenarios: scenariosRes.scenarios,
    objects: objectsRes.objects,
    regime,
    system,
    marketMap,
  };
}
