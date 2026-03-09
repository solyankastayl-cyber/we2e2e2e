/**
 * MetaBrain v1 — Controller
 * 
 * Main orchestration logic
 */

import { v4 as uuidv4 } from 'uuid';
import {
  MetaBrainContext,
  MetaBrainDecision,
  MetaBrainState,
  MetaBrainAction,
  MetaRiskMode,
  DEFAULT_METABRAIN_CONFIG
} from './metabrain.types.js';
import {
  buildMetaBrainContext,
  getDefaultContext,
  RegimeSource,
  StateSource,
  PhysicsSource,
  PortfolioSource,
  EdgeSource,
  StrategySource,
  GovernanceSource
} from './metabrain.context.js';
import { computeRiskMode, validateModeTransition, calculateRiskScore } from './metabrain.risk_mode.js';
import { buildMetaDecision, determineSignalThresholds } from './metabrain.policy.js';
import {
  getMetaBrainState,
  saveMetaBrainState,
  saveMetaBrainAction,
  getModeChangesToday,
  getLastModeChangeTime
} from './metabrain.storage.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY CACHE
// ═══════════════════════════════════════════════════════════════

let cachedState: MetaBrainState | null = null;
let lastComputeTime: Date | null = null;
const CACHE_TTL_MS = 60 * 1000;  // 1 minute

// ═══════════════════════════════════════════════════════════════
// MAIN CONTROLLER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Run full MetaBrain computation
 */
export async function runMetaBrain(
  sources?: {
    regime?: RegimeSource;
    state?: StateSource;
    physics?: PhysicsSource;
    portfolio?: PortfolioSource;
    edge?: EdgeSource;
    strategy?: StrategySource;
    governance?: GovernanceSource;
  }
): Promise<MetaBrainDecision> {
  
  // Build context from sources (or use defaults for testing)
  const context = sources ? buildMetaBrainContext(
    sources.regime || { regime: 'COMPRESSION', confidence: 0.5 },
    sources.state || { state: 'NEUTRAL' },
    sources.physics || { volatility: 1.0, atrRatio: 1.0 },
    sources.portfolio || { accountSize: 100000, unrealizedPnL: 0, realizedPnL: 0, totalRisk: 0, openPositions: 0 },
    sources.edge || { avgProfitFactor: 1.2, recentWinRate: 0.55, edgeTrend: 0 },
    sources.strategy || { bestScore: 0.5, activeCount: 3 },
    sources.governance || { frozen: false }
  ) : getDefaultContext();
  
  // Get current state
  const currentState = await getMetaBrainState();
  const previousRiskMode: MetaRiskMode = currentState?.currentRiskMode as MetaRiskMode || 'NORMAL';
  
  // Compute new risk mode
  const { mode: newRiskMode, reasons } = computeRiskMode(context);
  
  // Check if mode change is allowed
  const modeChangesToday = await getModeChangesToday();
  const lastChangeTime = await getLastModeChangeTime();
  
  let finalRiskMode = newRiskMode;
  let isOverride = false;
  let overrideReason: string | undefined;
  
  if (newRiskMode !== previousRiskMode) {
    const validation = validateModeTransition(
      previousRiskMode,
      newRiskMode,
      modeChangesToday,
      lastChangeTime
    );
    
    if (!validation.allowed) {
      finalRiskMode = previousRiskMode;
      isOverride = true;
      overrideReason = validation.reason;
    }
  }
  
  // Build decision
  const decision = buildMetaDecision(context, finalRiskMode, reasons);
  decision.isOverride = isOverride;
  decision.overrideReason = overrideReason;
  
  // Log action if mode changed
  if (finalRiskMode !== previousRiskMode && !isOverride) {
    const action: MetaBrainAction = {
      actionId: `MBA_${uuidv4().slice(0, 8)}`,
      timestamp: new Date(),
      actionType: 'SET_RISK_MODE',
      from: previousRiskMode,
      to: finalRiskMode,
      contextSnapshot: {
        drawdownPct: context.drawdownPct,
        volatility: context.volatility,
        edgeHealth: context.edgeHealth,
        regime: context.regime
      },
      reason: reasons
    };
    await saveMetaBrainAction(action);
  }
  
  // Update state
  const riskModeHistory = currentState?.riskModeHistory || [];
  if (finalRiskMode !== previousRiskMode && !isOverride) {
    riskModeHistory.push({
      mode: finalRiskMode,
      at: new Date(),
      reason: reasons
    });
    // Keep only last 100
    while (riskModeHistory.length > 100) riskModeHistory.shift();
  }
  
  const newState: Partial<MetaBrainState> = {
    currentRiskMode: finalRiskMode,
    currentDecision: decision,
    currentContext: context,
    riskModeHistory,
    totalDecisions: (currentState?.totalDecisions || 0) + 1,
    modeChangesToday: finalRiskMode !== previousRiskMode && !isOverride 
      ? modeChangesToday + 1 
      : modeChangesToday,
    systemHealth: determineSystemHealth(context),
    updatedAt: new Date()
  };
  
  await saveMetaBrainState(newState);
  
  // Update cache
  cachedState = newState as MetaBrainState;
  lastComputeTime = new Date();
  
  return decision;
}

/**
 * Get current MetaBrain state (with caching)
 */
export async function getCurrentState(): Promise<MetaBrainState | null> {
  // Return cache if fresh
  if (cachedState && lastComputeTime) {
    const age = Date.now() - lastComputeTime.getTime();
    if (age < CACHE_TTL_MS) {
      return cachedState;
    }
  }
  
  // Fetch from DB
  const state = await getMetaBrainState();
  if (state) {
    cachedState = state as unknown as MetaBrainState;
    lastComputeTime = new Date();
  }
  
  return cachedState;
}

/**
 * Get current decision (quick access)
 */
export async function getCurrentDecision(): Promise<MetaBrainDecision | null> {
  const state = await getCurrentState();
  return state?.currentDecision || null;
}

/**
 * Force recompute (bypasses cache)
 */
export async function forceRecompute(
  sources?: Parameters<typeof runMetaBrain>[0]
): Promise<MetaBrainDecision> {
  cachedState = null;
  lastComputeTime = null;
  return runMetaBrain(sources);
}

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function determineSystemHealth(context: MetaBrainContext): 'HEALTHY' | 'DEGRADED' | 'CRITICAL' {
  let issues = 0;
  
  if (context.drawdownPct > 0.1) issues += 2;
  else if (context.drawdownPct > 0.05) issues += 1;
  
  if (context.volatility === 'EXTREME') issues += 2;
  else if (context.volatility === 'HIGH') issues += 1;
  
  if (context.edgeHealth < 0.3) issues += 2;
  else if (context.edgeHealth < 0.4) issues += 1;
  
  if (context.governanceFrozen) issues += 3;
  
  if (issues >= 5) return 'CRITICAL';
  if (issues >= 2) return 'DEGRADED';
  return 'HEALTHY';
}

/**
 * Get risk multiplier for Execution Engine integration
 */
export async function getRiskMultiplier(): Promise<number> {
  const decision = await getCurrentDecision();
  return decision?.riskMultiplier || 1.0;
}

/**
 * Get confidence threshold for Decision Engine integration
 */
export async function getConfidenceThreshold(): Promise<number> {
  const decision = await getCurrentDecision();
  return decision?.confidenceThreshold || 0.55;
}

/**
 * Get strategy multiplier for Strategy Builder integration
 */
export async function getStrategyMultiplier(): Promise<number> {
  const decision = await getCurrentDecision();
  return decision?.strategyMultiplier || 1.0;
}
