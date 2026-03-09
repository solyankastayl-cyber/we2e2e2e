"""
Phase 8.5: Market Data Router
Routes data requests to appropriate providers.

Provider Priority:
1. Coinbase (primary) - clean historical data
2. Generated (fallback) - when APIs unavailable

Future providers:
- Kraken
- Hyperliquid (for perpetuals)
- Bitstamp
"""
import time
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from .coinbase_provider import coinbase_provider, fetch_coinbase_data


class MarketDataRouter:
    """
    Routes market data requests to the best available provider.
    
    Current providers:
    - coinbase: Primary for historical data
    - generated: Fallback synthetic data
    
    Configuration:
    - validation_provider: coinbase (default)
    - realtime_provider: (future) hyperliquid
    - backup_provider: (future) kraken
    """
    
    def __init__(self):
        self.providers = {
            "coinbase": coinbase_provider
        }
        self.default_provider = "coinbase"
        self._health_cache: Dict[str, Dict] = {}
        self._health_ttl = 60000  # 60 seconds
    
    async def fetch_candles(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "4h",
        start_date: str = "2022-01-01",
        end_date: str = "2024-01-01",
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch candles from the best available provider.
        
        Args:
            symbol: Trading pair
            timeframe: 1h, 4h, 1d, etc.
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            provider: Force specific provider (optional)
            
        Returns:
            List of candle dicts
        """
        provider_name = provider or self.default_provider
        
        # Try primary provider
        if provider_name in self.providers:
            try:
                candles = await self.providers[provider_name].fetch_candles(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if candles:
                    return candles
                    
            except Exception as e:
                print(f"[Router] {provider_name} failed: {e}")
        
        # Fallback to generated data
        print(f"[Router] Falling back to generated data for {symbol}")
        return self._generate_fallback_candles(symbol, timeframe, start_date, end_date)
    
    async def health_check(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Check provider health"""
        provider_name = provider or self.default_provider
        
        # Check cache
        cache_key = provider_name
        if cache_key in self._health_cache:
            cached = self._health_cache[cache_key]
            if time.time() * 1000 - cached.get("timestamp", 0) < self._health_ttl:
                return cached
        
        # Check health
        if provider_name in self.providers:
            try:
                health = await self.providers[provider_name].health_check()
                health["timestamp"] = int(time.time() * 1000)
                self._health_cache[cache_key] = health
                return health
            except Exception as e:
                return {"ok": False, "error": str(e), "provider": provider_name}
        
        return {"ok": False, "error": f"Unknown provider: {provider_name}"}
    
    async def get_available_providers(self) -> List[Dict[str, Any]]:
        """Get list of available providers with health status"""
        results = []
        
        for name in self.providers:
            health = await self.health_check(name)
            results.append({
                "name": name,
                "status": "UP" if health.get("ok") else "DOWN",
                "latencyMs": health.get("latencyMs", 0),
                "isDefault": name == self.default_provider
            })
        
        return results
    
    def _generate_fallback_candles(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Generate realistic fallback candles when API unavailable"""
        import random
        import math
        
        # Timeframe to hours
        tf_hours = {
            "1m": 1/60, "5m": 5/60, "15m": 0.25, "30m": 0.5,
            "1h": 1, "2h": 2, "4h": 4, "6h": 6, "8h": 8, "12h": 12,
            "1d": 24, "3d": 72, "1w": 168
        }.get(timeframe, 4)
        
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
        
        total_hours = (end_ts - start_ts) / (1000 * 3600)
        num_candles = int(total_hours / tf_hours)
        
        # Starting price based on symbol
        if "BTC" in symbol:
            base_price = 30000 + random.uniform(-5000, 15000)
        elif "ETH" in symbol:
            base_price = 2000 + random.uniform(-500, 1000)
        elif "SOL" in symbol:
            base_price = 100 + random.uniform(-30, 50)
        else:
            base_price = 100
        
        candles = []
        price = base_price
        trend = 0
        volatility = 0.02
        
        for i in range(num_candles):
            timestamp = start_ts + int(i * tf_hours * 3600 * 1000)
            
            # Evolve trend
            trend += random.uniform(-0.1, 0.1)
            trend = max(-0.8, min(0.8, trend))
            
            # Volatility clustering
            volatility = 0.015 + abs(random.gauss(0, 0.01))
            volatility = min(0.08, volatility)
            
            # Price change
            change = random.gauss(trend * 0.001, volatility)
            
            open_price = price
            close_price = price * (1 + change)
            
            # High/Low with wicks
            wick_up = abs(random.gauss(0, volatility * 0.5))
            wick_down = abs(random.gauss(0, volatility * 0.5))
            
            if change > 0:
                high_price = max(open_price, close_price) * (1 + wick_up)
                low_price = min(open_price, close_price) * (1 - wick_down * 0.5)
            else:
                high_price = max(open_price, close_price) * (1 + wick_up * 0.5)
                low_price = min(open_price, close_price) * (1 - wick_down)
            
            base_volume = 1000000 if "BTC" in symbol else 100000
            volume = base_volume * (1 + abs(change) * 10) * random.uniform(0.5, 1.5)
            
            candles.append({
                "timestamp": timestamp,
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": round(volume, 2),
                "source": "generated"
            })
            
            price = close_price
        
        return candles


# Global router instance
market_data_router = MarketDataRouter()


async def fetch_market_data(
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    start_date: str = "2022-01-01",
    end_date: str = "2024-01-01",
    provider: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for fetching market data.
    Routes to appropriate provider.
    
    Returns:
        Dict with candles and metadata
    """
    candles = await market_data_router.fetch_candles(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        provider=provider
    )
    
    if not candles:
        return {
            "success": False,
            "error": "No candles fetched",
            "candles": [],
            "count": 0
        }
    
    # Determine source
    source = candles[0].get("source", "unknown") if candles else "unknown"
    
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
        "source": source
    }


# Legacy alias for backward compatibility
binance_adapter = market_data_router
