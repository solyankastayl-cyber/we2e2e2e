"""
Test suite for P0 Backend Hardening - Event Bus, Policy Engine, Dataset Registry, Infrastructure

Tests:
1. Event Bus idempotency with idempotency_key
2. Event Bus DLQ endpoints
3. Policy Engine schema validation
4. Policy Engine update validation
5. Dataset Registry consistency checks
6. Dataset Registry registration validation
7. Infrastructure health and hardening stats
8. Circuit breakers listing
9. Stress test endpoint
10. Event Bus basic health
"""

import pytest
import requests
import os
import uuid
import time

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")


class TestEventBusHealth:
    """Test Event Bus health endpoint"""
    
    def test_event_bus_health_returns_200(self):
        """GET /api/events/health should return 200"""
        response = requests.get(f"{BASE_URL}/api/events/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "enabled" in data, "Should have 'enabled' field"
        assert "status" in data, "Should have 'status' field"
        assert data["status"] == "ok", f"Expected status 'ok', got {data['status']}"
        print(f"Event Bus health: {data['status']}, enabled={data['enabled']}")


class TestEventBusIdempotency:
    """Test Event Bus idempotency with idempotency_key"""
    
    def test_normal_publish_without_idempotency_key(self):
        """POST /api/events/publish without idempotency_key should work"""
        response = requests.post(
            f"{BASE_URL}/api/events/publish",
            json={
                "type": "test_event_no_key",
                "source": "test_runner",
                "payload": {"test": True, "timestamp": int(time.time() * 1000)}
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] is True, f"Event publish should succeed: {data}"
        assert "event" in data, "Response should include event"
        print(f"Published event successfully: {data['event'].get('id', 'no-id')}")
    
    def test_first_publish_with_idempotency_key_succeeds(self):
        """POST /api/events/publish with new idempotency_key should succeed"""
        unique_key = f"test_idem_{uuid.uuid4().hex[:16]}"
        
        response = requests.post(
            f"{BASE_URL}/api/events/publish",
            json={
                "type": "test_idempotent_event",
                "source": "test_runner",
                "payload": {"test": True},
                "idempotency_key": unique_key
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] is True, f"First event with idempotency_key should succeed: {data}"
        assert data.get("duplicate", False) is False, "Should not be marked as duplicate"
        print(f"First publish succeeded with idempotency_key: {unique_key}")
        
        # Return key for next test
        return unique_key
    
    def test_duplicate_idempotency_key_rejected(self):
        """POST /api/events/publish with same idempotency_key should be rejected"""
        # First publish
        unique_key = f"test_dup_{uuid.uuid4().hex[:16]}"
        
        first_response = requests.post(
            f"{BASE_URL}/api/events/publish",
            json={
                "type": "test_duplicate_event",
                "source": "test_runner",
                "payload": {"first": True},
                "idempotency_key": unique_key
            }
        )
        assert first_response.status_code == 200
        first_data = first_response.json()
        assert first_data["success"] is True, "First publish should succeed"
        
        # Second publish with same key
        second_response = requests.post(
            f"{BASE_URL}/api/events/publish",
            json={
                "type": "test_duplicate_event",
                "source": "test_runner",
                "payload": {"second": True},  # Different payload
                "idempotency_key": unique_key  # Same key
            }
        )
        assert second_response.status_code == 200
        second_data = second_response.json()
        
        # Should be rejected as duplicate
        assert second_data["success"] is False, f"Duplicate idempotency_key should fail: {second_data}"
        assert second_data.get("duplicate", False) is True, "Should be marked as duplicate"
        print(f"Duplicate correctly rejected for key: {unique_key}")


class TestEventBusDLQ:
    """Test Event Bus DLQ (Dead Letter Queue) endpoints"""
    
    def test_dlq_stats_returns_200(self):
        """GET /api/events/dlq/stats should return 200"""
        response = requests.get(f"{BASE_URL}/api/events/dlq/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check required fields
        assert "connected" in data, "Should have 'connected' field"
        assert "total" in data, "Should have 'total' field"
        assert "pending" in data, "Should have 'pending' field"
        assert "resolved" in data, "Should have 'resolved' field"
        print(f"DLQ stats: total={data['total']}, pending={data['pending']}, resolved={data['resolved']}")
    
    def test_dlq_pending_returns_200(self):
        """GET /api/events/dlq/pending should return 200"""
        response = requests.get(f"{BASE_URL}/api/events/dlq/pending")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "dead_letters" in data, "Should have 'dead_letters' field"
        assert "count" in data, "Should have 'count' field"
        assert isinstance(data["dead_letters"], list), "'dead_letters' should be a list"
        print(f"DLQ pending: {data['count']} dead letters")


class TestPolicyEngineValidation:
    """Test Policy Engine schema validation"""
    
    def test_policy_validate_rules_valid(self):
        """POST /api/policies/validate/rules with valid rules should pass"""
        response = requests.post(
            f"{BASE_URL}/api/policies/validate/rules",
            json={
                "policy_id": "RISK_LIMITS",
                "rules": {
                    "max_portfolio_drawdown": 0.15,
                    "max_leverage": 2.0,
                    "max_single_strategy_weight": 0.10
                }
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "valid" in data, "Response should have 'valid' field"
        assert data["valid"] is True, f"Valid rules should pass validation: {data}"
        assert data.get("violations", []) == [], "Should have no violations"
        print(f"Valid rules passed: {data['rules_checked']} rules checked")
    
    def test_policy_validate_rules_invalid_range(self):
        """POST /api/policies/validate/rules with out-of-range values should fail"""
        response = requests.post(
            f"{BASE_URL}/api/policies/validate/rules",
            json={
                "policy_id": "RISK_LIMITS",
                "rules": {
                    "max_leverage": 500.0  # Out of range (0-100)
                }
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "valid" in data, "Response should have 'valid' field"
        assert data["valid"] is False, f"Out-of-range values should fail: {data}"
        assert len(data.get("violations", [])) > 0, "Should have violations"
        print(f"Invalid rules correctly rejected: {len(data['violations'])} violations")
    
    def test_policy_validate_rules_unknown_rule(self):
        """POST /api/policies/validate/rules with unknown rule should flag it"""
        response = requests.post(
            f"{BASE_URL}/api/policies/validate/rules",
            json={
                "policy_id": "RISK_LIMITS",
                "rules": {
                    "unknown_rule_xyz": 0.5
                }
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["valid"] is False, f"Unknown rule should fail validation: {data}"
        violations = data.get("violations", [])
        assert any(v.get("error") == "unknown_rule" for v in violations), "Should flag unknown rule"
        print(f"Unknown rule correctly flagged")


class TestPolicyEngineUpdateValidation:
    """Test Policy Engine PATCH validation with out-of-range values"""
    
    def test_patch_risk_limits_valid_values(self):
        """PATCH /api/policies/RISK_LIMITS with valid values should succeed"""
        response = requests.patch(
            f"{BASE_URL}/api/policies/RISK_LIMITS",
            json={
                "rules": {
                    "max_portfolio_drawdown": 0.18
                }
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "error" not in data or data.get("error") != "validation_failed", f"Valid update should succeed: {data}"
        print(f"Policy update succeeded")
    
    def test_patch_risk_limits_out_of_range_returns_422(self):
        """PATCH /api/policies/RISK_LIMITS with out-of-range values should return 422"""
        response = requests.patch(
            f"{BASE_URL}/api/policies/RISK_LIMITS",
            json={
                "rules": {
                    "max_leverage": 200.0  # Out of range: max is 100.0
                }
            }
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print(f"Out-of-range update correctly returned 422")
    
    def test_patch_risk_limits_negative_drawdown_returns_422(self):
        """PATCH /api/policies/RISK_LIMITS with negative drawdown should return 422"""
        response = requests.patch(
            f"{BASE_URL}/api/policies/RISK_LIMITS",
            json={
                "rules": {
                    "max_portfolio_drawdown": -0.5  # Out of range: min is 0.0
                }
            }
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print(f"Negative drawdown correctly returned 422")


class TestDatasetRegistryConsistency:
    """Test Dataset Registry consistency checks"""
    
    def test_consistency_check_existing_dataset(self):
        """POST /api/datasets/{dataset_id}/consistency for existing dataset"""
        # btc_daily_v1 is a default dataset
        response = requests.post(f"{BASE_URL}/api/datasets/btc_daily_v1/consistency")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "valid" in data, "Should have 'valid' field"
        assert "issues" in data, "Should have 'issues' field"
        assert "warnings" in data, "Should have 'warnings' field"
        assert "checks_passed" in data, "Should have 'checks_passed' field"
        print(f"Consistency check: valid={data['valid']}, checks_passed={data['checks_passed']}/{data['total_checks']}")
    
    def test_consistency_check_nonexistent_dataset_returns_404(self):
        """POST /api/datasets/nonexistent/consistency should return 404"""
        response = requests.post(f"{BASE_URL}/api/datasets/nonexistent_dataset_xyz/consistency")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Non-existent dataset correctly returned 404")


class TestDatasetRegistryRegistration:
    """Test Dataset Registry registration validation"""
    
    def test_register_valid_dataset(self):
        """POST /api/datasets with valid data should succeed"""
        unique_id = f"test_dataset_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(
            f"{BASE_URL}/api/datasets",
            json={
                "dataset_id": unique_id,
                "name": "Test Dataset",
                "asset": "TEST",
                "version": "1.0",
                "start_date": "2020-01-01",
                "end_date": "2025-01-01",
                "rows": 1500,
                "source": "internal",
                "timeframe": "1D",
                "columns": ["open", "high", "low", "close", "volume"]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "dataset" in data, "Should have 'dataset' field"
        assert data.get("validation", {}).get("valid", False) is True, f"Valid dataset should pass: {data}"
        print(f"Valid dataset registered: {unique_id}")
    
    def test_register_invalid_dataset_returns_422(self):
        """POST /api/datasets with invalid data (missing columns) should return 422"""
        unique_id = f"invalid_dataset_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(
            f"{BASE_URL}/api/datasets",
            json={
                "dataset_id": unique_id,
                "name": "Invalid Dataset",
                "asset": "TEST",
                "rows": -100,  # Invalid: negative rows
                "timeframe": "INVALID_TF",  # Invalid timeframe
                "columns": ["foo", "bar"]  # Missing required columns
            }
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("Invalid dataset correctly returned 422")
    
    def test_register_dataset_invalid_date_range(self):
        """POST /api/datasets with start_date >= end_date should return 422"""
        unique_id = f"invalid_dates_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(
            f"{BASE_URL}/api/datasets",
            json={
                "dataset_id": unique_id,
                "name": "Invalid Date Dataset",
                "asset": "TEST",
                "start_date": "2025-01-01",
                "end_date": "2020-01-01",  # end < start
                "rows": 1000,
                "source": "internal",
                "timeframe": "1D",
                "columns": ["open", "high", "low", "close", "volume"]
            }
        )
        
        # Should return 422 Unprocessable Entity
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"
        print("Invalid date range correctly returned 422")


class TestInfrastructureHealth:
    """Test Infrastructure health endpoints"""
    
    def test_infra_health_returns_200(self):
        """GET /api/infra/health should return 200"""
        response = requests.get(f"{BASE_URL}/api/infra/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "status" in data, "Should have 'status' field"
        assert data["status"] in ["ok", "degraded"], f"Status should be 'ok' or 'degraded', got {data['status']}"
        assert "timestamp" in data, "Should have 'timestamp' field"
        assert "health_checks" in data, "Should have 'health_checks' field"
        print(f"Infrastructure health: {data['status']}")
    
    def test_infra_hardening_returns_200(self):
        """GET /api/infra/hardening should return 200"""
        response = requests.get(f"{BASE_URL}/api/infra/hardening")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check for hardening components
        assert "idempotency" in data, "Should have 'idempotency' stats"
        assert "dead_letter_queue" in data, "Should have 'dead_letter_queue' stats"
        assert "circuit_breakers" in data, "Should have 'circuit_breakers' stats"
        print(f"Hardening stats: idempotency={data['idempotency']}, dlq={data['dead_letter_queue']}")


class TestCircuitBreakers:
    """Test Circuit Breakers listing"""
    
    def test_circuits_list_returns_200(self):
        """GET /api/infra/circuits should return 200"""
        response = requests.get(f"{BASE_URL}/api/infra/circuits")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "circuit_breakers" in data, "Should have 'circuit_breakers' field"
        assert "count" in data, "Should have 'count' field"
        assert isinstance(data["circuit_breakers"], dict), "'circuit_breakers' should be a dict"
        print(f"Circuit breakers: {data['count']} registered")


class TestStressTest:
    """Test Stress Test endpoint"""
    
    def test_stress_test_low_level_event_bus(self):
        """POST /api/infra/stress-test with LOW level event_bus should succeed"""
        response = requests.post(
            f"{BASE_URL}/api/infra/stress-test",
            json={
                "level": "LOW",
                "test_type": "event_bus"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["success"] is True, f"Stress test should succeed: {data}"
        assert "result" in data, "Should have 'result' field"
        
        result = data["result"]
        assert "test_name" in result, "Result should have 'test_name'"
        assert "success_rate" in result, "Result should have 'success_rate'"
        assert "operations_per_second" in result, "Result should have 'operations_per_second'"
        print(f"Stress test result: {result['test_name']}, success_rate={result['success_rate']}, ops/s={result['operations_per_second']}")
    
    def test_stress_test_invalid_level_returns_400(self):
        """POST /api/infra/stress-test with invalid level should return 400"""
        response = requests.post(
            f"{BASE_URL}/api/infra/stress-test",
            json={
                "level": "INVALID_LEVEL",
                "test_type": "event_bus"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("Invalid level correctly returned 400")


class TestPolicyEngineHealth:
    """Test Policy Engine health endpoint"""
    
    def test_policy_engine_health(self):
        """GET /api/policies/health should return 200"""
        response = requests.get(f"{BASE_URL}/api/policies/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "enabled" in data, "Should have 'enabled' field"
        assert "status" in data, "Should have 'status' field"
        assert "total_policies" in data, "Should have 'total_policies' field"
        print(f"Policy Engine health: enabled={data['enabled']}, policies={data['total_policies']}")


class TestDatasetRegistryHealth:
    """Test Dataset Registry health endpoint"""
    
    def test_dataset_registry_health(self):
        """GET /api/datasets/health should return 200"""
        response = requests.get(f"{BASE_URL}/api/datasets/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "enabled" in data, "Should have 'enabled' field"
        assert "status" in data, "Should have 'status' field"
        assert "total_datasets" in data, "Should have 'total_datasets' field"
        print(f"Dataset Registry health: enabled={data['enabled']}, datasets={data['total_datasets']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
