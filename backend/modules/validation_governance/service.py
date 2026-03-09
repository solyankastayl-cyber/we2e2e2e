"""
Phase 9.25D: Validation Governance
==================================

Управление валидацией и релизами.

Компоненты:
1. Validation Registry — реестр всех валидаций
2. Benchmark Comparison — сравнение с baseline
3. Release Gate — контроль релизов

API:
- GET /api/validation/runs
- GET /api/validation/compare
- POST /api/validation/release-check
"""
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# Types & Enums
# ═══════════════════════════════════════════════════════════════

class ValidationStage(str, Enum):
    """Validation pipeline stages"""
    RESEARCH = "RESEARCH"
    VALIDATION = "VALIDATION"
    REGIME_VALIDATION = "REGIME_VALIDATION"
    CROSS_ASSET = "CROSS_ASSET"
    APPROVAL = "APPROVAL"
    PRODUCTION = "PRODUCTION"


class ValidationStatus(str, Enum):
    """Validation run status"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ReleaseGateStatus(str, Enum):
    """Release gate status"""
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


@dataclass
class ValidationSnapshot:
    """Snapshot of system state at validation time"""
    snapshot_id: str
    system_version: str
    dataset_version: str
    strategy_version: str
    config_version: str
    
    # Content hashes
    strategy_hash: str = ""
    config_hash: str = ""
    dataset_hash: str = ""
    
    created_at: int = 0


@dataclass
class ValidationRun:
    """A single validation run record"""
    run_id: str
    name: str
    stage: ValidationStage
    status: ValidationStatus
    
    # Snapshot
    snapshot: Optional[ValidationSnapshot] = None
    
    # Metrics
    profit_factor: float = 0.0
    win_rate: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    trades: int = 0
    
    # Validation details
    cutoff_time: int = 0  # Data cutoff timestamp
    guardrails_passed: bool = False
    isolation_passed: bool = False
    
    # Timing
    started_at: int = 0
    completed_at: int = 0
    duration_ms: int = 0
    
    # Notes
    notes: str = ""
    errors: List[str] = field(default_factory=list)


@dataclass
class BenchmarkComparison:
    """Comparison with baseline benchmark"""
    run_id: str
    baseline_run_id: str
    
    # Metric deltas
    pf_delta: float = 0.0
    wr_delta: float = 0.0
    sharpe_delta: float = 0.0
    dd_delta: float = 0.0
    
    # Percentage changes
    pf_change_pct: float = 0.0
    wr_change_pct: float = 0.0
    
    # Verdict
    is_improvement: bool = False
    is_regression: bool = False
    is_stable: bool = True
    
    # Details
    summary: str = ""
    timestamp: int = 0


@dataclass
class ReleaseGate:
    """Release gate checkpoint"""
    gate_id: str
    name: str
    status: ReleaseGateStatus
    
    # Pipeline stages
    stages_completed: List[str] = field(default_factory=list)
    stages_pending: List[str] = field(default_factory=list)
    
    # Checkpoints
    research_passed: bool = False
    validation_passed: bool = False
    regime_passed: bool = False
    cross_asset_passed: bool = False
    
    # Metrics thresholds
    min_pf: float = 1.5
    min_wr: float = 0.52
    max_dd: float = 0.20
    
    # Approvals
    auto_approved: bool = False
    manual_approval_required: bool = True
    approved_by: str = ""
    approved_at: int = 0
    
    # Notes
    blockers: List[str] = field(default_factory=list)
    notes: str = ""
    created_at: int = 0


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

VALIDATION_GOVERNANCE_CONFIG = {
    "version": "phase9.25D",
    "enabled": True,
    
    # Pipeline stages
    "pipeline_stages": [
        "RESEARCH",
        "VALIDATION",
        "REGIME_VALIDATION",
        "CROSS_ASSET",
        "APPROVAL"
    ],
    
    # Release criteria
    "release_criteria": {
        "min_pf": 1.5,
        "min_wr": 0.52,
        "min_sharpe": 1.0,
        "max_dd": 0.20,
        "min_trades": 200,
        "min_assets": 3,
        "guardrails_required": True,
        "isolation_required": True
    },
    
    # Regression thresholds
    "regression_thresholds": {
        "pf_decline": 0.10,  # 10% decline is regression
        "wr_decline": 0.03,  # 3pp decline
        "dd_increase": 0.05  # 5pp increase
    }
}


# ═══════════════════════════════════════════════════════════════
# Validation Registry
# ═══════════════════════════════════════════════════════════════

class ValidationRegistry:
    """
    Registry of all validation runs.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or VALIDATION_GOVERNANCE_CONFIG
        self._runs: Dict[str, ValidationRun] = {}
        self._baseline_id: Optional[str] = None
        
        # Initialize with default runs
        self._init_default_runs()
    
    def _init_default_runs(self):
        """Initialize default validation runs from previous phases"""
        default_runs = [
            {
                "id": "run_phase86_calibration",
                "name": "Phase 8.6 Core Calibration",
                "stage": ValidationStage.VALIDATION,
                "status": ValidationStatus.PASSED,
                "pf": 1.82, "wr": 0.54, "sharpe": 1.4, "dd": 0.15, "trades": 500
            },
            {
                "id": "run_phase87_btc_reval",
                "name": "Phase 8.7 BTC Re-validation",
                "stage": ValidationStage.VALIDATION,
                "status": ValidationStatus.PASSED,
                "pf": 2.24, "wr": 0.56, "sharpe": 1.8, "dd": 0.07, "trades": 500
            },
            {
                "id": "run_phase89_regime",
                "name": "Phase 8.9 Regime Validation",
                "stage": ValidationStage.REGIME_VALIDATION,
                "status": ValidationStatus.PASSED,
                "pf": 2.18, "wr": 0.58, "sharpe": 1.7, "dd": 0.09, "trades": 2982
            },
            {
                "id": "run_phase90_cross_asset",
                "name": "Phase 9.0 Cross-Asset Validation",
                "stage": ValidationStage.CROSS_ASSET,
                "status": ValidationStatus.PASSED,
                "pf": 2.40, "wr": 0.60, "sharpe": 1.92, "dd": 0.117, "trades": 2982
            },
            {
                "id": "run_phase92_quant_report",
                "name": "Phase 9.2 Final Quant Report",
                "stage": ValidationStage.APPROVAL,
                "status": ValidationStatus.PASSED,
                "pf": 2.40, "wr": 0.598, "sharpe": 1.92, "dd": 0.117, "trades": 2982
            }
        ]
        
        for r in default_runs:
            snapshot = ValidationSnapshot(
                snapshot_id=f"snapshot_{r['id']}",
                system_version="2.0.0",
                dataset_version="v1",
                strategy_version="phase8.8",
                config_version="calibration_v1",
                strategy_hash=hashlib.sha256(r['id'].encode()).hexdigest()[:16],
                created_at=int(time.time() * 1000) - 86400000
            )
            
            run = ValidationRun(
                run_id=r["id"],
                name=r["name"],
                stage=r["stage"],
                status=r["status"],
                snapshot=snapshot,
                profit_factor=r["pf"],
                win_rate=r["wr"],
                sharpe=r["sharpe"],
                max_drawdown=r["dd"],
                trades=r["trades"],
                cutoff_time=int(time.time() * 1000) - 86400000 * 30,
                guardrails_passed=True,
                isolation_passed=True,
                started_at=int(time.time() * 1000) - 86400000,
                completed_at=int(time.time() * 1000) - 86400000 + 300000,
                duration_ms=300000
            )
            
            self._runs[r["id"]] = run
        
        # Set baseline
        self._baseline_id = "run_phase90_cross_asset"
    
    def register_run(self, run: ValidationRun):
        """Register a validation run"""
        self._runs[run.run_id] = run
    
    def get_run(self, run_id: str) -> Optional[ValidationRun]:
        """Get validation run by ID"""
        return self._runs.get(run_id)
    
    def get_all_runs(self) -> Dict[str, ValidationRun]:
        """Get all runs"""
        return self._runs
    
    def get_runs_by_stage(self, stage: ValidationStage) -> List[ValidationRun]:
        """Get runs by stage"""
        return [r for r in self._runs.values() if r.stage == stage]
    
    def get_baseline(self) -> Optional[ValidationRun]:
        """Get baseline run"""
        if self._baseline_id:
            return self._runs.get(self._baseline_id)
        return None
    
    def set_baseline(self, run_id: str) -> bool:
        """Set baseline run"""
        if run_id in self._runs:
            self._baseline_id = run_id
            return True
        return False


# ═══════════════════════════════════════════════════════════════
# Benchmark Comparison
# ═══════════════════════════════════════════════════════════════

class BenchmarkComparator:
    """
    Compares validation runs against baseline.
    """
    
    def __init__(self, registry: Optional[ValidationRegistry] = None, config: Optional[Dict] = None):
        self.config = config or VALIDATION_GOVERNANCE_CONFIG
        self.registry = registry or ValidationRegistry(config)
    
    def compare(self, run_id: str, baseline_id: Optional[str] = None) -> Optional[BenchmarkComparison]:
        """
        Compare a run against baseline.
        """
        run = self.registry.get_run(run_id)
        if not run:
            return None
        
        baseline = self.registry.get_run(baseline_id) if baseline_id else self.registry.get_baseline()
        if not baseline:
            return None
        
        thresholds = self.config.get("regression_thresholds", {})
        
        # Calculate deltas
        pf_delta = run.profit_factor - baseline.profit_factor
        wr_delta = run.win_rate - baseline.win_rate
        sharpe_delta = run.sharpe - baseline.sharpe
        dd_delta = run.max_drawdown - baseline.max_drawdown
        
        # Calculate percentage changes
        pf_change = pf_delta / baseline.profit_factor if baseline.profit_factor > 0 else 0
        wr_change = wr_delta / baseline.win_rate if baseline.win_rate > 0 else 0
        
        # Determine verdict
        is_regression = (
            pf_change < -thresholds.get("pf_decline", 0.10) or
            wr_delta < -thresholds.get("wr_decline", 0.03) or
            dd_delta > thresholds.get("dd_increase", 0.05)
        )
        
        is_improvement = (
            pf_change > thresholds.get("pf_decline", 0.10) and
            wr_delta >= 0
        )
        
        is_stable = not is_regression and not is_improvement
        
        # Summary
        if is_improvement:
            summary = f"Improvement: PF +{pf_change*100:.1f}%, WR +{wr_delta*100:.1f}pp"
        elif is_regression:
            summary = f"Regression: PF {pf_change*100:.1f}%, WR {wr_delta*100:.1f}pp"
        else:
            summary = f"Stable: within thresholds"
        
        return BenchmarkComparison(
            run_id=run_id,
            baseline_run_id=baseline.run_id,
            pf_delta=round(pf_delta, 4),
            wr_delta=round(wr_delta, 4),
            sharpe_delta=round(sharpe_delta, 4),
            dd_delta=round(dd_delta, 4),
            pf_change_pct=round(pf_change, 4),
            wr_change_pct=round(wr_change, 4),
            is_improvement=is_improvement,
            is_regression=is_regression,
            is_stable=is_stable,
            summary=summary,
            timestamp=int(time.time() * 1000)
        )


# ═══════════════════════════════════════════════════════════════
# Release Gate
# ═══════════════════════════════════════════════════════════════

class ReleaseGateManager:
    """
    Manages release gates and approvals.
    """
    
    def __init__(self, registry: Optional[ValidationRegistry] = None, config: Optional[Dict] = None):
        self.config = config or VALIDATION_GOVERNANCE_CONFIG
        self.registry = registry or ValidationRegistry(config)
        self._gates: Dict[str, ReleaseGate] = {}
    
    def create_gate(self, name: str) -> ReleaseGate:
        """Create a new release gate"""
        gate_id = f"gate_{int(time.time() * 1000)}"
        
        criteria = self.config.get("release_criteria", {})
        
        gate = ReleaseGate(
            gate_id=gate_id,
            name=name,
            status=ReleaseGateStatus.NOT_STARTED,
            stages_pending=self.config.get("pipeline_stages", []),
            min_pf=criteria.get("min_pf", 1.5),
            min_wr=criteria.get("min_wr", 0.52),
            max_dd=criteria.get("max_dd", 0.20),
            created_at=int(time.time() * 1000)
        )
        
        self._gates[gate_id] = gate
        return gate
    
    def check_release(self, run_id: str) -> ReleaseGate:
        """
        Check if a validation run passes release criteria.
        """
        run = self.registry.get_run(run_id)
        criteria = self.config.get("release_criteria", {})
        
        gate = self.create_gate(f"Release Check for {run_id}")
        gate.status = ReleaseGateStatus.IN_PROGRESS
        
        blockers = []
        
        if not run:
            blockers.append(f"Run {run_id} not found")
            gate.status = ReleaseGateStatus.BLOCKED
            gate.blockers = blockers
            return gate
        
        # Check metrics
        if run.profit_factor < criteria.get("min_pf", 1.5):
            blockers.append(f"PF {run.profit_factor:.2f} < {criteria.get('min_pf')}")
        else:
            gate.stages_completed.append("PF_CHECK")
        
        if run.win_rate < criteria.get("min_wr", 0.52):
            blockers.append(f"WR {run.win_rate*100:.1f}% < {criteria.get('min_wr')*100}%")
        else:
            gate.stages_completed.append("WR_CHECK")
        
        if run.max_drawdown > criteria.get("max_dd", 0.20):
            blockers.append(f"DD {run.max_drawdown*100:.1f}% > {criteria.get('max_dd')*100}%")
        else:
            gate.stages_completed.append("DD_CHECK")
        
        if run.trades < criteria.get("min_trades", 200):
            blockers.append(f"Trades {run.trades} < {criteria.get('min_trades')}")
        else:
            gate.stages_completed.append("TRADES_CHECK")
        
        # Check guardrails
        if criteria.get("guardrails_required", True) and not run.guardrails_passed:
            blockers.append("Guardrails check not passed")
        else:
            gate.guardrails_passed = run.guardrails_passed
        
        # Check isolation
        if criteria.get("isolation_required", True) and not run.isolation_passed:
            blockers.append("Isolation check not passed")
        else:
            gate.isolation_passed = run.isolation_passed
        
        # Set status based on validation stage
        gate.research_passed = True
        gate.validation_passed = run.stage.value in ["VALIDATION", "REGIME_VALIDATION", "CROSS_ASSET", "APPROVAL"]
        gate.regime_passed = run.stage.value in ["REGIME_VALIDATION", "CROSS_ASSET", "APPROVAL"]
        gate.cross_asset_passed = run.stage.value in ["CROSS_ASSET", "APPROVAL"]
        
        if blockers:
            gate.status = ReleaseGateStatus.REJECTED
            gate.blockers = blockers
        else:
            gate.status = ReleaseGateStatus.APPROVED
            gate.auto_approved = True
            gate.approved_at = int(time.time() * 1000)
        
        self._gates[gate.gate_id] = gate
        return gate
    
    def get_gate(self, gate_id: str) -> Optional[ReleaseGate]:
        """Get gate by ID"""
        return self._gates.get(gate_id)
    
    def get_all_gates(self) -> Dict[str, ReleaseGate]:
        """Get all gates"""
        return self._gates


# ═══════════════════════════════════════════════════════════════
# Validation Governance Service
# ═══════════════════════════════════════════════════════════════

class ValidationGovernanceService:
    """
    Main Validation Governance Service.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or VALIDATION_GOVERNANCE_CONFIG
        
        self.registry = ValidationRegistry(config)
        self.comparator = BenchmarkComparator(self.registry, config)
        self.release_manager = ReleaseGateManager(self.registry, config)
    
    def get_governance_status(self) -> Dict:
        """Get governance status"""
        runs = self.registry.get_all_runs()
        
        passed = len([r for r in runs.values() if r.status == ValidationStatus.PASSED])
        failed = len([r for r in runs.values() if r.status == ValidationStatus.FAILED])
        
        by_stage = {}
        for stage in ValidationStage:
            count = len([r for r in runs.values() if r.stage == stage])
            if count > 0:
                by_stage[stage.value] = count
        
        baseline = self.registry.get_baseline()
        
        return {
            "totalRuns": len(runs),
            "passedRuns": passed,
            "failedRuns": failed,
            "byStage": by_stage,
            "baseline": {
                "runId": baseline.run_id,
                "pf": baseline.profit_factor,
                "wr": baseline.win_rate
            } if baseline else None,
            "version": self.config.get("version", "phase9.25D"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": self.config.get("enabled", True),
            "version": self.config.get("version", "phase9.25D"),
            "status": "ok",
            "components": {
                "registry": "ok",
                "comparator": "ok",
                "release_manager": "ok"
            },
            "runsCount": len(self.registry.get_all_runs()),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


# ═══════════════════════════════════════════════════════════════
# Serialization Functions
# ═══════════════════════════════════════════════════════════════

def validation_run_to_dict(run: ValidationRun) -> Dict:
    """Convert ValidationRun to dict"""
    return {
        "runId": run.run_id,
        "name": run.name,
        "stage": run.stage.value,
        "status": run.status.value,
        "snapshot": {
            "snapshotId": run.snapshot.snapshot_id,
            "systemVersion": run.snapshot.system_version,
            "datasetVersion": run.snapshot.dataset_version,
            "strategyVersion": run.snapshot.strategy_version
        } if run.snapshot else None,
        "metrics": {
            "profitFactor": run.profit_factor,
            "winRate": run.win_rate,
            "sharpe": run.sharpe,
            "maxDrawdown": run.max_drawdown,
            "trades": run.trades
        },
        "validation": {
            "cutoffTime": run.cutoff_time,
            "guardrailsPassed": run.guardrails_passed,
            "isolationPassed": run.isolation_passed
        },
        "timing": {
            "startedAt": run.started_at,
            "completedAt": run.completed_at,
            "durationMs": run.duration_ms
        },
        "notes": run.notes,
        "errors": run.errors
    }


def comparison_to_dict(comp: BenchmarkComparison) -> Dict:
    """Convert BenchmarkComparison to dict"""
    return {
        "runId": comp.run_id,
        "baselineRunId": comp.baseline_run_id,
        "deltas": {
            "pf": comp.pf_delta,
            "wr": comp.wr_delta,
            "sharpe": comp.sharpe_delta,
            "dd": comp.dd_delta
        },
        "changes": {
            "pfPct": comp.pf_change_pct,
            "wrPct": comp.wr_change_pct
        },
        "verdict": {
            "isImprovement": comp.is_improvement,
            "isRegression": comp.is_regression,
            "isStable": comp.is_stable
        },
        "summary": comp.summary,
        "timestamp": comp.timestamp
    }


def release_gate_to_dict(gate: ReleaseGate) -> Dict:
    """Convert ReleaseGate to dict"""
    return {
        "gateId": gate.gate_id,
        "name": gate.name,
        "status": gate.status.value,
        "stagesCompleted": gate.stages_completed,
        "stagesPending": gate.stages_pending,
        "checkpoints": {
            "research": gate.research_passed,
            "validation": gate.validation_passed,
            "regime": gate.regime_passed,
            "crossAsset": gate.cross_asset_passed
        },
        "criteria": {
            "minPf": gate.min_pf,
            "minWr": gate.min_wr,
            "maxDd": gate.max_dd
        },
        "approval": {
            "autoApproved": gate.auto_approved,
            "manualRequired": gate.manual_approval_required,
            "approvedBy": gate.approved_by,
            "approvedAt": gate.approved_at
        },
        "blockers": gate.blockers,
        "notes": gate.notes,
        "createdAt": gate.created_at
    }
