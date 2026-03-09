"""
Research Memory Engine
======================

Phase 9.32 - Core memory system for tracking research failures.

Converts every failure into knowledge:
- Records failures with full context
- Extracts patterns from multiple failures
- Checks new candidates against memory
- Prevents retesting dead ideas
- Accumulates institutional knowledge
"""

import time
import uuid
import hashlib
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .types import (
    MemoryEntry, MemoryPattern, MemorySummary, MemoryMatch, MemoryQuery,
    MemoryCategory, MemoryOutcome, MemoryImportance
)


class ResearchMemoryEngine:
    """
    Research Memory System.
    
    Stores and retrieves knowledge about failed research attempts.
    Prevents the system from repeating mistakes.
    """
    
    def __init__(self):
        # Storage
        self.entries: Dict[str, MemoryEntry] = {}
        self.patterns: Dict[str, MemoryPattern] = {}
        
        # Indexes
        self._by_category: Dict[str, List[str]] = defaultdict(list)
        self._by_family: Dict[str, List[str]] = defaultdict(list)
        self._by_regime: Dict[str, List[str]] = defaultdict(list)
        self._by_signature: Dict[str, List[str]] = defaultdict(list)
        
        # Statistics
        self.total_lookups = 0
        self.total_matches = 0
        self.compute_saved = 0
    
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
        metrics: Dict[str, float] = None,
        tags: List[str] = None,
        source_report_id: str = ""
    ) -> MemoryEntry:
        """Record a failed feature"""
        return self._record_failure(
            category=MemoryCategory.FEATURE,
            entity_id=feature_id,
            entity_name=feature_name,
            family=family,
            outcome=outcome,
            failure_reasons=failure_reasons,
            metrics=metrics,
            tags=tags,
            source_report_id=source_report_id
        )
    
    def record_alpha_failure(
        self,
        alpha_id: str,
        alpha_name: str,
        family: str = "",
        outcome: str = "FAILED",
        failure_reasons: List[str] = None,
        root_causes: List[str] = None,
        metrics: Dict[str, float] = None,
        regime: str = "",
        source_report_id: str = ""
    ) -> MemoryEntry:
        """Record a failed alpha"""
        return self._record_failure(
            category=MemoryCategory.ALPHA,
            entity_id=alpha_id,
            entity_name=alpha_name,
            family=family,
            outcome=outcome,
            failure_reasons=failure_reasons,
            root_causes=root_causes,
            metrics=metrics,
            regime=regime,
            source_report_id=source_report_id
        )
    
    def record_mutation_failure(
        self,
        mutation_id: str,
        mutation_name: str,
        parent_features: List[str] = None,
        outcome: str = "FAILED",
        failure_reasons: List[str] = None,
        metrics: Dict[str, float] = None
    ) -> MemoryEntry:
        """Record a failed mutation"""
        return self._record_failure(
            category=MemoryCategory.MUTATION,
            entity_id=mutation_id,
            entity_name=mutation_name,
            outcome=outcome,
            failure_reasons=failure_reasons,
            metrics=metrics,
            tags=parent_features or []
        )
    
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
        asset_class: str = "",
        source_report_id: str = ""
    ) -> MemoryEntry:
        """Record a failed strategy"""
        return self._record_failure(
            category=MemoryCategory.STRATEGY,
            entity_id=strategy_id,
            entity_name=strategy_name,
            family=family,
            outcome=outcome,
            failure_reasons=failure_reasons,
            root_causes=root_causes,
            metrics=metrics,
            regime=regime,
            asset_class=asset_class,
            source_report_id=source_report_id
        )
    
    def record_tournament_loss(
        self,
        alpha_id: str,
        alpha_name: str,
        family: str = "",
        metrics: Dict[str, float] = None,
        lost_to: str = "",
        reason: str = ""
    ) -> MemoryEntry:
        """Record a tournament loss"""
        return self._record_failure(
            category=MemoryCategory.TOURNAMENT,
            entity_id=alpha_id,
            entity_name=alpha_name,
            family=family,
            outcome="FAILED",
            failure_reasons=[reason, f"Lost to: {lost_to}"] if reason else [f"Lost to: {lost_to}"],
            metrics=metrics
        )
    
    def record_stress_failure(
        self,
        entity_id: str,
        entity_name: str,
        scenario: str = "",
        family: str = "",
        metrics: Dict[str, float] = None,
        failure_reasons: List[str] = None,
        source_report_id: str = ""
    ) -> MemoryEntry:
        """Record a stress test failure"""
        return self._record_failure(
            category=MemoryCategory.STRESS,
            entity_id=entity_id,
            entity_name=entity_name,
            family=family,
            outcome="FAILED",
            failure_reasons=failure_reasons,
            metrics=metrics,
            regime=scenario,
            source_report_id=source_report_id
        )
    
    def record_from_autopsy(
        self,
        autopsy_report: Dict
    ) -> MemoryEntry:
        """Record failure from autopsy report"""
        entity_type = autopsy_report.get("entity_type", "STRATEGY")
        
        category_map = {
            "STRATEGY": MemoryCategory.STRATEGY,
            "PORTFOLIO": MemoryCategory.STRATEGY,
            "STRESS_RUN": MemoryCategory.STRESS,
            "SHADOW_RUN": MemoryCategory.STRATEGY
        }
        
        return self._record_failure(
            category=category_map.get(entity_type, MemoryCategory.AUTOPSY),
            entity_id=autopsy_report.get("entity_id", ""),
            entity_name=autopsy_report.get("entity_id", ""),
            family=autopsy_report.get("family", ""),
            outcome="FAILED",
            failure_reasons=autopsy_report.get("contributing_factors", []),
            root_causes=autopsy_report.get("root_causes", []),
            metrics={
                "drawdown_pct": autopsy_report.get("drawdown_pct", 0),
                "pnl": autopsy_report.get("pnl_at_failure", 0),
                "win_rate": autopsy_report.get("win_rate_at_failure", 0)
            },
            regime=autopsy_report.get("regime_context", ""),
            asset_class=autopsy_report.get("asset_class", ""),
            source_report_id=autopsy_report.get("report_id", "")
        )
    
    def _record_failure(
        self,
        category: MemoryCategory,
        entity_id: str,
        entity_name: str,
        family: str = "",
        outcome: str = "FAILED",
        failure_reasons: List[str] = None,
        root_causes: List[str] = None,
        metrics: Dict[str, float] = None,
        regime: str = "",
        asset_class: str = "",
        tags: List[str] = None,
        source_report_id: str = ""
    ) -> MemoryEntry:
        """Internal method to record a failure"""
        
        entry_id = f"MEM_{uuid.uuid4().hex[:12]}"
        now = int(time.time() * 1000)
        
        # Parse outcome
        try:
            mem_outcome = MemoryOutcome(outcome)
        except ValueError:
            mem_outcome = MemoryOutcome.FAILED
        
        # Determine importance
        importance = self._determine_importance(metrics, failure_reasons)
        
        # Generate signature hash
        signature = self._generate_signature(
            category, family, regime, failure_reasons or []
        )
        
        # Generate lesson learned
        lesson = self._extract_lesson(category, failure_reasons, root_causes)
        
        entry = MemoryEntry(
            entry_id=entry_id,
            category=category,
            entity_id=entity_id,
            entity_name=entity_name,
            outcome=mem_outcome,
            importance=importance,
            family=family,
            asset_class=asset_class,
            regime=regime,
            failure_reasons=failure_reasons or [],
            root_causes=root_causes or [],
            metrics_at_failure=metrics or {},
            signature_hash=signature,
            lesson_learned=lesson,
            recommendations=self._generate_recommendations(category, root_causes),
            tags=tags or [],
            source_report_id=source_report_id,
            failed_at=now,
            recorded_at=now
        )
        
        # Store
        self.entries[entry_id] = entry
        
        # Update indexes
        self._by_category[category.value].append(entry_id)
        if family:
            self._by_family[family].append(entry_id)
        if regime:
            self._by_regime[regime].append(entry_id)
        self._by_signature[signature].append(entry_id)
        
        # Update patterns
        self._update_patterns(entry)
        
        return entry
    
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
    ) -> MemoryMatch:
        """Check if an entity matches existing memory"""
        
        self.total_lookups += 1
        
        # Generate signature
        try:
            cat = MemoryCategory(category) if category else MemoryCategory.STRATEGY
        except ValueError:
            cat = MemoryCategory.STRATEGY
        
        signature = self._generate_signature(cat, family, regime, tags or [])
        
        # Look for exact signature match
        matching_ids = self._by_signature.get(signature, [])
        
        # Also check by family + regime
        family_matches = set(self._by_family.get(family, []))
        regime_matches = set(self._by_regime.get(regime, []))
        
        combined_matches = family_matches & regime_matches if family and regime else set()
        all_matches = set(matching_ids) | combined_matches
        
        # Check for similar entities
        matching_entries = []
        matching_patterns = []
        confidence = 0.0
        
        for entry_id in all_matches:
            entry = self.entries.get(entry_id)
            if entry:
                matching_entries.append(entry_id)
                entry.last_referenced = int(time.time() * 1000)
                entry.reference_count += 1
        
        # Check patterns
        for pattern_id, pattern in self.patterns.items():
            if family in pattern.affected_families or regime in pattern.affected_regimes:
                matching_patterns.append(pattern_id)
        
        # Determine recommendation
        if matching_entries:
            self.total_matches += 1
            self.compute_saved += 1
            
            if len(matching_entries) >= 3:
                recommendation = "SKIP"
                confidence = 0.9
            elif len(matching_entries) >= 1:
                recommendation = "CAUTION"
                confidence = 0.6
            else:
                recommendation = "PROCEED"
                confidence = 0.3
        else:
            recommendation = "PROCEED"
            confidence = 0.0
        
        reasons = []
        if matching_entries:
            reasons.append(f"Found {len(matching_entries)} similar failures in memory")
        if matching_patterns:
            reasons.append(f"Matches {len(matching_patterns)} known failure patterns")
        
        return MemoryMatch(
            matched=len(matching_entries) > 0,
            confidence=confidence,
            matching_entries=matching_entries,
            matching_patterns=matching_patterns,
            recommendation=recommendation,
            reasons=reasons
        )
    
    def query(self, query: MemoryQuery) -> List[MemoryEntry]:
        """Query memory with filters"""
        
        results = list(self.entries.values())
        
        if query.category:
            results = [e for e in results if e.category == query.category]
        
        if query.outcome:
            results = [e for e in results if e.outcome == query.outcome]
        
        if query.family:
            results = [e for e in results if e.family == query.family]
        
        if query.regime:
            results = [e for e in results if e.regime == query.regime]
        
        if query.asset_class:
            results = [e for e in results if e.asset_class == query.asset_class]
        
        if query.tags:
            results = [e for e in results if any(t in e.tags for t in query.tags)]
        
        if query.min_importance:
            importance_order = [MemoryImportance.LOW, MemoryImportance.MEDIUM, 
                              MemoryImportance.HIGH, MemoryImportance.CRITICAL]
            min_idx = importance_order.index(query.min_importance)
            results = [e for e in results if importance_order.index(e.importance) >= min_idx]
        
        if query.signature_hash:
            results = [e for e in results if e.signature_hash == query.signature_hash]
        
        return sorted(results, key=lambda e: e.recorded_at, reverse=True)
    
    # ============================================
    # Pattern Extraction
    # ============================================
    
    def _update_patterns(self, entry: MemoryEntry):
        """Extract/update patterns from entry"""
        
        now = int(time.time() * 1000)
        
        # Pattern by category + family
        pattern_key = f"{entry.category.value}_{entry.family}_{entry.regime}"
        pattern = self.patterns.get(pattern_key)
        
        if not pattern:
            pattern = MemoryPattern(
                pattern_id=pattern_key,
                category=entry.category,
                description=f"Failures in {entry.family or 'unknown'} family during {entry.regime or 'any'} regime",
                first_seen=now
            )
            self.patterns[pattern_key] = pattern
        
        pattern.occurrence_count += 1
        pattern.last_seen = now
        pattern.entry_ids.append(entry.entry_id)
        
        # Update common causes
        for cause in entry.root_causes:
            if cause not in pattern.common_causes:
                pattern.common_causes.append(cause)
        
        if entry.family and entry.family not in pattern.affected_families:
            pattern.affected_families.append(entry.family)
        
        if entry.regime and entry.regime not in pattern.affected_regimes:
            pattern.affected_regimes.append(entry.regime)
    
    # ============================================
    # Helpers
    # ============================================
    
    def _generate_signature(
        self,
        category: MemoryCategory,
        family: str,
        regime: str,
        reasons: List[str]
    ) -> str:
        """Generate signature hash for duplicate detection"""
        
        sig_parts = [category.value, family, regime]
        sig_parts.extend(sorted(reasons[:3]))  # Top 3 reasons
        
        sig_string = "|".join(sig_parts)
        return hashlib.md5(sig_string.encode()).hexdigest()[:16]
    
    def _determine_importance(
        self,
        metrics: Dict[str, float] = None,
        reasons: List[str] = None
    ) -> MemoryImportance:
        """Determine importance level of failure"""
        
        if not metrics:
            return MemoryImportance.MEDIUM
        
        dd = abs(metrics.get("drawdown_pct", 0))
        pnl = metrics.get("pnl", 0)
        
        if dd > 0.30 or pnl < -10000:
            return MemoryImportance.CRITICAL
        elif dd > 0.15 or pnl < -5000:
            return MemoryImportance.HIGH
        elif dd > 0.05 or pnl < -1000:
            return MemoryImportance.MEDIUM
        return MemoryImportance.LOW
    
    def _extract_lesson(
        self,
        category: MemoryCategory,
        reasons: List[str] = None,
        root_causes: List[str] = None
    ) -> str:
        """Extract lesson learned from failure"""
        
        if not reasons and not root_causes:
            return f"{category.value} failed - insufficient data"
        
        causes = root_causes or reasons or []
        primary = causes[0] if causes else "unknown"
        
        lesson_templates = {
            "REGIME_MISMATCH": "Strategy fails when regime changes - add regime filter",
            "LOW_EDGE": "Insufficient edge - need stronger signal or better timing",
            "OVERFITTED": "Overfitting detected - reduce parameters or increase validation",
            "CORRELATION_SPIKE": "Correlation spike vulnerability - diversify signals",
            "VOLATILITY_SPIKE": "Not resilient to volatility - add vol scaling",
            "CROWDING": "Too similar to existing features - needs differentiation",
            "LIQUIDITY_SHOCK": "Fails in low liquidity - add liquidity checks"
        }
        
        return lesson_templates.get(primary, f"Failed due to: {primary}")
    
    def _generate_recommendations(
        self,
        category: MemoryCategory,
        root_causes: List[str] = None
    ) -> List[str]:
        """Generate recommendations based on failure"""
        
        recommendations = []
        
        cause_recs = {
            "REGIME_MISMATCH": "Add regime filter before deployment",
            "LOW_EDGE": "Improve signal quality or entry timing",
            "OVERFITTED": "Use stricter out-of-sample validation",
            "CORRELATION_SPIKE": "Add correlation monitoring",
            "VOLATILITY_SPIKE": "Implement volatility scaling",
            "CROWDING": "Differentiate from similar strategies",
            "LIQUIDITY_SHOCK": "Add liquidity constraints"
        }
        
        for cause in (root_causes or []):
            if cause in cause_recs:
                recommendations.append(cause_recs[cause])
        
        if not recommendations:
            recommendations.append("Review failure context before retry")
        
        return recommendations
    
    # ============================================
    # Summary & Stats
    # ============================================
    
    def get_summary(self) -> MemorySummary:
        """Get summary of research memory"""
        
        by_category = defaultdict(int)
        by_outcome = defaultdict(int)
        by_family = defaultdict(int)
        cause_counts = defaultdict(int)
        
        for entry in self.entries.values():
            by_category[entry.category.value] += 1
            by_outcome[entry.outcome.value] += 1
            if entry.family:
                by_family[entry.family] += 1
            for cause in entry.root_causes:
                cause_counts[cause] += 1
        
        # Top causes
        top_causes = sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Most fragile families
        fragile = sorted(by_family.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Danger regimes
        regime_counts = defaultdict(int)
        for entry in self.entries.values():
            if entry.regime:
                regime_counts[entry.regime] += 1
        danger_regimes = sorted(regime_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return MemorySummary(
            total_entries=len(self.entries),
            total_patterns=len(self.patterns),
            by_category=dict(by_category),
            by_outcome=dict(by_outcome),
            by_family=dict(by_family),
            most_common_causes=[{"cause": c, "count": n} for c, n in top_causes],
            most_fragile_families=[f[0] for f in fragile],
            danger_regimes=[r[0] for r in danger_regimes],
            compute_saved_estimate=self.compute_saved,
            computed_at=int(time.time() * 1000)
        )
    
    def get_health(self) -> Dict:
        """Get engine health"""
        return {
            "enabled": True,
            "version": "phase9.32",
            "status": "ok",
            "total_entries": len(self.entries),
            "total_patterns": len(self.patterns),
            "total_lookups": self.total_lookups,
            "total_matches": self.total_matches,
            "compute_saved": self.compute_saved,
            "match_rate": round(self.total_matches / max(1, self.total_lookups), 4),
            "supported_categories": [c.value for c in MemoryCategory],
            "timestamp": int(time.time() * 1000)
        }
    
    # ============================================
    # Serialization
    # ============================================
    
    def entry_to_dict(self, entry: MemoryEntry) -> Dict:
        """Convert entry to dict"""
        return {
            "entry_id": entry.entry_id,
            "category": entry.category.value,
            "entity_id": entry.entity_id,
            "entity_name": entry.entity_name,
            "outcome": entry.outcome.value,
            "importance": entry.importance.value,
            "family": entry.family,
            "asset_class": entry.asset_class,
            "regime": entry.regime,
            "failure_reasons": entry.failure_reasons,
            "root_causes": entry.root_causes,
            "metrics_at_failure": entry.metrics_at_failure,
            "lesson_learned": entry.lesson_learned,
            "recommendations": entry.recommendations,
            "tags": entry.tags,
            "source_report_id": entry.source_report_id,
            "failed_at": entry.failed_at,
            "recorded_at": entry.recorded_at,
            "reference_count": entry.reference_count
        }
    
    def pattern_to_dict(self, pattern: MemoryPattern) -> Dict:
        """Convert pattern to dict"""
        return {
            "pattern_id": pattern.pattern_id,
            "category": pattern.category.value,
            "description": pattern.description,
            "common_causes": pattern.common_causes,
            "affected_families": pattern.affected_families,
            "affected_regimes": pattern.affected_regimes,
            "occurrence_count": pattern.occurrence_count,
            "prevention_rules": pattern.prevention_rules,
            "first_seen": pattern.first_seen,
            "last_seen": pattern.last_seen
        }


# Singleton
research_memory = ResearchMemoryEngine()
