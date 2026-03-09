/**
 * Phase 6.5 — MTF Service
 * 
 * Main service for Multi-Timeframe Confirmation Layer
 */

import { Db } from 'mongodb';
import { 
  MTFState, 
  MTFConfig, 
  DEFAULT_MTF_CONFIG,
  MTFExplain 
} from './mtf.types.js';
import { 
  buildMTFContext, 
  MTFContext,
  createMockMTFContext,
  getTFHierarchy 
} from './mtf.context.js';
import { computeMTFState, calculateMTFBoost, MTFAlignmentInput } from './mtf.alignment.js';

export interface MTFService {
  /**
   * Get MTF state for symbol and timeframe
   */
  getState(symbol: string, anchorTf: string): Promise<MTFState>;
  
  /**
   * Get MTF boost for a specific direction
   */
  getBoostForDirection(
    symbol: string, 
    anchorTf: string, 
    direction: 'LONG' | 'SHORT'
  ): Promise<{ mtfBoost: number; mtfExecutionAdjustment: number; notes: string[] }>;
  
  /**
   * Get MTF explain block for Decision API
   */
  getExplain(symbol: string, anchorTf: string): Promise<MTFExplain>;
  
  /**
   * Health check
   */
  health(): { enabled: boolean; version: string };
}

/**
 * Create MTF Service
 */
export function createMTFService(
  db: Db,
  config: MTFConfig = DEFAULT_MTF_CONFIG
): MTFService {
  // Collection for caching MTF states
  const mtfStatesCol = db.collection('mtf_states');
  
  // Decision service fetcher (simplified - in prod would call actual decision service)
  async function fetchDecisionPack(symbol: string, tf: string): Promise<any> {
    // Try to get latest decision from DB
    const decision = await db.collection('ta_decisions')
      .findOne(
        { asset: symbol, timeframe: tf },
        { sort: { timestamp: -1 }, projection: { _id: 0 } }
      );
    
    if (decision) return decision;
    
    // Fallback: try ta_scenarios collection
    const scenario = await db.collection('ta_scenarios')
      .findOne(
        { asset: symbol, timeframe: tf },
        { sort: { createdAt: -1 }, projection: { _id: 0 } }
      );
    
    return scenario || {};
  }
  
  return {
    async getState(symbol: string, anchorTf: string): Promise<MTFState> {
      // Build context from 3 timeframes
      const ctx = await buildMTFContext(
        { symbol, anchorTf },
        fetchDecisionPack
      );
      
      // Compute MTF state
      const state = computeMTFState(ctx, config);
      
      // Cache the state (TTL 5 min)
      await mtfStatesCol.updateOne(
        { symbol, anchorTf },
        { 
          $set: { 
            ...state,
            updatedAt: new Date() 
          } 
        },
        { upsert: true }
      );
      
      return state;
    },
    
    async getBoostForDirection(
      symbol: string,
      anchorTf: string,
      direction: 'LONG' | 'SHORT'
    ): Promise<{ mtfBoost: number; mtfExecutionAdjustment: number; notes: string[] }> {
      // Get full state
      const state = await this.getState(symbol, anchorTf);
      
      // If current direction matches anchor, return as-is
      // Otherwise recalculate for the specific direction
      const notes = [...state.notes];
      
      return {
        mtfBoost: state.mtfBoost,
        mtfExecutionAdjustment: state.mtfExecutionAdjustment,
        notes
      };
    },
    
    async getExplain(symbol: string, anchorTf: string): Promise<MTFExplain> {
      const state = await this.getState(symbol, anchorTf);
      
      return {
        anchorTf: state.anchorTf,
        higherTf: state.higherTf,
        lowerTf: state.lowerTf,
        higherBias: state.higherBias,
        lowerMomentum: state.lowerMomentum,
        regimeAligned: state.regimeAligned,
        structureAligned: state.structureAligned,
        scenarioAligned: state.scenarioAligned,
        momentumAligned: state.momentumAligned,
        mtfBoost: state.mtfBoost,
        mtfExecutionAdjustment: state.mtfExecutionAdjustment,
        notes: state.notes
      };
    },
    
    health(): { enabled: boolean; version: string } {
      return {
        enabled: config.enabled,
        version: 'mtf_v2_phase6.5'
      };
    }
  };
}

// Singleton instance
let mtfServiceInstance: MTFService | null = null;

/**
 * Get or create MTF service instance
 */
export function getMTFService(db: Db, config?: MTFConfig): MTFService {
  if (!mtfServiceInstance) {
    mtfServiceInstance = createMTFService(db, config);
  }
  return mtfServiceInstance;
}

/**
 * Quick MTF boost calculation without full service
 * Used for integration into decision engine
 */
export function quickMTFBoost(
  higherBias: 'BULL' | 'BEAR' | 'NEUTRAL',
  higherRegime: string,
  higherStructure: string,
  lowerMomentum: 'BULL' | 'BEAR' | 'NEUTRAL',
  anchorDirection: 'LONG' | 'SHORT',
  config: MTFConfig = DEFAULT_MTF_CONFIG
): number {
  // Quick alignment checks
  const higherBiasAligned = 
    (anchorDirection === 'LONG' && higherBias === 'BULL') ||
    (anchorDirection === 'SHORT' && higherBias === 'BEAR') ||
    higherBias === 'NEUTRAL';
  
  const regimeAligned = 
    (anchorDirection === 'LONG' && (higherRegime === 'TREND_UP' || higherRegime === 'RANGE')) ||
    (anchorDirection === 'SHORT' && (higherRegime === 'TREND_DOWN' || higherRegime === 'RANGE'));
  
  const structureAligned = 
    (anchorDirection === 'LONG' && (higherStructure === 'BULLISH' || higherStructure === 'NEUTRAL')) ||
    (anchorDirection === 'SHORT' && (higherStructure === 'BEARISH' || higherStructure === 'NEUTRAL'));
  
  const momentumAligned = 
    (anchorDirection === 'LONG' && (lowerMomentum === 'BULL' || lowerMomentum === 'NEUTRAL')) ||
    (anchorDirection === 'SHORT' && (lowerMomentum === 'BEAR' || lowerMomentum === 'NEUTRAL'));
  
  const higherConflict = 
    (anchorDirection === 'LONG' && higherBias === 'BEAR') ||
    (anchorDirection === 'SHORT' && higherBias === 'BULL');
  
  const input: MTFAlignmentInput = {
    anchorDirection,
    higherBiasAligned,
    regimeAligned,
    structureAligned,
    scenarioAligned: true,  // Assume true for quick calculation
    lowerMomentumAligned: momentumAligned,
    higherConflict
  };
  
  return calculateMTFBoost(input, config);
}
