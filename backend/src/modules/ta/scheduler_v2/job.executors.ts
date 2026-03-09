/**
 * Phase 8.5 — Job Executors
 * 
 * Actual implementations for each pipeline job
 */

import { Db } from 'mongodb';
import { JobKey, JobContext } from './scheduler.types.js';
import { runOutcomesBackfillJob, getBackfillStatus } from '../outcomes_v3/labels_v3.job.js';
import { 
  createMLDatasetV3Storage, 
  createMLDatasetV3Indexes,
  buildMLRowV3 
} from '../outcomes_v3/ml_dataset_v3.js';
import { createOutcomesV3Storage } from '../outcomes_v3/outcomes_v3.storage.js';

export interface JobExecutor {
  execute(ctx: JobContext): Promise<{ counts?: Record<string, number>; error?: string }>;
}

/**
 * JOB_OUTCOMES_BACKFILL_V3
 * Compute OutcomeV3 for scenarios with PENDING outcomes
 */
export const outcomesBackfillExecutor: JobExecutor = {
  async execute(ctx: JobContext): Promise<{ counts?: Record<string, number>; error?: string }> {
    try {
      ctx.logger('Starting outcomes backfill...');
      
      const result = await runOutcomesBackfillJob(ctx.db, {
        limit: 500,  // process in batches
      });

      return {
        counts: {
          processed: result.processed,
          created: result.created,
          skipped: result.skipped,
          errors: result.errors,
          wins: result.byClass.WIN,
          losses: result.byClass.LOSS,
        },
      };
    } catch (err: any) {
      return { error: err.message };
    }
  },
};

/**
 * JOB_DATASET_BUILD_V3
 * Build ML dataset from outcomes and features
 */
export const datasetBuildExecutor: JobExecutor = {
  async execute(ctx: JobContext): Promise<{ counts?: Record<string, number>; error?: string }> {
    try {
      ctx.logger('Starting dataset build V3...');

      const outcomesStorage = createOutcomesV3Storage(ctx.db);
      const datasetStorage = createMLDatasetV3Storage(ctx.db);
      await createMLDatasetV3Indexes(ctx.db);

      // Get outcomes that aren't in dataset yet
      const scenariosCol = ctx.db.collection('ta_scenarios');
      const datasetCol = ctx.db.collection('ta_ml_rows_v3');

      // Get existing dataset scenario IDs
      const existingRows = await datasetCol
        .find({}, { projection: { scenarioId: 1 } })
        .toArray();
      const existingIds = new Set(existingRows.map(r => r.scenarioId));

      // Get outcomes not in dataset
      const outcomesCol = ctx.db.collection('ta_outcomes_v3');
      const outcomes = await outcomesCol
        .find({ class: { $ne: 'NO_ENTRY' } })  // exclude NO_ENTRY
        .limit(1000)
        .toArray();

      let created = 0;
      let skipped = 0;

      for (const outcome of outcomes) {
        if (existingIds.has(outcome.scenarioId)) {
          skipped++;
          continue;
        }

        // Get scenario features
        const scenario = await scenariosCol.findOne({ 
          $or: [
            { scenarioId: outcome.scenarioId },
            { _id: outcome.scenarioId }
          ]
        });

        if (!scenario) {
          skipped++;
          continue;
        }

        // Extract features from scenario
        const features: Record<string, number> = {};
        
        // Core features
        if (scenario.score !== undefined) features.score = scenario.score;
        if (scenario.confidence !== undefined) features.confidence = scenario.confidence;
        if (scenario.confluenceScore !== undefined) features.confluence = scenario.confluenceScore;
        
        // Risk features
        if (scenario.riskReward !== undefined) features.risk_reward = scenario.riskReward;
        if (scenario.riskPct !== undefined) features.risk_pct = scenario.riskPct;
        
        // Pattern features
        if (scenario.patternScore !== undefined) features.pattern_score = scenario.patternScore;
        
        // Context features  
        if (scenario.regimeScore !== undefined) features.regime_score = scenario.regimeScore;
        if (scenario.volatilityScore !== undefined) features.vol_score = scenario.volatilityScore;

        // Indicator features (if available)
        if (scenario.indicators) {
          if (scenario.indicators.rsi !== undefined) features.rsi = scenario.indicators.rsi;
          if (scenario.indicators.atr !== undefined) features.atr = scenario.indicators.atr;
          if (scenario.indicators.macd !== undefined) features.macd = scenario.indicators.macd;
        }

        // Build ML row
        const row = buildMLRowV3(
          outcome.scenarioId,
          outcome.asset,
          outcome.timeframe,
          features,
          outcome,
          '3.0'
        );

        await datasetStorage.insertRow(row);
        created++;
      }

      const stats = await datasetStorage.getStats();

      return {
        counts: {
          processed: outcomes.length,
          created,
          skipped,
          totalRows: stats.totalRows,
          wins: stats.byClass.WIN,
          losses: stats.byClass.LOSS,
        },
      };
    } catch (err: any) {
      return { error: err.message };
    }
  },
};

/**
 * JOB_TRAIN_MODEL
 * Train ML model on dataset
 */
export const trainModelExecutor: JobExecutor = {
  async execute(ctx: JobContext): Promise<{ counts?: Record<string, number>; error?: string }> {
    try {
      ctx.logger('Starting model training...');

      const datasetStorage = createMLDatasetV3Storage(ctx.db);
      const stats = await datasetStorage.getStats();

      // Check minimum rows
      const minRows = ctx.config.thresholds.minRowsForTrainShadow;
      if (stats.totalRows < minRows) {
        return {
          counts: { 
            totalRows: stats.totalRows, 
            required: minRows,
            skipped: 1 
          },
          error: `Insufficient data: ${stats.totalRows} < ${minRows}`,
        };
      }

      // Export data for training
      const trainData = await datasetStorage.exportForTraining({
        trainRatio: 0.8,
        excludeNoEntry: true,
      });

      ctx.logger(`Prepared ${trainData.length} rows for training`);

      // TODO: Call Python ML service for actual training
      // For now, log what we would train on
      
      return {
        counts: {
          totalRows: stats.totalRows,
          trainRows: trainData.length,
          wins: stats.byClass.WIN,
          losses: stats.byClass.LOSS,
          winRate: Math.round(stats.winRate * 100),
        },
      };
    } catch (err: any) {
      return { error: err.message };
    }
  },
};

/**
 * JOB_EVAL_MODEL
 * Evaluate model on holdout split
 */
export const evalModelExecutor: JobExecutor = {
  async execute(ctx: JobContext): Promise<{ counts?: Record<string, number>; error?: string }> {
    try {
      ctx.logger('Starting model evaluation...');

      // Get latest model from registry
      const modelsCol = ctx.db.collection('ta_ml_models');
      const latestModel = await modelsCol.findOne(
        { stage: 'SHADOW' },
        { sort: { createdAt: -1 } }
      );

      if (!latestModel) {
        return { counts: { skipped: 1 }, error: 'No SHADOW model found' };
      }

      // TODO: Actual evaluation with holdout data
      // For now, return placeholder metrics

      return {
        counts: {
          modelId: latestModel.modelId || 'unknown',
          auc: latestModel.metrics?.auc || 0,
          ece: latestModel.metrics?.ece || 0,
          accuracy: latestModel.metrics?.accuracy || 0,
        },
      };
    } catch (err: any) {
      return { error: err.message };
    }
  },
};

/**
 * JOB_REGISTER_MODEL
 * Register model in registry
 */
export const registerModelExecutor: JobExecutor = {
  async execute(ctx: JobContext): Promise<{ counts?: Record<string, number>; error?: string }> {
    try {
      ctx.logger('Registering model...');

      // This would be called after successful training
      // For now, check if there's a pending model to register

      return {
        counts: {
          registered: 0,  // placeholder
        },
      };
    } catch (err: any) {
      return { error: err.message };
    }
  },
};

/**
 * JOB_PROMOTE_MODEL
 * Promote model from SHADOW to LIVE_LITE if gates pass
 */
export const promoteModelExecutor: JobExecutor = {
  async execute(ctx: JobContext): Promise<{ counts?: Record<string, number>; error?: string }> {
    try {
      ctx.logger('Checking promotion gates...');

      const modelsCol = ctx.db.collection('ta_ml_models');
      const latestShadow = await modelsCol.findOne(
        { stage: 'SHADOW', active: true },
        { sort: { createdAt: -1 } }
      );

      if (!latestShadow) {
        return { counts: { promoted: 0 }, error: 'No active SHADOW model' };
      }

      // Check quality gates
      const auc = latestShadow.metrics?.auc || 0;
      const ece = latestShadow.metrics?.ece || 1;

      const minAuc = ctx.config.thresholds.minAucForPromote;
      const maxEce = ctx.config.thresholds.maxEceForPromote;

      const passesGates = auc >= minAuc && ece <= maxEce;

      if (!passesGates) {
        return {
          counts: {
            promoted: 0,
            auc: Math.round(auc * 1000) / 1000,
            ece: Math.round(ece * 1000) / 1000,
            minAuc,
            maxEce,
          },
          error: `Gates not passed: AUC=${auc.toFixed(3)} (min ${minAuc}), ECE=${ece.toFixed(3)} (max ${maxEce})`,
        };
      }

      // Promote model
      await modelsCol.updateOne(
        { _id: latestShadow._id },
        { 
          $set: { 
            stage: 'LIVE_LITE',
            promotedAt: new Date(),
          } 
        }
      );

      return {
        counts: {
          promoted: 1,
          modelId: latestShadow.modelId,
          auc: Math.round(auc * 1000) / 1000,
          ece: Math.round(ece * 1000) / 1000,
        },
      };
    } catch (err: any) {
      return { error: err.message };
    }
  },
};

/**
 * JOB_REBUILD_CALIBRATION
 * Rebuild probability calibration
 */
export const rebuildCalibrationExecutor: JobExecutor = {
  async execute(ctx: JobContext): Promise<{ counts?: Record<string, number>; error?: string }> {
    try {
      ctx.logger('Rebuilding calibration...');

      // Get outcomes for calibration
      const outcomesCol = ctx.db.collection('ta_outcomes_v3');
      const outcomes = await outcomesCol
        .find({ class: { $in: ['WIN', 'LOSS'] } })
        .toArray();

      if (outcomes.length < 100) {
        return { counts: { skipped: 1 }, error: 'Insufficient outcomes for calibration' };
      }

      // TODO: Actual calibration computation
      // For now, return placeholder

      return {
        counts: {
          outcomesUsed: outcomes.length,
          calibrated: 1,
        },
      };
    } catch (err: any) {
      return { error: err.message };
    }
  },
};

/**
 * JOB_DRIFT_CHECK
 * Check for feature/prediction drift
 */
export const driftCheckExecutor: JobExecutor = {
  async execute(ctx: JobContext): Promise<{ counts?: Record<string, number>; error?: string }> {
    try {
      ctx.logger('Checking for drift...');

      // Get recent predictions
      const predictionsCol = ctx.db.collection('ta_ml_predictions');
      const recentPredictions = await predictionsCol
        .find({})
        .sort({ createdAt: -1 })
        .limit(1000)
        .toArray();

      if (recentPredictions.length < 100) {
        return { counts: { checked: 0 }, error: 'Insufficient predictions for drift check' };
      }

      // TODO: Actual drift detection (PSI, feature distribution comparison)
      // For now, return placeholder

      return {
        counts: {
          checked: recentPredictions.length,
          driftDetected: 0,
        },
      };
    } catch (err: any) {
      return { error: err.message };
    }
  },
};

/**
 * Get all executors
 */
export function getAllExecutors(): Partial<Record<JobKey, JobExecutor>> {
  return {
    JOB_OUTCOMES_BACKFILL_V3: outcomesBackfillExecutor,
    JOB_DATASET_BUILD_V3: datasetBuildExecutor,
    JOB_TRAIN_MODEL: trainModelExecutor,
    JOB_EVAL_MODEL: evalModelExecutor,
    JOB_REGISTER_MODEL: registerModelExecutor,
    JOB_PROMOTE_MODEL: promoteModelExecutor,
    JOB_REBUILD_CALIBRATION: rebuildCalibrationExecutor,
    JOB_DRIFT_CHECK: driftCheckExecutor,
  };
}
