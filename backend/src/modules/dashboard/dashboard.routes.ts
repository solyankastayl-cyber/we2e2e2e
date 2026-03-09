/**
 * System Dashboard — Routes
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { collectDashboardData, generateAlerts } from './dashboard.collector.js';

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerDashboardRoutes(fastify: FastifyInstance): Promise<void> {
  /**
   * GET /api/ta/dashboard
   * Get full dashboard data
   */
  fastify.get('/api/ta/dashboard', async (
    req: FastifyRequest<{ Querystring: { asset?: string; tf?: string } }>,
    reply
  ) => {
    try {
      const { asset = 'BTCUSDT', tf = '1d' } = req.query;
      
      const data = await collectDashboardData(asset, tf);
      const alerts = generateAlerts(data);
      
      return {
        success: true,
        data: {
          ...data,
          alerts
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
   * GET /api/ta/dashboard/metabrain
   * Get MetaBrain status only
   */
  fastify.get('/api/ta/dashboard/metabrain', async (
    req: FastifyRequest<{ Querystring: { asset?: string; tf?: string } }>,
    reply
  ) => {
    try {
      const { asset = 'BTCUSDT', tf = '1d' } = req.query;
      const data = await collectDashboardData(asset, tf);
      
      return {
        success: true,
        data: data.metabrain
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/dashboard/modules
   * Get module health status
   */
  fastify.get('/api/ta/dashboard/modules', async (req, reply) => {
    try {
      const data = await collectDashboardData();
      
      return {
        success: true,
        data: {
          modules: data.modules,
          summary: {
            active: data.modules.filter(m => m.status === 'ACTIVE').length,
            softGated: data.modules.filter(m => m.status === 'SOFT_GATED').length,
            hardGated: data.modules.filter(m => m.status === 'HARD_GATED').length
          }
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
   * GET /api/ta/dashboard/regime
   * Get regime info
   */
  fastify.get('/api/ta/dashboard/regime', async (
    req: FastifyRequest<{ Querystring: { asset?: string; tf?: string } }>,
    reply
  ) => {
    try {
      const { asset = 'BTCUSDT', tf = '1d' } = req.query;
      const data = await collectDashboardData(asset, tf);
      
      return {
        success: true,
        data: data.regime
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/dashboard/tree
   * Get tree visualization
   */
  fastify.get('/api/ta/dashboard/tree', async (
    req: FastifyRequest<{ Querystring: { asset?: string; tf?: string } }>,
    reply
  ) => {
    try {
      const { asset = 'BTCUSDT', tf = '1d' } = req.query;
      const data = await collectDashboardData(asset, tf);
      
      return {
        success: true,
        data: data.tree
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/dashboard/memory
   * Get memory status
   */
  fastify.get('/api/ta/dashboard/memory', async (
    req: FastifyRequest<{ Querystring: { asset?: string; tf?: string } }>,
    reply
  ) => {
    try {
      const { asset = 'BTCUSDT', tf = '1d' } = req.query;
      const data = await collectDashboardData(asset, tf);
      
      return {
        success: true,
        data: data.memory
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/dashboard/strategies
   * Get strategy panel
   */
  fastify.get('/api/ta/dashboard/strategies', async (
    req: FastifyRequest<{ Querystring: { asset?: string; tf?: string } }>,
    reply
  ) => {
    try {
      const { asset = 'BTCUSDT', tf = '1d' } = req.query;
      const data = await collectDashboardData(asset, tf);
      
      return {
        success: true,
        data: data.strategies
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/dashboard/system
   * Get system metrics
   */
  fastify.get('/api/ta/dashboard/system', async (req, reply) => {
    try {
      const data = await collectDashboardData();
      
      return {
        success: true,
        data: data.system
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  /**
   * GET /api/ta/dashboard/alerts
   * Get current alerts
   */
  fastify.get('/api/ta/dashboard/alerts', async (
    req: FastifyRequest<{ Querystring: { asset?: string; tf?: string } }>,
    reply
  ) => {
    try {
      const { asset = 'BTCUSDT', tf = '1d' } = req.query;
      const data = await collectDashboardData(asset, tf);
      const alerts = generateAlerts(data);
      
      return {
        success: true,
        data: {
          alerts,
          critical: alerts.filter(a => a.type === 'CRITICAL').length,
          warnings: alerts.filter(a => a.type === 'WARNING').length
        }
      };
    } catch (err: any) {
      return reply.code(500).send({
        success: false,
        error: err.message
      });
    }
  });

  console.log('[Dashboard Routes] Registered:');
  console.log('  - GET  /api/ta/dashboard');
  console.log('  - GET  /api/ta/dashboard/metabrain');
  console.log('  - GET  /api/ta/dashboard/modules');
  console.log('  - GET  /api/ta/dashboard/regime');
  console.log('  - GET  /api/ta/dashboard/tree');
  console.log('  - GET  /api/ta/dashboard/memory');
  console.log('  - GET  /api/ta/dashboard/strategies');
  console.log('  - GET  /api/ta/dashboard/system');
  console.log('  - GET  /api/ta/dashboard/alerts');
}
