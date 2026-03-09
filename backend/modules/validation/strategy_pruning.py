"""
Phase 8.8 — Strategy Pruning
Formal strategy lifecycle management.

Strategy Status Categories:
- APPROVED: Production ready, validated across regimes
- LIMITED: Conditional use (specific regimes/TFs only)
- TESTING: Under validation, not for production
- DEPRECATED: Proven weak, removed from routing

Key Metrics for Classification:
- Win Rate (WR)
- Profit Factor (PF)
- Max Drawdown (DD)
- Sharpe Ratio
- Regime Sensitivity
- TF Stability
"""

import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class StrategyStatus(Enum):
    APPROVED = "APPROVED"
    LIMITED = "LIMITED"
    TESTING = "TESTING"
    DEPRECATED = "DEPRECATED"


@dataclass
class StrategyMetrics:
    """Performance metrics for a strategy"""
    strategy_id: str
    win_rate: float
    profit_factor: float
    avg_r: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int
    
    # Regime performance
    trend_up_wr: float = 0.0
    trend_down_wr: float = 0.0
    range_wr: float = 0.0
    
    # TF performance
    tf_1d_wr: float = 0.0
    tf_4h_wr: float = 0.0
    tf_1h_wr: float = 0.0
    
    # Computed fields
    regime_stable: bool = False
    tf_stable: bool = False


@dataclass
class StrategyClassification:
    """Strategy classification result"""
    strategy_id: str
    status: StrategyStatus
    reason: str
    metrics: StrategyMetrics
    
    # Conditions (for LIMITED status)
    allowed_regimes: List[str] = field(default_factory=list)
    allowed_timeframes: List[str] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# Strategy Thresholds
# ═══════════════════════════════════════════════════════════════

PRUNING_THRESHOLDS = {
    # APPROVED thresholds
    "approved": {
        "min_win_rate": 0.55,
        "min_profit_factor": 1.3,
        "min_avg_r": 0.10,
        "max_drawdown": 0.25,
        "min_sharpe": 0.8,
        "min_trades": 50,
        "regime_variance": 0.10,  # max WR difference across regimes
        "tf_variance": 0.10,      # max WR difference across TFs
    },
    
    # LIMITED thresholds (conditional use)
    "limited": {
        "min_win_rate": 0.50,
        "min_profit_factor": 1.1,
        "min_avg_r": 0.0,
        "max_drawdown": 0.35,
        "min_trades": 30,
    },
    
    # DEPRECATED triggers (any of these = deprecated)
    "deprecated": {
        "max_win_rate": 0.48,     # Below this = deprecated
        "max_profit_factor": 1.0, # Below this = deprecated
        "min_avg_r": -0.10,       # Below this = deprecated
    }
}


# ═══════════════════════════════════════════════════════════════
# Known Strategy Data (from Phase 8.7 validation)
# ═══════════════════════════════════════════════════════════════

STRATEGY_BASELINE_DATA = {
    # DEPRECATED - Confirmed weak in Phase 8.7
    "LIQUIDITY_SWEEP": {
        "win_rate": 0.43,
        "profit_factor": 0.85,
        "avg_r": -0.24,
        "max_drawdown": 0.38,
        "sharpe_ratio": -0.15,
        "total_trades": 180,
        "trend_up_wr": 0.45,
        "trend_down_wr": 0.42,
        "range_wr": 0.41,
        "status_override": "DEPRECATED",
        "reason": "Phase 8.7: Confirmed weak (WR 37-46%, negative avgR)"
    },
    "LIQUIDITY_SWEEP_HIGH": {
        "win_rate": 0.44,
        "profit_factor": 0.88,
        "avg_r": -0.22,
        "max_drawdown": 0.36,
        "sharpe_ratio": -0.12,
        "total_trades": 85,
        "status_override": "DEPRECATED",
        "reason": "Phase 8.7: Variant of LIQUIDITY_SWEEP, same issues"
    },
    "LIQUIDITY_SWEEP_LOW": {
        "win_rate": 0.42,
        "profit_factor": 0.82,
        "avg_r": -0.28,
        "max_drawdown": 0.40,
        "sharpe_ratio": -0.18,
        "total_trades": 78,
        "status_override": "DEPRECATED",
        "reason": "Phase 8.7: Variant of LIQUIDITY_SWEEP, same issues"
    },
    "RANGE_REVERSAL": {
        "win_rate": 0.38,
        "profit_factor": 0.72,
        "avg_r": -0.45,
        "max_drawdown": 0.42,
        "sharpe_ratio": -0.35,
        "total_trades": 150,
        "trend_up_wr": 0.35,
        "trend_down_wr": 0.36,
        "range_wr": 0.42,
        "status_override": "DEPRECATED",
        "reason": "Phase 8.7: Confirmed weak (WR 34-38%, worst avgR)"
    },
    
    # APPROVED - Strong performers
    "MTF_BREAKOUT": {
        "win_rate": 0.64,
        "profit_factor": 2.1,
        "avg_r": 0.36,
        "max_drawdown": 0.15,
        "sharpe_ratio": 1.8,
        "total_trades": 210,
        "trend_up_wr": 0.68,
        "trend_down_wr": 0.62,
        "range_wr": 0.52,
        "tf_1d_wr": 0.65,
        "tf_4h_wr": 0.64,
        "tf_1h_wr": 0.62,
    },
    "DOUBLE_BOTTOM": {
        "win_rate": 0.66,
        "profit_factor": 2.3,
        "avg_r": 0.28,
        "max_drawdown": 0.12,
        "sharpe_ratio": 2.0,
        "total_trades": 195,
        "trend_up_wr": 0.70,
        "trend_down_wr": 0.58,
        "range_wr": 0.55,
        "tf_1d_wr": 0.68,
        "tf_4h_wr": 0.65,
        "tf_1h_wr": 0.64,
    },
    "DOUBLE_TOP": {
        "win_rate": 0.63,
        "profit_factor": 2.0,
        "avg_r": 0.25,
        "max_drawdown": 0.14,
        "sharpe_ratio": 1.7,
        "total_trades": 188,
        "trend_up_wr": 0.58,
        "trend_down_wr": 0.68,
        "range_wr": 0.54,
    },
    "CHANNEL_BREAKOUT": {
        "win_rate": 0.58,
        "profit_factor": 1.8,
        "avg_r": 0.26,
        "max_drawdown": 0.18,
        "sharpe_ratio": 1.5,
        "total_trades": 175,
        "trend_up_wr": 0.62,
        "trend_down_wr": 0.60,
        "range_wr": 0.48,
    },
    "MOMENTUM_CONTINUATION": {
        "win_rate": 0.62,
        "profit_factor": 1.9,
        "avg_r": 0.22,
        "max_drawdown": 0.16,
        "sharpe_ratio": 1.6,
        "total_trades": 220,
        "trend_up_wr": 0.68,
        "trend_down_wr": 0.65,
        "range_wr": 0.45,
    },
    
    # LIMITED - Good in specific conditions
    "HEAD_SHOULDERS": {
        "win_rate": 0.52,
        "profit_factor": 1.25,
        "avg_r": 0.08,
        "max_drawdown": 0.22,
        "sharpe_ratio": 0.9,
        "total_trades": 145,
        "trend_up_wr": 0.48,
        "trend_down_wr": 0.58,
        "range_wr": 0.45,
        "tf_1d_wr": 0.56,
        "tf_4h_wr": 0.52,
        "tf_1h_wr": 0.48,
    },
    "HARMONIC_ABCD": {
        "win_rate": 0.54,
        "profit_factor": 1.4,
        "avg_r": 0.12,
        "max_drawdown": 0.20,
        "sharpe_ratio": 1.1,
        "total_trades": 160,
        "trend_up_wr": 0.56,
        "trend_down_wr": 0.55,
        "range_wr": 0.50,
    },
    "WEDGE_RISING": {
        "win_rate": 0.51,
        "profit_factor": 1.15,
        "avg_r": 0.05,
        "max_drawdown": 0.24,
        "sharpe_ratio": 0.7,
        "total_trades": 95,
        "trend_up_wr": 0.45,
        "trend_down_wr": 0.58,
        "range_wr": 0.48,
    },
    "WEDGE_FALLING": {
        "win_rate": 0.53,
        "profit_factor": 1.2,
        "avg_r": 0.06,
        "max_drawdown": 0.22,
        "sharpe_ratio": 0.75,
        "total_trades": 92,
        "trend_up_wr": 0.60,
        "trend_down_wr": 0.48,
        "range_wr": 0.50,
    },
    
    # TESTING - Need more data
    "TRIANGLE_ASCENDING": {
        "win_rate": 0.55,
        "profit_factor": 1.35,
        "avg_r": 0.10,
        "max_drawdown": 0.20,
        "sharpe_ratio": 1.0,
        "total_trades": 45,  # Low sample
    },
    "TRIANGLE_DESCENDING": {
        "win_rate": 0.54,
        "profit_factor": 1.30,
        "avg_r": 0.09,
        "max_drawdown": 0.21,
        "sharpe_ratio": 0.95,
        "total_trades": 42,  # Low sample
    },
    "FLAG_BULL": {
        "win_rate": 0.58,
        "profit_factor": 1.5,
        "avg_r": 0.15,
        "max_drawdown": 0.18,
        "sharpe_ratio": 1.2,
        "total_trades": 38,  # Low sample
    },
    "FLAG_BEAR": {
        "win_rate": 0.56,
        "profit_factor": 1.45,
        "avg_r": 0.13,
        "max_drawdown": 0.19,
        "sharpe_ratio": 1.15,
        "total_trades": 35,  # Low sample
    },
}


class StrategyPruner:
    """Phase 8.8 Strategy Pruning Engine"""
    
    def __init__(self):
        self.classifications: Dict[str, StrategyClassification] = {}
        self.pruning_history: List[Dict] = []
    
    def run_pruning(self) -> Dict[str, Any]:
        """
        Run full pruning analysis on all strategies.
        Returns pruning report with classifications.
        """
        started_at = int(time.time() * 1000)
        
        classifications = []
        
        for strategy_id, data in STRATEGY_BASELINE_DATA.items():
            classification = self._classify_strategy(strategy_id, data)
            self.classifications[strategy_id] = classification
            classifications.append(classification)
        
        # Group by status
        approved = [c for c in classifications if c.status == StrategyStatus.APPROVED]
        limited = [c for c in classifications if c.status == StrategyStatus.LIMITED]
        testing = [c for c in classifications if c.status == StrategyStatus.TESTING]
        deprecated = [c for c in classifications if c.status == StrategyStatus.DEPRECATED]
        
        completed_at = int(time.time() * 1000)
        
        report = {
            "reportId": f"pruning_{int(time.time() * 1000)}",
            "phase": "8.8",
            "title": "Strategy Pruning Report",
            "startedAt": started_at,
            "completedAt": completed_at,
            
            "summary": {
                "totalStrategies": len(classifications),
                "approved": len(approved),
                "limited": len(limited),
                "testing": len(testing),
                "deprecated": len(deprecated),
            },
            
            "approved": [self._classification_to_dict(c) for c in approved],
            "limited": [self._classification_to_dict(c) for c in limited],
            "testing": [self._classification_to_dict(c) for c in testing],
            "deprecated": [self._classification_to_dict(c) for c in deprecated],
            
            "thresholds": PRUNING_THRESHOLDS,
            
            "recommendations": self._generate_global_recommendations(
                approved, limited, testing, deprecated
            ),
            
            "nextSteps": [
                "Update pattern registry to mark DEPRECATED strategies",
                "Add regime conditions to LIMITED strategies",
                "Phase 8.9: Regime Validation for APPROVED/LIMITED",
                "Phase 9.0: Cross-Asset Validation"
            ]
        }
        
        # Store in history
        self.pruning_history.append(report)
        
        return report
    
    def _classify_strategy(
        self,
        strategy_id: str,
        data: Dict[str, Any]
    ) -> StrategyClassification:
        """Classify a single strategy"""
        
        metrics = StrategyMetrics(
            strategy_id=strategy_id,
            win_rate=data.get("win_rate", 0),
            profit_factor=data.get("profit_factor", 0),
            avg_r=data.get("avg_r", 0),
            max_drawdown=data.get("max_drawdown", 1),
            sharpe_ratio=data.get("sharpe_ratio", 0),
            total_trades=data.get("total_trades", 0),
            trend_up_wr=data.get("trend_up_wr", 0),
            trend_down_wr=data.get("trend_down_wr", 0),
            range_wr=data.get("range_wr", 0),
            tf_1d_wr=data.get("tf_1d_wr", 0),
            tf_4h_wr=data.get("tf_4h_wr", 0),
            tf_1h_wr=data.get("tf_1h_wr", 0),
        )
        
        # Check regime stability
        regime_wrs = [metrics.trend_up_wr, metrics.trend_down_wr, metrics.range_wr]
        regime_wrs = [w for w in regime_wrs if w > 0]
        if regime_wrs:
            metrics.regime_stable = (max(regime_wrs) - min(regime_wrs)) < PRUNING_THRESHOLDS["approved"]["regime_variance"]
        
        # Check TF stability
        tf_wrs = [metrics.tf_1d_wr, metrics.tf_4h_wr, metrics.tf_1h_wr]
        tf_wrs = [w for w in tf_wrs if w > 0]
        if tf_wrs:
            metrics.tf_stable = (max(tf_wrs) - min(tf_wrs)) < PRUNING_THRESHOLDS["approved"]["tf_variance"]
        
        # Check for override (from Phase 8.7 validation)
        if "status_override" in data:
            return StrategyClassification(
                strategy_id=strategy_id,
                status=StrategyStatus(data["status_override"]),
                reason=data.get("reason", "Manual override"),
                metrics=metrics,
                recommendations=[
                    f"Remove from production routing",
                    f"Archive for historical analysis"
                ]
            )
        
        # Automatic classification based on thresholds
        status, reason, allowed_regimes, allowed_tfs, recommendations = self._auto_classify(metrics)
        
        return StrategyClassification(
            strategy_id=strategy_id,
            status=status,
            reason=reason,
            metrics=metrics,
            allowed_regimes=allowed_regimes,
            allowed_timeframes=allowed_tfs,
            recommendations=recommendations
        )
    
    def _auto_classify(
        self,
        metrics: StrategyMetrics
    ) -> tuple:
        """Automatic classification based on thresholds"""
        
        thresh = PRUNING_THRESHOLDS
        recommendations = []
        
        # Check DEPRECATED triggers first
        if (metrics.win_rate < thresh["deprecated"]["max_win_rate"] or
            metrics.profit_factor < thresh["deprecated"]["max_profit_factor"] or
            metrics.avg_r < thresh["deprecated"]["min_avg_r"]):
            
            reasons = []
            if metrics.win_rate < thresh["deprecated"]["max_win_rate"]:
                reasons.append(f"WR {metrics.win_rate:.1%} < {thresh['deprecated']['max_win_rate']:.0%}")
            if metrics.profit_factor < thresh["deprecated"]["max_profit_factor"]:
                reasons.append(f"PF {metrics.profit_factor:.2f} < {thresh['deprecated']['max_profit_factor']:.1f}")
            if metrics.avg_r < thresh["deprecated"]["min_avg_r"]:
                reasons.append(f"avgR {metrics.avg_r:.2f} < {thresh['deprecated']['min_avg_r']:.2f}")
            
            return (
                StrategyStatus.DEPRECATED,
                f"Failed thresholds: {', '.join(reasons)}",
                [],
                [],
                ["Remove from production", "Archive for analysis"]
            )
        
        # Check for TESTING (low sample)
        if metrics.total_trades < thresh["approved"]["min_trades"]:
            return (
                StrategyStatus.TESTING,
                f"Insufficient trades ({metrics.total_trades} < {thresh['approved']['min_trades']})",
                [],
                [],
                ["Collect more data before classification", "Monitor performance in paper trading"]
            )
        
        # Check for APPROVED
        approved_criteria = [
            metrics.win_rate >= thresh["approved"]["min_win_rate"],
            metrics.profit_factor >= thresh["approved"]["min_profit_factor"],
            metrics.avg_r >= thresh["approved"]["min_avg_r"],
            metrics.max_drawdown <= thresh["approved"]["max_drawdown"],
            metrics.sharpe_ratio >= thresh["approved"]["min_sharpe"],
        ]
        
        if all(approved_criteria):
            stability_notes = []
            if metrics.regime_stable:
                stability_notes.append("regime-stable")
            if metrics.tf_stable:
                stability_notes.append("TF-stable")
            
            return (
                StrategyStatus.APPROVED,
                f"Passed all thresholds. {', '.join(stability_notes) if stability_notes else 'Check regime/TF stability'}",
                ["TREND_UP", "TREND_DOWN", "RANGE"],
                ["1d", "4h", "1h"],
                ["Ready for production", "Continue monitoring"]
            )
        
        # LIMITED - passes minimum but not all
        limited_criteria = [
            metrics.win_rate >= thresh["limited"]["min_win_rate"],
            metrics.profit_factor >= thresh["limited"]["min_profit_factor"],
            metrics.avg_r >= thresh["limited"]["min_avg_r"],
            metrics.max_drawdown <= thresh["limited"]["max_drawdown"],
        ]
        
        if all(limited_criteria):
            # Determine allowed regimes based on performance
            allowed_regimes = []
            if metrics.trend_up_wr >= 0.55:
                allowed_regimes.append("TREND_UP")
            if metrics.trend_down_wr >= 0.55:
                allowed_regimes.append("TREND_DOWN")
            if metrics.range_wr >= 0.50:
                allowed_regimes.append("RANGE")
            
            # Determine allowed TFs
            allowed_tfs = []
            if metrics.tf_1d_wr >= 0.52:
                allowed_tfs.append("1d")
            if metrics.tf_4h_wr >= 0.52:
                allowed_tfs.append("4h")
            if metrics.tf_1h_wr >= 0.52:
                allowed_tfs.append("1h")
            
            # Default if no specific data
            if not allowed_regimes:
                allowed_regimes = ["TREND_UP", "TREND_DOWN"]  # Avoid RANGE by default
            if not allowed_tfs:
                allowed_tfs = ["1d", "4h"]  # Prefer higher TFs
            
            failed = []
            if metrics.win_rate < thresh["approved"]["min_win_rate"]:
                failed.append(f"WR {metrics.win_rate:.1%}")
            if metrics.profit_factor < thresh["approved"]["min_profit_factor"]:
                failed.append(f"PF {metrics.profit_factor:.2f}")
            if metrics.sharpe_ratio < thresh["approved"]["min_sharpe"]:
                failed.append(f"Sharpe {metrics.sharpe_ratio:.2f}")
            
            return (
                StrategyStatus.LIMITED,
                f"Conditional use. Failed: {', '.join(failed)}",
                allowed_regimes,
                allowed_tfs,
                [
                    f"Use only in: {', '.join(allowed_regimes)}",
                    f"Recommended TFs: {', '.join(allowed_tfs)}",
                    "Reduce position size vs APPROVED strategies"
                ]
            )
        
        # Default to TESTING if unclear
        return (
            StrategyStatus.TESTING,
            "Mixed metrics, needs more analysis",
            [],
            [],
            ["Review individual trade data", "Consider regime-specific testing"]
        )
    
    def _generate_global_recommendations(
        self,
        approved: List,
        limited: List,
        testing: List,
        deprecated: List
    ) -> List[str]:
        """Generate global pruning recommendations"""
        
        recommendations = []
        
        # Portfolio concentration
        if len(approved) >= 3:
            approved_names = [c.strategy_id for c in approved[:5]]
            recommendations.append(
                f"Core portfolio: {', '.join(approved_names)}"
            )
        
        # Deprecated cleanup
        if deprecated:
            dep_names = [c.strategy_id for c in deprecated]
            recommendations.append(
                f"Immediate removal: {', '.join(dep_names)}"
            )
        
        # Limited usage
        if limited:
            recommendations.append(
                f"{len(limited)} strategies for conditional use only"
            )
        
        # Testing backlog
        if testing:
            recommendations.append(
                f"{len(testing)} strategies need more data before classification"
            )
        
        # Risk allocation
        total_approved = len(approved)
        total_active = total_approved + len(limited)
        
        if total_approved > 0:
            recommendations.append(
                f"Suggested allocation: {70//total_approved}% per APPROVED, {30//max(1,len(limited))}% per LIMITED"
            )
        
        return recommendations
    
    def _classification_to_dict(self, c: StrategyClassification) -> Dict[str, Any]:
        """Convert classification to dict"""
        return {
            "strategyId": c.strategy_id,
            "status": c.status.value,
            "reason": c.reason,
            "metrics": {
                "winRate": c.metrics.win_rate,
                "profitFactor": c.metrics.profit_factor,
                "avgR": c.metrics.avg_r,
                "maxDrawdown": c.metrics.max_drawdown,
                "sharpeRatio": c.metrics.sharpe_ratio,
                "totalTrades": c.metrics.total_trades,
                "regimeStable": c.metrics.regime_stable,
                "tfStable": c.metrics.tf_stable,
            },
            "allowedRegimes": c.allowed_regimes,
            "allowedTimeframes": c.allowed_timeframes,
            "recommendations": c.recommendations,
        }
    
    def get_active_strategies(self) -> List[str]:
        """Get list of strategies allowed in production"""
        active = []
        for strategy_id, classification in self.classifications.items():
            if classification.status in [StrategyStatus.APPROVED, StrategyStatus.LIMITED]:
                active.append(strategy_id)
        return active
    
    def get_deprecated_strategies(self) -> List[str]:
        """Get list of deprecated strategies"""
        return [
            strategy_id 
            for strategy_id, classification in self.classifications.items()
            if classification.status == StrategyStatus.DEPRECATED
        ]
    
    def is_strategy_allowed(
        self,
        strategy_id: str,
        regime: str = None,
        timeframe: str = None
    ) -> Dict[str, Any]:
        """Check if strategy is allowed for given conditions"""
        
        if strategy_id not in self.classifications:
            return {
                "allowed": False,
                "reason": "Strategy not found in registry"
            }
        
        classification = self.classifications[strategy_id]
        
        # DEPRECATED - never allowed
        if classification.status == StrategyStatus.DEPRECATED:
            return {
                "allowed": False,
                "reason": f"DEPRECATED: {classification.reason}",
                "status": "DEPRECATED"
            }
        
        # TESTING - not for production
        if classification.status == StrategyStatus.TESTING:
            return {
                "allowed": False,
                "reason": "Strategy in TESTING status, not for production",
                "status": "TESTING"
            }
        
        # APPROVED - always allowed
        if classification.status == StrategyStatus.APPROVED:
            return {
                "allowed": True,
                "reason": "APPROVED for production",
                "status": "APPROVED",
                "positionSizeMultiplier": 1.0
            }
        
        # LIMITED - check conditions
        if classification.status == StrategyStatus.LIMITED:
            regime_ok = regime is None or regime in classification.allowed_regimes
            tf_ok = timeframe is None or timeframe in classification.allowed_timeframes
            
            if regime_ok and tf_ok:
                return {
                    "allowed": True,
                    "reason": "LIMITED: Conditions met",
                    "status": "LIMITED",
                    "positionSizeMultiplier": 0.5,  # Reduced size for LIMITED
                    "conditions": {
                        "allowedRegimes": classification.allowed_regimes,
                        "allowedTimeframes": classification.allowed_timeframes
                    }
                }
            else:
                failed = []
                if not regime_ok:
                    failed.append(f"regime {regime} not in {classification.allowed_regimes}")
                if not tf_ok:
                    failed.append(f"TF {timeframe} not in {classification.allowed_timeframes}")
                
                return {
                    "allowed": False,
                    "reason": f"LIMITED: Conditions not met ({', '.join(failed)})",
                    "status": "LIMITED",
                    "conditions": {
                        "allowedRegimes": classification.allowed_regimes,
                        "allowedTimeframes": classification.allowed_timeframes
                    }
                }
        
        return {"allowed": False, "reason": "Unknown status"}


# Singleton instance
strategy_pruner = StrategyPruner()


def run_strategy_pruning() -> Dict[str, Any]:
    """Run Phase 8.8 Strategy Pruning"""
    return strategy_pruner.run_pruning()


if __name__ == "__main__":
    import json
    result = run_strategy_pruning()
    print(json.dumps(result, indent=2))
