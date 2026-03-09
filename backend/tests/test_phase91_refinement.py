"""
Phase 9.1 — Failure-Driven Refinement Tests
============================================

Тесты для модуля анализа потерь и рекомендаций по улучшению.
"""

import pytest
import requests
import time

BASE_URL = "http://localhost:8001"


class TestPhase91Health:
    """Тесты health endpoint для Phase 9.1"""
    
    def test_health_returns_ok(self):
        """Health endpoint должен возвращать status ok"""
        resp = requests.get(f"{BASE_URL}/api/refinement/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["enabled"] == True
        assert data["version"] == "refinement_v1_phase9.1"
    
    def test_health_has_capabilities(self):
        """Health должен показывать capabilities"""
        resp = requests.get(f"{BASE_URL}/api/refinement/health")
        data = resp.json()
        assert "capabilities" in data
        assert "exit_analysis" in data["capabilities"]
        assert "entry_analysis" in data["capabilities"]
        assert "tpsl_optimization" in data["capabilities"]


class TestPhase91Analysis:
    """Тесты анализа потерь"""
    
    def test_analyze_btc(self):
        """Анализ BTC должен возвращать результаты"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "runId" in data
        assert data["symbol"] == "BTC"
        assert data["timeframe"] == "1d"
        
    def test_analyze_returns_stats(self):
        """Анализ должен возвращать статистику"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        data = resp.json()
        
        assert "stats" in data
        assert "totalTrades" in data["stats"]
        assert "losingTrades" in data["stats"]
        assert "lossRate" in data["stats"]
        
        # Sanity checks
        assert data["stats"]["totalTrades"] > 0
        assert data["stats"]["lossRate"] >= 0
        assert data["stats"]["lossRate"] <= 1
    
    def test_analyze_returns_category_breakdown(self):
        """Анализ должен возвращать breakdown по категориям"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        data = resp.json()
        
        assert "categoryBreakdown" in data
        assert isinstance(data["categoryBreakdown"], dict)
        
    def test_analyze_returns_exit_analysis(self):
        """Анализ должен включать exit analysis"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        data = resp.json()
        
        assert "exitAnalysis" in data
        exit_data = data["exitAnalysis"]
        
        assert "prematureStopRate" in exit_data
        assert "avgRLossToStops" in exit_data
        assert "optimalSL" in exit_data
        assert "optimalTP" in exit_data
        
        # SL/TP должны быть в разумном диапазоне
        assert 1.0 <= exit_data["optimalSL"] <= 3.0
        assert 1.5 <= exit_data["optimalTP"] <= 4.0
    
    def test_analyze_returns_entry_analysis(self):
        """Анализ должен включать entry analysis"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        data = resp.json()
        
        assert "entryAnalysis" in data
        entry_data = data["entryAnalysis"]
        
        assert "falseBreakoutRate" in entry_data
        assert "counterTrendRate" in entry_data
    
    def test_analyze_returns_regime_analysis(self):
        """Анализ должен включать regime analysis"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        data = resp.json()
        
        assert "regimeAnalysis" in data
        regime_data = data["regimeAnalysis"]
        
        assert "worstRegime" in regime_data
        assert "worstRegimeLossRate" in regime_data
    
    def test_analyze_returns_strategy_analysis(self):
        """Анализ должен включать strategy analysis"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        data = resp.json()
        
        assert "strategyAnalysis" in data
        strategy_data = data["strategyAnalysis"]
        
        assert "worstStrategy" in strategy_data
        assert "worstStrategyLossRate" in strategy_data


class TestPhase91Recommendations:
    """Тесты рекомендаций"""
    
    def test_analyze_returns_recommendations(self):
        """Анализ должен возвращать рекомендации"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        data = resp.json()
        
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)
        assert len(data["recommendations"]) > 0
    
    def test_recommendations_have_required_fields(self):
        """Рекомендации должны иметь обязательные поля"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        data = resp.json()
        
        for rec in data["recommendations"]:
            assert "priority" in rec
            assert rec["priority"] in ["HIGH", "MEDIUM", "LOW"]
            assert "category" in rec
            assert "issue" in rec
            assert "action" in rec
    
    def test_recommendations_sorted_by_priority(self):
        """Рекомендации должны быть отсортированы по приоритету"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        data = resp.json()
        
        priorities = [r["priority"] for r in data["recommendations"]]
        
        # HIGH должен быть перед MEDIUM, MEDIUM перед LOW
        high_indices = [i for i, p in enumerate(priorities) if p == "HIGH"]
        medium_indices = [i for i, p in enumerate(priorities) if p == "MEDIUM"]
        low_indices = [i for i, p in enumerate(priorities) if p == "LOW"]
        
        if high_indices and medium_indices:
            assert max(high_indices) < min(medium_indices)
        
        if medium_indices and low_indices:
            assert max(medium_indices) < min(low_indices)
    
    def test_get_all_recommendations(self):
        """Endpoint для всех рекомендаций"""
        # First run analysis
        requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        
        resp = requests.get(f"{BASE_URL}/api/refinement/recommendations")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "OK"
        assert "totalRecommendations" in data
        assert "byPriority" in data
        assert "recommendations" in data


class TestPhase91Summary:
    """Тесты summary endpoint"""
    
    def test_summary_after_analysis(self):
        """Summary должен работать после анализа"""
        # Run analysis first
        requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": "BTC", "timeframe": "1d"}
        )
        
        resp = requests.get(f"{BASE_URL}/api/refinement/summary")
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["status"] == "OK"
        assert "totalAnalyses" in data
        assert data["totalAnalyses"] > 0
        assert "results" in data


class TestPhase91DifferentAssets:
    """Тесты для разных активов"""
    
    @pytest.mark.parametrize("symbol,timeframe", [
        ("BTC", "1d"),
        ("SPX", "1d"),
        ("DXY", "1d"),
    ])
    def test_analyze_different_symbols(self, symbol, timeframe):
        """Анализ должен работать для разных символов"""
        resp = requests.post(
            f"{BASE_URL}/api/refinement/analyze",
            json={"symbol": symbol, "timeframe": timeframe}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["symbol"] == symbol
        assert data["timeframe"] == timeframe


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
