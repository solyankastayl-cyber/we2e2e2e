/**
 * P0.1 — Decision Explain API Tests
 * 
 * Tests:
 * 1. Endpoint works
 * 2. Returns breakdown
 * 3. Memory boost present
 * 4. Learning weights present
 * 5. Execution sizing correct
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  buildExplainFromSnapshot,
  buildPipelineStages,
  DecisionSnapshot,
  ScoreBreakdown
} from './decision.explain.js';
import { LearningWeightMap } from '../../metabrain_learning/learning.integration.js';

// ═══════════════════════════════════════════════════════════════
// TEST DATA
// ═══════════════════════════════════════════════════════════════

const mockSnapshot: DecisionSnapshot = {
  asset: 'BTCUSDT',
  timeframe: '1d',
  ts: Date.now(),
  scenarioId: 'CLASSIC_BREAKOUT',
  patternType: 'BREAKOUT',
  direction: 'BULL',
  baseEV: 0.54,
  boosts: {
    pattern: 1.02,
    liquidity: 1.08,
    physics: 0.97,
    state: 1.03,
    regime: 1.04,
    graph: 1.05,
    geometry: 1.01
  },
  edgeMultiplier: 1.11,
  learningWeight: 1.06,
  memory: {
    directionBoost: 1.06,
    scenarioBoost: 1.00,
    riskAdjustment: 0.93,
    confidence: 0.70,
    matches: 30
  },
  finalScore: 0.69,
  createdAt: new Date()
};

const mockLearningWeights: LearningWeightMap = {
  pattern: 1.02,
  liquidity: 1.08,
  graph: 1.05,
  fractal: 1.0,
  physics: 0.97,
  state: 1.03,
  regime: 1.04,
  scenario: 1.0
};

// ═══════════════════════════════════════════════════════════════
// TEST 1: Build Explain From Snapshot
// ═══════════════════════════════════════════════════════════════

describe('Build Explain From Snapshot', () => {
  it('should build explain result from snapshot', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    expect(result.asset).toBe('BTCUSDT');
    expect(result.timeframe).toBe('1d');
    expect(result.scenario).toBe('CLASSIC_BREAKOUT');
    expect(result.direction).toBe('BULL');
  });

  it('should include score breakdown', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    expect(result.scoreBreakdown.baseEV).toBe(0.54);
    expect(result.scoreBreakdown.patternBoost).toBe(1.02);
    expect(result.scoreBreakdown.physicsBoost).toBe(0.97);
    expect(result.scoreBreakdown.edgeMultiplier).toBe(1.11);
    expect(result.scoreBreakdown.finalScore).toBe(0.69);
  });

  it('should include memory boost in breakdown', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    expect(result.scoreBreakdown.memoryBoost.directionBoost).toBe(1.06);
    expect(result.scoreBreakdown.memoryBoost.scenarioBoost).toBe(1.00);
  });

  it('should include memory context', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    expect(result.memoryContext.confidence).toBe(0.70);
    expect(result.memoryContext.matches).toBe(30);
    expect(result.memoryContext.riskAdjustment).toBe(0.93);
    expect(result.memoryContext.historicalBias).toBe('BULL');
  });

  it('should include execution plan', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    expect(result.executionPlan.baseSize).toBe(0.20);
    expect(result.executionPlan.riskAdjustment).toBe(0.93);
    expect(result.executionPlan.finalSize).toBeCloseTo(0.186, 2);
  });

  it('should include learning weights', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    expect(result.learningWeights.pattern).toBe(1.02);
    expect(result.learningWeights.physics).toBe(0.97);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 2: Score Breakdown Structure
// ═══════════════════════════════════════════════════════════════

describe('Score Breakdown Structure', () => {
  it('should have all required boost fields', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    const breakdown = result.scoreBreakdown;
    
    expect(breakdown).toHaveProperty('baseEV');
    expect(breakdown).toHaveProperty('patternBoost');
    expect(breakdown).toHaveProperty('liquidityBoost');
    expect(breakdown).toHaveProperty('physicsBoost');
    expect(breakdown).toHaveProperty('stateBoost');
    expect(breakdown).toHaveProperty('regimeBoost');
    expect(breakdown).toHaveProperty('graphBoost');
    expect(breakdown).toHaveProperty('geometryBoost');
    expect(breakdown).toHaveProperty('edgeMultiplier');
    expect(breakdown).toHaveProperty('learningWeight');
    expect(breakdown).toHaveProperty('memoryBoost');
    expect(breakdown).toHaveProperty('finalScore');
  });

  it('should have EV stages', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    const breakdown = result.scoreBreakdown;
    
    expect(breakdown).toHaveProperty('evAfterML');
    expect(breakdown).toHaveProperty('evAfterEdge');
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 3: Pipeline Stages
// ═══════════════════════════════════════════════════════════════

describe('Pipeline Stages', () => {
  it('should build pipeline stages', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    expect(result.pipelineStages).toBeDefined();
    expect(Array.isArray(result.pipelineStages)).toBe(true);
    expect(result.pipelineStages.length).toBeGreaterThan(0);
  });

  it('should have correct stage structure', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    const stage = result.pipelineStages[0];
    
    expect(stage).toHaveProperty('stage');
    expect(stage).toHaveProperty('input');
    expect(stage).toHaveProperty('output');
    expect(stage).toHaveProperty('boost');
    expect(stage).toHaveProperty('description');
  });

  it('should include Market Memory stage', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    const memoryStage = result.pipelineStages.find(s => s.stage === 'Market Memory');
    expect(memoryStage).toBeDefined();
    expect(memoryStage?.description).toContain('30 historical matches');
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 4: Execution Sizing
// ═══════════════════════════════════════════════════════════════

describe('Execution Sizing', () => {
  it('should calculate correct final size', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    const expectedSize = 0.20 * 0.93; // baseSize * riskAdjustment
    expect(result.executionPlan.finalSize).toBeCloseTo(expectedSize, 3);
  });

  it('should include all multipliers', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    const multipliers = result.executionPlan.multipliers;
    
    expect(multipliers).toHaveProperty('confidence');
    expect(multipliers).toHaveProperty('edge');
    expect(multipliers).toHaveProperty('regime');
    expect(multipliers).toHaveProperty('memory');
  });

  it('should apply memory risk adjustment', () => {
    const result = buildExplainFromSnapshot(mockSnapshot, mockLearningWeights);
    
    expect(result.executionPlan.riskAdjustment).toBe(0.93);
    expect(result.executionPlan.finalSize).toBeLessThan(result.executionPlan.baseSize);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 5: Historical Bias Detection
// ═══════════════════════════════════════════════════════════════

describe('Historical Bias Detection', () => {
  it('should detect BULL bias when directionBoost > 1', () => {
    const bullSnapshot = { ...mockSnapshot, memory: { ...mockSnapshot.memory, directionBoost: 1.15 } };
    const result = buildExplainFromSnapshot(bullSnapshot, mockLearningWeights);
    
    expect(result.memoryContext.historicalBias).toBe('BULL');
  });

  it('should detect BEAR bias when directionBoost < 1', () => {
    const bearSnapshot = { ...mockSnapshot, memory: { ...mockSnapshot.memory, directionBoost: 0.85 } };
    const result = buildExplainFromSnapshot(bearSnapshot, mockLearningWeights);
    
    expect(result.memoryContext.historicalBias).toBe('BEAR');
  });

  it('should detect NEUTRAL bias when directionBoost = 1', () => {
    const neutralSnapshot = { ...mockSnapshot, memory: { ...mockSnapshot.memory, directionBoost: 1.0 } };
    const result = buildExplainFromSnapshot(neutralSnapshot, mockLearningWeights);
    
    expect(result.memoryContext.historicalBias).toBe('NEUTRAL');
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 6: Edge Cases
// ═══════════════════════════════════════════════════════════════

describe('Edge Cases', () => {
  it('should handle zero memory confidence', () => {
    const zeroConfSnapshot = { 
      ...mockSnapshot, 
      memory: { ...mockSnapshot.memory, confidence: 0, matches: 0 } 
    };
    const result = buildExplainFromSnapshot(zeroConfSnapshot, mockLearningWeights);
    
    expect(result.memoryContext.confidence).toBe(0);
    expect(result.memoryContext.matches).toBe(0);
  });

  it('should handle neutral boosts', () => {
    const neutralSnapshot = { 
      ...mockSnapshot, 
      boosts: { pattern: 1, liquidity: 1, physics: 1, state: 1, regime: 1, graph: 1, geometry: 1 },
      edgeMultiplier: 1,
      memory: { directionBoost: 1, scenarioBoost: 1, riskAdjustment: 1, confidence: 0, matches: 0 }
    };
    const result = buildExplainFromSnapshot(neutralSnapshot, mockLearningWeights);
    
    expect(result.scoreBreakdown.patternBoost).toBe(1);
    expect(result.scoreBreakdown.edgeMultiplier).toBe(1);
  });
});
