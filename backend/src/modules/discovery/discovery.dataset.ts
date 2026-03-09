/**
 * Phase 9 — Strategy Discovery Engine: Dataset Builder
 * 
 * Builds training dataset from historical signals
 */

import { Db } from 'mongodb';
import {
  SignalRecord,
  PatternFeature,
  StructureFeature,
  IndicatorFeature,
  MTFFeature,
  RegimeFeature,
  MemoryFeature,
  AnyFeature
} from './discovery.types.js';

/**
 * Build dataset from historical signals
 */
export async function buildDataset(
  db: Db,
  options: {
    symbols?: string[];
    timeframes?: string[];
    startDate?: Date;
    endDate?: Date;
    limit?: number;
  } = {}
): Promise<SignalRecord[]> {
  const { 
    symbols = ['BTCUSDT', 'ETHUSDT'],
    timeframes = ['1h', '4h', '1d'],
    startDate,
    endDate,
    limit = 10000
  } = options;
  
  // Build query
  const query: any = {
    symbol: { $in: symbols },
    timeframe: { $in: timeframes }
  };
  
  if (startDate || endDate) {
    query.timestamp = {};
    if (startDate) query.timestamp.$gte = startDate.getTime();
    if (endDate) query.timestamp.$lte = endDate.getTime();
  }
  
  // Try to fetch from ta_decisions collection
  const decisions = await db.collection('ta_decisions')
    .find(query)
    .sort({ timestamp: -1 })
    .limit(limit)
    .project({ _id: 0 })
    .toArray();
  
  // Convert to SignalRecords
  return decisions.map(d => convertToSignalRecord(d));
}

/**
 * Convert raw decision to SignalRecord
 */
function convertToSignalRecord(decision: any): SignalRecord {
  return {
    id: decision.id || `sig_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    symbol: decision.symbol || decision.asset || 'BTCUSDT',
    timeframe: decision.timeframe || '4h',
    timestamp: decision.timestamp || Date.now(),
    
    pattern: extractPattern(decision),
    structure: extractStructure(decision),
    indicator: extractIndicator(decision),
    mtf: extractMTF(decision),
    regime: extractRegime(decision),
    memory: extractMemory(decision),
    
    features: extractAllFeatures(decision),
    
    direction: decision.direction || decision.topBias === 'BULL' ? 'LONG' : 'SHORT',
    entry: decision.entry || 0,
    stop: decision.stop || 0,
    target: decision.target || decision.target1 || 0,
    confidence: decision.confidence || decision.finalScore || 0.5,
    
    outcome: {
      result: decision.outcome?.result || 'PENDING',
      pnl: decision.outcome?.pnl || 0,
      rMultiple: decision.outcome?.rMultiple || 0,
      holdTime: decision.outcome?.holdTime || 0,
      exitReason: decision.outcome?.exitReason || 'PENDING' as any
    },
    
    scenarioScore: decision.scenarioScore || decision.topScenario?.probability || 0.5,
    decisionScore: decision.finalScore || 0.5,
    
    createdAt: decision.createdAt || Date.now()
  };
}

/**
 * Extract pattern feature
 */
function extractPattern(decision: any): PatternFeature | null {
  const pattern = decision.pattern || decision.topScenario?.patternType;
  if (!pattern) return null;
  
  const patternMap: Record<string, PatternFeature> = {
    'breakout': 'BREAKOUT',
    'compression': 'COMPRESSION',
    'double_top': 'DOUBLE_TOP',
    'double_bottom': 'DOUBLE_BOTTOM',
    'head_shoulders': 'HEAD_SHOULDERS',
    'triangle': 'TRIANGLE',
    'flag': 'FLAG',
    'wedge': 'WEDGE',
    'divergence': 'DIVERGENCE'
  };
  
  const normalized = pattern.toLowerCase().replace(/_/g, '');
  for (const [key, value] of Object.entries(patternMap)) {
    if (normalized.includes(key)) return value;
  }
  
  return 'BREAKOUT';  // Default
}

/**
 * Extract structure feature
 */
function extractStructure(decision: any): StructureFeature | null {
  const structure = decision.structure?.type || decision.structureEvent;
  if (!structure) return null;
  
  const structureMap: Record<string, StructureFeature> = {
    'sweep': 'SWEEP',
    'compression': 'COMPRESSION',
    'expansion': 'EXPANSION',
    'accumulation': 'ACCUMULATION',
    'distribution': 'DISTRIBUTION',
    'higher_high': 'HIGHER_HIGHS',
    'lower_low': 'LOWER_LOWS'
  };
  
  const normalized = structure.toLowerCase();
  for (const [key, value] of Object.entries(structureMap)) {
    if (normalized.includes(key)) return value;
  }
  
  return null;
}

/**
 * Extract indicator feature
 */
function extractIndicator(decision: any): IndicatorFeature | null {
  const rsi = decision.indicators?.rsi?.value || decision.rsi;
  const volume = decision.indicators?.volume?.spike || decision.volumeSpike;
  const macd = decision.indicators?.macd?.crossover;
  
  if (rsi !== undefined) {
    if (rsi < 30) return 'RSI_OVERSOLD';
    if (rsi > 70) return 'RSI_OVERBOUGHT';
  }
  
  if (decision.rsiDivergence) return 'RSI_DIVERGENCE';
  if (macd === 'BULL' || macd === 'BEAR') return 'MACD_CROSSOVER';
  if (volume) return 'VOLUME_SPIKE';
  
  return null;
}

/**
 * Extract MTF feature
 */
function extractMTF(decision: any): MTFFeature | null {
  const mtf = decision.mtf || decision.mtfState;
  if (!mtf) return null;
  
  if (mtf.higherConflict) return 'MTF_CONFLICT';
  if (mtf.regimeAligned && mtf.structureAligned) return 'MTF_ALIGNED';
  if (mtf.higherBias === 'BULL') return 'HIGHER_TF_BULL';
  if (mtf.higherBias === 'BEAR') return 'HIGHER_TF_BEAR';
  if (mtf.momentumAligned) return 'LOWER_TF_CONFIRMS';
  
  return null;
}

/**
 * Extract regime feature
 */
function extractRegime(decision: any): RegimeFeature {
  const regime = decision.regime?.market || decision.marketRegime || 'RANGE';
  
  const regimeMap: Record<string, RegimeFeature> = {
    'trend_up': 'TREND_UP',
    'trend_down': 'TREND_DOWN',
    'range': 'RANGE',
    'transition': 'TRANSITION'
  };
  
  const normalized = regime.toLowerCase().replace(/_/g, '');
  for (const [key, value] of Object.entries(regimeMap)) {
    if (normalized.includes(key.replace('_', ''))) return value;
  }
  
  return 'RANGE';
}

/**
 * Extract memory feature
 */
function extractMemory(decision: any): MemoryFeature | null {
  const memory = decision.memory;
  if (!memory) return null;
  
  if (memory.matchCount > 5 && memory.confidence > 0.7) return 'MEMORY_MATCH';
  if (memory.historicalBias === 'BULL' || memory.historicalBias === 'BEAR') {
    return memory.confidence > 0.6 ? 'HISTORICAL_WIN' : 'HISTORICAL_LOSS';
  }
  
  return 'MEMORY_WEAK';
}

/**
 * Extract all features
 */
function extractAllFeatures(decision: any): AnyFeature[] {
  const features: AnyFeature[] = [];
  
  const pattern = extractPattern(decision);
  const structure = extractStructure(decision);
  const indicator = extractIndicator(decision);
  const mtf = extractMTF(decision);
  const regime = extractRegime(decision);
  const memory = extractMemory(decision);
  
  if (pattern) features.push(pattern);
  if (structure) features.push(structure);
  if (indicator) features.push(indicator);
  if (mtf) features.push(mtf);
  features.push(regime);
  if (memory) features.push(memory);
  
  return features;
}

/**
 * Generate mock dataset for testing
 */
export function generateMockDataset(size: number = 500): SignalRecord[] {
  const patterns: PatternFeature[] = ['BREAKOUT', 'COMPRESSION', 'TRIANGLE', 'FLAG', 'DIVERGENCE'];
  const structures: StructureFeature[] = ['SWEEP', 'COMPRESSION', 'EXPANSION', 'ACCUMULATION'];
  const indicators: IndicatorFeature[] = ['RSI_OVERSOLD', 'RSI_OVERBOUGHT', 'VOLUME_SPIKE', 'MACD_CROSSOVER'];
  const mtfs: MTFFeature[] = ['MTF_ALIGNED', 'MTF_CONFLICT', 'HIGHER_TF_BULL', 'HIGHER_TF_BEAR'];
  const regimes: RegimeFeature[] = ['TREND_UP', 'TREND_DOWN', 'RANGE'];
  const memories: MemoryFeature[] = ['MEMORY_MATCH', 'MEMORY_WEAK', 'HISTORICAL_WIN'];
  const symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
  const timeframes = ['1h', '4h', '1d'];
  
  const records: SignalRecord[] = [];
  const now = Date.now();
  
  for (let i = 0; i < size; i++) {
    const pattern = patterns[Math.floor(Math.random() * patterns.length)];
    const structure = structures[Math.floor(Math.random() * structures.length)];
    const indicator = Math.random() > 0.3 ? indicators[Math.floor(Math.random() * indicators.length)] : null;
    const mtf = mtfs[Math.floor(Math.random() * mtfs.length)];
    const regime = regimes[Math.floor(Math.random() * regimes.length)];
    const memory = Math.random() > 0.4 ? memories[Math.floor(Math.random() * memories.length)] : null;
    
    // Calculate win probability based on features
    let winProb = 0.5;
    
    // Good combinations
    if (pattern === 'BREAKOUT' && mtf === 'MTF_ALIGNED') winProb += 0.15;
    if (structure === 'SWEEP' && indicator === 'RSI_OVERSOLD') winProb += 0.12;
    if (regime === 'TREND_UP' && mtf === 'HIGHER_TF_BULL') winProb += 0.1;
    if (memory === 'MEMORY_MATCH') winProb += 0.08;
    if (indicator === 'VOLUME_SPIKE' && pattern === 'BREAKOUT') winProb += 0.1;
    
    // Bad combinations
    if (mtf === 'MTF_CONFLICT') winProb -= 0.15;
    if (regime === 'RANGE' && pattern === 'BREAKOUT') winProb -= 0.1;
    
    winProb = Math.max(0.3, Math.min(0.8, winProb));
    const isWin = Math.random() < winProb;
    
    const direction = Math.random() > 0.5 ? 'LONG' : 'SHORT';
    const entry = 50000 + Math.random() * 10000;
    const stopDist = entry * (0.01 + Math.random() * 0.02);
    
    const features: AnyFeature[] = [pattern, structure, regime];
    if (indicator) features.push(indicator);
    if (mtf) features.push(mtf);
    if (memory) features.push(memory);
    
    records.push({
      id: `mock_${i}`,
      symbol: symbols[Math.floor(Math.random() * symbols.length)],
      timeframe: timeframes[Math.floor(Math.random() * timeframes.length)],
      timestamp: now - (size - i) * 3600000,  // 1 hour apart
      
      pattern,
      structure,
      indicator,
      mtf,
      regime,
      memory,
      features,
      
      direction,
      entry,
      stop: direction === 'LONG' ? entry - stopDist : entry + stopDist,
      target: direction === 'LONG' ? entry + stopDist * 2 : entry - stopDist * 2,
      confidence: 0.5 + Math.random() * 0.3,
      
      outcome: {
        result: isWin ? 'WIN' : 'LOSS',
        pnl: isWin ? (0.5 + Math.random() * 2) : -(0.5 + Math.random() * 1),
        rMultiple: isWin ? (1 + Math.random() * 2) : -(0.5 + Math.random() * 0.5),
        holdTime: Math.floor(5 + Math.random() * 20),
        exitReason: isWin ? 'TARGET' : 'STOP'
      },
      
      scenarioScore: 0.5 + Math.random() * 0.3,
      decisionScore: 0.5 + Math.random() * 0.3,
      
      createdAt: now - (size - i) * 3600000
    });
  }
  
  return records;
}
