/**
 * P1.3-P1.5 — Dataset V4 Builder
 * 
 * Full pipeline: Features + Labels V4 + Time Split + Regime
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import { 
  DatasetRowV4, 
  LabelsV4, 
  DatasetV4Config, 
  DEFAULT_DATASET_V4_CONFIG 
} from './labels_v4.types.js';
import { buildLabelsV4, getLabelStats } from './labels_v4.builder.js';
import { splitDataset, SplitResult, validateSplit, getSplitBoundaries } from './time_split.js';
import { 
  detectRegime, 
  calculateRegimeFeatures, 
  MarketRegime,
  RegimeFeatures 
} from './regime_mixture.js';
import { extractGeometryFeatures } from '../geometry/geometry.engine.js';
import { extractGraphFeatures } from '../graph/graph.integration.js';

const DATASET_V4_COLLECTION = 'ta_ml_dataset_v4';
const OUTCOMES_V3_COLLECTION = 'ta_outcomes_v3';
const SCENARIOS_COLLECTION = 'ta_scenarios';

export interface DatasetV4BuildResult {
  runId: string;
  rowsCreated: number;
  rowsSkipped: number;
  errors: number;
  split: SplitResult['stats'];
  labelStats: ReturnType<typeof getLabelStats>;
  regimeDistribution: Record<MarketRegime, number>;
  durationMs: number;
}

export interface DatasetV4Storage {
  insertRow(row: DatasetRowV4): Promise<void>;
  insertRows(rows: DatasetRowV4[]): Promise<number>;
  getRows(filter?: { split?: string; regime?: string; limit?: number }): Promise<DatasetRowV4[]>;
  getTrainData(): Promise<DatasetRowV4[]>;
  getValData(): Promise<DatasetRowV4[]>;
  getTestData(): Promise<DatasetRowV4[]>;
  getStats(): Promise<DatasetV4Stats>;
  clear(): Promise<void>;
}

export interface DatasetV4Stats {
  totalRows: number;
  trainRows: number;
  valRows: number;
  testRows: number;
  byRegime: Record<MarketRegime, number>;
  entryRate: number;
  avgR: number;
  featureCount: number;
}

export function createDatasetV4Storage(db: Db): DatasetV4Storage {
  const collection: Collection = db.collection(DATASET_V4_COLLECTION);

  return {
    async insertRow(row: DatasetRowV4): Promise<void> {
      await collection.updateOne(
        { rowId: row.rowId },
        { $set: row },
        { upsert: true }
      );
    },

    async insertRows(rows: DatasetRowV4[]): Promise<number> {
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

    async getRows(filter?: { split?: string; regime?: string; limit?: number }): Promise<DatasetRowV4[]> {
      const query: Record<string, any> = {};
      if (filter?.split) query.split = filter.split;
      if (filter?.regime) query.regime = filter.regime;
      
      return collection
        .find(query, { projection: { _id: 0 } })
        .limit(filter?.limit || 50000)
        .toArray() as Promise<DatasetRowV4[]>;
    },

    async getTrainData(): Promise<DatasetRowV4[]> {
      return collection
        .find({ split: 'train' }, { projection: { _id: 0 } })
        .toArray() as Promise<DatasetRowV4[]>;
    },

    async getValData(): Promise<DatasetRowV4[]> {
      return collection
        .find({ split: 'val' }, { projection: { _id: 0 } })
        .toArray() as Promise<DatasetRowV4[]>;
    },

    async getTestData(): Promise<DatasetRowV4[]> {
      return collection
        .find({ split: 'test' }, { projection: { _id: 0 } })
        .toArray() as Promise<DatasetRowV4[]>;
    },

    async getStats(): Promise<DatasetV4Stats> {
      const pipeline = [
        {
          $facet: {
            total: [{ $count: 'count' }],
            bySplit: [{ $group: { _id: '$split', count: { $sum: 1 } } }],
            byRegime: [{ $group: { _id: '$regime', count: { $sum: 1 } } }],
            avgMetrics: [{
              $group: {
                _id: null,
                entryRate: { $avg: '$labels.label_entry_hit' },
                avgR: { $avg: '$labels.label_r_multiple' },
              }
            }],
          }
        }
      ];

      const results = await collection.aggregate(pipeline).toArray();
      const r = results[0] || {};

      const totalRows = r.total?.[0]?.count || 0;
      
      const bySplit: Record<string, number> = {};
      for (const s of r.bySplit || []) {
        if (s._id) bySplit[s._id] = s.count;
      }

      const byRegime: Record<MarketRegime, number> = {
        TREND_UP: 0, TREND_DOWN: 0, RANGE: 0, TRANSITION: 0,
      };
      for (const s of r.byRegime || []) {
        if (s._id && s._id in byRegime) {
          byRegime[s._id as MarketRegime] = s.count;
        }
      }

      // Get feature count from sample
      const sample = await collection.findOne({});
      const featureCount = sample?.features ? Object.keys(sample.features).length : 0;

      return {
        totalRows,
        trainRows: bySplit.train || 0,
        valRows: bySplit.val || 0,
        testRows: bySplit.test || 0,
        byRegime,
        entryRate: r.avgMetrics?.[0]?.entryRate || 0,
        avgR: r.avgMetrics?.[0]?.avgR || 0,
        featureCount,
      };
    },

    async clear(): Promise<void> {
      await collection.deleteMany({});
    },
  };
}

/**
 * Build Dataset V4 from outcomes and scenarios
 */
export async function buildDatasetV4(
  db: Db,
  config: DatasetV4Config = DEFAULT_DATASET_V4_CONFIG
): Promise<DatasetV4BuildResult> {
  const runId = uuidv4();
  const startTime = Date.now();
  
  const storage = createDatasetV4Storage(db);
  const outcomesCol = db.collection(OUTCOMES_V3_COLLECTION);
  const scenariosCol = db.collection(SCENARIOS_COLLECTION);
  
  console.log(`[DatasetV4] Starting build ${runId}`);
  
  const rows: DatasetRowV4[] = [];
  const regimeDistribution: Record<MarketRegime, number> = {
    TREND_UP: 0, TREND_DOWN: 0, RANGE: 0, TRANSITION: 0,
  };
  
  let rowsCreated = 0;
  let rowsSkipped = 0;
  let errors = 0;
  
  // Get all outcomes
  const outcomes = await outcomesCol.find({}).toArray();
  console.log(`[DatasetV4] Processing ${outcomes.length} outcomes`);
  
  for (const outcome of outcomes) {
    try {
      // Get corresponding scenario
      const scenario = await scenariosCol.findOne({
        $or: [
          { scenarioId: outcome.scenarioId },
          { _id: outcome.scenarioId }
        ]
      });
      
      if (!scenario) {
        rowsSkipped++;
        continue;
      }
      
      // Build labels V4
      const labels = buildLabelsV4(outcome, config);
      
      // Extract features
      const features: Record<string, number> = {};
      
      // Base scenario features
      if (scenario.score !== undefined) features.score = scenario.score;
      if (scenario.confidence !== undefined) features.confidence = scenario.confidence;
      if (scenario.confluenceScore !== undefined) features.confluence = scenario.confluenceScore;
      if (scenario.riskReward !== undefined) features.risk_reward = scenario.riskReward;
      
      // Gate score if available
      if (scenario.gateScore !== undefined) features.gate_score = scenario.gateScore;
      
      // Geometry features
      if (scenario.geometry) {
        const geomFeatures = extractGeometryFeatures(scenario.geometry);
        Object.assign(features, geomFeatures);
      }
      
      // Graph boost features
      if (scenario.graphBoost) {
        const graphFeatures = extractGraphFeatures(scenario.graphBoost);
        Object.assign(features, graphFeatures);
      }
      
      // Indicator features
      if (scenario.indicators) {
        if (scenario.indicators.rsi !== undefined) features.rsi = scenario.indicators.rsi;
        if (scenario.indicators.atr !== undefined) features.atr = scenario.indicators.atr;
        if (scenario.indicators.adx !== undefined) features.adx = scenario.indicators.adx;
      }
      
      // Detect regime (simplified - would need candle data in production)
      const regime: MarketRegime = scenario.regime || 'RANGE';
      regimeDistribution[regime]++;
      
      // Build timestamp
      const timestamp = scenario.createdAt || outcome.createdAt || new Date();
      
      // Create row
      const row: DatasetRowV4 = {
        rowId: `${outcome.scenarioId}_v4`,
        scenarioId: outcome.scenarioId,
        asset: outcome.asset,
        timeframe: outcome.timeframe,
        timestamp: new Date(timestamp),
        features,
        labels,
        regime,
        featureSchemaVersion: config.featureSchemaVersion,
      };
      
      rows.push(row);
      rowsCreated++;
      
    } catch (err: any) {
      errors++;
      console.error(`[DatasetV4] Error processing ${outcome.scenarioId}: ${err.message}`);
    }
  }
  
  // Apply time-based split
  console.log(`[DatasetV4] Applying time-based split...`);
  const splitResult = splitDataset(rows, config);
  const validation = validateSplit(splitResult);
  
  if (!validation.valid) {
    console.warn(`[DatasetV4] Split validation issues:`, validation.issues);
  }
  
  // Save rows (excluding purged)
  const rowsToSave = [...splitResult.train, ...splitResult.val, ...splitResult.test];
  console.log(`[DatasetV4] Saving ${rowsToSave.length} rows (${splitResult.purged.length} purged)`);
  
  await storage.clear();
  await storage.insertRows(rowsToSave);
  
  // Get label stats
  const allLabels = rowsToSave.map(r => r.labels);
  const labelStats = getLabelStats(allLabels);
  
  const durationMs = Date.now() - startTime;
  console.log(`[DatasetV4] Complete: ${rowsCreated} created, ${rowsSkipped} skipped in ${durationMs}ms`);
  
  return {
    runId,
    rowsCreated: rowsToSave.length,
    rowsSkipped: rowsSkipped + splitResult.purged.length,
    errors,
    split: splitResult.stats,
    labelStats,
    regimeDistribution,
    durationMs,
  };
}

/**
 * Create indexes
 */
export async function createDatasetV4Indexes(db: Db): Promise<void> {
  const collection = db.collection(DATASET_V4_COLLECTION);
  
  await collection.createIndex({ rowId: 1 }, { unique: true });
  await collection.createIndex({ scenarioId: 1 });
  await collection.createIndex({ split: 1 });
  await collection.createIndex({ regime: 1 });
  await collection.createIndex({ timestamp: 1 });
  await collection.createIndex({ 'labels.label_entry_hit': 1 });
  
  console.log('[DatasetV4] Indexes created');
}
