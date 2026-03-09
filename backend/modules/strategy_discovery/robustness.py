"""
Phase 9.5: Robustness Engine
Calculates robustness score across market regimes and assets
"""
from typing import Dict, List, Optional, Any
import math
from .types import (
    RobustnessScore, 
    RegimeMetrics,
    RegimeType,
    VALIDATION_THRESHOLDS
)


class RobustnessEngine:
    """
    Calculates robustness score for discovered strategies.
    
    Key checks:
    1. Minimum evidence (enough trades)
    2. Regime robustness (works in different market conditions)
    3. Cross-asset validation (works on multiple assets)
    4. Temporal stability (consistent over time)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or VALIDATION_THRESHOLDS
        
    def calculate(self, strategy: Dict[str, Any]) -> RobustnessScore:
        """
        Calculate comprehensive robustness score for a strategy.
        
        Args:
            strategy: Strategy dict with metrics, regimeBreakdown, etc.
            
        Returns:
            RobustnessScore with detailed breakdown
        """
        notes = []
        
        # 1. Check minimum evidence
        total_trades = strategy.get("metrics", {}).get("trades", 0)
        min_trades = self.config.get("min_trades", 30)
        has_minimum_evidence = total_trades >= min_trades
        
        if not has_minimum_evidence:
            notes.append(f"Insufficient trades: {total_trades} < {min_trades}")
        
        # 2. Calculate regime robustness
        regime_breakdown = strategy.get("regimeBreakdown", {})
        regime_scores = self._calculate_regime_scores(regime_breakdown, notes)
        
        # 3. Check regime coverage
        min_regimes = self.config.get("min_regimes_tested", 2)
        regimes_tested = len([r for r in regime_breakdown.values() 
                             if r.get("trades", 0) >= self.config.get("min_trades_per_regime", 10)])
        regime_coverage = regimes_tested / max(len(RegimeType), 3)
        
        if regimes_tested < min_regimes:
            notes.append(f"Low regime coverage: {regimes_tested}/{min_regimes} regimes tested")
        
        # 4. Find weakest regime
        weakest_regime = None
        min_score = 1.0
        for regime, score in regime_scores.items():
            if score < min_score:
                min_score = score
                weakest_regime = regime
        
        # 5. Calculate temporal stability (from in-sample vs out-of-sample)
        metrics = strategy.get("metrics", {})
        in_sample_wr = metrics.get("inSampleWinRate", 0.5)
        out_sample_wr = metrics.get("outOfSampleWinRate", 0.5)
        temporal_stability = self._calculate_temporal_stability(in_sample_wr, out_sample_wr)
        
        if temporal_stability < 0.6:
            notes.append(f"Low temporal stability: {temporal_stability:.2f} (IS: {in_sample_wr:.2f}, OOS: {out_sample_wr:.2f})")
        
        # 6. Cross-asset score (placeholder - use robustness as proxy)
        cross_asset_score = strategy.get("robustness", 0.5)
        
        # 7. Calculate overall robustness score
        overall_score = self._aggregate_scores(
            regime_scores=regime_scores,
            regime_coverage=regime_coverage,
            temporal_stability=temporal_stability,
            cross_asset_score=cross_asset_score,
            has_minimum_evidence=has_minimum_evidence
        )
        
        if overall_score >= 0.7:
            notes.append("Strong robustness profile")
        elif overall_score >= 0.5:
            notes.append("Moderate robustness - proceed with caution")
        else:
            notes.append("Weak robustness - high risk of false edge")
        
        return RobustnessScore(
            overall_score=round(overall_score, 4),
            regime_scores=regime_scores,
            cross_asset_score=round(cross_asset_score, 4),
            temporal_stability=round(temporal_stability, 4),
            minimum_evidence=has_minimum_evidence,
            regime_coverage=round(regime_coverage, 4),
            weakest_regime=weakest_regime,
            notes=notes
        )
    
    def _calculate_regime_scores(
        self, 
        regime_breakdown: Dict[str, Dict], 
        notes: List[str]
    ) -> Dict[str, float]:
        """Calculate score for each regime based on performance"""
        regime_scores = {}
        min_wr = self.config.get("min_regime_win_rate", 0.45)
        min_trades = self.config.get("min_trades_per_regime", 10)
        
        for regime, data in regime_breakdown.items():
            trades = data.get("trades", 0)
            win_rate = data.get("winRate", 0.5)
            
            # Score components
            wr_score = min(1.0, (win_rate - 0.4) / 0.3)  # 0.4-0.7 mapped to 0-1
            evidence_score = min(1.0, trades / (min_trades * 2))  # Linear up to 2x min
            
            # Penalize if below minimum win rate
            if win_rate < min_wr:
                wr_score *= 0.5
                notes.append(f"Low win rate in {regime}: {win_rate:.2f}")
            
            # Penalize if insufficient trades
            if trades < min_trades:
                evidence_score *= 0.3
                
            # Combined score for this regime
            regime_scores[regime] = round(0.7 * wr_score + 0.3 * evidence_score, 4)
        
        return regime_scores
    
    def _calculate_temporal_stability(
        self, 
        in_sample_wr: float, 
        out_sample_wr: float
    ) -> float:
        """
        Calculate temporal stability from in-sample vs out-of-sample performance.
        High stability = similar performance in both periods.
        """
        if in_sample_wr <= 0 or out_sample_wr <= 0:
            return 0.5
            
        # Calculate degradation ratio
        degradation = abs(in_sample_wr - out_sample_wr) / max(in_sample_wr, 0.01)
        
        # Convert to stability score (less degradation = higher stability)
        stability = max(0, 1.0 - degradation * 2)
        
        # Bonus if OOS is actually better (rare but good)
        if out_sample_wr > in_sample_wr:
            stability = min(1.0, stability + 0.1)
            
        return stability
    
    def _aggregate_scores(
        self,
        regime_scores: Dict[str, float],
        regime_coverage: float,
        temporal_stability: float,
        cross_asset_score: float,
        has_minimum_evidence: bool
    ) -> float:
        """
        Aggregate all components into final robustness score.
        Uses weighted average with evidence gate.
        """
        # Gate: if no minimum evidence, cap score
        evidence_multiplier = 1.0 if has_minimum_evidence else 0.5
        
        # Average regime score
        if regime_scores:
            avg_regime_score = sum(regime_scores.values()) / len(regime_scores)
            # Penalize high variance across regimes
            regime_variance = self._calculate_variance(list(regime_scores.values()))
            max_variance = self.config.get("max_regime_variance", 0.20)
            variance_penalty = max(0, (regime_variance - max_variance) / max_variance)
            avg_regime_score = max(0, avg_regime_score - variance_penalty * 0.2)
        else:
            avg_regime_score = 0.3
        
        # Weighted combination
        weights = {
            "regime": 0.35,
            "coverage": 0.15,
            "temporal": 0.25,
            "cross_asset": 0.25
        }
        
        score = (
            weights["regime"] * avg_regime_score +
            weights["coverage"] * regime_coverage +
            weights["temporal"] * temporal_stability +
            weights["cross_asset"] * cross_asset_score
        )
        
        return min(1.0, score * evidence_multiplier)
    
    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of a list of values"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)
