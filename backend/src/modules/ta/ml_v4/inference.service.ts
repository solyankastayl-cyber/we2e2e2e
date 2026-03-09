/**
 * P1.8 — ML Inference Service
 * 
 * Loads trained LightGBM models and provides real-time predictions
 */

import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Feature names (must match training)
const FEATURES = [
  'score',
  'confidence', 
  'risk_reward',
  'gate_score',
  'geom_fit_error',
  'geom_maturity',
  'geom_compression',
  'geom_symmetry',
  'graph_boost_factor',
  'graph_lift',
  'graph_conditional_prob',
  'pattern_strength',
  'pattern_duration',
  'volatility',
  'atr_ratio',
  'regime_trend_up',
  'regime_trend_down',
  'regime_range',
];

export interface MLFeatures {
  score: number;
  confidence: number;
  risk_reward: number;
  gate_score: number;
  geom_fit_error: number;
  geom_maturity: number;
  geom_compression: number;
  geom_symmetry: number;
  graph_boost_factor: number;
  graph_lift: number;
  graph_conditional_prob: number;
  pattern_strength: number;
  pattern_duration: number;
  volatility: number;
  atr_ratio: number;
  regime_trend_up: number;
  regime_trend_down: number;
  regime_range: number;
}

export interface MLPrediction {
  pEntry: number;
  rExpected: number;
  ev: number;
  modelId: string;
  confidence: number;
}

/**
 * ML Inference Service
 * 
 * Uses Python subprocess to run predictions with LightGBM models
 */
export class MLInferenceService {
  private entryModelPath: string;
  private rModelPath: string;
  private modelsLoaded: boolean = false;
  
  constructor(
    entryModelPath: string = '/app/ml_artifacts/entry_model/model.joblib',
    rModelPath: string = '/app/ml_artifacts/r_model/model.joblib'
  ) {
    this.entryModelPath = entryModelPath;
    this.rModelPath = rModelPath;
  }
  
  /**
   * Check if models are available
   */
  async checkModels(): Promise<boolean> {
    try {
      const { stdout } = await execAsync(`python3 -c "import joblib; joblib.load('${this.entryModelPath}'); joblib.load('${this.rModelPath}'); print('ok')"`);
      this.modelsLoaded = stdout.trim() === 'ok';
      return this.modelsLoaded;
    } catch (err) {
      console.warn('[MLInference] Models not loaded:', err);
      return false;
    }
  }
  
  /**
   * Predict entry probability and expected R
   */
  async predict(features: MLFeatures): Promise<MLPrediction> {
    // Build feature array in correct order
    const featureArray = FEATURES.map(f => (features as any)[f] ?? 0);
    
    // Create Python inference script inline
    const script = `
import sys
import json
import joblib
import numpy as np

features = ${JSON.stringify(featureArray)}
X = np.array([features])

entry_model = joblib.load('${this.entryModelPath}')
r_model = joblib.load('${this.rModelPath}')

p_entry = float(entry_model.predict(X)[0])
r_expected = float(r_model.predict(X)[0])

# Clip values to reasonable range
p_entry = max(0.0, min(1.0, p_entry))
r_expected = max(-3.0, min(5.0, r_expected))

ev = p_entry * r_expected

print(json.dumps({
    "pEntry": round(p_entry, 4),
    "rExpected": round(r_expected, 4),
    "ev": round(ev, 4)
}))
`.trim();
    
    try {
      const { stdout, stderr } = await execAsync(`python3 -c '${script}'`, {
        timeout: 5000,
      });
      
      const result = JSON.parse(stdout.trim());
      
      return {
        pEntry: result.pEntry,
        rExpected: result.rExpected,
        ev: result.ev,
        modelId: 'lightgbm_v1',
        confidence: 0.7,
      };
    } catch (err: any) {
      console.warn('[MLInference] Prediction error, using fallback:', err.message);
      
      // Fallback to mock prediction
      return this.mockPredict(features);
    }
  }
  
  /**
   * Mock prediction (fallback when models unavailable)
   */
  mockPredict(features: MLFeatures): MLPrediction {
    // Simple heuristic based on gate_score and geometry
    const baseProb = 0.3 + features.gate_score * 0.4 + features.geom_maturity * 0.1;
    const pEntry = Math.max(0.1, Math.min(0.9, baseProb));
    
    const baseR = -0.2 + features.risk_reward * 0.3 + features.graph_boost_factor * 0.2;
    const rExpected = Math.max(-2, Math.min(3, baseR));
    
    return {
      pEntry,
      rExpected,
      ev: pEntry * rExpected,
      modelId: 'mock_v1',
      confidence: 0.3,
    };
  }
  
  /**
   * Batch predict for multiple scenarios
   */
  async predictBatch(featuresList: MLFeatures[]): Promise<MLPrediction[]> {
    // For batch, use Python with all features at once
    const featureArrays = featuresList.map(features =>
      FEATURES.map(f => (features as any)[f] ?? 0)
    );
    
    const script = `
import json
import joblib
import numpy as np

features_list = ${JSON.stringify(featureArrays)}
X = np.array(features_list)

entry_model = joblib.load('${this.entryModelPath}')
r_model = joblib.load('${this.rModelPath}')

p_entries = entry_model.predict(X)
r_expecteds = r_model.predict(X)

results = []
for i in range(len(X)):
    p_entry = max(0.0, min(1.0, float(p_entries[i])))
    r_expected = max(-3.0, min(5.0, float(r_expecteds[i])))
    ev = p_entry * r_expected
    results.append({
        "pEntry": round(p_entry, 4),
        "rExpected": round(r_expected, 4),
        "ev": round(ev, 4)
    })

print(json.dumps(results))
`.trim();
    
    try {
      const { stdout } = await execAsync(`python3 -c '${script}'`, {
        timeout: 10000,
      });
      
      const results = JSON.parse(stdout.trim());
      
      return results.map((r: any) => ({
        ...r,
        modelId: 'lightgbm_v1',
        confidence: 0.7,
      }));
    } catch (err: any) {
      console.warn('[MLInference] Batch prediction error:', err.message);
      return featuresList.map(f => this.mockPredict(f));
    }
  }
}

// Singleton instance
let inferenceService: MLInferenceService | null = null;

export function getMLInferenceService(): MLInferenceService {
  if (!inferenceService) {
    inferenceService = new MLInferenceService();
  }
  return inferenceService;
}

export function createMLInferenceService(): MLInferenceService {
  return new MLInferenceService();
}
