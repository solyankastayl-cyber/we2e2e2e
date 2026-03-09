/**
 * DT5 — Branch Tree API Routes
 * 
 * Endpoints:
 * - GET /api/ta/twin/tree - Get branch tree
 * - POST /api/ta/twin/tree/recompute - Recompute tree
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import { Db } from 'mongodb';
import {
  TwinBranchTree,
  TreeConfig,
  DEFAULT_TREE_CONFIG
} from './digital_twin.types.js';
import { buildBranchTree, getMainBranch, getLeafNodes, calculateTreeEntropy } from './digital_twin.tree_builder.js';
import {
  calculateTreeDecisionAdjustment,
  calculateTreeExecutionAdjustment,
  getRecommendedRiskMode,
  getTradingRecommendation,
  analyzeAlternativeBranches,
  calculateScenarioBreakProbability
} from './digital_twin.tree_scoring.js';
import { getLatestTwinState, saveTwinState } from './digital_twin.storage.js';
import { getTreeAdjustments, createTreeIntegrationResult, TreeAdjustments } from './tree.integration.js';

// ═══════════════════════════════════════════════════════════════
// STORAGE
// ═══════════════════════════════════════════════════════════════

let db: Db | null = null;

async function saveTree(tree: TwinBranchTree): Promise<void> {
  if (!db) return;
  
  const collection = db.collection('ta_digital_twin_trees');
  
  await collection.updateOne(
    { asset: tree.asset, timeframe: tree.timeframe },
    { $set: { ...tree, updatedAt: new Date() } },
    { upsert: true }
  );
}

async function getTree(asset: string, timeframe: string): Promise<TwinBranchTree | null> {
  if (!db) return null;
  
  const collection = db.collection('ta_digital_twin_trees');
  
  const doc = await collection.findOne(
    { asset, timeframe },
    { projection: { _id: 0 } }
  );
  
  return doc as TwinBranchTree | null;
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function registerTreeRoutes(
  fastify: FastifyInstance,
  database: Db
): Promise<void> {
  db = database;

  /**
   * GET /api/ta/twin/tree
   * Get branch tree for asset
   */
  fastify.get('/api/ta/twin/tree', async (req: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = req.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.code(400).send({ 
        error: 'Missing required parameters: asset, tf' 
      });
    }
    
    try {
      // Try to get cached tree first
      let tree = await getTree(asset, tf);
      
      // If no tree, build from twin state
      if (!tree) {
        const twinState = await getLatestTwinState(asset, tf);
        
        if (!twinState) {
          return reply.code(404).send({ 
            error: 'No Digital Twin state available for this asset/timeframe',
            suggestion: 'Run POST /api/ta/twin/recompute first'
          });
        }
        
        tree = buildBranchTree(twinState);
        await saveTree(tree);
      }
      
      // Get additional analysis
      const mainBranch = getMainBranch(tree);
      const analysis = analyzeAlternativeBranches(tree);
      const recommendation = getTradingRecommendation(tree.treeStats);
      
      return {
        success: true,
        data: {
          tree,
          analysis: {
            mainBranch: mainBranch ? {
              state: mainBranch.state,
              event: mainBranch.event,
              probability: mainBranch.probability
            } : null,
            alternativeCount: analysis.alternatives.length,
            alternativeRisk: analysis.alternativeRisk,
            scenarioBreakProbability: calculateScenarioBreakProbability(tree),
            entropy: calculateTreeEntropy(tree)
          },
          recommendation,
          adjustments: {
            decisionAdjustment: calculateTreeDecisionAdjustment(tree.treeStats),
            executionAdjustment: calculateTreeExecutionAdjustment(tree.treeStats),
            recommendedRiskMode: getRecommendedRiskMode(tree.treeStats)
          }
        }
      };
    } catch (err: any) {
      console.error('[TreeRoutes] Error:', err.message);
      return reply.code(500).send({ error: err.message });
    }
  });

  /**
   * POST /api/ta/twin/tree/recompute
   * Force recompute of branch tree
   */
  fastify.post('/api/ta/twin/tree/recompute', async (req: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf, maxDepth, maxChildren, minProbability } = req.body as {
      asset?: string;
      tf?: string;
      maxDepth?: number;
      maxChildren?: number;
      minProbability?: number;
    };
    
    if (!asset || !tf) {
      return reply.code(400).send({ 
        error: 'Missing required fields: asset, tf' 
      });
    }
    
    try {
      // Get twin state
      const twinState = await getLatestTwinState(asset, tf);
      
      if (!twinState) {
        return reply.code(404).send({ 
          error: 'No Digital Twin state available',
          suggestion: 'Run POST /api/ta/twin/recompute first to create twin state'
        });
      }
      
      // Custom config if provided
      const config: TreeConfig = {
        maxDepth: maxDepth ?? DEFAULT_TREE_CONFIG.maxDepth,
        maxChildrenPerNode: maxChildren ?? DEFAULT_TREE_CONFIG.maxChildrenPerNode,
        minBranchProbability: minProbability ?? DEFAULT_TREE_CONFIG.minBranchProbability
      };
      
      // Build tree
      const tree = buildBranchTree(twinState, config);
      await saveTree(tree);
      
      // Get leaf nodes
      const leafNodes = getLeafNodes(tree);
      
      return {
        success: true,
        data: {
          asset: tree.asset,
          timeframe: tree.timeframe,
          rootState: tree.rootState,
          depth: tree.depth,
          treeStats: tree.treeStats,
          totalBranches: tree.treeStats.totalBranches,
          leafNodes: leafNodes.length,
          adjustments: {
            decisionAdjustment: calculateTreeDecisionAdjustment(tree.treeStats),
            executionAdjustment: calculateTreeExecutionAdjustment(tree.treeStats),
            recommendedRiskMode: getRecommendedRiskMode(tree.treeStats)
          }
        }
      };
    } catch (err: any) {
      console.error('[TreeRoutes] Recompute error:', err.message);
      return reply.code(500).send({ error: err.message });
    }
  });

  /**
   * GET /api/ta/twin/tree/scoring
   * Get tree-based scoring adjustments
   */
  fastify.get('/api/ta/twin/tree/scoring', async (req: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = req.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.code(400).send({ 
        error: 'Missing required parameters: asset, tf' 
      });
    }
    
    try {
      const tree = await getTree(asset, tf);
      
      if (!tree) {
        return reply.code(404).send({ 
          error: 'No tree available for this asset/timeframe' 
        });
      }
      
      const recommendation = getTradingRecommendation(tree.treeStats);
      const analysis = analyzeAlternativeBranches(tree);
      
      // P1.1: Include full adjustments
      const adjustments = getTreeAdjustments(tree.treeStats);
      
      return {
        success: true,
        data: {
          treeStats: tree.treeStats,
          adjustments,
          scoring: {
            decisionAdjustment: adjustments.decisionAdjustment,
            executionAdjustment: adjustments.executionAdjustment,
            recommendedRiskMode: adjustments.riskModeHint
          },
          recommendation: {
            shouldTrade: adjustments.shouldTrade,
            confidence: adjustments.treeConfidence,
            reason: adjustments.tradeReason
          },
          stopAdjustment: adjustments.stopAdjustment,
          risk: {
            scenarioBreakProbability: calculateScenarioBreakProbability(tree),
            alternativeRisk: analysis.alternativeRisk,
            treeRisk: tree.treeStats.treeRisk
          }
        }
      };
    } catch (err: any) {
      console.error('[TreeRoutes] Scoring error:', err.message);
      return reply.code(500).send({ error: err.message });
    }
  });

  /**
   * GET /api/ta/twin/tree/integration
   * P1.1: Get tree integration data for Decision/Execution engines
   */
  fastify.get('/api/ta/twin/tree/integration', async (req: FastifyRequest, reply: FastifyReply) => {
    const { asset, tf } = req.query as { asset?: string; tf?: string };
    
    if (!asset || !tf) {
      return reply.code(400).send({ 
        error: 'Missing required parameters: asset, tf' 
      });
    }
    
    try {
      const tree = await getTree(asset, tf);
      
      if (!tree) {
        // Return neutral integration (no effect)
        return {
          success: true,
          data: createTreeIntegrationResult(
            {
              dominanceScore: 0.5,
              uncertaintyScore: 0.5,
              treeRisk: 0.3,
              mainBranchProbability: 0.5,
              totalBranches: 1,
              maxDepthReached: 0
            },
            false
          )
        };
      }
      
      const result = createTreeIntegrationResult(tree.treeStats, true);
      
      return {
        success: true,
        data: result
      };
    } catch (err: any) {
      console.error('[TreeRoutes] Integration error:', err.message);
      return reply.code(500).send({ error: err.message });
    }
  });

  console.log('[DT5 Tree Routes] Registered:');
  console.log('  - GET  /api/ta/twin/tree?asset=...&tf=...');
  console.log('  - POST /api/ta/twin/tree/recompute');
  console.log('  - GET  /api/ta/twin/tree/scoring?asset=...&tf=...');
  console.log('  - GET  /api/ta/twin/tree/integration?asset=...&tf=... (P1.1)');
}
