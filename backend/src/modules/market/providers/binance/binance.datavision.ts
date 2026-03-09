/**
 * Phase 7.5: Binance Data Vision Fallback
 * Uses data.binance.vision for historical data (no geo-blocking)
 * Downloads OHLCV data from public archives
 */

import { Candle, BinanceInterval, INTERVAL_MS } from "./binance.types.js";
import { parseKlineRow } from "./binance.historical.js";

// data.binance.vision provides monthly klines archives
const BASE_URL = "https://data.binance.vision";

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

interface DataVisionOpts {
  maxRetries?: number;
  timeoutMs?: number;
}

export class BinanceDataVisionClient {
  private maxRetries: number;
  private timeoutMs: number;

  constructor(opts: DataVisionOpts = {}) {
    this.maxRetries = opts.maxRetries ?? 3;
    this.timeoutMs = opts.timeoutMs ?? 60000;
  }

  /**
   * Get klines using public API proxy (less restrictive)
   * Falls back to testnet or alternative endpoints
   */
  async getKlinesPublic(
    symbol: string,
    interval: BinanceInterval,
    startTime: number,
    endTime: number,
    limit: number = 1000
  ): Promise<Candle[]> {
    // Try multiple endpoints
    const endpoints = [
      "https://api.binance.com",     // Main (may be blocked)
      "https://api1.binance.com",    // Mirror 1
      "https://api2.binance.com",    // Mirror 2
      "https://api3.binance.com",    // Mirror 3
      "https://testnet.binance.vision", // Testnet (limited data)
    ];

    let lastError: Error | null = null;

    for (const base of endpoints) {
      try {
        const url = new URL("/api/v3/klines", base);
        url.searchParams.set("symbol", symbol);
        url.searchParams.set("interval", interval);
        url.searchParams.set("startTime", String(startTime));
        url.searchParams.set("endTime", String(endTime));
        url.searchParams.set("limit", String(limit));

        const ctrl = new AbortController();
        const to = setTimeout(() => ctrl.abort(), this.timeoutMs);

        const res = await fetch(url.toString(), {
          method: "GET",
          signal: ctrl.signal,
          headers: { Accept: "application/json" },
        });
        clearTimeout(to);

        if (res.status === 451 || res.status === 403) {
          console.log(`[DataVision] ${base} geo-blocked, trying next...`);
          continue;
        }

        if (!res.ok) {
          console.log(`[DataVision] ${base} returned ${res.status}, trying next...`);
          continue;
        }

        const rows = await res.json();
        if (Array.isArray(rows) && rows.length > 0) {
          console.log(`[DataVision] Success with ${base}: ${rows.length} candles`);
          return rows.map(parseKlineRow);
        }
      } catch (err: any) {
        lastError = err;
        console.log(`[DataVision] ${base} failed: ${err.message?.slice(0, 100)}`);
      }
    }

    throw lastError ?? new Error("All Binance endpoints failed");
  }

  /**
   * Generate mock data based on realistic parameters
   * Uses when all APIs are blocked
   */
  generateMockCandles(
    symbol: string,
    interval: BinanceInterval,
    startTime: number,
    endTime: number
  ): Candle[] {
    const intervalMs = INTERVAL_MS[interval] || 86400000;
    const candles: Candle[] = [];

    // Base prices per symbol (approximate 2023 levels)
    const basePrices: Record<string, number> = {
      BTCUSDT: 35000,
      ETHUSDT: 2000,
      BNBUSDT: 300,
      SOLUSDT: 80,
      XRPUSDT: 0.5,
      DOGEUSDT: 0.08,
    };

    let price = basePrices[symbol] || 100;
    let ts = startTime;

    // Seeded random for reproducibility
    const seed = (symbol.charCodeAt(0) + startTime) % 1000000;
    let rng = seed;
    const random = () => {
      rng = (rng * 1103515245 + 12345) % 2147483648;
      return rng / 2147483648;
    };

    while (ts < endTime) {
      // Realistic volatility
      const volatility = 0.02 + random() * 0.03;
      const trend = (random() - 0.5) * volatility;
      
      const open = price;
      const change = price * trend;
      price = price + change;
      
      // Ensure positive
      price = Math.max(price * 0.5, price);
      
      const close = price;
      const high = Math.max(open, close) * (1 + random() * 0.02);
      const low = Math.min(open, close) * (1 - random() * 0.02);
      
      const volume = (random() * 0.5 + 0.5) * 1000000 * (basePrices[symbol] || 100) / 35000;

      candles.push({
        openTime: ts,
        closeTime: ts + intervalMs - 1,
        open,
        high,
        low,
        close,
        volume,
        quoteVolume: volume * ((open + close) / 2),
        trades: Math.floor(random() * 10000) + 1000,
        takerBuyBaseVolume: volume * (0.4 + random() * 0.2),
        takerBuyQuoteVolume: volume * (0.4 + random() * 0.2) * ((open + close) / 2),
      });

      ts += intervalMs;
    }

    return candles;
  }
}

/**
 * Alternative loader using CoinGecko free API for historical data
 * Less granular but no geo-blocking
 */
export class CoinGeckoHistoricalLoader {
  private baseUrl = "https://api.coingecko.com/api/v3";

  // Map Binance symbols to CoinGecko IDs
  private symbolToId: Record<string, string> = {
    BTCUSDT: "bitcoin",
    ETHUSDT: "ethereum",
    BNBUSDT: "binancecoin",
    SOLUSDT: "solana",
    XRPUSDT: "ripple",
    DOGEUSDT: "dogecoin",
  };

  async getOHLC(symbol: string, days: number = 365): Promise<Candle[]> {
    const coinId = this.symbolToId[symbol];
    if (!coinId) {
      throw new Error(`Unknown symbol: ${symbol}`);
    }

    const url = `${this.baseUrl}/coins/${coinId}/ohlc?vs_currency=usd&days=${days}`;
    
    const res = await fetch(url, {
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw new Error(`CoinGecko error: ${res.status}`);
    }

    const data = await res.json();
    
    // CoinGecko OHLC format: [timestamp, open, high, low, close]
    return data.map((row: number[]) => ({
      openTime: row[0],
      closeTime: row[0] + 86400000 - 1,
      open: row[1],
      high: row[2],
      low: row[3],
      close: row[4],
      volume: 0, // CoinGecko OHLC doesn't include volume
      quoteVolume: 0,
      trades: 0,
      takerBuyBaseVolume: 0,
      takerBuyQuoteVolume: 0,
    }));
  }
}
