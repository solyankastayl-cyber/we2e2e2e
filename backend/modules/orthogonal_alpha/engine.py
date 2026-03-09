"""
Orthogonal Alpha Engine - Core
==============================

Phase 9.3G - Transforms correlated alphas into independent residual alphas.

Methods:
1. Gram-Schmidt: Sequential orthogonalization
2. PCA: Principal Component decomposition
3. Factor Model: Residualize against common factors
4. Hierarchical: Family-aware orthogonalization
"""

import math
import uuid
import time
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .types import (
    AlphaVector, AlphaStatus, CorrelationPair, CommonFactor,
    OrthogonalizationResult, OrthogonalPortfolio, OrthogonalizationConfig,
    OrthogonalizationMethod
)


class OrthogonalAlphaEngine:
    """
    Core engine for alpha orthogonalization.
    
    Purpose:
    - Transform correlated alphas into independent residual alphas
    - Eliminate hidden crowding in the portfolio
    - Improve true diversification
    """
    
    def __init__(self, config: Optional[OrthogonalizationConfig] = None):
        self.config = config or OrthogonalizationConfig()
        self.alphas: Dict[str, AlphaVector] = {}
        self.results: Dict[str, OrthogonalizationResult] = {}
    
    # ============================================
    # Alpha Management
    # ============================================
    
    def add_alpha(
        self,
        alpha_id: str,
        returns: List[float],
        family: str = ""
    ) -> AlphaVector:
        """Add an alpha to the engine"""
        
        mean_return = sum(returns) / len(returns) if returns else 0
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns) if returns else 0
        volatility = math.sqrt(variance) if variance > 0 else 0
        sharpe = mean_return / volatility * math.sqrt(252) if volatility > 0 else 0
        
        alpha = AlphaVector(
            alpha_id=alpha_id,
            family=family,
            returns=returns,
            residual_returns=returns.copy(),  # Initially same as raw
            mean_return=mean_return,
            volatility=volatility,
            sharpe=sharpe,
            residual_mean=mean_return,
            residual_volatility=volatility,
            residual_sharpe=sharpe,
            status=AlphaStatus.ORIGINAL
        )
        
        self.alphas[alpha_id] = alpha
        return alpha
    
    def clear_alphas(self):
        """Clear all alphas"""
        self.alphas.clear()
    
    # ============================================
    # Correlation Analysis
    # ============================================
    
    def compute_correlation(self, returns_1: List[float], returns_2: List[float]) -> float:
        """Compute Pearson correlation between two return series"""
        n = min(len(returns_1), len(returns_2))
        if n < 2:
            return 0.0
        
        r1 = returns_1[:n]
        r2 = returns_2[:n]
        
        mean_1 = sum(r1) / n
        mean_2 = sum(r2) / n
        
        cov = sum((r1[i] - mean_1) * (r2[i] - mean_2) for i in range(n)) / n
        
        var_1 = sum((r - mean_1) ** 2 for r in r1) / n
        var_2 = sum((r - mean_2) ** 2 for r in r2) / n
        
        if var_1 <= 0 or var_2 <= 0:
            return 0.0
        
        return cov / (math.sqrt(var_1) * math.sqrt(var_2))
    
    def compute_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """Compute full correlation matrix for all alphas"""
        alpha_ids = list(self.alphas.keys())
        matrix = {}
        
        for i, id1 in enumerate(alpha_ids):
            matrix[id1] = {}
            for j, id2 in enumerate(alpha_ids):
                if i == j:
                    matrix[id1][id2] = 1.0
                elif j < i:
                    matrix[id1][id2] = matrix[id2][id1]
                else:
                    corr = self.compute_correlation(
                        self.alphas[id1].returns,
                        self.alphas[id2].returns
                    )
                    matrix[id1][id2] = corr
        
        return matrix
    
    def find_crowded_pairs(self) -> List[CorrelationPair]:
        """Find all crowded pairs (high correlation)"""
        pairs = []
        alpha_ids = list(self.alphas.keys())
        
        for i, id1 in enumerate(alpha_ids):
            for j, id2 in enumerate(alpha_ids):
                if j <= i:
                    continue
                
                corr = self.compute_correlation(
                    self.alphas[id1].returns,
                    self.alphas[id2].returns
                )
                
                if abs(corr) > self.config.crowding_threshold:
                    pair = CorrelationPair(
                        alpha_1=id1,
                        alpha_2=id2,
                        raw_correlation=corr,
                        is_crowded=True,
                        is_redundant=abs(corr) > self.config.redundancy_threshold
                    )
                    pairs.append(pair)
        
        return pairs
    
    # ============================================
    # Orthogonalization Methods
    # ============================================
    
    def orthogonalize(self) -> OrthogonalizationResult:
        """Run orthogonalization using configured method"""
        
        if self.config.method == OrthogonalizationMethod.GRAM_SCHMIDT:
            return self._gram_schmidt_orthogonalize()
        elif self.config.method == OrthogonalizationMethod.PCA:
            return self._pca_orthogonalize()
        elif self.config.method == OrthogonalizationMethod.FACTOR_MODEL:
            return self._factor_model_orthogonalize()
        elif self.config.method == OrthogonalizationMethod.HIERARCHICAL:
            return self._hierarchical_orthogonalize()
        else:
            return self._factor_model_orthogonalize()
    
    def _gram_schmidt_orthogonalize(self) -> OrthogonalizationResult:
        """
        Gram-Schmidt orthogonalization.
        
        Sequentially orthogonalizes each alpha against all previous ones.
        Order matters - alphas with higher Sharpe go first.
        """
        session_id = f"orth_gs_{int(time.time())}"
        
        # Sort alphas by Sharpe (best first)
        sorted_alphas = sorted(
            self.alphas.values(),
            key=lambda a: a.sharpe,
            reverse=True
        )
        
        # Store original correlation
        raw_corr_matrix = self.compute_correlation_matrix()
        avg_raw_corr = self._compute_avg_off_diagonal(raw_corr_matrix)
        
        # Orthogonalize
        orthogonal_basis = []
        redundant_ids = []
        
        for alpha in sorted_alphas:
            # Project out all previous basis vectors
            residual = alpha.returns.copy()
            
            for basis_alpha in orthogonal_basis:
                proj = self._project(residual, basis_alpha.residual_returns)
                residual = [residual[i] - proj[i] for i in range(len(residual))]
            
            # Check if residual is near-zero (redundant)
            residual_norm = math.sqrt(sum(r ** 2 for r in residual))
            
            if residual_norm < self.config.gs_tolerance:
                alpha.status = AlphaStatus.REDUNDANT
                redundant_ids.append(alpha.alpha_id)
            else:
                # Normalize
                residual = [r / residual_norm * alpha.volatility for r in residual]
                alpha.residual_returns = residual
                alpha.status = AlphaStatus.ORTHOGONALIZED
                
                # Update residual stats
                self._update_residual_stats(alpha)
                
                orthogonal_basis.append(alpha)
        
        # Compute new correlation matrix
        residual_corr_matrix = self._compute_residual_correlation_matrix()
        avg_residual_corr = self._compute_avg_off_diagonal(residual_corr_matrix)
        
        # Build result
        result = self._build_result(
            session_id=session_id,
            method=OrthogonalizationMethod.GRAM_SCHMIDT,
            redundant_ids=redundant_ids,
            avg_raw_corr=avg_raw_corr,
            avg_residual_corr=avg_residual_corr
        )
        
        self.results[session_id] = result
        return result
    
    def _factor_model_orthogonalize(self) -> OrthogonalizationResult:
        """
        Factor Model orthogonalization.
        
        1. Extract common factors via PCA
        2. Regress each alpha on common factors
        3. Use residuals as orthogonalized alpha
        """
        session_id = f"orth_fm_{int(time.time())}"
        
        if len(self.alphas) < 2:
            return self._build_empty_result(session_id, OrthogonalizationMethod.FACTOR_MODEL)
        
        # Store original correlation
        raw_corr_matrix = self.compute_correlation_matrix()
        avg_raw_corr = self._compute_avg_off_diagonal(raw_corr_matrix)
        
        # Step 1: Build return matrix
        alpha_ids = list(self.alphas.keys())
        returns_matrix = []
        for alpha_id in alpha_ids:
            returns_matrix.append(self.alphas[alpha_id].returns)
        
        # Step 2: Simple factor extraction (average of correlated alphas)
        common_factors = self._extract_common_factors(returns_matrix, alpha_ids)
        
        # Step 3: Residualize each alpha
        redundant_ids = []
        
        for alpha_id in alpha_ids:
            alpha = self.alphas[alpha_id]
            residual = alpha.returns.copy()
            total_r_squared = 0.0
            
            # Regress against each factor
            for factor in common_factors:
                if alpha_id not in factor.loadings:
                    continue
                
                loading = factor.loadings[alpha_id]
                n = min(len(residual), len(factor.returns))
                
                for i in range(n):
                    residual[i] -= loading * factor.returns[i]
                
                total_r_squared += loading ** 2 * self._variance(factor.returns) / max(0.0001, self._variance(alpha.returns))
            
            alpha.r_squared = min(1.0, total_r_squared)
            alpha.residual_variance_ratio = 1.0 - alpha.r_squared
            
            # Check if mostly explained by factors (redundant)
            if alpha.residual_variance_ratio < 0.1:
                alpha.status = AlphaStatus.REDUNDANT
                redundant_ids.append(alpha_id)
            else:
                alpha.residual_returns = residual
                alpha.status = AlphaStatus.ORTHOGONALIZED
                self._update_residual_stats(alpha)
        
        # Compute new correlation matrix
        residual_corr_matrix = self._compute_residual_correlation_matrix()
        avg_residual_corr = self._compute_avg_off_diagonal(residual_corr_matrix)
        
        # Build result
        result = self._build_result(
            session_id=session_id,
            method=OrthogonalizationMethod.FACTOR_MODEL,
            redundant_ids=redundant_ids,
            avg_raw_corr=avg_raw_corr,
            avg_residual_corr=avg_residual_corr,
            common_factors=common_factors
        )
        
        self.results[session_id] = result
        return result
    
    def _pca_orthogonalize(self) -> OrthogonalizationResult:
        """
        PCA-based orthogonalization.
        
        Uses first N principal components as orthogonal basis.
        """
        session_id = f"orth_pca_{int(time.time())}"
        
        # Store original correlation
        raw_corr_matrix = self.compute_correlation_matrix()
        avg_raw_corr = self._compute_avg_off_diagonal(raw_corr_matrix)
        
        # For simplicity, use factor model approach
        # Full PCA would require numpy/scipy
        result = self._factor_model_orthogonalize()
        result.session_id = session_id
        result.method = OrthogonalizationMethod.PCA
        
        self.results[session_id] = result
        return result
    
    def _hierarchical_orthogonalize(self) -> OrthogonalizationResult:
        """
        Hierarchical orthogonalization.
        
        1. Group alphas by family
        2. Orthogonalize within each family
        3. Then orthogonalize between families
        """
        session_id = f"orth_hier_{int(time.time())}"
        
        # Store original correlation
        raw_corr_matrix = self.compute_correlation_matrix()
        avg_raw_corr = self._compute_avg_off_diagonal(raw_corr_matrix)
        
        # Group by family
        families = defaultdict(list)
        for alpha_id, alpha in self.alphas.items():
            families[alpha.family or "default"].append(alpha)
        
        redundant_ids = []
        
        # Step 1: Orthogonalize within each family
        family_representatives = []
        
        for family, alphas in families.items():
            # Sort by Sharpe within family
            sorted_family = sorted(alphas, key=lambda a: a.sharpe, reverse=True)
            
            # Keep best, orthogonalize rest against it
            best = sorted_family[0]
            best.status = AlphaStatus.ORTHOGONALIZED
            family_representatives.append(best)
            
            for alpha in sorted_family[1:]:
                corr = self.compute_correlation(best.returns, alpha.returns)
                
                if abs(corr) > self.config.redundancy_threshold:
                    alpha.status = AlphaStatus.REDUNDANT
                    redundant_ids.append(alpha.alpha_id)
                else:
                    # Orthogonalize against family representative
                    proj = self._project(alpha.returns, best.returns)
                    alpha.residual_returns = [
                        alpha.returns[i] - proj[i] 
                        for i in range(len(alpha.returns))
                    ]
                    alpha.status = AlphaStatus.ORTHOGONALIZED
                    self._update_residual_stats(alpha)
        
        # Step 2: Orthogonalize between family representatives
        for i, rep in enumerate(family_representatives):
            for j in range(i):
                prev_rep = family_representatives[j]
                proj = self._project(rep.residual_returns, prev_rep.residual_returns)
                rep.residual_returns = [
                    rep.residual_returns[k] - proj[k]
                    for k in range(len(rep.residual_returns))
                ]
            self._update_residual_stats(rep)
        
        # Compute new correlation matrix
        residual_corr_matrix = self._compute_residual_correlation_matrix()
        avg_residual_corr = self._compute_avg_off_diagonal(residual_corr_matrix)
        
        result = self._build_result(
            session_id=session_id,
            method=OrthogonalizationMethod.HIERARCHICAL,
            redundant_ids=redundant_ids,
            avg_raw_corr=avg_raw_corr,
            avg_residual_corr=avg_residual_corr
        )
        
        self.results[session_id] = result
        return result
    
    # ============================================
    # Helper Methods
    # ============================================
    
    def _project(self, v: List[float], u: List[float]) -> List[float]:
        """Project vector v onto vector u"""
        n = min(len(v), len(u))
        
        dot_vu = sum(v[i] * u[i] for i in range(n))
        dot_uu = sum(u[i] * u[i] for i in range(n))
        
        if dot_uu == 0:
            return [0.0] * n
        
        scalar = dot_vu / dot_uu
        return [scalar * u[i] for i in range(n)]
    
    def _variance(self, returns: List[float]) -> float:
        """Compute variance of returns"""
        if not returns:
            return 0.0
        mean = sum(returns) / len(returns)
        return sum((r - mean) ** 2 for r in returns) / len(returns)
    
    def _update_residual_stats(self, alpha: AlphaVector):
        """Update residual statistics for an alpha"""
        if not alpha.residual_returns:
            return
        
        n = len(alpha.residual_returns)
        alpha.residual_mean = sum(alpha.residual_returns) / n
        
        variance = sum((r - alpha.residual_mean) ** 2 for r in alpha.residual_returns) / n
        alpha.residual_volatility = math.sqrt(variance) if variance > 0 else 0
        
        if alpha.residual_volatility > 0:
            alpha.residual_sharpe = alpha.residual_mean / alpha.residual_volatility * math.sqrt(252)
        else:
            alpha.residual_sharpe = 0
    
    def _compute_residual_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """Compute correlation matrix using residual returns"""
        alpha_ids = list(self.alphas.keys())
        matrix = {}
        
        for i, id1 in enumerate(alpha_ids):
            matrix[id1] = {}
            for j, id2 in enumerate(alpha_ids):
                if i == j:
                    matrix[id1][id2] = 1.0
                elif j < i:
                    matrix[id1][id2] = matrix[id2][id1]
                else:
                    corr = self.compute_correlation(
                        self.alphas[id1].residual_returns,
                        self.alphas[id2].residual_returns
                    )
                    matrix[id1][id2] = corr
        
        return matrix
    
    def _compute_avg_off_diagonal(self, matrix: Dict[str, Dict[str, float]]) -> float:
        """Compute average absolute off-diagonal correlation"""
        total = 0.0
        count = 0
        
        keys = list(matrix.keys())
        for i, k1 in enumerate(keys):
            for j, k2 in enumerate(keys):
                if i != j:
                    total += abs(matrix[k1][k2])
                    count += 1
        
        return total / count if count > 0 else 0.0
    
    def _extract_common_factors(
        self,
        returns_matrix: List[List[float]],
        alpha_ids: List[str]
    ) -> List[CommonFactor]:
        """Extract common factors (simplified approach)"""
        factors = []
        
        if len(returns_matrix) < 2:
            return factors
        
        n_series = len(returns_matrix)
        n_obs = min(len(r) for r in returns_matrix)
        
        # Factor 1: Market (equal-weighted average)
        market_returns = []
        for t in range(n_obs):
            avg = sum(returns_matrix[i][t] for i in range(n_series)) / n_series
            market_returns.append(avg)
        
        market_var = self._variance(market_returns)
        
        # Compute loadings (betas)
        loadings = {}
        for i, alpha_id in enumerate(alpha_ids):
            if len(returns_matrix[i]) >= n_obs:
                cov = sum(
                    returns_matrix[i][t] * market_returns[t] 
                    for t in range(n_obs)
                ) / n_obs
                
                beta = cov / market_var if market_var > 0 else 0
                loadings[alpha_id] = beta
        
        market_factor = CommonFactor(
            factor_id="F_MARKET",
            name="Market Factor",
            loadings=loadings,
            returns=market_returns,
            variance_explained=market_var,
            variance_explained_pct=0.0  # Would need total variance
        )
        factors.append(market_factor)
        
        return factors
    
    def _build_result(
        self,
        session_id: str,
        method: OrthogonalizationMethod,
        redundant_ids: List[str],
        avg_raw_corr: float,
        avg_residual_corr: float,
        common_factors: List[CommonFactor] = None
    ) -> OrthogonalizationResult:
        """Build orthogonalization result"""
        
        crowded_pairs = self.find_crowded_pairs()
        
        correlation_reduction = 0.0
        if avg_raw_corr > 0:
            correlation_reduction = (avg_raw_corr - avg_residual_corr) / avg_raw_corr * 100
        
        # Calculate portfolio Sharpe improvement
        non_redundant = [a for a in self.alphas.values() if a.status != AlphaStatus.REDUNDANT]
        
        raw_sharpes = [a.sharpe for a in self.alphas.values()]
        residual_sharpes = [a.residual_sharpe for a in non_redundant]
        
        raw_portfolio_sharpe = sum(raw_sharpes) / len(raw_sharpes) if raw_sharpes else 0
        orthogonal_portfolio_sharpe = sum(residual_sharpes) / len(residual_sharpes) if residual_sharpes else 0
        
        sharpe_improvement = 0.0
        if raw_portfolio_sharpe > 0:
            sharpe_improvement = (orthogonal_portfolio_sharpe - raw_portfolio_sharpe) / abs(raw_portfolio_sharpe) * 100
        
        return OrthogonalizationResult(
            session_id=session_id,
            method=method,
            input_alphas=len(self.alphas),
            output_alphas=len(non_redundant),
            redundant_alphas=len(redundant_ids),
            common_factors=common_factors or [],
            num_factors=len(common_factors) if common_factors else 0,
            avg_raw_correlation=round(avg_raw_corr, 4),
            avg_residual_correlation=round(avg_residual_corr, 4),
            correlation_reduction_pct=round(correlation_reduction, 2),
            raw_portfolio_sharpe=round(raw_portfolio_sharpe, 4),
            orthogonal_portfolio_sharpe=round(orthogonal_portfolio_sharpe, 4),
            sharpe_improvement_pct=round(sharpe_improvement, 2),
            redundant_alpha_ids=redundant_ids,
            crowded_pairs=crowded_pairs,
            created_at=int(time.time() * 1000)
        )
    
    def _build_empty_result(
        self,
        session_id: str,
        method: OrthogonalizationMethod
    ) -> OrthogonalizationResult:
        """Build empty result when not enough data"""
        return OrthogonalizationResult(
            session_id=session_id,
            method=method,
            input_alphas=len(self.alphas),
            output_alphas=len(self.alphas),
            created_at=int(time.time() * 1000)
        )
    
    # ============================================
    # Portfolio Construction
    # ============================================
    
    def build_orthogonal_portfolio(
        self,
        target_volatility: float = 0.15
    ) -> OrthogonalPortfolio:
        """Build portfolio using orthogonalized alphas"""
        
        portfolio_id = f"orth_port_{int(time.time())}"
        
        # Filter non-redundant alphas
        active_alphas = [
            a for a in self.alphas.values()
            if a.status != AlphaStatus.REDUNDANT
        ]
        
        if not active_alphas:
            return OrthogonalPortfolio(portfolio_id=portfolio_id)
        
        # Equal risk contribution weights (simplified)
        total_inv_vol = sum(
            1.0 / a.residual_volatility 
            for a in active_alphas 
            if a.residual_volatility > 0
        )
        
        weights = {}
        for alpha in active_alphas:
            if alpha.residual_volatility > 0 and total_inv_vol > 0:
                weight = (1.0 / alpha.residual_volatility) / total_inv_vol
            else:
                weight = 1.0 / len(active_alphas)
            weights[alpha.alpha_id] = round(weight, 4)
        
        # Portfolio metrics
        expected_return = sum(
            weights[a.alpha_id] * a.residual_mean
            for a in active_alphas
        )
        
        # Simplified volatility (assumes zero correlation after orthogonalization)
        portfolio_variance = sum(
            (weights[a.alpha_id] ** 2) * (a.residual_volatility ** 2)
            for a in active_alphas
        )
        portfolio_volatility = math.sqrt(portfolio_variance)
        
        portfolio_sharpe = 0.0
        if portfolio_volatility > 0:
            portfolio_sharpe = expected_return / portfolio_volatility * math.sqrt(252)
        
        # Correlation matrix
        corr_matrix = self._compute_residual_correlation_matrix()
        
        # Max and avg correlation
        max_corr = 0.0
        total_corr = 0.0
        count = 0
        
        active_ids = [a.alpha_id for a in active_alphas]
        for i, id1 in enumerate(active_ids):
            for j, id2 in enumerate(active_ids):
                if i < j:
                    corr = abs(corr_matrix.get(id1, {}).get(id2, 0))
                    max_corr = max(max_corr, corr)
                    total_corr += corr
                    count += 1
        
        avg_corr = total_corr / count if count > 0 else 0
        
        return OrthogonalPortfolio(
            portfolio_id=portfolio_id,
            alphas=active_alphas,
            weights=weights,
            expected_return=round(expected_return * 252, 4),  # Annualized
            portfolio_volatility=round(portfolio_volatility * math.sqrt(252), 4),
            portfolio_sharpe=round(portfolio_sharpe, 4),
            correlation_matrix=corr_matrix,
            max_correlation=round(max_corr, 4),
            avg_correlation=round(avg_corr, 4)
        )


# Singleton instance
orthogonal_engine = OrthogonalAlphaEngine()
