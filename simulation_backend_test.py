#!/usr/bin/env python3
"""
S1 Trading Simulation Engine Backend Test
=========================================

Tests all S1 Trading Simulation Engine endpoints:
- Health check
- Simulation run management (create, list, get, start, run, pause, resume, stop)
- Step control (single step execution)
- State queries (state, positions, equity, fingerprint)
- Capital profiles validation (MICRO=$100, SMALL=$1000, MEDIUM=$10000, LARGE=$100000)

Backend URL: https://pattern-detector-9.preview.emergentagent.com
"""

import requests
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

class S1SimulationTester:
    def __init__(self, base_url: str = "https://pattern-detector-9.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.tests_run = 0
        self.tests_passed = 0
        self.errors = []
        
        # Capital profiles to test
        self.capital_profiles = {
            "MICRO": 100.0,
            "SMALL": 1000.0,
            "MEDIUM": 10000.0,
            "LARGE": 100000.0
        }
        
        # Test run IDs for lifecycle testing
        self.test_run_ids = []
        
        print(f"[S1 Simulation Tester] Testing against: {self.base_url}")

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/api/trading/{endpoint}"
        
        if headers is None:
            headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   {method} {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=15)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {"raw_response": response.text}
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                print(f"❌ Failed - {error_msg}")
                print(f"   Response: {response.text[:200]}...")
                self.errors.append({
                    "test": name,
                    "error": error_msg,
                    "response": response.text[:500]
                })
                try:
                    return False, response.json()
                except:
                    return False, {"error": response.text}

        except Exception as e:
            error_msg = f"Exception: {str(e)}"
            print(f"❌ Failed - {error_msg}")
            self.errors.append({
                "test": name,
                "error": error_msg
            })
            return False, {"error": str(e)}

    def test_health_check(self) -> bool:
        """Test simulation health endpoint"""
        success, response = self.run_test(
            "Simulation Health Check",
            "GET",
            "simulation/health",
            200
        )
        
        if success:
            print(f"   Health Status: {response.get('status', 'unknown')}")
            print(f"   Version: {response.get('version', 'unknown')}")
            print(f"   Active Runs: {response.get('active_runs', 0)}")
            
        return success

    def test_create_simulation(self, capital_profile: str, strategy_id: str = "TEST_STRATEGY") -> tuple[bool, Optional[str]]:
        """Test create simulation with specific capital profile"""
        simulation_data = {
            "strategy_id": strategy_id,
            "asset": "BTCUSDT",
            "start_date": "2022-01-01",
            "end_date": "2023-01-01",
            "capital_profile": capital_profile,
            "market_type": "SPOT",
            "timeframe": "1D",
            "strategy_version": "1.0",
            "risk_profile_id": "default_risk"
        }
        
        success, response = self.run_test(
            f"Create Simulation ({capital_profile})",
            "POST",
            "simulation/runs",
            200,
            data=simulation_data
        )
        
        run_id = None
        if success:
            run_data = response.get('run', {})
            run_id = run_data.get('run_id')
            initial_capital = run_data.get('initial_capital_usd', 0)
            expected_capital = self.capital_profiles.get(capital_profile, 0)
            
            print(f"   Run ID: {run_id}")
            print(f"   Initial Capital: ${initial_capital}")
            print(f"   Expected Capital: ${expected_capital}")
            
            # Validate capital profile
            if abs(initial_capital - expected_capital) < 0.01:
                print(f"   ✅ Capital profile {capital_profile} validated")
            else:
                print(f"   ❌ Capital mismatch for {capital_profile}")
                success = False
            
            if run_id:
                self.test_run_ids.append(run_id)
                
        return success, run_id

    def test_list_simulations(self) -> tuple[bool, List[Dict]]:
        """Test list all simulations"""
        success, response = self.run_test(
            "List All Simulations",
            "GET", 
            "simulation/runs",
            200
        )
        
        runs = []
        if success:
            runs = response.get('runs', [])
            count = response.get('count', 0)
            print(f"   Found {count} simulations")
            
            for run in runs[:3]:  # Show first 3
                run_id = run.get('run_id', 'unknown')
                strategy_id = run.get('strategy_id', 'unknown')
                status = run.get('status', 'unknown')
                capital = run.get('initial_capital_usd', 0)
                print(f"   - {run_id[:8]}...: {strategy_id} ({status}) ${capital}")
                
        return success, runs

    def test_get_simulation(self, run_id: str) -> bool:
        """Test get simulation details"""
        success, response = self.run_test(
            f"Get Simulation Details",
            "GET",
            f"simulation/runs/{run_id}",
            200
        )
        
        if success:
            run_data = response.get('run', {})
            state_data = response.get('state', {})
            fingerprint_data = response.get('fingerprint', {})
            
            strategy_id = run_data.get('strategy_id', 'unknown')
            status = run_data.get('status', 'unknown')
            asset = run_data.get('asset', 'unknown')
            
            print(f"   Strategy: {strategy_id}")
            print(f"   Status: {status}")
            print(f"   Asset: {asset}")
            
            if state_data:
                equity = state_data.get('equity_usd', 0)
                step_index = state_data.get('current_step_index', 0)
                print(f"   Current Equity: ${equity}")
                print(f"   Step Index: {step_index}")
            
            if fingerprint_data:
                config_hash = fingerprint_data.get('config_hash', 'none')
                print(f"   Config Hash: {config_hash}")
                
        return success

    def test_start_simulation(self, run_id: str) -> bool:
        """Test start simulation (freeze config)"""
        start_data = {
            "strategy_config": {"test_param": "test_value"},
            "risk_config": {"max_risk": 0.02}
        }
        
        success, response = self.run_test(
            f"Start Simulation",
            "POST",
            f"simulation/runs/{run_id}/start",
            200,
            data=start_data
        )
        
        if success:
            new_status = response.get('status', 'unknown')
            print(f"   New Status: {new_status}")
            
        return success

    def test_run_full_simulation(self, run_id: str) -> bool:
        """Test run complete simulation"""
        run_data = {
            "strategy_config": {"test_param": "test_value"},
            "risk_config": {"max_risk": 0.02}
        }
        
        success, response = self.run_test(
            f"Run Full Simulation",
            "POST",
            f"simulation/runs/{run_id}/run",
            200,
            data=run_data
        )
        
        if success:
            run_result = response.get('run', {})
            state_result = response.get('state', {})
            total_steps = response.get('total_steps', 0)
            
            final_status = run_result.get('status', 'unknown')
            final_equity = run_result.get('final_equity_usd', 0)
            
            print(f"   Final Status: {final_status}")
            print(f"   Final Equity: ${final_equity}")
            print(f"   Total Steps: {total_steps}")
            
            if state_result:
                current_equity = state_result.get('equity_usd', 0)
                max_drawdown = state_result.get('max_drawdown_pct', 0)
                print(f"   Current Equity: ${current_equity}")
                print(f"   Max Drawdown: {max_drawdown:.2%}")
                
        return success

    def test_step_simulation(self, run_id: str) -> bool:
        """Test single step execution"""
        success, response = self.run_test(
            f"Step Simulation",
            "POST",
            f"simulation/runs/{run_id}/step",
            200
        )
        
        if success:
            finished = response.get('finished', False)
            step_data = response.get('step', {})
            tick_data = response.get('tick', {})
            
            print(f"   Finished: {finished}")
            
            if step_data:
                step_index = step_data.get('step_index', 0)
                timestamp = step_data.get('timestamp', 'unknown')
                print(f"   Step: {step_index} at {timestamp}")
            
            if tick_data:
                asset = tick_data.get('asset', 'unknown')
                candle = tick_data.get('candle', {})
                if candle:
                    close_price = candle.get('close', 0)
                    print(f"   Tick: {asset} @ ${close_price}")
                
        return success

    def test_pause_simulation(self, run_id: str) -> bool:
        """Test pause simulation"""
        success, response = self.run_test(
            f"Pause Simulation",
            "POST",
            f"simulation/runs/{run_id}/pause",
            200
        )
        
        if success:
            new_status = response.get('status', 'unknown')
            print(f"   New Status: {new_status}")
            
        return success

    def test_resume_simulation(self, run_id: str) -> bool:
        """Test resume simulation"""
        success, response = self.run_test(
            f"Resume Simulation",
            "POST",
            f"simulation/runs/{run_id}/resume",
            200
        )
        
        if success:
            new_status = response.get('status', 'unknown')
            print(f"   New Status: {new_status}")
            
        return success

    def test_stop_simulation(self, run_id: str) -> bool:
        """Test stop simulation"""
        success, response = self.run_test(
            f"Stop Simulation",
            "POST",
            f"simulation/runs/{run_id}/stop",
            200
        )
        
        if success:
            run_data = response.get('run', {})
            state_data = response.get('state', {})
            
            if run_data:
                final_status = run_data.get('status', 'unknown')
                final_equity = run_data.get('final_equity_usd', 0)
                print(f"   Final Status: {final_status}")
                print(f"   Final Equity: ${final_equity}")
                
        return success

    def test_get_simulation_state(self, run_id: str) -> bool:
        """Test get simulation state"""
        success, response = self.run_test(
            f"Get Simulation State",
            "GET",
            f"simulation/runs/{run_id}/state",
            200
        )
        
        if success:
            equity = response.get('equity_usd', 0)
            cash = response.get('cash_usd', 0)
            step_index = response.get('current_step_index', 0)
            timestamp = response.get('current_timestamp', 'unknown')
            
            print(f"   Equity: ${equity}")
            print(f"   Cash: ${cash}")
            print(f"   Step: {step_index} at {timestamp}")
            
        return success

    def test_get_positions(self, run_id: str) -> bool:
        """Test get simulation positions"""
        success, response = self.run_test(
            f"Get Simulation Positions",
            "GET",
            f"simulation/runs/{run_id}/positions",
            200
        )
        
        if success:
            positions = response.get('positions', [])
            count = response.get('count', 0)
            
            print(f"   Positions: {count}")
            
            for pos in positions:
                asset = pos.get('asset', 'unknown')
                side = pos.get('side', 'unknown')
                size = pos.get('size', 0)
                unrealized_pnl = pos.get('unrealized_pnl', 0)
                print(f"   - {asset}: {side} {size} (PnL: ${unrealized_pnl})")
                
        return success

    def test_get_equity_history(self, run_id: str) -> bool:
        """Test get equity curve"""
        success, response = self.run_test(
            f"Get Equity History",
            "GET",
            f"simulation/runs/{run_id}/equity",
            200
        )
        
        if success:
            history = response.get('equity_history', [])
            points = response.get('points', 0)
            
            print(f"   Equity Points: {points}")
            
            if history:
                first_point = history[0]
                last_point = history[-1]
                
                first_equity = first_point.get('equity_usd', 0)
                last_equity = last_point.get('equity_usd', 0)
                
                print(f"   First: ${first_equity}")
                print(f"   Last: ${last_equity}")
                
        return success

    def test_get_fingerprint(self, run_id: str) -> bool:
        """Test get simulation fingerprint"""
        success, response = self.run_test(
            f"Get Simulation Fingerprint",
            "GET",
            f"simulation/runs/{run_id}/fingerprint",
            200
        )
        
        if success:
            strategy_id = response.get('strategy_id', 'unknown')
            asset = response.get('asset', 'unknown')
            config_hash = response.get('config_hash', 'none')
            dataset_checksum = response.get('dataset_checksum', 'none')
            
            print(f"   Strategy: {strategy_id}")
            print(f"   Asset: {asset}")
            print(f"   Config Hash: {config_hash}")
            print(f"   Dataset Checksum: {dataset_checksum}")
            
        return success

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test suite"""
        print("=" * 70)
        print("S1 Trading Simulation Engine - Comprehensive Test Suite")
        print("=" * 70)
        
        results = {
            "health_check": False,
            "capital_profiles": {},
            "simulation_management": [],
            "step_control": [],
            "state_queries": [],
            "created_runs": [],
            "lifecycle_test_run": None
        }
        
        # 1. Health Check
        print("\n📊 HEALTH CHECK")
        results["health_check"] = self.test_health_check()
        
        # 2. Capital Profile Tests
        print("\n💰 CAPITAL PROFILE VALIDATION")
        for profile in self.capital_profiles.keys():
            success, run_id = self.test_create_simulation(profile)
            results["capital_profiles"][profile] = success
            if run_id:
                results["created_runs"].append(run_id)
        
        # 3. List Simulations
        print("\n📋 SIMULATION LISTING")
        success, runs = self.test_list_simulations()
        results["simulation_management"].append(("list_simulations", success))
        
        # 4. Simulation Lifecycle Test (using first created run)
        if results["created_runs"]:
            test_run_id = results["created_runs"][0]
            results["lifecycle_test_run"] = test_run_id
            
            print(f"\n🔄 SIMULATION LIFECYCLE TEST (Run: {test_run_id[:8]}...)")
            
            # Get simulation details
            success = self.test_get_simulation(test_run_id)
            results["simulation_management"].append(("get_simulation", success))
            
            # Start simulation
            success = self.test_start_simulation(test_run_id)
            results["simulation_management"].append(("start_simulation", success))
            
            # Single step test
            success = self.test_step_simulation(test_run_id)
            results["step_control"].append(("step_simulation", success))
            
            # Pause/Resume test
            success = self.test_pause_simulation(test_run_id)
            results["simulation_management"].append(("pause_simulation", success))
            
            success = self.test_resume_simulation(test_run_id)
            results["simulation_management"].append(("resume_simulation", success))
            
            # State queries
            success = self.test_get_simulation_state(test_run_id)
            results["state_queries"].append(("get_state", success))
            
            success = self.test_get_positions(test_run_id)
            results["state_queries"].append(("get_positions", success))
            
            success = self.test_get_equity_history(test_run_id)
            results["state_queries"].append(("get_equity_history", success))
            
            success = self.test_get_fingerprint(test_run_id)
            results["state_queries"].append(("get_fingerprint", success))
            
            # Stop simulation
            success = self.test_stop_simulation(test_run_id)
            results["simulation_management"].append(("stop_simulation", success))
        
        # 5. Full Simulation Test (using second created run if available)
        if len(results["created_runs"]) > 1:
            full_test_run_id = results["created_runs"][1]
            
            print(f"\n🚀 FULL SIMULATION TEST (Run: {full_test_run_id[:8]}...)")
            
            success = self.test_run_full_simulation(full_test_run_id)
            results["simulation_management"].append(("run_full_simulation", success))
            
            # Test state after completion
            success = self.test_get_simulation_state(full_test_run_id)
            results["state_queries"].append(("get_state_after_completion", success))
        
        return results

    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print test summary"""
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)
        
        print(f"📊 Tests Run: {self.tests_run}")
        print(f"✅ Tests Passed: {self.tests_passed}")
        print(f"❌ Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"📈 Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        # Capital Profile Analysis
        print(f"\n💰 CAPITAL PROFILE VALIDATION")
        for profile, success in results["capital_profiles"].items():
            expected_capital = self.capital_profiles[profile]
            status = "✅" if success else "❌"
            print(f"{status} {profile}: ${expected_capital}")
        
        # Feature Test Results
        print(f"\n🔍 FEATURE TEST RESULTS")
        
        feature_groups = [
            ("Health Check", [results["health_check"]]),
            ("Capital Profiles", list(results["capital_profiles"].values())),
            ("Simulation Management", [success for _, success in results["simulation_management"]]),
            ("Step Control", [success for _, success in results["step_control"]]),
            ("State Queries", [success for _, success in results["state_queries"]])
        ]
        
        for group_name, successes in feature_groups:
            if successes:
                passed = sum(successes)
                total = len(successes)
                status = "✅" if passed == total else "⚠️" if passed > 0 else "❌"
                print(f"{status} {group_name}: {passed}/{total}")
        
        # Created Runs
        print(f"\n🆔 CREATED SIMULATION RUNS")
        for i, run_id in enumerate(results["created_runs"], 1):
            print(f"{i}. {run_id}")
        
        # Error Details
        if self.errors:
            print(f"\n❌ ERROR DETAILS")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error['test']}: {error['error']}")
        
        print("\n" + "=" * 70)

def main():
    """Main test execution"""
    tester = S1SimulationTester()
    
    try:
        results = tester.run_comprehensive_test()
        tester.print_summary(results)
        
        # Return appropriate exit code
        success_rate = tester.tests_passed / tester.tests_run if tester.tests_run > 0 else 0
        
        if success_rate >= 0.8:  # 80% success rate threshold
            print("🎉 Test suite PASSED (≥80% success rate)")
            return 0
        else:
            print("💥 Test suite FAILED (<80% success rate)")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())