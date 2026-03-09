"""
Strategy Routes (T6)
====================

REST API endpoints for Strategy Runtime Engine.

Endpoints:

# Health
GET  /api/trading/strategies/health

# Strategy Management
GET  /api/trading/strategies                 - List all strategies
GET  /api/trading/strategies/{id}            - Get strategy
POST /api/trading/strategies/{id}/enable     - Enable strategy
POST /api/trading/strategies/{id}/disable    - Disable strategy
POST /api/trading/strategies/{id}/pause      - Pause strategy
POST /api/trading/strategies/{id}/resume     - Resume strategy

# Active Strategies
GET  /api/trading/strategies/active          - Get active strategies

# Signal Processing
POST /api/trading/strategies/signal/ta       - Process TA signal
POST /api/trading/strategies/signal/manual   - Process manual signal
POST /api/trading/strategies/signal/mbrain   - Process M-Brain signal

# Configuration
GET  /api/trading/strategies/config          - Get config
POST /api/trading/strategies/config/mode     - Set multi-strategy mode
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from .strategy_engine import strategy_engine
from .strategy_registry import strategy_registry
from .strategy_state import strategy_state_manager


router = APIRouter(prefix="/strategies", tags=["Strategy Runtime (T6)"])


# ===========================================
# Request Models
# ===========================================

class TASignalRequest(BaseModel):
    """TA signal for strategy processing"""
    asset: str
    bias: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float = 0.5
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    patterns: Optional[List[str]] = None
    timeframe: Optional[str] = None
    connection_id: Optional[str] = None
    auto_execute: bool = False


class ManualSignalRequest(BaseModel):
    """Manual signal for strategy processing"""
    asset: str
    action: str  # ENTER_LONG, EXIT_LONG, etc.
    confidence: float = 1.0
    size_pct: Optional[float] = None
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: Optional[str] = None
    connection_id: Optional[str] = None
    auto_execute: bool = False


class MBrainSignalRequest(BaseModel):
    """M-Brain signal for strategy processing"""
    asset: str
    ensemble_action: str
    ensemble_confidence: float = 0.5
    module_votes: Optional[Dict[str, Any]] = None
    connection_id: Optional[str] = None
    auto_execute: bool = False


class StrategyModeRequest(BaseModel):
    """Strategy mode configuration"""
    multi_strategy_mode: bool = False


# ===========================================
# Health
# ===========================================

@router.get("/health")
async def strategy_health():
    """Strategy Runtime health check"""
    return strategy_engine.get_health()


# ===========================================
# Strategy Management
# ===========================================

@router.get("")
async def list_strategies():
    """List all registered strategies"""
    strategies = strategy_engine.list_strategies()
    
    return {
        "strategies": strategies,
        "count": len(strategies)
    }


@router.get("/active")
async def get_active_strategies():
    """Get active strategies"""
    strategies = strategy_engine.get_active_strategies()
    
    return {
        "strategies": strategies,
        "count": len(strategies)
    }


@router.get("/config")
async def get_strategy_config():
    """Get strategy runtime configuration"""
    return {
        "multi_strategy_mode": strategy_engine.is_multi_strategy(),
        "registered_strategies": strategy_registry.count(),
        "active_strategies": len(strategy_state_manager.get_active_ids()),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy by ID"""
    strategy = strategy_engine.get_strategy(strategy_id)
    
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    
    return strategy


@router.post("/{strategy_id}/enable")
async def enable_strategy(strategy_id: str):
    """Enable a strategy"""
    result = strategy_engine.enable_strategy(strategy_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    
    return {
        "success": True,
        "strategy_id": strategy_id,
        "state": result
    }


@router.post("/{strategy_id}/disable")
async def disable_strategy(strategy_id: str):
    """Disable a strategy"""
    result = strategy_engine.disable_strategy(strategy_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")
    
    return {
        "success": True,
        "strategy_id": strategy_id,
        "state": result
    }


@router.post("/{strategy_id}/pause")
async def pause_strategy(strategy_id: str):
    """Pause a strategy temporarily"""
    result = strategy_engine.pause_strategy(strategy_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Strategy not found or not active: {strategy_id}")
    
    return {
        "success": True,
        "strategy_id": strategy_id,
        "state": result
    }


@router.post("/{strategy_id}/resume")
async def resume_strategy(strategy_id: str):
    """Resume a paused strategy"""
    result = strategy_engine.resume_strategy(strategy_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Strategy not found or not paused: {strategy_id}")
    
    return {
        "success": True,
        "strategy_id": strategy_id,
        "state": result
    }


# ===========================================
# Signal Processing
# ===========================================

@router.post("/signal/ta")
async def process_ta_signal(request: TASignalRequest):
    """
    Process TA signal through strategies.
    
    Sends signal to active strategies and returns their actions.
    """
    signal_data = {
        "asset": request.asset,
        "bias": request.bias,
        "confidence": request.confidence,
        "price": request.price,
        "stop_loss": request.stop_loss,
        "take_profit": request.take_profit,
        "patterns": request.patterns or [],
        "timeframe": request.timeframe
    }
    
    result = await strategy_engine.process_ta_signal(
        signal_data,
        connection_id=request.connection_id,
        auto_execute=request.auto_execute
    )
    
    return result


@router.post("/signal/manual")
async def process_manual_signal(request: ManualSignalRequest):
    """
    Process manual signal through strategies.
    """
    signal_data = {
        "asset": request.asset,
        "action": request.action,
        "confidence": request.confidence,
        "size_pct": request.size_pct,
        "price": request.price,
        "stop_loss": request.stop_loss,
        "take_profit": request.take_profit,
        "reason": request.reason
    }
    
    result = await strategy_engine.process_manual_signal(
        signal_data,
        connection_id=request.connection_id,
        auto_execute=request.auto_execute
    )
    
    return result


@router.post("/signal/mbrain")
async def process_mbrain_signal(request: MBrainSignalRequest):
    """
    Process M-Brain signal through strategies.
    """
    signal_data = {
        "asset": request.asset,
        "ensemble_action": request.ensemble_action,
        "ensemble_confidence": request.ensemble_confidence,
        "module_votes": request.module_votes or {}
    }
    
    result = await strategy_engine.process_mbrain_signal(
        signal_data,
        connection_id=request.connection_id,
        auto_execute=request.auto_execute
    )
    
    return result


# ===========================================
# Configuration
# ===========================================

@router.post("/config/mode")
async def set_strategy_mode(request: StrategyModeRequest):
    """Set multi-strategy mode"""
    strategy_engine.set_multi_strategy_mode(request.multi_strategy_mode)
    
    return {
        "success": True,
        "multi_strategy_mode": strategy_engine.is_multi_strategy()
    }
