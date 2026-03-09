/**
 * Phase 4.2 — Replay Engine Service
 * ===================================
 * Replays and simulates historical decisions
 */

import { v4 as uuidv4 } from 'uuid';
import {
  DecisionSnapshot,
  SnapshotContext,
  ReplayResult,
  ReplayDifference,
  CompareResult,
} from './replay.types.js';

// ═══════════════════════════════════════════════════════════════
// IN-MEMORY SNAPSHOT STORAGE
// ═══════════════════════════════════════════════════════════════

const snapshots: Map<string, DecisionSnapshot> = new Map();

// Seed demo snapshots
const seedSnapshots = () => {
  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
  const regimes = ['TREND_UP', 'TREND_DOWN', 'RANGE', 'EXPANSION'];
  const scenarios = ['BREAKOUT', 'REVERSAL', 'CONTINUATION', 'RANGE_BOUND'];
  const riskModes = ['NORMAL', 'CONSERVATIVE', 'AGGRESSIVE'];
  const basePrices: Record<string, number> = { BTCUSDT: 87000, ETHUSDT: 3200, SOLUSDT: 145 };
  
  const now = Date.now();
  
  for (let i = 0; i < 30; i++) {
    const symbol = symbols[i % symbols.length];
    const id = `snap_${uuidv4().slice(0, 8)}`;
    const signal = Math.random() > 0.3 ? (Math.random() > 0.5 ? 'LONG' : 'SHORT') : 'NO_TRADE';
    
    const snapshot: DecisionSnapshot = {
      id,
      decisionId: `dec_${uuidv4().slice(0, 8)}`,
      symbol,
      timestamp: now - (30 - i) * 3600000,
      context: {
        patternScore: Math.round(Math.random() * 0.8 * 100) / 100,
        patternType: 'ELLIOTT_5_WAVE',
        liquidityScore: Math.round(Math.random() * 0.9 * 100) / 100,
        liquiditySweep: Math.random() > 0.6,
        regime: regimes[Math.floor(Math.random() * regimes.length)],
        regimeStrength: Math.round((0.5 + Math.random() * 0.5) * 100) / 100,
        scenarioProbability: Math.round((0.3 + Math.random() * 0.6) * 100) / 100,
        scenarioType: scenarios[Math.floor(Math.random() * scenarios.length)],
        memoryBoost: Math.round((0.9 + Math.random() * 0.3) * 100) / 100,
        memoryMatches: Math.floor(Math.random() * 25),
        memoryBias: Math.random() > 0.5 ? 'BULL' : 'BEAR',
        graphBoost: Math.round((0.95 + Math.random() * 0.15) * 100) / 100,
        physicsScore: Math.round(Math.random() * 0.7 * 100) / 100,
        riskMode: riskModes[Math.floor(Math.random() * riskModes.length)],
        moduleWeights: { ta: 1.0, liquidity: 0.9, memory: 0.8, scenario: 1.0 },
      },
      decision: {
        signal: signal as any,
        score: Math.round((0.4 + Math.random() * 0.5) * 100) / 100,
        confidence: Math.round((0.5 + Math.random() * 0.4) * 100) / 100,
      },
      marketState: {
        price: basePrices[symbol] * (0.95 + Math.random() * 0.1),
        regime: regimes[Math.floor(Math.random() * regimes.length)],
        volatility: Math.round((0.01 + Math.random() * 0.04) * 1000) / 1000,
        volume: Math.floor(1000000 + Math.random() * 5000000),
      },
    };
    
    snapshots.set(id, snapshot);
  }
};

seedSnapshots();

// ═══════════════════════════════════════════════════════════════
// SNAPSHOT FUNCTIONS
// ═══════════════════════════════════════════════════════════════

export function saveSnapshot(
  decisionId: string,
  symbol: string,
  context: SnapshotContext,
  decision: DecisionSnapshot['decision'],
  marketState: DecisionSnapshot['marketState']
): DecisionSnapshot {
  const snapshot: DecisionSnapshot = {
    id: `snap_${uuidv4().slice(0, 8)}`,
    decisionId,
    symbol,
    timestamp: Date.now(),
    context,
    decision,
    marketState,
  };
  
  snapshots.set(snapshot.id, snapshot);
  if (snapshots.size > 500) {
    const oldest = [...snapshots.keys()][0];
    snapshots.delete(oldest);
  }
  
  return snapshot;
}

export function getSnapshot(id: string): DecisionSnapshot | null {
  return snapshots.get(id) || null;
}

export function getSnapshots(options: { symbol?: string; limit?: number } = {}): DecisionSnapshot[] {
  let results = [...snapshots.values()];
  if (options.symbol) results = results.filter(s => s.symbol === options.symbol);
  results.sort((a, b) => b.timestamp - a.timestamp);
  return results.slice(0, options.limit || 50);
}

// ═══════════════════════════════════════════════════════════════
// REPLAY FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function simulateDecision(context: SnapshotContext): { signal: string; score: number } {
  const weights = { pattern: 0.25, liquidity: 0.20, scenario: 0.30, memory: 0.15, physics: 0.10 };
  
  let score = 0;
  score += context.patternScore * weights.pattern;
  score += context.liquidityScore * weights.liquidity;
  score += context.scenarioProbability * weights.scenario;
  score += (context.memoryBoost - 0.9) * 3 * weights.memory;
  score += (context.physicsScore || 0) * weights.physics;
  
  if (context.regime === 'TREND_UP' || context.regime === 'EXPANSION') score *= 1.1;
  else if (context.regime === 'RANGE') score *= 0.85;
  
  if (context.riskMode === 'CONSERVATIVE') score *= 0.9;
  else if (context.riskMode === 'AGGRESSIVE') score *= 1.1;
  
  score = Math.round(Math.min(1, Math.max(0, score)) * 100) / 100;
  
  let signal = 'NO_TRADE';
  if (score >= 0.6) signal = context.memoryBias === 'BULL' ? 'LONG' : 'SHORT';
  else if (score >= 0.5) signal = Math.random() > 0.5 ? 'LONG' : 'SHORT';
  
  return { signal, score };
}

export function replaySnapshot(snapshotId: string): ReplayResult | null {
  const snapshot = snapshots.get(snapshotId);
  if (!snapshot) return null;
  
  const replayed = simulateDecision(snapshot.context);
  const differences: ReplayDifference[] = [];
  
  const factors = ['patternScore', 'liquidityScore', 'scenarioProbability', 'memoryBoost'];
  for (const factor of factors) {
    const original = (snapshot.context as any)[factor] || 0;
    const replayedValue = original * (0.95 + Math.random() * 0.1);
    const delta = replayedValue - original;
    
    if (Math.abs(delta) > 0.01) {
      differences.push({
        factor,
        original,
        replayed: Math.round(replayedValue * 100) / 100,
        delta: Math.round(delta * 100) / 100,
      });
    }
  }
  
  const changed = snapshot.decision.signal !== replayed.signal || 
    Math.abs(snapshot.decision.score - replayed.score) > 0.1;
  
  return {
    snapshotId,
    originalDecision: { signal: snapshot.decision.signal, score: snapshot.decision.score },
    replayedDecision: replayed,
    changed,
    differences,
    reason: changed ? 'Algorithm weights or thresholds have changed' : undefined,
  };
}

export function compareDecisions(symbol: string, limit: number = 10): CompareResult {
  const symbolSnapshots = getSnapshots({ symbol, limit });
  const decisions = symbolSnapshots.map(s => ({
    id: s.id,
    timestamp: s.timestamp,
    signal: s.decision.signal,
    score: s.decision.score,
  }));
  
  let consistentPairs = 0, totalPairs = 0;
  for (let i = 0; i < decisions.length - 1; i++) {
    for (let j = i + 1; j < decisions.length; j++) {
      if (decisions[i].signal !== 'NO_TRADE' && decisions[j].signal !== 'NO_TRADE') {
        totalPairs++;
        if (decisions[i].signal === decisions[j].signal) consistentPairs++;
      }
    }
  }
  
  return {
    symbol,
    decisions,
    stats: {
      total: decisions.length,
      consistency: totalPairs > 0 ? Math.round((consistentPairs / totalPairs) * 100) / 100 : 0,
      avgScore: decisions.length > 0 ? Math.round((decisions.reduce((s, d) => s + d.score, 0) / decisions.length) * 100) / 100 : 0,
    },
  };
}

export function getReplayStats(): {
  totalSnapshots: number;
  bySymbol: Record<string, number>;
  avgScore: number;
  signalDist: Record<string, number>;
} {
  const bySymbol: Record<string, number> = {};
  const signalDist: Record<string, number> = { LONG: 0, SHORT: 0, NO_TRADE: 0 };
  let totalScore = 0;
  
  for (const snapshot of snapshots.values()) {
    bySymbol[snapshot.symbol] = (bySymbol[snapshot.symbol] || 0) + 1;
    signalDist[snapshot.decision.signal]++;
    totalScore += snapshot.decision.score;
  }
  
  return {
    totalSnapshots: snapshots.size,
    bySymbol,
    avgScore: snapshots.size > 0 ? Math.round((totalScore / snapshots.size) * 100) / 100 : 0,
    signalDist,
  };
}
