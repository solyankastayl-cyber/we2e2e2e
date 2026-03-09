"""
Infrastructure Stress Test Module
=================================

Load testing for system components.

Tests:
- Event Bus throughput
- Research Loop concurrency
- Timeline write rate
- Memory/CPU under load
"""

import time
import asyncio
import random
import statistics
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
import concurrent.futures


import concurrent.futures as cf


@dataclass
class StressTestResult:
    """Result of a stress test"""
    test_id: str
    test_name: str
    started_at: int
    completed_at: int
    duration_ms: int
    
    # Load parameters
    concurrent_count: int
    total_operations: int
    
    # Results
    successful_operations: int
    failed_operations: int
    success_rate: float
    
    # Latency metrics
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    
    # Throughput
    operations_per_second: float
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "concurrent_count": self.concurrent_count,
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "operations_per_second": round(self.operations_per_second, 2),
            "errors": self.errors[:10]  # Limit errors
        }


class StressTestEngine:
    """
    Engine for running stress tests on system components.
    """
    
    def __init__(self):
        self.results: Dict[str, StressTestResult] = {}
        self._running = False
    
    def run_event_bus_test(
        self,
        event_count: int = 1000,
        concurrent: int = 10
    ) -> StressTestResult:
        """
        Test Event Bus throughput.
        """
        import uuid
        
        test_id = f"stress_eb_{uuid.uuid4().hex[:8]}"
        started_at = int(time.time() * 1000)
        latencies = []
        errors = []
        successful = 0
        failed = 0
        
        try:
            from modules.event_bus import create_publisher
            publisher = create_publisher("stress_test")
        except ImportError:
            return self._create_error_result(test_id, "event_bus_throughput", "Event Bus not available")
        
        def publish_event(i: int) -> float:
            start = time.time()
            try:
                publisher.publish(
                    f"stress_test_event_{i}",
                    {"index": i, "timestamp": int(time.time() * 1000)}
                )
                return (time.time() - start) * 1000
            except Exception as e:
                raise e
        
        with cf.ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = [executor.submit(publish_event, i) for i in range(event_count)]
            
            for future in cf.as_completed(futures):
                try:
                    latency = future.result()
                    latencies.append(latency)
                    successful += 1
                except Exception as e:
                    failed += 1
                    errors.append(str(e))
        
        completed_at = int(time.time() * 1000)
        
        return self._create_result(
            test_id=test_id,
            test_name="event_bus_throughput",
            started_at=started_at,
            completed_at=completed_at,
            concurrent=concurrent,
            total_ops=event_count,
            successful=successful,
            failed=failed,
            latencies=latencies,
            errors=errors
        )
    
    def run_timeline_write_test(
        self,
        event_count: int = 500,
        concurrent: int = 5
    ) -> StressTestResult:
        """
        Test Timeline Engine write throughput.
        """
        import uuid
        
        test_id = f"stress_tl_{uuid.uuid4().hex[:8]}"
        started_at = int(time.time() * 1000)
        latencies = []
        errors = []
        successful = 0
        failed = 0
        
        try:
            from modules.system_timeline import system_timeline_engine
        except ImportError:
            return self._create_error_result(test_id, "timeline_write", "Timeline Engine not available")
        
        def write_event(i: int) -> float:
            start = time.time()
            try:
                system_timeline_engine.record_manual_event(
                    event_type=f"stress_test_{i}",
                    source="stress_test",
                    payload={"index": i, "data": "x" * 100},
                    category="SYSTEM"
                )
                return (time.time() - start) * 1000
            except Exception as e:
                raise e
        
        with cf.ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = [executor.submit(write_event, i) for i in range(event_count)]
            
            for future in cf.as_completed(futures):
                try:
                    latency = future.result()
                    latencies.append(latency)
                    successful += 1
                except Exception as e:
                    failed += 1
                    errors.append(str(e))
        
        completed_at = int(time.time() * 1000)
        
        return self._create_result(
            test_id=test_id,
            test_name="timeline_write",
            started_at=started_at,
            completed_at=completed_at,
            concurrent=concurrent,
            total_ops=event_count,
            successful=successful,
            failed=failed,
            latencies=latencies,
            errors=errors
        )
    
    def run_lifecycle_test(
        self,
        strategy_count: int = 100,
        concurrent: int = 5
    ) -> StressTestResult:
        """
        Test Strategy Lifecycle Engine throughput.
        """
        import uuid
        
        test_id = f"stress_lc_{uuid.uuid4().hex[:8]}"
        started_at = int(time.time() * 1000)
        latencies = []
        errors = []
        successful = 0
        failed = 0
        
        try:
            from modules.strategy_lifecycle import strategy_lifecycle_engine
        except ImportError:
            return self._create_error_result(test_id, "lifecycle_operations", "Lifecycle Engine not available")
        
        def lifecycle_ops(i: int) -> float:
            start = time.time()
            strategy_id = f"stress_strat_{uuid.uuid4().hex[:8]}"
            try:
                # Register
                strategy_lifecycle_engine.register(
                    strategy_id=strategy_id,
                    alpha_id=f"alpha_{i}",
                    name=f"Stress Test {i}",
                    family="STRESS_TEST"
                )
                # Promote
                strategy_lifecycle_engine.promote(strategy_id, "stress test")
                return (time.time() - start) * 1000
            except Exception as e:
                raise e
        
        with cf.ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = [executor.submit(lifecycle_ops, i) for i in range(strategy_count)]
            
            for future in cf.as_completed(futures):
                try:
                    latency = future.result()
                    latencies.append(latency)
                    successful += 1
                except Exception as e:
                    failed += 1
                    errors.append(str(e))
        
        completed_at = int(time.time() * 1000)
        
        return self._create_result(
            test_id=test_id,
            test_name="lifecycle_operations",
            started_at=started_at,
            completed_at=completed_at,
            concurrent=concurrent,
            total_ops=strategy_count,
            successful=successful,
            failed=failed,
            latencies=latencies,
            errors=errors
        )
    
    def run_full_stress_test(
        self,
        level: str = "LOW"  # LOW, MEDIUM, HIGH, EXTREME
    ) -> Dict[str, StressTestResult]:
        """
        Run comprehensive stress test at specified level.
        """
        levels = {
            "LOW": {"events": 100, "concurrent": 5},
            "MEDIUM": {"events": 500, "concurrent": 10},
            "HIGH": {"events": 1000, "concurrent": 20},
            "EXTREME": {"events": 5000, "concurrent": 50}
        }
        
        config = levels.get(level, levels["LOW"])
        
        results = {}
        
        # Event Bus test
        results["event_bus"] = self.run_event_bus_test(
            event_count=config["events"],
            concurrent=config["concurrent"]
        )
        
        # Timeline test
        results["timeline"] = self.run_timeline_write_test(
            event_count=config["events"] // 2,
            concurrent=config["concurrent"] // 2
        )
        
        # Lifecycle test
        results["lifecycle"] = self.run_lifecycle_test(
            strategy_count=config["events"] // 10,
            concurrent=config["concurrent"] // 2
        )
        
        # Store results
        for name, result in results.items():
            self.results[result.test_id] = result
        
        return results
    
    def _create_result(
        self,
        test_id: str,
        test_name: str,
        started_at: int,
        completed_at: int,
        concurrent: int,
        total_ops: int,
        successful: int,
        failed: int,
        latencies: List[float],
        errors: List[str]
    ) -> StressTestResult:
        """Create a stress test result"""
        
        duration_ms = completed_at - started_at
        
        if latencies:
            sorted_latencies = sorted(latencies)
            avg_latency = statistics.mean(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            p50_idx = int(len(sorted_latencies) * 0.50)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p99_idx = int(len(sorted_latencies) * 0.99)
            p50 = sorted_latencies[p50_idx] if p50_idx < len(sorted_latencies) else 0
            p95 = sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else 0
            p99 = sorted_latencies[p99_idx] if p99_idx < len(sorted_latencies) else 0
        else:
            avg_latency = min_latency = max_latency = p50 = p95 = p99 = 0
        
        ops_per_sec = (successful / (duration_ms / 1000)) if duration_ms > 0 else 0
        success_rate = successful / total_ops if total_ops > 0 else 0
        
        result = StressTestResult(
            test_id=test_id,
            test_name=test_name,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            concurrent_count=concurrent,
            total_operations=total_ops,
            successful_operations=successful,
            failed_operations=failed,
            success_rate=success_rate,
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            operations_per_second=ops_per_sec,
            errors=errors
        )
        
        self.results[test_id] = result
        return result
    
    def _create_error_result(
        self,
        test_id: str,
        test_name: str,
        error: str
    ) -> StressTestResult:
        """Create an error result"""
        now = int(time.time() * 1000)
        return StressTestResult(
            test_id=test_id,
            test_name=test_name,
            started_at=now,
            completed_at=now,
            duration_ms=0,
            concurrent_count=0,
            total_operations=0,
            successful_operations=0,
            failed_operations=0,
            success_rate=0,
            avg_latency_ms=0,
            min_latency_ms=0,
            max_latency_ms=0,
            p50_latency_ms=0,
            p95_latency_ms=0,
            p99_latency_ms=0,
            operations_per_second=0,
            errors=[error]
        )
    
    def get_results(self) -> List[StressTestResult]:
        return list(self.results.values())
    
    def get_result(self, test_id: str) -> Optional[StressTestResult]:
        return self.results.get(test_id)


# Singleton
stress_test_engine = StressTestEngine()
