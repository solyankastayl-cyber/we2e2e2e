/**
 * Phase 7.5: Binance Candle Storage
 * MongoDB storage with idempotent upsert
 */

import { Collection, Db } from "mongodb";
import { Candle, CandleDoc, BinanceInterval, CoverageInfo } from "./binance.types.js";

export class BinanceCandleStorage {
  private col: Collection<CandleDoc>;

  constructor(private db: Db) {
    this.col = db.collection<CandleDoc>("candles_binance");
  }

  async ensureIndexes(): Promise<void> {
    await this.col.createIndex(
      { symbol: 1, interval: 1, openTime: 1 },
      { unique: true }
    );
    await this.col.createIndex({ symbol: 1, interval: 1, closeTime: 1 });
    await this.col.createIndex({ ingestedAt: 1 });
    console.log("[Binance Storage] Indexes ensured");
  }

  private toDoc(symbol: string, interval: BinanceInterval, c: Candle): CandleDoc {
    return {
      ...c,
      symbol,
      interval,
      source: "binance_spot",
      key: `${symbol}:${interval}:${c.openTime}`,
      ingestedAt: Date.now(),
    };
  }

  async upsertMany(symbol: string, interval: BinanceInterval, candles: Candle[]): Promise<number> {
    if (candles.length === 0) return 0;

    const ops = candles.map((c) => ({
      updateOne: {
        filter: { symbol, interval, openTime: c.openTime },
        update: { $set: this.toDoc(symbol, interval, c) },
        upsert: true,
      },
    }));

    // Process in batches to avoid memory issues
    const batchSize = 1000;
    let totalUpserted = 0;

    for (let i = 0; i < ops.length; i += batchSize) {
      const batch = ops.slice(i, i + batchSize);
      const res = await this.col.bulkWrite(batch, { ordered: false });
      totalUpserted += (res.upsertedCount ?? 0) + (res.modifiedCount ?? 0);
    }

    return totalUpserted;
  }

  async getCoverage(symbol: string, interval: BinanceInterval): Promise<CoverageInfo> {
    const count = await this.col.countDocuments({ symbol, interval });

    const first = await this.col
      .find({ symbol, interval })
      .sort({ openTime: 1 })
      .limit(1)
      .toArray();

    const last = await this.col
      .find({ symbol, interval })
      .sort({ openTime: -1 })
      .limit(1)
      .toArray();

    const earliest = first[0]?.openTime ?? null;
    const latest = last[0]?.openTime ?? null;

    let gapDays: number | undefined;
    if (earliest && latest) {
      gapDays = Math.round((latest - earliest) / (24 * 60 * 60 * 1000));
    }

    return { symbol, interval, count, earliest, latest, gapDays };
  }

  async getAllCoverage(): Promise<CoverageInfo[]> {
    const pipeline = [
      {
        $group: {
          _id: { symbol: "$symbol", interval: "$interval" },
          count: { $sum: 1 },
          earliest: { $min: "$openTime" },
          latest: { $max: "$openTime" },
        },
      },
      {
        $project: {
          _id: 0,
          symbol: "$_id.symbol",
          interval: "$_id.interval",
          count: 1,
          earliest: 1,
          latest: 1,
        },
      },
      { $sort: { symbol: 1, interval: 1 } },
    ];

    const results = await this.col.aggregate<CoverageInfo>(pipeline).toArray();
    return results.map((r) => ({
      ...r,
      gapDays: r.earliest && r.latest
        ? Math.round((r.latest - r.earliest) / (24 * 60 * 60 * 1000))
        : undefined,
    }));
  }

  async getCandles(
    symbol: string,
    interval: BinanceInterval,
    startTime: number,
    endTime: number
  ): Promise<Candle[]> {
    const docs = await this.col
      .find({
        symbol,
        interval,
        openTime: { $gte: startTime, $lt: endTime },
      })
      .sort({ openTime: 1 })
      .toArray();

    // Strip MongoDB fields
    return docs.map((d) => ({
      openTime: d.openTime,
      closeTime: d.closeTime,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
      volume: d.volume,
      quoteVolume: d.quoteVolume,
      trades: d.trades,
      takerBuyBaseVolume: d.takerBuyBaseVolume,
      takerBuyQuoteVolume: d.takerBuyQuoteVolume,
    }));
  }

  async getLatestCandle(symbol: string, interval: BinanceInterval): Promise<Candle | null> {
    const docs = await this.col
      .find({ symbol, interval })
      .sort({ openTime: -1 })
      .limit(1)
      .toArray();

    if (docs.length === 0) return null;

    const d = docs[0];
    return {
      openTime: d.openTime,
      closeTime: d.closeTime,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
      volume: d.volume,
      quoteVolume: d.quoteVolume,
      trades: d.trades,
      takerBuyBaseVolume: d.takerBuyBaseVolume,
      takerBuyQuoteVolume: d.takerBuyQuoteVolume,
    };
  }

  async deleteAll(symbol?: string, interval?: BinanceInterval): Promise<number> {
    const filter: any = {};
    if (symbol) filter.symbol = symbol;
    if (interval) filter.interval = interval;

    const res = await this.col.deleteMany(filter);
    return res.deletedCount ?? 0;
  }
}
