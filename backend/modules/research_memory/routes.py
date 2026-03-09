"""
Research Memory Routes
======================

Phase 9.32 - API endpoints for research memory system.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import research_memory_service


router = APIRouter(prefix="/api/memory", tags=["research-memory"])


# ============================================
# Request Models
# ============================================

class FeatureFailureRequest(BaseModel):
    feature_id: str
    feature_name: str
    family: str = ""
    outcome: str = "FAILED"
    failure_reasons: Optional[List[str]] = None
    metrics: Optional[Dict[str, float]] = None


class AlphaFailureRequest(BaseModel):
    alpha_id: str
    alpha_name: str
    family: str = ""
    outcome: str = "FAILED"
    failure_reasons: Optional[List[str]] = None
    root_causes: Optional[List[str]] = None
    metrics: Optional[Dict[str, float]] = None
    regime: str = ""


class MutationFailureRequest(BaseModel):
    mutation_id: str
    mutation_name: str
    parent_features: Optional[List[str]] = None
    outcome: str = "FAILED"
    failure_reasons: Optional[List[str]] = None


class StrategyFailureRequest(BaseModel):
    strategy_id: str
    strategy_name: str
    family: str = ""
    outcome: str = "FAILED"
    failure_reasons: Optional[List[str]] = None
    root_causes: Optional[List[str]] = None
    metrics: Optional[Dict[str, float]] = None
    regime: str = ""
    asset_class: str = ""


class TournamentLossRequest(BaseModel):
    alpha_id: str
    alpha_name: str
    family: str = ""
    metrics: Optional[Dict[str, float]] = None
    lost_to: str = ""
    reason: str = ""


class StressFailureRequest(BaseModel):
    entity_id: str
    entity_name: str
    scenario: str = ""
    family: str = ""
    metrics: Optional[Dict[str, float]] = None
    failure_reasons: Optional[List[str]] = None


class AutopsyRecordRequest(BaseModel):
    autopsy_report: Dict[str, Any]


class MemoryCheckRequest(BaseModel):
    entity_name: str
    family: str = ""
    regime: str = ""
    tags: Optional[List[str]] = None
    category: Optional[str] = None


# ============================================
# Health
# ============================================

@router.get("/health")
async def health_check():
    return research_memory_service.get_health()


# ============================================
# Record Failures
# ============================================

@router.post("/record/feature")
async def record_feature_failure(request: FeatureFailureRequest):
    """Record a failed feature"""
    return research_memory_service.record_feature_failure(
        feature_id=request.feature_id,
        feature_name=request.feature_name,
        family=request.family,
        outcome=request.outcome,
        failure_reasons=request.failure_reasons,
        metrics=request.metrics
    )


@router.post("/record/alpha")
async def record_alpha_failure(request: AlphaFailureRequest):
    """Record a failed alpha"""
    return research_memory_service.record_alpha_failure(
        alpha_id=request.alpha_id,
        alpha_name=request.alpha_name,
        family=request.family,
        outcome=request.outcome,
        failure_reasons=request.failure_reasons,
        root_causes=request.root_causes,
        metrics=request.metrics,
        regime=request.regime
    )


@router.post("/record/mutation")
async def record_mutation_failure(request: MutationFailureRequest):
    """Record a failed mutation"""
    return research_memory_service.record_mutation_failure(
        mutation_id=request.mutation_id,
        mutation_name=request.mutation_name,
        parent_features=request.parent_features,
        outcome=request.outcome,
        failure_reasons=request.failure_reasons
    )


@router.post("/record/strategy")
async def record_strategy_failure(request: StrategyFailureRequest):
    """Record a failed strategy"""
    return research_memory_service.record_strategy_failure(
        strategy_id=request.strategy_id,
        strategy_name=request.strategy_name,
        family=request.family,
        outcome=request.outcome,
        failure_reasons=request.failure_reasons,
        root_causes=request.root_causes,
        metrics=request.metrics,
        regime=request.regime,
        asset_class=request.asset_class
    )


@router.post("/record/tournament")
async def record_tournament_loss(request: TournamentLossRequest):
    """Record a tournament loss"""
    return research_memory_service.record_tournament_loss(
        alpha_id=request.alpha_id,
        alpha_name=request.alpha_name,
        family=request.family,
        metrics=request.metrics,
        lost_to=request.lost_to,
        reason=request.reason
    )


@router.post("/record/stress")
async def record_stress_failure(request: StressFailureRequest):
    """Record a stress test failure"""
    return research_memory_service.record_stress_failure(
        entity_id=request.entity_id,
        entity_name=request.entity_name,
        scenario=request.scenario,
        family=request.family,
        metrics=request.metrics,
        failure_reasons=request.failure_reasons
    )


@router.post("/record/autopsy")
async def record_from_autopsy(request: AutopsyRecordRequest):
    """Record failure from autopsy report"""
    return research_memory_service.record_from_autopsy(request.autopsy_report)


# ============================================
# Memory Lookup
# ============================================

@router.post("/check")
async def check_memory(request: MemoryCheckRequest):
    """Check if entity matches existing memory"""
    return research_memory_service.check_memory(
        entity_name=request.entity_name,
        family=request.family,
        regime=request.regime,
        tags=request.tags,
        category=request.category
    )


# ============================================
# Query
# ============================================

@router.get("/entries")
async def get_entries(
    category: Optional[str] = None,
    outcome: Optional[str] = None,
    family: Optional[str] = None,
    regime: Optional[str] = None,
    limit: int = 50
):
    """Get memory entries"""
    return research_memory_service.get_entries(
        category=category,
        outcome=outcome,
        family=family,
        regime=regime,
        limit=limit
    )


@router.get("/entry/{entry_id}")
async def get_entry(entry_id: str):
    """Get single memory entry"""
    result = research_memory_service.get_entry(entry_id)
    if not result:
        raise HTTPException(status_code=404, detail="Entry not found")
    return result


@router.get("/patterns")
async def get_patterns(min_occurrences: int = 1):
    """Get failure patterns"""
    return research_memory_service.get_patterns(min_occurrences)


@router.get("/summary")
async def get_summary():
    """Get memory summary"""
    return research_memory_service.get_summary()
