"""
Hierarchical Allocator Service
==============================

Service layer for hierarchical portfolio allocation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from .engine import HierarchicalAllocatorEngine
from .types import (
    FamilyType, AlphaInput, DEFAULT_FAMILY_BUDGETS,
    STRATEGY_FAMILY_MAP
)


class HierarchicalAllocatorService:
    """Service for hierarchical alpha allocation"""
    
    def __init__(self):
        self.engines: Dict[str, HierarchicalAllocatorEngine] = {}
    
    def get_engine(self, portfolio_id: str = "default") -> HierarchicalAllocatorEngine:
        """Get or create engine"""
        if portfolio_id not in self.engines:
            self.engines[portfolio_id] = HierarchicalAllocatorEngine()
        return self.engines[portfolio_id]
    
    def add_alpha(
        self,
        portfolio_id: str,
        strategy_id: str,
        family: str,
        returns: List[float],
        expected_return: float = None,
        volatility: float = None,
        health_score: float = 1.0,
        regime_fit: float = 1.0
    ) -> Dict[str, Any]:
        """Add an alpha to the allocator"""
        engine = self.get_engine(portfolio_id)
        
        # Parse family
        try:
            family_type = FamilyType(family.lower())
        except ValueError:
            # Try to infer from strategy ID
            family_type = STRATEGY_FAMILY_MAP.get(strategy_id, FamilyType.EXPERIMENTAL)
        
        # Calculate stats if not provided
        if returns and len(returns) > 10:
            import numpy as np
            returns_arr = np.array(returns)
            if expected_return is None:
                expected_return = float(np.mean(returns_arr) * 252)
            if volatility is None:
                volatility = float(np.std(returns_arr) * np.sqrt(252))
        else:
            expected_return = expected_return or 0.0
            volatility = volatility or 0.15
        
        sharpe = expected_return / volatility if volatility > 0 else 0
        
        alpha = AlphaInput(
            strategy_id=strategy_id,
            family=family_type,
            returns=list(returns) if returns else [],
            expected_return=expected_return,
            volatility=volatility,
            sharpe=sharpe,
            health_score=health_score,
            regime_fit=regime_fit
        )
        
        engine.add_alpha(alpha)
        
        return {
            "strategy_id": strategy_id,
            "family": family_type.value,
            "expected_return": round(expected_return, 4),
            "volatility": round(volatility, 4),
            "sharpe": round(sharpe, 2),
            "health_score": health_score,
            "regime_fit": regime_fit
        }
    
    def add_alphas_batch(
        self,
        portfolio_id: str,
        alphas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Add multiple alphas in batch"""
        results = []
        for alpha_data in alphas:
            result = self.add_alpha(
                portfolio_id=portfolio_id,
                **alpha_data
            )
            results.append(result)
        
        return {
            "portfolio_id": portfolio_id,
            "added": len(results),
            "alphas": results
        }
    
    def set_regime(self, portfolio_id: str, regime: str) -> Dict[str, Any]:
        """Set current regime for budget adjustments"""
        engine = self.get_engine(portfolio_id)
        engine.set_regime(regime)
        budgets = engine.get_regime_adjusted_budgets()
        
        return {
            "portfolio_id": portfolio_id,
            "regime": regime,
            "adjusted_budgets": {k.value: round(v, 3) for k, v in budgets.items()}
        }
    
    def allocate(
        self,
        portfolio_id: str = "default",
        method: str = "max_sharpe"
    ) -> Dict[str, Any]:
        """Run hierarchical allocation"""
        engine = self.get_engine(portfolio_id)
        portfolio = engine.allocate(method)
        
        return self._portfolio_to_dict(portfolio)
    
    def get_family_breakdown(self, portfolio_id: str = "default") -> Dict[str, Any]:
        """Get allocation breakdown by family"""
        engine = self.get_engine(portfolio_id)
        portfolio = engine.current_portfolio
        
        if portfolio is None:
            return {"status": "not_allocated", "portfolio_id": portfolio_id}
        
        families = {}
        for family_type, allocation in portfolio.family_allocations.items():
            families[family_type.value] = {
                "budget": round(allocation.budget, 3),
                "strategy_count": len(allocation.strategies),
                "strategies": allocation.strategies,
                "weights": {k: round(v, 4) for k, v in allocation.weights.items()},
                "sharpe": round(allocation.family_sharpe, 2),
                "intra_correlation": round(allocation.intra_correlation, 2)
            }
        
        return {
            "portfolio_id": portfolio_id,
            "regime": engine.current_regime,
            "families": families
        }
    
    def get_crowding_report(self, portfolio_id: str = "default") -> Dict[str, Any]:
        """Get crowding analysis"""
        engine = self.get_engine(portfolio_id)
        report = engine.get_crowding_report()
        
        return {
            "portfolio_id": portfolio_id,
            "families": report
        }
    
    def get_final_weights(self, portfolio_id: str = "default") -> Dict[str, Any]:
        """Get final portfolio weights"""
        engine = self.get_engine(portfolio_id)
        portfolio = engine.current_portfolio
        
        if portfolio is None:
            return {"status": "not_allocated", "weights": {}}
        
        return {
            "portfolio_id": portfolio_id,
            "weights": {k: round(v, 4) for k, v in portfolio.final_weights.items()},
            "total_strategies": len(portfolio.final_weights),
            "effective_strategies": round(portfolio.effective_strategies, 1),
            "effective_families": round(portfolio.effective_families, 1)
        }
    
    def update_family_budgets(
        self,
        portfolio_id: str,
        budgets: Dict[str, float]
    ) -> Dict[str, Any]:
        """Update family risk budgets"""
        engine = self.get_engine(portfolio_id)
        
        for family_str, budget in budgets.items():
            try:
                family = FamilyType(family_str.lower())
                engine.family_budgets[family] = budget
            except ValueError:
                pass
        
        # Normalize
        total = sum(engine.family_budgets.values())
        if total > 0:
            engine.family_budgets = {k: v/total for k, v in engine.family_budgets.items()}
        
        return {
            "portfolio_id": portfolio_id,
            "budgets": {k.value: round(v, 3) for k, v in engine.family_budgets.items()}
        }
    
    def reset(self, portfolio_id: str) -> Dict[str, Any]:
        """Reset allocator"""
        if portfolio_id in self.engines:
            self.engines[portfolio_id].reset()
            return {"status": "reset", "portfolio_id": portfolio_id}
        return {"status": "not_found", "portfolio_id": portfolio_id}
    
    def _portfolio_to_dict(self, portfolio) -> Dict[str, Any]:
        """Convert portfolio to dict"""
        families = {}
        for family_type, allocation in portfolio.family_allocations.items():
            families[family_type.value] = {
                "budget": round(allocation.budget, 3),
                "strategies": allocation.strategies,
                "weights": {k: round(v, 4) for k, v in allocation.absolute_weights.items()},
                "family_sharpe": round(allocation.family_sharpe, 2)
            }
        
        return {
            "timestamp": portfolio.timestamp,
            "families": families,
            "final_weights": {k: round(v, 4) for k, v in portfolio.final_weights.items()},
            
            "portfolio_metrics": {
                "expected_return": round(portfolio.expected_return, 4),
                "expected_vol": round(portfolio.expected_vol, 4),
                "expected_sharpe": round(portfolio.expected_sharpe, 2),
                "diversification_ratio": round(portfolio.diversification_ratio, 2)
            },
            
            "diversification": {
                "effective_families": round(portfolio.effective_families, 1),
                "effective_strategies": round(portfolio.effective_strategies, 1)
            },
            
            "family_risk_contribution": portfolio.family_risk_contribution
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.3F",
            "status": "ok",
            "portfolios_active": len(self.engines),
            "default_families": list(DEFAULT_FAMILY_BUDGETS.keys()),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
