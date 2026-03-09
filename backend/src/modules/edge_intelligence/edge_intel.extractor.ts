/**
 * Phase 7 — Edge Extractor
 * 
 * Extracts edge data from trade records
 */

import { v4 as uuidv4 } from 'uuid';
import { 
  EdgeRecord, 
  EdgeDimension,
  EdgeIntelligenceConfig,
  DEFAULT_EDGE_CONFIG
} from './edge_intel.types.js';

// ═══════════════════════════════════════════════════════════════
// TRADE TO EDGE RECORD CONVERSION
// ═══════════════════════════════════════════════════════════════

export interface TradeData {
  tradeId?: string;
  asset: string;
  timeframe: string;
  entryTime: Date;
  exitTime?: Date;
  
  // Pattern info
  pattern?: string;
  patternFamily?: string;
  
  // Decision context
  decisionPack?: {
    topScenario?: { pattern?: string; family?: string };
    graphBoost?: number;
    physicsBoost?: number;
    stateBoost?: number;
    score?: number;
    confidence?: number;
  };
  
  // Market context
  marketState?: string;
  physicsState?: string;
  liquidityContext?: string;
  fractalMatch?: string;
  scenarioId?: string;
  
  // Energy
  energyScore?: number;
  
  // Result
  pnlR: number;
}

/**
 * Convert trade data to edge record
 */
export function tradeToEdgeRecord(trade: TradeData): EdgeRecord {
  const resultR = trade.pnlR;
  const outcome: 'WIN' | 'LOSS' | 'BREAKEVEN' = 
    resultR > 0.1 ? 'WIN' : 
    resultR < -0.1 ? 'LOSS' : 'BREAKEVEN';
  
  return {
    tradeId: trade.tradeId || `TRD_${uuidv4().slice(0, 8)}`,
    asset: trade.asset,
    timeframe: trade.timeframe,
    entryTime: trade.entryTime,
    exitTime: trade.exitTime,
    
    pattern: trade.pattern || trade.decisionPack?.topScenario?.pattern || 'UNKNOWN',
    patternFamily: trade.patternFamily || trade.decisionPack?.topScenario?.family,
    fractal: trade.fractalMatch,
    scenario: trade.scenarioId,
    state: trade.marketState || 'UNKNOWN',
    liquidity: trade.liquidityContext || 'NEUTRAL',
    marketState: trade.marketState,
    physicsState: trade.physicsState,
    
    resultR,
    outcome,
    
    entryScore: trade.decisionPack?.score || 0,
    entryConfidence: trade.decisionPack?.confidence || 0,
    
    energyScore: trade.energyScore,
    graphBoost: trade.decisionPack?.graphBoost,
    stateBoost: trade.decisionPack?.stateBoost
  };
}

// ═══════════════════════════════════════════════════════════════
// DIMENSION EXTRACTION
// ═══════════════════════════════════════════════════════════════

/**
 * Extract dimension value from edge record
 */
export function extractDimensionValue(
  record: EdgeRecord,
  dimension: EdgeDimension
): string {
  switch (dimension) {
    case 'PATTERN':
      return record.pattern;
    case 'STATE':
      return record.state;
    case 'FRACTAL':
      return record.fractal || 'NONE';
    case 'SCENARIO':
      return record.scenario || 'NONE';
    case 'LIQUIDITY':
      return record.liquidity;
    case 'MARKET_STATE':
      return record.marketState || record.state;
    case 'TIMEFRAME':
      return record.timeframe;
    case 'ASSET':
      return record.asset;
    default:
      return 'UNKNOWN';
  }
}

/**
 * Group records by dimension
 */
export function groupByDimension(
  records: EdgeRecord[],
  dimension: EdgeDimension
): Map<string, EdgeRecord[]> {
  const groups = new Map<string, EdgeRecord[]>();
  
  for (const record of records) {
    const key = extractDimensionValue(record, dimension);
    
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(record);
  }
  
  return groups;
}

/**
 * Group by multiple dimensions (combination key)
 */
export function groupByDimensions(
  records: EdgeRecord[],
  dimensions: EdgeDimension[]
): Map<string, EdgeRecord[]> {
  const groups = new Map<string, EdgeRecord[]>();
  
  for (const record of records) {
    const keyParts = dimensions.map(d => extractDimensionValue(record, d));
    const key = keyParts.join('|');
    
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(record);
  }
  
  return groups;
}

// ═══════════════════════════════════════════════════════════════
// FILTERING
// ═══════════════════════════════════════════════════════════════

export interface EdgeFilter {
  assets?: string[];
  timeframes?: string[];
  patterns?: string[];
  states?: string[];
  dateFrom?: Date;
  dateTo?: Date;
  minScore?: number;
  outcomeOnly?: 'WIN' | 'LOSS';
}

/**
 * Filter edge records
 */
export function filterRecords(
  records: EdgeRecord[],
  filter: EdgeFilter
): EdgeRecord[] {
  return records.filter(r => {
    if (filter.assets && !filter.assets.includes(r.asset)) return false;
    if (filter.timeframes && !filter.timeframes.includes(r.timeframe)) return false;
    if (filter.patterns && !filter.patterns.includes(r.pattern)) return false;
    if (filter.states && !filter.states.includes(r.state)) return false;
    if (filter.dateFrom && r.entryTime < filter.dateFrom) return false;
    if (filter.dateTo && r.entryTime > filter.dateTo) return false;
    if (filter.minScore && r.entryScore < filter.minScore) return false;
    if (filter.outcomeOnly && r.outcome !== filter.outcomeOnly) return false;
    return true;
  });
}

// ═══════════════════════════════════════════════════════════════
// BATCH EXTRACTION
// ═══════════════════════════════════════════════════════════════

/**
 * Extract edge data from batch of trades
 */
export function extractEdgeDataBatch(
  trades: TradeData[],
  config: EdgeIntelligenceConfig = DEFAULT_EDGE_CONFIG
): {
  records: EdgeRecord[];
  summary: {
    total: number;
    wins: number;
    losses: number;
    avgR: number;
    winRate: number;
  };
} {
  const records = trades.map(t => tradeToEdgeRecord(t));
  
  const wins = records.filter(r => r.outcome === 'WIN').length;
  const losses = records.filter(r => r.outcome === 'LOSS').length;
  const avgR = records.length > 0 
    ? records.reduce((sum, r) => sum + r.resultR, 0) / records.length 
    : 0;
  
  return {
    records,
    summary: {
      total: records.length,
      wins,
      losses,
      avgR,
      winRate: records.length > 0 ? wins / records.length : 0
    }
  };
}
