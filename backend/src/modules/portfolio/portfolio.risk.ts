/**
 * Phase 5.5 — Portfolio Risk Service
 * ====================================
 * Calculates VaR, drawdown, concentration, and risk warnings
 */

import { PortfolioRisk, RiskWarning } from './portfolio.types.js';
import { getPortfolioState, getPortfolioLimits } from './portfolio.state.js';
import { getExposureState } from './portfolio.exposure.js';
import { buildCorrelationMatrix, checkCorrelationRisk } from './portfolio.correlation.js';

// ═══════════════════════════════════════════════════════════════
// RISK STATE
// ═══════════════════════════════════════════════════════════════

let peakValue = 100000;
let maxDrawdown = 0;
let drawdownStartDate: number | null = null;

// ═══════════════════════════════════════════════════════════════
// DRAWDOWN CALCULATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Update peak value and calculate drawdown
 */
function updateDrawdown(currentValue: number): { current: number; max: number; duration: number } {
  // Update peak
  if (currentValue > peakValue) {
    peakValue = currentValue;
    drawdownStartDate = null;
  }
  
  // Calculate current drawdown
  const currentDrawdown = peakValue > 0 ? (peakValue - currentValue) / peakValue : 0;
  
  // Update max drawdown
  if (currentDrawdown > maxDrawdown) {
    maxDrawdown = currentDrawdown;
  }
  
  // Track drawdown duration
  if (currentDrawdown > 0.01 && !drawdownStartDate) {
    drawdownStartDate = Date.now();
  }
  
  const duration = drawdownStartDate 
    ? Math.floor((Date.now() - drawdownStartDate) / (24 * 3600000))
    : 0;
  
  return {
    current: Math.round(currentDrawdown * 10000) / 10000,
    max: Math.round(maxDrawdown * 10000) / 10000,
    duration,
  };
}

// ═══════════════════════════════════════════════════════════════
// VAR CALCULATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate Value at Risk (simplified parametric approach)
 * In production, would use historical simulation or Monte Carlo
 */
function calculateVaR(portfolioValue: number, leverage: number): { var95: number; var99: number } {
  // Average daily volatility for crypto (simplified)
  const dailyVol = 0.035;  // 3.5% daily vol
  
  // Adjust for leverage
  const adjustedVol = dailyVol * leverage;
  
  // Z-scores
  const z95 = 1.645;
  const z99 = 2.326;
  
  const var95 = portfolioValue * adjustedVol * z95;
  const var99 = portfolioValue * adjustedVol * z99;
  
  return {
    var95: Math.round(var95 * 100) / 100,
    var99: Math.round(var99 * 100) / 100,
  };
}

// ═══════════════════════════════════════════════════════════════
// CONCENTRATION RISK
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate Herfindahl Index for concentration
 * 0 = perfectly diversified, 1 = single asset
 */
function calculateConcentration(): { herfindahl: number; largestPosition: number } {
  const exposure = getExposureState();
  
  if (exposure.byAsset.length === 0) {
    return { herfindahl: 0, largestPosition: 0 };
  }
  
  // Sum of squared weights
  const herfindahl = exposure.byAsset.reduce((sum, a) => sum + Math.pow(a.weight, 2), 0);
  
  // Largest single position
  const largestPosition = exposure.byAsset.length > 0 ? exposure.byAsset[0].weight : 0;
  
  return {
    herfindahl: Math.round(herfindahl * 10000) / 10000,
    largestPosition: Math.round(largestPosition * 10000) / 10000,
  };
}

// ═══════════════════════════════════════════════════════════════
// RISK WARNINGS
// ═══════════════════════════════════════════════════════════════

function generateWarnings(): RiskWarning[] {
  const warnings: RiskWarning[] = [];
  const limits = getPortfolioLimits();
  const state = getPortfolioState();
  const exposure = getExposureState();
  const concentration = calculateConcentration();
  const correlation = checkCorrelationRisk(limits.maxCorrelatedExposure);
  const drawdown = updateDrawdown(state.totalValue);
  
  // Concentration warning
  if (concentration.largestPosition > limits.maxSingleAssetExposure) {
    warnings.push({
      type: 'CONCENTRATION',
      severity: concentration.largestPosition > limits.maxSingleAssetExposure * 1.5 ? 'CRITICAL' : 'WARNING',
      message: `Single asset exposure ${(concentration.largestPosition * 100).toFixed(1)}% exceeds limit`,
      value: concentration.largestPosition,
      threshold: limits.maxSingleAssetExposure,
    });
  }
  
  // Leverage warning
  if (exposure.leverageRatio > limits.maxLeverage * 0.8) {
    warnings.push({
      type: 'LEVERAGE',
      severity: exposure.leverageRatio > limits.maxLeverage ? 'CRITICAL' : 'WARNING',
      message: `Leverage ratio ${exposure.leverageRatio.toFixed(2)}x approaching limit`,
      value: exposure.leverageRatio,
      threshold: limits.maxLeverage,
    });
  }
  
  // Correlation warning
  if (correlation.atRisk) {
    for (const { pair, combinedWeight } of correlation.correlatedPairs) {
      warnings.push({
        type: 'CORRELATION',
        severity: combinedWeight > limits.maxCorrelatedExposure * 1.3 ? 'CRITICAL' : 'WARNING',
        message: `High correlation (${(pair.correlation * 100).toFixed(0)}%) between ${pair.asset1} and ${pair.asset2}`,
        value: combinedWeight,
        threshold: limits.maxCorrelatedExposure,
      });
    }
  }
  
  // Drawdown warning
  if (drawdown.current > limits.maxDrawdown * 0.7) {
    warnings.push({
      type: 'DRAWDOWN',
      severity: drawdown.current > limits.maxDrawdown ? 'CRITICAL' : 'WARNING',
      message: `Drawdown ${(drawdown.current * 100).toFixed(1)}% approaching limit`,
      value: drawdown.current,
      threshold: limits.maxDrawdown,
    });
  }
  
  // Position count
  if (state.positionCount >= limits.maxPositions) {
    warnings.push({
      type: 'EXPOSURE',
      severity: 'WARNING',
      message: `Max positions (${limits.maxPositions}) reached`,
      value: state.positionCount,
      threshold: limits.maxPositions,
    });
  }
  
  return warnings;
}

// ═══════════════════════════════════════════════════════════════
// MAIN RISK FUNCTION
// ═══════════════════════════════════════════════════════════════

/**
 * Get comprehensive portfolio risk assessment
 */
export function getPortfolioRisk(): PortfolioRisk {
  const state = getPortfolioState();
  const exposure = getExposureState();
  const limits = getPortfolioLimits();
  const concentration = calculateConcentration();
  const drawdown = updateDrawdown(state.totalValue);
  const var_ = calculateVaR(state.totalValue, exposure.leverageRatio);
  const warnings = generateWarnings();
  
  // Calculate composite risk score (0-1)
  let riskScore = 0;
  
  // Leverage contribution (0-0.25)
  riskScore += Math.min(exposure.leverageRatio / limits.maxLeverage, 1) * 0.25;
  
  // Concentration contribution (0-0.25)
  riskScore += Math.min(concentration.herfindahl * 2, 1) * 0.25;
  
  // Drawdown contribution (0-0.25)
  riskScore += Math.min(drawdown.current / limits.maxDrawdown, 1) * 0.25;
  
  // Warning contribution (0-0.25)
  const criticalWarnings = warnings.filter(w => w.severity === 'CRITICAL').length;
  riskScore += Math.min(criticalWarnings / 3, 1) * 0.25;
  
  // Determine risk level
  let riskLevel: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  if (riskScore < 0.25) riskLevel = 'LOW';
  else if (riskScore < 0.50) riskLevel = 'MODERATE';
  else if (riskScore < 0.75) riskLevel = 'HIGH';
  else riskLevel = 'CRITICAL';
  
  return {
    var95: var_.var95,
    var99: var_.var99,
    currentDrawdown: drawdown.current,
    maxDrawdown: drawdown.max,
    drawdownDuration: drawdown.duration,
    concentrationRisk: concentration.herfindahl,
    largestPosition: concentration.largestPosition,
    effectiveLeverage: Math.round(exposure.leverageRatio * 100) / 100,
    maxAllowedLeverage: limits.maxLeverage,
    leverageUtilization: Math.round((exposure.leverageRatio / limits.maxLeverage) * 10000) / 10000,
    riskScore: Math.round(riskScore * 100) / 100,
    riskLevel,
    warnings,
    lastUpdated: Date.now(),
  };
}

/**
 * Reset risk tracking (e.g., after significant portfolio change)
 */
export function resetRiskTracking(newPeakValue?: number): void {
  peakValue = newPeakValue || 100000;
  maxDrawdown = 0;
  drawdownStartDate = null;
}
