"""
Feature Quality Control
=======================

Phase 9.31 - Quality assessment and filtering for features.
"""

import math
import time
from typing import List, Dict, Optional, Tuple

from .types import (
    FeatureDescriptor, FeatureQualityReport,
    FeatureFactoryConfig, FeatureStatus
)


class FeatureQualityEngine:
    """
    Assesses quality of features and filters garbage.
    
    Quality checks:
    - Coverage
    - Missing rate
    - Variance threshold
    - Stability
    - No constant behavior
    - No unstable spikes
    """
    
    def __init__(self, config: Optional[FeatureFactoryConfig] = None):
        self.config = config or FeatureFactoryConfig()
    
    def assess_quality(
        self,
        feature_id: str,
        values: List[float],
        normalized_values: List[float] = None
    ) -> FeatureQualityReport:
        """Run full quality assessment on a feature"""
        
        report = FeatureQualityReport(
            feature_id=feature_id,
            computed_at=int(time.time() * 1000)
        )
        
        # Check coverage
        coverage, missing_rate = self._check_coverage(values)
        report.coverage = coverage
        report.missing_rate = missing_rate
        
        # Check variance
        variance = self._compute_variance(values)
        report.variance = variance
        
        # Check for constant behavior
        is_constant = self._check_constant(values)
        report.is_constant = is_constant
        
        # Check for spikes
        has_spikes = self._check_spikes(values)
        report.has_spikes = has_spikes
        
        # Compute stability score
        stability_score = self._compute_stability(values)
        report.stability_score = stability_score
        
        # Check all quality gates
        passed, reasons = self._check_gates(report)
        report.passed = passed
        report.failure_reasons = reasons
        
        return report
    
    def _check_coverage(self, values: List[float]) -> Tuple[float, float]:
        """Check coverage and missing rate"""
        if not values:
            return 0.0, 1.0
        
        total = len(values)
        valid = sum(1 for v in values if v is not None and not math.isnan(v) and not math.isinf(v))
        
        coverage = valid / total
        missing_rate = 1 - coverage
        
        return round(coverage, 4), round(missing_rate, 4)
    
    def _compute_variance(self, values: List[float]) -> float:
        """Compute variance of values"""
        valid_values = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
        
        if len(valid_values) < 2:
            return 0.0
        
        mean = sum(valid_values) / len(valid_values)
        variance = sum((v - mean) ** 2 for v in valid_values) / len(valid_values)
        
        return round(variance, 8)
    
    def _check_constant(self, values: List[float]) -> bool:
        """Check if feature is essentially constant"""
        valid_values = [v for v in values if v is not None and not math.isnan(v)]
        
        if len(valid_values) < 2:
            return True
        
        unique_values = set(round(v, 6) for v in valid_values)
        
        # If less than 1% unique values, consider constant
        return len(unique_values) < max(2, len(valid_values) * 0.01)
    
    def _check_spikes(self, values: List[float], threshold: float = 5.0) -> bool:
        """Check for unstable spikes (outliers)"""
        valid_values = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
        
        if len(valid_values) < 20:
            return False
        
        mean = sum(valid_values) / len(valid_values)
        variance = sum((v - mean) ** 2 for v in valid_values) / len(valid_values)
        std = math.sqrt(variance) if variance > 0 else 0
        
        if std == 0:
            return False
        
        # Count values more than threshold std from mean
        spikes = sum(1 for v in valid_values if abs(v - mean) > threshold * std)
        spike_rate = spikes / len(valid_values)
        
        # More than 2% spikes is concerning
        return spike_rate > 0.02
    
    def _compute_stability(self, values: List[float], window: int = 50) -> float:
        """
        Compute stability score based on rolling statistics.
        
        Higher score = more stable over time.
        """
        valid_values = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
        
        if len(valid_values) < window * 2:
            return 0.5  # Not enough data
        
        # Compute rolling means
        rolling_means = []
        for i in range(window - 1, len(valid_values)):
            window_values = valid_values[i - window + 1:i + 1]
            rolling_means.append(sum(window_values) / window)
        
        if len(rolling_means) < 2:
            return 0.5
        
        # Compute coefficient of variation of rolling means
        mean_of_means = sum(rolling_means) / len(rolling_means)
        if mean_of_means == 0:
            return 0.5
        
        variance_of_means = sum((m - mean_of_means) ** 2 for m in rolling_means) / len(rolling_means)
        cv = math.sqrt(variance_of_means) / abs(mean_of_means) if mean_of_means != 0 else 0
        
        # Convert to 0-1 score (lower CV = higher stability)
        # CV of 0 = score 1.0, CV of 2 = score 0.0
        stability = max(0, 1 - cv / 2)
        
        return round(stability, 4)
    
    def _check_gates(self, report: FeatureQualityReport) -> Tuple[bool, List[str]]:
        """Check all quality gates"""
        
        reasons = []
        passed = True
        
        # Coverage gate
        if report.coverage < self.config.min_coverage:
            passed = False
            reasons.append(f"Coverage {report.coverage} < {self.config.min_coverage}")
        
        # Missing rate gate
        if report.missing_rate > self.config.max_missing_rate:
            passed = False
            reasons.append(f"Missing rate {report.missing_rate} > {self.config.max_missing_rate}")
        
        # Variance gate
        if report.variance < self.config.min_variance:
            passed = False
            reasons.append(f"Variance {report.variance} < {self.config.min_variance}")
        
        # Constant gate
        if report.is_constant:
            passed = False
            reasons.append("Feature is constant")
        
        # Spike gate
        if report.has_spikes:
            passed = False
            reasons.append("Feature has unstable spikes")
        
        return passed, reasons
    
    def compute_utility_score(
        self,
        feature_values: List[float],
        target_returns: List[float],
        lookahead: int = 1
    ) -> float:
        """
        Compute predictive utility score.
        
        Simple correlation with future returns.
        """
        if len(feature_values) < lookahead + 10:
            return 0.0
        
        # Align feature with future returns
        n = min(len(feature_values), len(target_returns)) - lookahead
        
        if n < 10:
            return 0.0
        
        feature = feature_values[:n]
        future_returns = target_returns[lookahead:n + lookahead]
        
        # Filter valid pairs
        valid_pairs = [
            (f, r) for f, r in zip(feature, future_returns)
            if f is not None and r is not None and not math.isnan(f) and not math.isnan(r)
        ]
        
        if len(valid_pairs) < 10:
            return 0.0
        
        f_vals = [p[0] for p in valid_pairs]
        r_vals = [p[1] for p in valid_pairs]
        
        # Compute correlation
        n = len(valid_pairs)
        mean_f = sum(f_vals) / n
        mean_r = sum(r_vals) / n
        
        cov = sum((f_vals[i] - mean_f) * (r_vals[i] - mean_r) for i in range(n)) / n
        var_f = sum((f - mean_f) ** 2 for f in f_vals) / n
        var_r = sum((r - mean_r) ** 2 for r in r_vals) / n
        
        if var_f <= 0 or var_r <= 0:
            return 0.0
        
        correlation = cov / (math.sqrt(var_f) * math.sqrt(var_r))
        
        # Convert correlation to utility score (absolute value, 0-1)
        utility = min(1.0, abs(correlation) * 2)  # Scale up small correlations
        
        return round(utility, 4)


# Singleton instance
quality_engine = FeatureQualityEngine()
