/**
 * Intelligence Engine (P4.1)
 * 
 * Orchestrator that combines all TA Engine components into IntelligencePack
 */

import { Db } from 'mongodb';
import { v4 as uuid } from 'uuid';
import type {
  IntelligencePack,
  IntelligenceRequest,
  TopScenario,
  IntelligenceComponents
} from './intelligence.types.js';
import {
  buildBias,
  buildTopScenario,
  buildProbability,
  buildExpectation,
  buildSignals,
  buildProjection,
  buildConfidence,
  buildMeta
} from './intelligence.mapper.js';
import { getIntelligenceStorage } from './intelligence.storage.js';
import { getMarketDataProvider } from '../../data/market.provider.js';

export class IntelligenceEngine {
  private db: Db;

  constructor(db: Db) {
    this.db = db;
  }

  /**
   * Main computation method - orchestrates all components
   */
  async compute(request: IntelligenceRequest): Promise<IntelligencePack> {
    const runId = uuid();
    const asset = request.asset.toUpperCase();
    const timeframe = request.timeframe.toLowerCase();
    const asOfTs = request.asOfTs || Date.now();
    
    const components: IntelligenceComponents = {};
    
    // 1. Get candles
    const provider = getMarketDataProvider(request.provider as any || 'mongo');
    const candles = await provider.getCandles(asset, timeframe, 200);
    const priceNow = candles.length > 0 ? candles[candles.length - 1].close : undefined;
    
    // 2. Fetch latest decision run (if available)
    const latestRun = await this.db.collection('ta_runs')
      .findOne({ asset, timeframe }, { sort: { timestamp: -1 } });
    
    let patterns: any[] = [];
    let scenarios: any[] = [];
    let mlResult: any = null;
    let stabilityScore = 0.7; // Default
    let conflictCount = 0;
    
    if (latestRun) {
      components.patternsRunId = latestRun.runId;
      
      // Get patterns from this run
      patterns = await this.db.collection('ta_patterns')
        .find({ runId: latestRun.runId })
        .toArray();
      
      // Get decision for scenarios
      const decision = await this.db.collection('ta_decisions')
        .findOne({ runId: latestRun.runId });
      
      if (decision) {
        scenarios = decision.scenarios || [];
        mlResult = decision.ml || null;
        conflictCount = decision.conflicts?.length || 0;
      }
    }
    
    // 3. Get stability from pattern stats
    const patternStats = await this.db.collection('ta_pattern_stats')
      .find({ enabled: true })
      .toArray();
    
    if (patternStats.length > 0) {
      const avgPF = patternStats.reduce((s, p) => s + (p.profitFactor || 1), 0) / patternStats.length;
      stabilityScore = Math.min(1, avgPF / 2); // Normalize PF to [0,1]
    }
    
    // 4. Get scenario cache for projection bands
    let scenarioBands = null;
    if (patterns.length > 0 && patterns[0].type) {
      const cached = await this.db.collection('ta_scenario_cache')
        .findOne({ patternId: patterns[0].type });
      
      if (cached) {
        scenarioBands = { p10: cached.p10, p50: cached.p50, p90: cached.p90 };
        components.scenarioRunId = cached.cacheKey;
      }
    }
    
    // 5. Get active models
    const entryModel = await this.db.collection('ta_model_registry')
      .findOne({ type: 'entry_probability', stage: { $in: ['LIVE_LOW', 'LIVE_MED', 'LIVE_HIGH'] } });
    const rModel = await this.db.collection('ta_model_registry')
      .findOne({ type: 'expected_r', stage: { $in: ['LIVE_LOW', 'LIVE_MED', 'LIVE_HIGH'] } });
    
    // 6. Get feature schema
    const featureSchema = await this.db.collection('ta_feature_schema')
      .findOne({ isActive: true });
    
    // === BUILD INTELLIGENCE PACK ===
    
    // Build top scenario
    const topScenario = buildTopScenario(
      scenarios.map(s => ({
        patternId: s.patternId || s.id,
        type: s.type || s.pattern,
        score: s.score || 0,
        probability: s.probability || 0.5,
        ev: s.ev || 0,
        riskReward: s.riskReward || 1.5
      }))
    );
    
    // Build probability
    const mlProb = mlResult?.p_entry || null;
    const scenarioProb = scenarios.length > 0 ? {
      pTarget: scenarios[0].p_target || 0.5,
      pStop: scenarios[0].p_stop || 0.3,
      pTimeout: scenarios[0].p_timeout || 0.2
    } : null;
    
    const { probabilities, source: probabilitySource } = buildProbability(
      mlProb,
      scenarioProb,
      null // No calibration yet
    );
    
    // Build signals
    const signals = buildSignals(
      patterns.map(p => ({
        direction: p.direction || (p.type?.includes('BULL') ? 'BULLISH' : p.type?.includes('BEAR') ? 'BEARISH' : 'NEUTRAL'),
        score: p.score || 0.5
      })),
      conflictCount
    );
    
    // Build expectation
    const expectedR = mlResult?.expected_r || (topScenario?.riskReward || 1.5);
    const expectation = buildExpectation(probabilities.pWin, expectedR);
    
    // Build projection
    const projection = buildProjection(scenarioBands, priceNow);
    
    // Build confidence
    const scenarioConsistency = scenarioBands ? 0.8 : 0.5;
    const conflictPenalty = Math.min(1, conflictCount * 0.2);
    const confidence = buildConfidence(
      probabilities.pEntry,
      stabilityScore,
      scenarioConsistency,
      conflictPenalty
    );
    
    // Build bias
    const topBias = buildBias(signals.netBias, topScenario);
    
    // Build meta
    const meta = buildMeta(
      entryModel?.modelId || null,
      rModel?.modelId || null,
      featureSchema?.version || null,
      probabilitySource
    );
    
    // === ASSEMBLE PACK ===
    const pack: IntelligencePack = {
      runId,
      asset,
      timeframe,
      asOfTs,
      topBias,
      topScenario,
      probability: probabilities,
      expectation,
      signals,
      projection,
      confidence,
      components,
      meta,
      createdAt: new Date()
    };
    
    // 7. Save to storage (immutable)
    const storage = getIntelligenceStorage(this.db);
    await storage.save(pack);
    
    return pack;
  }
}

// Singleton
let engineInstance: IntelligenceEngine | null = null;

export function getIntelligenceEngine(db: Db): IntelligenceEngine {
  if (!engineInstance) {
    engineInstance = new IntelligenceEngine(db);
  }
  return engineInstance;
}
