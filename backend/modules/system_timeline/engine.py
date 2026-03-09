"""
System Timeline Engine
======================

Black box of the entire system - records all events as a chronological history.

Converts Event Bus into:
- System history
- Debug trail
- Post-mortem analysis data
- Research insights

Features:
- Subscribes to ALL events
- Persists to MongoDB
- Provides timeline queries
- Creates daily snapshots
- Supports event replay
"""

import time
import uuid
import os
from typing import Dict, List, Optional, Any
from collections import defaultdict
from datetime import datetime, timezone

try:
    from pymongo import MongoClient, DESCENDING, ASCENDING
    from pymongo.collection import Collection
    MONGO_OK = True
except ImportError:
    MONGO_OK = False

# Event Bus integration
try:
    from modules.event_bus import create_subscriber, SystemEvent, EventCategory
    EVENT_BUS_ENABLED = True
except ImportError:
    EVENT_BUS_ENABLED = False


class TimelineEvent:
    """Timeline event record"""
    
    def __init__(
        self,
        event_id: str,
        timestamp: int,
        category: str,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None
    ):
        self.event_id = event_id
        self.timestamp = timestamp
        self.category = category
        self.event_type = event_type
        self.source = source
        self.payload = payload
        self.correlation_id = correlation_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "category": self.category,
            "event_type": self.event_type,
            "source": self.source,
            "payload": self.payload,
            "correlation_id": self.correlation_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineEvent":
        return cls(
            event_id=data.get("event_id", ""),
            timestamp=data.get("timestamp", 0),
            category=data.get("category", ""),
            event_type=data.get("event_type", ""),
            source=data.get("source", ""),
            payload=data.get("payload", {}),
            correlation_id=data.get("correlation_id")
        )


class SystemSnapshot:
    """Daily system snapshot"""
    
    def __init__(
        self,
        snapshot_id: str,
        timestamp: int,
        date: str,
        risk_state: str,
        system_state: str,
        portfolio_exposure: float,
        active_strategies: int,
        core_strategies: int,
        degraded_strategies: int,
        research_cycles_today: int,
        events_today: int,
        summary: Dict[str, Any] = None
    ):
        self.snapshot_id = snapshot_id
        self.timestamp = timestamp
        self.date = date
        self.risk_state = risk_state
        self.system_state = system_state
        self.portfolio_exposure = portfolio_exposure
        self.active_strategies = active_strategies
        self.core_strategies = core_strategies
        self.degraded_strategies = degraded_strategies
        self.research_cycles_today = research_cycles_today
        self.events_today = events_today
        self.summary = summary or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "date": self.date,
            "risk_state": self.risk_state,
            "system_state": self.system_state,
            "portfolio_exposure": round(self.portfolio_exposure, 4),
            "active_strategies": self.active_strategies,
            "core_strategies": self.core_strategies,
            "degraded_strategies": self.degraded_strategies,
            "research_cycles_today": self.research_cycles_today,
            "events_today": self.events_today,
            "summary": self.summary
        }


class SystemTimelineEngine:
    """
    System Timeline Engine - the black box of the system.
    
    Records all events for:
    - Debugging
    - Post-mortem analysis
    - Research insights
    - Compliance audit
    """
    
    def __init__(self):
        # MongoDB
        self._client: Optional[MongoClient] = None
        self._events_collection: Optional[Collection] = None
        self._snapshots_collection: Optional[Collection] = None
        self._connected = False
        
        # In-memory cache for recent events
        self._recent_events: List[TimelineEvent] = []
        self._max_recent = 500
        
        # Stats
        self._total_events = 0
        self._events_by_category: Dict[str, int] = defaultdict(int)
        self._events_by_type: Dict[str, int] = defaultdict(int)
        
        # Connect and subscribe
        self._connect()
        self._init_event_subscriptions()
    
    def _connect(self) -> bool:
        """Connect to MongoDB"""
        if not MONGO_OK:
            print("[Timeline] pymongo not installed")
            return False
        
        try:
            mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "ta_engine")
            
            self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self._client.admin.command('ping')
            
            db = self._client[db_name]
            self._events_collection = db["timeline_events"]
            self._snapshots_collection = db["system_snapshots"]
            
            # Create indexes
            self._events_collection.create_index([("timestamp", DESCENDING)])
            self._events_collection.create_index([("category", 1)])
            self._events_collection.create_index([("event_type", 1)])
            self._events_collection.create_index([("source", 1)])
            
            self._snapshots_collection.create_index([("date", DESCENDING)])
            
            self._connected = True
            print(f"[Timeline] Connected to MongoDB")
            return True
            
        except Exception as e:
            print(f"[Timeline] Connection error: {e}")
            return False
    
    def _init_event_subscriptions(self):
        """Subscribe to ALL events from Event Bus"""
        if not EVENT_BUS_ENABLED:
            return
        
        try:
            subscriber = create_subscriber("system_timeline")
            
            def on_any_event(event):
                """Record any event"""
                self.record_event(event)
            
            # Subscribe to wildcard (all events)
            subscriber.subscribe_all(on_any_event)
            print("[Timeline] Subscribed to all events")
            
        except Exception as e:
            print(f"[Timeline] Event subscription failed: {e}")
    
    # ============================================
    # Event Recording
    # ============================================
    
    def record_event(self, event) -> bool:
        """Record an event from Event Bus"""
        try:
            timeline_event = TimelineEvent(
                event_id=event.id if hasattr(event, 'id') else f"evt_{uuid.uuid4().hex[:12]}",
                timestamp=event.timestamp if hasattr(event, 'timestamp') else int(time.time() * 1000),
                category=event.category if hasattr(event, 'category') else "SYSTEM",
                event_type=event.type if hasattr(event, 'type') else "unknown",
                source=event.source if hasattr(event, 'source') else "unknown",
                payload=event.payload if hasattr(event, 'payload') else {},
                correlation_id=event.correlation_id if hasattr(event, 'correlation_id') else None
            )
            
            # Add to recent cache
            self._recent_events.append(timeline_event)
            if len(self._recent_events) > self._max_recent:
                self._recent_events.pop(0)
            
            # Update stats
            self._total_events += 1
            self._events_by_category[timeline_event.category] += 1
            self._events_by_type[timeline_event.event_type] += 1
            
            # Persist to MongoDB
            if self._connected:
                self._events_collection.insert_one(timeline_event.to_dict())
            
            return True
            
        except Exception as e:
            print(f"[Timeline] Record error: {e}")
            return False
    
    def record_manual_event(
        self,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        category: str = "SYSTEM"
    ) -> TimelineEvent:
        """Manually record an event"""
        event = TimelineEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            timestamp=int(time.time() * 1000),
            category=category,
            event_type=event_type,
            source=source,
            payload=payload
        )
        
        self._recent_events.append(event)
        self._total_events += 1
        self._events_by_category[category] += 1
        self._events_by_type[event_type] += 1
        
        if self._connected:
            self._events_collection.insert_one(event.to_dict())
        
        return event
    
    # ============================================
    # Timeline Queries
    # ============================================
    
    def get_recent(self, limit: int = 50) -> List[TimelineEvent]:
        """Get recent events from memory cache"""
        return list(reversed(self._recent_events[-limit:]))
    
    def query_events(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        since: Optional[int] = None,
        until: Optional[int] = None,
        strategy_id: Optional[str] = None
    ) -> List[TimelineEvent]:
        """Query events with filters"""
        if not self._connected:
            # Return from cache
            events = self._recent_events
            if category:
                events = [e for e in events if e.category == category]
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            if source:
                events = [e for e in events if e.source == source]
            return list(reversed(events[-limit:]))
        
        try:
            query: Dict[str, Any] = {}
            
            if category:
                query["category"] = category
            if event_type:
                query["event_type"] = event_type
            if source:
                query["source"] = source
            if since:
                query["timestamp"] = {"$gte": since}
            if until:
                if "timestamp" in query:
                    query["timestamp"]["$lte"] = until
                else:
                    query["timestamp"] = {"$lte": until}
            if strategy_id:
                query["payload.strategy_id"] = strategy_id
            
            cursor = self._events_collection.find(
                query,
                {"_id": 0}
            ).sort("timestamp", DESCENDING).limit(limit)
            
            return [TimelineEvent.from_dict(doc) for doc in cursor]
            
        except Exception as e:
            print(f"[Timeline] Query error: {e}")
            return []
    
    def get_events_for_strategy(self, strategy_id: str, limit: int = 100) -> List[TimelineEvent]:
        """Get events related to a specific strategy"""
        return self.query_events(limit=limit, strategy_id=strategy_id)
    
    def get_events_by_category(self, category: str, limit: int = 100) -> List[TimelineEvent]:
        """Get events by category"""
        return self.query_events(limit=limit, category=category)
    
    def get_events_in_range(
        self,
        since: int,
        until: int,
        limit: int = 500
    ) -> List[TimelineEvent]:
        """Get events in a time range (chronological order for replay)"""
        if not self._connected:
            events = [e for e in self._recent_events if since <= e.timestamp <= until]
            return events[:limit]
        
        try:
            cursor = self._events_collection.find(
                {"timestamp": {"$gte": since, "$lte": until}},
                {"_id": 0}
            ).sort("timestamp", ASCENDING).limit(limit)
            
            return [TimelineEvent.from_dict(doc) for doc in cursor]
            
        except Exception as e:
            print(f"[Timeline] Range query error: {e}")
            return []
    
    def get_events_before(
        self,
        event_id: str,
        count: int = 20
    ) -> List[TimelineEvent]:
        """Get events before a specific event (for analysis)"""
        # Find the event
        if not self._connected:
            return []
        
        try:
            event = self._events_collection.find_one({"event_id": event_id}, {"_id": 0})
            if not event:
                return []
            
            cursor = self._events_collection.find(
                {"timestamp": {"$lt": event["timestamp"]}},
                {"_id": 0}
            ).sort("timestamp", DESCENDING).limit(count)
            
            return [TimelineEvent.from_dict(doc) for doc in cursor]
            
        except Exception as e:
            print(f"[Timeline] Before query error: {e}")
            return []
    
    # ============================================
    # Snapshots
    # ============================================
    
    def create_snapshot(
        self,
        risk_state: str = "NORMAL",
        system_state: str = "ACTIVE",
        portfolio_exposure: float = 0.0,
        active_strategies: int = 0,
        core_strategies: int = 0,
        degraded_strategies: int = 0,
        research_cycles_today: int = 0,
        additional_summary: Dict[str, Any] = None
    ) -> SystemSnapshot:
        """Create a system snapshot"""
        now = int(time.time() * 1000)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Count events today
        day_start = int(datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        events_today = sum(1 for e in self._recent_events if e.timestamp >= day_start)
        
        snapshot = SystemSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:10]}",
            timestamp=now,
            date=today,
            risk_state=risk_state,
            system_state=system_state,
            portfolio_exposure=portfolio_exposure,
            active_strategies=active_strategies,
            core_strategies=core_strategies,
            degraded_strategies=degraded_strategies,
            research_cycles_today=research_cycles_today,
            events_today=events_today,
            summary=additional_summary or {}
        )
        
        # Persist
        if self._connected:
            self._snapshots_collection.insert_one(snapshot.to_dict())
        
        return snapshot
    
    def get_snapshots(self, limit: int = 30) -> List[SystemSnapshot]:
        """Get recent snapshots"""
        if not self._connected:
            return []
        
        try:
            cursor = self._snapshots_collection.find(
                {},
                {"_id": 0}
            ).sort("timestamp", DESCENDING).limit(limit)
            
            return [
                SystemSnapshot(
                    snapshot_id=doc.get("snapshot_id", ""),
                    timestamp=doc.get("timestamp", 0),
                    date=doc.get("date", ""),
                    risk_state=doc.get("risk_state", ""),
                    system_state=doc.get("system_state", ""),
                    portfolio_exposure=doc.get("portfolio_exposure", 0),
                    active_strategies=doc.get("active_strategies", 0),
                    core_strategies=doc.get("core_strategies", 0),
                    degraded_strategies=doc.get("degraded_strategies", 0),
                    research_cycles_today=doc.get("research_cycles_today", 0),
                    events_today=doc.get("events_today", 0),
                    summary=doc.get("summary", {})
                )
                for doc in cursor
            ]
            
        except Exception as e:
            print(f"[Timeline] Snapshot query error: {e}")
            return []
    
    # ============================================
    # Analytics
    # ============================================
    
    def get_daily_summary(self, date: str = None) -> Dict[str, Any]:
        """Get summary for a day"""
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Calculate day boundaries
        day_start = int(datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        day_end = day_start + 86400000
        
        events = self.get_events_in_range(day_start, day_end, limit=10000)
        
        # Aggregate by category and type
        by_category = defaultdict(int)
        by_type = defaultdict(int)
        
        for event in events:
            by_category[event.category] += 1
            by_type[event.event_type] += 1
        
        return {
            "date": date,
            "total_events": len(events),
            "events_by_category": dict(by_category),
            "events_by_type": dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:20])
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get timeline statistics"""
        return {
            "total_events": self._total_events,
            "events_by_category": dict(self._events_by_category),
            "events_by_type": dict(sorted(self._events_by_type.items(), key=lambda x: x[1], reverse=True)[:20]),
            "cached_events": len(self._recent_events),
            "connected": self._connected
        }
    
    def get_health(self) -> Dict[str, Any]:
        """Get health status"""
        return {
            "enabled": True,
            "version": "timeline_v1",
            "status": "ok",
            "connected": self._connected,
            "total_events": self._total_events,
            "cached_events": len(self._recent_events)
        }


# Singleton instance
system_timeline_engine = SystemTimelineEngine()
