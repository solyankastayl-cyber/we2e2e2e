/**
 * Phase 5.4 B7 — Edge Autopilot
 * 
 * Automatically adjusts pattern weights based on edge performance
 * - SOFT_DOWNWEIGHT: reduce weight when PF drops
 * - HARD_DISABLE: freeze pattern when PF < threshold
 */

import { Db, Collection } from 'mongodb';
import { FastifyInstance, FastifyRequest } from 'fastify';
import { v4 as uuidv4 } from 'uuid';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export type PolicyAction = 'SOFT_DOWNWEIGHT' | 'HARD_DISABLE' | 'RESTORE' | 'BOOST';

export interface PolicyConfig {
  // Thresholds
  softDownweightPF: number;   // PF below this → reduce weight (default 1.0)
  hardDisablePF: number;      // PF below this → disable (default 0.8)
  boostPF: number;            // PF above this → increase weight (default 1.3)
  
  // Multipliers
  downweightMultiplier: number;  // default 0.7
  boostMultiplier: number;       // default 1.2
  
  // Minimum samples
  minTrades: number;          // default 50
  
  // Auto-run
  autoEnabled: boolean;
}

export interface PolicyActionDoc {
  actionId: string;
  pattern: string;
  action: PolicyAction;
  
  reason: string;
  previousMultiplier: number;
  newMultiplier: number;
  
  metrics: {
    profitFactor: number;
    winRate: number;
    trades: number;
  };
  
  timestamp: Date;
  automatic: boolean;
}

export interface PatternWeightDoc {
  pattern: string;
  multiplier: number;
  disabled: boolean;
  lastUpdated: Date;
  reason?: string;
}

// ═══════════════════════════════════════════════════════════════
// Constants
// ═══════════════════════════════════════════════════════════════

const POLICY_ACTIONS_COLLECTION = 'ta_policy_actions';
const PATTERN_WEIGHTS_COLLECTION = 'ta_pattern_weights';

const DEFAULT_POLICY_CONFIG: PolicyConfig = {
  softDownweightPF: 1.0,
  hardDisablePF: 0.8,
  boostPF: 1.3,
  downweightMultiplier: 0.7,
  boostMultiplier: 1.2,
  minTrades: 50,
  autoEnabled: false,
};

// ═══════════════════════════════════════════════════════════════
// Edge Autopilot Service
// ═══════════════════════════════════════════════════════════════

export class EdgeAutopilot {
  private db: Db;
  private actions: Collection;
  private weights: Collection;
  private config: PolicyConfig;

  constructor(db: Db, config?: Partial<PolicyConfig>) {
    this.db = db;
    this.actions = db.collection(POLICY_ACTIONS_COLLECTION);
    this.weights = db.collection(PATTERN_WEIGHTS_COLLECTION);
    this.config = { ...DEFAULT_POLICY_CONFIG, ...config };
  }

  async ensureIndexes(): Promise<void> {
    await this.actions.createIndex({ pattern: 1, timestamp: -1 });
    await this.actions.createIndex({ timestamp: -1 });
    await this.weights.createIndex({ pattern: 1 }, { unique: true });
    console.log('[EdgeAutopilot] Indexes ensured');
  }

  // ─────────────────────────────────────────────────────────────
  // Get/Set Weights
  // ─────────────────────────────────────────────────────────────

  async getWeight(pattern: string): Promise<PatternWeightDoc | null> {
    const doc = await this.weights.findOne({ pattern });
    if (!doc) return null;
    const { _id, ...result } = doc as any;
    return result;
  }

  async getAllWeights(): Promise<PatternWeightDoc[]> {
    const docs = await this.weights.find({}).toArray();
    return docs.map(doc => {
      const { _id, ...result } = doc as any;
      return result;
    });
  }

  async setWeight(
    pattern: string,
    multiplier: number,
    reason?: string
  ): Promise<void> {
    await this.weights.updateOne(
      { pattern },
      {
        $set: {
          pattern,
          multiplier,
          disabled: multiplier === 0,
          lastUpdated: new Date(),
          reason,
        },
      },
      { upsert: true }
    );
  }

  async disablePattern(pattern: string, reason: string): Promise<void> {
    await this.setWeight(pattern, 0, reason);
  }

  async enablePattern(pattern: string): Promise<void> {
    await this.setWeight(pattern, 1.0, 'Restored');
  }

  // ─────────────────────────────────────────────────────────────
  // Compute Final Multiplier
  // ─────────────────────────────────────────────────────────────

  async getFinalMultiplier(
    pattern: string,
    edgeMultiplier: number = 1.0,
    qualityMultiplier: number = 1.0
  ): Promise<{
    finalMultiplier: number;
    edgeMultiplier: number;
    qualityMultiplier: number;
    patternMultiplier: number;
    disabled: boolean;
  }> {
    const weight = await this.getWeight(pattern);
    const patternMultiplier = weight?.multiplier ?? 1.0;
    const disabled = weight?.disabled ?? false;

    if (disabled) {
      return {
        finalMultiplier: 0,
        edgeMultiplier,
        qualityMultiplier,
        patternMultiplier: 0,
        disabled: true,
      };
    }

    // Combine multipliers with clamping
    const combined = edgeMultiplier * qualityMultiplier * patternMultiplier;
    const finalMultiplier = Math.max(0.3, Math.min(2.0, combined));

    return {
      finalMultiplier,
      edgeMultiplier,
      qualityMultiplier,
      patternMultiplier,
      disabled: false,
    };
  }

  // ─────────────────────────────────────────────────────────────
  // Evaluate Pattern
  // ─────────────────────────────────────────────────────────────

  async evaluatePattern(pattern: string): Promise<PolicyActionDoc | null> {
    // Get pattern metrics from coverage or backtest
    const metrics = await this.getPatternMetrics(pattern);

    if (!metrics || metrics.trades < this.config.minTrades) {
      return null;  // Not enough data
    }

    const currentWeight = await this.getWeight(pattern);
    const previousMultiplier = currentWeight?.multiplier ?? 1.0;

    let action: PolicyAction | null = null;
    let newMultiplier = previousMultiplier;
    let reason = '';

    const pf = metrics.profitFactor;

    // Check for HARD_DISABLE
    if (pf < this.config.hardDisablePF) {
      action = 'HARD_DISABLE';
      newMultiplier = 0;
      reason = `PF ${pf.toFixed(2)} < ${this.config.hardDisablePF}`;
    }
    // Check for SOFT_DOWNWEIGHT
    else if (pf < this.config.softDownweightPF) {
      action = 'SOFT_DOWNWEIGHT';
      newMultiplier = Math.max(0.3, previousMultiplier * this.config.downweightMultiplier);
      reason = `PF ${pf.toFixed(2)} < ${this.config.softDownweightPF}`;
    }
    // Check for BOOST
    else if (pf > this.config.boostPF && previousMultiplier < 1.5) {
      action = 'BOOST';
      newMultiplier = Math.min(1.5, previousMultiplier * this.config.boostMultiplier);
      reason = `PF ${pf.toFixed(2)} > ${this.config.boostPF}`;
    }

    if (!action) return null;

    // Apply change
    await this.setWeight(pattern, newMultiplier, reason);

    // Log action
    const actionDoc: PolicyActionDoc = {
      actionId: uuidv4(),
      pattern,
      action,
      reason,
      previousMultiplier,
      newMultiplier,
      metrics,
      timestamp: new Date(),
      automatic: true,
    };

    await this.actions.insertOne(actionDoc);

    return actionDoc;
  }

  // ─────────────────────────────────────────────────────────────
  // Run Autopilot
  // ─────────────────────────────────────────────────────────────

  async runAutopilot(): Promise<{
    evaluated: number;
    actions: PolicyActionDoc[];
  }> {
    if (!this.config.autoEnabled) {
      return { evaluated: 0, actions: [] };
    }

    // Get all patterns from coverage
    const patterns = await this.db.collection('ta_pattern_coverage')
      .find({})
      .project({ pattern: 1 })
      .toArray();

    const actions: PolicyActionDoc[] = [];
    let evaluated = 0;

    for (const p of patterns) {
      evaluated++;
      const action = await this.evaluatePattern(p.pattern);
      if (action) {
        actions.push(action);
      }
    }

    return { evaluated, actions };
  }

  // ─────────────────────────────────────────────────────────────
  // Get Action History
  // ─────────────────────────────────────────────────────────────

  async getActionHistory(limit: number = 50): Promise<PolicyActionDoc[]> {
    const docs = await this.actions
      .find({})
      .sort({ timestamp: -1 })
      .limit(limit)
      .toArray();

    return docs.map(doc => {
      const { _id, ...result } = doc as any;
      return result;
    });
  }

  async getPatternActions(pattern: string): Promise<PolicyActionDoc[]> {
    const docs = await this.actions
      .find({ pattern })
      .sort({ timestamp: -1 })
      .limit(20)
      .toArray();

    return docs.map(doc => {
      const { _id, ...result } = doc as any;
      return result;
    });
  }

  // ─────────────────────────────────────────────────────────────
  // Config
  // ─────────────────────────────────────────────────────────────

  getConfig(): PolicyConfig {
    return { ...this.config };
  }

  updateConfig(update: Partial<PolicyConfig>): PolicyConfig {
    this.config = { ...this.config, ...update };
    return this.getConfig();
  }

  // ─────────────────────────────────────────────────────────────
  // Private
  // ─────────────────────────────────────────────────────────────

  private async getPatternMetrics(pattern: string): Promise<{
    profitFactor: number;
    winRate: number;
    trades: number;
  } | null> {
    // Try coverage collection first
    const coverage = await this.db.collection('ta_pattern_coverage')
      .findOne({ pattern });

    if (coverage && coverage.trades >= this.config.minTrades) {
      return {
        profitFactor: coverage.profitFactor,
        winRate: coverage.winRate,
        trades: coverage.trades,
      };
    }

    // Fallback to computing from trades
    const trades = await this.db.collection('ta_backtest_trades')
      .find({ 'decisionSnapshot.patternsUsed': pattern })
      .toArray();

    if (trades.length < this.config.minTrades) return null;

    let wins = 0;
    let losses = 0;
    let positiveR = 0;
    let negativeR = 0;

    for (const trade of trades) {
      if (trade.exitType === 'T1' || trade.exitType === 'T2') wins++;
      else if (trade.exitType === 'STOP') losses++;

      if (trade.rMultiple > 0) positiveR += trade.rMultiple;
      else negativeR += Math.abs(trade.rMultiple);
    }

    const winRate = (wins + losses) > 0 ? wins / (wins + losses) : 0;
    const profitFactor = negativeR > 0 ? positiveR / negativeR : positiveR > 0 ? 10 : 0;

    return { profitFactor, winRate, trades: trades.length };
  }
}

// ═══════════════════════════════════════════════════════════════
// Routes
// ═══════════════════════════════════════════════════════════════

export async function registerAutopilotRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const autopilot = new EdgeAutopilot(db);
  await autopilot.ensureIndexes();

  // GET /config
  app.get('/config', async () => {
    return { ok: true, config: autopilot.getConfig() };
  });

  // PATCH /config
  app.patch('/config', async (request: FastifyRequest<{
    Body: Partial<PolicyConfig>
  }>) => {
    const config = autopilot.updateConfig(request.body || {});
    return { ok: true, config };
  });

  // POST /run
  app.post('/run', async () => {
    const result = await autopilot.runAutopilot();
    return { ok: true, ...result };
  });

  // GET /weights
  app.get('/weights', async () => {
    const weights = await autopilot.getAllWeights();
    return { ok: true, count: weights.length, weights };
  });

  // GET /weights/:pattern
  app.get('/weights/:pattern', async (request: FastifyRequest<{
    Params: { pattern: string }
  }>) => {
    const weight = await autopilot.getWeight(request.params.pattern);
    return { ok: true, weight };
  });

  // POST /weights/:pattern
  app.post('/weights/:pattern', async (request: FastifyRequest<{
    Params: { pattern: string };
    Body: { multiplier: number; reason?: string }
  }>) => {
    const { pattern } = request.params;
    const { multiplier, reason } = request.body || {};

    if (typeof multiplier !== 'number') {
      return { ok: false, error: 'multiplier required' };
    }

    await autopilot.setWeight(pattern, multiplier, reason);
    return { ok: true };
  });

  // POST /evaluate/:pattern
  app.post('/evaluate/:pattern', async (request: FastifyRequest<{
    Params: { pattern: string }
  }>) => {
    const action = await autopilot.evaluatePattern(request.params.pattern);
    return { ok: true, action };
  });

  // GET /multiplier/:pattern
  app.get('/multiplier/:pattern', async (request: FastifyRequest<{
    Params: { pattern: string };
    Querystring: { edge?: string; quality?: string }
  }>) => {
    const { pattern } = request.params;
    const { edge, quality } = request.query;

    const result = await autopilot.getFinalMultiplier(
      pattern,
      edge ? parseFloat(edge) : 1.0,
      quality ? parseFloat(quality) : 1.0
    );

    return { ok: true, pattern, ...result };
  });

  // GET /actions
  app.get('/actions', async (request: FastifyRequest<{
    Querystring: { limit?: string }
  }>) => {
    const limit = request.query.limit ? parseInt(request.query.limit, 10) : 50;
    const actions = await autopilot.getActionHistory(limit);
    return { ok: true, count: actions.length, actions };
  });

  // GET /actions/:pattern
  app.get('/actions/:pattern', async (request: FastifyRequest<{
    Params: { pattern: string }
  }>) => {
    const actions = await autopilot.getPatternActions(request.params.pattern);
    return { ok: true, count: actions.length, actions };
  });

  console.log('[Autopilot] Routes registered: /config, /run, /weights, /multiplier, /actions');
}

// ═══════════════════════════════════════════════════════════════
// Module
// ═══════════════════════════════════════════════════════════════

export async function registerAutopilotModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Autopilot] Registering Edge Autopilot v5.4...');
  
  await app.register(async (instance) => {
    await registerAutopilotRoutes(instance, { db });
  }, { prefix: '/autopilot' });
  
  console.log('[Autopilot] ✅ Edge Autopilot registered at /api/ta/autopilot/*');
}
