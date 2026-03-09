"""
Phase 8: Validation Report Generator
Generates final aggregated validation report.
"""
import time
from typing import Dict, List, Optional, Any

from .types import (
    ValidationReport,
    SimulationResult,
    AccuracyMetrics,
    FailureAnalysis,
    MonteCarloResult,
    VALIDATION_CONFIG
)


class ReportGenerator:
    """
    Validation Report Generator.
    
    Aggregates all validation results into a final report
    answering the key question: Does the system have real edge?
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or VALIDATION_CONFIG
        self._reports: Dict[str, ValidationReport] = {}
    
    def generate(
        self,
        simulation_result: Optional[SimulationResult] = None,
        accuracy_metrics: Optional[AccuracyMetrics] = None,
        failure_analysis: Optional[FailureAnalysis] = None,
        monte_carlo_result: Optional[MonteCarloResult] = None,
        isolation_context: Optional[Dict] = None
    ) -> ValidationReport:
        """
        Generate comprehensive validation report.
        
        Args:
            simulation_result: Results from historical simulation
            accuracy_metrics: Accuracy measurements
            failure_analysis: Failure breakdown
            monte_carlo_result: Robustness testing results
            isolation_context: Validation isolation context
            
        Returns:
            ValidationReport with edge assessment
        """
        run_id = f"report_{int(time.time() * 1000)}"
        started_at = int(time.time() * 1000)
        
        # Extract core metrics
        win_rate = simulation_result.win_rate if simulation_result else 0
        profit_factor = simulation_result.profit_factor if simulation_result else 0
        max_drawdown = simulation_result.max_drawdown if simulation_result else 0
        sharpe = simulation_result.sharpe_ratio if simulation_result else 0
        total_trades = simulation_result.trades if simulation_result else 0
        
        # Extract accuracy metrics
        direction_accuracy = accuracy_metrics.direction_accuracy if accuracy_metrics else 0
        scenario_accuracy = accuracy_metrics.scenario_accuracy if accuracy_metrics else 0
        structure_accuracy = accuracy_metrics.structure_accuracy if accuracy_metrics else 0
        timing_accuracy = accuracy_metrics.timing_accuracy if accuracy_metrics else 0
        
        # Extract robustness metrics
        mc_survival = monte_carlo_result.survival_rate if monte_carlo_result else 0
        mc_worst = monte_carlo_result.worst_case_pnl if monte_carlo_result else 0
        robustness = monte_carlo_result.robustness_score if monte_carlo_result else 0
        
        # Extract failure metrics
        top_failures = [f.value for f in failure_analysis.top_failures[:3]] if failure_analysis else []
        failure_rate = failure_analysis.failure_rate if failure_analysis else 0
        
        # Assess edge
        edge_assessment = self._assess_edge(
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe=sharpe,
            total_trades=total_trades,
            direction_accuracy=direction_accuracy,
            mc_survival=mc_survival,
            robustness=robustness
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            edge_assessment,
            simulation_result,
            accuracy_metrics,
            failure_analysis
        )
        
        completed_at = int(time.time() * 1000)
        
        report = ValidationReport(
            run_id=run_id,
            win_rate=round(win_rate, 4),
            profit_factor=round(profit_factor, 2),
            max_drawdown=round(max_drawdown, 4),
            sharpe_ratio=round(sharpe, 2),
            total_trades=total_trades,
            direction_accuracy=round(direction_accuracy, 4),
            scenario_accuracy=round(scenario_accuracy, 4),
            structure_accuracy=round(structure_accuracy, 4),
            timing_accuracy=round(timing_accuracy, 4),
            monte_carlo_survival_rate=round(mc_survival, 4),
            monte_carlo_worst_case=round(mc_worst, 4),
            robustness_score=round(robustness, 4),
            top_failures=top_failures,
            failure_rate=round(failure_rate, 4),
            has_edge=edge_assessment["has_edge"],
            edge_confidence=round(edge_assessment["confidence"], 4),
            edge_verdict=edge_assessment["verdict"],
            recommendations=recommendations,
            simulation_result=simulation_result,
            accuracy_metrics=accuracy_metrics,
            failure_analysis=failure_analysis,
            monte_carlo_result=monte_carlo_result,
            validation_isolation=isolation_context or {},
            started_at=started_at,
            completed_at=completed_at,
            timestamp=completed_at
        )
        
        self._reports[run_id] = report
        
        return report
    
    def get_report(self, run_id: str) -> Optional[ValidationReport]:
        """Get a report by ID"""
        return self._reports.get(run_id)
    
    def list_reports(self, limit: int = 20) -> List[Dict]:
        """List available reports"""
        reports = list(self._reports.values())
        reports = sorted(reports, key=lambda r: r.timestamp, reverse=True)[:limit]
        
        return [
            {
                "runId": r.run_id,
                "winRate": r.win_rate,
                "profitFactor": r.profit_factor,
                "edgeVerdict": r.edge_verdict,
                "hasEdge": r.has_edge,
                "timestamp": r.timestamp
            }
            for r in reports
        ]
    
    def _assess_edge(
        self,
        win_rate: float,
        profit_factor: float,
        sharpe: float,
        total_trades: int,
        direction_accuracy: float,
        mc_survival: float,
        robustness: float
    ) -> Dict[str, Any]:
        """
        Assess if the system has real edge.
        
        Returns:
            Dict with has_edge, confidence, verdict
        """
        thresholds = self.config.get("edge_thresholds", {})
        
        # Check minimum sample size
        min_trades = thresholds.get("min_trades", 100)
        if total_trades < min_trades:
            return {
                "has_edge": False,
                "confidence": 0.2,
                "verdict": "INSUFFICIENT_DATA",
                "reason": f"Need at least {min_trades} trades, have {total_trades}"
            }
        
        # Score components
        scores = []
        
        # Win rate score
        if win_rate >= thresholds.get("strong_win_rate", 0.60):
            scores.append(("win_rate", 1.0, "strong"))
        elif win_rate >= thresholds.get("moderate_win_rate", 0.55):
            scores.append(("win_rate", 0.7, "moderate"))
        elif win_rate >= 0.50:
            scores.append(("win_rate", 0.4, "weak"))
        else:
            scores.append(("win_rate", 0.0, "negative"))
        
        # Profit factor score
        if profit_factor >= thresholds.get("strong_pf", 1.5):
            scores.append(("profit_factor", 1.0, "strong"))
        elif profit_factor >= thresholds.get("moderate_pf", 1.2):
            scores.append(("profit_factor", 0.7, "moderate"))
        elif profit_factor >= 1.0:
            scores.append(("profit_factor", 0.4, "weak"))
        else:
            scores.append(("profit_factor", 0.0, "negative"))
        
        # Sharpe ratio score
        if sharpe >= thresholds.get("strong_sharpe", 1.5):
            scores.append(("sharpe", 1.0, "strong"))
        elif sharpe >= thresholds.get("moderate_sharpe", 1.0):
            scores.append(("sharpe", 0.7, "moderate"))
        elif sharpe >= 0.5:
            scores.append(("sharpe", 0.4, "weak"))
        else:
            scores.append(("sharpe", 0.0, "negative"))
        
        # Direction accuracy score
        if direction_accuracy >= 0.60:
            scores.append(("direction", 1.0, "strong"))
        elif direction_accuracy >= 0.55:
            scores.append(("direction", 0.7, "moderate"))
        elif direction_accuracy >= 0.50:
            scores.append(("direction", 0.4, "weak"))
        else:
            scores.append(("direction", 0.0, "negative"))
        
        # Robustness score
        if robustness >= 0.7:
            scores.append(("robustness", 1.0, "strong"))
        elif robustness >= 0.5:
            scores.append(("robustness", 0.7, "moderate"))
        elif robustness >= 0.3:
            scores.append(("robustness", 0.4, "weak"))
        else:
            scores.append(("robustness", 0.0, "negative"))
        
        # Calculate overall confidence
        weights = {
            "win_rate": 0.25,
            "profit_factor": 0.25,
            "sharpe": 0.15,
            "direction": 0.15,
            "robustness": 0.20
        }
        
        weighted_score = sum(
            weights.get(name, 0.2) * score
            for name, score, _ in scores
        )
        
        # Determine verdict
        strong_count = len([s for s in scores if s[2] == "strong"])
        negative_count = len([s for s in scores if s[2] == "negative"])
        
        if weighted_score >= 0.75 and strong_count >= 3 and negative_count == 0:
            verdict = "STRONG_EDGE"
            has_edge = True
        elif weighted_score >= 0.55 and strong_count >= 2 and negative_count <= 1:
            verdict = "MODERATE_EDGE"
            has_edge = True
        elif weighted_score >= 0.40 and negative_count <= 2:
            verdict = "WEAK_EDGE"
            has_edge = False  # Weak edge = not reliable
        else:
            verdict = "NO_EDGE"
            has_edge = False
        
        return {
            "has_edge": has_edge,
            "confidence": weighted_score,
            "verdict": verdict,
            "breakdown": scores
        }
    
    def _generate_recommendations(
        self,
        edge_assessment: Dict,
        simulation: Optional[SimulationResult],
        accuracy: Optional[AccuracyMetrics],
        failures: Optional[FailureAnalysis]
    ) -> List[str]:
        """
        Generate actionable recommendations.
        """
        recommendations = []
        verdict = edge_assessment.get("verdict", "UNKNOWN")
        
        if verdict == "STRONG_EDGE":
            recommendations.append("System shows strong edge - consider paper trading before live")
            recommendations.append("Monitor for regime changes that could degrade performance")
        
        elif verdict == "MODERATE_EDGE":
            recommendations.append("System shows moderate edge - focus on improving weak areas")
            if accuracy and accuracy.timing_accuracy < 0.5:
                recommendations.append("Priority: Improve entry/exit timing")
            if simulation and simulation.max_drawdown > 0.20:
                recommendations.append("Priority: Reduce position sizing to manage drawdown")
        
        elif verdict == "WEAK_EDGE":
            recommendations.append("Edge is weak and unreliable - further development needed")
            recommendations.append("Consider: Stricter filtering, better regime detection")
        
        else:  # NO_EDGE
            recommendations.append("No significant edge detected - system needs fundamental review")
            recommendations.append("Consider: Different strategies, markets, or timeframes")
        
        # Add failure-specific recommendations
        if failures and failures.recommendations:
            recommendations.extend(failures.recommendations[:2])
        
        return recommendations


def report_to_dict(report: ValidationReport) -> Dict[str, Any]:
    """Convert ValidationReport to JSON-serializable dict"""
    return {
        "runId": report.run_id,
        "winRate": report.win_rate,
        "profitFactor": report.profit_factor,
        "maxDrawdown": report.max_drawdown,
        "sharpeRatio": report.sharpe_ratio,
        "totalTrades": report.total_trades,
        "directionAccuracy": report.direction_accuracy,
        "scenarioAccuracy": report.scenario_accuracy,
        "structureAccuracy": report.structure_accuracy,
        "timingAccuracy": report.timing_accuracy,
        "monteCarloSurvivalRate": report.monte_carlo_survival_rate,
        "monteCarloWorstCase": report.monte_carlo_worst_case,
        "robustnessScore": report.robustness_score,
        "topFailures": report.top_failures,
        "failureRate": report.failure_rate,
        "hasEdge": report.has_edge,
        "edgeConfidence": report.edge_confidence,
        "edgeVerdict": report.edge_verdict,
        "recommendations": report.recommendations,
        "validationIsolation": report.validation_isolation,
        "startedAt": report.started_at,
        "completedAt": report.completed_at,
        "timestamp": report.timestamp
    }
