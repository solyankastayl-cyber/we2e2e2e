"""
Performance Metrics Types (S1.4B)
=================================

Type definitions for performance metrics.

Includes:
- PerformanceMetrics: Sharpe, Sortino, Returns
- EquityPoint: For equity curve analysis
- MetricsConfig: Calculation parameters
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


# ===========================================
# Configuration
# ===========================================

@dataclass
class MetricsConfig:
    """
    Configuration for metrics calculation.
    """
    # Risk-free rate for Sharpe/Sortino (annualized)
    risk_free_rate: float = 0.0  # Default: 0% (crypto context)
    
    # Trading days per year (for annualization)
    trading_days_per_year: int = 365  # Crypto trades 24/7
    
    # Minimum trades for valid metrics
    min_trades_for_metrics: int = 5
    
    # Minimum periods for time-based metrics
    min_periods_for_sharpe: int = 10


# ===========================================
# Equity Point
# ===========================================

@dataclass
class EquityPoint:
    """
    Single point on equity curve.
    """
    timestamp: str
    equity_usd: float
    return_pct: float = 0.0  # Period return
    cumulative_return_pct: float = 0.0
    drawdown_pct: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "equity_usd": round(self.equity_usd, 2),
            "return_pct": round(self.return_pct, 6),
            "cumulative_return_pct": round(self.cumulative_return_pct, 4),
            "drawdown_pct": round(self.drawdown_pct, 4)
        }


# ===========================================
# Performance Metrics
# ===========================================

@dataclass
class PerformanceMetrics:
    """
    Performance metrics for simulation run.
    
    Calculated from equity curve and trades.
    """
    run_id: str = ""
    
    # Return Metrics
    total_return_pct: float = 0.0       # Total return %
    total_return_usd: float = 0.0       # Total return $
    annual_return_pct: float = 0.0      # CAGR / Annualized return
    
    # Risk-Adjusted Metrics
    sharpe_ratio: float = 0.0           # Sharpe Ratio
    sortino_ratio: float = 0.0          # Sortino Ratio (downside deviation)
    
    # Volatility
    volatility_annual: float = 0.0      # Annualized volatility
    downside_deviation: float = 0.0     # Downside deviation (for Sortino)
    
    # Additional Stats
    avg_daily_return_pct: float = 0.0   # Average daily return
    best_day_return_pct: float = 0.0    # Best single day
    worst_day_return_pct: float = 0.0   # Worst single day
    
    # Time Info
    initial_capital_usd: float = 0.0
    final_equity_usd: float = 0.0
    trading_days: int = 0
    years_trading: float = 0.0
    
    # Calculation metadata
    config: MetricsConfig = field(default_factory=MetricsConfig)
    calculated_at: str = ""
    is_valid: bool = True
    validation_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            
            # Returns
            "total_return_pct": round(self.total_return_pct, 4),
            "total_return_usd": round(self.total_return_usd, 2),
            "annual_return_pct": round(self.annual_return_pct, 4),
            
            # Risk-Adjusted
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            
            # Volatility
            "volatility_annual": round(self.volatility_annual, 4),
            "downside_deviation": round(self.downside_deviation, 4),
            
            # Daily Stats
            "avg_daily_return_pct": round(self.avg_daily_return_pct, 6),
            "best_day_return_pct": round(self.best_day_return_pct, 4),
            "worst_day_return_pct": round(self.worst_day_return_pct, 4),
            
            # Capital Info
            "initial_capital_usd": round(self.initial_capital_usd, 2),
            "final_equity_usd": round(self.final_equity_usd, 2),
            "trading_days": self.trading_days,
            "years_trading": round(self.years_trading, 4),
            
            # Metadata
            "is_valid": self.is_valid,
            "validation_message": self.validation_message,
            "calculated_at": self.calculated_at
        }


# ===========================================
# Return Series
# ===========================================

@dataclass  
class ReturnSeries:
    """
    Return series for calculations.
    
    Contains processed equity data ready for metrics.
    """
    returns: List[float] = field(default_factory=list)        # Period returns
    negative_returns: List[float] = field(default_factory=list)  # Only negative
    timestamps: List[str] = field(default_factory=list)
    
    initial_equity: float = 0.0
    final_equity: float = 0.0
    
    @property
    def count(self) -> int:
        return len(self.returns)
    
    @property
    def has_data(self) -> bool:
        return len(self.returns) > 0
