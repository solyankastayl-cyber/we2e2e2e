/**
 * Model Registry
 * 
 * Manages ML model metadata and versioning
 */

import { Db } from 'mongodb';

export type ModelStage = 'DEV' | 'STAGING' | 'LIVE_LOW' | 'LIVE_MED' | 'LIVE_HIGH' | 'DEPRECATED';

export interface ModelRecord {
  modelId: string;
  type: 'entry_probability' | 'expected_r' | 'confidence' | 'regime';
  version: string;
  stage: ModelStage;
  
  // Metrics
  metrics: {
    auc?: number;        // For classification
    ece?: number;        // Expected Calibration Error
    mae?: number;        // For regression
    rmse?: number;
    r2?: number;
  };
  
  // Linkage
  featuresSchema: string;   // Schema version this model was trained on
  trainingDataRows: number;
  trainingDateRange: {
    from: string;
    to: string;
  };
  
  // Paths
  artifactPath: string;
  
  // Timestamps
  createdAt: Date;
  updatedAt: Date;
  promotedAt?: Date;
  deprecatedAt?: Date;
  
  // Notes
  notes?: string;
}

export class ModelRegistry {
  private db: Db;
  private collectionName = 'ta_model_registry';
  
  constructor(db: Db) {
    this.db = db;
  }

  async ensureIndexes(): Promise<void> {
    const collection = this.db.collection(this.collectionName);
    await collection.createIndex({ modelId: 1 }, { unique: true });
    await collection.createIndex({ type: 1, stage: 1 });
    await collection.createIndex({ stage: 1 });
    await collection.createIndex({ featuresSchema: 1 });
  }

  /**
   * Register a new model
   */
  async register(model: Omit<ModelRecord, 'createdAt' | 'updatedAt'>): Promise<ModelRecord> {
    const now = new Date();
    const record: ModelRecord = {
      ...model,
      createdAt: now,
      updatedAt: now
    };
    
    await this.db.collection(this.collectionName).insertOne(record);
    return record;
  }

  /**
   * Get model by ID
   */
  async getById(modelId: string): Promise<ModelRecord | null> {
    const model = await this.db.collection(this.collectionName)
      .findOne({ modelId });
    return model as ModelRecord | null;
  }

  /**
   * Get active model for type
   */
  async getActiveForType(type: ModelRecord['type']): Promise<ModelRecord | null> {
    const model = await this.db.collection(this.collectionName)
      .findOne({ 
        type, 
        stage: { $in: ['LIVE_LOW', 'LIVE_MED', 'LIVE_HIGH'] }
      }, {
        sort: { promotedAt: -1, createdAt: -1 }
      });
    return model as ModelRecord | null;
  }

  /**
   * Promote model to new stage
   */
  async promote(modelId: string, newStage: ModelStage): Promise<boolean> {
    const result = await this.db.collection(this.collectionName).updateOne(
      { modelId },
      { 
        $set: { 
          stage: newStage, 
          updatedAt: new Date(),
          promotedAt: new Date()
        }
      }
    );
    return result.modifiedCount > 0;
  }

  /**
   * Deprecate model
   */
  async deprecate(modelId: string): Promise<boolean> {
    const result = await this.db.collection(this.collectionName).updateOne(
      { modelId },
      { 
        $set: { 
          stage: 'DEPRECATED',
          updatedAt: new Date(),
          deprecatedAt: new Date()
        }
      }
    );
    return result.modifiedCount > 0;
  }

  /**
   * Get all models
   */
  async getAll(): Promise<ModelRecord[]> {
    const models = await this.db.collection(this.collectionName)
      .find({})
      .sort({ createdAt: -1 })
      .toArray();
    return models as unknown as ModelRecord[];
  }

  /**
   * Get models by stage
   */
  async getByStage(stage: ModelStage): Promise<ModelRecord[]> {
    const models = await this.db.collection(this.collectionName)
      .find({ stage })
      .sort({ createdAt: -1 })
      .toArray();
    return models as unknown as ModelRecord[];
  }

  /**
   * Get models using specific feature schema
   */
  async getBySchema(schemaVersion: string): Promise<ModelRecord[]> {
    const models = await this.db.collection(this.collectionName)
      .find({ featuresSchema: schemaVersion })
      .toArray();
    return models as unknown as ModelRecord[];
  }
}

// Singleton
let registryInstance: ModelRegistry | null = null;

export function getModelRegistry(db: Db): ModelRegistry {
  if (!registryInstance) {
    registryInstance = new ModelRegistry(db);
  }
  return registryInstance;
}
