"""
Service Timeout
===============

Wraps service calls with configurable timeouts.
"""

import signal
import threading
import time
from typing import Callable, Any, Dict, Optional


class ServiceTimeoutError(Exception):
    """Raised when a service call exceeds its timeout"""
    pass


def with_timeout(func: Callable, timeout_sec: float, *args, **kwargs) -> Any:
    """
    Execute function with timeout using threading.
    
    Args:
        func: Function to execute
        timeout_sec: Maximum execution time in seconds
        
    Returns:
        Function result
        
    Raises:
        ServiceTimeoutError if timeout exceeded
    """
    result_container = {"result": None, "error": None, "done": False}
    
    def target():
        try:
            result_container["result"] = func(*args, **kwargs)
        except Exception as e:
            result_container["error"] = e
        finally:
            result_container["done"] = True
    
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)
    
    if not result_container["done"]:
        raise ServiceTimeoutError(
            f"Service call timed out after {timeout_sec}s"
        )
    
    if result_container["error"]:
        raise result_container["error"]
    
    return result_container["result"]


# Default timeout configurations per service
SERVICE_TIMEOUTS: Dict[str, float] = {
    "event_bus.publish": 5.0,
    "event_bus.dispatch": 10.0,
    "event_store.save": 5.0,
    "event_store.query": 15.0,
    "policy_engine.validate": 5.0,
    "dataset_registry.validate": 10.0,
    "research_loop.cycle": 120.0,
    "evolution_engine.run": 60.0,
    "autopsy_engine.analyze": 30.0,
    "timeline.save": 5.0,
    "lifecycle.evaluate": 10.0,
    "market_reality.simulate": 30.0,
}


def get_timeout(service_name: str) -> float:
    """Get configured timeout for a service"""
    return SERVICE_TIMEOUTS.get(service_name, 30.0)
