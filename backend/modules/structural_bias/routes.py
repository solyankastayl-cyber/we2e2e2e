"""
Structural Bias API Routes
==========================

Phase 9.3A — Structural Market Bias Layer

Endpoints:
- GET  /api/structural-bias/health      - Service health
- GET  /api/structural-bias/assets      - List supported assets
- GET  /api/structural-bias/{asset}     - Get current bias for asset
- POST /api/structural-bias/update      - Update bias with price
- POST /api/structural-bias/apply       - Apply bias to signal
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from .service import StructuralBiasService


router = APIRouter(prefix="/api/structural-bias", tags=["Structural Bias"])

# Service instance
service = StructuralBiasService()


class UpdateBiasRequest(BaseModel):
    asset: str = Field(description="Asset symbol (SPX, BTC, etc)")
    price: float = Field(description="Current price")
    timestamp: int = Field(description="Timestamp in milliseconds")
    timeframe: str = Field(default="1d", description="Timeframe")


class ApplyBiasRequest(BaseModel):
    asset: str = Field(description="Asset symbol")
    direction: str = Field(description="LONG or SHORT")
    weight: float = Field(description="Original signal weight (0-1)")


@router.get("/health")
async def get_health():
    """Get structural bias service health"""
    return service.get_health()


@router.get("/assets")
async def list_assets():
    """List all supported assets with configurations"""
    return {
        "ok": True,
        "assets": service.list_supported_assets()
    }


@router.get("/{asset}")
async def get_bias(asset: str):
    """Get current structural bias for asset"""
    return service.get_current_bias(asset.upper())


@router.get("/{asset}/config")
async def get_asset_config(asset: str):
    """Get configuration for asset"""
    return service.get_asset_config(asset.upper())


@router.post("/update")
async def update_bias(request: UpdateBiasRequest):
    """
    Update structural bias with new price data.
    Call this on each candle to keep bias state current.
    """
    return service.update_bias(
        asset=request.asset.upper(),
        price=request.price,
        timestamp=request.timestamp,
        timeframe=request.timeframe
    )


@router.post("/apply")
async def apply_bias(request: ApplyBiasRequest):
    """
    Apply structural bias to a trading signal.
    
    Returns adjusted weight based on current market bias.
    For equities in bull market: shorts are reduced to 40% weight.
    """
    return service.apply_bias_to_signal(
        asset=request.asset.upper(),
        direction=request.direction.upper(),
        weight=request.weight
    )


@router.post("/{asset}/reset")
async def reset_engine(asset: str):
    """Reset bias engine for asset"""
    return service.reset_engine(asset.upper())


@router.get("/{asset}/explain")
async def explain_bias(asset: str):
    """Get detailed explanation of current bias state"""
    state = service.get_current_bias(asset.upper())
    
    if state.get("status") == "not_initialized":
        return {
            "asset": asset.upper(),
            "explanation": "Engine not initialized. Send price data first.",
            "current_bias": "NEUTRAL (default)"
        }
    
    explanation_parts = []
    
    # Trend explanation
    trend = state.get("long_term_trend", "FLAT")
    if "UP" in trend:
        explanation_parts.append(f"Price is above EMA200, indicating bullish trend.")
    elif "DOWN" in trend:
        explanation_parts.append(f"Price is below EMA200, indicating bearish trend.")
    else:
        explanation_parts.append(f"Price is near EMA200, trend is unclear.")
    
    # Volatility explanation
    vol = state.get("volatility_regime", "NORMAL")
    if vol == "HIGH" or vol == "EXTREME":
        explanation_parts.append(f"Volatility is elevated ({vol}).")
    elif vol == "LOW":
        explanation_parts.append(f"Volatility is compressed.")
    
    # Drawdown explanation
    dd = state.get("current_drawdown", 0)
    if dd > 0.10:
        explanation_parts.append(f"Market in drawdown of {dd*100:.1f}%.")
    
    # Bias explanation
    bias = state.get("bias", "NEUTRAL")
    long_mult = state.get("long_multiplier", 1.0)
    short_mult = state.get("short_multiplier", 1.0)
    
    explanation_parts.append(f"Current bias: {bias}")
    explanation_parts.append(f"Long trades: {long_mult*100:.0f}% weight")
    explanation_parts.append(f"Short trades: {short_mult*100:.0f}% weight")
    
    return {
        "asset": asset.upper(),
        "bias": bias,
        "explanation": " ".join(explanation_parts),
        "reasons": state.get("reasons", []),
        "multipliers": {
            "long": long_mult,
            "short": short_mult
        },
        "market_state": {
            "trend": trend,
            "volatility": vol,
            "drawdown": f"{dd*100:.1f}%"
        }
    }
