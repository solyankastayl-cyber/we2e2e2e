/**
 * Phase 7.8-7.9: Archive API Routes
 */

import { FastifyInstance } from "fastify";
import { Db } from "mongodb";
import { BinanceArchiveMongo } from "./archive.mongo.js";
import { BinanceArchiveParallelLoader } from "./archive.parallel.js";
import { monthsBetween } from "./archive.utils.js";

// Default assets
const DEFAULT_SYMBOLS = [
  "BTCUSDT",
  "ETHUSDT",
  "BNBUSDT",
  "SOLUSDT",
  "XRPUSDT",
  "DOGEUSDT",
];
const DEFAULT_INTERVALS = ["1h", "4h", "1d"];

export async function registerBinanceArchiveRoutes(
  app: FastifyInstance,
  deps: { mongoDb: Db }
) {
  const mongo = new BinanceArchiveMongo(deps.mongoDb);
  await mongo.ensureIndexes();

  const loader = new BinanceArchiveParallelLoader(mongo);

  /**
   * Load historical data from Binance archive
   * No API key, no geo-blocking, no rate limits
   */
  app.post("/api/market/binance/archive/load", async (req, reply) => {
    const body = req.body as any;

    const params = {
      symbols: body.symbols ?? DEFAULT_SYMBOLS,
      intervals: body.intervals ?? DEFAULT_INTERVALS,
      startYear: Number(body.startYear ?? 2020),
      startMonth: Number(body.startMonth ?? 1),
      endYear: Number(body.endYear ?? 2025),
      endMonth: Number(body.endMonth ?? 12),
      concurrency: Number(body.concurrency ?? 8),
      batchSize: Number(body.batchSize ?? 2000),
      failFast: body.failFast ?? false,
    };

    console.log(
      `[Archive] Starting load: ${params.symbols.length} symbols × ${params.intervals.length} intervals`
    );

    const result = await loader.loadMany(params);

    return reply.send({
      ok: true,
      phase: "7.8",
      description: "Binance Archive Loader (data.binance.vision)",
      ...result,
    });
  });

  /**
   * Estimate data size before loading
   */
  app.post("/api/market/binance/archive/estimate", async (req, reply) => {
    const body = req.body as any;

    const symbols = body.symbols ?? DEFAULT_SYMBOLS;
    const intervals = body.intervals ?? DEFAULT_INTERVALS;
    const startYear = Number(body.startYear ?? 2020);
    const startMonth = Number(body.startMonth ?? 1);
    const endYear = Number(body.endYear ?? 2025);
    const endMonth = Number(body.endMonth ?? 12);

    const months = monthsBetween(startYear, startMonth, endYear, endMonth);
    const totalTasks = symbols.length * intervals.length * months.length;

    // Estimate candles per month per interval
    const candlesPerMonth: Record<string, number> = {
      "1m": 43200,
      "5m": 8640,
      "15m": 2880,
      "1h": 720,
      "4h": 180,
      "1d": 30,
    };

    let estimatedCandles = 0;
    for (const interval of intervals) {
      const perMonth = candlesPerMonth[interval] ?? 720;
      estimatedCandles += symbols.length * months.length * perMonth;
    }

    return reply.send({
      ok: true,
      phase: "7.8",
      estimate: {
        symbols: symbols.length,
        intervals: intervals.length,
        months: months.length,
        totalTasks,
        estimatedCandles,
        estimatedDuration: `${Math.ceil(totalTasks / 8 / 60)}m`,
      },
    });
  });

  /**
   * Get archive data coverage
   */
  app.get("/api/market/binance/archive/coverage", async (req, reply) => {
    const total = await mongo.getCount();
    const archiveOnly = await mongo.getCount(); // All should be archive now

    // Get breakdown by source
    const col = deps.mongoDb.collection("candles_binance");
    const bySource = await col
      .aggregate([
        { $group: { _id: "$source", count: { $sum: 1 } } },
      ])
      .toArray();

    const bySymbol = await col
      .aggregate([
        { $match: { source: "binance_archive" } },
        { $group: { _id: "$symbol", count: { $sum: 1 } } },
        { $sort: { count: -1 } },
      ])
      .toArray();

    const byInterval = await col
      .aggregate([
        { $match: { source: "binance_archive" } },
        { $group: { _id: "$interval", count: { $sum: 1 } } },
      ])
      .toArray();

    return reply.send({
      ok: true,
      phase: "7.8",
      coverage: {
        total,
        bySource,
        bySymbol,
        byInterval,
      },
    });
  });

  /**
   * Clear mock data (keep only archive data)
   */
  app.post("/api/market/binance/archive/clear_mock", async (req, reply) => {
    const deleted = await mongo.clearMockData();
    return reply.send({
      ok: true,
      phase: "7.8",
      deleted,
      message: `Cleared ${deleted} mock candles, kept archive data`,
    });
  });

  console.log("[Archive] Routes registered:");
  console.log("  - POST /api/market/binance/archive/load");
  console.log("  - POST /api/market/binance/archive/estimate");
  console.log("  - GET  /api/market/binance/archive/coverage");
  console.log("  - POST /api/market/binance/archive/clear_mock");
}
