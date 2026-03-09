/**
 * DT3 — Twin Consistency Engine
 * 
 * Detects conflicts between modules and calculates consistency score
 */

import {
  DigitalTwinState,
  TwinConsistency,
  TwinConflict,
  ConflictType,
  ConflictSeverity,
  DEFAULT_TWIN_CONFIG,
  DigitalTwinConfig
} from './digital_twin.types.js';

// ═══════════════════════════════════════════════════════════════
// CONFLICT RULES
// ═══════════════════════════════════════════════════════════════

interface ConflictRule {
  type: ConflictType;
  modules: string[];
  check: (state: DigitalTwinState) => { hasConflict: boolean; description: string };
  severity: ConflictSeverity;
  resolution: string;
}

const CONFLICT_RULES: ConflictRule[] = [
  // ─────────────────────────────────────────────────────────────
  // REGIME vs PHYSICS
  // ─────────────────────────────────────────────────────────────
  {
    type: 'REGIME_PHYSICS',
    modules: ['RegimeEngine', 'PhysicsEngine'],
    severity: 'HIGH',
    resolution: 'reduce_physics_weight',
    check: (state) => {
      // COMPRESSION regime but ENERGY_RELEASE physics
      if (state.regime === 'COMPRESSION' && 
          (state.physicsState === 'RELEASE' || state.physicsState === 'EXPANSION')) {
        return {
          hasConflict: true,
          description: `Regime=${state.regime} conflicts with Physics=${state.physicsState}. Compression expects energy building, not release.`
        };
      }
      
      // EXPANSION regime but COMPRESSION physics
      if ((state.regime === 'TREND_EXPANSION' || state.regime === 'VOLATILITY_EXPANSION') && 
          state.physicsState === 'COMPRESSION') {
        return {
          hasConflict: true,
          description: `Regime=${state.regime} conflicts with Physics=${state.physicsState}. Expansion expects energy release.`
        };
      }
      
      // EXHAUSTION physics but expecting continuation
      if (state.physicsState === 'EXHAUSTION' && state.regime === 'TREND_CONTINUATION') {
        return {
          hasConflict: true,
          description: `Physics EXHAUSTION conflicts with TREND_CONTINUATION regime.`
        };
      }
      
      return { hasConflict: false, description: '' };
    }
  },
  
  // ─────────────────────────────────────────────────────────────
  // REGIME vs SCENARIO
  // ─────────────────────────────────────────────────────────────
  {
    type: 'REGIME_SCENARIO',
    modules: ['RegimeEngine', 'ScenarioEngine'],
    severity: 'MEDIUM',
    resolution: 'reduce_scenario_confidence',
    check: (state) => {
      const dominantBranch = state.branches[0];
      if (!dominantBranch) return { hasConflict: false, description: '' };
      
      // RANGE regime but trending scenario
      if (state.regime === 'RANGE_ROTATION' && 
          dominantBranch.direction !== 'NEUTRAL' &&
          dominantBranch.path.includes('EXPANSION')) {
        return {
          hasConflict: true,
          description: `Regime=${state.regime} conflicts with scenario direction=${dominantBranch.direction}. Range expects neutral movement.`
        };
      }
      
      // TREND regime but neutral scenario
      if ((state.regime === 'TREND_EXPANSION' || state.regime === 'TREND_CONTINUATION') &&
          dominantBranch.direction === 'NEUTRAL') {
        return {
          hasConflict: true,
          description: `Trend regime conflicts with NEUTRAL scenario direction.`
        };
      }
      
      return { hasConflict: false, description: '' };
    }
  },
  
  // ─────────────────────────────────────────────────────────────
  // LIQUIDITY vs DIRECTION
  // ─────────────────────────────────────────────────────────────
  {
    type: 'LIQUIDITY_DIRECTION',
    modules: ['LiquidityEngine', 'ScenarioEngine'],
    severity: 'MEDIUM',
    resolution: 'adjust_direction_confidence',
    check: (state) => {
      const dominantBranch = state.branches[0];
      if (!dominantBranch) return { hasConflict: false, description: '' };
      
      // SWEEP_LOW usually leads to bullish, but scenario is bearish
      if (state.liquidityState === 'SWEEP_LOW' && dominantBranch.direction === 'BEAR') {
        return {
          hasConflict: true,
          description: `Liquidity SWEEP_LOW (bullish signal) conflicts with BEAR scenario direction.`
        };
      }
      
      // SWEEP_HIGH usually leads to bearish, but scenario is bullish
      if (state.liquidityState === 'SWEEP_HIGH' && dominantBranch.direction === 'BULL') {
        return {
          hasConflict: true,
          description: `Liquidity SWEEP_HIGH (bearish signal) conflicts with BULL scenario direction.`
        };
      }
      
      return { hasConflict: false, description: '' };
    }
  },
  
  // ─────────────────────────────────────────────────────────────
  // PHYSICS vs SCENARIO
  // ─────────────────────────────────────────────────────────────
  {
    type: 'PHYSICS_SCENARIO',
    modules: ['PhysicsEngine', 'ScenarioEngine'],
    severity: 'HIGH',
    resolution: 'reduce_scenario_probability',
    check: (state) => {
      const dominantBranch = state.branches[0];
      if (!dominantBranch) return { hasConflict: false, description: '' };
      
      // LOW energy but expecting EXPANSION
      if (state.energy < 0.3 && dominantBranch.path.includes('EXPANSION')) {
        return {
          hasConflict: true,
          description: `Low energy (${state.energy.toFixed(2)}) conflicts with EXPANSION scenario. Need energy to expand.`
        };
      }
      
      // EXHAUSTION state but expecting CONTINUATION
      if (state.physicsState === 'EXHAUSTION' && dominantBranch.path.includes('CONTINUATION')) {
        return {
          hasConflict: true,
          description: `Physics EXHAUSTION conflicts with CONTINUATION scenario.`
        };
      }
      
      return { hasConflict: false, description: '' };
    }
  },
  
  // ─────────────────────────────────────────────────────────────
  // STATE vs SCENARIO
  // ─────────────────────────────────────────────────────────────
  {
    type: 'STATE_SCENARIO',
    modules: ['StateEngine', 'ScenarioEngine'],
    severity: 'LOW',
    resolution: 'monitor_state_transition',
    check: (state) => {
      const dominantBranch = state.branches[0];
      if (!dominantBranch) return { hasConflict: false, description: '' };
      
      // BALANCE state but scenario expects immediate breakout
      if (state.marketState === 'BALANCE' && 
          dominantBranch.path[0] === 'BREAKOUT') {
        return {
          hasConflict: true,
          description: `Market state BALANCE but scenario starts with BREAKOUT. May need state transition first.`
        };
      }
      
      // EXHAUSTION state but scenario expects continuation
      if (state.marketState === 'EXHAUSTION' && 
          dominantBranch.path.includes('CONTINUATION')) {
        return {
          hasConflict: true,
          description: `Market state EXHAUSTION conflicts with CONTINUATION in scenario path.`
        };
      }
      
      return { hasConflict: false, description: '' };
    }
  },
  
  // ─────────────────────────────────────────────────────────────
  // ENERGY vs SCENARIO
  // ─────────────────────────────────────────────────────────────
  {
    type: 'ENERGY_SCENARIO',
    modules: ['PhysicsEngine', 'ScenarioEngine'],
    severity: 'MEDIUM',
    resolution: 'adjust_expected_move',
    check: (state) => {
      const dominantBranch = state.branches[0];
      if (!dominantBranch) return { hasConflict: false, description: '' };
      
      // Low energy but high expected move
      if (state.energy < 0.4 && dominantBranch.expectedMoveATR > 2.0) {
        return {
          hasConflict: true,
          description: `Low energy (${state.energy.toFixed(2)}) conflicts with high expected move (${dominantBranch.expectedMoveATR.toFixed(1)} ATR).`
        };
      }
      
      // High energy but expecting range
      if (state.energy > 0.7 && dominantBranch.path.includes('RANGE')) {
        return {
          hasConflict: true,
          description: `High energy (${state.energy.toFixed(2)}) conflicts with RANGE scenario. Energy needs release.`
        };
      }
      
      return { hasConflict: false, description: '' };
    }
  }
];

// ═══════════════════════════════════════════════════════════════
// SEVERITY SCORES
// ═══════════════════════════════════════════════════════════════

const SEVERITY_SCORES: Record<ConflictSeverity, number> = {
  LOW: 0.1,
  MEDIUM: 0.3,
  HIGH: 0.6,
  CRITICAL: 0.9
};

// ═══════════════════════════════════════════════════════════════
// MAIN CONSISTENCY EVALUATOR
// ═══════════════════════════════════════════════════════════════

/**
 * Evaluate twin consistency
 */
export function evaluateTwinConsistency(
  state: DigitalTwinState,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): TwinConsistency {
  const conflicts: TwinConflict[] = [];
  
  // Check all conflict rules
  for (const rule of CONFLICT_RULES) {
    const result = rule.check(state);
    
    if (result.hasConflict) {
      conflicts.push({
        type: rule.type,
        modules: rule.modules,
        severity: rule.severity,
        severityScore: SEVERITY_SCORES[rule.severity],
        description: result.description,
        resolution: rule.resolution
      });
    }
  }
  
  // Calculate total conflict weight
  const totalConflictWeight = conflicts.reduce(
    (sum, c) => sum + c.severityScore,
    0
  );
  
  // Calculate consistency score (1 = fully consistent)
  const score = Math.max(0, Math.min(1, 1 - totalConflictWeight));
  
  return {
    score,
    conflicts,
    totalConflictWeight
  };
}

// ═══════════════════════════════════════════════════════════════
// CONFLICT ANALYSIS
// ═══════════════════════════════════════════════════════════════

/**
 * Get most critical conflict
 */
export function getMostCriticalConflict(
  consistency: TwinConsistency
): TwinConflict | null {
  if (consistency.conflicts.length === 0) return null;
  
  return consistency.conflicts.reduce((max, conflict) =>
    conflict.severityScore > max.severityScore ? conflict : max
  );
}

/**
 * Get conflicts by module
 */
export function getConflictsByModule(
  consistency: TwinConsistency,
  moduleName: string
): TwinConflict[] {
  return consistency.conflicts.filter(c => 
    c.modules.some(m => m.toLowerCase().includes(moduleName.toLowerCase()))
  );
}

/**
 * Check if consistency is acceptable
 */
export function isConsistencyAcceptable(
  consistency: TwinConsistency,
  config: DigitalTwinConfig = DEFAULT_TWIN_CONFIG
): boolean {
  return consistency.score >= config.minConsistencyScore;
}

/**
 * Get resolution suggestions prioritized by severity
 */
export function getResolutionSuggestions(
  consistency: TwinConsistency
): string[] {
  const sorted = [...consistency.conflicts].sort(
    (a, b) => b.severityScore - a.severityScore
  );
  
  return sorted.map(c => `${c.type}: ${c.resolution}`);
}

// ═══════════════════════════════════════════════════════════════
// CONSISTENCY CHANGE DETECTION
// ═══════════════════════════════════════════════════════════════

/**
 * Compare consistency between states
 */
export function compareConsistency(
  prev: TwinConsistency | undefined,
  next: TwinConsistency
): {
  improved: boolean;
  degraded: boolean;
  newConflicts: TwinConflict[];
  resolvedConflicts: TwinConflict[];
} {
  if (!prev) {
    return {
      improved: false,
      degraded: false,
      newConflicts: next.conflicts,
      resolvedConflicts: []
    };
  }
  
  const prevTypes = new Set(prev.conflicts.map(c => c.type));
  const nextTypes = new Set(next.conflicts.map(c => c.type));
  
  const newConflicts = next.conflicts.filter(c => !prevTypes.has(c.type));
  const resolvedConflicts = prev.conflicts.filter(c => !nextTypes.has(c.type));
  
  return {
    improved: next.score > prev.score,
    degraded: next.score < prev.score,
    newConflicts,
    resolvedConflicts
  };
}
