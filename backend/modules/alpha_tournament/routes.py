"""
Alpha Tournament Routes
=======================

Phase 9.29 - API endpoints for alpha tournament system.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import tournament_service


router = APIRouter(prefix="/api/tournament", tags=["alpha-tournament"])


# ============================================
# Request Models
# ============================================

class AdmitCandidateRequest(BaseModel):
    """Request to admit candidate"""
    alpha_id: str
    name: str
    family: str = "EXPERIMENTAL"
    asset_classes: List[str] = ["CRYPTO"]
    timeframes: List[str] = ["1D"]
    validation_score: float = 0.7
    orthogonality_score: float = 0.6
    crowding_score: float = 0.3
    registry_status: str = "VALIDATED"


class EvaluateScorecardRequest(BaseModel):
    """Request to evaluate scorecard"""
    profit_factor: float = 1.5
    sharpe: float = 1.0
    max_drawdown: float = 0.15
    cagr: float = 0.20
    win_rate: float = 0.55
    stability_score: float = 0.7
    regime_robustness: float = 0.6


class CreateBucketRequest(BaseModel):
    """Request to create bucket"""
    bucket_id: str
    family: str
    asset_class: str = "ALL"
    timeframe: str = "1D"


class UpdateConfigRequest(BaseModel):
    """Request to update config"""
    min_validation_score: Optional[float] = None
    promote_threshold: Optional[float] = None
    max_promotions_per_cycle: Optional[int] = None


class RunTournamentRequest(BaseModel):
    """Request to run tournament"""
    bucket_ids: Optional[List[str]] = None


# ============================================
# Health Check
# ============================================

@router.get("/health")
async def health_check():
    """Health check for tournament service"""
    return tournament_service.get_health()


@router.get("/stats")
async def get_stats():
    """Get tournament statistics"""
    return tournament_service.get_stats()


# ============================================
# Candidate Management
# ============================================

@router.post("/admit")
async def admit_candidate(request: AdmitCandidateRequest):
    """Admit a candidate to tournament"""
    return tournament_service.admit_candidate(
        alpha_id=request.alpha_id,
        name=request.name,
        family=request.family,
        asset_classes=request.asset_classes,
        timeframes=request.timeframes,
        validation_score=request.validation_score,
        orthogonality_score=request.orthogonality_score,
        crowding_score=request.crowding_score,
        registry_status=request.registry_status
    )


@router.get("/candidates")
async def get_candidates(bucket_id: Optional[str] = None):
    """Get all candidates"""
    return tournament_service.get_candidates(bucket_id)


# ============================================
# Scorecard Management
# ============================================

@router.post("/scorecard/{alpha_id}")
async def evaluate_scorecard(alpha_id: str, request: EvaluateScorecardRequest):
    """Evaluate scorecard for candidate"""
    result = tournament_service.evaluate_scorecard(
        alpha_id=alpha_id,
        profit_factor=request.profit_factor,
        sharpe=request.sharpe,
        max_drawdown=request.max_drawdown,
        cagr=request.cagr,
        win_rate=request.win_rate,
        stability_score=request.stability_score,
        regime_robustness=request.regime_robustness
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.get("/scorecard/{alpha_id}")
async def get_scorecard(alpha_id: str):
    """Get scorecard for alpha"""
    result = tournament_service.get_scorecard(alpha_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Scorecard not found")
    
    return result


# ============================================
# Bucket Management
# ============================================

@router.get("/buckets")
async def get_buckets():
    """Get all tournament buckets"""
    return tournament_service.get_buckets()


@router.get("/buckets/{bucket_id}")
async def get_bucket_results(bucket_id: str):
    """Get bucket results"""
    result = tournament_service.get_bucket_results(bucket_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Bucket not found")
    
    return result


@router.post("/buckets")
async def create_bucket(request: CreateBucketRequest):
    """Create a new bucket"""
    result = tournament_service.create_bucket(
        bucket_id=request.bucket_id,
        family=request.family,
        asset_class=request.asset_class,
        timeframe=request.timeframe
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# ============================================
# Tournament Execution
# ============================================

@router.post("/run")
async def run_tournament(request: RunTournamentRequest):
    """Run complete tournament cycle"""
    return tournament_service.run_tournament(request.bucket_ids)


@router.post("/run/{bucket_id}")
async def run_bucket_tournament(bucket_id: str):
    """Run tournament for single bucket"""
    return tournament_service.run_bucket_tournament(bucket_id)


@router.get("/runs")
async def list_runs(limit: int = 20):
    """List recent tournament runs"""
    return tournament_service.list_runs(limit)


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get tournament run by ID"""
    result = tournament_service.get_run(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return result


# ============================================
# History
# ============================================

@router.get("/history/{alpha_id}")
async def get_alpha_history(alpha_id: str):
    """Get tournament history for alpha"""
    result = tournament_service.get_alpha_history(alpha_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Alpha history not found")
    
    return result


# ============================================
# Management
# ============================================

@router.post("/clear")
async def clear_candidates():
    """Clear all candidates for new cycle"""
    return tournament_service.clear_candidates()


@router.get("/config")
async def get_config():
    """Get current configuration"""
    return tournament_service.get_config()


@router.put("/config")
async def update_config(request: UpdateConfigRequest):
    """Update tournament configuration"""
    return tournament_service.update_config(
        min_validation_score=request.min_validation_score,
        promote_threshold=request.promote_threshold,
        max_promotions_per_cycle=request.max_promotions_per_cycle
    )
