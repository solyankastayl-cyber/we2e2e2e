/**
 * Phase 6 — Indicators Routes
 * =============================
 * API endpoints for RSI, Volume Profile, OI, Macro
 * 
 * GET /api/indicators/momentum      — RSI + MACD + Stochastic
 * GET /api/indicators/volume-profile — Volume at price analysis
 * GET /api/indicators/positioning    — OI + sentiment
 * GET /api/indicators/macro          — Fear&Greed, BTC.D, Alt.D
 * GET /api/indicators/combined       — All indicators + boosts
 */

import { FastifyInstance } from 'fastify';
import { analyzeMomentum, getMomentumBoost } from './rsi.service.js';
import { getMockVolumeProfile, getVolumeProfileBoost } from './volume-profile.service.js';
import { analyzePositioning, getPositioningBoost } from './oi.service.js';
import { getMacroData, analyzeMacro } from './macro.service.js';
import { IndicatorState } from './indicators.types.js';

// Mock OHLCV data generator
function generateMockOHLCV(basePrice: number, count: number = 100): { highs: number[]; lows: number[]; closes: number[] } {
  const highs: number[] = [];
  const lows: number[] = [];
  const closes: number[] = [];
  
  let price = basePrice * (0.9 + Math.random() * 0.2);
  
  for (let i = 0; i < count; i++) {
    const change = (Math.random() - 0.5) * basePrice * 0.02;
    price += change;
    
    const high = price * (1 + Math.random() * 0.01);
    const low = price * (1 - Math.random() * 0.01);
    const close = low + Math.random() * (high - low);
    
    highs.push(high);
    lows.push(low);
    closes.push(close);
  }
  
  return { highs, lows, closes };
}

const basePrices: Record<string, number> = {
  BTCUSDT: 52000,
  ETHUSDT: 2800,
  SOLUSDT: 120,
  BNBUSDT: 380,
};

async function indicatorRoutes(app: FastifyInstance): Promise<void> {
  
  // ─────────────────────────────────────────────────────────────
  // MOMENTUM (RSI + MACD + Stochastic)
  // ─────────────────────────────────────────────────────────────
  
  app.get('/momentum', async (request, reply) => {
    try {
      const { symbol = 'BTCUSDT' } = request.query as { symbol?: string };
      const basePrice = basePrices[symbol] || 1000;
      const { highs, lows, closes } = generateMockOHLCV(basePrice);
      
      const momentum = analyzeMomentum(highs, lows, closes);
      const boost = getMomentumBoost(momentum);
      
      return reply.send({
        ok: true,
        data: {
          symbol,
          ...momentum,
          boost,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // VOLUME PROFILE
  // ─────────────────────────────────────────────────────────────
  
  app.get('/volume-profile', async (request, reply) => {
    try {
      const { symbol = 'BTCUSDT' } = request.query as { symbol?: string };
      const currentPrice = basePrices[symbol] || 1000;
      
      const profile = getMockVolumeProfile(currentPrice);
      const boost = getVolumeProfileBoost(profile, 'LONG');
      
      return reply.send({
        ok: true,
        data: {
          symbol,
          currentPrice,
          profile,
          boost,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // POSITIONING (OI + Sentiment)
  // ─────────────────────────────────────────────────────────────
  
  app.get('/positioning', async (request, reply) => {
    try {
      const { symbol = 'BTCUSDT' } = request.query as { symbol?: string };
      const currentPrice = basePrices[symbol] || 1000;
      
      const positioning = analyzePositioning(symbol, currentPrice);
      const boost = getPositioningBoost(positioning, 'LONG');
      
      return reply.send({
        ok: true,
        data: {
          symbol,
          currentPrice,
          ...positioning,
          boost,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // MACRO
  // ─────────────────────────────────────────────────────────────
  
  app.get('/macro', async (request, reply) => {
    try {
      const { symbol = 'BTCUSDT' } = request.query as { symbol?: string };
      
      const rawData = getMacroData();
      const boost = analyzeMacro(symbol);
      
      return reply.send({
        ok: true,
        data: {
          symbol,
          raw: rawData,
          boost,
        },
      });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // COMBINED INDICATORS
  // ─────────────────────────────────────────────────────────────
  
  app.get('/combined', async (request, reply) => {
    try {
      const { symbol = 'BTCUSDT', timeframe = '1d', side = 'LONG' } = request.query as { 
        symbol?: string; 
        timeframe?: string;
        side?: 'LONG' | 'SHORT';
      };
      
      const basePrice = basePrices[symbol] || 1000;
      const { highs, lows, closes } = generateMockOHLCV(basePrice);
      
      // Get all indicators
      const momentum = analyzeMomentum(highs, lows, closes);
      const volumeProfile = getMockVolumeProfile(basePrice);
      const positioning = analyzePositioning(symbol, basePrice);
      const macro = analyzeMacro(symbol);
      
      // Calculate boosts
      const boosts = {
        momentum: getMomentumBoost(momentum),
        volume: getVolumeProfileBoost(volumeProfile, side),
        positioning: getPositioningBoost(positioning, side),
        macro: macro.combined,
      };
      
      // Composite boost
      const compositeBoost = boosts.momentum * boosts.volume * boosts.positioning * boosts.macro;
      
      const state: IndicatorState = {
        symbol,
        timeframe,
        momentum,
        volumeProfile,
        positioning,
        macro,
        boosts,
        compositeBoost: Math.round(compositeBoost * 1000) / 1000,
        lastUpdated: Date.now(),
      };
      
      return reply.send({ ok: true, data: state });
    } catch (err: any) {
      return reply.status(500).send({ ok: false, error: err.message });
    }
  });
}

// ═══════════════════════════════════════════════════════════════
// PUBLIC REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerIndicatorRoutes(app: FastifyInstance): Promise<void> {
  await app.register(indicatorRoutes, { prefix: '/api/indicators' });
  
  console.log('[Indicators Layer] Routes registered at /api/indicators:');
  console.log('    - GET /api/indicators/momentum');
  console.log('    - GET /api/indicators/volume-profile');
  console.log('    - GET /api/indicators/positioning');
  console.log('    - GET /api/indicators/macro');
  console.log('    - GET /api/indicators/combined');
}
