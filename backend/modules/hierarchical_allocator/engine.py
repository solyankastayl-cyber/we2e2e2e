"""
Hierarchical Allocator Engine
=============================

Two-level portfolio optimization:
1. Intra-family: optimize within each family
2. Cross-family: allocate between families

This prevents optimizer from concentrating on noise.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict

from .types import (
    FamilyType, FamilyConfig, FamilyAllocation, HierarchicalPortfolio,
    AlphaInput, DEFAULT_FAMILY_BUDGETS, STRATEGY_FAMILY_MAP
)

# Import ACE components
try:
    from modules.alpha_combination.covariance import CovarianceEngine
    from modules.alpha_combination.optimizer import PortfolioOptimizer
    from modules.alpha_combination.types import (
        AlphaStats, CovarianceMatrix, OptimizationConstraints, OptimizationMethod
    )
    ACE_AVAILABLE = True
except ImportError:
    ACE_AVAILABLE = False
    print("[HierarchicalAllocator] ACE not available")


class HierarchicalAllocatorEngine:
    """
    Hierarchical Alpha Allocation Engine
    
    Solves the estimation noise problem by:
    1. Grouping alphas into families
    2. Optimizing within each family (reduces noise)
    3. Allocating between families (stable budgets)
    
    Scales to 50-100+ alphas without collapse.
    """
    
    def __init__(self, family_budgets: Dict[FamilyType, float] = None):
        self.family_budgets = family_budgets or DEFAULT_FAMILY_BUDGETS.copy()
        
        # Ensure budgets sum to 1
        total = sum(self.family_budgets.values())
        if total > 0:
            self.family_budgets = {k: v/total for k, v in self.family_budgets.items()}
        
        # Components
        self.cov_engine = CovarianceEngine() if ACE_AVAILABLE else None
        
        # State
        self.alphas: List[AlphaInput] = []
        self.families: Dict[FamilyType, List[AlphaInput]] = defaultdict(list)
        self.current_portfolio: Optional[HierarchicalPortfolio] = None
        
        # Current regime (affects family budgets)
        self.current_regime: str = "RANGE"
    
    def add_alpha(self, alpha: AlphaInput) -> None:
        """Add an alpha to the allocator"""
        # Remove if exists
        self.alphas = [a for a in self.alphas if a.strategy_id != alpha.strategy_id]
        
        # Add
        self.alphas.append(alpha)
        self._rebuild_families()
    
    def add_alphas(self, alphas: List[AlphaInput]) -> None:
        """Add multiple alphas"""
        for alpha in alphas:
            self.alphas = [a for a in self.alphas if a.strategy_id != alpha.strategy_id]
            self.alphas.append(alpha)
        self._rebuild_families()
    
    def _rebuild_families(self) -> None:
        """Rebuild family groupings"""
        self.families = defaultdict(list)
        for alpha in self.alphas:
            self.families[alpha.family].append(alpha)
    
    def set_regime(self, regime: str) -> None:
        """Set current regime for budget adjustments"""
        self.current_regime = regime
    
    def get_regime_adjusted_budgets(self) -> Dict[FamilyType, float]:
        """Get budgets adjusted for current regime"""
        budgets = self.family_budgets.copy()
        
        # Regime adjustments
        regime_adjustments = {
            "TREND_UP": {
                FamilyType.TREND: 1.3,
                FamilyType.BREAKOUT: 1.2,
                FamilyType.MOMENTUM: 1.2,
                FamilyType.REVERSAL: 0.6,
            },
            "TREND_DOWN": {
                FamilyType.REVERSAL: 1.4,
                FamilyType.TREND: 1.1,
                FamilyType.BREAKOUT: 0.8,
                FamilyType.MOMENTUM: 0.7,
            },
            "RANGE": {
                FamilyType.REVERSAL: 1.3,
                FamilyType.MEAN_REVERSION: 1.4,
                FamilyType.BREAKOUT: 0.7,
                FamilyType.MOMENTUM: 0.8,
            },
            "EXPANSION": {
                FamilyType.BREAKOUT: 1.4,
                FamilyType.MOMENTUM: 1.3,
                FamilyType.TREND: 1.2,
                FamilyType.MEAN_REVERSION: 0.5,
            },
            "CRISIS": {
                FamilyType.REVERSAL: 1.5,
                FamilyType.BREAKOUT: 0.6,
                FamilyType.EXPERIMENTAL: 0.3,
            }
        }
        
        adjustments = regime_adjustments.get(self.current_regime, {})
        
        for family, mult in adjustments.items():
            if family in budgets:
                budgets[family] *= mult
        
        # Renormalize
        total = sum(budgets.values())
        if total > 0:
            budgets = {k: v/total for k, v in budgets.items()}
        
        return budgets
    
    def allocate(self, method: str = "max_sharpe") -> HierarchicalPortfolio:
        """
        Run hierarchical allocation.
        
        Step 1: Get regime-adjusted family budgets
        Step 2: For each family, run intra-family optimization
        Step 3: Combine into final portfolio
        """
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        
        if not self.alphas:
            return self._empty_portfolio(timestamp)
        
        # Get adjusted budgets
        budgets = self.get_regime_adjusted_budgets()
        
        # Step 1: Intra-family optimization
        family_allocations: Dict[FamilyType, FamilyAllocation] = {}
        
        for family_type, family_alphas in self.families.items():
            if not family_alphas:
                continue
            
            budget = budgets.get(family_type, 0.1)
            
            allocation = self._optimize_family(
                family_type, family_alphas, budget, method
            )
            family_allocations[family_type] = allocation
        
        # Step 2: Combine into final weights
        final_weights: Dict[str, float] = {}
        for allocation in family_allocations.values():
            final_weights.update(allocation.absolute_weights)
        
        # Normalize (ensure sum = 1)
        total_weight = sum(final_weights.values())
        if total_weight > 0:
            final_weights = {k: v/total_weight for k, v in final_weights.items()}
        
        # Step 3: Calculate portfolio metrics
        portfolio_metrics = self._calculate_portfolio_metrics(final_weights)
        
        # Step 4: Calculate family risk contributions
        family_risk = {}
        for family_type, allocation in family_allocations.items():
            family_risk[family_type.value] = allocation.budget
        
        # Effective metrics
        weights_arr = np.array(list(final_weights.values()))
        effective_strategies = 1 / np.sum(weights_arr ** 2) if np.any(weights_arr > 0) else 0
        
        family_weights = np.array([a.budget for a in family_allocations.values()])
        effective_families = 1 / np.sum(family_weights ** 2) if np.any(family_weights > 0) else 0
        
        portfolio = HierarchicalPortfolio(
            timestamp=timestamp,
            family_allocations=family_allocations,
            final_weights=final_weights,
            expected_return=portfolio_metrics["return"],
            expected_vol=portfolio_metrics["vol"],
            expected_sharpe=portfolio_metrics["sharpe"],
            effective_families=effective_families,
            effective_strategies=effective_strategies,
            diversification_ratio=portfolio_metrics["div_ratio"],
            family_risk_contribution=family_risk
        )
        
        self.current_portfolio = portfolio
        return portfolio
    
    def _optimize_family(
        self,
        family_type: FamilyType,
        alphas: List[AlphaInput],
        budget: float,
        method: str
    ) -> FamilyAllocation:
        """Optimize allocation within a family"""
        
        strategy_ids = [a.strategy_id for a in alphas]
        n = len(alphas)
        
        if n == 0:
            return FamilyAllocation(
                family_type=family_type,
                budget=budget,
                strategies=[],
                weights={},
                absolute_weights={}
            )
        
        if n == 1:
            # Single strategy gets full family budget
            sid = alphas[0].strategy_id
            return FamilyAllocation(
                family_type=family_type,
                budget=budget,
                strategies=[sid],
                weights={sid: 1.0},
                absolute_weights={sid: budget},
                family_return=alphas[0].expected_return,
                family_vol=alphas[0].volatility,
                family_sharpe=alphas[0].sharpe
            )
        
        # Build alpha stats for optimizer
        alpha_stats = []
        for a in alphas:
            stats = AlphaStats(
                strategy_id=a.strategy_id,
                expected_return=a.expected_return * a.health_score * a.regime_fit,
                volatility=a.volatility,
                sharpe=a.sharpe * a.health_score,
                returns=a.returns
            )
            alpha_stats.append(stats)
        
        # Compute covariance
        if self.cov_engine and ACE_AVAILABLE:
            cov = self.cov_engine.compute(alpha_stats)
            cov = self.cov_engine.shrink_covariance(cov, 0.3)  # More shrinkage for families
        else:
            # Default uncorrelated
            cov = CovarianceMatrix(
                strategy_ids=strategy_ids,
                matrix=np.diag([a.volatility**2 for a in alphas]),
                correlation_matrix=np.eye(n)
            )
        
        # Run optimizer
        constraints = OptimizationConstraints(
            min_weight=0.05,
            max_weight=0.50,  # Within family max
            max_leverage=1.0
        )
        optimizer = PortfolioOptimizer(constraints)
        
        method_enum = OptimizationMethod(method)
        result = optimizer.optimize(alpha_stats, cov, method_enum)
        
        # Convert to absolute weights (multiply by family budget)
        intra_weights = result.weights
        absolute_weights = {sid: w * budget for sid, w in intra_weights.items()}
        
        # Calculate family metrics
        mu = np.array([a.expected_return for a in alpha_stats])
        weights = np.array([intra_weights.get(s, 0) for s in strategy_ids])
        
        family_return = float(np.dot(weights, mu))
        family_vol = result.expected_volatility
        family_sharpe = family_return / family_vol if family_vol > 0 else 0
        
        # Intra-family correlation
        corr_matrix = cov.correlation_matrix
        if n > 1:
            upper_tri = corr_matrix[np.triu_indices(n, k=1)]
            intra_corr = float(np.mean(upper_tri)) if len(upper_tri) > 0 else 0
        else:
            intra_corr = 0
        
        return FamilyAllocation(
            family_type=family_type,
            budget=budget,
            strategies=strategy_ids,
            weights=intra_weights,
            absolute_weights=absolute_weights,
            family_return=family_return,
            family_vol=family_vol,
            family_sharpe=family_sharpe,
            intra_correlation=intra_corr
        )
    
    def _calculate_portfolio_metrics(
        self,
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate overall portfolio metrics"""
        if not weights:
            return {"return": 0, "vol": 0, "sharpe": 0, "div_ratio": 1}
        
        # Get alpha returns and vols
        alpha_map = {a.strategy_id: a for a in self.alphas}
        
        port_return = 0.0
        weighted_vol = 0.0
        
        for sid, w in weights.items():
            if sid in alpha_map:
                alpha = alpha_map[sid]
                port_return += w * alpha.expected_return
                weighted_vol += w * alpha.volatility
        
        # Simple portfolio vol (assuming some correlation)
        # In reality would use full covariance
        avg_corr = 0.3  # Assume 30% average correlation
        port_var = 0
        for sid, w in weights.items():
            if sid in alpha_map:
                port_var += (w * alpha_map[sid].volatility) ** 2
        
        # Add correlation effect
        for sid1, w1 in weights.items():
            for sid2, w2 in weights.items():
                if sid1 < sid2 and sid1 in alpha_map and sid2 in alpha_map:
                    port_var += 2 * w1 * w2 * alpha_map[sid1].volatility * \
                               alpha_map[sid2].volatility * avg_corr
        
        port_vol = np.sqrt(max(port_var, 0))
        port_sharpe = port_return / port_vol if port_vol > 0 else 0
        
        div_ratio = weighted_vol / port_vol if port_vol > 0 else 1
        
        return {
            "return": port_return,
            "vol": port_vol,
            "sharpe": port_sharpe,
            "div_ratio": div_ratio
        }
    
    def _empty_portfolio(self, timestamp: int) -> HierarchicalPortfolio:
        """Return empty portfolio"""
        return HierarchicalPortfolio(
            timestamp=timestamp,
            family_allocations={},
            final_weights={},
            expected_return=0,
            expected_vol=0,
            expected_sharpe=0,
            effective_families=0,
            effective_strategies=0,
            diversification_ratio=1
        )
    
    def get_crowding_report(self) -> Dict[str, Any]:
        """Get crowding analysis by family"""
        report = {}
        
        for family_type, alphas in self.families.items():
            if len(alphas) < 2:
                continue
            
            # Build returns matrix
            min_len = min(len(a.returns) for a in alphas)
            if min_len < 10:
                continue
            
            returns_matrix = np.array([a.returns[-min_len:] for a in alphas])
            corr_matrix = np.corrcoef(returns_matrix)
            
            # Find high correlations
            n = len(alphas)
            high_corr_pairs = []
            for i in range(n):
                for j in range(i+1, n):
                    corr = corr_matrix[i, j]
                    if corr > 0.7:
                        high_corr_pairs.append({
                            "alpha1": alphas[i].strategy_id,
                            "alpha2": alphas[j].strategy_id,
                            "correlation": round(corr, 3)
                        })
            
            avg_corr = np.mean(corr_matrix[np.triu_indices(n, k=1)])
            
            report[family_type.value] = {
                "strategy_count": n,
                "avg_correlation": round(float(avg_corr), 3),
                "high_correlation_pairs": high_corr_pairs,
                "crowding_risk": "HIGH" if avg_corr > 0.6 else "MEDIUM" if avg_corr > 0.4 else "LOW"
            }
        
        return report
    
    def reset(self):
        """Reset allocator"""
        self.alphas = []
        self.families = defaultdict(list)
        self.current_portfolio = None
