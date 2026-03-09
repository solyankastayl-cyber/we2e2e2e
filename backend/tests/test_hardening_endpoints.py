"""
Test suite for Decision Pipeline Hardening endpoints
- Health Check (deep)
- Model Registry
- Feature Schema
- Pipeline Audit
- Decision Compute with Audit Trail
"""

import pytest
import requests
import os

BASE_URL = "http://localhost:8001"


class TestDeepHealthCheck:
    """Test GET /api/ta/health/deep - comprehensive pipeline health check"""
    
    def test_deep_health_returns_200(self):
        """Should return 200 with status and all checks"""
        response = requests.get(f"{BASE_URL}/api/ta/health/deep")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["ok"] in [True, False], "Should have 'ok' field"
        assert "status" in data, "Should have 'status' field"
        assert "timestamp" in data, "Should have 'timestamp' field"
        assert "checks" in data, "Should have 'checks' field"
        print(f"Health status: {data['status']}")
    
    def test_deep_health_has_required_checks(self):
        """Should include all required system checks"""
        response = requests.get(f"{BASE_URL}/api/ta/health/deep")
        data = response.json()
        checks = data.get("checks", {})
        
        required_checks = [
            "mongodb", "candles", "dataset_v4", "ml_models",
            "model_registry", "feature_schema", "audit", "quality_engine"
        ]
        
        for check in required_checks:
            assert check in checks, f"Missing check: {check}"
            assert "status" in checks[check], f"Check '{check}' missing status"
            assert checks[check]["status"] in ["ok", "warn", "fail"], f"Invalid status for '{check}'"
        
        print(f"All {len(required_checks)} checks present")


class TestModelRegistry:
    """Test Model Registry endpoints"""
    
    def test_get_all_models_returns_200(self):
        """GET /api/ta/registry/models should return list of models"""
        response = requests.get(f"{BASE_URL}/api/ta/registry/models")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "models" in data
        assert "count" in data
        assert isinstance(data["models"], list)
        print(f"Found {data['count']} models")
    
    def test_get_all_models_has_required_models(self):
        """Should have lightgbm_entry_v1 and lightgbm_r_v1 registered"""
        response = requests.get(f"{BASE_URL}/api/ta/registry/models")
        data = response.json()
        
        model_ids = [m["modelId"] for m in data["models"]]
        assert "lightgbm_entry_v1" in model_ids, "Missing lightgbm_entry_v1 model"
        assert "lightgbm_r_v1" in model_ids, "Missing lightgbm_r_v1 model"
        print(f"Both required models present: {model_ids}")
    
    def test_get_active_models_returns_200(self):
        """GET /api/ta/registry/models/active should return active models by type"""
        response = requests.get(f"{BASE_URL}/api/ta/registry/models/active")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "active" in data
        
        active = data["active"]
        assert "entry" in active, "Missing entry model type"
        assert "r" in active, "Missing r model type"
        assert "regime" in active, "Missing regime model type"
        
        # Validate active models are populated
        assert active["entry"] is not None, "Entry model should be populated"
        assert active["r"] is not None, "R model should be populated"
        print(f"Active models - entry: {active['entry']['modelId']}, r: {active['r']['modelId']}")
    
    def test_quality_gates_pass_for_entry_model(self):
        """POST /api/ta/registry/models/lightgbm_entry_v1/quality-gates should pass"""
        response = requests.post(
            f"{BASE_URL}/api/ta/registry/models/lightgbm_entry_v1/quality-gates",
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["passed"] is True, "Quality gates should pass for entry model"
        assert "checks" in data
        
        # AUC check should pass (0.64 >= 0.55 threshold)
        if "auc" in data["checks"]:
            auc_check = data["checks"]["auc"]
            assert auc_check["passed"] is True
            assert auc_check["value"] >= auc_check["threshold"]
            print(f"AUC check passed: {auc_check['value']} >= {auc_check['threshold']}")


class TestFeatureSchema:
    """Test Feature Schema endpoints"""
    
    def test_get_active_schema_returns_200(self):
        """GET /api/ta/registry/schema should return active schema"""
        response = requests.get(f"{BASE_URL}/api/ta/registry/schema")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "schema" in data
        
        schema = data["schema"]
        assert schema is not None, "Should have active schema"
        assert schema["version"] == "1.0.0", "Schema version should be 1.0.0"
        assert len(schema["features"]) == 18, f"Schema should have 18 features, got {len(schema['features'])}"
        print(f"Active schema: v{schema['version']} with {len(schema['features'])} features")
    
    def test_validate_features_incomplete(self):
        """POST /api/ta/registry/schema/validate with incomplete features should return valid=false"""
        response = requests.post(
            f"{BASE_URL}/api/ta/registry/schema/validate",
            json={"features": {"score": 0.75, "confidence": 0.8}}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["valid"] is False, "Should return valid=false for incomplete features"
        assert len(data["missing"]) > 0, "Should have missing features"
        print(f"Validation: valid={data['valid']}, missing {len(data['missing'])} features")
    
    def test_validate_features_complete(self):
        """POST /api/ta/registry/schema/validate with all features should return valid=true"""
        all_features = {
            "score": 0.75, "confidence": 0.8, "risk_reward": 2.0, "gate_score": 0.5,
            "geom_fit_error": 0.1, "geom_maturity": 0.8, "geom_compression": 0.5,
            "geom_symmetry": 0.9, "graph_boost_factor": 1.2, "graph_lift": 0.15,
            "graph_conditional_prob": 0.6, "pattern_strength": 0.7, "pattern_duration": 14,
            "volatility": 0.02, "atr_ratio": 1.5, "regime_trend_up": 0.3,
            "regime_trend_down": 0.2, "regime_range": 0.5
        }
        
        response = requests.post(
            f"{BASE_URL}/api/ta/registry/schema/validate",
            json={"features": all_features}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["valid"] is True, "Should return valid=true for complete features"
        assert len(data["missing"]) == 0, "Should have no missing features"
        print(f"Validation: valid={data['valid']}, complete feature set")


class TestDecisionComputeWithAudit:
    """Test Decision Compute with Audit Trail"""
    
    @pytest.fixture(scope="class")
    def computed_decision(self):
        """Compute a decision and return the response for subsequent tests"""
        response = requests.post(
            f"{BASE_URL}/api/ta/decision/compute",
            json={
                "asset": "BTCUSDT",
                "timeframe": "1D",
                "candles": [
                    {"openTime": 1700000000000, "open": 40000, "high": 41000, "low": 39000, "close": 40500, "volume": 100},
                    {"openTime": 1700086400000, "open": 40500, "high": 42000, "low": 40000, "close": 41500, "volume": 120},
                    {"openTime": 1700172800000, "open": 41500, "high": 43000, "low": 41000, "close": 42500, "volume": 110},
                    {"openTime": 1700259200000, "open": 42500, "high": 44000, "low": 42000, "close": 43500, "volume": 130},
                    {"openTime": 1700345600000, "open": 43500, "high": 45000, "low": 43000, "close": 44000, "volume": 100}
                ],
                "scenarios": [
                    {"scenarioId": "test_audit_1", "patternType": "ASCENDING_TRIANGLE", "direction": "LONG",
                     "entry": 42000, "stop": 39000, "target1": 45000, "score": 0.75, "confidence": 0.8, "touches": 3}
                ]
            }
        )
        assert response.status_code == 200
        return response.json()
    
    def test_decision_compute_returns_runId(self, computed_decision):
        """POST /api/ta/decision/compute should return runId in response"""
        assert computed_decision["ok"] is True
        assert "runId" in computed_decision, "Response should include runId"
        assert computed_decision["runId"].startswith("run_"), "runId should start with 'run_'"
        assert "decision" in computed_decision
        print(f"Decision computed with runId: {computed_decision['runId']}")
    
    def test_decision_has_required_fields(self, computed_decision):
        """Decision response should have all required fields"""
        decision = computed_decision["decision"]
        
        required_fields = ["asset", "timeframe", "timestamp", "regime", "modelId",
                          "totalScenarios", "passedGate", "rejected", "topScenario"]
        for field in required_fields:
            assert field in decision, f"Decision missing field: {field}"
        
        print(f"Decision fields valid: asset={decision['asset']}, regime={decision['regime']}")


class TestPipelineAudit:
    """Test Pipeline Audit endpoints"""
    
    def test_get_pipeline_runs_returns_200(self):
        """GET /api/ta/pipeline/runs should return recent pipeline runs"""
        response = requests.get(f"{BASE_URL}/api/ta/pipeline/runs")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "runs" in data
        assert "count" in data
        assert isinstance(data["runs"], list)
        print(f"Found {data['count']} pipeline runs")
    
    def test_pipeline_runs_have_required_fields(self):
        """Pipeline runs should have runId, status, duration fields"""
        response = requests.get(f"{BASE_URL}/api/ta/pipeline/runs")
        data = response.json()
        
        # Find runs with new schema (have duration field)
        new_runs = [r for r in data["runs"] if "duration" in r]
        assert len(new_runs) > 0, "Should have at least one run with duration field"
        
        run = new_runs[0]
        assert "runId" in run
        assert "status" in run
        assert run["status"] in ["RUNNING", "DONE", "FAILED"]
        print(f"Sample run: runId={run['runId']}, status={run['status']}, duration={run.get('duration')}ms")
    
    def test_get_audit_trail_for_existing_run(self):
        """GET /api/ta/pipeline/trail/{runId} should return audit layers"""
        # First get a valid runId
        runs_response = requests.get(f"{BASE_URL}/api/ta/pipeline/runs")
        runs = runs_response.json()["runs"]
        
        # Find a run with the new audit format (has featureSchemaVersion)
        audit_runs = [r for r in runs if "featureSchemaVersion" in r]
        if not audit_runs:
            pytest.skip("No audit runs available for testing")
        
        run_id = audit_runs[0]["runId"]
        
        response = requests.get(f"{BASE_URL}/api/ta/pipeline/trail/{run_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "trail" in data
        assert "layers" in data
        
        # Check for expected layers
        layer_names = [t["layer"] for t in data["trail"]]
        expected_layers = ["patterns", "regime", "geometry", "gates", "ml", "ranking"]
        for layer in expected_layers:
            assert layer in layer_names, f"Missing layer: {layer}"
        
        print(f"Audit trail for {run_id}: {data['layers']} layers - {layer_names}")
    
    def test_get_decision_for_existing_run(self):
        """GET /api/ta/pipeline/decision/{runId} should return stored decision"""
        # First get a valid runId with decision
        runs_response = requests.get(f"{BASE_URL}/api/ta/pipeline/runs")
        runs = runs_response.json()["runs"]
        
        # Find a run with the new audit format
        audit_runs = [r for r in runs if "featureSchemaVersion" in r]
        if not audit_runs:
            pytest.skip("No audit runs available for testing")
        
        run_id = audit_runs[0]["runId"]
        
        response = requests.get(f"{BASE_URL}/api/ta/pipeline/decision/{run_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "decision" in data
        
        decision = data["decision"]
        assert "runId" in decision
        assert "modelId" in decision
        assert "featureSchemaVersion" in decision
        assert "topScenario" in decision
        print(f"Decision for {run_id}: modelId={decision['modelId']}, schemaVersion={decision['featureSchemaVersion']}")
    
    def test_get_single_run_by_id(self):
        """GET /api/ta/pipeline/run/{runId} should return run details"""
        # First get a valid runId
        runs_response = requests.get(f"{BASE_URL}/api/ta/pipeline/runs")
        runs = runs_response.json()["runs"]
        
        audit_runs = [r for r in runs if "featureSchemaVersion" in r]
        if not audit_runs:
            pytest.skip("No audit runs available for testing")
        
        run_id = audit_runs[0]["runId"]
        
        response = requests.get(f"{BASE_URL}/api/ta/pipeline/run/{run_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "run" in data
        
        run = data["run"]
        assert run["runId"] == run_id
        assert "status" in run
        assert "duration" in run or run["status"] == "RUNNING"
        print(f"Run details: {run_id}, status={run['status']}")


class TestErrorHandling:
    """Test error handling for hardening endpoints"""
    
    def test_quality_gates_unknown_model(self):
        """Quality gates for unknown model should return passed=false"""
        response = requests.post(
            f"{BASE_URL}/api/ta/registry/models/unknown_model_xyz/quality-gates",
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert data["passed"] is False
        print("Unknown model quality gates correctly returned passed=false")
    
    def test_pipeline_run_not_found(self):
        """GET /api/ta/pipeline/run/{invalid_id} should return error"""
        response = requests.get(f"{BASE_URL}/api/ta/pipeline/run/nonexistent_run_id")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is False
        assert "error" in data
        print(f"Non-existent run correctly returned error: {data['error']}")
    
    def test_pipeline_decision_not_found(self):
        """GET /api/ta/pipeline/decision/{invalid_id} should return error"""
        response = requests.get(f"{BASE_URL}/api/ta/pipeline/decision/nonexistent_run_id")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is False
        assert "error" in data
        print(f"Non-existent decision correctly returned error: {data['error']}")
    
    def test_validate_features_missing_body(self):
        """Schema validation without features should return error"""
        response = requests.post(
            f"{BASE_URL}/api/ta/registry/schema/validate",
            json={}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is False
        assert "error" in data
        print(f"Missing features body correctly returned error: {data['error']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
