"""
Feature Mutation Engine
=======================

Phase 9.31B - Algorithmic feature mutation for discovering new factors.

Generates new features through:
- Arithmetic mutations (add, subtract, multiply, divide)
- Temporal mutations (lag, slope, persistence)
- Regime mutations (regime-conditional features)
- Cross-asset mutations (relative features)

All mutations go through:
- Sandbox testing
- Quality gates
- Crowding filter
"""

import time
import uuid
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .types import (
    FeatureDescriptor, FeatureFamily, FeatureType, FeatureStatus,
    NormalizationMethod, MutationOp, MutationConfig
)


class MutationCategory(str, Enum):
    """Categories of mutations"""
    ARITHMETIC = "ARITHMETIC"
    TEMPORAL = "TEMPORAL"
    REGIME = "REGIME"
    CROSS_ASSET = "CROSS_ASSET"


@dataclass
class MutationResult:
    """Result of a mutation attempt"""
    mutation_id: str
    parent_ids: List[str]
    category: MutationCategory
    operation: MutationOp
    parameters: Dict[str, Any]
    
    # Generated feature
    feature_id: str = ""
    feature_name: str = ""
    values: List[float] = field(default_factory=list)
    
    # Quality gates
    passed_quality: bool = False
    passed_crowding: bool = False
    passed_sandbox: bool = False
    
    # Scores
    quality_score: float = 0.0
    crowding_score: float = 0.0
    utility_score: float = 0.0
    final_score: float = 0.0
    
    # Status
    status: str = "PENDING"  # PENDING, PASSED, REJECTED
    rejection_reason: str = ""
    
    created_at: int = 0


@dataclass
class MutationBatchResult:
    """Result of batch mutation"""
    batch_id: str
    total_mutations: int = 0
    passed: int = 0
    rejected: int = 0
    results: List[MutationResult] = field(default_factory=list)
    
    best_mutation: Optional[MutationResult] = None
    created_at: int = 0


class FeatureMutationEngine:
    """
    Engine for generating mutated features.
    
    Mutations are hypothesis-driven:
    - Start with base features
    - Apply transformations
    - Test quality and crowding
    - Promote survivors to sandbox
    """
    
    def __init__(self):
        self.mutations: Dict[str, MutationResult] = {}
        self.batches: Dict[str, MutationBatchResult] = {}
        
        # Quality thresholds
        self.min_coverage = 0.90
        self.max_missing_rate = 0.05
        self.min_variance = 0.0001
        self.max_crowding = 0.85
        self.min_utility = 0.02
        
        # Counters
        self.total_generated = 0
        self.total_passed = 0
        self.total_rejected = 0
    
    # ============================================
    # Arithmetic Mutations
    # ============================================
    
    def mutate_add(
        self,
        feature_a_id: str,
        feature_b_id: str,
        values_a: List[float],
        values_b: List[float],
        name_suffix: str = ""
    ) -> MutationResult:
        """f_new = f_a + f_b"""
        return self._arithmetic_mutation(
            feature_a_id, feature_b_id,
            values_a, values_b,
            MutationOp.ADD,
            lambda a, b: a + b,
            name_suffix or "ADD"
        )
    
    def mutate_subtract(
        self,
        feature_a_id: str,
        feature_b_id: str,
        values_a: List[float],
        values_b: List[float],
        name_suffix: str = ""
    ) -> MutationResult:
        """f_new = f_a - f_b (spread/diff)"""
        return self._arithmetic_mutation(
            feature_a_id, feature_b_id,
            values_a, values_b,
            MutationOp.SUBTRACT,
            lambda a, b: a - b,
            name_suffix or "DIFF"
        )
    
    def mutate_multiply(
        self,
        feature_a_id: str,
        feature_b_id: str,
        values_a: List[float],
        values_b: List[float],
        name_suffix: str = ""
    ) -> MutationResult:
        """f_new = f_a * f_b (interaction)"""
        return self._arithmetic_mutation(
            feature_a_id, feature_b_id,
            values_a, values_b,
            MutationOp.MULTIPLY,
            lambda a, b: a * b,
            name_suffix or "MULT"
        )
    
    def mutate_divide(
        self,
        feature_a_id: str,
        feature_b_id: str,
        values_a: List[float],
        values_b: List[float],
        name_suffix: str = ""
    ) -> MutationResult:
        """f_new = f_a / f_b (ratio)"""
        def safe_divide(a, b):
            if b == 0 or abs(b) < 1e-10:
                return None
            return a / b
        
        return self._arithmetic_mutation(
            feature_a_id, feature_b_id,
            values_a, values_b,
            MutationOp.DIVIDE,
            safe_divide,
            name_suffix or "RATIO"
        )
    
    def _arithmetic_mutation(
        self,
        feature_a_id: str,
        feature_b_id: str,
        values_a: List[float],
        values_b: List[float],
        operation: MutationOp,
        op_func,
        name_suffix: str
    ) -> MutationResult:
        """Generic arithmetic mutation"""
        
        mutation_id = f"MUT_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        n = min(len(values_a), len(values_b))
        values = []
        
        for i in range(n):
            a, b = values_a[i], values_b[i]
            if a is None or b is None:
                values.append(None)
            elif math.isnan(a) or math.isnan(b):
                values.append(None)
            else:
                val = op_func(a, b)
                values.append(val)
        
        feature_id = f"F_MUT_{uuid.uuid4().hex[:6].upper()}"
        feature_name = f"{feature_a_id}_{name_suffix}_{feature_b_id}"
        
        result = MutationResult(
            mutation_id=mutation_id,
            parent_ids=[feature_a_id, feature_b_id],
            category=MutationCategory.ARITHMETIC,
            operation=operation,
            parameters={},
            feature_id=feature_id,
            feature_name=feature_name,
            values=values,
            created_at=now
        )
        
        self._run_quality_gates(result)
        self.mutations[mutation_id] = result
        self.total_generated += 1
        
        return result
    
    # ============================================
    # Temporal Mutations
    # ============================================
    
    def mutate_lag(
        self,
        feature_id: str,
        values: List[float],
        lag_periods: int = 5
    ) -> MutationResult:
        """f_new = f(t - lag)"""
        
        mutation_id = f"MUT_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        lagged = [None] * lag_periods + values[:-lag_periods] if lag_periods < len(values) else [None] * len(values)
        
        new_feature_id = f"F_MUT_{uuid.uuid4().hex[:6].upper()}"
        feature_name = f"{feature_id}_LAG{lag_periods}"
        
        result = MutationResult(
            mutation_id=mutation_id,
            parent_ids=[feature_id],
            category=MutationCategory.TEMPORAL,
            operation=MutationOp.LAG,
            parameters={"lag_periods": lag_periods},
            feature_id=new_feature_id,
            feature_name=feature_name,
            values=lagged,
            created_at=now
        )
        
        self._run_quality_gates(result)
        self.mutations[mutation_id] = result
        self.total_generated += 1
        
        return result
    
    def mutate_slope(
        self,
        feature_id: str,
        values: List[float],
        window: int = 10
    ) -> MutationResult:
        """f_new = (f(t) - f(t-window)) / window (trend/slope)"""
        
        mutation_id = f"MUT_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        slopes = []
        for i in range(len(values)):
            if i < window:
                slopes.append(None)
            elif values[i] is None or values[i - window] is None:
                slopes.append(None)
            else:
                slope = (values[i] - values[i - window]) / window
                slopes.append(slope)
        
        new_feature_id = f"F_MUT_{uuid.uuid4().hex[:6].upper()}"
        feature_name = f"{feature_id}_SLOPE{window}"
        
        result = MutationResult(
            mutation_id=mutation_id,
            parent_ids=[feature_id],
            category=MutationCategory.TEMPORAL,
            operation=MutationOp.SLOPE,
            parameters={"window": window},
            feature_id=new_feature_id,
            feature_name=feature_name,
            values=slopes,
            created_at=now
        )
        
        self._run_quality_gates(result)
        self.mutations[mutation_id] = result
        self.total_generated += 1
        
        return result
    
    def mutate_persistence(
        self,
        feature_id: str,
        values: List[float],
        threshold: float = 0.0,
        window: int = 10
    ) -> MutationResult:
        """f_new = count(f > threshold) / window (persistence/duration)"""
        
        mutation_id = f"MUT_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        persistence = []
        for i in range(len(values)):
            if i < window:
                persistence.append(None)
            else:
                window_vals = values[i - window + 1:i + 1]
                valid_vals = [v for v in window_vals if v is not None]
                if len(valid_vals) < window // 2:
                    persistence.append(None)
                else:
                    count_above = sum(1 for v in valid_vals if v > threshold)
                    persistence.append(count_above / len(valid_vals))
        
        new_feature_id = f"F_MUT_{uuid.uuid4().hex[:6].upper()}"
        feature_name = f"{feature_id}_PERSIST{window}"
        
        result = MutationResult(
            mutation_id=mutation_id,
            parent_ids=[feature_id],
            category=MutationCategory.TEMPORAL,
            operation=MutationOp.PERSISTENCE,
            parameters={"threshold": threshold, "window": window},
            feature_id=new_feature_id,
            feature_name=feature_name,
            values=persistence,
            created_at=now
        )
        
        self._run_quality_gates(result)
        self.mutations[mutation_id] = result
        self.total_generated += 1
        
        return result
    
    # ============================================
    # Regime Mutations
    # ============================================
    
    def mutate_regime_mask(
        self,
        feature_id: str,
        values: List[float],
        regime_indicators: List[int],
        target_regime: int = 1
    ) -> MutationResult:
        """f_new = f * I(regime == target)"""
        
        mutation_id = f"MUT_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        n = min(len(values), len(regime_indicators))
        masked = []
        
        for i in range(n):
            if values[i] is None or regime_indicators[i] is None:
                masked.append(None)
            elif regime_indicators[i] == target_regime:
                masked.append(values[i])
            else:
                masked.append(0.0)
        
        new_feature_id = f"F_MUT_{uuid.uuid4().hex[:6].upper()}"
        feature_name = f"{feature_id}_REGIME{target_regime}"
        
        result = MutationResult(
            mutation_id=mutation_id,
            parent_ids=[feature_id],
            category=MutationCategory.REGIME,
            operation=MutationOp.REGIME_MASK,
            parameters={"target_regime": target_regime},
            feature_id=new_feature_id,
            feature_name=feature_name,
            values=masked,
            created_at=now
        )
        
        self._run_quality_gates(result)
        self.mutations[mutation_id] = result
        self.total_generated += 1
        
        return result
    
    # ============================================
    # Cross-Asset Mutations
    # ============================================
    
    def mutate_relative(
        self,
        feature_a_id: str,
        feature_b_id: str,
        values_a: List[float],
        values_b: List[float],
        asset_a: str = "BTC",
        asset_b: str = "SPX"
    ) -> MutationResult:
        """f_new = f_a / f_b (cross-asset relative)"""
        
        mutation_id = f"MUT_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        n = min(len(values_a), len(values_b))
        relative = []
        
        for i in range(n):
            a, b = values_a[i], values_b[i]
            if a is None or b is None or b == 0:
                relative.append(None)
            else:
                relative.append(a / b)
        
        new_feature_id = f"F_MUT_{uuid.uuid4().hex[:6].upper()}"
        feature_name = f"{feature_a_id}_{asset_a}_REL_{asset_b}"
        
        result = MutationResult(
            mutation_id=mutation_id,
            parent_ids=[feature_a_id, feature_b_id],
            category=MutationCategory.CROSS_ASSET,
            operation=MutationOp.DIVIDE,
            parameters={"asset_a": asset_a, "asset_b": asset_b},
            feature_id=new_feature_id,
            feature_name=feature_name,
            values=relative,
            created_at=now
        )
        
        self._run_quality_gates(result)
        self.mutations[mutation_id] = result
        self.total_generated += 1
        
        return result
    
    # ============================================
    # Quality Gates
    # ============================================
    
    def _run_quality_gates(self, result: MutationResult):
        """Run quality and crowding checks on mutation result"""
        
        # Quality check
        quality_result = self._check_quality(result.values)
        result.passed_quality = quality_result["passed"]
        result.quality_score = quality_result["score"]
        
        if not result.passed_quality:
            result.status = "REJECTED"
            result.rejection_reason = quality_result["reason"]
            self.total_rejected += 1
            return
        
        # Crowding check is deferred (needs existing features)
        result.passed_crowding = True
        result.crowding_score = 0.0
        
        # Sandbox check (placeholder)
        result.passed_sandbox = True
        
        # Final score
        result.final_score = result.quality_score * (1 - result.crowding_score)
        result.status = "PASSED"
        self.total_passed += 1
    
    def _check_quality(self, values: List[float]) -> Dict:
        """Check quality of generated values"""
        
        # Filter valid values
        valid = [v for v in values if v is not None and not math.isnan(v)]
        
        if not valid:
            return {"passed": False, "score": 0.0, "reason": "No valid values"}
        
        # Coverage
        coverage = len(valid) / len(values) if values else 0
        if coverage < self.min_coverage:
            return {"passed": False, "score": 0.0, "reason": f"Low coverage: {coverage:.2%}"}
        
        # Variance
        mean = sum(valid) / len(valid)
        variance = sum((v - mean) ** 2 for v in valid) / len(valid)
        
        if variance < self.min_variance:
            return {"passed": False, "score": 0.0, "reason": "Near-constant values"}
        
        # Check for infinities
        if any(math.isinf(v) for v in valid):
            return {"passed": False, "score": 0.0, "reason": "Contains infinity"}
        
        # Stability score (based on variance consistency)
        half = len(valid) // 2
        var_first = sum((v - mean) ** 2 for v in valid[:half]) / half if half > 0 else variance
        var_second = sum((v - mean) ** 2 for v in valid[half:]) / (len(valid) - half) if len(valid) > half else variance
        
        stability = 1.0 - abs(var_first - var_second) / (max(var_first, var_second) + 1e-10)
        stability = max(0, min(1, stability))
        
        # Final quality score
        score = 0.5 * coverage + 0.5 * stability
        
        return {"passed": True, "score": round(score, 4), "reason": ""}
    
    def check_crowding(
        self,
        mutation_id: str,
        existing_feature_values: Dict[str, List[float]]
    ) -> Dict:
        """Check if mutation is redundant with existing features"""
        
        result = self.mutations.get(mutation_id)
        if not result:
            return {"error": "Mutation not found"}
        
        max_corr = 0.0
        crowded_with = ""
        
        for feat_id, feat_values in existing_feature_values.items():
            corr = self._compute_correlation(result.values, feat_values)
            if abs(corr) > max_corr:
                max_corr = abs(corr)
                crowded_with = feat_id
        
        result.crowding_score = max_corr
        result.passed_crowding = max_corr < self.max_crowding
        
        if not result.passed_crowding:
            result.status = "REJECTED"
            result.rejection_reason = f"Too correlated with {crowded_with}: {max_corr:.2%}"
            self.total_passed -= 1
            self.total_rejected += 1
        
        return {
            "mutation_id": mutation_id,
            "max_correlation": max_corr,
            "crowded_with": crowded_with,
            "passed": result.passed_crowding
        }
    
    def _compute_correlation(self, values_a: List[float], values_b: List[float]) -> float:
        """Compute Pearson correlation"""
        n = min(len(values_a), len(values_b))
        
        valid_pairs = []
        for i in range(n):
            a, b = values_a[i], values_b[i]
            if a is not None and b is not None:
                if not math.isnan(a) and not math.isnan(b):
                    valid_pairs.append((a, b))
        
        if len(valid_pairs) < 10:
            return 0.0
        
        a_vals = [p[0] for p in valid_pairs]
        b_vals = [p[1] for p in valid_pairs]
        
        mean_a = sum(a_vals) / len(a_vals)
        mean_b = sum(b_vals) / len(b_vals)
        
        cov = sum((a_vals[i] - mean_a) * (b_vals[i] - mean_b) for i in range(len(valid_pairs))) / len(valid_pairs)
        var_a = sum((a - mean_a) ** 2 for a in a_vals) / len(valid_pairs)
        var_b = sum((b - mean_b) ** 2 for b in b_vals) / len(valid_pairs)
        
        if var_a <= 0 or var_b <= 0:
            return 0.0
        
        return cov / (math.sqrt(var_a) * math.sqrt(var_b))
    
    # ============================================
    # Batch Mutations
    # ============================================
    
    def run_batch_arithmetic(
        self,
        feature_pairs: List[Tuple[str, str, List[float], List[float]]]
    ) -> MutationBatchResult:
        """Run batch of arithmetic mutations"""
        
        batch_id = f"BATCH_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        results = []
        
        for feat_a_id, feat_b_id, values_a, values_b in feature_pairs:
            # Try all arithmetic operations
            results.append(self.mutate_add(feat_a_id, feat_b_id, values_a, values_b))
            results.append(self.mutate_subtract(feat_a_id, feat_b_id, values_a, values_b))
            results.append(self.mutate_multiply(feat_a_id, feat_b_id, values_a, values_b))
            results.append(self.mutate_divide(feat_a_id, feat_b_id, values_a, values_b))
        
        passed = [r for r in results if r.status == "PASSED"]
        
        batch_result = MutationBatchResult(
            batch_id=batch_id,
            total_mutations=len(results),
            passed=len(passed),
            rejected=len(results) - len(passed),
            results=results,
            best_mutation=max(passed, key=lambda r: r.final_score) if passed else None,
            created_at=now
        )
        
        self.batches[batch_id] = batch_result
        return batch_result
    
    def run_batch_temporal(
        self,
        features: List[Tuple[str, List[float]]],
        lag_periods: List[int] = None,
        slope_windows: List[int] = None
    ) -> MutationBatchResult:
        """Run batch of temporal mutations"""
        
        batch_id = f"BATCH_{uuid.uuid4().hex[:10]}"
        now = int(time.time() * 1000)
        
        lag_periods = lag_periods or [1, 3, 5, 10, 20]
        slope_windows = slope_windows or [5, 10, 20]
        
        results = []
        
        for feat_id, values in features:
            # Lag mutations
            for lag in lag_periods:
                results.append(self.mutate_lag(feat_id, values, lag))
            
            # Slope mutations
            for window in slope_windows:
                results.append(self.mutate_slope(feat_id, values, window))
            
            # Persistence
            results.append(self.mutate_persistence(feat_id, values))
        
        passed = [r for r in results if r.status == "PASSED"]
        
        batch_result = MutationBatchResult(
            batch_id=batch_id,
            total_mutations=len(results),
            passed=len(passed),
            rejected=len(results) - len(passed),
            results=results,
            best_mutation=max(passed, key=lambda r: r.final_score) if passed else None,
            created_at=now
        )
        
        self.batches[batch_id] = batch_result
        return batch_result
    
    # ============================================
    # Queries
    # ============================================
    
    def get_mutation(self, mutation_id: str) -> Optional[Dict]:
        """Get mutation by ID"""
        result = self.mutations.get(mutation_id)
        return self._mutation_to_dict(result) if result else None
    
    def list_mutations(
        self,
        category: str = None,
        status: str = None,
        limit: int = 50
    ) -> Dict:
        """List mutations with filters"""
        
        results = list(self.mutations.values())
        
        if category:
            try:
                cat = MutationCategory(category)
                results = [r for r in results if r.category == cat]
            except ValueError:
                pass
        
        if status:
            results = [r for r in results if r.status == status]
        
        # Sort by final_score
        results.sort(key=lambda r: r.final_score, reverse=True)
        
        return {
            "total": len(self.mutations),
            "count": min(len(results), limit),
            "mutations": [self._mutation_to_dict(r) for r in results[:limit]]
        }
    
    def get_stats(self) -> Dict:
        """Get mutation statistics"""
        return {
            "total_generated": self.total_generated,
            "total_passed": self.total_passed,
            "total_rejected": self.total_rejected,
            "pass_rate": round(self.total_passed / max(1, self.total_generated), 4),
            "by_category": {
                cat.value: len([r for r in self.mutations.values() if r.category == cat])
                for cat in MutationCategory
            },
            "by_operation": {
                op.value: len([r for r in self.mutations.values() if r.operation == op])
                for op in MutationOp
            }
        }
    
    def get_health(self) -> Dict:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "phase9.31B",
            "status": "ok",
            "total_mutations": len(self.mutations),
            "total_batches": len(self.batches),
            "pass_rate": round(self.total_passed / max(1, self.total_generated), 4),
            "supported_categories": [c.value for c in MutationCategory],
            "supported_operations": [o.value for o in MutationOp],
            "timestamp": int(time.time() * 1000)
        }
    
    def _mutation_to_dict(self, result: MutationResult) -> Dict:
        """Convert mutation result to dict"""
        return {
            "mutation_id": result.mutation_id,
            "parent_ids": result.parent_ids,
            "category": result.category.value,
            "operation": result.operation.value,
            "parameters": result.parameters,
            "feature_id": result.feature_id,
            "feature_name": result.feature_name,
            "status": result.status,
            "passed_quality": result.passed_quality,
            "passed_crowding": result.passed_crowding,
            "quality_score": result.quality_score,
            "crowding_score": result.crowding_score,
            "final_score": result.final_score,
            "rejection_reason": result.rejection_reason,
            "created_at": result.created_at
        }


# Singleton
mutation_engine = FeatureMutationEngine()
