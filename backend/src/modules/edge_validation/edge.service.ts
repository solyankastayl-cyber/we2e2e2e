/**
 * Phase 9.5 — Edge Validation: Service
 */

import { Db } from 'mongodb';
import {
  RegimeType,
  MarketType,
  RegimePerformance,
  MarketPerformance,
  EdgeValidationResult,
  EdgeValidationConfig,
  DEFAULT_EDGE_CONFIG,
  ALL_REGIMES,
  ALL_MARKETS,
  StrategyLifecycle
} from './edge.types.js';
import { buildRobustnessScore } from './edge.robustness.js';
import { analyzeSimilarity, filterRedundantStrategies } from './edge.similarity.js';
import { calculateConfidenceScore, determineLifecycleStatus } from './edge.confidence.js';

export interface EdgeValidationService {
  /**
   * Validate a single strategy
   */
  validateStrategy(
    strategyId: string,
    strategyName: string,
    features: string[],
    metrics: { winRate: number; profitFactor: number; sharpe: number; maxDrawdown: number; trades: number },
    allStrategies: { id: string; features: string[] }[]
  ): Promise<EdgeValidationResult>;
  
  /**
   * Validate all discovered strategies
   */
  validateAllStrategies(
    strategies: {
      id: string;
      name: string;
      features: string[];
      metrics: { winRate: number; profitFactor: number; sharpe: number; maxDrawdown: number; trades: number };
    }[]
  ): Promise<EdgeValidationResult[]>;
  
  /**
   * Get validation result for strategy
   */
  getValidation(strategyId: string): Promise<EdgeValidationResult | null>;
  
  /**
   * Update strategy lifecycle
   */
  updateLifecycle(strategyId: string, status: StrategyLifecycle): Promise<boolean>;
  
  /**
   * Get validation summary
   */
  getSummary(): Promise<{
    total: number;
    approved: number;
    limited: number;
    testing: number;
    candidates: number;
    rejected: number;
    avgConfidence: number;
  }>;
  
  /**
   * Health check
   */
  health(): { enabled: boolean; version: string };
}

/**
 * Generate mock regime performance for testing
 */
function generateMockRegimeData(
  winRate: number,
  trades: number
): RegimePerformance[] {
  return ALL_REGIMES.map(regime => {
    const regimeTrades = Math.floor(trades / ALL_REGIMES.length + (Math.random() - 0.5) * 20);
    const variation = (Math.random() - 0.5) * 0.15;
    const regimeWinRate = Math.max(0.3, Math.min(0.8, winRate + variation));
    
    return {
      regime,
      trades: Math.max(5, regimeTrades),
      winRate: regimeWinRate,
      profitFactor: regimeWinRate > 0.5 ? 1 + (regimeWinRate - 0.5) * 2 : 0.8,
      edge: (regimeWinRate - 0.5) * 2,
      isStrong: regimeWinRate >= 0.58
    };
  });
}

/**
 * Generate mock market performance for testing
 */
function generateMockMarketData(
  winRate: number,
  trades: number
): MarketPerformance[] {
  return ALL_MARKETS.map(market => {
    const marketTrades = Math.floor(trades / ALL_MARKETS.length + (Math.random() - 0.5) * 15);
    const variation = (Math.random() - 0.5) * 0.12;
    const marketWinRate = Math.max(0.35, Math.min(0.75, winRate + variation));
    
    return {
      market,
      trades: Math.max(3, marketTrades),
      winRate: marketWinRate,
      profitFactor: marketWinRate > 0.5 ? 1 + (marketWinRate - 0.5) * 1.8 : 0.85,
      edge: (marketWinRate - 0.5) * 2,
      isValid: marketWinRate >= 0.52 && marketTrades >= 15
    };
  });
}

/**
 * Generate mock period results for stability
 */
function generateMockPeriodResults(winRate: number, periods: number = 5): number[] {
  return Array.from({ length: periods }, () => 
    Math.max(0.3, Math.min(0.8, winRate + (Math.random() - 0.5) * 0.15))
  );
}

/**
 * Create Edge Validation Service
 */
export function createEdgeValidationService(
  db: Db,
  config: EdgeValidationConfig = DEFAULT_EDGE_CONFIG
): EdgeValidationService {
  const validationsCol = db.collection('edge_validations');
  
  // Cache
  const validationCache = new Map<string, EdgeValidationResult>();
  
  return {
    async validateStrategy(
      strategyId,
      strategyName,
      features,
      metrics,
      allStrategies
    ): Promise<EdgeValidationResult> {
      // Generate mock regime/market data (in production, would come from real backtests)
      const regimeData = generateMockRegimeData(metrics.winRate, metrics.trades);
      const marketData = generateMockMarketData(metrics.winRate, metrics.trades);
      const periodResults = generateMockPeriodResults(metrics.winRate);
      
      // Build robustness score
      const robustness = buildRobustnessScore(regimeData, marketData, periodResults, config);
      
      // Analyze similarity
      const similarity = analyzeSimilarity(strategyId, features, allStrategies, config);
      
      // Calculate confidence
      const confidence = calculateConfidenceScore(
        metrics.trades,
        metrics.winRate,
        metrics.profitFactor,
        metrics.maxDrawdown,
        robustness,
        similarity,
        config
      );
      
      // Determine lifecycle
      const { status, reason } = determineLifecycleStatus(confidence, robustness, config);
      
      // Build limitations for LIMITED status
      let limitations;
      if (status === 'LIMITED') {
        limitations = {
          regimesOnly: robustness.strongRegimes.length > 0 ? robustness.strongRegimes : undefined,
          marketsOnly: robustness.validMarkets.length <= 2 ? robustness.validMarkets : undefined
        };
      }
      
      const result: EdgeValidationResult = {
        strategyId,
        strategyName,
        metrics,
        robustness,
        similarity,
        confidence,
        recommendedStatus: status,
        statusReason: reason,
        limitations,
        validatedAt: Date.now()
      };
      
      // Cache and store
      validationCache.set(strategyId, result);
      
      await validationsCol.updateOne(
        { strategyId },
        { $set: { ...result, storedAt: new Date() } },
        { upsert: true }
      ).catch(() => {});
      
      return result;
    },
    
    async validateAllStrategies(strategies): Promise<EdgeValidationResult[]> {
      const allStrategiesForSimilarity = strategies.map(s => ({
        id: s.id,
        features: s.features
      }));
      
      const results: EdgeValidationResult[] = [];
      
      for (const strategy of strategies) {
        const result = await this.validateStrategy(
          strategy.id,
          strategy.name,
          strategy.features,
          strategy.metrics,
          allStrategiesForSimilarity
        );
        results.push(result);
      }
      
      return results;
    },
    
    async getValidation(strategyId): Promise<EdgeValidationResult | null> {
      // Check cache
      if (validationCache.has(strategyId)) {
        return validationCache.get(strategyId)!;
      }
      
      // Check DB
      const stored = await validationsCol.findOne(
        { strategyId },
        { projection: { _id: 0 } }
      );
      
      if (stored) {
        validationCache.set(strategyId, stored as EdgeValidationResult);
        return stored as EdgeValidationResult;
      }
      
      return null;
    },
    
    async updateLifecycle(strategyId, status): Promise<boolean> {
      const result = await validationsCol.updateOne(
        { strategyId },
        { $set: { recommendedStatus: status, updatedAt: new Date() } }
      );
      
      // Update cache
      const cached = validationCache.get(strategyId);
      if (cached) {
        cached.recommendedStatus = status;
      }
      
      return result.modifiedCount > 0;
    },
    
    async getSummary(): Promise<{
      total: number;
      approved: number;
      limited: number;
      testing: number;
      candidates: number;
      rejected: number;
      avgConfidence: number;
    }> {
      const all = await validationsCol
        .find({})
        .project({ recommendedStatus: 1, confidence: 1 })
        .toArray();
      
      const summary = {
        total: all.length,
        approved: 0,
        limited: 0,
        testing: 0,
        candidates: 0,
        rejected: 0,
        avgConfidence: 0
      };
      
      let totalConfidence = 0;
      
      for (const v of all) {
        switch (v.recommendedStatus) {
          case 'APPROVED': summary.approved++; break;
          case 'LIMITED': summary.limited++; break;
          case 'TESTING': summary.testing++; break;
          case 'CANDIDATE': summary.candidates++; break;
          case 'REJECTED': summary.rejected++; break;
        }
        
        if (v.confidence?.adjustedConfidence) {
          totalConfidence += v.confidence.adjustedConfidence;
        }
      }
      
      summary.avgConfidence = all.length > 0 ? totalConfidence / all.length : 0;
      
      return summary;
    },
    
    health(): { enabled: boolean; version: string } {
      return {
        enabled: config.enabled,
        version: 'edge_validation_v1_phase9.5'
      };
    }
  };
}

// Singleton
let edgeServiceInstance: EdgeValidationService | null = null;

export function getEdgeValidationService(db: Db, config?: EdgeValidationConfig): EdgeValidationService {
  if (!edgeServiceInstance) {
    edgeServiceInstance = createEdgeValidationService(db, config);
  }
  return edgeServiceInstance;
}
