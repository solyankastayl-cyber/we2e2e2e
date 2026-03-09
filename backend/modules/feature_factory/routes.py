"""
Feature Factory Routes
======================

Phase 9.31 - API endpoints for feature factory.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import feature_factory_service


router = APIRouter(prefix="/api/features", tags=["feature-factory"])


# ============================================
# Request Models
# ============================================

class RegisterFeatureRequest(BaseModel):
    """Request to register feature"""
    name: str
    family: str = "EXPERIMENTAL"
    feature_type: str = "DERIVED"
    source_fields: Optional[List[str]] = None
    formula: str = ""
    description: str = ""
    parent_feature_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class GenerateBaseRequest(BaseModel):
    """Request to generate base features"""
    ohlcv: Dict[str, List[float]]


class QualityCheckRequest(BaseModel):
    """Request for quality check"""
    feature_id: str
    values: List[float]


class BatchQualityRequest(BaseModel):
    """Request for batch quality check"""
    feature_values: Dict[str, List[float]]


class ScoreFeatureRequest(BaseModel):
    """Request to score feature"""
    values: Optional[List[float]] = None
    target_returns: Optional[List[float]] = None


class UpdateStatusRequest(BaseModel):
    """Request to update status"""
    status: str


class CrowdingRequest(BaseModel):
    """Request to compute crowding"""
    feature_a_id: str
    feature_b_id: str
    values_a: List[float]
    values_b: List[float]


# ============================================
# Health Check
# ============================================

@router.get("/health")
async def health_check():
    """Health check for feature factory"""
    return feature_factory_service.get_health()


@router.get("/stats")
async def get_stats():
    """Get feature factory statistics"""
    return feature_factory_service.get_stats()


# ============================================
# Feature CRUD
# ============================================

@router.post("/register")
async def register_feature(request: RegisterFeatureRequest):
    """Register a new feature"""
    return feature_factory_service.register_feature(
        name=request.name,
        family=request.family,
        feature_type=request.feature_type,
        source_fields=request.source_fields,
        formula=request.formula,
        description=request.description,
        parent_feature_ids=request.parent_feature_ids,
        tags=request.tags
    )


@router.get("/list")
async def list_features(
    family: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """List features with filters"""
    return feature_factory_service.list_features(
        family=family,
        status=status,
        limit=limit
    )


@router.get("/{feature_id}")
async def get_feature(feature_id: str):
    """Get feature by ID"""
    result = feature_factory_service.get_feature(feature_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Feature not found")
    
    return result


# ============================================
# Feature Generation
# ============================================

@router.post("/generate-base")
async def generate_base_features(request: GenerateBaseRequest):
    """Generate base features from OHLCV data"""
    return feature_factory_service.generate_base_features(request.ohlcv)


# ============================================
# Quality Control
# ============================================

@router.post("/quality-check")
async def run_quality_check(request: QualityCheckRequest):
    """Run quality check on a feature"""
    return feature_factory_service.run_quality_check(
        feature_id=request.feature_id,
        values=request.values
    )


@router.post("/batch-quality-check")
async def run_batch_quality_check(request: BatchQualityRequest):
    """Run quality check on multiple features"""
    return feature_factory_service.run_batch_quality_check(request.feature_values)


# ============================================
# Scoring
# ============================================

@router.post("/{feature_id}/score")
async def score_feature(feature_id: str, request: ScoreFeatureRequest):
    """Score a feature"""
    result = feature_factory_service.score_feature(
        feature_id=feature_id,
        values=request.values,
        target_returns=request.target_returns
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


# ============================================
# Status Management
# ============================================

@router.post("/{feature_id}/status")
async def update_status(feature_id: str, request: UpdateStatusRequest):
    """Update feature status"""
    result = feature_factory_service.update_status(
        feature_id=feature_id,
        new_status=request.status
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============================================
# Crowding
# ============================================

@router.post("/crowding")
async def compute_crowding(request: CrowdingRequest):
    """Compute crowding between two features"""
    result = feature_factory_service.compute_crowding(
        feature_a_id=request.feature_a_id,
        feature_b_id=request.feature_b_id,
        values_a=request.values_a,
        values_b=request.values_b
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============================================
# Family Budgets
# ============================================

@router.get("/families/budgets")
async def get_family_budgets():
    """Get all family budgets"""
    return feature_factory_service.get_family_budgets()
