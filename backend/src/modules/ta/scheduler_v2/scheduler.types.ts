/**
 * Phase 8.5 — Auto Scheduler Types
 * 
 * Job definitions, pipeline DAG, threshold triggers
 */

export type JobKey = 
  | 'JOB_OUTCOMES_BACKFILL_V3'
  | 'JOB_DATASET_BUILD_V3'
  | 'JOB_TRAIN_MODEL'
  | 'JOB_EVAL_MODEL'
  | 'JOB_REGISTER_MODEL'
  | 'JOB_PROMOTE_MODEL'
  | 'JOB_REBUILD_CALIBRATION'
  | 'JOB_DRIFT_CHECK';

export type JobStatus = 'STARTED' | 'SUCCESS' | 'FAILED' | 'SKIPPED';

export interface JobLock {
  lockKey: string;
  ownerId: string;
  expiresAt: Date;
  updatedAt: Date;
}

export interface JobRun {
  runId: string;
  jobKey: JobKey;
  status: JobStatus;
  startedAt: Date;
  finishedAt?: Date;
  meta?: {
    counts?: Record<string, number>;
    thresholds?: Record<string, number>;
    error?: string;
    metrics?: Record<string, number>;
  };
}

export interface JobState {
  jobKey: JobKey;
  lastCursor?: string;
  lastSuccessAt?: Date;
  counters: {
    rowsSinceLastTrain: number;
    outcomesSinceLastDataset: number;
    scenariosSinceLastOutcomes: number;
  };
}

export interface JobDefinition {
  key: JobKey;
  name: string;
  description: string;
  dependsOn: JobKey[];
  minNewItems?: number;  // threshold to trigger
  cronExpression?: string;
  freezeAware: boolean;
  priority: number;  // P0 = highest
}

export const JOB_DEFINITIONS: Record<JobKey, JobDefinition> = {
  JOB_OUTCOMES_BACKFILL_V3: {
    key: 'JOB_OUTCOMES_BACKFILL_V3',
    name: 'Outcomes Backfill V3',
    description: 'Compute OutcomeV3 for scenarios with PENDING outcomes',
    dependsOn: [],
    minNewItems: 1,
    cronExpression: '*/30 * * * *',  // every 30 min
    freezeAware: true,
    priority: 0,
  },
  JOB_DATASET_BUILD_V3: {
    key: 'JOB_DATASET_BUILD_V3',
    name: 'Dataset Build V3',
    description: 'Build ML dataset from outcomes and features',
    dependsOn: ['JOB_OUTCOMES_BACKFILL_V3'],
    minNewItems: 500,  // min new outcomes
    cronExpression: '0 */2 * * *',  // every 2 hours
    freezeAware: true,
    priority: 0,
  },
  JOB_TRAIN_MODEL: {
    key: 'JOB_TRAIN_MODEL',
    name: 'Train Model',
    description: 'Train ML model on dataset',
    dependsOn: ['JOB_DATASET_BUILD_V3'],
    minNewItems: 5000,  // min new rows for LIVE_LITE, 500 for SHADOW
    cronExpression: '0 3 * * *',  // daily at 3am
    freezeAware: true,
    priority: 0,
  },
  JOB_EVAL_MODEL: {
    key: 'JOB_EVAL_MODEL',
    name: 'Evaluate Model',
    description: 'Evaluate model on holdout split',
    dependsOn: ['JOB_TRAIN_MODEL'],
    freezeAware: true,
    priority: 0,
  },
  JOB_REGISTER_MODEL: {
    key: 'JOB_REGISTER_MODEL',
    name: 'Register Model',
    description: 'Register model in registry',
    dependsOn: ['JOB_EVAL_MODEL'],
    freezeAware: true,
    priority: 0,
  },
  JOB_PROMOTE_MODEL: {
    key: 'JOB_PROMOTE_MODEL',
    name: 'Promote Model',
    description: 'Promote model from SHADOW to LIVE_LITE if gates pass',
    dependsOn: ['JOB_REGISTER_MODEL'],
    freezeAware: true,
    priority: 0,
  },
  JOB_REBUILD_CALIBRATION: {
    key: 'JOB_REBUILD_CALIBRATION',
    name: 'Rebuild Calibration',
    description: 'Rebuild probability calibration',
    dependsOn: [],
    cronExpression: '0 4 * * *',  // daily at 4am
    freezeAware: true,
    priority: 1,
  },
  JOB_DRIFT_CHECK: {
    key: 'JOB_DRIFT_CHECK',
    name: 'Drift Check',
    description: 'Check for feature/prediction drift',
    dependsOn: [],
    cronExpression: '0 */6 * * *',  // every 6 hours
    freezeAware: true,
    priority: 1,
  },
};

export interface SchedulerConfig {
  enabled: boolean;
  freezeEnabled: boolean;
  thresholds: {
    minOutcomesForDataset: number;
    minRowsForTrainShadow: number;
    minRowsForTrainLiveLite: number;
    minAucForPromote: number;
    maxEceForPromote: number;
  };
  cron: {
    outcomesCron: string;
    datasetCron: string;
    trainCron: string;
    calibrationCron: string;
    driftCron: string;
  };
}

export const DEFAULT_SCHEDULER_CONFIG: SchedulerConfig = {
  enabled: true,
  freezeEnabled: false,
  thresholds: {
    minOutcomesForDataset: 500,
    minRowsForTrainShadow: 500,
    minRowsForTrainLiveLite: 5000,
    minAucForPromote: 0.55,
    maxEceForPromote: 0.05,
  },
  cron: {
    outcomesCron: '*/30 * * * *',
    datasetCron: '0 */2 * * *',
    trainCron: '0 3 * * *',
    calibrationCron: '0 4 * * *',
    driftCron: '0 */6 * * *',
  },
};

export interface JobContext {
  db: any;
  config: SchedulerConfig;
  logger: (msg: string, data?: any) => void;
}
