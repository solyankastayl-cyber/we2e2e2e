#!/usr/bin/env python3
"""
T6 Strategy Runtime Engine Backend Test
======================================

Tests all T6 Strategy Runtime Engine endpoints:
- Health check
- Strategy management (list, get, enable/disable, pause/resume)
- Signal processing (TA, Manual, M-Brain)
- Configuration management

Backend URL: https://pattern-detector-9.preview.emergentagent.com
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

class T6StrategyTester:
    def __init__(self, base_url: str = "https://pattern-detector-9.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.tests_run = 0
        self.tests_passed = 0
        self.errors = []
        
        # Expected default strategies
        self.expected_strategies = [
            "TA_SIGNAL_FOLLOWER",
            "MANUAL_SIGNAL_EXECUTOR", 
            "MBRAIN_SIGNAL_ROUTER"
        ]
        
        print(f"[T6 Strategy Tester] Testing against: {self.base_url}")

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
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
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
        """Test strategy health endpoint"""
        success, response = self.run_test(
            "Strategy Health Check",
            "GET",
            "strategies/health",
            200
        )
        
        if success:
            print(f"   Health Status: {response.get('status', 'unknown')}")
            print(f"   Version: {response.get('version', 'unknown')}")
            
        return success

    def test_list_strategies(self) -> tuple[bool, List[Dict]]:
        """Test list all strategies"""
        success, response = self.run_test(
            "List All Strategies",
            "GET", 
            "strategies",
            200
        )
        
        strategies = []
        if success:
            strategies = response.get('strategies', [])
            count = response.get('count', 0)
            print(f"   Found {count} strategies")
            
            for strategy in strategies:
                strategy_id = strategy.get('strategy_id', 'unknown')
                name = strategy.get('name', 'unknown')
                status = strategy.get('state', {}).get('status', 'unknown')
                print(f"   - {strategy_id}: {name} ({status})")
                
        return success, strategies

    def test_get_active_strategies(self) -> tuple[bool, List[Dict]]:
        """Test get active strategies"""
        success, response = self.run_test(
            "Get Active Strategies",
            "GET",
            "strategies/active", 
            200
        )
        
        active_strategies = []
        if success:
            active_strategies = response.get('strategies', [])
            count = response.get('count', 0)
            print(f"   Found {count} active strategies")
            
            for strategy in active_strategies:
                strategy_id = strategy.get('strategy_id', 'unknown')
                name = strategy.get('name', 'unknown')
                print(f"   - Active: {strategy_id} ({name})")
                
        return success, active_strategies

    def test_get_strategy_by_id(self, strategy_id: str) -> bool:
        """Test get strategy by ID"""
        success, response = self.run_test(
            f"Get Strategy: {strategy_id}",
            "GET",
            f"strategies/{strategy_id}",
            200
        )
        
        if success:
            name = response.get('name', 'unknown')
            version = response.get('version', 'unknown')
            status = response.get('state', {}).get('status', 'unknown')
            print(f"   Strategy: {name} v{version} ({status})")
            
        return success

    def test_enable_strategy(self, strategy_id: str) -> bool:
        """Test enable strategy"""
        success, response = self.run_test(
            f"Enable Strategy: {strategy_id}",
            "POST",
            f"strategies/{strategy_id}/enable",
            200
        )
        
        if success:
            state = response.get('state', {})
            status = state.get('status', 'unknown')
            print(f"   New status: {status}")
            
        return success

    def test_disable_strategy(self, strategy_id: str) -> bool:
        """Test disable strategy"""
        success, response = self.run_test(
            f"Disable Strategy: {strategy_id}",
            "POST",
            f"strategies/{strategy_id}/disable",
            200
        )
        
        if success:
            state = response.get('state', {})
            status = state.get('status', 'unknown')
            print(f"   New status: {status}")
            
        return success

    def test_pause_strategy(self, strategy_id: str) -> bool:
        """Test pause strategy"""
        success, response = self.run_test(
            f"Pause Strategy: {strategy_id}",
            "POST",
            f"strategies/{strategy_id}/pause",
            200
        )
        
        if success:
            state = response.get('state', {})
            status = state.get('status', 'unknown')
            print(f"   New status: {status}")
            
        return success

    def test_resume_strategy(self, strategy_id: str) -> bool:
        """Test resume strategy"""
        success, response = self.run_test(
            f"Resume Strategy: {strategy_id}",
            "POST",
            f"strategies/{strategy_id}/resume",
            200
        )
        
        if success:
            state = response.get('state', {})
            status = state.get('status', 'unknown')
            print(f"   New status: {status}")
            
        return success

    def test_process_ta_signal(self) -> bool:
        """Test process TA signal"""
        signal_data = {
            "asset": "BTC",
            "bias": "BULLISH",
            "confidence": 0.75,
            "price": 45000.0,
            "stop_loss": 44000.0,
            "take_profit": 47000.0,
            "patterns": ["GOLDEN_CROSS"],
            "timeframe": "1h",
            "auto_execute": False
        }
        
        success, response = self.run_test(
            "Process TA Signal",
            "POST",
            "strategies/signal/ta",
            200,
            data=signal_data
        )
        
        if success:
            actions = response.get('actions', [])
            print(f"   Generated {len(actions)} actions")
            
            for action in actions:
                action_type = action.get('action', 'unknown')
                asset = action.get('asset', 'unknown')
                confidence = action.get('confidence', 0)
                strategy_id = action.get('strategy_id', 'unknown')
                print(f"   - {strategy_id}: {action_type} {asset} (confidence: {confidence:.0%})")
                
        return success

    def test_process_manual_signal(self) -> bool:
        """Test process manual signal"""
        signal_data = {
            "asset": "BTC",
            "action": "ENTER_LONG",
            "confidence": 1.0,
            "size_pct": 0.02,
            "price": 45000.0,
            "reason": "Manual entry signal",
            "auto_execute": False
        }
        
        success, response = self.run_test(
            "Process Manual Signal",
            "POST",
            "strategies/signal/manual",
            200,
            data=signal_data
        )
        
        if success:
            actions = response.get('actions', [])
            print(f"   Generated {len(actions)} actions")
            
            for action in actions:
                action_type = action.get('action', 'unknown')
                asset = action.get('asset', 'unknown')
                reason = action.get('reason', 'unknown')
                strategy_id = action.get('strategy_id', 'unknown')
                print(f"   - {strategy_id}: {action_type} {asset} ({reason})")
                
        return success

    def test_process_mbrain_signal(self) -> bool:
        """Test process M-Brain signal"""
        signal_data = {
            "asset": "BTC",
            "ensemble_action": "ENTER_LONG",
            "ensemble_confidence": 0.8,
            "module_votes": {
                "momentum_module": {"action": "ENTER_LONG", "confidence": 0.9},
                "mean_reversion_module": {"action": "ENTER_LONG", "confidence": 0.7},
                "volatility_module": {"action": "HOLD", "confidence": 0.5}
            },
            "auto_execute": False
        }
        
        success, response = self.run_test(
            "Process M-Brain Signal",
            "POST",
            "strategies/signal/mbrain",
            200,
            data=signal_data
        )
        
        if success:
            actions = response.get('actions', [])
            print(f"   Generated {len(actions)} actions")
            
            for action in actions:
                action_type = action.get('action', 'unknown')
                asset = action.get('asset', 'unknown')
                confidence = action.get('confidence', 0)
                strategy_id = action.get('strategy_id', 'unknown')
                print(f"   - {strategy_id}: {action_type} {asset} (confidence: {confidence:.0%})")
                
        return success

    def test_get_config(self) -> bool:
        """Test get strategy configuration"""
        success, response = self.run_test(
            "Get Strategy Config",
            "GET",
            "strategies/config",
            200
        )
        
        if success:
            multi_strategy = response.get('multi_strategy_mode', False)
            registered = response.get('registered_strategies', 0)
            active = response.get('active_strategies', 0)
            print(f"   Multi-strategy mode: {multi_strategy}")
            print(f"   Registered strategies: {registered}")
            print(f"   Active strategies: {active}")
            
        return success

    def test_set_multi_strategy_mode(self, enabled: bool) -> bool:
        """Test set multi-strategy mode"""
        config_data = {
            "multi_strategy_mode": enabled
        }
        
        success, response = self.run_test(
            f"Set Multi-Strategy Mode: {enabled}",
            "POST",
            "strategies/config/mode",
            200,
            data=config_data
        )
        
        if success:
            new_mode = response.get('multi_strategy_mode', False)
            print(f"   Multi-strategy mode set to: {new_mode}")
            
        return success

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive test suite"""
        print("=" * 60)
        print("T6 Strategy Runtime Engine - Comprehensive Test Suite")
        print("=" * 60)
        
        results = {
            "health_check": False,
            "list_strategies": False,
            "active_strategies": False,
            "strategy_management": [],
            "signal_processing": [],
            "configuration": [],
            "strategies_found": [],
            "active_strategies_found": []
        }
        
        # 1. Health Check
        print("\n📊 HEALTH CHECK")
        results["health_check"] = self.test_health_check()
        
        # 2. List Strategies
        print("\n📋 STRATEGY LISTING")
        success, strategies = self.test_list_strategies()
        results["list_strategies"] = success
        results["strategies_found"] = [s.get('strategy_id', 'unknown') for s in strategies]
        
        # 3. Active Strategies
        success, active_strategies = self.test_get_active_strategies()
        results["active_strategies"] = success
        results["active_strategies_found"] = [s.get('strategy_id', 'unknown') for s in active_strategies]
        
        # 4. Strategy Management Tests
        print("\n⚙️ STRATEGY MANAGEMENT")
        
        # Test with first available strategy
        test_strategy_id = None
        if strategies:
            test_strategy_id = strategies[0].get('strategy_id')
            
        if test_strategy_id:
            # Get strategy by ID
            success = self.test_get_strategy_by_id(test_strategy_id)
            results["strategy_management"].append(("get_by_id", success))
            
            # Test enable/disable cycle
            success = self.test_disable_strategy(test_strategy_id)
            results["strategy_management"].append(("disable", success))
            
            success = self.test_enable_strategy(test_strategy_id)
            results["strategy_management"].append(("enable", success))
            
            # Test pause/resume cycle
            success = self.test_pause_strategy(test_strategy_id)
            results["strategy_management"].append(("pause", success))
            
            success = self.test_resume_strategy(test_strategy_id)
            results["strategy_management"].append(("resume", success))
        else:
            print("⚠️ No strategies found for management testing")
        
        # 5. Signal Processing Tests
        print("\n📡 SIGNAL PROCESSING")
        
        success = self.test_process_ta_signal()
        results["signal_processing"].append(("ta_signal", success))
        
        success = self.test_process_manual_signal()
        results["signal_processing"].append(("manual_signal", success))
        
        success = self.test_process_mbrain_signal()
        results["signal_processing"].append(("mbrain_signal", success))
        
        # 6. Configuration Tests
        print("\n🔧 CONFIGURATION")
        
        success = self.test_get_config()
        results["configuration"].append(("get_config", success))
        
        # Test multi-strategy mode toggle
        success = self.test_set_multi_strategy_mode(True)
        results["configuration"].append(("enable_multi_strategy", success))
        
        success = self.test_set_multi_strategy_mode(False)
        results["configuration"].append(("disable_multi_strategy", success))
        
        return results

    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print test summary"""
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        print(f"📊 Tests Run: {self.tests_run}")
        print(f"✅ Tests Passed: {self.tests_passed}")
        print(f"❌ Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"📈 Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        # Strategy Analysis
        print(f"\n🎯 STRATEGY ANALYSIS")
        print(f"Expected strategies: {self.expected_strategies}")
        print(f"Found strategies: {results['strategies_found']}")
        print(f"Active strategies: {results['active_strategies_found']}")
        
        # Check if expected strategies are present
        missing_strategies = set(self.expected_strategies) - set(results['strategies_found'])
        if missing_strategies:
            print(f"⚠️ Missing strategies: {list(missing_strategies)}")
        else:
            print("✅ All expected strategies found")
        
        # Feature Test Results
        print(f"\n🔍 FEATURE TEST RESULTS")
        
        feature_groups = [
            ("Health Check", [results["health_check"]]),
            ("Strategy Listing", [results["list_strategies"], results["active_strategies"]]),
            ("Strategy Management", [success for _, success in results["strategy_management"]]),
            ("Signal Processing", [success for _, success in results["signal_processing"]]),
            ("Configuration", [success for _, success in results["configuration"]])
        ]
        
        for group_name, successes in feature_groups:
            if successes:
                passed = sum(successes)
                total = len(successes)
                status = "✅" if passed == total else "⚠️" if passed > 0 else "❌"
                print(f"{status} {group_name}: {passed}/{total}")
        
        # Error Details
        if self.errors:
            print(f"\n❌ ERROR DETAILS")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error['test']}: {error['error']}")
        
        print("\n" + "=" * 60)

def main():
    """Main test execution"""
    tester = T6StrategyTester()
    
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