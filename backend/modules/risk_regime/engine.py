"""
Risk Regime Engine - Core
=========================

Phase 9.3H - Global tactical risk state management.

Monitors market conditions and adjusts system behavior:
- NORMAL: Full allocation
- ELEVATED: Reduced exposure, no experimental
- STRESS: Defensive mode, no new positions
- CRISIS: Capital preservation
"""

import math
import time
import uuid
from typing import Dict, List, Optional, Tuple
from collections import deque

from .types import (
    RiskState, RiskIndicator, TransitionTrigger,
    RiskIndicatorValue, RiskRegimeState, RiskPolicy,
    StateTransition, RiskRegimeConfig, DEFAULT_POLICIES
)


class RiskRegimeEngine:
    """
    Core engine for risk regime management.
    
    Purpose:
    - Monitor risk indicators
    - Determine global risk state
    - Apply policy adjustments
    - Log state transitions
    """
    
    def __init__(self, config: Optional[RiskRegimeConfig] = None):
        self.config = config or RiskRegimeConfig()
        
        # Current state
        self.state = RiskRegimeState()
        
        # Policies
        self.policies = DEFAULT_POLICIES.copy()
        
        # History
        self.transitions: List[StateTransition] = []
        self.indicator_history: Dict[str, deque] = {}
        
        # Price/return history for calculations
        self.returns_history: deque = deque(maxlen=500)
        self.correlation_history: deque = deque(maxlen=100)
        
        # VIX-like proxy (if no VIX data)
        self.vix_proxy: float = 15.0
    
    # ============================================
    # Indicator Computation
    # ============================================
    
    def compute_volatility_indicator(
        self,
        returns: List[float],
        lookback: int = 20
    ) -> RiskIndicatorValue:
        """Compute realized volatility indicator"""
        
        if len(returns) < lookback:
            return RiskIndicatorValue(
                indicator=RiskIndicator.VOLATILITY,
                value=0.0,
                signal="neutral"
            )
        
        recent = returns[-lookback:]
        vol = math.sqrt(sum(r ** 2 for r in recent) / lookback) * math.sqrt(252) * 100
        
        # Historical comparison
        all_vols = []
        for i in range(lookback, len(returns)):
            window = returns[i-lookback:i]
            v = math.sqrt(sum(r ** 2 for r in window) / lookback) * math.sqrt(252) * 100
            all_vols.append(v)
        
        if all_vols:
            mean_vol = sum(all_vols) / len(all_vols)
            std_vol = math.sqrt(sum((v - mean_vol) ** 2 for v in all_vols) / len(all_vols))
            z_score = (vol - mean_vol) / std_vol if std_vol > 0 else 0
            percentile = sum(1 for v in all_vols if v < vol) / len(all_vols) * 100
        else:
            z_score = 0
            percentile = 50
        
        signal = "neutral"
        if z_score > 1.5:
            signal = "bearish"
        elif z_score < -1.0:
            signal = "bullish"
        
        return RiskIndicatorValue(
            indicator=RiskIndicator.VOLATILITY,
            value=round(vol, 2),
            z_score=round(z_score, 2),
            percentile=round(percentile, 1),
            signal=signal,
            weight=self.config.indicator_weights.get("VOLATILITY", 0.20),
            timestamp=int(time.time() * 1000)
        )
    
    def compute_correlation_indicator(
        self,
        returns_assets: Dict[str, List[float]],
        lookback: int = 60
    ) -> RiskIndicatorValue:
        """Compute cross-asset correlation indicator"""
        
        assets = list(returns_assets.keys())
        
        if len(assets) < 2:
            return RiskIndicatorValue(
                indicator=RiskIndicator.CORRELATION,
                value=0.0,
                signal="neutral"
            )
        
        # Compute pairwise correlations
        correlations = []
        
        for i, a1 in enumerate(assets):
            for j, a2 in enumerate(assets):
                if j <= i:
                    continue
                
                r1 = returns_assets[a1][-lookback:]
                r2 = returns_assets[a2][-lookback:]
                
                if len(r1) < 10 or len(r2) < 10:
                    continue
                
                n = min(len(r1), len(r2))
                mean1 = sum(r1[:n]) / n
                mean2 = sum(r2[:n]) / n
                
                cov = sum((r1[k] - mean1) * (r2[k] - mean2) for k in range(n)) / n
                var1 = sum((r - mean1) ** 2 for r in r1[:n]) / n
                var2 = sum((r - mean2) ** 2 for r in r2[:n]) / n
                
                if var1 > 0 and var2 > 0:
                    corr = cov / (math.sqrt(var1) * math.sqrt(var2))
                    correlations.append(abs(corr))
        
        if not correlations:
            return RiskIndicatorValue(
                indicator=RiskIndicator.CORRELATION,
                value=0.0,
                signal="neutral"
            )
        
        avg_corr = sum(correlations) / len(correlations)
        
        # Correlation explosion = danger
        signal = "neutral"
        if avg_corr > 0.7:
            signal = "bearish"
        elif avg_corr < 0.3:
            signal = "bullish"
        
        return RiskIndicatorValue(
            indicator=RiskIndicator.CORRELATION,
            value=round(avg_corr, 4),
            z_score=round((avg_corr - 0.4) / 0.15, 2),  # Approx z-score
            percentile=round(avg_corr * 100, 1),
            signal=signal,
            weight=self.config.indicator_weights.get("CORRELATION", 0.20),
            timestamp=int(time.time() * 1000)
        )
    
    def compute_drawdown_indicator(
        self,
        equity_curve: List[float]
    ) -> RiskIndicatorValue:
        """Compute drawdown indicator"""
        
        if len(equity_curve) < 2:
            return RiskIndicatorValue(
                indicator=RiskIndicator.DRAWDOWN,
                value=0.0,
                signal="neutral"
            )
        
        # Find peak and current drawdown
        peak = equity_curve[0]
        current_dd = 0.0
        
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0
            current_dd = dd
        
        # Drawdown level mapping
        signal = "neutral"
        if current_dd > 0.15:
            signal = "bearish"
        elif current_dd > 0.10:
            signal = "neutral"
        else:
            signal = "bullish"
        
        return RiskIndicatorValue(
            indicator=RiskIndicator.DRAWDOWN,
            value=round(current_dd * 100, 2),
            z_score=round((current_dd - 0.05) / 0.05, 2),
            percentile=round(current_dd * 200, 1),  # 10% DD = 20 percentile
            signal=signal,
            weight=self.config.indicator_weights.get("DRAWDOWN", 0.15),
            timestamp=int(time.time() * 1000)
        )
    
    def compute_vix_indicator(self, vix_value: Optional[float] = None) -> RiskIndicatorValue:
        """Compute VIX indicator"""
        
        if vix_value is None:
            vix_value = self.vix_proxy
        
        # VIX levels
        # < 15: Low volatility
        # 15-20: Normal
        # 20-30: Elevated
        # 30-40: High
        # > 40: Crisis
        
        signal = "neutral"
        z_score = (vix_value - 18) / 6  # Approximate
        
        if vix_value > 35:
            signal = "bearish"
        elif vix_value > 25:
            signal = "bearish"
        elif vix_value < 15:
            signal = "bullish"
        
        return RiskIndicatorValue(
            indicator=RiskIndicator.VIX,
            value=round(vix_value, 2),
            z_score=round(z_score, 2),
            percentile=round(min(100, vix_value * 2), 1),
            signal=signal,
            weight=self.config.indicator_weights.get("VIX", 0.25),
            timestamp=int(time.time() * 1000)
        )
    
    # ============================================
    # Risk Score Computation
    # ============================================
    
    def compute_risk_score(
        self,
        indicators: Dict[str, RiskIndicatorValue]
    ) -> float:
        """
        Compute composite risk score (0-100).
        
        Higher score = Higher risk = More defensive posture.
        """
        
        total_weight = 0.0
        weighted_score = 0.0
        
        for ind_name, ind_value in indicators.items():
            weight = ind_value.weight
            
            # Map indicator to risk contribution (0-100)
            if ind_value.indicator == RiskIndicator.VIX:
                # VIX: 10 = 0 risk, 50 = 100 risk
                score = max(0, min(100, (ind_value.value - 10) / 40 * 100))
            
            elif ind_value.indicator == RiskIndicator.VOLATILITY:
                # Vol: 10% = 0 risk, 50% = 100 risk
                score = max(0, min(100, (ind_value.value - 10) / 40 * 100))
            
            elif ind_value.indicator == RiskIndicator.CORRELATION:
                # Corr: 0.2 = 0 risk, 0.9 = 100 risk
                score = max(0, min(100, (ind_value.value - 0.2) / 0.7 * 100))
            
            elif ind_value.indicator == RiskIndicator.DRAWDOWN:
                # DD: 0% = 0 risk, 25% = 100 risk
                score = max(0, min(100, ind_value.value / 25 * 100))
            
            else:
                # Use percentile as default
                score = ind_value.percentile
            
            weighted_score += score * weight
            total_weight += weight
        
        if total_weight == 0:
            return 25.0  # Default to low risk
        
        return round(weighted_score / total_weight, 2)
    
    # ============================================
    # State Determination
    # ============================================
    
    def determine_state(self, risk_score: float) -> Tuple[RiskState, Optional[TransitionTrigger]]:
        """
        Determine risk state from score with hysteresis.
        
        Returns (new_state, trigger if transition occurred)
        """
        
        current_state = self.state.state
        new_state = current_state
        trigger = None
        
        # Upgrade (to higher risk)
        if current_state == RiskState.NORMAL:
            if risk_score >= self.config.normal_to_elevated:
                new_state = RiskState.ELEVATED
                trigger = TransitionTrigger.VOLATILITY_SPIKE
        
        elif current_state == RiskState.ELEVATED:
            if risk_score >= self.config.elevated_to_stress:
                new_state = RiskState.STRESS
                trigger = TransitionTrigger.DRAWDOWN_BREACH
        
        elif current_state == RiskState.STRESS:
            if risk_score >= self.config.stress_to_crisis:
                new_state = RiskState.CRISIS
                trigger = TransitionTrigger.CORRELATION_EXPLOSION
        
        # Downgrade (to lower risk) - with hysteresis
        if current_state == RiskState.CRISIS:
            if risk_score < self.config.crisis_to_stress:
                if self.state.bars_in_state >= self.config.min_bars_for_downgrade:
                    new_state = RiskState.STRESS
                    trigger = TransitionTrigger.RECOVERY
        
        elif current_state == RiskState.STRESS:
            if risk_score < self.config.stress_to_elevated:
                if self.state.bars_in_state >= self.config.min_bars_for_downgrade:
                    new_state = RiskState.ELEVATED
                    trigger = TransitionTrigger.RECOVERY
        
        elif current_state == RiskState.ELEVATED:
            if risk_score < self.config.elevated_to_normal:
                if self.state.bars_in_state >= self.config.min_bars_for_downgrade:
                    new_state = RiskState.NORMAL
                    trigger = TransitionTrigger.RECOVERY
        
        return new_state, trigger
    
    # ============================================
    # Update Methods
    # ============================================
    
    def update(
        self,
        returns: Optional[List[float]] = None,
        returns_by_asset: Optional[Dict[str, List[float]]] = None,
        equity_curve: Optional[List[float]] = None,
        vix_value: Optional[float] = None
    ) -> RiskRegimeState:
        """
        Update risk regime state.
        
        Call this on each bar to update the state.
        """
        
        # Compute indicators
        indicators = {}
        
        # VIX
        vix_ind = self.compute_vix_indicator(vix_value)
        indicators["VIX"] = vix_ind
        
        # Volatility
        if returns and len(returns) >= 20:
            vol_ind = self.compute_volatility_indicator(returns)
            indicators["VOLATILITY"] = vol_ind
            
            # Update VIX proxy from volatility
            self.vix_proxy = vol_ind.value * 0.8  # Rough approximation
        
        # Correlation
        if returns_by_asset and len(returns_by_asset) >= 2:
            corr_ind = self.compute_correlation_indicator(returns_by_asset)
            indicators["CORRELATION"] = corr_ind
        
        # Drawdown
        if equity_curve and len(equity_curve) >= 2:
            dd_ind = self.compute_drawdown_indicator(equity_curve)
            indicators["DRAWDOWN"] = dd_ind
        
        # Compute risk score
        risk_score = self.compute_risk_score(indicators)
        
        # Determine new state
        new_state, trigger = self.determine_state(risk_score)
        
        # Handle transition
        if new_state != self.state.state:
            transition = StateTransition(
                transition_id=f"trans_{int(time.time())}",
                from_state=self.state.state,
                to_state=new_state,
                trigger=trigger or TransitionTrigger.TIME_BASED,
                risk_score=risk_score,
                indicator_values={k: v.value for k, v in indicators.items()},
                actions_taken=self._get_transition_actions(self.state.state, new_state),
                timestamp=int(time.time() * 1000)
            )
            self.transitions.append(transition)
            
            # Update state
            self.state.previous_state = self.state.state
            self.state.state = new_state
            self.state.bars_in_state = 0
            self.state.state_start_timestamp = int(time.time() * 1000)
            self.state.last_transition = trigger
            self.state.last_transition_timestamp = int(time.time() * 1000)
        else:
            self.state.bars_in_state += 1
        
        # Update state values
        self.state.risk_score = risk_score
        self.state.indicators = {k: v for k, v in indicators.items()}
        
        return self.state
    
    def _get_transition_actions(
        self,
        from_state: RiskState,
        to_state: RiskState
    ) -> List[str]:
        """Get list of actions taken during transition"""
        
        old_policy = self.policies.get(from_state)
        new_policy = self.policies.get(to_state)
        
        if not old_policy or not new_policy:
            return []
        
        actions = []
        
        if new_policy.exposure_multiplier < old_policy.exposure_multiplier:
            actions.append(f"Reduce exposure to {new_policy.exposure_multiplier * 100:.0f}%")
        elif new_policy.exposure_multiplier > old_policy.exposure_multiplier:
            actions.append(f"Increase exposure to {new_policy.exposure_multiplier * 100:.0f}%")
        
        if new_policy.tactical_enabled != old_policy.tactical_enabled:
            if new_policy.tactical_enabled:
                actions.append("Enable tactical strategies")
            else:
                actions.append("Disable tactical strategies")
        
        if new_policy.experimental_enabled != old_policy.experimental_enabled:
            if not new_policy.experimental_enabled:
                actions.append("Disable experimental strategies")
        
        if new_policy.new_positions_enabled != old_policy.new_positions_enabled:
            if not new_policy.new_positions_enabled:
                actions.append("Block new positions")
            else:
                actions.append("Allow new positions")
        
        if new_policy.tighten_stops and not old_policy.tighten_stops:
            actions.append("Tighten stops")
        
        return actions
    
    # ============================================
    # Policy Access
    # ============================================
    
    def get_current_policy(self) -> RiskPolicy:
        """Get policy for current state"""
        return self.policies.get(self.state.state, self.policies[RiskState.NORMAL])
    
    def get_policy_for_state(self, state: RiskState) -> RiskPolicy:
        """Get policy for specific state"""
        return self.policies.get(state, self.policies[RiskState.NORMAL])
    
    def update_policy(self, state: RiskState, policy: RiskPolicy):
        """Update policy for a state"""
        self.policies[state] = policy
    
    # ============================================
    # Manual Override
    # ============================================
    
    def force_state(self, state: RiskState, reason: str = "manual override"):
        """Force a specific risk state (manual override)"""
        
        if state != self.state.state:
            transition = StateTransition(
                transition_id=f"trans_manual_{int(time.time())}",
                from_state=self.state.state,
                to_state=state,
                trigger=TransitionTrigger.MANUAL_OVERRIDE,
                risk_score=self.state.risk_score,
                indicator_values={k: v.value for k, v in self.state.indicators.items()},
                actions_taken=[f"Manual override: {reason}"],
                timestamp=int(time.time() * 1000)
            )
            self.transitions.append(transition)
            
            self.state.previous_state = self.state.state
            self.state.state = state
            self.state.bars_in_state = 0
            self.state.last_transition = TransitionTrigger.MANUAL_OVERRIDE
    
    # ============================================
    # Analysis
    # ============================================
    
    def get_state_history(self) -> List[Dict]:
        """Get history of state transitions"""
        return [
            {
                "transition_id": t.transition_id,
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "trigger": t.trigger.value,
                "risk_score": t.risk_score,
                "indicator_values": t.indicator_values,
                "actions_taken": t.actions_taken,
                "timestamp": t.timestamp
            }
            for t in self.transitions
        ]
    
    def get_state_distribution(self) -> Dict[str, int]:
        """Get distribution of time spent in each state"""
        dist = {state.value: 0 for state in RiskState}
        
        for i, trans in enumerate(self.transitions):
            if i > 0:
                prev_trans = self.transitions[i - 1]
                duration = trans.timestamp - prev_trans.timestamp
                dist[prev_trans.to_state.value] += duration
        
        # Add current state duration
        if self.transitions:
            last = self.transitions[-1]
            dist[last.to_state.value] += int(time.time() * 1000) - last.timestamp
        
        return dist


# Singleton instance
risk_regime_engine = RiskRegimeEngine()
