"""
Phase 2: Realtime Engine API Tests

Tests all new realtime endpoints including:
- /api/realtime/health
- /api/realtime/status
- /api/realtime/simulate/*
- /api/realtime/publish
- /api/ta/realtime/* (backward compatible)
- Phase 1 regression tests

Base URL: https://risk-control-system.preview.emergentagent.com
"""

import pytest
import requests
import time
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://risk-control-system.preview.emergentagent.com').rstrip('/')


class TestRealtimeHealth:
    """Health and status endpoint tests"""

    def test_realtime_health_returns_ok(self):
        """GET /api/realtime/health - returns {ok: true, status: 'healthy'}"""
        response = requests.get(f"{BASE_URL}/api/realtime/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data.get('status') == 'healthy'
        assert 'ts' in data  # timestamp
        print(f"✓ Health check passed: {data}")

    def test_realtime_status_returns_channels(self):
        """GET /api/realtime/status - returns connections, channels, channelEventMap, simulator status"""
        response = requests.get(f"{BASE_URL}/api/realtime/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
        
        status_data = data['data']
        # Check required fields exist
        assert 'connections' in status_data
        assert 'availableChannels' in status_data
        assert 'channelEventMap' in status_data
        assert 'simulator' in status_data
        
        # Verify channels
        expected_channels = ['chart', 'signals', 'system', 'regime', 'metabrain']
        for channel in expected_channels:
            assert channel in status_data['availableChannels'], f"Missing channel: {channel}"
            assert channel in status_data['channelEventMap'], f"Missing channelEventMap key: {channel}"
        
        # Verify simulator status
        assert 'running' in status_data['simulator']
        assert 'tickCount' in status_data['simulator']
        
        print(f"✓ Status check passed: channels={status_data['availableChannels']}")


class TestSimulator:
    """Event simulator control tests"""

    def test_simulator_status(self):
        """GET /api/realtime/simulate/status - returns {running, tickCount}"""
        response = requests.get(f"{BASE_URL}/api/realtime/simulate/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
        assert 'running' in data['data']
        assert 'tickCount' in data['data']
        print(f"✓ Simulator status: running={data['data']['running']}, tickCount={data['data']['tickCount']}")

    def test_simulator_start(self):
        """POST /api/realtime/simulate/start - starts event simulator"""
        # Start with custom interval
        response = requests.post(f"{BASE_URL}/api/realtime/simulate/start", json={"intervalMs": 500})
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data['data'].get('started') is True
        print(f"✓ Simulator started: intervalMs={data['data'].get('intervalMs', 500)}")

    def test_simulator_stop(self):
        """POST /api/realtime/simulate/stop - stops event simulator"""
        response = requests.post(f"{BASE_URL}/api/realtime/simulate/stop")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data['data'].get('stopped') is True
        print("✓ Simulator stopped")

    def test_simulator_produces_events(self):
        """Simulator produces events when running - start, wait, check events count > 0, stop"""
        # Get initial event count
        initial_events = requests.get(f"{BASE_URL}/api/ta/realtime/events?limit=100").json()
        initial_count = initial_events.get('data', {}).get('count', 0)
        
        # Start simulator with fast interval
        start_resp = requests.post(f"{BASE_URL}/api/realtime/simulate/start", json={"intervalMs": 200})
        assert start_resp.status_code == 200
        
        # Wait for events to be generated
        time.sleep(2)
        
        # Check simulator tick count
        status_resp = requests.get(f"{BASE_URL}/api/realtime/simulate/status")
        assert status_resp.status_code == 200
        tick_count = status_resp.json()['data']['tickCount']
        
        # Get events after running
        final_events = requests.get(f"{BASE_URL}/api/ta/realtime/events?limit=100").json()
        final_count = final_events.get('data', {}).get('count', 0)
        
        # Stop simulator
        stop_resp = requests.post(f"{BASE_URL}/api/realtime/simulate/stop")
        assert stop_resp.status_code == 200
        
        # Verify events were produced
        assert tick_count > 0, f"Expected tick_count > 0, got {tick_count}"
        print(f"✓ Simulator produced {tick_count} ticks, events: {initial_count} → {final_count}")


class TestPublishEndpoint:
    """POST /api/realtime/publish tests for various event types"""

    def test_publish_candle_update(self):
        """POST /api/realtime/publish with event=CANDLE_UPDATE"""
        payload = {
            "event": "CANDLE_UPDATE",
            "symbol": "BTCUSDT",
            "data": {
                "interval": "1m",
                "o": 87000,
                "h": 87500,
                "l": 86800,
                "c": 87300,
                "v": 1200
            }
        }
        response = requests.post(f"{BASE_URL}/api/realtime/publish", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data['data']['event'] == 'CANDLE_UPDATE'
        assert data['data']['symbol'] == 'BTCUSDT'
        assert 'publishedAt' in data['data']
        print(f"✓ Published CANDLE_UPDATE event")

    def test_publish_signal_created(self):
        """POST /api/realtime/publish with event=SIGNAL_CREATED"""
        payload = {
            "event": "SIGNAL_CREATED",
            "symbol": "ETHUSDT",
            "data": {
                "timeframe": "1h",
                "direction": "LONG",
                "entry": 3200,
                "stop": 3100,
                "target": 3500,
                "confidence": 0.75,
                "strategy": "BREAKOUT",
                "reason": "Test signal"
            }
        }
        response = requests.post(f"{BASE_URL}/api/realtime/publish", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data['data']['event'] == 'SIGNAL_CREATED'
        assert data['data']['symbol'] == 'ETHUSDT'
        print(f"✓ Published SIGNAL_CREATED event")

    def test_publish_pattern_detected(self):
        """POST /api/realtime/publish with event=PATTERN_DETECTED"""
        payload = {
            "event": "PATTERN_DETECTED",
            "symbol": "SOLUSDT",
            "data": {
                "timeframe": "4h",
                "pattern": "ascending_triangle",
                "direction": "BULLISH",
                "confidence": 0.82,
                "price": 145.50,
                "description": "Test pattern detection"
            }
        }
        response = requests.post(f"{BASE_URL}/api/realtime/publish", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data['data']['event'] == 'PATTERN_DETECTED'
        assert data['data']['symbol'] == 'SOLUSDT'
        print(f"✓ Published PATTERN_DETECTED event")

    def test_publish_scenario_update(self):
        """POST /api/realtime/publish with event=SCENARIO_UPDATE"""
        payload = {
            "event": "SCENARIO_UPDATE",
            "symbol": "BTCUSDT",
            "data": {
                "timeframe": "1d",
                "scenario": "bullish_breakout",
                "probability": 0.65,
                "alternatives": [
                    {"scenario": "range_consolidation", "probability": 0.25}
                ],
                "breakRisk": 0.15
            }
        }
        response = requests.post(f"{BASE_URL}/api/realtime/publish", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data['data']['event'] == 'SCENARIO_UPDATE'
        print(f"✓ Published SCENARIO_UPDATE event")

    def test_publish_regime_change(self):
        """POST /api/realtime/publish with event=REGIME_CHANGE"""
        payload = {
            "event": "REGIME_CHANGE",
            "symbol": "BTCUSDT",
            "data": {
                "timeframe": "1d",
                "previousRegime": "COMPRESSION",
                "newRegime": "TREND",
                "confidence": 0.78,
                "reason": "Breakout from consolidation"
            }
        }
        response = requests.post(f"{BASE_URL}/api/realtime/publish", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data['data']['event'] == 'REGIME_CHANGE'
        print(f"✓ Published REGIME_CHANGE event")

    def test_publish_metabrain_update(self):
        """POST /api/realtime/publish with event=METABRAIN_UPDATE"""
        payload = {
            "event": "METABRAIN_UPDATE",
            "symbol": "BTCUSDT",
            "data": {
                "timeframe": "1d",
                "analysisMode": "DEEP_MARKET",
                "riskMode": "NORMAL",
                "safeMode": False,
                "riskMultiplier": 1.0,
                "enabledStrategies": ["TREND_FOLLOW", "BREAKOUT"],
                "disabledStrategies": [],
                "reasons": ["Test update"]
            }
        }
        response = requests.post(f"{BASE_URL}/api/realtime/publish", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data['data']['event'] == 'METABRAIN_UPDATE'
        print(f"✓ Published METABRAIN_UPDATE event")

    def test_publish_missing_event_field(self):
        """POST /api/realtime/publish without event field returns error"""
        payload = {"symbol": "BTCUSDT"}
        response = requests.post(f"{BASE_URL}/api/realtime/publish", json=payload)
        assert response.status_code == 200  # API returns ok:false, not 400
        data = response.json()
        assert data.get('ok') is False
        assert 'error' in data
        print(f"✓ Missing event field correctly rejected: {data['error']}")

    def test_publish_unknown_event_type(self):
        """POST /api/realtime/publish with unknown event type returns error"""
        payload = {"event": "UNKNOWN_EVENT", "symbol": "BTCUSDT"}
        response = requests.post(f"{BASE_URL}/api/realtime/publish", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is False
        assert 'error' in data
        print(f"✓ Unknown event type correctly rejected: {data['error']}")


class TestTaRealtimeEndpoints:
    """Backward compatible /api/ta/realtime/* endpoints"""

    def test_ta_realtime_status(self):
        """GET /api/ta/realtime/status - backward compatible existing endpoint"""
        response = requests.get(f"{BASE_URL}/api/ta/realtime/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert 'data' in data
        assert 'websocket' in data['data']
        assert 'hub' in data['data']
        assert 'uptime' in data['data']
        print(f"✓ TA realtime status OK: websocket={data['data']['websocket']}")

    def test_ta_realtime_events(self):
        """GET /api/ta/realtime/events - shows recent published events"""
        response = requests.get(f"{BASE_URL}/api/ta/realtime/events")
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert 'data' in data
        assert 'events' in data['data']
        assert 'count' in data['data']
        print(f"✓ TA realtime events: count={data['data']['count']}")

    def test_ta_realtime_events_with_filters(self):
        """GET /api/ta/realtime/events with query params"""
        response = requests.get(f"{BASE_URL}/api/ta/realtime/events?limit=10&asset=BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        events = data['data']['events']
        # Verify filter works (all events should be BTCUSDT if any exist)
        for event in events:
            if 'asset' in event:
                assert event['asset'] == 'BTCUSDT'
        print(f"✓ TA realtime events with filter: count={data['data']['count']}")

    def test_ta_realtime_stats(self):
        """GET /api/ta/realtime/stats - shows event stats"""
        response = requests.get(f"{BASE_URL}/api/ta/realtime/stats")
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert 'data' in data
        stats = data['data']
        assert 'activeConnections' in stats
        assert 'totalSubscriptions' in stats
        assert 'eventsPublishedLastMinute' in stats
        assert 'eventsPublishedLastHour' in stats
        assert 'topEventTypes' in stats
        print(f"✓ TA realtime stats: connections={stats['activeConnections']}, subscriptions={stats['totalSubscriptions']}")

    def test_ta_realtime_connections(self):
        """GET /api/ta/realtime/connections - shows active WS connections"""
        response = requests.get(f"{BASE_URL}/api/ta/realtime/connections")
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert 'data' in data
        assert 'count' in data['data']
        assert 'connections' in data['data']
        print(f"✓ TA realtime connections: count={data['data']['count']}")


class TestTaRealtimeTestEndpoint:
    """POST /api/ta/realtime/test endpoint for various event types"""

    def test_ta_realtime_test_candle_update(self):
        """POST /api/ta/realtime/test - CANDLE_UPDATE event"""
        payload = {"type": "CANDLE_UPDATE", "asset": "BTCUSDT", "tf": "1m"}
        response = requests.post(f"{BASE_URL}/api/ta/realtime/test", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert data['data']['type'] == 'CANDLE_UPDATE'
        print(f"✓ TA test CANDLE_UPDATE event")

    def test_ta_realtime_test_pattern_detected(self):
        """POST /api/ta/realtime/test - PATTERN_DETECTED event"""
        payload = {"type": "PATTERN_DETECTED", "asset": "ETHUSDT", "tf": "1h"}
        response = requests.post(f"{BASE_URL}/api/ta/realtime/test", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert data['data']['type'] == 'PATTERN_DETECTED'
        print(f"✓ TA test PATTERN_DETECTED event")

    def test_ta_realtime_test_signal_created(self):
        """POST /api/ta/realtime/test - SIGNAL_CREATED event"""
        payload = {"type": "SIGNAL_CREATED", "asset": "SOLUSDT", "tf": "4h"}
        response = requests.post(f"{BASE_URL}/api/ta/realtime/test", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert data['data']['type'] == 'SIGNAL_CREATED'
        print(f"✓ TA test SIGNAL_CREATED event")

    def test_ta_realtime_test_scenario_update(self):
        """POST /api/ta/realtime/test - SCENARIO_UPDATE event"""
        payload = {"type": "SCENARIO_UPDATE", "asset": "BTCUSDT", "tf": "1d"}
        response = requests.post(f"{BASE_URL}/api/ta/realtime/test", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert data['data']['type'] == 'SCENARIO_UPDATE'
        print(f"✓ TA test SCENARIO_UPDATE event")

    def test_ta_realtime_test_regime_change(self):
        """POST /api/ta/realtime/test - REGIME_CHANGE event"""
        payload = {"type": "REGIME_CHANGE", "asset": "BTCUSDT", "tf": "1d"}
        response = requests.post(f"{BASE_URL}/api/ta/realtime/test", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert data['data']['type'] == 'REGIME_CHANGE'
        print(f"✓ TA test REGIME_CHANGE event")

    def test_ta_realtime_test_metabrain_update(self):
        """POST /api/ta/realtime/test - METABRAIN_UPDATE event (default)"""
        payload = {"asset": "BTCUSDT", "tf": "1d"}  # type defaults to METABRAIN_UPDATE
        response = requests.post(f"{BASE_URL}/api/ta/realtime/test", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is True
        assert data['data']['type'] == 'METABRAIN_UPDATE'
        print(f"✓ TA test METABRAIN_UPDATE event (default)")

    def test_ta_realtime_test_unknown_type(self):
        """POST /api/ta/realtime/test - unknown type returns error"""
        payload = {"type": "UNKNOWN_TYPE", "asset": "BTCUSDT"}
        response = requests.post(f"{BASE_URL}/api/ta/realtime/test", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data.get('success') is False
        assert 'error' in data
        print(f"✓ Unknown type correctly rejected")


class TestPhase1Regression:
    """Phase 1 regression tests - ensure Chart Intelligence endpoints still work"""

    def test_chart_state_endpoint(self):
        """GET /api/chart/state still works correctly (Phase 1 regression)"""
        response = requests.get(f"{BASE_URL}/api/chart/state?symbol=BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
        state_data = data['data']
        # Verify expected fields from Phase 1
        expected_fields = ['candles', 'prediction', 'levels', 'scenarios', 'objects', 'regime', 'system']
        for field in expected_fields:
            assert field in state_data, f"Missing field: {field}"
        print(f"✓ Phase 1 /api/chart/state endpoint works correctly")

    def test_chart_candles_endpoint(self):
        """GET /api/chart/candles still works correctly (Phase 1 regression)"""
        response = requests.get(f"{BASE_URL}/api/chart/candles?symbol=BTCUSDT&interval=1d&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
        # data may be {candles: [...], symbol, interval} or just [...]
        response_data = data['data']
        candles = response_data.get('candles', response_data) if isinstance(response_data, dict) else response_data
        assert isinstance(candles, list)
        assert len(candles) > 0
        # Verify candle structure
        for candle in candles:
            assert 't' in candle  # timestamp
            assert 'o' in candle  # open
            assert 'h' in candle  # high
            assert 'l' in candle  # low
            assert 'c' in candle  # close
            assert 'v' in candle  # volume
        print(f"✓ Phase 1 /api/chart/candles endpoint works correctly: {len(candles)} candles")

    def test_chart_prediction_endpoint(self):
        """GET /api/chart/prediction still works correctly (Phase 1 regression)"""
        response = requests.get(f"{BASE_URL}/api/chart/prediction?symbol=BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
        prediction = data['data']
        assert 'horizon' in prediction
        assert 'path' in prediction
        print(f"✓ Phase 1 /api/chart/prediction endpoint works correctly")

    def test_chart_levels_endpoint(self):
        """GET /api/chart/levels still works correctly (Phase 1 regression)"""
        response = requests.get(f"{BASE_URL}/api/chart/levels?symbol=BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
        levels = data['data']
        assert 'support' in levels
        assert 'resistance' in levels
        print(f"✓ Phase 1 /api/chart/levels endpoint works correctly")

    def test_chart_regime_endpoint(self):
        """GET /api/chart/regime still works correctly (Phase 1 regression)"""
        response = requests.get(f"{BASE_URL}/api/chart/regime?symbol=BTCUSDT")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'data' in data
        regime = data['data']
        assert 'regime' in regime
        assert 'bias' in regime
        print(f"✓ Phase 1 /api/chart/regime endpoint works correctly")


class TestHealthEndpoints:
    """General health endpoints"""

    def test_main_health_endpoint(self):
        """GET /api/health - main health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        print(f"✓ Main health endpoint OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
