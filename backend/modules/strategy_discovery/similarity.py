"""
Phase 9.5: Similarity Engine
Calculates similarity penalty for strategies that are too similar to existing ones
"""
from typing import Dict, List, Optional, Set, Any
from .types import SimilarityPenalty, VALIDATION_THRESHOLDS, FEATURE_WEIGHTS


class SimilarityEngine:
    """
    Calculates similarity between strategies to avoid redundancy.
    
    Key checks:
    1. Feature overlap (same features = same strategy)
    2. Return correlation (similar P&L = redundant)
    3. Uniqueness requirement (must add new value)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or VALIDATION_THRESHOLDS
        self.feature_weights = FEATURE_WEIGHTS
        
    def calculate(
        self, 
        candidate: Dict[str, Any], 
        existing_strategies: List[Dict[str, Any]]
    ) -> SimilarityPenalty:
        """
        Calculate similarity penalty for a candidate strategy.
        
        Args:
            candidate: New strategy to validate
            existing_strategies: List of existing approved/testing strategies
            
        Returns:
            SimilarityPenalty with detailed breakdown
        """
        if not existing_strategies:
            return SimilarityPenalty(
                penalty=0.0,
                similar_strategies=[],
                overlap_features=[],
                correlation=0.0,
                is_redundant=False,
                notes=["No existing strategies to compare"]
            )
        
        notes = []
        similar_ids = []
        all_overlaps = []
        max_similarity = 0.0
        correlations = []
        
        candidate_features = set(candidate.get("rules", {}).get("required", []))
        
        for existing in existing_strategies:
            # Skip self-comparison
            if existing.get("id") == candidate.get("id"):
                continue
                
            existing_features = set(existing.get("rules", {}).get("required", []))
            
            # Calculate feature similarity
            feature_sim = self._feature_similarity(candidate_features, existing_features)
            
            # Calculate return correlation (approximation based on metrics)
            return_corr = self._estimate_return_correlation(candidate, existing)
            
            # Combined similarity
            combined_sim = 0.6 * feature_sim + 0.4 * return_corr
            
            if combined_sim > max_similarity:
                max_similarity = combined_sim
            
            # Track similar strategies
            if combined_sim > self.config.get("max_similarity", 0.75):
                similar_ids.append(existing.get("id", "unknown"))
                overlap = candidate_features & existing_features
                all_overlaps.extend(list(overlap))
                correlations.append(return_corr)
        
        # Calculate final penalty (0 = unique, 1 = completely redundant)
        penalty = max_similarity
        
        # Check redundancy
        redundancy_threshold = self.config.get("redundancy_threshold", 0.85)
        is_redundant = penalty >= redundancy_threshold
        
        # Check unique features requirement
        unique_features = self._count_unique_features(candidate_features, existing_strategies)
        min_unique = self.config.get("min_unique_features", 1)
        
        if unique_features < min_unique:
            notes.append(f"Insufficient unique features: {unique_features} < {min_unique}")
            penalty = min(1.0, penalty + 0.1)
        
        if is_redundant:
            notes.append(f"Strategy is redundant (similarity: {penalty:.2f})")
        elif penalty > 0.5:
            notes.append(f"High similarity detected ({penalty:.2f}) - monitor for redundancy")
        else:
            notes.append(f"Sufficiently unique (similarity: {penalty:.2f})")
        
        # Get most common overlapping features
        overlap_features = list(set(all_overlaps))[:5]
        
        # Average correlation with similar strategies
        avg_correlation = sum(correlations) / len(correlations) if correlations else 0.0
        
        return SimilarityPenalty(
            penalty=round(penalty, 4),
            similar_strategies=similar_ids[:5],  # Top 5 similar
            overlap_features=overlap_features,
            correlation=round(avg_correlation, 4),
            is_redundant=is_redundant,
            notes=notes
        )
    
    def _feature_similarity(
        self, 
        features_a: Set[str], 
        features_b: Set[str]
    ) -> float:
        """
        Calculate weighted Jaccard similarity between feature sets.
        Uses feature importance weights for more meaningful comparison.
        """
        if not features_a or not features_b:
            return 0.0
        
        # Calculate weighted intersection
        intersection = features_a & features_b
        union = features_a | features_b
        
        if not union:
            return 0.0
        
        # Weight by feature importance
        weighted_intersection = sum(
            self.feature_weights.get(f, 0.5) for f in intersection
        )
        weighted_union = sum(
            self.feature_weights.get(f, 0.5) for f in union
        )
        
        if weighted_union == 0:
            return 0.0
            
        return weighted_intersection / weighted_union
    
    def _estimate_return_correlation(
        self, 
        strategy_a: Dict[str, Any], 
        strategy_b: Dict[str, Any]
    ) -> float:
        """
        Estimate return correlation based on metrics similarity.
        True correlation would require actual trade-by-trade data.
        """
        metrics_a = strategy_a.get("metrics", {})
        metrics_b = strategy_b.get("metrics", {})
        
        # Compare key metrics
        wr_diff = abs(metrics_a.get("winRate", 0.5) - metrics_b.get("winRate", 0.5))
        pf_diff = abs(metrics_a.get("profitFactor", 1.0) - metrics_b.get("profitFactor", 1.0))
        sharpe_diff = abs(metrics_a.get("sharpeRatio", 0) - metrics_b.get("sharpeRatio", 0))
        
        # Normalize differences
        wr_sim = max(0, 1.0 - wr_diff * 3)  # 0.33 diff = 0 similarity
        pf_sim = max(0, 1.0 - pf_diff / 2)  # 2.0 diff = 0 similarity
        sharpe_sim = max(0, 1.0 - sharpe_diff / 2)
        
        # Compare regime performance
        regime_a = strategy_a.get("regimeBreakdown", {})
        regime_b = strategy_b.get("regimeBreakdown", {})
        regime_sim = self._regime_similarity(regime_a, regime_b)
        
        # Weighted combination
        return 0.3 * wr_sim + 0.25 * pf_sim + 0.15 * sharpe_sim + 0.3 * regime_sim
    
    def _regime_similarity(
        self, 
        regime_a: Dict[str, Dict], 
        regime_b: Dict[str, Dict]
    ) -> float:
        """Compare regime performance profiles"""
        if not regime_a or not regime_b:
            return 0.5
        
        common_regimes = set(regime_a.keys()) & set(regime_b.keys())
        if not common_regimes:
            return 0.3
        
        similarities = []
        for regime in common_regimes:
            wr_a = regime_a[regime].get("winRate", 0.5)
            wr_b = regime_b[regime].get("winRate", 0.5)
            sim = max(0, 1.0 - abs(wr_a - wr_b) * 4)
            similarities.append(sim)
        
        return sum(similarities) / len(similarities)
    
    def _count_unique_features(
        self, 
        candidate_features: Set[str],
        existing_strategies: List[Dict[str, Any]]
    ) -> int:
        """Count features in candidate that don't appear in any existing strategy"""
        all_existing_features = set()
        
        for strategy in existing_strategies:
            features = strategy.get("rules", {}).get("required", [])
            all_existing_features.update(features)
        
        unique = candidate_features - all_existing_features
        return len(unique)
    
    def find_most_similar(
        self, 
        candidate: Dict[str, Any], 
        existing_strategies: List[Dict[str, Any]],
        top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find the most similar existing strategies.
        Useful for understanding why a strategy might be redundant.
        """
        if not existing_strategies:
            return []
        
        candidate_features = set(candidate.get("rules", {}).get("required", []))
        similarities = []
        
        for existing in existing_strategies:
            if existing.get("id") == candidate.get("id"):
                continue
                
            existing_features = set(existing.get("rules", {}).get("required", []))
            feature_sim = self._feature_similarity(candidate_features, existing_features)
            return_corr = self._estimate_return_correlation(candidate, existing)
            combined = 0.6 * feature_sim + 0.4 * return_corr
            
            similarities.append({
                "strategy": existing,
                "similarity": combined,
                "feature_overlap": list(candidate_features & existing_features)
            })
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        return similarities[:top_n]
