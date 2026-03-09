"""
Performance Metrics Service (S1.4B)
===================================

Service for calculating performance metrics from simulation results.

Metrics:
- Total Return (%)
- Annual Return (CAGR)
- Sharpe Ratio
- Sortino Ratio
- Volatility (Annualized)

Post-simulation analysis:
1. Get equity history from state service
2. Build return series
3. Calculate metrics
4. Cache results
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import threading
import math

from .performance_types import (
    PerformanceMetrics,
    MetricsConfig,
    EquityPoint,
    ReturnSeries
)

from ..simulation_state_service import simulation_state_service


class PerformanceMetricsService:
    """
    Service for calculating performance metrics.
    
    Thread-safe singleton.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Metrics cache: run_id -> PerformanceMetrics
        self._metrics_cache: Dict[str, PerformanceMetrics] = {}
        
        # Processed equity curves: run_id -> List[EquityPoint]
        self._equity_curves: Dict[str, List[EquityPoint]] = {}
        
        # Default config
        self._default_config = MetricsConfig()
        
        self._initialized = True
        print("[PerformanceMetricsService] Initialized")
    
    # ===========================================
    # Main Calculation Methods
    # ===========================================
    
    def calculate_metrics(
        self,
        run_id: str,
        initial_capital: Optional[float] = None,
        config: Optional[MetricsConfig] = None
    ) -> PerformanceMetrics:
        """
        Calculate all performance metrics for a simulation run.
        
        Args:
            run_id: Simulation run ID
            initial_capital: Override initial capital (optional)
            config: Metrics configuration
            
        Returns:
            PerformanceMetrics with all calculated values
        """
        config = config or self._default_config
        
        # Get equity history from state service
        equity_history = simulation_state_service.get_equity_history(run_id)
        
        if not equity_history:
            return self._invalid_metrics(run_id, "No equity history available")
        
        # Get initial capital from state if not provided
        if initial_capital is None:
            state = simulation_state_service.get_state(run_id)
            if state:
                # Estimate from first equity point
                initial_capital = equity_history[0].get("equity_usd", 0)
        
        if not initial_capital or initial_capital <= 0:
            return self._invalid_metrics(run_id, "Invalid initial capital")
        
        # Build return series
        return_series = self._build_return_series(equity_history, initial_capital)
        
        if not return_series.has_data:
            return self._invalid_metrics(run_id, "Insufficient data for metrics")
        
        # Validate minimum periods
        if return_series.count < config.min_periods_for_sharpe:
            return self._invalid_metrics(
                run_id, 
                f"Need at least {config.min_periods_for_sharpe} periods, got {return_series.count}"
            )
        
        # Calculate metrics
        metrics = self._compute_all_metrics(run_id, return_series, config)
        
        # Cache
        self._metrics_cache[run_id] = metrics
        
        print(f"[PerformanceMetrics] Calculated for run: {run_id}, Sharpe: {metrics.sharpe_ratio:.4f}")
        return metrics
    
    def get_metrics(self, run_id: str) -> Optional[PerformanceMetrics]:
        """
        Get cached metrics or calculate if not available.
        """
        if run_id in self._metrics_cache:
            return self._metrics_cache[run_id]
        
        # Try to calculate
        return self.calculate_metrics(run_id)
    
    # ===========================================
    # Return Series Builder
    # ===========================================
    
    def _build_return_series(
        self,
        equity_history: List[Dict[str, Any]],
        initial_capital: float
    ) -> ReturnSeries:
        """
        Build return series from equity history.
        
        Converts raw equity points to period returns.
        """
        series = ReturnSeries(initial_equity=initial_capital)
        
        if len(equity_history) < 2:
            return series
        
        prev_equity = initial_capital
        
        for point in equity_history:
            equity = point.get("equity_usd", 0)
            timestamp = point.get("timestamp", "")
            
            if prev_equity > 0:
                # Calculate period return
                period_return = (equity - prev_equity) / prev_equity
                series.returns.append(period_return)
                series.timestamps.append(timestamp)
                
                # Track negative returns for Sortino
                if period_return < 0:
                    series.negative_returns.append(period_return)
            
            prev_equity = equity
        
        series.final_equity = prev_equity
        return series
    
    # ===========================================
    # Metrics Computation
    # ===========================================
    
    def _compute_all_metrics(
        self,
        run_id: str,
        series: ReturnSeries,
        config: MetricsConfig
    ) -> PerformanceMetrics:
        """
        Compute all performance metrics from return series.
        """
        metrics = PerformanceMetrics(
            run_id=run_id,
            config=config,
            calculated_at=datetime.now(timezone.utc).isoformat(),
            initial_capital_usd=series.initial_equity,
            final_equity_usd=series.final_equity,
            trading_days=series.count
        )
        
        # Total Return
        if series.initial_equity > 0:
            metrics.total_return_usd = series.final_equity - series.initial_equity
            metrics.total_return_pct = (metrics.total_return_usd / series.initial_equity) * 100
        
        # Years trading (for annualization)
        metrics.years_trading = series.count / config.trading_days_per_year
        
        # Annual Return (CAGR)
        metrics.annual_return_pct = self._calculate_cagr(
            series.initial_equity,
            series.final_equity,
            metrics.years_trading
        )
        
        # Daily return statistics
        if series.returns:
            metrics.avg_daily_return_pct = sum(series.returns) / len(series.returns) * 100
            metrics.best_day_return_pct = max(series.returns) * 100
            metrics.worst_day_return_pct = min(series.returns) * 100
        
        # Volatility (Annualized)
        metrics.volatility_annual = self._calculate_volatility(
            series.returns,
            config.trading_days_per_year
        )
        
        # Downside Deviation (for Sortino)
        metrics.downside_deviation = self._calculate_downside_deviation(
            series.returns,
            config.risk_free_rate,
            config.trading_days_per_year
        )
        
        # Sharpe Ratio
        metrics.sharpe_ratio = self._calculate_sharpe(
            series.returns,
            config.risk_free_rate,
            config.trading_days_per_year
        )
        
        # Sortino Ratio
        metrics.sortino_ratio = self._calculate_sortino(
            series.returns,
            config.risk_free_rate,
            config.trading_days_per_year
        )
        
        metrics.is_valid = True
        metrics.validation_message = "Metrics calculated successfully"
        
        return metrics
    
    # ===========================================
    # Individual Metric Calculations
    # ===========================================
    
    def _calculate_cagr(
        self,
        initial_value: float,
        final_value: float,
        years: float
    ) -> float:
        """
        Calculate Compound Annual Growth Rate (CAGR).
        
        CAGR = (Final/Initial)^(1/years) - 1
        """
        if initial_value <= 0 or final_value <= 0 or years <= 0:
            return 0.0
        
        try:
            cagr = (final_value / initial_value) ** (1 / years) - 1
            return cagr * 100  # Convert to percentage
        except (ValueError, ZeroDivisionError):
            return 0.0
    
    def _calculate_volatility(
        self,
        returns: List[float],
        trading_days_per_year: int
    ) -> float:
        """
        Calculate annualized volatility (standard deviation of returns).
        
        Vol = StdDev(returns) * sqrt(trading_days)
        """
        if len(returns) < 2:
            return 0.0
        
        # Calculate standard deviation
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)
        
        # Annualize
        annualized_vol = std_dev * math.sqrt(trading_days_per_year)
        
        return annualized_vol * 100  # Convert to percentage
    
    def _calculate_downside_deviation(
        self,
        returns: List[float],
        target_return: float,
        trading_days_per_year: int
    ) -> float:
        """
        Calculate downside deviation (only negative returns below target).
        
        Used for Sortino Ratio calculation.
        """
        if len(returns) < 2:
            return 0.0
        
        # Daily target return
        daily_target = target_return / trading_days_per_year
        
        # Downside returns (below target)
        downside_returns = [r for r in returns if r < daily_target]
        
        if not downside_returns:
            return 0.0
        
        # Calculate downside variance
        downside_variance = sum((r - daily_target) ** 2 for r in downside_returns) / len(returns)
        downside_dev = math.sqrt(downside_variance)
        
        # Annualize
        return downside_dev * math.sqrt(trading_days_per_year) * 100
    
    def _calculate_sharpe(
        self,
        returns: List[float],
        risk_free_rate: float,
        trading_days_per_year: int
    ) -> float:
        """
        Calculate Sharpe Ratio.
        
        Sharpe = (Mean Return - Risk Free Rate) / StdDev(Returns)
        
        Returns annualized Sharpe.
        """
        if len(returns) < 2:
            return 0.0
        
        # Daily risk-free rate
        daily_rf = risk_free_rate / trading_days_per_year
        
        # Excess returns
        excess_returns = [r - daily_rf for r in returns]
        
        mean_excess = sum(excess_returns) / len(excess_returns)
        
        # Standard deviation
        variance = sum((r - mean_excess) ** 2 for r in excess_returns) / (len(excess_returns) - 1)
        std_dev = math.sqrt(variance)
        
        if std_dev == 0:
            return 0.0
        
        # Daily Sharpe
        daily_sharpe = mean_excess / std_dev
        
        # Annualize
        annualized_sharpe = daily_sharpe * math.sqrt(trading_days_per_year)
        
        return annualized_sharpe
    
    def _calculate_sortino(
        self,
        returns: List[float],
        risk_free_rate: float,
        trading_days_per_year: int
    ) -> float:
        """
        Calculate Sortino Ratio.
        
        Sortino = (Mean Return - Risk Free Rate) / Downside Deviation
        
        Similar to Sharpe but only penalizes downside volatility.
        """
        if len(returns) < 2:
            return 0.0
        
        # Daily risk-free rate
        daily_rf = risk_free_rate / trading_days_per_year
        
        # Mean return
        mean_return = sum(returns) / len(returns)
        excess_return = mean_return - daily_rf
        
        # Downside deviation (daily)
        downside_returns = [r for r in returns if r < daily_rf]
        
        if not downside_returns:
            # No negative returns - return high positive value
            return 99.99 if excess_return > 0 else 0.0
        
        downside_variance = sum((r - daily_rf) ** 2 for r in downside_returns) / len(returns)
        downside_dev = math.sqrt(downside_variance)
        
        if downside_dev == 0:
            return 0.0
        
        # Daily Sortino
        daily_sortino = excess_return / downside_dev
        
        # Annualize
        return daily_sortino * math.sqrt(trading_days_per_year)
    
    # ===========================================
    # Processed Equity Curve
    # ===========================================
    
    def get_processed_equity_curve(
        self,
        run_id: str,
        initial_capital: Optional[float] = None
    ) -> List[EquityPoint]:
        """
        Get processed equity curve with returns and drawdowns.
        """
        if run_id in self._equity_curves:
            return self._equity_curves[run_id]
        
        equity_history = simulation_state_service.get_equity_history(run_id)
        
        if not equity_history:
            return []
        
        if initial_capital is None:
            initial_capital = equity_history[0].get("equity_usd", 0)
        
        curve = self._process_equity_curve(equity_history, initial_capital)
        self._equity_curves[run_id] = curve
        
        return curve
    
    def _process_equity_curve(
        self,
        equity_history: List[Dict[str, Any]],
        initial_capital: float
    ) -> List[EquityPoint]:
        """
        Process raw equity history into detailed curve.
        """
        if not equity_history or initial_capital <= 0:
            return []
        
        curve: List[EquityPoint] = []
        prev_equity = initial_capital
        peak_equity = initial_capital
        
        for point in equity_history:
            equity = point.get("equity_usd", 0)
            timestamp = point.get("timestamp", "")
            
            # Period return
            period_return = 0.0
            if prev_equity > 0:
                period_return = (equity - prev_equity) / prev_equity
            
            # Cumulative return
            cumulative_return = 0.0
            if initial_capital > 0:
                cumulative_return = (equity - initial_capital) / initial_capital
            
            # Drawdown
            if equity > peak_equity:
                peak_equity = equity
            
            drawdown = 0.0
            if peak_equity > 0:
                drawdown = (peak_equity - equity) / peak_equity
            
            curve.append(EquityPoint(
                timestamp=timestamp,
                equity_usd=equity,
                return_pct=period_return * 100,
                cumulative_return_pct=cumulative_return * 100,
                drawdown_pct=drawdown * 100
            ))
            
            prev_equity = equity
        
        return curve
    
    # ===========================================
    # Utilities
    # ===========================================
    
    def _invalid_metrics(self, run_id: str, message: str) -> PerformanceMetrics:
        """Create invalid metrics response"""
        return PerformanceMetrics(
            run_id=run_id,
            is_valid=False,
            validation_message=message,
            calculated_at=datetime.now(timezone.utc).isoformat()
        )
    
    # ===========================================
    # Cache Management
    # ===========================================
    
    def invalidate_cache(self, run_id: str) -> None:
        """Invalidate cached metrics for run"""
        self._metrics_cache.pop(run_id, None)
        self._equity_curves.pop(run_id, None)
    
    def clear_run(self, run_id: str) -> None:
        """Clear all data for run"""
        self.invalidate_cache(run_id)
    
    def clear_all(self) -> int:
        """Clear all cached data"""
        count = len(self._metrics_cache)
        self._metrics_cache.clear()
        self._equity_curves.clear()
        return count


# Global singleton
performance_metrics_service = PerformanceMetricsService()
