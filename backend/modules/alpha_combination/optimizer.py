"""
Portfolio Optimizer
===================

Implements various portfolio optimization methods:
- Mean-Variance (Markowitz)
- Risk Parity
- Maximum Sharpe
- Minimum Variance
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from scipy.optimize import minimize, LinearConstraint, Bounds

from .types import (
    AlphaStats, CovarianceMatrix, OptimizationConstraints,
    OptimalWeights, OptimizationMethod
)


class PortfolioOptimizer:
    """
    Portfolio weight optimizer.
    
    Implements various optimization methods with constraints.
    """
    
    def __init__(self, constraints: OptimizationConstraints = None):
        self.constraints = constraints or OptimizationConstraints()
    
    def optimize(
        self,
        alphas: List[AlphaStats],
        cov: CovarianceMatrix,
        method: OptimizationMethod = OptimizationMethod.MAX_SHARPE
    ) -> OptimalWeights:
        """
        Optimize portfolio weights.
        
        Args:
            alphas: List of alpha statistics
            cov: Covariance matrix
            method: Optimization method
            
        Returns:
            Optimal weights
        """
        n = len(alphas)
        
        if n == 0:
            return OptimalWeights(
                weights={},
                method=method,
                expected_return=0,
                expected_volatility=0,
                expected_sharpe=0,
                diversification_ratio=0,
                effective_n=0
            )
        
        if n == 1:
            return self._single_alpha_weights(alphas[0], method)
        
        # Extract parameters
        mu = np.array([a.expected_return for a in alphas])
        sigma = cov.matrix
        
        # Ensure positive semi-definite
        sigma = self._make_psd(sigma)
        
        # Optimize based on method
        if method == OptimizationMethod.EQUAL_WEIGHT:
            weights = self._equal_weight(n)
        elif method == OptimizationMethod.MIN_VARIANCE:
            weights = self._min_variance(sigma)
        elif method == OptimizationMethod.RISK_PARITY:
            weights = self._risk_parity(sigma)
        elif method == OptimizationMethod.MAX_SHARPE:
            weights = self._max_sharpe(mu, sigma)
        else:  # MEAN_VARIANCE
            weights = self._mean_variance(mu, sigma)
        
        # Apply constraints
        weights = self._apply_constraints(weights)
        
        # Calculate portfolio metrics
        port_return = float(np.dot(weights, mu))
        port_var = float(np.dot(weights, np.dot(sigma, weights)))
        port_vol = np.sqrt(max(port_var, 0))
        port_sharpe = port_return / port_vol if port_vol > 0 else 0
        
        # Diversification metrics
        individual_vols = np.sqrt(np.diag(sigma))
        sum_weighted_vols = np.dot(weights, individual_vols)
        div_ratio = sum_weighted_vols / port_vol if port_vol > 0 else 1
        
        effective_n = 1 / np.sum(weights ** 2) if np.any(weights > 0) else 0
        
        # Build result
        strategy_ids = [a.strategy_id for a in alphas]
        weights_dict = {sid: float(w) for sid, w in zip(strategy_ids, weights)}
        
        return OptimalWeights(
            weights=weights_dict,
            method=method,
            expected_return=port_return,
            expected_volatility=port_vol,
            expected_sharpe=port_sharpe,
            diversification_ratio=div_ratio,
            effective_n=effective_n
        )
    
    def _equal_weight(self, n: int) -> np.ndarray:
        """Simple 1/N allocation"""
        return np.ones(n) / n
    
    def _min_variance(self, sigma: np.ndarray) -> np.ndarray:
        """Minimum variance portfolio"""
        n = len(sigma)
        
        try:
            sigma_inv = np.linalg.inv(sigma)
            ones = np.ones(n)
            weights = sigma_inv @ ones
            weights /= np.sum(weights)
            return np.maximum(weights, 0)  # Ensure non-negative
        except np.linalg.LinAlgError:
            return self._equal_weight(n)
    
    def _risk_parity(self, sigma: np.ndarray) -> np.ndarray:
        """Risk parity - equal risk contribution"""
        n = len(sigma)
        
        def risk_contribution(w):
            port_vol = np.sqrt(w @ sigma @ w)
            if port_vol < 1e-10:
                return np.zeros(n)
            mrc = sigma @ w / port_vol
            return w * mrc
        
        def objective(w):
            rc = risk_contribution(w)
            target_rc = np.sum(rc) / n
            return np.sum((rc - target_rc) ** 2)
        
        # Initial guess
        w0 = self._equal_weight(n)
        
        # Constraints: weights sum to 1, non-negative
        constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        bounds = Bounds(0, 1)
        
        try:
            result = minimize(
                objective, w0, method='SLSQP',
                bounds=bounds, constraints=constraints,
                options={'maxiter': 100}
            )
            return result.x if result.success else w0
        except Exception:
            return w0
    
    def _max_sharpe(self, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
        """Maximum Sharpe ratio portfolio"""
        n = len(mu)
        
        def neg_sharpe(w):
            port_ret = np.dot(w, mu)
            port_vol = np.sqrt(np.dot(w, np.dot(sigma, w)))
            if port_vol < 1e-10:
                return 0
            return -port_ret / port_vol
        
        # Initial guess
        w0 = self._equal_weight(n)
        
        # Constraints
        constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        bounds = Bounds(0, self.constraints.max_weight)
        
        try:
            result = minimize(
                neg_sharpe, w0, method='SLSQP',
                bounds=bounds, constraints=constraints,
                options={'maxiter': 100}
            )
            return result.x if result.success else w0
        except Exception:
            return w0
    
    def _mean_variance(self, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
        """Mean-Variance optimization: maximize μᵀw - λwᵀΣw"""
        n = len(mu)
        lamb = self.constraints.risk_aversion
        
        def objective(w):
            ret = np.dot(w, mu)
            risk = np.dot(w, np.dot(sigma, w))
            return -(ret - lamb * risk)  # Negative for minimization
        
        # Initial guess
        w0 = self._equal_weight(n)
        
        # Constraints
        constraints = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        bounds = Bounds(0, self.constraints.max_weight)
        
        try:
            result = minimize(
                objective, w0, method='SLSQP',
                bounds=bounds, constraints=constraints,
                options={'maxiter': 100}
            )
            return result.x if result.success else w0
        except Exception:
            return w0
    
    def _apply_constraints(self, weights: np.ndarray) -> np.ndarray:
        """Apply portfolio constraints"""
        # Ensure non-negative
        weights = np.maximum(weights, 0)
        
        # Apply max weight
        weights = np.minimum(weights, self.constraints.max_weight)
        
        # Renormalize if needed
        if np.sum(weights) > 0:
            if np.sum(weights) > self.constraints.max_leverage:
                weights /= np.sum(weights) / self.constraints.max_leverage
        
        return weights
    
    def _make_psd(self, sigma: np.ndarray) -> np.ndarray:
        """Ensure matrix is positive semi-definite"""
        try:
            eigvals, eigvecs = np.linalg.eigh(sigma)
            eigvals = np.maximum(eigvals, 1e-8)
            return eigvecs @ np.diag(eigvals) @ eigvecs.T
        except Exception:
            # Fallback to diagonal
            return np.diag(np.diag(sigma))
    
    def _single_alpha_weights(
        self, 
        alpha: AlphaStats, 
        method: OptimizationMethod
    ) -> OptimalWeights:
        """Handle single alpha case"""
        return OptimalWeights(
            weights={alpha.strategy_id: 1.0},
            method=method,
            expected_return=alpha.expected_return,
            expected_volatility=alpha.volatility,
            expected_sharpe=alpha.sharpe,
            diversification_ratio=1.0,
            effective_n=1.0
        )
    
    def compute_risk_contributions(
        self,
        weights: np.ndarray,
        sigma: np.ndarray,
        strategy_ids: List[str]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Compute marginal risk and risk contributions.
        
        Returns:
            (marginal_risk_dict, risk_contribution_dict)
        """
        port_vol = np.sqrt(weights @ sigma @ weights)
        
        if port_vol < 1e-10:
            n = len(weights)
            equal = {sid: 1/n for sid in strategy_ids}
            return equal, equal
        
        # Marginal risk contribution (∂σ/∂w)
        mrc = sigma @ weights / port_vol
        
        # Risk contribution
        rc = weights * mrc
        rc_pct = rc / np.sum(rc) if np.sum(rc) > 0 else rc
        
        marginal_risk = {sid: float(m) for sid, m in zip(strategy_ids, mrc)}
        risk_contribution = {sid: float(r) for sid, r in zip(strategy_ids, rc_pct)}
        
        return marginal_risk, risk_contribution
