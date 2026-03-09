/**
 * G1 — Market Event Extractor
 * 
 * Extracts market events from existing TA data:
 * - Pattern detections
 * - Liquidity sweeps
 * - Breakouts/breakdowns
 * - Retests
 * - Outcomes (target hit, stop hit)
 */

import { Db } from 'mongodb';
import { MarketEvent, MarketEventType } from './market_graph.types.js';
import { v4 as uuidv4 } from 'uuid';

export class MarketEventExtractor {
  private db: Db;

  constructor(db: Db) {
    this.db = db;
  }

  /**
   * Extract all events for a run/asset/timeframe
   */
  async extractEvents(
    asset: string,
    timeframe: string,
    startTs?: number,
    endTs?: number
  ): Promise<MarketEvent[]> {
    const events: MarketEvent[] = [];
    const runId = `${asset}_${timeframe}_${Date.now()}`;
    
    // 1. Extract pattern events
    const patternEvents = await this.extractPatternEvents(asset, timeframe, startTs, endTs);
    events.push(...patternEvents.map(e => ({ ...e, runId })));
    
    // 2. Extract liquidity events
    const liquidityEvents = await this.extractLiquidityEvents(asset, timeframe, startTs, endTs);
    events.push(...liquidityEvents.map(e => ({ ...e, runId })));
    
    // 3. Extract outcome events (from backtest trades)
    const outcomeEvents = await this.extractOutcomeEvents(asset, timeframe, startTs, endTs);
    events.push(...outcomeEvents.map(e => ({ ...e, runId })));
    
    // 4. Extract structure events (breakouts, retests)
    const structureEvents = await this.extractStructureEvents(asset, timeframe, startTs, endTs);
    events.push(...structureEvents.map(e => ({ ...e, runId })));
    
    // Sort by timestamp
    events.sort((a, b) => a.ts - b.ts);
    
    return events;
  }

  /**
   * Extract pattern detection events
   */
  private async extractPatternEvents(
    asset: string,
    timeframe: string,
    startTs?: number,
    endTs?: number
  ): Promise<Omit<MarketEvent, 'runId'>[]> {
    const events: Omit<MarketEvent, 'runId'>[] = [];
    
    const query: any = { asset, timeframe };
    if (startTs || endTs) {
      query.ts = {};
      if (startTs) query.ts.$gte = startTs;
      if (endTs) query.ts.$lte = endTs;
    }
    
    // Try ta_patterns collection
    const patterns = await this.db.collection('ta_patterns')
      .find(query)
      .sort({ ts: 1 })
      .limit(1000)
      .toArray();
    
    for (const p of patterns) {
      events.push({
        id: uuidv4(),
        asset,
        timeframe,
        ts: p.ts || p.openTime || Date.now(),
        barIndex: p.barIndex || 0,
        type: 'PATTERN_DETECTED',
        direction: p.direction === 'LONG' || p.direction === 'BULL' ? 'BULL' : 
                  p.direction === 'SHORT' || p.direction === 'BEAR' ? 'BEAR' : 'NEUTRAL',
        patternType: p.type || p.patternType,
        patternId: p.patternId || p._id?.toString(),
        price: p.price || p.entry,
        strength: p.score || p.confidence || 0.5,
        confidence: p.confidence || p.score || 0.5,
        meta: { source: 'ta_patterns' },
        createdAt: new Date(),
      });
    }
    
    return events;
  }

  /**
   * Extract liquidity sweep events
   */
  private async extractLiquidityEvents(
    asset: string,
    timeframe: string,
    startTs?: number,
    endTs?: number
  ): Promise<Omit<MarketEvent, 'runId'>[]> {
    const events: Omit<MarketEvent, 'runId'>[] = [];
    
    // Try to fetch from liquidity API
    try {
      const response = await fetch(
        `http://localhost:8001/api/ta/liquidity/sweeps?asset=${asset}&tf=${timeframe}`
      );
      
      if (response.ok) {
        const data = await response.json();
        const sweeps = data.sweeps || [];
        
        for (const s of sweeps) {
          // Filter by time range if provided
          if (startTs && s.timestamp < startTs) continue;
          if (endTs && s.timestamp > endTs) continue;
          
          events.push({
            id: uuidv4(),
            asset,
            timeframe,
            ts: s.timestamp,
            barIndex: s.candleIndex || 0,
            type: s.type === 'SWEEP_UP' ? 'LIQUIDITY_SWEEP_UP' : 'LIQUIDITY_SWEEP_DOWN',
            direction: s.type === 'SWEEP_UP' ? 'BEAR' : 'BULL', // Sweep up is bearish signal
            price: s.zonePrice,
            priceHigh: s.wickHigh,
            priceLow: s.wickLow,
            strength: s.recovered ? 0.8 : 0.5,
            confidence: s.recovered ? 0.8 : 0.5,
            meta: { 
              source: 'liquidity_engine',
              magnitude: s.magnitude,
              recovered: s.recovered,
            },
            createdAt: new Date(),
          });
        }
      }
    } catch (e) {
      // Ignore errors
    }
    
    return events;
  }

  /**
   * Extract outcome events from backtest trades
   */
  private async extractOutcomeEvents(
    asset: string,
    timeframe: string,
    startTs?: number,
    endTs?: number
  ): Promise<Omit<MarketEvent, 'runId'>[]> {
    const events: Omit<MarketEvent, 'runId'>[] = [];
    
    const query: any = { asset, timeframe };
    if (startTs || endTs) {
      query.entryTs = {};
      if (startTs) query.entryTs.$gte = startTs;
      if (endTs) query.entryTs.$lte = endTs;
    }
    
    const trades = await this.db.collection('ta_backtest_trades')
      .find(query)
      .sort({ entryTs: 1 })
      .limit(500)
      .toArray();
    
    for (const t of trades) {
      // Exit event
      if (t.exitTs && t.exitType) {
        let eventType: MarketEventType = 'FAILURE';
        
        if (t.exitType === 'T1' || t.exitType === 'T2' || t.exitType === 'TARGET') {
          eventType = 'TARGET_HIT';
        } else if (t.exitType === 'STOP') {
          eventType = 'STOP_HIT';
        }
        
        events.push({
          id: uuidv4(),
          asset,
          timeframe,
          ts: t.exitTs,
          barIndex: t.exitBarIndex || 0,
          type: eventType,
          direction: t.direction === 'LONG' ? 'BULL' : 'BEAR',
          patternType: t.patternType,
          price: t.exitPrice,
          strength: Math.abs(t.rMultiple || 0),
          confidence: 1,
          meta: { 
            source: 'ta_backtest_trades',
            tradeId: t._id?.toString(),
            rMultiple: t.rMultiple,
            exitType: t.exitType,
          },
          createdAt: new Date(),
        });
      }
    }
    
    return events;
  }

  /**
   * Extract structure events (breakouts, retests)
   * Using market state and context data
   */
  private async extractStructureEvents(
    asset: string,
    timeframe: string,
    startTs?: number,
    endTs?: number
  ): Promise<Omit<MarketEvent, 'runId'>[]> {
    const events: Omit<MarketEvent, 'runId'>[] = [];
    
    // Try to fetch context for structure events
    try {
      const response = await fetch(
        `http://localhost:8001/api/ta/context/analyze?asset=${asset}&tf=${timeframe}`
      );
      
      if (response.ok) {
        const data = await response.json();
        
        // Check for breakout
        if (data.structure?.breakingUp) {
          events.push({
            id: uuidv4(),
            asset,
            timeframe,
            ts: Date.now(),
            barIndex: 0,
            type: 'BREAKOUT',
            direction: 'BULL',
            strength: 0.7,
            confidence: 0.7,
            meta: { source: 'context_engine' },
            createdAt: new Date(),
          });
        } else if (data.structure?.breakingDown) {
          events.push({
            id: uuidv4(),
            asset,
            timeframe,
            ts: Date.now(),
            barIndex: 0,
            type: 'BREAKDOWN',
            direction: 'BEAR',
            strength: 0.7,
            confidence: 0.7,
            meta: { source: 'context_engine' },
            createdAt: new Date(),
          });
        }
        
        // Check for compression
        if (data.volatility?.compressing) {
          events.push({
            id: uuidv4(),
            asset,
            timeframe,
            ts: Date.now(),
            barIndex: 0,
            type: 'COMPRESSION',
            direction: 'NEUTRAL',
            strength: 0.6,
            confidence: 0.6,
            meta: { source: 'context_engine' },
            createdAt: new Date(),
          });
        }
        
        // Check for expansion
        if (data.volatility?.expanding) {
          events.push({
            id: uuidv4(),
            asset,
            timeframe,
            ts: Date.now(),
            barIndex: 0,
            type: 'EXPANSION',
            direction: data.trend?.direction === 'UP' ? 'BULL' : 
                      data.trend?.direction === 'DOWN' ? 'BEAR' : 'NEUTRAL',
            strength: 0.7,
            confidence: 0.7,
            meta: { source: 'context_engine' },
            createdAt: new Date(),
          });
        }
      }
    } catch (e) {
      // Ignore errors
    }
    
    return events;
  }
}
