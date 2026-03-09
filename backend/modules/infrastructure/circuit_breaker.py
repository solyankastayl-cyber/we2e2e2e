"""
Circuit Breaker
===============

Prevents cascading failures by monitoring service health.

States:
- CLOSED:    Normal operation, calls pass through
- OPEN:      Service down, calls fail immediately
- HALF_OPEN: Testing if service recovered
"""

import time
import threading
from enum import Enum
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker"""
    failure_threshold: int = 5
    recovery_timeout_sec: float = 30.0
    half_open_max_calls: int = 3
    success_threshold: int = 2


@dataclass
class CircuitMetrics:
    """Metrics for a circuit breaker"""
    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_at: Optional[float] = None
    last_success_at: Optional[float] = None
    times_opened: int = 0
    last_state_change_at: Optional[float] = None


class CircuitBreaker:
    """
    Circuit Breaker implementation.
    
    Usage:
        cb = CircuitBreaker("research_loop", config)
        result = cb.call(some_function, arg1, arg2)
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._metrics = CircuitMetrics()
        self._lock = threading.RLock()
        self._half_open_calls = 0
    
    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._transition(CircuitState.HALF_OPEN)
            return self._state
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker"""
        current_state = self.state
        
        if current_state == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit '{self.name}' is OPEN. "
                f"Recovery in {self._time_until_recovery():.1f}s"
            )
        
        if current_state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitOpenError(
                        f"Circuit '{self.name}' HALF_OPEN: max test calls reached"
                    )
                self._half_open_calls += 1
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        with self._lock:
            self._metrics.total_calls += 1
            self._metrics.total_successes += 1
            self._metrics.consecutive_successes += 1
            self._metrics.consecutive_failures = 0
            self._metrics.last_success_at = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                if self._metrics.consecutive_successes >= self.config.success_threshold:
                    self._transition(CircuitState.CLOSED)
    
    def _on_failure(self):
        with self._lock:
            self._metrics.total_calls += 1
            self._metrics.total_failures += 1
            self._metrics.consecutive_failures += 1
            self._metrics.consecutive_successes = 0
            self._metrics.last_failure_at = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN)
            elif self._metrics.consecutive_failures >= self.config.failure_threshold:
                self._transition(CircuitState.OPEN)
    
    def _transition(self, new_state: CircuitState):
        old_state = self._state
        self._state = new_state
        self._metrics.last_state_change_at = time.time()
        
        if new_state == CircuitState.OPEN:
            self._metrics.times_opened += 1
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._metrics.consecutive_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._metrics.consecutive_failures = 0
            self._half_open_calls = 0
        
        print(f"[CircuitBreaker:{self.name}] {old_state.value} -> {new_state.value}")
    
    def _should_attempt_recovery(self) -> bool:
        if self._metrics.last_failure_at is None:
            return True
        elapsed = time.time() - self._metrics.last_failure_at
        return elapsed >= self.config.recovery_timeout_sec
    
    def _time_until_recovery(self) -> float:
        if self._metrics.last_failure_at is None:
            return 0.0
        elapsed = time.time() - self._metrics.last_failure_at
        remaining = self.config.recovery_timeout_sec - elapsed
        return max(0.0, remaining)
    
    def reset(self):
        """Manually reset to CLOSED"""
        with self._lock:
            self._transition(CircuitState.CLOSED)
    
    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "metrics": {
                    "total_calls": self._metrics.total_calls,
                    "total_successes": self._metrics.total_successes,
                    "total_failures": self._metrics.total_failures,
                    "consecutive_failures": self._metrics.consecutive_failures,
                    "consecutive_successes": self._metrics.consecutive_successes,
                    "times_opened": self._metrics.times_opened,
                    "last_failure_at": self._metrics.last_failure_at,
                    "last_success_at": self._metrics.last_success_at,
                },
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout_sec": self.config.recovery_timeout_sec,
                    "half_open_max_calls": self.config.half_open_max_calls,
                    "success_threshold": self.config.success_threshold,
                },
                "time_until_recovery": (
                    self._time_until_recovery() if self._state == CircuitState.OPEN else None
                )
            }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# Registry of all circuit breakers
_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig = None
) -> CircuitBreaker:
    """Get or create a named circuit breaker"""
    with _registry_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name, config)
        return _breakers[name]


def get_all_breakers() -> Dict[str, Dict]:
    """Get status of all circuit breakers"""
    with _registry_lock:
        return {name: cb.get_status() for name, cb in _breakers.items()}


def reset_breaker(name: str) -> bool:
    """Reset a named circuit breaker"""
    with _registry_lock:
        if name in _breakers:
            _breakers[name].reset()
            return True
        return False
