"""
Alpha Combination Engine
========================

Main engine that combines all optimization components.
"""

import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime

from .types import (
    AlphaStats, CovarianceMatrix, OptimizationConstraints,
    OptimalWeights, AlphaPortfolio, OptimizationMethod
)
from .covariance import CovarianceEngine
from .optimizer import PortfolioOptimizer


class AlphaCombinationEngine:
    """
    Alpha Combination Engine (ACE)
    
    Optimizes the combination of multiple alphas/strategies using:
    - Mean-Variance optimization
    - Covariance estimation with shrinkage
    - Various optimization methods
    
    Result: optimal weights that maximize risk-adjusted returns.
    """
    
    def __init__(self, constraints: OptimizationConstraints = None):
        self.constraints = constraints or OptimizationConstraints()
        self.cov_engine = CovarianceEngine()
        self.optimizer = PortfolioOptimizer(self.constraints)
        
        # State
        self.alphas: List[AlphaStats] = []
        self.covariance: Optional[CovarianceMatrix] = None
        self.optimal_weights: Optional[OptimalWeights] = None
        self.current_portfolio: Optional[AlphaPortfolio] = None
    
    def add_alpha(
        self,
        strategy_id: str,
        returns: List[float],
        expected_return: float = None,
        volatility: float = None
    ) -> AlphaStats:
        """
        Add an alpha to the combination engine.
        
        If expected_return/volatility not provided, computed from returns.
        """
        # Remove if exists
        self.alphas = [a for a in self.alphas if a.strategy_id != strategy_id]
        
        # Compute stats from returns if not provided
        if returns and len(returns) > 10:
            returns_arr = np.array(returns)
            if expected_return is None:
                expected_return = float(np.mean(returns_arr) * 252)  # Annualize
            if volatility is None:
                volatility = float(np.std(returns_arr) * np.sqrt(252))
        else:
            expected_return = expected_return or 0.0
            volatility = volatility or 0.15
        
        sharpe = expected_return / volatility if volatility > 0 else 0
        
        alpha = AlphaStats(
            strategy_id=strategy_id,
            expected_return=expected_return,
            volatility=volatility,
            sharpe=sharpe,
            returns=list(returns) if returns else []
        )
        
        self.alphas.append(alpha)
        return alpha
    
    def optimize(
        self,
        method: OptimizationMethod = OptimizationMethod.MAX_SHARPE,
        use_shrinkage: bool = True,
        shrinkage_factor: float = 0.2
    ) -> AlphaPortfolio:
        """
        Run portfolio optimization.
        
        Args:
            method: Optimization method to use
            use_shrinkage: Apply Ledoit-Wolf shrinkage to covariance
            shrinkage_factor: Shrinkage intensity (0-1)
            
        Returns:
            AlphaPortfolio with optimal weights
        """
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        
        if not self.alphas:
            return self._empty_portfolio(timestamp)
        
        # Compute covariance matrix
        self.covariance = self.cov_engine.compute(self.alphas)
        
        # Apply shrinkage if requested
        if use_shrinkage and len(self.alphas) > 1:
            self.covariance = self.cov_engine.shrink_covariance(
                self.covariance, shrinkage_factor
            )
        
        # Optimize weights
        self.optimal_weights = self.optimizer.optimize(
            self.alphas, self.covariance, method
        )
        
        # Compute risk contributions
        weights_arr = np.array([
            self.optimal_weights.weights.get(a.strategy_id, 0) 
            for a in self.alphas
        ])
        strategy_ids = [a.strategy_id for a in self.alphas]
        
        marginal_risk, risk_contribution = self.optimizer.compute_risk_contributions(
            weights_arr, self.covariance.matrix, strategy_ids
        )
        
        # Build portfolio
        portfolio = AlphaPortfolio(
            timestamp=timestamp,
            alphas=self.alphas,
            covariance=self.covariance,
            optimal_weights=self.optimal_weights,
            portfolio_return=self.optimal_weights.expected_return,
            portfolio_vol=self.optimal_weights.expected_volatility,
            portfolio_sharpe=self.optimal_weights.expected_sharpe,
            marginal_risk=marginal_risk,
            risk_contribution=risk_contribution
        )
        
        self.current_portfolio = portfolio
        return portfolio
    
    def get_weights(self) -> Dict[str, float]:
        """Get current optimal weights"""
        if self.optimal_weights is None:
            return {}
        return self.optimal_weights.weights.copy()
    
    def get_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """Get correlation matrix as nested dict"""
        if self.covariance is None:
            return {}
        
        result = {}
        for i, sid1 in enumerate(self.covariance.strategy_ids):
            result[sid1] = {}
            for j, sid2 in enumerate(self.covariance.strategy_ids):
                result[sid1][sid2] = float(self.covariance.correlation_matrix[i, j])
        
        return result
    
    def compare_methods(self) -> Dict[str, Dict[str, Any]]:
        """
        Compare all optimization methods.
        
        Returns metrics for each method.
        """
        if not self.alphas or self.covariance is None:
            return {}
        
        results = {}
        
        for method in OptimizationMethod:
            weights = self.optimizer.optimize(self.alphas, self.covariance, method)
            results[method.value] = {
                "weights": weights.weights,
                "expected_return": weights.expected_return,
                "expected_volatility": weights.expected_volatility,
                "expected_sharpe": weights.expected_sharpe,
                "diversification_ratio": weights.diversification_ratio,
                "effective_n": weights.effective_n
            }
        
        return results
    
    def _empty_portfolio(self, timestamp: int) -> AlphaPortfolio:
        """Return empty portfolio"""
        return AlphaPortfolio(
            timestamp=timestamp,
            alphas=[],
            covariance=CovarianceMatrix([], np.array([[]]), np.array([[]])),
            optimal_weights=OptimalWeights(
                weights={},
                method=OptimizationMethod.EQUAL_WEIGHT,
                expected_return=0,
                expected_volatility=0,
                expected_sharpe=0,
                diversification_ratio=0,
                effective_n=0
            ),
            portfolio_return=0,
            portfolio_vol=0,
            portfolio_sharpe=0
        )
    
    def reset(self):
        """Reset engine state"""
        self.alphas = []
        self.covariance = None
        self.optimal_weights = None
        self.current_portfolio = None
