"""
Retry Policy
============

Configurable retry with exponential backoff.
"""

import time
import threading
from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum


class RetryStrategy(str, Enum):
    FIXED = "FIXED"
    EXPONENTIAL = "EXPONENTIAL"
    LINEAR = "LINEAR"


@dataclass
class RetryConfig:
    """Retry configuration"""
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay_sec: float = 1.0
    max_delay_sec: float = 30.0
    jitter: bool = True


@dataclass
class RetryResult:
    """Result of a retried operation"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0
    total_time_sec: float = 0.0
    retries_exhausted: bool = False


def calculate_delay(config: RetryConfig, attempt: int) -> float:
    """Calculate delay for retry attempt"""
    if config.strategy == RetryStrategy.FIXED:
        delay = config.base_delay_sec
    elif config.strategy == RetryStrategy.LINEAR:
        delay = config.base_delay_sec * (attempt + 1)
    else:  # EXPONENTIAL
        delay = config.base_delay_sec * (2 ** attempt)
    
    delay = min(delay, config.max_delay_sec)
    
    if config.jitter:
        import random
        delay *= (0.5 + random.random())
    
    return delay


def retry_with_policy(
    func: Callable,
    config: RetryConfig = None,
    *args,
    **kwargs
) -> RetryResult:
    """
    Execute function with retry policy.
    
    Usage:
        result = retry_with_policy(my_func, RetryConfig(max_retries=3), arg1, arg2)
    """
    config = config or RetryConfig()
    start_time = time.time()
    last_error = None
    
    for attempt in range(config.max_retries + 1):
        try:
            result = func(*args, **kwargs)
            return RetryResult(
                success=True,
                result=result,
                attempts=attempt + 1,
                total_time_sec=time.time() - start_time
            )
        except Exception as e:
            last_error = str(e)
            
            if attempt < config.max_retries:
                delay = calculate_delay(config, attempt)
                time.sleep(delay)
    
    return RetryResult(
        success=False,
        error=last_error,
        attempts=config.max_retries + 1,
        total_time_sec=time.time() - start_time,
        retries_exhausted=True
    )
