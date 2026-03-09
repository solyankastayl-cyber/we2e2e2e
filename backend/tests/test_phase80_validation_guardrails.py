"""
Phase 8.0: Validation Guardrails API Tests
Tests for lookahead bias detection, data snooping protection, and execution assumption validation.

Endpoints tested:
- GET /api/guardrails/health - Health check
- POST /api/guardrails/validate - Full validation with backtestConfig
- POST /api/guardrails/quick-check - Quick pre-flight validation
- GET /api/guardrails/execution/recommended-config - Recommended execution config
- POST /api/guardrails/execution/cost-drag - Cost drag estimation
- POST /api/guardrails/snooping/correction-factor - Multiple testing correction
- POST /api/guardrails/lookahead/quick-check - Lookahead risk assessment
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGuardrailsHealth:
    """Health check endpoint tests"""
    
    def test_guardrails_health_returns_enabled(self):
        """Test /api/guardrails/health returns enabled status"""
        response = requests.get(f"{BASE_URL}/api/guardrails/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify health response structure
        assert data.get("enabled") == True
        assert data.get("version") == "guardrails_v1_phase8.0"
        assert data.get("status") == "ok"
        
        # Verify all components are ok
        components = data.get("components", {})
        assert components.get("lookahead_detector") == "ok"
        assert components.get("snooping_guard") == "ok"
        assert components.get("execution_validator") == "ok"
        
        print(f"Guardrails health check passed: {data}")


class TestFullValidation:
    """POST /api/guardrails/validate - Full validation tests"""
    
    def test_unrealistic_config_generates_violations(self):
        """Test that unrealistic config (zero slippage/fees) generates violations"""
        unrealistic_config = {
            "backtestConfig": {
                "slippage_bps": 0,
                "fee_bps": 0,
                "fill_delay_ms": 0,
                "slippage_model": "none",
                "fee_model": "none",
                "liquidity_model": "unlimited"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/guardrails/validate",
            json=unrealistic_config
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have multiple violations with unrealistic config
        assert data.get("totalViolations") >= 5  # Zero slippage, fees, unlimited liquidity, instant fill, no impact
        assert data.get("highViolations") >= 2  # At least zero slippage and zero fees are HIGH
        
        # Execution check should FAIL with unrealistic config (even if overall passes due to lenient thresholds)
        execution_check = data.get("executionCheck", {})
        assert execution_check.get("passed") == False
        assert execution_check.get("realisticScore", 1) < 0.5  # Low realism score
        assert len(execution_check.get("violations", [])) >= 4  # Multiple execution violations
        
        # Check violation types present
        violation_types = [v.get("type") for v in execution_check.get("violations", [])]
        assert "EXECUTION_ZERO_SLIPPAGE" in violation_types
        assert "EXECUTION_UNREALISTIC_FEES" in violation_types
        assert "EXECUTION_UNLIMITED_LIQUIDITY" in violation_types
        assert "EXECUTION_INSTANT_FILL" in violation_types
        
        # Should have recommendations for improvement
        recommendations = data.get("recommendations", [])
        assert len(recommendations) >= 2
        
        print(f"Unrealistic config correctly generates {data.get('totalViolations')} violations")
        print(f"Execution violations: {violation_types}")
        print(f"Realism score: {execution_check.get('realisticScore')}")
        print(f"Recommendations: {recommendations}")
    
    def test_realistic_config_passes_validation(self):
        """Test that realistic config passes validation"""
        realistic_config = {
            "backtestConfig": {
                "slippage_bps": 15,
                "fee_bps": 10,
                "fill_delay_ms": 100,
                "slippage_model": "fixed",
                "fee_model": "fixed",
                "liquidity_model": "adv_based"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/guardrails/validate",
            json=realistic_config
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should pass with realistic config
        assert data.get("passed") == True
        
        # Overall score should be high
        assert data.get("overallScore", 0) >= 0.7
        
        # Execution check should pass
        execution_check = data.get("executionCheck", {})
        assert execution_check.get("passed") == True
        assert execution_check.get("realisticScore", 0) >= 0.7
        
        print(f"Realistic config passed with score: {data.get('overallScore')}")
        print(f"Execution realism score: {execution_check.get('realisticScore')}")
    
    def test_full_validation_response_structure(self):
        """Test that validation response has correct structure"""
        config = {
            "backtestConfig": {
                "slippage_bps": 10,
                "fee_bps": 10
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/guardrails/validate",
            json=config
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify top-level structure
        assert "passed" in data
        assert "overallScore" in data
        assert "lookaheadCheck" in data
        assert "snoopingCheck" in data
        assert "executionCheck" in data
        assert "totalViolations" in data
        assert "criticalViolations" in data
        assert "highViolations" in data
        assert "recommendations" in data
        assert "timestamp" in data
        
        # Verify lookahead check structure
        lookahead = data.get("lookaheadCheck", {})
        assert "passed" in lookahead
        assert "violations" in lookahead
        assert "fieldsChecked" in lookahead
        assert "timestampsAnalyzed" in lookahead
        assert "futureDataDetected" in lookahead
        
        # Verify snooping check structure
        snooping = data.get("snoopingCheck", {})
        assert "passed" in snooping
        assert "violations" in snooping
        assert "hypothesisCount" in snooping
        assert "adjustedSignificance" in snooping
        assert "multipleTestingPenalty" in snooping
        
        # Verify execution check structure
        execution = data.get("executionCheck", {})
        assert "passed" in execution
        assert "violations" in execution
        assert "slippageModel" in execution
        assert "liquidityModel" in execution
        assert "feeModel" in execution
        assert "realisticScore" in execution
        
        print(f"Validation response has correct structure with all expected fields")


class TestQuickCheck:
    """POST /api/guardrails/quick-check - Quick pre-flight validation tests"""
    
    def test_quick_check_with_issues(self):
        """Test quick check flags issues with zero slippage/fees"""
        config = {
            "backtestConfig": {
                "slippage_bps": 0,
                "fee_bps": 0,
                "fill_delay_ms": 20
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/guardrails/quick-check",
            json=config
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not be ready to run
        assert data.get("ready_to_run") == False
        
        # Should have issues
        issues = data.get("issues", [])
        assert len(issues) >= 2  # Zero slippage and zero fees
        
        # Check issue messages
        issues_text = " ".join(issues).lower()
        assert "slippage" in issues_text
        assert "fee" in issues_text
        
        print(f"Quick check correctly identified issues: {issues}")
    
    def test_quick_check_ready_to_run(self):
        """Test quick check returns ready when config is valid"""
        config = {
            "backtestConfig": {
                "slippage_bps": 15,
                "fee_bps": 10,
                "fill_delay_ms": 100
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/guardrails/quick-check",
            json=config
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be ready to run
        assert data.get("ready_to_run") == True
        
        # Should have no blocking issues
        assert len(data.get("issues", [])) == 0
        
        print(f"Quick check: ready_to_run={data.get('ready_to_run')}, warnings={data.get('warnings', [])}")


class TestExecutionRecommendedConfig:
    """GET /api/guardrails/execution/recommended-config - Recommended config tests"""
    
    def test_default_recommended_config(self):
        """Test default recommended config"""
        response = requests.get(f"{BASE_URL}/api/guardrails/execution/recommended-config")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have realistic defaults
        assert data.get("slippage_bps", 0) > 0
        assert data.get("fee_bps", 0) > 0
        assert data.get("fill_delay_ms", 0) > 0
        assert data.get("fill_rate", 0) > 0
        
        print(f"Default recommended config: {data}")
    
    def test_crypto_recommended_config(self):
        """Test recommended config for crypto"""
        response = requests.get(
            f"{BASE_URL}/api/guardrails/execution/recommended-config",
            params={"asset_type": "crypto", "strategy_type": "trend"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Crypto should have higher slippage than equity
        assert data.get("slippage_bps", 0) >= 10
        assert data.get("fee_bps", 0) >= 5
        
        print(f"Crypto recommended config: {data}")
    
    def test_equity_recommended_config(self):
        """Test recommended config for equity"""
        response = requests.get(
            f"{BASE_URL}/api/guardrails/execution/recommended-config",
            params={"asset_type": "equity", "strategy_type": "trend"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Equity should have lower slippage than crypto
        assert data.get("slippage_bps", 0) <= 10
        
        print(f"Equity recommended config: {data}")


class TestCostDrag:
    """POST /api/guardrails/execution/cost-drag - Cost drag estimation tests"""
    
    def test_cost_drag_calculation(self):
        """Test cost drag calculation"""
        payload = {
            "tradesPerYear": 100,
            "avgTradeSize": 10000,
            "feeBps": 10,
            "slippageBps": 10
        }
        
        response = requests.post(
            f"{BASE_URL}/api/guardrails/execution/cost-drag",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify cost drag structure
        assert "cost_per_trade_bps" in data
        assert "annual_cost_bps" in data
        assert "annual_cost_pct" in data
        assert "trades_per_year" in data
        assert "breakeven_edge_pct" in data
        assert "recommendation" in data
        
        # Verify calculations
        # Cost per trade = fee_bps + slippage_bps = 10 + 10 = 20 bps
        assert data.get("cost_per_trade_bps") == 20
        
        # Annual cost = 100 trades * 20 bps * 2 (round trip) = 4000 bps = 40%
        assert data.get("annual_cost_bps") == 4000
        assert data.get("annual_cost_pct") == 40
        
        print(f"Cost drag calculation: {data}")
    
    def test_cost_drag_defaults(self):
        """Test cost drag with default values"""
        response = requests.post(
            f"{BASE_URL}/api/guardrails/execution/cost-drag",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should use defaults (100 trades, 10 bps each)
        assert data.get("trades_per_year") == 100
        assert data.get("cost_per_trade_bps") == 20  # 10 + 10 default
        
        print(f"Cost drag with defaults: {data}")


class TestSnoopingCorrectionFactor:
    """POST /api/guardrails/snooping/correction-factor - Correction factor tests"""
    
    def test_single_test_no_correction(self):
        """Test single test needs no correction"""
        response = requests.post(
            f"{BASE_URL}/api/guardrails/snooping/correction-factor",
            json={"numTests": 1}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Single test should have factor = 1.0
        assert data.get("factor") == 1.0
        assert data.get("method") == "none"
        assert data.get("tests") == 1
        
        print(f"Single test correction: {data}")
    
    def test_multiple_tests_correction(self):
        """Test multiple tests need correction"""
        response = requests.post(
            f"{BASE_URL}/api/guardrails/snooping/correction-factor",
            json={"numTests": 100}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Multiple tests should have factor < 1.0
        assert data.get("factor", 1.0) < 1.0
        assert data.get("factor", 0) >= 0.3  # Floor at 30%
        assert data.get("tests") == 100
        assert "bonferroni" in data.get("method", "").lower()
        assert "recommendation" in data
        
        print(f"Multiple tests correction (100): {data}")
    
    def test_correction_factor_scaling(self):
        """Test correction factor scales with number of tests"""
        factors = []
        
        for num_tests in [5, 10, 50, 100]:
            response = requests.post(
                f"{BASE_URL}/api/guardrails/snooping/correction-factor",
                json={"numTests": num_tests}
            )
            assert response.status_code == 200
            factors.append((num_tests, response.json().get("factor")))
        
        # Factors should decrease as num_tests increases
        for i in range(len(factors) - 1):
            assert factors[i][1] >= factors[i+1][1], \
                f"Factor should decrease: {factors[i]} vs {factors[i+1]}"
        
        print(f"Correction factor scaling: {factors}")


class TestLookaheadQuickCheck:
    """POST /api/guardrails/lookahead/quick-check - Lookahead risk assessment tests"""
    
    def test_high_risk_fields_detected(self):
        """Test high-risk fields like 'close', 'high', 'low' are flagged"""
        # Strategy using close price (high risk)
        strategy = {
            "strategy": {
                "rules": {
                    "required": ["close", "high", "low"]
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/guardrails/lookahead/quick-check",
            json=strategy
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should flag high risk
        assert data.get("risk_level") in ["HIGH", "MEDIUM"]
        assert data.get("risk_score", 0) > 0.2
        assert data.get("high_risk_fields", 0) >= 2  # close, high, low
        
        print(f"High-risk fields detection: {data}")
    
    def test_low_risk_strategy(self):
        """Test low-risk strategy has low score"""
        # Strategy using only safe fields
        strategy = {
            "strategy": {
                "rules": {
                    "required": ["open", "prev_close"]
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/guardrails/lookahead/quick-check",
            json=strategy
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should be low risk
        assert data.get("risk_level") == "LOW"
        assert data.get("risk_score", 1) <= 0.2
        assert data.get("high_risk_fields", 1) == 0
        
        print(f"Low-risk strategy: {data}")
    
    def test_lookahead_quick_check_structure(self):
        """Test lookahead quick check response structure"""
        response = requests.post(
            f"{BASE_URL}/api/guardrails/lookahead/quick-check",
            json={"strategy": {"rules": {"required": ["rsi"]}}}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "risk_level" in data
        assert "risk_score" in data
        assert "high_risk_fields" in data
        assert "medium_risk_fields" in data
        assert "recommendation" in data
        
        print(f"Lookahead quick check structure verified: {data}")


class TestValidationIntegration:
    """Integration tests for validation workflow"""
    
    def test_full_workflow_unrealistic_to_realistic(self):
        """Test validation workflow from unrealistic to realistic config"""
        # Step 1: Quick check unrealistic config
        unrealistic = {
            "backtestConfig": {
                "slippage_bps": 0,
                "fee_bps": 0
            }
        }
        
        qc_response = requests.post(
            f"{BASE_URL}/api/guardrails/quick-check",
            json=unrealistic
        )
        assert qc_response.status_code == 200
        assert qc_response.json().get("ready_to_run") == False
        
        # Step 2: Get recommended config
        rec_response = requests.get(
            f"{BASE_URL}/api/guardrails/execution/recommended-config",
            params={"asset_type": "crypto"}
        )
        assert rec_response.status_code == 200
        recommended = rec_response.json()
        
        # Step 3: Apply recommended config and validate
        realistic = {
            "backtestConfig": {
                "slippage_bps": recommended.get("slippage_bps", 15),
                "fee_bps": recommended.get("fee_bps", 10),
                "fill_delay_ms": recommended.get("fill_delay_ms", 100),
                "slippage_model": "fixed",
                "fee_model": "fixed",
                "liquidity_model": recommended.get("liquidity_model", "adv_based")
            }
        }
        
        val_response = requests.post(
            f"{BASE_URL}/api/guardrails/validate",
            json=realistic
        )
        assert val_response.status_code == 200
        val_data = val_response.json()
        
        # Should pass with recommended config
        assert val_data.get("passed") == True
        assert val_data.get("overallScore", 0) >= 0.7
        
        print(f"Full workflow: unrealistic failed -> recommended config -> passed validation")
        print(f"Final score: {val_data.get('overallScore')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
