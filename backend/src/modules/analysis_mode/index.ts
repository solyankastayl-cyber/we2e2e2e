/**
 * Analysis Mode Engine
 * 
 * Controls which layers are active:
 * - CLASSIC_TA: Pure technical analysis (patterns, levels, channels)
 * - DEEP_MARKET: TA + all intelligence layers (context, state, liquidity, graph, fractal)
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { Db } from 'mongodb';

export type AnalysisMode = 'CLASSIC_TA' | 'DEEP_MARKET';

export interface AnalysisModeConfig {
  mode: AnalysisMode;
  
  // Layers enabled in each mode
  layers: {
    patterns: boolean;
    levels: boolean;
    channels: boolean;
    harmonics: boolean;
    divergences: boolean;
    context: boolean;
    marketState: boolean;
    liquidity: boolean;
    graph: boolean;
    fractal: boolean;
    physics: boolean;
  };
  
  // Scoring weights
  weights: {
    patternScore: number;
    mlScore: number;
    structureBoost: number;
    graphBoost: number;
    fractalBoost: number;
    physicsBoost: number;
    stateBoost: number;
  };
}

// Classic TA: Only traditional technical analysis
export const CLASSIC_TA_CONFIG: AnalysisModeConfig = {
  mode: 'CLASSIC_TA',
  layers: {
    patterns: true,
    levels: true,
    channels: true,
    harmonics: true,
    divergences: true,
    context: false,
    marketState: false,
    liquidity: false,
    graph: false,
    fractal: false,
    physics: false,
  },
  weights: {
    patternScore: 1.0,
    mlScore: 0.0,
    structureBoost: 1.0,  // No boost in classic
    graphBoost: 1.0,
    fractalBoost: 1.0,
    physicsBoost: 1.0,
    stateBoost: 1.0,
  },
};

// Deep Market: Full intelligence stack
export const DEEP_MARKET_CONFIG: AnalysisModeConfig = {
  mode: 'DEEP_MARKET',
  layers: {
    patterns: true,
    levels: true,
    channels: true,
    harmonics: true,
    divergences: true,
    context: true,
    marketState: true,
    liquidity: true,
    graph: true,
    fractal: true,
    physics: true,
  },
  weights: {
    patternScore: 1.0,
    mlScore: 0.15,
    structureBoost: 1.0,  // Applies full boost
    graphBoost: 1.0,
    fractalBoost: 1.0,
    physicsBoost: 1.0,
    stateBoost: 1.0,
  },
};

/**
 * Get config for mode
 */
export function getModeConfig(mode: AnalysisMode): AnalysisModeConfig {
  return mode === 'CLASSIC_TA' ? CLASSIC_TA_CONFIG : DEEP_MARKET_CONFIG;
}

/**
 * Check if layer is enabled for mode
 */
export function isLayerEnabled(mode: AnalysisMode, layer: keyof AnalysisModeConfig['layers']): boolean {
  const config = getModeConfig(mode);
  return config.layers[layer];
}

/**
 * Service for managing analysis mode
 */
export class AnalysisModeService {
  private db: Db;
  private currentMode: AnalysisMode = 'DEEP_MARKET';
  private customConfig: AnalysisModeConfig | null = null;

  constructor(db: Db) {
    this.db = db;
  }

  getMode(): AnalysisMode {
    return this.currentMode;
  }

  setMode(mode: AnalysisMode): void {
    this.currentMode = mode;
    this.customConfig = null; // Reset custom config
  }

  getConfig(): AnalysisModeConfig {
    return this.customConfig || getModeConfig(this.currentMode);
  }

  setCustomConfig(config: Partial<AnalysisModeConfig>): void {
    const base = getModeConfig(this.currentMode);
    this.customConfig = {
      ...base,
      ...config,
      layers: { ...base.layers, ...config.layers },
      weights: { ...base.weights, ...config.weights },
    };
  }

  isLayerEnabled(layer: keyof AnalysisModeConfig['layers']): boolean {
    const config = this.getConfig();
    return config.layers[layer];
  }

  /**
   * Calculate final score based on mode
   */
  calculateFinalScore(
    patternScore: number,
    mlScore: number,
    structureBoost: number,
    graphBoost: number,
    fractalBoost: number,
    physicsBoost: number,
    stateBoost: number
  ): number {
    const config = this.getConfig();
    
    if (config.mode === 'CLASSIC_TA') {
      // Classic: Only pattern score, no boosts
      return patternScore;
    }
    
    // Deep Market: Apply all boosts
    return patternScore 
      * (config.layers.context || config.layers.marketState || config.layers.liquidity ? structureBoost : 1)
      * (config.layers.graph ? graphBoost : 1)
      * (config.layers.fractal ? fractalBoost : 1)
      * (config.layers.physics ? physicsBoost : 1)
      * (config.layers.physics ? stateBoost : 1);
  }
}

/**
 * Register Analysis Mode routes
 */
export async function registerAnalysisModeRoutes(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  const service = new AnalysisModeService(db);

  // Store service on app for other modules
  (app as any).analysisModeService = service;

  /**
   * GET /mode - Get current analysis mode
   */
  app.get('/mode', async () => {
    return {
      ok: true,
      mode: service.getMode(),
      config: service.getConfig(),
    };
  });

  /**
   * POST /mode - Set analysis mode
   */
  app.post('/mode', async (
    request: FastifyRequest<{
      Body: { mode?: AnalysisMode };
    }>
  ) => {
    const body = request.body || {};
    const mode = body.mode || 'DEEP_MARKET';
    
    service.setMode(mode);
    
    return {
      ok: true,
      mode: service.getMode(),
      config: service.getConfig(),
    };
  });

  /**
   * GET /modes - List available modes
   */
  app.get('/modes', async () => {
    return {
      ok: true,
      modes: [
        {
          mode: 'CLASSIC_TA',
          description: 'Pure technical analysis (patterns, levels, channels)',
          layers: CLASSIC_TA_CONFIG.layers,
        },
        {
          mode: 'DEEP_MARKET',
          description: 'Full intelligence stack (TA + context + state + liquidity + graph + fractal)',
          layers: DEEP_MARKET_CONFIG.layers,
        },
      ],
    };
  });

  console.log('[AnalysisMode] Routes: /mode, /modes');
}

export async function registerAnalysisModeModule(
  app: FastifyInstance,
  { db }: { db: Db }
): Promise<void> {
  console.log('[AnalysisMode] Registering Analysis Mode Engine...');
  
  await app.register(async (instance) => {
    await registerAnalysisModeRoutes(instance, { db });
  }, { prefix: '/analysis_mode' });
  
  console.log('[AnalysisMode] ✅ Analysis Mode registered at /api/ta/analysis_mode/*');
}
