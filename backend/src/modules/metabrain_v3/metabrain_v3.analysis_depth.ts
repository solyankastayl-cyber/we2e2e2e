/**
 * MetaBrain v3 — Analysis Depth Controller
 */

import {
  MetaBrainV3Context,
  AnalysisMode,
  AnalysisDepthConfig,
  DEFAULT_ANALYSIS_DEPTH_CONFIG
} from './metabrain_v3.types.js';
import { MarketRegime } from '../regime/regime.types.js';

// ═══════════════════════════════════════════════════════════════
// ANALYSIS DEPTH DECISION
// ═══════════════════════════════════════════════════════════════

export interface AnalysisDepthDecision {
  mode: AnalysisMode;
  reason: string;
  enabledLayers: string[];
}

/**
 * Decide analysis depth based on context
 */
export function decideAnalysisDepth(
  context: MetaBrainV3Context,
  config: AnalysisDepthConfig = DEFAULT_ANALYSIS_DEPTH_CONFIG
): AnalysisDepthDecision {
  const reasons: string[] = [];
  let useDeepMarket = false;
  
  // Check tree uncertainty
  if (context.treeUncertainty > config.deepMarketTreeUncertaintyThreshold) {
    useDeepMarket = true;
    reasons.push(`High tree uncertainty (${context.treeUncertainty.toFixed(2)})`);
  }
  
  // Check memory confidence
  if (context.memoryConfidence > config.deepMarketMemoryConfidenceThreshold) {
    useDeepMarket = true;
    reasons.push(`Strong memory signals (${context.memoryConfidence.toFixed(2)})`);
  }
  
  // Check complex regime
  if (config.complexRegimes.includes(context.regime)) {
    useDeepMarket = true;
    reasons.push(`Complex regime (${context.regime})`);
  }
  
  // Check gated modules (need deep analysis to compensate)
  if (context.gatedModules >= config.deepMarketGatedModulesThreshold) {
    useDeepMarket = true;
    reasons.push(`${context.gatedModules} modules gated`);
  }
  
  // Determine enabled layers
  const enabledLayers = useDeepMarket
    ? ['TA', 'CONTEXT', 'LIQUIDITY', 'GRAPH', 'FRACTAL', 'PHYSICS', 'STATE', 'REGIME', 'SCENARIO', 'MEMORY', 'TWIN']
    : ['TA', 'CONTEXT', 'LIQUIDITY', 'STATE', 'REGIME'];
  
  return {
    mode: useDeepMarket ? 'DEEP_MARKET' : 'CLASSIC_TA',
    reason: reasons.length > 0 
      ? reasons.join('; ')
      : 'Standard market conditions - using classic TA',
    enabledLayers
  };
}

/**
 * Get modules enabled for analysis mode
 */
export function getEnabledModulesForMode(mode: AnalysisMode): string[] {
  if (mode === 'DEEP_MARKET') {
    return ['PATTERN', 'LIQUIDITY', 'GRAPH', 'FRACTAL', 'PHYSICS', 'STATE', 'REGIME', 'SCENARIO'];
  }
  
  // CLASSIC_TA
  return ['PATTERN', 'LIQUIDITY', 'STATE', 'REGIME'];
}
