"""
System State Machine Engine
===========================

Controls global system state.
Listens to events and triggers state transitions.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import threading
import os

try:
    from pymongo import MongoClient, DESCENDING
    from pymongo.collection import Collection
    MONGO_OK = True
except ImportError:
    MONGO_OK = False

from .types import (
    SystemState,
    StateRecord,
    StateTransition,
    ALLOWED_TRANSITIONS,
    STATE_CONFIG,
    is_transition_allowed,
    get_state_config
)


class SystemStateMachine:
    """
    Global state machine for the system.
    
    The system can only be in ONE state at a time.
    State determines what modules can run.
    """
    
    def __init__(self):
        self._current_state = SystemState.INITIALIZING
        self._state_since: int = int(datetime.now(timezone.utc).timestamp() * 1000)
        self._transitions: List[StateTransition] = []
        self._lock = threading.RLock()
        
        # MongoDB
        self._client: Optional[MongoClient] = None
        self._collection: Optional[Collection] = None
        self._history_collection: Optional[Collection] = None
        self._connected = False
        
        # Event bus integration
        self._event_publisher = None
        self._event_subscriber = None
    
    def connect(self) -> bool:
        """Connect to MongoDB for state persistence"""
        if not MONGO_OK:
            print("[SSM] pymongo not installed")
            return False
        
        try:
            mongo_uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
            db_name = os.environ.get("DB_NAME", "ta_engine")
            
            self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self._client.admin.command('ping')
            
            db = self._client[db_name]
            self._collection = db["system_state"]
            self._history_collection = db["state_history"]
            
            # Create indexes
            self._history_collection.create_index([("timestamp", DESCENDING)])
            
            # Load current state from DB if exists
            saved = self._collection.find_one({"_id": "current"})
            if saved:
                try:
                    self._current_state = SystemState(saved.get("state", "INITIALIZING"))
                    self._state_since = saved.get("since", self._state_since)
                except ValueError:
                    self._current_state = SystemState.INITIALIZING
            
            self._connected = True
            print(f"[SSM] Connected to MongoDB, current state: {self._current_state.value}")
            return True
            
        except Exception as e:
            print(f"[SSM] Connection error: {e}")
            return False
    
    def init_event_bus(self):
        """Initialize Event Bus integration"""
        try:
            from modules.event_bus import create_publisher, create_subscriber, EventType
            
            self._event_publisher = create_publisher("system_state_machine")
            self._event_subscriber = create_subscriber("system_state_machine")
            
            # Subscribe to risk events
            def handle_risk_event(event):
                self._on_risk_event(event)
            
            self._event_subscriber.on_risk_events(handle_risk_event)
            
            print("[SSM] Event Bus integration initialized")
            
        except ImportError as e:
            print(f"[SSM] Event Bus not available: {e}")
    
    def _on_risk_event(self, event):
        """Handle risk events for automatic state transitions"""
        event_type = event.type
        payload = event.payload
        
        # Volatility spike -> STRESS
        if event_type == "volatility_spike_detected":
            if self._current_state == SystemState.ACTIVE:
                self.transition(
                    SystemState.STRESS,
                    reason="Volatility spike detected",
                    triggered_by="risk_event"
                )
        
        # Drawdown threshold -> CRISIS
        elif event_type == "drawdown_threshold_hit":
            drawdown = payload.get("drawdown", 0)
            if drawdown > 0.15 and self._current_state in [SystemState.ACTIVE, SystemState.STRESS]:
                self.transition(
                    SystemState.CRISIS,
                    reason=f"Drawdown {drawdown*100:.1f}% exceeded threshold",
                    triggered_by="risk_event"
                )
        
        # Volatility normalized -> back to ACTIVE
        elif event_type == "risk_state_changed":
            new_risk_state = payload.get("new_state", "")
            if new_risk_state == "NORMAL" and self._current_state in [SystemState.STRESS, SystemState.CRISIS]:
                self.transition(
                    SystemState.ACTIVE,
                    reason="Risk normalized",
                    triggered_by="risk_event"
                )
    
    @property
    def current_state(self) -> SystemState:
        """Get current state"""
        return self._current_state
    
    @property
    def state_since(self) -> int:
        """Get timestamp when current state started"""
        return self._state_since
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get full state information"""
        config = get_state_config(self._current_state)
        
        return {
            "state": self._current_state.value,
            "since": self._state_since,
            "config": config,
            "allowed_transitions": [
                s.value for s in ALLOWED_TRANSITIONS.get(self._current_state, set())
            ]
        }
    
    def transition(
        self,
        new_state: SystemState,
        reason: str,
        triggered_by: str = "system"
    ) -> StateTransition:
        """
        Transition to a new state.
        
        Args:
            new_state: Target state
            reason: Why this transition is happening
            triggered_by: Module/user that triggered
            
        Returns:
            StateTransition record
        """
        with self._lock:
            old_state = self._current_state
            
            # Create transition record
            transition = StateTransition.create(
                from_state=old_state.value,
                to_state=new_state.value,
                reason=reason,
                triggered_by=triggered_by
            )
            
            # Check if transition is allowed
            if not is_transition_allowed(old_state, new_state):
                transition.success = False
                transition.error = f"Transition from {old_state.value} to {new_state.value} not allowed"
                print(f"[SSM] {transition.error}")
                return transition
            
            # Perform transition
            self._current_state = new_state
            self._state_since = transition.timestamp
            self._transitions.append(transition)
            
            # Persist to DB
            self._save_state()
            self._save_transition(transition)
            
            # Publish event
            if self._event_publisher:
                self._event_publisher.publish(
                    "system_state_changed",
                    {
                        "from_state": old_state.value,
                        "to_state": new_state.value,
                        "reason": reason,
                        "triggered_by": triggered_by
                    }
                )
            
            print(f"[SSM] State transition: {old_state.value} -> {new_state.value} ({reason})")
            
            return transition
    
    def _save_state(self):
        """Save current state to DB"""
        if not self._connected:
            return
        
        try:
            self._collection.update_one(
                {"_id": "current"},
                {"$set": {
                    "_id": "current",
                    "state": self._current_state.value,
                    "since": self._state_since,
                    "updated_at": int(datetime.now(timezone.utc).timestamp() * 1000)
                }},
                upsert=True
            )
        except Exception as e:
            print(f"[SSM] Save state error: {e}")
    
    def _save_transition(self, transition: StateTransition):
        """Save transition to history"""
        if not self._connected:
            return
        
        try:
            self._history_collection.insert_one(transition.to_dict())
        except Exception as e:
            print(f"[SSM] Save transition error: {e}")
    
    def get_history(self, limit: int = 50) -> List[StateTransition]:
        """Get transition history"""
        if not self._connected:
            return list(reversed(self._transitions[-limit:]))
        
        try:
            cursor = self._history_collection.find(
                {},
                {"_id": 0}
            ).sort("timestamp", DESCENDING).limit(limit)
            
            return [
                StateTransition(
                    id=doc.get("id", ""),
                    from_state=doc.get("from_state", ""),
                    to_state=doc.get("to_state", ""),
                    timestamp=doc.get("timestamp", 0),
                    reason=doc.get("reason", ""),
                    triggered_by=doc.get("triggered_by", ""),
                    success=doc.get("success", True),
                    error=doc.get("error")
                )
                for doc in cursor
            ]
            
        except Exception as e:
            print(f"[SSM] Get history error: {e}")
            return []
    
    def can_transition_to(self, target_state: SystemState) -> bool:
        """Check if can transition to target state"""
        return is_transition_allowed(self._current_state, target_state)
    
    def is_action_allowed(self, action: str) -> bool:
        """Check if an action is allowed in current state"""
        config = get_state_config(self._current_state)
        allowed = config.get("allowed_actions", [])
        return "all" in allowed or action in allowed
    
    def force_state(
        self,
        new_state: SystemState,
        reason: str,
        triggered_by: str = "admin"
    ) -> StateTransition:
        """Force transition (bypasses allowed check)"""
        with self._lock:
            old_state = self._current_state
            
            transition = StateTransition.create(
                from_state=old_state.value,
                to_state=new_state.value,
                reason=f"FORCED: {reason}",
                triggered_by=triggered_by
            )
            
            self._current_state = new_state
            self._state_since = transition.timestamp
            self._transitions.append(transition)
            
            self._save_state()
            self._save_transition(transition)
            
            if self._event_publisher:
                self._event_publisher.publish(
                    "system_state_forced",
                    {
                        "from_state": old_state.value,
                        "to_state": new_state.value,
                        "reason": reason,
                        "triggered_by": triggered_by
                    }
                )
            
            print(f"[SSM] FORCED state: {old_state.value} -> {new_state.value}")
            
            return transition


# Singleton instance
_ssm_instance: Optional[SystemStateMachine] = None


def get_state_machine() -> SystemStateMachine:
    """Get singleton state machine instance"""
    global _ssm_instance
    if _ssm_instance is None:
        _ssm_instance = SystemStateMachine()
        _ssm_instance.connect()
        _ssm_instance.init_event_bus()
    return _ssm_instance
