"""
Shadow Stress Lab API Tests - Phase 9.30B
==========================================

Tests for the Shadow Portfolio Stress Lab system that runs Shadow Portfolio
through historical crisis scenarios to validate system resilience.

Features tested:
- GET /api/stress/health - Service health with scenario count
- GET /api/stress/scenarios - Lists all 11 crisis scenarios
- GET /api/stress/scenarios?asset_class=CRYPTO - Filter by asset class
- POST /api/stress/run - Run single scenario
- POST /api/stress/run - Run with different modes (CORE_ONLY, FULL_STRESS_POLICIES)
- POST /api/stress/run-batch - Run all scenarios as batch
- GET /api/stress/runs - List completed stress runs
- GET /api/stress/run/{runId} - Full run details
- GET /api/stress/report/{runId} - Condensed report with verdict
- GET /api/stress/events/{runId} - Timeline events
- GET /api/stress/metrics/{runId} - Detailed stress metrics
- Scenario produces equity curve, strategy results, timeline events
- Verdict system (EXCELLENT/GOOD/ACCEPTABLE/WEAK/FAILED)
- Batch result includes survival rate, family vulnerability, weakest/strongest scenario

Note: Crisis dynamics are MOCKED (synthetic from CrisisProfile), market prices are mock,
signal generation is deterministic. Each run creates an ISOLATED shadow portfolio instance.
"""

import pytest
import requests
import os
import time

# Get base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Define expected scenarios
EXPECTED_SCENARIOS = [
    "EQUITY_1987_CRASH",
    "EQUITY_2000_DOTCOM",
    "EQUITY_2008_GFC",
    "EQUITY_2020_COVID",
    "EQUITY_2022_INFLATION",
    "CRYPTO_2018_WINTER",
    "CRYPTO_2020_MARCH",
    "CRYPTO_2022_DELEVERAGE",
    "MACRO_1970_INFLATION",
    "MACRO_1980_RATE_SHOCK",
    "MACRO_2022_DXY_SPIKE",
]

# Define expected modes
EXPECTED_MODES = ["CORE_ONLY", "FULL_SYSTEM", "FULL_STRESS_POLICIES"]

# Define expected verdicts
EXPECTED_VERDICTS = ["EXCELLENT", "GOOD", "ACCEPTABLE", "WEAK", "FAILED"]


class TestStressLabHealth:
    """Health endpoint tests"""
    
    def test_health_check(self):
        """Test stress lab health endpoint returns status with scenario count"""
        response = requests.get(f"{BASE_URL}/api/stress/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        
        data = response.json()
        assert data.get("enabled") == True
        assert data.get("status") == "ok"
        assert data.get("version") == "phase9.30B"
        assert "total_scenarios" in data
        assert data["total_scenarios"] == 11
        assert "total_runs" in data
        assert "total_batches" in data
        assert "timestamp" in data
        
        print(f"Health check passed - Scenarios: {data['total_scenarios']}, Runs: {data['total_runs']}")


class TestStressLabScenarios:
    """Scenarios listing tests"""
    
    def test_get_all_scenarios(self):
        """Test getting all 11 crisis scenarios"""
        response = requests.get(f"{BASE_URL}/api/stress/scenarios")
        assert response.status_code == 200, f"Get scenarios failed: {response.text}"
        
        data = response.json()
        assert "total" in data
        assert "scenarios" in data
        assert data["total"] == 11
        assert len(data["scenarios"]) == 11
        
        # Verify all expected scenarios are present
        scenario_ids = [s["scenario_id"] for s in data["scenarios"]]
        for expected_id in EXPECTED_SCENARIOS:
            assert expected_id in scenario_ids, f"Missing scenario: {expected_id}"
        
        # Verify scenario structure
        for scenario in data["scenarios"]:
            assert "scenario_id" in scenario
            assert "name" in scenario
            assert "description" in scenario
            assert "asset_class" in scenario
            assert "tags" in scenario
            assert "start_date" in scenario
            assert "end_date" in scenario
            assert "total_bars" in scenario
            assert "crisis_profile" in scenario
            assert "affected_assets" in scenario
            
            # Verify crisis_profile structure
            cp = scenario["crisis_profile"]
            assert "peak_drawdown" in cp
            assert "drawdown_duration_bars" in cp
            assert "recovery_duration_bars" in cp
            assert "volatility_multiplier" in cp
            assert "correlation_spike" in cp
            assert "mean_reversion_after" in cp
        
        print(f"All 11 scenarios retrieved successfully")
        for s in data["scenarios"]:
            print(f"  - {s['scenario_id']}: {s['name']} ({s['asset_class']})")
    
    def test_filter_scenarios_by_crypto(self):
        """Test filtering scenarios by CRYPTO asset class"""
        response = requests.get(f"{BASE_URL}/api/stress/scenarios?asset_class=CRYPTO")
        assert response.status_code == 200, f"Filter failed: {response.text}"
        
        data = response.json()
        assert data["total"] >= 1
        
        # All returned scenarios should be CRYPTO
        for scenario in data["scenarios"]:
            assert scenario["asset_class"] == "CRYPTO", f"Non-CRYPTO scenario returned: {scenario['scenario_id']}"
        
        # Verify expected CRYPTO scenarios
        crypto_ids = [s["scenario_id"] for s in data["scenarios"]]
        expected_crypto = ["CRYPTO_2018_WINTER", "CRYPTO_2020_MARCH", "CRYPTO_2022_DELEVERAGE"]
        for cid in expected_crypto:
            assert cid in crypto_ids, f"Missing CRYPTO scenario: {cid}"
        
        print(f"CRYPTO filter returned {data['total']} scenarios: {crypto_ids}")
    
    def test_filter_scenarios_by_equity(self):
        """Test filtering scenarios by EQUITY asset class"""
        response = requests.get(f"{BASE_URL}/api/stress/scenarios?asset_class=EQUITY")
        assert response.status_code == 200, f"Filter failed: {response.text}"
        
        data = response.json()
        assert data["total"] >= 1
        
        for scenario in data["scenarios"]:
            assert scenario["asset_class"] in ["EQUITY", "MULTI_ASSET"]
        
        print(f"EQUITY filter returned {data['total']} scenarios")
    
    def test_filter_scenarios_by_fx(self):
        """Test filtering scenarios by FX asset class"""
        response = requests.get(f"{BASE_URL}/api/stress/scenarios?asset_class=FX")
        assert response.status_code == 200, f"Filter failed: {response.text}"
        
        data = response.json()
        # FX scenarios: MACRO_1980_RATE_SHOCK, MACRO_2022_DXY_SPIKE
        fx_ids = [s["scenario_id"] for s in data["scenarios"]]
        print(f"FX filter returned {data['total']} scenarios: {fx_ids}")


class TestStressLabSingleRun:
    """Single scenario run tests"""
    
    def test_run_scenario_gfc_2008(self):
        """Test running 2008 GFC scenario with default FULL_SYSTEM mode"""
        payload = {
            "scenario_id": "EQUITY_2008_GFC",
            "mode": "FULL_SYSTEM",
            "initial_capital": 100000.0
        }
        
        response = requests.post(f"{BASE_URL}/api/stress/run", json=payload)
        assert response.status_code == 200, f"Run failed: {response.text}"
        
        data = response.json()
        
        # Verify run structure
        assert "run_id" in data
        assert data["scenario_id"] == "EQUITY_2008_GFC"
        assert data["scenario_name"] == "2008-2009 Global Financial Crisis"
        assert data["mode"] == "FULL_SYSTEM"
        assert data["status"] == "COMPLETED"
        assert data["initial_equity"] == 100000.0
        assert "final_equity" in data
        assert "survived" in data
        assert "verdict" in data
        assert data["verdict"] in EXPECTED_VERDICTS
        assert "verdict_details" in data
        assert isinstance(data["verdict_details"], list)
        
        # Verify metrics
        assert "metrics" in data
        metrics = data["metrics"]
        assert "total_return" in metrics
        assert "total_return_pct" in metrics
        assert "max_drawdown_pct" in metrics
        assert "recovery_bars" in metrics
        assert "capital_preserved_pct" in metrics
        assert "regime_switches" in metrics
        assert "strategies_survived" in metrics
        
        # Verify strategy results
        assert "strategy_results" in data
        assert len(data["strategy_results"]) > 0  # Should have default test strategies
        
        for sr in data["strategy_results"]:
            assert "strategy_id" in sr
            assert "alpha_id" in sr
            assert "name" in sr
            assert "family" in sr
            assert "survived" in sr
            assert "total_pnl" in sr
            assert "trades" in sr
        
        # Verify timeline and equity curve counts
        assert "timeline_events" in data
        assert "equity_curve_points" in data
        assert data["equity_curve_points"] > 0
        
        # Verify timestamps
        assert "started_at" in data
        assert "completed_at" in data
        assert "duration_ms" in data
        
        print(f"GFC 2008 run completed:")
        print(f"  Run ID: {data['run_id']}")
        print(f"  Verdict: {data['verdict']}")
        print(f"  Survived: {data['survived']}")
        print(f"  Final Equity: {data['final_equity']}")
        print(f"  Max Drawdown: {metrics['max_drawdown_pct']:.2%}")
        print(f"  Capital Preserved: {metrics['capital_preserved_pct']:.2%}")
        print(f"  Strategies: {len(data['strategy_results'])}")
        
        return data["run_id"]
    
    def test_run_scenario_core_only_mode(self):
        """Test running scenario with CORE_ONLY mode (minimal risk management)"""
        payload = {
            "scenario_id": "CRYPTO_2018_WINTER",
            "mode": "CORE_ONLY",
            "initial_capital": 50000.0
        }
        
        response = requests.post(f"{BASE_URL}/api/stress/run", json=payload)
        assert response.status_code == 200, f"Run failed: {response.text}"
        
        data = response.json()
        assert data["mode"] == "CORE_ONLY"
        assert data["initial_equity"] == 50000.0
        assert data["status"] == "COMPLETED"
        
        print(f"CORE_ONLY run completed - Verdict: {data['verdict']}")
        return data["run_id"]
    
    def test_run_scenario_full_stress_policies_mode(self):
        """Test running scenario with FULL_STRESS_POLICIES mode (aggressive risk management)"""
        payload = {
            "scenario_id": "EQUITY_2020_COVID",
            "mode": "FULL_STRESS_POLICIES",
            "initial_capital": 100000.0
        }
        
        response = requests.post(f"{BASE_URL}/api/stress/run", json=payload)
        assert response.status_code == 200, f"Run failed: {response.text}"
        
        data = response.json()
        assert data["mode"] == "FULL_STRESS_POLICIES"
        assert data["status"] == "COMPLETED"
        
        print(f"FULL_STRESS_POLICIES run completed - Verdict: {data['verdict']}")
        return data["run_id"]
    
    def test_run_unknown_scenario(self):
        """Test running an unknown scenario returns proper error"""
        payload = {
            "scenario_id": "UNKNOWN_SCENARIO",
            "mode": "FULL_SYSTEM"
        }
        
        response = requests.post(f"{BASE_URL}/api/stress/run", json=payload)
        assert response.status_code == 200  # Returns FAILED run, not HTTP error
        
        data = response.json()
        assert data["status"] == "FAILED"
        assert "not found" in data.get("verdict", "").lower()
        
        print(f"Unknown scenario handled correctly - Status: {data['status']}")


class TestStressLabBatchRun:
    """Batch scenario run tests"""
    
    def test_run_batch_all_scenarios(self):
        """Test running all 11 scenarios as a batch"""
        payload = {
            "scenario_ids": None,  # None means all scenarios
            "mode": "FULL_SYSTEM",
            "initial_capital": 100000.0
        }
        
        response = requests.post(f"{BASE_URL}/api/stress/run-batch", json=payload)
        assert response.status_code == 200, f"Batch run failed: {response.text}"
        
        data = response.json()
        
        # Verify batch structure
        assert "batch_id" in data
        assert data["mode"] == "FULL_SYSTEM"
        assert data["total_scenarios"] == 11
        assert "scenarios_survived" in data
        assert "scenarios_failed" in data
        assert data["scenarios_survived"] + data["scenarios_failed"] == 11
        
        # Verify survival rate
        assert "survival_rate" in data
        assert 0 <= data["survival_rate"] <= 1
        
        # Verify avg drawdown and recovery
        assert "avg_drawdown" in data
        assert "avg_recovery_bars" in data
        
        # Verify weakest/strongest
        assert "weakest_scenario" in data
        assert "strongest_scenario" in data
        
        # Verify family vulnerability
        assert "family_vulnerability" in data
        assert isinstance(data["family_vulnerability"], dict)
        
        # Verify run_ids
        assert "run_ids" in data
        assert len(data["run_ids"]) == 11
        
        # Verify timestamps
        assert "started_at" in data
        assert "completed_at" in data
        
        print(f"Batch run completed:")
        print(f"  Batch ID: {data['batch_id']}")
        print(f"  Total Scenarios: {data['total_scenarios']}")
        print(f"  Survived: {data['scenarios_survived']}")
        print(f"  Failed: {data['scenarios_failed']}")
        print(f"  Survival Rate: {data['survival_rate']:.2%}")
        print(f"  Avg Drawdown: {data['avg_drawdown']:.2%}")
        print(f"  Weakest: {data['weakest_scenario']}")
        print(f"  Strongest: {data['strongest_scenario']}")
        print(f"  Family Vulnerability: {data['family_vulnerability']}")
        
        return data
    
    def test_run_batch_specific_scenarios(self):
        """Test running specific scenarios as a batch"""
        payload = {
            "scenario_ids": ["EQUITY_2008_GFC", "CRYPTO_2020_MARCH", "MACRO_2022_DXY_SPIKE"],
            "mode": "FULL_SYSTEM",
            "initial_capital": 100000.0
        }
        
        response = requests.post(f"{BASE_URL}/api/stress/run-batch", json=payload)
        assert response.status_code == 200, f"Batch run failed: {response.text}"
        
        data = response.json()
        assert data["total_scenarios"] == 3
        assert len(data["run_ids"]) == 3
        
        print(f"Batch of 3 scenarios completed - Survival Rate: {data['survival_rate']:.2%}")


class TestStressLabQueryResults:
    """Query results endpoints tests"""
    
    @pytest.fixture(autouse=True)
    def setup_run(self):
        """Create a stress run for query tests"""
        payload = {
            "scenario_id": "EQUITY_1987_CRASH",
            "mode": "FULL_SYSTEM",
            "initial_capital": 100000.0
        }
        response = requests.post(f"{BASE_URL}/api/stress/run", json=payload)
        assert response.status_code == 200
        self.run_data = response.json()
        self.run_id = self.run_data["run_id"]
        yield
    
    def test_list_runs(self):
        """Test listing completed stress runs"""
        response = requests.get(f"{BASE_URL}/api/stress/runs")
        assert response.status_code == 200, f"List runs failed: {response.text}"
        
        data = response.json()
        assert "total" in data
        assert "runs" in data
        assert data["total"] >= 1  # At least the run we created
        
        # Verify run summary structure
        if data["runs"]:
            run = data["runs"][0]
            assert "run_id" in run
            assert "scenario" in run
            assert "mode" in run
            assert "status" in run
            assert "verdict" in run
            assert "survived" in run
            assert "max_drawdown_pct" in run
            assert "capital_preserved_pct" in run
            assert "completed_at" in run
        
        print(f"Listed {data['total']} runs")
    
    def test_get_run_details(self):
        """Test getting full run details"""
        response = requests.get(f"{BASE_URL}/api/stress/run/{self.run_id}")
        assert response.status_code == 200, f"Get run failed: {response.text}"
        
        data = response.json()
        assert data["run_id"] == self.run_id
        assert "scenario_id" in data
        assert "scenario_name" in data
        assert "mode" in data
        assert "status" in data
        assert "metrics" in data
        assert "strategy_results" in data
        assert "verdict" in data
        assert "verdict_details" in data
        
        print(f"Run details retrieved - Verdict: {data['verdict']}")
    
    def test_get_run_not_found(self):
        """Test 404 for non-existent run"""
        response = requests.get(f"{BASE_URL}/api/stress/run/non_existent_run_id")
        assert response.status_code == 404
        
        print("Non-existent run correctly returns 404")
    
    def test_get_report(self):
        """Test getting condensed report with verdict"""
        response = requests.get(f"{BASE_URL}/api/stress/report/{self.run_id}")
        assert response.status_code == 200, f"Get report failed: {response.text}"
        
        data = response.json()
        
        # Verify report structure
        assert data["run_id"] == self.run_id
        assert "scenario" in data
        assert "mode" in data
        assert "verdict" in data
        assert data["verdict"] in EXPECTED_VERDICTS
        assert "verdict_details" in data
        assert "survived" in data
        
        # Verify performance section
        assert "performance" in data
        perf = data["performance"]
        assert "total_return" in perf
        assert "total_return_pct" in perf
        assert "max_drawdown_pct" in perf
        assert "recovery_bars" in perf
        assert "stress_sharpe" in perf
        assert "calmar" in perf
        assert "capital_preserved_pct" in perf
        
        # Verify governance section
        assert "governance" in data
        gov = data["governance"]
        assert "regime_switches" in gov
        assert "healing_events" in gov
        assert "demotions" in gov
        assert "overlay_reductions" in gov
        
        # Verify survival section
        assert "survival" in data
        surv = data["survival"]
        assert "strategies_survived" in surv
        assert "strategies_paused" in surv
        assert "strategies_disabled" in surv
        assert "family_collapses" in surv
        
        # Verify strategy results
        assert "strategy_results" in data
        
        print(f"Report - Verdict: {data['verdict']}, Survived: {data['survived']}")
    
    def test_get_report_not_found(self):
        """Test 404 for non-existent report"""
        response = requests.get(f"{BASE_URL}/api/stress/report/non_existent_run_id")
        assert response.status_code == 404
    
    def test_get_events(self):
        """Test getting timeline events for a run"""
        response = requests.get(f"{BASE_URL}/api/stress/events/{self.run_id}")
        assert response.status_code == 200, f"Get events failed: {response.text}"
        
        data = response.json()
        
        assert data["run_id"] == self.run_id
        assert "scenario" in data
        assert "total_events" in data
        assert "timeline" in data
        
        # Verify timeline event structure
        if data["timeline"]:
            event = data["timeline"][0]
            assert "bar" in event
            assert "event_type" in event
            assert "description" in event
            assert "severity" in event
            assert "details" in event
        
        # Should have at least crisis onset and trough events
        event_types = [e["event_type"] for e in data["timeline"]]
        print(f"Timeline has {data['total_events']} events: {set(event_types)}")
    
    def test_get_events_not_found(self):
        """Test 404 for non-existent events"""
        response = requests.get(f"{BASE_URL}/api/stress/events/non_existent_run_id")
        assert response.status_code == 404
    
    def test_get_metrics(self):
        """Test getting detailed stress metrics"""
        response = requests.get(f"{BASE_URL}/api/stress/metrics/{self.run_id}")
        assert response.status_code == 200, f"Get metrics failed: {response.text}"
        
        data = response.json()
        
        assert data["run_id"] == self.run_id
        assert "scenario" in data
        
        # Verify performance section
        assert "performance" in data
        perf = data["performance"]
        assert "total_return" in perf
        assert "total_return_pct" in perf
        assert "max_drawdown" in perf
        assert "max_drawdown_pct" in perf
        assert "recovery_bars" in perf
        assert "tail_loss" in perf
        assert "stress_sharpe" in perf
        assert "calmar" in perf
        
        # Verify governance section
        assert "governance" in data
        gov = data["governance"]
        assert "regime_switches" in gov
        assert "healing_events" in gov
        assert "demotions" in gov
        assert "overlay_reductions" in gov
        assert "blocked_signals" in gov
        assert "total_governance_events" in gov
        
        # Verify survival section
        assert "survival" in data
        surv = data["survival"]
        assert "strategies_survived" in surv
        assert "strategies_paused" in surv
        assert "strategies_disabled" in surv
        assert "capital_preserved_pct" in surv
        assert "family_collapses" in surv
        
        # Verify activity section
        assert "activity" in data
        act = data["activity"]
        assert "total_cycles" in act
        assert "total_trades" in act
        
        print(f"Metrics - Max DD: {perf['max_drawdown_pct']:.2%}, Tail Loss: {perf['tail_loss']:.4f}")
    
    def test_get_metrics_not_found(self):
        """Test 404 for non-existent metrics"""
        response = requests.get(f"{BASE_URL}/api/stress/metrics/non_existent_run_id")
        assert response.status_code == 404


class TestStressLabScenarioDetails:
    """Test specific scenario characteristics"""
    
    def test_scenario_equity_curve_produced(self):
        """Test that scenario produces equity curve data"""
        payload = {
            "scenario_id": "CRYPTO_2022_DELEVERAGE",
            "mode": "FULL_SYSTEM",
            "initial_capital": 100000.0
        }
        
        response = requests.post(f"{BASE_URL}/api/stress/run", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["equity_curve_points"] > 0
        assert data["equity_curve_points"] >= 40  # At least scenario bars
        
        print(f"Equity curve has {data['equity_curve_points']} points")
    
    def test_scenario_strategy_results_produced(self):
        """Test that scenario produces per-strategy results"""
        payload = {
            "scenario_id": "MACRO_1970_INFLATION",
            "mode": "FULL_SYSTEM"
        }
        
        response = requests.post(f"{BASE_URL}/api/stress/run", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["strategy_results"]) >= 5  # 5 default test strategies
        
        families = set(sr["family"] for sr in data["strategy_results"])
        expected_families = {"TREND", "BREAKOUT", "MOMENTUM", "REVERSAL", "CROSS_ASSET"}
        for fam in expected_families:
            assert fam in families, f"Missing family: {fam}"
        
        print(f"Strategy families: {families}")
    
    def test_scenario_timeline_events_produced(self):
        """Test that scenario produces timeline events"""
        payload = {
            "scenario_id": "EQUITY_2000_DOTCOM",
            "mode": "FULL_SYSTEM"
        }
        
        response = requests.post(f"{BASE_URL}/api/stress/run", json=payload)
        assert response.status_code == 200
        
        run_id = response.json()["run_id"]
        
        # Get timeline events
        events_response = requests.get(f"{BASE_URL}/api/stress/events/{run_id}")
        assert events_response.status_code == 200
        
        events_data = events_response.json()
        assert events_data["total_events"] > 0
        
        # Should have crisis onset event
        event_types = [e["event_type"] for e in events_data["timeline"]]
        assert "CRISIS_ONSET" in event_types, "Missing CRISIS_ONSET event"
        assert "CRISIS_TROUGH" in event_types, "Missing CRISIS_TROUGH event"
        
        print(f"Timeline events: {events_data['total_events']} - Types: {set(event_types)}")


class TestStressLabVerdictSystem:
    """Test verdict system"""
    
    def test_verdict_values(self):
        """Test that verdicts are from expected set"""
        # Run multiple scenarios and collect verdicts
        scenarios = ["EQUITY_2008_GFC", "CRYPTO_2020_MARCH", "MACRO_2022_DXY_SPIKE"]
        verdicts = []
        
        for scenario_id in scenarios:
            response = requests.post(f"{BASE_URL}/api/stress/run", json={
                "scenario_id": scenario_id,
                "mode": "FULL_SYSTEM"
            })
            assert response.status_code == 200
            data = response.json()
            verdicts.append(data["verdict"])
            assert data["verdict"] in EXPECTED_VERDICTS, f"Invalid verdict: {data['verdict']}"
        
        print(f"Verdicts for 3 scenarios: {verdicts}")
    
    def test_verdict_details_populated(self):
        """Test that verdict details contain meaningful information"""
        response = requests.post(f"{BASE_URL}/api/stress/run", json={
            "scenario_id": "EQUITY_2020_COVID",
            "mode": "FULL_SYSTEM"
        })
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["verdict_details"]) > 0
        
        # Verdict details should contain useful info
        details_text = " ".join(data["verdict_details"])
        print(f"Verdict: {data['verdict']}")
        print(f"Details: {data['verdict_details']}")


class TestStressLabModeComparison:
    """Test different run modes"""
    
    def test_mode_affects_results(self):
        """Test that different modes produce different results"""
        scenario = "EQUITY_2008_GFC"
        modes = ["CORE_ONLY", "FULL_SYSTEM", "FULL_STRESS_POLICIES"]
        results = {}
        
        for mode in modes:
            response = requests.post(f"{BASE_URL}/api/stress/run", json={
                "scenario_id": scenario,
                "mode": mode,
                "initial_capital": 100000.0
            })
            assert response.status_code == 200
            data = response.json()
            results[mode] = {
                "max_dd": data["metrics"]["max_drawdown_pct"],
                "capital_preserved": data["metrics"]["capital_preserved_pct"],
                "verdict": data["verdict"]
            }
        
        print(f"\nMode comparison for {scenario}:")
        for mode, r in results.items():
            print(f"  {mode}: DD={r['max_dd']:.2%}, Capital={r['capital_preserved']:.2%}, Verdict={r['verdict']}")


class TestStressLabIntegration:
    """Full integration tests"""
    
    def test_full_workflow(self):
        """Test complete stress lab workflow"""
        print("\n=== Stress Lab Full Workflow Test ===")
        
        # 1. Health check
        health_resp = requests.get(f"{BASE_URL}/api/stress/health")
        assert health_resp.status_code == 200
        health = health_resp.json()
        print(f"1. Health OK - {health['total_scenarios']} scenarios available")
        
        # 2. List scenarios
        scenarios_resp = requests.get(f"{BASE_URL}/api/stress/scenarios")
        assert scenarios_resp.status_code == 200
        scenarios = scenarios_resp.json()
        print(f"2. Listed {scenarios['total']} scenarios")
        
        # 3. Filter scenarios
        crypto_resp = requests.get(f"{BASE_URL}/api/stress/scenarios?asset_class=CRYPTO")
        assert crypto_resp.status_code == 200
        print(f"3. Filtered to {crypto_resp.json()['total']} CRYPTO scenarios")
        
        # 4. Run single scenario
        run_resp = requests.post(f"{BASE_URL}/api/stress/run", json={
            "scenario_id": "EQUITY_2008_GFC",
            "mode": "FULL_SYSTEM",
            "initial_capital": 100000.0
        })
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        run_id = run_data["run_id"]
        print(f"4. Single run completed - ID: {run_id}, Verdict: {run_data['verdict']}")
        
        # 5. Get run details
        details_resp = requests.get(f"{BASE_URL}/api/stress/run/{run_id}")
        assert details_resp.status_code == 200
        print(f"5. Run details retrieved")
        
        # 6. Get report
        report_resp = requests.get(f"{BASE_URL}/api/stress/report/{run_id}")
        assert report_resp.status_code == 200
        report = report_resp.json()
        print(f"6. Report - Verdict: {report['verdict']}, Survived: {report['survived']}")
        
        # 7. Get events
        events_resp = requests.get(f"{BASE_URL}/api/stress/events/{run_id}")
        assert events_resp.status_code == 200
        events = events_resp.json()
        print(f"7. Timeline has {events['total_events']} events")
        
        # 8. Get metrics
        metrics_resp = requests.get(f"{BASE_URL}/api/stress/metrics/{run_id}")
        assert metrics_resp.status_code == 200
        metrics = metrics_resp.json()
        print(f"8. Metrics - Max DD: {metrics['performance']['max_drawdown_pct']:.2%}")
        
        # 9. List runs
        runs_resp = requests.get(f"{BASE_URL}/api/stress/runs")
        assert runs_resp.status_code == 200
        runs = runs_resp.json()
        print(f"9. Total runs in system: {runs['total']}")
        
        # 10. Run batch (subset)
        batch_resp = requests.post(f"{BASE_URL}/api/stress/run-batch", json={
            "scenario_ids": ["CRYPTO_2020_MARCH", "MACRO_2022_DXY_SPIKE"],
            "mode": "FULL_SYSTEM"
        })
        assert batch_resp.status_code == 200
        batch = batch_resp.json()
        print(f"10. Batch completed - Survived: {batch['scenarios_survived']}/{batch['total_scenarios']}")
        
        print("\n=== Full Workflow Test PASSED ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
