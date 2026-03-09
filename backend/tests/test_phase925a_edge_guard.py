"""
Test Phase 9.25A: Edge Protection Layer
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')

from modules.edge_guard.service import (
    EdgeGuardService,
    EdgeDecayMonitor,
    OverfitDetector,
    RegimeDriftDetector,
    ConfidenceIntegrityMonitor,
    EdgeStatus,
    StrategyHealthStatus,
    OverfitLevel,
    DriftSeverity,
    decay_report_to_dict,
    overfit_report_to_dict,
    drift_report_to_dict,
    confidence_report_to_dict,
    status_to_dict
)


class TestEdgeDecayMonitor:
    """Test Edge Decay Monitor"""
    
    def setup_method(self):
        self.monitor = EdgeDecayMonitor()
    
    def test_analyze_strategy(self):
        """Test analyzing strategy decay"""
        report = self.monitor.analyze("MTF_BREAKOUT")
        
        assert report.strategy_id == "MTF_BREAKOUT"
        assert report.current_status in StrategyHealthStatus
        assert report.rolling_50 is not None
        assert report.rolling_100 is not None
        assert report.rolling_200 is not None
    
    def test_decay_rates(self):
        """Test decay rate calculation"""
        report = self.monitor.analyze("DOUBLE_BOTTOM")
        
        assert -1 <= report.pf_decay_rate <= 1
        assert -1 <= report.wr_decay_rate <= 1
        assert -1 <= report.sharpe_decay_rate <= 1
    
    def test_decay_trend(self):
        """Test decay trend determination"""
        report = self.monitor.analyze("CHANNEL_BREAKOUT")
        
        assert report.decay_trend in ["IMPROVING", "STABLE", "DECLINING", "CRITICAL"]
    
    def test_status_transitions(self):
        """Test status transitions"""
        # First analysis
        report1 = self.monitor.analyze("MTF_BREAKOUT")
        
        # Second analysis
        report2 = self.monitor.analyze("MTF_BREAKOUT")
        
        assert report2.previous_status == report1.current_status
    
    def test_rolling_metrics(self):
        """Test rolling metrics calculation"""
        report = self.monitor.analyze("MOMENTUM_CONTINUATION")
        
        for rolling in [report.rolling_50, report.rolling_100, report.rolling_200]:
            assert rolling.profit_factor > 0
            assert 0 <= rolling.win_rate <= 1
            assert rolling.trades > 0
    
    def test_set_baseline(self):
        """Test setting baseline metrics"""
        self.monitor.set_baseline("TEST_STRATEGY", {
            "pf": 2.5,
            "wr": 0.65,
            "sharpe": 2.0
        })
        
        assert "TEST_STRATEGY" in self.monitor._baseline_metrics


class TestOverfitDetector:
    """Test Overfit Detector"""
    
    def setup_method(self):
        self.detector = OverfitDetector()
    
    def test_analyze_strategy(self):
        """Test analyzing overfitting"""
        report = self.detector.analyze("MTF_BREAKOUT")
        
        assert report.strategy_id == "MTF_BREAKOUT"
        assert report.overfit_level in OverfitLevel
        assert 0 <= report.overfit_score <= 1
    
    def test_overfit_indicators(self):
        """Test overfit indicators"""
        report = self.detector.analyze("DOUBLE_TOP")
        
        assert 0 <= report.train_test_divergence <= 1
        assert 0 <= report.parameter_sensitivity <= 1
        assert 0 <= report.regime_concentration <= 1
        assert 0 <= report.asset_concentration <= 1
    
    def test_overfit_levels(self):
        """Test overfit level thresholds"""
        # Analyze multiple strategies
        for strategy in ["MTF_BREAKOUT", "DOUBLE_BOTTOM", "CHANNEL_BREAKOUT"]:
            report = self.detector.analyze(strategy)
            
            # Just verify level is valid based on score
            if report.overfit_score >= 0.5:
                assert report.overfit_level == OverfitLevel.HIGH
            elif report.overfit_score >= 0.3:
                assert report.overfit_level == OverfitLevel.MEDIUM
            else:
                assert report.overfit_level in [OverfitLevel.LOW, OverfitLevel.MEDIUM]


class TestRegimeDriftDetector:
    """Test Regime Drift Detector"""
    
    def setup_method(self):
        self.detector = RegimeDriftDetector()
    
    def test_analyze_drift(self):
        """Test drift analysis"""
        report = self.detector.analyze()
        
        assert report.drift_severity in DriftSeverity
        assert 0 <= report.drift_score <= 1
    
    def test_drift_indicators(self):
        """Test drift indicators"""
        report = self.detector.analyze()
        
        assert 0 <= report.atr_distribution_shift <= 1
        assert 0 <= report.trend_persistence_change <= 1
        assert 0 <= report.range_duration_change <= 1
    
    def test_risk_throttle(self):
        """Test risk throttle recommendation"""
        report = self.detector.analyze()
        
        assert 0 < report.risk_throttle <= 1.0
    
    def test_regime_distribution(self):
        """Test regime distribution tracking"""
        report = self.detector.analyze()
        
        assert len(report.current_regime_distribution) > 0
        assert len(report.baseline_regime_distribution) > 0
        
        # Should sum to ~1.0
        current_sum = sum(report.current_regime_distribution.values())
        assert 0.99 <= current_sum <= 1.01
    
    def test_set_baseline(self):
        """Test setting baseline regime"""
        self.detector.set_baseline({
            "TREND_UP": 0.35,
            "TREND_DOWN": 0.25,
            "RANGE": 0.20,
            "COMPRESSION": 0.12,
            "EXPANSION": 0.08
        })
        
        assert "TREND_UP" in self.detector._baseline_regime


class TestConfidenceIntegrityMonitor:
    """Test Confidence Integrity Monitor"""
    
    def setup_method(self):
        self.monitor = ConfidenceIntegrityMonitor()
    
    def test_analyze_calibration(self):
        """Test calibration analysis"""
        report = self.monitor.analyze()
        
        assert report.is_calibrated in [True, False]
        assert 0 <= report.calibration_score <= 1
    
    def test_confidence_buckets(self):
        """Test confidence vs actual buckets"""
        report = self.monitor.analyze()
        
        assert len(report.confidence_vs_actual) > 0
        
        for bucket_name, data in report.confidence_vs_actual.items():
            assert "predicted" in data
            assert "actual" in data
            assert "gap" in data
    
    def test_overconfidence_rate(self):
        """Test overconfidence rate"""
        report = self.monitor.analyze()
        
        assert 0 <= report.overconfidence_rate <= 1
        assert 0 <= report.underconfidence_rate <= 1
    
    def test_brier_score(self):
        """Test Brier score"""
        report = self.monitor.analyze()
        
        assert report.brier_score >= 0


class TestEdgeGuardService:
    """Test Edge Guard Service"""
    
    def setup_method(self):
        self.service = EdgeGuardService()
    
    def test_get_status(self):
        """Test getting overall status"""
        status = self.service.get_status()
        
        assert status.overall_status in EdgeStatus
        assert status.version == "9.25A"
    
    def test_status_components(self):
        """Test status component tracking"""
        status = self.service.get_status()
        
        assert status.decay_status in ["OK", "WARNING", "DEGRADED", "CRITICAL"]
        assert status.overfit_status in ["OK", "WARNING"]
        assert status.drift_status in ["OK", "WARNING"]
        assert status.confidence_status in ["OK", "WARNING"]
    
    def test_risk_level(self):
        """Test risk level determination"""
        status = self.service.get_status()
        
        assert status.risk_level in ["LOW", "NORMAL", "ELEVATED", "HIGH", "CRITICAL"]
        assert 0 < status.risk_throttle <= 1.0
    
    def test_run_full_check(self):
        """Test running full check"""
        strategies = ["MTF_BREAKOUT", "DOUBLE_BOTTOM"]
        results = self.service.run_full_check(strategies)
        
        assert "decay" in results
        assert "overfit" in results
        assert "drift" in results
        assert "confidence" in results
        assert "status" in results
        
        assert len(results["decay"]) == len(strategies)
        assert len(results["overfit"]) == len(strategies)
    
    def test_get_health(self):
        """Test health endpoint"""
        health = self.service.get_health()
        
        assert health["enabled"] is True
        assert health["status"] == "ok"
        assert "components" in health


class TestSerialization:
    """Test serialization functions"""
    
    def test_decay_report_serialization(self):
        """Test EdgeDecayReport serialization"""
        monitor = EdgeDecayMonitor()
        report = monitor.analyze("MTF_BREAKOUT")
        
        data = decay_report_to_dict(report)
        
        assert "strategyId" in data
        assert "currentStatus" in data
        assert "rolling50" in data
        assert "decayTrend" in data
    
    def test_overfit_report_serialization(self):
        """Test OverfitReport serialization"""
        detector = OverfitDetector()
        report = detector.analyze("MTF_BREAKOUT")
        
        data = overfit_report_to_dict(report)
        
        assert "strategyId" in data
        assert "overfitLevel" in data
        assert "overfitScore" in data
    
    def test_drift_report_serialization(self):
        """Test RegimeDriftReport serialization"""
        detector = RegimeDriftDetector()
        report = detector.analyze()
        
        data = drift_report_to_dict(report)
        
        assert "driftSeverity" in data
        assert "driftScore" in data
        assert "riskThrottle" in data
    
    def test_confidence_report_serialization(self):
        """Test ConfidenceIntegrityReport serialization"""
        monitor = ConfidenceIntegrityMonitor()
        report = monitor.analyze()
        
        data = confidence_report_to_dict(report)
        
        assert "isCalibrated" in data
        assert "calibrationScore" in data
        assert "overconfidenceRate" in data
    
    def test_status_serialization(self):
        """Test EdgeProtectionStatus serialization"""
        service = EdgeGuardService()
        status = service.get_status()
        
        data = status_to_dict(status)
        
        assert "overallStatus" in data
        assert "riskLevel" in data
        assert "riskThrottle" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
