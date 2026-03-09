/**
 * Edge Datasource (P5.0.2)
 * 
 * Loads and joins data from outcomes/decisions/runs
 */

import { Db } from 'mongodb';
import type { EdgeRow, OutcomeClass, EdgeHealth } from './domain/types.js';
import { getPatternFamily } from './domain/types.js';
import { applyBuckets, normalizeRegime, normalizeVolRegime } from './edge.buckets.js';

export interface LoadEdgeRowsParams {
  from?: Date;
  to?: Date;
  assets?: string[];
  timeframes?: string[];
  limit?: number;
  skip?: number;
}

export class EdgeDatasource {
  private db: Db;

  constructor(db: Db) {
    this.db = db;
  }

  /**
   * Check health of data sources
   */
  async checkHealth(): Promise<EdgeHealth> {
    const outcomesCount = await this.db.collection('ta_outcomes').countDocuments();
    const decisionsCount = await this.db.collection('ta_decisions').countDocuments();
    
    // Check for required fields in a sample
    const sampleOutcome = await this.db.collection('ta_outcomes').findOne({});
    const sampleDecision = await this.db.collection('ta_decisions').findOne({});
    
    const missingFields: string[] = [];
    
    if (sampleOutcome) {
      if (!('rMultiple' in sampleOutcome)) missingFields.push('outcomes.rMultiple');
      if (!('outcomeClass' in sampleOutcome) && !('result' in sampleOutcome)) {
        missingFields.push('outcomes.outcomeClass');
      }
    }
    
    if (sampleDecision) {
      if (!('pEntry' in sampleDecision) && !('probability' in sampleDecision)) {
        missingFields.push('decisions.pEntry');
      }
    }
    
    // Get last outcome timestamp
    const lastOutcome = await this.db.collection('ta_outcomes')
      .findOne({}, { sort: { closedAt: -1 } });
    
    return {
      ok: outcomesCount > 0 && decisionsCount > 0 && missingFields.length === 0,
      outcomesCount,
      decisionsCount,
      hasRequiredFields: missingFields.length === 0,
      missingFields,
      lastOutcomeTs: lastOutcome?.closedAt || lastOutcome?.timestamp
    };
  }

  /**
   * Load edge rows with join
   */
  async loadEdgeRows(params: LoadEdgeRowsParams = {}): Promise<EdgeRow[]> {
    const { from, to, assets, timeframes, limit = 10000, skip = 0 } = params;
    
    // Build match stage
    const matchStage: any = {};
    
    if (from || to) {
      matchStage.closedAt = {};
      if (from) matchStage.closedAt.$gte = from.getTime();
      if (to) matchStage.closedAt.$lte = to.getTime();
    }
    
    if (assets && assets.length > 0) {
      matchStage.asset = { $in: assets.map(a => a.toUpperCase()) };
    }
    
    if (timeframes && timeframes.length > 0) {
      matchStage.timeframe = { $in: timeframes.map(t => t.toLowerCase()) };
    }
    
    // Only completed outcomes
    matchStage.$or = [
      { outcomeClass: { $in: ['WIN', 'LOSS', 'PARTIAL', 'TIMEOUT'] } },
      { result: { $in: ['WIN', 'LOSS', 'PARTIAL', 'TIMEOUT', 'HIT_TARGET', 'HIT_STOP'] } }
    ];
    
    // Aggregation pipeline
    const pipeline = [
      { $match: matchStage },
      { $sort: { closedAt: -1 } },
      { $skip: skip },
      { $limit: limit },
      // Join with decisions
      {
        $lookup: {
          from: 'ta_decisions',
          localField: 'runId',
          foreignField: 'runId',
          as: 'decision'
        }
      },
      { $unwind: { path: '$decision', preserveNullAndEmptyArrays: true } },
      // Join with runs for additional context
      {
        $lookup: {
          from: 'ta_runs',
          localField: 'runId',
          foreignField: 'runId',
          as: 'run'
        }
      },
      { $unwind: { path: '$run', preserveNullAndEmptyArrays: true } }
    ];
    
    const docs = await this.db.collection('ta_outcomes')
      .aggregate(pipeline)
      .toArray();
    
    // Transform to EdgeRow
    return docs.map(doc => this.transformToEdgeRow(doc));
  }

  /**
   * Load sample rows for debugging
   */
  async loadSample(limit: number = 20): Promise<EdgeRow[]> {
    return this.loadEdgeRows({ limit });
  }

  /**
   * Count total rows matching params
   */
  async countRows(params: LoadEdgeRowsParams = {}): Promise<number> {
    const { from, to, assets, timeframes } = params;
    
    const matchStage: any = {};
    
    if (from || to) {
      matchStage.closedAt = {};
      if (from) matchStage.closedAt.$gte = from.getTime();
      if (to) matchStage.closedAt.$lte = to.getTime();
    }
    
    if (assets && assets.length > 0) {
      matchStage.asset = { $in: assets.map(a => a.toUpperCase()) };
    }
    
    if (timeframes && timeframes.length > 0) {
      matchStage.timeframe = { $in: timeframes.map(t => t.toLowerCase()) };
    }
    
    matchStage.$or = [
      { outcomeClass: { $in: ['WIN', 'LOSS', 'PARTIAL', 'TIMEOUT'] } },
      { result: { $in: ['WIN', 'LOSS', 'PARTIAL', 'TIMEOUT', 'HIT_TARGET', 'HIT_STOP'] } }
    ];
    
    return this.db.collection('ta_outcomes').countDocuments(matchStage);
  }

  /**
   * Transform raw document to EdgeRow
   */
  private transformToEdgeRow(doc: any): EdgeRow {
    const decision = doc.decision || {};
    const run = doc.run || {};
    
    // Extract pattern info
    const patternTypes = this.extractPatternTypes(doc, decision, run);
    const primaryPatternType = patternTypes[0] || 'UNKNOWN';
    const patternFamily = getPatternFamily(primaryPatternType);
    
    // Extract probabilities
    const pEntry = decision.pEntry || decision.probability?.pEntry || 
                   decision.ml?.p_entry || 0.5;
    const expectedR = decision.expectedR || decision.expectation?.expectedR ||
                      decision.ml?.expected_r || 1.5;
    
    // Extract outcome
    const realizedR = doc.rMultiple || doc.realized_r || 0;
    const mfeR = doc.mfeR || doc.mfe_r || realizedR;
    const maeR = doc.maeR || doc.mae_r || 0;
    const outcomeClass = this.normalizeOutcomeClass(doc.outcomeClass || doc.result);
    
    // Extract regime
    const regime = normalizeRegime(doc.regime || decision.regime || run.regime);
    const volRegime = normalizeVolRegime(doc.volRegime || decision.volRegime || 'MED');
    
    // Extract ML info
    const mlProb = decision.ml?.p_entry || decision.mlProb;
    const mlStage = decision.ml?.model_id || decision.mlStage || 'UNKNOWN';
    const probabilitySource = decision.probabilitySource || 
                             decision.meta?.probabilitySource || 'FALLBACK';
    
    // Extract stability
    const stabilityMultiplier = decision.stabilityMultiplier || 
                               decision.stability?.multiplier || 1.0;
    
    // Extract geometry
    const geometry = {
      fitError: decision.geometry?.fitError || run.geometry?.fitError || 0.1,
      maturity: decision.geometry?.maturity || run.geometry?.maturity || 0.5,
      compression: decision.geometry?.compression || run.geometry?.compression || 0.5,
      symmetry: decision.geometry?.symmetry || run.geometry?.symmetry
    };
    
    // Apply buckets
    const buckets = applyBuckets({
      mlProb,
      stabilityMultiplier,
      geometry
    });
    
    return {
      runId: doc.runId || doc._id?.toString() || '',
      decisionRunId: decision.runId,
      outcomeId: doc._id?.toString(),
      
      asset: (doc.asset || 'UNKNOWN').toUpperCase(),
      timeframe: (doc.timeframe || '1d').toLowerCase(),
      ts: doc.timestamp || doc.ts || Date.now(),
      closedAt: doc.closedAt,
      
      patternTypes,
      primaryPatternType,
      patternFamily,
      
      regime,
      volRegime,
      
      pEntry,
      expectedR,
      ev: pEntry * expectedR,
      
      realizedR,
      mfeR,
      maeR,
      outcomeClass,
      
      mlProb,
      mlStage,
      probabilitySource,
      
      stabilityMultiplier,
      
      geometry,
      
      ...buckets
    };
  }

  /**
   * Extract pattern types from various sources
   */
  private extractPatternTypes(doc: any, decision: any, run: any): string[] {
    // Try different sources
    if (doc.patternTypes && doc.patternTypes.length > 0) {
      return doc.patternTypes;
    }
    
    if (decision.patternTypes && decision.patternTypes.length > 0) {
      return decision.patternTypes;
    }
    
    if (decision.topScenario?.type) {
      return [decision.topScenario.type];
    }
    
    if (run.patterns && run.patterns.length > 0) {
      return run.patterns.map((p: any) => p.type || p.patternType || 'UNKNOWN');
    }
    
    // Fallback: check scenario
    if (doc.scenarioId || decision.scenarioId) {
      return ['SCENARIO_BASED'];
    }
    
    return ['UNKNOWN'];
  }

  /**
   * Normalize outcome class
   */
  private normalizeOutcomeClass(raw: string | undefined): OutcomeClass {
    if (!raw) return 'UNKNOWN';
    
    const upper = raw.toUpperCase();
    
    if (upper === 'WIN' || upper === 'HIT_TARGET' || upper === 'TARGET_HIT') return 'WIN';
    if (upper === 'LOSS' || upper === 'HIT_STOP' || upper === 'STOP_HIT') return 'LOSS';
    if (upper === 'PARTIAL' || upper === 'PARTIAL_WIN') return 'PARTIAL';
    if (upper === 'TIMEOUT' || upper === 'EXPIRED') return 'TIMEOUT';
    if (upper === 'NO_ENTRY' || upper === 'SKIPPED') return 'NO_ENTRY';
    
    return 'UNKNOWN';
  }
}

// Singleton
let datasourceInstance: EdgeDatasource | null = null;

export function getEdgeDatasource(db: Db): EdgeDatasource {
  if (!datasourceInstance) {
    datasourceInstance = new EdgeDatasource(db);
  }
  return datasourceInstance;
}
