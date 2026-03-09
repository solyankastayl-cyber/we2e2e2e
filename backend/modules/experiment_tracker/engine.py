"""
Experiment Tracker
==================

Research experiment tracking and documentation.
"""

import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class ExperimentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class Experiment:
    """Research experiment"""
    experiment_id: str
    name: str
    
    # Context
    dataset_version: str = ""
    strategies: List[str] = field(default_factory=list)
    assets: List[str] = field(default_factory=list)
    regimes: List[str] = field(default_factory=list)
    
    # Parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Results
    results: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    
    # Status
    status: ExperimentStatus = ExperimentStatus.PENDING
    
    # Notes
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Timing
    started_at: int = 0
    completed_at: int = 0
    created_at: int = 0


class ExperimentTracker:
    """
    Experiment Tracker for research documentation.
    """
    
    def __init__(self):
        self.experiments: Dict[str, Experiment] = {}
    
    def create(
        self,
        name: str,
        dataset_version: str = "",
        strategies: List[str] = None,
        assets: List[str] = None,
        parameters: Dict = None,
        tags: List[str] = None
    ) -> Experiment:
        """Create new experiment"""
        
        exp_id = f"EXP_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        experiment = Experiment(
            experiment_id=exp_id,
            name=name,
            dataset_version=dataset_version,
            strategies=strategies or [],
            assets=assets or [],
            parameters=parameters or {},
            tags=tags or [],
            status=ExperimentStatus.PENDING,
            created_at=now
        )
        
        self.experiments[exp_id] = experiment
        return experiment
    
    def start(self, experiment_id: str) -> Optional[Experiment]:
        """Start an experiment"""
        exp = self.experiments.get(experiment_id)
        if not exp:
            return None
        
        exp.status = ExperimentStatus.RUNNING
        exp.started_at = int(time.time() * 1000)
        return exp
    
    def complete(
        self,
        experiment_id: str,
        results: Dict = None,
        metrics: Dict = None,
        notes: str = ""
    ) -> Optional[Experiment]:
        """Complete an experiment with results"""
        exp = self.experiments.get(experiment_id)
        if not exp:
            return None
        
        exp.status = ExperimentStatus.COMPLETED
        exp.completed_at = int(time.time() * 1000)
        exp.results = results or {}
        exp.metrics = metrics or {}
        if notes:
            exp.notes = notes
        
        return exp
    
    def fail(self, experiment_id: str, error: str = "") -> Optional[Experiment]:
        """Mark experiment as failed"""
        exp = self.experiments.get(experiment_id)
        if not exp:
            return None
        
        exp.status = ExperimentStatus.FAILED
        exp.completed_at = int(time.time() * 1000)
        exp.notes = error
        return exp
    
    def get(self, experiment_id: str) -> Optional[Experiment]:
        """Get experiment by ID"""
        return self.experiments.get(experiment_id)
    
    def list_all(
        self,
        status: str = None,
        tag: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """List experiments"""
        experiments = list(self.experiments.values())
        
        if status:
            try:
                s = ExperimentStatus(status)
                experiments = [e for e in experiments if e.status == s]
            except ValueError:
                pass
        
        if tag:
            experiments = [e for e in experiments if tag in e.tags]
        
        experiments.sort(key=lambda e: e.created_at, reverse=True)
        return [self._to_dict(e) for e in experiments[:limit]]
    
    def get_stats(self) -> Dict:
        """Get experiment statistics"""
        experiments = list(self.experiments.values())
        
        return {
            "total": len(experiments),
            "by_status": {
                s.value: len([e for e in experiments if e.status == s])
                for s in ExperimentStatus
            },
            "avg_duration_seconds": self._avg_duration(experiments),
            "recent_experiments": len([e for e in experiments if e.created_at > int(time.time() * 1000) - 86400000])
        }
    
    def _avg_duration(self, experiments: List[Experiment]) -> float:
        completed = [e for e in experiments if e.completed_at > 0 and e.started_at > 0]
        if not completed:
            return 0
        durations = [(e.completed_at - e.started_at) / 1000 for e in completed]
        return round(sum(durations) / len(durations), 2)
    
    def get_health(self) -> Dict:
        """Get tracker health"""
        return {
            "enabled": True,
            "version": "phaseC",
            "status": "ok",
            "total_experiments": len(self.experiments),
            "running": len([e for e in self.experiments.values() if e.status == ExperimentStatus.RUNNING]),
            "timestamp": int(time.time() * 1000)
        }
    
    def _to_dict(self, e: Experiment) -> Dict:
        return {
            "experiment_id": e.experiment_id,
            "name": e.name,
            "dataset_version": e.dataset_version,
            "strategies": e.strategies,
            "assets": e.assets,
            "parameters": e.parameters,
            "results": e.results,
            "metrics": e.metrics,
            "status": e.status.value,
            "notes": e.notes,
            "tags": e.tags,
            "started_at": e.started_at,
            "completed_at": e.completed_at,
            "created_at": e.created_at
        }


# Singleton
experiment_tracker = ExperimentTracker()
