/**
 * Probability Weights (P4.2)
 * 
 * Dynamic weight calculation based on data quality
 */

import type { 
  MLProbabilityInput, 
  ScenarioProbabilityInput, 
  PriorsProbabilityInput,
  CompositionWeights 
} from './probability.types.js';

/**
 * Calculate ML weight based on model quality
 */
export function calcMLWeight(ml: MLProbabilityInput | null): number {
  if (!ml) return 0;
  
  // Base weight
  let weight = 0.3;
  
  // Increase if confidence is high
  if (ml.confidence > 0.7) weight += 0.1;
  if (ml.confidence > 0.85) weight += 0.1;
  
  // Model ID present means registered model
  if (ml.modelId) weight += 0.05;
  
  return Math.min(0.5, weight);
}

/**
 * Calculate Scenario weight based on MC quality
 */
export function calcScenarioWeight(scenario: ScenarioProbabilityInput | null): number {
  if (!scenario) return 0;
  
  // Base weight
  let weight = 0.3;
  
  // More paths = more reliable
  if (scenario.paths && scenario.paths >= 1000) weight += 0.1;
  if (scenario.paths && scenario.paths >= 5000) weight += 0.05;
  
  // Consistency check: if bands are too wide, reduce weight
  const bandWidth = (scenario.p90 - scenario.p10) / scenario.p50;
  if (bandWidth < 0.5) weight += 0.05;
  
  return Math.min(0.45, weight);
}

/**
 * Calculate Priors weight based on sample size
 */
export function calcPriorsWeight(priors: PriorsProbabilityInput | null): number {
  if (!priors) return 0;
  
  // Base weight
  let weight = 0.15;
  
  // Sample size reliability
  if (priors.sampleSize >= 50) weight += 0.05;
  if (priors.sampleSize >= 100) weight += 0.05;
  if (priors.sampleSize >= 200) weight += 0.05;
  
  // Profit factor indicates reliable pattern
  if (priors.profitFactor > 1.2) weight += 0.05;
  
  return Math.min(0.35, weight);
}

/**
 * Calculate composition weights
 */
export function calculateWeights(
  ml: MLProbabilityInput | null,
  scenario: ScenarioProbabilityInput | null,
  priors: PriorsProbabilityInput | null
): CompositionWeights {
  const mlWeight = calcMLWeight(ml);
  const scenarioWeight = calcScenarioWeight(scenario);
  const priorsWeight = calcPriorsWeight(priors);
  
  // Normalize to sum to 1
  const total = mlWeight + scenarioWeight + priorsWeight;
  
  if (total === 0) {
    // Fallback: equal weights
    return { ml: 0.33, scenario: 0.33, priors: 0.34 };
  }
  
  return {
    ml: mlWeight / total,
    scenario: scenarioWeight / total,
    priors: priorsWeight / total
  };
}

/**
 * Apply stability damping to weights
 */
export function applyStabilityDamping(
  weights: CompositionWeights,
  stabilityMultiplier: number
): CompositionWeights {
  // If stability is degrading, reduce priors weight
  if (stabilityMultiplier < 0.8) {
    const reduction = (1 - stabilityMultiplier) * 0.5;
    const priorsReduction = weights.priors * reduction;
    
    return {
      ml: weights.ml + priorsReduction * 0.6,
      scenario: weights.scenario + priorsReduction * 0.4,
      priors: weights.priors - priorsReduction
    };
  }
  
  return weights;
}
