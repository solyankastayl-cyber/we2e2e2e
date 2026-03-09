/**
 * Phase 8.6 — Market Structure Graph Types
 * 
 * Graph of pattern/event transitions for conditional probability boost
 */

export interface NodeKey {
  family: string;      // PATTERN, STRUCT, LEVEL, CANDLE
  type: string;        // TRIANGLE_ASC, BOS_UP, etc.
  direction?: string;  // BULL, BEAR, NEUTRAL
  regime?: string;     // TREND_UP, TREND_DOWN, RANGE
  vol?: string;        // LOW, NORMAL, HIGH, EXTREME
  tf: string;          // 1H, 4H, 1D
}

export interface GraphNode {
  nodeId: string;      // hash of NodeKey
  key: NodeKey;
  count: number;
  firstSeenAt: Date;
  lastSeenAt: Date;
}

export interface GraphEdge {
  edgeId: string;      // hash(from, to, tf, window)
  fromId: string;
  toId: string;
  tf: string;
  windowBars: number;  // 10, 30, 60
  count: number;
  pToGivenFrom: number;  // P(B|A)
  lift: number;          // P(B|A) / P(B) - key metric
  avgDeltaBars: number;
  deltaBarsP50: number;
  deltaBarsP90: number;
  contexts?: {
    regimeDistribution?: Record<string, number>;
    volDistribution?: Record<string, number>;
  };
}

export interface GraphRunAudit {
  runId: string;
  builtAt: Date;
  tf: string;
  assets: string[];
  rowsUsed: number;
  nodesCount: number;
  edgesCount: number;
  version: string;
  notes?: string;
}

export interface GraphBoostResult {
  graphBoostFactor: number;  // 0.85 - 1.20
  graphReasons: GraphBoostReason[];
  supportingEdges: number;
  confidence: number;
}

export interface GraphBoostReason {
  fromType: string;
  toType: string;
  lift: number;
  deltaBars: number;
  weight: number;
}

export interface GraphBuildParams {
  assets: string[];
  timeframes: string[];
  windowBars: number[];  // [10, 30, 60]
  minEdgeCount: number;  // filter noise
  liftMin: number;       // min lift to keep edge
}

export const DEFAULT_GRAPH_PARAMS: GraphBuildParams = {
  assets: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'],
  timeframes: ['1h', '4h', '1d'],
  windowBars: [10, 30, 60],
  minEdgeCount: 50,
  liftMin: 1.2,
};

export interface PatternEvent {
  eventId: string;
  nodeKey: NodeKey;
  anchorIdx: number;      // bar index
  anchorTs: number;       // timestamp
  asset: string;
  timeframe: string;
  score?: number;
  confidence?: number;
}

export interface GraphConfig {
  enabled: boolean;
  minEdgeCount: number;
  liftMin: number;
  windows: number[];
  maxReasons: number;
  boostClamp: { min: number; max: number };
}

export const DEFAULT_GRAPH_CONFIG: GraphConfig = {
  enabled: true,
  minEdgeCount: 50,
  liftMin: 1.2,
  windows: [10, 30, 60],
  maxReasons: 5,
  boostClamp: { min: 0.82, max: 1.22 },
};
