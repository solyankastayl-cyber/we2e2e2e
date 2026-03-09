/**
 * MetaBrain v3 — Main Optimizer
 * 
 * Orchestrates all v3 components to produce final decision
 */

import {
  MetaBrainV3Context,
  MetaBrainV3Decision,
  MetaBrainV3State,
  MetaBrainRiskMode,
  AnalysisMode,
  ModulePolicy,
  ExecutionPolicy,
  ConfidencePolicy
} from './metabrain_v3.types.js';
import { buildMetaBrainV3Context, getDefaultContext } from './metabrain_v3.context.js';
import { checkSafeMode, getSafeModeAdjustments } from './metabrain_v3.safemode.js';
import { decideAnalysisDepth, getEnabledModulesForMode } from './metabrain_v3.analysis_depth.js';
import { buildStrategyPolicy } from './metabrain_v3.strategy.js';
import { AnalysisModule, ALL_MODULES } from '../metabrain_learning/module_attribution.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { MarketStateNode } from '../state_engine/state.types.js';

// ═══════════════════════════════════════════════════════════════
// RISK MODE DETERMINATION
// ═══════════════════════════════════════════════════════════════

/**
 * Determine risk mode based on context
 */
export function determineRiskMode(context: MetaBrainV3Context): MetaBrainRiskMode {
  // High drawdown → CONSERVATIVE or SAFE
  if (context.drawdownPct > 0.08) return 'SAFE';
  if (context.drawdownPct > 0.05) return 'CONSERVATIVE';
  
  // High tree risk → CONSERVATIVE
  if (context.treeRisk > 0.45) return 'CONSERVATIVE';
  
  // Low edge health → CONSERVATIVE
  if (context.edgeHealth < 0.35) return 'CONSERVATIVE';
  
  // Strong memory + low uncertainty → can be AGGRESSIVE
  if (context.memoryConfidence > 0.70 && 
      context.treeUncertainty < 0.35 &&
      context.edgeHealth > 0.60) {
    return 'AGGRESSIVE';
  }
  
  return 'NORMAL';
}

// ═══════════════════════════════════════════════════════════════
// MODULE POLICY
// ═══════════════════════════════════════════════════════════════

/**
 * Build module policy based on analysis mode and gating
 */
export function buildModulePolicy(
  analysisMode: AnalysisMode,
  gatedModules: number
): ModulePolicy {
  const enabledModuleNames = getEnabledModulesForMode(analysisMode);
  
  const enabled: AnalysisModule[] = [];
  const disabled: AnalysisModule[] = [];
  
  for (const module of ALL_MODULES) {
    if (enabledModuleNames.includes(module)) {
      enabled.push(module);
    } else {
      disabled.push(module);
    }
  }
  
  return { enabledModules: enabled, disabledModules: disabled };
}

// ═══════════════════════════════════════════════════════════════
// EXECUTION POLICY
// ═══════════════════════════════════════════════════════════════

/**
 * Build execution policy
 */
export function buildExecutionPolicy(
  context: MetaBrainV3Context,
  riskMode: MetaBrainRiskMode,
  safeMode: boolean
): ExecutionPolicy {
  if (safeMode) {
    const adj = getSafeModeAdjustments();
    return {
      riskMultiplier: adj.riskMultiplier,
      maxRiskPerTrade: adj.maxRiskPerTrade,
      maxPortfolioRisk: adj.maxPortfolioRisk
    };
  }
  
  let riskMultiplier = 1.0;
  let maxRiskPerTrade = 0.01;  // 1%
  let maxPortfolioRisk = 0.05; // 5%
  
  switch (riskMode) {
    case 'SAFE':
      riskMultiplier = 0.5;
      maxRiskPerTrade = 0.005;
      maxPortfolioRisk = 0.02;
      break;
    case 'CONSERVATIVE':
      riskMultiplier = 0.75;
      maxRiskPerTrade = 0.0075;
      maxPortfolioRisk = 0.035;
      break;
    case 'NORMAL':
      riskMultiplier = 1.0;
      maxRiskPerTrade = 0.01;
      maxPortfolioRisk = 0.05;
      break;
    case 'AGGRESSIVE':
      riskMultiplier = 1.15;
      maxRiskPerTrade = 0.015;
      maxPortfolioRisk = 0.07;
      break;
  }
  
  // Adjust by memory confidence
  if (context.memoryConfidence > 0.70) {
    riskMultiplier *= 1.05;
  }
  
  // Adjust by tree risk
  riskMultiplier *= (1 - context.treeRisk * 0.2);
  
  return {
    riskMultiplier: Math.round(riskMultiplier * 1000) / 1000,
    maxRiskPerTrade: Math.round(maxRiskPerTrade * 10000) / 10000,
    maxPortfolioRisk: Math.round(maxPortfolioRisk * 1000) / 1000
  };
}

// ═══════════════════════════════════════════════════════════════
// CONFIDENCE POLICY
// ═══════════════════════════════════════════════════════════════

/**
 * Build confidence policy
 */
export function buildConfidencePolicy(
  context: MetaBrainV3Context,
  riskMode: MetaBrainRiskMode,
  safeMode: boolean
): ConfidencePolicy {
  if (safeMode) {
    const adj = getSafeModeAdjustments();
    return {
      minSignalConfidence: adj.minSignalConfidence,
      minScenarioProbability: adj.minScenarioProbability
    };
  }
  
  let minSignalConfidence = 0.55;
  let minScenarioProbability = 0.50;
  
  switch (riskMode) {
    case 'SAFE':
      minSignalConfidence = 0.75;
      minScenarioProbability = 0.65;
      break;
    case 'CONSERVATIVE':
      minSignalConfidence = 0.65;
      minScenarioProbability = 0.55;
      break;
    case 'NORMAL':
      minSignalConfidence = 0.55;
      minScenarioProbability = 0.50;
      break;
    case 'AGGRESSIVE':
      minSignalConfidence = 0.50;
      minScenarioProbability = 0.45;
      break;
  }
  
  // Adjust by memory - strong memory lowers thresholds
  if (context.memoryConfidence > 0.70) {
    minSignalConfidence -= 0.05;
    minScenarioProbability -= 0.05;
  }
  
  return {
    minSignalConfidence: Math.round(Math.max(0.40, minSignalConfidence) * 100) / 100,
    minScenarioProbability: Math.round(Math.max(0.35, minScenarioProbability) * 100) / 100
  };
}

// ═══════════════════════════════════════════════════════════════
// MAIN OPTIMIZER
// ═══════════════════════════════════════════════════════════════

/**
 * Run MetaBrain v3 optimization
 */
export async function runMetaBrainV3(
  asset: string,
  timeframe: string,
  regime?: MarketRegime,
  state?: MarketStateNode
): Promise<MetaBrainV3State> {
  // Build context
  const context = await buildMetaBrainV3Context(
    asset,
    timeframe,
    regime ?? 'COMPRESSION',
    state ?? 'COMPRESSION'
  );
  
  return runMetaBrainV3WithContext(context, asset, timeframe);
}

/**
 * Run MetaBrain v3 with pre-built context
 */
export function runMetaBrainV3WithContext(
  context: MetaBrainV3Context,
  asset?: string,
  timeframe?: string
): MetaBrainV3State {
  const reasons: string[] = [];
  
  // 1. Check safe mode
  const safeModeCheck = checkSafeMode(context);
  const safeMode = safeModeCheck.triggered;
  
  if (safeMode) {
    reasons.push(`SAFE MODE: ${safeModeCheck.triggers.join(', ')}`);
  }
  
  // 2. Determine risk mode
  let riskMode = determineRiskMode(context);
  if (safeMode) {
    riskMode = 'SAFE';
  }
  reasons.push(`Risk mode: ${riskMode}`);
  
  // 3. Decide analysis depth
  const analysisDepth = decideAnalysisDepth(context);
  reasons.push(`Analysis mode: ${analysisDepth.mode} (${analysisDepth.reason})`);
  
  // 4. Build strategy policy
  const strategyPolicy = buildStrategyPolicy(context, riskMode, safeMode);
  
  // 5. Build module policy
  const modulePolicy = buildModulePolicy(analysisDepth.mode, context.gatedModules);
  
  // 6. Build execution policy
  const executionPolicy = buildExecutionPolicy(context, riskMode, safeMode);
  
  // 7. Build confidence policy
  const confidencePolicy = buildConfidencePolicy(context, riskMode, safeMode);
  
  // Calculate decision confidence
  let decisionConfidence = 0.5;
  if (context.memoryConfidence > 0.6) decisionConfidence += 0.15;
  if (context.treeUncertainty < 0.4) decisionConfidence += 0.10;
  if (context.edgeHealth > 0.5) decisionConfidence += 0.10;
  if (safeMode) decisionConfidence -= 0.20;
  
  const decision: MetaBrainV3Decision = {
    analysisMode: analysisDepth.mode,
    riskMode,
    strategyPolicy,
    modulePolicy,
    executionPolicy,
    confidencePolicy,
    safeMode,
    reasons,
    decisionConfidence: Math.round(Math.max(0.1, Math.min(0.95, decisionConfidence)) * 100) / 100,
    decidedAt: new Date()
  };
  
  return {
    context,
    decision,
    asset,
    timeframe,
    createdAt: new Date()
  };
}

/**
 * Get neutral/default decision
 */
export function getNeutralDecision(): MetaBrainV3Decision {
  return {
    analysisMode: 'CLASSIC_TA',
    riskMode: 'NORMAL',
    strategyPolicy: {
      enabledStrategies: ['TREND_FOLLOW', 'BREAKOUT'],
      disabledStrategies: [],
      strategyMultiplier: 1.0
    },
    modulePolicy: {
      enabledModules: ['PATTERN', 'LIQUIDITY', 'STATE', 'REGIME'],
      disabledModules: ['GRAPH', 'FRACTAL', 'PHYSICS', 'SCENARIO']
    },
    executionPolicy: {
      riskMultiplier: 1.0,
      maxRiskPerTrade: 0.01,
      maxPortfolioRisk: 0.05
    },
    confidencePolicy: {
      minSignalConfidence: 0.55,
      minScenarioProbability: 0.50
    },
    safeMode: false,
    reasons: ['Default neutral decision'],
    decisionConfidence: 0.5,
    decidedAt: new Date()
  };
}
