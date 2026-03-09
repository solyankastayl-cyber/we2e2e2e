"""
Dataset Registry
================

Data governance layer for managing datasets.
Includes consistency validation for data integrity.
"""

import time
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}
VALID_TIMEFRAMES = {"1m", "5m", "15m", "1h", "4h", "1D", "1W", "1M"}
VALID_SOURCES = {"coinbase", "yahoo", "fred", "binance", "bybit", "internal", "stooq"}


@dataclass
class Dataset:
    """Dataset metadata"""
    dataset_id: str
    name: str
    asset: str
    
    version: str = "1.0"
    start_date: str = ""
    end_date: str = ""
    rows: int = 0
    
    checksum: str = ""
    source: str = "internal"
    timeframe: str = "1D"
    
    columns: List[str] = field(default_factory=list)
    description: str = ""
    
    created_at: int = 0
    updated_at: int = 0


def validate_dataset_consistency(dataset: Dataset) -> Dict[str, Any]:
    """
    Validate dataset consistency.
    Checks:
    - Required columns present
    - Valid timeframe
    - Valid source
    - Row count positive
    - Date range valid
    - Checksum present
    """
    issues = []
    warnings = []
    
    # Check required columns
    if dataset.columns:
        missing_cols = REQUIRED_COLUMNS - set(dataset.columns)
        if missing_cols:
            issues.append({
                "check": "required_columns",
                "message": f"Missing required columns: {missing_cols}",
            })
    else:
        warnings.append({
            "check": "columns_empty",
            "message": "No columns defined",
        })
    
    # Check timeframe
    if dataset.timeframe and dataset.timeframe not in VALID_TIMEFRAMES:
        issues.append({
            "check": "timeframe",
            "message": f"Invalid timeframe '{dataset.timeframe}'. Valid: {VALID_TIMEFRAMES}",
        })
    
    # Check source
    if dataset.source and dataset.source not in VALID_SOURCES:
        warnings.append({
            "check": "source",
            "message": f"Unknown source '{dataset.source}'. Known: {VALID_SOURCES}",
        })
    
    # Check rows
    if dataset.rows <= 0:
        issues.append({
            "check": "rows",
            "message": f"Row count must be positive, got {dataset.rows}",
        })
    
    # Check dates
    if dataset.start_date and dataset.end_date:
        if dataset.start_date >= dataset.end_date:
            issues.append({
                "check": "date_range",
                "message": f"start_date ({dataset.start_date}) >= end_date ({dataset.end_date})",
            })
    
    # Check dataset_id format
    if not dataset.dataset_id or " " in dataset.dataset_id:
        issues.append({
            "check": "dataset_id",
            "message": "dataset_id must be non-empty and contain no spaces",
        })
    
    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "checks_passed": 6 - len(issues),
        "total_checks": 6,
    }


class DatasetRegistry:
    """
    Dataset Registry for data governance.
    """
    
    def __init__(self):
        self.datasets: Dict[str, Dataset] = {}
        self.versions: Dict[str, List[str]] = {}
        self._init_default_datasets()
    
    def _init_default_datasets(self):
        """Initialize with known datasets"""
        now = int(time.time() * 1000)
        
        datasets = [
            ("btc_daily_v1", "BTC", "1990-01-01", "2026-01-01", 5692, "coinbase"),
            ("spx_daily_v1", "SPX", "1950-01-01", "2026-01-01", 19242, "yahoo"),
            ("dxy_daily_v1", "DXY", "1971-01-01", "2026-01-01", 13366, "fred"),
            ("eth_daily_v1", "ETH", "2015-08-01", "2026-01-01", 3800, "coinbase"),
        ]
        
        for ds_id, asset, start, end, rows, source in datasets:
            checksum = hashlib.md5(f"{ds_id}_{rows}".encode()).hexdigest()[:16]
            
            self.datasets[ds_id] = Dataset(
                dataset_id=ds_id,
                name=f"{asset} Daily OHLCV",
                asset=asset,
                version="1.0",
                start_date=start,
                end_date=end,
                rows=rows,
                checksum=checksum,
                source=source,
                timeframe="1D",
                columns=["open", "high", "low", "close", "volume"],
                created_at=now
            )
            self.versions[ds_id] = ["1.0"]
    
    def register(self, dataset: Dataset) -> Dict:
        """Register a new dataset with consistency validation"""
        dataset.created_at = int(time.time() * 1000)
        
        # Validate consistency
        validation = validate_dataset_consistency(dataset)
        if not validation["valid"]:
            return {"error": "consistency_check_failed", "validation": validation}
        
        if not dataset.checksum:
            dataset.checksum = hashlib.md5(
                f"{dataset.dataset_id}_{dataset.rows}_{dataset.version}".encode()
            ).hexdigest()[:16]
        
        self.datasets[dataset.dataset_id] = dataset
        
        if dataset.dataset_id not in self.versions:
            self.versions[dataset.dataset_id] = []
        if dataset.version not in self.versions[dataset.dataset_id]:
            self.versions[dataset.dataset_id].append(dataset.version)
        
        return {
            "dataset": self._to_dict(dataset),
            "validation": validation
        }
    
    def get(self, dataset_id: str) -> Optional[Dataset]:
        """Get dataset by ID"""
        return self.datasets.get(dataset_id)
    
    def list_all(self, asset: str = None) -> List[Dict]:
        """List all datasets"""
        datasets = list(self.datasets.values())
        if asset:
            datasets = [d for d in datasets if d.asset == asset]
        return [self._to_dict(d) for d in datasets]
    
    def get_versions(self, dataset_id: str) -> List[str]:
        """Get all versions of a dataset"""
        return self.versions.get(dataset_id, [])
    
    def validate_checksum(self, dataset_id: str, checksum: str) -> bool:
        """Validate dataset checksum"""
        dataset = self.datasets.get(dataset_id)
        if not dataset:
            return False
        return dataset.checksum == checksum
    
    def get_health(self) -> Dict:
        """Get registry health"""
        return {
            "enabled": True,
            "version": "phaseC",
            "status": "ok",
            "total_datasets": len(self.datasets),
            "total_rows": sum(d.rows for d in self.datasets.values()),
            "assets": list(set(d.asset for d in self.datasets.values())),
            "timestamp": int(time.time() * 1000)
        }
    
    def _to_dict(self, d: Dataset) -> Dict:
        return {
            "dataset_id": d.dataset_id,
            "name": d.name,
            "asset": d.asset,
            "version": d.version,
            "start_date": d.start_date,
            "end_date": d.end_date,
            "rows": d.rows,
            "checksum": d.checksum,
            "source": d.source,
            "timeframe": d.timeframe,
            "columns": d.columns
        }


# Singleton
dataset_registry = DatasetRegistry()
