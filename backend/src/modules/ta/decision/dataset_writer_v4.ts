/**
 * P1.6 — Dataset Writer V4
 * 
 * Writes dataset rows from executed trades.
 * V4 format includes: geometry, gates, graph, ML predictions.
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuid } from 'uuid';
import { SimPosition, SimScenario } from '../simulator/domain.js';
import { DatasetRowV4, LabelsV4, OutcomeClassV4 } from '../ml_v4/labels_v4.types.js';
import { MarketRegime } from '../ml_v4/regime_mixture.js';
import { logger } from '../infra/logger.js';

const COLLECTION_NAME = 'ta_ml_rows_v4';

export interface DatasetWriterV4Config {
  enabled: boolean;
  minRForWrite: number;
  maxRForWrite: number;
  writeOnTimeout: boolean;
  writeOnNoEntry: boolean;
}

const DEFAULT_CONFIG: DatasetWriterV4Config = {
  enabled: true,
  minRForWrite: -5,
  maxRForWrite: 10,
  writeOnTimeout: true,
  writeOnNoEntry: true, // Important for entry model training
};

let config = { ...DEFAULT_CONFIG };
let dbInstance: Db | null = null;

export function initDatasetWriterV4(db: Db): void {
  dbInstance = db;
  console.log('[DatasetWriterV4] Initialized');
}

export function setDatasetWriterV4Config(newConfig: Partial<DatasetWriterV4Config>): void {
  config = { ...config, ...newConfig };
}

export function getDatasetWriterV4Config(): DatasetWriterV4Config {
  return { ...config };
}

export interface WriteRowV4Input {
  position: SimPosition;
  scenario: SimScenario & { _v4?: V4ScenarioData };
  runId: string;
  candles?: any[];
}

export interface V4ScenarioData {
  geometry: any;
  gateScore: number;
  gateResult: any;
  graphBoost: any;
  regime: MarketRegime;
  regimeConfidence: number;
  pEntry: number;
  rExpected: number;
  evBeforeML: number;
  evAfterML: number;
  features: Record<string, number>;
  modelId: string;
}

/**
 * Write V4 dataset row from closed position
 */
export async function writeDatasetRowV4(input: WriteRowV4Input): Promise<boolean> {
  if (!config.enabled) return false;
  if (!dbInstance) {
    logger.warn({ phase: 'dataset_writer_v4' }, 'DB not initialized');
    return false;
  }

  const { position, scenario, runId } = input;

  // Validate position
  if (position.status !== 'CLOSED') return false;

  // Get R-multiple
  const r = position.rMultiple ?? 0;
  const entryHit = position.exitReason !== 'NO_ENTRY';

  // Filter check
  if (!entryHit && !config.writeOnNoEntry) return false;
  if (entryHit && (r < config.minRForWrite || r > config.maxRForWrite)) {
    logger.debug({ phase: 'dataset_writer_v4', r, reason: 'out_of_range' }, 'Skipping row');
    return false;
  }
  if (!config.writeOnTimeout && position.exitReason === 'TIMEOUT') return false;

  try {
    // Extract V4 data
    const v4 = (scenario as any)._v4 as V4ScenarioData | undefined;

    // Build features
    const features: Record<string, number> = v4?.features || {};

    // Ensure core features
    if (!features.risk_reward) {
      const risk = Math.abs(position.entryPrice - position.stopPrice);
      const reward = Math.abs((position.target1Price || position.entryPrice) - position.entryPrice);
      features.risk_reward = risk > 0 ? reward / risk : 0;
    }

    // Add V4-specific features
    if (v4) {
      features.gate_score = v4.gateScore;
      features.p_entry_model = v4.pEntry;
      features.r_expected_model = v4.rExpected;
      features.ev_before_ml = v4.evBeforeML;
      features.ev_after_ml = v4.evAfterML;
      features.regime_confidence = v4.regimeConfidence;
    }

    // Geometry features
    if (v4?.geometry) {
      features.geom_fit_error = v4.geometry.fitError ?? 0;
      features.geom_maturity = v4.geometry.maturity ?? 0;
      features.geom_symmetry = v4.geometry.symmetry ?? 0;
      features.geom_compression = v4.geometry.compression ?? 0;
    }

    // Graph features
    if (v4?.graphBoost) {
      features.graph_boost_factor = v4.graphBoost.graphBoostFactor ?? 1;
      features.graph_lift = v4.graphBoost.lift ?? 1;
      features.graph_conditional_prob = v4.graphBoost.conditionalProb ?? 0;
    }

    // Build labels V4
    const labels: LabelsV4 = {
      label_entry_hit: entryHit ? 1 : 0,
      label_entry_probability: v4?.pEntry,
      label_r_multiple: entryHit ? r : 0,  // Important: null/0 if no entry
      label_mfe_r: entryHit ? (position.mfePct / 100) * (features.risk_reward || 1) : 0,
      label_mae_r: entryHit ? (position.maePct / 100) * (features.risk_reward || 1) : 0,
      label_time_to_entry: position.barsInTrade || 0,
      label_time_to_exit: position.barsInTrade || 0,
      label_ev: v4?.evAfterML,
      label_outcome_class: determineOutcomeClass(entryHit, r, position.exitReason),
    };

    // Build row
    const row: DatasetRowV4 = {
      rowId: uuid(),
      scenarioId: position.scenarioId,
      asset: position.symbol,
      timeframe: position.tf,
      timestamp: new Date(position.entryTs * 1000),
      features,
      labels,
      regime: v4?.regime || 'RANGE',
      split: determineSplit(position.entryTs),
      featureSchemaVersion: '4.0',
    };

    // Insert
    const collection = dbInstance.collection(COLLECTION_NAME);
    await collection.insertOne(row);

    logger.info({
      phase: 'dataset_writer_v4',
      scenarioId: position.scenarioId,
      entryHit: labels.label_entry_hit,
      r: labels.label_r_multiple.toFixed(2),
      outcomeClass: labels.label_outcome_class,
      regime: row.regime,
    }, 'V4 row written');

    return true;
  } catch (err: any) {
    logger.error({ phase: 'dataset_writer_v4', error: err.message }, 'Failed to write row');
    return false;
  }
}

/**
 * Determine outcome class
 */
function determineOutcomeClass(
  entryHit: boolean,
  r: number,
  exitReason?: string
): OutcomeClassV4 {
  if (!entryHit) return 'NO_ENTRY';
  if (r >= 1.5) return 'WIN';
  if (r > 0 && r < 1.5) return 'PARTIAL';
  if (r <= -1) return 'LOSS';
  return 'TIMEOUT';
}

/**
 * Determine split based on timestamp
 */
function determineSplit(ts: number): 'train' | 'val' | 'test' {
  const date = new Date(ts * 1000);
  const year = date.getFullYear();
  
  if (year <= 2022) return 'train';
  if (year === 2023) return 'val';
  return 'test';
}

/**
 * Get dataset V4 stats
 */
export async function getDatasetV4Stats(db: Db): Promise<{
  total: number;
  byEntryHit: { hit: number; noEntry: number };
  bySplit: Record<string, number>;
  byRegime: Record<string, number>;
  avgR: number;
  entryRate: number;
}> {
  const collection = db.collection(COLLECTION_NAME);
  
  const pipeline = [
    {
      $facet: {
        total: [{ $count: 'count' }],
        byEntryHit: [
          { $group: { _id: '$labels.label_entry_hit', count: { $sum: 1 } } }
        ],
        bySplit: [
          { $group: { _id: '$split', count: { $sum: 1 } } }
        ],
        byRegime: [
          { $group: { _id: '$regime', count: { $sum: 1 } } }
        ],
        avgMetrics: [
          { $match: { 'labels.label_entry_hit': 1 } },
          { $group: { _id: null, avgR: { $avg: '$labels.label_r_multiple' } } }
        ],
      }
    }
  ];

  const results = await collection.aggregate(pipeline).toArray();
  const r = results[0] || {};

  const total = r.total?.[0]?.count || 0;
  
  const byEntryHit = { hit: 0, noEntry: 0 };
  for (const e of r.byEntryHit || []) {
    if (e._id === 1) byEntryHit.hit = e.count;
    else byEntryHit.noEntry = e.count;
  }

  const bySplit: Record<string, number> = {};
  for (const s of r.bySplit || []) {
    if (s._id) bySplit[s._id] = s.count;
  }

  const byRegime: Record<string, number> = {};
  for (const s of r.byRegime || []) {
    if (s._id) byRegime[s._id] = s.count;
  }

  return {
    total,
    byEntryHit,
    bySplit,
    byRegime,
    avgR: r.avgMetrics?.[0]?.avgR || 0,
    entryRate: total > 0 ? byEntryHit.hit / total : 0,
  };
}

/**
 * Create indexes
 */
export async function createDatasetV4Indexes(db: Db): Promise<void> {
  const collection = db.collection(COLLECTION_NAME);
  
  await collection.createIndex({ rowId: 1 }, { unique: true });
  await collection.createIndex({ scenarioId: 1 });
  await collection.createIndex({ 'labels.label_entry_hit': 1 });
  await collection.createIndex({ split: 1 });
  await collection.createIndex({ regime: 1 });
  await collection.createIndex({ timestamp: 1 });
  await collection.createIndex({ asset: 1, timeframe: 1, timestamp: 1 });
  
  console.log('[DatasetWriterV4] Indexes created');
}

/**
 * Direct write for batch simulation (P1.6.1)
 * Writes a row directly without position wrapper
 */
export interface DirectWriteV4Input {
  scenario: {
    scenarioId: string;
    patternType: string;
    direction: 'LONG' | 'SHORT';
    entry: number;
    stop: number;
    target1: number;
    target2?: number;
    riskReward: number;
    geometry?: any;
    gateScore: number;
    graphBoostFactor: number;
    regime: string;
    regimeConfidence: number;
    pEntry: number;
    rExpected: number;
    evBeforeML: number;
    evAfterML: number;
    features: Record<string, number>;
  };
  decisionPack: {
    asset: string;
    timeframe: string;
    timestamp: Date;
    modelId: string;
  };
  outcome: {
    entryHit: boolean;
    rMultiple: number;
    mfeR: number;
    maeR: number;
    exitReason: string;
    closeTs: number;
  };
  split: 'train' | 'val' | 'test';
}

export async function writeDatasetRowV4Direct(
  db: Db,
  input: DirectWriteV4Input
): Promise<boolean> {
  const { scenario, decisionPack, outcome, split } = input;
  
  try {
    const labels: LabelsV4 = {
      label_entry_hit: outcome.entryHit ? 1 : 0,
      label_entry_probability: scenario.pEntry,
      label_r_multiple: outcome.entryHit ? outcome.rMultiple : 0,
      label_mfe_r: outcome.mfeR,
      label_mae_r: outcome.maeR,
      label_time_to_entry: 0,
      label_time_to_exit: 0,
      label_ev: scenario.evAfterML,
      label_outcome_class: determineOutcomeClass(
        outcome.entryHit,
        outcome.rMultiple,
        outcome.exitReason
      ),
    };
    
    const row: DatasetRowV4 = {
      rowId: uuid(),
      scenarioId: scenario.scenarioId,
      patternType: scenario.patternType,
      asset: decisionPack.asset,
      timeframe: decisionPack.timeframe,
      timestamp: decisionPack.timestamp,
      features: {
        ...scenario.features,
        gate_score: scenario.gateScore,
        graph_boost_factor: scenario.graphBoostFactor,
        p_entry_model: scenario.pEntry,
        r_expected_model: scenario.rExpected,
        ev_before_ml: scenario.evBeforeML,
        ev_after_ml: scenario.evAfterML,
        regime_confidence: scenario.regimeConfidence,
      },
      labels,
      regime: scenario.regime as any,
      split,
      featureSchemaVersion: '4.0',
    };
    
    const collection = db.collection(COLLECTION_NAME);
    await collection.insertOne(row);
    
    return true;
  } catch (err: any) {
    console.error('[DatasetWriterV4] Direct write error:', err.message);
    return false;
  }
}
