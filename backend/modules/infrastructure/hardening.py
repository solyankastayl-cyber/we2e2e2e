"""
Backend Hardening Module
========================

Engineering protection for the system.

Features:
- Event Bus: Idempotency, retry, dead letter queue
- Circuit Breaker: Timeout protection, backpressure
- Policy: Schema validation, version locking
- Dataset: Checksum validation, reproducibility
"""

import time
import uuid
import hashlib
import functools
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict
import threading
import asyncio


# ============================================
# Event Idempotency Store
# ============================================

class IdempotencyStore:
    """
    Ensures events are processed only once.
    Uses event ID deduplication with TTL.
    """
    
    def __init__(self, ttl_seconds: int = 3600):
        self._processed_ids: Dict[str, int] = {}  # event_id -> timestamp
        self._ttl = ttl_seconds * 1000  # Convert to ms
        self._lock = threading.RLock()
    
    def is_duplicate(self, event_id: str) -> bool:
        """Check if event was already processed"""
        with self._lock:
            self._cleanup_expired()
            return event_id in self._processed_ids
    
    def mark_processed(self, event_id: str):
        """Mark event as processed"""
        with self._lock:
            self._processed_ids[event_id] = int(time.time() * 1000)
    
    def _cleanup_expired(self):
        """Remove expired entries"""
        now = int(time.time() * 1000)
        expired = [
            eid for eid, ts in self._processed_ids.items()
            if now - ts > self._ttl
        ]
        for eid in expired:
            del self._processed_ids[eid]
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "stored_ids": len(self._processed_ids),
                "ttl_seconds": self._ttl // 1000
            }


# Global idempotency store
idempotency_store = IdempotencyStore()


def idempotent_handler(func: Callable) -> Callable:
    """Decorator to make event handler idempotent"""
    @functools.wraps(func)
    def wrapper(event, *args, **kwargs):
        event_id = getattr(event, 'id', None) or event.get('id') if isinstance(event, dict) else None
        
        if event_id and idempotency_store.is_duplicate(event_id):
            return None  # Skip duplicate
        
        result = func(event, *args, **kwargs)
        
        if event_id:
            idempotency_store.mark_processed(event_id)
        
        return result
    
    return wrapper


# ============================================
# Dead Letter Queue
# ============================================

@dataclass
class DeadLetterEntry:
    """Entry in dead letter queue"""
    entry_id: str
    event_id: str
    event_type: str
    payload: Dict[str, Any]
    error: str
    retries: int
    created_at: int
    last_retry_at: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "error": self.error,
            "retries": self.retries,
            "created_at": self.created_at,
            "last_retry_at": self.last_retry_at
        }


class DeadLetterQueue:
    """
    Stores failed events for later retry or manual intervention.
    """
    
    def __init__(self, max_retries: int = 3):
        self._queue: Dict[str, DeadLetterEntry] = {}
        self._max_retries = max_retries
        self._lock = threading.RLock()
    
    def add(
        self,
        event_id: str,
        event_type: str,
        payload: Dict[str, Any],
        error: str
    ) -> DeadLetterEntry:
        """Add failed event to queue"""
        with self._lock:
            # Check if already exists
            existing = self._find_by_event_id(event_id)
            if existing:
                existing.retries += 1
                existing.last_retry_at = int(time.time() * 1000)
                existing.error = error
                return existing
            
            entry = DeadLetterEntry(
                entry_id=f"dlq_{uuid.uuid4().hex[:12]}",
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                error=error,
                retries=0,
                created_at=int(time.time() * 1000)
            )
            self._queue[entry.entry_id] = entry
            return entry
    
    def _find_by_event_id(self, event_id: str) -> Optional[DeadLetterEntry]:
        for entry in self._queue.values():
            if entry.event_id == event_id:
                return entry
        return None
    
    def get_pending(self) -> List[DeadLetterEntry]:
        """Get entries that can be retried"""
        with self._lock:
            return [
                e for e in self._queue.values()
                if e.retries < self._max_retries
            ]
    
    def get_failed(self) -> List[DeadLetterEntry]:
        """Get entries that exceeded max retries"""
        with self._lock:
            return [
                e for e in self._queue.values()
                if e.retries >= self._max_retries
            ]
    
    def remove(self, entry_id: str) -> bool:
        """Remove entry from queue"""
        with self._lock:
            if entry_id in self._queue:
                del self._queue[entry_id]
                return True
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_entries": len(self._queue),
                "pending": len(self.get_pending()),
                "failed": len(self.get_failed()),
                "max_retries": self._max_retries
            }
    
    def get_all(self) -> List[DeadLetterEntry]:
        with self._lock:
            return list(self._queue.values())


# Global dead letter queue
dead_letter_queue = DeadLetterQueue()


# ============================================
# Circuit Breaker
# ============================================

class CircuitState:
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Failing, rejecting calls
    HALF_OPEN = "HALF_OPEN"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """
    Prevents cascade failures by stopping calls to failing services.
    """
    name: str
    failure_threshold: int = 5      # Failures before opening
    recovery_timeout: int = 30000   # ms before trying again
    half_open_max_calls: int = 3    # Test calls in half-open
    
    _state: str = CircuitState.CLOSED
    _failure_count: int = 0
    _success_count: int = 0
    _last_failure_time: int = 0
    _half_open_calls: int = 0
    
    def __post_init__(self):
        self._lock = threading.RLock()
    
    def can_execute(self) -> bool:
        """Check if call can proceed"""
        with self._lock:
            now = int(time.time() * 1000)
            
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout passed
                if now - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    return True
                return False
            
            if self._state == CircuitState.HALF_OPEN:
                return self._half_open_calls < self.half_open_max_calls
            
            return False
    
    def record_success(self):
        """Record successful call"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._reset()
            else:
                self._failure_count = max(0, self._failure_count - 1)
    
    def record_failure(self):
        """Record failed call"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = int(time.time() * 1000)
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
    
    def _reset(self):
        """Reset to closed state"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
    
    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state,
                "failure_count": self._failure_count,
                "failure_threshold": self.failure_threshold,
                "recovery_timeout_ms": self.recovery_timeout
            }


# Circuit breakers registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name=name)
    return _circuit_breakers[name]


def with_circuit_breaker(name: str):
    """Decorator to wrap function with circuit breaker"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cb = get_circuit_breaker(name)
            
            if not cb.can_execute():
                raise CircuitOpenError(f"Circuit breaker {name} is open")
            
            try:
                result = func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure()
                raise
        
        return wrapper
    return decorator


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# ============================================
# Timeout Protection
# ============================================

def with_timeout(seconds: float):
    """Decorator to add timeout to async functions"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds}s")
        
        return wrapper
    return decorator


# ============================================
# Rate Limiter
# ============================================

class RateLimiter:
    """
    Token bucket rate limiter.
    """
    
    def __init__(
        self,
        name: str,
        rate: float,          # Tokens per second
        burst: int            # Max tokens
    ):
        self.name = name
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = time.time()
        self._lock = threading.RLock()
    
    def acquire(self) -> bool:
        """Try to acquire a token"""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_update = now
            
            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "rate": self.rate,
                "burst": self.burst,
                "available_tokens": int(self._tokens)
            }


# Rate limiters registry
_rate_limiters: Dict[str, RateLimiter] = {}


def get_rate_limiter(name: str, rate: float = 10.0, burst: int = 20) -> RateLimiter:
    """Get or create a rate limiter"""
    if name not in _rate_limiters:
        _rate_limiters[name] = RateLimiter(name, rate, burst)
    return _rate_limiters[name]


# ============================================
# Data Integrity
# ============================================

def calculate_checksum(data: Any) -> str:
    """Calculate SHA256 checksum for data"""
    if isinstance(data, dict):
        # Sort keys for consistent hashing
        import json
        data_str = json.dumps(data, sort_keys=True, default=str)
    elif isinstance(data, (list, tuple)):
        import json
        data_str = json.dumps(list(data), default=str)
    else:
        data_str = str(data)
    
    return hashlib.sha256(data_str.encode()).hexdigest()


def verify_checksum(data: Any, expected_checksum: str) -> bool:
    """Verify data matches expected checksum"""
    return calculate_checksum(data) == expected_checksum


# ============================================
# Health Check Registry
# ============================================

class HealthCheckRegistry:
    """
    Registry for component health checks.
    """
    
    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._results: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def register(self, name: str, check_func: Callable):
        """Register a health check function"""
        with self._lock:
            self._checks[name] = check_func
    
    def run_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {}
        overall_healthy = True
        
        with self._lock:
            for name, check_func in self._checks.items():
                try:
                    result = check_func()
                    healthy = result.get("healthy", True) if isinstance(result, dict) else bool(result)
                    results[name] = {
                        "healthy": healthy,
                        "details": result if isinstance(result, dict) else {},
                        "error": None
                    }
                    if not healthy:
                        overall_healthy = False
                except Exception as e:
                    results[name] = {
                        "healthy": False,
                        "details": {},
                        "error": str(e)
                    }
                    overall_healthy = False
            
            self._results = results
        
        return {
            "overall_healthy": overall_healthy,
            "checks": results,
            "timestamp": int(time.time() * 1000)
        }
    
    def get_last_results(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "checks": self._results,
                "count": len(self._results)
            }


# Global health check registry
health_check_registry = HealthCheckRegistry()


# ============================================
# Module Exports
# ============================================

def get_hardening_stats() -> Dict[str, Any]:
    """Get stats for all hardening components"""
    return {
        "idempotency": idempotency_store.get_stats(),
        "dead_letter_queue": dead_letter_queue.get_stats(),
        "circuit_breakers": {
            name: cb.get_state() 
            for name, cb in _circuit_breakers.items()
        },
        "rate_limiters": {
            name: rl.get_stats()
            for name, rl in _rate_limiters.items()
        },
        "health_checks": health_check_registry.get_last_results()
    }
