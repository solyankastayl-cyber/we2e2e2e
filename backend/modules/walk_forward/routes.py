"""
Walk-Forward API Routes
=======================

Phase 9.3 — 1950 Walk-Forward Simulation API

Endpoints:
- POST /api/walk-forward/run           - Run single simulation
- POST /api/walk-forward/comparison    - Run 4-way comparison
- GET  /api/walk-forward/results       - List results
- GET  /api/walk-forward/results/{id}  - Get specific result
- GET  /api/walk-forward/equity/{id}   - Get equity curve
- GET  /api/walk-forward/health        - Service health
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .service import WalkForwardService


router = APIRouter(prefix="/api/walk-forward", tags=["Walk-Forward"])

# Service instance
service = WalkForwardService()

# Thread pool for long-running simulations
executor = ThreadPoolExecutor(max_workers=2)


class RunSimulationRequest(BaseModel):
    asset: str = Field(default="SPX", description="Asset to simulate")
    timeframe: str = Field(default="1d", description="Timeframe")
    mode: str = Field(default="full_system", description="Simulation mode: full_system, no_meta, no_healing, core_only")
    initial_capital: float = Field(default=100000.0, description="Starting capital")
    warmup_bars: int = Field(default=500, description="Warmup period in bars")
    start_date: Optional[str] = Field(default=None, description="Start date YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="End date YYYY-MM-DD")


class ComparisonRequest(BaseModel):
    asset: str = Field(default="SPX", description="Asset to simulate")
    timeframe: str = Field(default="1d", description="Timeframe")
    initial_capital: float = Field(default=100000.0, description="Starting capital")
    warmup_bars: int = Field(default=500, description="Warmup period")


# In-memory job tracking
running_jobs: Dict[str, Dict[str, Any]] = {}


@router.get("/health")
async def get_health():
    """Get walk-forward service health"""
    return service.get_health()


@router.post("/run")
async def run_simulation(request: RunSimulationRequest, background_tasks: BackgroundTasks):
    """
    Run a walk-forward simulation
    
    Modes:
    - full_system: All governance layers active
    - no_meta: Without Meta-Strategy (Phase 9.27)
    - no_healing: Without Self-Healing (Phase 9.26)
    - core_only: Only APPROVED core strategies
    """
    try:
        # Run in thread pool to not block
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            lambda: service.run_simulation(
                asset=request.asset,
                timeframe=request.timeframe,
                mode=request.mode,
                initial_capital=request.initial_capital,
                warmup_bars=request.warmup_bars,
                start_date=request.start_date,
                end_date=request.end_date
            )
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/comparison")
async def run_comparison(request: ComparisonRequest):
    """
    Run 4-way comparison:
    1. Full System
    2. Without Meta-Strategy
    3. Without Self-Healing
    4. Core Strategies Only
    
    This shows the contribution of each architectural layer.
    """
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            lambda: service.run_comparison(
                asset=request.asset,
                timeframe=request.timeframe,
                initial_capital=request.initial_capital,
                warmup_bars=request.warmup_bars
            )
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results")
async def list_results(asset: Optional[str] = None, limit: int = 20):
    """List recent walk-forward results"""
    try:
        results = service.list_results(asset=asset, limit=limit)
        return {
            "ok": True,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{run_id}")
async def get_result(run_id: str):
    """Get specific walk-forward result"""
    result = service.get_result(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return result


@router.get("/equity/{run_id}")
async def get_equity_curve(run_id: str):
    """Get equity curve for specific run"""
    result = service.get_result(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "run_id": run_id,
        "initial_capital": result.get("config", {}).get("initial_capital", 100000),
        "final_equity": result.get("final_equity", 0),
        "peak_equity": result.get("peak_equity", 0),
        "equity_curve": result.get("equity_curve", [])
    }


@router.get("/decades/{run_id}")
async def get_decade_breakdown(run_id: str):
    """Get per-decade breakdown"""
    result = service.get_result(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "run_id": run_id,
        "asset": result.get("config", {}).get("asset", ""),
        "decades": result.get("decade_metrics", [])
    }


@router.get("/regimes/{run_id}")
async def get_regime_breakdown(run_id: str):
    """Get per-regime breakdown"""
    result = service.get_result(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "run_id": run_id,
        "asset": result.get("config", {}).get("asset", ""),
        "regimes": result.get("regime_metrics", [])
    }


@router.get("/strategies/{run_id}")
async def get_strategy_breakdown(run_id: str):
    """Get per-strategy breakdown"""
    result = service.get_result(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "run_id": run_id,
        "strategies": result.get("strategy_metrics", [])
    }


@router.get("/failures/{run_id}")
async def get_failure_map(run_id: str):
    """Get failure events map"""
    result = service.get_result(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    failures = result.get("failure_events", [])
    
    # Group by type
    by_type: Dict[str, List] = {}
    for f in failures:
        ftype = f.get("type", "UNKNOWN")
        if ftype not in by_type:
            by_type[ftype] = []
        by_type[ftype].append(f)
    
    # Group by decade
    by_decade: Dict[str, int] = {}
    for f in failures:
        decade = f.get("decade", "unknown")
        by_decade[decade] = by_decade.get(decade, 0) + 1
    
    return {
        "run_id": run_id,
        "total_failures": len(failures),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "by_decade": by_decade,
        "failures": failures[:100]  # Limit
    }


@router.get("/summary/{run_id}")
async def get_summary(run_id: str):
    """Get condensed summary of walk-forward run"""
    result = service.get_result(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    config = result.get("config", {})
    
    # Best/worst decades
    decades = result.get("decade_metrics", [])
    best_decade = max(decades, key=lambda x: x.get("profit_factor", 0)) if decades else {}
    worst_decade = min(decades, key=lambda x: x.get("profit_factor", 999)) if decades else {}
    
    # Best/worst regimes
    regimes = result.get("regime_metrics", [])
    best_regime = max(regimes, key=lambda x: x.get("profit_factor", 0)) if regimes else {}
    worst_regime = min(regimes, key=lambda x: x.get("profit_factor", 999)) if regimes else {}
    
    # Top strategies
    strategies = result.get("strategy_metrics", [])
    top_strategies = sorted(strategies, key=lambda x: x.get("contribution_pct", 0), reverse=True)[:3]
    
    return {
        "run_id": run_id,
        "asset": config.get("asset"),
        "mode": result.get("mode"),
        "period": f"{config.get('start_date', '1950')} → {config.get('end_date', 'now')}",
        
        "global_metrics": {
            "total_trades": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
            "profit_factor": result.get("profit_factor"),
            "sharpe": result.get("sharpe"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "cagr": result.get("cagr"),
            "expectancy": result.get("expectancy")
        },
        
        "best_decade": {
            "decade": best_decade.get("decade"),
            "profit_factor": best_decade.get("profit_factor")
        },
        "worst_decade": {
            "decade": worst_decade.get("decade"),
            "profit_factor": worst_decade.get("profit_factor")
        },
        
        "best_regime": {
            "regime": best_regime.get("regime"),
            "profit_factor": best_regime.get("profit_factor")
        },
        "worst_regime": {
            "regime": worst_regime.get("regime"),
            "profit_factor": worst_regime.get("profit_factor")
        },
        
        "top_strategies": top_strategies,
        
        "governance": {
            "healing_events": result.get("healing_events"),
            "kill_switch_events": result.get("kill_switch_events"),
            "meta_reallocations": result.get("meta_reallocations")
        },
        
        "failures_count": len(result.get("failure_events", []))
    }
