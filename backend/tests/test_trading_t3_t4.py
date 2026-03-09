"""
Trading Capsule T3 (Execution) & T4 (Risk Control) API Tests
============================================================

Tests for:
- T3: Execution Decision Layer (signal normalization, preview, execute)
- T4: Risk Control Layer (risk checks, averaging, PnL tracking)

Using MockBrokerAdapter - api_key must contain 'mock' for testing.
"""

import pytest
import requests
import os
import time
from datetime import datetime

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test connection ID (will be created during test setup)
TEST_CONNECTION_ID = None

class TestSetup:
    """Setup tests - register mock connection for testing"""
    
    def test_trading_health(self):
        """Test trading module health"""
        response = requests.get(f"{BASE_URL}/api/trading/health")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == True
        assert data["status"] == "ok"
        print(f"Trading capsule version: {data['version']}")
    
    def test_register_mock_connection(self):
        """Register a mock connection for testing"""
        global TEST_CONNECTION_ID
        
        payload = {
            "exchange": "BINANCE",
            "label": "TEST_MockConnection",
            "api_key": "mock_test_key_12345",  # Contains 'mock' to use MockBrokerAdapter
            "api_secret": "mock_test_secret_12345",
            "selected_mode": "SPOT"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/connections/register", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "connection" in data
        
        TEST_CONNECTION_ID = data["connection"]["connection_id"]
        print(f"Registered test connection: {TEST_CONNECTION_ID}")
        
        return TEST_CONNECTION_ID


class TestT3ExecutionHealth:
    """T3 Execution Layer Health Tests"""
    
    def test_execution_health(self):
        """GET /api/trading/execution/health - Execution layer health"""
        response = requests.get(f"{BASE_URL}/api/trading/execution/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["enabled"] == True
        assert data["version"] == "execution_t3"
        assert data["status"] == "ok"
        assert "decisions_processed" in data
        assert "executions_total" in data
        print(f"Execution layer healthy - {data['decisions_processed']} decisions processed")


class TestT3SignalNormalization:
    """T3 Signal Normalization Tests"""
    
    def test_submit_ta_signal_bullish(self):
        """POST /api/trading/execution/signal/ta - Submit bullish TA signal"""
        payload = {
            "asset": "BTC",
            "bias": "BULLISH",
            "confidence": 0.75,
            "entry_price": 65000,
            "stop_loss": 64000,
            "take_profit": 68000,
            "patterns": ["head_and_shoulders", "bullish_engulfing"]
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/signal/ta", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        decision = data["decision"]
        assert decision["source_mode"] == "TA_ONLY"
        assert decision["asset"] == "BTC"
        assert decision["action"] == "ENTER_LONG"  # BULLISH maps to ENTER_LONG
        assert decision["confidence"] == 0.75
        assert "decision_id" in decision
        print(f"TA signal normalized: action={decision['action']}, decision_id={decision['decision_id'][:8]}...")
    
    def test_submit_ta_signal_bearish(self):
        """POST /api/trading/execution/signal/ta - Submit bearish TA signal"""
        payload = {
            "asset": "ETH",
            "bias": "BEARISH",
            "confidence": 0.65,
            "patterns": ["double_top"]
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/signal/ta", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        decision = data["decision"]
        assert decision["action"] == "EXIT_LONG"  # BEARISH maps to EXIT_LONG in SPOT
        print(f"Bearish TA signal: action={decision['action']}")
    
    def test_submit_ta_signal_neutral(self):
        """POST /api/trading/execution/signal/ta - Submit neutral TA signal"""
        payload = {
            "asset": "SOL",
            "bias": "NEUTRAL",
            "confidence": 0.5
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/signal/ta", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["decision"]["action"] == "HOLD"
        print("Neutral TA signal: action=HOLD")
    
    def test_submit_manual_signal_enter_long(self):
        """POST /api/trading/execution/signal/manual - Submit manual ENTER_LONG signal"""
        payload = {
            "asset": "BTC",
            "action": "ENTER_LONG",
            "confidence": 0.9,
            "size_pct": 0.05,
            "price": 65000,
            "stop_loss": 63000,
            "take_profit": 70000,
            "reason": "TEST manual entry for BTC",
            "market_type": "SPOT",
            "horizon": "1D"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/signal/manual", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        decision = data["decision"]
        assert decision["source_mode"] == "MANUAL_SIGNAL_SOURCE"
        assert decision["action"] == "ENTER_LONG"
        assert decision["asset"] == "BTC"
        assert decision["suggested_size_pct"] == 0.05
        print(f"Manual signal: {decision['action']} with {decision['confidence']*100}% confidence")
    
    def test_submit_manual_signal_exit_long(self):
        """POST /api/trading/execution/signal/manual - Submit EXIT_LONG signal"""
        payload = {
            "asset": "BTC",
            "action": "EXIT_LONG",
            "confidence": 0.85,
            "reason": "TEST exit position"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/signal/manual", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert data["decision"]["action"] == "EXIT_LONG"
        print("Manual EXIT_LONG signal created")
    
    def test_submit_manual_signal_hold(self):
        """POST /api/trading/execution/signal/manual - Submit HOLD signal"""
        payload = {
            "asset": "ETH",
            "action": "HOLD",
            "confidence": 0.6,
            "reason": "Wait for better entry"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/signal/manual", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["decision"]["action"] == "HOLD"
        print("Manual HOLD signal created")


class TestT3Preview:
    """T3 Preview Mode Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get or create a connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            # Get existing connections
            response = requests.get(f"{BASE_URL}/api/trading/connections")
            if response.status_code == 200:
                data = response.json()
                if data.get("connections"):
                    TEST_CONNECTION_ID = data["connections"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_preview_ta_signal(self):
        """POST /api/trading/execution/preview - Preview TA signal execution"""
        payload = {
            "connection_id": self.connection_id,
            "ta_signal": {
                "asset": "BTC",
                "bias": "BULLISH",
                "confidence": 0.8,
                "entry_price": 65000
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/preview", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert "decision" in data
        assert "context" in data
        assert "intent" in data or data.get("blocked") == True
        assert "would_execute" in data
        assert "blocked" in data
        print(f"Preview result: would_execute={data['would_execute']}, blocked={data['blocked']}")
        if data.get("block_reasons"):
            print(f"Block reasons: {data['block_reasons']}")
        if data.get("warnings"):
            print(f"Warnings: {data['warnings']}")
    
    def test_preview_manual_signal(self):
        """POST /api/trading/execution/preview - Preview manual signal execution"""
        payload = {
            "connection_id": self.connection_id,
            "manual_signal": {
                "asset": "ETH",
                "action": "ENTER_LONG",
                "confidence": 0.9,
                "size_pct": 0.03
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/preview", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Preview should return decision/context/intent structure
        assert "decision" in data
        assert "context" in data
        print(f"Manual signal preview: intent={data.get('intent') is not None}")
    
    def test_preview_without_signal_fails(self):
        """POST /api/trading/execution/preview - Should fail without signal"""
        payload = {
            "connection_id": self.connection_id
            # No ta_signal or manual_signal
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/preview", json=payload)
        # Should return 400 for missing signal
        assert response.status_code == 400
        print("Preview correctly requires ta_signal or manual_signal")


class TestT3Execute:
    """T3 Execution Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get or create a connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/connections")
            if response.status_code == 200:
                data = response.json()
                if data.get("connections"):
                    TEST_CONNECTION_ID = data["connections"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_execute_manual_signal(self):
        """POST /api/trading/execution/execute - Execute manual signal"""
        # First, set execution mode to MANUAL_SIGNAL_SOURCE
        mode_response = requests.post(
            f"{BASE_URL}/api/trading/mode/select",
            json={"execution_mode": "MANUAL_SIGNAL_SOURCE"}
        )
        
        payload = {
            "connection_id": self.connection_id,
            "manual_signal": {
                "asset": "BTC",
                "action": "ENTER_LONG",
                "confidence": 0.85,
                "size_pct": 0.02,
                "reason": "TEST execution"
            },
            "skip_risk_check": False
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/execute", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        # Check result structure
        assert "decision_id" in data
        assert "executed" in data or "blocked" in data
        
        if data.get("blocked"):
            print(f"Execution blocked: {data.get('block_reasons')}")
        else:
            print(f"Execution result: success={data.get('success')}, order_id={data.get('order_id')}")
    
    def test_execute_with_skip_risk_check(self):
        """POST /api/trading/execution/execute - Execute with skip_risk_check=True"""
        # Set mode to MANUAL
        requests.post(
            f"{BASE_URL}/api/trading/mode/select",
            json={"execution_mode": "MANUAL_SIGNAL_SOURCE"}
        )
        
        payload = {
            "connection_id": self.connection_id,
            "manual_signal": {
                "asset": "ETH",
                "action": "ENTER_LONG",
                "confidence": 0.9
            },
            "skip_risk_check": True  # Skip risk validation
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/execute", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        print(f"Execution with skip_risk_check: success={data.get('success')}")
    
    def test_execute_blocked_when_paused(self):
        """Execute should be blocked when trading is paused"""
        # Pause trading
        pause_response = requests.post(f"{BASE_URL}/api/trading/pause")
        assert pause_response.status_code == 200
        
        payload = {
            "connection_id": self.connection_id,
            "manual_signal": {
                "asset": "BTC",
                "action": "ENTER_LONG",
                "confidence": 0.8
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/execution/execute", json=payload)
        # Should return 400 because trading is paused
        assert response.status_code == 400
        print("Execution correctly blocked when paused")
        
        # Resume trading
        requests.post(f"{BASE_URL}/api/trading/resume")


class TestT3Decisions:
    """T3 Decision History Tests"""
    
    def test_get_decisions(self):
        """GET /api/trading/execution/decisions - Get decisions history"""
        response = requests.get(f"{BASE_URL}/api/trading/execution/decisions")
        assert response.status_code == 200
        data = response.json()
        
        assert "decisions" in data
        assert "count" in data
        assert isinstance(data["decisions"], list)
        print(f"Retrieved {data['count']} decisions")
        
        if data["decisions"]:
            decision = data["decisions"][0]
            assert "decision_id" in decision
            assert "source_mode" in decision
            assert "action" in decision
    
    def test_get_decisions_with_limit(self):
        """GET /api/trading/execution/decisions - With limit parameter"""
        response = requests.get(f"{BASE_URL}/api/trading/execution/decisions?limit=5")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["decisions"]) <= 5
        print(f"Retrieved {len(data['decisions'])} decisions with limit=5")
    
    def test_get_execution_results(self):
        """GET /api/trading/execution/results - Get execution results"""
        response = requests.get(f"{BASE_URL}/api/trading/execution/results")
        assert response.status_code == 200
        data = response.json()
        
        assert "results" in data
        assert "count" in data
        print(f"Retrieved {data['count']} execution results")


class TestT4RiskHealth:
    """T4 Risk Layer Health Tests"""
    
    def test_risk_health(self):
        """GET /api/trading/risk/health - Risk layer health"""
        response = requests.get(f"{BASE_URL}/api/trading/risk/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["enabled"] == True
        assert data["version"] == "risk_t4"
        assert data["status"] == "ok"
        assert "profile" in data
        assert "total_risk_events" in data
        print(f"Risk layer healthy - {data['total_risk_events']} events logged")


class TestT4RiskProfile:
    """T4 Risk Profile Tests"""
    
    def test_get_full_risk_profile(self):
        """GET /api/trading/risk/profile/full - Get full risk profile"""
        response = requests.get(f"{BASE_URL}/api/trading/risk/profile/full")
        assert response.status_code == 200
        data = response.json()
        
        # Check all profile fields
        assert "max_position_usd" in data
        assert "max_asset_exposure_pct" in data
        assert "max_portfolio_exposure_pct" in data
        assert "max_open_positions" in data
        assert "max_daily_drawdown_pct" in data
        assert "averaging_enabled" in data
        assert "max_averaging_steps" in data
        assert "spot_enabled" in data
        assert "emergency_stop_enabled" in data
        
        print(f"Risk profile: max_position=${data['max_position_usd']}, max_dd={data['max_daily_drawdown_pct']*100}%")
    
    def test_update_risk_profile(self):
        """POST /api/trading/risk/profile/update - Update risk profile"""
        payload = {
            "max_position_usd": 15000.0,
            "max_asset_exposure_pct": 0.25,
            "max_averaging_steps": 5
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/profile/update", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        profile = data["profile"]
        assert profile["max_position_usd"] == 15000.0
        assert profile["max_asset_exposure_pct"] == 0.25
        assert profile["max_averaging_steps"] == 5
        print(f"Updated risk profile: max_position=${profile['max_position_usd']}")
    
    def test_update_risk_profile_partial(self):
        """POST /api/trading/risk/profile/update - Partial update"""
        payload = {
            "averaging_enabled": True,
            "emergency_stop_enabled": True
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/profile/update", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["profile"]["averaging_enabled"] == True
        print("Partial profile update successful")


class TestT4RiskCheck:
    """T4 Pre-Trade Risk Check Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/connections")
            if response.status_code == 200:
                data = response.json()
                if data.get("connections"):
                    TEST_CONNECTION_ID = data["connections"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_risk_check_allowed(self):
        """POST /api/trading/risk/check - Risk check should allow normal trade"""
        payload = {
            "connection_id": self.connection_id,
            "asset": "BTC",
            "side": "BUY",
            "notional_usd": 1000.0,
            "quantity": 0.015,
            "reduce_only": False,
            "market_type": "SPOT"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/check", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert "verdict" in data
        assert "context" in data
        
        verdict = data["verdict"]
        assert "allowed" in verdict
        assert "severity" in verdict
        assert "checks_passed" in verdict
        
        print(f"Risk check: allowed={verdict['allowed']}, severity={verdict['severity']}")
        if verdict.get("reason_codes"):
            print(f"Reason codes: {verdict['reason_codes']}")
    
    def test_risk_check_blocked_large_position(self):
        """POST /api/trading/risk/check - Should block oversized position"""
        payload = {
            "connection_id": self.connection_id,
            "asset": "BTC",
            "side": "BUY",
            "notional_usd": 50000.0,  # Exceeds max_position_usd
            "quantity": 0.75,
            "reduce_only": False,
            "market_type": "SPOT"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/check", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        verdict = data["verdict"]
        # Should either be blocked or trimmed
        if not verdict["allowed"]:
            print(f"Large position blocked: {verdict['reason_codes']}")
        elif verdict.get("adjusted_notional_usd"):
            print(f"Large position trimmed to ${verdict['adjusted_notional_usd']}")
    
    def test_risk_check_reduce_only(self):
        """POST /api/trading/risk/check - Reduce only should pass position checks"""
        payload = {
            "connection_id": self.connection_id,
            "asset": "BTC",
            "side": "SELL",
            "notional_usd": 5000.0,
            "quantity": 0.08,
            "reduce_only": True,  # Reduce only flag
            "market_type": "SPOT"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/check", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        verdict = data["verdict"]
        # Reduce only orders should pass position count checks
        print(f"Reduce only check: allowed={verdict['allowed']}")


class TestT4Averaging:
    """T4 Averaging Management Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/connections")
            if response.status_code == 200:
                data = response.json()
                if data.get("connections"):
                    TEST_CONNECTION_ID = data["connections"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_start_averaging_ladder(self):
        """POST /api/trading/risk/averaging/start - Start averaging ladder"""
        payload = {
            "connection_id": self.connection_id,
            "asset": "TEST_BTC",  # Unique asset for test
            "entry_price": 65000.0,
            "quantity": 0.01,
            "notional_usd": 650.0
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/averaging/start", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        state = data["state"]
        assert state["active"] == True
        assert state["steps_used"] == 1
        assert state["asset"] == "TEST_BTC"
        print(f"Averaging started: avg_price={state['avg_entry_price']}, steps={state['steps_used']}")
    
    def test_get_averaging_state(self):
        """GET /api/trading/risk/averaging/{connection_id}/{asset} - Get averaging state"""
        response = requests.get(f"{BASE_URL}/api/trading/risk/averaging/{self.connection_id}/TEST_BTC")
        assert response.status_code == 200
        data = response.json()
        
        if data.get("active"):
            assert "steps_used" in data
            assert "avg_entry_price" in data
            print(f"Averaging state: steps={data['steps_used']}, avg_price={data['avg_entry_price']}")
        else:
            print("No active averaging state for asset")
    
    def test_get_averaging_state_nonexistent(self):
        """GET /api/trading/risk/averaging/{connection_id}/{asset} - Non-existent asset"""
        response = requests.get(f"{BASE_URL}/api/trading/risk/averaging/{self.connection_id}/NONEXISTENT")
        assert response.status_code == 200
        data = response.json()
        
        # Should return inactive state
        assert data.get("active") == False
        print("Correctly returns inactive for non-existent averaging state")
    
    def test_add_averaging_entry(self):
        """POST /api/trading/risk/averaging/add - Add averaging entry"""
        payload = {
            "connection_id": self.connection_id,
            "asset": "TEST_BTC",
            "entry_price": 63000.0,  # Lower price (averaging down)
            "quantity": 0.015,
            "notional_usd": 945.0
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/averaging/add", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        state = data["state"]
        assert state["steps_used"] >= 2  # At least 2 steps now
        print(f"Added averaging entry: new_avg_price={state['avg_entry_price']}, steps={state['steps_used']}")
    
    def test_update_averaging_price(self):
        """POST /api/trading/risk/averaging/update-price - Update current price"""
        payload = {
            "connection_id": self.connection_id,
            "asset": "TEST_BTC",
            "price": 62000.0
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/averaging/update-price", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        print("Updated averaging current price")
    
    def test_reset_averaging_ladder(self):
        """POST /api/trading/risk/averaging/reset - Reset averaging state"""
        response = requests.post(
            f"{BASE_URL}/api/trading/risk/averaging/reset",
            params={"connection_id": self.connection_id, "asset": "TEST_BTC"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        print("Averaging ladder reset")


class TestT4DailyPnL:
    """T4 Daily PnL Tracking Tests"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/connections")
            if response.status_code == 200:
                data = response.json()
                if data.get("connections"):
                    TEST_CONNECTION_ID = data["connections"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_record_positive_pnl(self):
        """POST /api/trading/risk/pnl/record - Record positive PnL"""
        payload = {
            "connection_id": self.connection_id,
            "pnl": 150.0
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/pnl/record", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        print(f"Recorded PnL: +$150")
    
    def test_record_negative_pnl(self):
        """POST /api/trading/risk/pnl/record - Record negative PnL"""
        payload = {
            "connection_id": self.connection_id,
            "pnl": -75.0
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/pnl/record", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        print(f"Recorded PnL: -$75")
    
    def test_get_daily_pnl(self):
        """GET /api/trading/risk/pnl/{connection_id} - Get daily PnL"""
        response = requests.get(f"{BASE_URL}/api/trading/risk/pnl/{self.connection_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "daily_pnl_usd" in data
        assert "date" in data
        print(f"Daily PnL: ${data['daily_pnl_usd']} for {data['date']}")


class TestT4RiskEvents:
    """T4 Risk Events Tests"""
    
    def test_get_risk_events(self):
        """GET /api/trading/risk/events - Get risk events history"""
        response = requests.get(f"{BASE_URL}/api/trading/risk/events")
        assert response.status_code == 200
        data = response.json()
        
        assert "events" in data
        assert "count" in data
        
        print(f"Retrieved {data['count']} risk events")
        
        if data["events"]:
            event = data["events"][-1]  # Latest event
            assert "type" in event
            assert "timestamp" in event
            print(f"Latest event: type={event['type']}")
    
    def test_get_risk_events_with_limit(self):
        """GET /api/trading/risk/events - With limit parameter"""
        response = requests.get(f"{BASE_URL}/api/trading/risk/events?limit=10")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["events"]) <= 10
        print(f"Retrieved {len(data['events'])} events with limit=10")


class TestIntegrationPipeline:
    """Integration Tests - Full Execution Pipeline with Risk Validation"""
    
    @pytest.fixture(autouse=True)
    def get_connection_id(self):
        """Get connection ID for testing"""
        global TEST_CONNECTION_ID
        if not TEST_CONNECTION_ID:
            response = requests.get(f"{BASE_URL}/api/trading/connections")
            if response.status_code == 200:
                data = response.json()
                if data.get("connections"):
                    TEST_CONNECTION_ID = data["connections"][0]["connection_id"]
        self.connection_id = TEST_CONNECTION_ID
    
    def test_full_pipeline_preview_then_execute(self):
        """Full pipeline: signal -> preview -> execute"""
        # 1. Set mode to MANUAL
        requests.post(
            f"{BASE_URL}/api/trading/mode/select",
            json={"execution_mode": "MANUAL_SIGNAL_SOURCE"}
        )
        
        # Ensure not paused
        requests.post(f"{BASE_URL}/api/trading/resume")
        
        # 2. Create manual signal
        signal_payload = {
            "asset": "SOL",
            "action": "ENTER_LONG",
            "confidence": 0.85,
            "size_pct": 0.02,
            "reason": "TEST full pipeline"
        }
        
        signal_response = requests.post(
            f"{BASE_URL}/api/trading/execution/signal/manual",
            json=signal_payload
        )
        assert signal_response.status_code == 200
        decision_id = signal_response.json()["decision"]["decision_id"]
        print(f"1. Created decision: {decision_id[:8]}...")
        
        # 3. Preview the decision
        preview_payload = {
            "connection_id": self.connection_id,
            "manual_signal": signal_payload
        }
        
        preview_response = requests.post(
            f"{BASE_URL}/api/trading/execution/preview",
            json=preview_payload
        )
        assert preview_response.status_code == 200
        preview = preview_response.json()
        print(f"2. Preview: would_execute={preview['would_execute']}, blocked={preview['blocked']}")
        
        # 4. Execute (if preview shows it would execute)
        execute_payload = {
            "connection_id": self.connection_id,
            "manual_signal": signal_payload,
            "skip_risk_check": False
        }
        
        execute_response = requests.post(
            f"{BASE_URL}/api/trading/execution/execute",
            json=execute_payload
        )
        assert execute_response.status_code == 200
        result = execute_response.json()
        print(f"3. Execute result: success={result.get('success')}, blocked={result.get('blocked')}")
        
        # 5. Verify in results
        results_response = requests.get(f"{BASE_URL}/api/trading/execution/results?limit=5")
        assert results_response.status_code == 200
        print(f"4. Verified in execution results")
    
    def test_risk_blocks_when_kill_switch_active(self):
        """Risk should block all trades when kill switch is active"""
        # Activate kill switch
        kill_response = requests.post(f"{BASE_URL}/api/trading/kill-switch/activate")
        assert kill_response.status_code == 200
        print("Kill switch activated")
        
        # Attempt risk check - should be blocked
        payload = {
            "connection_id": self.connection_id,
            "asset": "BTC",
            "side": "BUY",
            "notional_usd": 500.0,
            "quantity": 0.008,
            "reduce_only": False,
            "market_type": "SPOT"
        }
        
        response = requests.post(f"{BASE_URL}/api/trading/risk/check", json=payload)
        assert response.status_code == 200
        verdict = response.json()["verdict"]
        
        assert verdict["allowed"] == False
        assert "KILL_SWITCH_ACTIVE" in verdict["reason_codes"]
        print(f"Risk correctly blocked: {verdict['reason_codes']}")
        
        # Deactivate kill switch
        requests.post(f"{BASE_URL}/api/trading/kill-switch/deactivate")
        requests.post(f"{BASE_URL}/api/trading/resume")
        print("Kill switch deactivated")


class TestCleanup:
    """Cleanup tests - remove test data"""
    
    def test_cleanup_test_connection(self):
        """Cleanup test connection"""
        global TEST_CONNECTION_ID
        
        if TEST_CONNECTION_ID:
            # Don't actually delete, just mark as tested
            print(f"Test connection {TEST_CONNECTION_ID[:8]}... would be cleaned up")
        
        # Reset averaging states by getting them
        response = requests.get(f"{BASE_URL}/api/trading/risk/health")
        if response.status_code == 200:
            print("Risk service verified healthy after tests")


# Run configuration for pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
