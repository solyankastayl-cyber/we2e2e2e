"""
Phase 9.25E: Policy-based Admin Cockpit
=======================================

Слой управления системой через политики.

Принцип: админ управляет политиками, а не кодом.

Компоненты:
1. Policy Manager — управление YAML политиками
2. Strategy Control — ручное управление стратегиями
3. Self-Healing Overrides — переопределение auto-healing
4. Portfolio Policies — лимиты портфеля
5. Governance History — история всех изменений

API:
- GET /api/admin/policies
- POST /api/admin/policies/update
- GET /api/admin/policies/history
- POST /api/admin/control/strategy/{action}
- GET /api/admin/dashboard
"""
import os
import time
import json
import hashlib
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# Types & Enums
# ═══════════════════════════════════════════════════════════════

class PolicyType(str, Enum):
    """Types of policies"""
    STRATEGY = "strategy_policies"
    SELF_HEALING = "self_healing_policies"
    PORTFOLIO = "portfolio_policies"
    EDGE_GUARD = "edge_guard_policies"
    VALIDATION = "validation_policies"
    RISK = "risk_policies"


class ControlAction(str, Enum):
    """Admin control actions"""
    PROMOTE = "PROMOTE"
    DEMOTE = "DEMOTE"
    FREEZE = "FREEZE"
    UNFREEZE = "UNFREEZE"
    DISABLE = "DISABLE"
    ENABLE = "ENABLE"
    FORCE_RECOVERY = "FORCE_RECOVERY"
    FORCE_DEMOTION = "FORCE_DEMOTION"
    SET_WEIGHT = "SET_WEIGHT"
    SET_BUDGET = "SET_BUDGET"


class ChangeType(str, Enum):
    """Types of governance changes"""
    POLICY_UPDATE = "POLICY_UPDATE"
    STRATEGY_CONTROL = "STRATEGY_CONTROL"
    OVERRIDE = "OVERRIDE"
    ROLLBACK = "ROLLBACK"
    SYSTEM_CONFIG = "SYSTEM_CONFIG"


@dataclass
class PolicyChange:
    """Record of a policy change"""
    change_id: str
    change_type: ChangeType
    policy_type: Optional[PolicyType]
    
    author: str
    timestamp: int
    
    old_value: Any
    new_value: Any
    diff: Dict = field(default_factory=dict)
    
    reason: str = ""
    rollback_id: Optional[str] = None  # If this is a rollback, reference original


@dataclass
class PolicyVersion:
    """Versioned policy snapshot"""
    version_id: str
    version_number: int
    policies: Dict[str, Any]
    
    created_at: int
    created_by: str
    checksum: str
    
    is_active: bool = False
    notes: str = ""


@dataclass
class ControlResult:
    """Result of an admin control action"""
    success: bool
    action: ControlAction
    target: str
    
    old_state: str = ""
    new_state: str = ""
    
    message: str = ""
    timestamp: int = 0


@dataclass
class AdminDashboard:
    """Admin dashboard summary"""
    # System status
    system_status: str = "HEALTHY"
    active_policies_version: int = 1
    
    # Strategies
    total_strategies: int = 0
    healthy_strategies: int = 0
    degraded_strategies: int = 0
    frozen_strategies: int = 0
    
    # Self-healing
    self_healing_enabled: bool = True
    recent_demotions: int = 0
    recent_recoveries: int = 0
    
    # Portfolio
    current_exposure: float = 0.0
    max_exposure: float = 1.5
    kill_switch_active: bool = False
    
    # Governance
    recent_policy_changes: int = 0
    pending_approvals: int = 0
    
    last_update: int = 0


# ═══════════════════════════════════════════════════════════════
# Default Policies
# ═══════════════════════════════════════════════════════════════

DEFAULT_POLICIES = {
    "strategy_policies": {
        "version": "1.0.0",
        "max_family_exposure": 0.35,
        "max_strategy_exposure": 0.15,
        "max_concurrent_trades_per_strategy": 5,
        "max_daily_trades_per_strategy": 10,
        "promotion_criteria": {
            "min_trades": 200,
            "min_pf": 1.3,
            "min_sharpe": 0.8,
            "max_dd": 0.25
        },
        "demotion_criteria": {
            "min_pf_decline": 0.15,
            "consecutive_warning_windows": 2
        },
        "family_budgets": {
            "breakout_family": 0.35,
            "continuation_family": 0.30,
            "reversal_family": 0.20,
            "pattern_family": 0.10,
            "experimental_family": 0.05
        }
    },
    
    "self_healing_policies": {
        "version": "1.0.0",
        "enabled": True,
        "mode": "AUTO",  # AUTO, MANUAL, DISABLED
        "health_thresholds": {
            "healthy": 0.80,
            "warning": 0.60,
            "degraded": 0.40,
            "critical": 0.25
        },
        "weight_adjustment": {
            "healthy": 1.0,
            "warning": 0.75,
            "degraded": 0.40,
            "critical": 0.0
        },
        "weight_limits": {
            "max_daily_change": 0.10,
            "max_weekly_change": 0.25
        },
        "recovery_rules": {
            "min_trades": 50,
            "min_pf": 1.2,
            "min_sharpe": 0.8,
            "grace_period_days": 14
        },
        "rolling_windows": {
            "short": 50,
            "mid": 150,
            "long": 400
        }
    },
    
    "portfolio_policies": {
        "version": "1.0.0",
        "exposure_limits": {
            "max_gross": 1.5,
            "max_net": 1.0,
            "max_per_asset": 0.30,
            "max_per_strategy": 0.20,
            "max_per_family": 0.40
        },
        "correlation_limits": {
            "max_pairwise": 0.70,
            "avg_threshold": 0.50,
            "budget": 0.65
        },
        "kill_switch": {
            "max_drawdown": 0.20,
            "correlation_spike": 0.85,
            "volatility_multiplier": 3.0,
            "consecutive_losses": 10
        },
        "risk_modes": {
            "normal": {"exposure_mult": 1.0},
            "caution": {"exposure_mult": 0.7},
            "safe": {"exposure_mult": 0.3},
            "halt": {"exposure_mult": 0.0}
        }
    },
    
    "edge_guard_policies": {
        "version": "1.0.0",
        "decay_thresholds": {
            "pf_degraded": -0.15,
            "pf_watch": -0.25,
            "pf_disabled": -0.40
        },
        "overfit_thresholds": {
            "train_test_divergence_medium": 0.15,
            "train_test_divergence_high": 0.25,
            "regime_concentration_high": 0.80
        },
        "drift_thresholds": {
            "atr_shift_moderate": 0.20,
            "trend_change_moderate": 0.15
        }
    },
    
    "validation_policies": {
        "version": "1.0.0",
        "release_criteria": {
            "min_pf": 1.5,
            "min_wr": 0.52,
            "min_sharpe": 1.0,
            "max_dd": 0.20,
            "min_trades": 200,
            "guardrails_required": True,
            "isolation_required": True
        },
        "regression_thresholds": {
            "pf_decline": 0.10,
            "wr_decline": 0.03,
            "dd_increase": 0.05
        }
    },
    
    "risk_policies": {
        "version": "1.0.0",
        "max_portfolio_risk": 0.02,
        "max_single_trade_risk": 0.01,
        "daily_loss_limit": 0.05,
        "weekly_loss_limit": 0.10,
        "monthly_loss_limit": 0.15,
        "position_sizing": {
            "method": "ATR",
            "atr_multiplier": 2.0
        }
    }
}


# ═══════════════════════════════════════════════════════════════
# Policy Manager
# ═══════════════════════════════════════════════════════════════

class PolicyManager:
    """
    Manages system policies.
    
    - Load/save policies
    - Version control
    - Validation
    - Rollback
    """
    
    def __init__(self, policies_dir: str = "/app/backend/policies"):
        self.policies_dir = Path(policies_dir)
        self.policies_dir.mkdir(parents=True, exist_ok=True)
        
        self._active_policies: Dict[str, Any] = {}
        self._versions: List[PolicyVersion] = []
        self._current_version: int = 0
        
        # Load or initialize
        self._load_or_init()
    
    def _load_or_init(self):
        """Load existing policies or initialize defaults"""
        master_file = self.policies_dir / "master_policies.yaml"
        
        if master_file.exists():
            with open(master_file, 'r') as f:
                self._active_policies = yaml.safe_load(f) or {}
                self._current_version = self._active_policies.get("_meta", {}).get("version", 1)
        else:
            self._active_policies = DEFAULT_POLICIES.copy()
            self._active_policies["_meta"] = {
                "version": 1,
                "created_at": int(time.time() * 1000),
                "last_modified": int(time.time() * 1000)
            }
            self._current_version = 1
            self._save_policies()
    
    def _save_policies(self):
        """Save policies to file"""
        master_file = self.policies_dir / "master_policies.yaml"
        
        self._active_policies["_meta"]["last_modified"] = int(time.time() * 1000)
        
        with open(master_file, 'w') as f:
            yaml.dump(self._active_policies, f, default_flow_style=False)
    
    def get_policies(self, policy_type: Optional[PolicyType] = None) -> Dict:
        """Get all policies or specific type"""
        if policy_type:
            return self._active_policies.get(policy_type.value, {})
        return {k: v for k, v in self._active_policies.items() if not k.startswith("_")}
    
    def get_policy_value(self, policy_type: PolicyType, path: str) -> Any:
        """Get specific policy value by path (e.g., 'health_thresholds.warning')"""
        policies = self._active_policies.get(policy_type.value, {})
        
        keys = path.split(".")
        value = policies
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    def update_policy(
        self,
        policy_type: PolicyType,
        updates: Dict,
        author: str = "system",
        reason: str = ""
    ) -> PolicyChange:
        """Update a policy section"""
        old_value = self._active_policies.get(policy_type.value, {}).copy()
        
        # Deep merge updates
        if policy_type.value not in self._active_policies:
            self._active_policies[policy_type.value] = {}
        
        self._deep_merge(self._active_policies[policy_type.value], updates)
        
        # Update version
        self._current_version += 1
        self._active_policies["_meta"]["version"] = self._current_version
        
        # Save
        self._save_policies()
        
        # Create change record
        change = PolicyChange(
            change_id=f"change_{int(time.time() * 1000)}",
            change_type=ChangeType.POLICY_UPDATE,
            policy_type=policy_type,
            author=author,
            timestamp=int(time.time() * 1000),
            old_value=old_value,
            new_value=self._active_policies[policy_type.value],
            diff=self._compute_diff(old_value, updates),
            reason=reason
        )
        
        return change
    
    def create_version_snapshot(self, author: str = "system", notes: str = "") -> PolicyVersion:
        """Create a versioned snapshot of current policies"""
        import copy
        
        checksum = hashlib.sha256(
            json.dumps(self._active_policies, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        version = PolicyVersion(
            version_id=f"v{self._current_version}_{int(time.time())}",
            version_number=self._current_version,
            policies=copy.deepcopy(self._active_policies),  # Deep copy for immutability
            created_at=int(time.time() * 1000),
            created_by=author,
            checksum=checksum,
            is_active=True,
            notes=notes
        )
        
        # Deactivate previous versions
        for v in self._versions:
            v.is_active = False
        
        self._versions.append(version)
        
        # Save snapshot
        snapshot_file = self.policies_dir / f"snapshot_v{self._current_version}.yaml"
        with open(snapshot_file, 'w') as f:
            yaml.dump(self._active_policies, f, default_flow_style=False)
        
        return version
    
    def rollback(self, version_id: str, author: str = "system") -> Tuple[bool, str]:
        """Rollback to a previous version"""
        import copy
        
        target_version = None
        for v in self._versions:
            if v.version_id == version_id:
                target_version = v
                break
        
        if not target_version:
            return False, f"Version {version_id} not found"
        
        # Deep copy to avoid reference issues
        self._active_policies = copy.deepcopy(target_version.policies)
        self._current_version += 1
        self._active_policies["_meta"]["version"] = self._current_version
        self._active_policies["_meta"]["rollback_from"] = version_id
        
        self._save_policies()
        
        return True, f"Rolled back to {version_id}"
    
    def get_versions(self) -> List[Dict]:
        """Get all version snapshots"""
        return [
            {
                "versionId": v.version_id,
                "versionNumber": v.version_number,
                "createdAt": v.created_at,
                "createdBy": v.created_by,
                "checksum": v.checksum,
                "isActive": v.is_active,
                "notes": v.notes
            }
            for v in self._versions
        ]
    
    def validate_policy(self, policy_type: PolicyType, policy: Dict) -> Tuple[bool, List[str]]:
        """Validate a policy structure after merging with current values"""
        errors = []
        
        # Get current policies to merge with updates
        current = self._active_policies.get(policy_type.value, {}).copy()
        
        # Create merged version for validation
        merged = current.copy()
        self._deep_merge(merged, policy)
        
        if policy_type == PolicyType.SELF_HEALING:
            if "health_thresholds" in merged:
                thresholds = merged["health_thresholds"]
                healthy = thresholds.get("healthy", 0.80)
                warning = thresholds.get("warning", 0.60)
                degraded = thresholds.get("degraded", 0.40)
                
                if healthy <= warning:
                    errors.append("healthy threshold must be > warning")
                if warning <= degraded:
                    errors.append("warning threshold must be > degraded")
        
        elif policy_type == PolicyType.PORTFOLIO:
            if "exposure_limits" in merged:
                limits = merged["exposure_limits"]
                max_per_strategy = limits.get("max_per_strategy", 0)
                max_gross = limits.get("max_gross", 1)
                
                if max_per_strategy > max_gross:
                    errors.append("max_per_strategy cannot exceed max_gross")
        
        return len(errors) == 0, errors
    
    def _deep_merge(self, base: Dict, updates: Dict):
        """Deep merge updates into base dict"""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _compute_diff(self, old: Dict, new: Dict) -> Dict:
        """Compute diff between old and new values"""
        diff = {}
        for key, value in new.items():
            if key not in old:
                diff[key] = {"added": value}
            elif old[key] != value:
                diff[key] = {"old": old[key], "new": value}
        return diff


# ═══════════════════════════════════════════════════════════════
# Strategy Controller
# ═══════════════════════════════════════════════════════════════

class StrategyController:
    """
    Manual control over strategies.
    
    - Promote/demote
    - Freeze/unfreeze
    - Enable/disable
    - Force recovery
    """
    
    def __init__(self):
        self._frozen_strategies: set = set()
        self._overrides: Dict[str, Dict] = {}
        self._control_history: List[ControlResult] = []
    
    def execute(self, action: ControlAction, strategy_id: str, params: Optional[Dict] = None) -> ControlResult:
        """Execute a control action"""
        params = params or {}
        
        if action == ControlAction.FREEZE:
            return self._freeze(strategy_id)
        elif action == ControlAction.UNFREEZE:
            return self._unfreeze(strategy_id)
        elif action == ControlAction.PROMOTE:
            return self._promote(strategy_id, params.get("to_status"))
        elif action == ControlAction.DEMOTE:
            return self._demote(strategy_id, params.get("to_status"), params.get("reason", ""))
        elif action == ControlAction.DISABLE:
            return self._disable(strategy_id, params.get("reason", ""))
        elif action == ControlAction.ENABLE:
            return self._enable(strategy_id)
        elif action == ControlAction.FORCE_RECOVERY:
            return self._force_recovery(strategy_id)
        elif action == ControlAction.FORCE_DEMOTION:
            return self._force_demotion(strategy_id, params.get("to_status"))
        elif action == ControlAction.SET_WEIGHT:
            return self._set_weight(strategy_id, params.get("weight", 1.0))
        elif action == ControlAction.SET_BUDGET:
            return self._set_budget(strategy_id, params.get("budget", {}))
        else:
            return ControlResult(
                success=False,
                action=action,
                target=strategy_id,
                message=f"Unknown action: {action.value}",
                timestamp=int(time.time() * 1000)
            )
    
    def _freeze(self, strategy_id: str) -> ControlResult:
        """Freeze strategy from auto-healing"""
        self._frozen_strategies.add(strategy_id)
        self._overrides[strategy_id] = {
            "frozen": True,
            "frozen_at": int(time.time() * 1000)
        }
        
        result = ControlResult(
            success=True,
            action=ControlAction.FREEZE,
            target=strategy_id,
            old_state="active",
            new_state="frozen",
            message=f"Strategy {strategy_id} frozen from auto-healing",
            timestamp=int(time.time() * 1000)
        )
        self._control_history.append(result)
        return result
    
    def _unfreeze(self, strategy_id: str) -> ControlResult:
        """Unfreeze strategy"""
        self._frozen_strategies.discard(strategy_id)
        if strategy_id in self._overrides:
            self._overrides[strategy_id]["frozen"] = False
        
        result = ControlResult(
            success=True,
            action=ControlAction.UNFREEZE,
            target=strategy_id,
            old_state="frozen",
            new_state="active",
            message=f"Strategy {strategy_id} unfrozen",
            timestamp=int(time.time() * 1000)
        )
        self._control_history.append(result)
        return result
    
    def _promote(self, strategy_id: str, to_status: Optional[str]) -> ControlResult:
        """Promote strategy lifecycle"""
        to_status = to_status or "APPROVED"
        
        self._overrides[strategy_id] = self._overrides.get(strategy_id, {})
        old_status = self._overrides.get(strategy_id, {}).get("lifecycle", "LIMITED")
        self._overrides[strategy_id]["lifecycle"] = to_status
        self._overrides[strategy_id]["promoted_at"] = int(time.time() * 1000)
        
        result = ControlResult(
            success=True,
            action=ControlAction.PROMOTE,
            target=strategy_id,
            old_state=old_status,
            new_state=to_status,
            message=f"Strategy {strategy_id} promoted to {to_status}",
            timestamp=int(time.time() * 1000)
        )
        self._control_history.append(result)
        return result
    
    def _demote(self, strategy_id: str, to_status: Optional[str], reason: str) -> ControlResult:
        """Demote strategy lifecycle"""
        to_status = to_status or "WATCH"
        
        self._overrides[strategy_id] = self._overrides.get(strategy_id, {})
        old_status = self._overrides.get(strategy_id, {}).get("lifecycle", "APPROVED")
        self._overrides[strategy_id]["lifecycle"] = to_status
        self._overrides[strategy_id]["demoted_at"] = int(time.time() * 1000)
        self._overrides[strategy_id]["demotion_reason"] = reason
        
        result = ControlResult(
            success=True,
            action=ControlAction.DEMOTE,
            target=strategy_id,
            old_state=old_status,
            new_state=to_status,
            message=f"Strategy {strategy_id} demoted to {to_status}: {reason}",
            timestamp=int(time.time() * 1000)
        )
        self._control_history.append(result)
        return result
    
    def _disable(self, strategy_id: str, reason: str) -> ControlResult:
        """Disable strategy"""
        self._overrides[strategy_id] = self._overrides.get(strategy_id, {})
        self._overrides[strategy_id]["enabled"] = False
        self._overrides[strategy_id]["disabled_at"] = int(time.time() * 1000)
        self._overrides[strategy_id]["disable_reason"] = reason
        
        result = ControlResult(
            success=True,
            action=ControlAction.DISABLE,
            target=strategy_id,
            old_state="enabled",
            new_state="disabled",
            message=f"Strategy {strategy_id} disabled: {reason}",
            timestamp=int(time.time() * 1000)
        )
        self._control_history.append(result)
        return result
    
    def _enable(self, strategy_id: str) -> ControlResult:
        """Enable strategy"""
        self._overrides[strategy_id] = self._overrides.get(strategy_id, {})
        self._overrides[strategy_id]["enabled"] = True
        
        result = ControlResult(
            success=True,
            action=ControlAction.ENABLE,
            target=strategy_id,
            old_state="disabled",
            new_state="enabled",
            message=f"Strategy {strategy_id} enabled",
            timestamp=int(time.time() * 1000)
        )
        self._control_history.append(result)
        return result
    
    def _force_recovery(self, strategy_id: str) -> ControlResult:
        """Force start recovery for strategy"""
        self._overrides[strategy_id] = self._overrides.get(strategy_id, {})
        self._overrides[strategy_id]["force_recovery"] = True
        self._overrides[strategy_id]["recovery_started_at"] = int(time.time() * 1000)
        
        result = ControlResult(
            success=True,
            action=ControlAction.FORCE_RECOVERY,
            target=strategy_id,
            old_state="degraded",
            new_state="recovery",
            message=f"Recovery forced for {strategy_id}",
            timestamp=int(time.time() * 1000)
        )
        self._control_history.append(result)
        return result
    
    def _force_demotion(self, strategy_id: str, to_status: Optional[str]) -> ControlResult:
        """Force demotion bypassing normal rules"""
        to_status = to_status or "DISABLED"
        return self._demote(strategy_id, to_status, "Forced demotion by admin")
    
    def _set_weight(self, strategy_id: str, weight: float) -> ControlResult:
        """Set strategy weight override"""
        self._overrides[strategy_id] = self._overrides.get(strategy_id, {})
        old_weight = self._overrides.get(strategy_id, {}).get("weight", 1.0)
        self._overrides[strategy_id]["weight"] = weight
        self._overrides[strategy_id]["weight_set_at"] = int(time.time() * 1000)
        
        result = ControlResult(
            success=True,
            action=ControlAction.SET_WEIGHT,
            target=strategy_id,
            old_state=f"weight={old_weight}",
            new_state=f"weight={weight}",
            message=f"Weight set to {weight} for {strategy_id}",
            timestamp=int(time.time() * 1000)
        )
        self._control_history.append(result)
        return result
    
    def _set_budget(self, strategy_id: str, budget: Dict) -> ControlResult:
        """Set strategy budget override"""
        self._overrides[strategy_id] = self._overrides.get(strategy_id, {})
        self._overrides[strategy_id]["budget"] = budget
        self._overrides[strategy_id]["budget_set_at"] = int(time.time() * 1000)
        
        result = ControlResult(
            success=True,
            action=ControlAction.SET_BUDGET,
            target=strategy_id,
            old_state="default_budget",
            new_state=f"custom_budget",
            message=f"Budget updated for {strategy_id}",
            timestamp=int(time.time() * 1000)
        )
        self._control_history.append(result)
        return result
    
    def is_frozen(self, strategy_id: str) -> bool:
        """Check if strategy is frozen"""
        return strategy_id in self._frozen_strategies
    
    def get_override(self, strategy_id: str) -> Optional[Dict]:
        """Get overrides for strategy"""
        return self._overrides.get(strategy_id)
    
    def get_all_overrides(self) -> Dict[str, Dict]:
        """Get all overrides"""
        return self._overrides
    
    def get_control_history(self, limit: int = 50) -> List[ControlResult]:
        """Get control history"""
        return self._control_history[-limit:]


# ═══════════════════════════════════════════════════════════════
# Governance History
# ═══════════════════════════════════════════════════════════════

class GovernanceHistory:
    """
    Tracks all governance changes for audit.
    
    Every policy change, control action, override is recorded.
    """
    
    def __init__(self):
        self._changes: List[PolicyChange] = []
    
    def record(
        self,
        change_type: ChangeType,
        policy_type: Optional[PolicyType],
        author: str,
        old_value: Any,
        new_value: Any,
        reason: str = ""
    ) -> PolicyChange:
        """Record a governance change"""
        change = PolicyChange(
            change_id=f"gov_{int(time.time() * 1000)}_{len(self._changes)}",
            change_type=change_type,
            policy_type=policy_type,
            author=author,
            timestamp=int(time.time() * 1000),
            old_value=old_value,
            new_value=new_value,
            reason=reason
        )
        
        self._changes.append(change)
        return change
    
    def get_history(self, limit: int = 100) -> List[PolicyChange]:
        """Get recent history"""
        return self._changes[-limit:]
    
    def get_history_by_type(self, change_type: ChangeType, limit: int = 50) -> List[PolicyChange]:
        """Get history by type"""
        return [c for c in self._changes if c.change_type == change_type][-limit:]
    
    def get_history_by_author(self, author: str, limit: int = 50) -> List[PolicyChange]:
        """Get history by author"""
        return [c for c in self._changes if c.author == author][-limit:]
    
    def get_change(self, change_id: str) -> Optional[PolicyChange]:
        """Get specific change"""
        for c in self._changes:
            if c.change_id == change_id:
                return c
        return None


# ═══════════════════════════════════════════════════════════════
# Admin Cockpit Service
# ═══════════════════════════════════════════════════════════════

class AdminCockpitService:
    """
    Main Admin Cockpit Service.
    
    Central control plane for the entire system.
    """
    
    def __init__(self, policies_dir: str = "/app/backend/policies"):
        self.policy_manager = PolicyManager(policies_dir)
        self.strategy_controller = StrategyController()
        self.governance_history = GovernanceHistory()
        
        self._system_status = "HEALTHY"
    
    def get_dashboard(self) -> AdminDashboard:
        """Get admin dashboard"""
        policies = self.policy_manager.get_policies()
        
        # Get self-healing status if available
        self_healing_enabled = policies.get("self_healing_policies", {}).get("enabled", True)
        
        # Get portfolio limits
        portfolio = policies.get("portfolio_policies", {})
        max_exposure = portfolio.get("exposure_limits", {}).get("max_gross", 1.5)
        
        return AdminDashboard(
            system_status=self._system_status,
            active_policies_version=self.policy_manager._current_version,
            total_strategies=11,
            healthy_strategies=5,
            degraded_strategies=4,
            frozen_strategies=len(self.strategy_controller._frozen_strategies),
            self_healing_enabled=self_healing_enabled,
            recent_demotions=0,
            recent_recoveries=0,
            current_exposure=0.25,
            max_exposure=max_exposure,
            kill_switch_active=False,
            recent_policy_changes=len(self.governance_history._changes),
            pending_approvals=0,
            last_update=int(time.time() * 1000)
        )
    
    def get_policies(self, policy_type: Optional[str] = None) -> Dict:
        """Get policies"""
        if policy_type:
            try:
                pt = PolicyType(policy_type)
                return self.policy_manager.get_policies(pt)
            except ValueError:
                return {}
        return self.policy_manager.get_policies()
    
    def update_policy(
        self,
        policy_type: str,
        updates: Dict,
        author: str = "admin",
        reason: str = ""
    ) -> Dict:
        """Update a policy"""
        try:
            pt = PolicyType(policy_type)
        except ValueError:
            return {"success": False, "error": f"Invalid policy type: {policy_type}"}
        
        # Validate
        is_valid, errors = self.policy_manager.validate_policy(pt, updates)
        if not is_valid:
            return {"success": False, "errors": errors}
        
        # Update
        change = self.policy_manager.update_policy(pt, updates, author, reason)
        
        # Record in history
        self.governance_history.record(
            ChangeType.POLICY_UPDATE,
            pt,
            author,
            change.old_value,
            change.new_value,
            reason
        )
        
        return {
            "success": True,
            "changeId": change.change_id,
            "newVersion": self.policy_manager._current_version
        }
    
    def control_strategy(
        self,
        action: str,
        strategy_id: str,
        params: Optional[Dict] = None,
        author: str = "admin"
    ) -> Dict:
        """Execute strategy control action"""
        try:
            ctrl_action = ControlAction(action)
        except ValueError:
            return {"success": False, "error": f"Invalid action: {action}"}
        
        result = self.strategy_controller.execute(ctrl_action, strategy_id, params)
        
        # Record in history
        self.governance_history.record(
            ChangeType.STRATEGY_CONTROL,
            None,
            author,
            result.old_state,
            result.new_state,
            f"{action} on {strategy_id}"
        )
        
        return control_result_to_dict(result)
    
    def create_snapshot(self, author: str = "admin", notes: str = "") -> Dict:
        """Create policy version snapshot"""
        version = self.policy_manager.create_version_snapshot(author, notes)
        
        self.governance_history.record(
            ChangeType.SYSTEM_CONFIG,
            None,
            author,
            f"version_{version.version_number - 1}",
            f"version_{version.version_number}",
            f"Snapshot created: {notes}"
        )
        
        return {
            "versionId": version.version_id,
            "versionNumber": version.version_number,
            "checksum": version.checksum
        }
    
    def rollback(self, version_id: str, author: str = "admin") -> Dict:
        """Rollback to previous version"""
        success, message = self.policy_manager.rollback(version_id, author)
        
        if success:
            self.governance_history.record(
                ChangeType.ROLLBACK,
                None,
                author,
                "current",
                version_id,
                message
            )
        
        return {"success": success, "message": message}
    
    def get_governance_history(self, limit: int = 50) -> List[Dict]:
        """Get governance history"""
        return [change_to_dict(c) for c in self.governance_history.get_history(limit)]
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.25E",
            "status": "ok",
            "components": {
                "policy_manager": "ok",
                "strategy_controller": "ok",
                "governance_history": "ok"
            },
            "activePoliciesVersion": self.policy_manager._current_version,
            "frozenStrategies": len(self.strategy_controller._frozen_strategies),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


# ═══════════════════════════════════════════════════════════════
# Serialization Functions
# ═══════════════════════════════════════════════════════════════

def dashboard_to_dict(dashboard: AdminDashboard) -> Dict:
    """Convert AdminDashboard to dict"""
    return {
        "systemStatus": dashboard.system_status,
        "activePoliciesVersion": dashboard.active_policies_version,
        "strategies": {
            "total": dashboard.total_strategies,
            "healthy": dashboard.healthy_strategies,
            "degraded": dashboard.degraded_strategies,
            "frozen": dashboard.frozen_strategies
        },
        "selfHealing": {
            "enabled": dashboard.self_healing_enabled,
            "recentDemotions": dashboard.recent_demotions,
            "recentRecoveries": dashboard.recent_recoveries
        },
        "portfolio": {
            "currentExposure": dashboard.current_exposure,
            "maxExposure": dashboard.max_exposure,
            "killSwitchActive": dashboard.kill_switch_active
        },
        "governance": {
            "recentPolicyChanges": dashboard.recent_policy_changes,
            "pendingApprovals": dashboard.pending_approvals
        },
        "lastUpdate": dashboard.last_update
    }


def control_result_to_dict(result: ControlResult) -> Dict:
    """Convert ControlResult to dict"""
    return {
        "success": result.success,
        "action": result.action.value,
        "target": result.target,
        "oldState": result.old_state,
        "newState": result.new_state,
        "message": result.message,
        "timestamp": result.timestamp
    }


def change_to_dict(change: PolicyChange) -> Dict:
    """Convert PolicyChange to dict"""
    return {
        "changeId": change.change_id,
        "changeType": change.change_type.value,
        "policyType": change.policy_type.value if change.policy_type else None,
        "author": change.author,
        "timestamp": change.timestamp,
        "reason": change.reason,
        "diff": change.diff
    }
