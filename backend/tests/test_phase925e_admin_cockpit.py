"""
Phase 9.25E: Admin Cockpit Tests
=================================

Tests for Policy-based Admin Cockpit.
"""

import pytest
import time
import json
from pathlib import Path

# Import service
from modules.admin_cockpit.service import (
    AdminCockpitService,
    PolicyManager,
    StrategyController,
    GovernanceHistory,
    PolicyType,
    ControlAction,
    ChangeType,
    DEFAULT_POLICIES,
    dashboard_to_dict,
    control_result_to_dict,
    change_to_dict
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def temp_policies_dir(tmp_path):
    """Create temporary policies directory"""
    policies_dir = tmp_path / "policies"
    policies_dir.mkdir()
    return str(policies_dir)


@pytest.fixture
def policy_manager(temp_policies_dir):
    """Create PolicyManager with temp directory"""
    return PolicyManager(temp_policies_dir)


@pytest.fixture
def strategy_controller():
    """Create StrategyController"""
    return StrategyController()


@pytest.fixture
def governance_history():
    """Create GovernanceHistory"""
    return GovernanceHistory()


@pytest.fixture
def admin_service(temp_policies_dir):
    """Create AdminCockpitService with temp directory"""
    return AdminCockpitService(temp_policies_dir)


# ============================================
# PolicyManager Tests
# ============================================

class TestPolicyManager:
    """Tests for PolicyManager"""
    
    def test_init_creates_default_policies(self, policy_manager):
        """Test that initialization creates default policies"""
        policies = policy_manager.get_policies()
        
        assert "strategy_policies" in policies
        assert "self_healing_policies" in policies
        assert "portfolio_policies" in policies
        assert "edge_guard_policies" in policies
        assert "validation_policies" in policies
        assert "risk_policies" in policies
    
    def test_get_specific_policy_type(self, policy_manager):
        """Test getting specific policy type"""
        strategy_policies = policy_manager.get_policies(PolicyType.STRATEGY)
        
        assert "max_family_exposure" in strategy_policies
        assert "promotion_criteria" in strategy_policies
    
    def test_get_policy_value_by_path(self, policy_manager):
        """Test getting specific policy value by path"""
        value = policy_manager.get_policy_value(
            PolicyType.SELF_HEALING,
            "health_thresholds.healthy"
        )
        
        assert value == 0.80
    
    def test_update_policy(self, policy_manager):
        """Test updating a policy"""
        change = policy_manager.update_policy(
            PolicyType.SELF_HEALING,
            {"health_thresholds": {"warning": 0.65}},
            author="test_user",
            reason="Testing update"
        )
        
        assert change.change_type == ChangeType.POLICY_UPDATE
        assert change.policy_type == PolicyType.SELF_HEALING
        assert change.author == "test_user"
        
        # Verify update applied
        new_value = policy_manager.get_policy_value(
            PolicyType.SELF_HEALING,
            "health_thresholds.warning"
        )
        assert new_value == 0.65
    
    def test_version_increments_on_update(self, policy_manager):
        """Test that version increments on each update"""
        initial_version = policy_manager._current_version
        
        policy_manager.update_policy(
            PolicyType.STRATEGY,
            {"max_family_exposure": 0.40}
        )
        
        assert policy_manager._current_version == initial_version + 1
    
    def test_create_version_snapshot(self, policy_manager):
        """Test creating version snapshot"""
        version = policy_manager.create_version_snapshot(
            author="admin",
            notes="Test snapshot"
        )
        
        assert version.version_number == policy_manager._current_version
        assert version.created_by == "admin"
        assert version.notes == "Test snapshot"
        assert version.is_active == True
        assert len(version.checksum) == 16
    
    def test_rollback_to_version(self, policy_manager):
        """Test rollback to previous version"""
        # Create snapshot
        snapshot = policy_manager.create_version_snapshot(author="admin")
        
        # Make some changes
        policy_manager.update_policy(
            PolicyType.SELF_HEALING,
            {"enabled": False}
        )
        
        # Rollback
        success, message = policy_manager.rollback(snapshot.version_id)
        
        assert success == True
        assert "Rolled back" in message
    
    def test_validate_policy_valid(self, policy_manager):
        """Test policy validation - valid case"""
        valid_policy = {
            "health_thresholds": {
                "healthy": 0.80,
                "warning": 0.60,
                "degraded": 0.40
            }
        }
        
        is_valid, errors = policy_manager.validate_policy(
            PolicyType.SELF_HEALING,
            valid_policy
        )
        
        assert is_valid == True
        assert len(errors) == 0
    
    def test_validate_policy_invalid(self, policy_manager):
        """Test policy validation - invalid case"""
        invalid_policy = {
            "health_thresholds": {
                "healthy": 0.50,  # Less than warning - invalid
                "warning": 0.60,
                "degraded": 0.40
            }
        }
        
        is_valid, errors = policy_manager.validate_policy(
            PolicyType.SELF_HEALING,
            invalid_policy
        )
        
        assert is_valid == False
        assert len(errors) > 0
    
    def test_get_versions(self, policy_manager):
        """Test getting version history"""
        policy_manager.create_version_snapshot(author="admin", notes="v1")
        policy_manager.update_policy(PolicyType.STRATEGY, {"max_family_exposure": 0.40})
        policy_manager.create_version_snapshot(author="admin", notes="v2")
        
        versions = policy_manager.get_versions()
        
        assert len(versions) >= 2


# ============================================
# StrategyController Tests
# ============================================

class TestStrategyController:
    """Tests for StrategyController"""
    
    def test_freeze_strategy(self, strategy_controller):
        """Test freezing a strategy"""
        result = strategy_controller.execute(
            ControlAction.FREEZE,
            "MTF_BREAKOUT"
        )
        
        assert result.success == True
        assert result.action == ControlAction.FREEZE
        assert result.new_state == "frozen"
        assert strategy_controller.is_frozen("MTF_BREAKOUT") == True
    
    def test_unfreeze_strategy(self, strategy_controller):
        """Test unfreezing a strategy"""
        # First freeze
        strategy_controller.execute(ControlAction.FREEZE, "MTF_BREAKOUT")
        
        # Then unfreeze
        result = strategy_controller.execute(ControlAction.UNFREEZE, "MTF_BREAKOUT")
        
        assert result.success == True
        assert result.action == ControlAction.UNFREEZE
        assert result.new_state == "active"
        assert strategy_controller.is_frozen("MTF_BREAKOUT") == False
    
    def test_promote_strategy(self, strategy_controller):
        """Test promoting a strategy"""
        result = strategy_controller.execute(
            ControlAction.PROMOTE,
            "TEST_STRATEGY",
            {"to_status": "APPROVED"}
        )
        
        assert result.success == True
        assert result.new_state == "APPROVED"
        
        override = strategy_controller.get_override("TEST_STRATEGY")
        assert override["lifecycle"] == "APPROVED"
    
    def test_demote_strategy(self, strategy_controller):
        """Test demoting a strategy"""
        result = strategy_controller.execute(
            ControlAction.DEMOTE,
            "TEST_STRATEGY",
            {"to_status": "WATCH", "reason": "Performance drop"}
        )
        
        assert result.success == True
        assert result.new_state == "WATCH"
    
    def test_disable_strategy(self, strategy_controller):
        """Test disabling a strategy"""
        result = strategy_controller.execute(
            ControlAction.DISABLE,
            "TEST_STRATEGY",
            {"reason": "Manual disable for review"}
        )
        
        assert result.success == True
        assert result.new_state == "disabled"
        
        override = strategy_controller.get_override("TEST_STRATEGY")
        assert override["enabled"] == False
    
    def test_enable_strategy(self, strategy_controller):
        """Test enabling a strategy"""
        strategy_controller.execute(ControlAction.DISABLE, "TEST_STRATEGY", {"reason": "test"})
        
        result = strategy_controller.execute(ControlAction.ENABLE, "TEST_STRATEGY")
        
        assert result.success == True
        assert result.new_state == "enabled"
    
    def test_set_weight(self, strategy_controller):
        """Test setting strategy weight"""
        result = strategy_controller.execute(
            ControlAction.SET_WEIGHT,
            "TEST_STRATEGY",
            {"weight": 0.75}
        )
        
        assert result.success == True
        assert "0.75" in result.new_state
        
        override = strategy_controller.get_override("TEST_STRATEGY")
        assert override["weight"] == 0.75
    
    def test_set_budget(self, strategy_controller):
        """Test setting strategy budget"""
        budget = {
            "max_exposure": 0.10,
            "max_trades": 5
        }
        
        result = strategy_controller.execute(
            ControlAction.SET_BUDGET,
            "TEST_STRATEGY",
            {"budget": budget}
        )
        
        assert result.success == True
        
        override = strategy_controller.get_override("TEST_STRATEGY")
        assert override["budget"] == budget
    
    def test_force_recovery(self, strategy_controller):
        """Test force recovery"""
        result = strategy_controller.execute(
            ControlAction.FORCE_RECOVERY,
            "TEST_STRATEGY"
        )
        
        assert result.success == True
        assert result.new_state == "recovery"
    
    def test_control_history(self, strategy_controller):
        """Test control history tracking"""
        strategy_controller.execute(ControlAction.FREEZE, "STRAT_1")
        strategy_controller.execute(ControlAction.PROMOTE, "STRAT_2", {"to_status": "APPROVED"})
        strategy_controller.execute(ControlAction.SET_WEIGHT, "STRAT_3", {"weight": 0.5})
        
        history = strategy_controller.get_control_history()
        
        assert len(history) >= 3
    
    def test_get_all_overrides(self, strategy_controller):
        """Test getting all overrides"""
        strategy_controller.execute(ControlAction.SET_WEIGHT, "STRAT_1", {"weight": 0.8})
        strategy_controller.execute(ControlAction.SET_WEIGHT, "STRAT_2", {"weight": 0.6})
        
        overrides = strategy_controller.get_all_overrides()
        
        assert "STRAT_1" in overrides
        assert "STRAT_2" in overrides


# ============================================
# GovernanceHistory Tests
# ============================================

class TestGovernanceHistory:
    """Tests for GovernanceHistory"""
    
    def test_record_change(self, governance_history):
        """Test recording a governance change"""
        change = governance_history.record(
            ChangeType.POLICY_UPDATE,
            PolicyType.SELF_HEALING,
            "admin",
            {"old": "value"},
            {"new": "value"},
            "Testing"
        )
        
        assert change.change_type == ChangeType.POLICY_UPDATE
        assert change.author == "admin"
        assert change.reason == "Testing"
    
    def test_get_history(self, governance_history):
        """Test getting history"""
        for i in range(5):
            governance_history.record(
                ChangeType.POLICY_UPDATE,
                PolicyType.STRATEGY,
                f"user_{i}",
                {}, {}, f"Change {i}"
            )
        
        history = governance_history.get_history()
        
        assert len(history) == 5
    
    def test_get_history_by_type(self, governance_history):
        """Test getting history by type"""
        governance_history.record(ChangeType.POLICY_UPDATE, None, "admin", {}, {})
        governance_history.record(ChangeType.STRATEGY_CONTROL, None, "admin", {}, {})
        governance_history.record(ChangeType.POLICY_UPDATE, None, "admin", {}, {})
        
        policy_changes = governance_history.get_history_by_type(ChangeType.POLICY_UPDATE)
        
        assert len(policy_changes) == 2
    
    def test_get_history_by_author(self, governance_history):
        """Test getting history by author"""
        governance_history.record(ChangeType.POLICY_UPDATE, None, "alice", {}, {})
        governance_history.record(ChangeType.POLICY_UPDATE, None, "bob", {}, {})
        governance_history.record(ChangeType.POLICY_UPDATE, None, "alice", {}, {})
        
        alice_changes = governance_history.get_history_by_author("alice")
        
        assert len(alice_changes) == 2
    
    def test_get_specific_change(self, governance_history):
        """Test getting specific change by ID"""
        change = governance_history.record(
            ChangeType.ROLLBACK,
            None,
            "admin",
            "v1", "v2",
            "Rolling back"
        )
        
        retrieved = governance_history.get_change(change.change_id)
        
        assert retrieved is not None
        assert retrieved.change_id == change.change_id


# ============================================
# AdminCockpitService Tests
# ============================================

class TestAdminCockpitService:
    """Tests for AdminCockpitService"""
    
    def test_get_dashboard(self, admin_service):
        """Test getting admin dashboard"""
        dashboard = admin_service.get_dashboard()
        
        assert dashboard.system_status in ["HEALTHY", "WARNING", "CRITICAL"]
        assert dashboard.active_policies_version >= 1
        assert dashboard.total_strategies >= 0
    
    def test_get_policies(self, admin_service):
        """Test getting policies"""
        policies = admin_service.get_policies()
        
        assert "strategy_policies" in policies
        assert "self_healing_policies" in policies
    
    def test_get_specific_policy_type(self, admin_service):
        """Test getting specific policy type"""
        self_healing = admin_service.get_policies("self_healing_policies")
        
        assert "enabled" in self_healing
        assert "health_thresholds" in self_healing
    
    def test_update_policy(self, admin_service):
        """Test updating policy"""
        result = admin_service.update_policy(
            "self_healing_policies",
            {"enabled": False},
            author="test",
            reason="Testing disable"
        )
        
        assert result["success"] == True
        assert "changeId" in result
    
    def test_update_policy_invalid_type(self, admin_service):
        """Test updating with invalid policy type"""
        result = admin_service.update_policy(
            "invalid_type",
            {"some": "value"},
            author="test"
        )
        
        assert result["success"] == False
        assert "error" in result
    
    def test_control_strategy(self, admin_service):
        """Test strategy control"""
        result = admin_service.control_strategy(
            "FREEZE",
            "MTF_BREAKOUT",
            author="admin"
        )
        
        assert result["success"] == True
        assert result["action"] == "FREEZE"
    
    def test_control_strategy_invalid_action(self, admin_service):
        """Test strategy control with invalid action"""
        result = admin_service.control_strategy(
            "INVALID_ACTION",
            "MTF_BREAKOUT",
            author="admin"
        )
        
        assert result["success"] == False
    
    def test_create_snapshot(self, admin_service):
        """Test creating policy snapshot"""
        result = admin_service.create_snapshot(
            author="admin",
            notes="Test snapshot"
        )
        
        assert "versionId" in result
        assert "checksum" in result
    
    def test_rollback(self, admin_service):
        """Test rollback"""
        # Create a snapshot first
        snapshot = admin_service.create_snapshot(author="admin")
        version_id = snapshot["versionId"]
        
        # Make changes
        admin_service.update_policy(
            "self_healing_policies",
            {"mode": "MANUAL"}
        )
        
        # Rollback
        result = admin_service.rollback(version_id, author="admin")
        
        assert result["success"] == True
    
    def test_get_governance_history(self, admin_service):
        """Test getting governance history"""
        # Make some changes
        admin_service.update_policy("strategy_policies", {"max_family_exposure": 0.40})
        admin_service.control_strategy("FREEZE", "TEST_STRAT")
        
        history = admin_service.get_governance_history()
        
        assert len(history) >= 2
    
    def test_get_health(self, admin_service):
        """Test getting service health"""
        health = admin_service.get_health()
        
        assert health["enabled"] == True
        assert health["status"] == "ok"
        assert "components" in health


# ============================================
# Serialization Tests
# ============================================

class TestSerialization:
    """Tests for serialization functions"""
    
    def test_dashboard_to_dict(self, admin_service):
        """Test dashboard serialization"""
        dashboard = admin_service.get_dashboard()
        result = dashboard_to_dict(dashboard)
        
        assert "systemStatus" in result
        assert "strategies" in result
        assert "selfHealing" in result
        assert "portfolio" in result
        assert "governance" in result
    
    def test_control_result_to_dict(self, strategy_controller):
        """Test control result serialization"""
        result = strategy_controller.execute(ControlAction.FREEZE, "TEST")
        serialized = control_result_to_dict(result)
        
        assert "success" in serialized
        assert "action" in serialized
        assert serialized["action"] == "FREEZE"
    
    def test_change_to_dict(self, governance_history):
        """Test change serialization"""
        change = governance_history.record(
            ChangeType.POLICY_UPDATE,
            PolicyType.STRATEGY,
            "admin",
            {}, {},
            "Test"
        )
        serialized = change_to_dict(change)
        
        assert "changeId" in serialized
        assert "changeType" in serialized
        assert serialized["changeType"] == "POLICY_UPDATE"


# ============================================
# Default Policies Tests
# ============================================

class TestDefaultPolicies:
    """Tests for default policy values"""
    
    def test_strategy_policies_structure(self):
        """Test strategy policies have correct structure"""
        strategy = DEFAULT_POLICIES["strategy_policies"]
        
        assert "max_family_exposure" in strategy
        assert "promotion_criteria" in strategy
        assert "demotion_criteria" in strategy
        assert "family_budgets" in strategy
        
        # Check structure exists, values may vary
        assert isinstance(strategy["max_family_exposure"], float)
    
    def test_self_healing_policies_structure(self):
        """Test self-healing policies have correct structure"""
        healing = DEFAULT_POLICIES["self_healing_policies"]
        
        assert "enabled" in healing  # Just check key exists
        assert "health_thresholds" in healing
        assert "weight_adjustment" in healing
        assert "recovery_rules" in healing
        
        # Check structure has required keys
        thresholds = healing["health_thresholds"]
        assert "healthy" in thresholds
        assert "warning" in thresholds
        assert "degraded" in thresholds
    
    def test_portfolio_policies_structure(self):
        """Test portfolio policies have correct structure"""
        portfolio = DEFAULT_POLICIES["portfolio_policies"]
        
        assert "exposure_limits" in portfolio
        assert "correlation_limits" in portfolio
        assert "kill_switch" in portfolio
        
        limits = portfolio["exposure_limits"]
        assert limits["max_gross"] == 1.5
    
    def test_edge_guard_policies_structure(self):
        """Test edge guard policies have correct structure"""
        edge = DEFAULT_POLICIES["edge_guard_policies"]
        
        assert "decay_thresholds" in edge
        assert "overfit_thresholds" in edge
        assert "drift_thresholds" in edge
    
    def test_validation_policies_structure(self):
        """Test validation policies have correct structure"""
        validation = DEFAULT_POLICIES["validation_policies"]
        
        assert "release_criteria" in validation
        assert "regression_thresholds" in validation
        
        criteria = validation["release_criteria"]
        assert criteria["min_pf"] == 1.5
        assert criteria["guardrails_required"] == True
    
    def test_risk_policies_structure(self):
        """Test risk policies have correct structure"""
        risk = DEFAULT_POLICIES["risk_policies"]
        
        assert risk["max_portfolio_risk"] == 0.02
        assert risk["max_single_trade_risk"] == 0.01
        assert "position_sizing" in risk


# ============================================
# Integration Tests
# ============================================

class TestIntegration:
    """Integration tests for Admin Cockpit"""
    
    def test_full_policy_update_flow(self, temp_policies_dir):
        """Test full policy update flow"""
        # Use fresh service instance
        admin_service = AdminCockpitService(temp_policies_dir)
        
        # 1. Create snapshot
        snapshot = admin_service.create_snapshot(author="admin", notes="Before update")
        
        # 2. Update policy
        update_result = admin_service.update_policy(
            "self_healing_policies",
            {
                "health_thresholds": {"warning": 0.65},
                "mode": "MANUAL"
            },
            author="admin",
            reason="Adjusting thresholds"
        )
        
        assert update_result["success"] == True
        
        # 3. Verify update
        policies = admin_service.get_policies("self_healing_policies")
        assert policies["health_thresholds"]["warning"] == 0.65
        assert policies["mode"] == "MANUAL"
        
        # 4. Check history
        history = admin_service.get_governance_history()
        assert len(history) >= 1
        assert history[-1]["changeType"] == "POLICY_UPDATE"
    
    def test_full_strategy_control_flow(self, admin_service):
        """Test full strategy control flow"""
        strategy_id = "TEST_STRATEGY"
        
        # 1. Freeze
        freeze_result = admin_service.control_strategy("FREEZE", strategy_id)
        assert freeze_result["success"] == True
        
        # 2. Set weight
        weight_result = admin_service.control_strategy(
            "SET_WEIGHT",
            strategy_id,
            {"weight": 0.5}
        )
        assert weight_result["success"] == True
        
        # 3. Demote
        demote_result = admin_service.control_strategy(
            "DEMOTE",
            strategy_id,
            {"to_status": "WATCH", "reason": "Performance drop"}
        )
        assert demote_result["success"] == True
        
        # 4. Unfreeze
        unfreeze_result = admin_service.control_strategy("UNFREEZE", strategy_id)
        assert unfreeze_result["success"] == True
        
        # 5. Check override
        override = admin_service.strategy_controller.get_override(strategy_id)
        assert override is not None
        assert override["weight"] == 0.5
    
    def test_rollback_restores_state(self, temp_policies_dir):
        """Test that rollback restores previous state"""
        # Use fresh service instance
        admin_service = AdminCockpitService(temp_policies_dir)
        
        # 1. Get initial state
        initial_policies = admin_service.get_policies("self_healing_policies")
        initial_mode = initial_policies.get("mode", "AUTO")
        
        # 2. Create snapshot
        snapshot = admin_service.create_snapshot(author="admin")
        
        # 3. Make changes
        admin_service.update_policy("self_healing_policies", {"mode": "DISABLED"})
        
        # 4. Verify change
        changed = admin_service.get_policies("self_healing_policies")
        assert changed["mode"] == "DISABLED"
        
        # 5. Rollback
        admin_service.rollback(snapshot["versionId"])
        
        # 6. Verify rollback
        restored = admin_service.get_policies("self_healing_policies")
        assert restored["mode"] == initial_mode
