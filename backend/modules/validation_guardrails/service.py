"""
Phase 8.0: Validation Guardrails Service
Main service orchestrating all guardrail checks
"""
from typing import Dict, List, Optional, Any
import time
from dataclasses import asdict

from .types import (
    GuardrailsReport,
    Violation,
    SeverityLevel,
    GUARDRAILS_CONFIG
)
from .lookahead import LookaheadDetector
from .snooping import DataSnoopingGuard
from .execution import ExecutionValidator


class ValidationGuardrailsService:
    """
    Main service for validation guardrails.
    
    Orchestrates:
    1. Lookahead bias detection
    2. Data snooping protection
    3. Execution assumption validation
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or GUARDRAILS_CONFIG
        
        # Initialize components
        self.lookahead_detector = LookaheadDetector(self.config.get("lookahead"))
        self.snooping_guard = DataSnoopingGuard(self.config.get("snooping"))
        self.execution_validator = ExecutionValidator(self.config.get("execution"))
    
    def validate(
        self,
        backtest_config: Dict[str, Any],
        signals: Optional[List[Dict[str, Any]]] = None,
        test_runs: Optional[List[Dict[str, Any]]] = None,
        trades: Optional[List[Dict[str, Any]]] = None,
        price_data: Optional[List[Dict[str, Any]]] = None,
        strategy_rules: Optional[Dict[str, Any]] = None,
        strategy_versions: Optional[List[Dict[str, Any]]] = None,
        parameter_history: Optional[List[Dict[str, Any]]] = None,
        market_data: Optional[Dict[str, Any]] = None
    ) -> GuardrailsReport:
        """
        Run all guardrail validations.
        
        Args:
            backtest_config: Configuration of the backtest
            signals: Trading signals to check for lookahead
            test_runs: History of test runs for snooping check
            trades: Executed trades for execution validation
            price_data: Historical price data
            strategy_rules: Strategy rules definition
            strategy_versions: Strategy version history
            parameter_history: Parameter optimization history
            market_data: Market liquidity data
            
        Returns:
            GuardrailsReport with all checks
        """
        # 1. Lookahead check
        lookahead_result = self.lookahead_detector.check(
            signals=signals or [],
            price_data=price_data,
            strategy_rules=strategy_rules
        )
        
        # 2. Data snooping check
        snooping_result = self.snooping_guard.check(
            test_runs=test_runs or [],
            strategy_versions=strategy_versions,
            parameter_history=parameter_history
        )
        
        # 3. Execution validation
        execution_result = self.execution_validator.check(
            backtest_config=backtest_config,
            trades=trades,
            market_data=market_data
        )
        
        # Aggregate violations
        all_violations = (
            lookahead_result.violations +
            snooping_result.violations +
            execution_result.violations
        )
        
        total_violations = len(all_violations)
        critical_violations = len([v for v in all_violations if v.severity == SeverityLevel.CRITICAL])
        high_violations = len([v for v in all_violations if v.severity == SeverityLevel.HIGH])
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(
            lookahead_result,
            snooping_result,
            execution_result
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            lookahead_result,
            snooping_result,
            execution_result
        )
        
        # Determine pass/fail
        passed = (
            critical_violations == 0 and
            high_violations <= 2 and
            overall_score >= self.config.get("thresholds", {}).get("pass_score", 0.7)
        )
        
        return GuardrailsReport(
            passed=passed,
            overall_score=overall_score,
            lookahead_check=lookahead_result,
            snooping_check=snooping_result,
            execution_check=execution_result,
            total_violations=total_violations,
            critical_violations=critical_violations,
            high_violations=high_violations,
            recommendations=recommendations,
            timestamp=int(time.time() * 1000)
        )
    
    def quick_validate(
        self,
        backtest_config: Dict[str, Any],
        strategy: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Quick validation without detailed analysis.
        Good for pre-flight checks before running full backtest.
        """
        issues = []
        warnings = []
        
        # Quick lookahead check
        if strategy:
            lookahead_risk = self.lookahead_detector.quick_check(strategy)
            if lookahead_risk["risk_level"] == "HIGH":
                issues.append(f"High lookahead risk: {lookahead_risk['recommendation']}")
            elif lookahead_risk["risk_level"] == "MEDIUM":
                warnings.append(f"Medium lookahead risk: {lookahead_risk['recommendation']}")
        
        # Quick execution check
        if backtest_config.get("slippage_bps", 0) == 0:
            issues.append("Zero slippage - add realistic slippage")
        if backtest_config.get("fee_bps", 0) == 0:
            issues.append("Zero fees - add trading fees")
        if backtest_config.get("fill_delay_ms", 0) < 50:
            warnings.append("Fill delay < 50ms may be optimistic")
        
        return {
            "ready_to_run": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "recommendation": "Fix issues before running backtest" if issues else "Ready for validation"
        }
    
    def _calculate_overall_score(
        self,
        lookahead_result,
        snooping_result,
        execution_result
    ) -> float:
        """Calculate weighted overall score"""
        weights = self.config.get("thresholds", {})
        
        # Component scores
        lookahead_score = 1.0 if lookahead_result.passed else 0.3
        if lookahead_result.future_data_detected:
            lookahead_score = 0.0
        
        snooping_score = 1.0 - snooping_result.multiple_testing_penalty
        if not snooping_result.passed:
            snooping_score *= 0.5
        
        execution_score = execution_result.realistic_score
        
        # Weighted combination
        weighted_score = (
            weights.get("lookahead_weight", 0.4) * lookahead_score +
            weights.get("snooping_weight", 0.35) * snooping_score +
            weights.get("execution_weight", 0.25) * execution_score
        )
        
        return round(max(0.0, min(1.0, weighted_score)), 4)
    
    def _generate_recommendations(
        self,
        lookahead_result,
        snooping_result,
        execution_result
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Lookahead recommendations
        if lookahead_result.future_data_detected:
            recommendations.append("CRITICAL: Fix lookahead bias - future data detected in signals")
        elif not lookahead_result.passed:
            recommendations.append("Review signal data timestamps to eliminate lookahead risk")
        
        # Snooping recommendations
        if snooping_result.hypothesis_count > 10:
            factor = self.snooping_guard.get_correction_factor(snooping_result.hypothesis_count)
            recommendations.append(
                f"Apply multiple testing correction: multiply confidence by {factor['factor']:.2f}"
            )
        if snooping_result.multiple_testing_penalty > 0.2:
            recommendations.append("Consider walk-forward validation to reduce snooping risk")
        
        # Execution recommendations
        if execution_result.realistic_score < 0.5:
            recommendations.append("Improve execution model realism - current assumptions inflate returns")
        if execution_result.slippage_model == "none":
            recommendations.append("Add slippage model (recommended: 10-20 bps for crypto)")
        if execution_result.fee_model == "none":
            recommendations.append("Add fee model (recommended: 5-15 bps per trade)")
        
        return recommendations
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health status"""
        return {
            "enabled": True,
            "version": "guardrails_v1_phase8.0",
            "status": "ok",
            "components": {
                "lookahead_detector": "ok",
                "snooping_guard": "ok",
                "execution_validator": "ok"
            },
            "thresholds": self.config.get("thresholds", {}),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


def guardrails_report_to_dict(report: GuardrailsReport) -> Dict[str, Any]:
    """Convert GuardrailsReport to JSON-serializable dict"""
    return {
        "passed": report.passed,
        "overallScore": report.overall_score,
        "lookaheadCheck": {
            "passed": report.lookahead_check.passed,
            "violations": [
                {
                    "type": v.type.value,
                    "severity": v.severity.value,
                    "message": v.message,
                    "location": v.location,
                    "dataField": v.data_field,
                    "suggestion": v.suggestion
                }
                for v in report.lookahead_check.violations
            ],
            "fieldsChecked": report.lookahead_check.fields_checked,
            "timestampsAnalyzed": report.lookahead_check.timestamps_analyzed,
            "futureDataDetected": report.lookahead_check.future_data_detected,
            "notes": report.lookahead_check.notes
        },
        "snoopingCheck": {
            "passed": report.snooping_check.passed,
            "violations": [
                {
                    "type": v.type.value,
                    "severity": v.severity.value,
                    "message": v.message,
                    "suggestion": v.suggestion
                }
                for v in report.snooping_check.violations
            ],
            "hypothesisCount": report.snooping_check.hypothesis_count,
            "adjustedSignificance": report.snooping_check.adjusted_significance,
            "effectiveTests": report.snooping_check.effective_tests,
            "multipleTestingPenalty": report.snooping_check.multiple_testing_penalty,
            "notes": report.snooping_check.notes
        },
        "executionCheck": {
            "passed": report.execution_check.passed,
            "violations": [
                {
                    "type": v.type.value,
                    "severity": v.severity.value,
                    "message": v.message,
                    "suggestion": v.suggestion
                }
                for v in report.execution_check.violations
            ],
            "slippageModel": report.execution_check.slippage_model,
            "liquidityModel": report.execution_check.liquidity_model,
            "fillModel": report.execution_check.fill_model,
            "feeModel": report.execution_check.fee_model,
            "realisticScore": report.execution_check.realistic_score,
            "notes": report.execution_check.notes
        },
        "totalViolations": report.total_violations,
        "criticalViolations": report.critical_violations,
        "highViolations": report.high_violations,
        "recommendations": report.recommendations,
        "timestamp": report.timestamp
    }
