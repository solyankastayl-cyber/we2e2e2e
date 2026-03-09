/**
 * Phase 7.5: Binance Market Data Types
 * Production-grade types for historical candle loading
 */

export type BinanceInterval =
  | "1m" | "3m" | "5m" | "15m" | "30m"
  | "1h" | "2h" | "4h" | "6h" | "8h" | "12h"
  | "1d" | "3d" | "1w" | "1M";

export interface Candle {
  openTime: number;      // unix ms
  closeTime: number;     // unix ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  quoteVolume: number;
  trades: number;
  takerBuyBaseVolume: number;
  takerBuyQuoteVolume: number;
}

export interface CandleDoc extends Candle {
  symbol: string;              // "BTCUSDT"
  interval: BinanceInterval;
  source: "binance_spot";
  key: string;                 // `${symbol}:${interval}:${openTime}`
  ingestedAt: number;          // unix ms
}

export interface LoadCandlesParams {
  symbol: string;
  interval: BinanceInterval;
  startTime: number;           // unix ms inclusive
  endTime: number;             // unix ms exclusive
  limit?: number;              // <= 1000
}

export interface LoadResult {
  symbol: string;
  interval: BinanceInterval;
  requested: { startTime: number; endTime: number };
  fetchedCandles: number;
  upserted: number;
  earliest?: number;
  latest?: number;
  pages: number;
  durationMs: number;
}

export interface CoverageInfo {
  symbol: string;
  interval: BinanceInterval;
  count: number;
  earliest: number | null;
  latest: number | null;
  gapDays?: number;
}

// Interval to milliseconds mapping
export const INTERVAL_MS: Record<BinanceInterval, number> = {
  "1m": 60 * 1000,
  "3m": 3 * 60 * 1000,
  "5m": 5 * 60 * 1000,
  "15m": 15 * 60 * 1000,
  "30m": 30 * 60 * 1000,
  "1h": 60 * 60 * 1000,
  "2h": 2 * 60 * 60 * 1000,
  "4h": 4 * 60 * 60 * 1000,
  "6h": 6 * 60 * 60 * 1000,
  "8h": 8 * 60 * 60 * 1000,
  "12h": 12 * 60 * 60 * 1000,
  "1d": 24 * 60 * 60 * 1000,
  "3d": 3 * 24 * 60 * 60 * 1000,
  "1w": 7 * 24 * 60 * 60 * 1000,
  "1M": 30 * 24 * 60 * 60 * 1000,
};
