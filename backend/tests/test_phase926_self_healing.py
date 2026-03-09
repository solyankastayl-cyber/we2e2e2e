"""
Test Phase 9.26: Self-Healing Strategy Engine
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')

from modules.self_healing.service import (
    SelfHealingService,
    StrategyHealthEngine,
    AutoWeightAdjuster,
    AutoDemotionEngine,
    RecoveryEngine,
    AdaptiveHealingEngine,
    AuditTrail,
    HealthVerdict,
    HealingAction,
    RecoveryStatus,
    health_to_dict,
    status_to_dict,
    event_to_dict,
    recovery_state_to_dict
)


class TestStrategyHealthEngine:
    """Test Strategy Health Engine"""
    
    def setup_method(self):
        self.engine = StrategyHealthEngine()
    
    def test_compute_health(self):
        """Test health computation"""
        health = self.engine.compute_health("MTF_BREAKOUT")
        
        assert health.strategy_id == "MTF_BREAKOUT"
        assert 0 <= health.health_score <= 1
        assert health.verdict in HealthVerdict
    
    def test_health_verdicts(self):
        """Test health verdict thresholds"""
        # High-performing strategy should be healthy
        health = self.engine.compute_health("MTF_BREAKOUT")
        assert health.verdict in [HealthVerdict.HEALTHY, HealthVerdict.WARNING]
        
        # Poor strategy should be degraded or critical
        health = self.engine.compute_health("LIQUIDITY_SWEEP")
        assert health.verdict in [HealthVerdict.DEGRADED, HealthVerdict.CRITICAL, HealthVerdict.WARNING]
    
    def test_component_scores(self):
        """Test component scores"""
        health = self.engine.compute_health("DOUBLE_BOTTOM")
        
        assert 0 <= health.rolling_pf_score <= 1
        assert 0 <= health.rolling_sharpe_score <= 1
        assert 0 <= health.drawdown_score <= 1
        assert 0 <= health.edge_decay_score <= 1
    
    def test_health_trend(self):
        """Test health trend tracking"""
        # First computation
        health1 = self.engine.compute_health("CHANNEL_BREAKOUT")
        
        # Second computation
        health2 = self.engine.compute_health("CHANNEL_BREAKOUT")
        
        assert health2.health_trend in ["IMPROVING", "STABLE", "DECLINING"]
        assert health2.previous_health_score == health1.health_score


class TestAutoWeightAdjuster:
    """Test Auto Weight Adjuster"""
    
    def setup_method(self):
        self.adjuster = AutoWeightAdjuster()
    
    def test_compute_adjustment(self):
        """Test weight adjustment computation"""
        adjustment = self.adjuster.compute_adjustment("MTF_BREAKOUT")
        
        assert adjustment.strategy_id == "MTF_BREAKOUT"
        assert 0 <= adjustment.new_weight <= 1.5
        assert 0 <= adjustment.target_weight <= 1.5
    
    def test_weight_limits(self):
        """Test daily change limits"""
        # Make multiple adjustments
        for _ in range(5):
            adjustment = self.adjuster.compute_adjustment("DOUBLE_TOP")
        
        # Daily change should be limited
        assert abs(adjustment.daily_change) <= 0.10 + 0.01  # Allow small buffer
    
    def test_get_all_weights(self):
        """Test getting all weights"""
        weights = self.adjuster.get_all_weights()
        
        assert len(weights) == 11
        assert "MTF_BREAKOUT" in weights
    
    def test_recent_adjustments(self):
        """Test adjustment history"""
        self.adjuster.compute_adjustment("MTF_BREAKOUT")
        
        adjustments = self.adjuster.get_recent_adjustments()
        assert isinstance(adjustments, list)


class TestAutoDemotionEngine:
    """Test Auto Demotion Engine"""
    
    def setup_method(self):
        self.engine = AutoDemotionEngine()
    
    def test_check_demotion(self):
        """Test demotion check"""
        result = self.engine.check_demotion("MTF_BREAKOUT")
        
        # Healthy strategy shouldn't be demoted immediately
        # (may or may not be demoted depending on simulated metrics)
        assert result is None or isinstance(result, dict)
    
    def test_get_lifecycle(self):
        """Test lifecycle retrieval"""
        lifecycle = self.engine.get_lifecycle("MTF_BREAKOUT")
        
        assert lifecycle == "APPROVED"
    
    def test_get_all_lifecycles(self):
        """Test all lifecycles"""
        lifecycles = self.engine.get_all_lifecycles()
        
        assert len(lifecycles) == 11
        assert lifecycles["MTF_BREAKOUT"] == "APPROVED"
        assert lifecycles["HEAD_SHOULDERS"] == "LIMITED"
        assert lifecycles["LIQUIDITY_SWEEP"] == "DEPRECATED"


class TestRecoveryEngine:
    """Test Recovery Engine"""
    
    def setup_method(self):
        self.engine = RecoveryEngine()
    
    def test_start_recovery(self):
        """Test starting recovery"""
        state = self.engine.start_recovery("HEAD_SHOULDERS")
        
        assert state.strategy_id == "HEAD_SHOULDERS"
        assert state.status == RecoveryStatus.IN_PROGRESS
        assert state.target_trades == 50
    
    def test_check_recovery(self):
        """Test recovery progress check"""
        self.engine.start_recovery("WEDGE_RISING")
        state = self.engine.check_recovery("WEDGE_RISING")
        
        assert state.status in RecoveryStatus
        assert state.progress_pct >= 0
    
    def test_get_all_recoveries(self):
        """Test getting all recoveries"""
        self.engine.start_recovery("HARMONIC_ABCD")
        
        recoveries = self.engine.get_all_recoveries()
        assert "HARMONIC_ABCD" in recoveries


class TestAdaptiveHealingEngine:
    """Test Adaptive Healing Engine"""
    
    def setup_method(self):
        self.engine = AdaptiveHealingEngine()
    
    def test_compute_regime_health(self):
        """Test regime health computation"""
        states = self.engine.compute_regime_health("MTF_BREAKOUT")
        
        assert len(states) > 0
        assert "TREND_UP" in states
        
        trend_up = states["TREND_UP"]
        assert trend_up.strategy_id == "MTF_BREAKOUT"
        assert 0 <= trend_up.health_score <= 1
    
    def test_compute_asset_health(self):
        """Test asset health computation"""
        states = self.engine.compute_asset_health("DOUBLE_BOTTOM")
        
        assert len(states) > 0
        assert "BTC" in states
        
        btc = states["BTC"]
        assert btc.strategy_id == "DOUBLE_BOTTOM"
        assert 0 <= btc.health_score <= 1
    
    def test_restrictions(self):
        """Test restriction tracking"""
        self.engine.compute_regime_health("MTF_BREAKOUT")
        
        restrictions = self.engine.get_restrictions()
        assert isinstance(restrictions, list)


class TestAuditTrail:
    """Test Audit Trail"""
    
    def setup_method(self):
        self.audit = AuditTrail()
    
    def test_record_event(self):
        """Test recording event"""
        event = self.audit.record(
            "MTF_BREAKOUT",
            HealingAction.WEIGHT_REDUCED,
            "weight=1.0",
            "weight=0.75",
            "Health degradation"
        )
        
        assert event.strategy_id == "MTF_BREAKOUT"
        assert event.action == HealingAction.WEIGHT_REDUCED
    
    def test_get_events(self):
        """Test getting events"""
        self.audit.record("S1", HealingAction.DEMOTED, "A", "B", "Test")
        self.audit.record("S2", HealingAction.PROMOTED, "B", "A", "Test")
        
        events = self.audit.get_events()
        assert len(events) == 2
    
    def test_get_events_for_strategy(self):
        """Test filtering by strategy"""
        self.audit.record("MTF", HealingAction.DEMOTED, "A", "B", "")
        self.audit.record("OTHER", HealingAction.DEMOTED, "A", "B", "")
        self.audit.record("MTF", HealingAction.PROMOTED, "B", "A", "")
        
        mtf_events = self.audit.get_events_for_strategy("MTF")
        assert len(mtf_events) == 2


class TestSelfHealingService:
    """Test Self-Healing Service"""
    
    def setup_method(self):
        self.service = SelfHealingService()
    
    def test_recompute_all(self):
        """Test full recompute"""
        results = self.service.recompute_all()
        
        assert "health" in results
        assert "weights" in results
        assert "demotions" in results
        assert "regime_states" in results
        assert "asset_states" in results
        
        assert len(results["health"]) == 11
    
    def test_get_status(self):
        """Test status retrieval"""
        self.service.recompute_all()
        status = self.service.get_status()
        
        assert status.enabled is True
        total = status.healthy_strategies + status.warning_strategies + status.degraded_strategies + status.critical_strategies
        assert total > 0
    
    def test_get_strategy_details(self):
        """Test strategy details"""
        self.service.recompute_all()
        details = self.service.get_strategy_details("MTF_BREAKOUT")
        
        assert details["strategyId"] == "MTF_BREAKOUT"
        assert "health" in details
        assert "weight" in details
        assert "lifecycle" in details
    
    def test_override_weight(self):
        """Test manual weight override"""
        result = self.service.override("MTF_BREAKOUT", "SET_WEIGHT", {"weight": 0.5})
        
        assert result["success"] is True
        assert self.service.weight_adjuster.get_weight("MTF_BREAKOUT") == 0.5
    
    def test_override_lifecycle(self):
        """Test manual lifecycle override"""
        result = self.service.override("HEAD_SHOULDERS", "SET_LIFECYCLE", {"state": "APPROVED"})
        
        assert result["success"] is True
        assert self.service.demotion_engine.get_lifecycle("HEAD_SHOULDERS") == "APPROVED"
    
    def test_get_health(self):
        """Test health endpoint"""
        health = self.service.get_health()
        
        assert health["enabled"] is True
        assert health["status"] == "ok"
        assert "components" in health


class TestSerialization:
    """Test serialization functions"""
    
    def test_health_serialization(self):
        """Test health serialization"""
        engine = StrategyHealthEngine()
        health = engine.compute_health("MTF_BREAKOUT")
        
        data = health_to_dict(health)
        
        assert "strategyId" in data
        assert "healthScore" in data
        assert "verdict" in data
        assert "componentScores" in data
    
    def test_status_serialization(self):
        """Test status serialization"""
        service = SelfHealingService()
        service.recompute_all()
        status = service.get_status()
        
        data = status_to_dict(status)
        
        assert "enabled" in data
        assert "strategies" in data
        assert "recentActivity" in data
    
    def test_event_serialization(self):
        """Test event serialization"""
        audit = AuditTrail()
        event = audit.record("TEST", HealingAction.DEMOTED, "A", "B", "Test")
        
        data = event_to_dict(event)
        
        assert "eventId" in data
        assert "action" in data
        assert "reason" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
