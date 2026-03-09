/**
 * Phase 8.3 — Outcomes V3 Storage
 * 
 * MongoDB storage for OutcomeV3 records
 */

import { Db, Collection, ObjectId } from 'mongodb';
import { OutcomeV3, OutcomeClassV3, OutcomeV3Stats } from './labels_v3.types.js';

const COLLECTION_NAME = 'ta_outcomes_v3';

export interface OutcomesV3Storage {
  insertOne(outcome: OutcomeV3): Promise<string>;
  insertMany(outcomes: OutcomeV3[]): Promise<string[]>;
  upsertByScenario(outcome: OutcomeV3): Promise<void>;
  findByRunId(runId: string): Promise<OutcomeV3[]>;
  findByScenarioId(scenarioId: string): Promise<OutcomeV3 | null>;
  findLatest(asset: string, timeframe: string, limit?: number): Promise<OutcomeV3[]>;
  getStats(filter?: { asset?: string; timeframe?: string }): Promise<OutcomeV3Stats>;
  countByClass(filter?: { asset?: string; timeframe?: string }): Promise<Record<OutcomeClassV3, number>>;
}

export function createOutcomesV3Storage(db: Db): OutcomesV3Storage {
  const collection: Collection = db.collection(COLLECTION_NAME);

  return {
    async insertOne(outcome: OutcomeV3): Promise<string> {
      const result = await collection.insertOne(outcome);
      return result.insertedId.toString();
    },

    async insertMany(outcomes: OutcomeV3[]): Promise<string[]> {
      if (!outcomes.length) return [];
      const result = await collection.insertMany(outcomes);
      return Object.values(result.insertedIds).map(id => id.toString());
    },

    async upsertByScenario(outcome: OutcomeV3): Promise<void> {
      await collection.updateOne(
        { scenarioId: outcome.scenarioId },
        { $set: outcome },
        { upsert: true }
      );
    },

    async findByRunId(runId: string): Promise<OutcomeV3[]> {
      return collection.find({ runId }).toArray() as Promise<OutcomeV3[]>;
    },

    async findByScenarioId(scenarioId: string): Promise<OutcomeV3 | null> {
      return collection.findOne({ scenarioId }, { projection: { _id: 0 } }) as Promise<OutcomeV3 | null>;
    },

    async findLatest(asset: string, timeframe: string, limit = 100): Promise<OutcomeV3[]> {
      return collection
        .find({ asset, timeframe }, { projection: { _id: 0 } })
        .sort({ createdAt: -1 })
        .limit(limit)
        .toArray() as Promise<OutcomeV3[]>;
    },

    async getStats(filter?: { asset?: string; timeframe?: string }): Promise<OutcomeV3Stats> {
      const match: Record<string, any> = {};
      if (filter?.asset) match.asset = filter.asset;
      if (filter?.timeframe) match.timeframe = filter.timeframe;

      const pipeline = [
        { $match: match },
        {
          $group: {
            _id: null,
            total: { $sum: 1 },
            avgRMultiple: { $avg: '$rMultiple' },
            avgMfeR: { $avg: '$mfeR' },
            avgMaeR: { $avg: '$maeR' },
            avgTimeToEntry: { $avg: '$timeToEntryBars' },
            avgTimeToOutcome: { $avg: '$timeToOutcomeBars' },
            wins: { $sum: { $cond: [{ $eq: ['$class', 'WIN'] }, 1, 0] } },
            losses: { $sum: { $cond: [{ $eq: ['$class', 'LOSS'] }, 1, 0] } },
            partials: { $sum: { $cond: [{ $eq: ['$class', 'PARTIAL'] }, 1, 0] } },
            timeouts: { $sum: { $cond: [{ $eq: ['$class', 'TIMEOUT'] }, 1, 0] } },
            noEntries: { $sum: { $cond: [{ $eq: ['$class', 'NO_ENTRY'] }, 1, 0] } },
            totalProfitR: { $sum: { $cond: [{ $gt: ['$rMultiple', 0] }, '$rMultiple', 0] } },
            totalLossR: { $sum: { $cond: [{ $lt: ['$rMultiple', 0] }, { $abs: '$rMultiple' }, 0] } },
          },
        },
      ];

      const results = await collection.aggregate(pipeline).toArray();
      const r = results[0] || {};

      const enteredTotal = (r.wins || 0) + (r.losses || 0) + (r.partials || 0) + (r.timeouts || 0);
      const winRate = enteredTotal > 0 ? (r.wins || 0) / enteredTotal : 0;
      const profitFactor = (r.totalLossR || 0) > 0 
        ? (r.totalProfitR || 0) / r.totalLossR 
        : (r.totalProfitR || 0) > 0 ? Infinity : 0;

      return {
        total: r.total || 0,
        byClass: {
          WIN: r.wins || 0,
          LOSS: r.losses || 0,
          PARTIAL: r.partials || 0,
          TIMEOUT: r.timeouts || 0,
          NO_ENTRY: r.noEntries || 0,
        },
        avgRMultiple: r.avgRMultiple || 0,
        avgMfeR: r.avgMfeR || 0,
        avgMaeR: r.avgMaeR || 0,
        avgTimeToEntry: r.avgTimeToEntry || 0,
        avgTimeToOutcome: r.avgTimeToOutcome || 0,
        winRate,
        profitFactor,
      };
    },

    async countByClass(filter?: { asset?: string; timeframe?: string }): Promise<Record<OutcomeClassV3, number>> {
      const match: Record<string, any> = {};
      if (filter?.asset) match.asset = filter.asset;
      if (filter?.timeframe) match.timeframe = filter.timeframe;

      const pipeline = [
        { $match: match },
        { $group: { _id: '$class', count: { $sum: 1 } } },
      ];

      const results = await collection.aggregate(pipeline).toArray();
      
      const counts: Record<OutcomeClassV3, number> = {
        WIN: 0,
        LOSS: 0,
        PARTIAL: 0,
        TIMEOUT: 0,
        NO_ENTRY: 0,
      };

      for (const r of results) {
        if (r._id in counts) {
          counts[r._id as OutcomeClassV3] = r.count;
        }
      }

      return counts;
    },
  };
}

/**
 * Create indexes for ta_outcomes_v3 collection
 */
export async function createOutcomesV3Indexes(db: Db): Promise<void> {
  const collection = db.collection(COLLECTION_NAME);
  
  await collection.createIndex({ runId: 1 });
  await collection.createIndex({ scenarioId: 1 }, { unique: true });
  await collection.createIndex({ asset: 1, timeframe: 1, createdAt: -1 });
  await collection.createIndex({ class: 1 });
  await collection.createIndex({ createdAt: -1 });
  
  console.log('[OutcomesV3] Indexes created');
}
