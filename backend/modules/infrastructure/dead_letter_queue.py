"""
Dead Letter Queue (DLQ)
=======================

Stores events that failed processing after all retries.
Enables manual replay and monitoring.
"""

import os
import time
import threading
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

try:
    from pymongo import MongoClient, DESCENDING
    MONGO_OK = True
except ImportError:
    MONGO_OK = False


@dataclass
class DeadLetter:
    """A failed event in the DLQ"""
    id: str
    event_id: str
    event_type: str
    source: str
    payload: Dict[str, Any]
    handler_name: str
    error: str
    attempts: int
    first_failed_at: int
    last_failed_at: int
    resolved: bool = False
    resolved_at: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "payload": self.payload,
            "handler_name": self.handler_name,
            "error": self.error,
            "attempts": self.attempts,
            "first_failed_at": self.first_failed_at,
            "last_failed_at": self.last_failed_at,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
        }


class DeadLetterQueue:
    """
    MongoDB-backed Dead Letter Queue.
    """
    
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.collection = None
        self._connected = False
        self._lock = threading.Lock()
        # In-memory fallback
        self._memory_queue: List[DeadLetter] = []
    
    def connect(self) -> bool:
        if not MONGO_OK:
            return False
        
        try:
            mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "ta_engine")
            
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.client.admin.command('ping')
            db = self.client[db_name]
            self.collection = db["dead_letter_queue"]
            
            self.collection.create_index([("last_failed_at", DESCENDING)])
            self.collection.create_index([("event_type", 1)])
            self.collection.create_index([("resolved", 1)])
            self.collection.create_index([("handler_name", 1)])
            
            self._connected = True
            print("[DLQ] Connected to MongoDB")
            return True
        except Exception as e:
            print(f"[DLQ] Connection error: {e}")
            return False
    
    def add(
        self,
        event_id: str,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        handler_name: str,
        error: str,
        attempts: int
    ) -> str:
        """Add a failed event to DLQ"""
        import uuid
        now = int(time.time() * 1000)
        
        dl = DeadLetter(
            id=f"dlq_{uuid.uuid4().hex[:12]}",
            event_id=event_id,
            event_type=event_type,
            source=source,
            payload=payload,
            handler_name=handler_name,
            error=error,
            attempts=attempts,
            first_failed_at=now,
            last_failed_at=now,
        )
        
        if self._connected:
            try:
                self.collection.insert_one(dl.to_dict())
            except Exception as e:
                print(f"[DLQ] Save error: {e}")
                with self._lock:
                    self._memory_queue.append(dl)
        else:
            if not self.connect():
                with self._lock:
                    self._memory_queue.append(dl)
            else:
                try:
                    self.collection.insert_one(dl.to_dict())
                except Exception:
                    with self._lock:
                        self._memory_queue.append(dl)
        
        print(f"[DLQ] Added: {event_type} from {source} (handler: {handler_name})")
        return dl.id
    
    def get_pending(self, limit: int = 50) -> List[Dict]:
        """Get unresolved dead letters"""
        if self._connected:
            try:
                cursor = self.collection.find(
                    {"resolved": False},
                    {"_id": 0}
                ).sort("last_failed_at", DESCENDING).limit(limit)
                return list(cursor)
            except Exception:
                pass
        
        with self._lock:
            return [dl.to_dict() for dl in self._memory_queue if not dl.resolved][:limit]
    
    def resolve(self, dlq_id: str) -> bool:
        """Mark a dead letter as resolved"""
        now = int(time.time() * 1000)
        if self._connected:
            try:
                result = self.collection.update_one(
                    {"id": dlq_id},
                    {"$set": {"resolved": True, "resolved_at": now}}
                )
                return result.modified_count > 0
            except Exception:
                pass
        
        with self._lock:
            for dl in self._memory_queue:
                if dl.id == dlq_id:
                    dl.resolved = True
                    dl.resolved_at = now
                    return True
        return False
    
    def count_pending(self) -> int:
        """Count unresolved dead letters"""
        if self._connected:
            try:
                return self.collection.count_documents({"resolved": False})
            except Exception:
                pass
        
        with self._lock:
            return len([dl for dl in self._memory_queue if not dl.resolved])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics"""
        pending = self.count_pending()
        total = 0
        if self._connected:
            try:
                total = self.collection.count_documents({})
            except Exception:
                pass
        else:
            with self._lock:
                total = len(self._memory_queue)
        
        return {
            "connected": self._connected,
            "total": total,
            "pending": pending,
            "resolved": total - pending,
        }


# Singleton
_dlq_instance: Optional[DeadLetterQueue] = None


def get_dlq() -> DeadLetterQueue:
    """Get singleton DLQ instance"""
    global _dlq_instance
    if _dlq_instance is None:
        _dlq_instance = DeadLetterQueue()
        _dlq_instance.connect()
    return _dlq_instance
