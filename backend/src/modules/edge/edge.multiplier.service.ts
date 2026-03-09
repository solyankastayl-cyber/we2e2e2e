/**
 * Edge Multiplier Service (P5.0.9)
 * 
 * Provides edge-based multipliers for decision ranking.
 * Multiplier is applied only when:
 * - EDGE_MULT_ENABLED=true
 * - edgeStats.sampleSize >= MIN_EDGE_N
 * - edgeRun is fresh (< EDGE_MAX_AGE_H hours old)
 * - dimension=pattern and key=primaryPatternType found
 * 
 * Otherwise returns multiplier=1.0 (no-op)
 */

import { Db } from 'mongodb';
import { getEdgeStorage, EdgeStorage } from './edge.storage.js';
import { EdgeAggregate, EdgeRun } from './domain/types.js';

// ═══════════════════════════════════════════════════════════════
// Configuration Types
// ═══════════════════════════════════════════════════════════════

export interface EdgeMultiplierConfig {
  enabled: boolean;
  minN: number;
  maxAgeH: number;
  clampMin: number;
  clampMax: number;
}

export interface EdgeMultiplierResult {
  enabled: boolean;
  multiplier: number;
  clamped: boolean;
  rawMultiplier?: number;
  reason?: string;
  meta?: EdgeMultiplierMeta;
}

export interface EdgeMultiplierMeta {
  edgeRunId: string;
  source: string;
  dimension: string;
  key: string;
  n: number;
  edgeScore: number;
  rawMultiplier: number;
  finalMultiplier: number;
}

// ═══════════════════════════════════════════════════════════════
// Environment Config Reader
// ═══════════════════════════════════════════════════════════════

export function readEdgeMultiplierConfig(): EdgeMultiplierConfig {
  return {
    enabled: process.env.EDGE_MULT_ENABLED === 'true',
    minN: parseInt(process.env.EDGE_MIN_N || '200', 10),
    maxAgeH: parseInt(process.env.EDGE_MAX_AGE_H || '24', 10),
    clampMin: parseFloat(process.env.EDGE_CLAMP_MIN || '0.85'),
    clampMax: parseFloat(process.env.EDGE_CLAMP_MAX || '1.20'),
  };
}

// ═══════════════════════════════════════════════════════════════
// Edge Multiplier Service
// ═══════════════════════════════════════════════════════════════

export class EdgeMultiplierService {
  private db: Db;
  private storage: EdgeStorage;
  private config: EdgeMultiplierConfig;

  constructor(db: Db, config?: Partial<EdgeMultiplierConfig>) {
    this.db = db;
    this.storage = getEdgeStorage(db);
    this.config = { ...readEdgeMultiplierConfig(), ...config };
  }

  /**
   * Get current config
   */
  getConfig(): EdgeMultiplierConfig {
    return { ...this.config };
  }

  /**
   * Update config at runtime
   */
  updateConfig(update: Partial<EdgeMultiplierConfig>): EdgeMultiplierConfig {
    this.config = { ...this.config, ...update };
    return this.getConfig();
  }

  /**
   * Get edge multiplier for a pattern type
   * 
   * @param primaryPatternType - The main pattern type (e.g., "CUP_HANDLE_BULL")
   * @param regime - Optional market regime for context
   */
  async getMultiplier(
    primaryPatternType: string,
    regime?: string
  ): Promise<EdgeMultiplierResult> {
    // Check if enabled
    if (!this.config.enabled) {
      return {
        enabled: false,
        multiplier: 1.0,
        clamped: false,
        reason: 'EDGE_MULT_DISABLED',
      };
    }

    // Get latest run
    const latestRun = await this.storage.getLatestRun();
    if (!latestRun) {
      return {
        enabled: true,
        multiplier: 1.0,
        clamped: false,
        reason: 'NO_EDGE_RUN',
      };
    }

    // Check run freshness
    const runAgeHours = this.getRunAgeHours(latestRun);
    if (runAgeHours > this.config.maxAgeH) {
      return {
        enabled: true,
        multiplier: 1.0,
        clamped: false,
        reason: `EDGE_RUN_STALE (${runAgeHours.toFixed(1)}h > ${this.config.maxAgeH}h)`,
      };
    }

    // Get edge stat for pattern
    const stat = await this.storage.getAggregate('pattern', primaryPatternType.toUpperCase());
    if (!stat) {
      return {
        enabled: true,
        multiplier: 1.0,
        clamped: false,
        reason: `PATTERN_NOT_FOUND (${primaryPatternType})`,
      };
    }

    // Check sample size
    if (stat.sampleSize < this.config.minN) {
      return {
        enabled: true,
        multiplier: 1.0,
        clamped: false,
        reason: `INSUFFICIENT_DATA (n=${stat.sampleSize} < ${this.config.minN})`,
      };
    }

    // Calculate raw multiplier from edge score
    // edgeScore is typically -1 to +1, we convert to multiplier around 1.0
    // Formula: 1 + (edgeScore * 0.2) → gives range ~0.8 to ~1.2
    const rawMultiplier = 1 + (stat.edgeScore * 0.20);

    // Apply clamp
    const clampedMultiplier = Math.max(
      this.config.clampMin,
      Math.min(this.config.clampMax, rawMultiplier)
    );
    const wasClamped = clampedMultiplier !== rawMultiplier;

    return {
      enabled: true,
      multiplier: clampedMultiplier,
      clamped: wasClamped,
      rawMultiplier,
      meta: {
        edgeRunId: latestRun.runId,
        source: 'ta_edge_stats',
        dimension: 'pattern',
        key: primaryPatternType.toUpperCase(),
        n: stat.sampleSize,
        edgeScore: stat.edgeScore,
        rawMultiplier,
        finalMultiplier: clampedMultiplier,
      },
    };
  }

  /**
   * Get multipliers for multiple patterns at once
   */
  async getMultipliers(
    patternTypes: string[]
  ): Promise<Map<string, EdgeMultiplierResult>> {
    const results = new Map<string, EdgeMultiplierResult>();
    
    for (const pattern of patternTypes) {
      const result = await this.getMultiplier(pattern);
      results.set(pattern, result);
    }
    
    return results;
  }

  /**
   * Calculate combined multiplier for a scenario with multiple patterns
   * Uses weighted average based on pattern contribution
   */
  async getCombinedMultiplier(
    patternTypes: string[],
    weights?: number[]
  ): Promise<EdgeMultiplierResult> {
    if (patternTypes.length === 0) {
      return {
        enabled: this.config.enabled,
        multiplier: 1.0,
        clamped: false,
        reason: 'NO_PATTERNS',
      };
    }

    // Get individual multipliers
    const results = await this.getMultipliers(patternTypes);
    
    // Calculate weighted average
    const actualWeights = weights || patternTypes.map(() => 1 / patternTypes.length);
    let weightedSum = 0;
    let totalWeight = 0;
    let validCount = 0;
    
    for (let i = 0; i < patternTypes.length; i++) {
      const result = results.get(patternTypes[i]);
      if (result && result.meta) {
        weightedSum += result.multiplier * actualWeights[i];
        totalWeight += actualWeights[i];
        validCount++;
      }
    }

    if (validCount === 0) {
      return {
        enabled: this.config.enabled,
        multiplier: 1.0,
        clamped: false,
        reason: 'NO_VALID_EDGE_DATA',
      };
    }

    const combinedMultiplier = weightedSum / totalWeight;
    const clampedMultiplier = Math.max(
      this.config.clampMin,
      Math.min(this.config.clampMax, combinedMultiplier)
    );

    return {
      enabled: true,
      multiplier: clampedMultiplier,
      clamped: clampedMultiplier !== combinedMultiplier,
      rawMultiplier: combinedMultiplier,
      reason: `COMBINED (${validCount}/${patternTypes.length} patterns)`,
    };
  }

  /**
   * Helper to calculate run age in hours
   */
  private getRunAgeHours(run: EdgeRun): number {
    const finishedAt = run.finishedAt || run.startedAt;
    const ageMs = Date.now() - new Date(finishedAt).getTime();
    return ageMs / (1000 * 60 * 60);
  }
}

// ═══════════════════════════════════════════════════════════════
// Singleton
// ═══════════════════════════════════════════════════════════════

let serviceInstance: EdgeMultiplierService | null = null;

export function getEdgeMultiplierService(db: Db): EdgeMultiplierService {
  if (!serviceInstance) {
    serviceInstance = new EdgeMultiplierService(db);
  }
  return serviceInstance;
}
