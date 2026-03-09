"""
Alpha Combination Service
=========================

Service layer for ACE functionality.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import numpy as np

from .engine import AlphaCombinationEngine
from .types import OptimizationConstraints, OptimizationMethod


class AlphaCombinationService:
    """Service for managing alpha combination"""
    
    def __init__(self):
        self.engines: Dict[str, AlphaCombinationEngine] = {}
    
    def get_engine(self, portfolio_id: str = "default") -> AlphaCombinationEngine:
        """Get or create engine for portfolio"""
        if portfolio_id not in self.engines:
            self.engines[portfolio_id] = AlphaCombinationEngine()
        return self.engines[portfolio_id]
    
    def add_strategy(
        self,
        portfolio_id: str,
        strategy_id: str,
        returns: List[float],
        expected_return: float = None,
        volatility: float = None
    ) -> Dict[str, Any]:
        """Add a strategy to the combination"""
        engine = self.get_engine(portfolio_id)
        alpha = engine.add_alpha(strategy_id, returns, expected_return, volatility)
        
        return {
            "strategy_id": alpha.strategy_id,
            "expected_return": alpha.expected_return,
            "volatility": alpha.volatility,
            "sharpe": alpha.sharpe,
            "returns_count": len(alpha.returns)
        }
    
    def optimize(
        self,
        portfolio_id: str = "default",
        method: str = "max_sharpe",
        use_shrinkage: bool = True
    ) -> Dict[str, Any]:
        """Run portfolio optimization"""
        engine = self.get_engine(portfolio_id)
        
        method_enum = OptimizationMethod(method)
        portfolio = engine.optimize(method_enum, use_shrinkage)
        
        return self._portfolio_to_dict(portfolio)
    
    def get_weights(self, portfolio_id: str = "default") -> Dict[str, Any]:
        """Get current optimal weights"""
        engine = self.get_engine(portfolio_id)
        return {
            "portfolio_id": portfolio_id,
            "weights": engine.get_weights()
        }
    
    def get_correlations(self, portfolio_id: str = "default") -> Dict[str, Any]:
        """Get correlation matrix"""
        engine = self.get_engine(portfolio_id)
        return {
            "portfolio_id": portfolio_id,
            "correlations": engine.get_correlation_matrix()
        }
    
    def compare_methods(self, portfolio_id: str = "default") -> Dict[str, Any]:
        """Compare all optimization methods"""
        engine = self.get_engine(portfolio_id)
        
        # Ensure covariance is computed
        if engine.covariance is None:
            engine.optimize()
        
        comparison = engine.compare_methods()
        
        return {
            "portfolio_id": portfolio_id,
            "comparison": comparison
        }
    
    def get_risk_decomposition(self, portfolio_id: str = "default") -> Dict[str, Any]:
        """Get risk contribution breakdown"""
        engine = self.get_engine(portfolio_id)
        portfolio = engine.current_portfolio
        
        if portfolio is None:
            return {"status": "not_optimized", "portfolio_id": portfolio_id}
        
        return {
            "portfolio_id": portfolio_id,
            "portfolio_volatility": portfolio.portfolio_vol,
            "marginal_risk": portfolio.marginal_risk,
            "risk_contribution": portfolio.risk_contribution,
            "diversification_ratio": portfolio.optimal_weights.diversification_ratio,
            "effective_n": portfolio.optimal_weights.effective_n
        }
    
    def reset(self, portfolio_id: str) -> Dict[str, Any]:
        """Reset engine"""
        if portfolio_id in self.engines:
            self.engines[portfolio_id].reset()
            return {"status": "reset", "portfolio_id": portfolio_id}
        return {"status": "not_found", "portfolio_id": portfolio_id}
    
    def _portfolio_to_dict(self, portfolio) -> Dict[str, Any]:
        """Convert portfolio to dict"""
        return {
            "timestamp": portfolio.timestamp,
            
            "alphas": [
                {
                    "strategy_id": a.strategy_id,
                    "expected_return": round(a.expected_return, 4),
                    "volatility": round(a.volatility, 4),
                    "sharpe": round(a.sharpe, 2)
                }
                for a in portfolio.alphas
            ],
            
            "optimal_weights": portfolio.optimal_weights.weights,
            "method": portfolio.optimal_weights.method.value,
            
            "portfolio_metrics": {
                "expected_return": round(portfolio.portfolio_return, 4),
                "volatility": round(portfolio.portfolio_vol, 4),
                "sharpe": round(portfolio.portfolio_sharpe, 2),
                "diversification_ratio": round(portfolio.optimal_weights.diversification_ratio, 2),
                "effective_n": round(portfolio.optimal_weights.effective_n, 1)
            },
            
            "risk_contribution": {
                k: round(v, 4) for k, v in portfolio.risk_contribution.items()
            }
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.3E",
            "status": "ok",
            "portfolios_active": len(self.engines),
            "optimization_methods": [m.value for m in OptimizationMethod],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
