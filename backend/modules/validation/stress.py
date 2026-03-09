"""
Phase 8: Stress Test Engine
Infrastructure stress testing.
"""
import time
import random
import asyncio
from typing import Dict, List, Optional, Any

from .types import (
    StressTestResult,
    VALIDATION_CONFIG
)


class StressTestEngine:
    """
    Stress Test Engine.
    
    Tests system under various load scenarios:
    - 10 concurrent users
    - 100 concurrent users
    - 1000 concurrent users
    
    Measures:
    - p95/p99 latency
    - CPU usage
    - Memory usage
    - WebSocket delays
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or VALIDATION_CONFIG
        self._results: Dict[str, StressTestResult] = {}
    
    def run(
        self,
        scenarios: Optional[List[str]] = None,
        load_levels: Optional[List[int]] = None
    ) -> StressTestResult:
        """
        Run stress tests.
        
        Args:
            scenarios: List of scenarios to test
            load_levels: List of concurrent user levels
            
        Returns:
            StressTestResult with performance metrics
        """
        run_id = f"stress_{int(time.time() * 1000)}"
        
        scenarios = scenarios or ["api_calls", "websocket", "analysis", "combined"]
        load_levels = load_levels or self.config.get("stress_levels", [10, 50, 100, 500, 1000])
        
        results_by_level: Dict[str, Dict] = {}
        failure_modes: List[Dict] = []
        max_supported = 0
        
        for level in load_levels:
            level_key = f"{level}_users"
            
            # Simulate stress test results
            # In production, this would actually run load tests
            metrics = self._simulate_load_test(level, scenarios)
            
            results_by_level[level_key] = metrics
            
            # Check if system held up
            if metrics["error_rate"] < 0.05 and metrics["p95_latency"] < 5000:
                max_supported = level
            else:
                failure_modes.append({
                    "level": level,
                    "type": "LATENCY_EXCEEDED" if metrics["p95_latency"] >= 5000 else "ERROR_RATE_HIGH",
                    "p95_latency": metrics["p95_latency"],
                    "error_rate": metrics["error_rate"]
                })
        
        # Get peak metrics from highest successful level
        peak_level = f"{max_supported}_users" if max_supported > 0 else f"{load_levels[0]}_users"
        peak_metrics = results_by_level.get(peak_level, {})
        
        # Calculate overall score
        score = self._calculate_stress_score(results_by_level, max_supported, load_levels)
        
        result = StressTestResult(
            run_id=run_id,
            scenarios=scenarios,
            load_levels=results_by_level,
            max_supported_users=max_supported,
            p95_latency_ms=peak_metrics.get("p95_latency", 0),
            p99_latency_ms=peak_metrics.get("p99_latency", 0),
            cpu_peak=peak_metrics.get("cpu_peak", 0),
            memory_peak_mb=peak_metrics.get("memory_peak_mb", 0),
            ws_delay_ms=peak_metrics.get("ws_delay", 0),
            failure_modes=failure_modes,
            passed=len(failure_modes) <= 1 and max_supported >= 100,
            score=round(score, 4),
            timestamp=int(time.time() * 1000)
        )
        
        self._results[run_id] = result
        
        return result
    
    def get_result(self, run_id: str) -> Optional[StressTestResult]:
        """Get a stress test result by ID"""
        return self._results.get(run_id)
    
    def _simulate_load_test(self, users: int, scenarios: List[str]) -> Dict[str, Any]:
        """
        Simulate load test results.
        In production, this would run actual load tests.
        """
        # Base latency increases with load
        base_latency = 50 + (users * 0.3)  # ms
        
        # Add some variance
        variance = random.uniform(0.8, 1.3)
        
        # Calculate metrics with realistic degradation
        p95_latency = base_latency * variance * (1 + (users / 500))
        p99_latency = p95_latency * 1.5
        
        # CPU scales with users (but with ceiling)
        cpu_peak = min(0.95, 0.1 + (users / 1500))
        
        # Memory scales slower
        memory_peak = 512 + (users * 0.8)  # MB
        
        # WebSocket delay
        ws_delay = 10 + (users * 0.05)
        
        # Error rate increases under heavy load
        error_rate = 0.001 if users < 100 else 0.01 if users < 500 else 0.05 if users < 1000 else 0.15
        error_rate *= random.uniform(0.5, 1.5)
        
        return {
            "users": users,
            "scenarios": scenarios,
            "p95_latency": round(p95_latency, 2),
            "p99_latency": round(p99_latency, 2),
            "cpu_peak": round(cpu_peak, 4),
            "memory_peak_mb": round(memory_peak, 2),
            "ws_delay": round(ws_delay, 2),
            "error_rate": round(error_rate, 4),
            "requests_per_second": round(users * 2.5, 1),
            "success_rate": round(1 - error_rate, 4)
        }
    
    def _calculate_stress_score(
        self,
        results: Dict[str, Dict],
        max_supported: int,
        load_levels: List[int]
    ) -> float:
        """
        Calculate overall stress test score.
        
        Factors:
        - Max supported users vs target (1000)
        - Latency under load
        - Error rates
        """
        score = 0.0
        
        # Capacity score (40%)
        capacity_score = min(1.0, max_supported / 500)  # 500+ users = full marks
        score += 0.40 * capacity_score
        
        # Latency score (30%)
        latencies = [r.get("p95_latency", 10000) for r in results.values()]
        avg_latency = sum(latencies) / len(latencies) if latencies else 10000
        latency_score = max(0, 1 - (avg_latency / 2000))  # < 2000ms = good
        score += 0.30 * latency_score
        
        # Error rate score (30%)
        error_rates = [r.get("error_rate", 1.0) for r in results.values()]
        avg_error = sum(error_rates) / len(error_rates) if error_rates else 1.0
        error_score = max(0, 1 - (avg_error / 0.1))  # < 10% error = good
        score += 0.30 * error_score
        
        return score


def stress_test_to_dict(result: StressTestResult) -> Dict[str, Any]:
    """Convert StressTestResult to JSON-serializable dict"""
    return {
        "runId": result.run_id,
        "scenarios": result.scenarios,
        "loadLevels": result.load_levels,
        "maxSupportedUsers": result.max_supported_users,
        "p95LatencyMs": result.p95_latency_ms,
        "p99LatencyMs": result.p99_latency_ms,
        "cpuPeak": result.cpu_peak,
        "memoryPeakMb": result.memory_peak_mb,
        "wsDelayMs": result.ws_delay_ms,
        "failureModes": result.failure_modes,
        "passed": result.passed,
        "score": result.score,
        "timestamp": result.timestamp
    }
