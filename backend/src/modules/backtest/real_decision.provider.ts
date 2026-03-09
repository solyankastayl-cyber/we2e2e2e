/**
 * B3: Real Decision Provider for Backtest
 * 
 * Integrates the REAL Decision Engine into the backtester.
 * 
 * Pipeline:
 * 1. Takes historical candles (up to moment T - no lookahead)
 * 2. Runs TaService.analyzeWithCandles() → detects patterns
 * 3. Converts ScoredPattern[] → ScenarioInput[]
 * 4. Calls real DecisionEngine.computeDecision()
 * 5. Returns DecisionPackMinimal for backtest runner
 * 
 * This replaces the mock decision engine in backtest.runner.ts
 */

import { Db } from 'mongodb';
import { TaService } from '../ta/runtime/ta.service.js';
import { ScoredPattern } from '../ta/scoring/score.js';
import { 
  createDecisionEngine, 
  DecisionEngine as RealDecisionEngine,
  DecisionContext as RealDecisionContext,
  ScenarioInput,
  DecisionPack as RealDecisionPack,
  ProcessedScenario
} from '../ta/decision/decision.engine.js';
import { DecisionEngine, DecisionContext } from './backtest.runner.js';
import { DecisionPackMinimal } from './decision.adapter.js';
import { Candle as BacktestCandle } from './domain/types.js';

// ═══════════════════════════════════════════════════════════════
// Real Decision Provider
// ═══════════════════════════════════════════════════════════════

export interface RealDecisionProviderConfig {
  // Minimum patterns required to generate decision
  minPatterns: number;
  // Minimum score for pattern to be included
  minPatternScore: number;
  // Whether to include all ranked patterns or just top
  includeAllRanked: boolean;
}

export const DEFAULT_REAL_DECISION_CONFIG: RealDecisionProviderConfig = {
  minPatterns: 1,
  minPatternScore: 0.30,
  includeAllRanked: true,
};

/**
 * Creates a Real Decision Provider that wraps TaService + DecisionEngine
 */
export function createRealDecisionProvider(
  db: Db,
  config: Partial<RealDecisionProviderConfig> = {}
): DecisionEngine {
  const cfg = { ...DEFAULT_REAL_DECISION_CONFIG, ...config };
  
  // Initialize services
  const taService = new TaService();
  const decisionEngine = createDecisionEngine(db);
  
  return {
    async computeDecision(ctx: DecisionContext): Promise<DecisionPackMinimal> {
      const { asset, timeframe, timestamp, candles, currentPrice, atr } = ctx;
      
      // 1. Convert candles to TA format
      const taCandles = candles.map(c => ({
        ts: c.openTime,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
      }));
      
      // 2. Run TA analysis on historical candles (NO LOOKAHEAD)
      const taResult = taService.analyzeWithCandles(taCandles, asset, timeframe);
      
      if (!taResult.ok || taResult.patterns.length < cfg.minPatterns) {
        // No patterns detected → no trade signal
        return {
          asset,
          timeframe,
          timestamp,
          regime: taResult.structure?.regime || 'TRANSITION',
        };
      }
      
      // 3. Convert ScoredPatterns → ScenarioInput[] for DecisionEngine
      const patternsToProcess = cfg.includeAllRanked 
        ? (taResult.ranked || taResult.patterns)
        : taResult.patterns;
        
      const scenarios = patternsToProcess
        .filter(p => p.scoring.score >= cfg.minPatternScore)
        .map(p => scoredPatternToScenarioInput(p, currentPrice, atr));
      
      if (scenarios.length === 0) {
        return {
          asset,
          timeframe,
          timestamp,
          regime: taResult.structure?.regime || 'TRANSITION',
        };
      }
      
      // 4. Build context for real Decision Engine
      const realCtx: RealDecisionContext = {
        asset,
        timeframe,
        timestamp,
        candles: taCandles.map(c => ({
          openTime: c.ts,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        })),
        currentPrice,
        atr,
        scenarios,
        recentPatterns: extractRecentPatterns(patternsToProcess),
      };
      
      // 5. Run REAL Decision Engine
      let realDecision: RealDecisionPack;
      try {
        realDecision = await decisionEngine.computeDecision(realCtx);
      } catch (err) {
        console.error('[RealDecisionProvider] DecisionEngine error:', err);
        return {
          asset,
          timeframe,
          timestamp,
          regime: taResult.structure?.regime || 'TRANSITION',
        };
      }
      
      // 6. Convert RealDecisionPack → DecisionPackMinimal for backtest adapter
      return realDecisionPackToMinimal(realDecision);
    }
  };
}

// ═══════════════════════════════════════════════════════════════
// Converters
// ═══════════════════════════════════════════════════════════════

/**
 * Convert ScoredPattern from TaService to ScenarioInput for DecisionEngine
 */
function scoredPatternToScenarioInput(
  pattern: ScoredPattern,
  currentPrice: number,
  atr: number
): ScenarioInput {
  const trade = pattern.trade;
  
  // Determine direction
  let direction: 'LONG' | 'SHORT' = 'LONG';
  const typeStr = pattern.type as string;
  if (typeStr.includes('BEAR') || typeStr.includes('DESC') || typeStr.includes('DOWN') || typeStr.includes('RISING')) {
    direction = 'SHORT';
  }
  
  // Calculate entry/stop/target from pattern trade data or defaults
  let entry = trade?.entry ?? currentPrice;
  let stop = trade?.stop ?? (direction === 'LONG' ? currentPrice - atr : currentPrice + atr);
  let target1 = trade?.target1 ?? (direction === 'LONG' ? currentPrice + atr * 2 : currentPrice - atr * 2);
  let target2 = trade?.target2;
  
  // Extract pivot points from geometry if available
  const pivotHighs: number[] = [];
  const pivotLows: number[] = [];
  const pivotHighIdxs: number[] = [];
  const pivotLowIdxs: number[] = [];
  
  // Try to get pivots from geometry
  const geomPivots = pattern.geometry?.pivots;
  if (geomPivots && Array.isArray(geomPivots)) {
    for (const pt of geomPivots) {
      if (pt.type === 'HIGH') {
        pivotHighs.push(pt.price);
        pivotHighIdxs.push(pt.i ?? 0);
      } else if (pt.type === 'LOW') {
        pivotLows.push(pt.price);
        pivotLowIdxs.push(pt.i ?? 0);
      }
    }
  }
  
  return {
    scenarioId: pattern.id,
    patternType: pattern.type as string,
    direction,
    entry,
    stop,
    target1,
    target2,
    score: pattern.scoring.score,
    confidence: pattern.scoring.confidence,
    touches: pattern.metrics?.touchScore ?? 0,
    pivotHighs,
    pivotLows,
    pivotHighIdxs,
    pivotLowIdxs,
    startIdx: pattern.startIdx ?? 0,
    endIdx: pattern.endIdx ?? 0,
    // Line parameters if available
    lineHigh: pattern.geometry?.lineHigh,
    lineLow: pattern.geometry?.lineLow,
  };
}

/**
 * Extract recent pattern info for graph boost
 */
function extractRecentPatterns(
  patterns: ScoredPattern[]
): Array<{ type: string; direction: string; barsAgo: number }> {
  return patterns.slice(0, 5).map((p, idx) => ({
    type: p.type as string,
    direction: getPatternDirection(p.type as string),
    barsAgo: idx * 5, // Approximate
  }));
}

/**
 * Get pattern direction from type string
 */
function getPatternDirection(type: string): string {
  if (type.includes('BULL') || type.includes('ASC') || type.includes('UP') || type.includes('FALLING')) {
    return 'BULLISH';
  }
  if (type.includes('BEAR') || type.includes('DESC') || type.includes('DOWN') || type.includes('RISING')) {
    return 'BEARISH';
  }
  return 'NEUTRAL';
}

/**
 * Convert RealDecisionPack → DecisionPackMinimal
 */
function realDecisionPackToMinimal(pack: RealDecisionPack): DecisionPackMinimal {
  const minimal: DecisionPackMinimal = {
    asset: pack.asset,
    timeframe: pack.timeframe,
    timestamp: pack.timestamp,
    regime: pack.regime,
  };
  
  // Convert top scenario
  if (pack.topScenario) {
    minimal.topScenario = processedScenarioToMinimal(pack.topScenario);
  }
  
  // Convert all scenarios
  if (pack.scenarios.length > 0) {
    minimal.scenarios = pack.scenarios.map(processedScenarioToMinimal);
  }
  
  return minimal;
}

/**
 * Convert ProcessedScenario → minimal format
 */
function processedScenarioToMinimal(s: ProcessedScenario): NonNullable<DecisionPackMinimal['topScenario']> {
  return {
    scenarioId: s.scenarioId,
    patternType: s.patternType,
    direction: s.direction,
    entry: s.entry,
    stop: s.stop,
    target1: s.target1,
    target2: s.target2,
    riskReward: s.riskReward,
    score: s.finalScore,
    pEntry: s.pEntry,
    rExpected: s.rExpected,
    evAfterEdge: s.evAfterEdge,
    evAfterML: s.evAfterML,
    edge: {
      enabled: s.edge.enabled,
      multiplier: s.edge.multiplier,
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// Mock Decision Provider (for comparison/fallback)
// ═══════════════════════════════════════════════════════════════

/**
 * Creates a Mock Decision Provider (existing behavior)
 * Used for comparison testing or when real provider fails
 */
export function createMockDecisionProvider(): DecisionEngine {
  return {
    async computeDecision(ctx: DecisionContext): Promise<DecisionPackMinimal> {
      const { asset, timeframe, timestamp, candles, currentPrice, atr } = ctx;
      
      // Simple mock: generate random signal every ~10 bars
      const shouldSignal = Math.random() > 0.9;
      
      if (!shouldSignal) {
        return {
          asset,
          timeframe,
          timestamp,
          regime: 'RANGE',
        };
      }
      
      // Random direction
      const direction = Math.random() > 0.5 ? 'LONG' : 'SHORT';
      const isLong = direction === 'LONG';
      
      // Calculate trade plan
      const entry = currentPrice;
      const stop = isLong ? entry - atr : entry + atr;
      const target1 = isLong ? entry + atr * 2 : entry - atr * 2;
      const target2 = isLong ? entry + atr * 3 : entry - atr * 3;
      
      return {
        asset,
        timeframe,
        timestamp,
        regime: 'RANGE',
        topScenario: {
          scenarioId: `mock_${Date.now()}`,
          patternType: 'MOCK_PATTERN',
          direction,
          entry,
          stop,
          target1,
          target2,
          riskReward: 2,
          score: 0.5,
          pEntry: 0.5,
          rExpected: 1.5,
          evAfterEdge: 0.5,
          evAfterML: 0.5,
          edge: {
            enabled: false,
            multiplier: 1,
          },
        },
      };
    }
  };
}
