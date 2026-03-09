"""
Metrics Routes (S1.4A)
======================

REST API for trade normalization and metrics.

Endpoints:

GET /api/trading/simulation/runs/{runId}/trades        - Get closed trades
GET /api/trading/simulation/runs/{runId}/trades/stats  - Get trade statistics
GET /api/trading/simulation/runs/{runId}/trades/{id}   - Get specific trade
POST /api/trading/simulation/runs/{runId}/trades/normalize - Trigger normalization
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from .trade_types import ClosedTrade, TradeStats
from .trade_normalizer_service import trade_normalizer_service


router = APIRouter(tags=["Trade Metrics (S1.4)"])


# ===========================================
# Trade Endpoints (specific routes BEFORE generic {trade_id})
# ===========================================

@router.get("/runs/{run_id}/trades/stats")
async def get_trade_stats(run_id: str):
    """
    Get aggregate trade statistics.
    
    Includes win rate, profit factor, expectancy, etc.
    """
    stats = trade_normalizer_service.get_trade_stats(run_id)
    
    return {
        "run_id": run_id,
        "stats": stats.to_dict()
    }


@router.get("/runs/{run_id}/trades/summary")
async def get_trade_summary(run_id: str):
    """
    Get full trade summary with stats and all trades.
    """
    summary = trade_normalizer_service.get_trade_summary(run_id)
    return summary


@router.post("/runs/{run_id}/trades/normalize")
async def normalize_trades(
    run_id: str,
    close_open: bool = Query(True, description="Close open positions at final price")
):
    """
    Trigger trade normalization.
    
    Reconstructs closed trades from fills.
    Usually called automatically after simulation completes.
    """
    trades = trade_normalizer_service.normalize_from_broker(run_id, close_open)
    
    return {
        "run_id": run_id,
        "trades_normalized": len(trades),
        "success": True
    }


@router.get("/runs/{run_id}/trades")
async def get_trades(
    run_id: str,
    filter: Optional[str] = Query(None, description="Filter: 'winners' or 'losers'"),
    limit: int = Query(100, description="Max trades to return")
):
    """
    Get closed trades for simulation run.
    
    Trades are reconstructed from fills.
    """
    trades = trade_normalizer_service.get_trades(run_id)
    
    # Apply filter
    if filter == "winners":
        trades = [t for t in trades if t.is_winner]
    elif filter == "losers":
        trades = [t for t in trades if not t.is_winner]
    
    # Apply limit
    trades = trades[:limit]
    
    return {
        "run_id": run_id,
        "trades": [t.to_dict() for t in trades],
        "count": len(trades)
    }


@router.get("/runs/{run_id}/trades/{trade_id}")
async def get_trade(run_id: str, trade_id: str):
    """Get specific trade by ID"""
    trade = trade_normalizer_service.get_trade(run_id, trade_id)
    
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    return trade.to_dict()
