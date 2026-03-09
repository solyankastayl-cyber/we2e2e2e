"""
Phase 9.5: Strategy Lifecycle Manager
Handles promotion, demotion, and deprecation of strategies
"""
from typing import Dict, Optional, List, Any, Tuple
import time
from .types import (
    StrategyStatus,
    ConfidenceScore,
    EdgeValidationResult,
    VALIDATION_THRESHOLDS
)


class StrategyLifecycle:
    """
    Manages strategy lifecycle transitions based on validation results.
    
    Lifecycle states:
    CANDIDATE -> TESTING -> APPROVED
                        \-> QUARANTINE -> DEPRECATED
    
    Transitions based on confidence score and performance.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or VALIDATION_THRESHOLDS
        
        # State transition rules
        self.transitions = {
            StrategyStatus.CANDIDATE: {
                "PROMOTE": StrategyStatus.TESTING,
                "DEMOTE": StrategyStatus.QUARANTINE,
                "HOLD": StrategyStatus.CANDIDATE,
                "DEPRECATE": StrategyStatus.DEPRECATED
            },
            StrategyStatus.TESTING: {
                "PROMOTE": StrategyStatus.APPROVED,
                "DEMOTE": StrategyStatus.CANDIDATE,
                "HOLD": StrategyStatus.TESTING,
                "DEPRECATE": StrategyStatus.QUARANTINE
            },
            StrategyStatus.APPROVED: {
                "PROMOTE": StrategyStatus.APPROVED,  # Already at top
                "DEMOTE": StrategyStatus.TESTING,
                "HOLD": StrategyStatus.APPROVED,
                "DEPRECATE": StrategyStatus.QUARANTINE
            },
            StrategyStatus.QUARANTINE: {
                "PROMOTE": StrategyStatus.TESTING,
                "DEMOTE": StrategyStatus.DEPRECATED,
                "HOLD": StrategyStatus.QUARANTINE,
                "DEPRECATE": StrategyStatus.DEPRECATED
            },
            StrategyStatus.DEPRECATED: {
                "PROMOTE": StrategyStatus.QUARANTINE,  # Can be rehabilitated
                "DEMOTE": StrategyStatus.DEPRECATED,
                "HOLD": StrategyStatus.DEPRECATED,
                "DEPRECATE": StrategyStatus.DEPRECATED
            }
        }
    
    def determine_action(
        self, 
        strategy: Dict[str, Any],
        confidence: ConfidenceScore
    ) -> Tuple[str, StrategyStatus]:
        """
        Determine lifecycle action based on confidence score.
        
        Args:
            strategy: Strategy dict with current status
            confidence: Confidence assessment result
            
        Returns:
            (action, new_status) tuple
        """
        current_status = StrategyStatus(strategy.get("status", "CANDIDATE"))
        score = confidence.score
        verdict = confidence.verdict
        
        # Get thresholds
        promote_threshold = self.config.get("promote_threshold", 0.70)
        demote_threshold = self.config.get("demote_threshold", 0.35)
        deprecate_threshold = self.config.get("deprecate_threshold", 0.25)
        
        # Determine action
        if verdict == "REJECT" or score < deprecate_threshold:
            action = "DEPRECATE"
        elif verdict in ["STRONG"] and score >= promote_threshold:
            action = "PROMOTE"
        elif verdict in ["WEAK", "REJECT"] or score < demote_threshold:
            action = "DEMOTE"
        else:
            action = "HOLD"
        
        # Special cases
        if verdict == "NEEDS_MORE_DATA":
            action = "HOLD"  # Don't change status, just wait for more data
        
        # Get new status from transition table
        new_status = self.transitions[current_status].get(action, current_status)
        
        return action, new_status
    
    def evaluate_strategy(
        self, 
        strategy: Dict[str, Any],
        validation_result: EdgeValidationResult
    ) -> Dict[str, Any]:
        """
        Full lifecycle evaluation of a strategy.
        
        Returns updated strategy with new status and lifecycle metadata.
        """
        action, new_status = self.determine_action(
            strategy, 
            validation_result.confidence
        )
        
        # Build lifecycle record
        lifecycle_record = {
            "previousStatus": strategy.get("status", "CANDIDATE"),
            "newStatus": new_status.value,
            "action": action,
            "confidenceScore": validation_result.confidence.score,
            "verdict": validation_result.confidence.verdict,
            "timestamp": int(time.time() * 1000),
            "reasons": validation_result.confidence.reasons
        }
        
        # Update strategy
        updated_strategy = strategy.copy()
        updated_strategy["status"] = new_status.value
        updated_strategy["lastValidation"] = validation_result.timestamp
        updated_strategy["lifecycleHistory"] = strategy.get("lifecycleHistory", [])
        
        # Only add to history if status changed
        if lifecycle_record["previousStatus"] != lifecycle_record["newStatus"]:
            updated_strategy["lifecycleHistory"].append(lifecycle_record)
        
        # Update confidence and robustness from validation
        updated_strategy["confidence"] = validation_result.confidence.score
        updated_strategy["robustness"] = validation_result.robustness.overall_score
        
        return updated_strategy
    
    def batch_evaluate(
        self, 
        strategies: List[Dict[str, Any]],
        validation_results: Dict[str, EdgeValidationResult]
    ) -> List[Dict[str, Any]]:
        """
        Evaluate multiple strategies at once.
        
        Args:
            strategies: List of strategy dicts
            validation_results: Dict mapping strategy_id -> EdgeValidationResult
            
        Returns:
            List of updated strategies
        """
        updated = []
        
        for strategy in strategies:
            strategy_id = strategy.get("id")
            
            if strategy_id in validation_results:
                result = validation_results[strategy_id]
                updated_strategy = self.evaluate_strategy(strategy, result)
                updated.append(updated_strategy)
            else:
                # No validation result, keep as-is
                updated.append(strategy)
        
        return updated
    
    def get_promotion_candidates(
        self, 
        strategies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Get strategies that are candidates for promotion.
        These should be prioritized for validation.
        """
        candidates = []
        
        for strategy in strategies:
            status = strategy.get("status", "CANDIDATE")
            confidence = strategy.get("confidence", 0.5)
            
            # TESTING strategies with high confidence
            if status == "TESTING" and confidence >= 0.65:
                candidates.append(strategy)
            # CANDIDATE strategies with promising metrics
            elif status == "CANDIDATE":
                metrics = strategy.get("metrics", {})
                if metrics.get("winRate", 0) > 0.58 and metrics.get("trades", 0) >= 30:
                    candidates.append(strategy)
        
        # Sort by potential (confidence + win rate)
        candidates.sort(
            key=lambda s: s.get("confidence", 0) + s.get("metrics", {}).get("winRate", 0),
            reverse=True
        )
        
        return candidates
    
    def get_demotion_candidates(
        self, 
        strategies: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Get strategies that might need demotion.
        These should be validated to confirm poor performance.
        """
        candidates = []
        
        for strategy in strategies:
            status = strategy.get("status", "CANDIDATE")
            confidence = strategy.get("confidence", 0.5)
            robustness = strategy.get("robustness", 0.5)
            
            # APPROVED but low confidence
            if status == "APPROVED" and (confidence < 0.5 or robustness < 0.4):
                candidates.append(strategy)
            # TESTING with poor metrics
            elif status == "TESTING" and confidence < 0.35:
                candidates.append(strategy)
        
        return candidates
    
    def generate_lifecycle_report(
        self, 
        strategies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a summary report of strategy lifecycle status.
        """
        status_counts = {
            "CANDIDATE": 0,
            "TESTING": 0,
            "APPROVED": 0,
            "QUARANTINE": 0,
            "DEPRECATED": 0
        }
        
        recent_promotions = []
        recent_demotions = []
        
        for strategy in strategies:
            status = strategy.get("status", "CANDIDATE")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Check recent lifecycle changes
            history = strategy.get("lifecycleHistory", [])
            if history:
                latest = history[-1]
                if latest.get("action") == "PROMOTE":
                    recent_promotions.append({
                        "id": strategy.get("id"),
                        "name": strategy.get("name"),
                        "from": latest.get("previousStatus"),
                        "to": latest.get("newStatus"),
                        "timestamp": latest.get("timestamp")
                    })
                elif latest.get("action") in ["DEMOTE", "DEPRECATE"]:
                    recent_demotions.append({
                        "id": strategy.get("id"),
                        "name": strategy.get("name"),
                        "from": latest.get("previousStatus"),
                        "to": latest.get("newStatus"),
                        "timestamp": latest.get("timestamp")
                    })
        
        # Sort by timestamp
        recent_promotions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        recent_demotions.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        return {
            "statusDistribution": status_counts,
            "totalStrategies": sum(status_counts.values()),
            "activeStrategies": status_counts["APPROVED"] + status_counts["TESTING"],
            "recentPromotions": recent_promotions[:5],
            "recentDemotions": recent_demotions[:5],
            "promotionCandidates": len(self.get_promotion_candidates(strategies)),
            "demotionCandidates": len(self.get_demotion_candidates(strategies)),
            "timestamp": int(time.time() * 1000)
        }
