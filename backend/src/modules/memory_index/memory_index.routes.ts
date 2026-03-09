/**
 * ANN Memory Index — Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  vectorIndex,
  createMarketStateVector,
  euclideanDistance,
  cosineSimilarity
} from './memory_index.engine.js';
import { MarketStateVector, SearchRequest } from './memory_index.types.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerMemoryIndexRoutes(fastify: FastifyInstance): Promise<void> {
  /**
   * GET /api/ta/memory/index/stats
   * Get index statistics
   */
  fastify.get('/api/ta/memory/index/stats', async (req, reply) => {
    const stats = vectorIndex.getStats();
    
    return {
      success: true,
      data: stats
    };
  });

  /**
   * POST /api/ta/memory/index/add
   * Add vector to index
   */
  fastify.post('/api/ta/memory/index/add', async (
    req: FastifyRequest<{ Body: { vectors: MarketStateVector[] } }>,
    reply
  ) => {
    try {
      const { vectors } = req.body ?? {};
      
      if (!vectors || !Array.isArray(vectors)) {
        return reply.code(400).send({
          success: false,
          error: 'Missing vectors array'
        });
      }
      
      const added = vectorIndex.addBatch(vectors);
      
      return {
        success: true,
        data: {
          added,
          totalIndexed: vectorIndex.size()
        }
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * POST /api/ta/memory/index/search
   * Search for similar vectors
   */
  fastify.post('/api/ta/memory/index/search', async (
    req: FastifyRequest<{ Body: SearchRequest & { vector?: number[] } }>,
    reply
  ) => {
    try {
      const { asset, timeframe, k = 10, vector, regimeFilter, outcomeFilter, minTimestamp, maxTimestamp } = req.body ?? {};
      
      if (!vector || !Array.isArray(vector)) {
        return reply.code(400).send({
          success: false,
          error: 'Missing query vector'
        });
      }
      
      const result = vectorIndex.search(vector, k, {
        regimes: regimeFilter,
        outcomes: outcomeFilter,
        minTimestamp,
        maxTimestamp
      });
      
      return {
        success: true,
        data: {
          matches: result.matches.map(m => ({
            id: m.id,
            similarity: m.similarity,
            distance: m.distance,
            regime: m.vector.regime,
            state: m.vector.state,
            outcome: m.vector.outcome,
            timestamp: m.vector.timestamp
          })),
          searchTimeMs: result.searchTimeMs,
          totalIndexed: result.totalIndexed
        }
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/memory/index/search/:id
   * Search for similar vectors by ID
   */
  fastify.get('/api/ta/memory/index/search/:id', async (
    req: FastifyRequest<{ Params: { id: string }; Querystring: { k?: string } }>,
    reply
  ) => {
    try {
      const { id } = req.params;
      const { k = '10' } = req.query;
      
      const result = vectorIndex.searchById(id, parseInt(k, 10));
      
      if (!result) {
        return reply.code(404).send({
          success: false,
          error: `Vector ${id} not found`
        });
      }
      
      return {
        success: true,
        data: {
          matches: result.matches.slice(1).map(m => ({  // Exclude self
            id: m.id,
            similarity: m.similarity,
            distance: m.distance,
            regime: m.vector.regime,
            outcome: m.vector.outcome
          })),
          searchTimeMs: result.searchTimeMs
        }
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/memory/index/vector/:id
   * Get vector by ID
   */
  fastify.get('/api/ta/memory/index/vector/:id', async (
    req: FastifyRequest<{ Params: { id: string } }>,
    reply
  ) => {
    const { id } = req.params;
    const vector = vectorIndex.get(id);
    
    if (!vector) {
      return reply.code(404).send({
        success: false,
        error: `Vector ${id} not found`
      });
    }
    
    return {
      success: true,
      data: vector
    };
  });

  /**
   * DELETE /api/ta/memory/index/vector/:id
   * Remove vector by ID
   */
  fastify.delete('/api/ta/memory/index/vector/:id', async (
    req: FastifyRequest<{ Params: { id: string } }>,
    reply
  ) => {
    const { id } = req.params;
    const removed = vectorIndex.remove(id);
    
    return {
      success: true,
      data: {
        removed,
        totalIndexed: vectorIndex.size()
      }
    };
  });

  /**
   * POST /api/ta/memory/index/clear
   * Clear all vectors
   */
  fastify.post('/api/ta/memory/index/clear', async (req, reply) => {
    vectorIndex.clear();
    
    return {
      success: true,
      data: {
        cleared: true,
        totalIndexed: 0
      }
    };
  });

  /**
   * POST /api/ta/memory/index/seed
   * Seed index with test data
   */
  fastify.post('/api/ta/memory/index/seed', async (
    req: FastifyRequest<{ Body: { count?: number } }>,
    reply
  ) => {
    const { count = 100 } = req.body ?? {};
    
    const regimes = ['COMPRESSION', 'TREND_EXPANSION', 'RANGE_ROTATION', 'BREAKOUT_PREP'];
    const outcomes: ('BULLISH' | 'BEARISH' | 'NEUTRAL')[] = ['BULLISH', 'BEARISH', 'NEUTRAL'];
    
    let added = 0;
    for (let i = 0; i < count; i++) {
      const vector = createMarketStateVector(
        `seed_${Date.now()}_${i}`,
        'BTCUSDT',
        '1d',
        Date.now() - i * 86400000,
        {
          volatility: Math.random(),
          trend: Math.random() * 2 - 1,
          liquidityImbalance: Math.random() * 2 - 1,
          momentum: Math.random() * 2 - 1,
          volumeProfile: Math.random(),
          pricePosition: Math.random(),
          regimeStrength: Math.random(),
          scenarioConfidence: Math.random(),
          patternSignature: Math.random(),
          treeUncertainty: Math.random(),
          memoryConfidence: Math.random(),
          edgeHealth: Math.random(),
          drawdown: Math.random() * 0.2,
          rsi: 30 + Math.random() * 40,
          macdSignal: Math.random() * 2 - 1,
          atrNormalized: Math.random()
        },
        regimes[Math.floor(Math.random() * regimes.length)],
        'COMPRESSION',
        'CONTINUATION',
        outcomes[Math.floor(Math.random() * outcomes.length)]
      );
      
      vectorIndex.add(vector);
      added++;
    }
    
    return {
      success: true,
      data: {
        seeded: added,
        totalIndexed: vectorIndex.size()
      }
    };
  });

  console.log('[Memory Index Routes] Registered:');
  console.log('  - GET  /api/ta/memory/index/stats');
  console.log('  - POST /api/ta/memory/index/add');
  console.log('  - POST /api/ta/memory/index/search');
  console.log('  - GET  /api/ta/memory/index/search/:id');
  console.log('  - GET  /api/ta/memory/index/vector/:id');
  console.log('  - DELETE /api/ta/memory/index/vector/:id');
  console.log('  - POST /api/ta/memory/index/clear');
  console.log('  - POST /api/ta/memory/index/seed');
}
