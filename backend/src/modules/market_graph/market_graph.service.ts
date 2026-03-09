/**
 * G1 + G2 + G3 — Market Graph Service
 * 
 * Main service for market structure graph:
 * - Event extraction and storage
 * - Transition computation
 * - Graph scoring
 * - Path forecasting
 */

import { Db } from 'mongodb';
import { 
  MarketEvent, 
  EventTransition, 
  GraphStats, 
  GraphBoostResult,
  MarketEventType,
} from './market_graph.types.js';
import { MarketEventExtractor } from './market_graph.extractor.js';
import { MarketGraphStorage } from './market_graph.storage.js';
import { 
  computeTransitions, 
  predictNextEvents, 
  findBestPath,
  computeChainScore,
} from './market_graph.transitions.js';

export class MarketGraphService {
  private db: Db;
  private extractor: MarketEventExtractor;
  private storage: MarketGraphStorage;

  constructor(db: Db) {
    this.db = db;
    this.extractor = new MarketEventExtractor(db);
    this.storage = new MarketGraphStorage(db);
  }

  async ensureIndexes(): Promise<void> {
    await this.storage.ensureIndexes();
  }

  // ═══════════════════════════════════════════════════════════════
  // G1: Event Extraction & Storage
  // ═══════════════════════════════════════════════════════════════

  /**
   * Rebuild graph for asset/timeframe
   */
  async rebuild(
    asset: string,
    timeframe: string,
    startTs?: number,
    endTs?: number
  ): Promise<{
    eventsExtracted: number;
    eventsSaved: number;
    transitionsComputed: number;
  }> {
    // 1. Extract events
    const events = await this.extractor.extractEvents(asset, timeframe, startTs, endTs);
    
    // 2. Save events
    const eventsSaved = await this.storage.saveEvents(events);
    
    // 3. Compute transitions
    const { transitions } = computeTransitions(events);
    
    // 4. Save transitions
    const transitionsComputed = await this.storage.saveTransitions(transitions);
    
    return {
      eventsExtracted: events.length,
      eventsSaved,
      transitionsComputed,
    };
  }

  /**
   * Get events for asset/timeframe
   */
  async getEvents(
    asset: string,
    timeframe: string,
    limit: number = 200
  ): Promise<MarketEvent[]> {
    return this.storage.getEvents(asset, timeframe, limit);
  }

  /**
   * Get transitions
   */
  async getTransitions(limit: number = 100): Promise<EventTransition[]> {
    return this.storage.getTransitions(limit);
  }

  /**
   * Get graph statistics
   */
  async getStats(): Promise<GraphStats> {
    const totalEvents = await this.storage.countEvents();
    const eventsByType = await this.storage.getEventStats();
    const transitionsCount = await this.storage.countTransitions();
    const topTransitions = await this.storage.getTransitions(10);
    
    return {
      totalEvents,
      eventsByType,
      transitionsCount,
      topTransitions,
      avgChainLength: 0, // Would need more complex calculation
      winningChains: 0,
      losingChains: 0,
    };
  }

  // ═══════════════════════════════════════════════════════════════
  // G2: Graph Scoring
  // ═══════════════════════════════════════════════════════════════

  /**
   * Compute graph boost for current market state
   */
  async computeBoost(
    asset: string,
    timeframe: string,
    currentPattern?: string,
    currentDirection?: 'BULL' | 'BEAR'
  ): Promise<GraphBoostResult> {
    // Get recent events
    const recentEvents = await this.storage.getRecentEvents(asset, timeframe, 20);
    const transitions = await this.storage.getTransitions(200);
    
    // Compute chain score
    const { score, confidence, matchedTransitions } = computeChainScore(recentEvents, transitions);
    
    // Get last event type
    const lastEvent = recentEvents.length > 0 ? recentEvents[recentEvents.length - 1] : null;
    const lastType = lastEvent?.type || 'PATTERN_DETECTED';
    
    // Predict next events
    const predictedNext = predictNextEvents(lastType, currentPattern, transitions, 5);
    
    // Find best path
    const { path: bestPath, probability: pathProb } = findBestPath(lastType, transitions, 5);
    
    // Compute boost
    // Score > 0.5 means chain is historically successful
    // Convert to boost multiplier: 0.8 - 1.3
    const boost = 0.8 + score * 0.5;
    const clampedBoost = Math.min(1.3, Math.max(0.8, boost));
    
    return {
      score,
      confidence,
      boost: clampedBoost,
      currentChain: recentEvents,
      matchedTransitions: transitions.filter(t => 
        recentEvents.some(e => e.type === t.from) &&
        recentEvents.some(e => e.type === t.to)
      ),
      predictedNext,
      bestPath,
    };
  }

  // ═══════════════════════════════════════════════════════════════
  // G3: Path Forecasting
  // ═══════════════════════════════════════════════════════════════

  /**
   * Forecast next events in market sequence
   */
  async forecast(
    asset: string,
    timeframe: string,
    topN: number = 5
  ): Promise<{
    currentChain: MarketEvent[];
    predictedNext: Array<{ event: MarketEventType; probability: number; avgBarsAhead: number }>;
    bestPath: MarketEventType[];
    pathProbability: number;
  }> {
    const recentEvents = await this.storage.getRecentEvents(asset, timeframe, 10);
    const transitions = await this.storage.getTransitions(200);
    
    const lastEvent = recentEvents.length > 0 ? recentEvents[recentEvents.length - 1] : null;
    const lastType = lastEvent?.type || 'PATTERN_DETECTED';
    
    const predictedNext = predictNextEvents(lastType, lastEvent?.patternType, transitions, topN);
    const { path: bestPath, probability: pathProbability } = findBestPath(lastType, transitions, 5);
    
    return {
      currentChain: recentEvents,
      predictedNext,
      bestPath,
      pathProbability,
    };
  }

  /**
   * Get transition from specific event type
   */
  async getTransitionsFrom(from: MarketEventType): Promise<EventTransition[]> {
    return this.storage.getTransitionsFrom(from);
  }
}
