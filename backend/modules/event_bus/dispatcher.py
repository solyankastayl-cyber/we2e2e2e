"""
Event Dispatcher
================

Core of the Event Bus.
Routes events from publishers to subscribers.
Includes retry logic and Dead Letter Queue for failed handlers.
"""

from typing import Dict, List, Callable, Optional, Set
from datetime import datetime, timezone
import threading

from .types import SystemEvent, EventSubscription, EventHandler, EventStats

# Import infrastructure hardening
try:
    from modules.infrastructure.retry_policy import retry_with_policy, RetryConfig, RetryStrategy
    from modules.infrastructure.dead_letter_queue import get_dlq
    HARDENING_AVAILABLE = True
except ImportError:
    HARDENING_AVAILABLE = False


# Default retry config for event handlers
HANDLER_RETRY_CONFIG = RetryConfig(
    max_retries=2,
    strategy=RetryStrategy.EXPONENTIAL,
    base_delay_sec=0.5,
    max_delay_sec=5.0,
    jitter=True,
) if HARDENING_AVAILABLE else None


class EventDispatcher:
    """
    Central event dispatcher with retry and DLQ support.
    
    Rules:
    1. Publisher does not know subscribers
    2. Subscriber does not call publisher
    3. Events are idempotent
    4. Event payload is minimal
    5. Failed handlers are retried, then sent to DLQ
    """
    
    def __init__(self):
        # Map: event_type -> list of (handler, handler_name) tuples
        self._handlers: Dict[str, List[tuple]] = {}
        
        # Subscriptions registry
        self._subscriptions: Dict[str, EventSubscription] = {}
        
        # Stats
        self._stats = EventStats()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Event history (last N events for debugging)
        self._recent_events: List[SystemEvent] = []
        self._max_recent = 100
        
        # Processed events for idempotency at dispatcher level
        self._processed_events: Set[str] = set()
        self._processed_max = 5000
    
    def subscribe(
        self,
        event_types: List[str],
        handler: EventHandler,
        handler_name: str
    ) -> str:
        """
        Subscribe handler to event types.
        Returns subscription ID.
        """
        with self._lock:
            subscription = EventSubscription.create(event_types, handler_name)
            
            for event_type in event_types:
                if event_type not in self._handlers:
                    self._handlers[event_type] = []
                self._handlers[event_type].append((handler, handler_name))
            
            self._subscriptions[subscription.id] = subscription
            print(f"[EventDispatcher] Subscribed {handler_name} to {event_types}")
            
            return subscription.id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove subscription"""
        with self._lock:
            if subscription_id not in self._subscriptions:
                return False
            
            sub = self._subscriptions[subscription_id]
            sub.active = False
            
            return True
    
    def dispatch(self, event: SystemEvent) -> int:
        """
        Dispatch event to all subscribers.
        Retries failed handlers and sends to DLQ on exhaustion.
        Returns number of handlers called successfully.
        """
        handlers_called = 0
        
        with self._lock:
            # Store in recent events
            self._recent_events.append(event)
            if len(self._recent_events) > self._max_recent:
                self._recent_events.pop(0)
            
            # Get handlers for this event type
            handlers = self._handlers.get(event.type, [])
            
            # Also get wildcard handlers (subscribe to "*")
            wildcard_handlers = self._handlers.get("*", [])
            
            all_handlers = handlers + wildcard_handlers
        
        # Call handlers outside lock to prevent deadlocks
        for handler_tuple in all_handlers:
            handler, handler_name = handler_tuple
            try:
                if HARDENING_AVAILABLE and HANDLER_RETRY_CONFIG:
                    result = retry_with_policy(
                        handler, HANDLER_RETRY_CONFIG, event
                    )
                    if result.success:
                        handlers_called += 1
                    else:
                        # All retries exhausted -> DLQ
                        self._send_to_dlq(event, handler_name, result.error, result.attempts)
                        self._stats.errors += 1
                else:
                    handler(event)
                    handlers_called += 1
            except Exception as e:
                print(f"[EventDispatcher] Handler '{handler_name}' error for {event.type}: {e}")
                if HARDENING_AVAILABLE:
                    self._send_to_dlq(event, handler_name, str(e), 1)
                self._stats.errors += 1
        
        # Update stats
        self._stats.total_dispatched += 1
        self._stats.last_event_at = event.timestamp
        
        return handlers_called
    
    def _send_to_dlq(self, event: SystemEvent, handler_name: str, error: str, attempts: int):
        """Send failed event to Dead Letter Queue"""
        try:
            dlq = get_dlq()
            dlq.add(
                event_id=event.id,
                event_type=event.type,
                source=event.source,
                payload=event.payload,
                handler_name=handler_name,
                error=error,
                attempts=attempts,
            )
        except Exception as e:
            print(f"[EventDispatcher] Failed to send to DLQ: {e}")
    
    def get_subscriptions(self) -> List[EventSubscription]:
        """Get all active subscriptions"""
        with self._lock:
            return [
                sub for sub in self._subscriptions.values()
                if sub.active
            ]
    
    def get_handlers_for_type(self, event_type: str) -> int:
        """Get number of handlers for an event type"""
        with self._lock:
            return len(self._handlers.get(event_type, []))
    
    def get_recent_events(self, limit: int = 20) -> List[SystemEvent]:
        """Get recent events from memory"""
        with self._lock:
            return list(reversed(self._recent_events[-limit:]))
    
    def get_stats(self) -> Dict:
        """Get dispatcher statistics"""
        with self._lock:
            dlq_stats = {}
            if HARDENING_AVAILABLE:
                try:
                    dlq_stats = get_dlq().get_stats()
                except Exception:
                    pass
            
            return {
                "total_dispatched": self._stats.total_dispatched,
                "errors": self._stats.errors,
                "last_event_at": self._stats.last_event_at,
                "subscriptions_count": len([s for s in self._subscriptions.values() if s.active]),
                "event_types_subscribed": list(self._handlers.keys()),
                "handlers_count": sum(len(h) for h in self._handlers.values()),
                "recent_events_cached": len(self._recent_events),
                "hardening_enabled": HARDENING_AVAILABLE,
                "dlq": dlq_stats,
            }
    
    def clear(self):
        """Clear all subscriptions and handlers"""
        with self._lock:
            self._handlers.clear()
            self._subscriptions.clear()
            self._recent_events.clear()
            print("[EventDispatcher] Cleared all subscriptions")


# Singleton instance
_dispatcher_instance: Optional[EventDispatcher] = None


def get_dispatcher() -> EventDispatcher:
    """Get singleton dispatcher instance"""
    global _dispatcher_instance
    if _dispatcher_instance is None:
        _dispatcher_instance = EventDispatcher()
    return _dispatcher_instance
