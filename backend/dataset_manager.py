#!/usr/bin/env python3
"""
Dataset Manager v1
==================

Управление каноническими датасетами для TA Engine.

Функции:
- Merge и дедупликация исторических данных
- Dataset freeze с версионированием
- Metadata generation и validation
- Gap detection

Usage:
    python dataset_manager.py --merge-btc     # Merge BTC datasets
    python dataset_manager.py --freeze        # Create versioned snapshots
    python dataset_manager.py --validate      # Check data integrity
    python dataset_manager.py --status        # Show dataset info
"""

import os
import sys
import json
import csv
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import argparse

PROJECT_ROOT = Path(__file__).parent

# Source directories
BOOTSTRAP_DIR = PROJECT_ROOT / "data" / "fractal" / "bootstrap"
DATASETS_DIR = PROJECT_ROOT / "datasets"

# Source files
BTC_LEGACY_FILE = BOOTSTRAP_DIR / "BTC_legacy_2010.csv"
BTC_MODERN_FILE = BOOTSTRAP_DIR / "BTCUSD_daily.csv"
SPX_FILE = BOOTSTRAP_DIR / "spx_stooq_seed.csv"
DXY_FILE = BOOTSTRAP_DIR / "dxy_extended_seed.csv"


class DatasetManager:
    """Manages canonical datasets for TA Engine"""
    
    def __init__(self):
        DATASETS_DIR.mkdir(exist_ok=True)
    
    # ═══════════════════════════════════════════════════════════════
    # CSV Parsing (different formats)
    # ═══════════════════════════════════════════════════════════════
    
    def _parse_investing_format(self, filepath: Path) -> List[dict]:
        """Parse Investing.com format: Date,Price,Open,High,Low,Vol.,Change %"""
        records = []
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    date_str = row.get('Date', '').strip('"')
                    if not date_str:
                        continue
                    
                    # Parse "Jul 18, 2010" format
                    dt = datetime.strptime(date_str, '%b %d, %Y')
                    date_iso = dt.strftime('%Y-%m-%d')
                    
                    def parse_num(s):
                        return float(s.strip('"').replace(',', ''))
                    
                    records.append({
                        'date': date_iso,
                        'open': parse_num(row.get('Open', '0')),
                        'high': parse_num(row.get('High', '0')),
                        'low': parse_num(row.get('Low', '0')),
                        'close': parse_num(row.get('Price', '0')),  # Price = Close
                        'volume': 0,  # Vol. is in K format, skip for now
                    })
                except Exception as e:
                    continue
        
        return records
    
    def _parse_cryptodata_format(self, filepath: Path) -> List[dict]:
        """Parse CryptoDataDownload format: unix,date,symbol,open,high,low,close,Volume BTC,Volume USD"""
        records = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Skip URL comment line
            data_lines = [l for l in lines if not l.startswith('http')]
        
        reader = csv.DictReader(data_lines)
        for row in reader:
            try:
                date_str = row.get('date', '')
                if not date_str:
                    continue
                
                # Parse "2026-02-15 00:00:00" format
                dt = datetime.strptime(date_str.split()[0], '%Y-%m-%d')
                date_iso = dt.strftime('%Y-%m-%d')
                
                records.append({
                    'date': date_iso,
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row.get('Volume USD', 0)),
                })
            except Exception as e:
                continue
        
        return records
    
    def _parse_stooq_format(self, filepath: Path) -> List[dict]:
        """Parse Stooq format: Date,Open,High,Low,Close,Volume"""
        records = []
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    date_str = row.get('Date', row.get('date', ''))
                    if not date_str:
                        continue
                    
                    # Try different date formats
                    dt = None
                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                        try:
                            dt = datetime.strptime(date_str.split()[0], fmt)
                            break
                        except:
                            continue
                    
                    if not dt:
                        continue
                    
                    date_iso = dt.strftime('%Y-%m-%d')
                    
                    records.append({
                        'date': date_iso,
                        'open': float(row.get('Open', row.get('open', 0))),
                        'high': float(row.get('High', row.get('high', 0))),
                        'low': float(row.get('Low', row.get('low', 0))),
                        'close': float(row.get('Close', row.get('close', 0))),
                        'volume': float(row.get('Volume', row.get('volume', 0))),
                    })
                except:
                    continue
        
        return records
    
    # ═══════════════════════════════════════════════════════════════
    # BTC Merge Logic
    # ═══════════════════════════════════════════════════════════════
    
    def merge_btc_datasets(self) -> Tuple[bool, str]:
        """
        Merge BTC_legacy_2010.csv (2010-2020) and BTCUSD_daily.csv (2014-2026)
        into one canonical dataset.
        
        Algorithm:
        1. Load both datasets
        2. Normalize format
        3. Merge
        4. Deduplicate by date (keep newer source for overlapping dates)
        5. Sort by date
        6. Validate continuity
        
        Returns: (success, message)
        """
        print("\n" + "=" * 60)
        print("BTC DATASET MERGE")
        print("=" * 60)
        
        # Check source files exist
        if not BTC_LEGACY_FILE.exists():
            return False, f"Legacy file not found: {BTC_LEGACY_FILE}"
        
        if not BTC_MODERN_FILE.exists():
            return False, f"Modern file not found: {BTC_MODERN_FILE}"
        
        # Load datasets
        print("\n1. Loading source files...")
        
        legacy_records = self._parse_investing_format(BTC_LEGACY_FILE)
        print(f"   Legacy (2010-2020): {len(legacy_records)} records")
        
        modern_records = self._parse_cryptodata_format(BTC_MODERN_FILE)
        print(f"   Modern (2014-2026): {len(modern_records)} records")
        
        if not legacy_records or not modern_records:
            return False, "Failed to parse source files"
        
        # Create date-keyed dict (modern data takes priority for overlaps)
        print("\n2. Merging with deduplication...")
        
        merged = {}
        
        # Add legacy first
        for r in legacy_records:
            merged[r['date']] = r
        
        legacy_only_count = len(merged)
        
        # Modern overwrites overlapping dates (newer/better data)
        overlap_count = 0
        for r in modern_records:
            if r['date'] in merged:
                overlap_count += 1
            merged[r['date']] = r
        
        print(f"   Legacy-only dates: {legacy_only_count - overlap_count}")
        print(f"   Overlapping dates: {overlap_count}")
        print(f"   Modern-only dates: {len(modern_records) - overlap_count}")
        print(f"   Total unique dates: {len(merged)}")
        
        # Sort by date
        print("\n3. Sorting...")
        sorted_records = sorted(merged.values(), key=lambda x: x['date'])
        
        # Validate
        print("\n4. Validating...")
        
        min_date = sorted_records[0]['date']
        max_date = sorted_records[-1]['date']
        
        print(f"   Date range: {min_date} to {max_date}")
        
        # Check for gaps
        gaps = self._find_gaps(sorted_records)
        
        if gaps:
            print(f"   WARNING: Found {len(gaps)} gaps (weekends/holidays expected)")
            # Show only significant gaps (> 5 days)
            significant_gaps = [g for g in gaps if g['days'] > 5]
            if significant_gaps:
                print(f"   Significant gaps (> 5 days): {len(significant_gaps)}")
                for g in significant_gaps[:5]:
                    print(f"      {g['start']} -> {g['end']} ({g['days']} days)")
        else:
            print("   No gaps found")
        
        # Save merged dataset
        print("\n5. Saving merged dataset...")
        
        output_file = DATASETS_DIR / "btc_daily_v1.csv"
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'open', 'high', 'low', 'close', 'volume'])
            writer.writeheader()
            writer.writerows(sorted_records)
        
        print(f"   Saved: {output_file}")
        print(f"   Records: {len(sorted_records)}")
        
        # Generate checksum
        checksum = self._calculate_checksum(output_file)
        print(f"   SHA256: {checksum[:16]}...")
        
        return True, f"Merged {len(sorted_records)} records from {min_date} to {max_date}"
    
    def _find_gaps(self, records: List[dict]) -> List[dict]:
        """Find gaps in date sequence (excluding weekends for non-crypto)"""
        gaps = []
        
        for i in range(1, len(records)):
            prev_date = datetime.strptime(records[i-1]['date'], '%Y-%m-%d')
            curr_date = datetime.strptime(records[i]['date'], '%Y-%m-%d')
            
            diff = (curr_date - prev_date).days
            
            # BTC trades 24/7, so any gap > 1 day is notable
            if diff > 1:
                gaps.append({
                    'start': records[i-1]['date'],
                    'end': records[i]['date'],
                    'days': diff
                })
        
        return gaps
    
    # ═══════════════════════════════════════════════════════════════
    # Dataset Freeze (versioned snapshots)
    # ═══════════════════════════════════════════════════════════════
    
    def freeze_datasets(self) -> Tuple[bool, Dict]:
        """
        Create versioned dataset snapshots with metadata.
        
        Creates:
        - datasets/btc_daily_v1.csv (if not exists, creates from merge)
        - datasets/spx_daily_v1.csv
        - datasets/dxy_daily_v1.csv
        - datasets/metadata.json
        """
        print("\n" + "=" * 60)
        print("DATASET FREEZE")
        print("=" * 60)
        
        metadata = {
            "version": "v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "datasets": {}
        }
        
        # BTC
        btc_file = DATASETS_DIR / "btc_daily_v1.csv"
        if not btc_file.exists():
            print("\nBTC dataset not found, running merge first...")
            success, msg = self.merge_btc_datasets()
            if not success:
                return False, {"error": msg}
        
        btc_meta = self._create_dataset_metadata(btc_file, "BTC", "Merged: BTC_legacy_2010 + BTCUSD_daily")
        metadata["datasets"]["btc_daily_v1"] = btc_meta
        print(f"\n✓ BTC: {btc_meta['rows']} rows ({btc_meta['start_date']} to {btc_meta['end_date']})")
        
        # SPX
        if SPX_FILE.exists():
            spx_records = self._parse_stooq_format(SPX_FILE)
            spx_file = DATASETS_DIR / "spx_daily_v1.csv"
            
            with open(spx_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['date', 'open', 'high', 'low', 'close', 'volume'])
                writer.writeheader()
                sorted_records = sorted(spx_records, key=lambda x: x['date'])
                writer.writerows(sorted_records)
            
            spx_meta = self._create_dataset_metadata(spx_file, "SPX", "Source: spx_stooq_seed.csv")
            metadata["datasets"]["spx_daily_v1"] = spx_meta
            print(f"✓ SPX: {spx_meta['rows']} rows ({spx_meta['start_date']} to {spx_meta['end_date']})")
        
        # DXY
        if DXY_FILE.exists():
            dxy_records = self._parse_stooq_format(DXY_FILE)  # Standard format
            dxy_file = DATASETS_DIR / "dxy_daily_v1.csv"
            
            with open(dxy_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['date', 'open', 'high', 'low', 'close', 'volume'])
                writer.writeheader()
                sorted_records = sorted(dxy_records, key=lambda x: x['date'])
                writer.writerows(sorted_records)
            
            dxy_meta = self._create_dataset_metadata(dxy_file, "DXY", "Source: dxy_extended_seed.csv")
            metadata["datasets"]["dxy_daily_v1"] = dxy_meta
            print(f"✓ DXY: {dxy_meta['rows']} rows ({dxy_meta['start_date']} to {dxy_meta['end_date']})")
        
        # Save metadata
        metadata_file = DATASETS_DIR / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n✓ Metadata saved: {metadata_file}")
        
        return True, metadata
    
    def _create_dataset_metadata(self, filepath: Path, symbol: str, source: str) -> dict:
        """Generate metadata for a dataset file"""
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            records = list(reader)
        
        if not records:
            return {}
        
        dates = sorted([r['date'] for r in records])
        
        return {
            "symbol": symbol,
            "source": source,
            "file": filepath.name,
            "rows": len(records),
            "start_date": dates[0],
            "end_date": dates[-1],
            "checksum": self._calculate_checksum(filepath),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _calculate_checksum(self, filepath: Path) -> str:
        """Calculate SHA256 checksum of file"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    # ═══════════════════════════════════════════════════════════════
    # Validation
    # ═══════════════════════════════════════════════════════════════
    
    def validate_datasets(self) -> Tuple[bool, Dict]:
        """Validate all frozen datasets"""
        print("\n" + "=" * 60)
        print("DATASET VALIDATION")
        print("=" * 60)
        
        metadata_file = DATASETS_DIR / "metadata.json"
        
        if not metadata_file.exists():
            return False, {"error": "No metadata.json found. Run --freeze first."}
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        results = {
            "valid": True,
            "datasets": {},
            "errors": []
        }
        
        for dataset_id, meta in metadata.get("datasets", {}).items():
            filepath = DATASETS_DIR / meta["file"]
            
            if not filepath.exists():
                results["valid"] = False
                results["errors"].append(f"{dataset_id}: file not found")
                continue
            
            # Verify checksum
            current_checksum = self._calculate_checksum(filepath)
            stored_checksum = meta.get("checksum", "")
            
            checksum_valid = current_checksum == stored_checksum
            
            # Count rows
            with open(filepath, 'r') as f:
                row_count = sum(1 for _ in f) - 1  # minus header
            
            row_valid = row_count == meta.get("rows", 0)
            
            dataset_valid = checksum_valid and row_valid
            
            results["datasets"][dataset_id] = {
                "file": meta["file"],
                "checksum_valid": checksum_valid,
                "row_count_valid": row_valid,
                "expected_rows": meta.get("rows"),
                "actual_rows": row_count,
                "valid": dataset_valid
            }
            
            if dataset_valid:
                print(f"✓ {dataset_id}: {row_count} rows, checksum OK")
            else:
                print(f"✗ {dataset_id}: INVALID")
                results["valid"] = False
                if not checksum_valid:
                    results["errors"].append(f"{dataset_id}: checksum mismatch")
                if not row_valid:
                    results["errors"].append(f"{dataset_id}: row count mismatch ({row_count} vs {meta.get('rows')})")
        
        return results["valid"], results
    
    # ═══════════════════════════════════════════════════════════════
    # Status
    # ═══════════════════════════════════════════════════════════════
    
    def status(self):
        """Print dataset status"""
        print("\n" + "=" * 60)
        print("DATASET STATUS")
        print("=" * 60)
        
        metadata_file = DATASETS_DIR / "metadata.json"
        
        if not metadata_file.exists():
            print("\n⚠ No frozen datasets found")
            print("  Run: python dataset_manager.py --freeze")
            return
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        print(f"\nVersion: {metadata.get('version', 'unknown')}")
        print(f"Created: {metadata.get('created_at', 'unknown')}")
        
        print("\nDatasets:")
        for dataset_id, meta in metadata.get("datasets", {}).items():
            print(f"\n  {meta.get('symbol', dataset_id)}:")
            print(f"    File: {meta.get('file')}")
            print(f"    Rows: {meta.get('rows')}")
            print(f"    Range: {meta.get('start_date')} to {meta.get('end_date')}")
            print(f"    Checksum: {meta.get('checksum', '')[:16]}...")


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Dataset Manager")
    parser.add_argument("--merge-btc", action="store_true", help="Merge BTC historical datasets")
    parser.add_argument("--freeze", action="store_true", help="Create versioned dataset snapshots")
    parser.add_argument("--validate", action="store_true", help="Validate frozen datasets")
    parser.add_argument("--status", action="store_true", help="Show dataset status")
    args = parser.parse_args()
    
    manager = DatasetManager()
    
    if args.merge_btc:
        success, msg = manager.merge_btc_datasets()
        print(f"\n{'✅' if success else '❌'} {msg}")
    elif args.freeze:
        success, meta = manager.freeze_datasets()
        print(f"\n{'✅ FREEZE COMPLETE' if success else '❌ FREEZE FAILED'}")
    elif args.validate:
        valid, results = manager.validate_datasets()
        print(f"\n{'✅ ALL VALID' if valid else '❌ VALIDATION FAILED'}")
        if results.get("errors"):
            for err in results["errors"]:
                print(f"  - {err}")
    elif args.status:
        manager.status()
    else:
        # Default: show help
        parser.print_help()


if __name__ == "__main__":
    main()
