"""
Governance Events Logger
========================

Logs all governance decisions for audit trail and debugging.
"""

import uuid
import time
from typing import Dict, List, Any, Optional
from collections import defaultdict

from .types import GovernanceEvent, GovernanceLayer, GovernanceMetrics


class GovernanceEventLogger:
    """
    Logs and manages governance events during simulation.
    
    Tracks all system decisions including:
    - Regime changes
    - Self-healing actions
    - Meta-strategy reallocations
    - Overlay triggers
    - Kill switch events
    - Bias rejections
    """
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.events: List[GovernanceEvent] = []
        self._layer_counts: Dict[str, int] = defaultdict(int)
    
    def log(
        self,
        bar_index: int,
        asset: str,
        layer: GovernanceLayer,
        action: str,
        old_state: str = "",
        new_state: str = "",
        reason: str = "",
        metadata: Dict[str, Any] = None
    ) -> GovernanceEvent:
        """Log a governance event"""
        event = GovernanceEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            run_id=self.run_id,
            timestamp=int(time.time() * 1000),
            bar_index=bar_index,
            asset=asset,
            layer=layer,
            action=action,
            old_state=old_state,
            new_state=new_state,
            reason=reason,
            metadata=metadata or {}
        )
        
        self.events.append(event)
        self._layer_counts[layer.value] += 1
        
        return event
    
    def log_regime_change(
        self,
        bar_index: int,
        asset: str,
        old_regime: str,
        new_regime: str,
        confidence: float = 0.0
    ) -> GovernanceEvent:
        """Log regime change event"""
        return self.log(
            bar_index=bar_index,
            asset=asset,
            layer=GovernanceLayer.REGIME,
            action="REGIME_CHANGE",
            old_state=old_regime,
            new_state=new_regime,
            reason=f"Confidence: {confidence:.2f}",
            metadata={"confidence": confidence}
        )
    
    def log_healing_demotion(
        self,
        bar_index: int,
        asset: str,
        strategy_id: str,
        old_health: float,
        new_health: float,
        win_rate: float
    ) -> GovernanceEvent:
        """Log self-healing demotion event"""
        return self.log(
            bar_index=bar_index,
            asset=asset,
            layer=GovernanceLayer.SELF_HEALING,
            action="DEMOTION",
            old_state=f"health={old_health:.3f}",
            new_state=f"health={new_health:.3f}",
            reason=f"Low win rate: {win_rate:.2%}",
            metadata={
                "strategy_id": strategy_id,
                "old_health": old_health,
                "new_health": new_health,
                "win_rate": win_rate
            }
        )
    
    def log_healing_recovery(
        self,
        bar_index: int,
        asset: str,
        strategy_id: str,
        old_health: float,
        new_health: float,
        win_rate: float
    ) -> GovernanceEvent:
        """Log self-healing recovery event"""
        return self.log(
            bar_index=bar_index,
            asset=asset,
            layer=GovernanceLayer.SELF_HEALING,
            action="RECOVERY",
            old_state=f"health={old_health:.3f}",
            new_state=f"health={new_health:.3f}",
            reason=f"High win rate: {win_rate:.2%}",
            metadata={
                "strategy_id": strategy_id,
                "old_health": old_health,
                "new_health": new_health,
                "win_rate": win_rate
            }
        )
    
    def log_meta_reallocation(
        self,
        bar_index: int,
        asset: str,
        family: str,
        old_budget: float,
        new_budget: float,
        regime: str
    ) -> GovernanceEvent:
        """Log meta-strategy budget reallocation"""
        return self.log(
            bar_index=bar_index,
            asset=asset,
            layer=GovernanceLayer.META_STRATEGY,
            action="BUDGET_REALLOCATION",
            old_state=f"{family}={old_budget:.3f}",
            new_state=f"{family}={new_budget:.3f}",
            reason=f"Regime: {regime}",
            metadata={
                "family": family,
                "old_budget": old_budget,
                "new_budget": new_budget,
                "regime": regime
            }
        )
    
    def log_hierarchical_reweight(
        self,
        bar_index: int,
        asset: str,
        strategy_id: str,
        old_weight: float,
        new_weight: float,
        regime: str
    ) -> GovernanceEvent:
        """Log hierarchical allocator weight change"""
        return self.log(
            bar_index=bar_index,
            asset=asset,
            layer=GovernanceLayer.ALLOCATOR,
            action="HIERARCHICAL_REWEIGHT",
            old_state=f"{strategy_id}={old_weight:.4f}",
            new_state=f"{strategy_id}={new_weight:.4f}",
            reason=f"Regime: {regime}",
            metadata={
                "strategy_id": strategy_id,
                "old_weight": old_weight,
                "new_weight": new_weight,
                "regime": regime
            }
        )
    
    def log_overlay_trigger(
        self,
        bar_index: int,
        asset: str,
        trigger_type: str,
        multiplier: float,
        reason: str
    ) -> GovernanceEvent:
        """Log portfolio overlay trigger"""
        return self.log(
            bar_index=bar_index,
            asset=asset,
            layer=GovernanceLayer.OVERLAY,
            action=f"OVERLAY_{trigger_type.upper()}",
            new_state=f"multiplier={multiplier:.3f}",
            reason=reason,
            metadata={
                "trigger_type": trigger_type,
                "multiplier": multiplier
            }
        )
    
    def log_kill_switch(
        self,
        bar_index: int,
        asset: str,
        action: str,
        reason: str,
        drawdown: float = 0.0
    ) -> GovernanceEvent:
        """Log kill switch activation/deactivation"""
        return self.log(
            bar_index=bar_index,
            asset=asset,
            layer=GovernanceLayer.KILL_SWITCH,
            action=action,
            reason=reason,
            metadata={"drawdown": drawdown}
        )
    
    def log_bias_rejection(
        self,
        bar_index: int,
        asset: str,
        direction: str,
        bias_state: str,
        reason: str
    ) -> GovernanceEvent:
        """Log structural bias signal rejection"""
        return self.log(
            bar_index=bar_index,
            asset=asset,
            layer=GovernanceLayer.BIAS,
            action="SIGNAL_REJECTED",
            old_state=direction,
            new_state="BLOCKED",
            reason=reason,
            metadata={
                "direction": direction,
                "bias_state": bias_state
            }
        )
    
    def log_trade_blocked(
        self,
        bar_index: int,
        asset: str,
        strategy_id: str,
        reason: str
    ) -> GovernanceEvent:
        """Log blocked trade"""
        return self.log(
            bar_index=bar_index,
            asset=asset,
            layer=GovernanceLayer.RISK,
            action="TRADE_BLOCKED",
            reason=reason,
            metadata={"strategy_id": strategy_id}
        )
    
    def get_events_by_layer(self, layer: GovernanceLayer) -> List[GovernanceEvent]:
        """Get events filtered by layer"""
        return [e for e in self.events if e.layer == layer]
    
    def get_events_by_bar_range(
        self,
        start_bar: int,
        end_bar: int
    ) -> List[GovernanceEvent]:
        """Get events in bar range"""
        return [
            e for e in self.events
            if start_bar <= e.bar_index <= end_bar
        ]
    
    def get_metrics(self) -> GovernanceMetrics:
        """Calculate governance metrics"""
        metrics = GovernanceMetrics(
            total_events=len(self.events)
        )
        
        for event in self.events:
            if event.layer == GovernanceLayer.SELF_HEALING:
                metrics.healing_events += 1
            elif event.layer == GovernanceLayer.META_STRATEGY:
                metrics.meta_reallocations += 1
            elif event.layer == GovernanceLayer.OVERLAY:
                metrics.overlay_triggers += 1
            elif event.layer == GovernanceLayer.KILL_SWITCH:
                metrics.kill_switch_events += 1
            elif event.layer == GovernanceLayer.BIAS:
                metrics.bias_rejections += 1
            elif event.layer == GovernanceLayer.REGIME:
                metrics.regime_changes += 1
            elif event.layer == GovernanceLayer.RISK and event.action == "TRADE_BLOCKED":
                metrics.blocked_trades += 1
        
        return metrics
    
    def to_timeline(self) -> List[Dict]:
        """Export events as timeline"""
        return [
            {
                "event_id": e.event_id,
                "bar_index": e.bar_index,
                "timestamp": e.timestamp,
                "layer": e.layer.value,
                "action": e.action,
                "old_state": e.old_state,
                "new_state": e.new_state,
                "reason": e.reason
            }
            for e in self.events
        ]
    
    def get_summary(self) -> Dict:
        """Get summary of all events"""
        return {
            "run_id": self.run_id,
            "total_events": len(self.events),
            "by_layer": dict(self._layer_counts),
            "metrics": {
                "healing_events": self._layer_counts.get("SELF_HEALING", 0),
                "meta_reallocations": self._layer_counts.get("META_STRATEGY", 0),
                "regime_changes": self._layer_counts.get("REGIME", 0),
                "overlay_triggers": self._layer_counts.get("OVERLAY", 0),
                "kill_switch_events": self._layer_counts.get("KILL_SWITCH", 0),
                "bias_rejections": self._layer_counts.get("BIAS", 0)
            }
        }
    
    def reset(self):
        """Reset logger"""
        self.events = []
        self._layer_counts = defaultdict(int)
