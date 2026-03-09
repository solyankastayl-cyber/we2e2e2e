"""
Orthogonal Alpha Engine Types
=============================

Phase 9.3G - Data structures for alpha orthogonalization.

Goal: Transform correlated alphas into independent residual alphas
to eliminate hidden crowding and improve portfolio diversification.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class OrthogonalizationMethod(str, Enum):
    """Orthogonalization methods"""
    GRAM_SCHMIDT = "gram_schmidt"           # Classic sequential orthogonalization
    PCA = "pca"                              # Principal Component Analysis
    FACTOR_MODEL = "factor_model"            # Residualize against common factors
    HIERARCHICAL = "hierarchical"            # Hierarchical orthogonalization by family


class AlphaStatus(str, Enum):
    """Alpha status after orthogonalization"""
    ORIGINAL = "original"                    # Raw alpha, not processed
    ORTHOGONALIZED = "orthogonalized"        # Successfully orthogonalized
    REDUNDANT = "redundant"                  # Marked as redundant (high correlation)
    INDEPENDENT = "independent"              # Already independent, no change needed


@dataclass
class AlphaVector:
    """
    Single alpha's return series with metadata.
    """
    alpha_id: str
    family: str = ""
    
    # Return series (daily returns)
    returns: List[float] = field(default_factory=list)
    
    # Orthogonalized returns (after processing)
    residual_returns: List[float] = field(default_factory=list)
    
    # Statistics
    mean_return: float = 0.0
    volatility: float = 0.0
    sharpe: float = 0.0
    
    # Post-orthogonalization stats
    residual_mean: float = 0.0
    residual_volatility: float = 0.0
    residual_sharpe: float = 0.0
    
    # Variance explained by common factors
    r_squared: float = 0.0
    residual_variance_ratio: float = 1.0
    
    # Status
    status: AlphaStatus = AlphaStatus.ORIGINAL


@dataclass
class CorrelationPair:
    """
    Correlation between two alphas.
    """
    alpha_1: str
    alpha_2: str
    
    # Original correlation
    raw_correlation: float = 0.0
    
    # Correlation after orthogonalization
    residual_correlation: float = 0.0
    
    # Improvement
    correlation_reduction: float = 0.0
    
    # Flags
    is_crowded: bool = False       # High correlation (> 0.7)
    is_redundant: bool = False     # Very high correlation (> 0.9)


@dataclass
class CommonFactor:
    """
    Common factor extracted from alphas.
    """
    factor_id: str
    name: str
    
    # Factor loadings per alpha
    loadings: Dict[str, float] = field(default_factory=dict)
    
    # Factor return series
    returns: List[float] = field(default_factory=list)
    
    # Explained variance
    variance_explained: float = 0.0
    variance_explained_pct: float = 0.0


@dataclass
class OrthogonalizationResult:
    """
    Result of orthogonalization process.
    """
    session_id: str
    method: OrthogonalizationMethod
    
    # Input
    input_alphas: int = 0
    
    # Output
    output_alphas: int = 0
    redundant_alphas: int = 0
    
    # Common factors (if factor model used)
    common_factors: List[CommonFactor] = field(default_factory=list)
    num_factors: int = 0
    
    # Correlation improvement
    avg_raw_correlation: float = 0.0
    avg_residual_correlation: float = 0.0
    correlation_reduction_pct: float = 0.0
    
    # Portfolio improvement
    raw_portfolio_sharpe: float = 0.0
    orthogonal_portfolio_sharpe: float = 0.0
    sharpe_improvement_pct: float = 0.0
    
    # Diversification
    raw_diversification_ratio: float = 1.0
    orthogonal_diversification_ratio: float = 1.0
    
    # Redundancy
    redundant_alpha_ids: List[str] = field(default_factory=list)
    crowded_pairs: List[CorrelationPair] = field(default_factory=list)
    
    # Timestamp
    created_at: int = 0


@dataclass
class OrthogonalPortfolio:
    """
    Portfolio of orthogonalized alphas.
    """
    portfolio_id: str
    
    # Alphas
    alphas: List[AlphaVector] = field(default_factory=list)
    
    # Weights (after orthogonalization)
    weights: Dict[str, float] = field(default_factory=dict)
    
    # Metrics
    expected_return: float = 0.0
    portfolio_volatility: float = 0.0
    portfolio_sharpe: float = 0.0
    
    # Correlation matrix (post-orthogonalization)
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Max correlation in portfolio
    max_correlation: float = 0.0
    avg_correlation: float = 0.0


@dataclass
class OrthogonalizationConfig:
    """
    Configuration for orthogonalization engine.
    """
    # Method selection
    method: OrthogonalizationMethod = OrthogonalizationMethod.FACTOR_MODEL
    
    # Redundancy thresholds
    redundancy_threshold: float = 0.90      # Mark as redundant if correlation > 0.9
    crowding_threshold: float = 0.70        # Mark as crowded if correlation > 0.7
    
    # Factor model settings
    min_variance_explained: float = 0.05    # Minimum variance to keep a factor
    max_factors: int = 5                     # Maximum number of common factors
    
    # PCA settings
    pca_components: int = 3                  # Number of principal components
    
    # Gram-Schmidt settings
    gs_tolerance: float = 0.01              # Tolerance for near-zero vectors
    
    # Output
    remove_redundant: bool = True            # Remove redundant alphas from output
    preserve_family_structure: bool = True   # Keep at least one alpha per family
