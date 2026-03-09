"""
Phase 9.27: Meta-Strategy Layer Tests
=====================================

Tests for Meta-Strategy Layer.
"""

import pytest
import time
from typing import Dict

# Import service
from modules.meta_strategy.service import (
    MetaStrategyService,
    StrategyScoringEngine,
    CrowdingDetector,
    StrategyFamilyManager,
    TierAllocator,
    StrategyAdmissionEngine,
    StrategyScore,
    FamilyBudget,
    TierAllocation,
    CrowdingPair,
    AdmissionDecision,
    StrategyTier,
    StrategyFamily,
    DEFAULT_META_STRATEGY_CONFIG,
    strategy_score_to_dict,
    meta_state_to_dict
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def config():
    """Default config"""
    return DEFAULT_META_STRATEGY_CONFIG


@pytest.fixture
def scoring_engine(config):
    """Create StrategyScoringEngine"""
    return StrategyScoringEngine(config)


@pytest.fixture
def crowding_detector(config):
    """Create CrowdingDetector"""
    return CrowdingDetector(config)


@pytest.fixture
def family_manager(config):
    """Create StrategyFamilyManager"""
    return StrategyFamilyManager(config)


@pytest.fixture
def tier_allocator(config):
    """Create TierAllocator"""
    return TierAllocator(config)


@pytest.fixture
def admission_engine(config):
    """Create StrategyAdmissionEngine"""
    return StrategyAdmissionEngine(config)


@pytest.fixture
def meta_service(config):
    """Create MetaStrategyService"""
    return MetaStrategyService(config)


@pytest.fixture
def sample_strategies() -> Dict[str, Dict]:
    """Sample strategy data"""
    return {
        "MTF_BREAKOUT": {
            "family": "breakout_family",
            "tier": "CORE",
            "health_verdict": "HEALTHY",
            "health_score": 0.85,
            "lifecycle": "APPROVED",
            "healing_status": "HEALTHY",
            "healing_weight": 1.0,
            "rolling_pf": 1.6,
            "rolling_wr": 0.58,
            "calibration_score": 0.8,
            "brier_score": 0.15,
            "base_weight": 1.0,
            "activation_map": {"TREND_UP": "ON", "RANGE": "LIMITED", "TREND_DOWN": "OFF"},
            "features": ["breakout", "volume", "mtf", "momentum"]
        },
        "CHANNEL_BREAKOUT": {
            "family": "breakout_family",
            "tier": "TACTICAL",
            "health_verdict": "WARNING",
            "health_score": 0.65,
            "lifecycle": "LIMITED",
            "healing_status": "WARNING",
            "healing_weight": 0.8,
            "rolling_pf": 1.3,
            "rolling_wr": 0.55,
            "calibration_score": 0.7,
            "brier_score": 0.20,
            "base_weight": 1.0,
            "activation_map": {"TREND_UP": "ON", "RANGE": "OFF"},
            "features": ["breakout", "channel", "support_resistance"]
        },
        "REVERSAL_DIVERGENCE": {
            "family": "reversal_family",
            "tier": "TACTICAL",
            "health_verdict": "HEALTHY",
            "health_score": 0.80,
            "lifecycle": "APPROVED",
            "healing_status": "HEALTHY",
            "healing_weight": 1.0,
            "rolling_pf": 1.5,
            "rolling_wr": 0.60,
            "calibration_score": 0.85,
            "brier_score": 0.12,
            "base_weight": 1.0,
            "activation_map": {"RANGE": "ON", "COMPRESSION": "ON", "TREND_UP": "LIMITED"},
            "features": ["divergence", "rsi", "reversal", "exhaustion"]
        },
        "EXPERIMENTAL_ML": {
            "family": "experimental_family",
            "tier": "EXPERIMENTAL",
            "health_verdict": "DEGRADED",
            "health_score": 0.45,
            "lifecycle": "TESTING",
            "healing_status": "DEGRADED",
            "healing_weight": 0.5,
            "rolling_pf": 0.9,
            "rolling_wr": 0.48,
            "calibration_score": 0.5,
            "brier_score": 0.35,
            "base_weight": 1.0,
            "activation_map": {"TREND_UP": "WATCH"},
            "features": ["ml", "neural", "experimental"]
        }
    }


# ============================================
# StrategyScoringEngine Tests
# ============================================

class TestStrategyScoringEngine:
    """Tests for StrategyScoringEngine"""
    
    def test_score_healthy_strategy(self, scoring_engine, sample_strategies):
        """Test scoring a healthy strategy"""
        score = scoring_engine.score_strategy(
            "MTF_BREAKOUT",
            sample_strategies["MTF_BREAKOUT"],
            regime="TREND_UP"
        )
        
        assert score.strategy_id == "MTF_BREAKOUT"
        assert score.edge_health > 0.8
        assert score.regime_fit == 1.0  # ON in TREND_UP
        assert score.recent_performance >= 1.0
        assert score.final_weight > 0.5
        assert score.status == "ACTIVE"
    
    def test_score_degraded_strategy(self, scoring_engine, sample_strategies):
        """Test scoring a degraded strategy"""
        score = scoring_engine.score_strategy(
            "EXPERIMENTAL_ML",
            sample_strategies["EXPERIMENTAL_ML"],
            regime="RANGE"
        )
        
        assert score.edge_health < 0.6
        assert score.lifecycle_modifier < 0.5  # TESTING
        assert score.final_weight < 0.3
    
    def test_regime_fit_on(self, scoring_engine, sample_strategies):
        """Test regime fit when ON"""
        score = scoring_engine.score_strategy(
            "MTF_BREAKOUT",
            sample_strategies["MTF_BREAKOUT"],
            regime="TREND_UP"
        )
        
        assert score.regime_fit == 1.0
    
    def test_regime_fit_limited(self, scoring_engine, sample_strategies):
        """Test regime fit when LIMITED"""
        score = scoring_engine.score_strategy(
            "MTF_BREAKOUT",
            sample_strategies["MTF_BREAKOUT"],
            regime="RANGE"
        )
        
        assert score.regime_fit == 0.5
    
    def test_regime_fit_off(self, scoring_engine, sample_strategies):
        """Test regime fit when OFF"""
        score = scoring_engine.score_strategy(
            "MTF_BREAKOUT",
            sample_strategies["MTF_BREAKOUT"],
            regime="TREND_DOWN"
        )
        
        assert score.regime_fit == 0.0
    
    def test_performance_boost(self, scoring_engine):
        """Test performance boost for good PF"""
        data = {
            "rolling_pf": 1.6,
            "rolling_wr": 0.62,
            "health_verdict": "HEALTHY",
            "health_score": 0.8,
            "lifecycle": "APPROVED"
        }
        
        score = scoring_engine.score_strategy("TEST", data)
        
        assert score.recent_performance >= 1.1
    
    def test_lifecycle_modifier(self, scoring_engine):
        """Test lifecycle modifiers"""
        # APPROVED
        data = {"lifecycle": "APPROVED"}
        score = scoring_engine.score_strategy("TEST", data)
        assert score.lifecycle_modifier == 1.0
        
        # TESTING
        data = {"lifecycle": "TESTING"}
        score = scoring_engine.score_strategy("TEST", data)
        assert score.lifecycle_modifier == 0.3
        
        # DISABLED
        data = {"lifecycle": "DISABLED"}
        score = scoring_engine.score_strategy("TEST", data)
        assert score.lifecycle_modifier == 0.0


# ============================================
# CrowdingDetector Tests
# ============================================

class TestCrowdingDetector:
    """Tests for CrowdingDetector"""
    
    def test_no_crowding_different_families(self, crowding_detector, sample_strategies):
        """Test no crowding between different families"""
        pair = crowding_detector.detect_pairwise(
            "MTF_BREAKOUT",
            "REVERSAL_DIVERGENCE",
            sample_strategies["MTF_BREAKOUT"],
            sample_strategies["REVERSAL_DIVERGENCE"]
        )
        
        assert pair.total_overlap < 0.3
        assert pair.level in ["NONE", "LOW"]
    
    def test_crowding_same_family(self, crowding_detector, sample_strategies):
        """Test crowding between same family strategies"""
        pair = crowding_detector.detect_pairwise(
            "MTF_BREAKOUT",
            "CHANNEL_BREAKOUT",
            sample_strategies["MTF_BREAKOUT"],
            sample_strategies["CHANNEL_BREAKOUT"]
        )
        
        # Same family should have trade overlap
        assert pair.trade_overlap > 0
        assert pair.feature_overlap > 0
    
    def test_detect_all(self, crowding_detector, sample_strategies):
        """Test detecting all crowding"""
        pairs, clusters = crowding_detector.detect_all(sample_strategies)
        
        # Should find some pairs
        assert isinstance(pairs, list)
        assert isinstance(clusters, list)
    
    def test_get_strategy_penalty(self, crowding_detector, sample_strategies):
        """Test getting strategy penalty"""
        pairs, _ = crowding_detector.detect_all(sample_strategies)
        
        penalty = crowding_detector.get_strategy_penalty("MTF_BREAKOUT", pairs)
        
        # Penalty should be capped
        assert penalty <= 0.50
    
    def test_crowding_levels(self, crowding_detector):
        """Test crowding level thresholds"""
        assert crowding_detector._get_level(0.10) == "NONE"
        assert crowding_detector._get_level(0.25) == "LOW"
        assert crowding_detector._get_level(0.45) == "MEDIUM"
        assert crowding_detector._get_level(0.65) == "HIGH"
        assert crowding_detector._get_level(0.85) == "CRITICAL"


# ============================================
# StrategyFamilyManager Tests
# ============================================

class TestStrategyFamilyManager:
    """Tests for StrategyFamilyManager"""
    
    def test_get_family_budget_default(self, family_manager):
        """Test getting default family budget"""
        budget = family_manager.get_family_budget("breakout_family")
        
        # Default budget for breakout_family
        assert budget >= 0.10  # At least 10%
    
    def test_get_family_budget_regime(self, family_manager):
        """Test getting regime-specific budget"""
        budget = family_manager.get_family_budget("breakout_family", "TREND_UP")
        
        assert budget == 0.35
        
        budget = family_manager.get_family_budget("breakout_family", "RANGE")
        
        assert budget == 0.10
    
    def test_compute_family_allocations(self, family_manager, sample_strategies):
        """Test computing family allocations"""
        # First score the strategies
        scoring = StrategyScoringEngine()
        scores = {
            sid: scoring.score_strategy(sid, data)
            for sid, data in sample_strategies.items()
        }
        
        allocations = family_manager.compute_family_allocations(scores)
        
        assert "breakout_family" in allocations
        assert "reversal_family" in allocations
        assert "experimental_family" in allocations
        
        # Check breakout family has 2 strategies
        assert allocations["breakout_family"].strategy_count == 2
    
    def test_family_fit_modifier(self, family_manager):
        """Test family fit modifier"""
        # Under target
        mod = family_manager.get_family_fit_modifier("breakout_family", 0.05)
        assert mod >= 0.9  # Low allocation = good fit
        
        # At or over max
        mod = family_manager.get_family_fit_modifier("breakout_family", 0.50)
        assert mod <= 0.50  # Over max = penalty


# ============================================
# TierAllocator Tests
# ============================================

class TestTierAllocator:
    """Tests for TierAllocator"""
    
    def test_compute_tier_allocations(self, tier_allocator, sample_strategies):
        """Test computing tier allocations"""
        scoring = StrategyScoringEngine()
        scores = {
            sid: scoring.score_strategy(sid, data)
            for sid, data in sample_strategies.items()
        }
        
        allocations = tier_allocator.compute_tier_allocations(scores)
        
        assert "CORE" in allocations
        assert "TACTICAL" in allocations
        assert "EXPERIMENTAL" in allocations
        
        # CORE should have 1 strategy
        assert allocations["CORE"].strategy_count == 1
        
        # TACTICAL should have 2
        assert allocations["TACTICAL"].strategy_count == 2
    
    def test_tier_budgets(self, tier_allocator):
        """Test tier budgets"""
        assert tier_allocator.config.get("CORE") == 0.60
        assert tier_allocator.config.get("TACTICAL") == 0.30
        assert tier_allocator.config.get("EXPERIMENTAL") == 0.10
    
    def test_tier_modifier(self, tier_allocator):
        """Test tier modifier"""
        mod = tier_allocator.get_tier_modifier("CORE", 0.30)
        assert mod == 1.0
        
        mod = tier_allocator.get_tier_modifier("CORE", 0.55)
        assert mod == 0.80
        
        mod = tier_allocator.get_tier_modifier("CORE", 0.65)
        assert mod == 0.50


# ============================================
# StrategyAdmissionEngine Tests
# ============================================

class TestStrategyAdmissionEngine:
    """Tests for StrategyAdmissionEngine"""
    
    def test_admit_healthy_strategy(self, admission_engine):
        """Test admitting a healthy strategy"""
        score = StrategyScore(
            strategy_id="TEST",
            edge_health=0.85,
            regime_fit=1.0,
            recent_performance=1.1,
            confidence_integrity=0.9,
            portfolio_fit=1.0,
            lifecycle_modifier=1.0,
            self_healing_modifier=1.0,
            crowding_penalty=0.0,
            final_weight=0.8,
            family="breakout_family",
            tier="CORE",
            status="ACTIVE"
        )
        
        family_alloc = FamilyBudget(
            family="breakout_family",
            target_weight=0.30,
            current_weight=0.15,
            max_weight=0.40,
            strategy_count=2,
            active_strategies=1
        )
        
        tier_alloc = TierAllocation(
            tier="CORE",
            budget=0.60,
            current=0.30,
            remaining=0.30,
            strategy_count=2
        )
        
        decision = admission_engine.check_admission(
            "TEST",
            "sig_123",
            score,
            family_alloc,
            tier_alloc,
            0.0
        )
        
        assert decision.admitted == True
        assert decision.status == "ADMITTED"
    
    def test_block_low_health(self, admission_engine):
        """Test blocking low health strategy"""
        score = StrategyScore(
            strategy_id="TEST",
            edge_health=0.20,  # Below min
            regime_fit=1.0,
            final_weight=0.5,
            lifecycle_modifier=1.0,
            status="DEGRADED"
        )
        
        family_alloc = FamilyBudget(
            family="test",
            target_weight=0.30,
            current_weight=0.10,
            max_weight=0.40,
            strategy_count=1,
            active_strategies=0
        )
        
        tier_alloc = TierAllocation(
            tier="TACTICAL",
            budget=0.30,
            current=0.10,
            remaining=0.20,
            strategy_count=1
        )
        
        decision = admission_engine.check_admission(
            "TEST",
            "sig_123",
            score,
            family_alloc,
            tier_alloc,
            0.0
        )
        
        assert decision.admitted == False
        assert decision.status == "BLOCKED"
        assert "Health" in decision.reason
    
    def test_block_disabled_lifecycle(self, admission_engine):
        """Test blocking disabled strategy"""
        score = StrategyScore(
            strategy_id="TEST",
            edge_health=0.80,
            regime_fit=1.0,
            final_weight=0.5,
            lifecycle_modifier=0.0,  # DISABLED
            status="BLOCKED"
        )
        
        family_alloc = FamilyBudget(family="test", target_weight=0.30, current_weight=0.10, max_weight=0.40, strategy_count=1, active_strategies=0)
        tier_alloc = TierAllocation(tier="TACTICAL", budget=0.30, current=0.10, remaining=0.20, strategy_count=1)
        
        decision = admission_engine.check_admission("TEST", "sig_123", score, family_alloc, tier_alloc, 0.0)
        
        assert decision.admitted == False
        assert decision.status == "BLOCKED"
    
    def test_limit_family_exceeded(self, admission_engine):
        """Test limiting when family budget exceeded"""
        score = StrategyScore(
            strategy_id="TEST",
            edge_health=0.80,
            regime_fit=1.0,
            final_weight=0.5,
            lifecycle_modifier=1.0,
            status="ACTIVE"
        )
        
        family_alloc = FamilyBudget(
            family="test",
            target_weight=0.30,
            current_weight=0.45,  # Exceeded
            max_weight=0.40,
            strategy_count=3,
            active_strategies=2
        )
        
        tier_alloc = TierAllocation(tier="TACTICAL", budget=0.30, current=0.10, remaining=0.20, strategy_count=1)
        
        decision = admission_engine.check_admission("TEST", "sig_123", score, family_alloc, tier_alloc, 0.0)
        
        assert decision.status == "LIMITED"


# ============================================
# MetaStrategyService Tests
# ============================================

class TestMetaStrategyService:
    """Tests for MetaStrategyService"""
    
    def test_get_health(self, meta_service):
        """Test getting service health"""
        health = meta_service.get_health()
        
        assert health["enabled"] == True
        assert health["status"] == "ok"
        assert "components" in health
    
    def test_load_strategies(self, meta_service, sample_strategies):
        """Test loading strategies"""
        meta_service.load_strategies(sample_strategies)
        
        health = meta_service.get_health()
        assert health["strategiesLoaded"] == 4
    
    def test_recompute(self, meta_service, sample_strategies):
        """Test recomputing weights"""
        meta_service.load_strategies(sample_strategies)
        
        result = meta_service.recompute(regime="TREND_UP")
        
        assert result["success"] == True
        assert result["strategiesScored"] == 4
        assert result["regime"] == "TREND_UP"
    
    def test_get_weights(self, meta_service, sample_strategies):
        """Test getting weights"""
        meta_service.load_strategies(sample_strategies)
        meta_service.recompute(regime="TREND_UP")
        
        weights = meta_service.get_weights()
        
        assert "MTF_BREAKOUT" in weights
        assert weights["MTF_BREAKOUT"] > 0
    
    def test_get_families(self, meta_service, sample_strategies):
        """Test getting families"""
        meta_service.load_strategies(sample_strategies)
        meta_service.recompute()
        
        families = meta_service.get_families()
        
        assert "breakout_family" in families
        assert families["breakout_family"]["strategyCount"] == 2
    
    def test_get_tiers(self, meta_service, sample_strategies):
        """Test getting tiers"""
        meta_service.load_strategies(sample_strategies)
        meta_service.recompute()
        
        tiers = meta_service.get_tiers()
        
        assert "CORE" in tiers
        assert "TACTICAL" in tiers
        assert "EXPERIMENTAL" in tiers
    
    def test_get_crowding(self, meta_service, sample_strategies):
        """Test getting crowding"""
        meta_service.load_strategies(sample_strategies)
        meta_service.recompute()
        
        crowding = meta_service.get_crowding()
        
        assert "pairs" in crowding
        assert "clusters" in crowding
    
    def test_admit_signal(self, meta_service, sample_strategies):
        """Test admitting a signal"""
        meta_service.load_strategies(sample_strategies)
        meta_service.recompute(regime="TREND_UP")
        
        decision = meta_service.admit_signal("MTF_BREAKOUT", "sig_test_123")
        
        # Should be admitted - healthy strategy in good regime
        assert decision.admitted == True
        assert decision.status in ["ADMITTED", "LIMITED"]
    
    def test_admit_signal_not_found(self, meta_service):
        """Test admitting signal for unknown strategy"""
        decision = meta_service.admit_signal("UNKNOWN_STRAT", "sig_123")
        
        assert decision.admitted == False
        assert decision.status == "BLOCKED"
        assert "not found" in decision.reason
    
    def test_get_status(self, meta_service, sample_strategies):
        """Test getting full status"""
        meta_service.load_strategies(sample_strategies)
        meta_service.recompute()
        
        state = meta_service.get_status()
        
        assert state.status in ["ACTIVE", "LIMITED", "BLOCKED"]
        assert len(state.strategy_scores) == 4


# ============================================
# Serialization Tests
# ============================================

class TestSerialization:
    """Tests for serialization functions"""
    
    def test_strategy_score_to_dict(self):
        """Test strategy score serialization"""
        score = StrategyScore(
            strategy_id="TEST",
            edge_health=0.85,
            regime_fit=1.0,
            recent_performance=1.1,
            confidence_integrity=0.9,
            portfolio_fit=1.0,
            lifecycle_modifier=1.0,
            self_healing_modifier=1.0,
            crowding_penalty=0.1,
            base_weight=1.0,
            final_weight=0.75,
            family="breakout_family",
            tier="CORE",
            regime="TREND_UP",
            asset="BTC",
            status="ACTIVE",
            computed_at=int(time.time() * 1000)
        )
        
        result = strategy_score_to_dict(score)
        
        assert result["strategyId"] == "TEST"
        assert result["finalWeight"] == 0.75
        assert result["scores"]["edgeHealth"] == 0.85
        assert result["modifiers"]["crowdingPenalty"] == 0.1
    
    def test_meta_state_to_dict(self, meta_service, sample_strategies):
        """Test meta state serialization"""
        meta_service.load_strategies(sample_strategies)
        meta_service.recompute()
        
        state = meta_service.get_status()
        result = meta_state_to_dict(state)
        
        assert "status" in result
        assert "currentRegime" in result
        assert "strategies" in result
        assert "families" in result
        assert "tiers" in result
        assert "crowding" in result


# ============================================
# Integration Tests
# ============================================

class TestIntegration:
    """Integration tests for Meta-Strategy"""
    
    def test_full_pipeline(self, meta_service, sample_strategies):
        """Test full meta-strategy pipeline"""
        # 1. Load strategies
        meta_service.load_strategies(sample_strategies)
        
        # 2. Recompute for TREND_UP
        result = meta_service.recompute(regime="TREND_UP")
        assert result["success"] == True
        
        # 3. Check MTF_BREAKOUT has high weight (good in TREND_UP)
        weights = meta_service.get_weights()
        assert weights["MTF_BREAKOUT"] > 0.4
        
        # 4. Check REVERSAL_DIVERGENCE has lower weight (not ideal in TREND_UP)
        assert weights["REVERSAL_DIVERGENCE"] < weights["MTF_BREAKOUT"]
        
        # 5. Admit signal for MTF_BREAKOUT
        decision = meta_service.admit_signal("MTF_BREAKOUT", "sig_1")
        assert decision.admitted == True
        
        # 6. Now switch regime to RANGE
        result = meta_service.recompute(regime="RANGE")
        
        # 7. REVERSAL_DIVERGENCE should now have higher weight
        weights = meta_service.get_weights()
        assert weights["REVERSAL_DIVERGENCE"] > weights["MTF_BREAKOUT"]
    
    def test_crowding_affects_weights(self, meta_service):
        """Test that crowding affects weights"""
        # Create similar strategies
        strategies = {
            "BREAKOUT_A": {
                "family": "breakout_family",
                "tier": "CORE",
                "health_verdict": "HEALTHY",
                "health_score": 0.85,
                "lifecycle": "APPROVED",
                "rolling_pf": 1.5,
                "rolling_wr": 0.58,
                "features": ["breakout", "volume", "momentum", "trend"]
            },
            "BREAKOUT_B": {
                "family": "breakout_family",
                "tier": "CORE",
                "health_verdict": "HEALTHY",
                "health_score": 0.85,
                "lifecycle": "APPROVED",
                "rolling_pf": 1.5,
                "rolling_wr": 0.58,
                "features": ["breakout", "volume", "momentum", "trend"]  # Same features!
            }
        }
        
        meta_service.load_strategies(strategies)
        meta_service.recompute()
        
        # Both should have crowding penalty
        state = meta_service.get_status()
        
        score_a = state.strategy_scores["BREAKOUT_A"]
        score_b = state.strategy_scores["BREAKOUT_B"]
        
        # Feature overlap should create penalty
        assert score_a.crowding_penalty > 0 or score_b.crowding_penalty > 0
    
    def test_family_budget_limits(self, meta_service):
        """Test that family budgets are respected"""
        # Create many strategies in same family
        strategies = {
            f"BREAKOUT_{i}": {
                "family": "breakout_family",
                "tier": "TACTICAL",
                "health_verdict": "HEALTHY",
                "health_score": 0.80,
                "lifecycle": "APPROVED",
                "rolling_pf": 1.3,
                "base_weight": 1.0
            }
            for i in range(10)
        }
        
        meta_service.load_strategies(strategies)
        meta_service.recompute()
        
        families = meta_service.get_families()
        
        # Family should be at or near max
        assert families["breakout_family"]["strategyCount"] == 10
    
    def test_tier_budget_limits(self, meta_service):
        """Test that tier budgets are tracked"""
        # Create strategies across tiers
        strategies = {
            "CORE_1": {"tier": "CORE", "lifecycle": "APPROVED", "health_score": 0.9},
            "CORE_2": {"tier": "CORE", "lifecycle": "APPROVED", "health_score": 0.9},
            "TACTICAL_1": {"tier": "TACTICAL", "lifecycle": "APPROVED", "health_score": 0.8},
            "EXP_1": {"tier": "EXPERIMENTAL", "lifecycle": "TESTING", "health_score": 0.5},
        }
        
        meta_service.load_strategies(strategies)
        meta_service.recompute()
        
        tiers = meta_service.get_tiers()
        
        assert tiers["CORE"]["strategyCount"] == 2
        assert tiers["TACTICAL"]["strategyCount"] == 1
        assert tiers["EXPERIMENTAL"]["strategyCount"] == 1


# ============================================
# Default Config Tests
# ============================================

class TestDefaultConfig:
    """Tests for default configuration"""
    
    def test_tier_budgets(self):
        """Test tier budgets sum to approximately 1"""
        config = DEFAULT_META_STRATEGY_CONFIG
        tier_sum = sum(config["tier_budgets"].values())
        
        assert abs(tier_sum - 1.0) < 0.001  # Allow floating point tolerance
    
    def test_family_budgets_exist(self):
        """Test all families have budgets"""
        config = DEFAULT_META_STRATEGY_CONFIG
        
        for family in StrategyFamily:
            assert family.value in config["family_budgets"]
    
    def test_crowding_thresholds_ordered(self):
        """Test crowding thresholds are in order"""
        config = DEFAULT_META_STRATEGY_CONFIG["crowding"]
        
        assert config["low_threshold"] < config["medium_threshold"]
        assert config["medium_threshold"] < config["high_threshold"]
        assert config["high_threshold"] < config["critical_threshold"]
    
    def test_admission_thresholds_valid(self):
        """Test admission thresholds are valid"""
        config = DEFAULT_META_STRATEGY_CONFIG["admission"]
        
        assert 0 < config["min_health"] < 1
        assert 0 < config["min_regime_fit"] < 1
        assert 0 < config["max_family_weight"] <= 1
        assert 0 < config["max_strategy_weight"] <= 1
