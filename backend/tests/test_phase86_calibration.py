"""
Phase 8.6 Calibration Filters Tests
"""

import pytest
import httpx
import asyncio

BASE_URL = "http://localhost:8001"

# Sample candle data for testing
SAMPLE_CANDLES = [
    {"open": 48000, "high": 48500, "low": 47800, "close": 48200, "volume": 1000000},
    {"open": 48200, "high": 48800, "low": 47900, "close": 48600, "volume": 1200000},
    {"open": 48600, "high": 49200, "low": 48300, "close": 49000, "volume": 1100000},
    {"open": 49000, "high": 49500, "low": 48700, "close": 49300, "volume": 1300000},
    {"open": 49300, "high": 49800, "low": 49000, "close": 49600, "volume": 1500000},
    {"open": 49600, "high": 50200, "low": 49400, "close": 50000, "volume": 1400000},
    {"open": 50000, "high": 50500, "low": 49700, "close": 50300, "volume": 1600000},
    {"open": 50300, "high": 50800, "low": 50000, "close": 50500, "volume": 1450000},
    {"open": 50500, "high": 51000, "low": 50200, "close": 50800, "volume": 1550000},
    {"open": 50800, "high": 51300, "low": 50500, "close": 51100, "volume": 1700000},
    {"open": 51100, "high": 51600, "low": 50800, "close": 51400, "volume": 1800000},
    {"open": 51400, "high": 51900, "low": 51100, "close": 51700, "volume": 1950000},
    {"open": 51700, "high": 52200, "low": 51400, "close": 52000, "volume": 2100000},
    {"open": 52000, "high": 52500, "low": 51700, "close": 52300, "volume": 2200000},
    {"open": 52300, "high": 52800, "low": 52000, "close": 52600, "volume": 2400000},
]


class TestCalibrationHealth:
    """Test calibration health endpoint"""
    
    def test_health_endpoint(self):
        response = httpx.get(f"{BASE_URL}/api/calibration/health")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == True
        assert data["version"] == "calibration_v1_phase8.6"
        assert "LIQUIDITY_SWEEP" in data["disabledStrategies"]
        assert "RANGE_REVERSAL" in data["disabledStrategies"]


class TestCalibrationConfig:
    """Test calibration config endpoint"""
    
    def test_config_endpoint(self):
        response = httpx.get(f"{BASE_URL}/api/calibration/config")
        assert response.status_code == 200
        data = response.json()
        
        config = data["config"]
        
        # Volatility Filter: ATR > SMA(ATR) * 0.8
        assert config["volatilityFilter"]["enabled"] == True
        assert config["volatilityFilter"]["atrMultiplier"] == 0.8
        
        # Trend Alignment: EMA50/EMA200
        assert config["trendAlignment"]["enabled"] == True
        assert config["trendAlignment"]["emaShortPeriod"] == 50
        assert config["trendAlignment"]["emaLongPeriod"] == 200
        
        # Volume Breakout: volume > SMA(volume) * 1.4
        assert config["volumeBreakout"]["enabled"] == True
        assert config["volumeBreakout"]["volumeMultiplier"] == 1.4
        
        # ATR-based TP/SL: SL = 1.5 * ATR, TP = 2.5 * ATR
        assert config["atrRiskManagement"]["enabled"] == True
        assert config["atrRiskManagement"]["stopLossATR"] == 1.5
        assert config["atrRiskManagement"]["takeProfitATR"] == 2.5


class TestDisabledStrategies:
    """Test disabled strategies (LIQUIDITY_SWEEP, RANGE_REVERSAL)"""
    
    def test_liquidity_sweep_disabled(self):
        """LIQUIDITY_SWEEP should be rejected"""
        response = httpx.post(
            f"{BASE_URL}/api/calibration/apply",
            json={
                "candles": SAMPLE_CANDLES,
                "direction": "LONG",
                "patternType": "LIQUIDITY_SWEEP",
                "entry": 52500
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["passed"] == False
        assert data["filters"]["strategyEnabled"] == False
        assert "STRATEGY_DISABLED" in data["rejectionReasons"]
    
    def test_liquidity_sweep_high_disabled(self):
        """LIQUIDITY_SWEEP_HIGH should be rejected"""
        response = httpx.post(
            f"{BASE_URL}/api/calibration/apply",
            json={
                "candles": SAMPLE_CANDLES,
                "direction": "SHORT",
                "patternType": "LIQUIDITY_SWEEP_HIGH",
                "entry": 52500
            }
        )
        data = response.json()
        assert data["filters"]["strategyEnabled"] == False
    
    def test_range_reversal_disabled(self):
        """RANGE_REVERSAL should be rejected"""
        response = httpx.post(
            f"{BASE_URL}/api/calibration/apply",
            json={
                "candles": SAMPLE_CANDLES,
                "direction": "SHORT",
                "patternType": "RANGE_REVERSAL",
                "entry": 52500
            }
        )
        data = response.json()
        
        assert data["passed"] == False
        assert data["filters"]["strategyEnabled"] == False
        assert "STRATEGY_DISABLED" in data["rejectionReasons"]
    
    def test_enabled_strategy_passes_strategy_check(self):
        """Enabled strategies should pass strategy check"""
        response = httpx.post(
            f"{BASE_URL}/api/calibration/apply",
            json={
                "candles": SAMPLE_CANDLES,
                "direction": "LONG",
                "patternType": "DOUBLE_BOTTOM",
                "entry": 52500
            }
        )
        data = response.json()
        
        assert data["filters"]["strategyEnabled"] == True
        assert "STRATEGY_DISABLED" not in data["rejectionReasons"]


class TestCalibrationFilters:
    """Test individual calibration filters"""
    
    def test_volatility_filter_computed_values(self):
        """Test ATR and ATR SMA are computed correctly"""
        response = httpx.post(
            f"{BASE_URL}/api/calibration/apply",
            json={
                "candles": SAMPLE_CANDLES,
                "direction": "LONG",
                "patternType": "DOUBLE_BOTTOM",
                "entry": 52500
            }
        )
        data = response.json()
        
        computed = data["computedValues"]
        assert computed["atr"] > 0
        assert computed["atrSMA"] > 0
        assert computed["volatilityRatio"] > 0
    
    def test_trend_alignment_up(self):
        """Test trend alignment for LONG in uptrend"""
        response = httpx.post(
            f"{BASE_URL}/api/calibration/apply",
            json={
                "candles": SAMPLE_CANDLES,
                "direction": "LONG",
                "patternType": "CHANNEL_UP",
                "entry": 52500
            }
        )
        data = response.json()
        
        # Price (52600) > EMA50, so trend is UP
        assert data["computedValues"]["trendDirection"] == "UP"
        assert data["filters"]["trendAlignmentPassed"] == True
    
    def test_trend_misalignment_short_in_uptrend(self):
        """Test trend misalignment for SHORT in uptrend"""
        response = httpx.post(
            f"{BASE_URL}/api/calibration/apply",
            json={
                "candles": SAMPLE_CANDLES,
                "direction": "SHORT",
                "patternType": "HEAD_SHOULDERS",
                "entry": 52500
            }
        )
        data = response.json()
        
        # Price > EMA50, trend is UP, but direction is SHORT
        assert data["computedValues"]["trendDirection"] == "UP"
        assert data["filters"]["trendAlignmentPassed"] == False
        assert "TREND_MISALIGNED" in data["rejectionReasons"]
    
    def test_atr_based_tp_sl(self):
        """Test ATR-based TP/SL calculation"""
        response = httpx.post(
            f"{BASE_URL}/api/calibration/apply",
            json={
                "candles": SAMPLE_CANDLES,
                "direction": "LONG",
                "patternType": "DOUBLE_BOTTOM",
                "entry": 52500
            }
        )
        data = response.json()
        
        levels = data["adjustedLevels"]
        atr = data["computedValues"]["atr"]
        
        # SL = entry - 1.5 * ATR
        expected_sl = 52500 - 1.5 * atr
        assert abs(levels["stopLoss"] - expected_sl) < 1
        
        # TP = entry + 2.5 * ATR
        expected_tp = 52500 + 2.5 * atr
        assert abs(levels["takeProfit"] - expected_tp) < 1
        
        # Risk/Reward should be 2.5/1.5 ≈ 1.67
        assert 1.6 < levels["riskReward"] < 1.7


class TestBatchCalibration:
    """Test batch calibration endpoint"""
    
    def test_batch_filtering(self):
        """Test batch scenario filtering"""
        response = httpx.post(
            f"{BASE_URL}/api/calibration/batch",
            json={
                "candles": SAMPLE_CANDLES,
                "scenarios": [
                    {"id": 1, "direction": "LONG", "patternType": "DOUBLE_BOTTOM", "entry": 52500},
                    {"id": 2, "direction": "SHORT", "patternType": "LIQUIDITY_SWEEP", "entry": 52500},
                    {"id": 3, "direction": "LONG", "patternType": "RANGE_REVERSAL", "entry": 52500},
                    {"id": 4, "direction": "LONG", "patternType": "CHANNEL_UP", "entry": 52500},
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["stats"]["total"] == 4
        
        # LIQUIDITY_SWEEP and RANGE_REVERSAL should be rejected
        assert data["stats"]["byReason"].get("STRATEGY_DISABLED", 0) >= 2
        
        # Check individual results
        results = data["results"]
        
        # Find LIQUIDITY_SWEEP result
        liq_sweep = next(r for r in results if r["scenarioId"] == 2)
        assert liq_sweep["passed"] == False
        assert "STRATEGY_DISABLED" in liq_sweep["rejectionReasons"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
