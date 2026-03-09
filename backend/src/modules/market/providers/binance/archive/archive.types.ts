/**
 * Phase 7.8-7.9: Binance Archive Types
 * For data.binance.vision historical data
 */

export interface YearMonth {
  year: number;
  month: number; // 1..12
}

export interface ArchiveCandle {
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  closeTime: number;
  quoteVolume: number;
  trades: number;
  takerBuyBase: number;
  takerBuyQuote: number;
}

export interface ArchiveLoadParams {
  symbols: string[];
  intervals: string[];
  startYear: number;
  startMonth: number;
  endYear: number;
  endMonth: number;
  concurrency?: number;
  batchSize?: number;
  failFast?: boolean;
}

export interface TaskResult {
  symbol: string;
  interval: string;
  year: number;
  month: number;
  ok: boolean;
  written: number;
  error?: string;
  url: string;
}

export interface ArchiveLoadResult {
  totalTasks: number;
  ok: number;
  failed: number;
  candlesWritten: number;
  durationMs: number;
  byTask: TaskResult[];
}
