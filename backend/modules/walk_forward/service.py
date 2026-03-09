"""
Walk-Forward Service
====================

Main service for walk-forward simulation.
Handles data loading, engine execution, and comparison runs.
"""

import time
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pymongo import MongoClient
from dataclasses import asdict

from .types import (
    Candle, WalkForwardConfig, WalkForwardResult,
    SimulationMode, DecadeMetrics, RegimeMetrics, StrategyMetrics
)
from .engine import WalkForwardEngine


class WalkForwardService:
    """Walk-Forward Simulation Service"""
    
    def __init__(self):
        self.mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        self.db_name = os.environ.get("DB_NAME", "ta_engine")
        self.client = None
        self.db = None
        
        # Results storage
        self.results: Dict[str, WalkForwardResult] = {}
        self.comparison_results: Dict[str, Dict[str, WalkForwardResult]] = {}
    
    def _connect(self):
        """Connect to MongoDB"""
        if self.client is None:
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client[self.db_name]
    
    def _load_candles(self, asset: str, timeframe: str = "1d") -> List[Candle]:
        """Load candles from MongoDB"""
        self._connect()
        
        candles_collection = self.db["candles"]
        
        cursor = candles_collection.find(
            {"symbol": asset, "timeframe": timeframe},
            {"_id": 0}
        ).sort("timestamp", 1)
        
        candles = []
        for doc in cursor:
            candles.append(Candle(
                timestamp=doc["timestamp"],
                open=doc["open"],
                high=doc["high"],
                low=doc["low"],
                close=doc["close"],
                volume=doc.get("volume", 0)
            ))
        
        return candles
    
    def run_simulation(
        self,
        asset: str = "SPX",
        timeframe: str = "1d",
        mode: str = "full_system",
        initial_capital: float = 100000.0,
        warmup_bars: int = 500,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """Run a single walk-forward simulation"""
        
        # Load candles
        candles = self._load_candles(asset, timeframe)
        
        if not candles:
            return {"error": f"No candles found for {asset}/{timeframe}"}
        
        print(f"[WalkForward] Loaded {len(candles)} candles for {asset}")
        
        # Filter by date if specified
        if start_date:
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
            candles = [c for c in candles if c.timestamp >= start_ts]
        
        if end_date:
            end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
            candles = [c for c in candles if c.timestamp <= end_ts]
        
        if len(candles) < warmup_bars + 100:
            return {"error": f"Not enough candles: {len(candles)} < {warmup_bars + 100}"}
        
        # Create config
        config = WalkForwardConfig(
            asset=asset,
            timeframe=timeframe,
            mode=SimulationMode(mode),
            initial_capital=initial_capital,
            warmup_bars=warmup_bars
        )
        
        # Run engine
        engine = WalkForwardEngine(config)
        result = engine.run(candles)
        
        # Store result
        self.results[result.run_id] = result
        
        # Save to MongoDB
        self._save_result(result)
        
        return self._result_to_dict(result)
    
    def run_comparison(
        self,
        asset: str = "SPX",
        timeframe: str = "1d",
        initial_capital: float = 100000.0,
        warmup_bars: int = 500
    ) -> Dict[str, Any]:
        """Run 4 comparison runs for baseline analysis"""
        
        modes = [
            ("full_system", "Full System"),
            ("no_meta", "Without Meta-Strategy"),
            ("no_healing", "Without Self-Healing"),
            ("core_only", "Core Strategies Only")
        ]
        
        comparison_id = f"comparison_{asset}_{int(time.time())}"
        results = {}
        
        for mode, label in modes:
            print(f"\n[Comparison] Running: {label}")
            
            result = self.run_simulation(
                asset=asset,
                timeframe=timeframe,
                mode=mode,
                initial_capital=initial_capital,
                warmup_bars=warmup_bars
            )
            
            if "error" in result:
                return result
            
            results[mode] = result
        
        # Store comparison
        self.comparison_results[comparison_id] = results
        
        # Generate comparison summary
        summary = self._generate_comparison_summary(results)
        
        return {
            "comparison_id": comparison_id,
            "asset": asset,
            "timeframe": timeframe,
            "results": results,
            "summary": summary
        }
    
    def _generate_comparison_summary(self, results: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate comparison summary between runs"""
        summary = {
            "metrics_comparison": {},
            "layer_contribution": {},
            "insights": []
        }
        
        # Compare metrics
        metrics = ["profit_factor", "win_rate", "sharpe", "max_drawdown_pct", "cagr"]
        
        for metric in metrics:
            summary["metrics_comparison"][metric] = {
                mode: result.get(metric, 0) 
                for mode, result in results.items()
            }
        
        # Calculate layer contributions
        full = results.get("full_system", {})
        no_meta = results.get("no_meta", {})
        no_healing = results.get("no_healing", {})
        core = results.get("core_only", {})
        
        if full and no_meta:
            meta_contribution = full.get("profit_factor", 0) - no_meta.get("profit_factor", 0)
            summary["layer_contribution"]["meta_strategy"] = round(meta_contribution, 3)
            
            if meta_contribution > 0.1:
                summary["insights"].append(f"Meta-Strategy adds +{meta_contribution:.2f} to Profit Factor")
            elif meta_contribution < -0.1:
                summary["insights"].append(f"Meta-Strategy hurts PF by {meta_contribution:.2f}")
        
        if full and no_healing:
            healing_contribution = full.get("profit_factor", 0) - no_healing.get("profit_factor", 0)
            summary["layer_contribution"]["self_healing"] = round(healing_contribution, 3)
            
            if healing_contribution > 0.1:
                summary["insights"].append(f"Self-Healing adds +{healing_contribution:.2f} to Profit Factor")
        
        if full and core:
            tactical_contribution = full.get("profit_factor", 0) - core.get("profit_factor", 0)
            summary["layer_contribution"]["tactical_strategies"] = round(tactical_contribution, 3)
            
            if tactical_contribution > 0.1:
                summary["insights"].append(f"Tactical strategies add +{tactical_contribution:.2f} to PF")
            elif tactical_contribution < 0:
                summary["insights"].append("Core strategies outperform full portfolio")
        
        # Best mode
        best_pf = 0
        best_mode = ""
        for mode, result in results.items():
            pf = result.get("profit_factor", 0)
            if pf > best_pf:
                best_pf = pf
                best_mode = mode
        
        summary["best_mode"] = best_mode
        summary["insights"].append(f"Best mode: {best_mode} with PF={best_pf:.2f}")
        
        return summary
    
    def _save_result(self, result: WalkForwardResult):
        """Save result to MongoDB"""
        self._connect()
        
        collection = self.db["walk_forward_results"]
        
        # Convert to dict
        result_dict = self._result_to_dict(result)
        result_dict["_id"] = result.run_id
        
        collection.replace_one(
            {"_id": result.run_id},
            result_dict,
            upsert=True
        )
    
    def get_result(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get result by run_id"""
        if run_id in self.results:
            return self._result_to_dict(self.results[run_id])
        
        # Try from MongoDB
        self._connect()
        collection = self.db["walk_forward_results"]
        doc = collection.find_one({"_id": run_id})
        
        if doc:
            del doc["_id"]
            return doc
        
        return None
    
    def list_results(self, asset: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent results"""
        self._connect()
        collection = self.db["walk_forward_results"]
        
        query = {}
        if asset:
            query["config.asset"] = asset
        
        cursor = collection.find(
            query,
            {"_id": 0, "equity_curve": 0, "daily_results": 0}
        ).sort("completed_at", -1).limit(limit)
        
        return list(cursor)
    
    def _result_to_dict(self, result: WalkForwardResult) -> Dict[str, Any]:
        """Convert WalkForwardResult to dict"""
        # Convert config
        config_dict = {
            "asset": result.config.asset,
            "timeframe": result.config.timeframe,
            "mode": result.config.mode.value,
            "initial_capital": result.config.initial_capital,
            "warmup_bars": result.config.warmup_bars,
            "max_positions": result.config.max_positions,
            "position_size_pct": result.config.position_size_pct,
            "slippage_bps": result.config.slippage_bps,
            "fee_bps": result.config.fee_bps,
            "rebalance_frequency": result.config.rebalance_frequency
        }
        
        # Convert decade metrics
        decade_metrics = []
        for dm in result.decade_metrics:
            decade_metrics.append({
                "decade": dm.decade,
                "start_year": dm.start_year,
                "end_year": dm.end_year,
                "trades": dm.trades,
                "win_rate": dm.win_rate,
                "profit_factor": dm.profit_factor,
                "total_return": dm.total_return,
                "avg_r": dm.avg_r,
                "best_strategy": dm.best_strategy,
                "worst_strategy": dm.worst_strategy
            })
        
        # Convert regime metrics
        regime_metrics = []
        for rm in result.regime_metrics:
            regime_metrics.append({
                "regime": rm.regime,
                "trades": rm.trades,
                "win_rate": rm.win_rate,
                "profit_factor": rm.profit_factor,
                "avg_r": rm.avg_r,
                "active_strategies": rm.active_strategies,
                "family_performance": rm.family_performance
            })
        
        # Convert strategy metrics
        strategy_metrics = []
        for sm in result.strategy_metrics:
            strategy_metrics.append({
                "strategy_id": sm.strategy_id,
                "status": sm.status,
                "trades": sm.trades,
                "win_rate": sm.win_rate,
                "profit_factor": sm.profit_factor,
                "avg_r": sm.avg_r,
                "contribution_pct": sm.contribution_pct,
                "demotions": sm.demotions,
                "promotions": sm.promotions,
                "healing_events": sm.healing_events
            })
        
        # Convert failures
        failures = []
        for fe in result.failure_events:
            failures.append({
                "timestamp": fe.timestamp,
                "type": fe.type,
                "strategy_id": fe.strategy_id,
                "description": fe.description,
                "loss_amount": fe.loss_amount,
                "regime": fe.regime,
                "decade": fe.decade
            })
        
        return {
            "run_id": result.run_id,
            "config": config_dict,
            "mode": result.mode,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            
            "total_trades": result.total_trades,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "sharpe": result.sharpe,
            "sortino": result.sortino,
            "calmar": result.calmar,
            "max_drawdown": result.max_drawdown,
            "max_drawdown_pct": result.max_drawdown_pct,
            "total_return": result.total_return,
            "cagr": result.cagr,
            "expectancy": result.expectancy,
            "max_losing_streak": result.max_losing_streak,
            "avg_recovery_bars": result.avg_recovery_bars,
            
            "final_equity": result.final_equity,
            "peak_equity": result.peak_equity,
            
            "decade_metrics": decade_metrics,
            "regime_metrics": regime_metrics,
            "strategy_metrics": strategy_metrics,
            
            "governance_events": result.governance_events,
            "healing_events": result.healing_events,
            "kill_switch_events": result.kill_switch_events,
            "meta_reallocations": result.meta_reallocations,
            
            "failure_events": failures,
            "equity_curve": result.equity_curve[-1000:] if result.equity_curve else [],  # Limit for storage
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.3",
            "status": "ok",
            "results_cached": len(self.results),
            "comparisons_cached": len(self.comparison_results),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
