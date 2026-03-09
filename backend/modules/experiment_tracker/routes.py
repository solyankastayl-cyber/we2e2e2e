"""
Experiment Tracker Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from .engine import experiment_tracker


router = APIRouter(prefix="/api/experiments", tags=["experiment-tracker"])


class CreateExperimentRequest(BaseModel):
    name: str
    dataset_version: str = ""
    strategies: List[str] = []
    assets: List[str] = []
    parameters: Dict[str, Any] = {}
    tags: List[str] = []


class CompleteExperimentRequest(BaseModel):
    results: Dict[str, Any] = {}
    metrics: Dict[str, float] = {}
    notes: str = ""


@router.get("/health")
async def health_check():
    return experiment_tracker.get_health()


@router.get("/stats")
async def get_stats():
    return experiment_tracker.get_stats()


@router.get("")
async def list_experiments(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 50
):
    return {"experiments": experiment_tracker.list_all(status, tag, limit)}


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str):
    exp = experiment_tracker.get(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment_tracker._to_dict(exp)


@router.post("")
async def create_experiment(request: CreateExperimentRequest):
    # Validate name is not empty
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Experiment name is required")
    
    exp = experiment_tracker.create(
        name=request.name.strip(),
        dataset_version=request.dataset_version,
        strategies=request.strategies,
        assets=request.assets,
        parameters=request.parameters,
        tags=request.tags
    )
    return experiment_tracker._to_dict(exp)


@router.post("/{experiment_id}/start")
async def start_experiment(experiment_id: str):
    exp = experiment_tracker.start(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment_tracker._to_dict(exp)


@router.post("/{experiment_id}/complete")
async def complete_experiment(experiment_id: str, request: CompleteExperimentRequest):
    exp = experiment_tracker.complete(
        experiment_id,
        results=request.results,
        metrics=request.metrics,
        notes=request.notes
    )
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment_tracker._to_dict(exp)


@router.post("/{experiment_id}/fail")
async def fail_experiment(experiment_id: str, error: str = ""):
    exp = experiment_tracker.fail(experiment_id, error)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment_tracker._to_dict(exp)
