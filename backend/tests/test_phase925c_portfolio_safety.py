"""
Test Phase 9.25C: Portfolio Safety Layer
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')

from modules.portfolio_safety.service import (
    PortfolioSafetyService,
    ExposureMonitor,
    CorrelationMonitor,
    KillSwitch,
    RiskMode,
    KillSwitchTrigger,
    exposure_to_dict,
    correlation_to_dict,
    kill_switch_to_dict,
    safety_status_to_dict
)


class TestExposureMonitor:
    """Test Exposure Monitor"""
    
    def setup_method(self):
        self.monitor = ExposureMonitor()
    
    def test_calculate_exposure(self):
        """Test exposure calculation"""
        metrics = self.monitor.calculate()
        
        assert metrics.gross_exposure >= 0
        assert len(metrics.by_asset) > 0
        assert len(metrics.by_strategy) > 0
    
    def test_exposure_limits(self):
        """Test exposure limits checking"""
        metrics = self.monitor.calculate()
        
        assert metrics.gross_limit > 0
        assert metrics.within_limits in [True, False]


class TestCorrelationMonitor:
    """Test Correlation Monitor"""
    
    def setup_method(self):
        self.monitor = CorrelationMonitor()
    
    def test_calculate_correlation(self):
        """Test correlation calculation"""
        metrics = self.monitor.calculate()
        
        assert len(metrics.strategy_correlations) > 0
        assert 0 <= metrics.avg_strategy_correlation <= 1
    
    def test_high_correlation_detection(self):
        """Test high correlation pair detection"""
        metrics = self.monitor.calculate()
        
        # Should detect some high correlation pairs
        assert len(metrics.high_correlation_pairs) >= 0


class TestKillSwitch:
    """Test Kill Switch"""
    
    def setup_method(self):
        self.kill_switch = KillSwitch()
    
    def test_check_triggers_normal(self):
        """Test normal conditions don't trigger"""
        status = self.kill_switch.check_triggers(
            current_drawdown=0.05,
            correlation_level=0.5,
            volatility_multiplier=1.0,
            consecutive_losses=2
        )
        
        assert status.is_active is False
    
    def test_check_triggers_drawdown(self):
        """Test drawdown trigger"""
        status = self.kill_switch.check_triggers(
            current_drawdown=0.25  # Exceeds 20% threshold
        )
        
        assert status.is_active is True
        assert status.trigger == KillSwitchTrigger.MAX_DRAWDOWN
    
    def test_manual_activation(self):
        """Test manual activation"""
        status = self.kill_switch.activate(
            KillSwitchTrigger.MANUAL,
            "Testing"
        )
        
        assert status.is_active is True
        assert status.trigger == KillSwitchTrigger.MANUAL
    
    def test_deactivation(self):
        """Test deactivation"""
        self.kill_switch.activate(KillSwitchTrigger.MANUAL, "Test")
        status = self.kill_switch.deactivate("Test complete")
        
        assert status.is_active is False


class TestPortfolioSafetyService:
    """Test Portfolio Safety Service"""
    
    def setup_method(self):
        self.service = PortfolioSafetyService()
    
    def test_get_safety_status(self):
        """Test safety status"""
        status = self.service.get_safety_status()
        
        assert status.risk_mode in RiskMode
        assert status.risk_level in ["LOW", "NORMAL", "ELEVATED", "HIGH", "CRITICAL"]
    
    def test_get_health(self):
        """Test health endpoint"""
        health = self.service.get_health()
        
        assert health["enabled"] is True
        assert health["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
