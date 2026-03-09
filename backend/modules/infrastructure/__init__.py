"""
Infrastructure Module
=====================

Backend hardening and stress testing.

Components:
- Idempotency Store: Event deduplication
- Dead Letter Queue: Failed event storage
- Circuit Breaker: Cascade failure protection
- Rate Limiter: Throttling
- Stress Test Engine: Load testing
"""

from .hardening import (
    # Idempotency
    IdempotencyStore,
    idempotency_store,
    idempotent_handler,
    
    # Dead Letter Queue
    DeadLetterEntry,
    DeadLetterQueue,
    dead_letter_queue,
    
    # Circuit Breaker
    CircuitState,
    CircuitBreaker,
    CircuitOpenError,
    get_circuit_breaker,
    with_circuit_breaker,
    
    # Rate Limiter
    RateLimiter,
    get_rate_limiter,
    
    # Data Integrity
    calculate_checksum,
    verify_checksum,
    
    # Health Checks
    HealthCheckRegistry,
    health_check_registry,
    
    # Stats
    get_hardening_stats
)

from .stress_test import (
    StressTestResult,
    StressTestEngine,
    stress_test_engine
)

from .routes import router


__all__ = [
    # Idempotency
    "IdempotencyStore",
    "idempotency_store",
    "idempotent_handler",
    
    # Dead Letter Queue
    "DeadLetterEntry",
    "DeadLetterQueue",
    "dead_letter_queue",
    
    # Circuit Breaker
    "CircuitState",
    "CircuitBreaker",
    "CircuitOpenError",
    "get_circuit_breaker",
    "with_circuit_breaker",
    
    # Rate Limiter
    "RateLimiter",
    "get_rate_limiter",
    
    # Data Integrity
    "calculate_checksum",
    "verify_checksum",
    
    # Health Checks
    "HealthCheckRegistry",
    "health_check_registry",
    
    # Stats
    "get_hardening_stats",
    
    # Stress Test
    "StressTestResult",
    "StressTestEngine",
    "stress_test_engine",
    
    # Router
    "router"
]


print("[Infrastructure] Module loaded")
