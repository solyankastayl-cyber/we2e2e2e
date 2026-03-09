/**
 * Chart Intelligence — System Service
 * =====================================
 * Provides MetaBrain system state for chart overlay.
 */

import type { SystemResponse } from './types.js';
import { getMongoDb } from '../../../db/mongoose.js';

/**
 * Try to fetch MetaBrain v3 state from DB
 */
async function fetchSystemFromDB(): Promise<SystemResponse | null> {
  try {
    const db = getMongoDb();

    const doc = await db.collection('ta_metabrain_v3_state')
      .findOne(
        {},
        { projection: { _id: 0 }, sort: { ts: -1 } }
      );

    if (doc) {
      return {
        analysisMode: doc.analysisMode || 'CLASSIC_TA',
        riskMode: doc.riskMode || 'NORMAL',
        metabrainState: doc.safeMode ? 'SAFE_MODE' : 'ACTIVE',
      };
    }

    return null;
  } catch {
    return null;
  }
}

/**
 * Generate mock system state
 */
function generateMockSystem(): SystemResponse {
  return {
    analysisMode: 'DEEP_MARKET',
    riskMode: 'NORMAL',
    metabrainState: 'ACTIVE',
  };
}

/**
 * Main entry point — get system state
 */
export async function getSystemState(): Promise<SystemResponse> {
  const dbResult = await fetchSystemFromDB();
  if (dbResult) return dbResult;

  return generateMockSystem();
}
