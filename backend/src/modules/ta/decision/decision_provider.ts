/**
 * P1.6 — Decision Provider Adapter
 * 
 * Adapts DecisionEngine for use by SimRunner.
 * Single source of truth for decision logic.
 */

import { Db } from 'mongodb';
import { createDecisionEngine, DecisionEngine, DecisionContext, DecisionPack, ProcessedScenario, CandleData, ScenarioInput } from './decision.engine.js';
import { SimCandle, SimScenario, SimRiskPack } from '../simulator/domain.js';
import { DecisionProvider as IDecisionProvider } from '../simulator/runner.js';

/**
 * Convert SimCandle[] to CandleData[]
 */
function convertCandles(simCandles: SimCandle[]): CandleData[] {
  return simCandles.map(c => ({
    openTime: c.ts * 1000,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
    volume: c.volume || 0,
  }));
}

/**
 * Convert DecisionPack.topScenario to SimScenario
 */
function processedToSimScenario(
  processed: ProcessedScenario,
  symbol: string,
  tf: string
): SimScenario {
  return {
    scenarioId: processed.scenarioId,
    symbol,
    tf,
    side: processed.direction,
    probability: processed.pEntry,
    patternType: processed.patternType,
    risk: {
      entryType: 'LIMIT_PULLBACK',
      entryPrice: processed.entry,
      stopPrice: processed.stop,
      target1Price: processed.target1,
      target2Price: processed.target2,
      entryTimeoutBars: 10,
      tradeTimeoutBars: 50,
    },
    // V4 specific fields for dataset hook
    _v4: {
      geometry: processed.geometry,
      gateScore: processed.gateScore,
      gateResult: processed.gate,
      graphBoost: processed.graphBoost,
      regime: processed.regime,
      regimeConfidence: processed.regimeConfidence,
      pEntry: processed.pEntry,
      rExpected: processed.rExpected,
      evBeforeML: processed.evBeforeML,
      evAfterML: processed.evAfterML,
      features: processed.features,
      modelId: 'mock_v1',
    },
  } as SimScenario & { _v4: any };
}

/**
 * Create Decision Provider that wraps DecisionEngine
 */
export function createDecisionProvider(db: Db): IDecisionProvider {
  const engine = createDecisionEngine(db);
  
  // Pattern detection stub - in production would use pattern_registry
  const detectPatterns = (candles: CandleData[], symbol: string, tf: string): ScenarioInput[] => {
    // Simplified pattern detection for wiring test
    // Real implementation calls pattern registry
    const last = candles[candles.length - 1];
    if (!last) return [];
    
    const atr = calculateATR(candles);
    const currentPrice = last.close;
    
    // Detect simple support/resistance levels for demo
    const scenarios: ScenarioInput[] = [];
    
    // Look for recent swing points
    const recentCandles = candles.slice(-30);
    const highs = recentCandles.map(c => c.high);
    const lows = recentCandles.map(c => c.low);
    
    const resistance = Math.max(...highs);
    const support = Math.min(...lows);
    const range = resistance - support;
    
    if (range < atr * 0.5) return []; // No clear structure
    
    // If price near support, potential LONG
    if (currentPrice < support + range * 0.3) {
      scenarios.push({
        scenarioId: `${symbol}_${tf}_${Date.now()}_long`,
        patternType: 'SUPPORT_BOUNCE',
        direction: 'LONG',
        entry: support + atr * 0.1,
        stop: support - atr * 0.5,
        target1: support + range * 0.5,
        target2: resistance,
        score: 0.6,
        confidence: 0.55,
        touches: 2,
        pivotHighs: [resistance],
        pivotLows: [support],
        pivotHighIdxs: [highs.indexOf(resistance)],
        pivotLowIdxs: [lows.indexOf(support)],
        startIdx: candles.length - 30,
        endIdx: candles.length - 1,
      });
    }
    
    // If price near resistance, potential SHORT
    if (currentPrice > resistance - range * 0.3) {
      scenarios.push({
        scenarioId: `${symbol}_${tf}_${Date.now()}_short`,
        patternType: 'RESISTANCE_REJECTION',
        direction: 'SHORT',
        entry: resistance - atr * 0.1,
        stop: resistance + atr * 0.5,
        target1: resistance - range * 0.5,
        target2: support,
        score: 0.6,
        confidence: 0.55,
        touches: 2,
        pivotHighs: [resistance],
        pivotLows: [support],
        pivotHighIdxs: [highs.indexOf(resistance)],
        pivotLowIdxs: [lows.indexOf(support)],
        startIdx: candles.length - 30,
        endIdx: candles.length - 1,
      });
    }
    
    return scenarios;
  };

  return {
    async getDecision(symbol: string, tf: string, nowTs: number, candles: SimCandle[]): Promise<any> {
      // Convert candles
      const candleData = convertCandles(candles);
      
      if (candleData.length < 30) {
        return null; // Not enough data
      }
      
      // Calculate ATR
      const atr = calculateATR(candleData);
      const currentPrice = candleData[candleData.length - 1].close;
      
      // Detect patterns/scenarios
      const scenarios = detectPatterns(candleData, symbol, tf);
      
      if (scenarios.length === 0) {
        return null;
      }
      
      // Build context
      const ctx: DecisionContext = {
        asset: symbol,
        timeframe: tf,
        timestamp: new Date(nowTs * 1000),
        candles: candleData,
        currentPrice,
        atr,
        scenarios,
        recentPatterns: [], // Would be populated from history
      };
      
      // Get decision from unified engine
      const decisionPack = await engine.computeDecision(ctx);
      
      if (!decisionPack.topScenario) {
        return null;
      }
      
      // Convert to SimScenario
      return processedToSimScenario(decisionPack.topScenario, symbol, tf);
    },
  };
}

/**
 * Calculate ATR (Average True Range)
 */
function calculateATR(candles: CandleData[], period: number = 14): number {
  if (candles.length < period + 1) {
    // Fallback to simple range average
    const ranges = candles.slice(-period).map(c => c.high - c.low);
    return ranges.reduce((a, b) => a + b, 0) / ranges.length;
  }
  
  let atr = 0;
  for (let i = candles.length - period; i < candles.length; i++) {
    const curr = candles[i];
    const prev = candles[i - 1];
    if (!prev) continue;
    
    const tr = Math.max(
      curr.high - curr.low,
      Math.abs(curr.high - prev.close),
      Math.abs(curr.low - prev.close)
    );
    atr += tr;
  }
  
  return atr / period;
}

/**
 * Export engine for direct use in API
 */
export { createDecisionEngine };
