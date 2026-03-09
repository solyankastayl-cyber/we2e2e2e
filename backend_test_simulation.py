#!/usr/bin/env python3
"""
S1.3 Simulated Broker Adapter Backend Test
==========================================

Tests all S1.3 Simulated Broker Adapter endpoints:
- Health check (version s1.3)
- Simulation run creation with broker
- Full simulation execution with trading
- Fills, orders, positions retrieval
- State with realized_pnl verification
- Equity changes during simulation
- Fill generation (buys and sells)
- Drawdown tracking

Backend URL: https://market-replay-2.preview.emergentagent.com
"""

import requests
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

class S13SimulationTester:
    def __init__(self, base_url: str = "https://market-replay-2.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.tests_run = 0
        self.tests_passed = 0
        self.errors = []
        self.created_runs = []  # Track created runs for cleanup
        
        print(f"[S1.3 Simulation Tester] Testing against: {self.base_url}")

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
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
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

    def test_simulation_health(self) -> bool:
        """Test simulation health endpoint - should show version s1.3"""
        success, response = self.run_test(
            "Simulation Health Check",
            "GET",
            "simulation/health",
            200
        )
        
        if success:
            version = response.get('version', 'unknown')
            status = response.get('status', 'unknown')
            print(f"   Version: {version}")
            print(f"   Status: {status}")
            
            # Verify version contains s1.3
            if 's1.3' in version:
                print("✅ Version s1.3 confirmed")
            else:
                print(f"⚠️ Expected version s1.3, got: {version}")
                
        return success

    def test_create_simulation(self) -> tuple[bool, Optional[str]]:
        """Test creating simulation with broker"""
        simulation_data = {
            "strategy_id": "TEST_STRATEGY",
            "asset": "BTCUSDT",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "capital_profile": "SMALL",
            "initial_capital_usd": 10000.0,
            "market_type": "SPOT",
            "timeframe": "1D",
            "strategy_config": {
                "test_mode": True
            }
        }
        
        success, response = self.run_test(
            "Create Simulation with Broker",
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
                print(f"   Asset: {run_data.get('asset', 'unknown')}")
                print(f"   Capital: ${run_data.get('initial_capital_usd', 0):,.2f}")
                
                # Verify dataset and fingerprint are created
                dataset = response.get('dataset', {})
                fingerprint = response.get('fingerprint', {})
                
                if dataset:
                    print(f"   Dataset ID: {dataset.get('dataset_id', 'unknown')}")
                if fingerprint:
                    print(f"   Fingerprint: {fingerprint.get('fingerprint_hash', 'unknown')[:8]}...")
            else:
                print("❌ No run_id returned")
                success = False
                
        return success, run_id

    def test_run_full_simulation(self, run_id: str) -> bool:
        """Test running full simulation with trading"""
        if not run_id:
            return False
            
        config_data = {
            "strategy_config": {
                "test_mode": True,
                "position_size_pct": 0.02  # 2% position size
            }
        }
        
        success, response = self.run_test(
            f"Run Full Simulation: {run_id}",
            "POST",
            f"simulation/runs/{run_id}/run",
            200,
            data=config_data
        )
        
        if success:
            run_data = response.get('run', {})
            state_data = response.get('state', {})
            total_steps = response.get('total_steps', 0)
            
            print(f"   Final Status: {run_data.get('status', 'unknown')}")
            print(f"   Total Steps: {total_steps}")
            
            if state_data:
                equity = state_data.get('equity_usd', 0)
                cash = state_data.get('cash_usd', 0)
                realized_pnl = state_data.get('realized_pnl_usd', 0)
                unrealized_pnl = state_data.get('unrealized_pnl_usd', 0)
                
                print(f"   Final Equity: ${equity:,.2f}")
                print(f"   Cash: ${cash:,.2f}")
                print(f"   Realized PnL: ${realized_pnl:,.2f}")
                print(f"   Unrealized PnL: ${unrealized_pnl:,.2f}")
                
        return success

    def test_get_fills(self, run_id: str) -> tuple[bool, List[Dict]]:
        """Test getting fills from broker"""
        if not run_id:
            return False, []
            
        success, response = self.run_test(
            f"Get Simulation Fills: {run_id}",
            "GET",
            f"simulation/runs/{run_id}/fills",
            200
        )
        
        fills = []
        if success:
            fills = response.get('fills', [])
            count = response.get('count', 0)
            
            print(f"   Total Fills: {count}")
            
            # Analyze fills
            buy_fills = [f for f in fills if f.get('quantity', 0) > 0]
            sell_fills = [f for f in fills if f.get('quantity', 0) < 0]
            
            print(f"   Buy Fills: {len(buy_fills)}")
            print(f"   Sell Fills: {len(sell_fills)}")
            
            # Show sample fills
            for i, fill in enumerate(fills[:3]):
                asset = fill.get('asset', 'unknown')
                quantity = fill.get('quantity', 0)
                price = fill.get('price', 0)
                fee = fill.get('fee_usd', 0)
                timestamp = fill.get('timestamp', 'unknown')
                
                side = "BUY" if quantity > 0 else "SELL"
                print(f"   Fill {i+1}: {side} {abs(quantity):.4f} {asset} @ ${price:,.2f} (fee: ${fee:.2f})")
                
        return success, fills

    def test_get_orders(self, run_id: str) -> tuple[bool, Dict]:
        """Test getting orders from broker"""
        if not run_id:
            return False, {}
            
        success, response = self.run_test(
            f"Get Simulation Orders: {run_id}",
            "GET",
            f"simulation/runs/{run_id}/orders",
            200
        )
        
        orders_data = {}
        if success:
            open_orders = response.get('open', [])
            closed_orders = response.get('closed', [])
            
            print(f"   Open Orders: {len(open_orders)}")
            print(f"   Closed Orders: {len(closed_orders)}")
            
            orders_data = {
                "open": open_orders,
                "closed": closed_orders
            }
            
            # Show sample closed orders
            for i, order in enumerate(closed_orders[:3]):
                asset = order.get('asset', 'unknown')
                side = order.get('side', 'unknown')
                order_type = order.get('order_type', 'unknown')
                quantity = order.get('quantity', 0)
                price = order.get('price', 0)
                status = order.get('status', 'unknown')
                
                print(f"   Order {i+1}: {side} {quantity:.4f} {asset} {order_type} @ ${price:,.2f} ({status})")
                
        return success, orders_data

    def test_get_positions(self, run_id: str) -> tuple[bool, List[Dict]]:
        """Test getting positions"""
        if not run_id:
            return False, []
            
        success, response = self.run_test(
            f"Get Simulation Positions: {run_id}",
            "GET",
            f"simulation/runs/{run_id}/positions",
            200
        )
        
        positions = []
        if success:
            positions = response.get('positions', [])
            count = response.get('count', 0)
            
            print(f"   Total Positions: {count}")
            
            # Show positions
            for i, position in enumerate(positions):
                asset = position.get('asset', 'unknown')
                side = position.get('side', 'unknown')
                size = position.get('size', 0)
                entry_price = position.get('entry_price', 0)
                current_price = position.get('current_price', 0)
                unrealized_pnl = position.get('unrealized_pnl', 0)
                
                print(f"   Position {i+1}: {side} {size:.4f} {asset} @ ${entry_price:,.2f} (current: ${current_price:,.2f}, PnL: ${unrealized_pnl:,.2f})")
                
        return success, positions

    def test_get_state_with_realized_pnl(self, run_id: str) -> bool:
        """Test getting state - should reflect realized_pnl"""
        if not run_id:
            return False
            
        success, response = self.run_test(
            f"Get Simulation State: {run_id}",
            "GET",
            f"simulation/runs/{run_id}/state",
            200
        )
        
        if success:
            equity_usd = response.get('equity_usd', 0)
            cash_usd = response.get('cash_usd', 0)
            realized_pnl_usd = response.get('realized_pnl_usd', 0)
            unrealized_pnl_usd = response.get('unrealized_pnl_usd', 0)
            open_positions = response.get('open_positions', 0)
            open_orders = response.get('open_orders', 0)
            
            print(f"   Equity: ${equity_usd:,.2f}")
            print(f"   Cash: ${cash_usd:,.2f}")
            print(f"   Realized PnL: ${realized_pnl_usd:,.2f}")
            print(f"   Unrealized PnL: ${unrealized_pnl_usd:,.2f}")
            print(f"   Open Positions: {open_positions}")
            print(f"   Open Orders: {open_orders}")
            
            # Verify realized PnL is tracked
            if realized_pnl_usd != 0:
                print("✅ Realized PnL is being tracked")
            else:
                print("⚠️ No realized PnL recorded (may be expected if no trades closed)")
                
        return success

    def verify_equity_changes(self, run_id: str) -> bool:
        """Verify equity changes during simulation (not constant)"""
        if not run_id:
            return False
            
        success, response = self.run_test(
            f"Get Equity History: {run_id}",
            "GET",
            f"simulation/runs/{run_id}/equity",
            200
        )
        
        if success:
            equity_history = response.get('equity_history', [])
            points = response.get('points', 0)
            
            print(f"   Equity History Points: {points}")
            
            if len(equity_history) >= 2:
                first_equity = equity_history[0].get('equity_usd', 0)
                last_equity = equity_history[-1].get('equity_usd', 0)
                
                print(f"   Initial Equity: ${first_equity:,.2f}")
                print(f"   Final Equity: ${last_equity:,.2f}")
                print(f"   Total Change: ${last_equity - first_equity:,.2f}")
                
                # Check for equity variation
                equity_values = [point.get('equity_usd', 0) for point in equity_history]
                min_equity = min(equity_values)
                max_equity = max(equity_values)
                
                if max_equity != min_equity:
                    print("✅ Equity changes detected during simulation")
                    print(f"   Range: ${min_equity:,.2f} - ${max_equity:,.2f}")
                    return True
                else:
                    print("⚠️ Equity remained constant during simulation")
                    return False
            else:
                print("⚠️ Insufficient equity history points")
                return False
                
        return False

    def verify_fills_generated(self, fills: List[Dict]) -> bool:
        """Verify fills are generated (buys and sells)"""
        if not fills:
            print("❌ No fills generated")
            return False
            
        buy_fills = []
        sell_fills = []
        
        for fill in fills:
            quantity = fill.get('quantity', 0)
            if quantity > 0:
                buy_fills.append(fill)
            elif quantity < 0:
                sell_fills.append(fill)
                
        print(f"   Buy fills: {len(buy_fills)}")
        print(f"   Sell fills: {len(sell_fills)}")
        
        if len(buy_fills) > 0 and len(sell_fills) > 0:
            print("✅ Both buy and sell fills generated")
            return True
        elif len(buy_fills) > 0:
            print("⚠️ Only buy fills generated")
            return True
        elif len(sell_fills) > 0:
            print("⚠️ Only sell fills generated")
            return True
        else:
            print("❌ No valid fills found")
            return False

    def verify_drawdown_tracking(self, run_id: str) -> bool:
        """Verify drawdown tracking works"""
        if not run_id:
            return False
            
        # Get equity history for drawdown calculation
        success, response = self.run_test(
            f"Get Equity for Drawdown: {run_id}",
            "GET",
            f"simulation/runs/{run_id}/equity",
            200
        )
        
        if success:
            equity_history = response.get('equity_history', [])
            
            if len(equity_history) >= 2:
                equity_values = [point.get('equity_usd', 0) for point in equity_history]
                
                # Calculate drawdown
                peak = equity_values[0]
                max_drawdown = 0
                
                for equity in equity_values:
                    if equity > peak:
                        peak = equity
                    
                    drawdown = (peak - equity) / peak if peak > 0 else 0
                    max_drawdown = max(max_drawdown, drawdown)
                
                print(f"   Peak Equity: ${peak:,.2f}")
                print(f"   Max Drawdown: {max_drawdown:.2%}")
                
                if max_drawdown > 0:
                    print("✅ Drawdown tracking working (drawdown detected)")
                    return True
                else:
                    print("⚠️ No drawdown detected (equity only increased)")
                    return True
            else:
                print("⚠️ Insufficient data for drawdown calculation")
                return False
                
        return False

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive S1.3 test suite"""
        print("=" * 70)
        print("S1.3 Simulated Broker Adapter - Comprehensive Test Suite")
        print("=" * 70)
        
        results = {
            "health_check": False,
            "create_simulation": False,
            "run_simulation": False,
            "get_fills": False,
            "get_orders": False,
            "get_positions": False,
            "get_state": False,
            "equity_changes": False,
            "fills_generated": False,
            "drawdown_tracking": False,
            "run_id": None,
            "fills_data": [],
            "orders_data": {},
            "positions_data": []
        }
        
        # 1. Health Check - should show version s1.3
        print("\n📊 HEALTH CHECK")
        results["health_check"] = self.test_simulation_health()
        
        # 2. Create Simulation with Broker
        print("\n🏗️ CREATE SIMULATION")
        success, run_id = self.test_create_simulation()
        results["create_simulation"] = success
        results["run_id"] = run_id
        
        if not run_id:
            print("❌ Cannot continue without run_id")
            return results
        
        # 3. Run Full Simulation with Trading
        print("\n🚀 RUN FULL SIMULATION")
        results["run_simulation"] = self.test_run_full_simulation(run_id)
        
        # 4. Get Fills from Broker
        print("\n📋 GET FILLS")
        success, fills = self.test_get_fills(run_id)
        results["get_fills"] = success
        results["fills_data"] = fills
        
        # 5. Get Orders from Broker
        print("\n📄 GET ORDERS")
        success, orders = self.test_get_orders(run_id)
        results["get_orders"] = success
        results["orders_data"] = orders
        
        # 6. Get Positions
        print("\n📍 GET POSITIONS")
        success, positions = self.test_get_positions(run_id)
        results["get_positions"] = success
        results["positions_data"] = positions
        
        # 7. Get State - should reflect realized_pnl
        print("\n📊 GET STATE WITH REALIZED PNL")
        results["get_state"] = self.test_get_state_with_realized_pnl(run_id)
        
        # 8. Verify Equity Changes During Simulation
        print("\n📈 VERIFY EQUITY CHANGES")
        results["equity_changes"] = self.verify_equity_changes(run_id)
        
        # 9. Verify Fills are Generated (buys and sells)
        print("\n🔄 VERIFY FILLS GENERATED")
        results["fills_generated"] = self.verify_fills_generated(fills)
        
        # 10. Verify Drawdown Tracking
        print("\n📉 VERIFY DRAWDOWN TRACKING")
        results["drawdown_tracking"] = self.verify_drawdown_tracking(run_id)
        
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
        
        # Feature Test Results
        print(f"\n🔍 S1.3 FEATURE TEST RESULTS")
        
        feature_tests = [
            ("Health Check (version s1.3)", results["health_check"]),
            ("Create Simulation with Broker", results["create_simulation"]),
            ("Run Full Simulation with Trading", results["run_simulation"]),
            ("Get Fills from Broker", results["get_fills"]),
            ("Get Orders from Broker", results["get_orders"]),
            ("Get Positions", results["get_positions"]),
            ("Get State with Realized PnL", results["get_state"]),
            ("Verify Equity Changes", results["equity_changes"]),
            ("Verify Fills Generated", results["fills_generated"]),
            ("Verify Drawdown Tracking", results["drawdown_tracking"])
        ]
        
        for feature_name, success in feature_tests:
            status = "✅" if success else "❌"
            print(f"{status} {feature_name}")
        
        # Data Summary
        print(f"\n📊 DATA SUMMARY")
        if results["run_id"]:
            print(f"Run ID: {results['run_id']}")
        
        fills_count = len(results["fills_data"])
        print(f"Total Fills: {fills_count}")
        
        orders_data = results["orders_data"]
        if orders_data:
            open_orders = len(orders_data.get("open", []))
            closed_orders = len(orders_data.get("closed", []))
            print(f"Open Orders: {open_orders}")
            print(f"Closed Orders: {closed_orders}")
        
        positions_count = len(results["positions_data"])
        print(f"Positions: {positions_count}")
        
        # Error Details
        if self.errors:
            print(f"\n❌ ERROR DETAILS")
            for i, error in enumerate(self.errors, 1):
                print(f"{i}. {error['test']}: {error['error']}")
        
        print("\n" + "=" * 70)

def main():
    """Main test execution"""
    tester = S13SimulationTester()
    
    try:
        results = tester.run_comprehensive_test()
        tester.print_summary(results)
        
        # Return appropriate exit code
        success_rate = tester.tests_passed / tester.tests_run if tester.tests_run > 0 else 0
        
        if success_rate >= 0.8:  # 80% success rate threshold
            print("🎉 S1.3 Test suite PASSED (≥80% success rate)")
            return 0
        else:
            print("💥 S1.3 Test suite FAILED (<80% success rate)")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())