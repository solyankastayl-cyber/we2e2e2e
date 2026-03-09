/**
 * Phase 7.8-7.9: Archive MongoDB Storage
 */

import { Collection, Db } from "mongodb";
import { ArchiveCandle } from "./archive.types.js";

export interface CandleDoc extends ArchiveCandle {
  symbol: string;
  interval: string;
  source: "binance_archive";
  key: string;
  ingestedAt: number;
}

export class BinanceArchiveMongo {
  private col: Collection<CandleDoc>;

  constructor(db: Db) {
    this.col = db.collection<CandleDoc>("candles_binance");
  }

  async ensureIndexes(): Promise<void> {
    await this.col.createIndex(
      { symbol: 1, interval: 1, openTime: 1 },
      { unique: true }
    );
    await this.col.createIndex({ symbol: 1, interval: 1, closeTime: 1 });
    await this.col.createIndex({ ingestedAt: 1 });
    console.log("[Archive Mongo] Indexes ensured");
  }

  async upsertBatch(
    symbol: string,
    interval: string,
    rows: ArchiveCandle[]
  ): Promise<number> {
    if (!rows.length) return 0;

    const now = Date.now();
    const ops = rows.map((r) => ({
      updateOne: {
        filter: { symbol, interval, openTime: r.openTime },
        update: {
          $set: {
            ...r,
            symbol,
            interval,
            source: "binance_archive" as const,
            key: `${symbol}:${interval}:${r.openTime}`,
            ingestedAt: now,
          },
        },
        upsert: true,
      },
    }));

    // Process in batches
    const batchSize = 1000;
    let total = 0;

    for (let i = 0; i < ops.length; i += batchSize) {
      const batch = ops.slice(i, i + batchSize);
      const res = await this.col.bulkWrite(batch, { ordered: false });
      total += (res.upsertedCount ?? 0) + (res.modifiedCount ?? 0);
    }

    return total;
  }

  async getCount(symbol?: string, interval?: string): Promise<number> {
    const filter: any = {};
    if (symbol) filter.symbol = symbol;
    if (interval) filter.interval = interval;
    return this.col.countDocuments(filter);
  }

  async clearMockData(): Promise<number> {
    // Clear only mock data, keep archive data
    const res = await this.col.deleteMany({ source: { $ne: "binance_archive" } });
    return res.deletedCount ?? 0;
  }
}
