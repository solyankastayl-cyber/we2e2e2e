"""
Phase 9.25C: Portfolio Safety Layer
===================================

Защита портфеля от системных рисков.

Компоненты:
1. Exposure Monitor — контроль экспозиции
2. Correlation Budgeting — управление корреляцией
3. Kill Switch — аварийная остановка

API:
- GET /api/portfolio/exposure
- GET /api/portfolio/correlation
- POST /api/portfolio/kill-switch
"""
import time
import math
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# Types & Enums
# ═══════════════════════════════════════════════════════════════

class RiskMode(str, Enum):
    """Portfolio risk modes"""
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    SAFE = "SAFE"
    HALT = "HALT"


class KillSwitchTrigger(str, Enum):
    """Kill switch trigger types"""
    MANUAL = "MANUAL"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    CORRELATION_SPIKE = "CORRELATION_SPIKE"
    EXTREME_VOLATILITY = "EXTREME_VOLATILITY"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"


@dataclass
class ExposureMetrics:
    """Portfolio exposure metrics"""
    gross_exposure: float = 0.0  # Sum of all positions
    net_exposure: float = 0.0   # Long - Short
    
    # By dimension
    by_asset: Dict[str, float] = field(default_factory=dict)
    by_strategy: Dict[str, float] = field(default_factory=dict)
    by_family: Dict[str, float] = field(default_factory=dict)
    by_regime: Dict[str, float] = field(default_factory=dict)
    
    # Limits
    gross_limit: float = 1.5
    net_limit: float = 1.0
    asset_limit: float = 0.3
    strategy_limit: float = 0.2
    family_limit: float = 0.4
    
    # Status
    within_limits: bool = True
    violations: List[str] = field(default_factory=list)
    
    timestamp: int = 0


@dataclass
class CorrelationMetrics:
    """Correlation analysis metrics"""
    # Pairwise correlations
    strategy_correlations: Dict[str, Dict[str, float]] = field(default_factory=dict)
    asset_correlations: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Aggregated
    avg_strategy_correlation: float = 0.0
    avg_asset_correlation: float = 0.0
    max_correlation: float = 0.0
    
    # High correlation pairs
    high_correlation_pairs: List[Dict] = field(default_factory=list)
    
    # Correlation budget
    correlation_budget_used: float = 0.0
    correlation_limit: float = 0.7
    
    # Actions
    blocked_signals: List[str] = field(default_factory=list)
    size_adjustments: Dict[str, float] = field(default_factory=dict)
    
    timestamp: int = 0


@dataclass
class KillSwitchStatus:
    """Kill switch status"""
    is_active: bool = False
    trigger: Optional[KillSwitchTrigger] = None
    triggered_at: int = 0
    reason: str = ""
    
    # Current risk mode
    risk_mode: RiskMode = RiskMode.NORMAL
    
    # Disabled components
    disabled_strategies: List[str] = field(default_factory=list)
    disabled_families: List[str] = field(default_factory=list)
    
    # Recovery
    recovery_threshold: str = ""
    manual_override: bool = False


@dataclass
class PortfolioSafetyStatus:
    """Overall portfolio safety status"""
    is_safe: bool = True
    risk_mode: RiskMode = RiskMode.NORMAL
    
    # Risk level
    risk_score: float = 0.0  # 0-1
    risk_level: str = "LOW"  # LOW, NORMAL, ELEVATED, HIGH, CRITICAL
    
    # Components
    exposure_status: str = "OK"
    correlation_status: str = "OK"
    kill_switch_status: str = "INACTIVE"
    
    # Metrics summary
    gross_exposure: float = 0.0
    avg_correlation: float = 0.0
    max_drawdown: float = 0.0
    
    # Active warnings
    warnings: List[str] = field(default_factory=list)
    
    # Recommendations
    recommended_actions: List[str] = field(default_factory=list)
    
    timestamp: int = 0


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

PORTFOLIO_SAFETY_CONFIG = {
    "version": "phase9.25C",
    "enabled": True,
    
    # Exposure limits
    "exposure_limits": {
        "gross_exposure": 1.5,  # 150% max
        "net_exposure": 1.0,
        "per_asset": 0.30,
        "per_strategy": 0.20,
        "per_family": 0.40,
        "per_regime": 0.50
    },
    
    # Correlation limits
    "correlation_limits": {
        "max_pairwise": 0.70,
        "avg_threshold": 0.50,
        "budget": 0.65
    },
    
    # Kill switch triggers
    "kill_switch_triggers": {
        "max_drawdown": 0.20,  # 20% drawdown
        "correlation_spike": 0.85,
        "volatility_multiplier": 3.0,
        "consecutive_losses": 10
    },
    
    # Risk mode settings
    "risk_modes": {
        "NORMAL": {"exposure_multiplier": 1.0, "enabled_strategies": "all"},
        "CAUTION": {"exposure_multiplier": 0.7, "enabled_strategies": "approved_only"},
        "SAFE": {"exposure_multiplier": 0.3, "enabled_strategies": "core_only"},
        "HALT": {"exposure_multiplier": 0.0, "enabled_strategies": "none"}
    }
}


# ═══════════════════════════════════════════════════════════════
# Exposure Monitor
# ═══════════════════════════════════════════════════════════════

class ExposureMonitor:
    """
    Monitors portfolio exposure.
    
    Tracks:
    - Gross exposure
    - Net exposure
    - By asset/strategy/family/regime
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or PORTFOLIO_SAFETY_CONFIG
        self._last_metrics: Optional[ExposureMetrics] = None
    
    def calculate(
        self,
        positions: Optional[List[Dict]] = None
    ) -> ExposureMetrics:
        """
        Calculate current exposure metrics.
        
        Args:
            positions: List of {"asset", "strategy", "family", "regime", "size", "direction"}
        """
        limits = self.config.get("exposure_limits", {})
        
        # Default/simulated positions
        if not positions:
            positions = self._get_default_positions()
        
        # Calculate exposures
        gross = sum(abs(p.get("size", 0)) for p in positions)
        net = sum(p.get("size", 0) * (1 if p.get("direction", "LONG") == "LONG" else -1) for p in positions)
        
        by_asset = {}
        by_strategy = {}
        by_family = {}
        by_regime = {}
        
        for p in positions:
            size = abs(p.get("size", 0))
            
            asset = p.get("asset", "BTC")
            by_asset[asset] = by_asset.get(asset, 0) + size
            
            strategy = p.get("strategy", "MTF_BREAKOUT")
            by_strategy[strategy] = by_strategy.get(strategy, 0) + size
            
            family = p.get("family", "breakout_family")
            by_family[family] = by_family.get(family, 0) + size
            
            regime = p.get("regime", "TREND_UP")
            by_regime[regime] = by_regime.get(regime, 0) + size
        
        # Check limits
        violations = []
        
        if gross > limits.get("gross_exposure", 1.5):
            violations.append(f"Gross exposure {gross:.2f} exceeds limit {limits.get('gross_exposure')}")
        
        if abs(net) > limits.get("net_exposure", 1.0):
            violations.append(f"Net exposure {net:.2f} exceeds limit {limits.get('net_exposure')}")
        
        for asset, exp in by_asset.items():
            if exp > limits.get("per_asset", 0.3):
                violations.append(f"Asset {asset} exposure {exp:.2f} exceeds limit")
        
        for strategy, exp in by_strategy.items():
            if exp > limits.get("per_strategy", 0.2):
                violations.append(f"Strategy {strategy} exposure {exp:.2f} exceeds limit")
        
        metrics = ExposureMetrics(
            gross_exposure=round(gross, 4),
            net_exposure=round(net, 4),
            by_asset=by_asset,
            by_strategy=by_strategy,
            by_family=by_family,
            by_regime=by_regime,
            gross_limit=limits.get("gross_exposure", 1.5),
            net_limit=limits.get("net_exposure", 1.0),
            asset_limit=limits.get("per_asset", 0.3),
            strategy_limit=limits.get("per_strategy", 0.2),
            family_limit=limits.get("per_family", 0.4),
            within_limits=len(violations) == 0,
            violations=violations,
            timestamp=int(time.time() * 1000)
        )
        
        self._last_metrics = metrics
        return metrics
    
    def _get_default_positions(self) -> List[Dict]:
        """Get default simulated positions"""
        return [
            {"asset": "BTC", "strategy": "MTF_BREAKOUT", "family": "breakout_family", "regime": "TREND_UP", "size": 0.05, "direction": "LONG"},
            {"asset": "ETH", "strategy": "MTF_BREAKOUT", "family": "breakout_family", "regime": "TREND_UP", "size": 0.04, "direction": "LONG"},
            {"asset": "SOL", "strategy": "MOMENTUM_CONTINUATION", "family": "continuation_family", "regime": "TREND_UP", "size": 0.03, "direction": "LONG"},
            {"asset": "BTC", "strategy": "DOUBLE_BOTTOM", "family": "reversal_family", "regime": "RANGE", "size": 0.04, "direction": "LONG"},
            {"asset": "SPX", "strategy": "CHANNEL_BREAKOUT", "family": "breakout_family", "regime": "TREND_UP", "size": 0.06, "direction": "LONG"},
            {"asset": "GOLD", "strategy": "DOUBLE_TOP", "family": "reversal_family", "regime": "TREND_DOWN", "size": 0.03, "direction": "SHORT"},
        ]
    
    def get_last_metrics(self) -> Optional[ExposureMetrics]:
        """Get last calculated metrics"""
        return self._last_metrics


# ═══════════════════════════════════════════════════════════════
# Correlation Monitor
# ═══════════════════════════════════════════════════════════════

class CorrelationMonitor:
    """
    Monitors correlation between strategies and assets.
    
    - Correlation budgeting
    - Signal blocking
    - Size adjustments
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or PORTFOLIO_SAFETY_CONFIG
        self._last_metrics: Optional[CorrelationMetrics] = None
    
    def calculate(
        self,
        returns: Optional[Dict[str, List[float]]] = None
    ) -> CorrelationMetrics:
        """
        Calculate correlation metrics.
        
        Args:
            returns: Dict of strategy_id -> return series
        """
        limits = self.config.get("correlation_limits", {})
        
        # Simulated correlations
        strategy_corr = {
            "MTF_BREAKOUT": {"CHANNEL_BREAKOUT": 0.75, "MOMENTUM_CONTINUATION": 0.45, "DOUBLE_BOTTOM": 0.20},
            "CHANNEL_BREAKOUT": {"MTF_BREAKOUT": 0.75, "MOMENTUM_CONTINUATION": 0.55, "DOUBLE_TOP": 0.15},
            "DOUBLE_BOTTOM": {"DOUBLE_TOP": 0.65, "MTF_BREAKOUT": 0.20, "CHANNEL_BREAKOUT": 0.18},
            "DOUBLE_TOP": {"DOUBLE_BOTTOM": 0.65, "MTF_BREAKOUT": 0.15, "MOMENTUM_CONTINUATION": 0.25},
            "MOMENTUM_CONTINUATION": {"MTF_BREAKOUT": 0.45, "CHANNEL_BREAKOUT": 0.55, "DOUBLE_TOP": 0.25}
        }
        
        asset_corr = {
            "BTC": {"ETH": 0.85, "SOL": 0.78, "SPX": 0.35, "GOLD": 0.15},
            "ETH": {"BTC": 0.85, "SOL": 0.82, "SPX": 0.30, "GOLD": 0.12},
            "SOL": {"BTC": 0.78, "ETH": 0.82, "SPX": 0.25, "GOLD": 0.10},
            "SPX": {"BTC": 0.35, "ETH": 0.30, "GOLD": 0.20, "DXY": -0.45},
            "GOLD": {"BTC": 0.15, "SPX": 0.20, "DXY": -0.55},
            "DXY": {"SPX": -0.45, "GOLD": -0.55, "BTC": -0.25}
        }
        
        # Calculate averages
        all_strat_corr = []
        for s1, corrs in strategy_corr.items():
            all_strat_corr.extend(corrs.values())
        avg_strat_corr = sum(all_strat_corr) / len(all_strat_corr) if all_strat_corr else 0
        
        all_asset_corr = []
        for a1, corrs in asset_corr.items():
            all_asset_corr.extend(abs(c) for c in corrs.values())
        avg_asset_corr = sum(all_asset_corr) / len(all_asset_corr) if all_asset_corr else 0
        
        # Find max correlation
        max_corr = max(max(corrs.values()) for corrs in strategy_corr.values()) if strategy_corr else 0
        
        # Find high correlation pairs
        high_pairs = []
        threshold = limits.get("max_pairwise", 0.7)
        
        for s1, corrs in strategy_corr.items():
            for s2, corr in corrs.items():
                if corr >= threshold:
                    high_pairs.append({
                        "pair": [s1, s2],
                        "correlation": corr,
                        "type": "strategy"
                    })
        
        for a1, corrs in asset_corr.items():
            for a2, corr in corrs.items():
                if abs(corr) >= threshold:
                    high_pairs.append({
                        "pair": [a1, a2],
                        "correlation": corr,
                        "type": "asset"
                    })
        
        # Determine blocked signals and adjustments
        blocked = []
        adjustments = {}
        
        if max_corr >= threshold:
            blocked.append("CHANNEL_BREAKOUT")  # Due to high correlation with MTF_BREAKOUT
            adjustments["MTF_BREAKOUT"] = 0.8
            adjustments["CHANNEL_BREAKOUT"] = 0.5
        
        # Correlation budget
        budget_used = avg_strat_corr / limits.get("budget", 0.65)
        
        metrics = CorrelationMetrics(
            strategy_correlations=strategy_corr,
            asset_correlations=asset_corr,
            avg_strategy_correlation=round(avg_strat_corr, 4),
            avg_asset_correlation=round(avg_asset_corr, 4),
            max_correlation=round(max_corr, 4),
            high_correlation_pairs=high_pairs,
            correlation_budget_used=round(min(budget_used, 1.0), 4),
            correlation_limit=limits.get("max_pairwise", 0.7),
            blocked_signals=blocked,
            size_adjustments=adjustments,
            timestamp=int(time.time() * 1000)
        )
        
        self._last_metrics = metrics
        return metrics
    
    def get_last_metrics(self) -> Optional[CorrelationMetrics]:
        """Get last metrics"""
        return self._last_metrics


# ═══════════════════════════════════════════════════════════════
# Kill Switch
# ═══════════════════════════════════════════════════════════════

class KillSwitch:
    """
    Portfolio kill switch.
    
    Triggers on:
    - Max drawdown exceeded
    - Correlation spike
    - Extreme volatility
    - Consecutive losses
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or PORTFOLIO_SAFETY_CONFIG
        self._status = KillSwitchStatus()
    
    def check_triggers(
        self,
        current_drawdown: float = 0.0,
        correlation_level: float = 0.0,
        volatility_multiplier: float = 1.0,
        consecutive_losses: int = 0
    ) -> KillSwitchStatus:
        """
        Check all kill switch triggers.
        """
        triggers = self.config.get("kill_switch_triggers", {})
        
        # Check max drawdown
        if current_drawdown >= triggers.get("max_drawdown", 0.20):
            return self._activate(
                KillSwitchTrigger.MAX_DRAWDOWN,
                f"Drawdown {current_drawdown*100:.1f}% exceeds threshold"
            )
        
        # Check correlation spike
        if correlation_level >= triggers.get("correlation_spike", 0.85):
            return self._activate(
                KillSwitchTrigger.CORRELATION_SPIKE,
                f"Correlation {correlation_level:.2f} exceeds threshold"
            )
        
        # Check volatility
        if volatility_multiplier >= triggers.get("volatility_multiplier", 3.0):
            return self._activate(
                KillSwitchTrigger.EXTREME_VOLATILITY,
                f"Volatility {volatility_multiplier:.1f}x exceeds threshold"
            )
        
        # Check consecutive losses
        if consecutive_losses >= triggers.get("consecutive_losses", 10):
            return self._activate(
                KillSwitchTrigger.CONSECUTIVE_LOSSES,
                f"{consecutive_losses} consecutive losses exceeds threshold"
            )
        
        return self._status
    
    def activate(self, trigger: KillSwitchTrigger, reason: str = "") -> KillSwitchStatus:
        """Manually activate kill switch"""
        return self._activate(trigger, reason)
    
    def _activate(self, trigger: KillSwitchTrigger, reason: str) -> KillSwitchStatus:
        """Internal activation"""
        self._status = KillSwitchStatus(
            is_active=True,
            trigger=trigger,
            triggered_at=int(time.time() * 1000),
            reason=reason,
            risk_mode=RiskMode.SAFE if trigger != KillSwitchTrigger.MAX_DRAWDOWN else RiskMode.HALT,
            disabled_strategies=["EXPERIMENTAL", "HARMONIC"],
            disabled_families=["experimental_family", "harmonic_family"],
            recovery_threshold="DD < 10%, Correlation < 0.6",
            manual_override=False
        )
        return self._status
    
    def deactivate(self, reason: str = "Manual reset") -> KillSwitchStatus:
        """Deactivate kill switch"""
        self._status = KillSwitchStatus(
            is_active=False,
            risk_mode=RiskMode.NORMAL,
            reason=reason
        )
        return self._status
    
    def get_status(self) -> KillSwitchStatus:
        """Get current status"""
        return self._status


# ═══════════════════════════════════════════════════════════════
# Portfolio Safety Service
# ═══════════════════════════════════════════════════════════════

class PortfolioSafetyService:
    """
    Main Portfolio Safety Service.
    
    Orchestrates:
    - Exposure monitoring
    - Correlation monitoring
    - Kill switch
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or PORTFOLIO_SAFETY_CONFIG
        
        self.exposure_monitor = ExposureMonitor(config)
        self.correlation_monitor = CorrelationMonitor(config)
        self.kill_switch = KillSwitch(config)
    
    def get_safety_status(self) -> PortfolioSafetyStatus:
        """Get overall safety status"""
        exposure = self.exposure_monitor.get_last_metrics()
        correlation = self.correlation_monitor.get_last_metrics()
        kill_status = self.kill_switch.get_status()
        
        # Calculate if not available
        if not exposure:
            exposure = self.exposure_monitor.calculate()
        if not correlation:
            correlation = self.correlation_monitor.calculate()
        
        # Determine status
        warnings = []
        actions = []
        
        exposure_status = "OK"
        if not exposure.within_limits:
            exposure_status = "WARNING"
            warnings.extend(exposure.violations[:3])
            actions.append("Reduce position sizes")
        
        correlation_status = "OK"
        if correlation.correlation_budget_used > 0.8:
            correlation_status = "WARNING"
            warnings.append(f"High correlation budget usage: {correlation.correlation_budget_used*100:.0f}%")
            actions.append("Reduce correlated positions")
        
        kill_switch_status = "ACTIVE" if kill_status.is_active else "INACTIVE"
        if kill_status.is_active:
            warnings.append(f"Kill switch active: {kill_status.reason}")
        
        # Calculate risk score
        risk_score = (
            (1 - int(exposure.within_limits)) * 0.3 +
            min(correlation.correlation_budget_used, 1.0) * 0.3 +
            (1 if kill_status.is_active else 0) * 0.4
        )
        
        if risk_score >= 0.7:
            risk_level = "CRITICAL"
        elif risk_score >= 0.5:
            risk_level = "HIGH"
        elif risk_score >= 0.3:
            risk_level = "ELEVATED"
        elif risk_score >= 0.15:
            risk_level = "NORMAL"
        else:
            risk_level = "LOW"
        
        return PortfolioSafetyStatus(
            is_safe=risk_score < 0.5,
            risk_mode=kill_status.risk_mode,
            risk_score=round(risk_score, 4),
            risk_level=risk_level,
            exposure_status=exposure_status,
            correlation_status=correlation_status,
            kill_switch_status=kill_switch_status,
            gross_exposure=exposure.gross_exposure,
            avg_correlation=correlation.avg_strategy_correlation,
            max_drawdown=0.08,  # Simulated
            warnings=warnings,
            recommended_actions=actions,
            timestamp=int(time.time() * 1000)
        )
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": self.config.get("enabled", True),
            "version": self.config.get("version", "phase9.25C"),
            "status": "ok",
            "components": {
                "exposure_monitor": "ok",
                "correlation_monitor": "ok",
                "kill_switch": "ok"
            },
            "killSwitchActive": self.kill_switch.get_status().is_active,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


# ═══════════════════════════════════════════════════════════════
# Serialization Functions
# ═══════════════════════════════════════════════════════════════

def exposure_to_dict(metrics: ExposureMetrics) -> Dict:
    """Convert ExposureMetrics to dict"""
    return {
        "grossExposure": metrics.gross_exposure,
        "netExposure": metrics.net_exposure,
        "byAsset": metrics.by_asset,
        "byStrategy": metrics.by_strategy,
        "byFamily": metrics.by_family,
        "byRegime": metrics.by_regime,
        "limits": {
            "gross": metrics.gross_limit,
            "net": metrics.net_limit,
            "asset": metrics.asset_limit,
            "strategy": metrics.strategy_limit,
            "family": metrics.family_limit
        },
        "withinLimits": metrics.within_limits,
        "violations": metrics.violations,
        "timestamp": metrics.timestamp
    }


def correlation_to_dict(metrics: CorrelationMetrics) -> Dict:
    """Convert CorrelationMetrics to dict"""
    return {
        "strategyCorrelations": metrics.strategy_correlations,
        "assetCorrelations": metrics.asset_correlations,
        "avgStrategyCorrelation": metrics.avg_strategy_correlation,
        "avgAssetCorrelation": metrics.avg_asset_correlation,
        "maxCorrelation": metrics.max_correlation,
        "highCorrelationPairs": metrics.high_correlation_pairs,
        "correlationBudgetUsed": metrics.correlation_budget_used,
        "correlationLimit": metrics.correlation_limit,
        "blockedSignals": metrics.blocked_signals,
        "sizeAdjustments": metrics.size_adjustments,
        "timestamp": metrics.timestamp
    }


def kill_switch_to_dict(status: KillSwitchStatus) -> Dict:
    """Convert KillSwitchStatus to dict"""
    return {
        "isActive": status.is_active,
        "trigger": status.trigger.value if status.trigger else None,
        "triggeredAt": status.triggered_at,
        "reason": status.reason,
        "riskMode": status.risk_mode.value,
        "disabledStrategies": status.disabled_strategies,
        "disabledFamilies": status.disabled_families,
        "recoveryThreshold": status.recovery_threshold,
        "manualOverride": status.manual_override
    }


def safety_status_to_dict(status: PortfolioSafetyStatus) -> Dict:
    """Convert PortfolioSafetyStatus to dict"""
    return {
        "isSafe": status.is_safe,
        "riskMode": status.risk_mode.value,
        "riskScore": status.risk_score,
        "riskLevel": status.risk_level,
        "exposureStatus": status.exposure_status,
        "correlationStatus": status.correlation_status,
        "killSwitchStatus": status.kill_switch_status,
        "grossExposure": status.gross_exposure,
        "avgCorrelation": status.avg_correlation,
        "maxDrawdown": status.max_drawdown,
        "warnings": status.warnings,
        "recommendedActions": status.recommended_actions,
        "timestamp": status.timestamp
    }
