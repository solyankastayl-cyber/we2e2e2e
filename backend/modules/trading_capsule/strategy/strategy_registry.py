"""
Strategy Registry (T6)
======================

Registry for strategy plugins.

Handles:
- Registration of strategies
- Unregistration of strategies
- Strategy lookup
- Strategy metadata storage
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import threading

from .strategy_types import StrategyPlugin, StrategyStatus


class StrategyRegistry:
    """
    Registry for strategy plugins.
    
    Stores references to all registered strategies.
    Thread-safe singleton.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Strategy storage
        self._strategies: Dict[str, StrategyPlugin] = {}
        
        # Metadata storage
        self._metadata: Dict[str, Dict[str, Any]] = {}
        
        # Registration order
        self._registration_order: List[str] = []
        
        self._initialized = True
        print("[StrategyRegistry] Initialized")
    
    # ===========================================
    # Registration
    # ===========================================
    
    def register(
        self,
        strategy: StrategyPlugin,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Register a strategy plugin.
        
        Args:
            strategy: Strategy plugin instance
            metadata: Optional metadata
            
        Returns:
            True if registered, False if already exists
        """
        strategy_id = strategy.strategy_id
        
        if strategy_id in self._strategies:
            print(f"[StrategyRegistry] Strategy already exists: {strategy_id}")
            return False
        
        # Validate interface
        if not isinstance(strategy, StrategyPlugin):
            print(f"[StrategyRegistry] Invalid strategy interface: {strategy_id}")
            return False
        
        # Store strategy
        self._strategies[strategy_id] = strategy
        self._registration_order.append(strategy_id)
        
        # Store metadata
        self._metadata[strategy_id] = {
            "strategy_id": strategy_id,
            "name": strategy.name,
            "description": strategy.description,
            "version": strategy.version,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            **(metadata or {})
        }
        
        print(f"[StrategyRegistry] Registered: {strategy_id} ({strategy.name})")
        return True
    
    def unregister(self, strategy_id: str) -> bool:
        """
        Unregister a strategy.
        
        Args:
            strategy_id: Strategy ID to remove
            
        Returns:
            True if removed, False if not found
        """
        if strategy_id not in self._strategies:
            return False
        
        del self._strategies[strategy_id]
        del self._metadata[strategy_id]
        self._registration_order.remove(strategy_id)
        
        print(f"[StrategyRegistry] Unregistered: {strategy_id}")
        return True
    
    # ===========================================
    # Lookup
    # ===========================================
    
    def get(self, strategy_id: str) -> Optional[StrategyPlugin]:
        """Get strategy by ID"""
        return self._strategies.get(strategy_id)
    
    def get_all(self) -> List[StrategyPlugin]:
        """Get all registered strategies in order"""
        return [self._strategies[sid] for sid in self._registration_order]
    
    def get_ids(self) -> List[str]:
        """Get all strategy IDs"""
        return list(self._registration_order)
    
    def exists(self, strategy_id: str) -> bool:
        """Check if strategy exists"""
        return strategy_id in self._strategies
    
    def count(self) -> int:
        """Get number of registered strategies"""
        return len(self._strategies)
    
    # ===========================================
    # Metadata
    # ===========================================
    
    def get_metadata(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Get strategy metadata"""
        return self._metadata.get(strategy_id)
    
    def get_all_metadata(self) -> List[Dict[str, Any]]:
        """Get all strategy metadata"""
        return [self._metadata[sid] for sid in self._registration_order]
    
    def update_metadata(
        self,
        strategy_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update strategy metadata"""
        if strategy_id not in self._metadata:
            return False
        
        self._metadata[strategy_id].update(updates)
        self._metadata[strategy_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        return True
    
    # ===========================================
    # Summary
    # ===========================================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get registry summary"""
        return {
            "total_strategies": len(self._strategies),
            "strategy_ids": list(self._registration_order),
            "strategies": [
                {
                    "id": sid,
                    "name": self._metadata[sid].get("name", ""),
                    "version": self._metadata[sid].get("version", ""),
                    "registered_at": self._metadata[sid].get("registered_at")
                }
                for sid in self._registration_order
            ]
        }
    
    def clear(self) -> int:
        """Clear all strategies (for testing)"""
        count = len(self._strategies)
        self._strategies.clear()
        self._metadata.clear()
        self._registration_order.clear()
        print(f"[StrategyRegistry] Cleared {count} strategies")
        return count


# Global singleton
strategy_registry = StrategyRegistry()
