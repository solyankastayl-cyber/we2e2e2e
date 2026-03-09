"""
Risk Types (T4)
===============

Type definitions for risk control layer.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


class RiskSeverity(str, Enum):
    """Risk verdict severity"""
    OK = "OK"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


@dataclass
class RiskProfile:
    """
    Trading risk profile.
    
    Defines all risk limits and trading rules.
    """
    profile_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Position limits
    max_position_usd: float = 10000.0
    max_asset_exposure_pct: float = 0.20      # 20% per asset
    max_portfolio_exposure_pct: float = 0.50  # 50% total
    
    # Order limits
    max_open_positions: int = 5
    max_orders_per_asset: int = 3
    
    # Drawdown
    max_daily_drawdown_pct: float = 0.05  # 5%
    
    # Mode constraints
    spot_enabled: bool = True
    futures_enabled: bool = False
    short_allowed: bool = False
    leverage_allowed: bool = False
    max_leverage: float = 1.0
    
    # Averaging (controlled recovery)
    averaging_enabled: bool = True
    max_averaging_steps: int = 3
    max_averaging_capital_pct: float = 0.30   # Max 30% of equity in averaging
    averaging_step_multiplier: float = 1.5    # Each step 1.5x previous
    averaging_min_price_drop_pct: float = 0.05  # 5% drop required for next step
    
    # Emergency
    emergency_stop_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "max_position_usd": self.max_position_usd,
            "max_asset_exposure_pct": self.max_asset_exposure_pct,
            "max_portfolio_exposure_pct": self.max_portfolio_exposure_pct,
            "max_open_positions": self.max_open_positions,
            "max_orders_per_asset": self.max_orders_per_asset,
            "max_daily_drawdown_pct": self.max_daily_drawdown_pct,
            "spot_enabled": self.spot_enabled,
            "futures_enabled": self.futures_enabled,
            "short_allowed": self.short_allowed,
            "leverage_allowed": self.leverage_allowed,
            "max_leverage": self.max_leverage,
            "averaging_enabled": self.averaging_enabled,
            "max_averaging_steps": self.max_averaging_steps,
            "max_averaging_capital_pct": self.max_averaging_capital_pct,
            "averaging_step_multiplier": self.averaging_step_multiplier,
            "averaging_min_price_drop_pct": self.averaging_min_price_drop_pct,
            "emergency_stop_enabled": self.emergency_stop_enabled
        }


@dataclass
class RiskCheckContext:
    """
    Context for risk check.
    
    Contains current state for risk evaluation.
    """
    connection_id: str = ""
    asset: str = ""
    market_type: str = "SPOT"
    
    # Account state
    account_equity_usd: float = 0.0
    available_cash_usd: float = 0.0
    
    # Current exposure
    current_asset_exposure_usd: float = 0.0
    current_portfolio_exposure_usd: float = 0.0
    
    # Position counts
    open_positions_count: int = 0
    open_orders_count: int = 0
    asset_orders_count: int = 0
    
    # Drawdown
    daily_pnl_usd: float = 0.0
    current_daily_drawdown_pct: float = 0.0
    
    # Control state
    paused: bool = False
    kill_switch_active: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "asset": self.asset,
            "market_type": self.market_type,
            "account_equity_usd": round(self.account_equity_usd, 2),
            "available_cash_usd": round(self.available_cash_usd, 2),
            "current_asset_exposure_usd": round(self.current_asset_exposure_usd, 2),
            "current_portfolio_exposure_usd": round(self.current_portfolio_exposure_usd, 2),
            "open_positions_count": self.open_positions_count,
            "open_orders_count": self.open_orders_count,
            "asset_orders_count": self.asset_orders_count,
            "daily_pnl_usd": round(self.daily_pnl_usd, 2),
            "current_daily_drawdown_pct": round(self.current_daily_drawdown_pct, 4),
            "paused": self.paused,
            "kill_switch_active": self.kill_switch_active
        }


@dataclass
class RiskVerdict:
    """
    Risk check verdict.
    
    Determines if trade is allowed and any adjustments.
    """
    allowed: bool = True
    severity: RiskSeverity = RiskSeverity.OK
    
    reason_codes: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    
    # Adjustments (if allowed with modifications)
    adjusted_quantity: Optional[float] = None
    adjusted_notional_usd: Optional[float] = None
    
    # Checks performed
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "severity": self.severity.value,
            "reason_codes": self.reason_codes,
            "notes": self.notes,
            "adjusted_quantity": round(self.adjusted_quantity, 8) if self.adjusted_quantity else None,
            "adjusted_notional_usd": round(self.adjusted_notional_usd, 2) if self.adjusted_notional_usd else None,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed
        }


@dataclass
class AveragingState:
    """
    Averaging ladder state for an asset.
    
    Tracks controlled position building.
    """
    asset: str = ""
    connection_id: str = ""
    
    active: bool = False
    steps_used: int = 0
    total_capital_committed_usd: float = 0.0
    
    entries: List[Dict[str, Any]] = field(default_factory=list)  # [{price, quantity, timestamp}]
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    
    last_entry_price: float = 0.0
    last_entry_timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "connection_id": self.connection_id,
            "active": self.active,
            "steps_used": self.steps_used,
            "total_capital_committed_usd": round(self.total_capital_committed_usd, 2),
            "entries_count": len(self.entries),
            "avg_entry_price": round(self.avg_entry_price, 8),
            "current_price": round(self.current_price, 8),
            "last_entry_price": round(self.last_entry_price, 8),
            "last_entry_timestamp": self.last_entry_timestamp.isoformat() if self.last_entry_timestamp else None
        }
    
    def add_entry(self, price: float, quantity: float, notional_usd: float):
        """Add an averaging entry"""
        self.entries.append({
            "price": price,
            "quantity": quantity,
            "notional_usd": notional_usd,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        self.steps_used += 1
        self.total_capital_committed_usd += notional_usd
        self.last_entry_price = price
        self.last_entry_timestamp = datetime.now(timezone.utc)
        
        # Recalculate average
        total_qty = sum(e["quantity"] for e in self.entries)
        total_cost = sum(e["price"] * e["quantity"] for e in self.entries)
        self.avg_entry_price = total_cost / total_qty if total_qty > 0 else 0
        
        self.active = True
    
    def reset(self):
        """Reset averaging state"""
        self.active = False
        self.steps_used = 0
        self.total_capital_committed_usd = 0.0
        self.entries = []
        self.avg_entry_price = 0.0
        self.last_entry_price = 0.0
        self.last_entry_timestamp = None
