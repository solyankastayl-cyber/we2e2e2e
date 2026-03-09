"""
Event Bus Module
================

Asynchronous event-driven communication between modules.

Architecture:
- Publisher: Modules publish events without knowing subscribers
- Subscriber: Modules subscribe to events without calling publishers
- Dispatcher: Routes events from publishers to subscribers
- Store: Persists all events for audit and replay

Usage:

Publishing events:
    from modules.event_bus import create_publisher
    
    publisher = create_publisher("my_module")
    publisher.publish("my_event", {"key": "value"})

Subscribing to events:
    from modules.event_bus import create_subscriber
    
    def my_handler(event):
        print(f"Got event: {event.type}")
    
    subscriber = create_subscriber("my_module")
    subscriber.subscribe(["event_type_1", "event_type_2"], my_handler)

Event Types:
    See types.py for all standard event types.
    
API Endpoints:
    See routes.py for REST API.
"""

from .types import (
    SystemEvent,
    EventCategory,
    EventType,
    EventSubscription,
    EventStats,
    EventHandler,
    EVENT_CATEGORY_MAP
)

from .store import EventStore, get_event_store

from .dispatcher import EventDispatcher, get_dispatcher

from .publisher import (
    EventPublisher,
    create_publisher,
    get_research_publisher,
    get_risk_publisher,
    get_portfolio_publisher,
    get_governance_publisher,
    get_system_publisher
)

from .subscriber import (
    EventSubscriber,
    create_subscriber,
    get_admin_subscriber,
    get_memory_subscriber,
    get_stress_lab_subscriber,
    get_autopsy_subscriber
)

from .routes import router


__all__ = [
    # Types
    "SystemEvent",
    "EventCategory", 
    "EventType",
    "EventSubscription",
    "EventStats",
    "EventHandler",
    "EVENT_CATEGORY_MAP",
    
    # Store
    "EventStore",
    "get_event_store",
    
    # Dispatcher
    "EventDispatcher",
    "get_dispatcher",
    
    # Publisher
    "EventPublisher",
    "create_publisher",
    "get_research_publisher",
    "get_risk_publisher",
    "get_portfolio_publisher",
    "get_governance_publisher",
    "get_system_publisher",
    
    # Subscriber
    "EventSubscriber",
    "create_subscriber",
    "get_admin_subscriber",
    "get_memory_subscriber",
    "get_stress_lab_subscriber",
    "get_autopsy_subscriber",
    
    # Router
    "router"
]


# Initialize on import
print("[EventBus] Module loaded")
