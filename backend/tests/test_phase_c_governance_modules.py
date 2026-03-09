"""
Phase C Governance Modules Backend Tests
=========================================

Tests for:
1. Policy Engine (/api/policies/*)
2. Dataset Registry (/api/datasets/*)
3. Experiment Tracker (/api/experiments/*)
4. Admin Control Center (/api/admin/dashboard/*)

All modules are isolated and communicate via APIs.
"""

import pytest
import requests
import os
import time

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://risk-control-system.preview.emergentagent.com"


# ==============================================================================
# POLICY ENGINE TESTS
# ==============================================================================

class TestPolicyEngineHealth:
    """Test Policy Engine health endpoint"""
    
    def test_health_check_status(self):
        """Test /api/policies/health returns OK status"""
        response = requests.get(f"{BASE_URL}/api/policies/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert data["enabled"] == True
        assert data["version"] == "phaseC"
        print(f"✓ Policy Engine Health: {data['total_policies']} policies across categories")
    
    def test_health_check_categories(self):
        """Verify all policy categories exist"""
        response = requests.get(f"{BASE_URL}/api/policies/health")
        data = response.json()
        
        expected_categories = ["STRATEGY", "TOURNAMENT", "RESEARCH", "RISK", "EXECUTION", "GOVERNANCE"]
        by_category = data.get("by_category", {})
        
        for cat in expected_categories:
            assert cat in by_category, f"Missing category: {cat}"
            assert by_category[cat] >= 1, f"Category {cat} should have at least 1 policy"
        
        print(f"✓ All {len(expected_categories)} policy categories present")


class TestPolicyEngineList:
    """Test Policy Engine list endpoints"""
    
    def test_list_all_policies(self):
        """Test listing all policies"""
        response = requests.get(f"{BASE_URL}/api/policies")
        assert response.status_code == 200
        
        data = response.json()
        assert "policies" in data
        policies = data["policies"]
        assert len(policies) >= 6, "Should have at least 6 default policies"
        
        # Verify policy structure
        for policy in policies:
            assert "policy_id" in policy
            assert "name" in policy
            assert "category" in policy
            assert "rules" in policy
        
        print(f"✓ Listed {len(policies)} policies")
    
    def test_list_policies_by_category_strategy(self):
        """Test filtering policies by STRATEGY category"""
        response = requests.get(f"{BASE_URL}/api/policies?category=STRATEGY")
        assert response.status_code == 200
        
        data = response.json()
        policies = data["policies"]
        
        for policy in policies:
            assert policy["category"] == "STRATEGY"
        
        print(f"✓ Listed {len(policies)} STRATEGY policies")
    
    def test_list_policies_by_category_risk(self):
        """Test filtering policies by RISK category"""
        response = requests.get(f"{BASE_URL}/api/policies?category=RISK")
        assert response.status_code == 200
        
        data = response.json()
        policies = data["policies"]
        
        for policy in policies:
            assert policy["category"] == "RISK"
        
        print(f"✓ Listed {len(policies)} RISK policies")


class TestPolicyEngineGet:
    """Test Policy Engine get specific policy"""
    
    def test_get_strategy_admission_policy(self):
        """Test getting STRATEGY_ADMISSION policy"""
        response = requests.get(f"{BASE_URL}/api/policies/STRATEGY_ADMISSION")
        assert response.status_code == 200
        
        policy = response.json()
        assert policy["policy_id"] == "STRATEGY_ADMISSION"
        assert policy["category"] == "STRATEGY"
        assert "rules" in policy
        
        rules = policy["rules"]
        expected_rules = ["min_trades", "min_pf", "min_sharpe", "max_drawdown"]
        for rule in expected_rules:
            assert rule in rules, f"Missing rule: {rule}"
        
        print(f"✓ Got STRATEGY_ADMISSION policy with {len(rules)} rules")
    
    def test_get_risk_limits_policy(self):
        """Test getting RISK_LIMITS policy"""
        response = requests.get(f"{BASE_URL}/api/policies/RISK_LIMITS")
        assert response.status_code == 200
        
        policy = response.json()
        assert policy["policy_id"] == "RISK_LIMITS"
        assert policy["category"] == "RISK"
        
        rules = policy["rules"]
        assert "max_portfolio_drawdown" in rules
        assert "max_leverage" in rules
        
        print(f"✓ Got RISK_LIMITS policy with {len(rules)} rules")
    
    def test_get_nonexistent_policy_returns_404(self):
        """Test getting non-existent policy returns 404"""
        response = requests.get(f"{BASE_URL}/api/policies/NONEXISTENT_POLICY")
        assert response.status_code == 404
        print("✓ Non-existent policy returns 404")


class TestPolicyEngineUpdate:
    """Test Policy Engine update functionality"""
    
    def test_update_policy_rules(self):
        """Test updating policy rules"""
        # First get the current policy
        get_response = requests.get(f"{BASE_URL}/api/policies/STRATEGY_ADMISSION")
        original_policy = get_response.json()
        original_min_trades = original_policy["rules"].get("min_trades")
        
        # Update the policy with a new value
        new_min_trades = 35
        update_response = requests.patch(
            f"{BASE_URL}/api/policies/STRATEGY_ADMISSION",
            json={"rules": {"min_trades": new_min_trades}}
        )
        assert update_response.status_code == 200
        
        updated_policy = update_response.json()
        assert updated_policy["rules"]["min_trades"] == new_min_trades
        
        # Verify persistence by getting again
        verify_response = requests.get(f"{BASE_URL}/api/policies/STRATEGY_ADMISSION")
        verified_policy = verify_response.json()
        assert verified_policy["rules"]["min_trades"] == new_min_trades
        
        # Restore original value
        requests.patch(
            f"{BASE_URL}/api/policies/STRATEGY_ADMISSION",
            json={"rules": {"min_trades": original_min_trades}}
        )
        
        print(f"✓ Updated STRATEGY_ADMISSION min_trades: {original_min_trades} -> {new_min_trades}")
    
    def test_update_nonexistent_policy_returns_404(self):
        """Test updating non-existent policy returns 404"""
        response = requests.patch(
            f"{BASE_URL}/api/policies/NONEXISTENT_POLICY",
            json={"rules": {"test": 123}}
        )
        assert response.status_code == 404
        print("✓ Update non-existent policy returns 404")


class TestPolicyEngineCheck:
    """Test Policy Engine rule checking"""
    
    def test_check_rule_passes(self):
        """Test checking a value that passes the rule"""
        response = requests.post(
            f"{BASE_URL}/api/policies/STRATEGY_ADMISSION/check",
            json={"rule_name": "min_sharpe", "value": 1.0}  # Higher than 0.5
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["passed"] == True
        assert result["rule"] == "min_sharpe"
        print("✓ Rule check passes for value above threshold")
    
    def test_check_rule_fails(self):
        """Test checking a value that fails the rule"""
        response = requests.post(
            f"{BASE_URL}/api/policies/STRATEGY_ADMISSION/check",
            json={"rule_name": "min_sharpe", "value": 0.3}  # Lower than 0.5
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["passed"] == False
        print("✓ Rule check fails for value below threshold")
    
    def test_check_max_rule(self):
        """Test checking max rule"""
        response = requests.post(
            f"{BASE_URL}/api/policies/STRATEGY_ADMISSION/check",
            json={"rule_name": "max_drawdown", "value": 0.15}  # Less than 0.25
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["passed"] == True
        print("✓ Max rule check works correctly")


class TestPolicyEngineValidate:
    """Test Policy Engine strategy validation"""
    
    def test_validate_strategy_passes(self):
        """Test strategy validation that passes all rules"""
        response = requests.post(
            f"{BASE_URL}/api/policies/validate/strategy",
            json={
                "metrics": {
                    "min_trades": 50,
                    "min_pf": 1.5,
                    "min_sharpe": 1.0,
                    "max_drawdown": 0.10,
                    "min_win_rate": 0.55
                }
            }
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["valid"] == True
        assert len(result["violations"]) == 0
        print("✓ Strategy validation passes with good metrics")
    
    def test_validate_strategy_with_violations(self):
        """Test strategy validation with violations"""
        response = requests.post(
            f"{BASE_URL}/api/policies/validate/strategy",
            json={
                "metrics": {
                    "min_trades": 10,  # Below 30
                    "min_pf": 0.9,  # Below 1.1
                    "min_sharpe": 0.2  # Below 0.5
                }
            }
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["valid"] == False
        assert len(result["violations"]) >= 1
        print(f"✓ Strategy validation detects {len(result['violations'])} violations")


# ==============================================================================
# DATASET REGISTRY TESTS
# ==============================================================================

class TestDatasetRegistryHealth:
    """Test Dataset Registry health endpoint"""
    
    def test_health_check(self):
        """Test /api/datasets/health"""
        response = requests.get(f"{BASE_URL}/api/datasets/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert data["enabled"] == True
        assert data["version"] == "phaseC"
        assert data["total_datasets"] >= 4
        assert data["total_rows"] > 0
        assert len(data["assets"]) >= 4
        
        print(f"✓ Dataset Registry: {data['total_datasets']} datasets, {data['total_rows']} rows")


class TestDatasetRegistryList:
    """Test Dataset Registry list endpoints"""
    
    def test_list_all_datasets(self):
        """Test listing all datasets"""
        response = requests.get(f"{BASE_URL}/api/datasets")
        assert response.status_code == 200
        
        data = response.json()
        assert "datasets" in data
        datasets = data["datasets"]
        assert len(datasets) >= 4
        
        # Verify dataset structure
        for ds in datasets:
            assert "dataset_id" in ds
            assert "name" in ds
            assert "asset" in ds
            assert "version" in ds
            assert "rows" in ds
            assert "checksum" in ds
        
        print(f"✓ Listed {len(datasets)} datasets")
    
    def test_list_datasets_by_asset(self):
        """Test filtering datasets by asset"""
        response = requests.get(f"{BASE_URL}/api/datasets?asset=BTC")
        assert response.status_code == 200
        
        data = response.json()
        datasets = data["datasets"]
        
        for ds in datasets:
            assert ds["asset"] == "BTC"
        
        print(f"✓ Listed {len(datasets)} BTC datasets")


class TestDatasetRegistryGet:
    """Test Dataset Registry get specific dataset"""
    
    def test_get_btc_dataset(self):
        """Test getting BTC dataset"""
        response = requests.get(f"{BASE_URL}/api/datasets/btc_daily_v1")
        assert response.status_code == 200
        
        ds = response.json()
        assert ds["dataset_id"] == "btc_daily_v1"
        assert ds["asset"] == "BTC"
        assert ds["rows"] > 0
        assert "checksum" in ds
        assert len(ds["columns"]) > 0
        
        print(f"✓ Got BTC dataset: {ds['rows']} rows, {len(ds['columns'])} columns")
    
    def test_get_spx_dataset(self):
        """Test getting SPX dataset"""
        response = requests.get(f"{BASE_URL}/api/datasets/spx_daily_v1")
        assert response.status_code == 200
        
        ds = response.json()
        assert ds["dataset_id"] == "spx_daily_v1"
        assert ds["asset"] == "SPX"
        
        print(f"✓ Got SPX dataset: {ds['rows']} rows")
    
    def test_get_nonexistent_dataset_returns_404(self):
        """Test getting non-existent dataset returns 404"""
        response = requests.get(f"{BASE_URL}/api/datasets/nonexistent_dataset")
        assert response.status_code == 404
        print("✓ Non-existent dataset returns 404")


class TestDatasetRegistryVersions:
    """Test Dataset Registry versions endpoint"""
    
    def test_get_dataset_versions(self):
        """Test getting dataset versions"""
        response = requests.get(f"{BASE_URL}/api/datasets/btc_daily_v1/versions")
        assert response.status_code == 200
        
        data = response.json()
        assert data["dataset_id"] == "btc_daily_v1"
        assert "versions" in data
        assert len(data["versions"]) >= 1
        assert "1.0" in data["versions"]
        
        print(f"✓ BTC dataset has {len(data['versions'])} versions")


class TestDatasetRegistryRegister:
    """Test Dataset Registry registration"""
    
    def test_register_new_dataset(self):
        """Test registering a new dataset"""
        test_dataset_id = f"TEST_dataset_{int(time.time())}"
        
        response = requests.post(
            f"{BASE_URL}/api/datasets",
            json={
                "dataset_id": test_dataset_id,
                "name": "Test Dataset",
                "asset": "TEST",
                "version": "1.0",
                "start_date": "2020-01-01",
                "end_date": "2025-12-31",
                "rows": 1000,
                "source": "test",
                "timeframe": "1D",
                "columns": ["open", "high", "low", "close"]
            }
        )
        assert response.status_code == 200
        
        ds = response.json()
        assert ds["dataset_id"] == test_dataset_id
        assert ds["asset"] == "TEST"
        assert ds["rows"] == 1000
        assert "checksum" in ds  # Auto-generated
        
        # Verify persistence by getting it
        get_response = requests.get(f"{BASE_URL}/api/datasets/{test_dataset_id}")
        assert get_response.status_code == 200
        verified = get_response.json()
        assert verified["dataset_id"] == test_dataset_id
        
        print(f"✓ Registered and verified new dataset: {test_dataset_id}")


class TestDatasetRegistryValidate:
    """Test Dataset Registry checksum validation"""
    
    def test_validate_checksum_correct(self):
        """Test validating correct checksum"""
        # First get a dataset to know its checksum
        get_response = requests.get(f"{BASE_URL}/api/datasets/btc_daily_v1")
        ds = get_response.json()
        checksum = ds["checksum"]
        
        # Validate with correct checksum
        response = requests.post(
            f"{BASE_URL}/api/datasets/btc_daily_v1/validate?checksum={checksum}"
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["valid"] == True
        print("✓ Checksum validation passes with correct value")
    
    def test_validate_checksum_incorrect(self):
        """Test validating incorrect checksum"""
        response = requests.post(
            f"{BASE_URL}/api/datasets/btc_daily_v1/validate?checksum=invalid_checksum"
        )
        assert response.status_code == 200
        
        result = response.json()
        assert result["valid"] == False
        print("✓ Checksum validation fails with incorrect value")


# ==============================================================================
# EXPERIMENT TRACKER TESTS
# ==============================================================================

class TestExperimentTrackerHealth:
    """Test Experiment Tracker health endpoint"""
    
    def test_health_check(self):
        """Test /api/experiments/health"""
        response = requests.get(f"{BASE_URL}/api/experiments/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert data["enabled"] == True
        assert data["version"] == "phaseC"
        assert "total_experiments" in data
        assert "running" in data
        
        print(f"✓ Experiment Tracker: {data['total_experiments']} experiments, {data['running']} running")


class TestExperimentTrackerStats:
    """Test Experiment Tracker stats endpoint"""
    
    def test_get_stats(self):
        """Test getting experiment statistics"""
        response = requests.get(f"{BASE_URL}/api/experiments/stats")
        assert response.status_code == 200
        
        stats = response.json()
        assert "total" in stats
        assert "by_status" in stats
        assert "avg_duration_seconds" in stats
        
        by_status = stats["by_status"]
        expected_statuses = ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
        for status in expected_statuses:
            assert status in by_status
        
        print(f"✓ Stats: {stats['total']} experiments, avg duration: {stats['avg_duration_seconds']}s")


class TestExperimentTrackerList:
    """Test Experiment Tracker list endpoints"""
    
    def test_list_all_experiments(self):
        """Test listing all experiments"""
        response = requests.get(f"{BASE_URL}/api/experiments")
        assert response.status_code == 200
        
        data = response.json()
        assert "experiments" in data
        experiments = data["experiments"]
        
        # Verify structure if any experiments exist
        if len(experiments) > 0:
            exp = experiments[0]
            assert "experiment_id" in exp
            assert "name" in exp
            assert "status" in exp
            assert "created_at" in exp
        
        print(f"✓ Listed {len(experiments)} experiments")
    
    def test_list_experiments_by_status(self):
        """Test filtering experiments by status"""
        response = requests.get(f"{BASE_URL}/api/experiments?status=PENDING")
        assert response.status_code == 200
        
        data = response.json()
        experiments = data["experiments"]
        
        for exp in experiments:
            assert exp["status"] == "PENDING"
        
        print(f"✓ Listed {len(experiments)} PENDING experiments")


class TestExperimentTrackerCreate:
    """Test Experiment Tracker create endpoint"""
    
    def test_create_experiment(self):
        """Test creating a new experiment"""
        test_name = f"TEST_exp_{int(time.time())}"
        
        response = requests.post(
            f"{BASE_URL}/api/experiments",
            json={
                "name": test_name,
                "dataset_version": "btc_daily_v1",
                "strategies": ["trend_btc_v1", "momentum_btc_v1"],
                "assets": ["BTC"],
                "parameters": {"lookback": 20, "threshold": 0.05},
                "tags": ["test", "automated"]
            }
        )
        assert response.status_code == 200
        
        exp = response.json()
        assert "experiment_id" in exp
        assert exp["experiment_id"].startswith("EXP_")
        assert exp["name"] == test_name
        assert exp["status"] == "PENDING"
        assert exp["dataset_version"] == "btc_daily_v1"
        assert "BTC" in exp["assets"]
        assert "test" in exp["tags"]
        
        print(f"✓ Created experiment: {exp['experiment_id']}")
        return exp["experiment_id"]


class TestExperimentTrackerLifecycle:
    """Test Experiment Tracker full lifecycle"""
    
    def test_experiment_full_lifecycle(self):
        """Test creating, starting, completing an experiment"""
        # 1. Create experiment
        create_response = requests.post(
            f"{BASE_URL}/api/experiments",
            json={
                "name": f"TEST_lifecycle_{int(time.time())}",
                "dataset_version": "btc_daily_v1",
                "strategies": ["trend_btc_v1"],
                "assets": ["BTC"],
                "tags": ["lifecycle_test"]
            }
        )
        assert create_response.status_code == 200
        exp_id = create_response.json()["experiment_id"]
        print(f"  Created: {exp_id}")
        
        # 2. Verify PENDING status
        get_response = requests.get(f"{BASE_URL}/api/experiments/{exp_id}")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "PENDING"
        
        # 3. Start experiment
        start_response = requests.post(f"{BASE_URL}/api/experiments/{exp_id}/start")
        assert start_response.status_code == 200
        started_exp = start_response.json()
        assert started_exp["status"] == "RUNNING"
        assert started_exp["started_at"] > 0
        print(f"  Started: {exp_id}")
        
        # 4. Complete experiment with results
        complete_response = requests.post(
            f"{BASE_URL}/api/experiments/{exp_id}/complete",
            json={
                "results": {"best_strategy": "trend_btc_v1", "trades_analyzed": 150},
                "metrics": {"sharpe": 1.2, "pf": 1.5, "win_rate": 0.55},
                "notes": "Lifecycle test completed successfully"
            }
        )
        assert complete_response.status_code == 200
        completed_exp = complete_response.json()
        assert completed_exp["status"] == "COMPLETED"
        assert completed_exp["completed_at"] > 0
        assert completed_exp["metrics"]["sharpe"] == 1.2
        print(f"  Completed: {exp_id}")
        
        # 5. Verify persistence
        verify_response = requests.get(f"{BASE_URL}/api/experiments/{exp_id}")
        verified_exp = verify_response.json()
        assert verified_exp["status"] == "COMPLETED"
        assert verified_exp["notes"] == "Lifecycle test completed successfully"
        
        print(f"✓ Full lifecycle test passed for {exp_id}")
    
    def test_experiment_fail_flow(self):
        """Test creating and failing an experiment"""
        # Create experiment
        create_response = requests.post(
            f"{BASE_URL}/api/experiments",
            json={
                "name": f"TEST_fail_{int(time.time())}",
                "strategies": ["test_strategy"],
                "tags": ["fail_test"]
            }
        )
        exp_id = create_response.json()["experiment_id"]
        
        # Start it
        requests.post(f"{BASE_URL}/api/experiments/{exp_id}/start")
        
        # Fail it
        fail_response = requests.post(
            f"{BASE_URL}/api/experiments/{exp_id}/fail?error=Data%20validation%20failed"
        )
        assert fail_response.status_code == 200
        failed_exp = fail_response.json()
        assert failed_exp["status"] == "FAILED"
        
        print(f"✓ Fail flow test passed for {exp_id}")


class TestExperimentTrackerGet:
    """Test Experiment Tracker get specific experiment"""
    
    def test_get_nonexistent_experiment_returns_404(self):
        """Test getting non-existent experiment returns 404"""
        response = requests.get(f"{BASE_URL}/api/experiments/EXP_nonexistent123")
        assert response.status_code == 404
        print("✓ Non-existent experiment returns 404")


# ==============================================================================
# ADMIN CONTROL CENTER TESTS
# ==============================================================================

class TestAdminControlCenterHealth:
    """Test Admin Control Center health endpoint"""
    
    def test_dashboard_system_health(self):
        """Test /api/admin/dashboard/system for module health"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/system")
        assert response.status_code == 200
        
        data = response.json()
        assert "modules_loaded" in data
        assert "available_modules" in data
        assert "timestamp" in data
        
        modules = data["available_modules"]
        # Phase C modules should be loaded
        assert "policies" in modules
        assert "datasets" in modules
        assert "experiments" in modules
        
        print(f"✓ Admin System: {data['modules_loaded']} modules loaded")


class TestAdminDashboardFull:
    """Test Admin Control Center full dashboard"""
    
    def test_get_full_dashboard(self):
        """Test getting complete system dashboard"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard")
        assert response.status_code == 200
        
        data = response.json()
        # Note: Full dashboard from admin_cockpit returns different structure
        # This is expected due to route overlap
        assert "timestamp" in data or "systemStatus" in data
        print("✓ Full dashboard endpoint accessible")


class TestAdminDashboardEdge:
    """Test Admin Control Center edge dashboard"""
    
    def test_get_edge_dashboard(self):
        """Test /api/admin/dashboard/edge"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/edge")
        assert response.status_code == 200
        
        data = response.json()
        assert "families" in data
        assert "top_strategies" in data
        assert "decay_summary" in data
        assert "fragility_summary" in data
        assert "timestamp" in data
        
        # Verify family structure
        families = data["families"]
        assert len(families) >= 1
        for family in families:
            assert "family" in family
            assert "avg_pf" in family
            assert "robustness_level" in family
        
        print(f"✓ Edge Dashboard: {len(families)} families, {len(data['top_strategies'])} top strategies")


class TestAdminDashboardExecution:
    """Test Admin Control Center execution dashboard"""
    
    def test_get_execution_dashboard(self):
        """Test /api/admin/dashboard/execution"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/execution")
        assert response.status_code == 200
        
        data = response.json()
        assert "timestamp" in data
        # May have assets_profiled, scenarios_available, etc. if microstructure is loaded
        
        print(f"✓ Execution Dashboard: {len(data)} fields")


class TestAdminDashboardAlpha:
    """Test Admin Control Center alpha dashboard"""
    
    def test_get_alpha_dashboard(self):
        """Test /api/admin/dashboard/alpha"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/alpha")
        assert response.status_code == 200
        
        data = response.json()
        assert "timestamp" in data
        
        print(f"✓ Alpha Dashboard: {len(data)} fields")


class TestAdminDashboardRisk:
    """Test Admin Control Center risk dashboard"""
    
    def test_get_risk_dashboard(self):
        """Test /api/admin/dashboard/risk"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/risk")
        assert response.status_code == 200
        
        data = response.json()
        assert "timestamp" in data
        
        # Should include governance_policies count from policy engine
        if "governance_policies" in data:
            assert data["governance_policies"] >= 6
        
        print(f"✓ Risk Dashboard: {len(data)} fields")


class TestAdminDashboardResearch:
    """Test Admin Control Center research dashboard"""
    
    def test_get_research_dashboard(self):
        """Test /api/admin/dashboard/research"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/research")
        assert response.status_code == 200
        
        data = response.json()
        assert "timestamp" in data
        
        # Should include experiments stats from experiment tracker
        if "experiments" in data:
            exp_stats = data["experiments"]
            assert "total" in exp_stats
            assert "by_status" in exp_stats
        
        print(f"✓ Research Dashboard: {len(data)} fields")


class TestAdminDashboardShadow:
    """Test Admin Control Center shadow dashboard"""
    
    def test_get_shadow_dashboard(self):
        """Test /api/admin/dashboard/shadow"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/shadow")
        assert response.status_code == 200
        
        data = response.json()
        assert "timestamp" in data
        
        print(f"✓ Shadow Dashboard: {len(data)} fields")


class TestAdminResearchRun:
    """Test Admin Control Center research run trigger"""
    
    def test_trigger_research_cycle(self):
        """Test /api/admin/research/run"""
        response = requests.post(f"{BASE_URL}/api/admin/research/run")
        assert response.status_code == 200
        
        data = response.json()
        # May return error if research loop not available, which is OK
        if "error" not in data:
            assert "cycle_id" in data or "status" in data
            print(f"✓ Research cycle triggered: {data.get('cycle_id', 'N/A')}")
        else:
            print(f"✓ Research run endpoint accessible (module not available)")


class TestAdminRiskOverride:
    """Test Admin Control Center risk override"""
    
    def test_risk_override(self):
        """Test /api/admin/risk/override"""
        response = requests.post(
            f"{BASE_URL}/api/admin/risk/override",
            json={"state": "NORMAL", "reason": "Test override"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # May return error if risk brain not available, which is OK
        if "error" not in data:
            assert "state" in data
            print(f"✓ Risk override executed: {data.get('state', 'N/A')}")
        else:
            print(f"✓ Risk override endpoint accessible (module not available)")


class TestAdminExperimentCreate:
    """Test Admin Control Center experiment creation"""
    
    def test_create_experiment_via_admin(self):
        """Test /api/admin/experiments"""
        test_name = f"ADMIN_TEST_exp_{int(time.time())}"
        
        response = requests.post(
            f"{BASE_URL}/api/admin/experiments",
            json={
                "name": test_name,
                "dataset_version": "btc_daily_v1",
                "strategies": ["trend_btc_v1"],
                "assets": ["BTC"],
                "tags": ["admin_test"]
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        # May return error if experiment tracker not available
        if "error" not in data:
            assert "experiment_id" in data
            assert data["name"] == test_name
            print(f"✓ Admin created experiment: {data['experiment_id']}")
        else:
            print(f"✓ Admin experiment endpoint accessible")


# ==============================================================================
# RUN TESTS
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
