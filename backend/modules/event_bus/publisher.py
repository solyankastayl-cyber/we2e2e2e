"""
Event Publisher
===============

Interface for modules to publish events.
Publisher knows nothing about subscribers.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .types import SystemEvent, EventType
from .store import get_event_store
from .dispatcher import get_dispatcher


class EventPublisher:
    """
    Event publisher for a specific module.
    Each module creates its own publisher instance.
    """
    
    def __init__(self, source: str):
        """
        Initialize publisher for a module.
        
        Args:
            source: Module name (e.g., "research_loop", "alpha_tournament")
        """
        self.source = source
        self._store = get_event_store()
        self._dispatcher = get_dispatcher()
    
    def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Optional[SystemEvent]:
        """
        Publish an event.
        
        Args:
            event_type: Type of event (use EventType enum)
            payload: Event data (must be JSON-serializable)
            correlation_id: Optional ID to link related events
            idempotency_key: Optional key to prevent duplicate processing
            
        Returns:
            The created event, or None if duplicate
        """
        # Create event
        event = SystemEvent.create(
            event_type=event_type,
            source=self.source,
            payload=payload,
            correlation_id=correlation_id
        )
        
        # Check idempotency before persisting
        if idempotency_key and self._store.is_duplicate(event.id, idempotency_key):
            print(f"[EventPublisher:{self.source}] Duplicate rejected: {idempotency_key}")
            return None
        
        # Persist to store
        saved = self._store.save(event, idempotency_key=idempotency_key)
        if not saved:
            return None
        
        # Dispatch to subscribers
        handlers_called = self._dispatcher.dispatch(event)
        
        if handlers_called > 0:
            print(f"[EventPublisher:{self.source}] {event_type} -> {handlers_called} handlers")
        
        return event
    
    # Convenience methods for common events
    
    def research_cycle_started(self, cycle_id: str, config: Dict[str, Any]) -> SystemEvent:
        """Publish research cycle started event"""
        return self.publish(
            EventType.RESEARCH_CYCLE_STARTED.value,
            {"cycle_id": cycle_id, "config": config}
        )
    
    def research_cycle_completed(
        self,
        cycle_id: str,
        features_generated: int,
        alphas_generated: int,
        alphas_promoted: int
    ) -> SystemEvent:
        """Publish research cycle completed event"""
        return self.publish(
            EventType.RESEARCH_CYCLE_COMPLETED.value,
            {
                "cycle_id": cycle_id,
                "features_generated": features_generated,
                "alphas_generated": alphas_generated,
                "alphas_promoted": alphas_promoted
            }
        )
    
    def alpha_promoted(
        self,
        alpha_id: str,
        score: float,
        family: str,
        reason: str = ""
    ) -> SystemEvent:
        """Publish alpha promoted event"""
        return self.publish(
            EventType.ALPHA_PROMOTED.value,
            {
                "alpha_id": alpha_id,
                "score": score,
                "family": family,
                "reason": reason
            }
        )
    
    def alpha_demoted(
        self,
        alpha_id: str,
        reason: str,
        previous_status: str
    ) -> SystemEvent:
        """Publish alpha demoted event"""
        return self.publish(
            EventType.ALPHA_DEMOTED.value,
            {
                "alpha_id": alpha_id,
                "reason": reason,
                "previous_status": previous_status
            }
        )
    
    def risk_state_changed(
        self,
        previous_state: str,
        new_state: str,
        trigger: str,
        metrics: Dict[str, Any]
    ) -> SystemEvent:
        """Publish risk state change event"""
        return self.publish(
            EventType.RISK_STATE_CHANGED.value,
            {
                "previous_state": previous_state,
                "new_state": new_state,
                "trigger": trigger,
                "metrics": metrics
            }
        )
    
    def portfolio_rebalanced(
        self,
        changes: Dict[str, float],
        reason: str,
        total_value: float
    ) -> SystemEvent:
        """Publish portfolio rebalanced event"""
        return self.publish(
            EventType.PORTFOLIO_REBALANCED.value,
            {
                "changes": changes,
                "reason": reason,
                "total_value": total_value
            }
        )
    
    def policy_updated(
        self,
        policy_id: str,
        changes: Dict[str, Any],
        updated_by: str = "system"
    ) -> SystemEvent:
        """Publish policy updated event"""
        return self.publish(
            EventType.POLICY_UPDATED.value,
            {
                "policy_id": policy_id,
                "changes": changes,
                "updated_by": updated_by
            }
        )
    
    def experiment_started(
        self,
        experiment_id: str,
        name: str,
        config: Dict[str, Any]
    ) -> SystemEvent:
        """Publish experiment started event"""
        return self.publish(
            EventType.EXPERIMENT_STARTED.value,
            {
                "experiment_id": experiment_id,
                "name": name,
                "config": config
            }
        )
    
    def experiment_completed(
        self,
        experiment_id: str,
        results: Dict[str, Any],
        duration_ms: int
    ) -> SystemEvent:
        """Publish experiment completed event"""
        return self.publish(
            EventType.EXPERIMENT_COMPLETED.value,
            {
                "experiment_id": experiment_id,
                "results": results,
                "duration_ms": duration_ms
            }
        )


# Factory function
def create_publisher(source: str) -> EventPublisher:
    """Create a publisher for a module"""
    return EventPublisher(source)


# Convenience publishers for common modules
def get_research_publisher() -> EventPublisher:
    return EventPublisher("research_loop")


def get_risk_publisher() -> EventPublisher:
    return EventPublisher("global_risk_brain")


def get_portfolio_publisher() -> EventPublisher:
    return EventPublisher("portfolio_engine")


def get_governance_publisher() -> EventPublisher:
    return EventPublisher("governance")


def get_system_publisher() -> EventPublisher:
    return EventPublisher("system")
