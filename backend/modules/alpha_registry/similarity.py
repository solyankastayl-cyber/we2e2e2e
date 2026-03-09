"""
Alpha Similarity Engine
=======================

Phase 9.28 - Clone detection and similarity scoring between alphas.
"""

import math
from typing import Dict, List, Tuple, Optional

from .types import (
    AlphaDescriptor, AlphaSimilarityRecord,
    AlphaRegistryConfig
)
from .store import alpha_registry_store


class AlphaSimilarityEngine:
    """
    Computes similarity between alphas for clone/crowding detection.
    """
    
    def __init__(self, store=None, config: Optional[AlphaRegistryConfig] = None):
        self.store = store or alpha_registry_store
        self.config = config or AlphaRegistryConfig()
    
    def compute_feature_overlap(
        self,
        alpha_a: AlphaDescriptor,
        alpha_b: AlphaDescriptor
    ) -> float:
        """Compute feature overlap (Jaccard similarity)"""
        
        features_a = set(alpha_a.feature_ids)
        features_b = set(alpha_b.feature_ids)
        
        if not features_a and not features_b:
            return 0.0
        
        intersection = features_a.intersection(features_b)
        union = features_a.union(features_b)
        
        return len(intersection) / len(union) if union else 0.0
    
    def compute_signal_overlap(
        self,
        returns_a: List[float],
        returns_b: List[float]
    ) -> float:
        """Compute signal overlap (same sign days)"""
        
        n = min(len(returns_a), len(returns_b))
        if n == 0:
            return 0.0
        
        same_sign = sum(
            1 for i in range(n)
            if (returns_a[i] > 0) == (returns_b[i] > 0)
        )
        
        return same_sign / n
    
    def compute_pnl_correlation(
        self,
        returns_a: List[float],
        returns_b: List[float]
    ) -> float:
        """Compute PnL correlation (Pearson)"""
        
        n = min(len(returns_a), len(returns_b))
        if n < 5:
            return 0.0
        
        r_a = returns_a[:n]
        r_b = returns_b[:n]
        
        mean_a = sum(r_a) / n
        mean_b = sum(r_b) / n
        
        cov = sum((r_a[i] - mean_a) * (r_b[i] - mean_b) for i in range(n)) / n
        
        var_a = sum((r - mean_a) ** 2 for r in r_a) / n
        var_b = sum((r - mean_b) ** 2 for r in r_b) / n
        
        if var_a <= 0 or var_b <= 0:
            return 0.0
        
        return cov / (math.sqrt(var_a) * math.sqrt(var_b))
    
    def compute_regime_overlap(
        self,
        regime_fit_a: Dict[str, float],
        regime_fit_b: Dict[str, float]
    ) -> float:
        """Compute regime overlap (cosine similarity)"""
        
        all_regimes = set(regime_fit_a.keys()) | set(regime_fit_b.keys())
        
        if not all_regimes:
            return 0.0
        
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        
        for regime in all_regimes:
            val_a = regime_fit_a.get(regime, 0.0)
            val_b = regime_fit_b.get(regime, 0.0)
            
            dot += val_a * val_b
            norm_a += val_a ** 2
            norm_b += val_b ** 2
        
        if norm_a <= 0 or norm_b <= 0:
            return 0.0
        
        return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
    
    def compute_similarity(
        self,
        alpha_a_id: str,
        alpha_b_id: str,
        returns_a: List[float] = None,
        returns_b: List[float] = None,
        regime_fit_a: Dict[str, float] = None,
        regime_fit_b: Dict[str, float] = None
    ) -> Optional[AlphaSimilarityRecord]:
        """Compute full similarity between two alphas"""
        
        alpha_a = self.store.get_alpha(alpha_a_id)
        alpha_b = self.store.get_alpha(alpha_b_id)
        
        if not alpha_a or not alpha_b:
            return None
        
        # Feature overlap
        feature_overlap = self.compute_feature_overlap(alpha_a, alpha_b)
        
        # Signal overlap (if returns provided)
        signal_overlap = 0.5  # default neutral
        if returns_a and returns_b:
            signal_overlap = self.compute_signal_overlap(returns_a, returns_b)
        
        # PnL correlation (if returns provided)
        pnl_correlation = 0.0
        if returns_a and returns_b:
            pnl_correlation = self.compute_pnl_correlation(returns_a, returns_b)
        
        # Regime overlap (if provided)
        regime_overlap = 0.5  # default neutral
        if regime_fit_a and regime_fit_b:
            regime_overlap = self.compute_regime_overlap(regime_fit_a, regime_fit_b)
        
        # Final similarity score
        similarity_score = (
            0.30 * feature_overlap +
            0.25 * signal_overlap +
            0.30 * abs(pnl_correlation) +
            0.15 * regime_overlap
        )
        
        # Determine flags
        is_clone = similarity_score >= self.config.clone_threshold
        is_crowded = similarity_score >= self.config.crowded_threshold
        
        record = AlphaSimilarityRecord(
            alpha_a=alpha_a_id,
            alpha_b=alpha_b_id,
            feature_overlap=round(feature_overlap, 4),
            signal_overlap=round(signal_overlap, 4),
            pnl_correlation=round(pnl_correlation, 4),
            regime_overlap=round(regime_overlap, 4),
            similarity_score=round(similarity_score, 4),
            is_clone=is_clone,
            is_crowded=is_crowded,
            computed_at=int(__import__('time').time() * 1000)
        )
        
        # Store
        key = f"{alpha_a_id}:{alpha_b_id}"
        self.store.similarities[key] = record
        
        return record
    
    def check_for_clones(
        self,
        alpha_id: str,
        candidate_returns: List[float] = None
    ) -> List[AlphaSimilarityRecord]:
        """Check if alpha is a clone of any existing alpha"""
        
        clones = []
        
        for other_id in self.store.alphas.keys():
            if other_id == alpha_id:
                continue
            
            record = self.compute_similarity(
                alpha_id, other_id,
                returns_a=candidate_returns
            )
            
            if record and record.is_clone:
                clones.append(record)
        
        return clones
    
    def get_crowded_alphas(
        self,
        alpha_id: str
    ) -> List[AlphaSimilarityRecord]:
        """Get all alphas crowded with given alpha"""
        
        crowded = []
        
        for key, record in self.store.similarities.items():
            if alpha_id in key and record.is_crowded:
                crowded.append(record)
        
        return crowded
    
    def get_similarity(
        self,
        alpha_a_id: str,
        alpha_b_id: str
    ) -> Optional[AlphaSimilarityRecord]:
        """Get stored similarity record"""
        
        key1 = f"{alpha_a_id}:{alpha_b_id}"
        key2 = f"{alpha_b_id}:{alpha_a_id}"
        
        return self.store.similarities.get(key1) or self.store.similarities.get(key2)


# Singleton instance
similarity_engine = AlphaSimilarityEngine()
