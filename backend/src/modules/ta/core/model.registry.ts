/**
 * Model Registry
 * 
 * Tracks ML model versions, metrics, and deployment stages
 */

import { Db, Collection } from 'mongodb';
import { v4 as uuid } from 'uuid';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type ModelStage = 'SHADOW' | 'LIVE_LITE' | 'LIVE_MED' | 'LIVE_FULL' | 'RETIRED';

export interface ModelRecord {
  modelId: string;
  name: string;
  type: 'entry' | 'r' | 'regime';
  version: string;
  
  // Metrics
  metrics: {
    auc?: number;
    accuracy?: number;
    precision?: number;
    recall?: number;
    mae?: number;
    rmse?: number;
    r2?: number;
    ece?: number;            // Expected calibration error
    profitFactor?: number;
    evCorrelation?: number;
  };
  
  // Training info
  trainingInfo: {
    datasetSize: number;
    trainRows: number;
    valRows: number;
    testRows: number;
    trainPeriod: { from: string; to: string };
    features: string[];
    hyperparams?: Record<string, any>;
  };
  
  // Deployment
  stage: ModelStage;
  artifactPath: string;
  
  // Timestamps
  createdAt: Date;
  promotedAt?: Date;
  retiredAt?: Date;
}

export interface FeatureSchema {
  version: string;
  features: string[];
  createdAt: Date;
  active: boolean;
}

// ═══════════════════════════════════════════════════════════════
// COLLECTIONS
// ═══════════════════════════════════════════════════════════════

const COLLECTION_MODELS = 'ta_models';
const COLLECTION_SCHEMA = 'ta_feature_schema';

// ═══════════════════════════════════════════════════════════════
// MODEL REGISTRY
// ═══════════════════════════════════════════════════════════════

export class ModelRegistry {
  private db: Db;
  private modelsCol: Collection;
  private schemaCol: Collection;
  
  constructor(db: Db) {
    this.db = db;
    this.modelsCol = db.collection(COLLECTION_MODELS);
    this.schemaCol = db.collection(COLLECTION_SCHEMA);
  }
  
  /**
   * Initialize indexes
   */
  async ensureIndexes(): Promise<void> {
    await this.modelsCol.createIndex({ modelId: 1 }, { unique: true });
    await this.modelsCol.createIndex({ type: 1, stage: 1 });
    await this.modelsCol.createIndex({ createdAt: -1 });
    
    await this.schemaCol.createIndex({ version: 1 }, { unique: true });
    await this.schemaCol.createIndex({ active: 1 });
    
    console.log('[ModelRegistry] Indexes created');
  }
  
  /**
   * Register a new model
   */
  async registerModel(model: Omit<ModelRecord, 'createdAt'>): Promise<string> {
    const record: ModelRecord = {
      ...model,
      createdAt: new Date(),
    };
    
    await this.modelsCol.insertOne(record);
    console.log(`[ModelRegistry] Registered model ${model.modelId} (${model.type})`);
    
    return model.modelId;
  }
  
  /**
   * Get model by ID
   */
  async getModel(modelId: string): Promise<ModelRecord | null> {
    return this.modelsCol.findOne({ modelId }) as any;
  }
  
  /**
   * Get active model for type
   */
  async getActiveModel(type: 'entry' | 'r' | 'regime'): Promise<ModelRecord | null> {
    // Get highest stage model that's not SHADOW or RETIRED
    return this.modelsCol.findOne(
      { 
        type,
        stage: { $in: ['LIVE_LITE', 'LIVE_MED', 'LIVE_FULL'] }
      },
      { sort: { createdAt: -1 } }
    ) as any;
  }
  
  /**
   * Promote model to next stage
   */
  async promoteModel(modelId: string, toStage: ModelStage): Promise<boolean> {
    const result = await this.modelsCol.updateOne(
      { modelId },
      { 
        $set: { 
          stage: toStage,
          promotedAt: new Date()
        }
      }
    );
    
    if (result.modifiedCount > 0) {
      console.log(`[ModelRegistry] Promoted model ${modelId} to ${toStage}`);
      return true;
    }
    return false;
  }
  
  /**
   * Retire a model
   */
  async retireModel(modelId: string): Promise<boolean> {
    const result = await this.modelsCol.updateOne(
      { modelId },
      { 
        $set: { 
          stage: 'RETIRED',
          retiredAt: new Date()
        }
      }
    );
    return result.modifiedCount > 0;
  }
  
  /**
   * Get all models
   */
  async getAllModels(): Promise<ModelRecord[]> {
    return this.modelsCol.find().sort({ createdAt: -1 }).toArray() as any;
  }
  
  /**
   * Check quality gates for promotion
   */
  async checkQualityGates(
    modelId: string,
    previousModelId?: string
  ): Promise<{
    passed: boolean;
    checks: Record<string, { passed: boolean; value: number; threshold: number }>;
  }> {
    const model = await this.getModel(modelId);
    if (!model) {
      return { passed: false, checks: {} };
    }
    
    const checks: Record<string, { passed: boolean; value: number; threshold: number }> = {};
    
    // AUC check (for entry models)
    if (model.type === 'entry' && model.metrics.auc !== undefined) {
      const threshold = 0.55;
      checks['auc'] = {
        passed: model.metrics.auc >= threshold,
        value: model.metrics.auc,
        threshold,
      };
    }
    
    // ECE check (calibration)
    if (model.metrics.ece !== undefined) {
      const threshold = 0.08;
      checks['ece'] = {
        passed: model.metrics.ece <= threshold,
        value: model.metrics.ece,
        threshold,
      };
    }
    
    // MAE check (for R models)
    if (model.type === 'r' && model.metrics.mae !== undefined) {
      const threshold = 1.2;
      checks['mae'] = {
        passed: model.metrics.mae <= threshold,
        value: model.metrics.mae,
        threshold,
      };
    }
    
    // Profit factor check
    if (model.metrics.profitFactor !== undefined) {
      const threshold = 1.0;
      checks['profitFactor'] = {
        passed: model.metrics.profitFactor >= threshold,
        value: model.metrics.profitFactor,
        threshold,
      };
    }
    
    // Compare with previous model if provided
    if (previousModelId) {
      const prevModel = await this.getModel(previousModelId);
      if (prevModel && prevModel.metrics.auc && model.metrics.auc) {
        checks['auc_improvement'] = {
          passed: model.metrics.auc >= prevModel.metrics.auc,
          value: model.metrics.auc - prevModel.metrics.auc,
          threshold: 0,
        };
      }
    }
    
    const passed = Object.values(checks).every(c => c.passed);
    
    return { passed, checks };
  }
  
  // ═══════════════════════════════════════════════════════════════
  // FEATURE SCHEMA
  // ═══════════════════════════════════════════════════════════════
  
  /**
   * Register feature schema
   */
  async registerFeatureSchema(version: string, features: string[]): Promise<void> {
    // Deactivate previous schemas
    await this.schemaCol.updateMany(
      { active: true },
      { $set: { active: false } }
    );
    
    const schema: FeatureSchema = {
      version,
      features,
      createdAt: new Date(),
      active: true,
    };
    
    await this.schemaCol.updateOne(
      { version },
      { $set: schema },
      { upsert: true }
    );
    
    console.log(`[ModelRegistry] Registered feature schema v${version} with ${features.length} features`);
  }
  
  /**
   * Get active feature schema
   */
  async getActiveSchema(): Promise<FeatureSchema | null> {
    return this.schemaCol.findOne({ active: true }) as any;
  }
  
  /**
   * Validate features against schema
   */
  async validateFeatures(features: Record<string, any>): Promise<{
    valid: boolean;
    missing: string[];
    extra: string[];
  }> {
    const schema = await this.getActiveSchema();
    if (!schema) {
      return { valid: true, missing: [], extra: [] };
    }
    
    const featureKeys = Object.keys(features);
    const missing = schema.features.filter(f => !featureKeys.includes(f));
    const extra = featureKeys.filter(f => !schema.features.includes(f));
    
    return {
      valid: missing.length === 0,
      missing,
      extra,
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// FACTORY
// ═══════════════════════════════════════════════════════════════

let registryInstance: ModelRegistry | null = null;

export function getModelRegistry(db: Db): ModelRegistry {
  if (!registryInstance) {
    registryInstance = new ModelRegistry(db);
  }
  return registryInstance;
}

export function createModelRegistry(db: Db): ModelRegistry {
  return new ModelRegistry(db);
}
