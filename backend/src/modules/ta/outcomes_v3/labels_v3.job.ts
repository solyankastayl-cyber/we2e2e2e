/**
 * Phase 8.3 — Outcomes V3 Backfill Job
 * 
 * Берёт ta_scenarios где нет ta_outcomes_v3 или status=PENDING
 * Вытягивает forward candles через provider
 * Вычисляет OutcomeV3
 * Вставляет в ta_outcomes_v3 (INSERT-only)
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuidv4 } from 'uuid';
import { evaluateOutcomeV3 } from './labels_v3.evaluator.js';
import { 
  OutcomeV3, 
  EvalInputsV3, 
  DEFAULT_THRESHOLDS,
  OutcomeClassV3 
} from './labels_v3.types.js';
import { createOutcomesV3Storage } from './outcomes_v3.storage.js';

const SCENARIOS_COLLECTION = 'ta_scenarios';
const CANDLES_COLLECTION = 'candles_binance';

export interface BackfillJobParams {
  asset?: string;
  timeframe?: string;
  from?: Date;
  to?: Date;
  limit?: number;
  dryRun?: boolean;
}

export interface BackfillJobResult {
  runId: string;
  processed: number;
  created: number;
  skipped: number;
  errors: number;
  byClass: Record<OutcomeClassV3, number>;
  durationMs: number;
}

export interface ScenarioRecord {
  _id: any;
  scenarioId: string;
  runId: string;
  asset: string;
  timeframe: string;
  direction: 'LONG' | 'SHORT';
  entry?: number;
  stop?: number;
  target1?: number;
  target2?: number;
  anchorIdx: number;
  anchorTs: number;
  createdAt: Date;
  patternType?: string;
  score?: number;
}

/**
 * Fetch forward candles for outcome evaluation
 */
async function fetchForwardCandles(
  db: Db,
  asset: string,
  timeframe: string,
  fromTs: number,
  barsNeeded: number
): Promise<{ closes: number[]; highs: number[]; lows: number[]; timestamps: number[] }> {
  const collection = db.collection(CANDLES_COLLECTION);
  
  const candles = await collection
    .find({
      symbol: asset,
      interval: timeframe.toLowerCase(),
      openTime: { $gte: fromTs }
    })
    .sort({ openTime: 1 })
    .limit(barsNeeded + 10)  // extra buffer
    .toArray();

  return {
    closes: candles.map(c => c.close),
    highs: candles.map(c => c.high),
    lows: candles.map(c => c.low),
    timestamps: candles.map(c => c.openTime),
  };
}

/**
 * Get scenarios without outcomes
 */
async function getScenariosWithoutOutcomes(
  db: Db,
  params: BackfillJobParams
): Promise<ScenarioRecord[]> {
  const scenarios = db.collection(SCENARIOS_COLLECTION);
  const outcomes = db.collection('ta_outcomes_v3');

  // Build match query
  const match: Record<string, any> = {};
  if (params.asset) match.asset = params.asset;
  if (params.timeframe) match.timeframe = params.timeframe;
  if (params.from) match.createdAt = { $gte: params.from };
  if (params.to) {
    match.createdAt = { ...match.createdAt, $lte: params.to };
  }

  // Get scenario IDs that already have outcomes
  const existingOutcomes = await outcomes
    .find({}, { projection: { scenarioId: 1 } })
    .toArray();
  const existingIds = new Set(existingOutcomes.map(o => o.scenarioId));

  // Fetch scenarios
  const allScenarios = await scenarios
    .find(match)
    .sort({ createdAt: -1 })
    .limit(params.limit || 1000)
    .toArray();

  // Filter out those with existing outcomes
  return allScenarios
    .filter(s => !existingIds.has(s.scenarioId || s._id.toString()))
    .map(s => ({
      _id: s._id,
      scenarioId: s.scenarioId || s._id.toString(),
      runId: s.runId || 'unknown',
      asset: s.asset,
      timeframe: s.timeframe,
      direction: s.direction || 'LONG',
      entry: s.entry || s.tradePlan?.entry,
      stop: s.stop || s.tradePlan?.stop,
      target1: s.target1 || s.tradePlan?.target1,
      target2: s.target2 || s.tradePlan?.target2,
      anchorIdx: s.anchorIdx || s.startIdx || 0,
      anchorTs: s.anchorTs || s.startTs || 0,
      createdAt: s.createdAt,
      patternType: s.patternType || s.type,
      score: s.score,
    })) as ScenarioRecord[];
}

/**
 * Run outcomes backfill job
 */
export async function runOutcomesBackfillJob(
  db: Db,
  params: BackfillJobParams = {}
): Promise<BackfillJobResult> {
  const runId = uuidv4();
  const startTime = Date.now();
  const storage = createOutcomesV3Storage(db);

  const result: BackfillJobResult = {
    runId,
    processed: 0,
    created: 0,
    skipped: 0,
    errors: 0,
    byClass: {
      WIN: 0,
      LOSS: 0,
      PARTIAL: 0,
      TIMEOUT: 0,
      NO_ENTRY: 0,
    },
    durationMs: 0,
  };

  console.log(`[OutcomesBackfill] Starting job ${runId}`);

  // Get scenarios to process
  const scenarios = await getScenariosWithoutOutcomes(db, params);
  console.log(`[OutcomesBackfill] Found ${scenarios.length} scenarios to process`);

  if (!scenarios.length) {
    result.durationMs = Date.now() - startTime;
    return result;
  }

  // Process each scenario
  for (const scenario of scenarios) {
    result.processed++;

    try {
      // Validate trade plan
      if (!scenario.entry || !scenario.stop || !scenario.target1) {
        result.skipped++;
        continue;
      }

      // Fetch forward candles
      const timeoutBars = 40;  // configurable
      const candles = await fetchForwardCandles(
        db,
        scenario.asset,
        scenario.timeframe,
        scenario.anchorTs,
        timeoutBars + 20
      );

      if (candles.closes.length < 5) {
        result.skipped++;
        continue;
      }

      // Build eval inputs
      const evalInputs: EvalInputsV3 = {
        runId: scenario.runId,
        scenarioId: scenario.scenarioId,
        asset: scenario.asset,
        timeframe: scenario.timeframe,
        entry: scenario.entry,
        stop: scenario.stop,
        t1: scenario.target1,
        t2: scenario.target2,
        entryType: 'BREAKOUT',
        timeoutBars,
        closes: candles.closes,
        highs: candles.highs,
        lows: candles.lows,
        timestamps: candles.timestamps,
        decisionIdx: 0,
      };

      // Evaluate outcome
      const outcome = evaluateOutcomeV3(evalInputs, DEFAULT_THRESHOLDS);
      
      // O3: Add labelVersion
      outcome.labelVersion = 'v3';

      // Store if not dry run
      if (!params.dryRun) {
        await storage.upsertByScenario(outcome);
      }

      result.created++;
      result.byClass[outcome.class]++;

    } catch (err: any) {
      console.error(`[OutcomesBackfill] Error processing ${scenario.scenarioId}: ${err.message}`);
      result.errors++;
    }
  }

  result.durationMs = Date.now() - startTime;
  console.log(`[OutcomesBackfill] Completed: ${result.created} created, ${result.skipped} skipped, ${result.errors} errors`);

  return result;
}

/**
 * Get backfill job status
 */
export async function getBackfillStatus(db: Db): Promise<{
  scenariosTotal: number;
  outcomesTotal: number;
  pendingCount: number;
  coverage: number;
}> {
  const scenarios = db.collection(SCENARIOS_COLLECTION);
  const outcomes = db.collection('ta_outcomes_v3');

  const scenariosTotal = await scenarios.countDocuments();
  const outcomesTotal = await outcomes.countDocuments();
  const pendingCount = scenariosTotal - outcomesTotal;
  const coverage = scenariosTotal > 0 ? outcomesTotal / scenariosTotal : 0;

  return {
    scenariosTotal,
    outcomesTotal,
    pendingCount,
    coverage,
  };
}
