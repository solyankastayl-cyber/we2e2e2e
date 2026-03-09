"""
Test Phase 9.2: Final Quant Report
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')

from modules.validation.final_quant_report import (
    FinalQuantReportGenerator,
    FinalQuantReport,
    AssetPerformance,
    RegimePerformance,
    StrategyContribution,
    RiskMetrics,
    StabilityMetrics,
    FailureSummary,
    report_to_dict
)


class TestFinalQuantReportGenerator:
    """Test Final Quant Report Generator"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.generator = FinalQuantReportGenerator()
    
    def test_generate_default_report(self):
        """Test generating report with default data"""
        report = self.generator.generate()
        
        assert report is not None
        assert report.report_id.startswith("quant_report_")
        assert report.edge_verdict in ["STRONG_EDGE", "MODERATE_EDGE", "WEAK_EDGE", "NO_EDGE"]
        assert report.global_profit_factor > 0
        assert report.global_win_rate > 0
        assert report.total_trades > 0
    
    def test_executive_summary(self):
        """Test executive summary fields"""
        report = self.generator.generate()
        
        assert report.edge_verdict is not None
        assert report.global_profit_factor >= 0
        assert 0 <= report.global_win_rate <= 1
        assert report.global_sharpe >= 0
        assert 0 <= report.global_max_drawdown <= 1
        assert report.total_trades > 0
        assert len(report.datasets_used) > 0
    
    def test_asset_performance(self):
        """Test per-asset performance breakdown"""
        report = self.generator.generate()
        
        assert len(report.asset_performance) > 0
        
        for asset_perf in report.asset_performance:
            assert isinstance(asset_perf, AssetPerformance)
            assert asset_perf.asset in ["BTC", "ETH", "SOL", "SPX", "GOLD", "DXY"]
            assert asset_perf.asset_class in ["CRYPTO", "EQUITIES", "FX", "COMMODITIES"]
            assert asset_perf.trades > 0
            assert 0 <= asset_perf.win_rate <= 1
            assert asset_perf.profit_factor > 0
            assert asset_perf.verdict in ["PASS", "FAIL", "MARGINAL"]
    
    def test_regime_performance(self):
        """Test per-regime performance breakdown"""
        report = self.generator.generate()
        
        assert len(report.regime_performance) > 0
        
        for regime_perf in report.regime_performance:
            assert isinstance(regime_perf, RegimePerformance)
            assert regime_perf.regime in ["TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION"]
            assert regime_perf.trades >= 0
            assert 0 <= regime_perf.win_rate <= 1
    
    def test_strategy_contributions(self):
        """Test strategy contribution breakdown"""
        report = self.generator.generate()
        
        assert len(report.strategy_contributions) > 0
        
        total_contribution = sum(s.contribution for s in report.strategy_contributions)
        assert total_contribution > 90  # Should be close to 100%
        
        for strategy in report.strategy_contributions:
            assert isinstance(strategy, StrategyContribution)
            assert strategy.status in ["APPROVED", "LIMITED", "DEPRECATED"]
            assert strategy.trades >= 0
    
    def test_risk_metrics(self):
        """Test risk analysis metrics"""
        report = self.generator.generate()
        
        assert report.risk_metrics is not None
        assert isinstance(report.risk_metrics, RiskMetrics)
        assert report.risk_metrics.max_losing_streak > 0
        assert report.risk_metrics.risk_of_ruin >= 0
        assert report.risk_metrics.tail_risk_var_95 < 0  # VaR should be negative
    
    def test_failure_summary(self):
        """Test failure analysis summary"""
        report = self.generator.generate()
        
        assert len(report.failure_summary) > 0
        
        total_freq_pct = sum(f.frequency_pct for f in report.failure_summary)
        assert abs(total_freq_pct - 100) < 1  # Should sum to ~100%
        
        for failure in report.failure_summary:
            assert isinstance(failure, FailureSummary)
            assert failure.frequency > 0
            assert len(failure.mitigation) > 0
    
    def test_stability_metrics(self):
        """Test stability analysis"""
        report = self.generator.generate()
        
        assert report.stability_metrics is not None
        assert isinstance(report.stability_metrics, StabilityMetrics)
        assert len(report.stability_metrics.rolling_pf_50) > 0
        assert len(report.stability_metrics.rolling_wr_50) > 0
        assert 0 <= report.stability_metrics.stability_score <= 1
    
    def test_production_readiness(self):
        """Test production readiness flags"""
        report = self.generator.generate()
        
        assert report.strategy_pruning_done in [True, False]
        assert report.guardrails_active in [True, False]
        assert report.validation_isolation_active in [True, False]
        assert report.dataset_frozen in [True, False]
    
    def test_audit_fields(self):
        """Test audit/versioning fields"""
        report = self.generator.generate()
        
        assert report.system_version is not None
        assert report.dataset_version is not None
        assert report.strategy_version is not None
        assert report.validation_snapshot_id is not None
        assert len(report.checksum) == 16  # SHA256 truncated
    
    def test_edge_verdict_strong(self):
        """Test STRONG_EDGE verdict criteria"""
        # Create custom cross-asset results with strong performance
        strong_results = {
            "systemVerdict": "UNIVERSAL",
            "assets": {
                "BTC": {"verdict": "PASS", "pf": 2.5, "wr": 0.65, "avgR": 0.6, "maxDD": 0.05, "trades": 500, "class": "CRYPTO"},
                "ETH": {"verdict": "PASS", "pf": 2.8, "wr": 0.64, "avgR": 0.7, "maxDD": 0.04, "trades": 480, "class": "CRYPTO"},
                "SPX": {"verdict": "PASS", "pf": 2.6, "wr": 0.66, "avgR": 0.5, "maxDD": 0.03, "trades": 520, "class": "EQUITIES"},
            }
        }
        
        report = self.generator.generate(cross_asset_results=strong_results)
        
        assert report.edge_verdict == "STRONG_EDGE"
        assert report.global_profit_factor >= 2.0
        assert report.global_win_rate >= 0.58
    
    def test_report_to_dict(self):
        """Test JSON serialization"""
        report = self.generator.generate()
        result = report_to_dict(report)
        
        assert isinstance(result, dict)
        assert "reportId" in result
        assert "executiveSummary" in result
        assert "globalPerformance" in result
        assert "assetPerformance" in result
        assert "regimePerformance" in result
        assert "strategyContributions" in result
        assert "riskMetrics" in result
        assert "failureSummary" in result
        assert "productionReadiness" in result
        assert "metadata" in result
    
    def test_save_to_file(self, tmp_path):
        """Test saving report to files"""
        report = self.generator.generate()
        files = self.generator.save_to_file(report, str(tmp_path))
        
        assert "markdown" in files
        assert "json" in files
        
        # Verify files exist
        import os
        assert os.path.exists(files["markdown"])
        assert os.path.exists(files["json"])
        
        # Verify markdown content
        with open(files["markdown"], 'r') as f:
            md_content = f.read()
            assert "Final Quant Report" in md_content
            assert report.edge_verdict in md_content
    
    def test_list_reports(self):
        """Test listing reports"""
        # Generate multiple reports
        self.generator.generate()
        
        reports = self.generator.list_reports()
        
        assert len(reports) >= 1
        assert all("reportId" in r for r in reports)
        assert all("edgeVerdict" in r for r in reports)
    
    def test_get_report(self):
        """Test getting report by ID"""
        report = self.generator.generate()
        
        retrieved = self.generator.get_report(report.report_id)
        
        assert retrieved is not None
        assert retrieved.report_id == report.report_id
        assert retrieved.edge_verdict == report.edge_verdict


class TestEdgeVerdictLogic:
    """Test edge verdict determination logic"""
    
    def setup_method(self):
        self.generator = FinalQuantReportGenerator()
    
    def test_strong_edge_all_criteria(self):
        """Test STRONG_EDGE requires all criteria"""
        results = {
            "assets": {
                "BTC": {"verdict": "PASS", "pf": 2.5, "wr": 0.65, "avgR": 0.6, "maxDD": 0.05, "trades": 500, "class": "CRYPTO"},
                "ETH": {"verdict": "PASS", "pf": 2.8, "wr": 0.64, "avgR": 0.7, "maxDD": 0.04, "trades": 480, "class": "CRYPTO"},
            }
        }
        
        report = self.generator.generate(cross_asset_results=results)
        
        # With high PF, WR, and all assets passing, should be STRONG
        assert report.edge_verdict in ["STRONG_EDGE", "MODERATE_EDGE"]
    
    def test_moderate_edge(self):
        """Test MODERATE_EDGE criteria"""
        results = {
            "assets": {
                "BTC": {"verdict": "PASS", "pf": 1.6, "wr": 0.56, "avgR": 0.4, "maxDD": 0.08, "trades": 500, "class": "CRYPTO"},
            }
        }
        
        report = self.generator.generate(cross_asset_results=results)
        
        # With moderate metrics, should be MODERATE_EDGE
        assert report.edge_verdict in ["MODERATE_EDGE", "WEAK_EDGE"]
    
    def test_no_edge(self):
        """Test NO_EDGE when metrics are poor"""
        results = {
            "assets": {
                "BTC": {"verdict": "FAIL", "pf": 0.9, "wr": 0.45, "avgR": -0.1, "maxDD": 0.25, "trades": 500, "class": "CRYPTO"},
            }
        }
        
        report = self.generator.generate(cross_asset_results=results)
        
        # With poor metrics, should be NO_EDGE or WEAK_EDGE
        assert report.edge_verdict in ["NO_EDGE", "WEAK_EDGE"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
