/**
 * MetaBrain v3 — Safe Mode Controller
 */

import {
  MetaBrainV3Context,
  SafeModeConfig,
  DEFAULT_SAFE_MODE_CONFIG
} from './metabrain_v3.types.js';

// ═══════════════════════════════════════════════════════════════
// SAFE MODE CHECKS
// ═══════════════════════════════════════════════════════════════

export interface SafeModeCheckResult {
  triggered: boolean;
  triggers: string[];
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
}

/**
 * Check if safe mode should be triggered
 */
export function checkSafeMode(
  context: MetaBrainV3Context,
  config: SafeModeConfig = DEFAULT_SAFE_MODE_CONFIG
): SafeModeCheckResult {
  const triggers: string[] = [];
  
  // Check drawdown
  if (context.drawdownPct > config.maxDrawdownPct) {
    triggers.push(`Drawdown ${(context.drawdownPct * 100).toFixed(1)}% exceeds ${(config.maxDrawdownPct * 100).toFixed(0)}%`);
  }
  
  // Check tree uncertainty
  if (context.treeUncertainty > config.maxTreeUncertainty) {
    triggers.push(`Tree uncertainty ${context.treeUncertainty.toFixed(2)} exceeds ${config.maxTreeUncertainty}`);
  }
  
  // Check tree risk
  if (context.treeRisk > config.maxTreeRisk) {
    triggers.push(`Tree risk ${context.treeRisk.toFixed(2)} exceeds ${config.maxTreeRisk}`);
  }
  
  // Check memory confidence (low is bad)
  if (context.memoryConfidence < config.minMemoryConfidence && context.memoryMatches > 10) {
    triggers.push(`Memory confidence ${context.memoryConfidence.toFixed(2)} below ${config.minMemoryConfidence}`);
  }
  
  // Check gated modules
  if (context.gatedModules > config.maxGatedModules) {
    triggers.push(`${context.gatedModules} modules gated (max ${config.maxGatedModules})`);
  }
  
  // Check gate pressure
  if (context.gatePressure > config.maxGatePressure) {
    triggers.push(`Gate pressure ${context.gatePressure.toFixed(2)} exceeds ${config.maxGatePressure}`);
  }
  
  // Check edge health
  if (context.edgeHealth < config.minEdgeHealth) {
    triggers.push(`Edge health ${context.edgeHealth.toFixed(2)} below ${config.minEdgeHealth}`);
  }
  
  // Determine severity
  let severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' = 'LOW';
  if (triggers.length >= 4) severity = 'CRITICAL';
  else if (triggers.length >= 3) severity = 'HIGH';
  else if (triggers.length >= 2) severity = 'MEDIUM';
  else if (triggers.length >= 1) severity = 'LOW';
  
  return {
    triggered: triggers.length >= 2,  // Need at least 2 triggers
    triggers,
    severity
  };
}

/**
 * Get safe mode policy adjustments
 */
export function getSafeModeAdjustments(): {
  riskMultiplier: number;
  maxRiskPerTrade: number;
  maxPortfolioRisk: number;
  minSignalConfidence: number;
  minScenarioProbability: number;
} {
  return {
    riskMultiplier: 0.5,
    maxRiskPerTrade: 0.005,  // 0.5%
    maxPortfolioRisk: 0.02,  // 2%
    minSignalConfidence: 0.75,
    minScenarioProbability: 0.65
  };
}
