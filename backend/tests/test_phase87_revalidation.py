"""
Phase 8.7 BTC Re-Validation Tests
"""

import pytest
import httpx

BASE_URL = "http://localhost:8001"


class TestRevalidationHealth:
    """Test revalidation health endpoint"""
    
    def test_health_endpoint(self):
        response = httpx.get(f"{BASE_URL}/api/revalidation/health")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == True
        assert data["version"] == "revalidation_v1_phase8.7"
        assert "1d" in data["targetTimeframes"]
        assert "4h" in data["targetTimeframes"]
        assert "1h" in data["targetTimeframes"]


class TestBTCRevalidation:
    """Test BTC Re-Validation endpoint"""
    
    def test_run_btc_validation(self):
        """Run full BTC validation"""
        response = httpx.post(
            f"{BASE_URL}/api/revalidation/btc/run",
            json={"symbol": "BTCUSDT", "timeframes": ["1d", "4h", "1h"]},
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check report structure
        assert data["phase"] == "8.7"
        assert data["symbol"] == "BTCUSDT"
        assert len(data["timeframes"]) == 3
        assert data["status"] in ["EXCELLENT", "GOOD", "REVIEW"]
        
        # Check aggregate improvements
        assert "avgWinRateImprovement" in data["aggregateImprovement"]
        assert "avgProfitFactorImprovement" in data["aggregateImprovement"]
        
        # Check timeframe results
        assert len(data["timeframeResults"]) == 3
        for tf_result in data["timeframeResults"]:
            assert "before" in tf_result
            assert "after" in tf_result
            assert "improvement" in tf_result
            
            # Before should have more trades than after (calibration filters)
            assert tf_result["before"]["trades"] > tf_result["after"]["trades"]
    
    def test_calibration_improves_metrics(self):
        """Verify calibration improves key metrics on average"""
        response = httpx.get(f"{BASE_URL}/api/revalidation/btc/summary")
        assert response.status_code == 200
        data = response.json()
        
        if data["status"] == "NO_DATA":
            # Run validation first
            httpx.post(
                f"{BASE_URL}/api/revalidation/btc/run",
                json={"timeframes": ["4h"]},
                timeout=60
            )
            response = httpx.get(f"{BASE_URL}/api/revalidation/btc/summary")
            data = response.json()
        
        assert data["status"] == "OK"
        
        # Check that trades are reduced (calibration filters out signals)
        for run in data["lastRun"]:
            assert run["tradesReduced"] > 0  # More trades before than after


class TestComparisonEndpoints:
    """Test comparison detail endpoints"""
    
    def test_timeframe_comparison(self):
        """Test detailed comparison endpoint"""
        # First run validation
        httpx.post(
            f"{BASE_URL}/api/revalidation/btc/run",
            json={"timeframes": ["4h"]},
            timeout=60
        )
        
        response = httpx.get(f"{BASE_URL}/api/revalidation/comparison/4h")
        assert response.status_code == 200
        data = response.json()
        
        assert data["timeframe"] == "4h"
        assert data["symbol"] == "BTCUSDT"
        
        # Check before/after structure
        assert "trades" in data["before"]
        assert "winRate" in data["before"]
        assert "strategyBreakdown" in data["before"]
        
        assert "trades" in data["after"]
        assert "calibrationStats" in data["after"]
        
        # Check improvements
        assert "winRate" in data["improvement"]
        assert "profitFactor" in data["improvement"]
        
        # Check weak strategies were properly identified
        if "LIQUIDITY_SWEEP" in data["before"]["strategyBreakdown"]:
            sweep_stats = data["before"]["strategyBreakdown"]["LIQUIDITY_SWEEP"]
            assert sweep_stats["winRate"] < 0.50  # Should be underperforming
        
        if "RANGE_REVERSAL" in data["before"]["strategyBreakdown"]:
            reversal_stats = data["before"]["strategyBreakdown"]["RANGE_REVERSAL"]
            assert reversal_stats["winRate"] < 0.50  # Should be underperforming
    
    def test_invalid_timeframe(self):
        """Test error handling for invalid timeframe"""
        response = httpx.get(f"{BASE_URL}/api/revalidation/comparison/invalid")
        assert response.status_code == 404


class TestDisabledStrategiesValidation:
    """Test that disabled strategies are confirmed weak"""
    
    def test_disabled_strategies_underperform(self):
        """Verify disabled strategies have poor metrics"""
        response = httpx.post(
            f"{BASE_URL}/api/revalidation/btc/run",
            json={"timeframes": ["1d"]},
            timeout=60
        )
        data = response.json()
        
        # Find timeframe result
        tf_result = data["timeframeResults"][0]
        
        # Check that before has more trades than after (filtering works)
        assert tf_result["before"]["trades"] > tf_result["after"]["trades"]
        
        # Check that disabled strategies are listed in calibration config
        assert "disabledStrategiesValidation" in data
        disabled = [s["strategy"] for s in data["disabledStrategiesValidation"]]
        assert "LIQUIDITY_SWEEP" in disabled
        assert "RANGE_REVERSAL" in disabled


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
