/**
 * P1.6 — Dataset Writer V4
 * 
 * Writes dataset rows from executed trades
 * Includes all pipeline features: geometry, gate, graph, regime, ML
 */

import { Db, Collection } from 'mongodb';
import { ProcessedScenario, DecisionPack } from './decision.engine.js';
import { DatasetRowV4, LabelsV4, OutcomeClassV4 } from '../ml_v4/labels_v4.types.js';
import { OutcomeV4 } from './outcome_evaluator.js';

const DATASET_V4_COLLECTION = 'ta_ml_rows_v4';

export interface DatasetWriter {
  writeFromTrade(
    decision: DecisionPack,
    executedScenario: ProcessedScenario,
    outcome: OutcomeV4
  ): Promise<string>;
  
  writeBatch(rows: DatasetRowV4[]): Promise<number>;
}

export function createDatasetWriter(db: Db): DatasetWriter {
  const collection: Collection = db.collection(DATASET_V4_COLLECTION);

  return {
    async writeFromTrade(
      decision: DecisionPack,
      scenario: ProcessedScenario,
      outcome: OutcomeV4
    ): Promise<string> {
      // Build labels from outcome
      const labels: LabelsV4 = {
        label_entry_hit: outcome.entryHit ? 1 : 0,
        label_r_multiple: outcome.entryHit ? outcome.rMultiple : 0,
        label_mfe_r: outcome.mfeR,
        label_mae_r: outcome.maeR,
        label_time_to_entry: outcome.barsToEntry,
        label_time_to_exit: outcome.barsToExit,
        label_outcome_class: mapExitReasonToClass(outcome.exitReason, outcome.entryHit),
      };

      // Merge all features
      const features: Record<string, number> = {
        ...scenario.features,
        
        // Add ML predictions as features (for analysis)
        ml_p_entry: scenario.pEntry,
        ml_r_expected: scenario.rExpected,
        ml_ev: scenario.mlPrediction.ev,
        
        // Decision context
        ev_before_ml: scenario.evBeforeML,
        ev_after_ml: scenario.evAfterML,
      };

      const row: DatasetRowV4 = {
        rowId: `${scenario.scenarioId}_v4_${Date.now()}`,
        scenarioId: scenario.scenarioId,
        asset: decision.asset,
        timeframe: decision.timeframe,
        timestamp: decision.timestamp,
        features,
        labels,
        regime: scenario.regime,
        featureSchemaVersion: '4.1',
      };

      await collection.updateOne(
        { rowId: row.rowId },
        { $set: row },
        { upsert: true }
      );

      return row.rowId;
    },

    async writeBatch(rows: DatasetRowV4[]): Promise<number> {
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
  };
}

function mapExitReasonToClass(exitReason: string, entryHit: boolean): OutcomeClassV4 {
  if (!entryHit) return 'NO_ENTRY';
  
  switch (exitReason) {
    case 'STOP': return 'LOSS';
    case 'TARGET1': return 'WIN';
    case 'TARGET2': return 'WIN';
    case 'TIMEOUT': return 'TIMEOUT';
    case 'TIMEOUT_PARTIAL': return 'PARTIAL';
    default: return 'TIMEOUT';
  }
}
