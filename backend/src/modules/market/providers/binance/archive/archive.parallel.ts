/**
 * Phase 7.8-7.9: Parallel Binance Archive Loader
 * Downloads from data.binance.vision without API/VPN/rate-limits
 */

import unzipper from "unzipper";
import readline from "readline";
import pLimit from "p-limit";
import { Readable } from "stream";
import { pad2, monthsBetween, sleep } from "./archive.utils.js";
import { BinanceArchiveMongo } from "./archive.mongo.js";
import {
  ArchiveCandle,
  ArchiveLoadParams,
  ArchiveLoadResult,
  TaskResult,
} from "./archive.types.js";

export class BinanceArchiveParallelLoader {
  private base = "https://data.binance.vision/data/spot/monthly/klines";

  constructor(private mongo: BinanceArchiveMongo) {}

  buildUrl(symbol: string, interval: string, year: number, month: number): string {
    const mm = pad2(month);
    return `${this.base}/${symbol}/${interval}/${symbol}-${interval}-${year}-${mm}.zip`;
  }

  private parseCSVLine(line: string): ArchiveCandle | null {
    if (!line || line.startsWith("open")) return null; // skip header
    const p = line.split(",");
    if (p.length < 11) return null;

    return {
      openTime: Number(p[0]),
      open: Number(p[1]),
      high: Number(p[2]),
      low: Number(p[3]),
      close: Number(p[4]),
      volume: Number(p[5]),
      closeTime: Number(p[6]),
      quoteVolume: Number(p[7]),
      trades: Number(p[8]),
      takerBuyBase: Number(p[9]),
      takerBuyQuote: Number(p[10]),
    };
  }

  private async loadMonthToMongo(
    symbol: string,
    interval: string,
    year: number,
    month: number,
    batchSize: number
  ): Promise<{ written: number; url: string }> {
    const url = this.buildUrl(symbol, interval, year, month);

    const res = await fetch(url, {
      headers: { Accept: "application/zip" },
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status} for ${url}`);
    }

    if (!res.body) {
      throw new Error(`No body for ${url}`);
    }

    // Convert web ReadableStream to Node stream
    const nodeStream = Readable.fromWeb(res.body as any);
    const unzipStream = nodeStream.pipe(unzipper.Parse({ forceStream: true }));

    let written = 0;

    for await (const entry of unzipStream) {
      if (!entry.path.endsWith(".csv")) {
        entry.autodrain();
        continue;
      }

      const rl = readline.createInterface({ input: entry });
      let batch: ArchiveCandle[] = [];

      for await (const line of rl) {
        const candle = this.parseCSVLine(line);
        if (!candle) continue;

        batch.push(candle);

        if (batch.length >= batchSize) {
          written += await this.mongo.upsertBatch(symbol, interval, batch);
          batch = [];
        }
      }

      if (batch.length) {
        written += await this.mongo.upsertBatch(symbol, interval, batch);
      }

      // Only first CSV expected
      entry.autodrain();
    }

    return { written, url };
  }

  async loadMany(params: ArchiveLoadParams): Promise<ArchiveLoadResult> {
    const startTime = Date.now();
    const concurrency = Math.max(1, params.concurrency ?? 8);
    const batchSize = Math.max(200, params.batchSize ?? 2000);
    const failFast = params.failFast ?? false;

    const months = monthsBetween(
      params.startYear,
      params.startMonth,
      params.endYear,
      params.endMonth
    );

    // Build task list
    const tasks: Array<{
      symbol: string;
      interval: string;
      year: number;
      month: number;
    }> = [];

    for (const symbol of params.symbols) {
      for (const interval of params.intervals) {
        for (const ym of months) {
          tasks.push({
            symbol,
            interval,
            year: ym.year,
            month: ym.month,
          });
        }
      }
    }

    console.log(
      `[Archive] Starting parallel load: ${tasks.length} tasks, concurrency=${concurrency}`
    );

    const limit = pLimit(concurrency);

    let ok = 0;
    let failed = 0;
    let candlesWritten = 0;
    const byTask: TaskResult[] = [];

    const runners = tasks.map((t, idx) =>
      limit(async () => {
        const url = this.buildUrl(t.symbol, t.interval, t.year, t.month);
        try {
          const { written } = await this.loadMonthToMongo(
            t.symbol,
            t.interval,
            t.year,
            t.month,
            batchSize
          );
          ok++;
          candlesWritten += written;
          byTask.push({ ...t, ok: true, written, url });

          // Progress log every 10 tasks
          if ((ok + failed) % 10 === 0) {
            console.log(
              `[Archive] Progress: ${ok + failed}/${tasks.length} (${candlesWritten} candles)`
            );
          }
        } catch (e: any) {
          failed++;
          const errorMsg = String(e?.message ?? e).slice(0, 200);
          byTask.push({ ...t, ok: false, written: 0, error: errorMsg, url });

          // Some months may not exist (e.g., future months, coins launched later)
          if (!errorMsg.includes("404")) {
            console.log(`[Archive] Failed ${t.symbol} ${t.interval} ${t.year}-${pad2(t.month)}: ${errorMsg}`);
          }

          if (failFast) throw e;
        }
      })
    );

    // Execute all
    await Promise.allSettled(runners);

    const durationMs = Date.now() - startTime;

    console.log(
      `[Archive] Complete: ${ok} ok, ${failed} failed, ${candlesWritten} candles in ${Math.round(durationMs / 1000)}s`
    );

    return {
      totalTasks: tasks.length,
      ok,
      failed,
      candlesWritten,
      durationMs,
      byTask,
    };
  }
}
