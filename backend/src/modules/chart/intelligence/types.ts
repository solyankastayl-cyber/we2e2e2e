/**
 * Chart Intelligence Types
 * ========================
 * Types for the Chart Intelligence Layer endpoints
 */

// ═══════════════════════════════════════════════════════════════
// CANDLE TYPES
// ═══════════════════════════════════════════════════════════════

export interface Candle {
  t: number;  // timestamp ms
  o: number;  // open
  h: number;  // high
  l: number;  // low
  c: number;  // close
  v: number;  // volume
}

export interface CandlesResponse {
  symbol: string;
  interval: string;
  candles: Candle[];
}

// ═══════════════════════════════════════════════════════════════
// PREDICTION TYPES
// ═══════════════════════════════════════════════════════════════

export interface PredictionPathPoint {
  t: number;
  price: number;
}

export interface PredictionResponse {
  horizon: string;
  confidence: number;
  path: PredictionPathPoint[];
}

// ═══════════════════════════════════════════════════════════════
// LEVELS TYPES
// ═══════════════════════════════════════════════════════════════

export interface LevelsResponse {
  support: number[];
  resistance: number[];
  liquidity: number[];
}

// ═══════════════════════════════════════════════════════════════
// SCENARIO TYPES
// ═══════════════════════════════════════════════════════════════

export interface Scenario {
  type: string;
  probability: number;
  target?: number;
  stopLoss?: number;
  description?: string;
}

export interface ScenariosResponse {
  scenarios: Scenario[];
}

// ═══════════════════════════════════════════════════════════════
// CHART OBJECT TYPES
// ═══════════════════════════════════════════════════════════════

export interface PointTP {
  t: number;
  p: number;
}

export interface TrendLine {
  type: 'trendline';
  direction: 'up' | 'down';
  points: PointTP[];
}

export interface LiquidityZone {
  type: 'liquidity_zone';
  top: number;
  bottom: number;
}

export interface SupportLevel {
  type: 'support';
  price: number;
}

export interface ResistanceLevel {
  type: 'resistance';
  price: number;
}

export interface ScenarioPath {
  type: 'scenario';
  probability: number;
  path: PointTP[];
}

export interface MemoryMarker {
  type: 'memory';
  similarity: number;
  price: number;
  t: number;
}

export interface Channel {
  type: 'channel';
  upper: PointTP[];
  lower: PointTP[];
}

export interface Triangle {
  type: 'triangle';
  points: PointTP[];
}

export type ChartObject =
  | TrendLine
  | LiquidityZone
  | SupportLevel
  | ResistanceLevel
  | ScenarioPath
  | MemoryMarker
  | Channel
  | Triangle;

export interface ObjectsResponse {
  objects: ChartObject[];
}

// ═══════════════════════════════════════════════════════════════
// REGIME TYPES
// ═══════════════════════════════════════════════════════════════

export interface RegimeResponse {
  regime: string;
  bias: string;
  volatility: number;
}

// ═══════════════════════════════════════════════════════════════
// SYSTEM STATE TYPES
// ═══════════════════════════════════════════════════════════════

export interface SystemResponse {
  analysisMode: string;
  riskMode: string;
  metabrainState: string;
}

// ═══════════════════════════════════════════════════════════════
// AGGREGATED STATE
// ═══════════════════════════════════════════════════════════════

// Market Map summary for chart state
export interface MarketMapSummary {
  currentState: string;
  dominantScenario: string;
  dominantProbability: number;
  bullishBias: number;
  branchCount: number;
}

export interface ChartStateResponse {
  symbol: string;
  interval: string;
  ts: number;
  candles: Candle[];
  prediction: PredictionResponse;
  levels: LevelsResponse;
  scenarios: Scenario[];
  objects: ChartObject[];
  regime: RegimeResponse;
  system: SystemResponse;
  marketMap?: MarketMapSummary;  // Phase 2.5
}
