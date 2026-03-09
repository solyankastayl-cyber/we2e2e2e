"""
Phase 8.5: Coinbase Data Provider (Python)
Primary data source for validation runs.

Uses the same Coinbase Exchange API as the TypeScript module.
Clean historical data: BTC since 2015, ETH since 2016.
"""
import time
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import aiohttp


COINBASE_API = "https://api.exchange.coinbase.com"

# Granularity mapping (seconds)
GRANULARITY_MAP = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,  # Will aggregate from 1h
    "6h": 21600,  # Will aggregate from 1h
    "1d": 86400,
}


def map_symbol(symbol: str) -> str:
    """Map BTCUSDT -> BTC-USD format"""
    if symbol.endswith("USDT"):
        base = symbol.replace("USDT", "")
        return f"{base}-USD"
    if "-" in symbol:
        return symbol
    return f"{symbol}-USD"


class CoinbaseDataProvider:
    """
    Coinbase Historical Data Provider.
    
    Supports:
    - BTC-USD (since 2015)
    - ETH-USD (since 2016)
    - SOL-USD (since 2020)
    - Any USD pair available on Coinbase
    
    Timeframes: 1m, 5m, 15m, 1h, 4h, 6h, 1d
    """
    
    def __init__(self):
        self._cache: Dict[str, List[Dict]] = {}
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session
    
    async def close(self):
        """Close session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Coinbase API health"""
        start = time.time()
        try:
            session = await self._get_session()
            async with session.get(f"{COINBASE_API}/time") as response:
                latency = int((time.time() - start) * 1000)
                if response.status == 200:
                    return {"ok": True, "latencyMs": latency, "source": "coinbase"}
                return {"ok": False, "latencyMs": latency, "error": f"HTTP {response.status}"}
        except Exception as e:
            return {"ok": False, "latencyMs": int((time.time() - start) * 1000), "error": str(e)}
    
    async def fetch_candles(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        start_date: str = "2022-01-01",
        end_date: str = "2024-01-01",
        limit: int = 200  # Reduced from 300 for safety
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV candles from Coinbase.
        
        Args:
            symbol: Trading pair (BTCUSDT or BTC-USD)
            timeframe: 1m, 5m, 15m, 1h, 4h, 6h, 1d
            start_date: Start date YYYY-MM-DD
            end_date: End date YYYY-MM-DD
            limit: Max candles per request (Coinbase max: 300, using 200 for safety)
            
        Returns:
            List of candle dicts
        """
        cache_key = f"{symbol}_{timeframe}_{start_date}_{end_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        product = map_symbol(symbol)
        
        # Handle 4h/6h by aggregating from 1h
        if timeframe in ["4h", "6h"]:
            hourly_candles = await self._fetch_hourly_and_aggregate(
                product, timeframe, start_date, end_date
            )
            if hourly_candles:
                self._cache[cache_key] = hourly_candles
            return hourly_candles
        
        granularity = GRANULARITY_MAP.get(timeframe, 3600)
        
        start_ts = datetime.strptime(start_date, "%Y-%m-%d")
        end_ts = datetime.strptime(end_date, "%Y-%m-%d")
        
        all_candles = []
        current_start = start_ts
        
        session = await self._get_session()
        max_candles_per_request = 200  # Coinbase limit is 300, using 200 for safety
        
        while current_start < end_ts:
            # Calculate batch end (forward iteration is more reliable)
            batch_duration = granularity * max_candles_per_request
            batch_end = current_start + timedelta(seconds=batch_duration)
            if batch_end > end_ts:
                batch_end = end_ts
            
            url = f"{COINBASE_API}/products/{product}/candles"
            params = {
                "start": current_start.isoformat() + "Z",
                "end": batch_end.isoformat() + "Z",
                "granularity": granularity
            }
            
            try:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"[Coinbase] API error {response.status}: {error_text[:200]}")
                        # Try smaller batch
                        if response.status == 400 and "granularity too small" in error_text:
                            # Reduce batch size
                            batch_end = current_start + timedelta(seconds=granularity * 50)
                            if batch_end > end_ts:
                                batch_end = end_ts
                            params["end"] = batch_end.isoformat() + "Z"
                            async with session.get(url, params=params) as retry_response:
                                if retry_response.status == 200:
                                    data = await retry_response.json()
                                else:
                                    break
                        else:
                            break
                    else:
                        data = await response.json()
                    
                    if not data:
                        current_start = batch_end
                        continue
                    
                    # Coinbase format: [time, low, high, open, close, volume]
                    for row in data:
                        candle = {
                            "timestamp": row[0] * 1000,  # Convert to ms
                            "open": float(row[3]),
                            "high": float(row[2]),
                            "low": float(row[1]),
                            "close": float(row[4]),
                            "volume": float(row[5]),
                            "source": "coinbase"
                        }
                        all_candles.append(candle)
                    
                    # Move to next batch
                    current_start = batch_end
                    
                    # Rate limiting
                    await asyncio.sleep(0.15)
                    
            except asyncio.TimeoutError:
                print(f"[Coinbase] Timeout fetching {product}")
                break
            except Exception as e:
                print(f"[Coinbase] Error: {e}")
                break
                    
            except asyncio.TimeoutError:
                print(f"[Coinbase] Timeout fetching {product}")
                break
            except Exception as e:
                print(f"[Coinbase] Error: {e}")
                break
        
        # Sort by timestamp ascending
        all_candles.sort(key=lambda x: x["timestamp"])
        
        # Dedupe by timestamp
        seen = set()
        deduped = []
        for c in all_candles:
            if c["timestamp"] not in seen:
                seen.add(c["timestamp"])
                deduped.append(c)
        
        if deduped:
            self._cache[cache_key] = deduped
            print(f"[Coinbase] Fetched {len(deduped)} candles for {product} {timeframe}")
        
        return deduped
    
    async def _fetch_hourly_and_aggregate(
        self,
        product: str,
        target_tf: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch 1h candles and aggregate to 4h/6h.
        
        Coinbase 4h candles can be inconsistent, so we build them ourselves.
        """
        # Fetch hourly data
        hourly = await self.fetch_candles(
            symbol=product,
            timeframe="1h",
            start_date=start_date,
            end_date=end_date
        )
        
        if not hourly:
            return []
        
        # Determine aggregation period
        hours = 4 if target_tf == "4h" else 6
        ms_period = hours * 3600 * 1000
        
        # Group by period
        aggregated = []
        period_candles: List[Dict] = []
        current_period_start = None
        
        for candle in hourly:
            # Determine which period this candle belongs to
            period_start = (candle["timestamp"] // ms_period) * ms_period
            
            if current_period_start is None:
                current_period_start = period_start
            
            if period_start != current_period_start:
                # Finish previous period
                if period_candles:
                    agg = self._aggregate_candles(period_candles, current_period_start)
                    aggregated.append(agg)
                
                # Start new period
                period_candles = [candle]
                current_period_start = period_start
            else:
                period_candles.append(candle)
        
        # Don't forget last period
        if period_candles:
            agg = self._aggregate_candles(period_candles, current_period_start)
            aggregated.append(agg)
        
        print(f"[Coinbase] Aggregated {len(hourly)} 1h candles → {len(aggregated)} {target_tf} candles")
        return aggregated
    
    def _aggregate_candles(self, candles: List[Dict], timestamp: int) -> Dict[str, Any]:
        """Aggregate multiple candles into one"""
        return {
            "timestamp": timestamp,
            "open": candles[0]["open"],
            "high": max(c["high"] for c in candles),
            "low": min(c["low"] for c in candles),
            "close": candles[-1]["close"],
            "volume": sum(c["volume"] for c in candles),
            "source": "coinbase_aggregated"
        }
    
    async def get_products(self) -> List[Dict[str, str]]:
        """Get available USD products"""
        session = await self._get_session()
        
        try:
            async with session.get(f"{COINBASE_API}/products") as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                
                # Filter for USD pairs that are online
                products = [
                    {
                        "id": p["id"],
                        "base": p["base_currency"],
                        "quote": p["quote_currency"]
                    }
                    for p in data
                    if p.get("quote_currency") == "USD" and p.get("status") == "online"
                ]
                
                return products
        except Exception as e:
            print(f"[Coinbase] Error fetching products: {e}")
            return []
    
    def clear_cache(self):
        """Clear cached data"""
        self._cache.clear()


# Global instance
coinbase_provider = CoinbaseDataProvider()


async def fetch_coinbase_data(
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    start_date: str = "2022-01-01",
    end_date: str = "2024-01-01"
) -> Dict[str, Any]:
    """
    Fetch market data from Coinbase for validation.
    
    Returns:
        Dict with candles and metadata
    """
    candles = await coinbase_provider.fetch_candles(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date
    )
    
    if not candles:
        return {
            "success": False,
            "error": "No candles fetched from Coinbase",
            "candles": [],
            "count": 0,
            "source": "coinbase"
        }
    
    return {
        "success": True,
        "symbol": symbol,
        "timeframe": timeframe,
        "start_date": start_date,
        "end_date": end_date,
        "candles": candles,
        "count": len(candles),
        "first_candle": candles[0]["timestamp"] if candles else None,
        "last_candle": candles[-1]["timestamp"] if candles else None,
        "source": "coinbase"
    }
