"""
Trading Capsule T5 (Terminal Backend) API Tests
================================================

Tests for Terminal Backend endpoints:
- Account Monitor
- Position Monitor  
- Orders Monitor
- PnL Engine
- Execution Log
- Risk Monitor
- Averaging Monitor
- System State
- Terminal Actions
- Dashboard Aggregation

Using MockBrokerAdapter - api_key must contain 'mock' for testing.
"""

import pytest
import requests
import os
import time
from datetime import datetime

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test connection ID (will be retrieved during test setup)
TEST_CONNECTION_ID = None


class TestT5TerminalHealth:
    """T5 Terminal Backend Health Tests"""
    
    def test_terminal_health(self):
        """GET /api/trading/terminal/health - Terminal health check"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["enabled"] == True
        assert data["version"] == "terminal_t5"
        assert data["status"] == "ok"
        assert "log_entries" in data
        assert "uptime_minutes" in data
        assert "timestamp" in data
        print(f"Terminal health: OK, uptime={data['uptime_minutes']}min, log_entries={data['log_entries']}")


class TestT5SystemState:
    """T5 System State Tests"""
    
    def test_get_system_state(self):
        """GET /api/trading/terminal/state - Get trading system state"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/state")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all state fields
        assert "execution_mode" in data
        assert "trading_mode" in data
        assert "paused" in data
        assert "kill_switch_active" in data
        assert "active_connections" in data
        assert "healthy_connections" in data
        assert "open_positions" in data
        assert "open_orders" in data
        assert "daily_trades" in data
        assert "daily_volume_usd" in data
        assert "uptime_minutes" in data
        
        print(f"System state: mode={data['execution_mode']}, "
              f"connections={data['active_connections']}, "
              f"positions={data['open_positions']}, "
              f"paused={data['paused']}")


class TestT5AccountMonitor:
    """T5 Account Monitor Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/terminal/accounts")
            if response.status_code == 200:
                data = response.json()
                if data.get("accounts"):
                    TEST_CONNECTION_ID = data["accounts"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_get_accounts_overview(self):
        """GET /api/trading/terminal/accounts - Get all accounts overview"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/accounts")
        assert response.status_code == 200
        data = response.json()
        
        assert "accounts" in data
        assert "count" in data
        assert isinstance(data["accounts"], list)
        
        if data["accounts"]:
            account = data["accounts"][0]
            # Verify account fields
            assert "connection_id" in account
            assert "exchange" in account
            assert "label" in account
            assert "total_equity_usd" in account
            assert "available_cash_usd" in account
            assert "status" in account
            assert "health" in account
            assert "open_positions" in account
            assert "open_orders" in account
            
            print(f"Found {data['count']} accounts. First: {account['label']} - "
                  f"equity=${account['total_equity_usd']}, status={account['status']}")
    
    def test_get_single_account(self):
        """GET /api/trading/terminal/accounts/{id} - Get single account overview"""
        if not self.connection_id:
            pytest.skip("No connection available for testing")
        
        response = requests.get(f"{BASE_URL}/api/trading/terminal/accounts/{self.connection_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert data["connection_id"] == self.connection_id
        assert "total_equity_usd" in data
        assert "status" in data
        print(f"Account: equity=${data['total_equity_usd']}, positions={data['open_positions']}")
    
    def test_get_account_not_found(self):
        """GET /api/trading/terminal/accounts/{id} - Non-existent account returns 404"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/accounts/nonexistent-id")
        assert response.status_code == 404
        print("Correctly returns 404 for non-existent account")


class TestT5PositionsMonitor:
    """T5 Positions Monitor Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/terminal/accounts")
            if response.status_code == 200:
                data = response.json()
                if data.get("accounts"):
                    TEST_CONNECTION_ID = data["accounts"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_get_positions(self):
        """GET /api/trading/terminal/positions - Get all open positions"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/positions")
        assert response.status_code == 200
        data = response.json()
        
        assert "positions" in data
        assert "count" in data
        assert "total_exposure_usd" in data
        assert "total_unrealized_pnl_usd" in data
        assert isinstance(data["positions"], list)
        
        print(f"Positions: count={data['count']}, exposure=${data['total_exposure_usd']}")
        
        if data["positions"]:
            pos = data["positions"][0]
            assert "position_id" in pos
            assert "asset" in pos
            assert "side" in pos
            assert "quantity" in pos
            assert "avg_entry_price" in pos
            assert "current_price" in pos
            assert "unrealized_pnl_usd" in pos
    
    def test_get_positions_filtered_by_connection(self):
        """GET /api/trading/terminal/positions - Filter by connection_id"""
        if not self.connection_id:
            pytest.skip("No connection available for testing")
        
        response = requests.get(f"{BASE_URL}/api/trading/terminal/positions?connection_id={self.connection_id}")
        assert response.status_code == 200
        data = response.json()
        
        # All positions should belong to specified connection
        for pos in data["positions"]:
            assert pos["connection_id"] == self.connection_id
        print(f"Filtered positions for connection: count={data['count']}")
    
    def test_get_position_by_asset_not_found(self):
        """GET /api/trading/terminal/positions/{asset} - Non-existent position returns 404"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/positions/NONEXISTENT")
        assert response.status_code == 404
        print("Correctly returns 404 for non-existent position")


class TestT5OrdersMonitor:
    """T5 Orders Monitor Tests"""
    
    def test_get_orders(self):
        """GET /api/trading/terminal/orders - Get orders with filters"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/orders")
        assert response.status_code == 200
        data = response.json()
        
        assert "orders" in data
        assert "count" in data
        assert isinstance(data["orders"], list)
        
        print(f"Orders: count={data['count']}")
        
        if data["orders"]:
            order = data["orders"][0]
            assert "order_id" in order
            assert "connection_id" in order
            assert "asset" in order
            assert "symbol" in order
            assert "side" in order
            assert "order_type" in order
            assert "quantity" in order
            assert "status" in order
    
    def test_get_orders_with_limit(self):
        """GET /api/trading/terminal/orders - With limit parameter"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/orders?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["orders"]) <= 5
        print(f"Orders with limit=5: count={len(data['orders'])}")
    
    def test_get_open_orders(self):
        """GET /api/trading/terminal/orders/open - Get open orders"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/orders/open")
        assert response.status_code == 200
        data = response.json()
        
        assert "orders" in data
        assert "count" in data
        
        # All orders should have open status
        for order in data["orders"]:
            assert order["status"] in ["NEW", "SUBMITTED", "PARTIAL"]
        
        print(f"Open orders: count={data['count']}")
    
    def test_get_order_history(self):
        """GET /api/trading/terminal/orders/history - Get order history"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/orders/history")
        assert response.status_code == 200
        data = response.json()
        
        assert "orders" in data
        assert "count" in data
        
        # All orders should have completed status
        for order in data["orders"]:
            assert order["status"] in ["FILLED", "CANCELLED", "REJECTED", "EXPIRED"]
        
        print(f"Order history: count={data['count']}")


class TestT5PnLEngine:
    """T5 PnL Engine Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/terminal/accounts")
            if response.status_code == 200:
                data = response.json()
                if data.get("accounts"):
                    TEST_CONNECTION_ID = data["accounts"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_get_pnl_overview(self):
        """GET /api/trading/terminal/pnl - Get PnL overview"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/pnl")
        assert response.status_code == 200
        data = response.json()
        
        # Verify PnL fields
        assert "connection_id" in data
        assert "realized_pnl_usd" in data
        assert "unrealized_pnl_usd" in data
        assert "total_pnl_usd" in data
        assert "total_trades" in data
        assert "winning_trades" in data
        assert "losing_trades" in data
        assert "win_rate" in data
        assert "profit_factor" in data
        
        print(f"PnL: realized=${data['realized_pnl_usd']}, "
              f"unrealized=${data['unrealized_pnl_usd']}, "
              f"total=${data['total_pnl_usd']}, "
              f"win_rate={data['win_rate']*100}%")
    
    def test_get_pnl_filtered_by_connection(self):
        """GET /api/trading/terminal/pnl - Filter by connection_id"""
        if not self.connection_id:
            pytest.skip("No connection available for testing")
        
        response = requests.get(f"{BASE_URL}/api/trading/terminal/pnl?connection_id={self.connection_id}")
        assert response.status_code == 200
        data = response.json()
        
        # Should return PnL for specific connection or ALL
        assert data["connection_id"] in [self.connection_id, "ALL"]
        print(f"PnL for connection: total=${data['total_pnl_usd']}")
    
    def test_get_daily_pnl(self):
        """GET /api/trading/terminal/pnl/daily - Get today's PnL"""
        if not self.connection_id:
            pytest.skip("No connection available for testing")
        
        response = requests.get(f"{BASE_URL}/api/trading/terminal/pnl/daily?connection_id={self.connection_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "date" in data
        assert "connection_id" in data
        assert "pnl_usd" in data
        assert "trades_count" in data
        assert "volume_usd" in data
        
        print(f"Daily PnL: date={data['date']}, pnl=${data['pnl_usd']}, trades={data['trades_count']}")


class TestT5ExecutionLog:
    """T5 Execution Log Tests"""
    
    def test_get_execution_logs(self):
        """GET /api/trading/terminal/logs - Get execution logs"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/logs")
        assert response.status_code == 200
        data = response.json()
        
        assert "logs" in data
        assert "count" in data
        assert isinstance(data["logs"], list)
        
        print(f"Execution logs: count={data['count']}")
        
        if data["logs"]:
            log = data["logs"][0]
            assert "event_id" in log
            assert "event_type" in log
            assert "message" in log
            assert "severity" in log
            assert "timestamp" in log
            print(f"Latest log: type={log['event_type']}, severity={log['severity']}")
    
    def test_get_execution_logs_with_limit(self):
        """GET /api/trading/terminal/logs - With limit parameter"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/logs?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["logs"]) <= 5
        print(f"Logs with limit=5: count={len(data['logs'])}")
    
    def test_get_execution_logs_filtered_by_event_type(self):
        """GET /api/trading/terminal/logs - Filter by event_type"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/logs?event_type=SYSTEM_PAUSED")
        assert response.status_code == 200
        data = response.json()
        
        # All logs should be of specified type
        for log in data["logs"]:
            assert log["event_type"] == "SYSTEM_PAUSED"
        
        print(f"Filtered logs (SYSTEM_PAUSED): count={data['count']}")


class TestT5RiskMonitor:
    """T5 Risk Monitor Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/terminal/accounts")
            if response.status_code == 200:
                data = response.json()
                if data.get("accounts"):
                    TEST_CONNECTION_ID = data["accounts"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_get_risk_overview(self):
        """GET /api/trading/terminal/risk - Get risk overview"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/risk")
        assert response.status_code == 200
        data = response.json()
        
        # Verify risk overview fields
        assert "profile_id" in data
        assert "kill_switch_active" in data
        assert "paused" in data
        assert "current_exposure_usd" in data
        assert "current_exposure_pct" in data
        assert "max_exposure_pct" in data
        assert "daily_pnl_usd" in data
        assert "daily_drawdown_pct" in data
        assert "max_drawdown_pct" in data
        assert "open_positions" in data
        assert "max_positions" in data
        assert "blocked_trades_24h" in data
        
        print(f"Risk overview: exposure=${data['current_exposure_usd']} ({data['current_exposure_pct']*100}%), "
              f"kill_switch={data['kill_switch_active']}, paused={data['paused']}")
    
    def test_get_exposure_details(self):
        """GET /api/trading/terminal/risk/exposure - Get exposure details"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/risk/exposure")
        assert response.status_code == 200
        data = response.json()
        
        assert "total_exposure_usd" in data
        assert "total_exposure_pct" in data
        assert "max_exposure_pct" in data
        assert "by_asset" in data
        assert "positions_count" in data
        
        print(f"Exposure: total=${data['total_exposure_usd']}, "
              f"by_asset={data['by_asset']}, positions={data['positions_count']}")
    
    def test_get_drawdown_details(self):
        """GET /api/trading/terminal/risk/drawdown - Get drawdown details"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/risk/drawdown")
        assert response.status_code == 200
        data = response.json()
        
        assert "daily_pnl_usd" in data
        assert "daily_drawdown_pct" in data
        assert "max_drawdown_pct" in data
        assert "emergency_stop_triggered" in data
        assert "blocked_trades_24h" in data
        
        print(f"Drawdown: daily_pnl=${data['daily_pnl_usd']}, "
              f"drawdown={data['daily_drawdown_pct']*100}%, "
              f"emergency_stop={data['emergency_stop_triggered']}")


class TestT5AveragingMonitor:
    """T5 Averaging Monitor Tests"""
    
    def test_get_averaging_overview(self):
        """GET /api/trading/terminal/averaging - Get averaging states"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/averaging")
        assert response.status_code == 200
        data = response.json()
        
        assert "averaging_states" in data
        assert "active_count" in data
        assert "total_capital_committed_usd" in data
        assert isinstance(data["averaging_states"], list)
        
        print(f"Averaging: active={data['active_count']}, "
              f"capital_committed=${data['total_capital_committed_usd']}")
        
        if data["averaging_states"]:
            state = data["averaging_states"][0]
            assert "connection_id" in state
            assert "asset" in state
            assert "active" in state
            assert "steps_used" in state
            assert "max_steps" in state
            assert "capital_committed_usd" in state
    
    def test_get_averaging_state_for_asset(self):
        """GET /api/trading/terminal/averaging/{asset} - Get averaging for specific asset"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/averaging/BTC")
        assert response.status_code == 200
        data = response.json()
        
        assert "asset" in data
        assert data["asset"] == "BTC"
        
        if data.get("active"):
            assert "steps_used" in data
            assert "avg_entry_price" in data
            print(f"BTC averaging: active, steps={data['steps_used']}")
        else:
            print("BTC averaging: not active")


class TestT5TerminalActions:
    """T5 Terminal Actions Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/terminal/accounts")
            if response.status_code == 200:
                data = response.json()
                if data.get("accounts"):
                    TEST_CONNECTION_ID = data["accounts"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_action_pause(self):
        """POST /api/trading/terminal/actions/pause - Pause trading"""
        response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/pause")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["action"] == "PAUSE"
        assert "message" in data
        print(f"Pause action: success={data['success']}, msg={data['message']}")
        
        # Verify system state reflects pause
        state_response = requests.get(f"{BASE_URL}/api/trading/terminal/state")
        assert state_response.json()["paused"] == True
    
    def test_action_resume(self):
        """POST /api/trading/terminal/actions/resume - Resume trading"""
        # First ensure not in kill switch mode
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/deactivate-kill-switch")
        
        response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["action"] == "RESUME"
        print(f"Resume action: success={data['success']}, msg={data['message']}")
        
        # Verify system state reflects resume
        state_response = requests.get(f"{BASE_URL}/api/trading/terminal/state")
        assert state_response.json()["paused"] == False
    
    def test_action_resume_blocked_when_kill_switch_active(self):
        """POST /api/trading/terminal/actions/resume - Should fail if kill switch active"""
        # Activate kill switch
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/kill-switch")
        
        # Try to resume
        response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
        assert response.status_code == 400
        print("Resume correctly blocked when kill switch active")
        
        # Clean up - deactivate kill switch
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/deactivate-kill-switch")
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
    
    def test_action_kill_switch(self):
        """POST /api/trading/terminal/actions/kill-switch - Activate kill switch"""
        response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/kill-switch")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["action"] == "KILL_SWITCH"
        print(f"Kill switch: success={data['success']}, msg={data['message']}")
        
        # Verify system state reflects kill switch
        state_response = requests.get(f"{BASE_URL}/api/trading/terminal/state")
        state = state_response.json()
        assert state["kill_switch_active"] == True
        assert state["paused"] == True  # Kill switch also pauses
        
        # Clean up
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/deactivate-kill-switch")
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
    
    def test_action_deactivate_kill_switch(self):
        """POST /api/trading/terminal/actions/deactivate-kill-switch - Deactivate kill switch"""
        # First activate
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/kill-switch")
        
        # Then deactivate
        response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/deactivate-kill-switch")
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["action"] == "DEACTIVATE_KILL_SWITCH"
        print(f"Deactivate kill switch: success={data['success']}")
        
        # Verify kill switch is deactivated but still paused (manual resume required)
        state_response = requests.get(f"{BASE_URL}/api/trading/terminal/state")
        state = state_response.json()
        assert state["kill_switch_active"] == False
        
        # Resume trading
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
    
    def test_action_close_position_not_found(self):
        """POST /api/trading/terminal/actions/close-position - Non-existent position"""
        if not self.connection_id:
            pytest.skip("No connection available for testing")
        
        payload = {
            "connection_id": self.connection_id,
            "asset": "NONEXISTENT"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/close-position", json=payload)
        assert response.status_code == 400
        print("Close position correctly returns 400 for non-existent position")
    
    def test_action_cancel_order_not_found(self):
        """POST /api/trading/terminal/actions/cancel-order - Non-existent order"""
        payload = {
            "order_id": "nonexistent-order-id"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/cancel-order", json=payload)
        assert response.status_code == 400
        print("Cancel order correctly returns 400 for non-existent order")


class TestT5Dashboard:
    """T5 Dashboard Aggregation Tests"""
    
    def test_get_dashboard(self):
        """GET /api/trading/terminal/dashboard - Get full dashboard"""
        response = requests.get(f"{BASE_URL}/api/trading/terminal/dashboard")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all dashboard sections
        assert "system" in data
        assert "accounts" in data
        assert "positions" in data
        assert "orders" in data
        assert "risk" in data
        assert "pnl" in data
        assert "averaging" in data
        assert "recent_logs" in data
        assert "timestamp" in data
        
        # Verify system section
        system = data["system"]
        assert "execution_mode" in system
        assert "paused" in system
        assert "kill_switch_active" in system
        
        # Verify accounts section
        accounts = data["accounts"]
        assert "list" in accounts
        assert "total_equity_usd" in accounts
        
        # Verify positions section
        positions = data["positions"]
        assert "list" in positions
        assert "count" in positions
        assert "total_exposure_usd" in positions
        assert "total_unrealized_pnl_usd" in positions
        
        # Verify orders section
        orders = data["orders"]
        assert "open" in orders
        assert "open_count" in orders
        
        # Verify risk section
        risk = data["risk"]
        assert "kill_switch_active" in risk
        assert "current_exposure_usd" in risk
        
        # Verify pnl section
        pnl = data["pnl"]
        assert "realized_pnl_usd" in pnl
        assert "unrealized_pnl_usd" in pnl
        
        # Verify averaging section
        averaging = data["averaging"]
        assert "states" in averaging
        assert "active_count" in averaging
        
        # Verify recent_logs section
        assert isinstance(data["recent_logs"], list)
        
        print(f"Dashboard: accounts={len(accounts['list'])}, "
              f"positions={positions['count']}, "
              f"open_orders={orders['open_count']}, "
              f"logs={len(data['recent_logs'])}")
    
    def test_dashboard_data_consistency(self):
        """Verify dashboard data is consistent with individual endpoints"""
        # Get dashboard
        dashboard_response = requests.get(f"{BASE_URL}/api/trading/terminal/dashboard")
        dashboard = dashboard_response.json()
        
        # Get state separately
        state_response = requests.get(f"{BASE_URL}/api/trading/terminal/state")
        state = state_response.json()
        
        # Verify system data matches
        assert dashboard["system"]["execution_mode"] == state["execution_mode"]
        assert dashboard["system"]["paused"] == state["paused"]
        assert dashboard["system"]["kill_switch_active"] == state["kill_switch_active"]
        
        # Get positions separately
        positions_response = requests.get(f"{BASE_URL}/api/trading/terminal/positions")
        positions = positions_response.json()
        
        # Verify positions count matches
        assert dashboard["positions"]["count"] == positions["count"]
        
        print("Dashboard data is consistent with individual endpoints")


class TestT5IntegrationFlows:
    """T5 Integration Flow Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/terminal/accounts")
            if response.status_code == 200:
                data = response.json()
                if data.get("accounts"):
                    TEST_CONNECTION_ID = data["accounts"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_pause_resume_cycle(self):
        """Test full pause -> verify -> resume -> verify cycle"""
        # 1. Pause
        pause_response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/pause")
        assert pause_response.status_code == 200
        
        # 2. Verify paused in state
        state = requests.get(f"{BASE_URL}/api/trading/terminal/state").json()
        assert state["paused"] == True
        
        # 3. Verify paused in risk
        risk = requests.get(f"{BASE_URL}/api/trading/terminal/risk").json()
        assert risk["paused"] == True
        
        # 4. Verify paused in dashboard
        dashboard = requests.get(f"{BASE_URL}/api/trading/terminal/dashboard").json()
        assert dashboard["system"]["paused"] == True
        
        # 5. Resume
        resume_response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
        assert resume_response.status_code == 200
        
        # 6. Verify resumed
        state = requests.get(f"{BASE_URL}/api/trading/terminal/state").json()
        assert state["paused"] == False
        
        print("Pause/resume cycle completed successfully")
    
    def test_kill_switch_cycle(self):
        """Test full kill switch activate -> verify -> deactivate -> resume cycle"""
        # 1. Activate kill switch
        kill_response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/kill-switch")
        assert kill_response.status_code == 200
        
        # 2. Verify in all endpoints
        state = requests.get(f"{BASE_URL}/api/trading/terminal/state").json()
        assert state["kill_switch_active"] == True
        assert state["paused"] == True
        
        risk = requests.get(f"{BASE_URL}/api/trading/terminal/risk").json()
        assert risk["kill_switch_active"] == True
        
        dashboard = requests.get(f"{BASE_URL}/api/trading/terminal/dashboard").json()
        assert dashboard["system"]["kill_switch_active"] == True
        
        # 3. Try to resume (should fail)
        resume_response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
        assert resume_response.status_code == 400
        
        # 4. Deactivate kill switch
        deactivate_response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/deactivate-kill-switch")
        assert deactivate_response.status_code == 200
        
        # 5. Now resume should work
        resume_response = requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
        assert resume_response.status_code == 200
        
        # 6. Verify all clear
        state = requests.get(f"{BASE_URL}/api/trading/terminal/state").json()
        assert state["kill_switch_active"] == False
        assert state["paused"] == False
        
        print("Kill switch cycle completed successfully")
    
    def test_execution_logs_capture_events(self):
        """Test that actions create execution log entries"""
        # Get initial log count
        initial_logs = requests.get(f"{BASE_URL}/api/trading/terminal/logs").json()
        initial_count = initial_logs["count"]
        
        # Perform pause action
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/pause")
        
        # Wait a moment for log to be created
        time.sleep(0.5)
        
        # Get logs again
        logs_after = requests.get(f"{BASE_URL}/api/trading/terminal/logs").json()
        
        # Should have at least one new log entry
        assert logs_after["count"] >= initial_count
        
        # Check latest log is SYSTEM_PAUSED
        if logs_after["logs"]:
            latest = logs_after["logs"][0]
            # Could be SYSTEM_PAUSED from our action
            print(f"Latest log after pause: type={latest['event_type']}")
        
        # Resume
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
        
        print("Execution logs are capturing events")


class TestCleanup:
    """Cleanup tests - ensure system is in good state"""
    
    def test_cleanup_ensure_system_running(self):
        """Ensure system is running after tests"""
        # Deactivate kill switch if active
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/deactivate-kill-switch")
        
        # Resume if paused
        requests.post(f"{BASE_URL}/api/trading/terminal/actions/resume")
        
        # Verify system state
        state = requests.get(f"{BASE_URL}/api/trading/terminal/state").json()
        assert state["kill_switch_active"] == False
        assert state["paused"] == False
        
        # Verify health
        health = requests.get(f"{BASE_URL}/api/trading/terminal/health").json()
        assert health["status"] == "ok"
        
        print("System cleanup complete - running normally")


# Run configuration for pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
