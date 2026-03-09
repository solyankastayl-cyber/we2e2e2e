"""
Cross-Asset Walk-Forward Service
================================

Service layer for managing walk-forward runs.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from .types import (
    SimMode, WalkForwardRun, WalkForwardReport,
    BatchRunRequest, BatchRunResult, CrossAssetComparison
)
from .engine import cross_asset_engine
from .dataset_registry import dataset_registry
from .asset_adapter import asset_adapter_factory
from .report import ReportGenerator


class CrossAssetWalkForwardService:
    """
    Service for cross-asset walk-forward operations.
    
    Provides:
    - Single asset runs
    - Batch multi-asset runs
    - Comparison reports
    - Status monitoring
    """
    
    def __init__(self):
        self.batch_runs: Dict[str, BatchRunResult] = {}
    
    # ============================================
    # Single Run Operations
    # ============================================
    
    async def start_run(
        self,
        asset: str,
        mode: str = "full_system",
        start_date: str = "",
        end_date: str = "",
        initial_capital: float = 100000.0
    ) -> Dict:
        """Start a single walk-forward run"""
        try:
            # Parse mode
            sim_mode = SimMode(mode)
        except ValueError:
            sim_mode = SimMode.FULL_SYSTEM
        
        # Create run
        run = cross_asset_engine.create_run(
            asset=asset,
            mode=sim_mode,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        # Execute asynchronously
        asyncio.create_task(self._execute_run_async(run.run_id))
        
        return {
            "run_id": run.run_id,
            "asset": run.asset,
            "mode": run.mode.value,
            "status": run.status.value,
            "message": "Run started"
        }
    
    async def _execute_run_async(self, run_id: str):
        """Execute run asynchronously"""
        try:
            await cross_asset_engine.execute_run(run_id)
        except Exception as e:
            print(f"[CrossAsset] Run {run_id} failed: {e}")
    
    async def run_sync(
        self,
        asset: str,
        mode: str = "full_system",
        start_date: str = "",
        end_date: str = "",
        initial_capital: float = 100000.0
    ) -> Dict:
        """Run walk-forward synchronously and return results"""
        try:
            sim_mode = SimMode(mode)
        except ValueError:
            sim_mode = SimMode.FULL_SYSTEM
        
        run = cross_asset_engine.create_run(
            asset=asset,
            mode=sim_mode,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital
        )
        
        report = await cross_asset_engine.execute_run(run.run_id)
        
        return ReportGenerator.to_json(report)
    
    def get_run_status(self, run_id: str) -> Optional[Dict]:
        """Get run status"""
        run = cross_asset_engine.get_run(run_id)
        if not run:
            return None
        
        return {
            "run_id": run.run_id,
            "asset": run.asset,
            "mode": run.mode.value,
            "status": run.status.value,
            "progress_pct": round(run.progress_pct * 100, 1),
            "current_bar": run.current_bar,
            "total_bars": run.total_bars,
            "error_message": run.error_message if run.error_message else None
        }
    
    def get_report(self, run_id: str) -> Optional[Dict]:
        """Get report as JSON"""
        report = cross_asset_engine.get_report(run_id)
        if not report:
            return None
        return ReportGenerator.to_json(report)
    
    def get_report_markdown(self, run_id: str) -> Optional[str]:
        """Get report as Markdown"""
        report = cross_asset_engine.get_report(run_id)
        if not report:
            return None
        return ReportGenerator.to_markdown(report)
    
    # ============================================
    # Batch Operations
    # ============================================
    
    async def start_batch_run(
        self,
        assets: List[str],
        mode: str = "full_system",
        end_date: str = "",
        initial_capital: float = 100000.0
    ) -> Dict:
        """Start batch run across multiple assets"""
        batch_id = f"batch_{int(time.time())}"
        
        # Get default start dates
        start_dates = dataset_registry.get_batch_start_dates(assets)
        
        batch_result = BatchRunResult(
            batch_id=batch_id,
            total_assets=len(assets),
            status="RUNNING",
            started_at=int(time.time() * 1000)
        )
        
        self.batch_runs[batch_id] = batch_result
        
        # Start async execution
        asyncio.create_task(
            self._execute_batch_async(
                batch_id, assets, mode, start_dates, end_date, initial_capital
            )
        )
        
        return {
            "batch_id": batch_id,
            "assets": assets,
            "mode": mode,
            "status": "RUNNING",
            "message": f"Batch started for {len(assets)} assets"
        }
    
    async def _execute_batch_async(
        self,
        batch_id: str,
        assets: List[str],
        mode: str,
        start_dates: Dict[str, str],
        end_date: str,
        initial_capital: float
    ):
        """Execute batch runs"""
        batch = self.batch_runs.get(batch_id)
        if not batch:
            return
        
        try:
            sim_mode = SimMode(mode)
        except ValueError:
            sim_mode = SimMode.FULL_SYSTEM
        
        for asset in assets:
            try:
                start_date = start_dates.get(asset, "")
                
                run = cross_asset_engine.create_run(
                    asset=asset,
                    mode=sim_mode,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital
                )
                
                batch.run_ids[asset] = run.run_id
                
                await cross_asset_engine.execute_run(run.run_id)
                batch.completed_assets += 1
                
            except Exception as e:
                print(f"[CrossAsset] Batch {batch_id} - Asset {asset} failed: {e}")
                batch.failed_assets += 1
        
        # Generate summary
        batch.summary_table = self._generate_batch_summary(batch.run_ids)
        batch.status = "COMPLETED"
        batch.completed_at = int(time.time() * 1000)
    
    def _generate_batch_summary(self, run_ids: Dict[str, str]) -> List[Dict]:
        """Generate summary table for batch"""
        summary = []
        
        for asset, run_id in run_ids.items():
            report = cross_asset_engine.get_report(run_id)
            if report:
                summary.append({
                    "asset": asset,
                    "asset_class": report.asset_class,
                    "trades": report.trade_metrics.total_trades,
                    "win_rate": round(report.trade_metrics.win_rate, 4),
                    "profit_factor": round(report.trade_metrics.profit_factor, 2),
                    "sharpe": round(report.portfolio_metrics.sharpe, 2),
                    "cagr": round(report.portfolio_metrics.cagr, 4),
                    "max_dd": round(report.portfolio_metrics.max_drawdown_pct, 4),
                    "final_equity": round(report.portfolio_metrics.final_equity, 2)
                })
        
        return summary
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Get batch run status"""
        batch = self.batch_runs.get(batch_id)
        if not batch:
            return None
        
        return {
            "batch_id": batch.batch_id,
            "status": batch.status,
            "total_assets": batch.total_assets,
            "completed_assets": batch.completed_assets,
            "failed_assets": batch.failed_assets,
            "progress_pct": round(
                (batch.completed_assets + batch.failed_assets) / batch.total_assets * 100, 1
            ) if batch.total_assets > 0 else 0,
            "run_ids": batch.run_ids
        }
    
    def get_batch_summary(self, batch_id: str) -> Optional[Dict]:
        """Get batch summary"""
        batch = self.batch_runs.get(batch_id)
        if not batch:
            return None
        
        return {
            "batch_id": batch.batch_id,
            "status": batch.status,
            "summary_table": batch.summary_table,
            "completed_at": batch.completed_at
        }
    
    # ============================================
    # Comparison Operations
    # ============================================
    
    def generate_comparison(self, batch_id: str) -> Optional[Dict]:
        """Generate cross-asset comparison from batch"""
        batch = self.batch_runs.get(batch_id)
        if not batch or batch.status != "COMPLETED":
            return None
        
        # Collect reports
        reports = []
        for asset, run_id in batch.run_ids.items():
            report = cross_asset_engine.get_report(run_id)
            if report:
                reports.append(report)
        
        if not reports:
            return None
        
        # Generate comparison
        comparison = ReportGenerator.generate_comparison_report(
            reports, "full_system"
        )
        
        return {
            "comparison_id": comparison.comparison_id,
            "assets": comparison.assets,
            "mode": comparison.mode,
            "metrics_matrix": comparison.metrics_matrix,
            "sharpe_ranking": comparison.sharpe_ranking,
            "pf_ranking": comparison.pf_ranking,
            "cagr_ranking": comparison.cagr_ranking,
            "universal_edge": comparison.universal_edge,
            "universal_edge_confidence": round(comparison.universal_edge_confidence, 2)
        }
    
    def get_comparison_markdown(self, batch_id: str) -> Optional[str]:
        """Get comparison as Markdown"""
        batch = self.batch_runs.get(batch_id)
        if not batch or batch.status != "COMPLETED":
            return None
        
        reports = []
        for run_id in batch.run_ids.values():
            report = cross_asset_engine.get_report(run_id)
            if report:
                reports.append(report)
        
        if not reports:
            return None
        
        comparison = ReportGenerator.generate_comparison_report(reports, "full_system")
        return ReportGenerator.comparison_to_markdown(comparison)
    
    # ============================================
    # Registry Operations
    # ============================================
    
    def get_supported_assets(self) -> Dict:
        """Get all supported assets"""
        return dataset_registry.to_dict()
    
    def get_asset_info(self, asset: str) -> Optional[Dict]:
        """Get info for specific asset"""
        dataset = dataset_registry.get(asset)
        adapter = asset_adapter_factory.get(asset)
        
        if not dataset:
            return None
        
        result = {
            "asset": asset,
            "asset_class": dataset.asset_class.value,
            "start_date": dataset.start_date,
            "end_date": dataset.end_date,
            "total_bars": dataset.total_bars,
            "has_volume": dataset.has_volume
        }
        
        if adapter:
            result["adapter"] = {
                "trading_calendar": adapter.trading_calendar.value,
                "allow_shorts": adapter.allow_shorts,
                "structural_bias_allowed": adapter.structural_bias_allowed,
                "default_fee_bps": adapter.default_fee_bps,
                "demote_winrate_threshold": adapter.demote_winrate_threshold,
                "promote_winrate_threshold": adapter.promote_winrate_threshold
            }
        
        return result
    
    def list_runs(self) -> List[Dict]:
        """List all runs"""
        return cross_asset_engine.list_runs()


# Singleton instance
cross_asset_service = CrossAssetWalkForwardService()
