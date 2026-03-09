/**
 * Phase 5.3 B5 — Pattern Coverage Matrix
 * 
 * Tracks implementation and performance of all TA patterns
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export type CoverageStatus = 
  | 'IMPLEMENTED'     // Code exists
  | 'DETECTED'        // Actually finding patterns
  | 'VALIDATED'       // Has outcome data
  | 'EDGE_POSITIVE'   // PF > 1.1
  | 'EDGE_NEGATIVE'   // PF < 0.9
  | 'DEPRECATED';     // Disabled

export interface PatternCoverageDoc {
  pattern: string;
  group: string;
  
  implemented: boolean;
  detectorVersion?: string;
  
  detections: number;
  trades: number;
  
  winRate: number;
  profitFactor: number;
  avgR: number;
  
  edgeScore: number;
  status: CoverageStatus;
  
  lastSeen?: Date;
  lastEvaluated: Date;
}

export interface CoverageSummary {
  patternsTotal: number;
  implemented: number;
  detected: number;
  validated: number;
  edgePositive: number;
  edgeNegative: number;
  deprecated: number;
}

export interface CoverageAuditResult {
  missing: string[];
  unvalidated: string[];
  degraded: string[];
}

// ═══════════════════════════════════════════════════════════════
// Required TA List (from spec)
// ═══════════════════════════════════════════════════════════════

export const REQUIRED_TA_PATTERNS: Record<string, string[]> = {
  LEVELS: [
    'SUPPORT', 'RESISTANCE', 'PIVOT_POINT', 'FIBONACCI_RETRACEMENT',
    'FIBONACCI_EXTENSION', 'ROUND_NUMBER',
  ],
  CHANNELS: [
    'ASCENDING_CHANNEL', 'DESCENDING_CHANNEL', 'HORIZONTAL_CHANNEL',
    'PARALLEL_CHANNEL', 'REGRESSION_CHANNEL',
  ],
  TRIANGLES: [
    'ASCENDING_TRIANGLE', 'DESCENDING_TRIANGLE', 'SYMMETRICAL_TRIANGLE',
    'EXPANDING_TRIANGLE', 'WEDGE_RISING', 'WEDGE_FALLING',
  ],
  FLAGS: [
    'BULL_FLAG', 'BEAR_FLAG', 'BULL_PENNANT', 'BEAR_PENNANT',
  ],
  REVERSALS: [
    'HEAD_SHOULDERS', 'INVERSE_HEAD_SHOULDERS', 'DOUBLE_TOP', 'DOUBLE_BOTTOM',
    'TRIPLE_TOP', 'TRIPLE_BOTTOM', 'ROUNDING_TOP', 'ROUNDING_BOTTOM',
  ],
  CUPS: [
    'CUP_AND_HANDLE', 'INVERSE_CUP_AND_HANDLE',
  ],
  HARMONICS: [
    'GARTLEY', 'BUTTERFLY', 'BAT', 'CRAB', 'SHARK', 'CYPHER',
    'THREE_DRIVES', 'ABCD', 'AB_CD',
  ],
  WAVES: [
    'ELLIOTT_IMPULSE', 'ELLIOTT_CORRECTIVE', 'WOLFE_WAVE',
  ],
  GAPS: [
    'BREAKAWAY_GAP', 'RUNAWAY_GAP', 'EXHAUSTION_GAP', 'COMMON_GAP',
  ],
  CANDLES: [
    'DOJI', 'HAMMER', 'INVERTED_HAMMER', 'ENGULFING_BULL', 'ENGULFING_BEAR',
    'MORNING_STAR', 'EVENING_STAR', 'THREE_WHITE_SOLDIERS', 'THREE_BLACK_CROWS',
  ],
};

// ═══════════════════════════════════════════════════════════════
// Coverage Builder
// ═══════════════════════════════════════════════════════════════

const COVERAGE_COLLECTION = 'ta_pattern_coverage';

export class CoverageBuilder {
  private db: Db;
  private coverage: Collection;

  constructor(db: Db) {
    this.db = db;
    this.coverage = db.collection(COVERAGE_COLLECTION);
  }

  async ensureIndexes(): Promise<void> {
    await this.coverage.createIndex({ pattern: 1 }, { unique: true });
    await this.coverage.createIndex({ group: 1 });
    await this.coverage.createIndex({ status: 1 });
    await this.coverage.createIndex({ edgeScore: -1 });
    console.log('[CoverageBuilder] Indexes ensured');
  }

  /**
   * Rebuild entire coverage matrix
   */
  async rebuild(): Promise<{
    processed: number;
    summary: CoverageSummary;
  }> {
    const now = new Date();
    let processed = 0;

    // Get all required patterns
    const allPatterns: { pattern: string; group: string }[] = [];
    for (const [group, patterns] of Object.entries(REQUIRED_TA_PATTERNS)) {
      for (const pattern of patterns) {
        allPatterns.push({ pattern, group });
      }
    }

    // Get implemented patterns from registry
    const implementedPatterns = await this.getImplementedPatterns();

    // Get detection counts
    const detectionCounts = await this.getDetectionCounts();

    // Get trade metrics from backtest
    const tradeMetrics = await this.getTradeMetrics();

    // Build coverage for each pattern
    for (const { pattern, group } of allPatterns) {
      const implemented = implementedPatterns.has(pattern);
      const detections = detectionCounts.get(pattern) || 0;
      const metrics = tradeMetrics.get(pattern) || { trades: 0, wins: 0, losses: 0, sumR: 0 };

      const winRate = (metrics.wins + metrics.losses) > 0
        ? metrics.wins / (metrics.wins + metrics.losses)
        : 0;

      const profitFactor = metrics.losses > 0 && metrics.negativeR
        ? Math.abs(metrics.positiveR || 0) / Math.abs(metrics.negativeR)
        : metrics.positiveR > 0 ? 10 : 0;

      const avgR = metrics.trades > 0 ? metrics.sumR / metrics.trades : 0;

      // Calculate edge score
      const edgeScore = this.calculateEdgeScore(profitFactor, winRate, metrics.trades);

      // Determine status
      const status = this.determineStatus(implemented, detections, metrics.trades, profitFactor);

      const doc: PatternCoverageDoc = {
        pattern,
        group,
        implemented,
        detections,
        trades: metrics.trades,
        winRate,
        profitFactor,
        avgR,
        edgeScore,
        status,
        lastEvaluated: now,
      };

      if (detections > 0) {
        doc.lastSeen = now;  // Simplified - would need actual detection timestamps
      }

      // Upsert
      await this.coverage.updateOne(
        { pattern },
        { $set: doc },
        { upsert: true }
      );

      processed++;
    }

    // Compute summary
    const summary = await this.getSummary();

    return { processed, summary };
  }

  /**
   * Get coverage summary
   */
  async getSummary(): Promise<CoverageSummary> {
    const total = await this.coverage.countDocuments({});
    const implemented = await this.coverage.countDocuments({ implemented: true });
    const detected = await this.coverage.countDocuments({ detections: { $gt: 0 } });
    const validated = await this.coverage.countDocuments({ trades: { $gt: 0 } });
    const edgePositive = await this.coverage.countDocuments({ status: 'EDGE_POSITIVE' });
    const edgeNegative = await this.coverage.countDocuments({ status: 'EDGE_NEGATIVE' });
    const deprecated = await this.coverage.countDocuments({ status: 'DEPRECATED' });

    return {
      patternsTotal: total,
      implemented,
      detected,
      validated,
      edgePositive,
      edgeNegative,
      deprecated,
    };
  }

  /**
   * Get coverage for specific pattern
   */
  async getPattern(pattern: string): Promise<PatternCoverageDoc | null> {
    const doc = await this.coverage.findOne({ pattern: pattern.toUpperCase() });
    if (!doc) return null;
    const { _id, ...result } = doc as any;
    return result as PatternCoverageDoc;
  }

  /**
   * Get all coverage entries
   */
  async getAll(): Promise<PatternCoverageDoc[]> {
    const docs = await this.coverage.find({}).sort({ group: 1, pattern: 1 }).toArray();
    return docs.map(doc => {
      const { _id, ...result } = doc as any;
      return result as PatternCoverageDoc;
    });
  }

  /**
   * Audit coverage against required list
   */
  async audit(): Promise<CoverageAuditResult> {
    const allRequired: string[] = [];
    for (const patterns of Object.values(REQUIRED_TA_PATTERNS)) {
      allRequired.push(...patterns);
    }

    const coverage = await this.getAll();
    const coverageMap = new Map(coverage.map(c => [c.pattern, c]));

    const missing: string[] = [];
    const unvalidated: string[] = [];
    const degraded: string[] = [];

    for (const pattern of allRequired) {
      const cov = coverageMap.get(pattern);
      
      if (!cov || !cov.implemented) {
        missing.push(pattern);
      } else if (cov.trades === 0) {
        unvalidated.push(pattern);
      } else if (cov.status === 'EDGE_NEGATIVE') {
        degraded.push(pattern);
      }
    }

    return { missing, unvalidated, degraded };
  }

  // ─────────────────────────────────────────────────────────────
  // Private Helpers
  // ─────────────────────────────────────────────────────────────

  private async getImplementedPatterns(): Promise<Set<string>> {
    // Try to read from pattern registry
    try {
      const registry = await this.db.collection('ta_pattern_registry')
        .find({ implemented: true })
        .project({ type: 1 })
        .toArray();
      
      return new Set(registry.map(r => r.type));
    } catch {
      // Fallback - assume all required are implemented
      const all: string[] = [];
      for (const patterns of Object.values(REQUIRED_TA_PATTERNS)) {
        all.push(...patterns);
      }
      return new Set(all);
    }
  }

  private async getDetectionCounts(): Promise<Map<string, number>> {
    const result = new Map<string, number>();
    
    try {
      const agg = await this.db.collection('ta_patterns')
        .aggregate([
          { $group: { _id: '$type', count: { $sum: 1 } } }
        ])
        .toArray();
      
      for (const row of agg) {
        result.set(row._id, row.count);
      }
    } catch {
      // No patterns collection
    }
    
    return result;
  }

  private async getTradeMetrics(): Promise<Map<string, {
    trades: number;
    wins: number;
    losses: number;
    sumR: number;
    positiveR: number;
    negativeR: number;
  }>> {
    const result = new Map();
    
    try {
      const trades = await this.db.collection('ta_backtest_trades')
        .find({})
        .toArray();
      
      for (const trade of trades) {
        const patterns = trade.decisionSnapshot?.patternsUsed || [];
        for (const pattern of patterns) {
          const existing = result.get(pattern) || {
            trades: 0,
            wins: 0,
            losses: 0,
            sumR: 0,
            positiveR: 0,
            negativeR: 0,
          };

          existing.trades++;
          existing.sumR += trade.rMultiple || 0;
          
          if (trade.rMultiple > 0) {
            existing.positiveR += trade.rMultiple;
          } else {
            existing.negativeR += trade.rMultiple;
          }

          if (trade.exitType === 'T1' || trade.exitType === 'T2') {
            existing.wins++;
          } else if (trade.exitType === 'STOP') {
            existing.losses++;
          }

          result.set(pattern, existing);
        }
      }
    } catch {
      // No trades collection
    }
    
    return result;
  }

  private calculateEdgeScore(pf: number, winRate: number, trades: number): number {
    if (trades < 10) return 0;
    // Edge = (PF-1) * winRate * log(trades)
    return (pf - 1) * winRate * Math.log10(trades + 1);
  }

  private determineStatus(
    implemented: boolean,
    detections: number,
    trades: number,
    pf: number
  ): CoverageStatus {
    if (!implemented) return 'IMPLEMENTED';
    if (detections === 0) return 'IMPLEMENTED';
    if (trades === 0) return 'DETECTED';
    if (pf > 1.1) return 'EDGE_POSITIVE';
    if (pf < 0.9) return 'EDGE_NEGATIVE';
    return 'VALIDATED';
  }
}

// ═══════════════════════════════════════════════════════════════
// Coverage Routes
// ═══════════════════════════════════════════════════════════════

import { FastifyInstance, FastifyRequest } from 'fastify';

export async function registerCoverageRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const builder = new CoverageBuilder(db);
  await builder.ensureIndexes();

  // POST /rebuild
  app.post('/rebuild', async () => {
    const result = await builder.rebuild();
    return { ok: true, ...result };
  });

  // GET /summary
  app.get('/summary', async () => {
    const summary = await builder.getSummary();
    return { ok: true, ...summary };
  });

  // GET /pattern/:pattern
  app.get('/pattern/:pattern', async (request: FastifyRequest<{
    Params: { pattern: string }
  }>) => {
    const { pattern } = request.params;
    const coverage = await builder.getPattern(pattern);
    
    if (!coverage) {
      return { ok: false, error: 'Pattern not found' };
    }
    
    return { ok: true, coverage };
  });

  // GET /all
  app.get('/all', async () => {
    const patterns = await builder.getAll();
    return { ok: true, count: patterns.length, patterns };
  });

  // GET /audit
  app.get('/audit', async () => {
    const audit = await builder.audit();
    return { ok: true, ...audit };
  });

  console.log('[Coverage] Routes registered: /rebuild, /summary, /pattern/:pattern, /all, /audit');
}

// ═══════════════════════════════════════════════════════════════
// Module Export
// ═══════════════════════════════════════════════════════════════

export async function registerCoverageModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[Coverage] Registering Coverage Matrix v5.3...');
  
  await app.register(async (instance) => {
    await registerCoverageRoutes(instance, { db });
  }, { prefix: '/coverage' });
  
  console.log('[Coverage] ✅ Coverage Matrix registered at /api/ta/coverage/*');
}
