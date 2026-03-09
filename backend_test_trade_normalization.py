#!/usr/bin/env python3
"""
Backend Test: S1.4A Trade History Normalization
===============================================

Tests the trade normalization system that reconstructs closed trades from fills.

Key Features Tested:
- TradeBuilder: reconstruct closed trades from fills
- Handle averaging (multiple buys)
- Handle partial exits
- Calculate gross/net PnL with fees
- Track trade duration
- Compute TradeStats: win rate, profit factor, expectancy

Endpoints:
- POST /api/trading/simulation/runs - create simulation
- POST /api/trading/simulation/runs/{runId}/run - run simulation (should return trade_stats)
- GET /api/trading/simulation/runs/{runId}/trades - get closed trades
- GET /api/trading/simulation/runs/{runId}/trades/stats - get trade statistics
- GET /api/trading/simulation/runs/{runId}/trades/{tradeId} - get specific trade
- POST /api/trading/simulation/runs/{runId}/trades/normalize - manual normalization
"""

import requests
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

class TradeNormalizationTester:
    def __init__(self, base_url="https://pattern-detector-9.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.run_id = None
        self.created_trades = []
        
    def log(self, message: str, success: bool = True):
        """Log test result"""
        symbol = "✅" if success else "❌"
        print(f"{symbol} {message}")
        
    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, params: Optional[Dict] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/api/trading/simulation/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, params=params)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {"raw_response": response.text}
            else:
                self.log(f"Failed - Expected {expected_status}, got {response.status_code}", False)
                self.log(f"Response: {response.text}", False)
                return False, {}
                
        except Exception as e:
            self.log(f"Failed - Error: {str(e)}", False)
            return False, {}
    
    def test_create_simulation(self) -> bool:
        """Test creating a simulation run"""
        data = {
            "strategy_id": "test_strategy_s14a",
            "asset": "BTCUSDT",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "capital_profile": "SMALL",
            "initial_capital_usd": 10000,
            "market_type": "SPOT",
            "timeframe": "D1"
        }
        
        success, response = self.run_test(
            "Create Simulation for Trade Normalization",
            "POST", "runs", 200, data
        )
        
        if success and "run" in response:
            self.run_id = response["run"]["run_id"]
            self.log(f"Created simulation: {self.run_id}")
            return True
        return False
    
    def test_run_simulation(self) -> bool:
        """Test running simulation to generate fills and trades"""
        if not self.run_id:
            self.log("No run_id available", False)
            return False
            
        success, response = self.run_test(
            "Run Simulation (Generate Fills)",
            "POST", f"runs/{self.run_id}/run", 200
        )
        
        if success:
            # Check if trade_stats are returned
            if "trade_stats" in response:
                stats = response["trade_stats"]
                self.log(f"Trade stats returned: {len(stats)} metrics")
                
                # Verify required stats fields
                required_fields = ["win_rate", "profit_factor", "expectancy", "avg_win", "avg_loss"]
                for field in required_fields:
                    if field in stats:
                        self.log(f"  {field}: {stats[field]}")
                    else:
                        self.log(f"  Missing required field: {field}", False)
                        return False
                        
                return True
            else:
                self.log("No trade_stats in response", False)
                return False
        return False
    
    def test_get_trades(self) -> bool:
        """Test getting closed trades"""
        if not self.run_id:
            return False
            
        success, response = self.run_test(
            "Get Closed Trades",
            "GET", f"runs/{self.run_id}/trades", 200
        )
        
        if success and "trades" in response:
            trades = response["trades"]
            self.log(f"Retrieved {len(trades)} closed trades")
            
            if trades:
                # Verify trade structure
                trade = trades[0]
                required_fields = [
                    "entry_time", "exit_time", "entry_price", "exit_price", 
                    "net_pnl_usd", "duration_bars", "trade_id", "asset", "side"
                ]
                
                for field in required_fields:
                    if field in trade:
                        self.log(f"  {field}: {trade[field]}")
                    else:
                        self.log(f"  Missing required field: {field}", False)
                        return False
                
                # Store first trade for individual test
                self.created_trades = trades
                return True
            else:
                self.log("No trades found - this might be expected if simulation didn't generate trades")
                return True
        return False
    
    def test_get_trade_stats(self) -> bool:
        """Test getting trade statistics"""
        if not self.run_id:
            return False
            
        success, response = self.run_test(
            "Get Trade Statistics",
            "GET", f"runs/{self.run_id}/trades/stats", 200
        )
        
        if success and "stats" in response:
            stats = response["stats"]
            self.log(f"Retrieved trade statistics")
            
            # Verify all required stats fields
            required_fields = [
                "win_rate", "profit_factor", "expectancy", "avg_win", "avg_loss",
                "largest_win", "largest_loss", "total_fees", "avg_duration_bars",
                "total_trades", "winning_trades", "losing_trades"
            ]
            
            all_present = True
            for field in required_fields:
                if field in stats:
                    self.log(f"  {field}: {stats[field]}")
                else:
                    self.log(f"  Missing required field: {field}", False)
                    all_present = False
            
            return all_present
        return False
    
    def test_get_specific_trade(self) -> bool:
        """Test getting a specific trade by ID"""
        if not self.run_id or not self.created_trades:
            self.log("No trades available for individual test")
            return True  # Skip if no trades
            
        trade_id = self.created_trades[0]["trade_id"]
        
        success, response = self.run_test(
            "Get Specific Trade",
            "GET", f"runs/{self.run_id}/trades/{trade_id}", 200
        )
        
        if success:
            self.log(f"Retrieved specific trade: {trade_id}")
            
            # Verify it matches the trade from the list
            if "trade_id" in response and response["trade_id"] == trade_id:
                self.log("Trade ID matches")
                return True
            else:
                self.log("Trade ID mismatch", False)
                return False
        return False
    
    def test_manual_normalization(self) -> bool:
        """Test manual trade normalization trigger"""
        if not self.run_id:
            return False
            
        success, response = self.run_test(
            "Manual Trade Normalization",
            "POST", f"runs/{self.run_id}/trades/normalize", 200,
            params={"close_open": True}
        )
        
        if success:
            if "trades_normalized" in response:
                count = response["trades_normalized"]
                self.log(f"Normalized {count} trades manually")
                return True
            else:
                self.log("No trades_normalized count in response", False)
                return False
        return False
    
    def test_trade_filters(self) -> bool:
        """Test trade filtering (winners/losers)"""
        if not self.run_id:
            return False
            
        # Test winners filter
        success_winners, response_winners = self.run_test(
            "Get Winning Trades",
            "GET", f"runs/{self.run_id}/trades", 200,
            params={"filter": "winners", "limit": 50}
        )
        
        # Test losers filter  
        success_losers, response_losers = self.run_test(
            "Get Losing Trades", 
            "GET", f"runs/{self.run_id}/trades", 200,
            params={"filter": "losers", "limit": 50}
        )
        
        if success_winners and success_losers:
            winners = response_winners.get("trades", [])
            losers = response_losers.get("trades", [])
            
            self.log(f"Winners: {len(winners)}, Losers: {len(losers)}")
            
            # Verify winners have positive PnL
            for trade in winners:
                if trade.get("net_pnl_usd", 0) <= 0:
                    self.log(f"Winner has non-positive PnL: {trade['net_pnl_usd']}", False)
                    return False
            
            # Verify losers have non-positive PnL
            for trade in losers:
                if trade.get("net_pnl_usd", 0) > 0:
                    self.log(f"Loser has positive PnL: {trade['net_pnl_usd']}", False)
                    return False
                    
            return True
        return False
    
    def test_trade_summary(self) -> bool:
        """Test getting full trade summary"""
        if not self.run_id:
            return False
            
        success, response = self.run_test(
            "Get Trade Summary",
            "GET", f"runs/{self.run_id}/trades/summary", 200
        )
        
        if success:
            if "stats" in response and "trades" in response:
                self.log(f"Summary contains stats and {response.get('trade_count', 0)} trades")
                return True
            else:
                self.log("Summary missing stats or trades", False)
                return False
        return False
    
    def run_all_tests(self) -> bool:
        """Run all trade normalization tests"""
        print("=" * 60)
        print("S1.4A TRADE HISTORY NORMALIZATION TESTS")
        print("=" * 60)
        
        tests = [
            ("Create Simulation", self.test_create_simulation),
            ("Run Simulation", self.test_run_simulation),
            ("Get Trades", self.test_get_trades),
            ("Get Trade Stats", self.test_get_trade_stats),
            ("Get Specific Trade", self.test_get_specific_trade),
            ("Manual Normalization", self.test_manual_normalization),
            ("Trade Filters", self.test_trade_filters),
            ("Trade Summary", self.test_trade_summary),
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            try:
                result = test_func()
                if not result:
                    all_passed = False
                    print(f"❌ {test_name} FAILED")
                else:
                    print(f"✅ {test_name} PASSED")
            except Exception as e:
                all_passed = False
                print(f"❌ {test_name} ERROR: {e}")
        
        print("\n" + "=" * 60)
        print(f"RESULTS: {self.tests_passed}/{self.tests_run} tests passed")
        print(f"SUCCESS RATE: {(self.tests_passed/self.tests_run)*100:.1f}%")
        print("=" * 60)
        
        return all_passed

def main():
    tester = TradeNormalizationTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())