/**
 * P0.1 — Decision Explain API
 * 
 * Explainability Layer for Decision Engine
 * Shows breakdown of all boost factors and decision reasoning
 */

import { Db } from 'mongodb';
import { fetchMemoryBoost, DecisionMemoryBoost } from './decision.memory.js';
import { getLearningWeightMap, LearningWeightMap } from '../../metabrain_learning/learning.integration.js';
import { MarketRegime } from '../ml_v4/regime_mixture.js';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface ScoreBreakdown {
  baseEV: number;
  
  // Individual boosts
  patternBoost: number;
  liquidityBoost: number;
  physicsBoost: number;
  stateBoost: number;
  regimeBoost: number;
  graphBoost: number;
  geometryBoost: number;
  
  // Advanced multipliers
  edgeMultiplier: number;
  learningWeight: number;
  
  // Memory boost
  memoryBoost: {
    directionBoost: number;
    scenarioBoost: number;
  };
  
  // Final
  evAfterML: number;
  evAfterEdge: number;
  finalScore: number;
}

export interface MemoryContextExplain {
  confidence: number;
  matches: number;
  historicalBias: 'BULL' | 'BEAR' | 'NEUTRAL';
  riskAdjustment: number;
}

export interface ExecutionPlanExplain {
  baseSize: number;
  riskAdjustment: number;
  finalSize: number;
  multipliers: {
    confidence: number;
    edge: number;
    regime: number;
    memory: number;
  };
}

export interface DecisionExplainResult {
  asset: string;
  timeframe: string;
  timestamp: Date;
  
  // Top scenario
  scenario: string;
  direction: 'BULL' | 'BEAR' | 'NEUTRAL';
  patternType: string;
  
  // Score breakdown
  scoreBreakdown: ScoreBreakdown;
  
  // Memory context
  memoryContext: MemoryContextExplain;
  
  // Execution plan
  executionPlan: ExecutionPlanExplain;
  
  // Learning weights applied
  learningWeights: LearningWeightMap;
  
  // Regime info
  regime: MarketRegime;
  regimeConfidence: number;
  
  // Pipeline stages
  pipelineStages: PipelineStage[];
}

export interface PipelineStage {
  stage: string;
  input: number;
  output: number;
  boost: number;
  description: string;
}

// ═══════════════════════════════════════════════════════════════
// SNAPSHOT STORAGE
// ═══════════════════════════════════════════════════════════════

export interface DecisionSnapshot {
  asset: string;
  timeframe: string;
  ts: number;
  
  scenarioId: string;
  patternType: string;
  direction: string;
  
  baseEV: number;
  
  boosts: {
    pattern: number;
    liquidity: number;
    physics: number;
    state: number;
    regime: number;
    graph: number;
    geometry: number;
  };
  
  edgeMultiplier: number;
  learningWeight: number;
  
  memory: {
    directionBoost: number;
    scenarioBoost: number;
    riskAdjustment: number;
    confidence: number;
    matches: number;
  };
  
  finalScore: number;
  
  createdAt: Date;
}

let db: Db | null = null;

export function initExplainStorage(database: Db): void {
  db = database;
}

/**
 * Save decision snapshot for later explain
 */
export async function saveDecisionSnapshot(snapshot: DecisionSnapshot): Promise<void> {
  if (!db) return;
  
  const collection = db.collection('ta_decision_snapshots');
  
  await collection.updateOne(
    { asset: snapshot.asset, timeframe: snapshot.timeframe },
    { $set: snapshot },
    { upsert: true }
  );
}

/**
 * Get latest decision snapshot
 */
export async function getDecisionSnapshot(
  asset: string,
  timeframe: string
): Promise<DecisionSnapshot | null> {
  if (!db) return null;
  
  const collection = db.collection('ta_decision_snapshots');
  
  const doc = await collection.findOne(
    { asset, timeframe },
    { projection: { _id: 0 } }
  );
  
  return doc as DecisionSnapshot | null;
}

// ═══════════════════════════════════════════════════════════════
// EXPLAIN BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Build explain from snapshot
 */
export function buildExplainFromSnapshot(
  snapshot: DecisionSnapshot,
  learningWeights: LearningWeightMap
): DecisionExplainResult {
  // Calculate effective learning weight (average of applied weights)
  const effectiveLearningWeight = (
    learningWeights.pattern +
    learningWeights.physics +
    learningWeights.state +
    learningWeights.graph
  ) / 4;
  
  // Build score breakdown
  const scoreBreakdown: ScoreBreakdown = {
    baseEV: snapshot.baseEV,
    patternBoost: snapshot.boosts.pattern,
    liquidityBoost: snapshot.boosts.liquidity,
    physicsBoost: snapshot.boosts.physics,
    stateBoost: snapshot.boosts.state,
    regimeBoost: snapshot.boosts.regime,
    graphBoost: snapshot.boosts.graph,
    geometryBoost: snapshot.boosts.geometry,
    edgeMultiplier: snapshot.edgeMultiplier,
    learningWeight: effectiveLearningWeight,
    memoryBoost: {
      directionBoost: snapshot.memory.directionBoost,
      scenarioBoost: snapshot.memory.scenarioBoost
    },
    evAfterML: snapshot.baseEV * snapshot.boosts.pattern * snapshot.boosts.physics * snapshot.boosts.state,
    evAfterEdge: snapshot.baseEV * snapshot.edgeMultiplier,
    finalScore: snapshot.finalScore
  };
  
  // Build memory context
  const memoryContext: MemoryContextExplain = {
    confidence: snapshot.memory.confidence,
    matches: snapshot.memory.matches,
    historicalBias: snapshot.memory.directionBoost > 1 ? 'BULL' : 
                    snapshot.memory.directionBoost < 1 ? 'BEAR' : 'NEUTRAL',
    riskAdjustment: snapshot.memory.riskAdjustment
  };
  
  // Build execution plan
  const baseSize = 0.20; // Default 20%
  const executionPlan: ExecutionPlanExplain = {
    baseSize,
    riskAdjustment: snapshot.memory.riskAdjustment,
    finalSize: baseSize * snapshot.memory.riskAdjustment,
    multipliers: {
      confidence: 1.0,
      edge: snapshot.edgeMultiplier,
      regime: snapshot.boosts.regime,
      memory: snapshot.memory.riskAdjustment
    }
  };
  
  // Build pipeline stages
  const pipelineStages = buildPipelineStages(snapshot);
  
  return {
    asset: snapshot.asset,
    timeframe: snapshot.timeframe,
    timestamp: snapshot.createdAt,
    scenario: snapshot.scenarioId,
    direction: snapshot.direction as 'BULL' | 'BEAR' | 'NEUTRAL',
    patternType: snapshot.patternType,
    scoreBreakdown,
    memoryContext,
    executionPlan,
    learningWeights,
    regime: 'COMPRESSION' as MarketRegime, // Will be filled from actual data
    regimeConfidence: 0.8,
    pipelineStages
  };
}

/**
 * Build pipeline stages for visualization
 */
function buildPipelineStages(snapshot: DecisionSnapshot): PipelineStage[] {
  let currentValue = snapshot.baseEV;
  const stages: PipelineStage[] = [];
  
  // Pattern boost
  stages.push({
    stage: 'Pattern Detection',
    input: currentValue,
    output: currentValue * snapshot.boosts.pattern,
    boost: snapshot.boosts.pattern,
    description: `Pattern quality: ${snapshot.patternType}`
  });
  currentValue *= snapshot.boosts.pattern;
  
  // Liquidity boost
  stages.push({
    stage: 'Liquidity Analysis',
    input: currentValue,
    output: currentValue * snapshot.boosts.liquidity,
    boost: snapshot.boosts.liquidity,
    description: snapshot.boosts.liquidity > 1 ? 'Favorable liquidity' : 'Weak liquidity'
  });
  currentValue *= snapshot.boosts.liquidity;
  
  // Physics boost
  stages.push({
    stage: 'Physics Engine',
    input: currentValue,
    output: currentValue * snapshot.boosts.physics,
    boost: snapshot.boosts.physics,
    description: snapshot.boosts.physics > 1 ? 'Energy aligned' : 'Energy neutral'
  });
  currentValue *= snapshot.boosts.physics;
  
  // State boost
  stages.push({
    stage: 'State Machine',
    input: currentValue,
    output: currentValue * snapshot.boosts.state,
    boost: snapshot.boosts.state,
    description: snapshot.boosts.state > 1 ? 'State supports direction' : 'State neutral'
  });
  currentValue *= snapshot.boosts.state;
  
  // Regime boost
  stages.push({
    stage: 'Regime Analysis',
    input: currentValue,
    output: currentValue * snapshot.boosts.regime,
    boost: snapshot.boosts.regime,
    description: snapshot.boosts.regime > 1 ? 'Regime aligned' : 'Regime mismatch'
  });
  currentValue *= snapshot.boosts.regime;
  
  // Edge multiplier
  stages.push({
    stage: 'Edge Intelligence',
    input: currentValue,
    output: currentValue * snapshot.edgeMultiplier,
    boost: snapshot.edgeMultiplier,
    description: snapshot.edgeMultiplier > 1 ? 'Positive edge detected' : 'Neutral edge'
  });
  currentValue *= snapshot.edgeMultiplier;
  
  // Memory boost
  const memoryBoost = snapshot.memory.directionBoost * snapshot.memory.scenarioBoost;
  stages.push({
    stage: 'Market Memory',
    input: currentValue,
    output: currentValue * memoryBoost,
    boost: memoryBoost,
    description: `${snapshot.memory.matches} historical matches, ${Math.round(snapshot.memory.confidence * 100)}% confidence`
  });
  currentValue *= memoryBoost;
  
  return stages;
}

// ═══════════════════════════════════════════════════════════════
// LIVE EXPLAIN (Fallback when no snapshot)
// ═══════════════════════════════════════════════════════════════

/**
 * Build explain by fetching live data from modules
 */
export async function buildLiveExplain(
  asset: string,
  timeframe: string
): Promise<DecisionExplainResult | null> {
  try {
    // Fetch memory boost
    const memoryBoost = await fetchMemoryBoost(asset, timeframe);
    
    // Fetch learning weights
    let learningWeights: LearningWeightMap;
    try {
      learningWeights = await getLearningWeightMap('COMPRESSION');
    } catch {
      learningWeights = {
        pattern: 1.0, liquidity: 1.0, graph: 1.0, fractal: 1.0,
        physics: 1.0, state: 1.0, regime: 1.0, scenario: 1.0
      };
    }
    
    // Fetch module boosts
    const [physicsData, stateData] = await Promise.all([
      fetchModuleBoost('physics', asset, timeframe),
      fetchModuleBoost('state', asset, timeframe)
    ]);
    
    // Build mock explain with live data
    const baseEV = 0.5;
    const patternBoost = 1.0;
    const physicsBoost = physicsData.boost;
    const stateBoost = stateData.boost;
    const regimeBoost = 1.0;
    const edgeMultiplier = 1.0;
    
    const memoryMultiplier = memoryBoost.bullishBoost; // Assume BULL for demo
    const scenarioBoost = 1.0;
    
    const finalScore = baseEV * patternBoost * physicsBoost * stateBoost * 
                       regimeBoost * edgeMultiplier * memoryMultiplier * scenarioBoost;
    
    const scoreBreakdown: ScoreBreakdown = {
      baseEV,
      patternBoost,
      liquidityBoost: 1.0,
      physicsBoost,
      stateBoost,
      regimeBoost,
      graphBoost: 1.0,
      geometryBoost: 1.0,
      edgeMultiplier,
      learningWeight: 1.0,
      memoryBoost: {
        directionBoost: memoryBoost.bullishBoost,
        scenarioBoost: 1.0
      },
      evAfterML: baseEV * patternBoost * physicsBoost * stateBoost,
      evAfterEdge: baseEV * edgeMultiplier,
      finalScore
    };
    
    const memoryContext: MemoryContextExplain = {
      confidence: memoryBoost.memoryConfidence,
      matches: memoryBoost.matchCount,
      historicalBias: memoryBoost.historicalBias,
      riskAdjustment: memoryBoost.riskAdjustment
    };
    
    const baseSize = 0.20;
    const executionPlan: ExecutionPlanExplain = {
      baseSize,
      riskAdjustment: memoryBoost.riskAdjustment,
      finalSize: baseSize * memoryBoost.riskAdjustment,
      multipliers: {
        confidence: 1.0,
        edge: edgeMultiplier,
        regime: regimeBoost,
        memory: memoryBoost.riskAdjustment
      }
    };
    
    return {
      asset,
      timeframe,
      timestamp: new Date(),
      scenario: 'LIVE_ANALYSIS',
      direction: memoryBoost.historicalBias,
      patternType: 'UNKNOWN',
      scoreBreakdown,
      memoryContext,
      executionPlan,
      learningWeights,
      regime: 'COMPRESSION' as MarketRegime,
      regimeConfidence: 0.8,
      pipelineStages: []
    };
  } catch (err) {
    console.error('[Explain] Live explain failed:', err);
    return null;
  }
}

/**
 * Fetch boost from module
 */
async function fetchModuleBoost(
  module: 'physics' | 'state',
  asset: string,
  timeframe: string
): Promise<{ boost: number; state: string }> {
  try {
    const endpoint = module === 'physics' 
      ? `http://localhost:8001/api/ta/physics/boost?asset=${asset}&tf=${timeframe}&direction=BULL`
      : `http://localhost:8001/api/ta/state/boost?asset=${asset}&tf=${timeframe}&direction=BULL`;
    
    const res = await fetch(endpoint);
    if (res.ok) {
      const data = await res.json() as any;
      return { boost: data.boost ?? 1, state: data.state ?? 'NEUTRAL' };
    }
  } catch {}
  return { boost: 1, state: 'NEUTRAL' };
}

// ═══════════════════════════════════════════════════════════════
// MAIN EXPLAIN FUNCTION
// ═══════════════════════════════════════════════════════════════

/**
 * Get decision explanation
 * First tries snapshot, then falls back to live computation
 */
export async function explainDecision(
  asset: string,
  timeframe: string
): Promise<DecisionExplainResult | null> {
  // Try to get from snapshot first
  const snapshot = await getDecisionSnapshot(asset, timeframe);
  
  if (snapshot) {
    // Fetch learning weights
    let learningWeights: LearningWeightMap;
    try {
      learningWeights = await getLearningWeightMap('COMPRESSION');
    } catch {
      learningWeights = {
        pattern: 1.0, liquidity: 1.0, graph: 1.0, fractal: 1.0,
        physics: 1.0, state: 1.0, regime: 1.0, scenario: 1.0
      };
    }
    
    return buildExplainFromSnapshot(snapshot, learningWeights);
  }
  
  // Fall back to live explain
  return buildLiveExplain(asset, timeframe);
}
