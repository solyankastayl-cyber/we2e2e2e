"""
Orthogonal Alpha Routes
=======================

Phase 9.3G - API endpoints for alpha orthogonalization.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import orthogonal_service


router = APIRouter(prefix="/api/orthogonal-alpha", tags=["orthogonal-alpha"])


# ============================================
# Request/Response Models
# ============================================

class CreateSessionRequest(BaseModel):
    """Request to create session"""
    session_id: Optional[str] = None
    method: str = Field("factor_model", description="gram_schmidt, pca, factor_model, hierarchical")
    redundancy_threshold: float = Field(0.90, description="Correlation threshold for redundancy")
    crowding_threshold: float = Field(0.70, description="Correlation threshold for crowding")


class AddAlphaRequest(BaseModel):
    """Request to add single alpha"""
    alpha_id: str
    returns: List[float] = Field(..., description="Daily returns series")
    family: str = Field("", description="Alpha family (e.g., momentum, reversal)")


class AddAlphasBatchRequest(BaseModel):
    """Request to add multiple alphas"""
    alphas: List[Dict[str, Any]]


class BuildPortfolioRequest(BaseModel):
    """Request to build portfolio"""
    target_volatility: float = Field(0.15, description="Target annualized volatility")


# ============================================
# Health Check
# ============================================

@router.get("/health")
async def health_check():
    """Health check for orthogonal alpha service"""
    return orthogonal_service.get_health()


# ============================================
# Session Management
# ============================================

@router.post("/session")
async def create_session(request: CreateSessionRequest):
    """Create new orthogonalization session"""
    session_id = orthogonal_service.create_session(
        session_id=request.session_id,
        method=request.method,
        redundancy_threshold=request.redundancy_threshold,
        crowding_threshold=request.crowding_threshold
    )
    return {
        "session_id": session_id,
        "method": request.method,
        "message": "Session created"
    }


@router.get("/sessions")
async def list_sessions():
    """List all sessions"""
    return orthogonal_service.list_sessions()


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session info"""
    return orthogonal_service.get_alphas(session_id)


# ============================================
# Alpha Management
# ============================================

@router.post("/session/{session_id}/alpha")
async def add_alpha(session_id: str, request: AddAlphaRequest):
    """Add alpha to session"""
    result = orthogonal_service.add_alpha(
        session_id=session_id,
        alpha_id=request.alpha_id,
        returns=request.returns,
        family=request.family
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.post("/session/{session_id}/alphas")
async def add_alphas_batch(session_id: str, request: AddAlphasBatchRequest):
    """Add multiple alphas to session"""
    result = orthogonal_service.add_alphas_batch(
        session_id=session_id,
        alphas=request.alphas
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.get("/session/{session_id}/alphas")
async def get_alphas(session_id: str):
    """Get all alphas in session"""
    result = orthogonal_service.get_alphas(session_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


# ============================================
# Orthogonalization
# ============================================

@router.post("/session/{session_id}/orthogonalize")
async def run_orthogonalization(session_id: str):
    """Run orthogonalization on session"""
    result = orthogonal_service.run_orthogonalization(session_id)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============================================
# Analysis
# ============================================

@router.get("/session/{session_id}/correlations")
async def get_correlations(session_id: str, residuals: bool = False):
    """Get correlation matrix"""
    result = orthogonal_service.get_correlation_matrix(session_id, use_residuals=residuals)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.get("/session/{session_id}/crowded-pairs")
async def get_crowded_pairs(session_id: str):
    """Get crowded pairs"""
    result = orthogonal_service.get_crowded_pairs(session_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.get("/session/{session_id}/redundant")
async def get_redundant_alphas(session_id: str):
    """Get redundant alphas"""
    result = orthogonal_service.get_redundant_alphas(session_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


# ============================================
# Portfolio
# ============================================

@router.post("/session/{session_id}/portfolio")
async def build_portfolio(session_id: str, request: BuildPortfolioRequest):
    """Build orthogonal portfolio"""
    result = orthogonal_service.build_portfolio(
        session_id=session_id,
        target_volatility=request.target_volatility
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result
