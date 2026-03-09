/**
 * MetaBrain v2.1 — Controller
 * 
 * Main orchestration for module attribution and weight computation
 */

import {
  AnalysisModule,
  ModuleWeight,
  ModuleAttributionResult,
  ModuleWeightHistory,
  LearningConfig,
  DEFAULT_LEARNING_CONFIG
} from './module_attribution.types.js';
import { computeModuleAttribution } from './module_attribution.compute.js';
import { 
  computeModuleWeights, 
  getDefaultWeights,
  createWeightHistoryEntry,
  getWeightSummary
} from './module_weights.engine.js';
import { 
  loadAttributionRecordsInWindow,
  generateSyntheticRecords 
} from './module_datasource.js';
import {
  saveModuleAttributions,
  saveModuleWeights,
  saveWeightHistory,
  getModuleWeights,
  getModuleAttributions,
  getModuleWeightMap,
  getRecentWeightChanges
} from './module_storage.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY CACHE
// ═══════════════════════════════════════════════════════════════

let cachedWeights: ModuleWeight[] | null = null;
let lastComputeTime: Date | null = null;
const CACHE_TTL_MS = 5 * 60 * 1000;  // 5 minutes

// ═══════════════════════════════════════════════════════════════
// MAIN CONTROLLER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Rebuild module attribution and weights
 */
export async function rebuildModuleAttribution(
  config: LearningConfig = DEFAULT_LEARNING_CONFIG,
  options?: {
    asset?: string;
    timeframe?: string;
    regime?: string;
    useSynthetic?: boolean;
  }
): Promise<{
  attribution: ModuleAttributionResult;
  weights: ModuleWeight[];
  history: ModuleWeightHistory[];
}> {
  
  // Load trade records
  let records = await loadAttributionRecordsInWindow(config.dataWindowDays, {
    asset: options?.asset,
    timeframe: options?.timeframe,
    regime: options?.regime
  });
  
  // If no records, use synthetic for testing
  if (records.length < config.minSampleSize && options?.useSynthetic !== false) {
    console.log('[MetaBrainLearning] No records found, using synthetic data for testing');
    records = generateSyntheticRecords(500);
  }
  
  // Compute attribution
  const attribution = computeModuleAttribution(records, config, options);
  
  // Get previous weights
  const previousWeights = await getModuleWeightMap(options?.regime);
  
  // Compute new weights
  const weights = computeModuleWeights(attribution.modules, previousWeights, config, options?.regime);
  
  // Create weight history
  const history: ModuleWeightHistory[] = [];
  for (const w of weights) {
    const oldWeight = previousWeights.get(w.module);
    if (oldWeight === undefined || Math.abs(oldWeight - w.weight) > 0.01) {
      history.push(createWeightHistoryEntry(w.module, oldWeight, w.weight, options?.regime));
    }
  }
  
  // Save to database
  await saveModuleAttributions(attribution.modules);
  await saveModuleWeights(weights);
  if (history.length > 0) {
    await saveWeightHistory(history);
  }
  
  // Update cache
  cachedWeights = weights;
  lastComputeTime = new Date();
  
  return { attribution, weights, history };
}

/**
 * Get current module weights (with caching)
 */
export async function getCurrentWeights(regime?: string): Promise<ModuleWeight[]> {
  // Return cache if fresh and no regime filter
  if (!regime && cachedWeights && lastComputeTime) {
    const age = Date.now() - lastComputeTime.getTime();
    if (age < CACHE_TTL_MS) {
      return cachedWeights;
    }
  }
  
  // Fetch from DB
  const dbWeights = await getModuleWeights(regime);
  
  if (dbWeights.length === 0) {
    // Return default weights if none found
    return getDefaultWeights();
  }
  
  const weights = dbWeights.map(w => ({
    module: w.module as AnalysisModule,
    weight: w.weight,
    rawWeight: w.rawWeight,
    confidence: w.confidence,
    basedOnSample: w.basedOnSample,
    basedOnEdgeScore: w.basedOnEdgeScore,
    regime: w.regime,
    updatedAt: w.updatedAt
  }));
  
  // Update cache if no regime filter
  if (!regime) {
    cachedWeights = weights;
    lastComputeTime = new Date();
  }
  
  return weights;
}

/**
 * Get weight for specific module
 */
export async function getModuleWeight(module: AnalysisModule, regime?: string): Promise<number> {
  const weights = await getCurrentWeights(regime);
  const found = weights.find(w => w.module === module);
  return found?.weight ?? 1.0;
}

/**
 * Get current attribution
 */
export async function getCurrentAttribution(regime?: string): Promise<ModuleAttributionResult | null> {
  const attributions = await getModuleAttributions(regime);
  
  if (attributions.length === 0) return null;
  
  // Reconstruct result
  const modules = attributions.map(a => ({
    module: a.module as AnalysisModule,
    winRate: a.winRate,
    avgR: a.avgR,
    profitFactor: a.profitFactor,
    sharpe: a.sharpe,
    sampleSize: a.sampleSize,
    confidence: a.confidence,
    edgeScore: a.edgeScore,
    impact: a.impact as 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE',
    calculatedAt: a.calculatedAt
  }));
  
  const sorted = [...modules].sort((a, b) => b.edgeScore - a.edgeScore);
  
  return {
    regime,
    baseline: {
      winRate: 0.5,
      avgR: 0,
      profitFactor: 1,
      totalTrades: modules.reduce((sum, m) => sum + m.sampleSize, 0) / modules.length
    },
    modules,
    topModules: sorted.filter(m => m.impact === 'POSITIVE').map(m => m.module),
    weakModules: sorted.filter(m => m.impact === 'NEGATIVE').map(m => m.module),
    calculatedAt: new Date(),
    dataWindowDays: DEFAULT_LEARNING_CONFIG.dataWindowDays
  };
}

/**
 * Force recompute (bypass cache)
 */
export async function forceRecompute(
  options?: Parameters<typeof rebuildModuleAttribution>[1]
): Promise<{
  attribution: ModuleAttributionResult;
  weights: ModuleWeight[];
}> {
  cachedWeights = null;
  lastComputeTime = null;
  
  const result = await rebuildModuleAttribution(DEFAULT_LEARNING_CONFIG, options);
  return { attribution: result.attribution, weights: result.weights };
}

/**
 * Get learning status
 */
export async function getLearningStatus(): Promise<{
  hasData: boolean;
  lastComputed: Date | null;
  weightSummary: ReturnType<typeof getWeightSummary>;
  recentChanges: number;
}> {
  const weights = await getCurrentWeights();
  const recentChanges = await getRecentWeightChanges(7, 100);
  
  return {
    hasData: weights.length > 0 && weights[0].basedOnSample > 0,
    lastComputed: lastComputeTime,
    weightSummary: getWeightSummary(weights),
    recentChanges: recentChanges.length
  };
}
