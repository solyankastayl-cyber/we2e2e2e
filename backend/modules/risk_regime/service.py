"""
Risk Regime Service
===================

Phase 9.3H - Service layer for risk regime management.
"""

import time
from typing import Dict, List, Optional, Any

from .types import RiskState, RiskPolicy, RiskRegimeConfig, DEFAULT_POLICIES
from .engine import RiskRegimeEngine


class RiskRegimeService:
    """
    Service for managing risk regime engine.
    
    Provides:
    - Risk state updates
    - Policy management
    - Historical analysis
    """
    
    def __init__(self):
        self.engine = RiskRegimeEngine()
    
    # ============================================
    # State Management
    # ============================================
    
    def get_current_state(self) -> Dict:
        """Get current risk regime state"""
        state = self.engine.state
        policy = self.engine.get_current_policy()
        
        return {
            "state": state.state.value,
            "previous_state": state.previous_state.value,
            "risk_score": state.risk_score,
            "bars_in_state": state.bars_in_state,
            "indicators": {
                k: {
                    "value": v.value,
                    "z_score": v.z_score,
                    "percentile": v.percentile,
                    "signal": v.signal
                }
                for k, v in state.indicators.items()
            },
            "policy": {
                "exposure_multiplier": policy.exposure_multiplier,
                "leverage_multiplier": policy.leverage_multiplier,
                "tactical_enabled": policy.tactical_enabled,
                "experimental_enabled": policy.experimental_enabled,
                "new_positions_enabled": policy.new_positions_enabled,
                "budget_compression": policy.budget_compression,
                "max_drawdown_limit": policy.max_drawdown_limit,
                "tighten_stops": policy.tighten_stops
            },
            "last_transition": state.last_transition.value if state.last_transition else None,
            "timestamp": int(time.time() * 1000)
        }
    
    def update_state(
        self,
        returns: Optional[List[float]] = None,
        returns_by_asset: Optional[Dict[str, List[float]]] = None,
        equity_curve: Optional[List[float]] = None,
        vix_value: Optional[float] = None
    ) -> Dict:
        """Update risk regime state"""
        
        state = self.engine.update(
            returns=returns,
            returns_by_asset=returns_by_asset,
            equity_curve=equity_curve,
            vix_value=vix_value
        )
        
        return self.get_current_state()
    
    def force_state(self, state_name: str, reason: str = "manual") -> Dict:
        """Force a specific risk state"""
        
        try:
            state = RiskState(state_name)
        except ValueError:
            return {"error": f"Invalid state: {state_name}"}
        
        self.engine.force_state(state, reason)
        return self.get_current_state()
    
    # ============================================
    # Policy Management
    # ============================================
    
    def get_policies(self) -> Dict:
        """Get all policies"""
        return {
            state.value: {
                "exposure_multiplier": policy.exposure_multiplier,
                "leverage_multiplier": policy.leverage_multiplier,
                "tactical_enabled": policy.tactical_enabled,
                "experimental_enabled": policy.experimental_enabled,
                "new_positions_enabled": policy.new_positions_enabled,
                "budget_compression": policy.budget_compression,
                "max_drawdown_limit": policy.max_drawdown_limit,
                "position_size_cap": policy.position_size_cap,
                "tighten_stops": policy.tighten_stops,
                "stop_multiplier": policy.stop_multiplier,
                "max_correlation_allowed": policy.max_correlation_allowed
            }
            for state, policy in self.engine.policies.items()
        }
    
    def update_policy(
        self,
        state_name: str,
        exposure_multiplier: Optional[float] = None,
        leverage_multiplier: Optional[float] = None,
        tactical_enabled: Optional[bool] = None,
        experimental_enabled: Optional[bool] = None,
        new_positions_enabled: Optional[bool] = None,
        budget_compression: Optional[float] = None,
        max_drawdown_limit: Optional[float] = None
    ) -> Dict:
        """Update policy for a state"""
        
        try:
            state = RiskState(state_name)
        except ValueError:
            return {"error": f"Invalid state: {state_name}"}
        
        policy = self.engine.get_policy_for_state(state)
        
        if exposure_multiplier is not None:
            policy.exposure_multiplier = exposure_multiplier
        if leverage_multiplier is not None:
            policy.leverage_multiplier = leverage_multiplier
        if tactical_enabled is not None:
            policy.tactical_enabled = tactical_enabled
        if experimental_enabled is not None:
            policy.experimental_enabled = experimental_enabled
        if new_positions_enabled is not None:
            policy.new_positions_enabled = new_positions_enabled
        if budget_compression is not None:
            policy.budget_compression = budget_compression
        if max_drawdown_limit is not None:
            policy.max_drawdown_limit = max_drawdown_limit
        
        self.engine.update_policy(state, policy)
        
        return {"message": f"Policy updated for {state_name}"}
    
    # ============================================
    # Analysis
    # ============================================
    
    def get_transitions(self, limit: int = 100) -> Dict:
        """Get state transition history"""
        history = self.engine.get_state_history()
        
        return {
            "total_transitions": len(history),
            "transitions": history[-limit:]
        }
    
    def get_state_distribution(self) -> Dict:
        """Get time distribution across states"""
        dist = self.engine.get_state_distribution()
        total = sum(dist.values())
        
        return {
            "distribution": dist,
            "percentages": {
                k: round(v / total * 100, 2) if total > 0 else 0
                for k, v in dist.items()
            }
        }
    
    def get_indicator_breakdown(self) -> Dict:
        """Get current indicator values breakdown"""
        return {
            k: {
                "indicator": v.indicator.value,
                "value": v.value,
                "z_score": v.z_score,
                "percentile": v.percentile,
                "signal": v.signal,
                "weight": v.weight,
                "contribution": round(v.value * v.weight, 2)
            }
            for k, v in self.engine.state.indicators.items()
        }
    
    # ============================================
    # Simulation
    # ============================================
    
    def simulate_scenario(
        self,
        vix_value: float,
        volatility: float,
        correlation: float,
        drawdown: float
    ) -> Dict:
        """Simulate risk score for a scenario"""
        
        # Create temporary indicators
        from .types import RiskIndicator, RiskIndicatorValue
        
        indicators = {
            "VIX": RiskIndicatorValue(
                indicator=RiskIndicator.VIX,
                value=vix_value,
                weight=0.25
            ),
            "VOLATILITY": RiskIndicatorValue(
                indicator=RiskIndicator.VOLATILITY,
                value=volatility,
                weight=0.20
            ),
            "CORRELATION": RiskIndicatorValue(
                indicator=RiskIndicator.CORRELATION,
                value=correlation,
                weight=0.20
            ),
            "DRAWDOWN": RiskIndicatorValue(
                indicator=RiskIndicator.DRAWDOWN,
                value=drawdown * 100,  # Convert to percentage
                weight=0.15
            )
        }
        
        risk_score = self.engine.compute_risk_score(indicators)
        
        # Determine what state this would be
        if risk_score >= 80:
            implied_state = "CRISIS"
        elif risk_score >= 60:
            implied_state = "STRESS"
        elif risk_score >= 40:
            implied_state = "ELEVATED"
        else:
            implied_state = "NORMAL"
        
        return {
            "scenario": {
                "vix": vix_value,
                "volatility": volatility,
                "correlation": correlation,
                "drawdown": drawdown
            },
            "risk_score": risk_score,
            "implied_state": implied_state,
            "policy": self.get_policies()[implied_state]
        }
    
    # ============================================
    # Health Check
    # ============================================
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.3H",
            "status": "ok",
            "current_state": self.engine.state.state.value,
            "risk_score": self.engine.state.risk_score,
            "total_transitions": len(self.engine.transitions),
            "supported_states": [s.value for s in RiskState],
            "timestamp": int(time.time() * 1000)
        }


# Singleton instance
risk_regime_service = RiskRegimeService()
