/**
 * P1.6 + P5.0.9 + D3/D4 — Unified Decision Engine with Edge Attribution & Market Dynamics
 * 
 * Single pipeline for both API and simulation:
 * patterns → geometry → gates → graph → regime → physics → state → ML → EV → EDGE → ranking
 * 
 * D3: Market Physics Engine - energy/compression/pressure boost
 * D4: State Transition Engine - state-based boost
 * P5.0.9: Edge Multiplier Integration
 */

import { Db } from 'mongodb';
import { computeGeometryForScenario, computeGeometryBoost, extractGeometryFeatures } from '../geometry/geometry.engine.js';
import { GeometryInput, GeometryPack } from '../geometry/geometry.types.js';
import { isTradeableScenario } from '../gates/tradeability.gate.js';
import { GateInput, TradeabilityResult, DEFAULT_GATE_CONFIG } from '../gates/tradeability.types.js';
import { createGraphBoostService, BoostParams } from '../graph/graph.service.js';
import { GraphBoostResult, DEFAULT_GRAPH_CONFIG } from '../graph/graph.types.js';
import { extractGraphFeatures } from '../graph/graph.integration.js';
import { detectRegime, calculateRegimeFeatures, MarketRegime, RegimeDetectionResult } from '../ml_v4/regime_mixture.js';
import { createEVPredictor, EVPredictor } from '../ml_v4/ev_predictor.js';
import { EVPrediction } from '../ml_v4/labels_v4.types.js';

// P5.0.9: Edge Multiplier
import { 
  getEdgeMultiplierService, 
  EdgeMultiplierService, 
  EdgeMultiplierResult 
} from '../../edge/edge.multiplier.service.js';

// Phase 11.1: MetaBrain Learning Layer
import { 
  getLearningWeightMap, 
  LearningWeightMap,
  applyLearningWeights 
} from '../../metabrain_learning/learning.integration.js';

// P0: Memory Boost Integration
import {
  fetchMemoryBoost,
  DecisionMemoryBoost,
  getDirectionBoost,
  getScenarioBoost,
  MemoryIntegrationResult
} from './decision.memory.js';

// Phase 8.6: Calibration Filters
import {
  applyCalibrationFilters,
  CalibrationFilterResult,
  DEFAULT_CALIBRATION_FILTER_CONFIG,
  CandleWithVolume,
} from '../calibration_filters/index.js';

// Phase 6.5: MTF Confirmation Layer
import { 
  quickMTFBoost, 
  MTFExplain,
  DEFAULT_MTF_CONFIG 
} from '../../mtf_v2/index.js';

// D3: Market Physics Boost
interface PhysicsBoostData {
  boost: number;
  state: string;
  reason: string;
}

// D4: State Boost
interface StateBoostData {
  boost: number;
  state: string;
  reason: string;
}

async function fetchPhysicsBoost(asset: string, timeframe: string, direction: string): Promise<PhysicsBoostData> {
  try {
    const resp = await fetch(`http://localhost:8001/api/ta/physics/boost?asset=${asset}&tf=${timeframe}&direction=${direction}`);
    if (resp.ok) {
      const data = await resp.json() as any;
      return { boost: data.boost ?? 1, state: data.state ?? 'NEUTRAL', reason: data.reason ?? '' };
    }
  } catch {}
  return { boost: 1, state: 'NEUTRAL', reason: 'unavailable' };
}

async function fetchStateBoost(asset: string, timeframe: string, direction: string): Promise<StateBoostData> {
  try {
    const resp = await fetch(`http://localhost:8001/api/ta/state/boost?asset=${asset}&tf=${timeframe}&direction=${direction}`);
    if (resp.ok) {
      const data = await resp.json() as any;
      return { boost: data.boost ?? 1, state: data.state ?? 'BALANCE', reason: data.reason ?? '' };
    }
  } catch {}
  return { boost: 1, state: 'BALANCE', reason: 'unavailable' };
}

export interface DecisionContext {
  asset: string;
  timeframe: string;
  timestamp: Date;
  
  // Market data
  candles: CandleData[];
  currentPrice: number;
  atr: number;
  
  // Detected patterns/scenarios
  scenarios: ScenarioInput[];
  
  // Optional: recent patterns for graph boost
  recentPatterns?: Array<{ type: string; direction: string; barsAgo: number }>;
}

export interface CandleData {
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ScenarioInput {
  scenarioId: string;
  patternType: string;
  direction: 'LONG' | 'SHORT';
  
  // Trade plan
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  
  // Pattern data
  score: number;
  confidence: number;
  touches?: number;
  
  // Pivot points for geometry
  pivotHighs?: number[];
  pivotLows?: number[];
  pivotHighIdxs?: number[];
  pivotLowIdxs?: number[];
  startIdx?: number;
  endIdx?: number;
  
  // Pre-computed (optional)
  lineHigh?: { slope: number; intercept: number };
  lineLow?: { slope: number; intercept: number };
  
  // Harmonic points (if applicable)
  pointX?: number;
  pointA?: number;
  pointB?: number;
  pointC?: number;
  pointD?: number;
}

export interface ProcessedScenario {
  scenarioId: string;
  patternType: string;
  direction: 'LONG' | 'SHORT';
  
  // Trade plan
  entry: number;
  stop: number;
  target1: number;
  target2?: number;
  riskReward: number;
  
  // Pipeline results
  geometry: GeometryPack;
  geometryBoost: number;
  
  gate: TradeabilityResult;
  gateScore: number;
  
  graphBoost: GraphBoostResult;
  graphBoostFactor: number;
  
  // D3: Market Physics
  physicsBoost: number;
  physicsState: string;
  
  // D4: State Transition
  stateBoost: number;
  marketState: string;
  
  regime: MarketRegime;
  regimeConfidence: number;
  
  // ML predictions
  mlPrediction: EVPrediction;
  pEntry: number;
  rExpected: number;
  
  // P5.0.9: Edge Attribution
  edge: EdgeInfo;
  
  // Phase 11.1: Learning weights applied
  learningWeights?: LearningWeightMap;
  
  // P0: Memory Boost Integration
  memory?: {
    confidence: number;
    matchCount: number;
    directionBoost: number;
    scenarioBoost: number;
    riskAdjustment: number;
    historicalBias: 'BULL' | 'BEAR' | 'NEUTRAL';
  };
  
  // Phase 6.5: MTF Confirmation Layer
  mtf?: {
    mtfBoost: number;
    mtfExecutionAdjustment: number;
    higherBias: string;
    lowerMomentum: string;
    regimeAligned: boolean;
    structureAligned: boolean;
    scenarioAligned: boolean;
    momentumAligned: boolean;
  };
  
  // Phase 8.6: Calibration Filters
  calibration?: {
    passed: boolean;
    score: number;
    volatilityPassed: boolean;
    trendAlignmentPassed: boolean;
    volumeBreakoutPassed: boolean;
    strategyEnabled: boolean;
    adjustedStopLoss: number;
    adjustedTakeProfit: number;
    adjustedRiskReward: number;
    rejectionReasons: string[];
  };
  
  // Final scores
  evBeforeML: number;
  evAfterML: number;
  evAfterEdge: number;  // P5.0.9: EV after edge multiplier
  finalScore: number;
  
  // Features for dataset
  features: Record<string, number>;
}

// P5.0.9: Edge info for debugging
export interface EdgeInfo {
  enabled: boolean;
  edgeRunId?: string;
  source?: string;
  dimension?: string;
  key?: string;
  n?: number;
  edgeScore?: number;
  multiplier: number;
  clamped: boolean;
  reason?: string;
}

export interface DecisionPack {
  asset: string;
  timeframe: string;
  timestamp: Date;
  
  // All processed scenarios
  scenarios: ProcessedScenario[];
  
  // Top scenario
  topScenario: ProcessedScenario | null;
  
  // Meta
  regime: MarketRegime;
  regimeConfidence: number;
  overlayStage: string;
  modelId: string;
  
  // P0: Memory context (for Digital Twin)
  memoryContext?: {
    confidence: number;
    matches: number;
    bias: 'BULL' | 'BEAR' | 'NEUTRAL';
  };
  
  // Phase 6.5: MTF context
  mtfContext?: {
    higherTf: string;
    lowerTf: string;
    mtfBoost: number;
  };
  
  // Stats
  totalScenarios: number;
  passedGate: number;
  rejected: number;
}

export interface DecisionEngine {
  computeDecision(ctx: DecisionContext): Promise<DecisionPack>;
}

/**
 * Create unified decision engine with Edge Attribution (P5.0.9) + Learning Weights (P11.1)
 */
export function createDecisionEngine(db: Db): DecisionEngine {
  const graphBoostService = createGraphBoostService(db, DEFAULT_GRAPH_CONFIG);
  const evPredictor = createEVPredictor(db);
  // P5.0.9: Edge Multiplier Service
  const edgeMultiplierService = getEdgeMultiplierService(db);

  return {
    async computeDecision(ctx: DecisionContext): Promise<DecisionPack> {
      const { asset, timeframe, timestamp, scenarios, currentPrice, atr, candles, recentPatterns } = ctx;
      
      // 1. Detect market regime
      const closes = candles.map(c => c.close);
      const highs = candles.map(c => c.high);
      const lows = candles.map(c => c.low);
      
      const regimeFeatures = calculateRegimeFeatures(closes, highs, lows, atr);
      const regimeResult = detectRegime(regimeFeatures);
      const regime = regimeResult.regime;
      const regimeConfidence = regimeResult.confidence;

      // Phase 11.1: Fetch learning weights (regime-aware)
      let learningWeights: LearningWeightMap;
      try {
        learningWeights = await getLearningWeightMap(regime);
      } catch {
        // Fallback to default weights
        learningWeights = {
          pattern: 1.0, liquidity: 1.0, graph: 1.0, fractal: 1.0,
          physics: 1.0, state: 1.0, regime: 1.0, scenario: 1.0
        };
      }

      // P0: Fetch memory boost
      let memoryBoost: DecisionMemoryBoost;
      try {
        memoryBoost = await fetchMemoryBoost(asset, timeframe);
      } catch {
        // Fallback to neutral (no effect)
        memoryBoost = {
          memoryConfidence: 0,
          bullishBoost: 1,
          bearishBoost: 1,
          neutralBoost: 1,
          scenarioBoost: {},
          riskAdjustment: 1,
          matchCount: 0,
          dominantOutcome: 'NEUTRAL',
          historicalBias: 'NEUTRAL'
        };
      }

      const processedScenarios: ProcessedScenario[] = [];
      let passedGate = 0;
      let rejected = 0;

      for (const scenario of scenarios) {
        // 2. Compute geometry
        const geomInput: GeometryInput = {
          patternType: scenario.patternType,
          timeframe,
          direction: scenario.direction,
          pivotHighs: scenario.pivotHighs || [],
          pivotLows: scenario.pivotLows || [],
          pivotHighIdxs: scenario.pivotHighIdxs || [],
          pivotLowIdxs: scenario.pivotLowIdxs || [],
          atr,
          price: currentPrice,
          startIdx: scenario.startIdx || 0,
          endIdx: scenario.endIdx || 100,
          lineHigh: scenario.lineHigh,
          lineLow: scenario.lineLow,
          pointX: scenario.pointX,
          pointA: scenario.pointA,
          pointB: scenario.pointB,
          pointC: scenario.pointC,
          pointD: scenario.pointD,
        };
        
        const geometry = computeGeometryForScenario(geomInput);
        const geometryBoost = computeGeometryBoost(geometry);
        const geomFeatures = extractGeometryFeatures(geometry);

        // 3. Check tradeability gate
        const gateInput: GateInput = {
          entry: scenario.entry,
          stop: scenario.stop,
          target1: scenario.target1,
          target2: scenario.target2,
          direction: scenario.direction,
          patternType: scenario.patternType,
          touches: scenario.touches,
          price: currentPrice,
          atr,
        };
        
        const gate = isTradeableScenario(gateInput, DEFAULT_GATE_CONFIG);
        
        if (!gate.ok) {
          rejected++;
          continue;  // Skip non-tradeable scenarios
        }
        passedGate++;

        // 3.5 Phase 8.6: Apply Calibration Filters
        const candlesWithVolume: CandleWithVolume[] = candles.map(c => ({
          openTime: c.openTime,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        }));
        
        const calibrationResult = applyCalibrationFilters({
          candles: candlesWithVolume,
          direction: scenario.direction,
          patternType: scenario.patternType,
          entry: scenario.entry,
          atr,
        }, DEFAULT_CALIBRATION_FILTER_CONFIG);
        
        // If calibration filter fails, reject the scenario
        if (!calibrationResult.passed) {
          rejected++;
          continue;  // Skip scenarios that don't pass calibration filters
        }

        // 4. Compute graph boost
        const boostParams: BoostParams = {
          patternType: scenario.patternType,
          direction: scenario.direction,
          timeframe,
          recentEvents: recentPatterns || [],
        };
        
        const graphBoost = await graphBoostService.computeBoost(boostParams);
        const graphFeatures = extractGraphFeatures(graphBoost);

        // 4b. Fetch D3 Physics Boost & D4 State Boost
        const physicsDir = scenario.direction === 'LONG' ? 'BULL' : 'BEAR';
        const [physicsBoostData, stateBoostData] = await Promise.all([
          fetchPhysicsBoost(asset, timeframe, physicsDir),
          fetchStateBoost(asset, timeframe, physicsDir),
        ]);

        // 5. Calculate risk/reward
        const risk = Math.abs(scenario.entry - scenario.stop);
        const reward = Math.abs(scenario.target1 - scenario.entry);
        const riskReward = risk > 0 ? reward / risk : 0;

        // 6. Build features for ML
        const features: Record<string, number> = {
          // Base
          score: scenario.score,
          confidence: scenario.confidence,
          risk_reward: riskReward,
          gate_score: gate.gateScore,
          
          // Geometry
          ...geomFeatures,
          
          // Graph
          ...graphFeatures,
          
          // Regime
          regime_trend_up: regime === 'TREND_UP' ? 1 : 0,
          regime_trend_down: regime === 'TREND_DOWN' ? 1 : 0,
          regime_range: regime === 'RANGE' ? 1 : 0,
          
          // D3: Physics
          physics_boost: physicsBoostData.boost,
          
          // D4: State
          state_boost: stateBoostData.boost,
        };

        // 7. ML prediction
        const mlPrediction = evPredictor.predict(features, regime);
        
        // 8. Calculate EV before Edge
        // EV = base score × geometry × graph × physics × state
        // Phase 11.1: Apply learning weights to each boost
        const adjustedBoosts = applyLearningWeights(
          {
            patternBoost: scenario.score,
            graphBoost: graphBoost.graphBoostFactor,
            physicsBoost: physicsBoostData.boost,
            stateBoost: stateBoostData.boost
          },
          learningWeights
        );
        
        const evBeforeML = adjustedBoosts.patternBoost * 
          (1 + geometryBoost) * 
          adjustedBoosts.graphBoost * 
          adjustedBoosts.physicsBoost * 
          adjustedBoosts.stateBoost;
        
        // EV after ML = blend of base EV and ML prediction
        const alpha = 0.15;  // LIVE_LITE stage
        const evAfterML = evBeforeML + alpha * (mlPrediction.ev - evBeforeML);
        
        // 9. P5.0.9: Apply Edge Multiplier
        const edgeResult = await edgeMultiplierService.getMultiplier(scenario.patternType, regime);
        
        // Apply edge multiplier to EV
        const evAfterEdge = evAfterML * edgeResult.multiplier;
        
        // 10. P0: Apply Memory Boost
        // Get direction and scenario boosts from memory (clamped 0.85-1.20)
        const directionBoost = getDirectionBoost(scenario.direction, memoryBoost);
        const scenarioMemoryBoost = getScenarioBoost(scenario.scenarioId, memoryBoost);
        
        // 11. Phase 6.5: Apply MTF Boost
        // Quick MTF check using higher TF regime/bias and lower TF momentum
        // In real implementation, would fetch actual MTF context
        const higherBias = regime === 'TREND_UP' ? 'BULL' : 
                          regime === 'TREND_DOWN' ? 'BEAR' : 'NEUTRAL';
        const higherStructure = higherBias === 'BULL' ? 'BULLISH' : 
                               higherBias === 'BEAR' ? 'BEARISH' : 'NEUTRAL';
        const lowerMomentum = higherBias;  // Simplified - assume momentum follows regime
        
        const mtfBoostValue = quickMTFBoost(
          higherBias as 'BULL' | 'BEAR' | 'NEUTRAL',
          regime,
          higherStructure,
          lowerMomentum as 'BULL' | 'BEAR' | 'NEUTRAL',
          scenario.direction
        );
        
        // MTF Execution Adjustment (for position sizing)
        const regimeAligned = 
          (scenario.direction === 'LONG' && regime === 'TREND_UP') ||
          (scenario.direction === 'SHORT' && regime === 'TREND_DOWN');
        const structureAligned = 
          (scenario.direction === 'LONG' && higherStructure === 'BULLISH') ||
          (scenario.direction === 'SHORT' && higherStructure === 'BEARISH');
        const scenarioAligned = true;  // Simplified
        const momentumAligned = 
          (scenario.direction === 'LONG' && lowerMomentum === 'BULL') ||
          (scenario.direction === 'SHORT' && lowerMomentum === 'BEAR');
        
        const alignmentCount = [regimeAligned, structureAligned, scenarioAligned, momentumAligned]
          .filter(Boolean).length;
        const higherConflict = 
          (scenario.direction === 'LONG' && higherBias === 'BEAR') ||
          (scenario.direction === 'SHORT' && higherBias === 'BULL');
        
        const mtfExecutionAdjustment = higherConflict ? 0.85 :
          alignmentCount >= 3 ? 1.00 : 0.92;
        
        // Build MTF info
        const mtfInfo = {
          mtfBoost: mtfBoostValue,
          mtfExecutionAdjustment,
          higherBias,
          lowerMomentum,
          regimeAligned,
          structureAligned,
          scenarioAligned,
          momentumAligned
        };
        
        // Final score formula:
        // finalScore = evAfterEdge × directionBoost × scenarioBoost × mtfBoost
        const finalScore = evAfterEdge * directionBoost * scenarioMemoryBoost * mtfBoostValue;
        
        // Build memory info for output
        const memoryInfo = {
          confidence: memoryBoost.memoryConfidence,
          matchCount: memoryBoost.matchCount,
          directionBoost,
          scenarioBoost: scenarioMemoryBoost,
          riskAdjustment: memoryBoost.riskAdjustment,
          historicalBias: memoryBoost.historicalBias
        };
        
        // Build edge info for output
        const edgeInfo: EdgeInfo = {
          enabled: edgeResult.enabled,
          multiplier: edgeResult.multiplier,
          clamped: edgeResult.clamped,
          reason: edgeResult.reason,
        };
        
        if (edgeResult.meta) {
          edgeInfo.edgeRunId = edgeResult.meta.edgeRunId;
          edgeInfo.source = edgeResult.meta.source;
          edgeInfo.dimension = edgeResult.meta.dimension;
          edgeInfo.key = edgeResult.meta.key;
          edgeInfo.n = edgeResult.meta.n;
          edgeInfo.edgeScore = edgeResult.meta.edgeScore;
        }
        
        processedScenarios.push({
          scenarioId: scenario.scenarioId,
          patternType: scenario.patternType,
          direction: scenario.direction,
          entry: scenario.entry,
          stop: scenario.stop,
          target1: scenario.target1,
          target2: scenario.target2,
          riskReward,
          geometry,
          geometryBoost,
          gate,
          gateScore: gate.gateScore,
          graphBoost,
          graphBoostFactor: graphBoost.graphBoostFactor,
          physicsBoost: physicsBoostData.boost,
          physicsState: physicsBoostData.state,
          stateBoost: stateBoostData.boost,
          marketState: stateBoostData.state,
          regime,
          regimeConfidence,
          mlPrediction,
          pEntry: mlPrediction.pEntry,
          rExpected: mlPrediction.rExpected,
          edge: edgeInfo,  // P5.0.9
          learningWeights,  // Phase 11.1
          memory: memoryInfo,  // P0: Memory Boost
          mtf: mtfInfo,  // Phase 6.5: MTF Confirmation Layer
          calibration: {  // Phase 8.6: Calibration Filters
            passed: calibrationResult.passed,
            score: calibrationResult.score,
            volatilityPassed: calibrationResult.volatilityPassed,
            trendAlignmentPassed: calibrationResult.trendAlignmentPassed,
            volumeBreakoutPassed: calibrationResult.volumeBreakoutPassed,
            strategyEnabled: calibrationResult.strategyEnabled,
            adjustedStopLoss: calibrationResult.adjustedLevels.stopLoss,
            adjustedTakeProfit: calibrationResult.adjustedLevels.takeProfit,
            adjustedRiskReward: calibrationResult.adjustedLevels.riskReward,
            rejectionReasons: calibrationResult.rejectionReasons,
          },
          evBeforeML,
          evAfterML,
          evAfterEdge,  // P5.0.9
          finalScore,  // Now includes memory boost + MTF boost
          features,
        });
      }

      // 11. Rank by final score (EV after Edge + Memory)
      processedScenarios.sort((a, b) => b.finalScore - a.finalScore);
      
      const topScenario = processedScenarios.length > 0 ? processedScenarios[0] : null;

      // P0: Build memory context for Digital Twin
      const memoryContext = {
        confidence: memoryBoost.memoryConfidence,
        matches: memoryBoost.matchCount,
        bias: memoryBoost.historicalBias
      };

      return {
        asset,
        timeframe,
        timestamp,
        scenarios: processedScenarios,
        topScenario,
        regime,
        regimeConfidence,
        overlayStage: 'LIVE_LITE',
        modelId: 'mock_v1',
        memoryContext,  // P0: For Digital Twin
        totalScenarios: scenarios.length,
        passedGate,
        rejected,
      };
    },
  };
}
