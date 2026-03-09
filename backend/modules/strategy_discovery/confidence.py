"""
Phase 9.5: Confidence Calculator
Combines robustness and similarity into final confidence score
"""
from typing import Dict, Optional, List, Any
from .types import (
    ConfidenceScore, 
    RobustnessScore, 
    SimilarityPenalty,
    VALIDATION_THRESHOLDS
)


class ConfidenceCalculator:
    """
    Calculates final confidence score for a strategy.
    
    Combines:
    1. Robustness score (positive contribution)
    2. Similarity penalty (negative contribution)
    3. Evidence quality (trade count, regime coverage)
    4. Metric stability (consistency across time/regime)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or VALIDATION_THRESHOLDS
        
    def calculate(
        self, 
        strategy: Dict[str, Any],
        robustness: RobustnessScore,
        similarity: SimilarityPenalty
    ) -> ConfidenceScore:
        """
        Calculate final confidence score for a strategy.
        
        Args:
            strategy: Strategy dict with metrics
            robustness: Robustness assessment
            similarity: Similarity penalty assessment
            
        Returns:
            ConfidenceScore with verdict and breakdown
        """
        reasons = []
        
        # 1. Robustness component (0-1)
        robustness_component = robustness.overall_score
        
        # 2. Similarity component (penalty, 0-1 becomes -0.3 to 0)
        similarity_component = self._calculate_similarity_component(similarity)
        
        # 3. Evidence component (based on trade count and coverage)
        evidence_component = self._calculate_evidence_component(strategy, robustness)
        
        # 4. Regime stability component
        regime_stability_component = self._calculate_regime_stability(strategy, robustness)
        
        # Weights for each component
        weights = {
            "robustness": 0.40,
            "similarity": 0.15,  # This is subtracted, not added
            "evidence": 0.20,
            "regime_stability": 0.25
        }
        
        # Calculate weighted score
        raw_score = (
            weights["robustness"] * robustness_component +
            weights["evidence"] * evidence_component +
            weights["regime_stability"] * regime_stability_component
        )
        
        # Apply similarity penalty (subtractive)
        final_score = raw_score + (weights["similarity"] * similarity_component)
        final_score = max(0.0, min(1.0, final_score))
        
        # Generate verdict
        verdict, verdict_reasons = self._determine_verdict(
            final_score, robustness, similarity
        )
        reasons.extend(verdict_reasons)
        
        # Build breakdown
        breakdown = {
            "robustness": round(robustness_component, 4),
            "similarity_penalty": round(similarity_component, 4),
            "evidence": round(evidence_component, 4),
            "regime_stability": round(regime_stability_component, 4),
            "raw_score": round(raw_score, 4),
            "final_score": round(final_score, 4)
        }
        
        return ConfidenceScore(
            score=round(final_score, 4),
            robustness_component=round(robustness_component, 4),
            similarity_component=round(similarity_component, 4),
            evidence_component=round(evidence_component, 4),
            regime_stability_component=round(regime_stability_component, 4),
            breakdown=breakdown,
            verdict=verdict,
            reasons=reasons
        )
    
    def _calculate_similarity_component(
        self, 
        similarity: SimilarityPenalty
    ) -> float:
        """
        Convert similarity penalty to score component.
        High similarity = negative contribution.
        """
        if similarity.is_redundant:
            return -0.3  # Heavy penalty for redundant strategies
        
        # Linear penalty: 0 similarity = 0, 0.75 similarity = -0.2
        penalty = -similarity.penalty * 0.3
        
        return max(-0.3, penalty)
    
    def _calculate_evidence_component(
        self, 
        strategy: Dict[str, Any],
        robustness: RobustnessScore
    ) -> float:
        """
        Calculate evidence quality component.
        Based on trade count and regime coverage.
        """
        metrics = strategy.get("metrics", {})
        total_trades = metrics.get("trades", 0)
        min_trades = self.config.get("min_trades", 30)
        
        # Trade count score (0-1)
        # 30 trades = 0.5, 100 trades = 0.8, 200+ = 1.0
        trade_score = min(1.0, 0.3 + (total_trades / 300))
        
        # Regime coverage bonus
        coverage_score = robustness.regime_coverage
        
        # Combined evidence score
        return 0.6 * trade_score + 0.4 * coverage_score
    
    def _calculate_regime_stability(
        self, 
        strategy: Dict[str, Any],
        robustness: RobustnessScore
    ) -> float:
        """
        Calculate stability across regimes.
        Low variance = high stability = high score.
        """
        regime_scores = robustness.regime_scores
        
        if not regime_scores or len(regime_scores) < 2:
            return 0.5  # Neutral if can't assess
        
        scores = list(regime_scores.values())
        mean_score = sum(scores) / len(scores)
        
        # Calculate variance
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        std_dev = variance ** 0.5
        
        # Lower std_dev = higher stability
        # std_dev of 0.1 = 0.8 stability, std_dev of 0.3 = 0.4 stability
        stability = max(0, 1.0 - std_dev * 2)
        
        # Bonus for temporal stability from robustness
        temporal_bonus = (robustness.temporal_stability - 0.5) * 0.2
        
        return min(1.0, stability + temporal_bonus)
    
    def _determine_verdict(
        self, 
        score: float,
        robustness: RobustnessScore,
        similarity: SimilarityPenalty
    ) -> tuple:
        """
        Determine final verdict based on score and components.
        
        Returns:
            (verdict, reasons)
        """
        reasons = []
        
        # Check for automatic rejection conditions
        if similarity.is_redundant:
            reasons.append("Strategy is too similar to existing strategies")
            return "REJECT", reasons
        
        if not robustness.minimum_evidence:
            reasons.append("Insufficient evidence (trades) for validation")
            return "NEEDS_MORE_DATA", reasons
        
        if robustness.overall_score < self.config.get("min_robustness", 0.5):
            reasons.append(f"Low robustness score: {robustness.overall_score:.2f}")
        
        # Determine verdict based on score
        strong_threshold = self.config.get("strong_confidence", 0.75)
        moderate_threshold = self.config.get("moderate_confidence", 0.55)
        weak_threshold = self.config.get("weak_confidence", 0.40)
        
        if score >= strong_threshold:
            verdict = "STRONG"
            reasons.append(f"High confidence ({score:.2f}) - recommended for approval")
            
            if robustness.temporal_stability > 0.7:
                reasons.append("Strong out-of-sample performance")
            if robustness.regime_coverage > 0.6:
                reasons.append("Good regime coverage")
                
        elif score >= moderate_threshold:
            verdict = "MODERATE"
            reasons.append(f"Moderate confidence ({score:.2f}) - proceed with caution")
            
            if robustness.weakest_regime:
                reasons.append(f"Weak in regime: {robustness.weakest_regime}")
                
        elif score >= weak_threshold:
            verdict = "WEAK"
            reasons.append(f"Low confidence ({score:.2f}) - needs improvement")
            
            if robustness.regime_coverage < 0.5:
                reasons.append("Poor regime coverage - test in more conditions")
                
        else:
            verdict = "REJECT"
            reasons.append(f"Very low confidence ({score:.2f}) - not recommended")
            
            if similarity.penalty > 0.5:
                reasons.append(f"High similarity to existing strategies ({similarity.penalty:.2f})")
        
        return verdict, reasons
    
    def quick_score(self, strategy: Dict[str, Any]) -> float:
        """
        Quick confidence estimate without full analysis.
        Useful for filtering before detailed validation.
        """
        metrics = strategy.get("metrics", {})
        
        # Base score from win rate
        win_rate = metrics.get("winRate", 0.5)
        wr_score = (win_rate - 0.45) * 3  # 0.45-0.75 -> 0-0.9
        wr_score = max(0, min(0.9, wr_score))
        
        # Profit factor bonus
        pf = metrics.get("profitFactor", 1.0)
        pf_bonus = min(0.2, (pf - 1.0) * 0.1)
        
        # Trade count factor
        trades = metrics.get("trades", 0)
        trade_factor = min(1.0, trades / 100)
        
        # Status bonus
        status_bonus = {
            "APPROVED": 0.1,
            "TESTING": 0.0,
            "CANDIDATE": -0.05
        }.get(strategy.get("status", "CANDIDATE"), 0)
        
        return round(min(1.0, (wr_score + pf_bonus) * trade_factor + status_bonus), 4)
