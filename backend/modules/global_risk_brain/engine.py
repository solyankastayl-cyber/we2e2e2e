"""
Global Risk Brain Engine
========================

Phase 9.35 - Top-level risk controller for the entire system.

GRB sits above all other modules and makes system-wide risk decisions:
- Monitors global risk indicators
- Manages risk state machine
- Controls capital allocation
- Activates crisis policies

Phase D: Integrated with Event Bus for loosely-coupled communication.
"""

import time
import uuid
import math
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .types import (
    RiskState, DetectorType, PolicyAction,
    RiskEnvelope, CapitalAllocation, DetectorSignal,
    RiskSnapshot, StateTransition, CrisisPolicy, GRBConfig,
    DEFAULT_ENVELOPES
)

# Event Bus integration
try:
    from modules.event_bus import create_publisher, EventType
    _event_publisher = create_publisher("global_risk_brain")
    EVENT_BUS_ENABLED = True
except ImportError:
    _event_publisher = None
    EVENT_BUS_ENABLED = False


class GlobalRiskBrain:
    """
    Global Risk Brain - Top-level risk controller.
    
    Manages the entire system's risk exposure based on:
    - Market conditions
    - Portfolio performance
    - Systemic risk indicators
    """
    
    def __init__(self, config: GRBConfig = None):
        self.config = config or GRBConfig()
        
        # Current state
        self.current_state = RiskState.NORMAL
        self.current_envelope = DEFAULT_ENVELOPES[RiskState.NORMAL]
        self.current_allocation = CapitalAllocation()
        
        # History
        self.transitions: List[StateTransition] = []
        self.snapshots: List[RiskSnapshot] = []
        
        # Policies
        self.policies: Dict[str, CrisisPolicy] = {}
        self._init_default_policies()
        
        # State timing
        self.state_entered_at = int(time.time() * 1000)
        self.last_evaluation_at = 0
        
        # Detectors
        self.detector_values: Dict[str, float] = {}
    
    def _init_default_policies(self):
        """Initialize default crisis policies"""
        
        # Stress policy
        self.policies["STRESS_POLICY"] = CrisisPolicy(
            policy_id="STRESS_POLICY",
            name="Stress Response",
            trigger_state=RiskState.STRESS,
            actions=[
                PolicyAction.REDUCE_EXPOSURE,
                PolicyAction.DISABLE_EXPERIMENTAL,
                PolicyAction.INCREASE_STOPS
            ]
        )
        
        # Crisis policy
        self.policies["CRISIS_POLICY"] = CrisisPolicy(
            policy_id="CRISIS_POLICY",
            name="Crisis Response",
            trigger_state=RiskState.CRISIS,
            actions=[
                PolicyAction.REDUCE_EXPOSURE,
                PolicyAction.DISABLE_EXPERIMENTAL,
                PolicyAction.FREEZE_TACTICAL,
                PolicyAction.INCREASE_STOPS,
                PolicyAction.SHIFT_ALLOCATION
            ],
            allocation_override=CapitalAllocation(
                equities=0.10, crypto=0.05, fx=0.15, commodities=0.10, cash=0.60
            )
        )
        
        # Survival policy
        self.policies["SURVIVAL_POLICY"] = CrisisPolicy(
            policy_id="SURVIVAL_POLICY",
            name="Survival Mode",
            trigger_state=RiskState.SURVIVAL,
            actions=[PolicyAction.FULL_FREEZE],
            allocation_override=CapitalAllocation(
                equities=0.0, crypto=0.0, fx=0.0, commodities=0.0, cash=1.0
            )
        )
    
    # ============================================
    # Risk Detectors
    # ============================================
    
    def detect_volatility(
        self,
        current_vol: float,
        avg_vol: float
    ) -> DetectorSignal:
        """Detect volatility spike"""
        
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        triggered = ratio > self.config.vol_spike_threshold
        severity = min(1.0, (ratio - 1) / 3) if ratio > 1 else 0
        
        signal = DetectorSignal(
            detector_type=DetectorType.VOLATILITY,
            name="Volatility Spike",
            value=ratio,
            threshold=self.config.vol_spike_threshold,
            triggered=triggered,
            severity=severity,
            message=f"Vol ratio: {ratio:.2f}x (threshold: {self.config.vol_spike_threshold}x)",
            timestamp=int(time.time() * 1000)
        )
        
        self.detector_values["volatility"] = ratio
        return signal
    
    def detect_drawdown(
        self,
        current_drawdown: float
    ) -> DetectorSignal:
        """Detect portfolio drawdown"""
        
        triggered = current_drawdown > self.config.drawdown_threshold
        severity = min(1.0, current_drawdown / 0.30)  # 30% = max severity
        
        signal = DetectorSignal(
            detector_type=DetectorType.DRAWDOWN,
            name="Portfolio Drawdown",
            value=current_drawdown,
            threshold=self.config.drawdown_threshold,
            triggered=triggered,
            severity=severity,
            message=f"Drawdown: {current_drawdown:.1%} (threshold: {self.config.drawdown_threshold:.1%})",
            timestamp=int(time.time() * 1000)
        )
        
        self.detector_values["drawdown"] = current_drawdown
        return signal
    
    def detect_correlation(
        self,
        avg_correlation: float
    ) -> DetectorSignal:
        """Detect correlation spike"""
        
        triggered = avg_correlation > self.config.correlation_threshold
        severity = min(1.0, (avg_correlation - 0.5) / 0.5) if avg_correlation > 0.5 else 0
        
        signal = DetectorSignal(
            detector_type=DetectorType.CORRELATION,
            name="Correlation Spike",
            value=avg_correlation,
            threshold=self.config.correlation_threshold,
            triggered=triggered,
            severity=severity,
            message=f"Avg correlation: {avg_correlation:.2f} (threshold: {self.config.correlation_threshold})",
            timestamp=int(time.time() * 1000)
        )
        
        self.detector_values["correlation"] = avg_correlation
        return signal
    
    def detect_liquidity(
        self,
        atr_ratio: float
    ) -> DetectorSignal:
        """Detect liquidity stress (via ATR explosion)"""
        
        triggered = atr_ratio > self.config.liquidity_threshold
        severity = min(1.0, (atr_ratio - 1) / 4) if atr_ratio > 1 else 0
        
        signal = DetectorSignal(
            detector_type=DetectorType.LIQUIDITY,
            name="Liquidity Stress",
            value=atr_ratio,
            threshold=self.config.liquidity_threshold,
            triggered=triggered,
            severity=severity,
            message=f"ATR ratio: {atr_ratio:.2f}x (threshold: {self.config.liquidity_threshold}x)",
            timestamp=int(time.time() * 1000)
        )
        
        self.detector_values["liquidity"] = atr_ratio
        return signal
    
    # ============================================
    # State Machine
    # ============================================
    
    def evaluate(
        self,
        vol_ratio: float = 1.0,
        drawdown: float = 0.0,
        correlation: float = 0.3,
        liquidity_ratio: float = 1.0,
        regime: str = "NORMAL"
    ) -> RiskSnapshot:
        """
        Evaluate current risk and potentially transition state.
        
        This is the main entry point for risk assessment.
        """
        
        now = int(time.time() * 1000)
        
        # Run detectors
        signals = [
            self.detect_volatility(vol_ratio, 1.0),
            self.detect_drawdown(drawdown),
            self.detect_correlation(correlation),
            self.detect_liquidity(liquidity_ratio)
        ]
        
        # Calculate aggregate severity
        triggered_signals = [s for s in signals if s.triggered]
        triggered_names = [s.name for s in triggered_signals]
        
        if triggered_signals:
            aggregate_severity = sum(s.severity for s in triggered_signals) / len(triggered_signals)
            # Weight by number of triggers
            aggregate_severity *= (1 + 0.2 * len(triggered_signals))
            aggregate_severity = min(1.0, aggregate_severity)
        else:
            aggregate_severity = 0.0
        
        # Determine target state
        target_state = self._determine_target_state(aggregate_severity, regime)
        
        # Check if we should transition
        if target_state != self.current_state:
            self._transition_state(target_state, triggered_names, self.detector_values.copy())
        
        # Apply policies
        active_policies = self._get_active_policies()
        
        # Create snapshot
        snapshot = RiskSnapshot(
            state=self.current_state,
            envelope=self.current_envelope,
            allocation=self.current_allocation,
            signals=signals,
            triggered_detectors=triggered_names,
            current_exposure=self.current_envelope.max_exposure,
            current_leverage=self.current_envelope.max_leverage,
            current_drawdown=drawdown,
            portfolio_correlation=correlation,
            active_policies=active_policies,
            timestamp=now
        )
        
        self.snapshots.append(snapshot)
        self.last_evaluation_at = now
        
        # Keep only last 1000 snapshots
        if len(self.snapshots) > 1000:
            self.snapshots = self.snapshots[-1000:]
        
        return snapshot
    
    def _determine_target_state(self, severity: float, regime: str) -> RiskState:
        """Determine target state based on severity and regime"""
        
        # Regime override
        if regime == "CRISIS":
            return RiskState.CRISIS
        
        # Severity-based
        if severity >= self.config.survival_trigger_score:
            return RiskState.SURVIVAL
        elif severity >= self.config.crisis_trigger_score:
            return RiskState.CRISIS
        elif severity >= self.config.stress_trigger_score:
            return RiskState.STRESS
        elif severity >= self.config.elevated_trigger_score:
            return RiskState.ELEVATED
        else:
            # Check recovery cooldown
            if self._can_recover():
                return RiskState.NORMAL
            return self.current_state
    
    def _can_recover(self) -> bool:
        """Check if we can recover to a lower risk state"""
        now = int(time.time() * 1000)
        time_in_state = now - self.state_entered_at
        return time_in_state > (self.config.recovery_cooldown_seconds * 1000)
    
    def _transition_state(
        self,
        new_state: RiskState,
        trigger_detectors: List[str],
        trigger_values: Dict[str, float]
    ):
        """Transition to a new risk state"""
        
        now = int(time.time() * 1000)
        old_state = self.current_state
        
        # Record transition
        transition = StateTransition(
            transition_id=f"TRANS_{uuid.uuid4().hex[:8]}",
            from_state=self.current_state,
            to_state=new_state,
            trigger_detectors=trigger_detectors,
            trigger_values=trigger_values,
            actions_taken=self._get_transition_actions(new_state),
            timestamp=now
        )
        self.transitions.append(transition)
        
        # Update state
        self.current_state = new_state
        self.current_envelope = DEFAULT_ENVELOPES[new_state]
        self.state_entered_at = now
        
        # Publish risk state changed event
        if EVENT_BUS_ENABLED and _event_publisher:
            _event_publisher.risk_state_changed(
                previous_state=old_state.value,
                new_state=new_state.value,
                trigger=", ".join(trigger_detectors) if trigger_detectors else "recovery",
                metrics=trigger_values
            )
        
        # Apply policy allocation override if exists
        for policy in self.policies.values():
            if policy.trigger_state == new_state and policy.allocation_override:
                self.current_allocation = policy.allocation_override
                break
    
    def _get_transition_actions(self, state: RiskState) -> List[PolicyAction]:
        """Get actions for transitioning to a state"""
        actions = []
        for policy in self.policies.values():
            if policy.trigger_state == state:
                actions.extend(policy.actions)
        return list(set(actions))
    
    def _get_active_policies(self) -> List[PolicyAction]:
        """Get currently active policy actions"""
        actions = []
        for policy in self.policies.values():
            if policy.trigger_state == self.current_state:
                actions.extend(policy.actions)
        return list(set(actions))
    
    # ============================================
    # Capital Allocation
    # ============================================
    
    def get_allocation(self) -> CapitalAllocation:
        """Get current capital allocation"""
        return self.current_allocation
    
    def set_allocation(self, allocation: CapitalAllocation):
        """Manually set allocation (admin override)"""
        if allocation.validate():
            self.current_allocation = allocation
    
    def suggest_allocation(self, regime: str = "NORMAL") -> CapitalAllocation:
        """Suggest allocation based on current state and regime"""
        
        if self.current_state in [RiskState.CRISIS, RiskState.SURVIVAL]:
            return self.config.crisis_allocation
        
        if regime == "STRESS":
            return CapitalAllocation(
                equities=0.25, crypto=0.15, fx=0.20, commodities=0.15, cash=0.25
            )
        
        return self.config.normal_allocation
    
    # ============================================
    # Manual Override
    # ============================================
    
    def override_state(self, state: RiskState, reason: str = "Manual override"):
        """Manually override the risk state (admin action)"""
        
        self._transition_state(
            state,
            ["MANUAL_OVERRIDE"],
            {"reason": reason}
        )
    
    def reset_to_normal(self):
        """Reset to normal state (admin action)"""
        self.override_state(RiskState.NORMAL, "Manual reset to normal")
    
    # ============================================
    # Queries
    # ============================================
    
    def get_state(self) -> Dict:
        """Get current state"""
        return {
            "state": self.current_state.value,
            "envelope": self._envelope_to_dict(self.current_envelope),
            "allocation": self._allocation_to_dict(self.current_allocation),
            "state_entered_at": self.state_entered_at,
            "time_in_state_seconds": (int(time.time() * 1000) - self.state_entered_at) / 1000,
            "detector_values": self.detector_values,
            "active_policies": [a.value for a in self._get_active_policies()]
        }
    
    def get_envelope(self) -> Dict:
        """Get current risk envelope"""
        return self._envelope_to_dict(self.current_envelope)
    
    def get_transitions(self, limit: int = 50) -> List[Dict]:
        """Get recent state transitions"""
        transitions = sorted(self.transitions, key=lambda t: t.timestamp, reverse=True)
        return [
            {
                "transition_id": t.transition_id,
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "trigger_detectors": t.trigger_detectors,
                "trigger_values": t.trigger_values,
                "actions_taken": [a.value for a in t.actions_taken],
                "timestamp": t.timestamp
            }
            for t in transitions[:limit]
        ]
    
    def get_health(self) -> Dict:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "phase9.35",
            "status": "ok",
            "current_state": self.current_state.value,
            "total_transitions": len(self.transitions),
            "total_snapshots": len(self.snapshots),
            "policies_count": len(self.policies),
            "last_evaluation_at": self.last_evaluation_at,
            "timestamp": int(time.time() * 1000)
        }
    
    # ============================================
    # Serialization
    # ============================================
    
    def _envelope_to_dict(self, envelope: RiskEnvelope) -> Dict:
        return {
            "state": envelope.state.value,
            "max_exposure": envelope.max_exposure,
            "max_leverage": envelope.max_leverage,
            "max_drawdown": envelope.max_drawdown,
            "stop_multiplier": envelope.stop_multiplier,
            "experimental_allowed": envelope.experimental_allowed,
            "tactical_allowed": envelope.tactical_allowed
        }
    
    def _allocation_to_dict(self, allocation: CapitalAllocation) -> Dict:
        return {
            "equities": allocation.equities,
            "crypto": allocation.crypto,
            "fx": allocation.fx,
            "commodities": allocation.commodities,
            "cash": allocation.cash
        }


# Singleton
global_risk_brain = GlobalRiskBrain()
