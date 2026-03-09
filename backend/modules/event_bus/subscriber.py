"""
Event Subscriber
================

Interface for modules to subscribe to events.
Subscriber does not call publishers directly.
"""

from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timezone

from .types import SystemEvent, EventType, EventHandler
from .dispatcher import get_dispatcher


class EventSubscriber:
    """
    Event subscriber for a specific module.
    Each module creates its own subscriber instance.
    """
    
    def __init__(self, handler_name: str):
        """
        Initialize subscriber for a module.
        
        Args:
            handler_name: Module name (e.g., "admin_control_center", "research_memory")
        """
        self.handler_name = handler_name
        self._dispatcher = get_dispatcher()
        self._subscription_ids: List[str] = []
    
    def subscribe(
        self,
        event_types: List[str],
        handler: EventHandler
    ) -> str:
        """
        Subscribe to event types.
        
        Args:
            event_types: List of event types to subscribe to
            handler: Callback function(event: SystemEvent) -> None
            
        Returns:
            Subscription ID
        """
        sub_id = self._dispatcher.subscribe(
            event_types=event_types,
            handler=handler,
            handler_name=self.handler_name
        )
        self._subscription_ids.append(sub_id)
        return sub_id
    
    def subscribe_all(self, handler: EventHandler) -> str:
        """Subscribe to all events (wildcard)"""
        return self.subscribe(["*"], handler)
    
    def subscribe_category(
        self,
        category_events: List[str],
        handler: EventHandler
    ) -> str:
        """Subscribe to all events in a category"""
        return self.subscribe(category_events, handler)
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events"""
        if subscription_id in self._subscription_ids:
            self._subscription_ids.remove(subscription_id)
            return self._dispatcher.unsubscribe(subscription_id)
        return False
    
    def unsubscribe_all(self):
        """Unsubscribe from all subscriptions"""
        for sub_id in self._subscription_ids:
            self._dispatcher.unsubscribe(sub_id)
        self._subscription_ids.clear()
    
    def get_subscription_ids(self) -> List[str]:
        """Get all subscription IDs for this subscriber"""
        return list(self._subscription_ids)
    
    # Convenience methods for subscribing to common event groups
    
    def on_research_events(self, handler: EventHandler) -> str:
        """Subscribe to all research events"""
        return self.subscribe([
            EventType.RESEARCH_CYCLE_STARTED.value,
            EventType.RESEARCH_CYCLE_COMPLETED.value,
            EventType.FEATURE_GENERATED.value,
            EventType.FEATURE_REJECTED.value,
            EventType.ALPHA_GENERATED.value,
            EventType.ALPHA_PROMOTED.value,
            EventType.ALPHA_REJECTED.value,
            EventType.ALPHA_DEMOTED.value,
        ], handler)
    
    def on_risk_events(self, handler: EventHandler) -> str:
        """Subscribe to all risk events"""
        return self.subscribe([
            EventType.RISK_STATE_CHANGED.value,
            EventType.DRAWDOWN_THRESHOLD_HIT.value,
            EventType.EXPOSURE_REDUCED.value,
            EventType.VOLATILITY_SPIKE_DETECTED.value,
            EventType.CORRELATION_SPIKE_DETECTED.value,
        ], handler)
    
    def on_portfolio_events(self, handler: EventHandler) -> str:
        """Subscribe to all portfolio events"""
        return self.subscribe([
            EventType.PORTFOLIO_REBALANCED.value,
            EventType.STRATEGY_WEIGHT_CHANGED.value,
            EventType.FAMILY_BUDGET_ADJUSTED.value,
            EventType.SHADOW_PORTFOLIO_UPDATED.value,
        ], handler)
    
    def on_governance_events(self, handler: EventHandler) -> str:
        """Subscribe to all governance events"""
        return self.subscribe([
            EventType.POLICY_UPDATED.value,
            EventType.DATASET_REGISTERED.value,
            EventType.EXPERIMENT_STARTED.value,
            EventType.EXPERIMENT_COMPLETED.value,
            EventType.EXPERIMENT_FAILED.value,
        ], handler)
    
    def on_execution_events(self, handler: EventHandler) -> str:
        """Subscribe to all execution events"""
        return self.subscribe([
            EventType.TRADE_OPENED.value,
            EventType.TRADE_CLOSED.value,
            EventType.SLIPPAGE_DETECTED.value,
            EventType.GAP_EVENT_DETECTED.value,
            EventType.FILL_REJECTED.value,
        ], handler)


# Factory function
def create_subscriber(handler_name: str) -> EventSubscriber:
    """Create a subscriber for a module"""
    return EventSubscriber(handler_name)


# Pre-configured subscribers for common modules
def get_admin_subscriber() -> EventSubscriber:
    """Subscriber for Admin Control Center"""
    return EventSubscriber("admin_control_center")


def get_memory_subscriber() -> EventSubscriber:
    """Subscriber for Research Memory"""
    return EventSubscriber("research_memory")


def get_stress_lab_subscriber() -> EventSubscriber:
    """Subscriber for Stress Lab"""
    return EventSubscriber("stress_lab")


def get_autopsy_subscriber() -> EventSubscriber:
    """Subscriber for Autopsy Engine"""
    return EventSubscriber("autopsy_engine")
