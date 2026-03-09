/**
 * Phase 5.1 B1.8 — Decision Adapter
 * 
 * Converts DecisionPack → TradePlan for Backtest Harness.
 * Keeps backtest decoupled from Decision Engine internals.
 */

import { TradePlan } from './domain/types.js';

// ═══════════════════════════════════════════════════════════════
// DecisionPack interface (what we expect from Decision Engine)
// ═══════════════════════════════════════════════════════════════

export interface DecisionPackMinimal {
  asset?: string;
  timeframe?: string;
  timestamp?: Date;
  
  // Top scenario (must have for trade)
  topScenario?: {
    scenarioId?: string;
    patternType?: string;
    direction?: 'LONG' | 'SHORT';
    
    entry?: number;
    stop?: number;
    target1?: number;
    target2?: number;
    
    riskReward?: number;
    score?: number;
    
    // ML predictions
    pEntry?: number;
    rExpected?: number;
    evAfterEdge?: number;
    evAfterML?: number;
    
    // Edge info
    edge?: {
      enabled?: boolean;
      multiplier?: number;
    };
  };
  
  // Fallback structure from actual DecisionEngine
  scenarios?: Array<{
    scenarioId?: string;
    patternType?: string;
    direction?: 'LONG' | 'SHORT';
    entry?: number;
    stop?: number;
    target1?: number;
    target2?: number;
    pEntry?: number;
    rExpected?: number;
    evAfterEdge?: number;
    evAfterML?: number;
    finalScore?: number;
  }>;
  
  // Meta
  regime?: string;
}

// ═══════════════════════════════════════════════════════════════
// Adapter Function
// ═══════════════════════════════════════════════════════════════

/**
 * Convert DecisionPack to TradePlan
 * Returns null if no valid trade signal
 */
export function decisionToTradePlan(
  decision: DecisionPackMinimal,
  defaultTimeoutBars: number = 50
): TradePlan | null {
  // Get top scenario
  const scenario = decision.topScenario || decision.scenarios?.[0];
  
  // No scenario = no trade
  if (!scenario) {
    return null;
  }
  
  // Validate direction
  const direction = scenario.direction;
  if (!direction || direction === 'WAIT' as any) {
    return null;
  }
  
  // Validate trade plan
  const entry = scenario.entry;
  const stop = scenario.stop;
  const target1 = scenario.target1;
  
  if (!entry || !stop || !target1) {
    return null;
  }
  
  // Validate risk makes sense
  const isLong = direction === 'LONG';
  const risk = isLong ? entry - stop : stop - entry;
  if (risk <= 0) {
    return null;  // Invalid risk
  }
  
  // Extract patterns used
  const patternsUsed = extractPatternsUsed(scenario);
  
  // Build trade plan
  const plan: TradePlan = {
    scenarioId: scenario.scenarioId || `sc_${Date.now()}`,
    bias: direction,
    
    entryPrice: entry,
    stopPrice: stop,
    target1: target1,
    target2: scenario.target2,
    
    timeoutBars: defaultTimeoutBars,
    
    // ML predictions
    pEntry: scenario.pEntry || 0.5,
    eR: scenario.rExpected || 1.5,
    ev: scenario.evAfterEdge || scenario.evAfterML || scenario.finalScore || 0,
    
    patternsUsed,
    edgeMultiplier: scenario.edge?.multiplier,
  };
  
  return plan;
}

/**
 * Extract pattern types from scenario
 */
function extractPatternsUsed(scenario: any): string[] {
  // Try different sources
  if (scenario.patterns && Array.isArray(scenario.patterns)) {
    return scenario.patterns.map((p: any) => p.type || p.patternType || 'UNKNOWN');
  }
  
  if (scenario.patternType) {
    return [scenario.patternType];
  }
  
  if (scenario.components && Array.isArray(scenario.components)) {
    return scenario.components.map((c: any) => c.type || 'UNKNOWN');
  }
  
  return ['UNKNOWN'];
}

/**
 * Build decision snapshot for trade record
 */
export function buildDecisionSnapshot(
  plan: TradePlan
): {
  scenarioId: string;
  bias: 'LONG' | 'SHORT' | 'WAIT';
  pEntry: number;
  eR: number;
  ev: number;
  patternsUsed: string[];
  edgeMultiplier?: number;
} {
  return {
    scenarioId: plan.scenarioId,
    bias: plan.bias,
    pEntry: plan.pEntry,
    eR: plan.eR,
    ev: plan.ev,
    patternsUsed: plan.patternsUsed,
    edgeMultiplier: plan.edgeMultiplier,
  };
}
