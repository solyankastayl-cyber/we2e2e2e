/**
 * Phase 6 — Scenario Generator
 * 
 * Generates candidate scenarios based on current market state
 */

import { v4 as uuidv4 } from 'uuid';
import {
  MarketScenario,
  MarketBehaviorState,
  ScenarioDirection,
  ScenarioSimulationInput,
  ScenarioTemplate,
  SCENARIO_TEMPLATES,
  STATE_TRANSITIONS,
  ScenarioEngineConfig,
  DEFAULT_SCENARIO_CONFIG
} from './scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// STATE MAPPING
// ═══════════════════════════════════════════════════════════════

/**
 * Map physics state to behavior state
 */
export function mapPhysicsToState(physicsState?: string): MarketBehaviorState {
  switch (physicsState) {
    case 'COMPRESSION':
      return 'COMPRESSION';
    case 'PRESSURE':
      return 'COMPRESSION';
    case 'RELEASE':
      return 'BREAKOUT';
    case 'EXPANSION':
      return 'EXPANSION';
    case 'EXHAUSTION':
      return 'EXHAUSTION';
    case 'NEUTRAL':
    default:
      return 'RANGE';
  }
}

/**
 * Determine current market behavior state from inputs
 */
export function determineCurrentState(input: ScenarioSimulationInput): MarketBehaviorState {
  // If explicit current state provided
  if (input.currentState) {
    return input.currentState;
  }
  
  // Derive from physics
  if (input.physicsState) {
    return mapPhysicsToState(input.physicsState);
  }
  
  // Derive from indicators
  if (input.atrRatio && input.atrRatio < 0.7) {
    return 'COMPRESSION';
  }
  
  if (input.releaseProbability && input.releaseProbability > 0.6) {
    return 'BREAKOUT';
  }
  
  if (input.exhaustionScore && input.exhaustionScore > 0.6) {
    return 'EXHAUSTION';
  }
  
  return 'RANGE';
}

// ═══════════════════════════════════════════════════════════════
// TRANSITION PROBABILITY
// ═══════════════════════════════════════════════════════════════

/**
 * Get transition probability with condition multipliers
 */
export function getTransitionProbability(
  from: MarketBehaviorState,
  to: MarketBehaviorState,
  input: ScenarioSimulationInput
): number {
  const transition = STATE_TRANSITIONS.find(t => t.from === from && t.to === to);
  
  if (!transition) {
    return 0.05; // Small base probability for undefined transitions
  }
  
  let probability = transition.baseProbability;
  
  // Apply condition multipliers
  if (transition.conditionMultipliers.highEnergy && input.energyScore && input.energyScore > 0.6) {
    probability *= transition.conditionMultipliers.highEnergy;
  }
  
  if (transition.conditionMultipliers.liquiditySweep && 
      (input.recentSweepUp || input.recentSweepDown)) {
    probability *= transition.conditionMultipliers.liquiditySweep;
  }
  
  if (transition.conditionMultipliers.trendAlignment && input.trendStrength) {
    if (input.trendStrength > 0.5) {
      probability *= transition.conditionMultipliers.trendAlignment;
    }
  }
  
  if (transition.conditionMultipliers.volumeSpike && input.volumeProfile && input.volumeProfile > 1.5) {
    probability *= transition.conditionMultipliers.volumeSpike;
  }
  
  return Math.min(1, probability);
}

// ═══════════════════════════════════════════════════════════════
// PATH PROBABILITY
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate cumulative probability for a state path
 */
export function calculatePathProbability(
  path: MarketBehaviorState[],
  input: ScenarioSimulationInput
): number {
  if (path.length < 2) return 1;
  
  let probability = 1;
  
  for (let i = 0; i < path.length - 1; i++) {
    const transitionProb = getTransitionProbability(path[i], path[i + 1], input);
    probability *= transitionProb;
  }
  
  return probability;
}

/**
 * Determine direction from path
 */
export function determinePathDirection(
  path: MarketBehaviorState[],
  input: ScenarioSimulationInput
): ScenarioDirection {
  // Count directional states
  const bullishStates = ['BREAKOUT', 'EXPANSION', 'CONTINUATION'];
  const bearishStates = ['REVERSAL'];
  const neutralStates = ['RANGE', 'COMPRESSION', 'FALSE_BREAKOUT'];
  
  let bullCount = 0;
  let bearCount = 0;
  
  for (const state of path) {
    if (bullishStates.includes(state)) bullCount++;
    if (bearishStates.includes(state)) bearCount++;
  }
  
  // Factor in trend direction
  if (input.trendDirection === 'BULL') bullCount += 0.5;
  if (input.trendDirection === 'BEAR') bearCount += 0.5;
  
  // Factor in liquidity sweeps (sweep opposite to trend = reversal)
  if (input.recentSweepDown && input.trendDirection !== 'BEAR') bullCount += 1;
  if (input.recentSweepUp && input.trendDirection !== 'BULL') bearCount += 1;
  
  if (bullCount > bearCount * 1.2) return 'BULL';
  if (bearCount > bullCount * 1.2) return 'BEAR';
  return 'NEUTRAL';
}

// ═══════════════════════════════════════════════════════════════
// SCENARIO GENERATION
// ═══════════════════════════════════════════════════════════════

/**
 * Generate scenarios from templates
 */
export function generateFromTemplates(
  input: ScenarioSimulationInput,
  config: ScenarioEngineConfig = DEFAULT_SCENARIO_CONFIG
): MarketScenario[] {
  const currentState = determineCurrentState(input);
  const scenarios: MarketScenario[] = [];
  
  for (const template of SCENARIO_TEMPLATES) {
    // Check if template starts from current or compatible state
    const startState = template.path[0];
    if (startState !== currentState && !isCompatibleState(currentState, startState)) {
      continue;
    }
    
    // Adjust path to start from current state
    const adjustedPath = startState === currentState 
      ? template.path 
      : [currentState, ...template.path];
    
    // Calculate probability
    let probability = template.baseProb * calculatePathProbability(adjustedPath, input);
    
    // Boost if direction aligns with trend
    if (template.direction === input.trendDirection) {
      probability *= 1.3;
    }
    
    // Boost if liquidity sweep matches reversal pattern
    if (template.name.includes('SWEEP_REVERSAL')) {
      if ((template.direction === 'BULL' && input.recentSweepDown) ||
          (template.direction === 'BEAR' && input.recentSweepUp)) {
        probability *= 1.5;
      }
    }
    
    if (probability < config.minScenarioProbability) continue;
    
    // Calculate expected move
    const expectedMoveATR = calculateExpectedMove(adjustedPath, template.direction, input);
    
    // Calculate confidence
    const confidence = calculateScenarioConfidence(adjustedPath, input);
    
    scenarios.push({
      scenarioId: `SCN_${uuidv4().slice(0, 8).toUpperCase()}`,
      asset: input.asset,
      timeframe: input.timeframe,
      direction: template.direction,
      probability,
      expectedMoveATR,
      path: adjustedPath,
      events: generateEvents(adjustedPath),
      states: adjustedPath,
      confidence,
      score: probability * expectedMoveATR * confidence,
      generatedAt: new Date(),
      expiresAt: new Date(Date.now() + config.scenarioExpiryBars * 4 * 60 * 60 * 1000) // 4h bars
    });
  }
  
  return scenarios;
}

/**
 * Generate dynamic scenarios by exploring state graph
 */
export function generateDynamicScenarios(
  input: ScenarioSimulationInput,
  config: ScenarioEngineConfig = DEFAULT_SCENARIO_CONFIG
): MarketScenario[] {
  const currentState = determineCurrentState(input);
  const scenarios: MarketScenario[] = [];
  
  // BFS through state graph
  interface PathNode {
    path: MarketBehaviorState[];
    probability: number;
  }
  
  const queue: PathNode[] = [{ path: [currentState], probability: 1 }];
  const visited = new Set<string>();
  
  while (queue.length > 0) {
    const node = queue.shift()!;
    const lastState = node.path[node.path.length - 1];
    
    // Check depth limit
    if (node.path.length >= config.maxPathDepth) {
      // Terminal - create scenario
      if (node.probability >= config.minScenarioProbability) {
        const direction = determinePathDirection(node.path, input);
        const expectedMoveATR = calculateExpectedMove(node.path, direction, input);
        const confidence = calculateScenarioConfidence(node.path, input);
        
        scenarios.push({
          scenarioId: `SCN_${uuidv4().slice(0, 8).toUpperCase()}`,
          asset: input.asset,
          timeframe: input.timeframe,
          direction,
          probability: node.probability,
          expectedMoveATR,
          path: node.path,
          events: generateEvents(node.path),
          states: node.path,
          confidence,
          score: node.probability * expectedMoveATR * confidence,
          generatedAt: new Date()
        });
      }
      continue;
    }
    
    // Get possible next states
    const transitions = STATE_TRANSITIONS.filter(t => t.from === lastState);
    
    for (const transition of transitions) {
      const newPath = [...node.path, transition.to];
      const pathKey = newPath.join('->');
      
      if (visited.has(pathKey)) continue;
      visited.add(pathKey);
      
      const transitionProb = getTransitionProbability(lastState, transition.to, input);
      const newProbability = node.probability * transitionProb;
      
      // Prune low probability paths
      if (newProbability < config.minScenarioProbability * 0.5) continue;
      
      queue.push({ path: newPath, probability: newProbability });
    }
  }
  
  return scenarios;
}

/**
 * Main scenario generation function
 */
export function generateScenarios(
  input: ScenarioSimulationInput,
  config: ScenarioEngineConfig = DEFAULT_SCENARIO_CONFIG
): MarketScenario[] {
  // Generate from templates
  const templateScenarios = generateFromTemplates(input, config);
  
  // Generate dynamic scenarios
  const dynamicScenarios = generateDynamicScenarios(input, config);
  
  // Merge and deduplicate
  const allScenarios = [...templateScenarios, ...dynamicScenarios];
  const uniqueScenarios = deduplicateScenarios(allScenarios);
  
  // Sort by score
  uniqueScenarios.sort((a, b) => b.score - a.score);
  
  // Return top N
  return uniqueScenarios.slice(0, config.topScenariosCount * 2);
}

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function isCompatibleState(current: MarketBehaviorState, target: MarketBehaviorState): boolean {
  const compatibilityMap: Record<MarketBehaviorState, MarketBehaviorState[]> = {
    'COMPRESSION': ['RANGE'],
    'BREAKOUT': ['EXPANSION'],
    'FALSE_BREAKOUT': ['RANGE'],
    'RETEST': ['COMPRESSION'],
    'EXPANSION': ['CONTINUATION'],
    'LIQUIDITY_SWEEP': ['REVERSAL', 'FALSE_BREAKOUT'],
    'REVERSAL': ['EXHAUSTION'],
    'RANGE': ['COMPRESSION'],
    'EXHAUSTION': ['REVERSAL'],
    'CONTINUATION': ['EXPANSION']
  };
  
  return compatibilityMap[current]?.includes(target) || false;
}

function calculateExpectedMove(
  path: MarketBehaviorState[],
  direction: ScenarioDirection,
  input: ScenarioSimulationInput
): number {
  let moveATR = 0.5; // Base move
  
  for (const state of path) {
    switch (state) {
      case 'EXPANSION':
        moveATR += 1.5;
        break;
      case 'BREAKOUT':
        moveATR += 1.0;
        break;
      case 'CONTINUATION':
        moveATR += 0.8;
        break;
      case 'REVERSAL':
        moveATR += 1.2;
        break;
      case 'RETEST':
        moveATR += 0.3;
        break;
    }
  }
  
  // Adjust for energy
  if (input.energyScore && input.energyScore > 0.6) {
    moveATR *= (1 + (input.energyScore - 0.5));
  }
  
  // Neutral scenarios have smaller expected moves
  if (direction === 'NEUTRAL') {
    moveATR *= 0.3;
  }
  
  return Math.min(5, moveATR);
}

function calculateScenarioConfidence(
  path: MarketBehaviorState[],
  input: ScenarioSimulationInput
): number {
  let confidence = 0.5;
  
  // Shorter paths = higher confidence
  confidence += (5 - path.length) * 0.05;
  
  // Energy alignment
  if (input.energyScore) {
    confidence += input.energyScore * 0.2;
  }
  
  // Trend alignment
  if (input.trendStrength) {
    confidence += input.trendStrength * 0.15;
  }
  
  // Release probability
  if (input.releaseProbability && path.includes('BREAKOUT')) {
    confidence += input.releaseProbability * 0.15;
  }
  
  return Math.min(1, Math.max(0.2, confidence));
}

function generateEvents(path: MarketBehaviorState[]): string[] {
  const events: string[] = [];
  
  for (let i = 0; i < path.length - 1; i++) {
    const from = path[i];
    const to = path[i + 1];
    events.push(`${from} -> ${to}`);
  }
  
  return events;
}

function deduplicateScenarios(scenarios: MarketScenario[]): MarketScenario[] {
  const seen = new Map<string, MarketScenario>();
  
  for (const scenario of scenarios) {
    const key = scenario.path.join('->') + '_' + scenario.direction;
    const existing = seen.get(key);
    
    if (!existing || scenario.score > existing.score) {
      seen.set(key, scenario);
    }
  }
  
  return Array.from(seen.values());
}
