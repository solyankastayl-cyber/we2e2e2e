/**
 * Phase 5.2 B4 — Calibration Training & Storage
 * 
 * Implements Isotonic Regression for probability calibration
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import {
  CalibrationModelDoc,
  CalibrationTrainRequest,
  ReliabilityBucket,
  CALIBRATION_COLLECTION,
  DEFAULT_CALIBRATION_CONFIG,
} from './calibration.types.js';

// ═══════════════════════════════════════════════════════════════
// Calibration Storage
// ═══════════════════════════════════════════════════════════════

export class CalibrationStorage {
  private db: Db;
  private models: Collection;

  constructor(db: Db) {
    this.db = db;
    this.models = db.collection(CALIBRATION_COLLECTION);
  }

  async ensureIndexes(): Promise<void> {
    await this.models.createIndex({ modelId: 1 }, { unique: true });
    await this.models.createIndex({ trainedAt: -1 });
    await this.models.createIndex({ version: 1 });
    console.log('[CalibrationStorage] Indexes ensured');
  }

  async saveModel(model: CalibrationModelDoc): Promise<void> {
    await this.models.insertOne(model);
  }

  async getLatestModel(): Promise<CalibrationModelDoc | null> {
    const doc = await this.models.findOne({}, { sort: { trainedAt: -1 } });
    if (!doc) return null;
    const { _id, ...model } = doc as any;
    return model as CalibrationModelDoc;
  }

  async getModel(modelId: string): Promise<CalibrationModelDoc | null> {
    const doc = await this.models.findOne({ modelId });
    if (!doc) return null;
    const { _id, ...model } = doc as any;
    return model as CalibrationModelDoc;
  }

  async listModels(limit: number = 10): Promise<CalibrationModelDoc[]> {
    const docs = await this.models
      .find({})
      .sort({ trainedAt: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...model } = doc as any;
      return model as CalibrationModelDoc;
    });
  }
}

// ═══════════════════════════════════════════════════════════════
// Isotonic Regression Implementation
// ═══════════════════════════════════════════════════════════════

/**
 * Pool Adjacent Violators Algorithm (PAVA) for isotonic regression
 * Ensures monotonically increasing output
 */
export function isotonicRegression(
  x: number[],
  y: number[],
  weights?: number[]
): { x: number[]; y: number[] } {
  if (x.length !== y.length || x.length === 0) {
    return { x: [], y: [] };
  }

  const n = x.length;
  const w = weights || Array(n).fill(1);

  // Sort by x
  const indices = Array.from({ length: n }, (_, i) => i);
  indices.sort((a, b) => x[a] - x[b]);

  const sortedX = indices.map(i => x[i]);
  const sortedY = indices.map(i => y[i]);
  const sortedW = indices.map(i => w[i]);

  // PAVA algorithm
  const blocks: { sum: number; weight: number; start: number; end: number }[] = [];

  for (let i = 0; i < n; i++) {
    blocks.push({
      sum: sortedY[i] * sortedW[i],
      weight: sortedW[i],
      start: i,
      end: i,
    });

    // Pool adjacent violators
    while (blocks.length > 1) {
      const last = blocks[blocks.length - 1];
      const prev = blocks[blocks.length - 2];

      const lastMean = last.sum / last.weight;
      const prevMean = prev.sum / prev.weight;

      if (prevMean <= lastMean) break;

      // Merge blocks
      prev.sum += last.sum;
      prev.weight += last.weight;
      prev.end = last.end;
      blocks.pop();
    }
  }

  // Build result
  const resultX: number[] = [];
  const resultY: number[] = [];

  for (const block of blocks) {
    const mean = block.sum / block.weight;
    // Add start and end points of each block
    if (resultX.length === 0 || resultX[resultX.length - 1] !== sortedX[block.start]) {
      resultX.push(sortedX[block.start]);
      resultY.push(mean);
    }
    if (sortedX[block.end] !== sortedX[block.start]) {
      resultX.push(sortedX[block.end]);
      resultY.push(mean);
    }
  }

  return { x: resultX, y: resultY };
}

// ═══════════════════════════════════════════════════════════════
// Calibration Trainer
// ═══════════════════════════════════════════════════════════════

export class CalibrationTrainer {
  private db: Db;
  private storage: CalibrationStorage;

  constructor(db: Db) {
    this.db = db;
    this.storage = new CalibrationStorage(db);
  }

  /**
   * Train calibration model from backtest or outcomes data
   */
  async train(request: CalibrationTrainRequest = {}): Promise<CalibrationModelDoc> {
    const config = {
      minSamples: request.minSamples ?? DEFAULT_CALIBRATION_CONFIG.minSamples,
      excludeNoEntry: request.excludeNoEntry ?? DEFAULT_CALIBRATION_CONFIG.excludeNoEntry,
      excludeTimeout: request.excludeTimeout ?? DEFAULT_CALIBRATION_CONFIG.excludeTimeout,
    };

    // Load training data
    const data = await this.loadTrainingData(config, request.source || 'backtest');

    if (data.length < config.minSamples) {
      throw new Error(`Insufficient data: ${data.length} samples, need ${config.minSamples}`);
    }

    // Extract x (pRaw) and y (win=1, loss=0)
    const x = data.map(d => d.pRaw);
    const y = data.map(d => d.win ? 1 : 0);

    // Run isotonic regression
    const { x: calibX, y: calibY } = isotonicRegression(x, y);

    // Calculate metrics
    const reliability = this.computeReliabilityBuckets(data);
    const ece = this.computeECE(data);
    const brier = this.computeBrierScore(data);

    // Build model document
    const model: CalibrationModelDoc = {
      modelId: uuidv4(),
      modelType: 'ISOTONIC',
      version: `v${Date.now()}`,
      trainedAt: new Date(),
      sampleSize: data.length,
      input: 'probabilityRaw',
      output: 'probabilityCalibrated',
      params: {
        x: calibX,
        y: calibY,
      },
      metrics: {
        ece,
        brier,
        reliability,
      },
      config,
    };

    // Save model
    await this.storage.ensureIndexes();
    await this.storage.saveModel(model);

    console.log(`[CalibrationTrainer] Model trained. ECE=${ece.toFixed(4)}, Brier=${brier.toFixed(4)}`);

    return model;
  }

  /**
   * Load training data from backtest trades or outcomes
   */
  private async loadTrainingData(
    config: any,
    source: string
  ): Promise<Array<{ pRaw: number; win: boolean }>> {
    const data: Array<{ pRaw: number; win: boolean }> = [];

    if (source === 'backtest') {
      // Load from ta_backtest_trades
      const trades = await this.db.collection('ta_backtest_trades')
        .find({})
        .toArray();

      for (const trade of trades) {
        if (config.excludeNoEntry && trade.exitType === 'NO_ENTRY') continue;
        if (config.excludeTimeout && trade.exitType === 'TIMEOUT') continue;

        const pRaw = trade.decisionSnapshot?.pEntry;
        if (typeof pRaw !== 'number') continue;

        const win = trade.exitType === 'T1' || trade.exitType === 'T2';
        data.push({ pRaw, win });
      }
    } else {
      // Load from ta_outcomes_v3
      const outcomes = await this.db.collection('ta_outcomes_v3')
        .find({})
        .toArray();

      for (const outcome of outcomes) {
        if (config.excludeNoEntry && outcome.class === 'NO_ENTRY') continue;
        if (config.excludeTimeout && outcome.class === 'TIMEOUT') continue;

        const pRaw = outcome.pEntry || outcome.probabilityRaw;
        if (typeof pRaw !== 'number') continue;

        const win = outcome.class === 'WIN';
        data.push({ pRaw, win });
      }
    }

    return data;
  }

  /**
   * Compute reliability buckets
   */
  private computeReliabilityBuckets(
    data: Array<{ pRaw: number; win: boolean }>
  ): ReliabilityBucket[] {
    const ranges = ['0.0-0.2', '0.2-0.4', '0.4-0.5', '0.5-0.6', '0.6-0.7', '0.7-0.8', '0.8-1.0'];
    const buckets: Map<string, { total: number; wins: number; sumP: number }> = new Map();

    for (const range of ranges) {
      buckets.set(range, { total: 0, wins: 0, sumP: 0 });
    }

    for (const d of data) {
      const range = this.getBucketRange(d.pRaw);
      const bucket = buckets.get(range)!;
      bucket.total++;
      bucket.sumP += d.pRaw;
      if (d.win) bucket.wins++;
    }

    return ranges.map(range => {
      const bucket = buckets.get(range)!;
      const predictedWin = bucket.total > 0 ? bucket.sumP / bucket.total : 0;
      const actualWin = bucket.total > 0 ? bucket.wins / bucket.total : 0;
      return {
        range,
        predictedWin,
        actualWin,
        count: bucket.total,
        gap: predictedWin - actualWin,
      };
    });
  }

  private getBucketRange(p: number): string {
    if (p < 0.2) return '0.0-0.2';
    if (p < 0.4) return '0.2-0.4';
    if (p < 0.5) return '0.4-0.5';
    if (p < 0.6) return '0.5-0.6';
    if (p < 0.7) return '0.6-0.7';
    if (p < 0.8) return '0.7-0.8';
    return '0.8-1.0';
  }

  /**
   * Expected Calibration Error
   */
  private computeECE(data: Array<{ pRaw: number; win: boolean }>): number {
    const buckets = this.computeReliabilityBuckets(data);
    const total = data.length;
    
    if (total === 0) return 0;

    let ece = 0;
    for (const bucket of buckets) {
      ece += (bucket.count / total) * Math.abs(bucket.gap);
    }

    return ece;
  }

  /**
   * Brier Score
   */
  private computeBrierScore(data: Array<{ pRaw: number; win: boolean }>): number {
    if (data.length === 0) return 0;

    let sum = 0;
    for (const d of data) {
      const y = d.win ? 1 : 0;
      sum += Math.pow(d.pRaw - y, 2);
    }

    return sum / data.length;
  }
}

// ═══════════════════════════════════════════════════════════════
// Singleton
// ═══════════════════════════════════════════════════════════════

let storageInstance: CalibrationStorage | null = null;

export function getCalibrationStorage(db: Db): CalibrationStorage {
  if (!storageInstance) {
    storageInstance = new CalibrationStorage(db);
  }
  return storageInstance;
}
