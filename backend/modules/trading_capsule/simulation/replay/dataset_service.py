"""
Market Dataset Service (S1.2)
=============================

Manages market data for simulation replay.

Provides:
- Dataset creation (from CSV, API, or mock)
- Candle retrieval by index
- Dataset metadata
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading
import hashlib
import json

from ..simulation_types import (
    MarketCandle,
    MarketDataset,
    Timeframe
)


class MarketDatasetService:
    """
    Service for managing market datasets.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Dataset storage: dataset_id -> MarketDataset
        self._datasets: Dict[str, MarketDataset] = {}
        
        # Candle storage: dataset_id -> List[MarketCandle]
        self._candles: Dict[str, List[MarketCandle]] = {}
        
        self._initialized = True
        print("[MarketDatasetService] Initialized")
    
    # ===========================================
    # Dataset Creation
    # ===========================================
    
    def create_dataset(
        self,
        asset: str,
        timeframe: Timeframe,
        candles: List[Dict[str, Any]],
        dataset_id: Optional[str] = None
    ) -> MarketDataset:
        """
        Create a dataset from candle data.
        
        Args:
            asset: Asset symbol (e.g., "BTCUSDT")
            timeframe: Timeframe (1D, 4H, 1H)
            candles: List of candle dicts with timestamp, open, high, low, close, volume
            dataset_id: Optional custom dataset ID
        """
        import uuid
        
        dataset_id = dataset_id or str(uuid.uuid4())
        
        # Convert to MarketCandle objects
        candle_objects = []
        for c in candles:
            candle_objects.append(MarketCandle(
                timestamp=c.get("timestamp", ""),
                open=float(c.get("open", 0)),
                high=float(c.get("high", 0)),
                low=float(c.get("low", 0)),
                close=float(c.get("close", 0)),
                volume=float(c.get("volume", 0)) if c.get("volume") else None
            ))
        
        # Sort by timestamp
        candle_objects.sort(key=lambda c: c.timestamp)
        
        # Compute checksum
        checksum = self._compute_checksum(candle_objects)
        
        # Create dataset
        dataset = MarketDataset(
            dataset_id=dataset_id,
            asset=asset,
            timeframe=timeframe,
            start_date=candle_objects[0].timestamp if candle_objects else "",
            end_date=candle_objects[-1].timestamp if candle_objects else "",
            rows=len(candle_objects),
            checksum=checksum
        )
        
        # Store
        self._datasets[dataset_id] = dataset
        self._candles[dataset_id] = candle_objects
        
        print(f"[MarketDatasetService] Created dataset: {dataset_id} ({len(candle_objects)} candles)")
        return dataset
    
    def create_mock_dataset(
        self,
        asset: str = "BTCUSDT",
        timeframe: Timeframe = Timeframe.D1,
        days: int = 365,
        start_price: float = 40000.0,
        volatility: float = 0.02
    ) -> MarketDataset:
        """
        Create a mock dataset for testing.
        
        Generates realistic-looking price data.
        """
        import random
        from datetime import timedelta
        
        candles = []
        current_price = start_price
        current_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
        
        for _ in range(days):
            # Random price movement
            change_pct = random.gauss(0, volatility)
            
            open_price = current_price
            high_price = open_price * (1 + abs(random.gauss(0, volatility * 0.5)))
            low_price = open_price * (1 - abs(random.gauss(0, volatility * 0.5)))
            close_price = open_price * (1 + change_pct)
            
            # Ensure high >= open, close and low <= open, close
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
            
            volume = random.uniform(1000, 50000)
            
            candles.append({
                "timestamp": current_date.strftime("%Y-%m-%d"),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume
            })
            
            current_price = close_price
            current_date += timedelta(days=1)
        
        return self.create_dataset(asset, timeframe, candles)
    
    # ===========================================
    # Dataset Retrieval
    # ===========================================
    
    def get_dataset(self, dataset_id: str) -> Optional[MarketDataset]:
        """Get dataset metadata"""
        return self._datasets.get(dataset_id)
    
    def get_candle(self, dataset_id: str, index: int) -> Optional[MarketCandle]:
        """Get candle by index"""
        candles = self._candles.get(dataset_id)
        if candles and 0 <= index < len(candles):
            return candles[index]
        return None
    
    def get_candles(
        self,
        dataset_id: str,
        start_index: int = 0,
        count: int = 100
    ) -> List[MarketCandle]:
        """Get range of candles"""
        candles = self._candles.get(dataset_id, [])
        return candles[start_index:start_index + count]
    
    def get_dataset_length(self, dataset_id: str) -> int:
        """Get number of candles in dataset"""
        return len(self._candles.get(dataset_id, []))
    
    def list_datasets(self) -> List[MarketDataset]:
        """List all datasets"""
        return list(self._datasets.values())
    
    # ===========================================
    # Utilities
    # ===========================================
    
    def _compute_checksum(self, candles: List[MarketCandle]) -> str:
        """Compute checksum for candle data"""
        data = [
            {
                "t": c.timestamp,
                "o": round(c.open, 8),
                "h": round(c.high, 8),
                "l": round(c.low, 8),
                "c": round(c.close, 8)
            }
            for c in candles
        ]
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    
    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset"""
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            del self._candles[dataset_id]
            return True
        return False


# Global singleton
market_dataset_service = MarketDatasetService()
