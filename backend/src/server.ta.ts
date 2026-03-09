/**
 * TA Isolated Server — Minimal boot for TA module development
 * 
 * Phase 8.2-8.6 + P5.0.9: TA Engine Core Runtime with Edge Attribution
 * 
 * Starts only:
 * - MongoDB connection
 * - TA Module (Core + Patterns + Outcomes V3 + Scheduler V2 + Graph)
 * - Edge Attribution Module (P5.0.9)
 * 
 * Usage: yarn dev:ta
 */

import 'dotenv/config';
import Fastify, { FastifyInstance } from 'fastify';
import cors from '@fastify/cors';
import { connectMongo, disconnectMongo, getMongoDb } from './db/mongoose.js';
import { taRoutes } from './modules/ta/runtime/ta.controller.js';
import { initializeDetectors } from './modules/ta/detectors/index.js';
import { registerBinanceHistoricalRoutes } from './modules/market/providers/binance/binance.routes.js';
import { registerBinanceArchiveRoutes } from './modules/market/providers/binance/archive/archive.routes.js';

// Phase 8.3: Outcomes V3
import { registerOutcomesV3Routes } from './modules/ta/outcomes_v3/outcomes_v3.routes.js';

// Phase 8.5: Scheduler V2
import { registerSchedulerV2Routes } from './modules/ta/scheduler_v2/scheduler.routes.js';

// Phase 8.6: Graph
import { registerGraphRoutes } from './modules/ta/graph/graph.routes.js';

// P1.2: Geometry Engine
import { registerGeometryRoutes } from './modules/ta/geometry/geometry.routes.js';

// P1.3-P1.5: ML V4 (EV decomposition + Time split + Regime mixture)
import { registerMLV4Routes } from './modules/ta/ml_v4/ml_v4.routes.js';

// P1.6: Unified Decision Pipeline
import { registerDecisionRoutes } from './modules/ta/decision/decision.routes.js';

// D1: Structure-Aware Scoring
import { registerStructureScoringRoutes } from './modules/ta/decision/structure_scoring.routes.js';

// P1.6.1, P1.9, P2.0: Research Layer
import { registerResearchRoutes } from './modules/ta/research/research.routes.js';

// Data backfill
import { registerDataRoutes } from './modules/ta/data/data.routes.js';

// P2.1, P2.7, P3.1: Advanced modules
import { registerAdvancedRoutes } from './modules/ta/advanced.routes.js';

// Hardening: Audit, Registry, Health
import { registerHardeningRoutes } from './modules/ta/hardening/hardening.routes.js';

// Phase 4 prep routes
import { registerPhase4Routes } from './modules/ta/phase4/index.js';

// P4.1: Intelligence Layer
import { registerIntelligenceRoutes } from './modules/ta/routes/intelligence.routes.js';

// P4.2-4.4: Probability, Explanation, Forecast
import { registerP4Routes } from './modules/ta/routes/p4.routes.js';

// P5.0: Edge Attribution Engine
import { registerEdgeModule } from './modules/edge/index.js';

// M1: Market State Engine
import { registerMarketStateModule } from './modules/marketState/index.js';

// C1: Context Engine
import { registerContextModule } from './modules/context/index.js';

// L1: Liquidity Engine
import { registerLiquidityModule } from './modules/liquidity/index.js';

// G1-G3: Market Structure Graph
import { registerMarketGraphModule } from './modules/market_graph/index.js';

// D2: Fractal Engine
import { registerFractalModule } from './modules/fractal_engine/index.js';

// Analysis Mode Engine
import { registerAnalysisModeModule } from './modules/analysis_mode/index.js';

// Governance Engine
import { registerGovernanceModule } from './modules/governance/index.js';

// D3: Market Physics Engine
import { registerMarketPhysicsModule } from './modules/market_physics/index.js';

// D4: State Transition Engine
import { registerStateEngineModule } from './modules/state_engine/index.js';

// Phase 6: Scenario Engine 2.0
import { registerScenarioRoutes } from './modules/scenario_engine/index.js';

// Phase 7: Edge Intelligence Layer
import { registerEdgeIntelligenceRoutes } from './modules/edge_intelligence/index.js';

// Phase 8: Strategy Builder
import { registerStrategyRoutes as registerStrategyBuilderRoutes } from './modules/strategy_builder/index.js';

// Phase 9: Regime Intelligence Engine
import { registerRegimeRoutes } from './modules/regime/index.js';

// Phase 10: Execution Intelligence
import { registerExecutionRoutes } from './modules/execution/index.js';

// Phase 11: MetaBrain - Global Policy Layer
import { registerMetaBrainRoutes } from './modules/metabrain/index.js';

// Phase 11.1: MetaBrain Learning Layer
import { registerLearningRoutes } from './modules/metabrain_learning/index.js';

// Phase 12: Digital Twin (DT1-DT4)
import { registerDigitalTwinRoutes, registerTreeRoutes } from './modules/digital_twin/index.js';

// Phase 13: Market Memory Engine (MM1-MM2)
import { registerMemoryRoutes } from './modules/market_memory/index.js';

// P1.3: Memory-conditioned MetaBrain Policies (MM3)
import { registerMemoryPolicyRoutes } from './modules/metabrain_memory/index.js';

// P1.4: Regime-conditioned Learning
import { registerRegimeLearningRoutes } from './modules/metabrain_regime/index.js';

// MetaBrain v3: Self-Optimizing System
import { registerMetaBrainV3Routes } from './modules/metabrain_v3/index.js';

// Real-time WebSocket Layer
import { registerRealtimeRoutes, setupWebSocketServer } from './modules/realtime/index.js';

// System Dashboard (Observability)
import { registerDashboardRoutes } from './modules/dashboard/index.js';

// ANN Memory Index
import { registerMemoryIndexRoutes } from './modules/memory_index/index.js';

// Chart Intelligence Layer (Phase 1)
import { registerChartIntelligenceRoutes } from './modules/chart/intelligence/index.js';

// Market Map Layer (Phase 2.5)
import { registerMarketMapRoutes } from './modules/market_map/index.js';

// Admin Control Plane (Phase 3)
import { registerAdminControlRoutes } from './modules/admin_control/index.js';

// Observability Layer (Phase 4)
import { registerObservabilityRoutes } from './modules/observability/index.js';

// Strategy Platform (Phase 5)
import { registerStrategyRoutes as registerStrategyPlatformRoutes } from './modules/strategy/index.js';

// Portfolio Intelligence (Phase 5.5)
import { registerPortfolioRoutes } from './modules/portfolio/index.js';

// Indicators Layer (Phase 6)
import { registerIndicatorRoutes } from './modules/indicators/index.js';

// Phase 6.5: MTF Confirmation Layer
import { registerMTFV2Routes, initMTFV2Indexes } from './modules/mtf_v2/index.js';

const PORT = parseInt(process.env.PORT || '8001', 10);

async function main(): Promise<void> {
  console.log('[TA Server] Starting isolated TA module...');

  // Connect to MongoDB
  console.log('[TA Server] Connecting to MongoDB...');
  await connectMongo();
  console.log('[TA Server] ✅ MongoDB connected');

  // Build minimal Fastify app
  const app: FastifyInstance = Fastify({
    logger: {
      level: 'info',
    },
    trustProxy: true,
  });

  // CORS
  await app.register(cors, {
    origin: true,
    credentials: true,
  });

  // Health endpoint
  app.get('/api/health', async () => ({
    ok: true,
    mode: 'TA_ONLY',
    version: '2.0.0',
    timestamp: new Date().toISOString()
  }));

  // System health endpoint (for frontend compatibility)
  app.get('/api/system/health', async () => ({
    status: 'healthy',
    ts: new Date().toISOString(),
    services: {},
    metrics: { bootstrap: {} },
    notes: ['TA_ONLY mode - isolated TA module'],
  }));

  // Initialize TA detectors
  console.log('[TA Server] Initializing TA detectors...');
  initializeDetectors();

  // Register TA routes
  console.log('[TA Server] Registering TA module at /api/ta/*...');
  await app.register(taRoutes, { prefix: '/api/ta' });

  // Register Binance Historical Data routes (Phase 7.5)
  console.log('[TA Server] Registering Binance Historical routes...');
  const db = getMongoDb();
  await registerBinanceHistoricalRoutes(app, { mongoDb: db });

  // Register Binance Archive routes (Phase 7.8-7.9)
  console.log('[TA Server] Registering Binance Archive routes...');
  await registerBinanceArchiveRoutes(app, { mongoDb: db });

  // Phase 8.3: Register Outcomes V3 routes
  console.log('[TA Server] Registering Outcomes V3 routes (Phase 8.3)...');
  await app.register(async (instance) => {
    await registerOutcomesV3Routes(instance, { db });
  }, { prefix: '/api/ta' });

  // Phase 8.5: Register Scheduler V2 routes
  console.log('[TA Server] Registering Scheduler V2 routes (Phase 8.5)...');
  await app.register(async (instance) => {
    await registerSchedulerV2Routes(instance, { db });
  }, { prefix: '/api/ta' });

  // Phase 8.6: Register Graph routes
  console.log('[TA Server] Registering Graph routes (Phase 8.6)...');
  await app.register(async (instance) => {
    await registerGraphRoutes(instance, { db });
  }, { prefix: '/api/ta' });

  // P1.2: Register Geometry routes
  console.log('[TA Server] Registering Geometry routes (P1.2)...');
  await app.register(async (instance) => {
    await registerGeometryRoutes(instance, { db });
  }, { prefix: '/api/ta' });

  // P1.3-P1.5: Register ML V4 routes
  console.log('[TA Server] Registering ML V4 routes (P1.3-P1.5)...');
  await app.register(async (instance) => {
    await registerMLV4Routes(instance, { db });
  }, { prefix: '/api/ta' });

  // P1.6: Register Decision routes (Unified Pipeline)
  console.log('[TA Server] Registering Decision routes (P1.6)...');
  await app.register(async (instance) => {
    await registerDecisionRoutes(instance, { db });
  }, { prefix: '/api/ta' });

  // D1: Structure-Aware Scoring
  console.log('[TA Server] Registering Structure-Aware Scoring (D1)...');
  await app.register(async (instance) => {
    await registerStructureScoringRoutes(instance, { db });
  }, { prefix: '/api/ta' });

  // P1.6.1, P1.9, P2.0: Register Research routes
  console.log('[TA Server] Registering Research routes (P1.6.1, P1.9, P2.0)...');
  await app.register(async (instance) => {
    await registerResearchRoutes(instance, { db });
  }, { prefix: '/api/ta' });

  // Data routes
  console.log('[TA Server] Registering Data routes...');
  await app.register(async (instance) => {
    await registerDataRoutes(instance, { db });
  }, { prefix: '/api/ta' });

  // P2.1, P2.7, P3.1: Advanced routes
  console.log('[TA Server] Registering Advanced routes (P2.1, P2.7, P3.1)...');
  await app.register(async (instance) => {
    await registerAdvancedRoutes(instance, { db });
  }, { prefix: '/api/ta' });

  // Hardening: Audit, Registry, Health
  console.log('[TA Server] Registering Hardening routes (Audit, Registry, Health)...');
  await app.register(async (instance) => {
    await registerHardeningRoutes(instance, { db });
  }, { prefix: '/api/ta' });

  // Phase 4 prep routes
  console.log('[TA Server] Registering Phase 4 prep routes...');
  await app.register(async (instance) => {
    await registerPhase4Routes(instance, { db });
  }, { prefix: '/api/ta' });

  // P4.1: Intelligence Layer routes
  console.log('[TA Server] Registering Intelligence routes (P4.1)...');
  await app.register(async (instance) => {
    await registerIntelligenceRoutes(instance, { db });
  }, { prefix: '/api/ta' });

  // P4.2-4.4: Probability, Explanation, Forecast routes
  console.log('[TA Server] Registering P4.2-4.4 routes...');
  await app.register(async (instance) => {
    await registerP4Routes(instance, { db });
  }, { prefix: '/api/ta' });

  // P5.0: Edge Attribution Engine
  console.log('[TA Server] Registering Edge Attribution routes (P5.0)...');
  await app.register(async (instance) => {
    await registerEdgeModule(instance, { db });
  }, { prefix: '/api/ta' });

  // P5.1: Backtest Harness
  console.log('[TA Server] Registering Backtest Harness routes (P5.1)...');
  const { registerBacktestModule } = await import('./modules/backtest/index.js');
  await app.register(async (instance) => {
    await registerBacktestModule(instance, { db });
  }, { prefix: '/api/ta' });

  // P5.2: Calibration Engine
  console.log('[TA Server] Registering Calibration Engine (P5.2)...');
  const { registerCalibrationModule } = await import('./modules/calibration/index.js');
  await app.register(async (instance) => {
    await registerCalibrationModule(instance, { db });
  }, { prefix: '/api/ta' });

  // P5.3: Coverage Matrix
  console.log('[TA Server] Registering Coverage Matrix (P5.3)...');
  const { registerCoverageModule } = await import('./modules/coverage/index.js');
  await app.register(async (instance) => {
    await registerCoverageModule(instance, { db });
  }, { prefix: '/api/ta' });

  // P5.3: Backtest Scheduler
  console.log('[TA Server] Registering Backtest Scheduler (P5.3)...');
  const { registerSchedulerModule } = await import('./modules/scheduler/backtest.scheduler.js');
  await app.register(async (instance) => {
    await registerSchedulerModule(instance, { db });
  }, { prefix: '/api/ta' });

  // P5.4: Edge Autopilot
  console.log('[TA Server] Registering Edge Autopilot (P5.4)...');
  const { registerAutopilotModule } = await import('./modules/autopilot/index.js');
  await app.register(async (instance) => {
    await registerAutopilotModule(instance, { db });
  }, { prefix: '/api/ta' });

  // P5.5: Replay & Audit
  console.log('[TA Server] Registering Replay & Audit (P5.5)...');
  const { registerAuditModule } = await import('./modules/audit/index.js');
  await app.register(async (instance) => {
    await registerAuditModule(instance, { db });
  }, { prefix: '/api/ta' });

  // M1: Market State Engine
  console.log('[TA Server] Registering Market State Engine (M1)...');
  await app.register(async (instance) => {
    await registerMarketStateModule(instance, { db });
  }, { prefix: '/api/ta' });

  // C1: Context Engine
  console.log('[TA Server] Registering Context Engine (C1)...');
  await app.register(async (instance) => {
    await registerContextModule(instance, { db });
  }, { prefix: '/api/ta' });

  // L1: Liquidity Engine
  console.log('[TA Server] Registering Liquidity Engine (L1)...');
  await app.register(async (instance) => {
    await registerLiquidityModule(instance, { db });
  }, { prefix: '/api/ta' });

  // G1-G3: Market Structure Graph
  console.log('[TA Server] Registering Market Structure Graph (G1-G3)...');
  await app.register(async (instance) => {
    await registerMarketGraphModule(instance, { db });
  }, { prefix: '/api/ta' });

  // D2: Fractal Engine
  console.log('[TA Server] Registering Fractal Engine (D2)...');
  await app.register(async (instance) => {
    await registerFractalModule(instance, { db });
  }, { prefix: '/api/ta' });

  // Analysis Mode Engine
  console.log('[TA Server] Registering Analysis Mode Engine...');
  await app.register(async (instance) => {
    await registerAnalysisModeModule(instance, { db });
  }, { prefix: '/api/ta' });

  // Governance Engine
  console.log('[TA Server] Registering Governance Engine...');
  await app.register(async (instance) => {
    await registerGovernanceModule(instance, { db });
  }, { prefix: '/api/ta' });

  // D3: Market Physics Engine
  console.log('[TA Server] Registering Market Physics Engine (D3)...');
  await app.register(async (instance) => {
    await registerMarketPhysicsModule(instance, { db });
  }, { prefix: '/api/ta' });

  // D4: State Transition Engine
  console.log('[TA Server] Registering State Transition Engine (D4)...');
  await app.register(async (instance) => {
    await registerStateEngineModule(instance, { db });
  }, { prefix: '/api/ta' });

  // Phase 6: Scenario Engine 2.0
  console.log('[TA Server] Registering Scenario Engine 2.0 (Phase 6)...');
  await registerScenarioRoutes(app);

  // Phase 7: Edge Intelligence Layer  
  console.log('[TA Server] Registering Edge Intelligence (Phase 7)...');
  await registerEdgeIntelligenceRoutes(app);

  // Phase 8: Strategy Builder
  console.log('[TA Server] Registering Strategy Builder (Phase 8)...');
  await registerStrategyBuilderRoutes(app);

  // Phase 9: Regime Intelligence Engine
  console.log('[TA Server] Registering Regime Intelligence (Phase 9)...');
  await registerRegimeRoutes(app);

  // Phase 10: Execution Intelligence
  console.log('[TA Server] Registering Execution Intelligence (Phase 10)...');
  await registerExecutionRoutes(app);

  // Phase 11: MetaBrain - Global Policy Layer
  console.log('[TA Server] Registering MetaBrain (Phase 11)...');
  await registerMetaBrainRoutes(app);

  // Phase 11.1: MetaBrain Learning Layer
  console.log('[TA Server] Registering MetaBrain Learning Layer (Phase 11.1)...');
  await registerLearningRoutes(app);

  // Phase 12: Digital Twin (DT1-DT4)
  console.log('[TA Server] Registering Digital Twin (Phase 12 - DT1-DT4)...');
  await registerDigitalTwinRoutes(app);

  // DT5: Branch Tree Expansion
  console.log('[TA Server] Registering Branch Tree Routes (DT5)...');
  await registerTreeRoutes(app, db);

  // Phase 13: Market Memory Engine (MM1-MM2)
  console.log('[TA Server] Registering Market Memory Engine (Phase 13 - MM1-MM2)...');
  await registerMemoryRoutes(app);

  // P1.3: Memory-conditioned MetaBrain Policies (MM3)
  console.log('[TA Server] Registering Memory Policy Routes (P1.3 - MM3)...');
  await registerMemoryPolicyRoutes(app, db);

  // P1.4: Regime-conditioned Learning
  console.log('[TA Server] Registering Regime Learning Routes (P1.4)...');
  await registerRegimeLearningRoutes(app, db);

  // MetaBrain v3: Self-Optimizing System
  console.log('[TA Server] Registering MetaBrain v3 Routes...');
  await registerMetaBrainV3Routes(app, db);

  // Real-time WebSocket Layer
  console.log('[TA Server] Registering Real-time Routes...');
  await registerRealtimeRoutes(app);

  // System Dashboard (Observability)
  console.log('[TA Server] Registering Dashboard Routes...');
  await registerDashboardRoutes(app);

  // ANN Memory Index
  console.log('[TA Server] Registering Memory Index Routes...');
  await registerMemoryIndexRoutes(app);

  // Chart Intelligence Layer (Phase 1)
  console.log('[TA Server] Registering Chart Intelligence Routes...');
  await registerChartIntelligenceRoutes(app);

  // Market Map Layer (Phase 2.5)
  console.log('[TA Server] Registering Market Map Routes (Phase 2.5)...');
  await registerMarketMapRoutes(app);

  // Admin Control Plane (Phase 3)
  console.log('[TA Server] Registering Admin Control Routes (Phase 3)...');
  await registerAdminControlRoutes(app);

  // Observability Layer (Phase 4)
  console.log('[TA Server] Registering Observability Routes (Phase 4)...');
  await registerObservabilityRoutes(app);

  // Strategy Platform (Phase 5)
  console.log('[TA Server] Registering Strategy Platform Routes (Phase 5)...');
  await registerStrategyPlatformRoutes(app);

  // Portfolio Intelligence (Phase 5.5)
  console.log('[TA Server] Registering Portfolio Intelligence Routes (Phase 5.5)...');
  await registerPortfolioRoutes(app);

  // Indicators Layer (Phase 6)
  console.log('[TA Server] Registering Indicators Layer (Phase 6)...');
  await registerIndicatorRoutes(app);

  // Phase 6.5: MTF Confirmation Layer
  console.log('[TA Server] Registering MTF Confirmation Layer (Phase 6.5)...');
  await initMTFV2Indexes(db);
  await app.register(async (instance) => {
    await registerMTFV2Routes(instance, { db });
  }, { prefix: '/api/mtf' });

  // Graceful shutdown
  const shutdown = async (signal: string) => {
    console.log(`[TA Server] Received ${signal}, shutting down...`);
    await app.close();
    await disconnectMongo();
    console.log('[TA Server] Shutdown complete');
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  // Start server
  try {
    await app.listen({ port: PORT, host: '0.0.0.0' });
    console.log(`[TA Server] ✅ TA module started on port ${PORT}`);
    console.log('[TA Server] Endpoints:');
    console.log('  - GET  /api/ta/health');
    console.log('  - GET  /api/ta/analyze?asset=SPX');
    console.log('  - GET  /api/ta/structure?asset=SPX');
    console.log('  - GET  /api/ta/levels?asset=SPX');
    console.log('  - GET  /api/ta/patterns?asset=SPX');
    console.log('  - GET  /api/ta/pivots?asset=SPX');
    console.log('  - GET  /api/ta/features?asset=SPX');
    console.log('  - GET  /api/ta/audit/latest?asset=SPX');
    console.log('  - GET  /api/ta/audit/runs?asset=SPX');
    console.log('  - GET  /api/ta/outcomes/latest?asset=SPX');
    console.log('  - POST /api/ta/outcomes/recompute');
    console.log('  - GET  /api/ta/performance?asset=SPX');
    console.log('  - GET  /api/ta/calibration');
    console.log('  - GET  /api/ta/calibration/pattern/:type');
    console.log('  - GET  /api/ta/calibration/all');
    console.log('  - GET  /api/ta/calibration/health');
    console.log('  - POST /api/ta/calibration/calibrate');
    console.log('  [Phase A: Hypothesis Engine Registry]');
    console.log('  - GET  /api/ta/registry/stats');
    console.log('  - GET  /api/ta/registry/patterns');
    console.log('  - GET  /api/ta/registry/pattern/:type');
    console.log('  - GET  /api/ta/registry/groups');
    console.log('  - GET  /api/ta/registry/implemented');
    console.log('  - GET  /api/ta/registry/check/:type');
    console.log('  [Phase K: ML Dataset Builder]');
    console.log('  - GET  /api/ta/ml_dataset/status');
    console.log('  - POST /api/ta/ml_dataset/build');
    console.log('  - GET  /api/ta/ml_dataset/preview');
    console.log('  - GET  /api/ta/ml_dataset/rows');
    console.log('  [Phase L: ML Overlay]');
    console.log('  - GET  /api/ta/ml_overlay/status');
    console.log('  - PATCH /api/ta/ml_overlay/config');
    console.log('  - POST /api/ta/ml_overlay/predict');
    console.log('  - GET  /api/ta/ml_overlay/predictions/latest');
    console.log('  [Phase M: Multi-Timeframe]');
    console.log('  - GET  /api/ta/mtf/status');
    console.log('  - GET  /api/ta/mtf/decision?asset=BTCUSDT');
    console.log('  - GET  /api/ta/mtf/audit/latest');
    console.log('  - GET  /api/ta/mtf/summary');
    console.log('  [Phase N: Production Hardening]');
    console.log('  - GET  /api/ta/health/extended');
    console.log('  - GET  /api/ta/engine/summary');
    console.log('  - GET  /api/ta/cache/stats');
    console.log('  - POST /api/ta/cache/config');
    console.log('  - POST /api/ta/cache/clear');
    console.log('  - GET  /api/ta/metrics');
    console.log('  - GET  /api/ta/scheduler/stats');
    console.log('  [Phase O: Real-Time Streaming]');
    console.log('  - GET  /api/ta/stream/health');
    console.log('  - GET  /api/ta/stream/stats');
    console.log('  - POST /api/ta/stream/pump');
    console.log('  - GET  /api/ta/stream/replay');
    console.log('  - POST /api/ta/stream/test');
    console.log('  [Phase 8.3: Outcomes V3 - Multiclass Labels]');
    console.log('  - GET  /outcomes_v3/latest?asset=...&timeframe=...');
    console.log('  - GET  /outcomes_v3/stats');
    console.log('  - GET  /outcomes_v3/by_class');
    console.log('  - POST /outcomes_v3/evaluate');
    console.log('  - POST /outcomes_v3/evaluate_batch');
    console.log('  [Phase 8.5: Auto Scheduler V2]');
    console.log('  - GET  /scheduler/status');
    console.log('  - GET  /scheduler/health');
    console.log('  - POST /scheduler/start');
    console.log('  - POST /scheduler/stop');
    console.log('  - POST /scheduler/run/:jobKey');
    console.log('  - GET  /scheduler/runs');
    console.log('  - GET  /scheduler/jobs');
    console.log('  [Phase 8.6: Market Structure Graph]');
    console.log('  - GET  /graph/status');
    console.log('  - POST /graph/boost');
    console.log('  - GET  /graph/node/:type');
    console.log('  - GET  /graph/transitions/:type');
    console.log('  - GET  /graph/edges');
    console.log('  [P1.6.1: Batch Simulation]');
    console.log('  - POST /api/ta/research/batch-simulate');
    console.log('  - GET  /api/ta/research/batch-simulate/stats');
    console.log('  [P1.9: Backtest]');
    console.log('  - POST /api/ta/research/backtest/run');
    console.log('  - GET  /api/ta/research/backtest/status?runId=');
    console.log('  - GET  /api/ta/research/backtest/report?runId=');
    console.log('  [P2.0: Quality Engine]');
    console.log('  - GET  /api/ta/quality/pattern?type=...&asset=...&tf=...&regime=...');
    console.log('  - GET  /api/ta/quality/top?asset=...&tf=...&limit=...');
    console.log('  - POST /api/ta/quality/rebuild');
    console.log('  - GET  /api/ta/quality/multiplier?patterns=...&asset=...&tf=...&regime=...');
    console.log('  [P5.0: Edge Attribution Engine]');
    console.log('  - GET  /api/ta/edge/health');
    console.log('  - GET  /api/ta/edge/sample?limit=20');
    console.log('  - GET  /api/ta/edge/count');
    console.log('  - GET  /api/ta/edge/rows');
    console.log('  - GET  /api/ta/edge/dimensions');
    console.log('  - POST /api/ta/edge/rebuild');
    console.log('  - GET  /api/ta/edge/rebuild/status');
    console.log('  - GET  /api/ta/edge/latest?dimension=...');
    console.log('  - GET  /api/ta/edge/top?dimension=...');
    console.log('  - GET  /api/ta/edge/worst?dimension=...');
    console.log('  - GET  /api/ta/edge/stat/:dimension/:key');
    console.log('  - GET  /api/ta/edge/runs');
    console.log('  - GET  /api/ta/edge/run/:runId');
    console.log('  - GET  /api/ta/edge/global');
    console.log('  [M1: Market State Engine]');
    console.log('  - GET  /api/ta/marketState/state?asset=BTCUSDT&tf=1d&bars=100');
    console.log('  - POST /api/ta/marketState/analyze');
    console.log('  - GET  /api/ta/marketState/adjustment/:pattern?state=...');
    console.log('  [C1: Context Engine]');
    console.log('  - GET  /api/ta/context/analyze?asset=BTCUSDT&tf=1d&lookback=100');
    console.log('  - POST /api/ta/context/boost');
    console.log('  [L1: Liquidity Engine]');
    console.log('  - GET  /api/ta/liquidity/analyze?asset=BTCUSDT&tf=1d');
    console.log('  - GET  /api/ta/liquidity/zones?asset=BTCUSDT&tf=1d');
    console.log('  - GET  /api/ta/liquidity/sweeps?asset=BTCUSDT&tf=1d');
    console.log('  - POST /api/ta/liquidity/boost');
    console.log('  [Phase 6: Scenario Engine 2.0]');
    console.log('  - GET  /api/ta/scenarios?asset=BTCUSDT&timeframe=1d');
    console.log('  - GET  /api/ta/scenarios/active?asset=BTCUSDT&timeframe=1d');
    console.log('  - POST /api/ta/scenarios/simulate');
    console.log('  - POST /api/ta/scenarios/refine');
    console.log('  - GET  /api/ta/scenarios/stats');
    console.log('  - POST /api/ta/scenarios/outcome');
    console.log('  - GET  /api/ta/scenarios/templates');
    console.log('  - GET  /api/ta/scenarios/transitions');
    console.log('  [Phase 7: Edge Intelligence Layer]');
    console.log('  - GET  /api/ta/edge/patterns');
    console.log('  - GET  /api/ta/edge/states');
    console.log('  - GET  /api/ta/edge/scenarios');
    console.log('  - GET  /api/ta/edge/attribution');
    console.log('  - GET  /api/ta/edge/baseline');
    console.log('  - POST /api/ta/edge/record');
    console.log('  - POST /api/ta/edge/analyze');
    console.log('  - GET  /api/ta/edge/multiplier?pattern=...&state=...');
    console.log('  [Phase 11: MetaBrain - Global Policy Layer]');
    console.log('  - GET  /api/ta/metabrain/state');
    console.log('  - GET  /api/ta/metabrain/decision');
    console.log('  - POST /api/ta/metabrain/recompute');
    console.log('  - GET  /api/ta/metabrain/multipliers');
    console.log('  - GET  /api/ta/metabrain/actions');
    console.log('  - GET  /api/ta/metabrain/stats');
    console.log('  - POST /api/ta/metabrain/simulate');
    console.log('  - GET  /api/ta/metabrain/config');
    console.log('  - GET  /api/ta/metabrain/history');
    console.log('  [Phase 11.1: MetaBrain Learning Layer]');
    console.log('  - GET  /api/ta/metabrain/learning/status');
    console.log('  - GET  /api/ta/metabrain/learning/weights');
    console.log('  - GET  /api/ta/metabrain/learning/attribution');
    console.log('  - POST /api/ta/metabrain/learning/rebuild');
    console.log('  - GET  /api/ta/metabrain/learning/weight/:module');
    console.log('  - GET  /api/ta/metabrain/learning/history');
    console.log('  - GET  /api/ta/metabrain/learning/config');
    console.log('  [Phase 12: Digital Twin (DT1-DT4)]');
    console.log('  - GET  /api/ta/twin/state?asset=BTCUSDT&tf=1d');
    console.log('  - POST /api/ta/twin/recompute');
    console.log('  - GET  /api/ta/twin/branches?asset=BTCUSDT&tf=1d');
    console.log('  - GET  /api/ta/twin/consistency?asset=BTCUSDT&tf=1d');
    console.log('  - GET  /api/ta/twin/counterfactual?asset=BTCUSDT&tf=1d');
    console.log('  - POST /api/ta/twin/counterfactual/recompute');
    console.log('  - POST /api/ta/twin/event');
    console.log('  - GET  /api/ta/twin/history?asset=BTCUSDT&tf=1d');
    console.log('  - GET  /api/ta/twin/status');
    console.log('  - GET  /api/ta/twin/metrics?asset=BTCUSDT&tf=1d');
    console.log('  - POST /api/ta/twin/cleanup');
    console.log('  [Phase 13: Market Memory Engine (MM1-MM2)]');
    console.log('  - GET  /api/ta/memory/status');
    console.log('  - POST /api/ta/memory/snapshot');
    console.log('  - GET  /api/ta/memory/search?asset=BTCUSDT&tf=1d');
    console.log('  - GET  /api/ta/memory/boost?asset=BTCUSDT&tf=1d');
    console.log('  - POST /api/ta/memory/resolve');
    console.log('  - POST /api/ta/memory/generate');
    console.log('  - POST /api/ta/memory/cleanup');
    console.log('  [Phase 6.5: MTF Confirmation Layer]');
    console.log('  - GET  /api/mtf/state?symbol=BTCUSDT&tf=4h');
    console.log('  - GET  /api/mtf/boost?symbol=BTCUSDT&tf=4h&direction=LONG');
    console.log('  - GET  /api/mtf/explain?symbol=BTCUSDT&tf=4h');
    console.log('  - GET  /api/mtf/config');
    console.log('  - GET  /api/mtf/health');
    console.log('  - GET  /api/mtf/history?symbol=BTCUSDT&tf=4h');
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}

main().catch((err) => {
  console.error('[TA Server] Fatal error:', err);
  process.exit(1);
});
