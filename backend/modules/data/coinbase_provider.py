"""
Coinbase Data Provider
======================

Fetches live and historical OHLCV data from Coinbase.

Usage:
    from coinbase_provider import CoinbaseProvider
    
    provider = CoinbaseProvider()
    candles = await provider.get_candles("BTC-USD", "1d", limit=100)
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

try:
    import httpx
    HTTPX_OK = True
except ImportError:
    HTTPX_OK = False


class CoinbaseProvider:
    """Coinbase Exchange Data Provider"""
    
    BASE_URL = "https://api.exchange.coinbase.com"
    
    GRANULARITIES = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }
    
    SUPPORTED_PAIRS = [
        "BTC-USD", "ETH-USD", "SOL-USD",
        "BTC-USDT", "ETH-USDT", "SOL-USDT",
    ]
    
    def __init__(self):
        self.last_request = 0
        self.rate_limit_delay = 0.1  # 100ms between requests
    
    async def get_candles(
        self,
        product_id: str,
        timeframe: str = "1d",
        limit: int = 300,
        start: Optional[int] = None,
        end: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV candles from Coinbase.
        
        Args:
            product_id: Trading pair (e.g., "BTC-USD")
            timeframe: Candle interval (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Max candles to return (max 300)
            start: Start timestamp (ISO format or unix seconds)
            end: End timestamp (ISO format or unix seconds)
        
        Returns:
            List of candle dicts with: timestamp, open, high, low, close, volume
        """
        if not HTTPX_OK:
            raise ImportError("httpx required: pip install httpx")
        
        granularity = self.GRANULARITIES.get(timeframe)
        if not granularity:
            raise ValueError(f"Invalid timeframe: {timeframe}. Use: {list(self.GRANULARITIES.keys())}")
        
        # Rate limiting
        await self._rate_limit()
        
        # Build request
        url = f"{self.BASE_URL}/products/{product_id}/candles"
        params = {"granularity": granularity}
        
        if start:
            params["start"] = self._to_iso(start)
        if end:
            params["end"] = self._to_iso(end)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        
        # Parse response: [[timestamp, low, high, open, close, volume], ...]
        candles = []
        for row in data[:limit]:
            if len(row) >= 6:
                candles.append({
                    "timestamp": row[0] * 1000,  # Convert to ms
                    "open": float(row[3]),
                    "high": float(row[2]),
                    "low": float(row[1]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "timeframe": timeframe,
                    "source": "coinbase",
                })
        
        # Sort by timestamp ascending
        candles.sort(key=lambda x: x["timestamp"])
        
        return candles
    
    async def get_ticker(self, product_id: str) -> Dict[str, Any]:
        """Get current ticker for product"""
        if not HTTPX_OK:
            raise ImportError("httpx required: pip install httpx")
        
        await self._rate_limit()
        
        url = f"{self.BASE_URL}/products/{product_id}/ticker"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        
        return {
            "product_id": product_id,
            "price": float(data.get("price", 0)),
            "bid": float(data.get("bid", 0)),
            "ask": float(data.get("ask", 0)),
            "volume": float(data.get("volume", 0)),
            "time": data.get("time"),
        }
    
    async def get_products(self) -> List[Dict[str, Any]]:
        """Get all available trading pairs"""
        if not HTTPX_OK:
            raise ImportError("httpx required: pip install httpx")
        
        await self._rate_limit()
        
        url = f"{self.BASE_URL}/products"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        
        return [
            {
                "id": p["id"],
                "base": p["base_currency"],
                "quote": p["quote_currency"],
                "status": p.get("status", "online"),
            }
            for p in data
        ]
    
    async def _rate_limit(self):
        """Enforce rate limiting"""
        now = time.time()
        elapsed = now - self.last_request
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self.last_request = time.time()
    
    def _to_iso(self, ts: int) -> str:
        """Convert timestamp to ISO format"""
        if ts > 1e12:  # Already in ms
            ts = ts / 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.isoformat()


# Singleton
coinbase_provider = CoinbaseProvider()


async def fetch_btc_candles(timeframe: str = "1d", limit: int = 100) -> List[Dict]:
    """Quick helper to fetch BTC candles"""
    return await coinbase_provider.get_candles("BTC-USD", timeframe, limit)


async def fetch_eth_candles(timeframe: str = "1d", limit: int = 100) -> List[Dict]:
    """Quick helper to fetch ETH candles"""
    return await coinbase_provider.get_candles("ETH-USD", timeframe, limit)


# CLI test
if __name__ == "__main__":
    import json
    
    async def test():
        provider = CoinbaseProvider()
        
        print("Testing Coinbase Provider...")
        
        # Get ticker
        ticker = await provider.get_ticker("BTC-USD")
        print(f"\nBTC Ticker: ${ticker['price']:,.2f}")
        
        # Get candles
        candles = await provider.get_candles("BTC-USD", "1d", limit=5)
        print(f"\nLast 5 daily candles:")
        for c in candles[-5:]:
            dt = datetime.fromtimestamp(c['timestamp']/1000)
            print(f"  {dt.date()}: O={c['open']:.0f} H={c['high']:.0f} L={c['low']:.0f} C={c['close']:.0f}")
    
    asyncio.run(test())
