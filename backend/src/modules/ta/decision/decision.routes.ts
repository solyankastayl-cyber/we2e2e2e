/**
 * P1.6 + P0.1 — Decision API Routes
 * 
 * Endpoints for unified decision pipeline:
 * - POST /decision/compute - Get decision from unified pipeline
 * - GET /decision/explain - P0.1: Explainability Layer
 * - GET /decision/test - Run outcome evaluator tests
 * - GET /dataset_v4/stats - V4 dataset statistics
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import { createDecisionEngine, DecisionContext, CandleData, ScenarioInput } from '../decision/decision.engine.js';
import { runOutcomeTests } from '../decision/outcome_evaluator.js';
import { getDatasetV4Stats, initDatasetWriterV4, createDatasetV4Indexes } from '../decision/dataset_writer_v4.js';
import { getDecisionAuditService } from '../core/audit.service.js';
import { getModelRegistry } from '../core/model.registry.js';
import { explainDecision, initExplainStorage, saveDecisionSnapshot, DecisionSnapshot } from './decision.explain.js';

interface RouteContext {
  db: Db;
}

export async function registerDecisionRoutes(app: FastifyInstance, ctx: RouteContext): Promise<void> {
  const { db } = ctx;
  const engine = createDecisionEngine(db);
  const auditService = getDecisionAuditService(db);
  const modelRegistry = getModelRegistry(db);
  
  // Initialize dataset writer and explain storage
  initDatasetWriterV4(db);
  initExplainStorage(db);
  await createDatasetV4Indexes(db);

  /**
   * POST /decision/compute
   * Compute decision through unified pipeline (with audit trail)
   */
  app.post('/decision/compute', async (req: FastifyRequest, reply: FastifyReply) => {
    const t0 = Date.now();
    let runId: string | null = null;

    try {
      const body = req.body as {
        asset: string;
        timeframe: string;
        candles: CandleData[];
        scenarios: ScenarioInput[];
        currentPrice?: number;
        atr?: number;
      };

      if (!body.asset || !body.timeframe || !body.candles || !body.scenarios) {
        return reply.code(400).send({ error: 'Missing required fields: asset, timeframe, candles, scenarios' });
      }

      // Resolve active model and schema
      const activeEntry = await modelRegistry.getActiveModel('entry');
      const activeSchema = await modelRegistry.getActiveSchema();

      // Start audited run
      runId = await auditService.startRun({
        asset: body.asset,
        timeframe: body.timeframe,
        window: body.candles.length,
        modelId: activeEntry?.modelId || 'mock_v1',
        featureSchemaVersion: activeSchema?.version || 'unregistered',
      });

      const lastCandle = body.candles[body.candles.length - 1];
      const currentPrice = body.currentPrice || lastCandle?.close || 0;
      const atr = body.atr || calculateATR(body.candles);

      const decisionCtx: DecisionContext = {
        asset: body.asset,
        timeframe: body.timeframe,
        timestamp: new Date(),
        candles: body.candles,
        currentPrice,
        atr,
        scenarios: body.scenarios,
      };

      const decision = await engine.computeDecision(decisionCtx);

      // Audit: pipeline layers
      await auditService.writeAudit(runId, 'patterns', {
        totalScenarios: decision.totalScenarios,
        passedGate: decision.passedGate,
        rejected: decision.rejected,
      });

      await auditService.writeAudit(runId, 'regime', {
        regime: decision.regime,
        confidence: decision.regimeConfidence,
      });

      if (decision.topScenario) {
        await auditService.writeAudit(runId, 'geometry', {
          geometryBoost: decision.topScenario.geometryBoost,
        });
        await auditService.writeAudit(runId, 'gates', {
          gateScore: decision.topScenario.gateScore,
        });
        await auditService.writeAudit(runId, 'ml', {
          pEntry: decision.topScenario.pEntry,
          rExpected: decision.topScenario.rExpected,
          evBeforeML: decision.topScenario.evBeforeML,
          evAfterML: decision.topScenario.evAfterML,
        });
        await auditService.writeAudit(runId, 'ranking', {
          topPattern: decision.topScenario.patternType,
          finalScore: decision.topScenario.finalScore,
          scenariosRanked: decision.scenarios.length,
        });

        // Save decision record
        await auditService.saveDecision({
          runId,
          asset: decision.asset,
          timeframe: decision.timeframe,
          timestamp: decision.timestamp,
          topScenario: {
            scenarioId: decision.topScenario.scenarioId,
            patternType: decision.topScenario.patternType,
            direction: decision.topScenario.direction,
            entry: decision.topScenario.entry,
            stop: decision.topScenario.stop,
            target1: decision.topScenario.target1,
            target2: decision.topScenario.target2,
          },
          probability: decision.topScenario.pEntry,
          ev: decision.topScenario.evAfterML,
          evBeforeML: decision.topScenario.evBeforeML,
          evAfterML: decision.topScenario.evAfterML,
          qualityMultiplier: 1.0,
          stabilityMultiplier: 1.0,
          scenarioMultiplier: 1.0,
          ranking: decision.scenarios.map(s => ({
            scenarioId: s.scenarioId,
            patternType: s.patternType,
            finalScore: s.finalScore,
          })),
          modelId: activeEntry?.modelId || 'mock_v1',
          featureSchemaVersion: activeSchema?.version || 'unregistered',
        });
        
        // P0.1: Save snapshot for explain API
        const snapshot: DecisionSnapshot = {
          asset: decision.asset,
          timeframe: decision.timeframe,
          ts: Date.now(),
          scenarioId: decision.topScenario.scenarioId,
          patternType: decision.topScenario.patternType,
          direction: decision.topScenario.direction === 'LONG' ? 'BULL' : 'BEAR',
          baseEV: decision.topScenario.evBeforeML,
          boosts: {
            pattern: 1.0, // From scenario score
            liquidity: 1.0,
            physics: decision.topScenario.physicsBoost,
            state: decision.topScenario.stateBoost,
            regime: 1.0,
            graph: decision.topScenario.graphBoostFactor,
            geometry: decision.topScenario.geometryBoost
          },
          edgeMultiplier: decision.topScenario.edge?.multiplier || 1.0,
          learningWeight: 1.0, // Average of applied weights
          memory: {
            directionBoost: decision.topScenario.memory?.directionBoost || 1.0,
            scenarioBoost: decision.topScenario.memory?.scenarioBoost || 1.0,
            riskAdjustment: decision.topScenario.memory?.riskAdjustment || 1.0,
            confidence: decision.topScenario.memory?.confidence || 0,
            matches: decision.topScenario.memory?.matchCount || 0
          },
          finalScore: decision.topScenario.finalScore,
          createdAt: new Date()
        };
        await saveDecisionSnapshot(snapshot);
      }

      // Complete the run
      await auditService.completeRun(runId, Date.now() - t0);

      return {
        ok: true,
        runId,
        decision: {
          asset: decision.asset,
          timeframe: decision.timeframe,
          timestamp: decision.timestamp,
          regime: decision.regime,
          regimeConfidence: decision.regimeConfidence,
          overlayStage: decision.overlayStage,
          modelId: decision.modelId,
          totalScenarios: decision.totalScenarios,
          passedGate: decision.passedGate,
          rejected: decision.rejected,
          topScenario: decision.topScenario ? {
            scenarioId: decision.topScenario.scenarioId,
            patternType: decision.topScenario.patternType,
            direction: decision.topScenario.direction,
            entry: decision.topScenario.entry,
            stop: decision.topScenario.stop,
            target1: decision.topScenario.target1,
            target2: decision.topScenario.target2,
            riskReward: decision.topScenario.riskReward,
            gateScore: decision.topScenario.gateScore,
            geometryBoost: decision.topScenario.geometryBoost,
            graphBoostFactor: decision.topScenario.graphBoostFactor,
            physicsBoost: decision.topScenario.physicsBoost,
            physicsState: decision.topScenario.physicsState,
            stateBoost: decision.topScenario.stateBoost,
            marketState: decision.topScenario.marketState,
            pEntry: decision.topScenario.pEntry,
            rExpected: decision.topScenario.rExpected,
            evBeforeML: decision.topScenario.evBeforeML,
            evAfterML: decision.topScenario.evAfterML,
            finalScore: decision.topScenario.finalScore,
            // P0: Memory Boost fields
            memory: decision.topScenario.memory ? {
              confidence: decision.topScenario.memory.confidence,
              matches: decision.topScenario.memory.matchCount,
              directionBoost: decision.topScenario.memory.directionBoost,
              scenarioBoost: decision.topScenario.memory.scenarioBoost,
              riskAdjustment: decision.topScenario.memory.riskAdjustment,
            } : undefined,
          } : null,
          // P0: Memory context for Digital Twin
          memoryContext: decision.memoryContext,
          scenariosCount: decision.scenarios.length,
        },
      };
    } catch (err: any) {
      if (runId) {
        await auditService.failRun(runId, err.message).catch(() => {});
      }
      console.error('[Decision Route] Error:', err.message);
      return reply.code(500).send({ error: err.message });
    }
  });

  /**
   * GET /decision/test/outcomes
   * Run outcome evaluator tests
   */
  app.get('/decision/test/outcomes', async (req: FastifyRequest, reply: FastifyReply) => {
    const results = runOutcomeTests();
    
    return {
      ok: true,
      passed: results.passed,
      failed: results.failed,
      total: results.passed + results.failed,
      results: results.results,
    };
  });

  /**
   * GET /decision/explain
   * P0.1: Explainability Layer - shows breakdown of all boost factors
   */
  app.get('/decision/explain', async (req: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = req.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.code(400).send({ 
        error: 'Missing required parameters: asset, tf' 
      });
    }
    
    try {
      const explain = await explainDecision(asset, tf);
      
      if (!explain) {
        return reply.code(404).send({ 
          error: 'No decision data available for this asset/timeframe',
          suggestion: 'Run POST /decision/compute first to generate decision data'
        });
      }
      
      return {
        ok: true,
        explain
      };
    } catch (err: any) {
      console.error('[Decision Explain] Error:', err.message);
      return reply.code(500).send({ error: err.message });
    }
  });

  /**
   * GET /decision/status
   * Decision engine status
   */
  app.get('/decision/status', async () => {
    return {
      ok: true,
      version: '1.8',
      phase: 'P0.1 Explainability Layer',
      components: {
        decisionEngine: 'active',
        geometryEngine: 'active',
        tradeabilityGate: 'active',
        graphBoost: 'active',
        physicsEngine: 'active (D3)',
        stateEngine: 'active (D4)',
        regimeMixture: 'active',
        evPredictor: 'active (mock)',
        datasetWriterV4: 'active',
        memoryBoost: 'active (P0)',
        explainAPI: 'active (P0.1)',  // New
      },
      pipeline: 'patterns → geometry → gates → graph → physics → state → regime → ML → EDGE → MEMORY → ranking',
      overlayStage: 'LIVE_LITE',
    };
  });

  /**
   * GET /dataset_v4/stats
   * V4 dataset statistics
   */
  app.get('/dataset_v4/stats', async (req: FastifyRequest, reply: FastifyReply) => {
    try {
      const stats = await getDatasetV4Stats(db);
      
      return {
        ok: true,
        stats,
      };
    } catch (err: any) {
      return reply.code(500).send({ error: err.message });
    }
  });

  console.log('[Decision Routes] Registered:');
  console.log('  - POST /decision/compute');
  console.log('  - GET  /decision/test/outcomes');
  console.log('  - GET  /decision/status');
  console.log('  - GET  /dataset_v4/stats');
}

/**
 * Calculate ATR
 */
function calculateATR(candles: CandleData[], period: number = 14): number {
  if (candles.length < period + 1) {
    const ranges = candles.slice(-period).map(c => c.high - c.low);
    return ranges.reduce((a, b) => a + b, 0) / ranges.length || 1;
  }
  
  let atr = 0;
  for (let i = candles.length - period; i < candles.length; i++) {
    const curr = candles[i];
    const prev = candles[i - 1];
    if (!prev) continue;
    
    const tr = Math.max(
      curr.high - curr.low,
      Math.abs(curr.high - prev.close),
      Math.abs(curr.low - prev.close)
    );
    atr += tr;
  }
  
  return atr / period;
}
