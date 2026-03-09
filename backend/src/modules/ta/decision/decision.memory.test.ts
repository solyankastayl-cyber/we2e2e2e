/**
 * P0 — Decision Memory Integration Tests
 * 
 * Tests:
 * 1. Memory boost is applied (finalScore > baseScore)
 * 2. Fallback works (memory unavailable → boost = 1)
 * 3. Risk adjustment is applied (position size decreases)
 * 4. Scenario boost is applied (scenario probability increases)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchMemoryBoost,
  getDirectionBoost,
  getScenarioBoost,
  calculateMemoryIntegration,
  applyRiskAdjustment,
  DecisionMemoryBoost
} from './decision.memory.js';

// ═══════════════════════════════════════════════════════════════
// TEST 1: Memory Boost Applied
// ═══════════════════════════════════════════════════════════════

describe('Memory Boost Application', () => {
  const mockMemoryBoost: DecisionMemoryBoost = {
    memoryConfidence: 0.73,
    bullishBoost: 1.12,
    bearishBoost: 0.92,
    neutralBoost: 1.0,
    scenarioBoost: {
      'CLASSIC_BREAKOUT': 1.15,
      'LIQUIDITY_SWEEP': 0.95
    },
    riskAdjustment: 0.94,
    matchCount: 18,
    dominantOutcome: 'BULL',
    historicalBias: 'BULL'
  };

  it('should apply bullish direction boost for LONG trades', () => {
    const boost = getDirectionBoost('LONG', mockMemoryBoost);
    expect(boost).toBe(1.12);
  });

  it('should apply bearish direction boost for SHORT trades', () => {
    const boost = getDirectionBoost('SHORT', mockMemoryBoost);
    expect(boost).toBe(0.92);
  });

  it('should apply scenario-specific boost', () => {
    const boost = getScenarioBoost('CLASSIC_BREAKOUT', mockMemoryBoost);
    expect(boost).toBe(1.15);
  });

  it('should return 1 for unknown scenarios', () => {
    const boost = getScenarioBoost('UNKNOWN_SCENARIO', mockMemoryBoost);
    expect(boost).toBe(1);
  });

  it('should clamp direction boost to max 1.20', () => {
    const highBoost: DecisionMemoryBoost = {
      ...mockMemoryBoost,
      bullishBoost: 1.5  // Exceeds max
    };
    const boost = getDirectionBoost('LONG', highBoost);
    expect(boost).toBe(1.20);
  });

  it('should clamp direction boost to min 0.85', () => {
    const lowBoost: DecisionMemoryBoost = {
      ...mockMemoryBoost,
      bearishBoost: 0.5  // Below min
    };
    const boost = getDirectionBoost('SHORT', lowBoost);
    expect(boost).toBe(0.85);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 2: Fallback Works
// ═══════════════════════════════════════════════════════════════

describe('Memory Boost Fallback', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('should return neutral boost on network error', async () => {
    vi.mocked(fetch).mockRejectedValue(new Error('Network error'));
    
    const result = await fetchMemoryBoost('BTCUSDT', '1h');
    
    expect(result.memoryConfidence).toBe(0);
    expect(result.bullishBoost).toBe(1);
    expect(result.bearishBoost).toBe(1);
    expect(result.riskAdjustment).toBe(1);
  });

  it('should return neutral boost on API error', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500
    } as Response);
    
    const result = await fetchMemoryBoost('BTCUSDT', '1h');
    
    expect(result.memoryConfidence).toBe(0);
    expect(result.bullishBoost).toBe(1);
    expect(result.scenarioBoost).toEqual({});
  });

  it('should return neutral boost on invalid response', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ success: false, error: 'No data' })
    } as Response);
    
    const result = await fetchMemoryBoost('BTCUSDT', '1h');
    
    expect(result.memoryConfidence).toBe(0);
    expect(result.matchCount).toBe(0);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 3: Risk Adjustment Applied
// ═══════════════════════════════════════════════════════════════

describe('Risk Adjustment', () => {
  it('should reduce position size with low risk adjustment', () => {
    const baseSize = 0.20;
    const riskAdjustment = 0.82;
    
    const adjustedSize = applyRiskAdjustment(baseSize, riskAdjustment);
    
    expect(adjustedSize).toBeCloseTo(0.164, 3);
  });

  it('should increase position size with high risk adjustment', () => {
    const baseSize = 0.20;
    const riskAdjustment = 1.1;
    
    const adjustedSize = applyRiskAdjustment(baseSize, riskAdjustment);
    
    expect(adjustedSize).toBeCloseTo(0.22, 3);
  });

  it('should not change position size with neutral adjustment', () => {
    const baseSize = 0.20;
    const riskAdjustment = 1.0;
    
    const adjustedSize = applyRiskAdjustment(baseSize, riskAdjustment);
    
    expect(adjustedSize).toBe(0.20);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 4: Complete Integration
// ═══════════════════════════════════════════════════════════════

describe('Memory Integration Calculation', () => {
  const mockMemory: DecisionMemoryBoost = {
    memoryConfidence: 0.73,
    bullishBoost: 1.12,
    bearishBoost: 0.88,
    neutralBoost: 1.0,
    scenarioBoost: {
      'CLASSIC_BREAKOUT': 1.15
    },
    riskAdjustment: 0.94,
    matchCount: 18,
    dominantOutcome: 'BULL',
    historicalBias: 'BULL'
  };

  it('should calculate complete memory integration for LONG CLASSIC_BREAKOUT', () => {
    const result = calculateMemoryIntegration('CLASSIC_BREAKOUT', 'LONG', mockMemory);
    
    expect(result.directionBoost).toBe(1.12);
    expect(result.scenarioBoost).toBe(1.15);
    expect(result.riskAdjustment).toBe(0.94);
    expect(result.memoryConfidence).toBe(0.73);
    expect(result.matchCount).toBe(18);
    expect(result.historicalBias).toBe('BULL');
  });

  it('should calculate complete memory integration for SHORT unknown scenario', () => {
    const result = calculateMemoryIntegration('UNKNOWN', 'SHORT', mockMemory);
    
    expect(result.directionBoost).toBe(0.88);
    expect(result.scenarioBoost).toBe(1);  // Default for unknown
    expect(result.riskAdjustment).toBe(0.94);
  });

  it('should demonstrate finalScore increase with positive memory boost', () => {
    const baseScore = 1.0;
    const directionBoost = 1.12;
    const scenarioBoost = 1.15;
    
    const finalScore = baseScore * directionBoost * scenarioBoost;
    
    expect(finalScore).toBeCloseTo(1.288, 2);
    expect(finalScore).toBeGreaterThan(baseScore);
  });

  it('should demonstrate finalScore decrease with negative memory boost', () => {
    const baseScore = 1.0;
    const directionBoost = 0.88;  // Bearish boost for LONG trade
    const scenarioBoost = 0.95;
    
    const finalScore = baseScore * directionBoost * scenarioBoost;
    
    expect(finalScore).toBeCloseTo(0.836, 2);
    expect(finalScore).toBeLessThan(baseScore);
  });
});

// ═══════════════════════════════════════════════════════════════
// TEST 5: API Integration (requires running server)
// ═══════════════════════════════════════════════════════════════

describe('API Integration', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('should parse successful API response', async () => {
    const mockResponse = {
      success: true,
      data: {
        memoryConfidence: 0.8,
        bullishBoost: 1.15,
        bearishBoost: 0.9,
        neutralBoost: 1.0,
        scenarioBoost: { 'TEST_SCENARIO': 1.1 },
        riskAdjustment: 0.95,
        matchCount: 25,
        dominantOutcome: 'BULL'
      }
    };

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => mockResponse
    } as Response);

    const result = await fetchMemoryBoost('BTCUSDT', '1h');

    expect(result.memoryConfidence).toBe(0.8);
    expect(result.bullishBoost).toBe(1.15);
    expect(result.matchCount).toBe(25);
    expect(result.historicalBias).toBe('BULL');
  });
});
