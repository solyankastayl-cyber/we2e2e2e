"""
Infrastructure API Routes
=========================

REST API for infrastructure management.

Endpoints:
- GET  /api/infra/health           - Overall health
- GET  /api/infra/hardening        - Hardening stats
- GET  /api/infra/dlq              - Dead letter queue
- POST /api/infra/dlq/retry/{id}   - Retry DLQ entry
- GET  /api/infra/circuits         - Circuit breakers
- POST /api/infra/stress-test      - Run stress test
- GET  /api/infra/stress-test/{id} - Get stress test result
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .hardening import (
    idempotency_store,
    dead_letter_queue,
    get_circuit_breaker,
    get_rate_limiter,
    health_check_registry,
    get_hardening_stats,
    _circuit_breakers
)
from .stress_test import stress_test_engine


router = APIRouter(prefix="/api/infra", tags=["Infrastructure"])


# Request models

class RunStressTestRequest(BaseModel):
    """Request to run stress test"""
    level: str = "LOW"  # LOW, MEDIUM, HIGH, EXTREME
    test_type: Optional[str] = None  # event_bus, timeline, lifecycle, or None for all


# Endpoints

@router.get("/health")
async def infra_health():
    """Infrastructure health check"""
    # Run all registered health checks
    results = health_check_registry.run_checks()
    
    return {
        "status": "ok" if results["overall_healthy"] else "degraded",
        "version": "infra_v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "health_checks": results
    }


@router.get("/hardening")
async def get_hardening():
    """Get hardening component statistics"""
    return get_hardening_stats()


@router.get("/dlq")
async def get_dead_letter_queue():
    """Get dead letter queue entries"""
    entries = dead_letter_queue.get_all()
    
    return {
        "entries": [e.to_dict() for e in entries],
        "stats": dead_letter_queue.get_stats()
    }


@router.post("/dlq/retry/{entry_id}")
async def retry_dlq_entry(entry_id: str):
    """Retry a dead letter queue entry"""
    entries = dead_letter_queue.get_all()
    entry = next((e for e in entries if e.entry_id == entry_id), None)
    
    if not entry:
        raise HTTPException(status_code=404, detail=f"Entry not found: {entry_id}")
    
    # Attempt to republish
    try:
        from modules.event_bus import create_publisher
        publisher = create_publisher("dlq_retry")
        publisher.publish(entry.event_type, entry.payload)
        
        # Remove from DLQ
        dead_letter_queue.remove(entry_id)
        
        return {"success": True, "message": "Event republished"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.delete("/dlq/{entry_id}")
async def delete_dlq_entry(entry_id: str):
    """Delete a dead letter queue entry"""
    if dead_letter_queue.remove(entry_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail=f"Entry not found: {entry_id}")


@router.get("/circuits")
async def get_circuit_breakers():
    """Get all circuit breakers status"""
    return {
        "circuit_breakers": {
            name: cb.get_state()
            for name, cb in _circuit_breakers.items()
        },
        "count": len(_circuit_breakers)
    }


@router.post("/circuits/{name}/reset")
async def reset_circuit_breaker(name: str):
    """Reset a circuit breaker"""
    if name not in _circuit_breakers:
        raise HTTPException(status_code=404, detail=f"Circuit breaker not found: {name}")
    
    cb = _circuit_breakers[name]
    cb._reset()
    
    return {
        "success": True,
        "circuit_breaker": cb.get_state()
    }


@router.get("/idempotency")
async def get_idempotency_stats():
    """Get idempotency store statistics"""
    return idempotency_store.get_stats()


@router.post("/stress-test")
async def run_stress_test(request: RunStressTestRequest):
    """
    Run infrastructure stress test.
    
    Levels:
    - LOW: 100 events, 5 concurrent
    - MEDIUM: 500 events, 10 concurrent
    - HIGH: 1000 events, 20 concurrent
    - EXTREME: 5000 events, 50 concurrent
    """
    level = request.level.upper()
    if level not in ["LOW", "MEDIUM", "HIGH", "EXTREME"]:
        raise HTTPException(status_code=400, detail=f"Invalid level: {level}")
    
    if request.test_type:
        # Run specific test
        test_type = request.test_type.lower()
        levels = {
            "LOW": {"events": 100, "concurrent": 5},
            "MEDIUM": {"events": 500, "concurrent": 10},
            "HIGH": {"events": 1000, "concurrent": 20},
            "EXTREME": {"events": 5000, "concurrent": 50}
        }
        config = levels[level]
        
        if test_type == "event_bus":
            result = stress_test_engine.run_event_bus_test(
                event_count=config["events"],
                concurrent=config["concurrent"]
            )
        elif test_type == "timeline":
            result = stress_test_engine.run_timeline_write_test(
                event_count=config["events"] // 2,
                concurrent=config["concurrent"] // 2
            )
        elif test_type == "lifecycle":
            result = stress_test_engine.run_lifecycle_test(
                strategy_count=config["events"] // 10,
                concurrent=config["concurrent"] // 2
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown test type: {test_type}")
        
        return {"success": True, "result": result.to_dict()}
    
    # Run all tests
    results = stress_test_engine.run_full_stress_test(level)
    
    return {
        "success": True,
        "level": level,
        "results": {name: r.to_dict() for name, r in results.items()}
    }


@router.get("/stress-test/{test_id}")
async def get_stress_test_result(test_id: str):
    """Get stress test result by ID"""
    result = stress_test_engine.get_result(test_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Test result not found: {test_id}")
    
    return result.to_dict()


@router.get("/stress-test")
async def list_stress_test_results(limit: int = Query(20, ge=1, le=100)):
    """List stress test results"""
    results = stress_test_engine.get_results()
    results = sorted(results, key=lambda r: r.started_at, reverse=True)[:limit]
    
    return {
        "results": [r.to_dict() for r in results],
        "count": len(results)
    }
