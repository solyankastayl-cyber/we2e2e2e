"""
Feature Mutation Routes
=======================

Phase 9.31B - API endpoints for feature mutation engine.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple

from .mutation import mutation_engine


router = APIRouter(prefix="/api/mutation", tags=["feature-mutation"])


# ============================================
# Request Models
# ============================================

class ArithmeticMutationRequest(BaseModel):
    feature_a_id: str
    feature_b_id: str
    values_a: List[float]
    values_b: List[float]
    operation: str = "ADD"  # ADD, SUBTRACT, MULTIPLY, DIVIDE


class TemporalMutationRequest(BaseModel):
    feature_id: str
    values: List[float]
    operation: str = "LAG"  # LAG, SLOPE, PERSISTENCE
    lag_periods: int = 5
    window: int = 10
    threshold: float = 0.0


class RegimeMutationRequest(BaseModel):
    feature_id: str
    values: List[float]
    regime_indicators: List[int]
    target_regime: int = 1


class CrossAssetMutationRequest(BaseModel):
    feature_a_id: str
    feature_b_id: str
    values_a: List[float]
    values_b: List[float]
    asset_a: str = "BTC"
    asset_b: str = "SPX"


class BatchArithmeticRequest(BaseModel):
    feature_pairs: List[Dict[str, Any]]
    # Each dict: {feature_a_id, feature_b_id, values_a, values_b}


class BatchTemporalRequest(BaseModel):
    features: List[Dict[str, Any]]
    # Each dict: {feature_id, values}
    lag_periods: Optional[List[int]] = None
    slope_windows: Optional[List[int]] = None


class CrowdingCheckRequest(BaseModel):
    mutation_id: str
    existing_features: Dict[str, List[float]]


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    return mutation_engine.get_health()


@router.get("/stats")
async def get_stats():
    return mutation_engine.get_stats()


# ============================================
# Arithmetic Mutations
# ============================================

@router.post("/arithmetic")
async def run_arithmetic_mutation(request: ArithmeticMutationRequest):
    """Run a single arithmetic mutation"""
    
    op = request.operation.upper()
    
    if op == "ADD":
        result = mutation_engine.mutate_add(
            request.feature_a_id, request.feature_b_id,
            request.values_a, request.values_b
        )
    elif op == "SUBTRACT":
        result = mutation_engine.mutate_subtract(
            request.feature_a_id, request.feature_b_id,
            request.values_a, request.values_b
        )
    elif op == "MULTIPLY":
        result = mutation_engine.mutate_multiply(
            request.feature_a_id, request.feature_b_id,
            request.values_a, request.values_b
        )
    elif op == "DIVIDE":
        result = mutation_engine.mutate_divide(
            request.feature_a_id, request.feature_b_id,
            request.values_a, request.values_b
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown operation: {op}")
    
    return mutation_engine._mutation_to_dict(result)


@router.post("/arithmetic/batch")
async def run_batch_arithmetic(request: BatchArithmeticRequest):
    """Run batch of arithmetic mutations"""
    
    pairs = []
    for pair in request.feature_pairs:
        pairs.append((
            pair.get("feature_a_id"),
            pair.get("feature_b_id"),
            pair.get("values_a", []),
            pair.get("values_b", [])
        ))
    
    batch = mutation_engine.run_batch_arithmetic(pairs)
    
    return {
        "batch_id": batch.batch_id,
        "total_mutations": batch.total_mutations,
        "passed": batch.passed,
        "rejected": batch.rejected,
        "best_mutation": mutation_engine._mutation_to_dict(batch.best_mutation) if batch.best_mutation else None,
        "results": [mutation_engine._mutation_to_dict(r) for r in batch.results]
    }


# ============================================
# Temporal Mutations
# ============================================

@router.post("/temporal")
async def run_temporal_mutation(request: TemporalMutationRequest):
    """Run a single temporal mutation"""
    
    op = request.operation.upper()
    
    if op == "LAG":
        result = mutation_engine.mutate_lag(
            request.feature_id, request.values, request.lag_periods
        )
    elif op == "SLOPE":
        result = mutation_engine.mutate_slope(
            request.feature_id, request.values, request.window
        )
    elif op == "PERSISTENCE":
        result = mutation_engine.mutate_persistence(
            request.feature_id, request.values,
            request.threshold, request.window
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown operation: {op}")
    
    return mutation_engine._mutation_to_dict(result)


@router.post("/temporal/batch")
async def run_batch_temporal(request: BatchTemporalRequest):
    """Run batch of temporal mutations"""
    
    features = []
    for feat in request.features:
        features.append((
            feat.get("feature_id"),
            feat.get("values", [])
        ))
    
    batch = mutation_engine.run_batch_temporal(
        features,
        request.lag_periods,
        request.slope_windows
    )
    
    return {
        "batch_id": batch.batch_id,
        "total_mutations": batch.total_mutations,
        "passed": batch.passed,
        "rejected": batch.rejected,
        "best_mutation": mutation_engine._mutation_to_dict(batch.best_mutation) if batch.best_mutation else None,
        "results": [mutation_engine._mutation_to_dict(r) for r in batch.results]
    }


# ============================================
# Regime Mutations
# ============================================

@router.post("/regime")
async def run_regime_mutation(request: RegimeMutationRequest):
    """Run a regime-conditional mutation"""
    
    result = mutation_engine.mutate_regime_mask(
        request.feature_id,
        request.values,
        request.regime_indicators,
        request.target_regime
    )
    
    return mutation_engine._mutation_to_dict(result)


# ============================================
# Cross-Asset Mutations
# ============================================

@router.post("/cross-asset")
async def run_cross_asset_mutation(request: CrossAssetMutationRequest):
    """Run a cross-asset relative mutation"""
    
    result = mutation_engine.mutate_relative(
        request.feature_a_id, request.feature_b_id,
        request.values_a, request.values_b,
        request.asset_a, request.asset_b
    )
    
    return mutation_engine._mutation_to_dict(result)


# ============================================
# Crowding Check
# ============================================

@router.post("/crowding-check")
async def check_crowding(request: CrowdingCheckRequest):
    """Check if mutation is crowded with existing features"""
    
    return mutation_engine.check_crowding(
        request.mutation_id,
        request.existing_features
    )


# ============================================
# Query Mutations
# ============================================

@router.get("/mutations")
async def list_mutations(
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50
):
    """List mutations with filters"""
    return mutation_engine.list_mutations(category, status, limit)


@router.get("/mutation/{mutation_id}")
async def get_mutation(mutation_id: str):
    """Get single mutation"""
    result = mutation_engine.get_mutation(mutation_id)
    if not result:
        raise HTTPException(status_code=404, detail="Mutation not found")
    return result
