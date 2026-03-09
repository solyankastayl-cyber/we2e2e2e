"""
Test Phase 9.25B: Strategy Governance Layer
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')

from modules.strategy_governance.service import (
    StrategyGovernanceService,
    StrategyLifecycleManager,
    StrategyFamilyManager,
    StrategyBudgetManager,
    StrategyLifecycle,
    StrategyFamily,
    strategy_record_to_dict,
    budget_to_dict,
    family_to_dict,
    promotion_result_to_dict
)


class TestStrategyLifecycleManager:
    """Test Strategy Lifecycle Manager"""
    
    def setup_method(self):
        self.manager = StrategyLifecycleManager()
    
    def test_get_strategy(self):
        """Test getting strategy"""
        strategy = self.manager.get_strategy("MTF_BREAKOUT")
        
        assert strategy is not None
        assert strategy.strategy_id == "MTF_BREAKOUT"
        assert strategy.lifecycle == StrategyLifecycle.APPROVED
    
    def test_get_all_strategies(self):
        """Test getting all strategies"""
        strategies = self.manager.get_all_strategies()
        
        assert len(strategies) == 11  # Default strategies
        assert "MTF_BREAKOUT" in strategies
        assert "DOUBLE_BOTTOM" in strategies
    
    def test_get_strategies_by_lifecycle(self):
        """Test filtering by lifecycle"""
        approved = self.manager.get_strategies_by_lifecycle(StrategyLifecycle.APPROVED)
        limited = self.manager.get_strategies_by_lifecycle(StrategyLifecycle.LIMITED)
        deprecated = self.manager.get_strategies_by_lifecycle(StrategyLifecycle.DEPRECATED)
        
        assert len(approved) == 5
        assert len(limited) == 4
        assert len(deprecated) == 2
    
    def test_get_strategies_by_family(self):
        """Test filtering by family"""
        breakout = self.manager.get_strategies_by_family(StrategyFamily.BREAKOUT)
        reversal = self.manager.get_strategies_by_family(StrategyFamily.REVERSAL)
        
        assert len(breakout) == 2
        assert len(reversal) == 2
    
    def test_promote_valid_transition(self):
        """Test valid promotion"""
        # Get a LIMITED strategy
        strategy = self.manager.get_strategy("HEAD_SHOULDERS")
        assert strategy.lifecycle == StrategyLifecycle.LIMITED
        
        # Promote to APPROVED (with force since it may not meet criteria)
        result = self.manager.promote("HEAD_SHOULDERS", StrategyLifecycle.APPROVED, force=True)
        
        assert result.success is True
        assert result.to_status == StrategyLifecycle.APPROVED
        
        # Verify change
        updated = self.manager.get_strategy("HEAD_SHOULDERS")
        assert updated.lifecycle == StrategyLifecycle.APPROVED
    
    def test_promote_invalid_transition(self):
        """Test invalid promotion"""
        # Try invalid transition (APPROVED -> TESTING)
        result = self.manager.promote("MTF_BREAKOUT", StrategyLifecycle.TESTING)
        
        assert result.success is False
        assert "Invalid transition" in result.reason
    
    def test_demote(self):
        """Test demotion"""
        result = self.manager.demote(
            "MOMENTUM_CONTINUATION",
            StrategyLifecycle.WATCH,
            reason="Performance drop"
        )
        
        assert result.success is True
        assert result.to_status == StrategyLifecycle.WATCH
    
    def test_status_history(self):
        """Test status history tracking"""
        # Make a promotion
        self.manager.promote("HARMONIC_ABCD", StrategyLifecycle.APPROVED, force=True)
        
        strategy = self.manager.get_strategy("HARMONIC_ABCD")
        assert len(strategy.status_history) > 0
    
    def test_promotion_history(self):
        """Test promotion history"""
        self.manager.promote("WEDGE_RISING", StrategyLifecycle.APPROVED, force=True)
        
        history = self.manager.get_promotion_history()
        assert len(history) > 0


class TestStrategyFamilyManager:
    """Test Strategy Family Manager"""
    
    def setup_method(self):
        self.manager = StrategyFamilyManager()
    
    def test_get_family(self):
        """Test getting family"""
        family = self.manager.get_family(StrategyFamily.BREAKOUT)
        
        assert family is not None
        assert family.family == StrategyFamily.BREAKOUT
        assert len(family.strategies) > 0
    
    def test_get_all_families(self):
        """Test getting all families"""
        families = self.manager.get_all_families()
        
        assert len(families) == len(StrategyFamily)
    
    def test_set_family_allocation(self):
        """Test setting allocation"""
        self.manager.set_family_allocation(StrategyFamily.BREAKOUT, 0.40)
        
        family = self.manager.get_family(StrategyFamily.BREAKOUT)
        assert family.allocation_pct == 0.40
    
    def test_disable_family(self):
        """Test disabling family"""
        result = self.manager.disable_family(StrategyFamily.EXPERIMENTAL)
        
        assert result is True
        
        family = self.manager.get_family(StrategyFamily.EXPERIMENTAL)
        assert family.is_active is False
    
    def test_enable_family(self):
        """Test enabling family"""
        self.manager.disable_family(StrategyFamily.HARMONIC)
        result = self.manager.enable_family(StrategyFamily.HARMONIC)
        
        assert result is True
        
        family = self.manager.get_family(StrategyFamily.HARMONIC)
        assert family.is_active is True
    
    def test_get_family_exposure(self):
        """Test getting exposure"""
        exposure = self.manager.get_family_exposure()
        
        assert len(exposure) > 0
        for family_name, data in exposure.items():
            assert "target" in data
            assert "current" in data
            assert "strategies" in data


class TestStrategyBudgetManager:
    """Test Strategy Budget Manager"""
    
    def setup_method(self):
        self.manager = StrategyBudgetManager()
    
    def test_get_budget(self):
        """Test getting budget"""
        budget = self.manager.get_budget("MTF_BREAKOUT")
        
        assert budget is not None
        assert budget.strategy_id == "MTF_BREAKOUT"
        assert budget.risk_budget > 0
    
    def test_set_budget(self):
        """Test setting budget"""
        result = self.manager.set_budget(
            "MTF_BREAKOUT",
            risk_budget=0.025,
            capital_budget=0.15
        )
        
        assert result is True
        
        budget = self.manager.get_budget("MTF_BREAKOUT")
        assert budget.risk_budget == 0.025
        assert budget.capital_budget == 0.15
    
    def test_set_allowed_assets(self):
        """Test setting allowed assets"""
        result = self.manager.set_allowed_assets("DOUBLE_BOTTOM", ["BTC", "ETH"])
        
        assert result is True
        
        budget = self.manager.get_budget("DOUBLE_BOTTOM")
        assert budget.allowed_assets == ["BTC", "ETH"]
    
    def test_set_allowed_regimes(self):
        """Test setting allowed regimes"""
        result = self.manager.set_allowed_regimes("DOUBLE_TOP", ["TREND_DOWN", "RANGE"])
        
        assert result is True
        
        budget = self.manager.get_budget("DOUBLE_TOP")
        assert budget.allowed_regimes == ["TREND_DOWN", "RANGE"]
    
    def test_get_all_budgets(self):
        """Test getting all budgets"""
        budgets = self.manager.get_all_budgets()
        
        assert len(budgets) == 11
    
    def test_get_total_risk_allocation(self):
        """Test total risk calculation"""
        total = self.manager.get_total_risk_allocation()
        
        assert total > 0
        assert total < 1.0


class TestStrategyGovernanceService:
    """Test Strategy Governance Service"""
    
    def setup_method(self):
        self.service = StrategyGovernanceService()
    
    def test_get_governance_status(self):
        """Test governance status"""
        status = self.service.get_governance_status()
        
        assert "totalStrategies" in status
        assert "byLifecycle" in status
        assert "byFamily" in status
        assert "totalRiskAllocation" in status
        assert status["totalStrategies"] == 11
    
    def test_get_health(self):
        """Test health endpoint"""
        health = self.service.get_health()
        
        assert health["enabled"] is True
        assert health["status"] == "ok"
        assert "components" in health


class TestSerialization:
    """Test serialization functions"""
    
    def test_strategy_record_serialization(self):
        """Test StrategyRecord serialization"""
        manager = StrategyLifecycleManager()
        record = manager.get_strategy("MTF_BREAKOUT")
        
        data = strategy_record_to_dict(record)
        
        assert "strategyId" in data
        assert "lifecycle" in data
        assert "metrics" in data
        assert "budget" in data
    
    def test_budget_serialization(self):
        """Test Budget serialization"""
        manager = StrategyBudgetManager()
        budget = manager.get_budget("MTF_BREAKOUT")
        
        data = budget_to_dict(budget)
        
        assert "strategyId" in data
        assert "riskBudget" in data
        assert "capitalBudget" in data
    
    def test_family_serialization(self):
        """Test Family serialization"""
        manager = StrategyFamilyManager()
        family = manager.get_family(StrategyFamily.BREAKOUT)
        
        data = family_to_dict(family)
        
        assert "family" in data
        assert "strategies" in data
        assert "allocationPct" in data
    
    def test_promotion_result_serialization(self):
        """Test PromotionResult serialization"""
        manager = StrategyLifecycleManager()
        result = manager.promote("WEDGE_FALLING", StrategyLifecycle.APPROVED, force=True)
        
        data = promotion_result_to_dict(result)
        
        assert "strategyId" in data
        assert "success" in data
        assert "fromStatus" in data
        assert "toStatus" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
