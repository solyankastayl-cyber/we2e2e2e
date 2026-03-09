/**
 * Feature Schema Registry
 * 
 * Manages versioned feature schemas for ML models
 * Protects against silent feature drift
 */

import { Db } from 'mongodb';
import * as crypto from 'crypto';

export interface FeatureSchema {
  version: string;
  features: string[];
  schemaHash: string;
  description?: string;
  createdAt: Date;
  isActive: boolean;
}

// Current v1.0.0 features (locked)
export const FEATURE_SCHEMA_V1: string[] = [
  'pattern_score',
  'compression_score', 
  'impulse_score',
  'rsi',
  'macd',
  'atr',
  'bb_width',
  'ma_alignment',
  'trend_slope',
  'volume_spike',
  'breakout_distance',
  'risk_reward',
  'pattern_confidence',
  'graph_boost',
  'stability_score',
  'scenario_p_target',
  'scenario_p_stop',
  'scenario_p_timeout'
];

export class FeatureSchemaRegistry {
  private db: Db;
  private collectionName = 'ta_feature_schema';
  
  constructor(db: Db) {
    this.db = db;
  }

  async ensureIndexes(): Promise<void> {
    const collection = this.db.collection(this.collectionName);
    await collection.createIndex({ version: 1 }, { unique: true });
    await collection.createIndex({ schemaHash: 1 }, { unique: true });
    await collection.createIndex({ isActive: 1 });
  }

  /**
   * Generate SHA256 hash of features
   */
  generateHash(features: string[]): string {
    const sorted = [...features].sort();
    const hash = crypto.createHash('sha256')
      .update(sorted.join(','))
      .digest('hex');
    return hash.substring(0, 16);
  }

  /**
   * Register a new feature schema
   */
  async register(version: string, features: string[], description?: string): Promise<FeatureSchema> {
    const schemaHash = this.generateHash(features);
    
    const schema: FeatureSchema = {
      version,
      features,
      schemaHash,
      description,
      createdAt: new Date(),
      isActive: true
    };
    
    // Deactivate previous schemas
    await this.db.collection(this.collectionName).updateMany(
      { isActive: true },
      { $set: { isActive: false } }
    );
    
    // Insert new
    await this.db.collection(this.collectionName).insertOne(schema);
    
    return schema;
  }

  /**
   * Get active schema
   */
  async getActive(): Promise<FeatureSchema | null> {
    const schema = await this.db.collection(this.collectionName)
      .findOne({ isActive: true });
    return schema as FeatureSchema | null;
  }

  /**
   * Get schema by version
   */
  async getByVersion(version: string): Promise<FeatureSchema | null> {
    const schema = await this.db.collection(this.collectionName)
      .findOne({ version });
    return schema as FeatureSchema | null;
  }

  /**
   * Get schema by hash
   */
  async getByHash(schemaHash: string): Promise<FeatureSchema | null> {
    const schema = await this.db.collection(this.collectionName)
      .findOne({ schemaHash });
    return schema as FeatureSchema | null;
  }

  /**
   * Validate features against active schema
   */
  async validate(features: Record<string, any>): Promise<{
    valid: boolean;
    missing: string[];
    extra: string[];
  }> {
    const active = await this.getActive();
    if (!active) {
      return { valid: false, missing: [], extra: [] };
    }
    
    const requiredFeatures = new Set(active.features);
    const providedFeatures = new Set(Object.keys(features));
    
    const missing = [...requiredFeatures].filter(f => !providedFeatures.has(f));
    const extra = [...providedFeatures].filter(f => !requiredFeatures.has(f));
    
    return {
      valid: missing.length === 0,
      missing,
      extra
    };
  }

  /**
   * Get all schemas
   */
  async getAll(): Promise<FeatureSchema[]> {
    const schemas = await this.db.collection(this.collectionName)
      .find({})
      .sort({ createdAt: -1 })
      .toArray();
    return schemas as unknown as FeatureSchema[];
  }
}

// Singleton
let registryInstance: FeatureSchemaRegistry | null = null;

export function getFeatureSchemaRegistry(db: Db): FeatureSchemaRegistry {
  if (!registryInstance) {
    registryInstance = new FeatureSchemaRegistry(db);
  }
  return registryInstance;
}
