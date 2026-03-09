/**
 * G1 — Market Graph Storage
 * 
 * MongoDB storage for market events and transitions
 */

import { Db, Collection } from 'mongodb';
import { MarketEvent, EventTransition, MarketEventType } from './market_graph.types.js';

const EVENTS_COLLECTION = 'ta_market_events';
const TRANSITIONS_COLLECTION = 'ta_market_transitions';

export class MarketGraphStorage {
  private db: Db;
  private events: Collection;
  private transitions: Collection;

  constructor(db: Db) {
    this.db = db;
    this.events = db.collection(EVENTS_COLLECTION);
    this.transitions = db.collection(TRANSITIONS_COLLECTION);
  }

  async ensureIndexes(): Promise<void> {
    // Events indexes
    await this.events.createIndex({ runId: 1 });
    await this.events.createIndex({ asset: 1, timeframe: 1, ts: 1 });
    await this.events.createIndex({ type: 1 });
    await this.events.createIndex({ patternType: 1 });
    
    // Transitions indexes
    await this.transitions.createIndex({ from: 1, to: 1 });
    await this.transitions.createIndex({ fromPattern: 1 });
    await this.transitions.createIndex({ probability: -1 });
    
    console.log('[MarketGraph] Indexes ensured');
  }

  // ═══════════════════════════════════════════════════════════════
  // Events
  // ═══════════════════════════════════════════════════════════════

  async saveEvents(events: MarketEvent[]): Promise<number> {
    if (events.length === 0) return 0;
    
    // Use upsert to avoid duplicates
    let written = 0;
    for (const event of events) {
      const result = await this.events.updateOne(
        { 
          asset: event.asset, 
          timeframe: event.timeframe,
          ts: event.ts,
          type: event.type,
          patternType: event.patternType,
        },
        { $set: event },
        { upsert: true }
      );
      if (result.upsertedCount > 0) written++;
    }
    
    return written;
  }

  async getEvents(
    asset: string,
    timeframe: string,
    limit: number = 200
  ): Promise<MarketEvent[]> {
    const docs = await this.events
      .find({ asset, timeframe })
      .sort({ ts: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...event } = doc as any;
      return event;
    }).reverse();
  }

  async getRecentEvents(
    asset: string,
    timeframe: string,
    barsBack: number = 50
  ): Promise<MarketEvent[]> {
    // Get last N events
    const docs = await this.events
      .find({ asset, timeframe })
      .sort({ ts: -1 })
      .limit(barsBack)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...event } = doc as any;
      return event;
    }).reverse();
  }

  async getEventsByType(
    type: MarketEventType,
    limit: number = 100
  ): Promise<MarketEvent[]> {
    const docs = await this.events
      .find({ type })
      .sort({ ts: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...event } = doc as any;
      return event;
    });
  }

  async countEvents(): Promise<number> {
    return this.events.countDocuments();
  }

  async getEventStats(): Promise<Record<MarketEventType, number>> {
    const pipeline = [
      { $group: { _id: '$type', count: { $sum: 1 } } },
    ];
    
    const results = await this.events.aggregate(pipeline).toArray();
    const stats: Record<string, number> = {};
    
    for (const r of results) {
      stats[r._id] = r.count;
    }
    
    return stats as Record<MarketEventType, number>;
  }

  // ═══════════════════════════════════════════════════════════════
  // Transitions
  // ═══════════════════════════════════════════════════════════════

  async saveTransitions(transitions: EventTransition[]): Promise<number> {
    if (transitions.length === 0) return 0;
    
    let written = 0;
    for (const transition of transitions) {
      const result = await this.transitions.updateOne(
        { from: transition.from, to: transition.to, fromPattern: transition.fromPattern },
        { $set: transition },
        { upsert: true }
      );
      if (result.upsertedCount > 0 || result.modifiedCount > 0) written++;
    }
    
    return written;
  }

  async getTransitions(limit: number = 100): Promise<EventTransition[]> {
    const docs = await this.transitions
      .find({})
      .sort({ probability: -1 })
      .limit(limit)
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...transition } = doc as any;
      return transition;
    });
  }

  async getTransitionsFrom(from: MarketEventType): Promise<EventTransition[]> {
    const docs = await this.transitions
      .find({ from })
      .sort({ probability: -1 })
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...transition } = doc as any;
      return transition;
    });
  }

  async getTransitionsTo(to: MarketEventType): Promise<EventTransition[]> {
    const docs = await this.transitions
      .find({ to })
      .sort({ probability: -1 })
      .toArray();
    
    return docs.map(doc => {
      const { _id, ...transition } = doc as any;
      return transition;
    });
  }

  async getTransition(from: MarketEventType, to: MarketEventType): Promise<EventTransition | null> {
    const doc = await this.transitions.findOne({ from, to });
    if (!doc) return null;
    
    const { _id, ...transition } = doc as any;
    return transition;
  }

  async countTransitions(): Promise<number> {
    return this.transitions.countDocuments();
  }

  // ═══════════════════════════════════════════════════════════════
  // Cleanup
  // ═══════════════════════════════════════════════════════════════

  async clearEvents(asset?: string, timeframe?: string): Promise<number> {
    const query: any = {};
    if (asset) query.asset = asset;
    if (timeframe) query.timeframe = timeframe;
    
    const result = await this.events.deleteMany(query);
    return result.deletedCount;
  }

  async clearTransitions(): Promise<number> {
    const result = await this.transitions.deleteMany({});
    return result.deletedCount;
  }
}
