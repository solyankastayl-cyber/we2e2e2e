/**
 * Phase 7.5: Binance REST API Client
 * Production-grade with rate limiting, retry, and backoff
 */

import { BinanceInterval, LoadCandlesParams } from "./binance.types.js";

type FetchFn = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

interface BinanceClientOpts {
  baseUrl?: string;
  fetchFn?: FetchFn;
  timeoutMs?: number;
  maxRps?: number;
  maxRetries?: number;
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Simple token bucket for rate limiting
 */
class TokenBucket {
  private tokens: number;
  private lastRefill: number;

  constructor(private capacity: number, private refillPerSec: number) {
    this.tokens = capacity;
    this.lastRefill = Date.now();
  }

  async take(n = 1): Promise<void> {
    while (true) {
      this.refill();
      if (this.tokens >= n) {
        this.tokens -= n;
        return;
      }
      await sleep(50);
    }
  }

  private refill(): void {
    const now = Date.now();
    const dt = (now - this.lastRefill) / 1000;
    if (dt <= 0) return;
    const add = dt * this.refillPerSec;
    if (add > 0) {
      this.tokens = Math.min(this.capacity, this.tokens + add);
      this.lastRefill = now;
    }
  }
}

export class BinanceSpotClient {
  private baseUrl: string;
  private fetchFn: FetchFn;
  private timeoutMs: number;
  private bucket: TokenBucket;
  private maxRetries: number;

  constructor(opts: BinanceClientOpts = {}) {
    this.baseUrl = opts.baseUrl ?? "https://api.binance.com";
    this.fetchFn = opts.fetchFn ?? fetch;
    this.timeoutMs = opts.timeoutMs ?? 15000;
    const maxRps = opts.maxRps ?? 8;
    this.bucket = new TokenBucket(Math.max(8, 2 * maxRps), maxRps);
    this.maxRetries = opts.maxRetries ?? 6;
  }

  async getKlines(params: LoadCandlesParams): Promise<any[]> {
    const limit = Math.min(params.limit ?? 1000, 1000);
    const url = new URL("/api/v3/klines", this.baseUrl);
    url.searchParams.set("symbol", params.symbol);
    url.searchParams.set("interval", params.interval as string);
    url.searchParams.set("startTime", String(params.startTime));
    url.searchParams.set("endTime", String(params.endTime));
    url.searchParams.set("limit", String(limit));

    return this.requestJson<any[]>(url.toString());
  }

  async getExchangeInfo(): Promise<any> {
    const url = new URL("/api/v3/exchangeInfo", this.baseUrl);
    return this.requestJson<any>(url.toString());
  }

  async getServerTime(): Promise<number> {
    const url = new URL("/api/v3/time", this.baseUrl);
    const res = await this.requestJson<{ serverTime: number }>(url.toString());
    return res.serverTime;
  }

  private async requestJson<T>(url: string): Promise<T> {
    let attempt = 0;
    while (true) {
      attempt++;
      await this.bucket.take(1);

      const ctrl = new AbortController();
      const to = setTimeout(() => ctrl.abort(), this.timeoutMs);

      try {
        const res = await this.fetchFn(url, { 
          method: "GET", 
          signal: ctrl.signal,
          headers: {
            'Accept': 'application/json',
          }
        });
        clearTimeout(to);

        // Handle rate limiting
        if (res.status === 429 || res.status === 418) {
          const retryAfter = res.headers.get("retry-after");
          const waitMs = retryAfter ? Number(retryAfter) * 1000 : this.backoffMs(attempt);
          console.log(`[Binance] Rate limited, waiting ${waitMs}ms (attempt ${attempt})`);
          if (attempt <= this.maxRetries) {
            await sleep(waitMs);
            continue;
          }
          throw new Error(`Binance rate limited (status=${res.status}) after ${attempt} retries`);
        }

        // Handle server errors
        if (res.status >= 500) {
          console.log(`[Binance] Server error ${res.status}, retrying... (attempt ${attempt})`);
          if (attempt <= this.maxRetries) {
            await sleep(this.backoffMs(attempt));
            continue;
          }
          throw new Error(`Binance server error status=${res.status}`);
        }

        // Handle geo-blocking (451/403)
        if (res.status === 451 || res.status === 403) {
          const txt = await res.text().catch(() => "");
          throw new Error(`Binance geo-blocked or forbidden (status=${res.status}). Consider using VPN or data.binance.vision fallback. Body: ${txt.slice(0, 200)}`);
        }

        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          throw new Error(`Binance error status=${res.status} body=${txt.slice(0, 200)}`);
        }

        return (await res.json()) as T;
      } catch (e: any) {
        clearTimeout(to);
        const msg = String(e?.message ?? e);
        
        // Retryable network errors
        const retryable =
          msg.includes("AbortError") ||
          msg.includes("abort") ||
          msg.includes("fetch") ||
          msg.includes("network") ||
          msg.includes("ECONN") ||
          msg.includes("ETIMEDOUT") ||
          msg.includes("ENOTFOUND");

        if (retryable && attempt <= this.maxRetries) {
          console.log(`[Binance] Network error, retrying... (attempt ${attempt}): ${msg.slice(0, 100)}`);
          await sleep(this.backoffMs(attempt));
          continue;
        }
        throw e;
      }
    }
  }

  private backoffMs(attempt: number): number {
    const base = Math.min(8000, 250 * Math.pow(2, attempt - 1));
    const jitter = Math.floor(Math.random() * 200);
    return base + jitter;
  }
}
