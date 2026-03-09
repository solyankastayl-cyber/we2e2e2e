"""
D3 (Market Physics Engine) and D4 (State Transition Engine) Integration Tests
Phase 5 - Testing newly registered modules for TA Engine

Tests cover:
- D3: Market Physics state, compression, energy, release, boost, config
- D4: State Transition current, transitions, boost, allowed, states
- Decision Engine: Physics/State engine integration status
- Analysis Mode: stateBoost weight in DEEP_MARKET mode
- Structure Scoring: POST endpoint still works
- Cross-integration: Modules fetching data from each other
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestTAHealthCheck:
    """Basic health check tests"""
    
    def test_ta_health_endpoint(self):
        """TA Engine health check returns ok: true"""
        response = requests.get(f"{BASE_URL}/api/ta/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert 'version' in data
        print(f"TA Health: OK, version={data.get('version')}, detectors={data.get('detectors')}")


class TestD3MarketPhysicsEngine:
    """D3 - Market Physics Engine tests"""
    
    def test_physics_state(self):
        """GET /api/ta/physics/state returns physicsState, scores, boost"""
        response = requests.get(f"{BASE_URL}/api/ta/physics/state?asset=BTCUSDT&tf=1d")
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert data.get('ok') is True
        assert data.get('asset') == 'BTCUSDT'
        assert data.get('timeframe') == '1d'
        assert 'physicsState' in data
        assert data['physicsState'] in ['COMPRESSION', 'PRESSURE', 'RELEASE', 'EXPANSION', 'EXHAUSTION', 'NEUTRAL']
        assert 'stateConfidence' in data
        assert 'directionBias' in data
        assert 'physicsBoost' in data
        assert 'scores' in data
        
        # Validate scores structure
        scores = data['scores']
        assert 'compression' in scores
        assert 'pressure' in scores
        assert 'energy' in scores
        assert 'release' in scores
        assert 'exhaustion' in scores
        
        print(f"Physics State: {data['physicsState']}, confidence={data['stateConfidence']}, boost={data['physicsBoost']}")
    
    def test_physics_compression(self):
        """GET /api/ta/physics/compression returns compressionScore, metrics"""
        response = requests.get(f"{BASE_URL}/api/ta/physics/compression?asset=BTCUSDT&tf=1d")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'compressionScore' in data
        assert 'metrics' in data
        assert 'isCompressed' in data
        
        metrics = data['metrics']
        assert 'atrRatio' in metrics
        assert 'rangeContraction' in metrics
        assert 'bollingerWidth' in metrics
        
        print(f"Compression: score={data['compressionScore']:.3f}, isCompressed={data['isCompressed']}")
    
    def test_physics_energy(self):
        """GET /api/ta/physics/energy returns energyScore, releaseProbability"""
        response = requests.get(f"{BASE_URL}/api/ta/physics/energy?asset=BTCUSDT&tf=1d")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'energyScore' in data
        assert 'components' in data
        assert 'releaseProbability' in data
        assert 'isHighEnergy' in data
        
        print(f"Energy: score={data['energyScore']:.3f}, releaseProbability={data['releaseProbability']}, isHighEnergy={data['isHighEnergy']}")
    
    def test_physics_release(self):
        """GET /api/ta/physics/release returns releaseProbability, direction"""
        response = requests.get(f"{BASE_URL}/api/ta/physics/release?asset=BTCUSDT&tf=1d")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'releaseProbability' in data
        assert 'isReleasing' in data
        assert 'direction' in data
        assert data['direction'] in ['BULL', 'BEAR', 'NEUTRAL']
        assert 'volumeProfile' in data
        
        print(f"Release: probability={data['releaseProbability']}, isReleasing={data['isReleasing']}, direction={data['direction']}")
    
    def test_physics_boost_bull(self):
        """GET /api/ta/physics/boost with direction=BULL returns boost 0.7-1.3"""
        response = requests.get(f"{BASE_URL}/api/ta/physics/boost?asset=BTCUSDT&tf=1d&direction=BULL")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'boost' in data
        assert 0.7 <= data['boost'] <= 1.3, f"Boost {data['boost']} not in valid range [0.7, 1.3]"
        assert 'state' in data
        assert 'reason' in data
        assert data['direction'] == 'BULL'
        
        print(f"Physics Boost (BULL): boost={data['boost']:.3f}, state={data['state']}, reason={data['reason']}")
    
    def test_physics_boost_bear(self):
        """GET /api/ta/physics/boost with direction=BEAR returns boost 0.7-1.3"""
        response = requests.get(f"{BASE_URL}/api/ta/physics/boost?asset=BTCUSDT&tf=1d&direction=BEAR")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'boost' in data
        assert 0.7 <= data['boost'] <= 1.3, f"Boost {data['boost']} not in valid range [0.7, 1.3]"
        assert data['direction'] == 'BEAR'
        
        print(f"Physics Boost (BEAR): boost={data['boost']:.3f}, state={data['state']}")
    
    def test_physics_config(self):
        """GET /api/ta/physics/config returns configuration"""
        response = requests.get(f"{BASE_URL}/api/ta/physics/config")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'config' in data
        
        config = data['config']
        # Verify key config fields exist
        assert 'compressionATRPeriod' in config
        assert 'compressionThreshold' in config
        assert 'bollingerPeriod' in config
        assert 'energyWeights' in config
        
        print(f"Physics Config: ATR period={config['compressionATRPeriod']}, threshold={config['compressionThreshold']}")


class TestD4StateTransitionEngine:
    """D4 - State Transition Engine tests"""
    
    def test_state_current(self):
        """GET /api/ta/state/current returns currentState, stateConfidence, stateBoost"""
        response = requests.get(f"{BASE_URL}/api/ta/state/current?asset=BTCUSDT&tf=1d")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('asset') == 'BTCUSDT'
        assert data.get('timeframe') == '1d'
        assert 'currentState' in data
        valid_states = ['BALANCE', 'COMPRESSION', 'BREAKOUT_ATTEMPT', 'EXPANSION', 'EXHAUSTION', 'REVERSAL_ATTEMPT']
        assert data['currentState'] in valid_states, f"State {data['currentState']} not in valid states"
        assert 'stateConfidence' in data
        assert 'stateBoost' in data
        assert 'stateReason' in data
        
        print(f"State Current: {data['currentState']}, confidence={data['stateConfidence']}, boost={data['stateBoost']}")
    
    def test_state_transitions(self):
        """GET /api/ta/state/transitions returns nextStateProbabilities, likelyPath"""
        response = requests.get(f"{BASE_URL}/api/ta/state/transitions?asset=BTCUSDT&tf=1d")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'currentState' in data
        assert 'nextStateProbabilities' in data
        assert isinstance(data['nextStateProbabilities'], list)
        assert len(data['nextStateProbabilities']) > 0
        assert 'likelyPath' in data
        assert isinstance(data['likelyPath'], list)
        assert 'pathProbability' in data
        
        # Validate transition structure
        for trans in data['nextStateProbabilities']:
            assert 'state' in trans
            assert 'probability' in trans
        
        print(f"State Transitions: current={data['currentState']}, transitions={len(data['nextStateProbabilities'])}, path={data['likelyPath']}")
    
    def test_state_boost_bull(self):
        """GET /api/ta/state/boost with direction=BULL returns boost 0.7-1.3"""
        response = requests.get(f"{BASE_URL}/api/ta/state/boost?asset=BTCUSDT&tf=1d&direction=BULL")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'boost' in data
        assert 0.7 <= data['boost'] <= 1.3, f"State boost {data['boost']} not in valid range [0.7, 1.3]"
        assert 'state' in data
        assert 'reason' in data
        assert data['direction'] == 'BULL'
        
        print(f"State Boost (BULL): boost={data['boost']}, state={data['state']}")
    
    def test_state_boost_bear(self):
        """GET /api/ta/state/boost with direction=BEAR returns boost 0.7-1.3"""
        response = requests.get(f"{BASE_URL}/api/ta/state/boost?asset=BTCUSDT&tf=1d&direction=BEAR")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'boost' in data
        assert 0.7 <= data['boost'] <= 1.3
        assert data['direction'] == 'BEAR'
        
        print(f"State Boost (BEAR): boost={data['boost']}, state={data['state']}")
    
    def test_state_allowed_compression(self):
        """GET /api/ta/state/allowed?state=COMPRESSION returns allowedTransitions array"""
        response = requests.get(f"{BASE_URL}/api/ta/state/allowed?state=COMPRESSION")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert data.get('state') == 'COMPRESSION'
        assert 'allowedTransitions' in data
        assert isinstance(data['allowedTransitions'], list)
        # COMPRESSION can transition to BREAKOUT_ATTEMPT or BALANCE
        assert 'BREAKOUT_ATTEMPT' in data['allowedTransitions']
        assert 'BALANCE' in data['allowedTransitions']
        
        print(f"Allowed Transitions from COMPRESSION: {data['allowedTransitions']}")
    
    def test_state_allowed_balance(self):
        """GET /api/ta/state/allowed?state=BALANCE returns allowedTransitions"""
        response = requests.get(f"{BASE_URL}/api/ta/state/allowed?state=BALANCE")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'allowedTransitions' in data
        # BALANCE can transition to COMPRESSION or BREAKOUT_ATTEMPT
        assert 'COMPRESSION' in data['allowedTransitions']
        
        print(f"Allowed Transitions from BALANCE: {data['allowedTransitions']}")
    
    def test_state_all_states(self):
        """GET /api/ta/state/states returns all states and transition graph"""
        response = requests.get(f"{BASE_URL}/api/ta/state/states")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'states' in data
        assert 'transitions' in data
        
        expected_states = ['BALANCE', 'COMPRESSION', 'BREAKOUT_ATTEMPT', 'EXPANSION', 'EXHAUSTION', 'REVERSAL_ATTEMPT']
        for state in expected_states:
            assert state in data['states'], f"Missing state: {state}"
            assert state in data['transitions'], f"Missing transition for state: {state}"
        
        print(f"All States: {data['states']}")


class TestDecisionEngineIntegration:
    """Decision Engine integration with D3/D4"""
    
    def test_decision_status_shows_physics_state_engines(self):
        """GET /api/ta/decision/status shows physicsEngine and stateEngine as active"""
        response = requests.get(f"{BASE_URL}/api/ta/decision/status")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'components' in data
        components = data['components']
        
        # Verify D3 and D4 are registered
        assert 'physicsEngine' in components
        assert 'D3' in components['physicsEngine'] or 'active' in components['physicsEngine']
        assert 'stateEngine' in components
        assert 'D4' in components['stateEngine'] or 'active' in components['stateEngine']
        
        # Verify pipeline includes physics and state
        assert 'pipeline' in data
        assert 'physics' in data['pipeline'].lower() or 'state' in data['pipeline'].lower()
        
        print(f"Decision Status: physicsEngine={components['physicsEngine']}, stateEngine={components['stateEngine']}")
        print(f"Pipeline: {data['pipeline']}")


class TestAnalysisModeIntegration:
    """Analysis Mode integration tests"""
    
    def test_analysis_mode_deep_market_has_physics_state_weights(self):
        """GET /api/ta/analysis_mode/mode shows DEEP_MARKET with physics=true and stateBoost weight"""
        response = requests.get(f"{BASE_URL}/api/ta/analysis_mode/mode")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'mode' in data
        assert 'config' in data
        
        config = data['config']
        
        # Check layers include physics
        if 'layers' in config:
            layers = config['layers']
            assert layers.get('physics') is True, "DEEP_MARKET should have physics=true"
        
        # Check weights include physics and state boosts
        if 'weights' in config:
            weights = config['weights']
            assert 'physicsBoost' in weights, "weights should include physicsBoost"
            assert 'stateBoost' in weights, "weights should include stateBoost"
            assert weights['physicsBoost'] > 0, "physicsBoost weight should be positive"
            assert weights['stateBoost'] > 0, "stateBoost weight should be positive"
        
        print(f"Analysis Mode: {data['mode']}")
        if 'weights' in config:
            print(f"Weights: physicsBoost={config['weights'].get('physicsBoost')}, stateBoost={config['weights'].get('stateBoost')}")


class TestStructureScoringEndpoint:
    """Structure Scoring endpoint continues to work"""
    
    def test_structure_score_compute(self):
        """POST /api/ta/structure_score/compute still works with {asset, timeframe}"""
        response = requests.post(
            f"{BASE_URL}/api/ta/structure_score/compute",
            json={"asset": "BTCUSDT", "timeframe": "1d"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get('ok') is True
        assert 'structureBoost' in data
        assert 'contextScore' in data
        assert 'marketStateScore' in data
        assert 'liquidityScore' in data
        assert 'breakdown' in data
        
        print(f"Structure Score: boost={data['structureBoost']:.3f}")
        print(f"Breakdown: context={data['breakdown'].get('contextContribution'):.3f}, marketState={data['breakdown'].get('marketStateContribution'):.3f}")


class TestCrossIntegration:
    """Cross-module integration tests - D3 and D4 fetch from each other without circular crash"""
    
    def test_state_engine_fetches_from_physics_no_crash(self):
        """State Engine calls Physics Engine internally - no circular dependency crash"""
        # D4 State Engine fetches from D3 Physics when computing state
        response = requests.get(f"{BASE_URL}/api/ta/state/current?asset=BTCUSDT&tf=1d")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        
        # The state computation uses physics data internally
        print("Cross-integration: State Engine → Physics Engine: OK (no crash)")
    
    def test_physics_fetches_from_liquidity_no_crash(self):
        """Physics Engine calls Liquidity Engine internally - no crash"""
        # D3 Physics Engine fetches from Liquidity when computing physics
        response = requests.get(f"{BASE_URL}/api/ta/physics/state?asset=BTCUSDT&tf=1d")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        
        print("Cross-integration: Physics Engine → Liquidity Engine: OK (no crash)")
    
    def test_multiple_assets_no_crash(self):
        """Test D3/D4 with different assets don't crash"""
        assets = ['BTCUSDT', 'ETHUSDT']
        
        for asset in assets:
            # Physics
            resp_physics = requests.get(f"{BASE_URL}/api/ta/physics/state?asset={asset}&tf=1d")
            assert resp_physics.status_code == 200
            
            # State
            resp_state = requests.get(f"{BASE_URL}/api/ta/state/current?asset={asset}&tf=1d")
            assert resp_state.status_code == 200
        
        print(f"Multi-asset testing: {assets} - all endpoints working")


class TestEdgeCases:
    """Edge case testing"""
    
    def test_physics_default_asset_timeframe(self):
        """Physics endpoint works with default parameters"""
        response = requests.get(f"{BASE_URL}/api/ta/physics/state")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        # Default should be BTCUSDT and 1d
        assert data.get('asset') == 'BTCUSDT'
        assert data.get('timeframe') == '1d'
    
    def test_state_default_asset_timeframe(self):
        """State endpoint works with default parameters"""
        response = requests.get(f"{BASE_URL}/api/ta/state/current")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        assert data.get('asset') == 'BTCUSDT'
        assert data.get('timeframe') == '1d'
    
    def test_physics_boost_default_direction(self):
        """Physics boost works with default direction"""
        response = requests.get(f"{BASE_URL}/api/ta/physics/boost?asset=BTCUSDT&tf=1d")
        assert response.status_code == 200
        data = response.json()
        assert data.get('ok') is True
        # Default direction should be BULL
        assert data.get('direction') == 'BULL'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
