"""
Alpha Registry Service
======================

Phase 9.28 - Service layer for alpha registry operations.
"""

import time
from typing import Dict, List, Optional, Any

from .types import (
    AlphaDescriptor, AlphaFamily, AlphaStatus, AlphaCreationSource,
    AlphaLineageNode, AlphaVersion, AlphaValidationLink,
    AlphaSimilarityRecord, AlphaFamilyBudget, AlphaRegistryConfig
)
from .store import alpha_registry_store
from .similarity import similarity_engine


class AlphaRegistryService:
    """
    Service for managing alpha registry.
    
    Provides:
    - Alpha registration and management
    - Lineage tracking
    - Similarity detection
    - Status lifecycle
    - Family budgeting
    """
    
    def __init__(self):
        self.store = alpha_registry_store
        self.similarity = similarity_engine
    
    # ============================================
    # Alpha Registration
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
        tags: List[str] = None,
        check_clones: bool = True
    ) -> Dict:
        """Register a new alpha"""
        
        alpha = self.store.register_alpha(
            name=name,
            family=family,
            created_by=created_by,
            feature_ids=feature_ids,
            asset_classes=asset_classes,
            timeframes=timeframes,
            parent_alpha_id=parent_alpha_id,
            description=description,
            tags=tags
        )
        
        result = {
            "alpha_id": alpha.alpha_id,
            "name": alpha.name,
            "family": alpha.family.value,
            "status": alpha.status.value,
            "version": alpha.version,
            "created_at": alpha.created_at,
            "clone_warnings": []
        }
        
        # Check for clones
        if check_clones:
            clones = self.similarity.check_for_clones(alpha.alpha_id)
            if clones:
                result["clone_warnings"] = [
                    {
                        "similar_to": c.alpha_b if c.alpha_a == alpha.alpha_id else c.alpha_a,
                        "similarity": c.similarity_score,
                        "is_clone": c.is_clone
                    }
                    for c in clones
                ]
        
        return result
    
    def get_alpha(self, alpha_id: str) -> Optional[Dict]:
        """Get alpha by ID"""
        
        alpha = self.store.get_alpha(alpha_id)
        if not alpha:
            return None
        
        return self._alpha_to_dict(alpha)
    
    def list_alphas(
        self,
        family: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """List alphas with filters"""
        
        alphas = self.store.list_alphas(
            family=family,
            status=status,
            limit=limit,
            offset=offset
        )
        
        return {
            "total": len(self.store.alphas),
            "count": len(alphas),
            "alphas": [self._alpha_to_dict(a) for a in alphas]
        }
    
    def update_alpha(self, alpha_id: str, **kwargs) -> Optional[Dict]:
        """Update alpha fields"""
        
        alpha = self.store.update_alpha(alpha_id, **kwargs)
        if not alpha:
            return None
        
        return self._alpha_to_dict(alpha)
    
    def delete_alpha(self, alpha_id: str) -> Dict:
        """Delete alpha"""
        
        success = self.store.delete_alpha(alpha_id)
        return {"success": success, "alpha_id": alpha_id}
    
    # ============================================
    # Status Management
    # ============================================
    
    def update_status(
        self,
        alpha_id: str,
        new_status: str,
        notes: str = ""
    ) -> Dict:
        """Update alpha status"""
        
        # Check if can promote
        can_promote, reason = self.store.can_promote(alpha_id, new_status)
        
        if not can_promote:
            return {"error": reason, "can_promote": False}
        
        alpha = self.store.update_status(alpha_id, new_status, notes)
        
        if not alpha:
            return {"error": "Alpha not found"}
        
        return {
            "alpha_id": alpha_id,
            "new_status": alpha.status.value,
            "version": alpha.version,
            "can_promote": True
        }
    
    def check_promotion(self, alpha_id: str, target_status: str) -> Dict:
        """Check if alpha can be promoted"""
        
        can_promote, reason = self.store.can_promote(alpha_id, target_status)
        
        return {
            "alpha_id": alpha_id,
            "target_status": target_status,
            "can_promote": can_promote,
            "reason": reason
        }
    
    # ============================================
    # Lineage
    # ============================================
    
    def get_lineage(self, alpha_id: str) -> Optional[Dict]:
        """Get lineage info for alpha"""
        
        lineage = self.store.get_lineage(alpha_id)
        if not lineage:
            return None
        
        return {
            "alpha_id": lineage.alpha_id,
            "parent_alpha_id": lineage.parent_alpha_id,
            "root_idea_id": lineage.root_idea_id,
            "mutation_type": lineage.mutation_type.value if lineage.mutation_type else None,
            "generation": lineage.generation,
            "child_count": len(lineage.child_alpha_ids),
            "child_alpha_ids": lineage.child_alpha_ids,
            "created_from_features": lineage.created_from_feature_ids
        }
    
    def get_lineage_tree(self, root_idea_id: str) -> Dict:
        """Get full lineage tree from root idea"""
        
        tree = self.store.get_lineage_tree(root_idea_id)
        
        return {
            "root_idea_id": root_idea_id,
            "total_descendants": len(tree),
            "tree": tree
        }
    
    def get_ancestors(self, alpha_id: str) -> Dict:
        """Get all ancestors"""
        
        ancestors = self.store.get_ancestors(alpha_id)
        
        return {
            "alpha_id": alpha_id,
            "ancestors": ancestors,
            "depth": len(ancestors)
        }
    
    def get_descendants(self, alpha_id: str) -> Dict:
        """Get all descendants"""
        
        descendants = self.store.get_descendants(alpha_id)
        
        return {
            "alpha_id": alpha_id,
            "descendants": descendants,
            "count": len(descendants)
        }
    
    # ============================================
    # Validation
    # ============================================
    
    def add_validation(
        self,
        alpha_id: str,
        validation_run_id: str,
        datasets: List[str],
        asset_results: Dict[str, Dict[str, float]],
        verdict: str
    ) -> Dict:
        """Add validation link"""
        
        link = self.store.add_validation_link(
            alpha_id=alpha_id,
            validation_run_id=validation_run_id,
            datasets=datasets,
            asset_results=asset_results,
            verdict=verdict
        )
        
        if not link:
            return {"error": "Alpha not found"}
        
        return {
            "alpha_id": alpha_id,
            "validation_run_id": validation_run_id,
            "verdict": link.verdict.value,
            "validated_at": link.validated_at
        }
    
    def get_validation_history(self, alpha_id: str) -> Dict:
        """Get validation history"""
        
        validations = self.store.get_validation_history(alpha_id)
        
        return {
            "alpha_id": alpha_id,
            "total_validations": len(validations),
            "validations": [
                {
                    "validation_run_id": v.validation_run_id,
                    "datasets": v.datasets,
                    "verdict": v.verdict.value,
                    "asset_results": v.asset_results,
                    "validated_at": v.validated_at
                }
                for v in validations
            ]
        }
    
    # ============================================
    # Versions
    # ============================================
    
    def get_versions(self, alpha_id: str) -> Dict:
        """Get all versions for alpha"""
        
        versions = self.store.get_versions(alpha_id)
        
        return {
            "alpha_id": alpha_id,
            "total_versions": len(versions),
            "versions": [
                {
                    "version": v.version,
                    "status": v.status.value,
                    "profit_factor": v.profit_factor,
                    "sharpe": v.sharpe,
                    "created_at": v.created_at,
                    "notes": v.notes
                }
                for v in versions
            ]
        }
    
    # ============================================
    # Similarity
    # ============================================
    
    def compute_similarity(
        self,
        alpha_a_id: str,
        alpha_b_id: str,
        returns_a: List[float] = None,
        returns_b: List[float] = None
    ) -> Dict:
        """Compute similarity between two alphas"""
        
        record = self.similarity.compute_similarity(
            alpha_a_id, alpha_b_id,
            returns_a=returns_a,
            returns_b=returns_b
        )
        
        if not record:
            return {"error": "One or both alphas not found"}
        
        return {
            "alpha_a": record.alpha_a,
            "alpha_b": record.alpha_b,
            "feature_overlap": record.feature_overlap,
            "signal_overlap": record.signal_overlap,
            "pnl_correlation": record.pnl_correlation,
            "regime_overlap": record.regime_overlap,
            "similarity_score": record.similarity_score,
            "is_clone": record.is_clone,
            "is_crowded": record.is_crowded
        }
    
    def check_clones(self, alpha_id: str) -> Dict:
        """Check for clones of an alpha"""
        
        clones = self.similarity.check_for_clones(alpha_id)
        
        return {
            "alpha_id": alpha_id,
            "clone_count": len(clones),
            "clones": [
                {
                    "similar_to": c.alpha_b if c.alpha_a == alpha_id else c.alpha_a,
                    "similarity": c.similarity_score,
                    "feature_overlap": c.feature_overlap
                }
                for c in clones
            ]
        }
    
    def get_crowded(self, alpha_id: str) -> Dict:
        """Get crowded alphas"""
        
        crowded = self.similarity.get_crowded_alphas(alpha_id)
        
        return {
            "alpha_id": alpha_id,
            "crowded_count": len(crowded),
            "crowded_with": [
                {
                    "alpha": c.alpha_b if c.alpha_a == alpha_id else c.alpha_a,
                    "similarity": c.similarity_score
                }
                for c in crowded
            ]
        }
    
    # ============================================
    # Family Budgets
    # ============================================
    
    def get_family_budgets(self) -> Dict:
        """Get all family budgets"""
        
        budgets = {}
        
        for family, budget in self.store.family_budgets.items():
            budgets[family.value] = {
                "max_core": budget.max_core,
                "max_shadow": budget.max_shadow,
                "max_sandbox": budget.max_sandbox,
                "max_total": budget.max_total,
                "target_share": budget.target_share,
                "current_core": budget.current_core,
                "current_shadow": budget.current_shadow,
                "current_sandbox": budget.current_sandbox,
                "current_total": budget.current_total
            }
        
        return budgets
    
    def update_family_budget(
        self,
        family: str,
        max_core: int = None,
        max_shadow: int = None,
        max_sandbox: int = None,
        target_share: float = None
    ) -> Dict:
        """Update family budget"""
        
        try:
            f = AlphaFamily(family)
        except ValueError:
            return {"error": f"Invalid family: {family}"}
        
        if f not in self.store.family_budgets:
            return {"error": f"Family not found: {family}"}
        
        budget = self.store.family_budgets[f]
        
        if max_core is not None:
            budget.max_core = max_core
        if max_shadow is not None:
            budget.max_shadow = max_shadow
        if max_sandbox is not None:
            budget.max_sandbox = max_sandbox
        if target_share is not None:
            budget.target_share = target_share
        
        return {"family": family, "updated": True}
    
    # ============================================
    # Statistics
    # ============================================
    
    def get_stats(self) -> Dict:
        """Get registry statistics"""
        return self.store.get_stats()
    
    # ============================================
    # Health Check
    # ============================================
    
    def get_health(self) -> Dict:
        """Get service health"""
        
        stats = self.store.get_stats()
        
        return {
            "enabled": True,
            "version": "phase9.28",
            "status": "ok",
            "total_alphas": stats["total_alphas"],
            "by_status": stats["by_status"],
            "supported_families": [f.value for f in AlphaFamily],
            "supported_statuses": [s.value for s in AlphaStatus],
            "timestamp": int(time.time() * 1000)
        }
    
    # ============================================
    # Helpers
    # ============================================
    
    def _alpha_to_dict(self, alpha: AlphaDescriptor) -> Dict:
        """Convert alpha to dict"""
        return {
            "alpha_id": alpha.alpha_id,
            "name": alpha.name,
            "family": alpha.family.value,
            "created_by": alpha.created_by.value,
            "version": alpha.version,
            "parent_alpha_id": alpha.parent_alpha_id,
            "root_idea_id": alpha.root_idea_id,
            "feature_ids": alpha.feature_ids,
            "asset_classes": alpha.asset_classes,
            "timeframes": alpha.timeframes,
            "status": alpha.status.value,
            "metrics": {
                "profit_factor": alpha.profit_factor,
                "win_rate": alpha.win_rate,
                "sharpe": alpha.sharpe,
                "max_drawdown": alpha.max_drawdown,
                "expectancy": alpha.expectancy
            },
            "scores": {
                "stability": alpha.stability_score,
                "utility": alpha.utility_score,
                "portability": alpha.portability_score,
                "regime_fit": alpha.regime_fit_score,
                "crowding": alpha.crowding_score,
                "final": alpha.final_score
            },
            "tags": alpha.tags,
            "description": alpha.description,
            "created_at": alpha.created_at,
            "updated_at": alpha.updated_at,
            "validated_at": alpha.validated_at,
            "promoted_at": alpha.promoted_at
        }


# Singleton instance
alpha_registry_service = AlphaRegistryService()
