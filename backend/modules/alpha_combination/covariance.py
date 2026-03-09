"""
Covariance Engine
=================

Computes covariance and correlation matrices between strategies.
"""

import numpy as np
from typing import List, Dict, Optional
from .types import AlphaStats, CovarianceMatrix


class CovarianceEngine:
    """
    Computes covariance matrices for strategy returns.
    
    Uses exponentially weighted moving covariance for regime adaptation.
    """
    
    def __init__(self, halflife: int = 60):
        self.halflife = halflife
        self.decay = 0.5 ** (1 / halflife)
    
    def compute(self, alphas: List[AlphaStats]) -> CovarianceMatrix:
        """
        Compute covariance matrix from alpha returns.
        
        Uses exponential weighting for recent data emphasis.
        """
        n = len(alphas)
        strategy_ids = [a.strategy_id for a in alphas]
        
        if n == 0:
            return CovarianceMatrix(
                strategy_ids=[],
                matrix=np.array([[]]),
                correlation_matrix=np.array([[]])
            )
        
        # Get minimum common length
        min_len = min(len(a.returns) for a in alphas)
        if min_len < 10:
            # Not enough data - return identity-like matrix
            return self._default_matrix(alphas)
        
        # Build return matrix (T x N)
        returns_matrix = np.zeros((min_len, n))
        for i, alpha in enumerate(alphas):
            returns_matrix[:, i] = alpha.returns[-min_len:]
        
        # Compute exponential weights
        weights = np.array([self.decay ** i for i in range(min_len - 1, -1, -1)])
        weights /= weights.sum()
        
        # Weighted mean
        weighted_mean = np.average(returns_matrix, axis=0, weights=weights)
        
        # Centered returns
        centered = returns_matrix - weighted_mean
        
        # Weighted covariance
        cov_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(i, n):
                cov = np.sum(weights * centered[:, i] * centered[:, j])
                cov_matrix[i, j] = cov
                cov_matrix[j, i] = cov
        
        # Annualize (assuming daily returns)
        cov_matrix *= 252
        
        # Compute correlation matrix
        std_devs = np.sqrt(np.diag(cov_matrix))
        std_devs[std_devs == 0] = 1e-6  # Avoid division by zero
        
        corr_matrix = cov_matrix / np.outer(std_devs, std_devs)
        np.fill_diagonal(corr_matrix, 1.0)
        
        return CovarianceMatrix(
            strategy_ids=strategy_ids,
            matrix=cov_matrix,
            correlation_matrix=corr_matrix
        )
    
    def _default_matrix(self, alphas: List[AlphaStats]) -> CovarianceMatrix:
        """Return default uncorrelated matrix"""
        n = len(alphas)
        strategy_ids = [a.strategy_id for a in alphas]
        
        # Diagonal covariance (uncorrelated)
        cov_matrix = np.diag([a.variance for a in alphas])
        corr_matrix = np.eye(n)
        
        return CovarianceMatrix(
            strategy_ids=strategy_ids,
            matrix=cov_matrix,
            correlation_matrix=corr_matrix
        )
    
    def shrink_covariance(
        self, 
        cov: CovarianceMatrix, 
        shrinkage: float = 0.2
    ) -> CovarianceMatrix:
        """
        Apply Ledoit-Wolf shrinkage to covariance matrix.
        
        Shrinks toward diagonal (uncorrelated) matrix.
        """
        n = len(cov.strategy_ids)
        if n == 0:
            return cov
        
        # Target: scaled identity
        avg_var = np.trace(cov.matrix) / n
        target = np.eye(n) * avg_var
        
        # Shrunk covariance
        shrunk = (1 - shrinkage) * cov.matrix + shrinkage * target
        
        # Recompute correlation
        std_devs = np.sqrt(np.diag(shrunk))
        std_devs[std_devs == 0] = 1e-6
        corr_matrix = shrunk / np.outer(std_devs, std_devs)
        np.fill_diagonal(corr_matrix, 1.0)
        
        return CovarianceMatrix(
            strategy_ids=cov.strategy_ids,
            matrix=shrunk,
            correlation_matrix=corr_matrix
        )
