"""
Alpha Registry Store
====================

Phase 9.28 - Core storage and CRUD operations for alpha registry.
"""

import time
import uuid
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from .types import (
    AlphaDescriptor, AlphaLineageNode, AlphaVersion,
    AlphaValidationLink, AlphaSimilarityRecord, AlphaFamilyBudget,
    AlphaFamily, AlphaStatus, AlphaCreationSource, MutationType,
    ValidationVerdict, AlphaRegistryConfig, DEFAULT_FAMILY_BUDGETS
)


class AlphaRegistryStore:
    """
    Central store for all alpha data.
    
    This is the single source of truth for alphas in the system.
    """
    
    def __init__(self, config: Optional[AlphaRegistryConfig] = None):
        self.config = config or AlphaRegistryConfig()
        
        # Main storage
        self.alphas: Dict[str, AlphaDescriptor] = {}
        self.lineage: Dict[str, AlphaLineageNode] = {}
        self.versions: Dict[str, List[AlphaVersion]] = {}
        self.validations: Dict[str, List[AlphaValidationLink]] = {}
        self.similarities: Dict[str, AlphaSimilarityRecord] = {}
        
        # Family budgets
        self.family_budgets: Dict[AlphaFamily, AlphaFamilyBudget] = DEFAULT_FAMILY_BUDGETS.copy()
        
        # Indexes
        self._by_family: Dict[str, List[str]] = defaultdict(list)
        self._by_status: Dict[str, List[str]] = defaultdict(list)
        self._by_root_idea: Dict[str, List[str]] = defaultdict(list)
    
    # ============================================
    # Alpha CRUD
    # ============================================
    
    def register_alpha(
        self,
        name: str,
        family: str = "EXPERIMENTAL",
        created_by: str = "HUMAN",
        feature_ids: List[str] = None,
        asset_classes: List[str] = None,
        timeframes: List[str] = None,
        parent_alpha_id: str = None,
        description: str = "",
        tags: List[str] = None
    ) -> AlphaDescriptor:
        """Register a new alpha in the registry"""
        
        alpha_id = f"alpha_{uuid.uuid4().hex[:12]}"
        now = int(time.time() * 1000)
        
        # Determine root idea
        root_idea_id = alpha_id
        if parent_alpha_id and parent_alpha_id in self.lineage:
            root_idea_id = self.lineage[parent_alpha_id].root_idea_id
        
        # Parse enums
        try:
            alpha_family = AlphaFamily(family)
        except ValueError:
            alpha_family = AlphaFamily.EXPERIMENTAL
        
        try:
            source = AlphaCreationSource(created_by)
        except ValueError:
            source = AlphaCreationSource.HUMAN
        
        # Create descriptor
        alpha = AlphaDescriptor(
            alpha_id=alpha_id,
            name=name,
            family=alpha_family,
            created_at=now,
            created_by=source,
            version="v1",
            parent_alpha_id=parent_alpha_id,
            root_idea_id=root_idea_id,
            feature_ids=feature_ids or [],
            asset_classes=asset_classes or ["CRYPTO"],
            timeframes=timeframes or ["1D"],
            status=AlphaStatus.CANDIDATE,
            tags=tags or [],
            description=description,
            updated_at=now
        )
        
        # Create lineage node
        lineage_node = AlphaLineageNode(
            alpha_id=alpha_id,
            parent_alpha_id=parent_alpha_id,
            root_idea_id=root_idea_id,
            created_from_feature_ids=feature_ids or [],
            generation=0
        )
        
        if parent_alpha_id and parent_alpha_id in self.lineage:
            lineage_node.generation = self.lineage[parent_alpha_id].generation + 1
            # Update parent's children
            self.lineage[parent_alpha_id].child_alpha_ids.append(alpha_id)
        
        # Create initial version
        version = AlphaVersion(
            alpha_id=alpha_id,
            version="v1",
            feature_ids=feature_ids or [],
            status=AlphaStatus.CANDIDATE,
            created_at=now
        )
        
        # Store
        self.alphas[alpha_id] = alpha
        self.lineage[alpha_id] = lineage_node
        self.versions[alpha_id] = [version]
        self.validations[alpha_id] = []
        
        # Update indexes
        self._by_family[alpha_family.value].append(alpha_id)
        self._by_status[AlphaStatus.CANDIDATE.value].append(alpha_id)
        self._by_root_idea[root_idea_id].append(alpha_id)
        
        # Update family budget counts
        self._update_family_counts()
        
        return alpha
    
    def get_alpha(self, alpha_id: str) -> Optional[AlphaDescriptor]:
        """Get alpha by ID"""
        return self.alphas.get(alpha_id)
    
    def update_alpha(
        self,
        alpha_id: str,
        **kwargs
    ) -> Optional[AlphaDescriptor]:
        """Update alpha fields"""
        
        alpha = self.alphas.get(alpha_id)
        if not alpha:
            return None
        
        # Update allowed fields
        allowed_fields = [
            'name', 'description', 'notes', 'tags',
            'profit_factor', 'win_rate', 'sharpe', 'max_drawdown', 'expectancy',
            'stability_score', 'utility_score', 'portability_score',
            'regime_fit_score', 'crowding_score', 'final_score'
        ]
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(alpha, key, value)
        
        alpha.updated_at = int(time.time() * 1000)
        
        return alpha
    
    def delete_alpha(self, alpha_id: str) -> bool:
        """Delete alpha from registry"""
        
        if alpha_id not in self.alphas:
            return False
        
        alpha = self.alphas[alpha_id]
        
        # Remove from indexes
        if alpha_id in self._by_family.get(alpha.family.value, []):
            self._by_family[alpha.family.value].remove(alpha_id)
        if alpha_id in self._by_status.get(alpha.status.value, []):
            self._by_status[alpha.status.value].remove(alpha_id)
        
        # Remove from parent's children
        lineage = self.lineage.get(alpha_id)
        if lineage and lineage.parent_alpha_id:
            parent_lineage = self.lineage.get(lineage.parent_alpha_id)
            if parent_lineage and alpha_id in parent_lineage.child_alpha_ids:
                parent_lineage.child_alpha_ids.remove(alpha_id)
        
        # Delete all data
        del self.alphas[alpha_id]
        if alpha_id in self.lineage:
            del self.lineage[alpha_id]
        if alpha_id in self.versions:
            del self.versions[alpha_id]
        if alpha_id in self.validations:
            del self.validations[alpha_id]
        
        # Delete similarity records
        to_delete = [k for k in self.similarities.keys() if alpha_id in k]
        for k in to_delete:
            del self.similarities[k]
        
        self._update_family_counts()
        
        return True
    
    # ============================================
    # Status Management
    # ============================================
    
    def update_status(
        self,
        alpha_id: str,
        new_status: str,
        notes: str = ""
    ) -> Optional[AlphaDescriptor]:
        """Update alpha status"""
        
        alpha = self.alphas.get(alpha_id)
        if not alpha:
            return None
        
        try:
            status = AlphaStatus(new_status)
        except ValueError:
            return None
        
        old_status = alpha.status
        
        # Update index
        if alpha_id in self._by_status.get(old_status.value, []):
            self._by_status[old_status.value].remove(alpha_id)
        self._by_status[status.value].append(alpha_id)
        
        # Update alpha
        alpha.status = status
        alpha.updated_at = int(time.time() * 1000)
        
        if status in [AlphaStatus.SHADOW, AlphaStatus.LIMITED, AlphaStatus.CORE]:
            alpha.promoted_at = int(time.time() * 1000)
        
        # Create new version snapshot
        self._create_version_snapshot(alpha_id, notes)
        
        self._update_family_counts()
        
        return alpha
    
    def can_promote(self, alpha_id: str, target_status: str) -> Tuple[bool, str]:
        """Check if alpha can be promoted to target status"""
        
        alpha = self.alphas.get(alpha_id)
        if not alpha:
            return False, "Alpha not found"
        
        try:
            target = AlphaStatus(target_status)
        except ValueError:
            return False, "Invalid status"
        
        # Check score threshold
        thresholds = {
            AlphaStatus.VALIDATED: self.config.validated_threshold,
            AlphaStatus.SHADOW: self.config.shadow_threshold,
            AlphaStatus.CORE: self.config.core_threshold
        }
        
        if target in thresholds:
            if alpha.final_score < thresholds[target]:
                return False, f"Score {alpha.final_score} below threshold {thresholds[target]}"
        
        # Check family budget
        budget = self.family_budgets.get(alpha.family)
        if budget:
            if target == AlphaStatus.CORE and budget.current_core >= budget.max_core:
                return False, f"Family {alpha.family.value} at core limit ({budget.max_core})"
            if target == AlphaStatus.SHADOW and budget.current_shadow >= budget.max_shadow:
                return False, f"Family {alpha.family.value} at shadow limit ({budget.max_shadow})"
        
        # Check validation requirements
        if target == AlphaStatus.SHADOW:
            validations = self.validations.get(alpha_id, [])
            passed = [v for v in validations if v.verdict == ValidationVerdict.PASS]
            if len(passed) < self.config.min_validation_runs_for_shadow:
                return False, f"Need {self.config.min_validation_runs_for_shadow} passed validations"
        
        # Check cross-asset for CORE
        if target == AlphaStatus.CORE and self.config.require_cross_asset_for_core:
            if len(alpha.asset_classes) < 2:
                return False, "Core status requires cross-asset validation"
        
        return True, "OK"
    
    # ============================================
    # Lineage Operations
    # ============================================
    
    def get_lineage(self, alpha_id: str) -> Optional[AlphaLineageNode]:
        """Get lineage info for alpha"""
        return self.lineage.get(alpha_id)
    
    def get_lineage_tree(self, root_idea_id: str) -> List[Dict]:
        """Get full lineage tree from root idea"""
        
        alpha_ids = self._by_root_idea.get(root_idea_id, [])
        
        tree = []
        for alpha_id in alpha_ids:
            alpha = self.alphas.get(alpha_id)
            lineage = self.lineage.get(alpha_id)
            
            if alpha and lineage:
                tree.append({
                    "alpha_id": alpha_id,
                    "name": alpha.name,
                    "parent_alpha_id": lineage.parent_alpha_id,
                    "generation": lineage.generation,
                    "mutation_type": lineage.mutation_type.value if lineage.mutation_type else None,
                    "status": alpha.status.value,
                    "score": alpha.final_score,
                    "children_count": len(lineage.child_alpha_ids)
                })
        
        return tree
    
    def get_descendants(self, alpha_id: str) -> List[str]:
        """Get all descendant alpha IDs"""
        
        descendants = []
        lineage = self.lineage.get(alpha_id)
        
        if not lineage:
            return descendants
        
        for child_id in lineage.child_alpha_ids:
            descendants.append(child_id)
            descendants.extend(self.get_descendants(child_id))
        
        return descendants
    
    def get_ancestors(self, alpha_id: str) -> List[str]:
        """Get all ancestor alpha IDs"""
        
        ancestors = []
        lineage = self.lineage.get(alpha_id)
        
        while lineage and lineage.parent_alpha_id:
            ancestors.append(lineage.parent_alpha_id)
            lineage = self.lineage.get(lineage.parent_alpha_id)
        
        return ancestors
    
    # ============================================
    # Validation Links
    # ============================================
    
    def add_validation_link(
        self,
        alpha_id: str,
        validation_run_id: str,
        datasets: List[str],
        asset_results: Dict[str, Dict[str, float]],
        verdict: str
    ) -> Optional[AlphaValidationLink]:
        """Add validation link to alpha"""
        
        if alpha_id not in self.alphas:
            return None
        
        try:
            v = ValidationVerdict(verdict)
        except ValueError:
            v = ValidationVerdict.PENDING
        
        link = AlphaValidationLink(
            alpha_id=alpha_id,
            validation_run_id=validation_run_id,
            datasets=datasets,
            asset_results=asset_results,
            verdict=v,
            validated_at=int(time.time() * 1000)
        )
        
        if alpha_id not in self.validations:
            self.validations[alpha_id] = []
        self.validations[alpha_id].append(link)
        
        # Update alpha validated timestamp
        alpha = self.alphas[alpha_id]
        alpha.validated_at = int(time.time() * 1000)
        
        return link
    
    def get_validation_history(self, alpha_id: str) -> List[AlphaValidationLink]:
        """Get all validation links for alpha"""
        return self.validations.get(alpha_id, [])
    
    # ============================================
    # Version Management
    # ============================================
    
    def get_versions(self, alpha_id: str) -> List[AlphaVersion]:
        """Get all versions for alpha"""
        return self.versions.get(alpha_id, [])
    
    def _create_version_snapshot(self, alpha_id: str, notes: str = ""):
        """Create a new version snapshot"""
        
        alpha = self.alphas.get(alpha_id)
        if not alpha:
            return
        
        versions = self.versions.get(alpha_id, [])
        new_version = f"v{len(versions) + 1}"
        
        version = AlphaVersion(
            alpha_id=alpha_id,
            version=new_version,
            feature_ids=alpha.feature_ids.copy(),
            profit_factor=alpha.profit_factor,
            win_rate=alpha.win_rate,
            sharpe=alpha.sharpe,
            status=alpha.status,
            notes=notes,
            created_at=int(time.time() * 1000)
        )
        
        versions.append(version)
        alpha.version = new_version
    
    # ============================================
    # Query Methods
    # ============================================
    
    def list_alphas(
        self,
        family: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AlphaDescriptor]:
        """List alphas with filters"""
        
        results = list(self.alphas.values())
        
        if family:
            try:
                f = AlphaFamily(family)
                results = [a for a in results if a.family == f]
            except ValueError:
                pass
        
        if status:
            try:
                s = AlphaStatus(status)
                results = [a for a in results if a.status == s]
            except ValueError:
                pass
        
        # Sort by final_score descending
        results.sort(key=lambda a: a.final_score, reverse=True)
        
        return results[offset:offset + limit]
    
    def search_by_features(self, feature_ids: List[str]) -> List[AlphaDescriptor]:
        """Find alphas using specific features"""
        
        results = []
        feature_set = set(feature_ids)
        
        for alpha in self.alphas.values():
            if feature_set.intersection(set(alpha.feature_ids)):
                results.append(alpha)
        
        return results
    
    def get_by_root_idea(self, root_idea_id: str) -> List[AlphaDescriptor]:
        """Get all alphas from a root idea"""
        
        alpha_ids = self._by_root_idea.get(root_idea_id, [])
        return [self.alphas[aid] for aid in alpha_ids if aid in self.alphas]
    
    # ============================================
    # Statistics
    # ============================================
    
    def get_stats(self) -> Dict:
        """Get registry statistics"""
        
        stats = {
            "total_alphas": len(self.alphas),
            "by_status": {},
            "by_family": {},
            "avg_score": 0.0
        }
        
        # Count by status
        for status in AlphaStatus:
            count = len(self._by_status.get(status.value, []))
            stats["by_status"][status.value] = count
        
        # Count by family
        for family in AlphaFamily:
            count = len(self._by_family.get(family.value, []))
            stats["by_family"][family.value] = count
        
        # Average score
        if self.alphas:
            scores = [a.final_score for a in self.alphas.values()]
            stats["avg_score"] = round(sum(scores) / len(scores), 4)
        
        return stats
    
    def _update_family_counts(self):
        """Update family budget counts"""
        
        for family, budget in self.family_budgets.items():
            budget.current_core = 0
            budget.current_shadow = 0
            budget.current_sandbox = 0
            budget.current_total = 0
            
            for alpha in self.alphas.values():
                if alpha.family == family:
                    budget.current_total += 1
                    if alpha.status == AlphaStatus.CORE:
                        budget.current_core += 1
                    elif alpha.status == AlphaStatus.SHADOW:
                        budget.current_shadow += 1
                    elif alpha.status == AlphaStatus.SANDBOX:
                        budget.current_sandbox += 1


# Singleton instance
alpha_registry_store = AlphaRegistryStore()
