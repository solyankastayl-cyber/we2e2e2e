"""
Phase 8.9 Regime Validation Tests
"""

import pytest
import httpx

BASE_URL = "http://localhost:8001"

VALID_REGIMES = ["TREND_UP", "TREND_DOWN", "RANGE", "COMPRESSION", "EXPANSION"]
VALID_STATUSES = ["ON", "LIMITED", "WATCH", "OFF"]


class TestRegimeHealth:
    """Test regime validation health"""
    
    def test_health_endpoint(self):
        response = httpx.get(f"{BASE_URL}/api/regime/health")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == True
        assert data["version"] == "regime_v1_phase8.9"
        assert all(r in data["regimes"] for r in VALID_REGIMES)


class TestRegimeValidation:
    """Test regime validation endpoint"""
    
    def test_run_validation(self):
        """Run full regime validation"""
        response = httpx.post(f"{BASE_URL}/api/regime/validate", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        assert data["phase"] == "8.9"
        assert "activationMap" in data
        assert "regimeBreakdown" in data
        assert "tradingPolicy" in data
        assert data["summary"]["strategiesAnalyzed"] > 0


class TestActivationMap:
    """Test activation map functionality"""
    
    def test_get_activation_map(self):
        """Get complete activation map"""
        response = httpx.get(f"{BASE_URL}/api/regime/activation-map")
        assert response.status_code == 200
        data = response.json()
        
        assert "regimes" in data
        assert "strategies" in data
        assert len(data["regimes"]) == 5
        
        # Each strategy should have status for each regime
        for strategy in data["strategies"]:
            for regime in VALID_REGIMES:
                assert regime in strategy
                assert strategy[regime] in VALID_STATUSES
    
    def test_trend_strategies_differ_from_range(self):
        """Trend strategies should have different activation than range"""
        response = httpx.get(f"{BASE_URL}/api/regime/activation-map")
        data = response.json()
        
        # MTF_BREAKOUT should be ON in TREND but not in RANGE
        mtf = next(s for s in data["strategies"] if s["strategy"] == "MTF_BREAKOUT")
        assert mtf["TREND_UP"] == "ON"
        assert mtf["RANGE"] in ["WATCH", "OFF"]
        
        # MOMENTUM_CONTINUATION should be OFF in RANGE
        momentum = next(s for s in data["strategies"] if s["strategy"] == "MOMENTUM_CONTINUATION")
        assert momentum["RANGE"] == "OFF"


class TestRegimeStrategies:
    """Test getting strategies for specific regime"""
    
    def test_trend_up_strategies(self):
        """Test getting strategies for TREND_UP"""
        response = httpx.get(f"{BASE_URL}/api/regime/TREND_UP/strategies")
        assert response.status_code == 200
        data = response.json()
        
        assert data["regime"] == "TREND_UP"
        assert data["totalActive"] > 0
        
        # Check sorted by edge score
        edges = [s["edgeScore"] for s in data["activeStrategies"]]
        assert edges == sorted(edges, reverse=True)
    
    def test_range_has_fewer_strategies(self):
        """RANGE regime should have fewer active strategies than TREND"""
        trend_resp = httpx.get(f"{BASE_URL}/api/regime/TREND_UP/strategies")
        range_resp = httpx.get(f"{BASE_URL}/api/regime/RANGE/strategies")
        
        trend_data = trend_resp.json()
        range_data = range_resp.json()
        
        # RANGE typically has fewer active strategies
        assert range_data["totalActive"] <= trend_data["totalActive"]
    
    def test_invalid_regime(self):
        """Invalid regime should return 400"""
        response = httpx.get(f"{BASE_URL}/api/regime/INVALID/strategies")
        assert response.status_code == 400


class TestStrategyProfile:
    """Test strategy regime profile"""
    
    def test_get_strategy_profile(self):
        """Get regime profile for strategy"""
        response = httpx.get(f"{BASE_URL}/api/regime/strategy/MTF_BREAKOUT")
        assert response.status_code == 200
        data = response.json()
        
        assert data["strategyId"] == "MTF_BREAKOUT"
        assert data["bestRegime"] in VALID_REGIMES
        assert "activationMap" in data
        assert "regimeMetrics" in data
        assert "tradingRules" in data
        
        # Should have metrics for all regimes
        for regime in VALID_REGIMES:
            assert regime in data["regimeMetrics"]
    
    def test_unknown_strategy(self):
        """Unknown strategy should return 404"""
        response = httpx.get(f"{BASE_URL}/api/regime/strategy/UNKNOWN")
        assert response.status_code == 404


class TestRegimeCheck:
    """Test regime activation check"""
    
    def test_check_mtf_trend_up(self):
        """MTF_BREAKOUT should be ON in TREND_UP"""
        response = httpx.post(
            f"{BASE_URL}/api/regime/check",
            json={"strategyId": "MTF_BREAKOUT", "regime": "TREND_UP"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "ON"
        assert data["positionMultiplier"] == 1.0
        assert data["tradeable"] == True
    
    def test_check_mtf_range(self):
        """MTF_BREAKOUT should be WATCH in RANGE"""
        response = httpx.post(
            f"{BASE_URL}/api/regime/check",
            json={"strategyId": "MTF_BREAKOUT", "regime": "RANGE"}
        )
        data = response.json()
        
        assert data["status"] in ["WATCH", "OFF"]
        assert data["tradeable"] == False
    
    def test_position_multipliers(self):
        """Test position multipliers are correct"""
        # ON = 1.0x
        response = httpx.post(
            f"{BASE_URL}/api/regime/check",
            json={"strategyId": "MTF_BREAKOUT", "regime": "TREND_UP"}
        )
        assert response.json()["positionMultiplier"] == 1.0
        
        # Find a LIMITED case
        response = httpx.post(
            f"{BASE_URL}/api/regime/check",
            json={"strategyId": "DOUBLE_BOTTOM", "regime": "TREND_DOWN"}
        )
        data = response.json()
        if data["status"] == "LIMITED":
            assert data["positionMultiplier"] == 0.5


class TestTradingPolicy:
    """Test trading policy endpoint"""
    
    def test_get_policy(self):
        """Get complete trading policy"""
        response = httpx.get(f"{BASE_URL}/api/regime/policy")
        assert response.status_code == 200
        data = response.json()
        
        assert data["version"] == "phase8.9"
        assert "positionSizing" in data
        assert "regimeRules" in data
        
        # Check position sizing
        assert data["positionSizing"]["ON"]["multiplier"] == 1.0
        assert data["positionSizing"]["LIMITED"]["multiplier"] == 0.5
        assert data["positionSizing"]["OFF"]["multiplier"] == 0.0
        
        # Check regime rules exist for all regimes
        for regime in VALID_REGIMES:
            assert regime in data["regimeRules"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
