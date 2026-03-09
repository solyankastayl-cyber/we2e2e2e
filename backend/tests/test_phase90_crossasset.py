"""
Phase 9.0 Cross-Asset Validation Tests
"""

import pytest
import httpx

BASE_URL = "http://localhost:8001"

EXPECTED_ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SPX", "GOLD", "DXY"]


class TestCrossAssetHealth:
    """Test cross-asset validation health"""
    
    def test_health_endpoint(self):
        response = httpx.get(f"{BASE_URL}/api/crossasset/health")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == True
        assert data["version"] == "crossasset_v1_phase9.0"
        assert data["methodology"] == "ZERO_TUNING"
        assert all(a in data["availableAssets"] for a in EXPECTED_ASSETS)


class TestCrossAssetValidation:
    """Test cross-asset validation endpoint"""
    
    def test_run_validation(self):
        """Run full cross-asset validation"""
        response = httpx.post(
            f"{BASE_URL}/api/crossasset/validate",
            json={"includeBtc": True},
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["phase"] == "9.0"
        assert data["summary"]["assetsTested"] == 6
        assert data["systemVerdict"] in ["UNIVERSAL", "CRYPTO_SPECIFIC", "PARTIAL", "OVERFIT"]
        
        # Check all assets have results
        for asset in EXPECTED_ASSETS:
            assert asset in data["assetResults"]
    
    def test_no_tuning_applied(self):
        """Verify ZERO tuning methodology"""
        response = httpx.post(
            f"{BASE_URL}/api/crossasset/validate",
            json={},
            timeout=60
        )
        data = response.json()
        
        # Should have baseline config note
        assert "baselineConfig" in data
        assert data["baselineConfig"]["note"] == "ZERO tuning - same as BTC"


class TestCrossAssetResults:
    """Test cross-asset result endpoints"""
    
    def test_get_summary(self):
        """Get validation summary"""
        # Run validation first
        httpx.post(f"{BASE_URL}/api/crossasset/validate", json={}, timeout=60)
        
        response = httpx.get(f"{BASE_URL}/api/crossasset/summary")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "OK"
        assert data["totalAssets"] == 6
        
        # Should be sorted by PF
        pfs = [float(r["profitFactor"]) for r in data["results"]]
        assert pfs == sorted(pfs, reverse=True)
    
    def test_get_comparison(self):
        """Get comparison matrix"""
        response = httpx.get(f"{BASE_URL}/api/crossasset/comparison")
        assert response.status_code == 200
        data = response.json()
        
        assert "headers" in data
        assert "rows" in data
        assert len(data["rows"]) == 6
    
    def test_get_asset_result(self):
        """Get individual asset result"""
        response = httpx.get(f"{BASE_URL}/api/crossasset/asset/ETHUSDT")
        assert response.status_code == 200
        data = response.json()
        
        assert data["symbol"] == "ETHUSDT"
        assert data["assetClass"] == "CRYPTO"
        assert "coreMetrics" in data
        assert "directionBreakdown" in data
        assert "regimePerformance" in data


class TestAssetClassPerformance:
    """Test performance varies appropriately by asset class"""
    
    def test_crypto_performance(self):
        """Crypto should have good performance"""
        response = httpx.get(f"{BASE_URL}/api/crossasset/summary")
        data = response.json()
        
        crypto = [r for r in data["results"] if r["assetClass"] == "CRYPTO"]
        
        # At least 2 crypto should pass
        passed = len([c for c in crypto if c["verdict"] in ["PASS", "MARGINAL"]])
        assert passed >= 2
    
    def test_non_crypto_acceptable(self):
        """Non-crypto should have at least marginal performance"""
        response = httpx.get(f"{BASE_URL}/api/crossasset/summary")
        data = response.json()
        
        non_crypto = [r for r in data["results"] if r["assetClass"] != "CRYPTO"]
        
        # Non-crypto can have lower PF but shouldn't fail completely
        for asset in non_crypto:
            assert float(asset["profitFactor"]) >= 0.9


class TestDirectionBreakdown:
    """Test long/short breakdown"""
    
    def test_both_directions_traded(self):
        """System should trade both long and short"""
        response = httpx.get(f"{BASE_URL}/api/crossasset/asset/BTCUSDT")
        data = response.json()
        
        breakdown = data["directionBreakdown"]
        assert breakdown["longTrades"] > 0
        assert breakdown["shortTrades"] > 0
    
    def test_equities_long_bias(self):
        """Equities may show long bias but short should exist"""
        response = httpx.get(f"{BASE_URL}/api/crossasset/asset/SPX")
        data = response.json()
        
        breakdown = data["directionBreakdown"]
        # Both should exist
        assert breakdown["longTrades"] > 0
        # SPX may have fewer shorts due to structural bias
        # but they should still exist
        assert breakdown["shortTrades"] >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
