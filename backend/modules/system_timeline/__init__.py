"""
System Timeline Module
======================

Black box of the entire system - records all events as chronological history.

Usage:
    from modules.system_timeline import system_timeline_engine
    
    # Query recent events
    events = system_timeline_engine.get_recent(50)
    
    # Query by category
    risk_events = system_timeline_engine.get_events_by_category("RISK")
    
    # Create snapshot
    snapshot = system_timeline_engine.create_snapshot(
        risk_state="NORMAL",
        system_state="ACTIVE",
        active_strategies=10
    )
"""

from .engine import (
    TimelineEvent,
    SystemSnapshot,
    SystemTimelineEngine,
    system_timeline_engine
)

from .routes import router


__all__ = [
    "TimelineEvent",
    "SystemSnapshot",
    "SystemTimelineEngine",
    "system_timeline_engine",
    "router"
]


print("[SystemTimeline] Module loaded")
