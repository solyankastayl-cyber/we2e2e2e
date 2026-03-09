/**
 * P1.4 — MetaBrain v2.3 Regime Learning Storage
 */

import mongoose, { Schema, Document, Model } from 'mongoose';
import { AnalysisModule, ALL_MODULES } from '../metabrain_learning/module_attribution.types.js';
import { MarketRegime } from '../regime/regime.types.js';
import { RegimeModuleWeight, RegimeWeightMap, ALL_REGIMES } from './regime.learning.types.js';
import { buildRegimeWeightMap } from './regime.learning.js';

// ═══════════════════════════════════════════════════════════════
// SCHEMA
// ═══════════════════════════════════════════════════════════════

interface RegimeWeightDoc extends Document {
  module: string;
  regime: string;
  weight: number;
  sampleSize: number;
  avgOutcomeImpact: number;
  confidence: number;
  updatedAt: Date;
  createdAt: Date;
}

const RegimeWeightSchema = new Schema<RegimeWeightDoc>({
  module: { type: String, required: true, index: true },
  regime: { type: String, required: true, index: true },
  weight: { type: Number, required: true },
  sampleSize: { type: Number, required: true },
  avgOutcomeImpact: { type: Number, required: true },
  confidence: { type: Number, required: true },
  updatedAt: { type: Date, default: Date.now },
  createdAt: { type: Date, default: Date.now }
}, {
  collection: 'ta_module_regime_weights'
});

RegimeWeightSchema.index({ module: 1, regime: 1 }, { unique: true });

// ═══════════════════════════════════════════════════════════════
// MODEL
// ═══════════════════════════════════════════════════════════════

export const RegimeWeightModel: Model<RegimeWeightDoc> = mongoose.models.RegimeWeight ||
  mongoose.model<RegimeWeightDoc>('RegimeWeight', RegimeWeightSchema);

// ═══════════════════════════════════════════════════════════════
// STORAGE FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Save regime weight
 */
export async function saveRegimeWeight(weight: RegimeModuleWeight): Promise<void> {
  await RegimeWeightModel.findOneAndUpdate(
    { module: weight.module, regime: weight.regime },
    {
      weight: weight.weight,
      sampleSize: weight.sampleSize,
      avgOutcomeImpact: weight.avgOutcomeImpact,
      confidence: weight.confidence,
      updatedAt: new Date(weight.updatedAt)
    },
    { upsert: true, new: true }
  );
}

/**
 * Save multiple regime weights
 */
export async function saveRegimeWeights(weights: RegimeModuleWeight[]): Promise<void> {
  const operations = weights.map(w => ({
    updateOne: {
      filter: { module: w.module, regime: w.regime },
      update: {
        $set: {
          weight: w.weight,
          sampleSize: w.sampleSize,
          avgOutcomeImpact: w.avgOutcomeImpact,
          confidence: w.confidence,
          updatedAt: new Date(w.updatedAt)
        },
        $setOnInsert: {
          createdAt: new Date()
        }
      },
      upsert: true
    }
  }));
  
  await RegimeWeightModel.bulkWrite(operations);
}

/**
 * Get weight for module/regime
 */
export async function getRegimeWeight(
  module: AnalysisModule,
  regime: MarketRegime
): Promise<RegimeModuleWeight | null> {
  const doc = await RegimeWeightModel.findOne({ module, regime });
  
  if (!doc) return null;
  
  return {
    module: doc.module as AnalysisModule,
    regime: doc.regime as MarketRegime,
    weight: doc.weight,
    sampleSize: doc.sampleSize,
    avgOutcomeImpact: doc.avgOutcomeImpact,
    confidence: doc.confidence,
    updatedAt: doc.updatedAt.getTime(),
    createdAt: doc.createdAt.getTime()
  };
}

/**
 * Get all weights for a regime
 */
export async function getRegimeWeights(regime: MarketRegime): Promise<RegimeModuleWeight[]> {
  const docs = await RegimeWeightModel.find({ regime }).lean();
  
  return docs.map(doc => ({
    module: doc.module as AnalysisModule,
    regime: doc.regime as MarketRegime,
    weight: doc.weight,
    sampleSize: doc.sampleSize,
    avgOutcomeImpact: doc.avgOutcomeImpact,
    confidence: doc.confidence,
    updatedAt: doc.updatedAt.getTime(),
    createdAt: doc.createdAt.getTime()
  }));
}

/**
 * Get all regime weights
 */
export async function getAllRegimeWeights(): Promise<RegimeModuleWeight[]> {
  const docs = await RegimeWeightModel.find().lean();
  
  return docs.map(doc => ({
    module: doc.module as AnalysisModule,
    regime: doc.regime as MarketRegime,
    weight: doc.weight,
    sampleSize: doc.sampleSize,
    avgOutcomeImpact: doc.avgOutcomeImpact,
    confidence: doc.confidence,
    updatedAt: doc.updatedAt.getTime(),
    createdAt: doc.createdAt.getTime()
  }));
}

/**
 * Get regime weight maps
 */
export async function getRegimeWeightMaps(): Promise<RegimeWeightMap[]> {
  const weights = await getAllRegimeWeights();
  
  return ALL_REGIMES.map(regime => buildRegimeWeightMap(regime, weights));
}

/**
 * Get weights as map
 */
export async function getRegimeWeightsMap(): Promise<Map<string, RegimeModuleWeight>> {
  const weights = await getAllRegimeWeights();
  const map = new Map<string, RegimeModuleWeight>();
  
  for (const w of weights) {
    map.set(`${w.module}:${w.regime}`, w);
  }
  
  return map;
}

/**
 * Delete weights for regime
 */
export async function deleteRegimeWeights(regime: MarketRegime): Promise<number> {
  const result = await RegimeWeightModel.deleteMany({ regime });
  return result.deletedCount;
}

/**
 * Reset all regime weights
 */
export async function resetAllRegimeWeights(): Promise<number> {
  const result = await RegimeWeightModel.deleteMany({});
  return result.deletedCount;
}
