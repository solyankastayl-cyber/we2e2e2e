/**
 * Phase 9 — Regime Engine API Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { MarketRegime, REGIME_DESCRIPTIONS, REGIME_PATTERN_BOOSTS, DEFAULT_REGIME_CONFIG } from './regime.types.js';
import { calculateRegimeFeatures, CandleInput } from './regime.features.js';
import { detectRegime, detectRegimeSmoothed, getRegimeBoost } from './regime.classifier.js';
import {
  saveRegimeHistory,
  getLatestRegime,
  getRegimeHistory,
  getRegimeTransitions,
  calculateTransitions,
  getRegimeStats
} from './regime.storage.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerRegimeRoutes(fastify: FastifyInstance): Promise<void> {

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/regime/detect — For Digital Twin Live Context
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/regime/detect', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset = 'BTCUSDT', tf = '1d' } = request.query as Record<string, string>;
    
    try {
      const latest = await getLatestRegime(asset, tf);
      
      if (!latest) {
        // Return mock if no data
        return {
          asset,
          timeframe: tf,
          regime: 'COMPRESSION',
          confidence: 0.65,
          probabilities: {
            'COMPRESSION': 0.35,
            'BREAKOUT_PREP': 0.25,
            'TREND_EXPANSION': 0.15,
            'RANGE_ROTATION': 0.10,
            'TREND_CONTINUATION': 0.05,
            'VOLATILITY_EXPANSION': 0.04,
            'LIQUIDITY_HUNT': 0.03,
            'ACCUMULATION': 0.02,
            'DISTRIBUTION': 0.01
          }
        };
      }
      
      return {
        asset,
        timeframe: tf,
        regime: latest.regime,
        confidence: latest.confidence,
        probabilities: latest.features ? {
          'COMPRESSION': latest.features.compression || 0.2,
          'TREND_EXPANSION': latest.features.trendStrength || 0.15,
          'RANGE_ROTATION': latest.features.rangeScore || 0.15
        } : undefined
      };
    } catch (error) {
      console.error('[RegimeRoutes] Detect error:', error);
      return reply.status(500).send({ error: 'Failed to detect regime' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/regime-intel/current - Get current regime
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/regime-intel/current', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset = 'BTCUSDT', timeframe = '1d' } = request.query as Record<string, string>;
    
    try {
      const latest = await getLatestRegime(asset, timeframe);
      
      if (!latest) {
        return {
          asset,
          timeframe,
          regime: 'COMPRESSION',
          confidence: 0.5,
          description: REGIME_DESCRIPTIONS['COMPRESSION'],
          message: 'No regime history found, returning default'
        };
      }
      
      return {
        asset,
        timeframe,
        regime: latest.regime,
        confidence: Math.round(latest.confidence * 100) / 100,
        description: REGIME_DESCRIPTIONS[latest.regime as MarketRegime] || '',
        timestamp: latest.timestamp,
        features: {
          trendStrength: Math.round(latest.features.trendStrength * 100) / 100,
          volatility: Math.round(latest.features.volatility * 100) / 100,
          compression: Math.round(latest.features.compression * 100) / 100,
          rangeScore: Math.round(latest.features.rangeScore * 100) / 100
        }
      };
    } catch (error) {
      console.error('[RegimeRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to get current regime' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/regime-intel/history - Get regime history
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/regime-intel/history', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset = 'BTCUSDT', timeframe = '1d', limit = '50' } = request.query as Record<string, string>;
    
    try {
      const history = await getRegimeHistory(asset, timeframe, parseInt(limit));
      
      return {
        asset,
        timeframe,
        count: history.length,
        history: history.map(h => ({
          regime: h.regime,
          confidence: Math.round(h.confidence * 100) / 100,
          timestamp: h.timestamp,
          duration: h.duration
        }))
      };
    } catch (error) {
      console.error('[RegimeRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to get regime history' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/regime-intel/transitions - Get regime transitions
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/regime-intel/transitions', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, timeframe } = request.query as Record<string, string>;
    
    try {
      const transitions = await getRegimeTransitions(asset, timeframe);
      
      // Group by 'from' regime
      const grouped: Record<string, Array<{ to: string; probability: number; avgDuration: number }>> = {};
      
      for (const t of transitions) {
        if (!grouped[t.from]) grouped[t.from] = [];
        grouped[t.from].push({
          to: t.to,
          probability: Math.round(t.probability * 100) / 100,
          avgDuration: Math.round(t.avgDuration)
        });
      }
      
      return {
        totalTransitions: transitions.length,
        byRegime: grouped
      };
    } catch (error) {
      console.error('[RegimeRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to get regime transitions' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/regime-intel/detect - Detect regime from candles
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/regime-intel/detect', async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as any;
    const { asset = 'BTCUSDT', timeframe = '1d', candles = [], save = true } = body;
    
    if (candles.length < 50) {
      // Return mock detection if no candles
      const mockFeatures = {
        trendStrength: 0.45,
        trendDirection: 0.2,
        volatility: 1.1,
        volatilityTrend: 0.05,
        compression: 0.55,
        compressionTrend: 0.1,
        rangeScore: 0.4,
        rangeWidth: 0.04,
        liquidityActivity: 0.25,
        liquidityBias: 0.1,
        momentum: 0.15,
        momentumDivergence: 0,
        volumeProfile: 1.1,
        volumeTrend: 0.05
      };
      
      const result = detectRegime(mockFeatures, DEFAULT_REGIME_CONFIG);
      
      return {
        asset,
        timeframe,
        regime: result.regime,
        confidence: Math.round(result.confidence * 100) / 100,
        description: REGIME_DESCRIPTIONS[result.regime],
        scores: result.scores,
        probabilities: Object.fromEntries(
          Object.entries(result.probabilities).map(([k, v]) => [k, Math.round(v * 100) / 100])
        ),
        source: 'mock'
      };
    }
    
    try {
      // Calculate features from candles
      const candleInputs: CandleInput[] = candles.map((c: any) => ({
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume || 0
      }));
      
      const features = calculateRegimeFeatures(candleInputs);
      
      // Get previous regime for smoothing
      const previous = await getLatestRegime(asset, timeframe);
      
      // Detect regime
      const result = previous 
        ? detectRegimeSmoothed(features, previous.regime as MarketRegime, previous.confidence, DEFAULT_REGIME_CONFIG)
        : detectRegime(features, DEFAULT_REGIME_CONFIG);
      
      // Save if requested
      if (save) {
        await saveRegimeHistory({
          asset,
          timeframe,
          timestamp: new Date(),
          regime: result.regime,
          confidence: result.confidence,
          features
        });
      }
      
      return {
        asset,
        timeframe,
        regime: result.regime,
        confidence: Math.round(result.confidence * 100) / 100,
        description: REGIME_DESCRIPTIONS[result.regime],
        scores: {
          trendScore: Math.round(result.scores.trendScore * 100) / 100,
          rangeScore: Math.round(result.scores.rangeScore * 100) / 100,
          compressionScore: Math.round(result.scores.compressionScore * 100) / 100,
          volatilityScore: Math.round(result.scores.volatilityScore * 100) / 100,
          liquidityScore: Math.round(result.scores.liquidityScore * 100) / 100
        },
        probabilities: Object.fromEntries(
          Object.entries(result.probabilities).map(([k, v]) => [k, Math.round(v * 100) / 100])
        ),
        source: 'candles'
      };
    } catch (error) {
      console.error('[RegimeRoutes] Detection error:', error);
      return reply.status(500).send({ error: 'Regime detection failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/regime-intel/boost - Get regime boost for pattern
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/regime-intel/boost', async (request: FastifyRequest, reply: FastifyReply) => {
    const { regime = 'COMPRESSION', pattern = 'TRIANGLE_ASC' } = request.query as Record<string, string>;
    
    try {
      const boost = getRegimeBoost(regime as MarketRegime, pattern);
      
      return {
        regime,
        pattern,
        boost: Math.round(boost * 100) / 100,
        description: boost > 1 ? 'Pattern works well in this regime' : 
                     boost < 1 ? 'Pattern underperforms in this regime' : 'Neutral'
      };
    } catch (error) {
      console.error('[RegimeRoutes] Error:', error);
      return reply.status(500).send({ error: 'Failed to get regime boost' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/regime-intel/boosts - Get all boosts for regime
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/regime-intel/boosts', async (request: FastifyRequest, reply: FastifyReply) => {
    const { regime = 'COMPRESSION' } = request.query as Record<string, string>;
    
    const boosts = REGIME_PATTERN_BOOSTS[regime as MarketRegime] || {};
    
    return {
      regime,
      description: REGIME_DESCRIPTIONS[regime as MarketRegime] || '',
      boosts: Object.entries(boosts).map(([family, boost]) => ({
        patternFamily: family,
        boost: boost as number,
        effect: (boost as number) > 1 ? 'POSITIVE' : (boost as number) < 1 ? 'NEGATIVE' : 'NEUTRAL'
      }))
    };
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/regime-intel/stats - Regime statistics
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/regime-intel/stats', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, timeframe, days = '30' } = request.query as Record<string, string>;
    
    try {
      const stats = await getRegimeStats(
        asset || undefined,
        timeframe || undefined,
        parseInt(days)
      );
      
      return {
        ...stats,
        avgDuration: Object.fromEntries(
          Object.entries(stats.avgDuration).map(([k, v]) => [k, Math.round(v)])
        )
      };
    } catch (error) {
      console.error('[RegimeRoutes] Stats error:', error);
      return reply.status(500).send({ error: 'Failed to fetch regime stats' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/regime-intel/recalculate - Recalculate transitions
  // ─────────────────────────────────────────────────────────────
  fastify.post('/api/ta/regime-intel/recalculate', async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, timeframe } = request.body as any;
    
    try {
      const transitions = await calculateTransitions(asset, timeframe);
      
      return {
        success: true,
        transitionsCalculated: transitions.length,
        transitions: transitions.slice(0, 20).map(t => ({
          from: t.from,
          to: t.to,
          probability: Math.round(t.probability * 100) / 100,
          avgDuration: Math.round(t.avgDuration),
          sampleSize: t.sampleSize
        }))
      };
    } catch (error) {
      console.error('[RegimeRoutes] Recalculation error:', error);
      return reply.status(500).send({ error: 'Transition recalculation failed' });
    }
  });

  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/regime-intel/descriptions - All regime descriptions
  // ─────────────────────────────────────────────────────────────
  fastify.get('/api/ta/regime-intel/descriptions', async (request: FastifyRequest, reply: FastifyReply) => {
    return {
      count: Object.keys(REGIME_DESCRIPTIONS).length,
      regimes: Object.entries(REGIME_DESCRIPTIONS).map(([regime, description]) => ({
        regime,
        description
      }))
    };
  });
}

export default registerRegimeRoutes;
