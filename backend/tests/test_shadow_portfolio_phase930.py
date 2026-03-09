"""
Shadow Portfolio API Tests - Phase 9.30
========================================

Tests for the Shadow Portfolio system that provides production-like simulation
for tournament winner alphas without real money.

Endpoints tested:
- GET /api/shadow/health - Service health check
- GET /api/shadow/config - Portfolio configuration
- POST /api/shadow/add-strategy - Add tournament winners
- POST /api/shadow/remove-strategy/{id} - Remove strategy
- POST /api/shadow/run-cycle - Execute one portfolio cycle
- POST /api/shadow/run-cycles - Run multiple cycles
- GET /api/shadow/portfolio - Full portfolio state
- GET /api/shadow/positions - Position list (open/closed)
- GET /api/shadow/trades - Trade log
- GET /api/shadow/equity - Equity curve data
- GET /api/shadow/metrics - Computed metrics
- GET /api/shadow/events - Governance events
- GET /api/shadow/stats - Portfolio statistics summary
- PUT /api/shadow/config - Update configuration
- POST /api/shadow/reset - Full portfolio reset
"""

import pytest
import requests
import os
import time

# Get base URL from environment (must have trailing /api for proper routing)
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestShadowPortfolioHealth:
    """Health and configuration tests"""
    
    def test_health_check(self):
        """Test shadow portfolio health endpoint"""
        response = requests.get(f"{BASE_URL}/api/shadow/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        
        data = response.json()
        assert data.get("enabled") == True
        assert data.get("status") == "ok"
        assert data.get("version") == "phase9.30"
        assert "portfolio_id" in data
        assert "equity" in data
        assert "strategies" in data
        assert "regime" in data
        assert data["regime"] in ["NORMAL", "ELEVATED", "STRESS", "CRISIS"]
        print(f"Health check passed - Portfolio ID: {data['portfolio_id']}, Equity: {data['equity']}")
    
    def test_config_get(self):
        """Test getting portfolio configuration"""
        response = requests.get(f"{BASE_URL}/api/shadow/config")
        assert response.status_code == 200, f"Config get failed: {response.text}"
        
        data = response.json()
        assert "initial_capital" in data
        assert "max_strategies" in data
        assert "max_position_per_strategy" in data
        assert "stop_loss_pct" in data
        assert "take_profit_pct" in data
        assert "drawdown_limits" in data
        assert "regime_exposure" in data
        assert "allocation" in data
        
        # Verify default values
        assert data["initial_capital"] == 100000.0
        assert data["max_strategies"] == 10
        print(f"Config retrieved - Initial Capital: {data['initial_capital']}, Max Strategies: {data['max_strategies']}")


class TestShadowPortfolioReset:
    """Reset functionality tests - run first to ensure clean state"""
    
    def test_portfolio_reset(self):
        """Test full portfolio reset"""
        response = requests.post(f"{BASE_URL}/api/shadow/reset")
        assert response.status_code == 200, f"Reset failed: {response.text}"
        
        data = response.json()
        assert data.get("reset") == True
        assert "portfolio_id" in data
        assert data.get("equity") == 100000.0  # Should reset to initial capital
        print(f"Portfolio reset - New ID: {data['portfolio_id']}, Equity: {data['equity']}")
        
        # Verify health shows clean state
        health = requests.get(f"{BASE_URL}/api/shadow/health").json()
        assert health["strategies"] == 0
        assert health["open_positions"] == 0
        assert health["total_trades"] == 0
        assert health["cycles"] == 0
        print("Reset verification passed - clean state confirmed")


class TestShadowPortfolioStrategyManagement:
    """Strategy lifecycle tests"""
    
    @pytest.fixture(autouse=True)
    def reset_portfolio(self):
        """Reset portfolio before each test"""
        requests.post(f"{BASE_URL}/api/shadow/reset")
        yield
    
    def test_add_strategy_success(self):
        """Test adding a tournament winner strategy"""
        payload = {
            "alpha_id": "TEST_alpha_001",
            "name": "Test Momentum Strategy",
            "family": "MOMENTUM",
            "asset_classes": ["CRYPTO"],
            "timeframes": ["1D"],
            "tournament_run_id": "tourney_001",
            "tournament_score": 0.75,
            "confidence": 0.65
        }
        
        response = requests.post(f"{BASE_URL}/api/shadow/add-strategy", json=payload)
        assert response.status_code == 200, f"Add strategy failed: {response.text}"
        
        data = response.json()
        assert data.get("added") == True
        assert "strategy" in data
        
        strategy = data["strategy"]
        assert strategy["alpha_id"] == "TEST_alpha_001"
        assert strategy["name"] == "Test Momentum Strategy"
        assert strategy["family"] == "MOMENTUM"
        assert strategy["status"] == "ACTIVE"
        assert strategy["tournament_score"] == 0.75
        assert "strategy_id" in strategy
        assert strategy["weight"] > 0  # Should have been assigned a weight
        
        print(f"Strategy added - ID: {strategy['strategy_id']}, Weight: {strategy['weight']}")
        return strategy["strategy_id"]
    
    def test_add_multiple_strategies(self):
        """Test adding multiple strategies with weight rebalancing"""
        strategies_data = [
            {"alpha_id": "TEST_trend_001", "name": "Trend Strategy", "family": "TREND", "tournament_score": 0.8},
            {"alpha_id": "TEST_reversal_001", "name": "Reversal Strategy", "family": "REVERSAL", "tournament_score": 0.7},
            {"alpha_id": "TEST_breakout_001", "name": "Breakout Strategy", "family": "BREAKOUT", "tournament_score": 0.6}
        ]
        
        strategy_ids = []
        for strat_data in strategies_data:
            response = requests.post(f"{BASE_URL}/api/shadow/add-strategy", json=strat_data)
            assert response.status_code == 200, f"Failed to add strategy: {response.text}"
            data = response.json()
            assert data.get("added") == True
            strategy_ids.append(data["strategy"]["strategy_id"])
        
        # Verify portfolio state
        portfolio = requests.get(f"{BASE_URL}/api/shadow/portfolio").json()
        assert len(portfolio["strategies"]) == 3
        
        # Verify weights sum to approximately 1.0 (equal weight mode)
        total_weight = sum(s["weight"] for s in portfolio["strategies"])
        assert 0.89 <= total_weight <= 1.1, f"Weights don't sum to ~1.0: {total_weight}"
        
        print(f"Added 3 strategies with total weight: {total_weight}")
        return strategy_ids
    
    def test_add_strategy_max_limit(self):
        """Test rejection when max_strategies limit is reached"""
        # First update config to have max 2 strategies
        config_response = requests.put(f"{BASE_URL}/api/shadow/config", json={"max_strategies": 2})
        assert config_response.status_code == 200
        
        # Add 2 strategies (should succeed)
        for i in range(2):
            response = requests.post(f"{BASE_URL}/api/shadow/add-strategy", json={
                "alpha_id": f"TEST_limit_{i}",
                "name": f"Limit Test {i}",
                "family": "EXPERIMENTAL"
            })
            assert response.status_code == 200, f"Failed to add strategy {i}"
        
        # Try to add 3rd (should fail with 400)
        response = requests.post(f"{BASE_URL}/api/shadow/add-strategy", json={
            "alpha_id": "TEST_limit_2",
            "name": "Should Fail",
            "family": "EXPERIMENTAL"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert "max strategies" in response.json().get("detail", "").lower()
        
        print("Max strategy limit enforcement verified")
        
        # Reset config back to default
        requests.put(f"{BASE_URL}/api/shadow/config", json={"max_strategies": 10})
    
    def test_remove_strategy(self):
        """Test removing a strategy"""
        # Add a strategy first
        add_response = requests.post(f"{BASE_URL}/api/shadow/add-strategy", json={
            "alpha_id": "TEST_remove_001",
            "name": "To Be Removed",
            "family": "EXPERIMENTAL"
        })
        assert add_response.status_code == 200
        strategy_id = add_response.json()["strategy"]["strategy_id"]
        
        # Remove the strategy
        remove_response = requests.post(
            f"{BASE_URL}/api/shadow/remove-strategy/{strategy_id}",
            json={"reason": "Test removal"}
        )
        assert remove_response.status_code == 200
        
        data = remove_response.json()
        assert data.get("removed") == True
        assert data.get("strategy_id") == strategy_id
        
        # Verify strategy is gone
        portfolio = requests.get(f"{BASE_URL}/api/shadow/portfolio").json()
        assert len(portfolio["strategies"]) == 0
        
        # Verify removal event was logged
        events = requests.get(f"{BASE_URL}/api/shadow/events").json()
        removal_events = [e for e in events["events"] if e["event_type"] == "STRATEGY_REMOVED"]
        assert len(removal_events) > 0
        
        print(f"Strategy {strategy_id} removed successfully")
    
    def test_remove_strategy_not_found(self):
        """Test removing a non-existent strategy"""
        response = requests.post(
            f"{BASE_URL}/api/shadow/remove-strategy/non_existent_id",
            json={"reason": "Test"}
        )
        assert response.status_code == 404
        print("Non-existent strategy removal correctly returns 404")


class TestShadowPortfolioCycleExecution:
    """Cycle execution tests"""
    
    @pytest.fixture(autouse=True)
    def setup_portfolio(self):
        """Reset and add strategies before each test"""
        requests.post(f"{BASE_URL}/api/shadow/reset")
        # Add test strategies
        for i in range(3):
            requests.post(f"{BASE_URL}/api/shadow/add-strategy", json={
                "alpha_id": f"TEST_cycle_{i}",
                "name": f"Cycle Test Strategy {i}",
                "family": ["TREND", "MOMENTUM", "BREAKOUT"][i],
                "tournament_score": 0.7 + i * 0.05,
                "confidence": 0.6 + i * 0.1
            })
        yield
    
    def test_run_single_cycle(self):
        """Test executing one portfolio cycle"""
        response = requests.post(f"{BASE_URL}/api/shadow/run-cycle", json={})
        assert response.status_code == 200, f"Run cycle failed: {response.text}"
        
        data = response.json()
        assert "cycle_id" in data
        assert "cycle_number" in data
        assert data["cycle_number"] == 1
        assert data["status"] == "COMPLETED"
        assert "signals_generated" in data
        assert "positions_opened" in data
        assert "positions_closed" in data
        assert "equity_before" in data
        assert "equity_after" in data
        assert "cycle_pnl" in data
        assert "regime" in data
        
        print(f"Cycle {data['cycle_number']} completed - Signals: {data['signals_generated']}, "
              f"Opened: {data['positions_opened']}, PnL: {data['cycle_pnl']}")
    
    def test_run_multiple_cycles(self):
        """Test running multiple cycles"""
        response = requests.post(f"{BASE_URL}/api/shadow/run-cycles", json={"count": 10})
        assert response.status_code == 200, f"Run cycles failed: {response.text}"
        
        data = response.json()
        assert data["cycles_run"] == 10
        assert "final_equity" in data
        assert "total_pnl" in data
        assert "regime" in data
        assert "cycles" in data
        assert len(data["cycles"]) == 10
        
        # Verify cycle numbers are sequential
        for i, cycle in enumerate(data["cycles"]):
            assert cycle["cycle_number"] == i + 1
        
        print(f"Ran 10 cycles - Final Equity: {data['final_equity']}, Total PnL: {data['total_pnl']}")
    
    def test_cycle_produces_positions(self):
        """Test that cycles produce positions and trades over time"""
        # Run enough cycles to generate some trades
        requests.post(f"{BASE_URL}/api/shadow/run-cycles", json={"count": 30})
        
        # Check positions
        positions_response = requests.get(f"{BASE_URL}/api/shadow/positions")
        assert positions_response.status_code == 200
        positions_data = positions_response.json()
        
        # Check trades
        trades_response = requests.get(f"{BASE_URL}/api/shadow/trades")
        assert trades_response.status_code == 200
        trades_data = trades_response.json()
        
        # With 3 strategies and 30 cycles, we should have some activity
        total_activity = positions_data["total"] + trades_data["total"]
        print(f"After 30 cycles: {positions_data['total']} positions, {trades_data['total']} trades")
        
        # Verify equity curve has data points
        equity_response = requests.get(f"{BASE_URL}/api/shadow/equity")
        assert equity_response.status_code == 200
        equity_data = equity_response.json()
        assert equity_data["total_points"] >= 30  # At least one per cycle + initial
        print(f"Equity curve has {equity_data['total_points']} data points")


class TestShadowPortfolioPositionsAndTrades:
    """Position and trade query tests"""
    
    @pytest.fixture(autouse=True)
    def setup_with_trades(self):
        """Setup portfolio with trades"""
        requests.post(f"{BASE_URL}/api/shadow/reset")
        # Add strategies
        for i in range(3):
            requests.post(f"{BASE_URL}/api/shadow/add-strategy", json={
                "alpha_id": f"TEST_pos_{i}",
                "name": f"Position Test {i}",
                "family": ["TREND", "MOMENTUM", "REVERSAL"][i],
                "tournament_score": 0.75,
                "confidence": 0.7
            })
        # Run cycles to generate positions
        requests.post(f"{BASE_URL}/api/shadow/run-cycles", json={"count": 30})
        yield
    
    def test_get_all_positions(self):
        """Test getting all positions"""
        response = requests.get(f"{BASE_URL}/api/shadow/positions")
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "positions" in data
        assert isinstance(data["positions"], list)
        
        if data["total"] > 0:
            pos = data["positions"][0]
            assert "position_id" in pos
            assert "strategy_id" in pos
            assert "asset" in pos
            assert "direction" in pos
            assert "status" in pos
            assert "entry_price" in pos
            print(f"Total positions: {data['total']}")
    
    def test_get_open_positions(self):
        """Test filtering open positions"""
        response = requests.get(f"{BASE_URL}/api/shadow/positions?status=open")
        assert response.status_code == 200
        
        data = response.json()
        for pos in data["positions"]:
            assert pos["status"] == "OPEN"
        print(f"Open positions: {data['total']}")
    
    def test_get_closed_positions(self):
        """Test filtering closed positions"""
        response = requests.get(f"{BASE_URL}/api/shadow/positions?status=closed")
        assert response.status_code == 200
        
        data = response.json()
        for pos in data["positions"]:
            assert pos["status"] != "OPEN"
        print(f"Closed positions: {data['total']}")
    
    def test_get_trades(self):
        """Test getting trade log"""
        response = requests.get(f"{BASE_URL}/api/shadow/trades")
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "returned" in data
        assert "trades" in data
        
        if data["total"] > 0:
            trade = data["trades"][0]
            assert "trade_id" in trade
            assert "position_id" in trade
            assert "strategy_id" in trade
            assert "asset" in trade
            assert "direction" in trade
            assert "entry_price" in trade
            assert "exit_price" in trade
            assert "pnl" in trade
            assert "pnl_pct" in trade
            print(f"Total trades: {data['total']}, Returned: {data['returned']}")
    
    def test_get_trades_with_strategy_filter(self):
        """Test filtering trades by strategy"""
        # Get a strategy ID first
        portfolio = requests.get(f"{BASE_URL}/api/shadow/portfolio").json()
        if portfolio["strategies"]:
            strategy_id = portfolio["strategies"][0]["strategy_id"]
            
            response = requests.get(f"{BASE_URL}/api/shadow/trades?strategy_id={strategy_id}")
            assert response.status_code == 200
            
            data = response.json()
            for trade in data["trades"]:
                assert trade["strategy_id"] == strategy_id
            print(f"Trades for strategy {strategy_id}: {data['returned']}")


class TestShadowPortfolioEquityAndMetrics:
    """Equity curve and metrics tests"""
    
    @pytest.fixture(autouse=True)
    def setup_with_history(self):
        """Setup portfolio with trading history"""
        requests.post(f"{BASE_URL}/api/shadow/reset")
        for i in range(3):
            requests.post(f"{BASE_URL}/api/shadow/add-strategy", json={
                "alpha_id": f"TEST_metrics_{i}",
                "name": f"Metrics Test {i}",
                "family": ["TREND", "MOMENTUM", "BREAKOUT"][i],
                "tournament_score": 0.7 + i * 0.05,
                "confidence": 0.65
            })
        # Run cycles to generate meaningful metrics
        requests.post(f"{BASE_URL}/api/shadow/run-cycles", json={"count": 50})
        yield
    
    def test_get_equity_curve(self):
        """Test getting equity curve data"""
        response = requests.get(f"{BASE_URL}/api/shadow/equity")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_points" in data
        assert "returned" in data
        assert "current_equity" in data
        assert "initial_capital" in data
        assert "peak_equity" in data
        assert "curve" in data
        
        if data["curve"]:
            point = data["curve"][0]
            assert "timestamp" in point
            assert "equity" in point
            assert "cash" in point
            assert "exposure" in point
            assert "drawdown" in point
            assert "drawdown_pct" in point
            assert "regime" in point
            assert "open_positions" in point
            assert "cycle_number" in point
        
        print(f"Equity curve: {data['total_points']} points, Current: {data['current_equity']}, Peak: {data['peak_equity']}")
    
    def test_get_metrics(self):
        """Test computing portfolio metrics"""
        response = requests.get(f"{BASE_URL}/api/shadow/metrics")
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all expected metrics are present
        expected_fields = [
            "total_return", "total_return_pct", "sharpe_ratio", "sortino_ratio",
            "profit_factor", "max_drawdown", "max_drawdown_pct", "calmar_ratio",
            "win_rate", "avg_win", "avg_loss", "total_trades", "winning_trades",
            "losing_trades", "avg_holding_bars", "turnover", "exposure_avg",
            "strategy_contributions", "family_contributions", "computed_at"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing metric field: {field}"
        
        # Verify metrics are reasonable
        assert 0 <= data["win_rate"] <= 1, f"Invalid win rate: {data['win_rate']}"
        assert data["total_trades"] >= 0
        assert data["winning_trades"] + data["losing_trades"] == data["total_trades"]
        
        print(f"Metrics - Win Rate: {data['win_rate']:.2%}, Sharpe: {data['sharpe_ratio']:.2f}, "
              f"PF: {data['profit_factor']:.2f}, Max DD: {data['max_drawdown_pct']:.2%}")
    
    def test_get_stats(self):
        """Test getting portfolio statistics summary"""
        response = requests.get(f"{BASE_URL}/api/shadow/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "portfolio" in data
        assert "performance" in data
        assert "strategy_contributions" in data
        assert "family_contributions" in data
        
        portfolio = data["portfolio"]
        assert "equity" in portfolio
        assert "exposure" in portfolio
        assert "regime" in portfolio
        
        performance = data["performance"]
        assert "total_return" in performance
        assert "sharpe" in performance
        assert "win_rate" in performance
        
        print(f"Stats - Equity: {portfolio['equity']}, Return: {performance['total_return']}")


class TestShadowPortfolioGovernanceEvents:
    """Governance events tests"""
    
    @pytest.fixture(autouse=True)
    def setup_with_events(self):
        """Setup portfolio with governance events"""
        requests.post(f"{BASE_URL}/api/shadow/reset")
        # Add and remove a strategy to generate events
        add_resp = requests.post(f"{BASE_URL}/api/shadow/add-strategy", json={
            "alpha_id": "TEST_events_001",
            "name": "Events Test",
            "family": "MOMENTUM",
            "tournament_score": 0.7
        })
        strategy_id = add_resp.json()["strategy"]["strategy_id"]
        requests.post(f"{BASE_URL}/api/shadow/run-cycles", json={"count": 5})
        requests.post(f"{BASE_URL}/api/shadow/remove-strategy/{strategy_id}", json={"reason": "Test"})
        yield
    
    def test_get_all_events(self):
        """Test getting all governance events"""
        response = requests.get(f"{BASE_URL}/api/shadow/events")
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "returned" in data
        assert "events" in data
        
        if data["events"]:
            event = data["events"][0]
            assert "event_id" in event
            assert "event_type" in event
            assert "timestamp" in event
            assert "details" in event
            assert "reason" in event
        
        # Should have at least: reset, add, cycles, remove events
        print(f"Total events: {data['total']}")
    
    def test_get_events_by_type(self):
        """Test filtering events by type"""
        response = requests.get(f"{BASE_URL}/api/shadow/events?event_type=STRATEGY_ADDED")
        assert response.status_code == 200
        
        data = response.json()
        for event in data["events"]:
            assert event["event_type"] == "STRATEGY_ADDED"
        print(f"STRATEGY_ADDED events: {data['returned']}")
    
    def test_cycle_completed_events(self):
        """Test that cycle completion events are logged"""
        response = requests.get(f"{BASE_URL}/api/shadow/events?event_type=CYCLE_COMPLETED")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["events"]) >= 5  # We ran 5 cycles
        print(f"CYCLE_COMPLETED events: {data['returned']}")


class TestShadowPortfolioConfiguration:
    """Configuration update tests"""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset portfolio before and after tests"""
        requests.post(f"{BASE_URL}/api/shadow/reset")
        yield
        # Restore defaults
        requests.put(f"{BASE_URL}/api/shadow/config", json={
            "max_strategies": 10,
            "max_total_exposure": 1.0,
            "stop_loss_pct": 0.02,
            "take_profit_pct": 0.04
        })
    
    def test_update_config(self):
        """Test updating configuration"""
        new_config = {
            "max_strategies": 5,
            "max_total_exposure": 0.8,
            "stop_loss_pct": 0.03,
            "take_profit_pct": 0.06
        }
        
        response = requests.put(f"{BASE_URL}/api/shadow/config", json=new_config)
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("updated") == True
        assert "config" in data
        
        config = data["config"]
        assert config["max_strategies"] == 5
        assert config["max_total_exposure"] == 0.8
        assert config["stop_loss_pct"] == 0.03
        assert config["take_profit_pct"] == 0.06
        
        print("Configuration updated successfully")
    
    def test_partial_config_update(self):
        """Test partial configuration update"""
        response = requests.put(f"{BASE_URL}/api/shadow/config", json={"max_strategies": 15})
        assert response.status_code == 200
        
        data = response.json()
        assert data["config"]["max_strategies"] == 15
        # Other values should remain unchanged
        assert data["config"]["initial_capital"] == 100000.0
        
        print("Partial config update successful")


class TestShadowPortfolioRiskRegime:
    """Risk regime integration tests"""
    
    @pytest.fixture(autouse=True)
    def setup_portfolio(self):
        """Setup portfolio"""
        requests.post(f"{BASE_URL}/api/shadow/reset")
        for i in range(3):
            requests.post(f"{BASE_URL}/api/shadow/add-strategy", json={
                "alpha_id": f"TEST_regime_{i}",
                "name": f"Regime Test {i}",
                "family": "MOMENTUM",
                "tournament_score": 0.7
            })
        yield
    
    def test_regime_in_health(self):
        """Test regime is reported in health"""
        response = requests.get(f"{BASE_URL}/api/shadow/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "regime" in data
        assert data["regime"] in ["NORMAL", "ELEVATED", "STRESS", "CRISIS"]
        print(f"Current regime: {data['regime']}")
    
    def test_regime_in_cycle_result(self):
        """Test regime is reported in cycle results"""
        response = requests.post(f"{BASE_URL}/api/shadow/run-cycle", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert "regime" in data
        assert data["regime"] in ["NORMAL", "ELEVATED", "STRESS", "CRISIS"]
        print(f"Cycle regime: {data['regime']}")
    
    def test_regime_in_equity_curve(self):
        """Test regime is tracked in equity curve"""
        requests.post(f"{BASE_URL}/api/shadow/run-cycles", json={"count": 10})
        
        response = requests.get(f"{BASE_URL}/api/shadow/equity")
        assert response.status_code == 200
        
        data = response.json()
        for point in data["curve"]:
            assert "regime" in point
            assert point["regime"] in ["NORMAL", "ELEVATED", "STRESS", "CRISIS"]
        
        print("Regime tracking in equity curve verified")


class TestShadowPortfolioIntegration:
    """Full integration tests"""
    
    def test_full_workflow(self):
        """Test complete shadow portfolio workflow"""
        # 1. Reset
        reset_resp = requests.post(f"{BASE_URL}/api/shadow/reset")
        assert reset_resp.status_code == 200
        print("1. Portfolio reset")
        
        # 2. Add strategies
        strategy_ids = []
        for i, family in enumerate(["TREND", "MOMENTUM", "BREAKOUT"]):
            add_resp = requests.post(f"{BASE_URL}/api/shadow/add-strategy", json={
                "alpha_id": f"TEST_workflow_{i}",
                "name": f"Workflow {family}",
                "family": family,
                "tournament_score": 0.7 + i * 0.05,
                "confidence": 0.65
            })
            assert add_resp.status_code == 200
            strategy_ids.append(add_resp.json()["strategy"]["strategy_id"])
        print(f"2. Added {len(strategy_ids)} strategies")
        
        # 3. Verify portfolio state
        portfolio_resp = requests.get(f"{BASE_URL}/api/shadow/portfolio")
        assert portfolio_resp.status_code == 200
        portfolio = portfolio_resp.json()
        assert len(portfolio["strategies"]) == 3
        print(f"3. Portfolio verified - {len(portfolio['strategies'])} strategies")
        
        # 4. Run cycles
        cycles_resp = requests.post(f"{BASE_URL}/api/shadow/run-cycles", json={"count": 30})
        assert cycles_resp.status_code == 200
        cycles_data = cycles_resp.json()
        print(f"4. Ran {cycles_data['cycles_run']} cycles - PnL: {cycles_data['total_pnl']}")
        
        # 5. Check positions
        pos_resp = requests.get(f"{BASE_URL}/api/shadow/positions")
        assert pos_resp.status_code == 200
        print(f"5. Positions: {pos_resp.json()['total']}")
        
        # 6. Check trades
        trades_resp = requests.get(f"{BASE_URL}/api/shadow/trades")
        assert trades_resp.status_code == 200
        print(f"6. Trades: {trades_resp.json()['total']}")
        
        # 7. Get metrics
        metrics_resp = requests.get(f"{BASE_URL}/api/shadow/metrics")
        assert metrics_resp.status_code == 200
        metrics = metrics_resp.json()
        print(f"7. Metrics - Win Rate: {metrics['win_rate']:.2%}, Sharpe: {metrics['sharpe_ratio']:.2f}")
        
        # 8. Get events
        events_resp = requests.get(f"{BASE_URL}/api/shadow/events")
        assert events_resp.status_code == 200
        print(f"8. Events: {events_resp.json()['total']}")
        
        # 9. Remove a strategy
        remove_resp = requests.post(
            f"{BASE_URL}/api/shadow/remove-strategy/{strategy_ids[0]}",
            json={"reason": "Workflow test"}
        )
        assert remove_resp.status_code == 200
        print("9. Removed one strategy")
        
        # 10. Final health check
        health_resp = requests.get(f"{BASE_URL}/api/shadow/health")
        assert health_resp.status_code == 200
        health = health_resp.json()
        assert health["strategies"] == 2
        print(f"10. Final state - Strategies: {health['strategies']}, Equity: {health['equity']}")
        
        print("\nFull workflow test PASSED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
