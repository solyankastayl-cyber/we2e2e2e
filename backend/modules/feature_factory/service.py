"""
Feature Factory Service
=======================

Phase 9.31 - Service layer for feature factory.
"""

import time
import uuid
from typing import Dict, List, Optional, Any
from collections import defaultdict

from .types import (
    FeatureDescriptor, FeatureFamily, FeatureType, FeatureStatus,
    NormalizationMethod, FeatureQualityReport, FeatureCrowdingRecord,
    FeatureFamilyBudget, FeatureFactoryConfig, DEFAULT_FEATURE_BUDGETS
)
from .base_features import BaseFeatureGenerator, BASE_FEATURE_DEFINITIONS
from .quality import quality_engine


class FeatureFactoryService:
    """
    Service for managing feature factory.
    
    Provides:
    - Feature registration
    - Feature generation
    - Quality control
    - Crowding detection
    - Scoring and promotion
    """
    
    def __init__(self):
        self.config = FeatureFactoryConfig()
        
        # Storage
        self.features: Dict[str, FeatureDescriptor] = {}
        self.quality_reports: Dict[str, FeatureQualityReport] = {}
        self.crowding_records: Dict[str, FeatureCrowdingRecord] = {}
        
        # Family budgets
        self.family_budgets: Dict[FeatureFamily, FeatureFamilyBudget] = DEFAULT_FEATURE_BUDGETS.copy()
        
        # Indexes
        self._by_family: Dict[str, List[str]] = defaultdict(list)
        self._by_status: Dict[str, List[str]] = defaultdict(list)
        
        # Initialize base features
        self._init_base_features()
    
    def _init_base_features(self):
        """Initialize base feature definitions"""
        for feature_def in BASE_FEATURE_DEFINITIONS:
            feature_def.created_at = int(time.time() * 1000)
            feature_def.updated_at = feature_def.created_at
            self.features[feature_def.feature_id] = feature_def
            self._by_family[feature_def.family.value].append(feature_def.feature_id)
            self._by_status[feature_def.status.value].append(feature_def.feature_id)
    
    # ============================================
    # Feature Registration
    # ============================================
    
    def register_feature(
        self,
        name: str,
        family: str = "EXPERIMENTAL",
        feature_type: str = "DERIVED",
        source_fields: List[str] = None,
        formula: str = "",
        description: str = "",
        parent_feature_ids: List[str] = None,
        tags: List[str] = None
    ) -> Dict:
        """Register a new feature"""
        
        feature_id = f"F_{uuid.uuid4().hex[:8].upper()}"
        now = int(time.time() * 1000)
        
        try:
            f_family = FeatureFamily(family)
        except ValueError:
            f_family = FeatureFamily.EXPERIMENTAL
        
        try:
            f_type = FeatureType(feature_type)
        except ValueError:
            f_type = FeatureType.DERIVED
        
        feature = FeatureDescriptor(
            feature_id=feature_id,
            name=name,
            family=f_family,
            feature_type=f_type,
            source_fields=source_fields or [],
            formula=formula,
            description=description,
            parent_feature_ids=parent_feature_ids or [],
            tags=tags or [],
            status=FeatureStatus.CANDIDATE,
            created_at=now,
            updated_at=now
        )
        
        self.features[feature_id] = feature
        self._by_family[f_family.value].append(feature_id)
        self._by_status[FeatureStatus.CANDIDATE.value].append(feature_id)
        
        self._update_family_counts()
        
        return self._feature_to_dict(feature)
    
    def get_feature(self, feature_id: str) -> Optional[Dict]:
        """Get feature by ID"""
        feature = self.features.get(feature_id)
        return self._feature_to_dict(feature) if feature else None
    
    def list_features(
        self,
        family: str = None,
        status: str = None,
        limit: int = 100
    ) -> Dict:
        """List features with filters"""
        
        features = list(self.features.values())
        
        if family:
            try:
                f = FeatureFamily(family)
                features = [feat for feat in features if feat.family == f]
            except ValueError:
                pass
        
        if status:
            try:
                s = FeatureStatus(status)
                features = [feat for feat in features if feat.status == s]
            except ValueError:
                pass
        
        # Sort by final_score descending
        features.sort(key=lambda f: f.final_score, reverse=True)
        
        return {
            "total": len(self.features),
            "count": min(len(features), limit),
            "features": [self._feature_to_dict(f) for f in features[:limit]]
        }
    
    # ============================================
    # Feature Generation
    # ============================================
    
    def generate_base_features(
        self,
        ohlcv: Dict[str, List[float]]
    ) -> Dict:
        """Generate all base features from OHLCV data"""
        
        results = {}
        
        opens = ohlcv.get("open", [])
        highs = ohlcv.get("high", [])
        lows = ohlcv.get("low", [])
        closes = ohlcv.get("close", [])
        volumes = ohlcv.get("volume", [])
        
        # Returns
        returns = BaseFeatureGenerator.returns(closes)
        results["F_RETURNS"] = returns
        
        log_returns = BaseFeatureGenerator.log_returns(closes)
        results["F_LOG_RETURNS"] = log_returns
        
        # Volatility
        vol = BaseFeatureGenerator.rolling_volatility(returns, 20)
        results["F_VOLATILITY_20"] = vol
        
        atr = BaseFeatureGenerator.atr(highs, lows, closes, 14)
        results["F_ATR_14"] = atr
        
        # Moving averages
        ma_dist = BaseFeatureGenerator.ma_distance(closes, 20)
        results["F_MA_DISTANCE_20"] = ma_dist
        
        ma_spread = BaseFeatureGenerator.ma_spread(closes, 10, 50)
        results["F_MA_SPREAD_10_50"] = ma_spread
        
        # Momentum
        momentum = BaseFeatureGenerator.momentum(closes, 10)
        results["F_MOMENTUM_10"] = momentum
        
        rsi = BaseFeatureGenerator.rsi(closes, 14)
        results["F_RSI_14"] = rsi
        
        # Trend
        trend_strength = BaseFeatureGenerator.trend_strength(closes, 20)
        results["F_TREND_STRENGTH_20"] = trend_strength
        
        trend_persist = BaseFeatureGenerator.trend_persistence(returns, 20)
        results["F_TREND_PERSISTENCE_20"] = trend_persist
        
        # Structure
        range_width = BaseFeatureGenerator.range_width(highs, lows, 20)
        results["F_RANGE_WIDTH_20"] = range_width
        
        candle_body = BaseFeatureGenerator.candle_body_ratio(opens, highs, lows, closes)
        results["F_CANDLE_BODY_RATIO"] = candle_body
        
        drawdown = BaseFeatureGenerator.drawdown_depth(closes)
        results["F_DRAWDOWN_DEPTH"] = drawdown
        
        # Volume
        if volumes:
            vol_ratio = BaseFeatureGenerator.volume_ratio(volumes, 20)
            results["F_VOLUME_RATIO_20"] = vol_ratio
        
        # Breakout
        breakout = BaseFeatureGenerator.breakout_distance(closes, highs, lows, 20)
        results["F_BREAKOUT_DISTANCE_20"] = breakout
        
        return {
            "features_generated": len(results),
            "feature_ids": list(results.keys()),
            "values": results
        }
    
    # ============================================
    # Quality Control
    # ============================================
    
    def run_quality_check(
        self,
        feature_id: str,
        values: List[float]
    ) -> Dict:
        """Run quality check on a feature"""
        
        report = quality_engine.assess_quality(feature_id, values)
        self.quality_reports[feature_id] = report
        
        # Update feature scores
        feature = self.features.get(feature_id)
        if feature:
            feature.coverage = report.coverage
            feature.missing_rate = report.missing_rate
            feature.stability_score = report.stability_score
            feature.updated_at = int(time.time() * 1000)
        
        return {
            "feature_id": feature_id,
            "coverage": report.coverage,
            "missing_rate": report.missing_rate,
            "variance": report.variance,
            "stability_score": report.stability_score,
            "is_constant": report.is_constant,
            "has_spikes": report.has_spikes,
            "passed": report.passed,
            "failure_reasons": report.failure_reasons
        }
    
    def run_batch_quality_check(
        self,
        feature_values: Dict[str, List[float]]
    ) -> Dict:
        """Run quality check on multiple features"""
        
        results = []
        passed_count = 0
        
        for feature_id, values in feature_values.items():
            result = self.run_quality_check(feature_id, values)
            results.append(result)
            if result["passed"]:
                passed_count += 1
        
        return {
            "total_checked": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "results": results
        }
    
    # ============================================
    # Scoring
    # ============================================
    
    def score_feature(
        self,
        feature_id: str,
        values: List[float] = None,
        target_returns: List[float] = None
    ) -> Dict:
        """Compute final score for a feature"""
        
        feature = self.features.get(feature_id)
        if not feature:
            return {"error": "Feature not found"}
        
        # Run quality check if values provided
        if values:
            report = quality_engine.assess_quality(feature_id, values)
            feature.coverage = report.coverage
            feature.missing_rate = report.missing_rate
            feature.stability_score = report.stability_score
        
        # Compute utility score if target returns provided
        if values and target_returns:
            utility = quality_engine.compute_utility_score(values, target_returns)
            feature.utility_score = utility
        
        # Compute final score
        final_score = (
            self.config.stability_weight * feature.stability_score +
            self.config.utility_weight * feature.utility_score +
            self.config.portability_weight * feature.portability_score +
            self.config.regime_fit_weight * feature.regime_fit_score -
            self.config.crowding_penalty_weight * feature.crowding_score
        )
        
        feature.final_score = round(max(0, min(1, final_score)), 4)
        feature.updated_at = int(time.time() * 1000)
        
        return {
            "feature_id": feature_id,
            "scores": {
                "stability": feature.stability_score,
                "utility": feature.utility_score,
                "portability": feature.portability_score,
                "regime_fit": feature.regime_fit_score,
                "crowding": feature.crowding_score
            },
            "final_score": feature.final_score
        }
    
    # ============================================
    # Status Management
    # ============================================
    
    def update_status(
        self,
        feature_id: str,
        new_status: str
    ) -> Dict:
        """Update feature status"""
        
        feature = self.features.get(feature_id)
        if not feature:
            return {"error": "Feature not found"}
        
        try:
            status = FeatureStatus(new_status)
        except ValueError:
            return {"error": f"Invalid status: {new_status}"}
        
        # Check thresholds
        if status == FeatureStatus.APPROVED:
            if feature.final_score < self.config.approved_threshold:
                return {"error": f"Score {feature.final_score} below threshold {self.config.approved_threshold}"}
        
        old_status = feature.status
        
        # Update indexes
        if feature_id in self._by_status.get(old_status.value, []):
            self._by_status[old_status.value].remove(feature_id)
        self._by_status[status.value].append(feature_id)
        
        feature.status = status
        feature.updated_at = int(time.time() * 1000)
        
        self._update_family_counts()
        
        return {
            "feature_id": feature_id,
            "old_status": old_status.value,
            "new_status": status.value
        }
    
    # ============================================
    # Crowding Detection
    # ============================================
    
    def compute_crowding(
        self,
        feature_a_id: str,
        feature_b_id: str,
        values_a: List[float],
        values_b: List[float]
    ) -> Dict:
        """Compute crowding between two features"""
        
        import math
        
        n = min(len(values_a), len(values_b))
        if n < 10:
            return {"error": "Not enough data"}
        
        # Filter valid pairs
        valid_pairs = [
            (values_a[i], values_b[i]) for i in range(n)
            if values_a[i] is not None and values_b[i] is not None
            and not math.isnan(values_a[i]) and not math.isnan(values_b[i])
        ]
        
        if len(valid_pairs) < 10:
            return {"error": "Not enough valid pairs"}
        
        a_vals = [p[0] for p in valid_pairs]
        b_vals = [p[1] for p in valid_pairs]
        
        # Compute correlation
        n = len(valid_pairs)
        mean_a = sum(a_vals) / n
        mean_b = sum(b_vals) / n
        
        cov = sum((a_vals[i] - mean_a) * (b_vals[i] - mean_b) for i in range(n)) / n
        var_a = sum((a - mean_a) ** 2 for a in a_vals) / n
        var_b = sum((b - mean_b) ** 2 for b in b_vals) / n
        
        if var_a <= 0 or var_b <= 0:
            correlation = 0.0
        else:
            correlation = cov / (math.sqrt(var_a) * math.sqrt(var_b))
        
        # Determine crowding level
        abs_corr = abs(correlation)
        is_redundant = abs_corr >= self.config.high_crowding_threshold
        is_crowded = abs_corr >= self.config.medium_crowding_threshold
        
        record = FeatureCrowdingRecord(
            feature_a=feature_a_id,
            feature_b=feature_b_id,
            correlation=round(correlation, 4),
            crowding_score=round(abs_corr, 4),
            is_redundant=is_redundant,
            is_crowded=is_crowded,
            computed_at=int(time.time() * 1000)
        )
        
        key = f"{feature_a_id}:{feature_b_id}"
        self.crowding_records[key] = record
        
        return {
            "feature_a": feature_a_id,
            "feature_b": feature_b_id,
            "correlation": record.correlation,
            "crowding_score": record.crowding_score,
            "is_redundant": record.is_redundant,
            "is_crowded": record.is_crowded
        }
    
    # ============================================
    # Family Budgets
    # ============================================
    
    def get_family_budgets(self) -> Dict:
        """Get all family budgets"""
        return {
            family.value: {
                "max_approved": budget.max_approved,
                "max_sandbox": budget.max_sandbox,
                "max_experimental": budget.max_experimental,
                "target_share": budget.target_share,
                "current_approved": budget.current_approved,
                "current_sandbox": budget.current_sandbox,
                "current_experimental": budget.current_experimental
            }
            for family, budget in self.family_budgets.items()
        }
    
    def _update_family_counts(self):
        """Update family budget counts"""
        for family, budget in self.family_budgets.items():
            budget.current_approved = 0
            budget.current_sandbox = 0
            budget.current_experimental = 0
            
            for feature in self.features.values():
                if feature.family == family:
                    if feature.status == FeatureStatus.APPROVED:
                        budget.current_approved += 1
                    elif feature.status == FeatureStatus.SANDBOX:
                        budget.current_sandbox += 1
                    elif feature.status == FeatureStatus.CANDIDATE:
                        budget.current_experimental += 1
    
    # ============================================
    # Health Check
    # ============================================
    
    def get_health(self) -> Dict:
        """Get service health"""
        return {
            "enabled": True,
            "version": "phase9.31",
            "status": "ok",
            "total_features": len(self.features),
            "base_features": len([f for f in self.features.values() if f.feature_type == FeatureType.BASE]),
            "derived_features": len([f for f in self.features.values() if f.feature_type == FeatureType.DERIVED]),
            "approved_features": len(self._by_status.get(FeatureStatus.APPROVED.value, [])),
            "supported_families": [f.value for f in FeatureFamily],
            "timestamp": int(time.time() * 1000)
        }
    
    def get_stats(self) -> Dict:
        """Get feature factory statistics"""
        return {
            "total_features": len(self.features),
            "by_family": {
                family.value: len(self._by_family.get(family.value, []))
                for family in FeatureFamily
            },
            "by_status": {
                status.value: len(self._by_status.get(status.value, []))
                for status in FeatureStatus
            },
            "by_type": {
                ftype.value: len([f for f in self.features.values() if f.feature_type == ftype])
                for ftype in FeatureType
            }
        }
    
    # ============================================
    # Helpers
    # ============================================
    
    def _feature_to_dict(self, feature: FeatureDescriptor) -> Dict:
        """Convert feature to dict"""
        return {
            "feature_id": feature.feature_id,
            "name": feature.name,
            "family": feature.family.value,
            "feature_type": feature.feature_type.value,
            "source_fields": feature.source_fields,
            "formula": feature.formula,
            "normalization": feature.normalization.value,
            "status": feature.status.value,
            "version": feature.version,
            "scores": {
                "coverage": feature.coverage,
                "stability": feature.stability_score,
                "utility": feature.utility_score,
                "portability": feature.portability_score,
                "regime_fit": feature.regime_fit_score,
                "crowding": feature.crowding_score,
                "final": feature.final_score
            },
            "parent_feature_ids": feature.parent_feature_ids,
            "tags": feature.tags,
            "description": feature.description,
            "created_at": feature.created_at
        }


# Singleton instance
feature_factory_service = FeatureFactoryService()
