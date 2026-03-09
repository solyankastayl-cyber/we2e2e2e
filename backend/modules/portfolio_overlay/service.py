"""
Portfolio Overlay Service
=========================

Service layer for portfolio overlay functionality.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .engine import PortfolioOverlayEngine
from .types import OverlayConfig, OverlayState


class PortfolioOverlayService:
    """Service for managing portfolio overlay"""
    
    def __init__(self):
        self.engines: Dict[str, PortfolioOverlayEngine] = {}
    
    def get_engine(self, portfolio_id: str = "default") -> PortfolioOverlayEngine:
        """Get or create engine for portfolio"""
        if portfolio_id not in self.engines:
            self.engines[portfolio_id] = PortfolioOverlayEngine()
        return self.engines[portfolio_id]
    
    def update(
        self,
        portfolio_id: str,
        equity: float,
        daily_return: float = 0.0,
        strategy_score: float = 0.5,
        regime_confidence: float = 0.5,
        health_score: float = 1.0,
        signal_confidence: float = 0.5
    ) -> Dict[str, Any]:
        """Update overlay state"""
        engine = self.get_engine(portfolio_id)
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        
        state = engine.update(
            timestamp=timestamp,
            equity=equity,
            daily_return=daily_return,
            strategy_score=strategy_score,
            regime_confidence=regime_confidence,
            health_score=health_score,
            signal_confidence=signal_confidence
        )
        
        return self._state_to_dict(state)
    
    def get_current_state(self, portfolio_id: str = "default") -> Dict[str, Any]:
        """Get current overlay state"""
        engine = self.get_engine(portfolio_id)
        state = engine.get_state()
        
        if state is None:
            return {
                "status": "not_initialized",
                "portfolio_id": portfolio_id,
                "final_multiplier": 1.0
            }
        
        return self._state_to_dict(state)
    
    def size_position(
        self,
        portfolio_id: str,
        base_size: float
    ) -> Dict[str, Any]:
        """Get overlay-adjusted position size"""
        engine = self.get_engine(portfolio_id)
        result = engine.size_position(base_size)
        
        return {
            "original_size": result.original_size,
            "volatility_adjusted": result.volatility_adjusted,
            "conviction_adjusted": result.conviction_adjusted,
            "drawdown_adjusted": result.drawdown_adjusted,
            "final_size": result.final_size,
            "multipliers": result.multipliers
        }
    
    def configure(
        self,
        portfolio_id: str,
        target_volatility: float = None,
        dd_threshold_critical: float = None
    ) -> Dict[str, Any]:
        """Update configuration for portfolio"""
        engine = self.get_engine(portfolio_id)
        
        if target_volatility is not None:
            engine.config.target_volatility = target_volatility
        
        if dd_threshold_critical is not None:
            engine.config.dd_threshold_critical = dd_threshold_critical
        
        return {
            "status": "configured",
            "portfolio_id": portfolio_id,
            "config": {
                "target_volatility": engine.config.target_volatility,
                "dd_threshold_critical": engine.config.dd_threshold_critical
            }
        }
    
    def reset(self, portfolio_id: str) -> Dict[str, Any]:
        """Reset overlay engine"""
        if portfolio_id in self.engines:
            self.engines[portfolio_id].reset()
            return {"status": "reset", "portfolio_id": portfolio_id}
        return {"status": "not_found", "portfolio_id": portfolio_id}
    
    def _state_to_dict(self, state: OverlayState) -> Dict[str, Any]:
        """Convert state to dict"""
        return {
            "timestamp": state.timestamp,
            
            "volatility": {
                "target": state.target_volatility,
                "realized": round(state.realized_volatility, 4),
                "multiplier": round(state.volatility_multiplier, 2)
            },
            
            "conviction": {
                "strategy_score": round(state.strategy_score, 2),
                "regime_confidence": round(state.regime_confidence, 2),
                "health_score": round(state.health_score, 2),
                "level": state.conviction_level.value,
                "multiplier": round(state.conviction_multiplier, 2)
            },
            
            "drawdown": {
                "current": round(state.current_drawdown, 4),
                "peak_equity": round(state.peak_equity, 2),
                "state": state.drawdown_state.value,
                "multiplier": round(state.drawdown_multiplier, 2)
            },
            
            "final_multiplier": round(state.final_multiplier, 2),
            "reasons": state.reasons
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.3D",
            "status": "ok",
            "portfolios_active": len(self.engines),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
