"""
B3: Real Decision Engine Integration Tests

Tests the integration of REAL Decision Engine into the Backtest Harness:
- POST /api/ta/backtest/run with useRealDecision=true returns real pattern data
- POST /api/ta/backtest/run with useRealDecision=false returns mock data
- decisionSnapshot.patternsUsed contains actual pattern types (not MOCK_PATTERN)
- decisionSnapshot.pEntry, eR, ev are populated with ML predictions
- Backtest run status is DONE
- GET /api/ta/backtest/run/:runId returns run details
- GET /api/ta/backtest/run/:runId/trades returns trades with decisionSnapshot
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data constants
TEST_ASSET = "BTCUSDT"
TEST_TIMEFRAME = "1h"
TEST_FROM = "2024-01-01"
TEST_TO = "2024-01-15"
TEST_WARMUP_BARS = 50
TEST_MAX_TRADES = 10


class TestB3RealDecisionEngineIntegration:
    """Tests for B3 Real Decision Engine integration into Backtest Harness"""
    
    real_run_id = None
    mock_run_id = None
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        assert BASE_URL, "REACT_APP_BACKEND_URL environment variable not set"
    
    # ═══════════════════════════════════════════════════════════════
    # Test 1: Backend Health Check
    # ═══════════════════════════════════════════════════════════════
    
    def test_01_health_check(self):
        """Verify backend and TA Engine are running"""
        # Backend health
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        print(f"Backend health: {data}")
        
        # TA Engine health
        response = requests.get(f"{BASE_URL}/api/ta/health")
        assert response.status_code == 200
        ta_data = response.json()
        assert ta_data.get("ok") == True
        print(f"TA Engine health: {ta_data}")
    
    # ═══════════════════════════════════════════════════════════════
    # Test 2: Run backtest with useRealDecision=true (REAL patterns)
    # ═══════════════════════════════════════════════════════════════
    
    def test_02_backtest_run_real_decision_engine(self):
        """POST /api/ta/backtest/run with useRealDecision=true"""
        payload = {
            "asset": TEST_ASSET,
            "timeframe": TEST_TIMEFRAME,
            "from": TEST_FROM,
            "to": TEST_TO,
            "warmupBars": TEST_WARMUP_BARS,
            "maxTrades": TEST_MAX_TRADES,
            "useRealDecision": True
        }
        
        response = requests.post(f"{BASE_URL}/api/ta/backtest/run", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Validate response structure
        assert data.get("ok") == True, f"Expected ok=true, got: {data}"
        assert "runId" in data, "Missing runId in response"
        assert data.get("status") == "DONE", f"Expected status=DONE, got: {data.get('status')}"
        assert data.get("decisionEngine") == "REAL", f"Expected decisionEngine=REAL, got: {data.get('decisionEngine')}"
        
        # Store runId for subsequent tests
        TestB3RealDecisionEngineIntegration.real_run_id = data["runId"]
        
        print(f"Real Decision Engine backtest completed: runId={data['runId']}")
        print(f"Summary: {data.get('summary')}")
    
    # ═══════════════════════════════════════════════════════════════
    # Test 3: Run backtest with useRealDecision=false (MOCK patterns)
    # ═══════════════════════════════════════════════════════════════
    
    def test_03_backtest_run_mock_decision_engine(self):
        """POST /api/ta/backtest/run with useRealDecision=false"""
        payload = {
            "asset": TEST_ASSET,
            "timeframe": TEST_TIMEFRAME,
            "from": TEST_FROM,
            "to": TEST_TO,
            "warmupBars": TEST_WARMUP_BARS,
            "maxTrades": TEST_MAX_TRADES,
            "useRealDecision": False
        }
        
        response = requests.post(f"{BASE_URL}/api/ta/backtest/run", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Validate response structure
        assert data.get("ok") == True, f"Expected ok=true, got: {data}"
        assert "runId" in data, "Missing runId in response"
        assert data.get("status") == "DONE", f"Expected status=DONE, got: {data.get('status')}"
        assert data.get("decisionEngine") == "MOCK", f"Expected decisionEngine=MOCK, got: {data.get('decisionEngine')}"
        
        # Store runId for subsequent tests
        TestB3RealDecisionEngineIntegration.mock_run_id = data["runId"]
        
        print(f"Mock Decision Engine backtest completed: runId={data['runId']}")
        print(f"Summary: {data.get('summary')}")
    
    # ═══════════════════════════════════════════════════════════════
    # Test 4: Get run details for REAL decision engine run
    # ═══════════════════════════════════════════════════════════════
    
    def test_04_get_real_run_details(self):
        """GET /api/ta/backtest/run/:runId for real decision run"""
        run_id = TestB3RealDecisionEngineIntegration.real_run_id
        assert run_id, "No real run_id available - test_02 must run first"
        
        response = requests.get(f"{BASE_URL}/api/ta/backtest/run/{run_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        run = data.get("run")
        assert run is not None, "Missing run object"
        assert run.get("runId") == run_id
        assert run.get("status") == "DONE"
        assert run.get("asset") == TEST_ASSET
        assert run.get("timeframe") == TEST_TIMEFRAME
        
        # Validate config
        config = run.get("config")
        assert config is not None
        assert config.get("warmupBars") == TEST_WARMUP_BARS
        
        print(f"Real run details retrieved: status={run.get('status')}")
    
    # ═══════════════════════════════════════════════════════════════
    # Test 5: Get trades from REAL decision engine run - validate decisionSnapshot
    # ═══════════════════════════════════════════════════════════════
    
    def test_05_get_real_decision_trades_with_patterns(self):
        """GET /api/ta/backtest/run/:runId/trades - validates REAL pattern detection"""
        run_id = TestB3RealDecisionEngineIntegration.real_run_id
        assert run_id, "No real run_id available - test_02 must run first"
        
        response = requests.get(f"{BASE_URL}/api/ta/backtest/run/{run_id}/trades?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert data.get("runId") == run_id
        
        trades = data.get("trades", [])
        
        # Need at least some trades to validate
        if len(trades) == 0:
            pytest.skip("No trades generated - may need longer date range or different parameters")
        
        print(f"Found {len(trades)} trades from real decision engine")
        
        real_pattern_types = set()
        
        for trade in trades:
            snapshot = trade.get("decisionSnapshot")
            assert snapshot is not None, f"Trade {trade.get('tradeId')} missing decisionSnapshot"
            
            # Validate decisionSnapshot structure
            assert "scenarioId" in snapshot, "Missing scenarioId in decisionSnapshot"
            assert "bias" in snapshot, "Missing bias in decisionSnapshot"
            assert "pEntry" in snapshot, "Missing pEntry in decisionSnapshot"
            assert "eR" in snapshot, "Missing eR in decisionSnapshot"
            assert "ev" in snapshot, "Missing ev in decisionSnapshot"
            assert "patternsUsed" in snapshot, "Missing patternsUsed in decisionSnapshot"
            
            # Validate patternsUsed contains REAL pattern types (not MOCK_PATTERN)
            patterns_used = snapshot.get("patternsUsed", [])
            assert len(patterns_used) > 0, "patternsUsed is empty"
            
            for pattern in patterns_used:
                assert pattern != "MOCK_PATTERN", f"Found MOCK_PATTERN in REAL decision run"
                real_pattern_types.add(pattern)
            
            # Validate ML predictions are populated (not mock defaults)
            pEntry = snapshot.get("pEntry")
            eR = snapshot.get("eR")
            ev = snapshot.get("ev")
            
            # pEntry should be valid probability
            assert 0 <= pEntry <= 1, f"pEntry {pEntry} out of [0,1] range"
            
            # eR should be reasonable
            assert eR > 0, f"eR {eR} should be positive"
            
        print(f"Real pattern types detected: {real_pattern_types}")
        assert len(real_pattern_types) > 0, "No real pattern types detected"
    
    # ═══════════════════════════════════════════════════════════════
    # Test 6: Get trades from MOCK decision engine run - validate MOCK_PATTERN
    # ═══════════════════════════════════════════════════════════════
    
    def test_06_get_mock_decision_trades_with_mock_pattern(self):
        """GET /api/ta/backtest/run/:runId/trades - validates MOCK pattern data"""
        run_id = TestB3RealDecisionEngineIntegration.mock_run_id
        assert run_id, "No mock run_id available - test_03 must run first"
        
        response = requests.get(f"{BASE_URL}/api/ta/backtest/run/{run_id}/trades?limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        trades = data.get("trades", [])
        
        if len(trades) == 0:
            pytest.skip("No mock trades generated")
        
        print(f"Found {len(trades)} trades from mock decision engine")
        
        for trade in trades:
            snapshot = trade.get("decisionSnapshot")
            assert snapshot is not None
            
            # Mock trades should have MOCK_PATTERN
            patterns_used = snapshot.get("patternsUsed", [])
            assert "MOCK_PATTERN" in patterns_used, f"Expected MOCK_PATTERN in mock run, got: {patterns_used}"
            
            # Mock values should be default (0.5 for pEntry, 1.5 for eR)
            pEntry = snapshot.get("pEntry")
            eR = snapshot.get("eR")
            ev = snapshot.get("ev")
            
            assert pEntry == 0.5, f"Mock pEntry should be 0.5, got {pEntry}"
            assert eR == 1.5, f"Mock eR should be 1.5, got {eR}"
            assert ev == 0.5, f"Mock ev should be 0.5, got {ev}"
        
        print("Mock decision engine correctly returns MOCK_PATTERN with default values")
    
    # ═══════════════════════════════════════════════════════════════
    # Test 7: Compare REAL vs MOCK decision snapshot differences
    # ═══════════════════════════════════════════════════════════════
    
    def test_07_compare_real_vs_mock_decision_snapshots(self):
        """Compare decisionSnapshot fields between REAL and MOCK runs"""
        real_run_id = TestB3RealDecisionEngineIntegration.real_run_id
        mock_run_id = TestB3RealDecisionEngineIntegration.mock_run_id
        
        assert real_run_id and mock_run_id, "Both run IDs required"
        
        # Get trades from both runs
        real_response = requests.get(f"{BASE_URL}/api/ta/backtest/run/{real_run_id}/trades?limit=5")
        mock_response = requests.get(f"{BASE_URL}/api/ta/backtest/run/{mock_run_id}/trades?limit=5")
        
        assert real_response.status_code == 200
        assert mock_response.status_code == 200
        
        real_trades = real_response.json().get("trades", [])
        mock_trades = mock_response.json().get("trades", [])
        
        if len(real_trades) == 0 or len(mock_trades) == 0:
            pytest.skip("Need trades from both runs for comparison")
        
        # Compare first trade from each
        real_snapshot = real_trades[0].get("decisionSnapshot", {})
        mock_snapshot = mock_trades[0].get("decisionSnapshot", {})
        
        print("\n=== REAL vs MOCK Decision Snapshot Comparison ===")
        print(f"REAL patternsUsed: {real_snapshot.get('patternsUsed')}")
        print(f"MOCK patternsUsed: {mock_snapshot.get('patternsUsed')}")
        print(f"REAL pEntry: {real_snapshot.get('pEntry')}")
        print(f"MOCK pEntry: {mock_snapshot.get('pEntry')}")
        print(f"REAL eR: {real_snapshot.get('eR')}")
        print(f"MOCK eR: {mock_snapshot.get('eR')}")
        print(f"REAL ev: {real_snapshot.get('ev')}")
        print(f"MOCK ev: {mock_snapshot.get('ev')}")
        print(f"REAL scenarioId: {real_snapshot.get('scenarioId')}")
        print(f"MOCK scenarioId: {mock_snapshot.get('scenarioId')}")
        
        # Validate differences
        real_patterns = real_snapshot.get('patternsUsed', [])
        mock_patterns = mock_snapshot.get('patternsUsed', [])
        
        # Real should NOT contain MOCK_PATTERN
        assert "MOCK_PATTERN" not in real_patterns, "REAL run should not have MOCK_PATTERN"
        
        # Mock SHOULD contain MOCK_PATTERN
        assert "MOCK_PATTERN" in mock_patterns, "MOCK run should have MOCK_PATTERN"
        
        # Real pEntry should differ from mock default
        assert real_snapshot.get('pEntry') != 0.5, "REAL pEntry should not be mock default 0.5"
        
        # Scenario IDs should be different
        assert real_snapshot.get('scenarioId') != mock_snapshot.get('scenarioId'), "ScenarioIds should differ"
    
    # ═══════════════════════════════════════════════════════════════
    # Test 8: Validate ML predictions in REAL decision snapshots
    # ═══════════════════════════════════════════════════════════════
    
    def test_08_validate_ml_predictions_in_real_snapshots(self):
        """Validate pEntry, eR, ev are ML predictions in REAL run"""
        run_id = TestB3RealDecisionEngineIntegration.real_run_id
        assert run_id, "No real run_id available"
        
        response = requests.get(f"{BASE_URL}/api/ta/backtest/run/{run_id}/trades?limit=20")
        assert response.status_code == 200
        
        trades = response.json().get("trades", [])
        if len(trades) == 0:
            pytest.skip("No trades to validate")
        
        pEntry_values = []
        eR_values = []
        ev_values = []
        
        for trade in trades:
            snapshot = trade.get("decisionSnapshot", {})
            pEntry_values.append(snapshot.get("pEntry", 0))
            eR_values.append(snapshot.get("eR", 0))
            ev_values.append(snapshot.get("ev", 0))
        
        # pEntry should have variance (not all 0.5)
        pEntry_unique = set(pEntry_values)
        assert len(pEntry_unique) > 1 or (len(pEntry_unique) == 1 and 0.5 not in pEntry_unique), \
            f"pEntry values should be ML predictions, not all 0.5. Unique values: {pEntry_unique}"
        
        # eR should have variance (not all 1.5)
        eR_unique = set(eR_values)
        assert len(eR_unique) > 1 or (len(eR_unique) == 1 and 1.5 not in eR_unique), \
            f"eR values should vary. Unique values: {eR_unique}"
        
        # ev should have variance (not all 0.5)
        ev_unique = set(ev_values)
        assert len(ev_unique) > 1 or (len(ev_unique) == 1 and 0.5 not in ev_unique), \
            f"ev values should vary. Unique values: {ev_unique}"
        
        print(f"ML prediction ranges:")
        print(f"  pEntry: {min(pEntry_values):.4f} - {max(pEntry_values):.4f}")
        print(f"  eR: {min(eR_values):.4f} - {max(eR_values):.4f}")
        print(f"  ev: {min(ev_values):.4f} - {max(ev_values):.4f}")
    
    # ═══════════════════════════════════════════════════════════════
    # Test 9: Default useRealDecision behavior (should be true)
    # ═══════════════════════════════════════════════════════════════
    
    def test_09_default_use_real_decision(self):
        """POST /api/ta/backtest/run without useRealDecision flag defaults to REAL"""
        payload = {
            "asset": TEST_ASSET,
            "timeframe": TEST_TIMEFRAME,
            "from": TEST_FROM,
            "to": TEST_TO,
            "warmupBars": TEST_WARMUP_BARS,
            "maxTrades": 5
            # useRealDecision not specified - should default to true
        }
        
        response = requests.post(f"{BASE_URL}/api/ta/backtest/run", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        
        # Should default to REAL decision engine
        assert data.get("decisionEngine") == "REAL", \
            f"Default should be REAL, got: {data.get('decisionEngine')}"
        
        print("Default useRealDecision behavior: REAL (confirmed)")
    
    # ═══════════════════════════════════════════════════════════════
    # Test 10: Invalid request validation
    # ═══════════════════════════════════════════════════════════════
    
    def test_10_invalid_request_validation(self):
        """POST /api/ta/backtest/run with missing required fields"""
        # Missing asset
        payload = {
            "timeframe": "1h",
            "from": TEST_FROM,
            "to": TEST_TO
        }
        
        response = requests.post(f"{BASE_URL}/api/ta/backtest/run", json=payload)
        data = response.json()
        
        assert data.get("ok") == False, "Should fail with missing asset"
        assert "error" in data, "Should return error message"
        print(f"Validation error (as expected): {data.get('error')}")
    
    # ═══════════════════════════════════════════════════════════════
    # Test 11: Nonexistent run ID handling
    # ═══════════════════════════════════════════════════════════════
    
    def test_11_nonexistent_run_id(self):
        """GET /api/ta/backtest/run/:runId with invalid runId"""
        fake_run_id = "00000000-0000-0000-0000-000000000000"
        
        response = requests.get(f"{BASE_URL}/api/ta/backtest/run/{fake_run_id}")
        data = response.json()
        
        assert data.get("ok") == False, "Should fail with invalid runId"
        assert "error" in data, "Should return error message"
        print(f"Error for nonexistent run (as expected): {data.get('error')}")
    
    # ═══════════════════════════════════════════════════════════════
    # Test 12: List runs endpoint
    # ═══════════════════════════════════════════════════════════════
    
    def test_12_list_runs(self):
        """GET /api/ta/backtest/runs lists recent runs"""
        response = requests.get(f"{BASE_URL}/api/ta/backtest/runs?limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("ok") == True
        assert "runs" in data
        assert isinstance(data["runs"], list)
        
        print(f"Found {len(data['runs'])} recent backtest runs")
        
        # Verify our test runs are in the list
        run_ids = [r.get("runId") for r in data["runs"]]
        if TestB3RealDecisionEngineIntegration.real_run_id:
            assert TestB3RealDecisionEngineIntegration.real_run_id in run_ids, \
                "Real test run should be in list"


class TestB3DecisionSnapshotStructure:
    """Tests for decisionSnapshot structure and field validation"""
    
    def test_decision_snapshot_required_fields(self):
        """Validate all required fields in decisionSnapshot"""
        payload = {
            "asset": TEST_ASSET,
            "timeframe": TEST_TIMEFRAME,
            "from": TEST_FROM,
            "to": TEST_TO,
            "warmupBars": TEST_WARMUP_BARS,
            "maxTrades": 5,
            "useRealDecision": True
        }
        
        response = requests.post(f"{BASE_URL}/api/ta/backtest/run", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        run_id = data.get("runId")
        
        if not run_id:
            pytest.skip("No runId returned")
        
        # Get trades
        trades_response = requests.get(f"{BASE_URL}/api/ta/backtest/run/{run_id}/trades?limit=10")
        trades = trades_response.json().get("trades", [])
        
        if len(trades) == 0:
            pytest.skip("No trades generated")
        
        # Validate structure of first trade's decisionSnapshot
        snapshot = trades[0].get("decisionSnapshot")
        assert snapshot is not None
        
        required_fields = ["scenarioId", "bias", "pEntry", "eR", "ev", "patternsUsed"]
        for field in required_fields:
            assert field in snapshot, f"Missing required field: {field}"
        
        # Validate field types
        assert isinstance(snapshot["scenarioId"], str), "scenarioId should be string"
        assert snapshot["bias"] in ["LONG", "SHORT", "WAIT"], f"Invalid bias: {snapshot['bias']}"
        assert isinstance(snapshot["pEntry"], (int, float)), "pEntry should be numeric"
        assert isinstance(snapshot["eR"], (int, float)), "eR should be numeric"
        assert isinstance(snapshot["ev"], (int, float)), "ev should be numeric"
        assert isinstance(snapshot["patternsUsed"], list), "patternsUsed should be list"
        
        print(f"DecisionSnapshot structure validated: {list(snapshot.keys())}")


# Run pytest with: pytest -v test_b3_real_decision_engine.py
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
