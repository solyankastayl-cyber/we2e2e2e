"""
Dataset Registry
================

Manages dataset metadata for all supported assets.
Knows what data is available, date ranges, and properties.
"""

from typing import Dict, List, Optional
from datetime import datetime

from .types import DatasetDescriptor, AssetClass


class DatasetRegistry:
    """
    Registry of all available datasets.
    
    Provides metadata about what data is available for each asset,
    enabling the engine to make informed decisions about date ranges
    and supported features.
    """
    
    def __init__(self):
        self._datasets: Dict[str, DatasetDescriptor] = {}
        self._load_default_datasets()
    
    def _load_default_datasets(self):
        """Load default dataset descriptors for supported assets"""
        
        # SPX - S&P 500 Index (longest history)
        self.register(DatasetDescriptor(
            asset="SPX",
            asset_class=AssetClass.EQUITY,
            dataset_version="v1",
            start_date="1950-01-03",
            end_date="2026-02-20",
            base_timeframe="1D",
            supported_derived_timeframes=["1W", "1M"],
            has_volume=False,
            has_open_interest=False,
            has_macro_fields=False,
            total_bars=19242,
            gaps_detected=0,
            source="internal",
            created_at=datetime.utcnow().isoformat()
        ))
        
        # BTC - Bitcoin
        self.register(DatasetDescriptor(
            asset="BTC",
            asset_class=AssetClass.CRYPTO,
            dataset_version="v1",
            start_date="2010-07-18",
            end_date="2026-02-15",
            base_timeframe="1D",
            supported_derived_timeframes=["1W", "1M"],
            has_volume=True,
            has_open_interest=False,
            has_macro_fields=False,
            total_bars=5692,
            gaps_detected=0,
            source="internal",
            created_at=datetime.utcnow().isoformat()
        ))
        
        # ETH - Ethereum
        self.register(DatasetDescriptor(
            asset="ETH",
            asset_class=AssetClass.CRYPTO,
            dataset_version="v1",
            start_date="2016-01-01",
            end_date="2026-02-15",
            base_timeframe="1D",
            supported_derived_timeframes=["1W", "1M"],
            has_volume=True,
            has_open_interest=False,
            has_macro_fields=False,
            total_bars=3700,
            gaps_detected=0,
            source="internal",
            created_at=datetime.utcnow().isoformat()
        ))
        
        # SOL - Solana
        self.register(DatasetDescriptor(
            asset="SOL",
            asset_class=AssetClass.CRYPTO,
            dataset_version="v1",
            start_date="2020-04-01",
            end_date="2026-02-15",
            base_timeframe="1D",
            supported_derived_timeframes=["1W", "1M"],
            has_volume=True,
            has_open_interest=False,
            has_macro_fields=False,
            total_bars=2150,
            gaps_detected=0,
            source="internal",
            created_at=datetime.utcnow().isoformat()
        ))
        
        # DXY - US Dollar Index
        self.register(DatasetDescriptor(
            asset="DXY",
            asset_class=AssetClass.FX,
            dataset_version="v1",
            start_date="1973-01-02",
            end_date="2026-02-20",
            base_timeframe="1D",
            supported_derived_timeframes=["1W", "1M"],
            has_volume=False,
            has_open_interest=False,
            has_macro_fields=False,
            total_bars=13366,
            gaps_detected=0,
            source="internal",
            created_at=datetime.utcnow().isoformat()
        ))
        
        # GOLD - Gold
        self.register(DatasetDescriptor(
            asset="GOLD",
            asset_class=AssetClass.COMMODITY,
            dataset_version="v1",
            start_date="1975-01-02",
            end_date="2026-02-20",
            base_timeframe="1D",
            supported_derived_timeframes=["1W", "1M"],
            has_volume=False,
            has_open_interest=False,
            has_macro_fields=False,
            total_bars=12800,
            gaps_detected=0,
            source="internal",
            created_at=datetime.utcnow().isoformat()
        ))
    
    def register(self, descriptor: DatasetDescriptor) -> None:
        """Register a dataset descriptor"""
        self._datasets[descriptor.asset.upper()] = descriptor
    
    def get(self, asset: str) -> Optional[DatasetDescriptor]:
        """Get dataset descriptor for an asset"""
        return self._datasets.get(asset.upper())
    
    def list_assets(self) -> List[str]:
        """List all registered assets"""
        return list(self._datasets.keys())
    
    def list_by_class(self, asset_class: AssetClass) -> List[str]:
        """List assets by asset class"""
        return [
            asset for asset, desc in self._datasets.items()
            if desc.asset_class == asset_class
        ]
    
    def get_default_start_date(self, asset: str) -> Optional[str]:
        """Get default start date for an asset"""
        desc = self.get(asset)
        return desc.start_date if desc else None
    
    def get_default_end_date(self, asset: str) -> Optional[str]:
        """Get default end date for an asset"""
        desc = self.get(asset)
        return desc.end_date if desc else None
    
    def validate_date_range(self, asset: str, start_date: str, end_date: str) -> Dict:
        """Validate if date range is valid for an asset"""
        desc = self.get(asset)
        if not desc:
            return {
                "valid": False,
                "error": f"Unknown asset: {asset}"
            }
        
        # Parse dates
        try:
            req_start = datetime.strptime(start_date, "%Y-%m-%d")
            req_end = datetime.strptime(end_date, "%Y-%m-%d")
            data_start = datetime.strptime(desc.start_date, "%Y-%m-%d")
            data_end = datetime.strptime(desc.end_date, "%Y-%m-%d")
        except ValueError as e:
            return {
                "valid": False,
                "error": f"Invalid date format: {e}"
            }
        
        # Check bounds
        if req_start < data_start:
            return {
                "valid": False,
                "error": f"Start date {start_date} is before data start {desc.start_date}",
                "adjusted_start": desc.start_date
            }
        
        if req_end > data_end:
            return {
                "valid": False,
                "error": f"End date {end_date} is after data end {desc.end_date}",
                "adjusted_end": desc.end_date
            }
        
        if req_start >= req_end:
            return {
                "valid": False,
                "error": "Start date must be before end date"
            }
        
        return {
            "valid": True,
            "asset": asset,
            "start_date": start_date,
            "end_date": end_date,
            "estimated_bars": (req_end - req_start).days
        }
    
    def get_batch_start_dates(self, assets: List[str]) -> Dict[str, str]:
        """Get optimal start dates for a batch run"""
        result = {}
        for asset in assets:
            desc = self.get(asset)
            if desc:
                result[asset] = desc.start_date
        return result
    
    def to_dict(self) -> Dict:
        """Export registry as dictionary"""
        return {
            asset: {
                "asset": desc.asset,
                "asset_class": desc.asset_class.value,
                "start_date": desc.start_date,
                "end_date": desc.end_date,
                "total_bars": desc.total_bars,
                "has_volume": desc.has_volume,
                "version": desc.dataset_version
            }
            for asset, desc in self._datasets.items()
        }


# Singleton instance
dataset_registry = DatasetRegistry()
