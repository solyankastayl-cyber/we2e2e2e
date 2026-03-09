"""
Phase 9.5: Edge Validation Service
Main service orchestrating edge validation for discovered strategies
"""
from typing import Dict, List, Optional, Any
import time
from dataclasses import asdict

from .types import (
    EdgeValidationResult,
    StrategyStatus,
    VALIDATION_THRESHOLDS
)
from .robustness import RobustnessEngine
from .similarity import SimilarityEngine
from .confidence import ConfidenceCalculator
from .lifecycle import StrategyLifecycle


class EdgeValidationService:
    """
    Main service for validating strategy edge.
    
    Orchestrates:
    1. Robustness calculation
    2. Similarity penalty calculation
    3. Confidence scoring
    4. Lifecycle management
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or VALIDATION_THRESHOLDS
        
        # Initialize engines
        self.robustness_engine = RobustnessEngine(self.config)
        self.similarity_engine = SimilarityEngine(self.config)
        self.confidence_calculator = ConfidenceCalculator(self.config)
        self.lifecycle_manager = StrategyLifecycle(self.config)
    
    def validate_strategy(
        self, 
        strategy: Dict[str, Any],
        existing_strategies: List[Dict[str, Any]] = None
    ) -> EdgeValidationResult:
        """
        Perform full edge validation on a single strategy.
        
        Args:
            strategy: Strategy dict to validate
            existing_strategies: List of existing strategies for similarity check
            
        Returns:
            EdgeValidationResult with all assessments
        """
        existing_strategies = existing_strategies or []
        notes = []
        
        # 1. Calculate robustness
        robustness = self.robustness_engine.calculate(strategy)
        
        # 2. Calculate similarity penalty
        similarity = self.similarity_engine.calculate(strategy, existing_strategies)
        
        # 3. Calculate confidence score
        confidence = self.confidence_calculator.calculate(
            strategy, robustness, similarity
        )
        
        # 4. Determine lifecycle action
        action, recommended_status = self.lifecycle_manager.determine_action(
            strategy, confidence
        )
        
        # Build notes
        notes.extend(robustness.notes)
        notes.extend(similarity.notes)
        notes.extend(confidence.reasons)
        
        return EdgeValidationResult(
            strategy_id=strategy.get("id", "unknown"),
            robustness=robustness,
            similarity=similarity,
            confidence=confidence,
            recommended_status=recommended_status,
            lifecycle_action=action,
            timestamp=int(time.time() * 1000),
            notes=notes
        )
    
    def validate_batch(
        self, 
        strategies: List[Dict[str, Any]]
    ) -> Dict[str, EdgeValidationResult]:
        """
        Validate multiple strategies at once.
        
        Uses the existing (already validated) strategies for similarity comparison.
        
        Returns:
            Dict mapping strategy_id -> EdgeValidationResult
        """
        results = {}
        
        # Sort by status - validate APPROVED/TESTING first (they become "existing")
        sorted_strategies = sorted(
            strategies,
            key=lambda s: {"APPROVED": 0, "TESTING": 1}.get(s.get("status"), 2)
        )
        
        existing = []
        for strategy in sorted_strategies:
            # Validate against already-validated strategies
            result = self.validate_strategy(strategy, existing)
            results[strategy.get("id")] = result
            
            # Add to existing pool if not redundant
            if not result.similarity.is_redundant:
                existing.append(strategy)
        
        return results
    
    def apply_validation(
        self, 
        strategies: List[Dict[str, Any]],
        validation_results: Dict[str, EdgeValidationResult]
    ) -> List[Dict[str, Any]]:
        """
        Apply validation results to update strategy statuses.
        
        Returns:
            Updated list of strategies
        """
        return self.lifecycle_manager.batch_evaluate(strategies, validation_results)
    
    def get_validation_summary(
        self, 
        validation_results: Dict[str, EdgeValidationResult]
    ) -> Dict[str, Any]:
        """
        Generate summary of validation results.
        """
        verdicts = {"STRONG": 0, "MODERATE": 0, "WEAK": 0, "REJECT": 0, "NEEDS_MORE_DATA": 0}
        actions = {"PROMOTE": 0, "DEMOTE": 0, "HOLD": 0, "DEPRECATE": 0}
        
        total_confidence = 0
        total_robustness = 0
        redundant_count = 0
        
        for result in validation_results.values():
            verdicts[result.confidence.verdict] = verdicts.get(result.confidence.verdict, 0) + 1
            actions[result.lifecycle_action] = actions.get(result.lifecycle_action, 0) + 1
            total_confidence += result.confidence.score
            total_robustness += result.robustness.overall_score
            
            if result.similarity.is_redundant:
                redundant_count += 1
        
        count = len(validation_results)
        
        return {
            "totalValidated": count,
            "verdictDistribution": verdicts,
            "actionDistribution": actions,
            "averageConfidence": round(total_confidence / max(count, 1), 4),
            "averageRobustness": round(total_robustness / max(count, 1), 4),
            "redundantStrategies": redundant_count,
            "promotionRate": round(actions["PROMOTE"] / max(count, 1), 4),
            "rejectionRate": round((actions["DEMOTE"] + actions["DEPRECATE"]) / max(count, 1), 4),
            "timestamp": int(time.time() * 1000)
        }
    
    def quick_filter(
        self, 
        strategies: List[Dict[str, Any]],
        min_confidence: float = 0.4
    ) -> List[Dict[str, Any]]:
        """
        Quick filter strategies by estimated confidence.
        Useful for pre-filtering before full validation.
        """
        filtered = []
        
        for strategy in strategies:
            quick_score = self.confidence_calculator.quick_score(strategy)
            if quick_score >= min_confidence:
                filtered.append(strategy)
        
        return filtered
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health status"""
        return {
            "enabled": True,
            "version": "edge_validation_v1_phase9.5",
            "status": "ok",
            "components": {
                "robustness_engine": "ok",
                "similarity_engine": "ok",
                "confidence_calculator": "ok",
                "lifecycle_manager": "ok"
            },
            "thresholds": {
                "min_trades": self.config.get("min_trades"),
                "min_robustness": self.config.get("min_robustness"),
                "max_similarity": self.config.get("max_similarity"),
                "strong_confidence": self.config.get("strong_confidence"),
                "promote_threshold": self.config.get("promote_threshold")
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


# Helper function to convert dataclass to dict for JSON serialization
def validation_result_to_dict(result: EdgeValidationResult) -> Dict[str, Any]:
    """Convert EdgeValidationResult to JSON-serializable dict"""
    return {
        "strategyId": result.strategy_id,
        "robustness": {
            "overallScore": result.robustness.overall_score,
            "regimeScores": result.robustness.regime_scores,
            "crossAssetScore": result.robustness.cross_asset_score,
            "temporalStability": result.robustness.temporal_stability,
            "minimumEvidence": result.robustness.minimum_evidence,
            "regimeCoverage": result.robustness.regime_coverage,
            "weakestRegime": result.robustness.weakest_regime,
            "notes": result.robustness.notes
        },
        "similarity": {
            "penalty": result.similarity.penalty,
            "similarStrategies": result.similarity.similar_strategies,
            "overlapFeatures": result.similarity.overlap_features,
            "correlation": result.similarity.correlation,
            "isRedundant": result.similarity.is_redundant,
            "notes": result.similarity.notes
        },
        "confidence": {
            "score": result.confidence.score,
            "robustnessComponent": result.confidence.robustness_component,
            "similarityComponent": result.confidence.similarity_component,
            "evidenceComponent": result.confidence.evidence_component,
            "regimeStabilityComponent": result.confidence.regime_stability_component,
            "breakdown": result.confidence.breakdown,
            "verdict": result.confidence.verdict,
            "reasons": result.confidence.reasons
        },
        "recommendedStatus": result.recommended_status.value,
        "lifecycleAction": result.lifecycle_action,
        "timestamp": result.timestamp,
        "notes": result.notes
    }
