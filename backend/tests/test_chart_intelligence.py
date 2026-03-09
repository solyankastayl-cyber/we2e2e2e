"""
Chart Intelligence Layer - Backend API Tests
============================================
Phase 1: Tests for 8 Chart Intelligence API endpoints under /api/chart/*

Endpoints tested:
1. GET /api/chart/candles    - OHLCV data
2. GET /api/chart/prediction - Forecast path
3. GET /api/chart/levels     - Support/Resistance/Liquidity
4. GET /api/chart/scenarios  - Probable market scenarios
5. GET /api/chart/objects    - Graphical objects for frontend
6. GET /api/chart/regime     - Current market regime
7. GET /api/chart/system     - MetaBrain state
8. GET /api/chart/state      - Aggregated full state
"""

import pytest
import requests
import os
from typing import Dict, Any

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Symbols to test
TEST_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']


class TestHealthEndpoint:
    """Health check - ensure backend is running"""
    
    def test_health_endpoint(self):
        """Verify health endpoint returns ok"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        
        data = response.json()
        assert data.get('ok') is True, f"Health check returned ok=false: {data}"
        print(f"✅ Health check passed: {data}")


class TestCandlesEndpoint:
    """Test GET /api/chart/candles - OHLCV candle data"""
    
    def test_candles_default_params(self):
        """Test candles with default parameters"""
        response = requests.get(f"{BASE_URL}/api/chart/candles")
        assert response.status_code == 200, f"Candles request failed: {response.status_code}"
        
        result = response.json()
        assert result.get('ok') is True, f"Candles returned ok=false: {result}"
        assert 'data' in result, "Missing 'data' field in response"
        
        data = result['data']
        assert 'candles' in data, "Missing 'candles' array"
        assert 'symbol' in data, "Missing 'symbol' field"
        assert 'interval' in data, "Missing 'interval' field"
        
        # Verify candle structure
        if len(data['candles']) > 0:
            candle = data['candles'][0]
            assert 't' in candle, "Candle missing 't' (timestamp)"
            assert 'o' in candle, "Candle missing 'o' (open)"
            assert 'h' in candle, "Candle missing 'h' (high)"
            assert 'l' in candle, "Candle missing 'l' (low)"
            assert 'c' in candle, "Candle missing 'c' (close)"
            assert 'v' in candle, "Candle missing 'v' (volume)"
        
        print(f"✅ Candles default test passed: {len(data['candles'])} candles returned")
    
    def test_candles_with_params(self):
        """Test candles with specific symbol, interval, and limit"""
        response = requests.get(
            f"{BASE_URL}/api/chart/candles",
            params={'symbol': 'BTCUSDT', 'interval': '1d', 'limit': 5}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        
        data = result['data']
        assert data['symbol'] == 'BTCUSDT', f"Symbol mismatch: {data['symbol']}"
        assert data['interval'] == '1d', f"Interval mismatch: {data['interval']}"
        assert len(data['candles']) == 5, f"Expected 5 candles, got {len(data['candles'])}"
        
        print(f"✅ Candles with params test passed: {data['symbol']} {data['interval']} limit=5")
    
    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_candles_multiple_symbols(self, symbol):
        """Test candles endpoint works for different symbols"""
        response = requests.get(
            f"{BASE_URL}/api/chart/candles",
            params={'symbol': symbol, 'limit': 3}
        )
        assert response.status_code == 200, f"Failed for symbol {symbol}"
        
        result = response.json()
        assert result.get('ok') is True
        assert result['data']['symbol'] == symbol
        
        print(f"✅ Candles for {symbol}: {len(result['data']['candles'])} candles")


class TestPredictionEndpoint:
    """Test GET /api/chart/prediction - Forecast path"""
    
    def test_prediction_default(self):
        """Test prediction with default parameters"""
        response = requests.get(f"{BASE_URL}/api/chart/prediction")
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert 'data' in result
        
        data = result['data']
        assert 'horizon' in data, "Missing 'horizon' field"
        assert 'confidence' in data, "Missing 'confidence' field"
        assert 'path' in data, "Missing 'path' array"
        assert isinstance(data['path'], list), "Path should be an array"
        
        # Verify path point structure
        if len(data['path']) > 0:
            point = data['path'][0]
            assert 't' in point, "Path point missing 't' (timestamp)"
            assert 'price' in point, "Path point missing 'price'"
        
        print(f"✅ Prediction default test passed: horizon={data['horizon']}, confidence={data['confidence']:.2f}, path_points={len(data['path'])}")
    
    def test_prediction_with_horizon(self):
        """Test prediction with specific symbol and horizon"""
        response = requests.get(
            f"{BASE_URL}/api/chart/prediction",
            params={'symbol': 'BTCUSDT', 'horizon': '90d'}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert result['data']['horizon'] == '90d'
        
        print(f"✅ Prediction with horizon=90d passed: {len(result['data']['path'])} path points")
    
    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_prediction_multiple_symbols(self, symbol):
        """Test prediction works for different symbols"""
        response = requests.get(
            f"{BASE_URL}/api/chart/prediction",
            params={'symbol': symbol}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert 'data' in result
        
        print(f"✅ Prediction for {symbol}: {len(result['data']['path'])} path points")


class TestLevelsEndpoint:
    """Test GET /api/chart/levels - Support/Resistance/Liquidity levels"""
    
    def test_levels_default(self):
        """Test levels with default symbol"""
        response = requests.get(f"{BASE_URL}/api/chart/levels")
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert 'data' in result
        
        data = result['data']
        assert 'support' in data, "Missing 'support' array"
        assert 'resistance' in data, "Missing 'resistance' array"
        assert 'liquidity' in data, "Missing 'liquidity' array"
        
        assert isinstance(data['support'], list), "support should be an array"
        assert isinstance(data['resistance'], list), "resistance should be an array"
        assert isinstance(data['liquidity'], list), "liquidity should be an array"
        
        print(f"✅ Levels default test passed: support={len(data['support'])}, resistance={len(data['resistance'])}, liquidity={len(data['liquidity'])}")
    
    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_levels_multiple_symbols(self, symbol):
        """Test levels endpoint works for different symbols"""
        response = requests.get(
            f"{BASE_URL}/api/chart/levels",
            params={'symbol': symbol}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        
        data = result['data']
        # Verify numeric values in arrays
        for price in data['support']:
            assert isinstance(price, (int, float)), f"Support price should be numeric: {price}"
        for price in data['resistance']:
            assert isinstance(price, (int, float)), f"Resistance price should be numeric: {price}"
        
        print(f"✅ Levels for {symbol}: S={len(data['support'])}, R={len(data['resistance'])}, L={len(data['liquidity'])}")


class TestScenariosEndpoint:
    """Test GET /api/chart/scenarios - Probable market scenarios"""
    
    def test_scenarios_default(self):
        """Test scenarios with default symbol"""
        response = requests.get(f"{BASE_URL}/api/chart/scenarios")
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert 'data' in result
        
        data = result['data']
        assert 'scenarios' in data, "Missing 'scenarios' array"
        assert isinstance(data['scenarios'], list), "scenarios should be an array"
        
        # Verify scenario structure
        if len(data['scenarios']) > 0:
            scenario = data['scenarios'][0]
            assert 'type' in scenario, "Scenario missing 'type'"
            assert 'probability' in scenario, "Scenario missing 'probability'"
            assert isinstance(scenario['probability'], (int, float)), "Probability should be numeric"
        
        print(f"✅ Scenarios default test passed: {len(data['scenarios'])} scenarios")
    
    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_scenarios_multiple_symbols(self, symbol):
        """Test scenarios endpoint works for different symbols"""
        response = requests.get(
            f"{BASE_URL}/api/chart/scenarios",
            params={'symbol': symbol}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        
        scenarios = result['data']['scenarios']
        # Verify all scenarios have required fields
        for s in scenarios:
            assert 'type' in s
            assert 'probability' in s
        
        print(f"✅ Scenarios for {symbol}: {len(scenarios)} scenarios with types: {[s['type'] for s in scenarios]}")


class TestObjectsEndpoint:
    """Test GET /api/chart/objects - Graphical chart objects"""
    
    def test_objects_default(self):
        """Test objects with default symbol"""
        response = requests.get(f"{BASE_URL}/api/chart/objects")
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert 'data' in result
        
        data = result['data']
        assert 'objects' in data, "Missing 'objects' array"
        assert isinstance(data['objects'], list), "objects should be an array"
        
        # Verify object types
        valid_types = ['trendline', 'liquidity_zone', 'support', 'resistance', 'scenario', 'memory', 'channel', 'triangle']
        for obj in data['objects']:
            assert 'type' in obj, f"Object missing 'type': {obj}"
            assert obj['type'] in valid_types, f"Invalid object type: {obj['type']}"
        
        # Count object types
        type_counts = {}
        for obj in data['objects']:
            t = obj['type']
            type_counts[t] = type_counts.get(t, 0) + 1
        
        print(f"✅ Objects default test passed: {len(data['objects'])} objects, types: {type_counts}")
    
    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_objects_multiple_symbols(self, symbol):
        """Test objects endpoint works for different symbols"""
        response = requests.get(
            f"{BASE_URL}/api/chart/objects",
            params={'symbol': symbol}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        
        print(f"✅ Objects for {symbol}: {len(result['data']['objects'])} objects")


class TestRegimeEndpoint:
    """Test GET /api/chart/regime - Current market regime"""
    
    def test_regime_default(self):
        """Test regime with default symbol"""
        response = requests.get(f"{BASE_URL}/api/chart/regime")
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert 'data' in result
        
        data = result['data']
        assert 'regime' in data, "Missing 'regime' field"
        assert 'bias' in data, "Missing 'bias' field"
        assert 'volatility' in data, "Missing 'volatility' field"
        
        assert isinstance(data['regime'], str), "regime should be a string"
        assert isinstance(data['bias'], str), "bias should be a string"
        assert isinstance(data['volatility'], (int, float)), "volatility should be numeric"
        
        print(f"✅ Regime default test passed: regime={data['regime']}, bias={data['bias']}, volatility={data['volatility']:.2f}")
    
    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_regime_multiple_symbols(self, symbol):
        """Test regime endpoint works for different symbols"""
        response = requests.get(
            f"{BASE_URL}/api/chart/regime",
            params={'symbol': symbol}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        
        print(f"✅ Regime for {symbol}: {result['data']['regime']}, {result['data']['bias']}")


class TestSystemEndpoint:
    """Test GET /api/chart/system - MetaBrain system state"""
    
    def test_system_endpoint(self):
        """Test system state endpoint"""
        response = requests.get(f"{BASE_URL}/api/chart/system")
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert 'data' in result
        
        data = result['data']
        assert 'analysisMode' in data, "Missing 'analysisMode' field"
        assert 'riskMode' in data, "Missing 'riskMode' field"
        assert 'metabrainState' in data, "Missing 'metabrainState' field"
        
        assert isinstance(data['analysisMode'], str), "analysisMode should be a string"
        assert isinstance(data['riskMode'], str), "riskMode should be a string"
        assert isinstance(data['metabrainState'], str), "metabrainState should be a string"
        
        print(f"✅ System state test passed: analysisMode={data['analysisMode']}, riskMode={data['riskMode']}, metabrainState={data['metabrainState']}")


class TestStateEndpoint:
    """Test GET /api/chart/state - Aggregated full state"""
    
    def test_state_default(self):
        """Test aggregated state with default parameters"""
        response = requests.get(f"{BASE_URL}/api/chart/state")
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert 'data' in result
        
        data = result['data']
        
        # Verify all aggregated fields are present
        assert 'symbol' in data, "Missing 'symbol'"
        assert 'interval' in data, "Missing 'interval'"
        assert 'ts' in data, "Missing 'ts' (timestamp)"
        assert 'candles' in data, "Missing 'candles'"
        assert 'prediction' in data, "Missing 'prediction'"
        assert 'levels' in data, "Missing 'levels'"
        assert 'scenarios' in data, "Missing 'scenarios'"
        assert 'objects' in data, "Missing 'objects'"
        assert 'regime' in data, "Missing 'regime'"
        assert 'system' in data, "Missing 'system'"
        
        # Verify nested structures
        assert isinstance(data['candles'], list), "candles should be array"
        assert isinstance(data['prediction'], dict), "prediction should be object"
        assert isinstance(data['levels'], dict), "levels should be object"
        assert isinstance(data['scenarios'], list), "scenarios should be array"
        assert isinstance(data['objects'], list), "objects should be array"
        assert isinstance(data['regime'], dict), "regime should be object"
        assert isinstance(data['system'], dict), "system should be object"
        
        print(f"✅ Aggregated state test passed: symbol={data['symbol']}, candles={len(data['candles'])}, scenarios={len(data['scenarios'])}, objects={len(data['objects'])}")
    
    def test_state_with_params(self):
        """Test aggregated state with specific parameters"""
        response = requests.get(
            f"{BASE_URL}/api/chart/state",
            params={'symbol': 'BTCUSDT', 'interval': '1d', 'limit': 10}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        
        data = result['data']
        assert data['symbol'] == 'BTCUSDT'
        assert data['interval'] == '1d'
        assert len(data['candles']) == 10, f"Expected 10 candles, got {len(data['candles'])}"
        
        # Verify prediction has path
        assert 'path' in data['prediction'], "Prediction should have path"
        
        # Verify levels structure
        assert 'support' in data['levels']
        assert 'resistance' in data['levels']
        assert 'liquidity' in data['levels']
        
        # Verify regime structure
        assert 'regime' in data['regime']
        assert 'bias' in data['regime']
        assert 'volatility' in data['regime']
        
        # Verify system structure
        assert 'analysisMode' in data['system']
        assert 'riskMode' in data['system']
        assert 'metabrainState' in data['system']
        
        print(f"✅ State with params test passed: {data['symbol']}, {data['interval']}, limit=10")
    
    @pytest.mark.parametrize("symbol", TEST_SYMBOLS)
    def test_state_multiple_symbols(self, symbol):
        """Test aggregated state works for different symbols"""
        response = requests.get(
            f"{BASE_URL}/api/chart/state",
            params={'symbol': symbol, 'limit': 5}
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result.get('ok') is True
        assert result['data']['symbol'] == symbol
        
        print(f"✅ State for {symbol}: candles={len(result['data']['candles'])}, objects={len(result['data']['objects'])}")


class TestResponseFormat:
    """Verify all endpoints return { ok: true, data: ... } format"""
    
    @pytest.mark.parametrize("endpoint", [
        '/api/chart/candles',
        '/api/chart/prediction',
        '/api/chart/levels',
        '/api/chart/scenarios',
        '/api/chart/objects',
        '/api/chart/regime',
        '/api/chart/system',
        '/api/chart/state'
    ])
    def test_response_format(self, endpoint):
        """Verify consistent response format across all endpoints"""
        response = requests.get(f"{BASE_URL}{endpoint}")
        assert response.status_code == 200, f"{endpoint} returned {response.status_code}"
        
        result = response.json()
        assert 'ok' in result, f"{endpoint} missing 'ok' field"
        assert result['ok'] is True, f"{endpoint} returned ok=false"
        assert 'data' in result, f"{endpoint} missing 'data' field"
        
        print(f"✅ Response format verified for {endpoint}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
