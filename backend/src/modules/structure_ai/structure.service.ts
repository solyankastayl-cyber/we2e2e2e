/**
 * Phase 7 — Market Structure AI: Service
 * 
 * Main service for structure analysis
 */

import { Db } from 'mongodb';
import {
  MarketEvent,
  StructureState,
  StructureInput,
  StructureAIConfig,
  DEFAULT_STRUCTURE_CONFIG,
  EventDirection
} from './structure.types.js';
import { detectAllEvents } from './structure.detector.js';
import { 
  buildEventChain, 
  determineStructureType, 
  generateNarrative,
  getExpectedNextEvents 
} from './structure.chain.js';

export interface StructureAIService {
  /**
   * Analyze structure and return full state
   */
  analyze(symbol: string, timeframe: string, input?: Partial<StructureInput>): Promise<StructureState>;
  
  /**
   * Get current events
   */
  getEvents(symbol: string, timeframe: string): Promise<MarketEvent[]>;
  
  /**
   * Get structure narrative
   */
  getNarrative(symbol: string, timeframe: string): Promise<string>;
  
  /**
   * Health check
   */
  health(): { enabled: boolean; version: string };
}

/**
 * Create mock structure input for testing
 */
function createMockInput(symbol: string, timeframe: string): StructureInput {
  // Generate realistic mock data
  const random = Math.random();
  const trend = random > 0.6 ? 'TREND_UP' : random < 0.3 ? 'TREND_DOWN' : 'RANGE';
  
  return {
    symbol,
    timeframe,
    rsi: {
      value: 45 + Math.random() * 25,  // 45-70
      divergence: Math.random() > 0.7 ? (Math.random() > 0.5 ? 'BULL' : 'BEAR') : null
    },
    macd: {
      histogram: (Math.random() - 0.5) * 100,
      signal: (Math.random() - 0.5) * 50,
      crossover: Math.random() > 0.7 ? (Math.random() > 0.5 ? 'BULL' : 'BEAR') : null
    },
    volume: {
      current: 1000000 + Math.random() * 500000,
      average: 1000000,
      spike: Math.random() > 0.6
    },
    atr: {
      value: 100 + Math.random() * 50,
      percentile: Math.random() * 100
    },
    equalHighs: Math.random() > 0.7,
    equalLows: Math.random() > 0.7,
    higherHigh: trend === 'TREND_UP',
    higherLow: trend === 'TREND_UP' || Math.random() > 0.5,
    lowerHigh: trend === 'TREND_DOWN' || Math.random() > 0.5,
    lowerLow: trend === 'TREND_DOWN',
    liquidityCluster: Math.random() > 0.5 ? {
      price: 50000 + Math.random() * 10000,
      strength: Math.random(),
      swept: Math.random() > 0.6
    } : undefined,
    liquiditySweep: Math.random() > 0.6 ? {
      direction: Math.random() > 0.5 ? 'UP' : 'DOWN',
      price: 50000 + Math.random() * 10000
    } : undefined,
    compression: Math.random() > 0.5,
    compressionCandles: Math.random() > 0.5 ? Math.floor(5 + Math.random() * 10) : undefined,
    breakout: Math.random() > 0.6 ? {
      direction: Math.random() > 0.5 ? 'UP' : 'DOWN',
      confirmed: Math.random() > 0.4
    } : undefined,
    regime: trend as any,
    volRegime: Math.random() > 0.6 ? 'HIGH' : Math.random() > 0.3 ? 'NORMAL' : 'LOW'
  };
}

/**
 * Create Structure AI Service
 */
export function createStructureAIService(
  db: Db,
  config: StructureAIConfig = DEFAULT_STRUCTURE_CONFIG
): StructureAIService {
  // Collection for caching structure states
  const structureCol = db.collection('structure_states');
  const eventsCol = db.collection('structure_events');
  
  return {
    async analyze(
      symbol: string, 
      timeframe: string, 
      input?: Partial<StructureInput>
    ): Promise<StructureState> {
      // Build full input (use mock if not provided)
      const fullInput: StructureInput = {
        ...createMockInput(symbol, timeframe),
        ...input
      };
      
      // Detect events
      const events = detectAllEvents(fullInput);
      
      // Build event chain
      const chain = buildEventChain(events);
      
      // Determine structure type
      const structureType = determineStructureType(events);
      
      // Get expected next events
      let expectedNext: any[] = [];
      let expectedProbability = 0;
      
      if (chain && chain.expected.length > 0) {
        expectedNext = chain.expected.slice(0, 2);
        expectedProbability = chain.probability;
      } else if (events.length > 0) {
        const lastEvent = events[0];
        const nextEvents = getExpectedNextEvents(lastEvent.type);
        expectedNext = nextEvents.slice(0, 2).map(e => e.event);
        expectedProbability = nextEvents[0]?.probability || 0;
      }
      
      // Generate narrative
      const narrative = generateNarrative(events, chain, structureType);
      
      // Determine bias
      let bias: EventDirection = 'NEUTRAL';
      if (chain) {
        bias = chain.direction;
      } else if (events.length > 0) {
        const directionalEvent = events.find(e => e.direction !== 'NEUTRAL');
        if (directionalEvent) bias = directionalEvent.direction;
      }
      
      // Determine momentum
      let momentum: 'STRONG' | 'MODERATE' | 'WEAK' = 'MODERATE';
      if (events.length > 0) {
        const avgStrength = events.reduce((sum, e) => sum + e.strength, 0) / events.length;
        if (avgStrength > 0.7) momentum = 'STRONG';
        else if (avgStrength < 0.4) momentum = 'WEAK';
      }
      
      const state: StructureState = {
        symbol,
        timeframe,
        structure: structureType,
        structureConfidence: chain ? chain.probability : (events[0]?.confidence || 0.5),
        currentEvents: events,
        activeChain: chain || undefined,
        expectedNext,
        expectedProbability,
        bias,
        momentum,
        narrative,
        computedAt: Date.now()
      };
      
      // Cache the state
      await structureCol.updateOne(
        { symbol, timeframe },
        { $set: { ...state, updatedAt: new Date() } },
        { upsert: true }
      );
      
      // Store events
      if (events.length > 0) {
        await eventsCol.insertMany(
          events.map(e => ({ ...e, symbol, timeframe, storedAt: new Date() }))
        ).catch(() => {}); // Ignore duplicate errors
      }
      
      return state;
    },
    
    async getEvents(symbol: string, timeframe: string): Promise<MarketEvent[]> {
      // Get recent events from cache
      const cached = await eventsCol
        .find({ symbol, timeframe })
        .sort({ timestamp: -1 })
        .limit(20)
        .project({ _id: 0 })
        .toArray();
      
      if (cached.length > 0) {
        return cached as MarketEvent[];
      }
      
      // Generate new events
      const state = await this.analyze(symbol, timeframe);
      return state.currentEvents;
    },
    
    async getNarrative(symbol: string, timeframe: string): Promise<string> {
      const state = await this.analyze(symbol, timeframe);
      return state.narrative;
    },
    
    health(): { enabled: boolean; version: string } {
      return {
        enabled: config.enabled,
        version: 'structure_ai_phase7'
      };
    }
  };
}

// Singleton instance
let structureServiceInstance: StructureAIService | null = null;

/**
 * Get or create Structure AI service instance
 */
export function getStructureAIService(db: Db, config?: StructureAIConfig): StructureAIService {
  if (!structureServiceInstance) {
    structureServiceInstance = createStructureAIService(db, config);
  }
  return structureServiceInstance;
}
