"""
MetaBrain v2.1 Learning Layer - Module Attribution Engine Tests
Tests for edge score calculation, adaptive weights, and attribution analysis

Endpoints tested:
- GET /api/ta/metabrain/learning/status
- GET /api/ta/metabrain/learning/weights
- GET /api/ta/metabrain/learning/attribution
- POST /api/ta/metabrain/learning/rebuild
- GET /api/ta/metabrain/learning/weight/:module
- GET /api/ta/metabrain/learning/history
- GET /api/ta/metabrain/learning/config
"""

import pytest
import requests

BASE_URL = "http://localhost:3001"

# All analysis modules in the system
ALL_MODULES = ['PATTERN', 'LIQUIDITY', 'GRAPH', 'FRACTAL', 'PHYSICS', 'STATE', 'REGIME', 'SCENARIO']

class TestLearningStatus:
    """Tests for GET /api/ta/metabrain/learning/status"""
    
    def test_status_returns_200(self):
        """Status endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/status")
        assert response.status_code == 200
        print("✓ Status endpoint returns 200")
    
    def test_status_has_required_fields(self):
        """Status response contains all required fields"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/status")
        data = response.json()
        
        assert 'hasData' in data, "Missing hasData field"
        assert 'lastComputed' in data, "Missing lastComputed field"
        assert 'weightSummary' in data, "Missing weightSummary field"
        assert 'recentChanges' in data, "Missing recentChanges field"
        print(f"✓ Status has all required fields: hasData={data['hasData']}, recentChanges={data['recentChanges']}")
    
    def test_status_weight_summary_structure(self):
        """Weight summary contains min, max, avg, spread, topModule, weakestModule"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/status")
        data = response.json()
        summary = data['weightSummary']
        
        assert 'min' in summary, "Missing min in summary"
        assert 'max' in summary, "Missing max in summary"
        assert 'avg' in summary, "Missing avg in summary"
        assert 'spread' in summary, "Missing spread in summary"
        assert 'topModule' in summary, "Missing topModule in summary"
        assert 'weakestModule' in summary, "Missing weakestModule in summary"
        print(f"✓ Weight summary complete: min={summary['min']}, max={summary['max']}, avg={summary['avg']}")


class TestLearningWeights:
    """Tests for GET /api/ta/metabrain/learning/weights"""
    
    def test_weights_returns_200(self):
        """Weights endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weights")
        assert response.status_code == 200
        print("✓ Weights endpoint returns 200")
    
    def test_weights_has_all_modules(self):
        """Weights response contains weights for all 8 modules"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weights")
        data = response.json()
        
        assert 'weights' in data, "Missing weights array"
        weight_modules = [w['module'] for w in data['weights']]
        
        for module in ALL_MODULES:
            assert module in weight_modules, f"Missing weight for module {module}"
        print(f"✓ Weights contain all {len(ALL_MODULES)} modules")
    
    def test_weight_bounds(self):
        """All weights are within bounds 0.4 - 1.6"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weights")
        data = response.json()
        
        for w in data['weights']:
            weight = w['weight']
            assert 0.4 <= weight <= 1.6, f"Weight {weight} for {w['module']} out of bounds [0.4, 1.6]"
        print("✓ All weights within bounds [0.4, 1.6]")
    
    def test_weights_include_summary(self):
        """Weights response includes summary statistics"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weights")
        data = response.json()
        
        assert 'summary' in data, "Missing summary in response"
        assert 'topModule' in data['summary'], "Missing topModule in summary"
        assert 'weakestModule' in data['summary'], "Missing weakestModule in summary"
        print(f"✓ Top module: {data['summary']['topModule']}, Weakest: {data['summary']['weakestModule']}")
    
    def test_weights_have_edge_scores(self):
        """Each weight entry includes edgeScore and confidence"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weights")
        data = response.json()
        
        for w in data['weights']:
            assert 'edgeScore' in w, f"Missing edgeScore for {w['module']}"
            assert 'confidence' in w, f"Missing confidence for {w['module']}"
            assert 'sampleSize' in w, f"Missing sampleSize for {w['module']}"
        print("✓ All weights include edgeScore, confidence, sampleSize")


class TestLearningAttribution:
    """Tests for GET /api/ta/metabrain/learning/attribution"""
    
    def test_attribution_returns_200(self):
        """Attribution endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/attribution")
        assert response.status_code == 200
        print("✓ Attribution endpoint returns 200")
    
    def test_attribution_has_modules(self):
        """Attribution response includes module contributions"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/attribution")
        data = response.json()
        
        if data.get('hasData'):
            assert 'attribution' in data, "Missing attribution object"
            assert 'modules' in data['attribution'], "Missing modules array"
            assert len(data['attribution']['modules']) == 8, f"Expected 8 modules, got {len(data['attribution']['modules'])}"
            print(f"✓ Attribution has {len(data['attribution']['modules'])} module contributions")
        else:
            print("⚠ No attribution data yet (run /rebuild first)")
    
    def test_attribution_module_metrics(self):
        """Each module in attribution has performance metrics"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/attribution")
        data = response.json()
        
        if data.get('hasData'):
            for m in data['attribution']['modules']:
                assert 'module' in m, "Missing module name"
                assert 'edgeScore' in m, f"Missing edgeScore for {m['module']}"
                assert 'winRate' in m, f"Missing winRate for {m['module']}"
                assert 'profitFactor' in m, f"Missing profitFactor for {m['module']}"
                assert 'avgR' in m, f"Missing avgR for {m['module']}"
                assert 'impact' in m, f"Missing impact for {m['module']}"
                assert 'sampleSize' in m, f"Missing sampleSize for {m['module']}"
                assert 'confidence' in m, f"Missing confidence for {m['module']}"
            print("✓ All module contributions have required metrics")
    
    def test_attribution_top_weak_modules(self):
        """Attribution identifies top and weak modules"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/attribution")
        data = response.json()
        
        if data.get('hasData'):
            assert 'topModules' in data['attribution'], "Missing topModules"
            assert 'weakModules' in data['attribution'], "Missing weakModules"
            print(f"✓ Top modules: {data['attribution']['topModules'][:3]}")
            print(f"✓ Weak modules: {data['attribution']['weakModules']}")
    
    def test_attribution_baseline(self):
        """Attribution includes baseline performance"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/attribution")
        data = response.json()
        
        if data.get('hasData'):
            assert 'baseline' in data['attribution'], "Missing baseline"
            baseline = data['attribution']['baseline']
            assert 'winRate' in baseline, "Missing winRate in baseline"
            assert 'avgR' in baseline, "Missing avgR in baseline"
            assert 'profitFactor' in baseline, "Missing profitFactor in baseline"
            assert 'totalTrades' in baseline, "Missing totalTrades in baseline"
            print(f"✓ Baseline: WR={baseline['winRate']}, PF={baseline['profitFactor']}, totalTrades={baseline['totalTrades']}")


class TestLearningRebuild:
    """Tests for POST /api/ta/metabrain/learning/rebuild"""
    
    def test_rebuild_returns_200(self):
        """Rebuild endpoint returns 200 OK"""
        response = requests.post(
            f"{BASE_URL}/api/ta/metabrain/learning/rebuild",
            json={"useSynthetic": True}
        )
        assert response.status_code == 200
        print("✓ Rebuild endpoint returns 200")
    
    def test_rebuild_with_synthetic_data(self):
        """Rebuild works with synthetic data flag"""
        response = requests.post(
            f"{BASE_URL}/api/ta/metabrain/learning/rebuild",
            json={"useSynthetic": True}
        )
        data = response.json()
        
        assert data.get('success') == True, "Rebuild should succeed"
        assert 'attribution' in data, "Missing attribution result"
        assert 'weights' in data, "Missing weights result"
        print(f"✓ Rebuild successful with synthetic data")
    
    def test_rebuild_returns_attribution_summary(self):
        """Rebuild response includes attribution summary"""
        response = requests.post(
            f"{BASE_URL}/api/ta/metabrain/learning/rebuild",
            json={"useSynthetic": True}
        )
        data = response.json()
        
        assert 'topModules' in data['attribution'], "Missing topModules"
        assert 'weakModules' in data['attribution'], "Missing weakModules"
        assert 'moduleCount' in data['attribution'], "Missing moduleCount"
        assert 'totalSamples' in data['attribution'], "Missing totalSamples"
        print(f"✓ Attribution summary: {data['attribution']['moduleCount']} modules, {data['attribution']['totalSamples']} samples")
    
    def test_rebuild_returns_weights(self):
        """Rebuild response includes calculated weights"""
        response = requests.post(
            f"{BASE_URL}/api/ta/metabrain/learning/rebuild",
            json={"useSynthetic": True}
        )
        data = response.json()
        
        assert len(data['weights']) == 8, f"Expected 8 weights, got {len(data['weights'])}"
        for w in data['weights']:
            assert 'module' in w, "Missing module in weight"
            assert 'weight' in w, "Missing weight value"
            assert 'edgeScore' in w, "Missing edgeScore"
            assert 0.4 <= w['weight'] <= 1.6, f"Weight {w['weight']} out of bounds"
        print("✓ Rebuild returns weights for all modules within bounds")
    
    def test_rebuild_returns_history(self):
        """Rebuild response includes weight history entries"""
        response = requests.post(
            f"{BASE_URL}/api/ta/metabrain/learning/rebuild",
            json={"useSynthetic": True}
        )
        data = response.json()
        
        assert 'history' in data, "Missing history"
        # History may be empty if weights didn't change significantly
        print(f"✓ Rebuild history entries: {len(data['history'])}")
    
    def test_rebuild_with_regime_filter(self):
        """Rebuild accepts regime parameter"""
        response = requests.post(
            f"{BASE_URL}/api/ta/metabrain/learning/rebuild",
            json={"useSynthetic": True, "regime": "TREND_EXPANSION"}
        )
        data = response.json()
        
        assert data.get('success') == True, "Rebuild with regime should succeed"
        assert data.get('regime') == 'TREND_EXPANSION', f"Regime should be TREND_EXPANSION, got {data.get('regime')}"
        print("✓ Rebuild accepts regime filter")


class TestModuleWeight:
    """Tests for GET /api/ta/metabrain/learning/weight/:module"""
    
    def test_get_single_module_weight(self):
        """Get weight for STATE module"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weight/STATE")
        assert response.status_code == 200
        
        data = response.json()
        assert data['module'] == 'STATE', "Module name should be STATE"
        assert 'weight' in data, "Missing weight"
        assert 0.4 <= data['weight'] <= 1.6, f"Weight {data['weight']} out of bounds"
        print(f"✓ STATE module weight: {data['weight']}")
    
    def test_get_fractal_module_weight(self):
        """Get weight for FRACTAL module (typically weaker)"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weight/FRACTAL")
        assert response.status_code == 200
        
        data = response.json()
        assert data['module'] == 'FRACTAL', "Module name should be FRACTAL"
        assert 'weight' in data, "Missing weight"
        print(f"✓ FRACTAL module weight: {data['weight']}")
    
    def test_module_weight_includes_history(self):
        """Module weight endpoint includes weight history"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weight/LIQUIDITY")
        data = response.json()
        
        assert 'history' in data, "Missing history"
        print(f"✓ LIQUIDITY weight history entries: {len(data['history'])}")
    
    def test_all_modules_return_weight(self):
        """All 8 modules return valid weights"""
        for module in ALL_MODULES:
            response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weight/{module}")
            assert response.status_code == 200, f"Failed to get weight for {module}"
            data = response.json()
            assert data['module'] == module
            assert 0.4 <= data['weight'] <= 1.6
        print(f"✓ All {len(ALL_MODULES)} modules return valid weights")


class TestLearningHistory:
    """Tests for GET /api/ta/metabrain/learning/history"""
    
    def test_history_returns_200(self):
        """History endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/history")
        assert response.status_code == 200
        print("✓ History endpoint returns 200")
    
    def test_history_structure(self):
        """History response has required structure"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/history")
        data = response.json()
        
        assert 'count' in data, "Missing count"
        assert 'daysBack' in data, "Missing daysBack"
        assert 'changes' in data, "Missing changes"
        print(f"✓ History: {data['count']} changes in last {data['daysBack']} days")
    
    def test_history_entry_structure(self):
        """Each history entry has required fields"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/history")
        data = response.json()
        
        if data['count'] > 0:
            for entry in data['changes'][:5]:
                assert 'module' in entry, "Missing module"
                assert 'weight' in entry, "Missing weight"
                assert 'reason' in entry, "Missing reason"
                assert 'changedAt' in entry, "Missing changedAt"
            print("✓ History entries have all required fields")
        else:
            print("⚠ No history entries to validate")
    
    def test_history_with_limit(self):
        """History respects limit parameter"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/history?limit=5")
        data = response.json()
        
        assert len(data['changes']) <= 5, f"Expected max 5 changes, got {len(data['changes'])}"
        print(f"✓ History limit works: got {len(data['changes'])} entries")
    
    def test_history_with_days_filter(self):
        """History respects days parameter"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/history?days=7")
        data = response.json()
        
        assert data['daysBack'] == 7, f"Expected 7 days, got {data['daysBack']}"
        print("✓ History days filter works")


class TestLearningConfig:
    """Tests for GET /api/ta/metabrain/learning/config"""
    
    def test_config_returns_200(self):
        """Config endpoint returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/config")
        assert response.status_code == 200
        print("✓ Config endpoint returns 200")
    
    def test_config_has_required_fields(self):
        """Config includes all learning parameters"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/config")
        data = response.json()
        
        config = data.get('config', {})
        assert 'minSampleSize' in config, "Missing minSampleSize"
        assert 'shrinkageStrength' in config, "Missing shrinkageStrength"
        assert 'minWeight' in config, "Missing minWeight"
        assert 'maxWeight' in config, "Missing maxWeight"
        assert 'maxDailyChange' in config, "Missing maxDailyChange"
        assert 'dataWindowDays' in config, "Missing dataWindowDays"
        assert 'regimeSpecificLearning' in config, "Missing regimeSpecificLearning"
        print(f"✓ Config complete: minSample={config['minSampleSize']}, windowDays={config['dataWindowDays']}")
    
    def test_config_weight_bounds(self):
        """Config specifies correct weight bounds (0.4 - 1.6)"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/config")
        data = response.json()
        config = data.get('config', {})
        
        assert config['minWeight'] == 0.4, f"minWeight should be 0.4, got {config['minWeight']}"
        assert config['maxWeight'] == 1.6, f"maxWeight should be 1.6, got {config['maxWeight']}"
        print("✓ Weight bounds configured correctly: [0.4, 1.6]")


class TestEdgeScoreCalculation:
    """Tests for edge score and weight calculation logic"""
    
    def test_high_edge_modules_get_higher_weight(self):
        """Modules with higher edge score get higher weight"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weights")
        data = response.json()
        
        # Get weights sorted by edgeScore
        weights = sorted(data['weights'], key=lambda x: x['edgeScore'], reverse=True)
        
        # Top edge module should have higher weight than bottom
        top = weights[0]
        bottom = weights[-1]
        
        assert top['weight'] >= bottom['weight'], \
            f"Top module ({top['module']}) should have higher weight. Top: {top['weight']}, Bottom: {bottom['weight']}"
        print(f"✓ Edge score correlation: {top['module']}(edge={top['edgeScore']:.2f}, w={top['weight']}) > {bottom['module']}(edge={bottom['edgeScore']:.2f}, w={bottom['weight']})")
    
    def test_shrinkage_with_low_sample(self):
        """Low sample size modules have weights closer to 1.0 (shrinkage)"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weights")
        data = response.json()
        
        # Find module with lowest sample size
        weights = sorted(data['weights'], key=lambda x: x['sampleSize'])
        low_sample = weights[0]
        
        # Low sample module should have confidence < 1
        if low_sample['sampleSize'] < 100:
            assert low_sample['confidence'] < 1.0, \
                f"Low sample module should have confidence < 1, got {low_sample['confidence']}"
            print(f"✓ Shrinkage applied: {low_sample['module']} has confidence {low_sample['confidence']:.2f} with {low_sample['sampleSize']} samples")
        else:
            print(f"⚠ All modules have sufficient samples (min={low_sample['sampleSize']})")
    
    def test_edge_score_range(self):
        """Edge scores are in expected range (0-3)"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/weights")
        data = response.json()
        
        for w in data['weights']:
            assert 0 <= w['edgeScore'] <= 3, f"Edge score {w['edgeScore']} for {w['module']} out of range [0, 3]"
        print("✓ All edge scores within expected range [0, 3]")


class TestTopWeakModuleDetection:
    """Tests for top and weak module identification"""
    
    def test_top_modules_identified(self):
        """System identifies top performing modules"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/attribution")
        data = response.json()
        
        if data.get('hasData'):
            top_modules = data['attribution']['topModules']
            # Verify top modules have POSITIVE impact
            modules_data = {m['module']: m for m in data['attribution']['modules']}
            for mod in top_modules:
                if mod in modules_data:
                    assert modules_data[mod]['impact'] == 'POSITIVE', \
                        f"Top module {mod} should have POSITIVE impact"
            print(f"✓ Top modules identified: {top_modules[:3]}")
    
    def test_weak_modules_identified(self):
        """System identifies weak performing modules"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/attribution")
        data = response.json()
        
        if data.get('hasData'):
            weak_modules = data['attribution']['weakModules']
            print(f"✓ Weak modules identified: {weak_modules if weak_modules else 'None (all modules positive)'}")
    
    def test_status_summary_shows_top_weak(self):
        """Status summary shows top and weakest module"""
        response = requests.get(f"{BASE_URL}/api/ta/metabrain/learning/status")
        data = response.json()
        
        summary = data['weightSummary']
        if summary['topModule'] and summary['weakestModule']:
            print(f"✓ Summary shows: Top={summary['topModule']}, Weakest={summary['weakestModule']}")
        else:
            print("⚠ No modules identified in summary yet")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
