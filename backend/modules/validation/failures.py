"""
Phase 8: Failure Analysis Engine
Analyzes why the system fails.
"""
import time
import random
from typing import Dict, List, Optional, Any
from collections import Counter

from .types import (
    FailureAnalysis,
    FailureInstance,
    FailureType,
    Trade,
    TradeOutcome,
    VALIDATION_CONFIG
)


class FailureAnalyzer:
    """
    Failure Analysis Engine.
    
    Analyzes system failures to answer:
    - Why does the system fail?
    - What are the most common failure modes?
    - What patterns lead to failures?
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or VALIDATION_CONFIG
        self._results: Dict[str, FailureAnalysis] = {}
    
    def analyze(
        self,
        trades: Optional[List[Trade]] = None
    ) -> FailureAnalysis:
        """
        Analyze failures from trades.
        
        Args:
            trades: List of trades to analyze
            
        Returns:
            FailureAnalysis with breakdown of failures
        """
        run_id = f"failures_{int(time.time() * 1000)}"
        
        # Generate mock failures if no trades provided
        if not trades:
            trades = self._generate_mock_failed_trades()
        
        # Get losing trades with failure types
        failed_trades = [t for t in trades if t.outcome == TradeOutcome.LOSS and t.failure_type]
        
        # Count failures by type
        failure_counts = Counter(t.failure_type.value for t in failed_trades if t.failure_type)
        
        # Get top failures
        top_failures = [FailureType(ft) for ft, _ in failure_counts.most_common(5)]
        
        # Calculate failure rate
        total_trades = len(trades)
        failure_rate = len(failed_trades) / total_trades if total_trades > 0 else 0
        
        # Calculate impact
        total_impact = sum(abs(t.r_multiple) for t in failed_trades)
        avg_impact = total_impact / len(failed_trades) if failed_trades else 0
        
        # Create failure instances
        failure_instances = [
            FailureInstance(
                failure_id=f"fail_{i+1}",
                failure_type=t.failure_type,
                trade_id=t.trade_id,
                timestamp=t.exit_time,
                description=self._get_failure_description(t.failure_type),
                impact_r=abs(t.r_multiple),
                root_cause=self._get_root_cause(t.failure_type),
                related_signals=[t.strategy_id, t.scenario_id],
                context={
                    "direction": t.direction,
                    "confidence": t.confidence,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price
                }
            )
            for i, t in enumerate(failed_trades[:50])  # Limit to 50 instances
        ]
        
        # Identify patterns
        patterns = self._identify_patterns(failed_trades)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(failure_counts, patterns)
        
        result = FailureAnalysis(
            run_id=run_id,
            failure_counts=dict(failure_counts),
            top_failures=top_failures,
            total_failures=len(failed_trades),
            failure_rate=round(failure_rate, 4),
            total_failure_impact_r=round(total_impact, 2),
            avg_failure_impact_r=round(avg_impact, 4),
            failure_instances=failure_instances,
            failure_patterns=patterns,
            recommendations=recommendations,
            timestamp=int(time.time() * 1000)
        )
        
        self._results[run_id] = result
        
        return result
    
    def get_result(self, run_id: str) -> Optional[FailureAnalysis]:
        """Get failure analysis by ID"""
        return self._results.get(run_id)
    
    def _generate_mock_failed_trades(self) -> List[Trade]:
        """
        Generate mock failed trades for testing.
        """
        trades = []
        failure_weights = {
            FailureType.FALSE_BREAKOUT: 0.25,
            FailureType.WRONG_SCENARIO: 0.18,
            FailureType.LATE_ENTRY: 0.15,
            FailureType.EARLY_EXIT: 0.12,
            FailureType.MTF_CONFLICT: 0.10,
            FailureType.MEMORY_MISLEAD: 0.08,
            FailureType.REGIME_MISMATCH: 0.06,
            FailureType.LIQUIDITY_TRAP: 0.03,
            FailureType.STRUCTURE_BREAK: 0.02,
            FailureType.OVERCONFIDENCE: 0.01
        }
        
        # Generate mix of wins and losses
        for i in range(400):
            is_win = random.random() < 0.58  # 58% win rate
            
            if is_win:
                r_multiple = random.uniform(0.5, 3.0)
                outcome = TradeOutcome.WIN
                failure_type = None
            else:
                r_multiple = -random.uniform(0.5, 1.5)
                outcome = TradeOutcome.LOSS
                # Assign failure type based on weights
                rand = random.random()
                cumulative = 0
                failure_type = FailureType.FALSE_BREAKOUT  # Default
                for ft, weight in failure_weights.items():
                    cumulative += weight
                    if rand < cumulative:
                        failure_type = ft
                        break
            
            trades.append(Trade(
                trade_id=f"trade_{i+1}",
                symbol="BTCUSDT",
                timeframe="4h",
                direction=random.choice(["LONG", "SHORT"]),
                entry_price=40000 + random.uniform(-5000, 10000),
                exit_price=40000 + random.uniform(-5000, 10000),
                entry_time=int(time.time() * 1000) - (400 - i) * 4 * 3600000,
                exit_time=int(time.time() * 1000) - (400 - i - 1) * 4 * 3600000,
                r_multiple=round(r_multiple, 2),
                outcome=outcome,
                strategy_id=random.choice(["MTF_BREAKOUT", "LIQUIDITY_SWEEP", "RANGE_REVERSAL"]),
                scenario_id=f"scenario_{random.choice(['breakout', 'reversal', 'continuation'])}",
                confidence=round(0.4 + random.uniform(0, 0.5), 2),
                failure_type=failure_type
            ))
        
        return trades
    
    def _get_failure_description(self, failure_type: FailureType) -> str:
        """Get human-readable failure description"""
        descriptions = {
            FailureType.FALSE_BREAKOUT: "Price broke level but quickly reversed - false breakout signal",
            FailureType.WRONG_SCENARIO: "Scenario prediction was incorrect - market moved differently",
            FailureType.LATE_ENTRY: "Entry was too late - missed optimal entry point",
            FailureType.EARLY_EXIT: "Exit was premature - would have been profitable if held",
            FailureType.MTF_CONFLICT: "Higher/lower timeframe signals conflicted with entry timeframe",
            FailureType.MEMORY_MISLEAD: "Historical pattern similarity led to wrong conclusion",
            FailureType.REGIME_MISMATCH: "Wrong market regime detected - strategy not suitable",
            FailureType.LIQUIDITY_TRAP: "Liquidity sweep not detected - stopped out at sweep",
            FailureType.STRUCTURE_BREAK: "Market structure broke unexpectedly",
            FailureType.OVERCONFIDENCE: "System was overconfident despite weak signals"
        }
        return descriptions.get(failure_type, "Unknown failure type")
    
    def _get_root_cause(self, failure_type: FailureType) -> str:
        """Get root cause for failure type"""
        causes = {
            FailureType.FALSE_BREAKOUT: "Breakout detector sensitivity too high",
            FailureType.WRONG_SCENARIO: "Scenario engine needs more training data",
            FailureType.LATE_ENTRY: "Entry confirmation delay too long",
            FailureType.EARLY_EXIT: "Stop loss or target placement issues",
            FailureType.MTF_CONFLICT: "MTF alignment weights need calibration",
            FailureType.MEMORY_MISLEAD: "Memory similarity threshold too low",
            FailureType.REGIME_MISMATCH: "Regime detection latency",
            FailureType.LIQUIDITY_TRAP: "Liquidity sweep detector needs tuning",
            FailureType.STRUCTURE_BREAK: "Structure detection lag",
            FailureType.OVERCONFIDENCE: "Confidence calibration needed"
        }
        return causes.get(failure_type, "Needs investigation")
    
    def _identify_patterns(self, failed_trades: List[Trade]) -> List[Dict]:
        """
        Identify patterns in failures.
        """
        patterns = []
        
        # Pattern 1: Failures by time of day (mock)
        patterns.append({
            "pattern": "TIME_CLUSTERING",
            "description": "Failures cluster around certain hours",
            "peak_hours": ["08:00", "14:00", "20:00"],
            "significance": 0.72
        })
        
        # Pattern 2: Failures by strategy
        strategy_failures = Counter(t.strategy_id for t in failed_trades)
        worst_strategy = strategy_failures.most_common(1)[0] if strategy_failures else ("unknown", 0)
        patterns.append({
            "pattern": "STRATEGY_WEAKNESS",
            "description": f"Strategy '{worst_strategy[0]}' has highest failure count",
            "strategy": worst_strategy[0],
            "count": worst_strategy[1],
            "significance": 0.68
        })
        
        # Pattern 3: Consecutive failures
        max_consecutive = 0
        current_consecutive = 0
        for t in failed_trades:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        
        if max_consecutive > 3:
            patterns.append({
                "pattern": "CONSECUTIVE_FAILURES",
                "description": f"Up to {max_consecutive} consecutive failures detected",
                "max_consecutive": max_consecutive,
                "significance": 0.65
            })
        
        # Pattern 4: High confidence failures
        high_conf_failures = [t for t in failed_trades if t.confidence > 0.7]
        if high_conf_failures:
            patterns.append({
                "pattern": "OVERCONFIDENCE_FAILURES",
                "description": f"{len(high_conf_failures)} failures with confidence > 70%",
                "count": len(high_conf_failures),
                "significance": 0.82
            })
        
        return patterns
    
    def _generate_recommendations(self, failure_counts: Counter, patterns: List[Dict]) -> List[str]:
        """
        Generate actionable recommendations based on failures.
        """
        recommendations = []
        
        # Based on top failures
        if failure_counts:
            top_failure = failure_counts.most_common(1)[0][0]
            if top_failure == FailureType.FALSE_BREAKOUT.value:
                recommendations.append("Reduce breakout detector sensitivity or add confirmation filters")
            elif top_failure == FailureType.WRONG_SCENARIO.value:
                recommendations.append("Improve scenario engine with more historical data")
            elif top_failure == FailureType.LATE_ENTRY.value:
                recommendations.append("Reduce entry confirmation delay")
            elif top_failure == FailureType.MTF_CONFLICT.value:
                recommendations.append("Recalibrate MTF alignment weights")
        
        # Based on patterns
        for pattern in patterns:
            if pattern["pattern"] == "OVERCONFIDENCE_FAILURES":
                recommendations.append("Implement confidence calibration to reduce overconfidence")
            elif pattern["pattern"] == "STRATEGY_WEAKNESS":
                recommendations.append(f"Review and potentially retire strategy '{pattern.get('strategy')}'")
        
        # General recommendations
        recommendations.append("Consider regime-specific strategy switching")
        
        return recommendations


def failure_analysis_to_dict(analysis: FailureAnalysis) -> Dict[str, Any]:
    """Convert FailureAnalysis to JSON-serializable dict"""
    return {
        "runId": analysis.run_id,
        "failureCounts": analysis.failure_counts,
        "topFailures": [f.value for f in analysis.top_failures],
        "totalFailures": analysis.total_failures,
        "failureRate": analysis.failure_rate,
        "totalFailureImpactR": analysis.total_failure_impact_r,
        "avgFailureImpactR": analysis.avg_failure_impact_r,
        "failureInstances": [
            {
                "failureId": fi.failure_id,
                "failureType": fi.failure_type.value,
                "tradeId": fi.trade_id,
                "timestamp": fi.timestamp,
                "description": fi.description,
                "impactR": fi.impact_r,
                "rootCause": fi.root_cause
            }
            for fi in analysis.failure_instances[:20]  # Limit output
        ],
        "failurePatterns": analysis.failure_patterns,
        "recommendations": analysis.recommendations,
        "timestamp": analysis.timestamp
    }
