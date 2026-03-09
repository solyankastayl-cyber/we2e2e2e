/**
 * P2.0 — Quality Repository (MongoDB)
 */

import { Db, Collection } from 'mongodb';
import { PatternQualityDoc, QualityKey, QualityQueryParams } from './quality.types.js';

const COLLECTION_NAME = 'ta_pattern_quality';

export class QualityRepo {
  private collection: Collection<PatternQualityDoc>;
  
  constructor(db: Db) {
    this.collection = db.collection(COLLECTION_NAME);
  }
  
  /**
   * Ensure indexes
   */
  async ensureIndexes(): Promise<void> {
    // Unique compound index
    await this.collection.createIndex(
      { patternType: 1, asset: 1, tf: 1, regime: 1 },
      { unique: true }
    );
    
    // For queries by updatedAt
    await this.collection.createIndex({ updatedAt: -1 });
    
    // For quality score sorting
    await this.collection.createIndex({ qualityScore: -1 });
  }
  
  /**
   * Upsert quality document
   */
  async upsert(doc: PatternQualityDoc): Promise<void> {
    await this.collection.updateOne(
      {
        patternType: doc.patternType,
        asset: doc.asset,
        tf: doc.tf,
        regime: doc.regime,
      },
      { $set: doc },
      { upsert: true }
    );
  }
  
  /**
   * Get quality by key
   */
  async get(key: QualityKey): Promise<PatternQualityDoc | null> {
    return this.collection.findOne({
      patternType: key.patternType,
      asset: key.asset,
      tf: key.tf,
      regime: key.regime,
    });
  }
  
  /**
   * Get top patterns by quality score
   */
  async top(params: QualityQueryParams): Promise<PatternQualityDoc[]> {
    const filter: Record<string, any> = {};
    
    if (params.asset) filter.asset = params.asset;
    if (params.tf) filter.tf = params.tf;
    if (params.regime) filter.regime = params.regime;
    if (params.patternType) filter.patternType = params.patternType;
    
    return this.collection
      .find(filter)
      .sort({ qualityScore: -1 })
      .limit(params.limit || 20)
      .toArray();
  }
  
  /**
   * Get all quality docs
   */
  async getAll(): Promise<PatternQualityDoc[]> {
    return this.collection.find({}).toArray();
  }
  
  /**
   * Delete all (for rebuild)
   */
  async deleteAll(): Promise<number> {
    const result = await this.collection.deleteMany({});
    return result.deletedCount;
  }
  
  /**
   * Get count
   */
  async count(): Promise<number> {
    return this.collection.countDocuments();
  }
}

export function createQualityRepo(db: Db): QualityRepo {
  return new QualityRepo(db);
}
