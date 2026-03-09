"""
Alpha Combination Types
=======================

Types for Mean-Variance Optimization and portfolio construction.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
import numpy as np


class OptimizationMethod(str, Enum):
    """Optimization methods available"""
    MEAN_VARIANCE = "mean_variance"     # Classic Markowitz
    RISK_PARITY = "risk_parity"         # Equal risk contribution
    MAX_SHARPE = "max_sharpe"           # Maximize Sharpe ratio
    MIN_VARIANCE = "min_variance"       # Minimum variance portfolio
    EQUAL_WEIGHT = "equal_weight"       # Simple 1/N


@dataclass
class AlphaStats:
    """Statistics for a single alpha/strategy"""
    strategy_id: str
    expected_return: float      # μ (annualized)
    volatility: float           # σ (annualized)
    sharpe: float               # μ/σ
    returns: List[float] = field(default_factory=list)  # Historical returns
    
    @property
    def variance(self) -> float:
        return self.volatility ** 2


@dataclass
class CovarianceMatrix:
    """Covariance matrix between strategies"""
    strategy_ids: List[str]
    matrix: np.ndarray          # NxN covariance matrix
    correlation_matrix: np.ndarray  # NxN correlation matrix
    
    def get_covariance(self, id1: str, id2: str) -> float:
        """Get covariance between two strategies"""
        try:
            i = self.strategy_ids.index(id1)
            j = self.strategy_ids.index(id2)
            return float(self.matrix[i, j])
        except (ValueError, IndexError):
            return 0.0
    
    def get_correlation(self, id1: str, id2: str) -> float:
        """Get correlation between two strategies"""
        try:
            i = self.strategy_ids.index(id1)
            j = self.strategy_ids.index(id2)
            return float(self.correlation_matrix[i, j])
        except (ValueError, IndexError):
            return 0.0


@dataclass
class OptimizationConstraints:
    """Constraints for portfolio optimization"""
    min_weight: float = 0.0         # Minimum strategy weight
    max_weight: float = 0.40        # Maximum strategy weight (40%)
    max_family_exposure: float = 0.50  # Max exposure to one family
    max_leverage: float = 1.0       # Maximum leverage
    target_volatility: float = 0.12 # Target portfolio vol
    risk_aversion: float = 1.0      # λ parameter


@dataclass
class OptimalWeights:
    """Result of optimization"""
    weights: Dict[str, float]       # strategy_id -> weight
    method: OptimizationMethod
    
    expected_return: float
    expected_volatility: float
    expected_sharpe: float
    
    diversification_ratio: float    # Sum of individual vols / portfolio vol
    effective_n: float              # Effective number of bets (1/Σw²)
    
    constraints_active: List[str] = field(default_factory=list)
    iterations: int = 0


@dataclass
class AlphaPortfolio:
    """Complete alpha portfolio state"""
    timestamp: int
    
    alphas: List[AlphaStats]
    covariance: CovarianceMatrix
    optimal_weights: OptimalWeights
    
    # Portfolio metrics
    portfolio_return: float
    portfolio_vol: float
    portfolio_sharpe: float
    
    # Risk decomposition
    marginal_risk: Dict[str, float] = field(default_factory=dict)
    risk_contribution: Dict[str, float] = field(default_factory=dict)
