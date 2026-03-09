/**
 * Phase 8.6 — GraphBoost Integration
 * 
 * Integrates GraphBoost into the decision/scenario pipeline
 */

import { Db } from 'mongodb';
import { createGraphBoostService, BoostParams } from './graph.service.js';
import { GraphBoostResult, GraphConfig, DEFAULT_GRAPH_CONFIG } from './graph.types.js';

export interface ScenarioWithBoost {
  scenarioId: string;
  patternType: string;
  direction: string;
  timeframe: string;
  baseScore: number;
  boostedScore: number;
  graphBoost: GraphBoostResult;
}

export interface DecisionPack {
  asset: string;
  timeframe: string;
  timestamp: Date;
  scenarios: ScenarioWithBoost[];
  topScenario: ScenarioWithBoost | null;
  graphEnabled: boolean;
}

/**
 * Apply GraphBoost to a list of scenarios
 */
export async function applyGraphBoostToScenarios(
  db: Db,
  scenarios: Array<{
    scenarioId: string;
    patternType: string;
    direction: string;
    timeframe: string;
    score: number;
    recentPatterns?: Array<{ type: string; direction: string; barsAgo: number }>;
  }>,
  config: GraphConfig = DEFAULT_GRAPH_CONFIG
): Promise<ScenarioWithBoost[]> {
  if (!config.enabled) {
    return scenarios.map(s => ({
      scenarioId: s.scenarioId,
      patternType: s.patternType,
      direction: s.direction,
      timeframe: s.timeframe,
      baseScore: s.score,
      boostedScore: s.score,
      graphBoost: {
        graphBoostFactor: 1,
        graphReasons: [],
        supportingEdges: 0,
        confidence: 0,
      },
    }));
  }

  const boostService = createGraphBoostService(db, config);
  const results: ScenarioWithBoost[] = [];

  for (const scenario of scenarios) {
    const boostParams: BoostParams = {
      patternType: scenario.patternType,
      direction: scenario.direction,
      timeframe: scenario.timeframe,
      recentEvents: scenario.recentPatterns || [],
    };

    const boost = await boostService.computeBoost(boostParams);
    const boostedScore = scenario.score * boost.graphBoostFactor;

    results.push({
      scenarioId: scenario.scenarioId,
      patternType: scenario.patternType,
      direction: scenario.direction,
      timeframe: scenario.timeframe,
      baseScore: scenario.score,
      boostedScore,
      graphBoost: boost,
    });
  }

  // Sort by boosted score
  results.sort((a, b) => b.boostedScore - a.boostedScore);

  return results;
}

/**
 * Create decision pack with GraphBoost
 */
export async function createDecisionPackWithBoost(
  db: Db,
  asset: string,
  timeframe: string,
  scenarios: Array<{
    scenarioId: string;
    patternType: string;
    direction: string;
    score: number;
    recentPatterns?: Array<{ type: string; direction: string; barsAgo: number }>;
  }>,
  config: GraphConfig = DEFAULT_GRAPH_CONFIG
): Promise<DecisionPack> {
  const scenariosWithTf = scenarios.map(s => ({ ...s, timeframe }));
  const boostedScenarios = await applyGraphBoostToScenarios(db, scenariosWithTf, config);

  return {
    asset,
    timeframe,
    timestamp: new Date(),
    scenarios: boostedScenarios,
    topScenario: boostedScenarios.length > 0 ? boostedScenarios[0] : null,
    graphEnabled: config.enabled,
  };
}

/**
 * Add graph features to ML dataset row
 */
export function extractGraphFeatures(boost: GraphBoostResult): Record<string, number> {
  return {
    graph_boost_factor: boost.graphBoostFactor,
    graph_confidence: boost.confidence,
    graph_supporting_edges: boost.supportingEdges,
    graph_top_lift: boost.graphReasons.length > 0 ? boost.graphReasons[0].lift : 0,
    graph_avg_lift: boost.graphReasons.length > 0 
      ? boost.graphReasons.reduce((sum, r) => sum + r.lift, 0) / boost.graphReasons.length 
      : 0,
  };
}

/**
 * Calculate expected value using GraphBoost
 * 
 * EV = P(win) * reward - P(loss) * risk
 * where P(win) is adjusted by graphBoostFactor
 */
export function calculateBoostedEV(
  baseWinProbability: number,
  graphBoostFactor: number,
  riskRewardRatio: number
): { boostedProbability: number; expectedValue: number } {
  // Clamp boost factor
  const clampedBoost = Math.max(0.8, Math.min(1.25, graphBoostFactor));
  
  // Apply boost to base probability
  // Using logit transform to keep probability in valid range
  const logitBase = Math.log(baseWinProbability / (1 - baseWinProbability));
  const logitBoosted = logitBase + Math.log(clampedBoost);
  const boostedProbability = 1 / (1 + Math.exp(-logitBoosted));
  
  // Calculate EV
  // Assuming risk = 1, reward = riskRewardRatio
  const expectedValue = boostedProbability * riskRewardRatio - (1 - boostedProbability) * 1;
  
  return { boostedProbability, expectedValue };
}
