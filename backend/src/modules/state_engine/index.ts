/**
 * D4 — State Transition Engine Service & Routes
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db, Collection } from 'mongodb';
import { 
  MarketStateNode,
  StateTransitionResult,
  StateEngineConfig,
  DEFAULT_STATE_CONFIG,
  ALLOWED_TRANSITIONS,
} from './state.types.js';
import { 
  computeCurrentState, 
  computeTransitionProbabilities,
  findLikelyPath,
  computeStateBoost,
} from './state.compute.js';

export class StateTransitionService {
  private db: Db;
  private statesCollection: Collection;
  private transitionsCollection: Collection;
  private config: StateEngineConfig;

  constructor(db: Db, config?: Partial<StateEngineConfig>) {
    this.db = db;
    this.statesCollection = db.collection('ta_market_states');
    this.transitionsCollection = db.collection('ta_state_transitions');
    this.config = { ...DEFAULT_STATE_CONFIG, ...config };
  }

  async ensureIndexes(): Promise<void> {
    await this.statesCollection.createIndex({ asset: 1, timeframe: 1 });
    await this.transitionsCollection.createIndex({ from: 1, to: 1 });
  }

  /**
   * Fetch data from other intelligence layers
   */
  private async fetchIntelligenceData(asset: string, timeframe: string): Promise<{
    context: any;
    marketState: any;
    liquidity: any;
    physics: any;
    graph: any;
  }> {
    const baseUrl = 'http://localhost:8001/api/ta';
    
    const [contextResp, stateResp, liquidityResp, physicsResp, graphResp] = await Promise.all([
      fetch(`${baseUrl}/context/analyze?asset=${asset}&tf=${timeframe}`).catch(() => null),
      fetch(`${baseUrl}/marketState/state?asset=${asset}&tf=${timeframe}`).catch(() => null),
      fetch(`${baseUrl}/liquidity/analyze?asset=${asset}&tf=${timeframe}`).catch(() => null),
      fetch(`${baseUrl}/physics/state?asset=${asset}&tf=${timeframe}`).catch(() => null),
      fetch(`${baseUrl}/market_graph/score?asset=${asset}&tf=${timeframe}`).catch(() => null),
    ]);

    const context = contextResp?.ok ? await contextResp.json() : {};
    const marketState = stateResp?.ok ? await stateResp.json() : {};
    const liquidity = liquidityResp?.ok ? await liquidityResp.json() : {};
    const physics = physicsResp?.ok ? await physicsResp.json() : {};
    const graph = graphResp?.ok ? await graphResp.json() : {};

    return {
      context: {
        trendDirection: context.trend?.direction,
        trendStrength: context.trend?.strength,
        bullishScore: context.score?.bullish,
        bearishScore: context.score?.bearish,
      },
      marketState: {
        state: marketState.state,
        confidence: marketState.confidence,
      },
      liquidity: {
        recentSweepUp: liquidity.metrics?.recentSweepUp,
        recentSweepDown: liquidity.metrics?.recentSweepDown,
        liquidityBias: liquidity.metrics?.liquidityBias,
      },
      physics: {
        compressionScore: physics.scores?.compression,
        pressureScore: physics.scores?.pressure,
        energyScore: physics.scores?.energy,
        releaseProbability: physics.scores?.release,
        exhaustionScore: physics.scores?.exhaustion,
        physicsState: physics.physicsState,
      },
      graph: {
        currentChain: graph.currentChain,
        predictedNext: graph.predictedNext,
      },
    };
  }

  /**
   * Analyze state transitions for asset/timeframe
   */
  async analyze(asset: string, timeframe: string): Promise<StateTransitionResult> {
    const data = await this.fetchIntelligenceData(asset, timeframe);
    
    // Compute current state
    const { state, confidence, reason } = computeCurrentState(
      data.context,
      data.marketState,
      data.liquidity,
      data.physics,
      data.graph,
      this.config
    );
    
    // Compute transition probabilities
    const nextProbs = computeTransitionProbabilities(
      state,
      data.physics,
      data.liquidity
    );
    
    // Find likely path
    const { path, probability } = findLikelyPath(state, nextProbs, 3);
    
    // Compute state boost (default direction BULL for now)
    const stateBoost = computeStateBoost(state, 'BULL', data.physics, data.liquidity);
    
    const result: StateTransitionResult = {
      asset,
      timeframe,
      timestamp: new Date(),
      currentState: state,
      stateConfidence: confidence,
      barsInState: 0,  // Would need tracking
      nextStateProbabilities: nextProbs,
      likelyPath: path,
      pathProbability: probability,
      stateBoost,
      stateReason: reason,
    };
    
    // Save to storage
    await this.statesCollection.updateOne(
      { asset, timeframe },
      { $set: result },
      { upsert: true }
    );
    
    return result;
  }

  /**
   * Get state boost for decision engine
   */
  async getStateBoost(
    asset: string,
    timeframe: string,
    patternDirection: 'BULL' | 'BEAR'
  ): Promise<{ boost: number; state: MarketStateNode; reason: string }> {
    const data = await this.fetchIntelligenceData(asset, timeframe);
    
    const { state, reason } = computeCurrentState(
      data.context,
      data.marketState,
      data.liquidity,
      data.physics,
      data.graph,
      this.config
    );
    
    const boost = computeStateBoost(state, patternDirection, data.physics, data.liquidity);
    
    return { boost, state, reason };
  }

  /**
   * Get allowed transitions from state
   */
  getAllowedTransitions(state: MarketStateNode): MarketStateNode[] {
    return ALLOWED_TRANSITIONS[state] || [];
  }
}

export async function registerStateEngineRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const service = new StateTransitionService(db);
  await service.ensureIndexes();

  /**
   * GET /current - Get current market state
   */
  app.get('/current', async (
    request: FastifyRequest<{
      Querystring: { asset?: string; tf?: string };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';

    const result = await service.analyze(asset, timeframe);

    return {
      ok: true,
      asset,
      timeframe,
      currentState: result.currentState,
      stateConfidence: result.stateConfidence,
      stateReason: result.stateReason,
      stateBoost: result.stateBoost,
    };
  });

  /**
   * GET /transitions - Get transition probabilities
   */
  app.get('/transitions', async (
    request: FastifyRequest<{
      Querystring: { asset?: string; tf?: string };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';

    const result = await service.analyze(asset, timeframe);

    return {
      ok: true,
      asset,
      timeframe,
      currentState: result.currentState,
      nextStateProbabilities: result.nextStateProbabilities,
      likelyPath: result.likelyPath,
      pathProbability: result.pathProbability,
    };
  });

  /**
   * GET /boost - Get state boost for decision engine
   */
  app.get('/boost', async (
    request: FastifyRequest<{
      Querystring: { asset?: string; tf?: string; direction?: string };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const direction = (request.query.direction || 'BULL') as 'BULL' | 'BEAR';

    const result = await service.getStateBoost(asset, timeframe, direction);

    return {
      ok: true,
      asset,
      timeframe,
      direction,
      ...result,
    };
  });

  /**
   * GET /allowed - Get allowed transitions from a state
   */
  app.get('/allowed', async (
    request: FastifyRequest<{
      Querystring: { state?: string };
    }>
  ) => {
    const state = (request.query.state || 'BALANCE') as MarketStateNode;
    const allowed = service.getAllowedTransitions(state);

    return {
      ok: true,
      state,
      allowedTransitions: allowed,
    };
  });

  /**
   * GET /states - List all possible states
   */
  app.get('/states', async () => {
    return {
      ok: true,
      states: Object.keys(ALLOWED_TRANSITIONS),
      transitions: ALLOWED_TRANSITIONS,
    };
  });

  console.log('[StateEngine] Routes: /current, /transitions, /boost, /allowed, /states');
}

export async function registerStateEngineModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[StateEngine] Registering State Transition Engine (D4)...');
  
  await app.register(async (instance) => {
    await registerStateEngineRoutes(instance, { db });
  }, { prefix: '/state' });
  
  console.log('[StateEngine] ✅ State Transition Engine registered at /api/ta/state/*');
}
