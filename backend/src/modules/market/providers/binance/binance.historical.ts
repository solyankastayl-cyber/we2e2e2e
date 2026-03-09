/**
 * Phase 7.5: Binance Historical Loader
 * Pagination, normalization, and batch loading
 */

import { BinanceSpotClient } from "./binance.client.js";
import { Candle, BinanceInterval, LoadResult, INTERVAL_MS } from "./binance.types.js";

export function parseKlineRow(row: any[]): Candle {
  // Binance kline array format:
  // [0] openTime, [1] open, [2] high, [3] low, [4] close, [5] volume,
  // [6] closeTime, [7] quoteAssetVolume, [8] numberOfTrades,
  // [9] takerBuyBaseVolume, [10] takerBuyQuoteVolume, [11] ignore
  return {
    openTime: Number(row[0]),
    open: Number(row[1]),
    high: Number(row[2]),
    low: Number(row[3]),
    close: Number(row[4]),
    volume: Number(row[5]),
    closeTime: Number(row[6]),
    quoteVolume: Number(row[7]),
    trades: Number(row[8]),
    takerBuyBaseVolume: Number(row[9]),
    takerBuyQuoteVolume: Number(row[10]),
  };
}

function assertValidWindow(startTime: number, endTime: number): void {
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) {
    throw new Error("Invalid time parameters");
  }
  if (endTime <= startTime) {
    throw new Error("endTime must be > startTime");
  }
}

export interface HistoricalLoaderOpts {
  pageLimit?: number;
  maxPages?: number;
  onProgress?: (loaded: number, pages: number) => void;
}

export class BinanceHistoricalLoader {
  constructor(private client: BinanceSpotClient) {}

  /**
   * Loads candles in [startTime, endTime) with pagination.
   * Returns strictly sorted unique candles by openTime.
   */
  async loadAll(
    symbol: string,
    interval: BinanceInterval,
    startTime: number,
    endTime: number,
    opts: HistoricalLoaderOpts = {}
  ): Promise<{ candles: Candle[]; pages: number }> {
    assertValidWindow(startTime, endTime);

    const limit = Math.min(opts.pageLimit ?? 1000, 1000);
    const maxPages = opts.maxPages ?? 20000;

    let cursor = startTime;
    let pages = 0;
    const out: Candle[] = [];
    let lastOpenTime = -1;

    console.log(`[Binance] Loading ${symbol} ${interval} from ${new Date(startTime).toISOString()} to ${new Date(endTime).toISOString()}`);

    while (cursor < endTime) {
      pages++;
      if (pages > maxPages) {
        throw new Error(`Exceeded maxPages=${maxPages}`);
      }

      const rows = await this.client.getKlines({
        symbol,
        interval,
        startTime: cursor,
        endTime,
        limit,
      });

      if (!rows || rows.length === 0) break;

      const batch = rows.map(parseKlineRow);

      // Guard monotonicity and avoid duplicates
      for (const c of batch) {
        if (c.openTime <= lastOpenTime) continue;
        out.push(c);
        lastOpenTime = c.openTime;
      }

      // Progress callback
      if (opts.onProgress) {
        opts.onProgress(out.length, pages);
      }

      // Pagination: next cursor = last candle openTime + 1ms
      const last = batch[batch.length - 1];
      if (!last) break;

      const next = last.openTime + 1;
      if (next <= cursor) break;
      cursor = next;

      // If returned less than limit, likely reached end
      if (rows.length < limit) break;

      // Log progress every 10 pages
      if (pages % 10 === 0) {
        console.log(`[Binance] ${symbol} ${interval}: ${out.length} candles loaded (page ${pages})`);
      }
    }

    console.log(`[Binance] ${symbol} ${interval}: Complete - ${out.length} candles in ${pages} pages`);

    return { candles: out, pages };
  }

  /**
   * Load multiple symbols and intervals in sequence
   */
  async loadBulk(
    assets: string[],
    intervals: BinanceInterval[],
    startTime: number,
    endTime: number,
    onResult?: (result: LoadResult) => void
  ): Promise<LoadResult[]> {
    const results: LoadResult[] = [];
    const total = assets.length * intervals.length;
    let current = 0;

    for (const symbol of assets) {
      for (const interval of intervals) {
        current++;
        console.log(`[Binance] Bulk load ${current}/${total}: ${symbol} ${interval}`);
        
        const startMs = Date.now();
        try {
          const { candles, pages } = await this.loadAll(symbol, interval, startTime, endTime);
          const result: LoadResult = {
            symbol,
            interval,
            requested: { startTime, endTime },
            fetchedCandles: candles.length,
            upserted: 0, // Will be updated by caller after storage
            earliest: candles[0]?.openTime,
            latest: candles[candles.length - 1]?.openTime,
            pages,
            durationMs: Date.now() - startMs,
          };
          results.push(result);
          if (onResult) onResult(result);
        } catch (err) {
          console.error(`[Binance] Failed to load ${symbol} ${interval}:`, err);
          // Continue with other pairs
        }
      }
    }

    return results;
  }

  makeLoadResult(
    symbol: string,
    interval: BinanceInterval,
    startTime: number,
    endTime: number,
    candles: Candle[],
    upserted: number,
    pages: number,
    durationMs: number
  ): LoadResult {
    return {
      symbol,
      interval,
      requested: { startTime, endTime },
      fetchedCandles: candles.length,
      upserted,
      earliest: candles[0]?.openTime,
      latest: candles[candles.length - 1]?.openTime,
      pages,
      durationMs,
    };
  }

  /**
   * Estimate expected candles for a time range
   */
  estimateCandles(interval: BinanceInterval, startTime: number, endTime: number): number {
    const intervalMs = INTERVAL_MS[interval] || 86400000;
    return Math.ceil((endTime - startTime) / intervalMs);
  }
}
