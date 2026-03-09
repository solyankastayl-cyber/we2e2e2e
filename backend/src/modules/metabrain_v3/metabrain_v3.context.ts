/**
 * MetaBrain v3 — Context Builder
 * 
 * Collects global system context from all engines
 */

import { MetaBrainV3Context } from './metabrain_v3.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';

// ═══════════════════════════════════════════════════════════════
// CONTEXT FETCHERS
// ═══════════════════════════════════════════════════════════════

/**
 * Fetch tree stats from Digital Twin
 */
async function fetchTreeStats(asset: string, tf: string): Promise<{
  uncertainty: number;
  risk: number;
} | null> {
  try {
    const url = `http://localhost:8001/api/ta/twin/tree/integration?asset=${asset}&tf=${tf}`;
    const resp = await fetch(url);
    if (!resp.ok) return null;
    
    const data = await resp.json() as { data?: any };
    return {
      uncertainty: data.data?.treeStats?.uncertaintyScore ?? 0.5,
      risk: data.data?.treeStats?.treeRisk ?? 0.3
    };
  } catch {
    return null;
  }
}

/**
 * Fetch memory context
 */
async function fetchMemoryContext(asset: string, tf: string): Promise<{
  confidence: number;
  bias: 'BULL' | 'BEAR' | 'NEUTRAL';
  matches: number;
} | null> {
  try {
    const url = `http://localhost:8001/api/ta/memory/boost?asset=${asset}&tf=${tf}`;
    const resp = await fetch(url);
    if (!resp.ok) return null;
    
    const data = await resp.json() as { data?: any };
    
    const dominantOutcome = data.data?.dominantOutcome ?? 'NEUTRAL';
    const bias: 'BULL' | 'BEAR' | 'NEUTRAL' = 
      dominantOutcome === 'BULLISH' ? 'BULL' :
      dominantOutcome === 'BEARISH' ? 'BEAR' : 'NEUTRAL';
    
    return {
      confidence: data.data?.memoryConfidence ?? 0,
      bias,
      matches: data.data?.matchCount ?? 0
    };
  } catch {
    return null;
  }
}

/**
 * Fetch gating info
 */
async function fetchGatingInfo(): Promise<{
  gatedModules: number;
  gatePressure: number;
} | null> {
  try {
    const url = 'http://localhost:8001/api/ta/metabrain/learning/gates';
    const resp = await fetch(url);
    if (!resp.ok) return null;
    
    const data = await resp.json() as { data?: any };
    return {
      gatedModules: data.data?.summary?.hardGatedModules ?? 0,
      gatePressure: data.data?.summary?.gatePressure ?? 0
    };
  } catch {
    return null;
  }
}

/**
 * Fetch MetaBrain state
 */
async function fetchMetaBrainState(): Promise<{
  edgeHealth: number;
  drawdownPct: number;
  portfolioRiskPct: number;
} | null> {
  try {
    const url = 'http://localhost:8001/api/ta/metabrain/state';
    const resp = await fetch(url);
    if (!resp.ok) return null;
    
    const data = await resp.json() as { data?: any };
    return {
      edgeHealth: data.data?.edgeHealthScore ?? 0.5,
      drawdownPct: data.data?.drawdown ?? 0,
      portfolioRiskPct: data.data?.portfolioRisk ?? 0
    };
  } catch {
    return null;
  }
}

// ═══════════════════════════════════════════════════════════════
// MAIN CONTEXT BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Build full MetaBrain v3 context
 */
export async function buildMetaBrainV3Context(
  asset: string,
  timeframe: string,
  regime: MarketRegime = 'COMPRESSION',
  state: MarketStateNode = 'COMPRESSION'
): Promise<MetaBrainV3Context> {
  // Fetch all data in parallel
  const [treeStats, memoryCtx, gatingInfo, metaBrainState] = await Promise.all([
    fetchTreeStats(asset, timeframe),
    fetchMemoryContext(asset, timeframe),
    fetchGatingInfo(),
    fetchMetaBrainState()
  ]);
  
  return {
    // Market state
    regime,
    state,
    
    // Volatility & uncertainty
    volatility: 0.5,  // Would come from indicator engine
    treeUncertainty: treeStats?.uncertainty ?? 0.5,
    treeRisk: treeStats?.risk ?? 0.3,
    
    // Memory state
    memoryConfidence: memoryCtx?.confidence ?? 0,
    memoryBias: memoryCtx?.bias ?? 'NEUTRAL',
    memoryMatches: memoryCtx?.matches ?? 0,
    
    // System health
    edgeHealth: metaBrainState?.edgeHealth ?? 0.5,
    drawdownPct: metaBrainState?.drawdownPct ?? 0,
    portfolioRiskPct: metaBrainState?.portfolioRiskPct ?? 0,
    
    // Module state
    activeStrategies: 3,  // Default
    gatedModules: gatingInfo?.gatedModules ?? 0,
    gatePressure: gatingInfo?.gatePressure ?? 0,
    
    // Scenario state
    dominantScenario: 'CONTINUATION',  // Default
    dominantScenarioProbability: 0.5,
    
    ts: Date.now()
  };
}

/**
 * Create default context
 */
export function getDefaultContext(): MetaBrainV3Context {
  return {
    regime: 'COMPRESSION',
    state: 'COMPRESSION',
    volatility: 0.5,
    treeUncertainty: 0.5,
    treeRisk: 0.3,
    memoryConfidence: 0,
    memoryBias: 'NEUTRAL',
    memoryMatches: 0,
    edgeHealth: 0.5,
    drawdownPct: 0,
    portfolioRiskPct: 0,
    activeStrategies: 3,
    gatedModules: 0,
    gatePressure: 0,
    dominantScenario: 'CONTINUATION',
    dominantScenarioProbability: 0.5,
    ts: Date.now()
  };
}
