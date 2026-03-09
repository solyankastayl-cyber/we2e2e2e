/**
 * Market Memory — API Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import * as controller from './memory.controller.js';
import { buildMemorySnapshot, buildMemorySnapshotFromRaw } from './memory.snapshot.js';
import { searchSimilarSnapshots, summarizeMemoryMatches } from './memory.search.js';
import { buildMemoryBoost } from './memory.boost.js';
import { getTwinState } from '../digital_twin/digital_twin.controller.js';
import { DEFAULT_MEMORY_CONFIG } from './memory.types.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerMemoryRoutes(fastify: FastifyInstance): Promise<void> {
  const prefix = '/api/ta/memory';
  
  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/memory/status
  // ─────────────────────────────────────────────────────────────
  fastify.get(`${prefix}/status`, async (_request: FastifyRequest, reply: FastifyReply) => {
    try {
      const status = await controller.getMemoryStatus();
      return reply.send({
        success: true,
        data: status
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get status'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/memory/snapshot — Save current state as memory
  // ─────────────────────────────────────────────────────────────
  fastify.post(`${prefix}/snapshot`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.body as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required body params: asset, tf'
      });
    }
    
    try {
      // Get current Twin state
      const twinResult = await getTwinState(asset, tf);
      
      if (!twinResult.success || !twinResult.data) {
        return reply.status(404).send({
          success: false,
          error: 'Twin state not found. Call /api/ta/twin/recompute first.'
        });
      }
      
      // Capture snapshot
      const snapshot = await controller.captureMemorySnapshot(twinResult.data);
      
      return reply.send({
        success: true,
        data: {
          snapshotId: snapshot.snapshotId,
          asset: snapshot.asset,
          timeframe: snapshot.timeframe,
          regime: snapshot.regime,
          marketState: snapshot.marketState,
          createdAt: snapshot.createdAt
        }
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Failed to capture snapshot'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/memory/search — Search similar historical states
  // ─────────────────────────────────────────────────────────────
  fastify.get(`${prefix}/search`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required params: asset, tf'
      });
    }
    
    try {
      // Get current Twin state
      const twinResult = await getTwinState(asset, tf);
      
      if (!twinResult.success || !twinResult.data) {
        return reply.status(404).send({
          success: false,
          error: 'Twin state not found. Call /api/ta/twin/recompute first.'
        });
      }
      
      // Search memory
      const { matches, summary } = await controller.searchMemory(twinResult.data);
      
      return reply.send({
        success: true,
        data: {
          currentSnapshot: {
            regime: twinResult.data.regime,
            marketState: twinResult.data.marketState,
            physicsState: twinResult.data.physicsState,
            dominantScenario: twinResult.data.dominantScenario,
            energy: twinResult.data.energy,
            confidence: twinResult.data.confidence
          },
          matches: matches.slice(0, 10).map(m => ({
            snapshotId: m.snapshotId,
            similarity: Math.round(m.similarity * 100) / 100,
            regime: m.regime,
            marketState: m.marketState,
            outcomeDirection: m.outcomeDirection,
            moveATR: m.moveATR ? Math.round(m.moveATR * 100) / 100 : undefined
          })),
          summary: {
            matches: summary.matches,
            avgSimilarity: Math.round(summary.avgSimilarity * 100) / 100,
            bullRate: Math.round(summary.bullRate * 100) / 100,
            bearRate: Math.round(summary.bearRate * 100) / 100,
            neutralRate: Math.round(summary.neutralRate * 100) / 100,
            avgMoveATR: Math.round(summary.avgMoveATR * 100) / 100,
            dominantDirection: summary.dominantDirection,
            memoryConfidence: Math.round(summary.memoryConfidence * 100) / 100
          }
        }
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Search failed'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // GET /api/ta/memory/boost — Get memory boost for current state
  // ─────────────────────────────────────────────────────────────
  fastify.get(`${prefix}/boost`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required params: asset, tf'
      });
    }
    
    try {
      // Get current Twin state
      const twinResult = await getTwinState(asset, tf);
      
      if (!twinResult.success || !twinResult.data) {
        return reply.status(404).send({
          success: false,
          error: 'Twin state not found. Call /api/ta/twin/recompute first.'
        });
      }
      
      // Get scenarios from Twin branches
      const currentScenarios = twinResult.data.branches.map(b => ({
        scenarioId: b.branchId,
        direction: b.direction
      }));
      
      // Get boost
      const boost = await controller.getMemoryBoost(twinResult.data, currentScenarios);
      
      return reply.send({
        success: true,
        data: {
          memoryConfidence: Math.round(boost.memoryConfidence * 100) / 100,
          bullishBoost: Math.round(boost.bullishBoost * 100) / 100,
          bearishBoost: Math.round(boost.bearishBoost * 100) / 100,
          neutralBoost: Math.round(boost.neutralBoost * 100) / 100,
          scenarioBoost: Object.fromEntries(
            Object.entries(boost.scenarioBoost).map(([k, v]) => [k, Math.round(v * 100) / 100])
          ),
          riskAdjustment: Math.round(boost.riskAdjustment * 100) / 100,
          matchCount: boost.matchCount,
          dominantOutcome: boost.dominantOutcome
        }
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get boost'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/memory/resolve — Resolve snapshot outcome
  // ─────────────────────────────────────────────────────────────
  fastify.post(`${prefix}/resolve`, async (request: FastifyRequest, reply: FastifyReply) => {
    const body = request.body as {
      snapshotId?: string;
      direction?: 'BULL' | 'BEAR' | 'NEUTRAL';
      moveATR?: number;
      scenarioResolved?: string;
      barsToResolution?: number;
    };
    
    if (!body.snapshotId || !body.direction) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required: snapshotId, direction'
      });
    }
    
    try {
      await controller.resolveOutcome(
        body.snapshotId,
        body.direction,
        body.moveATR || 0,
        body.scenarioResolved || 'UNKNOWN',
        body.barsToResolution || 0
      );
      
      return reply.send({
        success: true,
        message: `Snapshot ${body.snapshotId} resolved`
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Resolution failed'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/memory/generate — Generate synthetic data
  // ─────────────────────────────────────────────────────────────
  fastify.post(`${prefix}/generate`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset = 'BTCUSDT', tf = '1d', count = 100 } = request.body as {
      asset?: string;
      tf?: string;
      count?: number;
    };
    
    try {
      const created = await controller.generateSyntheticMemory(asset, tf, Math.min(count, 500));
      
      return reply.send({
        success: true,
        data: {
          created,
          asset,
          timeframe: tf
        }
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Generation failed'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // POST /api/ta/memory/cleanup — Cleanup old data
  // ─────────────────────────────────────────────────────────────
  fastify.post(`${prefix}/cleanup`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { keepDays = 365 } = request.body as { keepDays?: number };
    
    try {
      const deleted = await controller.cleanupMemory(keepDays);
      
      return reply.send({
        success: true,
        data: { deletedCount: deleted }
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Cleanup failed'
      });
    }
  });
  
  console.log('✅ Market Memory routes registered');
}

export default registerMemoryRoutes;
