"""
Orthogonal Alpha Service
========================

Phase 9.3G - Service layer for alpha orthogonalization.
"""

import time
from typing import Dict, List, Optional, Any

from .types import (
    OrthogonalizationConfig, OrthogonalizationMethod,
    OrthogonalizationResult, OrthogonalPortfolio, AlphaStatus
)
from .engine import OrthogonalAlphaEngine


class OrthogonalAlphaService:
    """
    Service for managing alpha orthogonalization.
    
    Provides:
    - Alpha ingestion
    - Orthogonalization execution
    - Portfolio construction
    - Analysis and reporting
    """
    
    def __init__(self):
        self.engines: Dict[str, OrthogonalAlphaEngine] = {}
        self.default_config = OrthogonalizationConfig()
    
    # ============================================
    # Engine Management
    # ============================================
    
    def create_session(
        self,
        session_id: Optional[str] = None,
        method: str = "factor_model",
        redundancy_threshold: float = 0.90,
        crowding_threshold: float = 0.70
    ) -> str:
        """Create new orthogonalization session"""
        
        if not session_id:
            session_id = f"orth_session_{int(time.time())}"
        
        try:
            orth_method = OrthogonalizationMethod(method)
        except ValueError:
            orth_method = OrthogonalizationMethod.FACTOR_MODEL
        
        config = OrthogonalizationConfig(
            method=orth_method,
            redundancy_threshold=redundancy_threshold,
            crowding_threshold=crowding_threshold
        )
        
        engine = OrthogonalAlphaEngine(config)
        self.engines[session_id] = engine
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[OrthogonalAlphaEngine]:
        """Get session engine"""
        return self.engines.get(session_id)
    
    def list_sessions(self) -> List[Dict]:
        """List all sessions"""
        return [
            {
                "session_id": sid,
                "num_alphas": len(engine.alphas),
                "method": engine.config.method.value
            }
            for sid, engine in self.engines.items()
        ]
    
    # ============================================
    # Alpha Management
    # ============================================
    
    def add_alpha(
        self,
        session_id: str,
        alpha_id: str,
        returns: List[float],
        family: str = ""
    ) -> Dict:
        """Add alpha to session"""
        
        engine = self.get_session(session_id)
        if not engine:
            return {"error": f"Session not found: {session_id}"}
        
        alpha = engine.add_alpha(alpha_id, returns, family)
        
        return {
            "alpha_id": alpha.alpha_id,
            "family": alpha.family,
            "mean_return": round(alpha.mean_return * 252, 4),
            "volatility": round(alpha.volatility * 16, 4),  # Annualized (sqrt(252))
            "sharpe": round(alpha.sharpe, 4),
            "num_observations": len(returns)
        }
    
    def add_alphas_batch(
        self,
        session_id: str,
        alphas: List[Dict]
    ) -> Dict:
        """Add multiple alphas at once"""
        
        engine = self.get_session(session_id)
        if not engine:
            return {"error": f"Session not found: {session_id}"}
        
        results = []
        for alpha_data in alphas:
            alpha = engine.add_alpha(
                alpha_id=alpha_data.get("alpha_id", f"alpha_{len(results)}"),
                returns=alpha_data.get("returns", []),
                family=alpha_data.get("family", "")
            )
            results.append({
                "alpha_id": alpha.alpha_id,
                "sharpe": round(alpha.sharpe, 4)
            })
        
        return {
            "added": len(results),
            "alphas": results
        }
    
    def get_alphas(self, session_id: str) -> Dict:
        """Get all alphas in session"""
        
        engine = self.get_session(session_id)
        if not engine:
            return {"error": f"Session not found: {session_id}"}
        
        alphas = []
        for alpha in engine.alphas.values():
            alphas.append({
                "alpha_id": alpha.alpha_id,
                "family": alpha.family,
                "sharpe": round(alpha.sharpe, 4),
                "residual_sharpe": round(alpha.residual_sharpe, 4),
                "status": alpha.status.value,
                "r_squared": round(alpha.r_squared, 4)
            })
        
        return {
            "session_id": session_id,
            "num_alphas": len(alphas),
            "alphas": alphas
        }
    
    # ============================================
    # Orthogonalization
    # ============================================
    
    def run_orthogonalization(self, session_id: str) -> Dict:
        """Run orthogonalization on session"""
        
        engine = self.get_session(session_id)
        if not engine:
            return {"error": f"Session not found: {session_id}"}
        
        if len(engine.alphas) < 2:
            return {"error": "Need at least 2 alphas for orthogonalization"}
        
        result = engine.orthogonalize()
        
        return self._result_to_dict(result)
    
    def get_result(self, session_id: str, result_id: str) -> Optional[Dict]:
        """Get orthogonalization result"""
        
        engine = self.get_session(session_id)
        if not engine:
            return None
        
        result = engine.results.get(result_id)
        if not result:
            return None
        
        return self._result_to_dict(result)
    
    # ============================================
    # Analysis
    # ============================================
    
    def get_correlation_matrix(self, session_id: str, use_residuals: bool = False) -> Dict:
        """Get correlation matrix"""
        
        engine = self.get_session(session_id)
        if not engine:
            return {"error": f"Session not found: {session_id}"}
        
        if use_residuals:
            matrix = engine._compute_residual_correlation_matrix()
            matrix_type = "residual"
        else:
            matrix = engine.compute_correlation_matrix()
            matrix_type = "raw"
        
        # Round values
        rounded_matrix = {}
        for k1, row in matrix.items():
            rounded_matrix[k1] = {k2: round(v, 4) for k2, v in row.items()}
        
        return {
            "session_id": session_id,
            "matrix_type": matrix_type,
            "matrix": rounded_matrix
        }
    
    def get_crowded_pairs(self, session_id: str) -> Dict:
        """Get list of crowded pairs"""
        
        engine = self.get_session(session_id)
        if not engine:
            return {"error": f"Session not found: {session_id}"}
        
        pairs = engine.find_crowded_pairs()
        
        return {
            "session_id": session_id,
            "num_pairs": len(pairs),
            "pairs": [
                {
                    "alpha_1": p.alpha_1,
                    "alpha_2": p.alpha_2,
                    "correlation": round(p.raw_correlation, 4),
                    "is_redundant": p.is_redundant
                }
                for p in pairs
            ]
        }
    
    def get_redundant_alphas(self, session_id: str) -> Dict:
        """Get list of redundant alphas"""
        
        engine = self.get_session(session_id)
        if not engine:
            return {"error": f"Session not found: {session_id}"}
        
        redundant = [
            {
                "alpha_id": a.alpha_id,
                "family": a.family,
                "sharpe": round(a.sharpe, 4),
                "r_squared": round(a.r_squared, 4)
            }
            for a in engine.alphas.values()
            if a.status == AlphaStatus.REDUNDANT
        ]
        
        return {
            "session_id": session_id,
            "num_redundant": len(redundant),
            "redundant_alphas": redundant
        }
    
    # ============================================
    # Portfolio Construction
    # ============================================
    
    def build_portfolio(
        self,
        session_id: str,
        target_volatility: float = 0.15
    ) -> Dict:
        """Build orthogonal portfolio"""
        
        engine = self.get_session(session_id)
        if not engine:
            return {"error": f"Session not found: {session_id}"}
        
        portfolio = engine.build_orthogonal_portfolio(target_volatility)
        
        return {
            "portfolio_id": portfolio.portfolio_id,
            "num_alphas": len(portfolio.alphas),
            "weights": portfolio.weights,
            "expected_return": portfolio.expected_return,
            "portfolio_volatility": portfolio.portfolio_volatility,
            "portfolio_sharpe": portfolio.portfolio_sharpe,
            "max_correlation": portfolio.max_correlation,
            "avg_correlation": portfolio.avg_correlation
        }
    
    # ============================================
    # Health Check
    # ============================================
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.3G",
            "status": "ok",
            "active_sessions": len(self.engines),
            "supported_methods": [m.value for m in OrthogonalizationMethod],
            "timestamp": int(time.time() * 1000)
        }
    
    # ============================================
    # Helpers
    # ============================================
    
    def _result_to_dict(self, result: OrthogonalizationResult) -> Dict:
        """Convert result to dict"""
        return {
            "session_id": result.session_id,
            "method": result.method.value,
            "input_alphas": result.input_alphas,
            "output_alphas": result.output_alphas,
            "redundant_alphas": result.redundant_alphas,
            "num_factors": result.num_factors,
            "correlation_improvement": {
                "raw_avg": result.avg_raw_correlation,
                "residual_avg": result.avg_residual_correlation,
                "reduction_pct": result.correlation_reduction_pct
            },
            "sharpe_improvement": {
                "raw_portfolio": result.raw_portfolio_sharpe,
                "orthogonal_portfolio": result.orthogonal_portfolio_sharpe,
                "improvement_pct": result.sharpe_improvement_pct
            },
            "redundant_alpha_ids": result.redundant_alpha_ids,
            "crowded_pairs_count": len(result.crowded_pairs),
            "created_at": result.created_at
        }


# Singleton instance
orthogonal_service = OrthogonalAlphaService()
