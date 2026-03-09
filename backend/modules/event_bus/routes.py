"""
Event Bus API Routes
====================

REST API endpoints for Event Bus.

Endpoints:
- GET  /api/events              - List events
- GET  /api/events/{id}         - Get event by ID
- POST /api/events/publish      - Publish event
- GET  /api/events/replay       - Replay events
- GET  /api/events/stats        - Get statistics
- GET  /api/events/subscriptions - List subscriptions
- GET  /api/events/health       - Health check
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .types import SystemEvent, EventCategory, EventType
from .store import get_event_store
from .dispatcher import get_dispatcher
from .publisher import create_publisher


router = APIRouter(prefix="/api/events", tags=["Event Bus"])


# Request/Response models

class PublishEventRequest(BaseModel):
    """Request to publish an event"""
    type: str
    source: str
    payload: Dict[str, Any] = {}
    correlation_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class ReplayRequest(BaseModel):
    """Request to replay events"""
    since: int  # Unix timestamp ms
    until: Optional[int] = None
    event_types: Optional[List[str]] = None
    limit: int = 100


# Endpoints

@router.get("/health")
async def event_bus_health():
    """Event Bus health check"""
    store = get_event_store()
    dispatcher = get_dispatcher()
    
    return {
        "enabled": True,
        "version": "event_bus_v1",
        "status": "ok",
        "store_connected": store.is_connected(),
        "dispatcher_stats": dispatcher.get_stats(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("")
async def list_events(
    limit: int = Query(50, ge=1, le=500),
    category: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, alias="type"),
    source: Optional[str] = Query(None),
    since: Optional[int] = Query(None),
    until: Optional[int] = Query(None),
    correlation_id: Optional[str] = Query(None)
):
    """
    List events with optional filters.
    
    Query params:
    - limit: Max events to return (1-500)
    - category: Filter by category (RESEARCH, PORTFOLIO, RISK, etc.)
    - type: Filter by event type
    - source: Filter by source module
    - since: Filter events after timestamp (ms)
    - until: Filter events before timestamp (ms)
    - correlation_id: Filter by correlation ID
    """
    store = get_event_store()
    
    events = store.get_events(
        limit=limit,
        category=category,
        event_type=event_type,
        source=source,
        since=since,
        until=until,
        correlation_id=correlation_id
    )
    
    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
        "filters": {
            "category": category,
            "type": event_type,
            "source": source,
            "since": since,
            "until": until
        }
    }


@router.get("/categories")
async def list_categories():
    """List all event categories"""
    return {
        "categories": [c.value for c in EventCategory],
        "descriptions": {
            "RESEARCH": "Research cycle, features, alphas",
            "PORTFOLIO": "Portfolio rebalancing, weights",
            "RISK": "Risk state changes, drawdowns",
            "EXECUTION": "Trade execution, slippage",
            "GOVERNANCE": "Policies, datasets, experiments",
            "SYSTEM": "System startup, modules"
        }
    }


@router.get("/types")
async def list_event_types():
    """List all event types"""
    return {
        "types": [t.value for t in EventType],
        "by_category": {
            cat.value: [
                t.value for t, c in 
                __import__('modules.event_bus.types', fromlist=['EVENT_CATEGORY_MAP']).EVENT_CATEGORY_MAP.items()
                if c == cat
            ]
            for cat in EventCategory
        }
    }


@router.post("/publish")
async def publish_event(request: PublishEventRequest):
    """
    Publish a new event with optional idempotency.
    
    Body:
    - type: Event type (string)
    - source: Source module name
    - payload: Event data (object)
    - correlation_id: Optional correlation ID
    - idempotency_key: Optional key to prevent duplicates
    """
    publisher = create_publisher(request.source)
    
    event = publisher.publish(
        event_type=request.type,
        payload=request.payload,
        correlation_id=request.correlation_id,
        idempotency_key=request.idempotency_key
    )
    
    if event is None:
        return {
            "success": False,
            "duplicate": True,
            "message": "Event rejected: duplicate idempotency key"
        }
    
    dispatcher = get_dispatcher()
    handlers_count = dispatcher.get_handlers_for_type(request.type)
    
    return {
        "success": True,
        "event": event.to_dict(),
        "handlers_notified": handlers_count
    }


@router.get("/stats")
async def get_stats():
    """Get event bus statistics"""
    store = get_event_store()
    dispatcher = get_dispatcher()
    
    store_stats = store.get_stats()
    dispatcher_stats = dispatcher.get_stats()
    
    return {
        "store": store_stats.to_dict(),
        "dispatcher": dispatcher_stats,
        "total_events": store_stats.total_published,
        "total_dispatched": dispatcher_stats["total_dispatched"],
        "errors": store_stats.errors + dispatcher_stats["errors"]
    }


@router.get("/recent")
async def get_recent_events(limit: int = Query(20, ge=1, le=100)):
    """Get recent events from memory (fast, no DB query)"""
    dispatcher = get_dispatcher()
    events = dispatcher.get_recent_events(limit)
    
    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
        "source": "memory_cache"
    }


@router.get("/subscriptions")
async def list_subscriptions():
    """List all active subscriptions"""
    dispatcher = get_dispatcher()
    subscriptions = dispatcher.get_subscriptions()
    
    return {
        "subscriptions": [s.to_dict() for s in subscriptions],
        "count": len(subscriptions)
    }


@router.post("/replay")
async def replay_events(request: ReplayRequest):
    """
    Replay events for a time range.
    Returns events in chronological order.
    
    Body:
    - since: Start timestamp (ms)
    - until: End timestamp (ms, optional)
    - event_types: Filter by types (optional)
    - limit: Max events (default 100)
    """
    store = get_event_store()
    
    events = store.get_events_for_replay(
        since=request.since,
        until=request.until,
        event_types=request.event_types,
        limit=request.limit
    )
    
    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
        "replay_config": {
            "since": request.since,
            "until": request.until,
            "event_types": request.event_types
        }
    }


@router.get("/count")
async def count_events(
    category: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, alias="type"),
    since: Optional[int] = Query(None)
):
    """Count events matching criteria"""
    store = get_event_store()
    
    count = store.count_events(
        category=category,
        event_type=event_type,
        since=since
    )
    
    return {
        "count": count,
        "filters": {
            "category": category,
            "type": event_type,
            "since": since
        }
    }


@router.get("/latest/{event_type}")
async def get_latest_by_type(event_type: str):
    """Get most recent event of a specific type"""
    store = get_event_store()
    event = store.get_latest_by_type(event_type)
    
    if not event:
        raise HTTPException(status_code=404, detail=f"No events of type: {event_type}")
    
    return event.to_dict()


@router.delete("/cleanup")
async def cleanup_old_events(before: int = Query(..., description="Delete events before this timestamp (ms)")):
    """Delete old events for cleanup"""
    store = get_event_store()
    deleted = store.clear_old_events(before)
    
    return {
        "success": True,
        "deleted_count": deleted,
        "before_timestamp": before
    }


@router.get("/{event_id}")
async def get_event(event_id: str):
    """Get event by ID"""
    store = get_event_store()
    event = store.get_by_id(event_id)
    
    if not event:
        raise HTTPException(status_code=404, detail=f"Event not found: {event_id}")
    
    return event.to_dict()


# ============================================
# Dead Letter Queue endpoints
# ============================================

@router.get("/dlq/pending")
async def dlq_pending(limit: int = Query(50, ge=1, le=200)):
    """Get pending dead letters"""
    try:
        from modules.infrastructure.dead_letter_queue import get_dlq
        dlq = get_dlq()
        return {
            "dead_letters": dlq.get_pending(limit),
            "count": dlq.count_pending()
        }
    except ImportError:
        return {"dead_letters": [], "count": 0, "error": "DLQ not available"}


@router.get("/dlq/stats")
async def dlq_stats():
    """Get DLQ statistics"""
    try:
        from modules.infrastructure.dead_letter_queue import get_dlq
        dlq = get_dlq()
        return dlq.get_stats()
    except ImportError:
        return {"connected": False, "total": 0, "pending": 0, "resolved": 0}


@router.post("/dlq/{dlq_id}/resolve")
async def dlq_resolve(dlq_id: str):
    """Mark a dead letter as resolved"""
    try:
        from modules.infrastructure.dead_letter_queue import get_dlq
        dlq = get_dlq()
        success = dlq.resolve(dlq_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Dead letter not found: {dlq_id}")
        return {"success": True, "id": dlq_id}
    except ImportError:
        raise HTTPException(status_code=503, detail="DLQ not available")
