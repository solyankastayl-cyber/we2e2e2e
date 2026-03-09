/**
 * MM1 — Memory Feature Vector
 * 
 * Builds feature vectors for similarity search
 */

import {
  MarketMemorySnapshot,
  REGIME_ENCODING,
  STATE_ENCODING,
  PHYSICS_ENCODING,
  LIQUIDITY_ENCODING,
  DEFAULT_MEMORY_CONFIG,
  MemoryConfig
} from './memory.types.js';

// ═══════════════════════════════════════════════════════════════
// VECTOR BUILDER
// ═══════════════════════════════════════════════════════════════

/**
 * Build feature vector from memory snapshot
 * 
 * Vector structure (16 dimensions):
 * [0] regime encoded
 * [1] state encoded
 * [2] physics encoded
 * [3] liquidity encoded
 * [4] scenario encoded (hash-based)
 * [5] energy
 * [6] instability
 * [7] confidence
 * [8] regime * energy
 * [9] state * instability
 * [10] physics * confidence
 * [11] liquidity * energy
 * [12] regime weight
 * [13] state weight
 * [14] physics weight
 * [15] combined score
 */
export function buildFeatureVector(
  snapshot: MarketMemorySnapshot,
  config: MemoryConfig = DEFAULT_MEMORY_CONFIG
): number[] {
  // Encode categorical fields
  const regimeVal = REGIME_ENCODING[snapshot.regime] || 0.5;
  const stateVal = STATE_ENCODING[snapshot.marketState] || 0.5;
  const physicsVal = PHYSICS_ENCODING[snapshot.physicsState] || 0.5;
  const liquidityVal = LIQUIDITY_ENCODING[snapshot.liquidityState] || 0.5;
  const scenarioVal = encodeScenario(snapshot.dominantScenario);
  
  // Normalize metrics
  const energy = clamp(snapshot.energy, 0, 1);
  const instability = clamp(snapshot.instability, 0, 1);
  const confidence = clamp(snapshot.confidence, 0, 1);
  
  // Build vector with cross-features
  const vector: number[] = [
    regimeVal,                           // [0]
    stateVal,                            // [1]
    physicsVal,                          // [2]
    liquidityVal,                        // [3]
    scenarioVal,                         // [4]
    energy,                              // [5]
    instability,                         // [6]
    confidence,                          // [7]
    regimeVal * energy,                  // [8] Cross: regime-energy
    stateVal * instability,              // [9] Cross: state-instability
    physicsVal * confidence,             // [10] Cross: physics-confidence
    liquidityVal * energy,               // [11] Cross: liquidity-energy
    regimeVal * config.vectorWeights.regime,      // [12] Weighted regime
    stateVal * config.vectorWeights.state,        // [13] Weighted state
    physicsVal * config.vectorWeights.physics,    // [14] Weighted physics
    calculateCombinedScore(regimeVal, stateVal, physicsVal, energy, confidence) // [15]
  ];
  
  return vector;
}

/**
 * Encode scenario name to numeric value
 */
function encodeScenario(scenario: string): number {
  if (!scenario) return 0.5;
  
  // Simple hash-based encoding
  const scenarios: Record<string, number> = {
    'CLASSIC_BREAKOUT': 0.15,
    'FALSE_BREAKOUT': 0.25,
    'SWEEP_REVERSAL': 0.35,
    'RANGE_CONTINUATION': 0.45,
    'COMPRESSION_BREAKOUT': 0.55,
    'LIQUIDITY_HUNT': 0.65,
    'TREND_CONTINUATION': 0.75,
    'EXHAUSTION_REVERSAL': 0.85
  };
  
  return scenarios[scenario] || hashToNumber(scenario);
}

/**
 * Hash string to number (0-1)
 */
function hashToNumber(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash % 1000) / 1000;
}

/**
 * Calculate combined score
 */
function calculateCombinedScore(
  regime: number,
  state: number,
  physics: number,
  energy: number,
  confidence: number
): number {
  return (regime + state + physics + energy + confidence) / 5;
}

function clamp(value: number, min: number, max: number): number {
  if (isNaN(value)) return (min + max) / 2;
  return Math.max(min, Math.min(max, value));
}

// ═══════════════════════════════════════════════════════════════
// SIMILARITY CALCULATIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate cosine similarity between two vectors
 */
export function cosineSimilarity(vec1: number[], vec2: number[]): number {
  if (vec1.length !== vec2.length) {
    // Pad shorter vector
    const maxLen = Math.max(vec1.length, vec2.length);
    while (vec1.length < maxLen) vec1.push(0);
    while (vec2.length < maxLen) vec2.push(0);
  }
  
  let dotProduct = 0;
  let norm1 = 0;
  let norm2 = 0;
  
  for (let i = 0; i < vec1.length; i++) {
    dotProduct += vec1[i] * vec2[i];
    norm1 += vec1[i] * vec1[i];
    norm2 += vec2[i] * vec2[i];
  }
  
  const magnitude = Math.sqrt(norm1) * Math.sqrt(norm2);
  if (magnitude === 0) return 0;
  
  return dotProduct / magnitude;
}

/**
 * Calculate euclidean distance between two vectors
 */
export function euclideanDistance(vec1: number[], vec2: number[]): number {
  if (vec1.length !== vec2.length) {
    const maxLen = Math.max(vec1.length, vec2.length);
    while (vec1.length < maxLen) vec1.push(0);
    while (vec2.length < maxLen) vec2.push(0);
  }
  
  let sum = 0;
  for (let i = 0; i < vec1.length; i++) {
    const diff = vec1[i] - vec2[i];
    sum += diff * diff;
  }
  
  return Math.sqrt(sum);
}

/**
 * Calculate weighted similarity (cosine + euclidean blend)
 */
export function weightedSimilarity(
  vec1: number[],
  vec2: number[],
  cosineWeight: number = 0.7
): number {
  const cosine = cosineSimilarity(vec1, vec2);
  const euclidean = euclideanDistance(vec1, vec2);
  
  // Convert euclidean to similarity (inverse normalized)
  const maxDistance = Math.sqrt(vec1.length);  // Max possible distance
  const euclideanSim = 1 - (euclidean / maxDistance);
  
  return cosine * cosineWeight + euclideanSim * (1 - cosineWeight);
}
