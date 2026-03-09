"""
Dataset Registry Routes
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from .engine import dataset_registry, Dataset, validate_dataset_consistency


router = APIRouter(prefix="/api/datasets", tags=["dataset-registry"])


class RegisterDatasetRequest(BaseModel):
    dataset_id: str
    name: str
    asset: str
    version: str = "1.0"
    start_date: str = ""
    end_date: str = ""
    rows: int = 0
    source: str = "internal"
    timeframe: str = "1D"
    columns: List[str] = []


@router.get("/health")
async def health_check():
    return dataset_registry.get_health()


@router.get("")
async def list_datasets(asset: Optional[str] = None):
    return {"datasets": dataset_registry.list_all(asset)}


@router.get("/{dataset_id}")
async def get_dataset(dataset_id: str):
    dataset = dataset_registry.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset_registry._to_dict(dataset)


@router.get("/{dataset_id}/versions")
async def get_versions(dataset_id: str):
    versions = dataset_registry.get_versions(dataset_id)
    return {"dataset_id": dataset_id, "versions": versions}


@router.post("")
async def register_dataset(request: RegisterDatasetRequest):
    dataset = Dataset(
        dataset_id=request.dataset_id,
        name=request.name,
        asset=request.asset,
        version=request.version,
        start_date=request.start_date,
        end_date=request.end_date,
        rows=request.rows,
        source=request.source,
        timeframe=request.timeframe,
        columns=request.columns
    )
    result = dataset_registry.register(dataset)
    if "error" in result and result["error"] == "consistency_check_failed":
        raise HTTPException(status_code=422, detail=result["validation"])
    return result


@router.post("/{dataset_id}/validate")
async def validate_checksum(dataset_id: str, checksum: str):
    valid = dataset_registry.validate_checksum(dataset_id, checksum)
    return {"dataset_id": dataset_id, "checksum": checksum, "valid": valid}


@router.post("/{dataset_id}/consistency")
async def check_consistency(dataset_id: str):
    """Run consistency checks on a dataset"""
    dataset = dataset_registry.get(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return validate_dataset_consistency(dataset)
