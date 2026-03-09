/**
 * Phase 5.5 B8 — Replay & Audit Reconstructor
 * 
 * Enables deterministic replay and comparison of runs
 * - Reconstruct all intermediate layers
 * - Compare versions
 * - Debug decision paths
 */

import { Db, Collection } from 'mongodb';
import { FastifyInstance, FastifyRequest } from 'fastify';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export interface ReplayResult {
  runId: string;
  reconstructed: boolean;
  
  config: {
    labelVersion: string;
    featureSchemaVersion: string;
    entryModelVersion: string;
    rModelVersion: string;
    edgeRunId: string;
    seed: number;
  };
  
  layers: {
    patterns: number;
    geometry: number;
    gates: number;
    ml: number;
    ranking: number;
    trades: number;
  };
  
  timeline: Array<{
    barIndex: number;
    timestamp: number;
    event: string;
    data?: any;
  }>;
}

export interface DiffResult {
  runIdA: string;
  runIdB: string;
  
  configDiff: {
    field: string;
    valueA: any;
    valueB: any;
  }[];
  
  metricsDiff: {
    metric: string;
    valueA: number;
    valueB: number;
    delta: number;
    deltaPct: number;
  }[];
  
  tradeDiff: {
    matches: number;
    onlyInA: number;
    onlyInB: number;
    different: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// Audit Reconstructor
// ═══════════════════════════════════════════════════════════════

export class AuditReconstructor {
  private db: Db;

  constructor(db: Db) {
    this.db = db;
  }

  /**
   * Replay a run and reconstruct all layers
   */
  async replay(runId: string): Promise<ReplayResult | null> {
    // Get run
    const run = await this.db.collection('ta_backtest_runs').findOne({ runId });
    if (!run) return null;

    // Get trades
    const trades = await this.db.collection('ta_backtest_trades')
      .find({ runId })
      .sort({ signalIndex: 1 })
      .toArray();

    // Build timeline
    const timeline: ReplayResult['timeline'] = [];

    for (const trade of trades) {
      timeline.push({
        barIndex: trade.signalIndex,
        timestamp: trade.signalIndex,  // Would need actual timestamp
        event: 'DECISION',
        data: {
          scenarioId: trade.decisionSnapshot?.scenarioId,
          bias: trade.decisionSnapshot?.bias,
          patterns: trade.decisionSnapshot?.patternsUsed,
        },
      });

      if (trade.openedAtIndex >= 0) {
        timeline.push({
          barIndex: trade.openedAtIndex,
          timestamp: trade.openedAtIndex,
          event: 'ENTRY',
          data: {
            price: trade.entryPrice,
          },
        });
      }

      timeline.push({
        barIndex: trade.closedAtIndex,
        timestamp: trade.closedAtIndex,
        event: 'EXIT',
        data: {
          type: trade.exitType,
          price: trade.exitPrice,
          rMultiple: trade.rMultiple,
        },
      });
    }

    // Count layers (simplified - would need actual layer data)
    const layers = {
      patterns: trades.reduce((sum, t) => sum + (t.decisionSnapshot?.patternsUsed?.length || 0), 0),
      geometry: trades.length,
      gates: trades.length,
      ml: trades.length,
      ranking: trades.length,
      trades: trades.length,
    };

    return {
      runId,
      reconstructed: true,
      config: {
        labelVersion: run.config?.labelVersion || 'v3',
        featureSchemaVersion: run.config?.featureSchemaVersion || 'v1.0',
        entryModelVersion: run.config?.entryModelVersion || 'mock_v1',
        rModelVersion: run.config?.rModelVersion || 'mock_v1',
        edgeRunId: run.config?.edgeRunId || 'NONE',
        seed: run.config?.seed || 1337,
      },
      layers,
      timeline: timeline.slice(0, 100),  // Limit for response size
    };
  }

  /**
   * Compare two runs
   */
  async diff(runIdA: string, runIdB: string): Promise<DiffResult | null> {
    // Get runs
    const runA = await this.db.collection('ta_backtest_runs').findOne({ runId: runIdA });
    const runB = await this.db.collection('ta_backtest_runs').findOne({ runId: runIdB });

    if (!runA || !runB) return null;

    // Config diff
    const configDiff: DiffResult['configDiff'] = [];
    const configFields = ['labelVersion', 'featureSchemaVersion', 'entryModelVersion', 'rModelVersion', 'seed'];

    for (const field of configFields) {
      const valueA = runA.config?.[field];
      const valueB = runB.config?.[field];
      if (valueA !== valueB) {
        configDiff.push({ field, valueA, valueB });
      }
    }

    // Metrics diff
    const metricsDiff: DiffResult['metricsDiff'] = [];
    const metricFields = ['trades', 'winRate', 'avgR', 'profitFactor', 'maxDrawdownR'];

    for (const metric of metricFields) {
      const valueA = runA.summary?.[metric] || 0;
      const valueB = runB.summary?.[metric] || 0;
      const delta = valueB - valueA;
      const deltaPct = valueA !== 0 ? (delta / Math.abs(valueA)) * 100 : 0;

      metricsDiff.push({ metric, valueA, valueB, delta, deltaPct });
    }

    // Trade diff
    const tradesA = await this.db.collection('ta_backtest_trades')
      .find({ runId: runIdA })
      .project({ signalIndex: 1, exitType: 1, rMultiple: 1 })
      .toArray();

    const tradesB = await this.db.collection('ta_backtest_trades')
      .find({ runId: runIdB })
      .project({ signalIndex: 1, exitType: 1, rMultiple: 1 })
      .toArray();

    const signalsA = new Set(tradesA.map(t => t.signalIndex));
    const signalsB = new Set(tradesB.map(t => t.signalIndex));

    let matches = 0;
    let different = 0;

    for (const tradeA of tradesA) {
      const tradeB = tradesB.find(t => t.signalIndex === tradeA.signalIndex);
      if (tradeB) {
        if (tradeA.exitType === tradeB.exitType) {
          matches++;
        } else {
          different++;
        }
      }
    }

    const onlyInA = tradesA.filter(t => !signalsB.has(t.signalIndex)).length;
    const onlyInB = tradesB.filter(t => !signalsA.has(t.signalIndex)).length;

    return {
      runIdA,
      runIdB,
      configDiff,
      metricsDiff,
      tradeDiff: { matches, onlyInA, onlyInB, different },
    };
  }

  /**
   * Get trade details for a specific bar
   */
  async getTradeAtBar(runId: string, barIndex: number): Promise<any | null> {
    const trade = await this.db.collection('ta_backtest_trades')
      .findOne({ runId, signalIndex: barIndex });

    if (!trade) return null;

    const { _id, ...result } = trade as any;
    return result;
  }

  /**
   * Get decision path for debugging
   */
  async getDecisionPath(runId: string, signalIndex: number): Promise<{
    found: boolean;
    path?: any;
  }> {
    const trade = await this.getTradeAtBar(runId, signalIndex);

    if (!trade) {
      return { found: false };
    }

    return {
      found: true,
      path: {
        signalIndex,
        decision: trade.decisionSnapshot,
        entry: {
          planned: trade.entryPrice,
          actual: trade.entryPrice,
          barIndex: trade.openedAtIndex,
        },
        exit: {
          type: trade.exitType,
          price: trade.exitPrice,
          barIndex: trade.closedAtIndex,
        },
        metrics: {
          rMultiple: trade.rMultiple,
          mfeR: trade.mfeR,
          maeR: trade.maeR,
          barsToEntry: trade.barsToEntry,
          barsToExit: trade.barsToExit,
        },
      },
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// Routes
// ═══════════════════════════════════════════════════════════════

export async function registerAuditRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const audit = new AuditReconstructor(db);

  // GET /replay/:runId
  app.get('/replay/:runId', async (request: FastifyRequest<{
    Params: { runId: string }
  }>) => {
    const result = await audit.replay(request.params.runId);
    if (!result) {
      return { ok: false, error: 'Run not found' };
    }
    return { ok: true, ...result };
  });

  // GET /diff/:runIdA/:runIdB
  app.get('/diff/:runIdA/:runIdB', async (request: FastifyRequest<{
    Params: { runIdA: string; runIdB: string }
  }>) => {
    const { runIdA, runIdB } = request.params;
    const result = await audit.diff(runIdA, runIdB);
    if (!result) {
      return { ok: false, error: 'One or both runs not found' };
    }
    return { ok: true, ...result };
  });

  // GET /trade/:runId/:barIndex
  app.get('/trade/:runId/:barIndex', async (request: FastifyRequest<{
    Params: { runId: string; barIndex: string }
  }>) => {
    const { runId, barIndex } = request.params;
    const trade = await audit.getTradeAtBar(runId, parseInt(barIndex, 10));
    if (!trade) {
      return { ok: false, error: 'Trade not found' };
    }
    return { ok: true, trade };
  });

  // GET /path/:runId/:signalIndex
  app.get('/path/:runId/:signalIndex', async (request: FastifyRequest<{
    Params: { runId: string; signalIndex: string }
  }>) => {
    const { runId, signalIndex } = request.params;
    const result = await audit.getDecisionPath(runId, parseInt(signalIndex, 10));
    return { ok: result.found, ...result };
  });

  console.log('[Audit] Routes registered: /replay, /diff, /trade, /path');
}

// ═══════════════════════════════════════════════════════════════
// Module
// ═══════════════════════════════════════════════════════════════

export async function registerAuditModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Audit] Registering Replay & Audit v5.5...');
  
  await app.register(async (instance) => {
    await registerAuditRoutes(instance, { db });
  }, { prefix: '/audit' });
  
  console.log('[Audit] ✅ Replay & Audit registered at /api/ta/audit/*');
}
