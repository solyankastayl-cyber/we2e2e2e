"""
Test Phase 9.25D: Validation Governance
"""
import pytest
import sys
sys.path.insert(0, '/app/backend')

from modules.validation_governance.service import (
    ValidationGovernanceService,
    ValidationRegistry,
    BenchmarkComparator,
    ReleaseGateManager,
    ValidationStage,
    ValidationStatus,
    ReleaseGateStatus,
    validation_run_to_dict,
    comparison_to_dict,
    release_gate_to_dict
)


class TestValidationRegistry:
    """Test Validation Registry"""
    
    def setup_method(self):
        self.registry = ValidationRegistry()
    
    def test_get_all_runs(self):
        """Test getting all runs"""
        runs = self.registry.get_all_runs()
        
        assert len(runs) == 5  # Default runs
    
    def test_get_run(self):
        """Test getting specific run"""
        run = self.registry.get_run("run_phase92_quant_report")
        
        assert run is not None
        assert run.stage == ValidationStage.APPROVAL
    
    def test_get_runs_by_stage(self):
        """Test filtering by stage"""
        validation_runs = self.registry.get_runs_by_stage(ValidationStage.VALIDATION)
        
        assert len(validation_runs) >= 1
    
    def test_get_baseline(self):
        """Test getting baseline"""
        baseline = self.registry.get_baseline()
        
        assert baseline is not None
        assert baseline.run_id == "run_phase90_cross_asset"


class TestBenchmarkComparator:
    """Test Benchmark Comparator"""
    
    def setup_method(self):
        self.comparator = BenchmarkComparator()
    
    def test_compare_runs(self):
        """Test comparing runs"""
        comparison = self.comparator.compare("run_phase92_quant_report")
        
        assert comparison is not None
        assert comparison.run_id == "run_phase92_quant_report"
        assert comparison.summary != ""
    
    def test_comparison_verdict(self):
        """Test comparison verdict"""
        comparison = self.comparator.compare("run_phase92_quant_report")
        
        # One of these should be True
        assert comparison.is_improvement or comparison.is_regression or comparison.is_stable


class TestReleaseGateManager:
    """Test Release Gate Manager"""
    
    def setup_method(self):
        self.manager = ReleaseGateManager()
    
    def test_create_gate(self):
        """Test creating gate"""
        gate = self.manager.create_gate("Test Release")
        
        assert gate.gate_id.startswith("gate_")
        assert gate.status == ReleaseGateStatus.NOT_STARTED
    
    def test_check_release_approved(self):
        """Test release check that passes"""
        gate = self.manager.check_release("run_phase92_quant_report")
        
        assert gate.status == ReleaseGateStatus.APPROVED
        assert gate.cross_asset_passed is True
    
    def test_check_release_not_found(self):
        """Test release check for non-existent run"""
        gate = self.manager.check_release("non_existent_run")
        
        assert gate.status == ReleaseGateStatus.BLOCKED


class TestValidationGovernanceService:
    """Test Validation Governance Service"""
    
    def setup_method(self):
        self.service = ValidationGovernanceService()
    
    def test_get_governance_status(self):
        """Test governance status"""
        status = self.service.get_governance_status()
        
        assert status["totalRuns"] == 5
        assert status["baseline"] is not None
    
    def test_get_health(self):
        """Test health endpoint"""
        health = self.service.get_health()
        
        assert health["enabled"] is True
        assert health["status"] == "ok"


class TestSerialization:
    """Test serialization functions"""
    
    def test_validation_run_serialization(self):
        """Test ValidationRun serialization"""
        registry = ValidationRegistry()
        run = registry.get_run("run_phase92_quant_report")
        
        data = validation_run_to_dict(run)
        
        assert "runId" in data
        assert "metrics" in data
        assert "validation" in data
    
    def test_comparison_serialization(self):
        """Test Comparison serialization"""
        comparator = BenchmarkComparator()
        comparison = comparator.compare("run_phase92_quant_report")
        
        data = comparison_to_dict(comparison)
        
        assert "deltas" in data
        assert "verdict" in data
    
    def test_release_gate_serialization(self):
        """Test ReleaseGate serialization"""
        manager = ReleaseGateManager()
        gate = manager.check_release("run_phase92_quant_report")
        
        data = release_gate_to_dict(gate)
        
        assert "gateId" in data
        assert "status" in data
        assert "checkpoints" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
