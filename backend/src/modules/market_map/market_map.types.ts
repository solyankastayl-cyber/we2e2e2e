/**
 * Phase 2.5 — Market Map Layer Types
 * ====================================
 * Types for probabilistic future market visualization
 * 
 * Market Map transforms the product from:
 *   "AI chart tool" → "AI market intelligence system"
 */

// ═══════════════════════════════════════════════════════════════
// MARKET STATE
// ═══════════════════════════════════════════════════════════════

export type MarketState = 
  | 'COMPRESSION'
  | 'BREAKOUT'
  | 'EXPANSION'
  | 'RANGE'
  | 'EXHAUSTION'
  | 'REVERSAL'
  | 'CONTINUATION'
  | 'LIQUIDITY_SWEEP'
  | 'RETEST';

// ═══════════════════════════════════════════════════════════════
// PATH POINT
// ═══════════════════════════════════════════════════════════════

export interface PathPoint {
  t: number;      // timestamp ms
  price: number;  // expected price
}

// ═══════════════════════════════════════════════════════════════
// MARKET BRANCH
// ═══════════════════════════════════════════════════════════════

export interface MarketBranch {
  scenario: string;         // e.g. 'breakout', 'range', 'fakeout'
  probability: number;      // 0..1
  path: PathPoint[];        // price trajectory
  target?: number;          // target price
  stopLoss?: number;        // invalidation level
  direction: 'BULL' | 'BEAR' | 'NEUTRAL';
  expectedMoveATR: number;  // expected move in ATR units
  confidence: number;       // scenario confidence
  events: string[];         // expected events sequence
}

// ═══════════════════════════════════════════════════════════════
// MARKET MAP RESPONSE
// ═══════════════════════════════════════════════════════════════

export interface MarketMapResponse {
  symbol: string;
  timeframe: string;
  ts: number;
  currentState: MarketState;
  currentPrice: number;
  branches: MarketBranch[];
  stats: MarketMapStats;
}

export interface MarketMapStats {
  dominantScenario: string;
  dominantProbability: number;
  uncertainty: number;        // entropy measure
  totalBranches: number;
  bullishBias: number;        // -1..1, > 0 = bullish
  avgExpectedMove: number;
}

// ═══════════════════════════════════════════════════════════════
// HEATMAP
// ═══════════════════════════════════════════════════════════════

export interface HeatmapLevel {
  price: number;
  probability: number;
  type: 'support' | 'resistance' | 'magnet' | 'neutral';
}

export interface HeatmapResponse {
  symbol: string;
  timeframe: string;
  ts: number;
  levels: HeatmapLevel[];
  priceRange: {
    min: number;
    max: number;
    mean: number;
    stdDev: number;
  };
}

// ═══════════════════════════════════════════════════════════════
// EVENT TIMELINE
// ═══════════════════════════════════════════════════════════════

export interface TimelineEvent {
  event: string;
  probability: number;
  expectedTime?: number;   // timestamp when event likely occurs
  impact: 'HIGH' | 'MEDIUM' | 'LOW';
  description?: string;
}

export interface TimelineResponse {
  symbol: string;
  timeframe: string;
  ts: number;
  events: TimelineEvent[];
  sequence: string[];      // most probable event sequence
}

// ═══════════════════════════════════════════════════════════════
// SCENARIO PATHS
// ═══════════════════════════════════════════════════════════════

export interface ScenarioPath {
  id: string;
  probability: number;
  direction: 'BULL' | 'BEAR' | 'NEUTRAL';
  points: PathPoint[];
  label: string;
  color?: string;          // for UI rendering
}

export interface ScenarioPathsResponse {
  symbol: string;
  timeframe: string;
  ts: number;
  currentPrice: number;
  paths: ScenarioPath[];
}

// ═══════════════════════════════════════════════════════════════
// MARKET TREE (Branch Tree Structure)
// ═══════════════════════════════════════════════════════════════

export interface TreeNode {
  id: string;
  state: MarketState;
  probability: number;
  expectedMove: number;
  children?: TreeNode[];
}

export interface MarketTreeResponse {
  symbol: string;
  timeframe: string;
  ts: number;
  root: MarketState;
  branches: TreeNode[];
  stats: {
    totalNodes: number;
    maxDepth: number;
    dominancePath: string[];
  };
}
