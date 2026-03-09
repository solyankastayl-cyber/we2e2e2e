/**
 * MetaBrain v2.1 — Data Source
 * 
 * Transforms existing Edge Intelligence data into attribution records
 */

import {
  AnalysisModule,
  AttributionTradeRecord
} from './module_attribution.types.js';
import { EdgeRecordModel } from '../edge_intelligence/edge_intel.storage.js';

// ═══════════════════════════════════════════════════════════════
// DATA TRANSFORMATION
// ═══════════════════════════════════════════════════════════════

/**
 * Transform EdgeRecord to AttributionTradeRecord
 */
export function transformEdgeRecord(edgeRecord: any): AttributionTradeRecord {
  const moduleActivations: AttributionTradeRecord['moduleActivations'] = [];
  
  // Pattern module
  if (edgeRecord.pattern) {
    moduleActivations.push({
      module: 'PATTERN',
      value: edgeRecord.pattern,
      boost: edgeRecord.entryScore || 0.5
    });
  }
  
  // Liquidity module
  if (edgeRecord.liquidity) {
    const liquidityBoost = edgeRecord.liquidity !== 'NEUTRAL' ? 0.8 : 0.3;
    moduleActivations.push({
      module: 'LIQUIDITY',
      value: edgeRecord.liquidity,
      boost: liquidityBoost
    });
  }
  
  // State module
  if (edgeRecord.state) {
    moduleActivations.push({
      module: 'STATE',
      value: edgeRecord.state,
      boost: edgeRecord.stateBoost || 0.5
    });
  }
  
  // Fractal module
  if (edgeRecord.fractal) {
    moduleActivations.push({
      module: 'FRACTAL',
      value: edgeRecord.fractal,
      boost: 0.6
    });
  }
  
  // Scenario module
  if (edgeRecord.scenario) {
    moduleActivations.push({
      module: 'SCENARIO',
      value: edgeRecord.scenario,
      boost: 0.7
    });
  }
  
  // Physics module
  if (edgeRecord.physicsState) {
    moduleActivations.push({
      module: 'PHYSICS',
      value: edgeRecord.physicsState,
      boost: edgeRecord.energyScore || 0.5
    });
  }
  
  // Graph module
  if (edgeRecord.graphBoost) {
    moduleActivations.push({
      module: 'GRAPH',
      value: 'GRAPH_ACTIVE',
      boost: edgeRecord.graphBoost
    });
  }
  
  // Regime module (from market state)
  if (edgeRecord.marketState) {
    moduleActivations.push({
      module: 'REGIME',
      value: edgeRecord.marketState,
      boost: 0.6
    });
  }
  
  return {
    tradeId: edgeRecord.tradeId,
    asset: edgeRecord.asset,
    timeframe: edgeRecord.timeframe,
    resultR: edgeRecord.resultR,
    outcome: edgeRecord.outcome,
    moduleActivations,
    regime: edgeRecord.marketState,
    entryTime: new Date(edgeRecord.entryTime)
  };
}

// ═══════════════════════════════════════════════════════════════
// DATA LOADING
// ═══════════════════════════════════════════════════════════════

/**
 * Load attribution trade records from Edge Intelligence
 */
export async function loadAttributionRecords(
  filter?: {
    asset?: string;
    timeframe?: string;
    dateFrom?: Date;
    dateTo?: Date;
    regime?: string;
  },
  limit: number = 5000
): Promise<AttributionTradeRecord[]> {
  const query: any = {};
  
  if (filter?.asset) query.asset = filter.asset;
  if (filter?.timeframe) query.timeframe = filter.timeframe;
  if (filter?.regime) query.marketState = filter.regime;
  
  if (filter?.dateFrom || filter?.dateTo) {
    query.entryTime = {};
    if (filter.dateFrom) query.entryTime.$gte = filter.dateFrom;
    if (filter.dateTo) query.entryTime.$lte = filter.dateTo;
  }
  
  const edgeRecords = await EdgeRecordModel.find(query)
    .sort({ entryTime: -1 })
    .limit(limit)
    .lean();
  
  return edgeRecords.map(transformEdgeRecord);
}

/**
 * Load attribution records within time window
 */
export async function loadAttributionRecordsInWindow(
  daysBack: number = 180,
  options?: {
    asset?: string;
    timeframe?: string;
    regime?: string;
  }
): Promise<AttributionTradeRecord[]> {
  const dateFrom = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000);
  
  return loadAttributionRecords({
    ...options,
    dateFrom
  });
}

// ═══════════════════════════════════════════════════════════════
// SYNTHETIC DATA FOR TESTING
// ═══════════════════════════════════════════════════════════════

/**
 * Generate synthetic attribution records for testing
 * Creates realistic edge distribution across modules
 */
export function generateSyntheticRecords(count: number = 500): AttributionTradeRecord[] {
  const records: AttributionTradeRecord[] = [];
  const patterns = ['DOUBLE_BOTTOM', 'HEAD_SHOULDERS', 'TRIANGLE', 'FLAG', 'WEDGE'];
  const states = ['BREAKOUT', 'RETEST', 'CONTINUATION', 'REVERSAL', 'RANGE'];
  const liquidities = ['SWEEP_LOW', 'SWEEP_HIGH', 'EQUAL_HIGHS', 'EQUAL_LOWS', 'NEUTRAL'];
  const scenarios = ['CLASSIC_BREAKOUT', 'FALSE_BREAKOUT', 'TREND_CONTINUATION', 'RANGE_ROTATION'];
  const regimes = ['TREND_EXPANSION', 'COMPRESSION', 'RANGE_ROTATION', 'VOLATILITY_EXPANSION'];
  
  // Realistic module edge profiles
  // LIQUIDITY and STATE are strong, FRACTAL is weak
  const moduleEdge: Record<AnalysisModule, number> = {
    'PATTERN': 0.52,      // Slight positive
    'LIQUIDITY': 0.58,    // Strong positive
    'GRAPH': 0.51,        // Near neutral
    'FRACTAL': 0.46,      // Negative (weak module)
    'PHYSICS': 0.53,      // Positive
    'STATE': 0.56,        // Strong positive
    'REGIME': 0.52,       // Slight positive
    'SCENARIO': 0.54      // Positive
  };
  
  for (let i = 0; i < count; i++) {
    const pattern = patterns[Math.floor(Math.random() * patterns.length)];
    const state = states[Math.floor(Math.random() * states.length)];
    const liquidity = liquidities[Math.floor(Math.random() * liquidities.length)];
    const scenario = scenarios[Math.floor(Math.random() * scenarios.length)];
    const regime = regimes[Math.floor(Math.random() * regimes.length)];
    
    // Build module activations with varying boost levels
    const moduleActivations: AttributionTradeRecord['moduleActivations'] = [
      { module: 'PATTERN', value: pattern, boost: 0.3 + Math.random() * 0.7 },
      { module: 'STATE', value: state, boost: 0.3 + Math.random() * 0.7 },
      { module: 'LIQUIDITY', value: liquidity, boost: liquidity !== 'NEUTRAL' ? (0.5 + Math.random() * 0.5) : (0.1 + Math.random() * 0.3) },
      { module: 'SCENARIO', value: scenario, boost: 0.4 + Math.random() * 0.5 },
      { module: 'REGIME', value: regime, boost: 0.4 + Math.random() * 0.4 }
    ];
    
    // Add optional modules with 50% probability
    if (Math.random() > 0.5) {
      moduleActivations.push({ module: 'PHYSICS', value: 'HIGH_ENERGY', boost: 0.3 + Math.random() * 0.6 });
    }
    if (Math.random() > 0.5) {
      moduleActivations.push({ module: 'GRAPH', value: 'GRAPH_ACTIVE', boost: 0.3 + Math.random() * 0.5 });
    }
    if (Math.random() > 0.6) {
      moduleActivations.push({ module: 'FRACTAL', value: 'FRACTAL_FOUND', boost: 0.2 + Math.random() * 0.5 });
    }
    
    // Calculate win probability based on active high-boost modules
    let winProb = 0.48;  // Base slightly below 50%
    for (const activation of moduleActivations) {
      if (activation.boost >= 0.5) {
        // Module contributes its edge when activated
        winProb += (moduleEdge[activation.module] - 0.5) * 0.3;
      }
    }
    
    // Add some noise
    winProb += (Math.random() - 0.5) * 0.1;
    
    // Cap win probability
    winProb = Math.max(0.35, Math.min(0.65, winProb));
    
    // Determine outcome
    const isWin = Math.random() < winProb;
    const resultR = isWin 
      ? 0.3 + Math.random() * 1.7  // Win: 0.3R to 2R
      : -(0.5 + Math.random() * 0.5);  // Loss: -0.5R to -1R
    
    records.push({
      tradeId: `SYN_${i.toString().padStart(5, '0')}`,
      asset: 'BTCUSDT',
      timeframe: '1d',
      resultR,
      outcome: isWin ? 'WIN' : (Math.abs(resultR) < 0.1 ? 'BREAKEVEN' : 'LOSS'),
      moduleActivations,
      regime,
      entryTime: new Date(Date.now() - Math.random() * 180 * 24 * 60 * 60 * 1000)
    });
  }
  
  return records;
}
