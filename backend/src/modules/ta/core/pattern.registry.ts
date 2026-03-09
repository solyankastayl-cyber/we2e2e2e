/**
 * Pattern Registry
 * 
 * Unified registry for classic and discovered patterns
 */

import { Db, Collection } from 'mongodb';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type PatternSource = 'classic' | 'discovered' | 'custom';

export interface PatternRegistryEntry {
  patternId: string;
  name: string;
  source: PatternSource;
  group: string;               // e.g., 'TRIANGLES', 'HARMONICS'
  
  // Priors (historical stats)
  priors: {
    successRate: number;
    avgR: number;
    profitFactor: number;
    sampleSize: number;
  };
  
  // Detection config
  detectionConfig: {
    minMaturity?: number;
    minTouches?: number;
    minConfidence?: number;
  };
  
  // Status
  enabled: boolean;
  qualityScore?: number;
  lastUpdated: Date;
}

// ═══════════════════════════════════════════════════════════════
// COLLECTIONS
// ═══════════════════════════════════════════════════════════════

const COLLECTION_REGISTRY = 'ta_pattern_registry';

// ═══════════════════════════════════════════════════════════════
// CLASSIC PATTERNS (99 patterns)
// ═══════════════════════════════════════════════════════════════

const CLASSIC_PATTERNS: Omit<PatternRegistryEntry, 'lastUpdated'>[] = [
  // Triangles
  { patternId: 'TRIANGLE_ASC', name: 'Ascending Triangle', source: 'classic', group: 'TRIANGLES', priors: { successRate: 0.68, avgR: 0.85, profitFactor: 1.6, sampleSize: 10000 }, detectionConfig: { minTouches: 2 }, enabled: true },
  { patternId: 'TRIANGLE_DESC', name: 'Descending Triangle', source: 'classic', group: 'TRIANGLES', priors: { successRate: 0.65, avgR: 0.80, profitFactor: 1.5, sampleSize: 10000 }, detectionConfig: { minTouches: 2 }, enabled: true },
  { patternId: 'TRIANGLE_SYM', name: 'Symmetrical Triangle', source: 'classic', group: 'TRIANGLES', priors: { successRate: 0.55, avgR: 0.70, profitFactor: 1.3, sampleSize: 10000 }, detectionConfig: { minTouches: 2 }, enabled: true },
  
  // Channels
  { patternId: 'CHANNEL_UP', name: 'Ascending Channel', source: 'classic', group: 'CHANNELS', priors: { successRate: 0.60, avgR: 0.75, profitFactor: 1.4, sampleSize: 8000 }, detectionConfig: { minTouches: 3 }, enabled: true },
  { patternId: 'CHANNEL_DOWN', name: 'Descending Channel', source: 'classic', group: 'CHANNELS', priors: { successRate: 0.60, avgR: 0.75, profitFactor: 1.4, sampleSize: 8000 }, detectionConfig: { minTouches: 3 }, enabled: true },
  { patternId: 'CHANNEL_HORIZ', name: 'Horizontal Channel', source: 'classic', group: 'CHANNELS', priors: { successRate: 0.55, avgR: 0.65, profitFactor: 1.2, sampleSize: 8000 }, detectionConfig: { minTouches: 3 }, enabled: true },
  
  // Flags
  { patternId: 'FLAG_BULL', name: 'Bull Flag', source: 'classic', group: 'FLAGS', priors: { successRate: 0.70, avgR: 0.90, profitFactor: 1.7, sampleSize: 6000 }, detectionConfig: { minMaturity: 0.3 }, enabled: true },
  { patternId: 'FLAG_BEAR', name: 'Bear Flag', source: 'classic', group: 'FLAGS', priors: { successRate: 0.68, avgR: 0.85, profitFactor: 1.6, sampleSize: 6000 }, detectionConfig: { minMaturity: 0.3 }, enabled: true },
  { patternId: 'PENNANT_BULL', name: 'Bull Pennant', source: 'classic', group: 'FLAGS', priors: { successRate: 0.65, avgR: 0.80, profitFactor: 1.5, sampleSize: 5000 }, detectionConfig: { minMaturity: 0.3 }, enabled: true },
  { patternId: 'PENNANT_BEAR', name: 'Bear Pennant', source: 'classic', group: 'FLAGS', priors: { successRate: 0.63, avgR: 0.78, profitFactor: 1.45, sampleSize: 5000 }, detectionConfig: { minMaturity: 0.3 }, enabled: true },
  
  // Head and Shoulders
  { patternId: 'HEAD_SHOULDERS', name: 'Head and Shoulders', source: 'classic', group: 'REVERSALS', priors: { successRate: 0.72, avgR: 1.20, profitFactor: 1.9, sampleSize: 4000 }, detectionConfig: { minTouches: 5 }, enabled: true },
  { patternId: 'HEAD_SHOULDERS_INV', name: 'Inverse Head and Shoulders', source: 'classic', group: 'REVERSALS', priors: { successRate: 0.70, avgR: 1.15, profitFactor: 1.8, sampleSize: 4000 }, detectionConfig: { minTouches: 5 }, enabled: true },
  
  // Double patterns
  { patternId: 'DOUBLE_TOP', name: 'Double Top', source: 'classic', group: 'REVERSALS', priors: { successRate: 0.65, avgR: 0.95, profitFactor: 1.55, sampleSize: 7000 }, detectionConfig: { minTouches: 2 }, enabled: true },
  { patternId: 'DOUBLE_BOTTOM', name: 'Double Bottom', source: 'classic', group: 'REVERSALS', priors: { successRate: 0.67, avgR: 1.00, profitFactor: 1.6, sampleSize: 7000 }, detectionConfig: { minTouches: 2 }, enabled: true },
  { patternId: 'TRIPLE_TOP', name: 'Triple Top', source: 'classic', group: 'REVERSALS', priors: { successRate: 0.70, avgR: 1.10, profitFactor: 1.75, sampleSize: 3000 }, detectionConfig: { minTouches: 3 }, enabled: true },
  { patternId: 'TRIPLE_BOTTOM', name: 'Triple Bottom', source: 'classic', group: 'REVERSALS', priors: { successRate: 0.72, avgR: 1.15, profitFactor: 1.8, sampleSize: 3000 }, detectionConfig: { minTouches: 3 }, enabled: true },
  
  // Wedges
  { patternId: 'WEDGE_RISING', name: 'Rising Wedge', source: 'classic', group: 'WEDGES', priors: { successRate: 0.62, avgR: 0.85, profitFactor: 1.45, sampleSize: 5000 }, detectionConfig: { minTouches: 3 }, enabled: true },
  { patternId: 'WEDGE_FALLING', name: 'Falling Wedge', source: 'classic', group: 'WEDGES', priors: { successRate: 0.64, avgR: 0.88, profitFactor: 1.5, sampleSize: 5000 }, detectionConfig: { minTouches: 3 }, enabled: true },
  
  // S/R patterns
  { patternId: 'SR_FLIP_LONG', name: 'Support/Resistance Flip (Long)', source: 'classic', group: 'SR_PATTERNS', priors: { successRate: 0.55, avgR: 0.70, profitFactor: 1.3, sampleSize: 15000 }, detectionConfig: { minTouches: 2 }, enabled: true },
  { patternId: 'SR_FLIP_SHORT', name: 'Support/Resistance Flip (Short)', source: 'classic', group: 'SR_PATTERNS', priors: { successRate: 0.55, avgR: 0.70, profitFactor: 1.3, sampleSize: 15000 }, detectionConfig: { minTouches: 2 }, enabled: true },
  
  // Harmonics
  { patternId: 'HARMONIC_GARTLEY', name: 'Gartley Pattern', source: 'classic', group: 'HARMONICS', priors: { successRate: 0.60, avgR: 1.00, profitFactor: 1.5, sampleSize: 2000 }, detectionConfig: { minConfidence: 0.7 }, enabled: true },
  { patternId: 'HARMONIC_BAT', name: 'Bat Pattern', source: 'classic', group: 'HARMONICS', priors: { successRate: 0.58, avgR: 0.95, profitFactor: 1.45, sampleSize: 2000 }, detectionConfig: { minConfidence: 0.7 }, enabled: true },
  { patternId: 'HARMONIC_BUTTERFLY', name: 'Butterfly Pattern', source: 'classic', group: 'HARMONICS', priors: { successRate: 0.56, avgR: 0.90, profitFactor: 1.4, sampleSize: 2000 }, detectionConfig: { minConfidence: 0.7 }, enabled: true },
  { patternId: 'HARMONIC_CRAB', name: 'Crab Pattern', source: 'classic', group: 'HARMONICS', priors: { successRate: 0.55, avgR: 0.85, profitFactor: 1.35, sampleSize: 2000 }, detectionConfig: { minConfidence: 0.7 }, enabled: true },
  
  // Elliott Waves
  { patternId: 'ELLIOTT_IMPULSE', name: 'Elliott Impulse Wave', source: 'classic', group: 'WAVES', priors: { successRate: 0.52, avgR: 0.75, profitFactor: 1.2, sampleSize: 3000 }, detectionConfig: { minMaturity: 0.5 }, enabled: true },
  { patternId: 'ELLIOTT_CORRECTION', name: 'Elliott Correction', source: 'classic', group: 'WAVES', priors: { successRate: 0.50, avgR: 0.70, profitFactor: 1.15, sampleSize: 3000 }, detectionConfig: { minMaturity: 0.5 }, enabled: true },
];

// ═══════════════════════════════════════════════════════════════
// PATTERN REGISTRY SERVICE
// ═══════════════════════════════════════════════════════════════

export class PatternRegistryService {
  private db: Db;
  private registryCol: Collection;
  
  constructor(db: Db) {
    this.db = db;
    this.registryCol = db.collection(COLLECTION_REGISTRY);
  }
  
  /**
   * Initialize registry with classic patterns
   */
  async initialize(): Promise<void> {
    await this.registryCol.createIndex({ patternId: 1 }, { unique: true });
    await this.registryCol.createIndex({ source: 1, enabled: 1 });
    await this.registryCol.createIndex({ group: 1 });
    
    // Seed classic patterns
    for (const pattern of CLASSIC_PATTERNS) {
      await this.registryCol.updateOne(
        { patternId: pattern.patternId },
        { 
          $setOnInsert: { ...pattern, lastUpdated: new Date() }
        },
        { upsert: true }
      );
    }
    
    const count = await this.registryCol.countDocuments();
    console.log(`[PatternRegistry] Initialized with ${count} patterns`);
  }
  
  /**
   * Get all enabled patterns
   */
  async getEnabledPatterns(): Promise<PatternRegistryEntry[]> {
    return this.registryCol.find({ enabled: true }).toArray() as any;
  }
  
  /**
   * Get pattern by ID
   */
  async getPattern(patternId: string): Promise<PatternRegistryEntry | null> {
    return this.registryCol.findOne({ patternId }) as any;
  }
  
  /**
   * Get patterns by group
   */
  async getPatternsByGroup(group: string): Promise<PatternRegistryEntry[]> {
    return this.registryCol.find({ group, enabled: true }).toArray() as any;
  }
  
  /**
   * Get patterns by source
   */
  async getPatternsBySource(source: PatternSource): Promise<PatternRegistryEntry[]> {
    return this.registryCol.find({ source, enabled: true }).toArray() as any;
  }
  
  /**
   * Register a discovered pattern
   */
  async registerDiscoveredPattern(
    patternId: string,
    name: string,
    priors: PatternRegistryEntry['priors']
  ): Promise<void> {
    const entry: PatternRegistryEntry = {
      patternId,
      name,
      source: 'discovered',
      group: 'DISCOVERED',
      priors,
      detectionConfig: {},
      enabled: true,
      lastUpdated: new Date(),
    };
    
    await this.registryCol.updateOne(
      { patternId },
      { $set: entry },
      { upsert: true }
    );
    
    console.log(`[PatternRegistry] Registered discovered pattern: ${name}`);
  }
  
  /**
   * Update pattern priors
   */
  async updatePriors(
    patternId: string,
    priors: Partial<PatternRegistryEntry['priors']>
  ): Promise<void> {
    await this.registryCol.updateOne(
      { patternId },
      { 
        $set: { 
          ...Object.fromEntries(
            Object.entries(priors).map(([k, v]) => [`priors.${k}`, v])
          ),
          lastUpdated: new Date()
        }
      }
    );
  }
  
  /**
   * Enable/disable pattern
   */
  async setEnabled(patternId: string, enabled: boolean): Promise<void> {
    await this.registryCol.updateOne(
      { patternId },
      { $set: { enabled, lastUpdated: new Date() } }
    );
  }
  
  /**
   * Update quality score
   */
  async updateQualityScore(patternId: string, score: number): Promise<void> {
    await this.registryCol.updateOne(
      { patternId },
      { $set: { qualityScore: score, lastUpdated: new Date() } }
    );
  }
  
  /**
   * Get registry stats
   */
  async getStats(): Promise<{
    total: number;
    enabled: number;
    bySource: Record<string, number>;
    byGroup: Record<string, number>;
  }> {
    const total = await this.registryCol.countDocuments();
    const enabled = await this.registryCol.countDocuments({ enabled: true });
    
    const sourceAgg = await this.registryCol.aggregate([
      { $group: { _id: '$source', count: { $sum: 1 } } }
    ]).toArray();
    
    const groupAgg = await this.registryCol.aggregate([
      { $group: { _id: '$group', count: { $sum: 1 } } }
    ]).toArray();
    
    return {
      total,
      enabled,
      bySource: Object.fromEntries(sourceAgg.map(s => [s._id, s.count])),
      byGroup: Object.fromEntries(groupAgg.map(g => [g._id, g.count])),
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

export function createPatternRegistryService(db: Db): PatternRegistryService {
  return new PatternRegistryService(db);
}
