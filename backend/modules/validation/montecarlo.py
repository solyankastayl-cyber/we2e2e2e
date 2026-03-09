"""
Phase 8: Monte Carlo Engine
Robustness testing through simulated variations.
"""
import time
import random
import math
from typing import Dict, List, Optional, Any

from .types import (
    MonteCarloResult,
    VALIDATION_CONFIG
)


class MonteCarloEngine:
    """
    Monte Carlo Simulation Engine.
    
    Tests strategy robustness by varying:
    - Volatility
    - Slippage
    - Wick sizes
    - False breakouts
    - Liquidity shocks
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or VALIDATION_CONFIG
        self._results: Dict[str, MonteCarloResult] = {}
    
    def run(
        self,
        base_win_rate: float = 0.60,
        base_profit_factor: float = 1.5,
        base_avg_r: float = 0.3,
        trades_per_run: int = 300,
        iterations: int = 1000,
        variations: Optional[Dict] = None
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.
        
        Args:
            base_win_rate: Base strategy win rate
            base_profit_factor: Base profit factor
            base_avg_r: Base average R-multiple
            trades_per_run: Number of trades per iteration
            iterations: Number of Monte Carlo iterations
            variations: Dict of variation parameters
            
        Returns:
            MonteCarloResult with distribution analysis
        """
        run_id = f"mc_{int(time.time() * 1000)}"
        
        variations = variations or self.config.get("monte_carlo_variations", {})
        
        # Run simulations
        pnl_results = []
        survived_count = 0
        ruin_count = 0
        
        for i in range(iterations):
            # Apply random variations
            volatility_mult = random.uniform(
                variations.get("volatility_range", [0.8, 1.2])[0],
                variations.get("volatility_range", [0.8, 1.2])[1]
            )
            
            slippage_mult = random.uniform(
                variations.get("slippage_range", [5, 30])[0] / 10,
                variations.get("slippage_range", [5, 30])[1] / 10
            )
            
            wick_mult = random.uniform(
                variations.get("wick_multiplier_range", [0.5, 2.0])[0],
                variations.get("wick_multiplier_range", [0.5, 2.0])[1]
            )
            
            # Adjust win rate based on variations
            adjusted_win_rate = base_win_rate
            adjusted_win_rate *= (1 - (volatility_mult - 1) * 0.1)  # Higher vol = lower WR
            adjusted_win_rate *= (1 - (slippage_mult - 1) * 0.02)  # Higher slip = lower WR
            adjusted_win_rate *= (1 - (wick_mult - 1) * 0.03)  # Bigger wicks = lower WR
            adjusted_win_rate = max(0.3, min(0.8, adjusted_win_rate))  # Clamp
            
            # Simulate trades for this iteration
            total_r = 0
            equity = 100000
            max_equity = equity
            
            for _ in range(trades_per_run):
                if random.random() < adjusted_win_rate:
                    # Win
                    r = random.uniform(0.5, 3.0) * volatility_mult
                else:
                    # Loss
                    r = -random.uniform(0.5, 1.5) * wick_mult
                
                # Apply slippage
                r -= slippage_mult * 0.01
                
                total_r += r
                equity += r * 0.02 * equity  # 2% risk per trade
                max_equity = max(max_equity, equity)
                
                # Check for ruin (50% drawdown)
                if equity < max_equity * 0.5:
                    ruin_count += 1
                    break
            else:
                # Survived the run
                survived_count += 1
            
            pnl_results.append(total_r / trades_per_run)  # Normalize by trades
        
        # Calculate statistics
        pnl_results.sort()
        
        median_pnl = pnl_results[len(pnl_results) // 2]
        mean_pnl = sum(pnl_results) / len(pnl_results)
        
        variance = sum((x - mean_pnl) ** 2 for x in pnl_results) / len(pnl_results)
        std_pnl = math.sqrt(variance)
        
        worst_case = pnl_results[0]
        best_case = pnl_results[-1]
        
        percentile_5 = pnl_results[int(0.05 * len(pnl_results))]
        percentile_25 = pnl_results[int(0.25 * len(pnl_results))]
        percentile_75 = pnl_results[int(0.75 * len(pnl_results))]
        percentile_95 = pnl_results[int(0.95 * len(pnl_results))]
        
        survival_rate = survived_count / iterations
        ruin_probability = ruin_count / iterations
        
        # Calculate robustness score
        robustness_score = self._calculate_robustness(
            survival_rate, median_pnl, std_pnl, percentile_5
        )
        
        result = MonteCarloResult(
            run_id=run_id,
            iterations=iterations,
            median_pnl=round(median_pnl, 4),
            mean_pnl=round(mean_pnl, 4),
            std_pnl=round(std_pnl, 4),
            worst_case_pnl=round(worst_case, 4),
            best_case_pnl=round(best_case, 4),
            percentile_5=round(percentile_5, 4),
            percentile_25=round(percentile_25, 4),
            percentile_75=round(percentile_75, 4),
            percentile_95=round(percentile_95, 4),
            survival_rate=round(survival_rate, 4),
            ruin_probability=round(ruin_probability, 4),
            robustness_score=round(robustness_score, 4),
            variations={
                "volatility_range": variations.get("volatility_range", [0.8, 1.2]),
                "slippage_range": variations.get("slippage_range", [5, 30]),
                "wick_multiplier_range": variations.get("wick_multiplier_range", [0.5, 2.0])
            },
            timestamp=int(time.time() * 1000)
        )
        
        self._results[run_id] = result
        
        return result
    
    def get_result(self, run_id: str) -> Optional[MonteCarloResult]:
        """Get a Monte Carlo result by ID"""
        return self._results.get(run_id)
    
    def _calculate_robustness(
        self,
        survival_rate: float,
        median_pnl: float,
        std_pnl: float,
        percentile_5: float
    ) -> float:
        """
        Calculate overall robustness score.
        
        Weights:
        - Survival rate: 30%
        - Positive median: 25%
        - Low volatility: 20%
        - Positive 5th percentile: 25%
        """
        score = 0.0
        
        # Survival component
        score += 0.30 * survival_rate
        
        # Positive median component
        median_score = 1.0 if median_pnl > 0.1 else max(0, (median_pnl + 0.5) / 0.6)
        score += 0.25 * median_score
        
        # Low volatility component (lower std is better)
        vol_score = max(0, 1 - std_pnl / 0.5)  # std < 0.5 is good
        score += 0.20 * vol_score
        
        # Positive 5th percentile (worst case still positive)
        p5_score = 1.0 if percentile_5 > 0 else max(0, (percentile_5 + 0.5) / 0.5)
        score += 0.25 * p5_score
        
        return min(1.0, max(0.0, score))


def monte_carlo_to_dict(result: MonteCarloResult) -> Dict[str, Any]:
    """Convert MonteCarloResult to JSON-serializable dict"""
    return {
        "runId": result.run_id,
        "iterations": result.iterations,
        "medianPnL": result.median_pnl,
        "meanPnL": result.mean_pnl,
        "stdPnL": result.std_pnl,
        "worstCasePnL": result.worst_case_pnl,
        "bestCasePnL": result.best_case_pnl,
        "percentile5": result.percentile_5,
        "percentile25": result.percentile_25,
        "percentile75": result.percentile_75,
        "percentile95": result.percentile_95,
        "survivalRate": result.survival_rate,
        "ruinProbability": result.ruin_probability,
        "robustnessScore": result.robustness_score,
        "variations": result.variations,
        "timestamp": result.timestamp
    }
