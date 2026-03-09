/**
 * Intelligence Health Check (P4.1)
 */

import { Db } from 'mongodb';
import type { IntelligenceHealth } from './intelligence.types.js';

export class IntelligenceHealthChecker {
  private db: Db;

  constructor(db: Db) {
    this.db = db;
  }

  async check(): Promise<IntelligenceHealth> {
    const checks = {
      mongo: false,
      decisionEngine: false,
      modelRegistry: false,
      calibration: false,
      stability: false
    };
    
    try {
      // MongoDB
      await this.db.command({ ping: 1 });
      checks.mongo = true;
      
      // Decision engine (check if ta_runs collection exists)
      const runsCount = await this.db.collection('ta_runs').countDocuments();
      checks.decisionEngine = true;
      
      // Model registry
      const modelsCount = await this.db.collection('ta_model_registry').countDocuments();
      checks.modelRegistry = true;
      
      // Stability (check pattern stats)
      const statsCount = await this.db.collection('ta_pattern_stats').countDocuments();
      checks.stability = true;
      
      // Calibration (check if scenario cache exists)
      const cacheCount = await this.db.collection('ta_scenario_cache').countDocuments();
      checks.calibration = cacheCount > 0;
      
    } catch (e) {
      // Partial failure
    }
    
    const allPassing = Object.values(checks).every(v => v);
    const somePassing = Object.values(checks).some(v => v);
    
    return {
      status: allPassing ? 'OK' : somePassing ? 'DEGRADED' : 'ERROR',
      checks,
      message: allPassing ? undefined : 'Some components are degraded'
    };
  }
}

export function getIntelligenceHealthChecker(db: Db): IntelligenceHealthChecker {
  return new IntelligenceHealthChecker(db);
}
