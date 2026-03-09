"""
Phase 9.5 Edge Validation API Tests
Tests for edge validation, robustness scoring, similarity penalty, confidence calculation, and lifecycle management.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://risk-control-system.preview.emergentagent.com"


class TestEdgeValidationHealth:
    """Health check endpoint tests for Phase 9.5"""
    
    def test_edge_validation_health(self):
        """Test /api/discovery/edge-validation/health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/discovery/edge-validation/health", timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert data.get("enabled") == True
        assert data.get("version") == "edge_validation_v1_phase9.5"
        assert data.get("status") == "ok"
        
        # Validate components
        components = data.get("components", {})
        assert components.get("robustness_engine") == "ok"
        assert components.get("similarity_engine") == "ok"
        assert components.get("confidence_calculator") == "ok"
        assert components.get("lifecycle_manager") == "ok"
        
        # Validate thresholds are present
        thresholds = data.get("thresholds", {})
        assert "min_trades" in thresholds
        assert "min_robustness" in thresholds
        assert "max_similarity" in thresholds
        assert "strong_confidence" in thresholds
        assert "promote_threshold" in thresholds
        
        print(f"✓ Edge Validation Health: enabled={data.get('enabled')}, version={data.get('version')}")


class TestDiscoverySetup:
    """Tests to ensure discovery has strategies for validation"""
    
    @pytest.fixture(scope="class")
    def discovery_run(self):
        """Run discovery to generate strategies for testing"""
        response = requests.post(
            f"{BASE_URL}/api/discovery/run",
            json={"symbols": ["BTCUSDT", "ETHUSDT"], "timeframes": ["1h", "4h"]},
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Discovery Run: {data.get('strategiesGenerated')} strategies generated")
        return data
    
    def test_discovery_generates_strategies(self, discovery_run):
        """Verify discovery generates strategies for validation testing"""
        assert discovery_run.get("strategiesGenerated", 0) >= 5, "Need at least 5 strategies for testing"
        assert len(discovery_run.get("topStrategies", [])) >= 1, "Need at least 1 top strategy"
        
        first_strategy = discovery_run.get("topStrategies", [{}])[0]
        assert "id" in first_strategy, "Strategy must have an ID"
        assert "metrics" in first_strategy, "Strategy must have metrics"
        assert "rules" in first_strategy, "Strategy must have rules"
        
        print(f"✓ Discovery generated {discovery_run.get('strategiesGenerated')} strategies with proper structure")


class TestSingleStrategyValidation:
    """Tests for single strategy edge validation endpoint"""
    
    @pytest.fixture(scope="class")
    def strategy_id(self):
        """Get a strategy ID for testing"""
        # First run discovery
        requests.post(
            f"{BASE_URL}/api/discovery/run",
            json={"symbols": ["BTCUSDT"], "timeframes": ["4h"]},
            timeout=30
        )
        
        # Get strategies
        response = requests.get(f"{BASE_URL}/api/discovery/strategies", timeout=10)
        if response.status_code == 200:
            strategies = response.json().get("strategies", [])
            if strategies:
                return strategies[0].get("id")
        return None
    
    def test_single_strategy_validation(self, strategy_id):
        """Test GET /api/discovery/edge-validation/{strategy_id}"""
        if not strategy_id:
            pytest.skip("No strategy ID available")
        
        response = requests.get(
            f"{BASE_URL}/api/discovery/edge-validation/{strategy_id}",
            timeout=15
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure - strategyId field
        assert data.get("strategyId") == strategy_id
        
        # Validate robustness section
        robustness = data.get("robustness", {})
        assert "overallScore" in robustness
        assert 0 <= robustness.get("overallScore", -1) <= 1
        assert "regimeScores" in robustness
        assert "temporalStability" in robustness
        assert "minimumEvidence" in robustness
        assert "regimeCoverage" in robustness
        assert "notes" in robustness
        
        # Validate similarity section
        similarity = data.get("similarity", {})
        assert "penalty" in similarity
        assert 0 <= similarity.get("penalty", -1) <= 1
        assert "similarStrategies" in similarity
        assert "overlapFeatures" in similarity
        assert "correlation" in similarity
        assert "isRedundant" in similarity
        assert "notes" in similarity
        
        # Validate confidence section
        confidence = data.get("confidence", {})
        assert "score" in confidence
        assert 0 <= confidence.get("score", -1) <= 1
        assert "robustnessComponent" in confidence
        assert "similarityComponent" in confidence
        assert "evidenceComponent" in confidence
        assert "regimeStabilityComponent" in confidence
        assert "breakdown" in confidence
        assert "verdict" in confidence
        assert confidence.get("verdict") in ["STRONG", "MODERATE", "WEAK", "REJECT", "NEEDS_MORE_DATA"]
        assert "reasons" in confidence
        
        # Validate lifecycle section
        assert "recommendedStatus" in data
        assert data.get("recommendedStatus") in ["CANDIDATE", "TESTING", "APPROVED", "QUARANTINE", "DEPRECATED"]
        assert "lifecycleAction" in data
        assert data.get("lifecycleAction") in ["PROMOTE", "DEMOTE", "HOLD", "DEPRECATE"]
        assert "timestamp" in data
        assert "notes" in data
        
        print(f"✓ Single Strategy Validation: confidence={confidence.get('score'):.4f}, verdict={confidence.get('verdict')}, action={data.get('lifecycleAction')}")
    
    def test_validation_404_for_invalid_strategy(self):
        """Test that invalid strategy ID returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/discovery/edge-validation/invalid_strategy_id_12345",
            timeout=10
        )
        
        assert response.status_code == 404
        print("✓ Invalid strategy ID correctly returns 404")


class TestBatchValidation:
    """Tests for batch edge validation endpoint"""
    
    def test_batch_validation_all_strategies(self):
        """Test POST /api/discovery/edge-validation/batch validates all strategies"""
        # First ensure we have strategies
        requests.post(
            f"{BASE_URL}/api/discovery/run",
            json={"symbols": ["BTCUSDT", "ETHUSDT"], "timeframes": ["1h", "4h"]},
            timeout=30
        )
        
        # Run batch validation
        response = requests.post(
            f"{BASE_URL}/api/discovery/edge-validation/batch",
            json={},  # Empty body = validate all
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate results structure
        assert "results" in data
        assert "summary" in data
        
        results = data.get("results", {})
        assert len(results) >= 1, "Should have at least 1 validation result"
        
        # Validate each result
        for strategy_id, result in results.items():
            assert "strategyId" in result
            assert "robustness" in result
            assert "similarity" in result
            assert "confidence" in result
            assert "recommendedStatus" in result
            assert "lifecycleAction" in result
        
        # Validate summary
        summary = data.get("summary", {})
        assert "totalValidated" in summary
        assert summary.get("totalValidated") >= 1
        assert "verdictDistribution" in summary
        assert "actionDistribution" in summary
        assert "averageConfidence" in summary
        assert "averageRobustness" in summary
        assert "redundantStrategies" in summary
        assert "promotionRate" in summary
        assert "rejectionRate" in summary
        
        print(f"✓ Batch Validation: validated {summary.get('totalValidated')} strategies, avg confidence={summary.get('averageConfidence'):.4f}")
    
    def test_batch_validation_with_filter(self):
        """Test batch validation with specific strategy IDs filter"""
        # Get strategies first
        response = requests.get(f"{BASE_URL}/api/discovery/strategies", timeout=10)
        if response.status_code != 200:
            pytest.skip("Could not get strategies")
        
        strategies = response.json().get("strategies", [])
        if len(strategies) < 2:
            pytest.skip("Need at least 2 strategies for filter test")
        
        # Get first 2 strategy IDs
        strategy_ids = [s.get("id") for s in strategies[:2]]
        
        # Run filtered batch validation
        response = requests.post(
            f"{BASE_URL}/api/discovery/edge-validation/batch",
            json={"strategyIds": strategy_ids},
            timeout=20
        )
        
        assert response.status_code == 200
        data = response.json()
        
        results = data.get("results", {})
        summary = data.get("summary", {})
        
        # Should only validate the filtered strategies
        assert summary.get("totalValidated") == len(strategy_ids)
        
        # Verify the IDs match
        for sid in strategy_ids:
            assert sid in results, f"Strategy {sid} should be in results"
        
        print(f"✓ Filtered Batch Validation: validated {summary.get('totalValidated')} specific strategies")


class TestApplyValidation:
    """Tests for applying validation results to update statuses"""
    
    def test_apply_validation(self):
        """Test POST /api/discovery/edge-validation/apply updates strategy statuses"""
        # Ensure strategies exist
        requests.post(
            f"{BASE_URL}/api/discovery/run",
            json={"symbols": ["BTCUSDT"], "timeframes": ["4h"]},
            timeout=30
        )
        
        # Apply validation
        response = requests.post(
            f"{BASE_URL}/api/discovery/edge-validation/apply",
            json={},
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "updated" in data
        assert "changes" in data
        assert "summary" in data
        
        changes = data.get("changes", {})
        assert "promoted" in changes
        assert "demoted" in changes
        assert "deprecated" in changes
        assert "unchanged" in changes
        
        total_changes = changes.get("promoted", 0) + changes.get("demoted", 0) + changes.get("deprecated", 0) + changes.get("unchanged", 0)
        assert total_changes == data.get("updated"), "Changes should sum to updated count"
        
        print(f"✓ Apply Validation: updated={data.get('updated')}, promoted={changes.get('promoted')}, demoted={changes.get('demoted')}, unchanged={changes.get('unchanged')}")


class TestLifecycleEndpoints:
    """Tests for lifecycle management endpoints"""
    
    def test_lifecycle_report(self):
        """Test GET /api/discovery/lifecycle/report returns status distribution"""
        # Ensure strategies exist
        requests.post(
            f"{BASE_URL}/api/discovery/run",
            json={"symbols": ["BTCUSDT"], "timeframes": ["4h"]},
            timeout=30
        )
        
        response = requests.get(f"{BASE_URL}/api/discovery/lifecycle/report", timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "statusDistribution" in data
        status_dist = data.get("statusDistribution", {})
        assert "CANDIDATE" in status_dist
        assert "TESTING" in status_dist
        assert "APPROVED" in status_dist
        assert "QUARANTINE" in status_dist
        assert "DEPRECATED" in status_dist
        
        assert "totalStrategies" in data
        assert "activeStrategies" in data
        assert "recentPromotions" in data
        assert "recentDemotions" in data
        assert "promotionCandidates" in data
        assert "demotionCandidates" in data
        assert "timestamp" in data
        
        # Validate counts
        total = sum(status_dist.values())
        assert data.get("totalStrategies") == total
        
        active = status_dist.get("APPROVED", 0) + status_dist.get("TESTING", 0)
        assert data.get("activeStrategies") == active
        
        print(f"✓ Lifecycle Report: total={data.get('totalStrategies')}, active={data.get('activeStrategies')}, status_dist={status_dist}")
    
    def test_lifecycle_candidates(self):
        """Test GET /api/discovery/lifecycle/candidates returns promotion/demotion candidates"""
        response = requests.get(f"{BASE_URL}/api/discovery/lifecycle/candidates", timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "promotionCandidates" in data
        assert "demotionCandidates" in data
        
        # Validate candidate structure if any exist
        for candidate in data.get("promotionCandidates", []):
            assert "id" in candidate
            assert "name" in candidate
            assert "status" in candidate
            assert "confidence" in candidate
        
        for candidate in data.get("demotionCandidates", []):
            assert "id" in candidate
            assert "name" in candidate
            assert "status" in candidate
            assert "confidence" in candidate
        
        print(f"✓ Lifecycle Candidates: promotion={len(data.get('promotionCandidates', []))}, demotion={len(data.get('demotionCandidates', []))}")


class TestRobustnessCalculation:
    """Tests to verify robustness scoring logic"""
    
    def test_robustness_scoring_components(self):
        """Verify robustness score has all expected components"""
        # Get a validated strategy
        response = requests.get(f"{BASE_URL}/api/discovery/strategies", timeout=10)
        if response.status_code != 200:
            pytest.skip("Could not get strategies")
        
        strategies = response.json().get("strategies", [])
        if not strategies:
            pytest.skip("No strategies available")
        
        strategy_id = strategies[0].get("id")
        
        # Validate the strategy
        response = requests.get(
            f"{BASE_URL}/api/discovery/edge-validation/{strategy_id}",
            timeout=15
        )
        
        assert response.status_code == 200
        data = response.json()
        
        robustness = data.get("robustness", {})
        
        # Verify all robustness components
        assert 0 <= robustness.get("overallScore", -1) <= 1, "Overall score should be 0-1"
        assert isinstance(robustness.get("regimeScores"), dict), "Regime scores should be a dict"
        assert 0 <= robustness.get("crossAssetScore", -1) <= 1, "Cross asset score should be 0-1"
        assert 0 <= robustness.get("temporalStability", -1) <= 1, "Temporal stability should be 0-1"
        assert isinstance(robustness.get("minimumEvidence"), bool), "Minimum evidence should be bool"
        assert 0 <= robustness.get("regimeCoverage", -1) <= 1, "Regime coverage should be 0-1"
        
        # Check regime breakdown
        regime_scores = robustness.get("regimeScores", {})
        for regime, score in regime_scores.items():
            assert 0 <= score <= 1, f"Regime {regime} score should be 0-1"
        
        print(f"✓ Robustness Calculation: overall={robustness.get('overallScore'):.4f}, temporal={robustness.get('temporalStability'):.4f}, regimes={len(regime_scores)}")


class TestSimilarityPenalty:
    """Tests to verify similarity penalty logic"""
    
    def test_similarity_penalty_calculation(self):
        """Verify similarity penalty is calculated correctly"""
        # Get all strategies
        response = requests.get(f"{BASE_URL}/api/discovery/strategies", timeout=10)
        if response.status_code != 200:
            pytest.skip("Could not get strategies")
        
        strategies = response.json().get("strategies", [])
        if len(strategies) < 2:
            pytest.skip("Need at least 2 strategies for similarity test")
        
        # Validate the second strategy (should compare against first)
        strategy_id = strategies[1].get("id")
        response = requests.get(
            f"{BASE_URL}/api/discovery/edge-validation/{strategy_id}",
            timeout=15
        )
        
        assert response.status_code == 200
        data = response.json()
        
        similarity = data.get("similarity", {})
        
        # Verify all similarity components
        assert 0 <= similarity.get("penalty", -1) <= 1, "Penalty should be 0-1"
        assert isinstance(similarity.get("similarStrategies"), list), "Similar strategies should be list"
        assert isinstance(similarity.get("overlapFeatures"), list), "Overlap features should be list"
        assert 0 <= similarity.get("correlation", -1) <= 1, "Correlation should be 0-1"
        assert isinstance(similarity.get("isRedundant"), bool), "Is redundant should be bool"
        assert isinstance(similarity.get("notes"), list), "Notes should be list"
        
        print(f"✓ Similarity Penalty: penalty={similarity.get('penalty'):.4f}, similar_count={len(similarity.get('similarStrategies', []))}, redundant={similarity.get('isRedundant')}")


class TestConfidenceScore:
    """Tests to verify confidence score calculation"""
    
    def test_confidence_score_components(self):
        """Verify confidence score combines all components correctly"""
        # Get strategies
        response = requests.get(f"{BASE_URL}/api/discovery/strategies", timeout=10)
        if response.status_code != 200:
            pytest.skip("Could not get strategies")
        
        strategies = response.json().get("strategies", [])
        if not strategies:
            pytest.skip("No strategies available")
        
        strategy_id = strategies[0].get("id")
        
        response = requests.get(
            f"{BASE_URL}/api/discovery/edge-validation/{strategy_id}",
            timeout=15
        )
        
        assert response.status_code == 200
        data = response.json()
        
        confidence = data.get("confidence", {})
        
        # Verify all confidence components
        assert 0 <= confidence.get("score", -1) <= 1, "Score should be 0-1"
        assert 0 <= confidence.get("robustnessComponent", -1) <= 1, "Robustness component should be 0-1"
        assert -1 <= confidence.get("similarityComponent", 0) <= 1, "Similarity component can be negative"
        assert 0 <= confidence.get("evidenceComponent", -1) <= 1, "Evidence component should be 0-1"
        assert 0 <= confidence.get("regimeStabilityComponent", -1) <= 1, "Regime stability should be 0-1"
        
        # Verify breakdown matches components
        breakdown = confidence.get("breakdown", {})
        assert "robustness" in breakdown
        assert "similarity_penalty" in breakdown
        assert "evidence" in breakdown
        assert "regime_stability" in breakdown
        assert "raw_score" in breakdown
        assert "final_score" in breakdown
        
        # Verify verdict is valid
        assert confidence.get("verdict") in ["STRONG", "MODERATE", "WEAK", "REJECT", "NEEDS_MORE_DATA"]
        
        # Verify reasons exist
        reasons = confidence.get("reasons", [])
        assert isinstance(reasons, list)
        
        print(f"✓ Confidence Score: score={confidence.get('score'):.4f}, verdict={confidence.get('verdict')}, reasons={len(reasons)}")


class TestIntegration:
    """Integration tests for full edge validation workflow"""
    
    def test_full_discovery_to_validation_workflow(self):
        """Test complete workflow: discovery -> validation -> apply"""
        # Step 1: Run discovery
        run_response = requests.post(
            f"{BASE_URL}/api/discovery/run",
            json={"symbols": ["BTCUSDT", "ETHUSDT"], "timeframes": ["1h", "4h"]},
            timeout=30
        )
        assert run_response.status_code == 200
        run_data = run_response.json()
        strategy_count = run_data.get("strategiesGenerated", 0)
        print(f"  Step 1: Generated {strategy_count} strategies")
        
        # Step 2: Batch validate
        batch_response = requests.post(
            f"{BASE_URL}/api/discovery/edge-validation/batch",
            json={},
            timeout=30
        )
        assert batch_response.status_code == 200
        batch_data = batch_response.json()
        validated_count = batch_data.get("summary", {}).get("totalValidated", 0)
        print(f"  Step 2: Validated {validated_count} strategies")
        
        # Step 3: Apply validation
        apply_response = requests.post(
            f"{BASE_URL}/api/discovery/edge-validation/apply",
            json={},
            timeout=30
        )
        assert apply_response.status_code == 200
        apply_data = apply_response.json()
        updated_count = apply_data.get("updated", 0)
        print(f"  Step 3: Updated {updated_count} strategy statuses")
        
        # Step 4: Check lifecycle report
        report_response = requests.get(f"{BASE_URL}/api/discovery/lifecycle/report", timeout=10)
        assert report_response.status_code == 200
        report_data = report_response.json()
        print(f"  Step 4: Lifecycle report shows {report_data.get('totalStrategies')} strategies, {report_data.get('activeStrategies')} active")
        
        # Verify workflow integrity
        assert validated_count == updated_count, "Validated count should match updated count"
        assert report_data.get("totalStrategies", 0) >= strategy_count, "Report should include all strategies"
        
        print("✓ Full Workflow Integration Test Passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
