"""
Structural Bias Service
=======================

Service layer for structural bias functionality.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from .engine import StructuralBiasEngine
from .types import (
    StructuralBiasState, BiasDirection, BiasAdjustedSignal,
    ASSET_CLASS_CONFIG
)


class StructuralBiasService:
    """Service for managing structural bias across assets"""
    
    def __init__(self):
        self.engines: Dict[str, StructuralBiasEngine] = {}
    
    def get_engine(self, asset: str) -> StructuralBiasEngine:
        """Get or create engine for asset"""
        if asset not in self.engines:
            self.engines[asset] = StructuralBiasEngine(asset)
        return self.engines[asset]
    
    def update_bias(self, asset: str, price: float, timestamp: int, timeframe: str = "1d") -> Dict[str, Any]:
        """Update bias state for asset"""
        engine = self.get_engine(asset)
        state = engine.update(price, timestamp, timeframe)
        return self._state_to_dict(state)
    
    def get_current_bias(self, asset: str) -> Dict[str, Any]:
        """Get current bias state for asset"""
        engine = self.get_engine(asset)
        state = engine.get_state()
        
        if state is None:
            return {
                "asset": asset,
                "bias": "NEUTRAL",
                "long_multiplier": 1.0,
                "short_multiplier": 1.0,
                "status": "not_initialized"
            }
        
        return self._state_to_dict(state)
    
    def apply_bias_to_signal(
        self,
        asset: str,
        direction: str,
        weight: float
    ) -> Dict[str, Any]:
        """Apply structural bias to a trading signal"""
        engine = self.get_engine(asset)
        result = engine.apply_bias(direction, weight)
        
        return {
            "direction": result.direction,
            "original_weight": result.original_weight,
            "bias_multiplier": result.bias_multiplier,
            "adjusted_weight": result.adjusted_weight,
            "bias_state": result.bias_state.value,
            "allowed": result.allowed,
            "rejection_reason": result.rejection_reason
        }
    
    def get_asset_config(self, asset: str) -> Dict[str, Any]:
        """Get configuration for asset"""
        config = ASSET_CLASS_CONFIG.get(asset, ASSET_CLASS_CONFIG.get("SPX", {}))
        return {
            "asset": asset,
            "class": config.get("class", "unknown"),
            "default_bias": config.get("default_bias", BiasDirection.NEUTRAL).value,
            "long_multiplier_default": config.get("long_multiplier_default", 1.0),
            "short_multiplier_default": config.get("short_multiplier_default", 1.0),
            "enable_crisis_override": config.get("enable_crisis_override", False)
        }
    
    def list_supported_assets(self) -> List[Dict[str, Any]]:
        """List all supported assets with configs"""
        assets = []
        for asset, config in ASSET_CLASS_CONFIG.items():
            assets.append({
                "asset": asset,
                "class": config["class"],
                "default_bias": config["default_bias"].value
            })
        return assets
    
    def reset_engine(self, asset: str) -> Dict[str, Any]:
        """Reset engine for asset"""
        if asset in self.engines:
            self.engines[asset].reset()
            return {"status": "reset", "asset": asset}
        return {"status": "not_found", "asset": asset}
    
    def _state_to_dict(self, state: StructuralBiasState) -> Dict[str, Any]:
        """Convert state to dict"""
        return {
            "asset": state.asset,
            "timeframe": state.timeframe,
            "timestamp": state.timestamp,
            
            "long_term_trend": state.long_term_trend.value,
            "volatility_regime": state.volatility_regime.value,
            "drawdown_state": state.drawdown_state.value,
            
            "price": round(state.price, 2),
            "ema_50": round(state.ema_50, 2),
            "ema_200": round(state.ema_200, 2),
            "ema_200_slope": round(state.ema_200_slope, 6),
            
            "current_vol": round(state.current_vol, 4),
            "avg_vol": round(state.avg_vol, 4),
            "vol_ratio": round(state.vol_ratio, 2),
            
            "current_drawdown": round(state.current_drawdown, 4),
            "peak_price": round(state.peak_price, 2),
            
            "bias": state.bias.value,
            "long_multiplier": state.long_multiplier,
            "short_multiplier": state.short_multiplier,
            
            "crisis_override_active": state.crisis_override_active,
            "reasons": state.reasons
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.3A",
            "status": "ok",
            "engines_active": len(self.engines),
            "supported_assets": list(ASSET_CLASS_CONFIG.keys()),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
