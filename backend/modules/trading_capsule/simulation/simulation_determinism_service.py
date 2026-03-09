"""
Simulation Determinism Service (S1.1)
=====================================

Determinism Guard for simulation.

Ensures:
- Same inputs → same results
- Config frozen at start
- No external dependencies during run
- Reproducible simulations
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading
import hashlib
import json

from .simulation_types import (
    SimulationRun,
    SimulationFingerprint,
    FrozenSimulationConfig
)


class SimulationDeterminismService:
    """
    Service for ensuring simulation determinism.
    
    Responsibilities:
    - Build fingerprints
    - Freeze configs at start
    - Validate consistency
    - Compare runs
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Fingerprint storage
        self._fingerprints: Dict[str, SimulationFingerprint] = {}
        
        # Frozen config storage
        self._frozen_configs: Dict[str, FrozenSimulationConfig] = {}
        
        self._initialized = True
        print("[SimulationDeterminismService] Initialized")
    
    # ===========================================
    # Fingerprint Operations
    # ===========================================
    
    def build_fingerprint(
        self,
        run: SimulationRun,
        strategy_config: Optional[Dict[str, Any]] = None,
        risk_config: Optional[Dict[str, Any]] = None
    ) -> SimulationFingerprint:
        """
        Build determinism fingerprint for a run.
        
        Called at run creation to capture all inputs.
        """
        # Compute config hash
        config_data = {
            "strategy_config": strategy_config or {},
            "risk_config": risk_config or {},
            "strategy_id": run.strategy_id,
            "strategy_version": run.strategy_version,
            "asset": run.asset,
            "market_type": run.market_type.value,
            "timeframe": run.timeframe.value,
            "start_date": run.start_date,
            "end_date": run.end_date,
            "initial_capital_usd": run.initial_capital_usd,
            "capital_profile": run.capital_profile.value
        }
        config_json = json.dumps(config_data, sort_keys=True)
        config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:16]
        
        fingerprint = SimulationFingerprint(
            run_id=run.run_id,
            strategy_id=run.strategy_id,
            strategy_version=run.strategy_version,
            asset=run.asset,
            market_type=run.market_type.value,
            timeframe=run.timeframe.value,
            dataset_id=run.dataset_id,
            dataset_checksum=run.dataset_checksum,
            start_date=run.start_date,
            end_date=run.end_date,
            initial_capital_usd=run.initial_capital_usd,
            capital_profile=run.capital_profile.value,
            risk_profile_id=run.risk_profile_id,
            risk_profile_version=run.risk_profile_version,
            config_hash=config_hash
        )
        
        # Store
        self._fingerprints[run.run_id] = fingerprint
        
        print(f"[DeterminismService] Built fingerprint for run: {run.run_id}")
        return fingerprint
    
    def get_fingerprint(self, run_id: str) -> Optional[SimulationFingerprint]:
        """Get fingerprint for run"""
        return self._fingerprints.get(run_id)
    
    # ===========================================
    # Config Freezing
    # ===========================================
    
    def freeze_config(
        self,
        run_id: str,
        strategy_config: Dict[str, Any],
        risk_config: Dict[str, Any],
        execution_config: Optional[Dict[str, Any]] = None
    ) -> FrozenSimulationConfig:
        """
        Freeze configuration at run start.
        
        Once frozen, config cannot be modified during run.
        """
        frozen = FrozenSimulationConfig(
            run_id=run_id,
            strategy_config=strategy_config.copy(),
            risk_config=risk_config.copy(),
            execution_config=(execution_config or {}).copy()
        )
        
        self._frozen_configs[run_id] = frozen
        
        print(f"[DeterminismService] Froze config for run: {run_id}")
        return frozen
    
    def get_frozen_config(self, run_id: str) -> Optional[FrozenSimulationConfig]:
        """Get frozen config for run"""
        return self._frozen_configs.get(run_id)
    
    def is_config_frozen(self, run_id: str) -> bool:
        """Check if config is frozen"""
        return run_id in self._frozen_configs
    
    # ===========================================
    # Validation
    # ===========================================
    
    def validate_run_consistency(
        self,
        run: SimulationRun,
        current_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate that current run state matches frozen config.
        
        Returns validation result with any inconsistencies.
        """
        frozen = self._frozen_configs.get(run.run_id)
        if not frozen:
            return {
                "valid": False,
                "error": "Config not frozen",
                "inconsistencies": []
            }
        
        inconsistencies = []
        
        # Check strategy config
        if current_config.get("strategy_config") != frozen.strategy_config:
            inconsistencies.append({
                "field": "strategy_config",
                "expected": frozen.strategy_config,
                "actual": current_config.get("strategy_config")
            })
        
        # Check risk config
        if current_config.get("risk_config") != frozen.risk_config:
            inconsistencies.append({
                "field": "risk_config",
                "expected": frozen.risk_config,
                "actual": current_config.get("risk_config")
            })
        
        return {
            "valid": len(inconsistencies) == 0,
            "inconsistencies": inconsistencies,
            "fingerprint": self._fingerprints.get(run.run_id, {})
        }
    
    # ===========================================
    # Comparison
    # ===========================================
    
    def compare_fingerprints(
        self,
        run_id_a: str,
        run_id_b: str
    ) -> Dict[str, Any]:
        """
        Compare fingerprints of two runs.
        
        Useful for checking if two runs should produce same results.
        """
        fp_a = self._fingerprints.get(run_id_a)
        fp_b = self._fingerprints.get(run_id_b)
        
        if not fp_a or not fp_b:
            return {
                "comparable": False,
                "error": "Missing fingerprint(s)"
            }
        
        differences = []
        
        # Compare fields
        fields_to_compare = [
            "strategy_id", "strategy_version", "asset", "market_type",
            "timeframe", "dataset_id", "dataset_checksum", "start_date",
            "end_date", "initial_capital_usd", "capital_profile",
            "risk_profile_id", "config_hash"
        ]
        
        for field in fields_to_compare:
            val_a = getattr(fp_a, field, None)
            val_b = getattr(fp_b, field, None)
            if val_a != val_b:
                differences.append({
                    "field": field,
                    "run_a": val_a,
                    "run_b": val_b
                })
        
        # Compute hashes
        hash_a = fp_a.compute_hash()
        hash_b = fp_b.compute_hash()
        
        return {
            "comparable": True,
            "identical": len(differences) == 0,
            "hash_a": hash_a,
            "hash_b": hash_b,
            "hashes_match": hash_a == hash_b,
            "differences": differences
        }
    
    def are_runs_identical(self, run_id_a: str, run_id_b: str) -> bool:
        """Check if two runs have identical inputs"""
        comparison = self.compare_fingerprints(run_id_a, run_id_b)
        return comparison.get("identical", False)
    
    # ===========================================
    # Cleanup
    # ===========================================
    
    def delete_run_data(self, run_id: str) -> bool:
        """Delete fingerprint and frozen config for run"""
        deleted = False
        
        if run_id in self._fingerprints:
            del self._fingerprints[run_id]
            deleted = True
        
        if run_id in self._frozen_configs:
            del self._frozen_configs[run_id]
            deleted = True
        
        return deleted
    
    def clear_all(self) -> int:
        """Clear all stored data"""
        count = len(self._fingerprints)
        self._fingerprints.clear()
        self._frozen_configs.clear()
        return count


# Global singleton
simulation_determinism_service = SimulationDeterminismService()
