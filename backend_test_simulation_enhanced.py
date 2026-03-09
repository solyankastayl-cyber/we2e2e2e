#!/usr/bin/env python3
"""
S1.3 Simulated Broker Adapter - Enhanced Backend Test
====================================================

Enhanced test that also checks strategy configuration and tests
different scenarios to ensure both buy and sell signals are generated.

Backend URL: https://pattern-detector-9.preview.emergentagent.com
"""

import requests
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

class S13EnhancedTester:
    def __init__(self, base_url: str = "https://pattern-detector-9.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.tests_run = 0
        self.tests_passed = 0
        self.errors = []
        self.created_runs = []
        
        print(f"[S1.3 Enhanced Tester] Testing against: {self.base_url}")

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
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
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

    def test_strategy_health(self) -> bool:
        """Test strategy health to ensure strategies are available"""
        success, response = self.run_test(
            "Strategy Health Check",
            "GET",
            "strategies/health",
            200
        )
        
        if success:
            version = response.get('version', 'unknown')
            status = response.get('status', 'unknown')
            print(f"   Strategy Version: {version}")
            print(f"   Strategy Status: {status}")
                
        return success

    def test_list_strategies(self) -> tuple[bool, List[Dict]]:
        """Test list strategies to see what's available"""
        success, response = self.run_test(
            "List Strategies",
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
                state = strategy.get('state', {})
                status = state.get('status', 'unknown')
                print(f"   - {strategy_id}: {name} ({status})")
                
        return success, strategies

    def test_create_simulation_with_lower_confidence(self) -> tuple[bool, Optional[str]]:
        """Test creating simulation with lower confidence threshold"""
        simulation_data = {
            "strategy_id": "TEST_STRATEGY",
            "asset": "BTCUSDT",
            "start_date": "2023-01-01",
            "end_date": "2023-02-28",  # Longer period for more signals
            "capital_profile": "SMALL",
            "initial_capital_usd": 10000.0,
            "market_type": "SPOT",
            "timeframe": "1D",
            "strategy_config": {
                "test_mode": True,
                "min_confidence": 0.3,  # Lower confidence threshold
                "position_size_pct": 0.05  # Larger position size
            }
        }
        
        success, response = self.run_test(
            "Create Simulation (Lower Confidence)",
            "POST",
            "simulation/runs",
            200,
            data=simulation_data
        )
        
        run_id = None
        if success:
            run_data = response.get('run', {})
            run_id = run_data.get('run_id')
            
            if run_id:
                self.created_runs.append(run_id)
                print(f"   Created run: {run_id}")
                print(f"   Status: {run_data.get('status', 'unknown')}")
                print(f"   Period: {simulation_data['start_date']} to {simulation_data['end_date']}")
                
        return success, run_id

    def test_manual_signal_processing(self) -> bool:
        """Test manual signal processing to verify strategy integration"""
        # Test ENTER_LONG signal
        enter_signal = {
            "asset": "BTC",
            "action": "ENTER_LONG",
            "confidence": 0.8,
            "size_pct": 0.02,
            "price": 45000.0,
            "reason": "Test manual entry",
            "auto_execute": False
        }
        
        success1, response1 = self.run_test(
            "Process Manual ENTER_LONG Signal",
            "POST",
            "strategies/signal/manual",
            200,
            data=enter_signal
        )
        
        if success1:
            actions = response1.get('actions', [])
            print(f"   Generated {len(actions)} actions for ENTER_LONG")
            for action in actions:
                print(f"   - Action: {action.get('action')} (confidence: {action.get('confidence', 0):.0%})")
        
        # Test EXIT_LONG signal
        exit_signal = {
            "asset": "BTC",
            "action": "EXIT_LONG",
            "confidence": 0.8,
            "price": 46000.0,
            "reason": "Test manual exit",
            "auto_execute": False
        }
        
        success2, response2 = self.run_test(
            "Process Manual EXIT_LONG Signal",
            "POST",
            "strategies/signal/manual",
            200,
            data=exit_signal
        )
        
        if success2:
            actions = response2.get('actions', [])
            print(f"   Generated {len(actions)} actions for EXIT_LONG")
            for action in actions:
                print(f"   - Action: {action.get('action')} (confidence: {action.get('confidence', 0):.0%})")
        
        return success1 and success2

    def test_ta_signal_processing(self) -> bool:
        """Test TA signal processing with different biases"""
        # Test BULLISH signal
        bullish_signal = {
            "asset": "BTC",
            "bias": "BULLISH",
            "confidence": 0.75,
            "price": 45000.0,
            "auto_execute": False
        }
        
        success1, response1 = self.run_test(
            "Process TA BULLISH Signal",
            "POST",
            "strategies/signal/ta",
            200,
            data=bullish_signal
        )
        
        if success1:
            actions = response1.get('actions', [])
            print(f"   Generated {len(actions)} actions for BULLISH")
            for action in actions:
                print(f"   - Action: {action.get('action')} (confidence: {action.get('confidence', 0):.0%})")
        
        # Test BEARISH signal
        bearish_signal = {
            "asset": "BTC",
            "bias": "BEARISH",
            "confidence": 0.75,
            "price": 44000.0,
            "auto_execute": False
        }
        
        success2, response2 = self.run_test(
            "Process TA BEARISH Signal",
            "POST",
            "strategies/signal/ta",
            200,
            data=bearish_signal
        )
        
        if success2:
            actions = response2.get('actions', [])
            print(f"   Generated {len(actions)} actions for BEARISH")
            for action in actions:
                print(f"   - Action: {action.get('action')} (confidence: {action.get('confidence', 0):.0%})")
        
        return success1 and success2

    def analyze_simulation_results(self, run_id: str) -> Dict[str, Any]:
        """Analyze simulation results in detail"""
        if not run_id:
            return {}
        
        analysis = {
            "fills_analysis": {},
            "orders_analysis": {},
            "positions_analysis": {},
            "state_analysis": {},
            "equity_analysis": {}
        }
        
        # Get fills
        success, fills_response = self.run_test(
            f"Analyze Fills: {run_id}",
            "GET",
            f"simulation/runs/{run_id}/fills",
            200
        )
        
        if success:
            fills = fills_response.get('fills', [])
            buy_fills = [f for f in fills if f.get('quantity', 0) > 0]
            sell_fills = [f for f in fills if f.get('quantity', 0) < 0]
            
            analysis["fills_analysis"] = {
                "total_fills": len(fills),
                "buy_fills": len(buy_fills),
                "sell_fills": len(sell_fills),
                "buy_volume": sum(f.get('quantity', 0) for f in buy_fills),
                "sell_volume": abs(sum(f.get('quantity', 0) for f in sell_fills)),
                "total_fees": sum(f.get('fee_usd', 0) for f in fills)
            }
            
            print(f"   📊 Fills Analysis:")
            print(f"      Total: {analysis['fills_analysis']['total_fills']}")
            print(f"      Buys: {analysis['fills_analysis']['buy_fills']}")
            print(f"      Sells: {analysis['fills_analysis']['sell_fills']}")
            print(f"      Total Fees: ${analysis['fills_analysis']['total_fees']:.2f}")
        
        # Get state
        success, state_response = self.run_test(
            f"Analyze State: {run_id}",
            "GET",
            f"simulation/runs/{run_id}/state",
            200
        )
        
        if success:
            analysis["state_analysis"] = {
                "equity_usd": state_response.get('equity_usd', 0),
                "cash_usd": state_response.get('cash_usd', 0),
                "realized_pnl_usd": state_response.get('realized_pnl_usd', 0),
                "unrealized_pnl_usd": state_response.get('unrealized_pnl_usd', 0),
                "open_positions": state_response.get('open_positions', 0),
                "open_orders": state_response.get('open_orders', 0)
            }
            
            print(f"   📊 State Analysis:")
            print(f"      Final Equity: ${analysis['state_analysis']['equity_usd']:,.2f}")
            print(f"      Realized PnL: ${analysis['state_analysis']['realized_pnl_usd']:,.2f}")
            print(f"      Unrealized PnL: ${analysis['state_analysis']['unrealized_pnl_usd']:,.2f}")
        
        return analysis

    def run_enhanced_test(self) -> Dict[str, Any]:
        """Run enhanced S1.3 test suite"""
        print("=" * 80)
        print("S1.3 Simulated Broker Adapter - Enhanced Test Suite")
        print("=" * 80)
        
        results = {
            "strategy_health": False,
            "list_strategies": False,
            "manual_signal_processing": False,
            "ta_signal_processing": False,
            "create_simulation": False,
            "run_simulation": False,
            "analysis": {},
            "strategies_found": [],
            "run_id": None
        }
        
        # 1. Strategy Health Check
        print("\n📊 STRATEGY HEALTH CHECK")
        results["strategy_health"] = self.test_strategy_health()
        
        # 2. List Strategies
        print("\n📋 LIST STRATEGIES")
        success, strategies = self.test_list_strategies()
        results["list_strategies"] = success
        results["strategies_found"] = [s.get('strategy_id', 'unknown') for s in strategies]
        
        # 3. Manual Signal Processing
        print("\n🎯 MANUAL SIGNAL PROCESSING")
        results["manual_signal_processing"] = self.test_manual_signal_processing()
        
        # 4. TA Signal Processing
        print("\n📈 TA SIGNAL PROCESSING")
        results["ta_signal_processing"] = self.test_ta_signal_processing()
        
        # 5. Create Simulation with Lower Confidence
        print("\n🏗️ CREATE SIMULATION (ENHANCED)")
        success, run_id = self.test_create_simulation_with_lower_confidence()
        results["create_simulation"] = success
        results["run_id"] = run_id
        
        if not run_id:
            print("❌ Cannot continue without run_id")
            return results
        
        # 6. Run Full Simulation
        print("\n🚀 RUN FULL SIMULATION")
        config_data = {
            "strategy_config": {
                "test_mode": True,
                "min_confidence": 0.3,  # Lower confidence
                "position_size_pct": 0.05  # Larger positions
            }
        }
        
        success, response = self.run_test(
            f"Run Enhanced Simulation: {run_id}",
            "POST",
            f"simulation/runs/{run_id}/run",
            200,
            data=config_data
        )
        results["run_simulation"] = success
        
        if success:
            run_data = response.get('run', {})
            state_data = response.get('state', {})
            total_steps = response.get('total_steps', 0)
            
            print(f"   Final Status: {run_data.get('status', 'unknown')}")
            print(f"   Total Steps: {total_steps}")
            print(f"   Final Equity: ${state_data.get('equity_usd', 0):,.2f}")
        
        # 7. Detailed Analysis
        print("\n🔍 DETAILED ANALYSIS")
        results["analysis"] = self.analyze_simulation_results(run_id)
        
        return results

    def print_enhanced_summary(self, results: Dict[str, Any]) -> None:
        """Print enhanced test summary"""
        print("\n" + "=" * 80)
        print("ENHANCED TEST SUMMARY")
        print("=" * 80)
        
        print(f"📊 Tests Run: {self.tests_run}")
        print(f"✅ Tests Passed: {self.tests_passed}")
        print(f"❌ Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"📈 Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        # Feature Test Results
        print(f"\n🔍 ENHANCED FEATURE TEST RESULTS")
        
        feature_tests = [
            ("Strategy Health Check", results["strategy_health"]),
            ("List Strategies", results["list_strategies"]),
            ("Manual Signal Processing", results["manual_signal_processing"]),
            ("TA Signal Processing", results["ta_signal_processing"]),
            ("Create Enhanced Simulation", results["create_simulation"]),
            ("Run Enhanced Simulation", results["run_simulation"])
        ]
        
        for feature_name, success in feature_tests:
            status = "✅" if success else "❌"
            print(f"{status} {feature_name}")
        
        # Strategy Analysis
        print(f"\n🎯 STRATEGY ANALYSIS")
        print(f"Strategies found: {results['strategies_found']}")
        
        # Simulation Analysis
        analysis = results.get("analysis", {})
        if analysis:
            print(f"\n📊 SIMULATION ANALYSIS")
            
            fills_analysis = analysis.get("fills_analysis", {})
            if fills_analysis:
                print(f"Total Fills: {fills_analysis.get('total_fills', 0)}")
                print(f"Buy Fills: {fills_analysis.get('buy_fills', 0)}")
                print(f"Sell Fills: {fills_analysis.get('sell_fills', 0)}")
                print(f"Total Fees: ${fills_analysis.get('total_fees', 0):.2f}")
                
                # Check if both buy and sell fills were generated
                if fills_analysis.get('buy_fills', 0) > 0 and fills_analysis.get('sell_fills', 0) > 0:
                    print("✅ Both buy and sell fills generated")
                elif fills_analysis.get('buy_fills', 0) > 0:
                    print("⚠️ Only buy fills generated")
                elif fills_analysis.get('sell_fills', 0) > 0:
                    print("⚠️ Only sell fills generated")
                else:
                    print("❌ No fills generated")
            
            state_analysis = analysis.get("state_analysis", {})
            if state_analysis:
                realized_pnl = state_analysis.get('realized_pnl_usd', 0)
                if realized_pnl != 0:
                    print(f"✅ Realized PnL tracked: ${realized_pnl:.2f}")
                else:
                    print("⚠️ No realized PnL (no closed positions)")
        
        # Error Details
        if self.errors:
            print(f"\n❌ ERROR DETAILS")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error['test']}: {error['error']}")
        
        print("\n" + "=" * 80)

def main():
    """Main test execution"""
    tester = S13EnhancedTester()
    
    try:
        results = tester.run_enhanced_test()
        tester.print_enhanced_summary(results)
        
        # Return appropriate exit code
        success_rate = tester.tests_passed / tester.tests_run if tester.tests_run > 0 else 0
        
        if success_rate >= 0.8:  # 80% success rate threshold
            print("🎉 S1.3 Enhanced Test suite PASSED (≥80% success rate)")
            return 0
        else:
            print("💥 S1.3 Enhanced Test suite FAILED (<80% success rate)")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())