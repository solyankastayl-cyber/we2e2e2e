"""
Alpha Registry Routes
=====================

Phase 9.28 - API endpoints for alpha registry.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import alpha_registry_service


router = APIRouter(prefix="/api/alpha", tags=["alpha-registry"])


# ============================================
# Request Models
# ============================================

class RegisterAlphaRequest(BaseModel):
    """Request to register alpha"""
    name: str
    family: str = Field("EXPERIMENTAL", description="Alpha family")
    created_by: str = Field("HUMAN", description="Creation source")
    feature_ids: Optional[List[str]] = None
    asset_classes: Optional[List[str]] = None
    timeframes: Optional[List[str]] = None
    parent_alpha_id: Optional[str] = None
    description: str = ""
    tags: Optional[List[str]] = None
    check_clones: bool = True


class UpdateAlphaRequest(BaseModel):
    """Request to update alpha"""
    name: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    profit_factor: Optional[float] = None
    win_rate: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown: Optional[float] = None
    stability_score: Optional[float] = None
    utility_score: Optional[float] = None
    final_score: Optional[float] = None


class UpdateStatusRequest(BaseModel):
    """Request to update status"""
    status: str
    notes: str = ""


class AddValidationRequest(BaseModel):
    """Request to add validation"""
    validation_run_id: str
    datasets: List[str]
    asset_results: Dict[str, Dict[str, float]]
    verdict: str


class SimilarityRequest(BaseModel):
    """Request to compute similarity"""
    alpha_a_id: str
    alpha_b_id: str
    returns_a: Optional[List[float]] = None
    returns_b: Optional[List[float]] = None


class UpdateBudgetRequest(BaseModel):
    """Request to update family budget"""
    max_core: Optional[int] = None
    max_shadow: Optional[int] = None
    max_sandbox: Optional[int] = None
    target_share: Optional[float] = None


# ============================================
# Health Check
# ============================================

@router.get("/health")
async def health_check():
    """Health check for alpha registry"""
    return alpha_registry_service.get_health()


# ============================================
# Alpha CRUD
# ============================================

@router.post("/register")
async def register_alpha(request: RegisterAlphaRequest):
    """Register a new alpha"""
    return alpha_registry_service.register_alpha(
        name=request.name,
        family=request.family,
        created_by=request.created_by,
        feature_ids=request.feature_ids,
        asset_classes=request.asset_classes,
        timeframes=request.timeframes,
        parent_alpha_id=request.parent_alpha_id,
        description=request.description,
        tags=request.tags,
        check_clones=request.check_clones
    )


@router.get("/list")
async def list_alphas(
    family: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """List alphas with optional filters"""
    return alpha_registry_service.list_alphas(
        family=family,
        status=status,
        limit=limit,
        offset=offset
    )


@router.get("/{alpha_id}")
async def get_alpha(alpha_id: str):
    """Get alpha by ID"""
    result = alpha_registry_service.get_alpha(alpha_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Alpha not found")
    
    return result


@router.put("/{alpha_id}")
async def update_alpha(alpha_id: str, request: UpdateAlphaRequest):
    """Update alpha"""
    result = alpha_registry_service.update_alpha(
        alpha_id,
        **{k: v for k, v in request.dict().items() if v is not None}
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Alpha not found")
    
    return result


@router.delete("/{alpha_id}")
async def delete_alpha(alpha_id: str):
    """Delete alpha"""
    return alpha_registry_service.delete_alpha(alpha_id)


# ============================================
# Status Management
# ============================================

@router.post("/{alpha_id}/status")
async def update_status(alpha_id: str, request: UpdateStatusRequest):
    """Update alpha status"""
    result = alpha_registry_service.update_status(
        alpha_id=alpha_id,
        new_status=request.status,
        notes=request.notes
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/{alpha_id}/can-promote/{target_status}")
async def check_promotion(alpha_id: str, target_status: str):
    """Check if alpha can be promoted"""
    return alpha_registry_service.check_promotion(alpha_id, target_status)


# ============================================
# Lineage
# ============================================

@router.get("/{alpha_id}/lineage")
async def get_lineage(alpha_id: str):
    """Get lineage info"""
    result = alpha_registry_service.get_lineage(alpha_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Alpha not found")
    
    return result


@router.get("/root/{root_idea_id}")
async def get_lineage_tree(root_idea_id: str):
    """Get full lineage tree from root idea"""
    return alpha_registry_service.get_lineage_tree(root_idea_id)


@router.get("/{alpha_id}/ancestors")
async def get_ancestors(alpha_id: str):
    """Get all ancestors"""
    return alpha_registry_service.get_ancestors(alpha_id)


@router.get("/{alpha_id}/descendants")
async def get_descendants(alpha_id: str):
    """Get all descendants"""
    return alpha_registry_service.get_descendants(alpha_id)


# ============================================
# Validation
# ============================================

@router.post("/{alpha_id}/validation")
async def add_validation(alpha_id: str, request: AddValidationRequest):
    """Add validation link"""
    result = alpha_registry_service.add_validation(
        alpha_id=alpha_id,
        validation_run_id=request.validation_run_id,
        datasets=request.datasets,
        asset_results=request.asset_results,
        verdict=request.verdict
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.get("/{alpha_id}/validation")
async def get_validation_history(alpha_id: str):
    """Get validation history"""
    return alpha_registry_service.get_validation_history(alpha_id)


# ============================================
# Versions
# ============================================

@router.get("/{alpha_id}/versions")
async def get_versions(alpha_id: str):
    """Get all versions"""
    return alpha_registry_service.get_versions(alpha_id)


# ============================================
# Similarity
# ============================================

@router.post("/similarity")
async def compute_similarity(request: SimilarityRequest):
    """Compute similarity between two alphas"""
    result = alpha_registry_service.compute_similarity(
        request.alpha_a_id,
        request.alpha_b_id,
        returns_a=request.returns_a,
        returns_b=request.returns_b
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.get("/{alpha_id}/clones")
async def check_clones(alpha_id: str):
    """Check for clones"""
    return alpha_registry_service.check_clones(alpha_id)


@router.get("/{alpha_id}/crowded")
async def get_crowded(alpha_id: str):
    """Get crowded alphas"""
    return alpha_registry_service.get_crowded(alpha_id)


# ============================================
# Family Budgets
# ============================================

@router.get("/family/budgets")
async def get_family_budgets():
    """Get all family budgets"""
    return alpha_registry_service.get_family_budgets()


@router.put("/family/{family}/budget")
async def update_family_budget(family: str, request: UpdateBudgetRequest):
    """Update family budget"""
    result = alpha_registry_service.update_family_budget(
        family=family,
        max_core=request.max_core,
        max_shadow=request.max_shadow,
        max_sandbox=request.max_sandbox,
        target_share=request.target_share
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============================================
# Statistics
# ============================================

@router.get("/stats/overview")
async def get_stats():
    """Get registry statistics"""
    return alpha_registry_service.get_stats()
