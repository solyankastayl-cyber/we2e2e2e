/**
 * Forecast Engine (P4.4)
 * 
 * Main orchestrator that builds ForecastPack
 */

import { Db } from 'mongodb';
import { v4 as uuid } from 'uuid';
import type { 
  ForecastPack, 
  ForecastComputeInput, 
  ForecastStats,
  ProjectionMeta 
} from './forecast.types.js';
import { getHorizonBars } from './forecast.types.js';
import { buildPath } from './forecast.path_builder.js';
import { buildProjectionPath } from './forecast.projector.js';
import { buildBands, applyStabilityDamping } from './forecast.bands.js';
import { extractEvents } from './forecast.events.js';
import { calculateSourceWeights, blendPaths, applyStabilityToPath } from './forecast.blend.js';
import { getForecastStorage } from './forecast.storage.js';
import { getMarketDataProvider } from '../../data/market.provider.js';

export class ForecastEngine {
  private db: Db;

  constructor(db: Db) {
    this.db = db;
  }

  /**
   * Compute forecast from decision/intelligence data
   */
  async compute(
    asset: string,
    timeframe: string,
    options?: Partial<ForecastComputeInput>
  ): Promise<ForecastPack> {
    const runId = uuid();
    const tf = timeframe.toLowerCase();
    const assetUpper = asset.toUpperCase();
    
    // Get current price
    const provider = getMarketDataProvider('mongo');
    const candles = await provider.getCandles(assetUpper, tf, 100);
    const priceNow = candles.length > 0 ? candles[candles.length - 1].close : 50000;
    
    // Get latest decision
    const latestDecision = await this.db.collection('ta_decisions')
      .findOne({ asset: assetUpper, timeframe: tf }, { sort: { timestamp: -1 } });
    
    // Get latest intelligence
    const latestIntelligence = await this.db.collection('ta_intelligence_runs')
      .findOne({ asset: assetUpper, timeframe: tf }, { sort: { createdAt: -1 } });
    
    // Build input
    const input: ForecastComputeInput = {
      asset: assetUpper,
      timeframe: tf,
      priceNow,
      bias: latestIntelligence?.topBias || options?.bias || 'WAIT',
      target: latestDecision?.topScenario?.targets?.[0] || options?.target,
      stop: latestDecision?.topScenario?.stop || options?.stop,
      patternType: latestDecision?.topScenario?.type || options?.patternType,
      breakoutLevel: options?.breakoutLevel,
      measuredMove: options?.measuredMove,
      scenarioBands: latestIntelligence?.projection ? {
        p10: latestIntelligence.projection.r_p10,
        p50: latestIntelligence.projection.r_p50,
        p90: latestIntelligence.projection.r_p90
      } : options?.scenarioBands,
      atrPct: options?.atrPct || 0.02,
      stabilityMultiplier: options?.stabilityMultiplier || 1.0,
      ...options
    };
    
    // Calculate source weights
    const sources = calculateSourceWeights(input);
    
    // Build projection-aware path
    const { path: projectorPath, method, patternType } = buildProjectionPath(input);
    
    // Build simple path for blending
    const simplePath = buildPath(input);
    
    // Blend paths
    let finalPath = blendPaths(projectorPath, simplePath, sources);
    
    // Apply stability damping
    if (input.stabilityMultiplier && input.stabilityMultiplier < 1.0) {
      finalPath = applyStabilityToPath(finalPath, input.stabilityMultiplier, priceNow);
    }
    
    // Build bands
    let bands = buildBands(finalPath, input);
    
    // Apply stability damping to bands
    if (input.stabilityMultiplier && input.stabilityMultiplier < 1.0) {
      bands = applyStabilityDamping(bands, input.stabilityMultiplier);
    }
    
    // Extract events
    const levels = []; // Could add SR levels here
    const events = extractEvents(finalPath, bands, input, levels);
    
    // Calculate stats
    const stats = this.calculateStats(finalPath, bands, input);
    
    // Build projection meta
    const projection: ProjectionMeta = {
      patternType: patternType,
      breakoutLevel: input.breakoutLevel,
      measuredMove: input.measuredMove,
      projectionConfidence: method === 'PATTERN_PROJECTOR' ? 0.7 : 0.5,
      method: method === 'PATTERN_PROJECTOR' ? 'PATTERN_PROJECTOR' : 
              input.scenarioBands ? 'SCENARIO_MC' : 'FALLBACK'
    };
    
    // Build pack
    const pack: ForecastPack = {
      runId,
      decisionRunId: latestDecision?.runId,
      intelligenceRunId: latestIntelligence?.runId,
      asset: assetUpper,
      tf,
      nowTs: Date.now(),
      priceNow,
      horizonBars: getHorizonBars(tf),
      path: finalPath,
      bands,
      events,
      sources,
      stats,
      projection,
      createdAt: new Date()
    };
    
    // Save to storage
    const storage = getForecastStorage(this.db);
    await storage.save(pack);
    
    return pack;
  }

  /**
   * Calculate forecast statistics
   */
  private calculateStats(
    path: import('./forecast.types.js').ForecastPoint[],
    bands: import('./forecast.types.js').ForecastBandsPoint[],
    input: ForecastComputeInput
  ): ForecastStats {
    const priceStart = path[0].price;
    const priceEnd = path[path.length - 1].price;
    const expectedReturnPct = (priceEnd - priceStart) / priceStart * 100;
    
    // Calculate expected volatility from bands
    const bandWidths = bands.map(b => (b.p90 - b.p10) / b.p50);
    const avgBandWidth = bandWidths.reduce((a, b) => a + b, 0) / bandWidths.length;
    const expectedVolPct = avgBandWidth * 100;
    
    // Calculate max drawdown from path
    let maxDrawdown = 0;
    let peak = path[0].price;
    for (const p of path) {
      if (p.price > peak) peak = p.price;
      const drawdown = (peak - p.price) / peak;
      if (drawdown > maxDrawdown) maxDrawdown = drawdown;
    }
    
    // Probability up/down based on scenario bands
    let probUp = 0.5;
    let probDown = 0.5;
    if (input.scenarioBands) {
      const p50 = input.scenarioBands.p50;
      probUp = p50 > 0 ? Math.min(0.9, 0.5 + p50 * 0.1) : Math.max(0.1, 0.5 + p50 * 0.1);
      probDown = 1 - probUp;
    }
    
    return {
      expectedReturnPct: Math.round(expectedReturnPct * 100) / 100,
      expectedVolPct: Math.round(expectedVolPct * 100) / 100,
      maxDrawdownPct: Math.round(maxDrawdown * 10000) / 100,
      probUp,
      probDown,
      horizonBars: path.length - 1
    };
  }
}

// Singleton
let engineInstance: ForecastEngine | null = null;

export function getForecastEngine(db: Db): ForecastEngine {
  if (!engineInstance) {
    engineInstance = new ForecastEngine(db);
  }
  return engineInstance;
}
