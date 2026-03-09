/**
 * Phase 8.3 — ML Dataset V3 Integration
 * 
 * Adds outcome labels to ML dataset rows:
 * - label_class (string)
 * - label_r (float)
 * - label_mfeR
 * - label_maeR
 * - label_tEntry
 * - label_tOutcome
 */

import { Db, Collection } from 'mongodb';
import { OutcomeV3, OutcomeClassV3 } from './labels_v3.types.js';

const ML_ROWS_V3_COLLECTION = 'ta_ml_rows_v3';
const OUTCOMES_V3_COLLECTION = 'ta_outcomes_v3';

export interface MLRowV3 {
  rowId: string;
  scenarioId: string;
  asset: string;
  timeframe: string;
  
  // Features (from existing dataset builder)
  features: Record<string, number>;
  
  // Labels V3
  label_class: OutcomeClassV3;
  label_r: number;           // rMultiple
  label_mfeR: number;
  label_maeR: number;
  label_tEntry: number;      // timeToEntryBars
  label_tOutcome: number;    // timeToOutcomeBars
  
  // For stratified sampling
  label_binary: 0 | 1;       // 1 = WIN, 0 = other
  
  // Meta
  createdAt: Date;
  featureSchemaVersion: string;
}

/**
 * Build ML dataset row from scenario features + outcome
 */
export function buildMLRowV3(
  scenarioId: string,
  asset: string,
  timeframe: string,
  features: Record<string, number>,
  outcome: OutcomeV3,
  featureSchemaVersion: string = '3.0'
): MLRowV3 {
  return {
    rowId: `${scenarioId}_v3`,
    scenarioId,
    asset,
    timeframe,
    features,
    label_class: outcome.class,
    label_r: outcome.rMultiple,
    label_mfeR: outcome.mfeR,
    label_maeR: outcome.maeR,
    label_tEntry: outcome.timeToEntryBars,
    label_tOutcome: outcome.timeToOutcomeBars,
    label_binary: outcome.class === 'WIN' ? 1 : 0,
    createdAt: new Date(),
    featureSchemaVersion,
  };
}

export interface MLDatasetV3Storage {
  insertRow(row: MLRowV3): Promise<void>;
  insertRows(rows: MLRowV3[]): Promise<number>;
  getRows(filter?: { asset?: string; timeframe?: string; limit?: number }): Promise<MLRowV3[]>;
  getStats(): Promise<MLDatasetV3Stats>;
  exportForTraining(options?: ExportOptions): Promise<MLRowV3[]>;
}

export interface MLDatasetV3Stats {
  totalRows: number;
  byClass: Record<OutcomeClassV3, number>;
  byAsset: Record<string, number>;
  avgRMultiple: number;
  winRate: number;
  featureCount: number;
}

export interface ExportOptions {
  trainRatio?: number;       // 0.8 = 80% train
  minRows?: number;
  excludeNoEntry?: boolean;
  balanceClasses?: boolean;
}

export function createMLDatasetV3Storage(db: Db): MLDatasetV3Storage {
  const collection: Collection = db.collection(ML_ROWS_V3_COLLECTION);

  return {
    async insertRow(row: MLRowV3): Promise<void> {
      await collection.updateOne(
        { rowId: row.rowId },
        { $set: row },
        { upsert: true }
      );
    },

    async insertRows(rows: MLRowV3[]): Promise<number> {
      if (!rows.length) return 0;
      
      const ops = rows.map(r => ({
        updateOne: {
          filter: { rowId: r.rowId },
          update: { $set: r },
          upsert: true,
        },
      }));

      const result = await collection.bulkWrite(ops);
      return result.upsertedCount + result.modifiedCount;
    },

    async getRows(filter?: { asset?: string; timeframe?: string; limit?: number }): Promise<MLRowV3[]> {
      const query: Record<string, any> = {};
      if (filter?.asset) query.asset = filter.asset;
      if (filter?.timeframe) query.timeframe = filter.timeframe;

      return collection
        .find(query, { projection: { _id: 0 } })
        .limit(filter?.limit || 10000)
        .toArray() as Promise<MLRowV3[]>;
    },

    async getStats(): Promise<MLDatasetV3Stats> {
      const pipeline = [
        {
          $group: {
            _id: null,
            totalRows: { $sum: 1 },
            avgRMultiple: { $avg: '$label_r' },
            wins: { $sum: { $cond: [{ $eq: ['$label_class', 'WIN'] }, 1, 0] } },
            losses: { $sum: { $cond: [{ $eq: ['$label_class', 'LOSS'] }, 1, 0] } },
            partials: { $sum: { $cond: [{ $eq: ['$label_class', 'PARTIAL'] }, 1, 0] } },
            timeouts: { $sum: { $cond: [{ $eq: ['$label_class', 'TIMEOUT'] }, 1, 0] } },
            noEntries: { $sum: { $cond: [{ $eq: ['$label_class', 'NO_ENTRY'] }, 1, 0] } },
          },
        },
      ];

      const results = await collection.aggregate(pipeline).toArray();
      const r = results[0] || {};

      const byAssetPipeline = [
        { $group: { _id: '$asset', count: { $sum: 1 } } },
      ];
      const byAssetResults = await collection.aggregate(byAssetPipeline).toArray();
      const byAsset: Record<string, number> = {};
      for (const a of byAssetResults) {
        byAsset[a._id] = a.count;
      }

      // Get feature count from sample row
      const sampleRow = await collection.findOne({});
      const featureCount = sampleRow?.features ? Object.keys(sampleRow.features).length : 0;

      const enteredTotal = (r.wins || 0) + (r.losses || 0) + (r.partials || 0) + (r.timeouts || 0);

      return {
        totalRows: r.totalRows || 0,
        byClass: {
          WIN: r.wins || 0,
          LOSS: r.losses || 0,
          PARTIAL: r.partials || 0,
          TIMEOUT: r.timeouts || 0,
          NO_ENTRY: r.noEntries || 0,
        },
        byAsset,
        avgRMultiple: r.avgRMultiple || 0,
        winRate: enteredTotal > 0 ? (r.wins || 0) / enteredTotal : 0,
        featureCount,
      };
    },

    async exportForTraining(options: ExportOptions = {}): Promise<MLRowV3[]> {
      const query: Record<string, any> = {};
      
      if (options.excludeNoEntry) {
        query.label_class = { $ne: 'NO_ENTRY' };
      }

      let rows = await collection
        .find(query, { projection: { _id: 0 } })
        .sort({ createdAt: 1 })  // time-based ordering
        .toArray() as MLRowV3[];

      // Balance classes if requested
      if (options.balanceClasses) {
        const byClass: Record<string, MLRowV3[]> = {};
        for (const row of rows) {
          if (!byClass[row.label_class]) byClass[row.label_class] = [];
          byClass[row.label_class].push(row);
        }

        // Find minimum class size
        const minSize = Math.min(...Object.values(byClass).map(arr => arr.length));
        
        // Sample equal amounts from each class
        rows = [];
        for (const cls of Object.keys(byClass)) {
          rows.push(...byClass[cls].slice(0, minSize));
        }
      }

      // Apply train ratio split
      if (options.trainRatio && options.trainRatio < 1) {
        const splitIdx = Math.floor(rows.length * options.trainRatio);
        rows = rows.slice(0, splitIdx);
      }

      return rows;
    },
  };
}

/**
 * Create indexes for ML dataset V3
 */
export async function createMLDatasetV3Indexes(db: Db): Promise<void> {
  const collection = db.collection(ML_ROWS_V3_COLLECTION);

  await collection.createIndex({ rowId: 1 }, { unique: true });
  await collection.createIndex({ scenarioId: 1 });
  await collection.createIndex({ asset: 1, timeframe: 1 });
  await collection.createIndex({ label_class: 1 });
  await collection.createIndex({ createdAt: 1 });
  await collection.createIndex({ label_binary: 1 });

  console.log('[MLDatasetV3] Indexes created');
}
