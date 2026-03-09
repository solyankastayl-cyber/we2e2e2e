"""
System Timeline API Routes
==========================

REST API for System Timeline queries.

Endpoints:
- GET  /api/timeline/health          - Health check
- GET  /api/timeline/recent          - Get recent events
- GET  /api/timeline/events          - Query events with filters
- GET  /api/timeline/category/{cat}  - Get events by category
- GET  /api/timeline/strategy/{id}   - Get events for strategy
- GET  /api/timeline/range           - Get events in time range
- GET  /api/timeline/before/{id}     - Get events before specific event
- POST /api/timeline/record          - Manually record event
- POST /api/timeline/snapshot        - Create system snapshot
- GET  /api/timeline/snapshots       - Get recent snapshots
- GET  /api/timeline/daily/{date}    - Get daily summary
- GET  /api/timeline/stats           - Get statistics
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .engine import system_timeline_engine


router = APIRouter(prefix="/api/timeline", tags=["System Timeline"])


# Request models

class RecordEventRequest(BaseModel):
    """Request to manually record an event"""
    event_type: str
    source: str
    payload: Dict[str, Any] = {}
    category: str = "SYSTEM"


class CreateSnapshotRequest(BaseModel):
    """Request to create a snapshot"""
    risk_state: str = "NORMAL"
    system_state: str = "ACTIVE"
    portfolio_exposure: float = 0.0
    active_strategies: int = 0
    core_strategies: int = 0
    degraded_strategies: int = 0
    research_cycles_today: int = 0
    summary: Optional[Dict[str, Any]] = None


# Endpoints

@router.get("/health")
async def timeline_health():
    """System Timeline health check"""
    return system_timeline_engine.get_health()


@router.get("/recent")
async def get_recent_events(limit: int = Query(50, ge=1, le=200)):
    """Get recent events from memory cache (fast)"""
    events = system_timeline_engine.get_recent(limit)
    
    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
        "source": "memory_cache"
    }


@router.get("/events")
async def query_events(
    limit: int = Query(100, ge=1, le=500),
    category: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None, alias="type"),
    source: Optional[str] = Query(None),
    since: Optional[int] = Query(None),
    until: Optional[int] = Query(None)
):
    """Query events with filters"""
    events = system_timeline_engine.query_events(
        limit=limit,
        category=category,
        event_type=event_type,
        source=source,
        since=since,
        until=until
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


@router.get("/category/{category}")
async def get_events_by_category(
    category: str,
    limit: int = Query(100, ge=1, le=500)
):
    """Get events by category"""
    events = system_timeline_engine.get_events_by_category(category, limit)
    
    return {
        "category": category,
        "events": [e.to_dict() for e in events],
        "count": len(events)
    }


@router.get("/strategy/{strategy_id}")
async def get_events_for_strategy(
    strategy_id: str,
    limit: int = Query(100, ge=1, le=500)
):
    """Get events related to a strategy"""
    events = system_timeline_engine.get_events_for_strategy(strategy_id, limit)
    
    return {
        "strategy_id": strategy_id,
        "events": [e.to_dict() for e in events],
        "count": len(events)
    }


@router.get("/range")
async def get_events_in_range(
    since: int = Query(..., description="Start timestamp (ms)"),
    until: int = Query(..., description="End timestamp (ms)"),
    limit: int = Query(500, ge=1, le=2000)
):
    """Get events in a time range (chronological order)"""
    events = system_timeline_engine.get_events_in_range(since, until, limit)
    
    return {
        "events": [e.to_dict() for e in events],
        "count": len(events),
        "range": {"since": since, "until": until}
    }


@router.get("/before/{event_id}")
async def get_events_before(
    event_id: str,
    count: int = Query(20, ge=1, le=100)
):
    """Get events before a specific event (for analysis)"""
    events = system_timeline_engine.get_events_before(event_id, count)
    
    return {
        "reference_event_id": event_id,
        "events": [e.to_dict() for e in events],
        "count": len(events)
    }


@router.post("/record")
async def record_event(request: RecordEventRequest):
    """Manually record an event"""
    event = system_timeline_engine.record_manual_event(
        event_type=request.event_type,
        source=request.source,
        payload=request.payload,
        category=request.category
    )
    
    return {
        "success": True,
        "event": event.to_dict()
    }


@router.post("/snapshot")
async def create_snapshot(request: CreateSnapshotRequest):
    """Create a system snapshot"""
    snapshot = system_timeline_engine.create_snapshot(
        risk_state=request.risk_state,
        system_state=request.system_state,
        portfolio_exposure=request.portfolio_exposure,
        active_strategies=request.active_strategies,
        core_strategies=request.core_strategies,
        degraded_strategies=request.degraded_strategies,
        research_cycles_today=request.research_cycles_today,
        additional_summary=request.summary
    )
    
    return {
        "success": True,
        "snapshot": snapshot.to_dict()
    }


@router.get("/snapshots")
async def get_snapshots(limit: int = Query(30, ge=1, le=100)):
    """Get recent system snapshots"""
    snapshots = system_timeline_engine.get_snapshots(limit)
    
    return {
        "snapshots": [s.to_dict() for s in snapshots],
        "count": len(snapshots)
    }


@router.get("/daily/{date}")
async def get_daily_summary(date: str):
    """Get summary for a specific day (format: YYYY-MM-DD)"""
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    summary = system_timeline_engine.get_daily_summary(date)
    
    return summary


@router.get("/daily")
async def get_today_summary():
    """Get summary for today"""
    summary = system_timeline_engine.get_daily_summary()
    return summary


@router.get("/stats")
async def get_stats():
    """Get timeline statistics"""
    return system_timeline_engine.get_stats()
