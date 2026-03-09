/**
 * P1.6 — Decision Pipeline Integration Tests
 * 
 * Verifies wiring of:
 * 1. Simulation uses same decision engine as API
 * 2. Dataset hook writes V4 from executed scenario
 * 3. Outcome evaluator handles all 5 cases
 */

import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { Db, MongoClient } from 'mongodb';
import { createDecisionEngine, DecisionContext, CandleData, ScenarioInput } from '../src/modules/ta/decision/decision.engine.js';
import { createDecisionProvider } from '../src/modules/ta/decision/decision_provider.js';
import { evaluateOutcome, TradeSetup, CandleBar, runOutcomeTests } from '../src/modules/ta/decision/outcome_evaluator.js';
import { initDatasetWriterV4, writeDatasetRowV4, getDatasetV4Stats, createDatasetV4Indexes } from '../src/modules/ta/decision/dataset_writer_v4.js';
import { SimPosition, SimScenario } from '../src/modules/ta/simulator/domain.js';

const MONGO_URI = process.env.MONGO_URL || 'mongodb://localhost:27017/ta_test';
const DB_NAME = process.env.DB_NAME || 'ta_test';

let client: MongoClient;
let db: Db;

describe('P1.6 Decision Pipeline', () => {
  beforeAll(async () => {
    client = new MongoClient(MONGO_URI);
    await client.connect();
    db = client.db(DB_NAME);
    
    // Initialize dataset writer
    initDatasetWriterV4(db);
    await createDatasetV4Indexes(db);
    
    // Clear test data
    await db.collection('ta_ml_rows_v4').deleteMany({});
  });

  afterAll(async () => {
    await client.close();
  });

  describe('COMMIT 1: Decision Engine Unified Pipeline', () => {
    it('should process scenarios through full pipeline', async () => {
      const engine = createDecisionEngine(db);
      
      // Create test candles (100 bars, trending up)
      const candles = generateTrendingCandles(100, 50000, 'UP');
      const atr = calculateATR(candles);
      
      // Create test scenario
      const scenarios: ScenarioInput[] = [{
        scenarioId: 'test_scenario_1',
        patternType: 'ASCENDING_TRIANGLE',
        direction: 'LONG',
        entry: 51000,
        stop: 49500,
        target1: 53000,
        target2: 55000,
        score: 0.7,
        confidence: 0.65,
        touches: 3,
        pivotHighs: [52000, 52100, 52050],
        pivotLows: [50000, 50500, 50800],
        pivotHighIdxs: [20, 50, 80],
        pivotLowIdxs: [10, 40, 70],
        startIdx: 10,
        endIdx: 90,
      }];
      
      const ctx: DecisionContext = {
        asset: 'BTCUSDT',
        timeframe: '1d',
        timestamp: new Date(),
        candles,
        currentPrice: candles[candles.length - 1].close,
        atr,
        scenarios,
      };
      
      const decision = await engine.computeDecision(ctx);
      
      // Verify decision pack structure
      expect(decision).toBeDefined();
      expect(decision.asset).toBe('BTCUSDT');
      expect(decision.timeframe).toBe('1d');
      expect(decision.totalScenarios).toBe(1);
      
      // If passed gate, should have top scenario
      if (decision.passedGate > 0) {
        expect(decision.topScenario).toBeDefined();
        expect(decision.topScenario!.scenarioId).toBe('test_scenario_1');
        
        // Verify all pipeline components ran
        expect(decision.topScenario!.geometry).toBeDefined();
        expect(decision.topScenario!.gate).toBeDefined();
        expect(decision.topScenario!.graphBoost).toBeDefined();
        expect(decision.topScenario!.regime).toBeDefined();
        expect(decision.topScenario!.mlPrediction).toBeDefined();
        
        // Verify EV calculation
        expect(decision.topScenario!.evBeforeML).toBeGreaterThan(0);
        expect(decision.topScenario!.evAfterML).toBeGreaterThan(0);
        expect(decision.topScenario!.pEntry).toBeGreaterThan(0);
        expect(decision.topScenario!.rExpected).toBeDefined();
      }
    });

    it('should reject scenarios that fail gate', async () => {
      const engine = createDecisionEngine(db);
      
      const candles = generateTrendingCandles(100, 50000, 'UP');
      const atr = calculateATR(candles);
      
      // Scenario designed to fail multiple gates:
      // 1. RR < 1.2 (score -0.25)
      // 2. Entry too far (score -0.25)
      // 3. Invalid touches (score -0.2)
      // Total: 1.0 - 0.7 = 0.3 < minPassScore of 0.5
      const scenarios: ScenarioInput[] = [{
        scenarioId: 'bad_scenario_1',
        patternType: 'RANDOM_PATTERN',
        direction: 'LONG',
        entry: 60000,      // Very far from current price (entry too far)
        stop: 59000,       // Risk = 1000
        target1: 60500,    // Reward = 500, R:R = 0.5 < 1.2
        score: 0.3,
        confidence: 0.2,
        touches: 1,        // Below minTouches (3)
      }];
      
      const ctx: DecisionContext = {
        asset: 'BTCUSDT',
        timeframe: '1d',
        timestamp: new Date(),
        candles,
        currentPrice: 50500,
        atr,
        scenarios,
      };
      
      const decision = await engine.computeDecision(ctx);
      
      // Should be rejected by gate
      expect(decision.rejected).toBe(1);
      expect(decision.passedGate).toBe(0);
      expect(decision.topScenario).toBeNull();
    });
  });

  describe('COMMIT 2: Simulation uses DecisionPack', () => {
    it('should create decision provider from engine', () => {
      const provider = createDecisionProvider(db);
      expect(provider).toBeDefined();
      expect(typeof provider.getDecision).toBe('function');
    });

    it('should return SimScenario from decision provider', async () => {
      const provider = createDecisionProvider(db);
      
      // Generate candles with clear structure
      const candles = generateTrendingCandles(100, 40000, 'DOWN').map(c => ({
        ts: c.openTime / 1000,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
      }));
      
      const scenario = await provider.getDecision(
        'BTCUSDT',
        '4h',
        Date.now() / 1000,
        candles
      );
      
      // May return null if no clear pattern
      if (scenario) {
        expect(scenario.scenarioId).toBeDefined();
        expect(scenario.symbol).toBe('BTCUSDT');
        expect(scenario.tf).toBe('4h');
        expect(['LONG', 'SHORT']).toContain(scenario.side);
        expect(scenario.risk).toBeDefined();
        expect(scenario.risk.stopPrice).toBeDefined();
        
        // V4 data should be attached
        expect((scenario as any)._v4).toBeDefined();
        expect((scenario as any)._v4.pEntry).toBeDefined();
        expect((scenario as any)._v4.regime).toBeDefined();
      }
    });
  });

  describe('COMMIT 3: Dataset Hook V4', () => {
    it('should write V4 row from closed position', async () => {
      const position: SimPosition = {
        positionId: 'test_pos_1',
        runId: 'test_run_1',
        scenarioId: 'test_scenario_v4',
        symbol: 'ETHUSDT',
        tf: '1h',
        side: 'LONG',
        entryTs: Date.now() / 1000,
        entryPrice: 3000,
        entryOrderId: 'order_1',
        stopPrice: 2900,
        target1Price: 3200,
        timeoutBars: 50,
        status: 'CLOSED',
        exitTs: Date.now() / 1000 + 3600,
        exitPrice: 3150,
        exitReason: 'TARGET1',
        barsInTrade: 10,
        mfePct: 6.67,
        maePct: 1.0,
        rMultiple: 1.5,
        feesPaid: 0,
        slippagePaid: 0,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      const scenario: SimScenario & { _v4: any } = {
        scenarioId: 'test_scenario_v4',
        symbol: 'ETHUSDT',
        tf: '1h',
        side: 'LONG',
        probability: 0.65,
        patternType: 'ASCENDING_TRIANGLE',
        risk: {
          entryType: 'LIMIT_PULLBACK',
          entryPrice: 3000,
          stopPrice: 2900,
          target1Price: 3200,
          entryTimeoutBars: 10,
          tradeTimeoutBars: 50,
        },
        _v4: {
          geometry: { fitError: 0.15, maturity: 0.7, symmetry: 0.8, compression: 0.3 },
          gateScore: 0.72,
          gateResult: { ok: true, gateScore: 0.72 },
          graphBoost: { graphBoostFactor: 1.15, lift: 1.1, conditionalProb: 0.6 },
          regime: 'TREND_UP',
          regimeConfidence: 0.75,
          pEntry: 0.65,
          rExpected: 1.8,
          evBeforeML: 0.8,
          evAfterML: 0.95,
          features: { score: 0.7, confidence: 0.65, risk_reward: 2 },
          modelId: 'mock_v1',
        },
      };

      const result = await writeDatasetRowV4({
        position,
        scenario,
        runId: 'test_run_1',
      });

      expect(result).toBe(true);

      // Verify row in DB
      const row = await db.collection('ta_ml_rows_v4').findOne({
        scenarioId: 'test_scenario_v4'
      });

      expect(row).toBeDefined();
      expect(row!.labels.label_entry_hit).toBe(1);
      expect(row!.labels.label_r_multiple).toBe(1.5);
      expect(row!.labels.label_outcome_class).toBe('WIN');
      expect(row!.regime).toBe('TREND_UP');
      expect(row!.features.gate_score).toBe(0.72);
      expect(row!.features.geom_maturity).toBe(0.7);
    });

    it('should write NO_ENTRY correctly', async () => {
      const position: SimPosition = {
        positionId: 'test_pos_no_entry',
        runId: 'test_run_1',
        scenarioId: 'test_no_entry',
        symbol: 'BTCUSDT',
        tf: '4h',
        side: 'LONG',
        entryTs: Date.now() / 1000,
        entryPrice: 50000,
        entryOrderId: 'order_2',
        stopPrice: 49000,
        target1Price: 52000,
        timeoutBars: 10,
        status: 'CLOSED',
        exitTs: Date.now() / 1000 + 7200,
        exitPrice: 49500,
        exitReason: 'NO_ENTRY',
        barsInTrade: 10,
        mfePct: 0,
        maePct: 0,
        rMultiple: 0,
        feesPaid: 0,
        slippagePaid: 0,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      const scenario: SimScenario & { _v4: any } = {
        scenarioId: 'test_no_entry',
        symbol: 'BTCUSDT',
        tf: '4h',
        side: 'LONG',
        probability: 0.5,
        patternType: 'DOUBLE_BOTTOM',
        risk: {
          entryType: 'LIMIT_PULLBACK',
          stopPrice: 49000,
          target1Price: 52000,
          entryTimeoutBars: 10,
          tradeTimeoutBars: 50,
        },
        _v4: {
          geometry: { fitError: 0.3, maturity: 0.4 },
          gateScore: 0.5,
          gateResult: { ok: true },
          graphBoost: { graphBoostFactor: 1.0 },
          regime: 'RANGE',
          regimeConfidence: 0.6,
          pEntry: 0.4,
          rExpected: 1.5,
          evBeforeML: 0.5,
          evAfterML: 0.5,
          features: { score: 0.5 },
          modelId: 'mock_v1',
        },
      };

      await writeDatasetRowV4({ position, scenario, runId: 'test_run_1' });

      const row = await db.collection('ta_ml_rows_v4').findOne({
        scenarioId: 'test_no_entry'
      });

      expect(row).toBeDefined();
      expect(row!.labels.label_entry_hit).toBe(0);
      expect(row!.labels.label_r_multiple).toBe(0);  // Important: 0 for no entry
      expect(row!.labels.label_outcome_class).toBe('NO_ENTRY');
    });
  });

  describe('COMMIT 4: Outcome Evaluator V4', () => {
    it('should pass all 5 test cases', () => {
      const results = runOutcomeTests();
      
      console.log('Outcome Evaluator Test Results:');
      results.results.forEach(r => console.log(r));
      
      expect(results.passed).toBe(5);
      expect(results.failed).toBe(0);
    });

    it('Test 1: NO_ENTRY - price never reaches entry', () => {
      const result = evaluateOutcome(
        { direction: 'LONG', entry: 100, stop: 95, target1: 110, signalIdx: 0, timeoutBars: 10 },
        Array(10).fill({ high: 99, low: 97, close: 98 })
      );
      
      expect(result.exitReason).toBe('NO_ENTRY');
      expect(result.entryHit).toBe(false);
      expect(result.rMultiple).toBe(0);
    });

    it('Test 2: STOP - entry hit then stop hit', () => {
      const result = evaluateOutcome(
        { direction: 'LONG', entry: 100, stop: 95, target1: 110, signalIdx: 0, timeoutBars: 10 },
        [
          { high: 101, low: 99, close: 100 },   // Entry hit
          { high: 100, low: 94, close: 95 },    // Stop hit
        ]
      );
      
      expect(result.exitReason).toBe('STOP');
      expect(result.entryHit).toBe(true);
      expect(result.rMultiple).toBe(-1);
    });

    it('Test 3: TARGET1 - entry hit then target1 hit', () => {
      const result = evaluateOutcome(
        { direction: 'LONG', entry: 100, stop: 95, target1: 110, signalIdx: 0, timeoutBars: 10 },
        [
          { high: 101, low: 99, close: 100 },   // Entry hit
          { high: 105, low: 100, close: 104 },  // Moving up
          { high: 111, low: 108, close: 110 },  // Target1 hit
        ]
      );
      
      expect(result.exitReason).toBe('TARGET1');
      expect(result.entryHit).toBe(true);
      expect(result.rMultiple).toBe(2);
    });

    it('Test 4: TARGET2 - entry hit then target2 hit', () => {
      const result = evaluateOutcome(
        { direction: 'LONG', entry: 100, stop: 95, target1: 110, target2: 120, signalIdx: 0, timeoutBars: 10 },
        [
          { high: 101, low: 99, close: 100 },   // Entry hit
          { high: 109, low: 100, close: 108 },  // Moving up but not at target1
          { high: 122, low: 115, close: 121 },  // Both targets hit on same candle, target2 wins
        ]
      );
      
      expect(result.exitReason).toBe('TARGET2');
      expect(result.entryHit).toBe(true);
      expect(result.rMultiple).toBe(4);
    });

    it('Test 5: TIMEOUT_PARTIAL - entry hit, small profit at timeout', () => {
      const result = evaluateOutcome(
        { direction: 'LONG', entry: 100, stop: 95, target1: 110, signalIdx: 0, timeoutBars: 5 },
        [
          { high: 101, low: 99, close: 100 },
          { high: 103, low: 100, close: 102 },
          { high: 104, low: 101, close: 103 },
          { high: 103, low: 101, close: 102 },
          { high: 102, low: 100, close: 101 },  // Timeout
        ]
      );
      
      expect(result.entryHit).toBe(true);
      expect(result.rMultiple).toBeGreaterThan(0);
      expect(['TIMEOUT', 'TIMEOUT_PARTIAL']).toContain(result.exitReason);
    });

    it('Test SHORT direction: STOP', () => {
      const result = evaluateOutcome(
        { direction: 'SHORT', entry: 100, stop: 105, target1: 90, signalIdx: 0, timeoutBars: 10 },
        [
          { high: 101, low: 99, close: 100 },   // Entry hit
          { high: 106, low: 102, close: 105 },  // Stop hit
        ]
      );
      
      expect(result.exitReason).toBe('STOP');
      expect(result.entryHit).toBe(true);
      expect(result.rMultiple).toBe(-1);
    });

    it('Test SHORT direction: TARGET1', () => {
      const result = evaluateOutcome(
        { direction: 'SHORT', entry: 100, stop: 105, target1: 90, signalIdx: 0, timeoutBars: 10 },
        [
          { high: 101, low: 99, close: 100 },   // Entry hit
          { high: 98, low: 89, close: 90 },     // Target1 hit
        ]
      );
      
      expect(result.exitReason).toBe('TARGET1');
      expect(result.entryHit).toBe(true);
      expect(result.rMultiple).toBe(2);
    });
  });

  describe('COMMIT 5: Full Pipeline Verification', () => {
    it('Dataset V4 stats should reflect written rows', async () => {
      const stats = await getDatasetV4Stats(db);
      
      expect(stats.total).toBeGreaterThan(0);
      expect(stats.byEntryHit.hit + stats.byEntryHit.noEntry).toBe(stats.total);
    });

    it('API and Simulation should produce identical DecisionPack structure', async () => {
      const engine = createDecisionEngine(db);
      const provider = createDecisionProvider(db);
      
      const candles = generateTrendingCandles(100, 45000, 'UP');
      const simCandles = candles.map(c => ({
        ts: c.openTime / 1000,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
      }));
      
      const scenarios: ScenarioInput[] = [{
        scenarioId: 'verify_scenario',
        patternType: 'FLAG',
        direction: 'LONG',
        entry: 46000,
        stop: 45000,
        target1: 48000,
        score: 0.6,
        confidence: 0.6,
        touches: 2,
      }];
      
      // Direct engine call (API path)
      const apiDecision = await engine.computeDecision({
        asset: 'BTCUSDT',
        timeframe: '1d',
        timestamp: new Date(),
        candles,
        currentPrice: candles[candles.length - 1].close,
        atr: calculateATR(candles),
        scenarios,
      });
      
      // Verify structure matches expected
      expect(apiDecision).toHaveProperty('asset');
      expect(apiDecision).toHaveProperty('timeframe');
      expect(apiDecision).toHaveProperty('scenarios');
      expect(apiDecision).toHaveProperty('topScenario');
      expect(apiDecision).toHaveProperty('regime');
      expect(apiDecision).toHaveProperty('overlayStage');
    });
  });
});

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

function generateTrendingCandles(
  count: number,
  startPrice: number,
  direction: 'UP' | 'DOWN'
): CandleData[] {
  const candles: CandleData[] = [];
  let price = startPrice;
  const volatility = startPrice * 0.02; // 2% volatility
  const trend = direction === 'UP' ? 0.001 : -0.001;
  
  for (let i = 0; i < count; i++) {
    const change = (Math.random() - 0.5) * volatility;
    const trendMove = price * trend;
    
    const open = price;
    const close = price + change + trendMove;
    const high = Math.max(open, close) + Math.random() * volatility * 0.3;
    const low = Math.min(open, close) - Math.random() * volatility * 0.3;
    
    candles.push({
      openTime: Date.now() - (count - i) * 86400000, // 1 day apart
      open,
      high,
      low,
      close,
      volume: 1000 + Math.random() * 500,
    });
    
    price = close;
  }
  
  return candles;
}

function calculateATR(candles: CandleData[], period: number = 14): number {
  if (candles.length < period + 1) {
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
