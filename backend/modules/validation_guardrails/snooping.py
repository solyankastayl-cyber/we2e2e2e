"""
Phase 8.0: Data Snooping Guard
Protects against overfitting and multiple testing bias
"""
from typing import Dict, List, Optional, Any
import math
from .types import (
    SnoopingCheckResult,
    Violation,
    ViolationType,
    SeverityLevel,
    GUARDRAILS_CONFIG
)


class DataSnoopingGuard:
    """
    Guards against data snooping / p-hacking / overfitting.
    
    Data snooping occurs when:
    1. Testing many hypotheses without statistical correction
    2. Optimizing parameters on test data
    3. Cherry-picking time periods with good results
    4. Ignoring failed strategies (survivorship bias)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or GUARDRAILS_CONFIG.get("snooping", {})
        
    def check(
        self,
        test_runs: List[Dict[str, Any]],
        strategy_versions: Optional[List[Dict[str, Any]]] = None,
        parameter_history: Optional[List[Dict[str, Any]]] = None
    ) -> SnoopingCheckResult:
        """
        Check for data snooping violations.
        
        Args:
            test_runs: History of backtest runs
            strategy_versions: Different versions of strategy tested
            parameter_history: History of parameter changes
            
        Returns:
            SnoopingCheckResult with violations
        """
        violations = []
        notes = []
        
        # 1. Check multiple testing
        hypothesis_count = len(test_runs) if test_runs else 0
        multiple_testing_result = self._check_multiple_testing(test_runs)
        violations.extend(multiple_testing_result["violations"])
        
        # 2. Check parameter optimization
        if parameter_history:
            param_violations = self._check_parameter_optimization(parameter_history)
            violations.extend(param_violations)
        
        # 3. Check for cherry-picking
        if test_runs:
            cherry_violations = self._check_cherry_picking(test_runs)
            violations.extend(cherry_violations)
        
        # 4. Check survivorship bias
        if strategy_versions:
            survivorship_violations = self._check_survivorship_bias(strategy_versions)
            violations.extend(survivorship_violations)
        
        # 5. Calculate adjusted significance
        adjusted_significance = self._calculate_adjusted_significance(
            hypothesis_count,
            self.config.get("significance_level", 0.05)
        )
        
        # 6. Calculate multiple testing penalty
        penalty = self._calculate_penalty(hypothesis_count)
        
        # Generate notes
        if hypothesis_count > self.config.get("max_hypotheses_without_correction", 5):
            notes.append(f"Warning: {hypothesis_count} tests run - apply statistical correction")
            notes.append(f"Adjusted significance level: {adjusted_significance:.4f}")
        
        if not violations:
            notes.append("No data snooping violations detected")
        
        return SnoopingCheckResult(
            passed=len([v for v in violations if v.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]]) == 0,
            violations=violations,
            hypothesis_count=hypothesis_count,
            adjusted_significance=adjusted_significance,
            effective_tests=multiple_testing_result.get("effective_tests", hypothesis_count),
            multiple_testing_penalty=penalty,
            notes=notes
        )
    
    def _check_multiple_testing(
        self, 
        test_runs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check for multiple testing without correction"""
        violations = []
        
        if not test_runs:
            return {"violations": [], "effective_tests": 0}
        
        num_tests = len(test_runs)
        max_allowed = self.config.get("max_hypotheses_without_correction", 5)
        
        if num_tests > max_allowed:
            # Check if correction was applied
            correction_applied = any(
                run.get("statistical_correction") for run in test_runs
            )
            
            if not correction_applied:
                violations.append(Violation(
                    type=ViolationType.SNOOPING_MULTIPLE_TESTING,
                    severity=SeverityLevel.HIGH,
                    message=f"Multiple testing detected: {num_tests} tests without statistical correction",
                    details={
                        "tests_run": num_tests,
                        "threshold": max_allowed,
                        "correction_applied": False
                    },
                    suggestion=f"Apply Bonferroni or Benjamini-Hochberg correction for {num_tests} comparisons"
                ))
        
        # Count truly independent tests
        unique_strategies = len(set(r.get("strategy_id", "") for r in test_runs))
        unique_timeframes = len(set(r.get("timeframe", "") for r in test_runs))
        effective_tests = max(unique_strategies, unique_timeframes)
        
        return {
            "violations": violations,
            "effective_tests": effective_tests
        }
    
    def _check_parameter_optimization(
        self, 
        parameter_history: List[Dict[str, Any]]
    ) -> List[Violation]:
        """Check for excessive parameter optimization"""
        violations = []
        
        if not parameter_history:
            return violations
        
        max_combinations = self.config.get("max_parameter_combinations", 100)
        
        # Count parameter combinations tested
        combinations = len(parameter_history)
        
        if combinations > max_combinations:
            violations.append(Violation(
                type=ViolationType.SNOOPING_PARAMETER_OPTIMIZATION,
                severity=SeverityLevel.HIGH,
                message=f"Excessive parameter optimization: {combinations} combinations tested",
                details={
                    "combinations_tested": combinations,
                    "threshold": max_combinations
                },
                suggestion="Use walk-forward optimization or cross-validation instead of brute-force"
            ))
        
        # Check for in-sample optimization without OOS validation
        has_oos = any(p.get("out_of_sample_test") for p in parameter_history)
        if not has_oos and combinations > 10:
            violations.append(Violation(
                type=ViolationType.SNOOPING_PARAMETER_OPTIMIZATION,
                severity=SeverityLevel.MEDIUM,
                message="Parameters optimized without out-of-sample validation",
                details={"has_oos_validation": False},
                suggestion="Reserve 30% of data for out-of-sample testing"
            ))
        
        return violations
    
    def _check_cherry_picking(
        self, 
        test_runs: List[Dict[str, Any]]
    ) -> List[Violation]:
        """Check for cherry-picking favorable time periods"""
        violations = []
        
        if len(test_runs) < 3:
            return violations
        
        # Check for varying date ranges
        date_ranges = []
        for run in test_runs:
            start = run.get("start_date")
            end = run.get("end_date")
            if start and end:
                date_ranges.append((start, end))
        
        if len(date_ranges) > 1:
            # Check if ranges keep getting narrower (cherry-picking)
            range_sizes = [(e - s) if isinstance(s, int) else 0 for s, e in date_ranges]
            if len(range_sizes) > 2:
                if range_sizes[-1] < range_sizes[0] * 0.5:
                    violations.append(Violation(
                        type=ViolationType.SNOOPING_CHERRY_PICKING,
                        severity=SeverityLevel.MEDIUM,
                        message="Possible cherry-picking: test period narrowed significantly",
                        details={
                            "initial_range": range_sizes[0],
                            "final_range": range_sizes[-1],
                            "reduction_pct": round((1 - range_sizes[-1] / range_sizes[0]) * 100, 1)
                        },
                        suggestion="Use full available data or predefined periods only"
                    ))
        
        # Check if only profitable periods are being reported
        profitable_runs = [r for r in test_runs if r.get("pnl", 0) > 0]
        if len(profitable_runs) == len(test_runs) and len(test_runs) > 5:
            violations.append(Violation(
                type=ViolationType.SNOOPING_CHERRY_PICKING,
                severity=SeverityLevel.MEDIUM,
                message="All reported test runs are profitable - possible selection bias",
                details={"profitable_runs": len(profitable_runs), "total_runs": len(test_runs)},
                suggestion="Include and report all test runs, not just successful ones"
            ))
        
        return violations
    
    def _check_survivorship_bias(
        self, 
        strategy_versions: List[Dict[str, Any]]
    ) -> List[Violation]:
        """Check for survivorship bias in strategy selection"""
        violations = []
        
        total = len(strategy_versions)
        deprecated = len([s for s in strategy_versions if s.get("status") == "DEPRECATED"])
        active = total - deprecated
        
        # If many strategies were tried and deprecated, warn about survivorship
        if total > 10 and deprecated > total * 0.7:
            violations.append(Violation(
                type=ViolationType.SNOOPING_SURVIVORSHIP_BIAS,
                severity=SeverityLevel.MEDIUM,
                message=f"Potential survivorship bias: {deprecated}/{total} strategies deprecated",
                details={
                    "total_strategies": total,
                    "deprecated": deprecated,
                    "active": active,
                    "deprecation_rate": round(deprecated / total, 2)
                },
                suggestion="Account for all attempted strategies when evaluating expected performance"
            ))
        
        return violations
    
    def _calculate_adjusted_significance(
        self, 
        num_tests: int,
        base_significance: float
    ) -> float:
        """
        Calculate adjusted significance level for multiple testing.
        Uses Bonferroni correction by default.
        """
        if num_tests <= 1:
            return base_significance
        
        method = self.config.get("correction_method", "bonferroni")
        
        if method == "bonferroni":
            # Bonferroni: divide alpha by number of tests
            return base_significance / num_tests
        elif method == "holm":
            # Holm: slightly less conservative
            return base_significance / num_tests  # Simplified
        elif method == "benjamini-hochberg":
            # BH: control false discovery rate
            return base_significance * (1 / num_tests)  # Simplified
        else:
            return base_significance / num_tests
    
    def _calculate_penalty(self, num_tests: int) -> float:
        """
        Calculate confidence penalty for multiple testing.
        Higher penalty = less confident in results.
        """
        if num_tests <= 1:
            return 0.0
        
        # Log-scale penalty
        penalty = math.log10(num_tests) * 0.1
        return min(0.5, penalty)  # Cap at 50% penalty
    
    def get_correction_factor(self, num_tests: int) -> Dict[str, Any]:
        """
        Get correction factor for strategy confidence scores.
        Should be applied to reduce confidence when many strategies tested.
        """
        if num_tests <= 1:
            return {"factor": 1.0, "method": "none", "tests": num_tests}
        
        method = self.config.get("correction_method", "bonferroni")
        
        if method == "bonferroni":
            factor = 1.0 / math.sqrt(num_tests)
        else:
            factor = 1.0 / math.log10(num_tests + 1)
        
        factor = max(0.3, factor)  # Floor at 30%
        
        return {
            "factor": round(factor, 4),
            "method": method,
            "tests": num_tests,
            "recommendation": f"Multiply confidence scores by {factor:.2f}"
        }
