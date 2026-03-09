/**
 * D3 — Market Physics Service & Routes
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db, Collection } from 'mongodb';
import { 
  MarketPhysicsResult, 
  PhysicsConfig, 
  DEFAULT_PHYSICS_CONFIG 
} from './physics.types.js';
import { analyzeMarketPhysics } from './physics.compute.js';

export class MarketPhysicsService {
  private db: Db;
  private collection: Collection;
  private config: PhysicsConfig;

  constructor(db: Db, config?: Partial<PhysicsConfig>) {
    this.db = db;
    this.collection = db.collection('ta_market_physics');
    this.config = { ...DEFAULT_PHYSICS_CONFIG, ...config };
  }

  async ensureIndexes(): Promise<void> {
    await this.collection.createIndex({ asset: 1, timeframe: 1, timestamp: -1 });
  }

  async analyze(asset: string, timeframe: string): Promise<MarketPhysicsResult> {
    // Fetch candles
    const candles = await this.fetchCandles(asset, timeframe, 200);
    
    // Get liquidity bias from liquidity engine
    let liquidityBias = 0;
    try {
      const resp = await fetch(`http://localhost:8001/api/ta/liquidity/analyze?asset=${asset}&tf=${timeframe}`);
      if (resp.ok) {
        const data = await resp.json();
        const bias = data.metrics?.liquidityBias;
        liquidityBias = bias === 'BULLISH' ? 0.5 : bias === 'BEARISH' ? -0.5 : 0;
      }
    } catch (e) {
      // Ignore
    }
    
    // Analyze physics
    const result = analyzeMarketPhysics(candles, asset, timeframe, liquidityBias, this.config);
    
    // Save result
    await this.collection.updateOne(
      { asset, timeframe },
      { $set: { ...result, updatedAt: new Date() } },
      { upsert: true }
    );
    
    return result;
  }

  async getStoredPhysics(asset: string, timeframe: string): Promise<MarketPhysicsResult | null> {
    const doc = await this.collection.findOne({ asset, timeframe });
    if (!doc) return null;
    
    const { _id, ...result } = doc as any;
    return result;
  }

  async getPhysicsBoost(
    asset: string,
    timeframe: string,
    patternDirection: 'BULL' | 'BEAR'
  ): Promise<{ boost: number; state: string; reason: string }> {
    const physics = await this.analyze(asset, timeframe);
    
    let boost = physics.physicsBoost;
    let reason = `Physics state: ${physics.physicsState}`;
    
    // Adjust boost based on direction alignment
    if (physics.directionBias !== 'NEUTRAL') {
      const aligned = 
        (patternDirection === 'BULL' && physics.directionBias === 'BULL') ||
        (patternDirection === 'BEAR' && physics.directionBias === 'BEAR');
      
      if (aligned) {
        boost *= 1.05;
        reason += ' (direction aligned)';
      } else {
        boost *= 0.95;
        reason += ' (direction opposed)';
      }
    }
    
    return {
      boost: Math.min(1.3, Math.max(0.7, boost)),
      state: physics.physicsState,
      reason,
    };
  }

  private async fetchCandles(symbol: string, interval: string, limit: number): Promise<any[]> {
    const docs = await this.db.collection('candles_binance')
      .find({ symbol, interval })
      .sort({ openTime: -1 })
      .limit(limit)
      .toArray();
    
    if (docs.length > 0) return docs.reverse();
    
    const taDocs = await this.db.collection('ta_candles')
      .find({ asset: symbol, timeframe: interval })
      .sort({ openTime: -1 })
      .limit(limit)
      .toArray();
    
    return taDocs.reverse();
  }
}

export async function registerMarketPhysicsRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const service = new MarketPhysicsService(db);
  await service.ensureIndexes();

  /**
   * GET /state - Get market physics state
   */
  app.get('/state', async (
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
      physicsState: result.physicsState,
      stateConfidence: result.stateConfidence,
      directionBias: result.directionBias,
      physicsBoost: result.physicsBoost,
      scores: {
        compression: result.compressionScore,
        pressure: result.pressureScore,
        energy: result.energyScore,
        release: result.releaseProbability,
        exhaustion: result.exhaustionScore,
      },
    };
  });

  /**
   * GET /compression - Compression analysis
   */
  app.get('/compression', async (
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
      compressionScore: result.compressionScore,
      metrics: {
        atrRatio: result.metrics.atrRatio,
        rangeContraction: result.metrics.rangeContraction,
        bollingerWidth: result.metrics.bollingerWidth,
      },
      isCompressed: result.compressionScore > 0.5,
    };
  });

  /**
   * GET /energy - Energy buildup analysis
   */
  app.get('/energy', async (
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
      energyScore: result.energyScore,
      components: {
        compression: result.compressionScore,
        pressure: result.pressureScore,
      },
      releaseProbability: result.releaseProbability,
      isHighEnergy: result.energyScore > 0.6,
    };
  });

  /**
   * GET /release - Release probability
   */
  app.get('/release', async (
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
      releaseProbability: result.releaseProbability,
      isReleasing: result.physicsState === 'RELEASE',
      direction: result.directionBias,
      volumeProfile: result.metrics.volumeProfile,
    };
  });

  /**
   * GET /boost - Get physics boost for decision engine
   */
  app.get('/boost', async (
    request: FastifyRequest<{
      Querystring: { asset?: string; tf?: string; direction?: string };
    }>
  ) => {
    const asset = request.query.asset || 'BTCUSDT';
    const timeframe = request.query.tf || '1d';
    const direction = (request.query.direction || 'BULL') as 'BULL' | 'BEAR';

    const result = await service.getPhysicsBoost(asset, timeframe, direction);

    return {
      ok: true,
      asset,
      timeframe,
      direction,
      ...result,
    };
  });

  /**
   * GET /config - Get configuration
   */
  app.get('/config', async () => {
    return {
      ok: true,
      config: DEFAULT_PHYSICS_CONFIG,
    };
  });

  console.log('[MarketPhysics] Routes: /state, /compression, /energy, /release, /boost, /config');
}

export async function registerMarketPhysicsModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[MarketPhysics] Registering Market Physics Engine (D3)...');
  
  await app.register(async (instance) => {
    await registerMarketPhysicsRoutes(instance, { db });
  }, { prefix: '/physics' });
  
  console.log('[MarketPhysics] ✅ Market Physics registered at /api/ta/physics/*');
}
