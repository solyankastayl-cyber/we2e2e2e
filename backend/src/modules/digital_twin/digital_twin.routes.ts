/**
 * Digital Twin API Routes
 * 
 * REST endpoints for Digital Twin module
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import * as controller from './digital_twin.controller.js';
import { TwinEvent, TwinEventType } from './digital_twin.types.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerDigitalTwinRoutes(fastify: FastifyInstance): Promise<void> {
  const prefix = '/api/ta/twin';
  
  // ─────────────────────────────────────────────────────────────
  // DT1 — Core State
  // ─────────────────────────────────────────────────────────────
  
  /**
   * GET /api/ta/twin/state
   * Get current digital twin state
   */
  fastify.get(`${prefix}/state`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required params: asset, tf'
      });
    }
    
    const result = await controller.getTwinState(asset, tf);
    return reply.send(result);
  });
  
  /**
   * POST /api/ta/twin/recompute
   * Force recomputation of twin state
   */
  fastify.post(`${prefix}/recompute`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.body as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required body params: asset, tf'
      });
    }
    
    try {
      const state = await controller.recomputeTwin(asset, tf);
      return reply.send({
        success: true,
        data: state
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Recompute failed'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // DT1 — Branches
  // ─────────────────────────────────────────────────────────────
  
  /**
   * GET /api/ta/twin/branches
   * Get twin branches (scenario paths)
   */
  fastify.get(`${prefix}/branches`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required params: asset, tf'
      });
    }
    
    const result = await controller.getTwinBranches(asset, tf);
    return reply.send(result);
  });
  
  // ─────────────────────────────────────────────────────────────
  // DT3 — Consistency
  // ─────────────────────────────────────────────────────────────
  
  /**
   * GET /api/ta/twin/consistency
   * Get consistency analysis
   */
  fastify.get(`${prefix}/consistency`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required params: asset, tf'
      });
    }
    
    const result = await controller.getTwinConsistency(asset, tf);
    return reply.send(result);
  });
  
  // ─────────────────────────────────────────────────────────────
  // DT4 — Counterfactual
  // ─────────────────────────────────────────────────────────────
  
  /**
   * GET /api/ta/twin/counterfactual
   * Get counterfactual analysis
   */
  fastify.get(`${prefix}/counterfactual`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required params: asset, tf'
      });
    }
    
    const result = await controller.getTwinCounterfactual(asset, tf);
    return reply.send(result);
  });
  
  /**
   * POST /api/ta/twin/counterfactual/recompute
   * Recompute counterfactual analysis
   */
  fastify.post(`${prefix}/counterfactual/recompute`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.body as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required body params: asset, tf'
      });
    }
    
    try {
      const state = await controller.recomputeTwin(asset, tf);
      return reply.send({
        success: true,
        data: state.counterfactual
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Recompute failed'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // DT2 — Reactor (Event processing)
  // ─────────────────────────────────────────────────────────────
  
  /**
   * POST /api/ta/twin/event
   * Process event and update twin
   */
  fastify.post(`${prefix}/event`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { type, asset, timeframe, payload } = request.body as {
      type?: TwinEventType;
      asset?: string;
      timeframe?: string;
      payload?: unknown;
    };
    
    if (!type || !asset || !timeframe) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required body params: type, asset, timeframe'
      });
    }
    
    const validTypes: TwinEventType[] = [
      'NEW_CANDLE', 'PATTERN_DETECTED', 'LIQUIDITY_EVENT',
      'REGIME_CHANGE', 'STATE_CHANGE', 'SCENARIO_UPDATE', 'EXECUTION_EVENT'
    ];
    
    if (!validTypes.includes(type)) {
      return reply.status(400).send({
        success: false,
        error: `Invalid event type. Valid types: ${validTypes.join(', ')}`
      });
    }
    
    try {
      const event: TwinEvent = {
        type,
        asset,
        timeframe,
        ts: Date.now(),
        payload
      };
      
      const state = await controller.processEvent(event);
      return reply.send({
        success: true,
        data: state
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Event processing failed'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // History & Status
  // ─────────────────────────────────────────────────────────────
  
  /**
   * GET /api/ta/twin/history
   * Get twin state history
   */
  fastify.get(`${prefix}/history`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf, limit } = request.query as { 
      asset?: string; 
      tf?: string;
      limit?: string;
    };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required params: asset, tf'
      });
    }
    
    const result = await controller.getTwinHistory(asset, tf, limit ? parseInt(limit) : 100);
    return reply.send(result);
  });
  
  /**
   * GET /api/ta/twin/status
   * Get Digital Twin module status
   */
  fastify.get(`${prefix}/status`, async (_request: FastifyRequest, reply: FastifyReply) => {
    const status = await controller.getTwinStatus();
    return reply.send({
      success: true,
      data: status
    });
  });

  /**
   * GET /api/ta/twin/modules
   * Check which live modules are available
   */
  fastify.get(`${prefix}/modules`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required params: asset, tf'
      });
    }
    
    try {
      const availability = await controller.checkModuleAvailability(asset, tf);
      return reply.send({
        success: true,
        data: availability
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Failed to check modules'
      });
    }
  });
  
  /**
   * GET /api/ta/twin/metrics
   * Get twin metrics for asset
   */
  fastify.get(`${prefix}/metrics`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = request.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.status(400).send({
        success: false,
        error: 'Missing required params: asset, tf'
      });
    }
    
    try {
      const metrics = await controller.getTwinMetrics(asset, tf);
      return reply.send({
        success: true,
        data: metrics
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Failed to get metrics'
      });
    }
  });
  
  // ─────────────────────────────────────────────────────────────
  // Admin
  // ─────────────────────────────────────────────────────────────
  
  /**
   * POST /api/ta/twin/cleanup
   * Cleanup old twin states
   */
  fastify.post(`${prefix}/cleanup`, async (request: FastifyRequest, reply: FastifyReply) => {
    const { keepDays } = request.body as { keepDays?: number };
    
    try {
      const result = await controller.cleanupTwinHistory(keepDays || 30);
      return reply.send({
        success: true,
        data: result
      });
    } catch (error) {
      return reply.status(500).send({
        success: false,
        error: error instanceof Error ? error.message : 'Cleanup failed'
      });
    }
  });
  
  console.log('✅ Digital Twin routes registered');
}

export default registerDigitalTwinRoutes;
