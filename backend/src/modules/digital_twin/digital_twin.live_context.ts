/**
 * Digital Twin — Live Context Provider
 * 
 * Fetches real data from all modules to build live TwinContext
 */

import { TwinContext, LiquidityStateType } from './digital_twin.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';
import { PhysicsState } from '../market_physics/physics.types.js';
import { MarketBehaviorState, ScenarioDirection } from '../scenario_engine/scenario.types.js';

// ═══════════════════════════════════════════════════════════════
// MODULE FETCHERS
// ═══════════════════════════════════════════════════════════════

const BASE_URL = 'http://localhost:3001/api/ta';

interface FetchResult<T> {
  success: boolean;
  data?: T;
  error?: string;
}

async function fetchWithTimeout<T>(url: string, timeout = 3000): Promise<FetchResult<T>> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    const resp = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);
    
    if (!resp.ok) {
      return { success: false, error: `HTTP ${resp.status}` };
    }
    
    const data = await resp.json() as T;
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : 'unknown' };
  }
}

/**
 * Fetch Regime data
 */
async function fetchRegimeData(asset: string, timeframe: string): Promise<TwinContext['regime'] | undefined> {
  const result = await fetchWithTimeout<{
    regime: MarketRegime;
    confidence: number;
    probabilities?: Record<MarketRegime, number>;
  }>(`${BASE_URL}/regime/detect?asset=${asset}&tf=${timeframe}`);
  
  if (!result.success || !result.data) return undefined;
  
  return {
    regime: result.data.regime,
    confidence: result.data.confidence,
    probabilities: result.data.probabilities
  };
}

/**
 * Fetch State data
 */
async function fetchStateData(asset: string, timeframe: string): Promise<TwinContext['state'] | undefined> {
  const result = await fetchWithTimeout<{
    state: MarketStateNode;
    confidence: number;
    boost: number;
    transitions?: Array<{ state: MarketStateNode; probability: number }>;
  }>(`${BASE_URL}/state/current?asset=${asset}&tf=${timeframe}`);
  
  if (!result.success || !result.data) return undefined;
  
  return {
    currentState: result.data.state,
    stateConfidence: result.data.confidence,
    stateBoost: result.data.boost,
    nextStateProbabilities: result.data.transitions
  };
}

/**
 * Fetch Physics data
 */
async function fetchPhysicsData(asset: string, timeframe: string): Promise<TwinContext['physics'] | undefined> {
  const result = await fetchWithTimeout<{
    state: PhysicsState;
    energy: number;
    compression: number;
    releaseProbability: number;
    exhaustion: number;
    boost: number;
  }>(`${BASE_URL}/physics/state?asset=${asset}&tf=${timeframe}`);
  
  if (!result.success || !result.data) return undefined;
  
  return {
    physicsState: result.data.state,
    energyScore: result.data.energy,
    compressionScore: result.data.compression,
    releaseProbability: result.data.releaseProbability,
    exhaustionScore: result.data.exhaustion,
    physicsBoost: result.data.boost
  };
}

/**
 * Fetch Liquidity data
 */
async function fetchLiquidityData(asset: string, timeframe: string): Promise<TwinContext['liquidity'] | undefined> {
  const result = await fetchWithTimeout<{
    bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    recentSweepUp: boolean;
    recentSweepDown: boolean;
    zonesAbove: number;
    zonesBelow: number;
  }>(`${BASE_URL}/liquidity/analyze?asset=${asset}&tf=${timeframe}`);
  
  if (!result.success || !result.data) return undefined;
  
  return {
    liquidityBias: result.data.bias,
    recentSweepUp: result.data.recentSweepUp,
    recentSweepDown: result.data.recentSweepDown,
    zonesAbove: result.data.zonesAbove,
    zonesBelow: result.data.zonesBelow
  };
}

/**
 * Fetch Scenario data
 */
async function fetchScenarioData(asset: string, timeframe: string): Promise<TwinContext['scenarios'] | undefined> {
  const result = await fetchWithTimeout<{
    scenarios: Array<{
      scenarioId: string;
      direction: ScenarioDirection;
      probability: number;
      confidence: number;
      path: MarketBehaviorState[];
      expectedMoveATR: number;
    }>;
  }>(`${BASE_URL}/scenarios/top?asset=${asset}&tf=${timeframe}&limit=5`);
  
  if (!result.success || !result.data) return undefined;
  
  return result.data.scenarios;
}

/**
 * Fetch MetaBrain data
 */
async function fetchMetaBrainData(asset: string, timeframe: string): Promise<TwinContext['metabrain'] | undefined> {
  const result = await fetchWithTimeout<{
    riskMode: 'CONSERVATIVE' | 'NORMAL' | 'AGGRESSIVE';
    confidenceThreshold: number;
    metaRiskMultiplier: number;
  }>(`${BASE_URL}/metabrain/status?asset=${asset}&tf=${timeframe}`);
  
  if (!result.success || !result.data) return undefined;
  
  return {
    riskMode: result.data.riskMode,
    confidenceThreshold: result.data.confidenceThreshold,
    metaRiskMultiplier: result.data.metaRiskMultiplier
  };
}

/**
 * Fetch Execution data
 */
async function fetchExecutionData(asset: string, timeframe: string): Promise<TwinContext['execution'] | undefined> {
  const result = await fetchWithTimeout<{
    portfolioExposure: number;
    openPositions: number;
    portfolioStress: number;
  }>(`${BASE_URL}/execution/status?asset=${asset}&tf=${timeframe}`);
  
  if (!result.success || !result.data) return undefined;
  
  return {
    portfolioExposure: result.data.portfolioExposure,
    openPositions: result.data.openPositions,
    portfolioStress: result.data.portfolioStress
  };
}

// ═══════════════════════════════════════════════════════════════
// MAIN LIVE CONTEXT BUILDER
// ═══════════════════════════════════════════════════════════════

export interface LiveContextOptions {
  timeout?: number;
  skipModules?: Array<'regime' | 'state' | 'physics' | 'liquidity' | 'scenarios' | 'metabrain' | 'execution'>;
  fallbackToMock?: boolean;
}

/**
 * Build live TwinContext from all modules
 */
export async function buildLiveTwinContext(
  asset: string,
  timeframe: string,
  options: LiveContextOptions = {}
): Promise<TwinContext> {
  const skip = new Set(options.skipModules || []);
  
  // Fetch all modules in parallel
  const [
    regimeData,
    stateData,
    physicsData,
    liquidityData,
    scenarioData,
    metabrainData,
    executionData
  ] = await Promise.all([
    skip.has('regime') ? undefined : fetchRegimeData(asset, timeframe),
    skip.has('state') ? undefined : fetchStateData(asset, timeframe),
    skip.has('physics') ? undefined : fetchPhysicsData(asset, timeframe),
    skip.has('liquidity') ? undefined : fetchLiquidityData(asset, timeframe),
    skip.has('scenarios') ? undefined : fetchScenarioData(asset, timeframe),
    skip.has('metabrain') ? undefined : fetchMetaBrainData(asset, timeframe),
    skip.has('execution') ? undefined : fetchExecutionData(asset, timeframe)
  ]);
  
  const context: TwinContext = {
    asset,
    timeframe,
    ts: Date.now(),
    regime: regimeData,
    state: stateData,
    physics: physicsData,
    liquidity: liquidityData,
    scenarios: scenarioData,
    metabrain: metabrainData,
    execution: executionData
  };
  
  return context;
}

/**
 * Check which modules are available
 */
export async function checkModuleAvailability(asset: string, timeframe: string): Promise<{
  regime: boolean;
  state: boolean;
  physics: boolean;
  liquidity: boolean;
  scenarios: boolean;
  metabrain: boolean;
  execution: boolean;
  available: number;
  total: number;
}> {
  const context = await buildLiveTwinContext(asset, timeframe, { timeout: 2000 });
  
  const availability = {
    regime: context.regime !== undefined,
    state: context.state !== undefined,
    physics: context.physics !== undefined,
    liquidity: context.liquidity !== undefined,
    scenarios: context.scenarios !== undefined && context.scenarios.length > 0,
    metabrain: context.metabrain !== undefined,
    execution: context.execution !== undefined,
    available: 0,
    total: 7
  };
  
  availability.available = Object.values(availability)
    .filter(v => v === true).length;
  
  return availability;
}
