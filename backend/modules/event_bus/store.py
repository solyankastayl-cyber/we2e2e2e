"""
Event Store
===========

Persistent storage for events in MongoDB.
Enables audit trail, replay, and debugging.
Supports idempotency via unique event ID index.
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
import os
import threading

try:
    from pymongo import MongoClient, DESCENDING
    from pymongo.collection import Collection
    from pymongo.errors import DuplicateKeyError
    MONGO_OK = True
except ImportError:
    MONGO_OK = False

from .types import SystemEvent, EventStats


class EventStore:
    """
    MongoDB-backed event store.
    All events are persisted for audit and replay.
    Idempotency: duplicate event IDs are rejected silently.
    """
    
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.collection: Optional[Collection] = None
        self.stats = EventStats()
        self._connected = False
        self._idempotency_cache: Set[str] = set()
        self._cache_max = 10000
        self._lock = threading.Lock()
    
    def connect(self) -> bool:
        """Connect to MongoDB"""
        if not MONGO_OK:
            print("[EventStore] pymongo not installed")
            return False
        
        try:
            mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "ta_engine")
            
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            
            db = self.client[db_name]
            self.collection = db["events"]
            
            # Create indexes (including unique ID for idempotency)
            self.collection.create_index([("id", 1)], unique=True)
            self.collection.create_index([("timestamp", DESCENDING)])
            self.collection.create_index([("type", 1)])
            self.collection.create_index([("category", 1)])
            self.collection.create_index([("source", 1)])
            self.collection.create_index([("correlation_id", 1)])
            self.collection.create_index([("idempotency_key", 1)], unique=True, sparse=True)
            
            self._connected = True
            print(f"[EventStore] Connected to MongoDB: {db_name}.events")
            return True
            
        except Exception as e:
            print(f"[EventStore] Connection error: {e}")
            return False
    
    def is_connected(self) -> bool:
        return self._connected
    
    def is_duplicate(self, event_id: str, idempotency_key: str = None) -> bool:
        """Check if event is a duplicate (idempotency check)"""
        with self._lock:
            check_key = idempotency_key or event_id
            if check_key in self._idempotency_cache:
                return True
        
        if self._connected and idempotency_key:
            try:
                existing = self.collection.find_one(
                    {"idempotency_key": idempotency_key}, {"_id": 0, "id": 1}
                )
                if existing:
                    return True
            except Exception:
                pass
        
        return False
    
    def save(self, event: SystemEvent, idempotency_key: str = None) -> bool:
        """
        Save event to store with idempotency support.
        Duplicate event IDs or idempotency keys are rejected silently.
        """
        if not self._connected:
            if not self.connect():
                return False
        
        # Fast in-memory dedup check
        check_key = idempotency_key or event.id
        with self._lock:
            if check_key in self._idempotency_cache:
                self.stats.duplicates_rejected = getattr(self.stats, 'duplicates_rejected', 0) + 1
                return False
        
        try:
            doc = event.to_dict()
            if idempotency_key:
                doc["idempotency_key"] = idempotency_key
            
            self.collection.insert_one(doc)
            
            # Add to idempotency cache
            with self._lock:
                self._idempotency_cache.add(check_key)
                if len(self._idempotency_cache) > self._cache_max:
                    # Evict oldest (convert to list, remove first half)
                    items = list(self._idempotency_cache)
                    self._idempotency_cache = set(items[self._cache_max // 2:])
            
            # Update stats
            self.stats.total_published += 1
            self.stats.last_event_at = event.timestamp
            
            cat = event.category
            self.stats.events_by_category[cat] = self.stats.events_by_category.get(cat, 0) + 1
            
            evt_type = event.type
            self.stats.events_by_type[evt_type] = self.stats.events_by_type.get(evt_type, 0) + 1
            
            return True
            
        except DuplicateKeyError:
            self.stats.duplicates_rejected = getattr(self.stats, 'duplicates_rejected', 0) + 1
            return False
        except Exception as e:
            print(f"[EventStore] Save error: {e}")
            self.stats.errors += 1
            return False
    
    def get_by_id(self, event_id: str) -> Optional[SystemEvent]:
        """Get event by ID"""
        if not self._connected:
            if not self.connect():
                return None
        
        try:
            doc = self.collection.find_one({"id": event_id}, {"_id": 0})
            if doc:
                return SystemEvent.from_dict(doc)
            return None
        except Exception as e:
            print(f"[EventStore] Get error: {e}")
            return None
    
    def get_events(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        since: Optional[int] = None,
        until: Optional[int] = None,
        correlation_id: Optional[str] = None
    ) -> List[SystemEvent]:
        """Query events with filters"""
        if not self._connected:
            if not self.connect():
                return []
        
        try:
            query: Dict[str, Any] = {}
            
            if category:
                query["category"] = category
            if event_type:
                query["type"] = event_type
            if source:
                query["source"] = source
            if correlation_id:
                query["correlation_id"] = correlation_id
            if since:
                query["timestamp"] = {"$gte": since}
            if until:
                if "timestamp" in query:
                    query["timestamp"]["$lte"] = until
                else:
                    query["timestamp"] = {"$lte": until}
            
            cursor = self.collection.find(
                query,
                {"_id": 0}
            ).sort("timestamp", DESCENDING).limit(limit)
            
            return [SystemEvent.from_dict(doc) for doc in cursor]
            
        except Exception as e:
            print(f"[EventStore] Query error: {e}")
            return []
    
    def get_latest_by_type(self, event_type: str) -> Optional[SystemEvent]:
        """Get most recent event of a type"""
        events = self.get_events(limit=1, event_type=event_type)
        return events[0] if events else None
    
    def get_events_for_replay(
        self,
        since: int,
        until: Optional[int] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 1000
    ) -> List[SystemEvent]:
        """Get events for replay in chronological order"""
        if not self._connected:
            if not self.connect():
                return []
        
        try:
            query: Dict[str, Any] = {"timestamp": {"$gte": since}}
            
            if until:
                query["timestamp"]["$lte"] = until
            if event_types:
                query["type"] = {"$in": event_types}
            
            cursor = self.collection.find(
                query,
                {"_id": 0}
            ).sort("timestamp", 1).limit(limit)  # Ascending for replay
            
            return [SystemEvent.from_dict(doc) for doc in cursor]
            
        except Exception as e:
            print(f"[EventStore] Replay query error: {e}")
            return []
    
    def count_events(
        self,
        category: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[int] = None
    ) -> int:
        """Count events matching criteria"""
        if not self._connected:
            if not self.connect():
                return 0
        
        try:
            query: Dict[str, Any] = {}
            if category:
                query["category"] = category
            if event_type:
                query["type"] = event_type
            if since:
                query["timestamp"] = {"$gte": since}
            
            return self.collection.count_documents(query)
            
        except Exception as e:
            print(f"[EventStore] Count error: {e}")
            return 0
    
    def get_stats(self) -> EventStats:
        """Get current statistics"""
        if not self._connected:
            self.connect()
        
        # Refresh counts from DB if connected
        if self._connected:
            try:
                self.stats.total_published = self.collection.count_documents({})
                
                # Get category breakdown
                pipeline = [
                    {"$group": {"_id": "$category", "count": {"$sum": 1}}}
                ]
                for doc in self.collection.aggregate(pipeline):
                    self.stats.events_by_category[doc["_id"]] = doc["count"]
                
                # Get type breakdown (top 20)
                pipeline = [
                    {"$group": {"_id": "$type", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 20}
                ]
                self.stats.events_by_type = {}
                for doc in self.collection.aggregate(pipeline):
                    self.stats.events_by_type[doc["_id"]] = doc["count"]
                
                # Get last event timestamp
                last = self.collection.find_one({}, {"_id": 0, "timestamp": 1}, sort=[("timestamp", -1)])
                if last:
                    self.stats.last_event_at = last.get("timestamp")
                    
            except Exception as e:
                print(f"[EventStore] Stats error: {e}")
        
        return self.stats
    
    def clear_old_events(self, before_timestamp: int) -> int:
        """Delete events older than timestamp"""
        if not self._connected:
            if not self.connect():
                return 0
        
        try:
            result = self.collection.delete_many({"timestamp": {"$lt": before_timestamp}})
            return result.deleted_count
        except Exception as e:
            print(f"[EventStore] Clear error: {e}")
            return 0


# Singleton instance
_store_instance: Optional[EventStore] = None


def get_event_store() -> EventStore:
    """Get singleton event store instance"""
    global _store_instance
    if _store_instance is None:
        _store_instance = EventStore()
        _store_instance.connect()
    return _store_instance
