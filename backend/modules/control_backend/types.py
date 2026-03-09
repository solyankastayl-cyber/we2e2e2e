"""
Control Backend Types
=====================

Data models for P0-3 Control Backend.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid


class AdminActionType(str, Enum):
    """Admin action types for audit log"""
    PAUSE_SYSTEM = "pause_system"
    RESUME_SYSTEM = "resume_system"
    RISK_OVERRIDE = "risk_override"
    STRATEGY_FREEZE = "strategy_freeze"
    STRATEGY_UNFREEZE = "strategy_unfreeze"
    LIFECYCLE_OVERRIDE = "lifecycle_override"
    MAINTENANCE_START = "maintenance_start"
    MAINTENANCE_END = "maintenance_end"
    CONFIG_UPDATE = "config_update"
    EMERGENCY_STOP = "emergency_stop"


class ServiceStatus(str, Enum):
    """Service health status"""
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class AdminAction:
    """Record of admin action for audit trail"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user: str = "admin"
    action: AdminActionType = AdminActionType.PAUSE_SYSTEM
    target: str = "system"
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    success: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user": self.user,
            "action": self.action.value,
            "target": self.target,
            "payload": self.payload,
            "result": self.result,
            "success": self.success
        }


@dataclass
class SystemHealthStatus:
    """System health status"""
    status: str = "healthy"
    services: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "services": self.services,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class SystemMetrics:
    """System metrics"""
    event_throughput: int = 0
    active_strategies: int = 0
    risk_state: str = "NORMAL"
    research_cycles_today: int = 0
    timeline_events_today: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_throughput": self.event_throughput,
            "active_strategies": self.active_strategies,
            "risk_state": self.risk_state,
            "research_cycles_today": self.research_cycles_today,
            "timeline_events_today": self.timeline_events_today
        }


@dataclass
class StrategyHealth:
    """Strategy health metrics"""
    strategy: str = ""
    pf: float = 0.0
    sharpe: float = 0.0
    drawdown: float = 0.0
    win_rate: float = 0.0
    trades: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "pf": round(self.pf, 2),
            "sharpe": round(self.sharpe, 2),
            "drawdown": round(self.drawdown, 3),
            "win_rate": round(self.win_rate, 3),
            "trades": self.trades
        }


@dataclass
class StrategyDecay:
    """Strategy decay info"""
    strategy: str = ""
    decay_score: float = 0.0
    trend: str = "stable"  # stable, increasing, decreasing
    days_in_state: int = 0
    warning_level: str = "none"  # none, low, medium, high
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "decay_score": round(self.decay_score, 3),
            "trend": self.trend,
            "days_in_state": self.days_in_state,
            "warning_level": self.warning_level
        }


@dataclass
class RiskExposure:
    """Risk exposure metrics"""
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "gross_exposure": round(self.gross_exposure, 3),
            "net_exposure": round(self.net_exposure, 3),
            "long_exposure": round(self.long_exposure, 3),
            "short_exposure": round(self.short_exposure, 3)
        }


@dataclass
class RiskAlert:
    """Risk alert"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    severity: AlertSeverity = AlertSeverity.WARNING
    type: str = "general"
    message: str = ""
    source: str = "risk_brain"
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "type": self.type,
            "message": self.message,
            "source": self.source,
            "acknowledged": self.acknowledged
        }


# Frozen strategies storage
@dataclass
class FrozenStrategy:
    """Frozen strategy record"""
    strategy_id: str
    frozen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    frozen_by: str = "admin"
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "frozen_at": self.frozen_at.isoformat(),
            "frozen_by": self.frozen_by,
            "reason": self.reason
        }
