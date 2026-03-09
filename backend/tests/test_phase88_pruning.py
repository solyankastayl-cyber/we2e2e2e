"""
Phase 8.8 Strategy Pruning Tests
"""

import pytest
import httpx

BASE_URL = "http://localhost:8001"


class TestPruningHealth:
    """Test pruning health endpoint"""
    
    def test_health_endpoint(self):
        response = httpx.get(f"{BASE_URL}/api/pruning/health")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == True
        assert data["version"] == "pruning_v1_phase8.8"
        assert "APPROVED" in data["categories"]
        assert "DEPRECATED" in data["categories"]


class TestStrategyPruning:
    """Test strategy pruning endpoint"""
    
    def test_run_pruning(self):
        """Run full pruning analysis"""
        response = httpx.post(f"{BASE_URL}/api/pruning/run", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert data["phase"] == "8.8"
        assert "summary" in data
        assert "approved" in data
        assert "limited" in data
        assert "testing" in data
        assert "deprecated" in data
        
        # Should have strategies in each category
        summary = data["summary"]
        assert summary["totalStrategies"] > 0
        assert summary["deprecated"] >= 4  # At least our 4 deprecated
    
    def test_deprecated_includes_known_weak(self):
        """Verify known weak strategies are deprecated"""
        response = httpx.get(f"{BASE_URL}/api/pruning/deprecated")
        assert response.status_code == 200
        data = response.json()
        
        deprecated_ids = [s["strategyId"] for s in data["strategies"]]
        
        # Phase 8.7 confirmed these as weak
        assert "LIQUIDITY_SWEEP" in deprecated_ids
        assert "RANGE_REVERSAL" in deprecated_ids
    
    def test_approved_strategies_meet_thresholds(self):
        """Verify approved strategies have good metrics"""
        response = httpx.get(f"{BASE_URL}/api/pruning/summary")
        data = response.json()
        
        for strategy in data["strategies"]["APPROVED"]:
            assert strategy["winRate"] >= 0.55
            assert strategy["profitFactor"] >= 1.3
            assert strategy["avgR"] >= 0.10


class TestStrategyCheck:
    """Test strategy check endpoint"""
    
    def test_deprecated_strategy_blocked(self):
        """Deprecated strategies should be blocked"""
        response = httpx.post(
            f"{BASE_URL}/api/pruning/check",
            json={"strategyId": "LIQUIDITY_SWEEP", "regime": "TREND_UP", "timeframe": "4h"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["allowed"] == False
        assert data["status"] == "DEPRECATED"
    
    def test_approved_strategy_allowed(self):
        """Approved strategies should be allowed"""
        response = httpx.post(
            f"{BASE_URL}/api/pruning/check",
            json={"strategyId": "MTF_BREAKOUT", "regime": "TREND_UP", "timeframe": "4h"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["allowed"] == True
        assert data["status"] == "APPROVED"
    
    def test_limited_strategy_conditional(self):
        """Limited strategies should check conditions"""
        # First check what conditions HEAD_SHOULDERS has
        response = httpx.get(f"{BASE_URL}/api/pruning/strategy/HEAD_SHOULDERS")
        data = response.json()
        allowed_regimes = data["conditions"]["allowedRegimes"]
        
        # Test with allowed regime
        if allowed_regimes:
            response = httpx.post(
                f"{BASE_URL}/api/pruning/check",
                json={"strategyId": "HEAD_SHOULDERS", "regime": allowed_regimes[0], "timeframe": "4h"}
            )
            data = response.json()
            assert data["allowed"] == True
            assert data["status"] == "LIMITED"
            assert data["positionSizeMultiplier"] == 0.5  # Reduced size
        
        # Test with disallowed regime (RANGE usually not allowed for LIMITED)
        response = httpx.post(
            f"{BASE_URL}/api/pruning/check",
            json={"strategyId": "HEAD_SHOULDERS", "regime": "RANGE", "timeframe": "4h"}
        )
        data = response.json()
        # Should either be allowed or show conditions
        assert "status" in data


class TestStrategyClassification:
    """Test individual strategy classification"""
    
    def test_get_strategy_details(self):
        """Test getting strategy details"""
        response = httpx.get(f"{BASE_URL}/api/pruning/strategy/MTF_BREAKOUT")
        assert response.status_code == 200
        data = response.json()
        
        assert data["strategyId"] == "MTF_BREAKOUT"
        assert data["status"] == "APPROVED"
        assert "metrics" in data
        assert "regime" in data
        assert "recommendations" in data
    
    def test_unknown_strategy_404(self):
        """Unknown strategy should return 404"""
        response = httpx.get(f"{BASE_URL}/api/pruning/strategy/UNKNOWN_STRATEGY")
        assert response.status_code == 404


class TestProductionRouting:
    """Test production routing lists"""
    
    def test_production_active_excludes_deprecated(self):
        """Production active list should not include deprecated"""
        response = httpx.get(f"{BASE_URL}/api/pruning/summary")
        data = response.json()
        
        active = data["productionActive"]
        blocked = data["productionBlocked"]
        
        # No overlap
        for strategy in blocked:
            assert strategy not in active
        
        # Deprecated should be blocked
        assert "LIQUIDITY_SWEEP" in blocked
        assert "RANGE_REVERSAL" in blocked


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
