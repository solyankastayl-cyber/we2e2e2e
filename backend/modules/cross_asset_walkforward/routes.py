"""
Cross-Asset Walk-Forward Routes
===============================

API endpoints for cross-asset simulation.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from .service import cross_asset_service


router = APIRouter(prefix="/api/cross-wf", tags=["cross-asset-walkforward"])


# ============================================
# Request/Response Models
# ============================================

class RunRequest(BaseModel):
    """Request for single run"""
    asset: str = Field(..., description="Asset symbol (e.g., SPX, BTC)")
    mode: str = Field("full_system", description="Simulation mode")
    start_date: str = Field("", description="Start date (YYYY-MM-DD)")
    end_date: str = Field("", description="End date (YYYY-MM-DD)")
    initial_capital: float = Field(100000.0, description="Initial capital")


class BatchRunRequest(BaseModel):
    """Request for batch run"""
    assets: List[str] = Field(..., description="List of assets")
    mode: str = Field("full_system", description="Simulation mode")
    end_date: str = Field("", description="End date (optional)")
    initial_capital: float = Field(100000.0, description="Initial capital")


# ============================================
# Health Check
# ============================================

@router.get("/health")
async def health_check():
    """Health check for cross-asset walk-forward service"""
    return {
        "enabled": True,
        "version": "phase9.X",
        "status": "ok",
        "supported_assets": list(cross_asset_service.get_supported_assets().keys()),
        "supported_modes": [
            "core_only",
            "full_system",
            "full_hierarchical"
        ]
    }


# ============================================
# Single Run Endpoints
# ============================================

@router.post("/run")
async def start_run(request: RunRequest, background_tasks: BackgroundTasks):
    """Start a walk-forward run (async)"""
    try:
        result = await cross_asset_service.start_run(
            asset=request.asset,
            mode=request.mode,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-sync")
async def run_sync(request: RunRequest):
    """Run walk-forward synchronously and return results"""
    try:
        result = await cross_asset_service.run_sync(
            asset=request.asset,
            mode=request.mode,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{run_id}")
async def get_run_status(run_id: str):
    """Get run status"""
    result = cross_asset_service.get_run_status(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.get("/report/{run_id}")
async def get_report(run_id: str):
    """Get run report as JSON"""
    result = cross_asset_service.get_report(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    return result


@router.get("/report/{run_id}/markdown")
async def get_report_markdown(run_id: str):
    """Get run report as Markdown"""
    result = cross_asset_service.get_report_markdown(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"markdown": result}


# ============================================
# Batch Run Endpoints
# ============================================

@router.post("/run-batch")
async def start_batch_run(request: BatchRunRequest):
    """Start batch run across multiple assets"""
    try:
        result = await cross_asset_service.start_batch_run(
            assets=request.assets,
            mode=request.mode,
            end_date=request.end_date,
            initial_capital=request.initial_capital
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{batch_id}/status")
async def get_batch_status(batch_id: str):
    """Get batch run status"""
    result = cross_asset_service.get_batch_status(batch_id)
    if not result:
        raise HTTPException(status_code=404, detail="Batch not found")
    return result


@router.get("/batch/{batch_id}/summary")
async def get_batch_summary(batch_id: str):
    """Get batch summary"""
    result = cross_asset_service.get_batch_summary(batch_id)
    if not result:
        raise HTTPException(status_code=404, detail="Batch not found")
    return result


# ============================================
# Comparison Endpoints
# ============================================

@router.get("/comparison/{batch_id}")
async def get_comparison(batch_id: str):
    """Get cross-asset comparison for batch"""
    result = cross_asset_service.generate_comparison(batch_id)
    if not result:
        raise HTTPException(status_code=404, detail="Comparison not available")
    return result


@router.get("/comparison/{batch_id}/markdown")
async def get_comparison_markdown(batch_id: str):
    """Get comparison as Markdown"""
    result = cross_asset_service.get_comparison_markdown(batch_id)
    if not result:
        raise HTTPException(status_code=404, detail="Comparison not available")
    return {"markdown": result}


# ============================================
# Registry Endpoints
# ============================================

@router.get("/assets")
async def get_supported_assets():
    """Get all supported assets"""
    return cross_asset_service.get_supported_assets()


@router.get("/assets/{asset}")
async def get_asset_info(asset: str):
    """Get info for specific asset"""
    result = cross_asset_service.get_asset_info(asset)
    if not result:
        raise HTTPException(status_code=404, detail="Asset not found")
    return result


@router.get("/runs")
async def list_runs():
    """List all runs"""
    return cross_asset_service.list_runs()
