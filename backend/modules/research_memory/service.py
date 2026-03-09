"""
Research Memory Service
=======================

Phase 9.32 - Service layer for research memory operations.
"""

import time
from typing import Dict, List, Optional, Any

from .types import MemoryEntry, MemoryPattern, MemorySummary, MemoryMatch, MemoryCategory
from .engine import research_memory


class ResearchMemoryService:
    """Service for research memory operations"""
    
    def __init__(self):
        self.engine = research_memory
    
    # ============================================
    # Record Failures
    # ============================================
    
    def record_feature_failure(
        self,
        feature_id: str,
        feature_name: str,
        family: str = "",
        outcome: str = "FAILED",
        failure_reasons: List[str] = None,
        metrics: Dict[str, float] = None
    ) -> Dict:
        """Record a failed feature"""
        entry = self.engine.record_feature_failure(
            feature_id=feature_id,
            feature_name=feature_name,
            family=family,
            outcome=outcome,
            failure_reasons=failure_reasons,
            metrics=metrics
        )
        return self.engine.entry_to_dict(entry)
    
    def record_alpha_failure(
        self,
        alpha_id: str,
        alpha_name: str,
        family: str = "",
        outcome: str = "FAILED",
        failure_reasons: List[str] = None,
        root_causes: List[str] = None,
        metrics: Dict[str, float] = None,
        regime: str = ""
    ) -> Dict:
        """Record a failed alpha"""
        entry = self.engine.record_alpha_failure(
            alpha_id=alpha_id,
            alpha_name=alpha_name,
            family=family,
            outcome=outcome,
            failure_reasons=failure_reasons,
            root_causes=root_causes,
            metrics=metrics,
            regime=regime
        )
        return self.engine.entry_to_dict(entry)
    
    def record_mutation_failure(
        self,
        mutation_id: str,
        mutation_name: str,
        parent_features: List[str] = None,
        outcome: str = "FAILED",
        failure_reasons: List[str] = None
    ) -> Dict:
        """Record a failed mutation"""
        entry = self.engine.record_mutation_failure(
            mutation_id=mutation_id,
            mutation_name=mutation_name,
            parent_features=parent_features,
            outcome=outcome,
            failure_reasons=failure_reasons
        )
        return self.engine.entry_to_dict(entry)
    
    def record_strategy_failure(
        self,
        strategy_id: str,
        strategy_name: str,
        family: str = "",
        outcome: str = "FAILED",
        failure_reasons: List[str] = None,
        root_causes: List[str] = None,
        metrics: Dict[str, float] = None,
        regime: str = "",
        asset_class: str = ""
    ) -> Dict:
        """Record a failed strategy"""
        entry = self.engine.record_strategy_failure(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            family=family,
            outcome=outcome,
            failure_reasons=failure_reasons,
            root_causes=root_causes,
            metrics=metrics,
            regime=regime,
            asset_class=asset_class
        )
        return self.engine.entry_to_dict(entry)
    
    def record_tournament_loss(
        self,
        alpha_id: str,
        alpha_name: str,
        family: str = "",
        metrics: Dict[str, float] = None,
        lost_to: str = "",
        reason: str = ""
    ) -> Dict:
        """Record a tournament loss"""
        entry = self.engine.record_tournament_loss(
            alpha_id=alpha_id,
            alpha_name=alpha_name,
            family=family,
            metrics=metrics,
            lost_to=lost_to,
            reason=reason
        )
        return self.engine.entry_to_dict(entry)
    
    def record_stress_failure(
        self,
        entity_id: str,
        entity_name: str,
        scenario: str = "",
        family: str = "",
        metrics: Dict[str, float] = None,
        failure_reasons: List[str] = None
    ) -> Dict:
        """Record a stress test failure"""
        entry = self.engine.record_stress_failure(
            entity_id=entity_id,
            entity_name=entity_name,
            scenario=scenario,
            family=family,
            metrics=metrics,
            failure_reasons=failure_reasons
        )
        return self.engine.entry_to_dict(entry)
    
    def record_from_autopsy(self, autopsy_report: Dict) -> Dict:
        """Record failure from autopsy report"""
        entry = self.engine.record_from_autopsy(autopsy_report)
        return self.engine.entry_to_dict(entry)
    
    # ============================================
    # Memory Lookup
    # ============================================
    
    def check_memory(
        self,
        entity_name: str,
        family: str = "",
        regime: str = "",
        tags: List[str] = None,
        category: str = None
    ) -> Dict:
        """Check if entity matches existing memory"""
        match = self.engine.check_memory(
            entity_name=entity_name,
            family=family,
            regime=regime,
            tags=tags,
            category=category
        )
        return {
            "matched": match.matched,
            "confidence": match.confidence,
            "matching_entries": match.matching_entries,
            "matching_patterns": match.matching_patterns,
            "recommendation": match.recommendation,
            "reasons": match.reasons
        }
    
    # ============================================
    # Query
    # ============================================
    
    def get_entries(
        self,
        category: str = None,
        outcome: str = None,
        family: str = None,
        regime: str = None,
        limit: int = 50
    ) -> Dict:
        """Get memory entries with filters"""
        
        from .types import MemoryQuery, MemoryCategory, MemoryOutcome
        
        query = MemoryQuery()
        
        if category:
            try:
                query.category = MemoryCategory(category)
            except ValueError:
                pass
        
        if outcome:
            try:
                query.outcome = MemoryOutcome(outcome)
            except ValueError:
                pass
        
        if family:
            query.family = family
        
        if regime:
            query.regime = regime
        
        entries = self.engine.query(query)
        
        return {
            "total": len(self.engine.entries),
            "count": min(len(entries), limit),
            "entries": [self.engine.entry_to_dict(e) for e in entries[:limit]]
        }
    
    def get_entry(self, entry_id: str) -> Optional[Dict]:
        """Get single entry"""
        entry = self.engine.entries.get(entry_id)
        return self.engine.entry_to_dict(entry) if entry else None
    
    def get_patterns(self, min_occurrences: int = 1) -> Dict:
        """Get failure patterns"""
        patterns = [
            p for p in self.engine.patterns.values()
            if p.occurrence_count >= min_occurrences
        ]
        patterns.sort(key=lambda p: p.occurrence_count, reverse=True)
        
        return {
            "total": len(patterns),
            "patterns": [self.engine.pattern_to_dict(p) for p in patterns]
        }
    
    def get_summary(self) -> Dict:
        """Get memory summary"""
        summary = self.engine.get_summary()
        return {
            "total_entries": summary.total_entries,
            "total_patterns": summary.total_patterns,
            "by_category": summary.by_category,
            "by_outcome": summary.by_outcome,
            "by_family": summary.by_family,
            "most_common_causes": summary.most_common_causes,
            "most_fragile_families": summary.most_fragile_families,
            "danger_regimes": summary.danger_regimes,
            "compute_saved_estimate": summary.compute_saved_estimate,
            "computed_at": summary.computed_at
        }
    
    def get_health(self) -> Dict:
        """Get service health"""
        return self.engine.get_health()


# Singleton
research_memory_service = ResearchMemoryService()
