/**
 * Market Memory Engine — Tests
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import {
  buildMemorySnapshot,
  buildMemorySnapshotFromRaw,
  buildFeatureVector,
  cosineSimilarity,
  euclideanDistance,
  weightedSimilarity,
  searchSimilarSnapshotsInMemory,
  summarizeMemoryMatches,
  buildMemoryBoost,
  applyMemoryBoostToScenario,
  MarketMemorySnapshot,
  MemoryMatch,
  DEFAULT_MEMORY_CONFIG
} from './index.js';
import { buildMockTwinContext } from '../digital_twin/digital_twin.context.js';
import { buildDigitalTwinState } from '../digital_twin/digital_twin.state.js';

// ═══════════════════════════════════════════════════════════════
// TEST DATA
// ═══════════════════════════════════════════════════════════════

function createMockSnapshot(overrides?: Partial<MarketMemorySnapshot>): MarketMemorySnapshot {
  const base: MarketMemorySnapshot = {
    snapshotId: `MEM_TEST_${Math.random().toString(36).substring(7)}`,
    asset: 'BTCUSDT',
    timeframe: '1d',
    ts: Date.now(),
    regime: 'COMPRESSION',
    marketState: 'COMPRESSION',
    physicsState: 'COMPRESSION',
    liquidityState: 'NEUTRAL',
    dominantScenario: 'CLASSIC_BREAKOUT',
    energy: 0.7,
    instability: 0.3,
    confidence: 0.65,
    featureVector: [],
    createdAt: new Date()
  };
  
  const snapshot = { ...base, ...overrides };
  snapshot.featureVector = buildFeatureVector(snapshot);
  
  return snapshot;
}

function createMockHistoricalSnapshots(count: number = 20): MarketMemorySnapshot[] {
  const regimes = ['COMPRESSION', 'BREAKOUT_PREP', 'TREND_EXPANSION'];
  const states = ['COMPRESSION', 'BREAKOUT_ATTEMPT', 'BREAKOUT'];
  const directions: Array<'BULL' | 'BEAR' | 'NEUTRAL'> = ['BULL', 'BEAR', 'NEUTRAL'];
  
  const snapshots: MarketMemorySnapshot[] = [];
  
  for (let i = 0; i < count; i++) {
    const snapshot = createMockSnapshot({
      snapshotId: `MEM_HIST_${i}`,
      regime: regimes[i % regimes.length] as MarketMemorySnapshot['regime'],
      marketState: states[i % states.length] as MarketMemorySnapshot['marketState'],
      energy: 0.5 + Math.random() * 0.4,
      instability: 0.2 + Math.random() * 0.5,
      confidence: 0.4 + Math.random() * 0.4
    });
    
    // Add outcome
    snapshot.outcome = {
      direction: directions[i % directions.length],
      moveATR: 0.5 + Math.random() * 2.5,
      scenarioResolved: ['CLASSIC_BREAKOUT', 'FALSE_BREAKOUT', 'RANGE_CONTINUATION'][i % 3],
      barsToResolution: 3 + Math.floor(Math.random() * 12)
    };
    snapshot.resolvedAt = new Date();
    
    snapshots.push(snapshot);
  }
  
  return snapshots;
}

// ═══════════════════════════════════════════════════════════════
// MM1 — SNAPSHOT TESTS
// ═══════════════════════════════════════════════════════════════

describe('MM1 - Memory Snapshot', () => {
  it('should build snapshot from Twin state', () => {
    const context = buildMockTwinContext('BTCUSDT', '1d');
    const twinState = buildDigitalTwinState(context);
    
    const snapshot = buildMemorySnapshot(twinState);
    
    expect(snapshot.snapshotId).toBeDefined();
    expect(snapshot.asset).toBe('BTCUSDT');
    expect(snapshot.regime).toBeDefined();
    expect(snapshot.featureVector.length).toBeGreaterThan(0);
  });
  
  it('should build snapshot from raw data', () => {
    const snapshot = buildMemorySnapshotFromRaw({
      asset: 'ETHUSDT',
      timeframe: '4h',
      ts: Date.now(),
      regime: 'TREND_EXPANSION',
      marketState: 'EXPANSION',
      physicsState: 'EXPANSION',
      liquidityState: 'NEUTRAL',
      dominantScenario: 'TREND_CONTINUATION',
      energy: 0.8,
      instability: 0.2,
      confidence: 0.75
    });
    
    expect(snapshot.snapshotId).toBeDefined();
    expect(snapshot.regime).toBe('TREND_EXPANSION');
    expect(snapshot.featureVector.length).toBeGreaterThan(0);
  });
});

// ═══════════════════════════════════════════════════════════════
// MM1 — VECTOR TESTS
// ═══════════════════════════════════════════════════════════════

describe('MM1 - Feature Vector', () => {
  it('should build feature vector with correct dimensions', () => {
    const snapshot = createMockSnapshot();
    const vector = buildFeatureVector(snapshot);
    
    expect(vector.length).toBe(16);
    expect(vector.every(v => !isNaN(v))).toBe(true);
  });
  
  it('should calculate cosine similarity', () => {
    const vec1 = [1, 2, 3, 4];
    const vec2 = [1, 2, 3, 4];
    const similarity = cosineSimilarity(vec1, vec2);
    
    expect(similarity).toBeCloseTo(1.0, 2);
  });
  
  it('should calculate euclidean distance', () => {
    const vec1 = [0, 0, 0];
    const vec2 = [1, 0, 0];
    const distance = euclideanDistance(vec1, vec2);
    
    expect(distance).toBe(1);
  });
  
  it('should calculate weighted similarity', () => {
    const snapshot1 = createMockSnapshot({ regime: 'COMPRESSION' });
    const snapshot2 = createMockSnapshot({ regime: 'COMPRESSION' });
    
    const similarity = weightedSimilarity(
      snapshot1.featureVector,
      snapshot2.featureVector
    );
    
    expect(similarity).toBeGreaterThan(0.8);
  });
});

// ═══════════════════════════════════════════════════════════════
// MM1 — SEARCH TESTS
// ═══════════════════════════════════════════════════════════════

describe('MM1 - Memory Search', () => {
  it('should find similar snapshots', () => {
    const current = createMockSnapshot({ regime: 'COMPRESSION' });
    const historical = createMockHistoricalSnapshots(20);
    
    const matches = searchSimilarSnapshotsInMemory(current, historical);
    
    expect(matches.length).toBeGreaterThan(0);
    expect(matches[0].similarity).toBeGreaterThanOrEqual(0.6);
  });
  
  it('should sort matches by similarity', () => {
    const current = createMockSnapshot();
    const historical = createMockHistoricalSnapshots(30);
    
    const matches = searchSimilarSnapshotsInMemory(current, historical);
    
    for (let i = 1; i < matches.length; i++) {
      expect(matches[i - 1].similarity).toBeGreaterThanOrEqual(matches[i].similarity);
    }
  });
  
  it('should summarize matches correctly', () => {
    const current = createMockSnapshot();
    const historical = createMockHistoricalSnapshots(30);
    const matches = searchSimilarSnapshotsInMemory(current, historical);
    
    const summary = summarizeMemoryMatches(matches);
    
    expect(summary.matches).toBeGreaterThan(0);
    expect(summary.bullRate + summary.bearRate + summary.neutralRate).toBeCloseTo(1, 1);
    expect(summary.memoryConfidence).toBeGreaterThanOrEqual(0);
    expect(summary.memoryConfidence).toBeLessThanOrEqual(1);
  });
});

// ═══════════════════════════════════════════════════════════════
// MM2 — BOOST TESTS
// ═══════════════════════════════════════════════════════════════

describe('MM2 - Memory Boost', () => {
  it('should build memory boost from matches', () => {
    const current = createMockSnapshot();
    const historical = createMockHistoricalSnapshots(30);
    const matches = searchSimilarSnapshotsInMemory(current, historical);
    const summary = summarizeMemoryMatches(matches);
    
    const boost = buildMemoryBoost(matches, summary);
    
    expect(boost.memoryConfidence).toBeGreaterThanOrEqual(0);
    expect(boost.bullishBoost).toBeGreaterThanOrEqual(0.85);
    expect(boost.bullishBoost).toBeLessThanOrEqual(1.20);
    expect(boost.riskAdjustment).toBeGreaterThan(0);
  });
  
  it('should apply boost to scenario probability', () => {
    const boost = {
      memoryConfidence: 0.7,
      bullishBoost: 1.15,
      bearishBoost: 0.85,
      neutralBoost: 1.0,
      scenarioBoost: {},
      riskAdjustment: 1.0,
      matchCount: 20,
      dominantOutcome: 'BULL' as const
    };
    
    const probability = 0.5;
    const adjusted = applyMemoryBoostToScenario(probability, 'BULL', boost);
    
    expect(adjusted).toBe(0.5 * 1.15);
    expect(adjusted).toBeGreaterThan(probability);
  });
  
  it('should return neutral boost when no matches', () => {
    const boost = buildMemoryBoost([], {
      matches: 0,
      avgSimilarity: 0,
      bullRate: 0.33,
      bearRate: 0.33,
      neutralRate: 0.34,
      avgMoveATR: 0,
      avgBarsToResolution: 0,
      dominantDirection: 'NEUTRAL',
      dominantResolvedScenario: 'UNKNOWN',
      memoryConfidence: 0
    });
    
    expect(boost.bullishBoost).toBe(1.0);
    expect(boost.bearishBoost).toBe(1.0);
    expect(boost.riskAdjustment).toBe(1.0);
  });
});

// ═══════════════════════════════════════════════════════════════
// FULL PIPELINE TESTS
// ═══════════════════════════════════════════════════════════════

describe('Market Memory - Full Pipeline', () => {
  it('should run complete memory analysis pipeline', () => {
    // 1. Build current snapshot
    const current = createMockSnapshot({ 
      regime: 'COMPRESSION',
      marketState: 'BREAKOUT_ATTEMPT',
      energy: 0.75
    });
    
    // 2. Create historical data
    const historical = createMockHistoricalSnapshots(50);
    
    // 3. Search
    const matches = searchSimilarSnapshotsInMemory(current, historical);
    expect(matches.length).toBeGreaterThan(0);
    
    // 4. Summarize
    const summary = summarizeMemoryMatches(matches);
    expect(summary.matches).toBeGreaterThan(0);
    
    // 5. Build boost
    const currentScenarios = [
      { scenarioId: 'CLASSIC_BREAKOUT', direction: 'BULL' as const },
      { scenarioId: 'FALSE_BREAKOUT', direction: 'BEAR' as const }
    ];
    
    const boost = buildMemoryBoost(matches, summary, currentScenarios);
    
    expect(boost.memoryConfidence).toBeGreaterThan(0);
    expect(Object.keys(boost.scenarioBoost).length).toBeGreaterThan(0);
  });
});
