"""
Phase 9.25B: Strategy Governance Layer
======================================

Управление жизненным циклом стратегий.

Компоненты:
1. Strategy Lifecycle Manager — управление статусами
2. Promotion Rules Engine — правила продвижения
3. Strategy Families — группировка стратегий
4. Strategy Budgeting — бюджетирование риска

API:
- GET /api/strategy/lifecycle
- POST /api/strategy/promote
- POST /api/strategy/demote
- GET /api/strategy/families
- GET /api/strategy/budgets
"""
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# Types & Enums
# ═══════════════════════════════════════════════════════════════

class StrategyLifecycle(str, Enum):
    """Strategy lifecycle statuses"""
    CANDIDATE = "CANDIDATE"
    TESTING = "TESTING"
    LIMITED = "LIMITED"
    APPROVED = "APPROVED"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    DISABLED = "DISABLED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class StrategyFamily(str, Enum):
    """Strategy families"""
    BREAKOUT = "breakout_family"
    REVERSAL = "reversal_family"
    CONTINUATION = "continuation_family"
    PATTERN = "pattern_family"
    HARMONIC = "harmonic_family"
    EXPERIMENTAL = "experimental_family"


@dataclass
class PromotionCriteria:
    """Criteria for strategy promotion"""
    min_trades: int = 200
    min_pf: float = 1.3
    min_sharpe: float = 0.8
    max_dd: float = 0.25
    min_wr: float = 0.50
    min_days: int = 90


@dataclass
class DemotionCriteria:
    """Criteria for strategy demotion"""
    min_pf_decline: float = 0.20
    min_wr_decline: float = 0.08
    max_consecutive_losses: int = 10
    max_dd_spike: float = 0.15


@dataclass
class StrategyBudget:
    """Budget constraints for a strategy"""
    strategy_id: str
    risk_budget: float = 0.02  # % of capital per trade
    capital_budget: float = 0.10  # max % of portfolio
    max_concurrent_trades: int = 3
    max_daily_trades: int = 5
    allowed_assets: List[str] = field(default_factory=list)
    allowed_regimes: List[str] = field(default_factory=list)
    is_active: bool = True


@dataclass
class StrategyRecord:
    """Complete strategy record"""
    strategy_id: str
    name: str
    family: StrategyFamily
    lifecycle: StrategyLifecycle
    
    # Metrics
    trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    
    # Budget
    budget: Optional[StrategyBudget] = None
    
    # History
    created_at: int = 0
    last_trade_at: int = 0
    last_status_change: int = 0
    status_history: List[Dict] = field(default_factory=list)
    
    # Notes
    notes: str = ""


@dataclass
class FamilyAllocation:
    """Family allocation settings"""
    family: StrategyFamily
    name: str
    strategies: List[str] = field(default_factory=list)
    allocation_pct: float = 0.0  # Target allocation
    current_pct: float = 0.0  # Current allocation
    max_strategies: int = 5
    is_active: bool = True
    notes: str = ""


@dataclass
class PromotionResult:
    """Result of promotion/demotion attempt"""
    strategy_id: str
    success: bool
    from_status: StrategyLifecycle
    to_status: StrategyLifecycle
    reason: str = ""
    criteria_met: Dict[str, bool] = field(default_factory=dict)
    timestamp: int = 0


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

STRATEGY_GOVERNANCE_CONFIG = {
    "version": "phase9.25B",
    "enabled": True,
    
    # Promotion criteria by target status
    "promotion_criteria": {
        "TESTING_to_LIMITED": {
            "min_trades": 100,
            "min_pf": 1.1,
            "min_wr": 0.48,
            "max_dd": 0.30
        },
        "LIMITED_to_APPROVED": {
            "min_trades": 200,
            "min_pf": 1.3,
            "min_sharpe": 0.8,
            "min_wr": 0.52,
            "max_dd": 0.25,
            "min_days": 90
        },
        "APPROVED_to_CORE": {
            "min_trades": 500,
            "min_pf": 1.5,
            "min_sharpe": 1.2,
            "min_wr": 0.55,
            "max_dd": 0.20,
            "min_days": 180
        }
    },
    
    # Demotion triggers
    "demotion_triggers": {
        "APPROVED_to_WATCH": {
            "pf_decline": 0.15,
            "wr_decline": 0.05
        },
        "WATCH_to_DEGRADED": {
            "pf_decline": 0.25,
            "wr_decline": 0.08,
            "days_in_watch": 30
        },
        "DEGRADED_to_DISABLED": {
            "pf_below": 1.0,
            "consecutive_losses": 10
        }
    },
    
    # Family allocations
    "family_allocations": {
        "breakout_family": {"target": 0.35, "max_strategies": 5},
        "continuation_family": {"target": 0.30, "max_strategies": 4},
        "reversal_family": {"target": 0.20, "max_strategies": 4},
        "pattern_family": {"target": 0.10, "max_strategies": 3},
        "experimental_family": {"target": 0.05, "max_strategies": 2}
    },
    
    # Default budgets by lifecycle
    "default_budgets": {
        "CANDIDATE": {"risk": 0.005, "capital": 0.02, "max_trades": 1},
        "TESTING": {"risk": 0.01, "capital": 0.05, "max_trades": 2},
        "LIMITED": {"risk": 0.015, "capital": 0.08, "max_trades": 3},
        "APPROVED": {"risk": 0.02, "capital": 0.12, "max_trades": 5},
        "WATCH": {"risk": 0.01, "capital": 0.05, "max_trades": 2},
        "DEGRADED": {"risk": 0.005, "capital": 0.02, "max_trades": 1}
    }
}


# ═══════════════════════════════════════════════════════════════
# Strategy Lifecycle Manager
# ═══════════════════════════════════════════════════════════════

class StrategyLifecycleManager:
    """
    Manages strategy lifecycle transitions.
    
    Lifecycle:
    CANDIDATE → TESTING → LIMITED → APPROVED → WATCH → DEGRADED → DISABLED → DEPRECATED → ARCHIVED
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or STRATEGY_GOVERNANCE_CONFIG
        self._strategies: Dict[str, StrategyRecord] = {}
        self._history: List[PromotionResult] = []
        
        # Initialize default strategies
        self._init_default_strategies()
    
    def _init_default_strategies(self):
        """Initialize strategies from Phase 8.8 registry"""
        default_strategies = [
            {"id": "MTF_BREAKOUT", "name": "MTF Breakout", "family": StrategyFamily.BREAKOUT, 
             "lifecycle": StrategyLifecycle.APPROVED, "pf": 2.1, "wr": 0.64, "sharpe": 1.8, "trades": 500},
            {"id": "DOUBLE_BOTTOM", "name": "Double Bottom", "family": StrategyFamily.REVERSAL,
             "lifecycle": StrategyLifecycle.APPROVED, "pf": 2.3, "wr": 0.66, "sharpe": 1.9, "trades": 480},
            {"id": "DOUBLE_TOP", "name": "Double Top", "family": StrategyFamily.REVERSAL,
             "lifecycle": StrategyLifecycle.APPROVED, "pf": 2.0, "wr": 0.63, "sharpe": 1.7, "trades": 450},
            {"id": "CHANNEL_BREAKOUT", "name": "Channel Breakout", "family": StrategyFamily.BREAKOUT,
             "lifecycle": StrategyLifecycle.APPROVED, "pf": 1.8, "wr": 0.58, "sharpe": 1.5, "trades": 420},
            {"id": "MOMENTUM_CONTINUATION", "name": "Momentum Continuation", "family": StrategyFamily.CONTINUATION,
             "lifecycle": StrategyLifecycle.APPROVED, "pf": 1.9, "wr": 0.62, "sharpe": 1.6, "trades": 460},
            {"id": "HEAD_SHOULDERS", "name": "Head & Shoulders", "family": StrategyFamily.PATTERN,
             "lifecycle": StrategyLifecycle.LIMITED, "pf": 1.25, "wr": 0.52, "sharpe": 0.9, "trades": 180},
            {"id": "HARMONIC_ABCD", "name": "Harmonic ABCD", "family": StrategyFamily.HARMONIC,
             "lifecycle": StrategyLifecycle.LIMITED, "pf": 1.4, "wr": 0.54, "sharpe": 1.0, "trades": 150},
            {"id": "WEDGE_RISING", "name": "Rising Wedge", "family": StrategyFamily.PATTERN,
             "lifecycle": StrategyLifecycle.LIMITED, "pf": 1.15, "wr": 0.51, "sharpe": 0.7, "trades": 120},
            {"id": "WEDGE_FALLING", "name": "Falling Wedge", "family": StrategyFamily.PATTERN,
             "lifecycle": StrategyLifecycle.LIMITED, "pf": 1.2, "wr": 0.53, "sharpe": 0.8, "trades": 130},
            {"id": "LIQUIDITY_SWEEP", "name": "Liquidity Sweep", "family": StrategyFamily.EXPERIMENTAL,
             "lifecycle": StrategyLifecycle.DEPRECATED, "pf": 0.85, "wr": 0.42, "sharpe": 0.3, "trades": 200},
            {"id": "RANGE_REVERSAL", "name": "Range Reversal", "family": StrategyFamily.EXPERIMENTAL,
             "lifecycle": StrategyLifecycle.DEPRECATED, "pf": 0.72, "wr": 0.36, "sharpe": 0.1, "trades": 180},
        ]
        
        for s in default_strategies:
            record = StrategyRecord(
                strategy_id=s["id"],
                name=s["name"],
                family=s["family"],
                lifecycle=s["lifecycle"],
                trades=s.get("trades", 0),
                win_rate=s.get("wr", 0),
                profit_factor=s.get("pf", 1.0),
                sharpe=s.get("sharpe", 0),
                max_drawdown=0.15,
                created_at=int(time.time() * 1000) - 86400000 * 180,  # 180 days ago
                last_status_change=int(time.time() * 1000)
            )
            
            # Set budget based on lifecycle
            record.budget = self._get_default_budget(s["id"], s["lifecycle"])
            
            self._strategies[s["id"]] = record
    
    def _get_default_budget(self, strategy_id: str, lifecycle: StrategyLifecycle) -> StrategyBudget:
        """Get default budget for lifecycle status"""
        defaults = self.config.get("default_budgets", {})
        budget_config = defaults.get(lifecycle.value, {})
        
        return StrategyBudget(
            strategy_id=strategy_id,
            risk_budget=budget_config.get("risk", 0.02),
            capital_budget=budget_config.get("capital", 0.10),
            max_concurrent_trades=budget_config.get("max_trades", 3),
            max_daily_trades=budget_config.get("max_trades", 3) * 2,
            allowed_assets=["BTC", "ETH", "SOL", "SPX", "GOLD", "DXY"],
            allowed_regimes=["TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION"],
            is_active=lifecycle not in [StrategyLifecycle.DISABLED, StrategyLifecycle.DEPRECATED, StrategyLifecycle.ARCHIVED]
        )
    
    def get_strategy(self, strategy_id: str) -> Optional[StrategyRecord]:
        """Get strategy record"""
        return self._strategies.get(strategy_id)
    
    def get_all_strategies(self) -> Dict[str, StrategyRecord]:
        """Get all strategies"""
        return self._strategies
    
    def get_strategies_by_lifecycle(self, lifecycle: StrategyLifecycle) -> List[StrategyRecord]:
        """Get strategies by lifecycle status"""
        return [s for s in self._strategies.values() if s.lifecycle == lifecycle]
    
    def get_strategies_by_family(self, family: StrategyFamily) -> List[StrategyRecord]:
        """Get strategies by family"""
        return [s for s in self._strategies.values() if s.family == family]
    
    def promote(self, strategy_id: str, to_status: StrategyLifecycle, force: bool = False) -> PromotionResult:
        """
        Promote strategy to new status.
        
        Args:
            strategy_id: Strategy identifier
            to_status: Target lifecycle status
            force: Skip criteria check
        """
        strategy = self._strategies.get(strategy_id)
        
        if not strategy:
            return PromotionResult(
                strategy_id=strategy_id,
                success=False,
                from_status=StrategyLifecycle.CANDIDATE,
                to_status=to_status,
                reason="Strategy not found",
                timestamp=int(time.time() * 1000)
            )
        
        from_status = strategy.lifecycle
        
        # Check if transition is valid
        valid_transitions = self._get_valid_transitions(from_status)
        
        if to_status not in valid_transitions and not force:
            return PromotionResult(
                strategy_id=strategy_id,
                success=False,
                from_status=from_status,
                to_status=to_status,
                reason=f"Invalid transition from {from_status.value} to {to_status.value}",
                timestamp=int(time.time() * 1000)
            )
        
        # Check criteria
        criteria_met = {}
        if not force:
            criteria_key = f"{from_status.value}_to_{to_status.value}"
            criteria = self.config.get("promotion_criteria", {}).get(criteria_key, {})
            
            criteria_met["min_trades"] = strategy.trades >= criteria.get("min_trades", 0)
            criteria_met["min_pf"] = strategy.profit_factor >= criteria.get("min_pf", 0)
            criteria_met["min_wr"] = strategy.win_rate >= criteria.get("min_wr", 0)
            criteria_met["max_dd"] = strategy.max_drawdown <= criteria.get("max_dd", 1.0)
            
            if not all(criteria_met.values()):
                failed = [k for k, v in criteria_met.items() if not v]
                return PromotionResult(
                    strategy_id=strategy_id,
                    success=False,
                    from_status=from_status,
                    to_status=to_status,
                    reason=f"Criteria not met: {', '.join(failed)}",
                    criteria_met=criteria_met,
                    timestamp=int(time.time() * 1000)
                )
        
        # Execute promotion
        strategy.lifecycle = to_status
        strategy.last_status_change = int(time.time() * 1000)
        strategy.status_history.append({
            "from": from_status.value,
            "to": to_status.value,
            "at": strategy.last_status_change,
            "forced": force
        })
        
        # Update budget
        strategy.budget = self._get_default_budget(strategy_id, to_status)
        
        result = PromotionResult(
            strategy_id=strategy_id,
            success=True,
            from_status=from_status,
            to_status=to_status,
            reason="Promotion successful",
            criteria_met=criteria_met,
            timestamp=int(time.time() * 1000)
        )
        
        self._history.append(result)
        return result
    
    def demote(self, strategy_id: str, to_status: StrategyLifecycle, reason: str = "") -> PromotionResult:
        """Demote strategy to lower status"""
        strategy = self._strategies.get(strategy_id)
        
        if not strategy:
            return PromotionResult(
                strategy_id=strategy_id,
                success=False,
                from_status=StrategyLifecycle.CANDIDATE,
                to_status=to_status,
                reason="Strategy not found",
                timestamp=int(time.time() * 1000)
            )
        
        from_status = strategy.lifecycle
        
        # Execute demotion
        strategy.lifecycle = to_status
        strategy.last_status_change = int(time.time() * 1000)
        strategy.status_history.append({
            "from": from_status.value,
            "to": to_status.value,
            "at": strategy.last_status_change,
            "reason": reason
        })
        
        # Update budget
        strategy.budget = self._get_default_budget(strategy_id, to_status)
        
        result = PromotionResult(
            strategy_id=strategy_id,
            success=True,
            from_status=from_status,
            to_status=to_status,
            reason=reason or "Demotion executed",
            timestamp=int(time.time() * 1000)
        )
        
        self._history.append(result)
        return result
    
    def _get_valid_transitions(self, current: StrategyLifecycle) -> List[StrategyLifecycle]:
        """Get valid transitions from current status"""
        transitions = {
            StrategyLifecycle.CANDIDATE: [StrategyLifecycle.TESTING],
            StrategyLifecycle.TESTING: [StrategyLifecycle.LIMITED, StrategyLifecycle.DEPRECATED],
            StrategyLifecycle.LIMITED: [StrategyLifecycle.APPROVED, StrategyLifecycle.WATCH, StrategyLifecycle.DEPRECATED],
            StrategyLifecycle.APPROVED: [StrategyLifecycle.WATCH, StrategyLifecycle.DEGRADED],
            StrategyLifecycle.WATCH: [StrategyLifecycle.APPROVED, StrategyLifecycle.DEGRADED],
            StrategyLifecycle.DEGRADED: [StrategyLifecycle.WATCH, StrategyLifecycle.DISABLED],
            StrategyLifecycle.DISABLED: [StrategyLifecycle.DEPRECATED, StrategyLifecycle.TESTING],
            StrategyLifecycle.DEPRECATED: [StrategyLifecycle.ARCHIVED],
            StrategyLifecycle.ARCHIVED: []
        }
        return transitions.get(current, [])
    
    def get_promotion_history(self) -> List[PromotionResult]:
        """Get promotion/demotion history"""
        return self._history


# ═══════════════════════════════════════════════════════════════
# Strategy Family Manager
# ═══════════════════════════════════════════════════════════════

class StrategyFamilyManager:
    """
    Manages strategy families.
    
    - Family allocations
    - Family exposure limits
    - Family enable/disable
    """
    
    def __init__(self, config: Optional[Dict] = None, lifecycle_manager: Optional[StrategyLifecycleManager] = None):
        self.config = config or STRATEGY_GOVERNANCE_CONFIG
        self.lifecycle_manager = lifecycle_manager or StrategyLifecycleManager(config)
        self._family_settings: Dict[str, FamilyAllocation] = {}
        
        self._init_families()
    
    def _init_families(self):
        """Initialize family allocations"""
        family_config = self.config.get("family_allocations", {})
        
        for family in StrategyFamily:
            config = family_config.get(family.value, {})
            strategies = self.lifecycle_manager.get_strategies_by_family(family)
            strategy_ids = [s.strategy_id for s in strategies]
            
            self._family_settings[family.value] = FamilyAllocation(
                family=family,
                name=family.value.replace("_", " ").title(),
                strategies=strategy_ids,
                allocation_pct=config.get("target", 0.2),
                current_pct=len(strategy_ids) * 0.05,  # Simplified
                max_strategies=config.get("max_strategies", 5),
                is_active=True
            )
    
    def get_family(self, family: StrategyFamily) -> Optional[FamilyAllocation]:
        """Get family allocation"""
        return self._family_settings.get(family.value)
    
    def get_all_families(self) -> Dict[str, FamilyAllocation]:
        """Get all family allocations"""
        return self._family_settings
    
    def set_family_allocation(self, family: StrategyFamily, allocation_pct: float):
        """Set family target allocation"""
        if family.value in self._family_settings:
            self._family_settings[family.value].allocation_pct = allocation_pct
    
    def disable_family(self, family: StrategyFamily) -> bool:
        """Disable a strategy family"""
        if family.value in self._family_settings:
            self._family_settings[family.value].is_active = False
            return True
        return False
    
    def enable_family(self, family: StrategyFamily) -> bool:
        """Enable a strategy family"""
        if family.value in self._family_settings:
            self._family_settings[family.value].is_active = True
            return True
        return False
    
    def get_family_exposure(self) -> Dict[str, Dict]:
        """Get current exposure by family"""
        exposure = {}
        
        for family_name, family in self._family_settings.items():
            active_strategies = [
                s for s in family.strategies
                if self.lifecycle_manager.get_strategy(s) and
                self.lifecycle_manager.get_strategy(s).lifecycle in 
                [StrategyLifecycle.APPROVED, StrategyLifecycle.LIMITED]
            ]
            
            exposure[family_name] = {
                "target": family.allocation_pct,
                "current": len(active_strategies) * 0.05,
                "strategies": len(family.strategies),
                "activeStrategies": len(active_strategies),
                "isActive": family.is_active
            }
        
        return exposure


# ═══════════════════════════════════════════════════════════════
# Strategy Budget Manager
# ═══════════════════════════════════════════════════════════════

class StrategyBudgetManager:
    """
    Manages strategy budgets.
    
    - Risk budgets
    - Capital budgets
    - Trade limits
    - Asset/regime restrictions
    """
    
    def __init__(self, lifecycle_manager: Optional[StrategyLifecycleManager] = None):
        self.lifecycle_manager = lifecycle_manager or StrategyLifecycleManager()
    
    def get_budget(self, strategy_id: str) -> Optional[StrategyBudget]:
        """Get budget for strategy"""
        strategy = self.lifecycle_manager.get_strategy(strategy_id)
        return strategy.budget if strategy else None
    
    def set_budget(
        self,
        strategy_id: str,
        risk_budget: Optional[float] = None,
        capital_budget: Optional[float] = None,
        max_concurrent: Optional[int] = None,
        max_daily: Optional[int] = None
    ) -> bool:
        """Set budget parameters for strategy"""
        strategy = self.lifecycle_manager.get_strategy(strategy_id)
        if not strategy or not strategy.budget:
            return False
        
        if risk_budget is not None:
            strategy.budget.risk_budget = risk_budget
        if capital_budget is not None:
            strategy.budget.capital_budget = capital_budget
        if max_concurrent is not None:
            strategy.budget.max_concurrent_trades = max_concurrent
        if max_daily is not None:
            strategy.budget.max_daily_trades = max_daily
        
        return True
    
    def set_allowed_assets(self, strategy_id: str, assets: List[str]) -> bool:
        """Set allowed assets for strategy"""
        strategy = self.lifecycle_manager.get_strategy(strategy_id)
        if not strategy or not strategy.budget:
            return False
        
        strategy.budget.allowed_assets = assets
        return True
    
    def set_allowed_regimes(self, strategy_id: str, regimes: List[str]) -> bool:
        """Set allowed regimes for strategy"""
        strategy = self.lifecycle_manager.get_strategy(strategy_id)
        if not strategy or not strategy.budget:
            return False
        
        strategy.budget.allowed_regimes = regimes
        return True
    
    def get_all_budgets(self) -> Dict[str, StrategyBudget]:
        """Get all strategy budgets"""
        budgets = {}
        for strategy_id, strategy in self.lifecycle_manager.get_all_strategies().items():
            if strategy.budget:
                budgets[strategy_id] = strategy.budget
        return budgets
    
    def get_total_risk_allocation(self) -> float:
        """Get total risk allocation across all active strategies"""
        total = 0.0
        for strategy in self.lifecycle_manager.get_all_strategies().values():
            if strategy.budget and strategy.budget.is_active:
                total += strategy.budget.risk_budget
        return total


# ═══════════════════════════════════════════════════════════════
# Strategy Governance Service
# ═══════════════════════════════════════════════════════════════

class StrategyGovernanceService:
    """
    Main Strategy Governance Service.
    
    Orchestrates:
    - Lifecycle management
    - Family management
    - Budget management
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or STRATEGY_GOVERNANCE_CONFIG
        
        self.lifecycle_manager = StrategyLifecycleManager(config)
        self.family_manager = StrategyFamilyManager(config, self.lifecycle_manager)
        self.budget_manager = StrategyBudgetManager(self.lifecycle_manager)
    
    def get_governance_status(self) -> Dict:
        """Get overall governance status"""
        strategies = self.lifecycle_manager.get_all_strategies()
        
        by_lifecycle = {}
        for lifecycle in StrategyLifecycle:
            count = len([s for s in strategies.values() if s.lifecycle == lifecycle])
            if count > 0:
                by_lifecycle[lifecycle.value] = count
        
        by_family = {}
        for family in StrategyFamily:
            count = len([s for s in strategies.values() if s.family == family])
            if count > 0:
                by_family[family.value] = count
        
        return {
            "totalStrategies": len(strategies),
            "byLifecycle": by_lifecycle,
            "byFamily": by_family,
            "totalRiskAllocation": round(self.budget_manager.get_total_risk_allocation(), 4),
            "familyExposure": self.family_manager.get_family_exposure(),
            "version": self.config.get("version", "phase9.25B"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": self.config.get("enabled", True),
            "version": self.config.get("version", "phase9.25B"),
            "status": "ok",
            "components": {
                "lifecycle_manager": "ok",
                "family_manager": "ok",
                "budget_manager": "ok"
            },
            "strategiesCount": len(self.lifecycle_manager.get_all_strategies()),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


# ═══════════════════════════════════════════════════════════════
# Serialization Functions
# ═══════════════════════════════════════════════════════════════

def strategy_record_to_dict(record: StrategyRecord) -> Dict:
    """Convert StrategyRecord to dict"""
    return {
        "strategyId": record.strategy_id,
        "name": record.name,
        "family": record.family.value,
        "lifecycle": record.lifecycle.value,
        "metrics": {
            "trades": record.trades,
            "winRate": record.win_rate,
            "profitFactor": record.profit_factor,
            "sharpe": record.sharpe,
            "maxDrawdown": record.max_drawdown
        },
        "budget": budget_to_dict(record.budget) if record.budget else None,
        "createdAt": record.created_at,
        "lastTradeAt": record.last_trade_at,
        "lastStatusChange": record.last_status_change,
        "statusHistoryCount": len(record.status_history),
        "notes": record.notes
    }


def budget_to_dict(budget: StrategyBudget) -> Dict:
    """Convert StrategyBudget to dict"""
    return {
        "strategyId": budget.strategy_id,
        "riskBudget": budget.risk_budget,
        "capitalBudget": budget.capital_budget,
        "maxConcurrentTrades": budget.max_concurrent_trades,
        "maxDailyTrades": budget.max_daily_trades,
        "allowedAssets": budget.allowed_assets,
        "allowedRegimes": budget.allowed_regimes,
        "isActive": budget.is_active
    }


def family_to_dict(family: FamilyAllocation) -> Dict:
    """Convert FamilyAllocation to dict"""
    return {
        "family": family.family.value,
        "name": family.name,
        "strategies": family.strategies,
        "allocationPct": family.allocation_pct,
        "currentPct": family.current_pct,
        "maxStrategies": family.max_strategies,
        "isActive": family.is_active,
        "notes": family.notes
    }


def promotion_result_to_dict(result: PromotionResult) -> Dict:
    """Convert PromotionResult to dict"""
    return {
        "strategyId": result.strategy_id,
        "success": result.success,
        "fromStatus": result.from_status.value,
        "toStatus": result.to_status.value,
        "reason": result.reason,
        "criteriaMet": result.criteria_met,
        "timestamp": result.timestamp
    }
