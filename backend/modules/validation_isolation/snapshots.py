"""
Phase 8.1: Snapshot Manager
Handles creation, storage, and retrieval of validation snapshots.
"""
import time
import hashlib
import json
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from .types import (
    ValidationSnapshot,
    SnapshotType,
    ISOLATION_CONFIG
)


class SnapshotManager:
    """
    Manages snapshots for validation isolation.
    
    Responsibilities:
    - Create snapshots of strategies, memory, metabrain, configs
    - Store and retrieve snapshots from MongoDB
    - Validate snapshot integrity
    - Cleanup old snapshots
    """
    
    def __init__(self, db=None, config: Optional[Dict] = None):
        self.db = db
        self.config = config or ISOLATION_CONFIG
        self._snapshot_cache: Dict[str, ValidationSnapshot] = {}
    
    def create_snapshot(
        self,
        snapshot_type: SnapshotType,
        data: Dict[str, Any],
        cutoff_time: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ValidationSnapshot:
        """
        Create a new snapshot of the given type.
        
        Args:
            snapshot_type: Type of snapshot (strategy, memory, etc.)
            data: Data to snapshot
            cutoff_time: Cutoff timestamp for this snapshot
            metadata: Additional metadata
            
        Returns:
            Created ValidationSnapshot
        """
        now = int(time.time() * 1000)
        
        # Generate snapshot ID
        snapshot_id = self._generate_snapshot_id(snapshot_type, cutoff_time)
        
        # Calculate checksum for data integrity
        checksum = self._calculate_checksum(data)
        
        snapshot = ValidationSnapshot(
            snapshot_id=snapshot_id,
            snapshot_type=snapshot_type,
            cutoff_time=cutoff_time,
            created_at=now,
            data=data,
            checksum=checksum,
            metadata=metadata or {}
        )
        
        # Store in MongoDB if available
        if self.db:
            self._store_snapshot(snapshot)
        
        # Cache locally
        self._snapshot_cache[snapshot_id] = snapshot
        
        return snapshot
    
    def get_snapshot(
        self,
        snapshot_id: str
    ) -> Optional[ValidationSnapshot]:
        """
        Retrieve a snapshot by ID.
        
        Args:
            snapshot_id: The snapshot ID
            
        Returns:
            ValidationSnapshot or None if not found
        """
        # Check cache first
        if snapshot_id in self._snapshot_cache:
            return self._snapshot_cache[snapshot_id]
        
        # Try loading from MongoDB
        if self.db:
            snapshot = self._load_snapshot(snapshot_id)
            if snapshot:
                self._snapshot_cache[snapshot_id] = snapshot
                return snapshot
        
        return None
    
    def get_latest_snapshot(
        self,
        snapshot_type: SnapshotType,
        before_time: Optional[int] = None
    ) -> Optional[ValidationSnapshot]:
        """
        Get the latest snapshot of a given type, optionally before a certain time.
        
        Args:
            snapshot_type: Type of snapshot
            before_time: Optional cutoff time constraint
            
        Returns:
            Latest ValidationSnapshot or None
        """
        if not self.db:
            # Return from cache
            matching = [
                s for s in self._snapshot_cache.values()
                if s.snapshot_type == snapshot_type
                and (before_time is None or s.cutoff_time <= before_time)
            ]
            if matching:
                return max(matching, key=lambda s: s.cutoff_time)
            return None
        
        collection_name = self._get_collection_name(snapshot_type)
        query = {"snapshot_type": snapshot_type.value}
        
        if before_time:
            query["cutoff_time"] = {"$lte": before_time}
        
        doc = self.db[collection_name].find_one(
            query,
            sort=[("cutoff_time", -1)]
        )
        
        if doc:
            return self._doc_to_snapshot(doc)
        
        return None
    
    def verify_integrity(self, snapshot: ValidationSnapshot) -> bool:
        """
        Verify the integrity of a snapshot by recalculating checksum.
        
        Args:
            snapshot: The snapshot to verify
            
        Returns:
            True if integrity check passes
        """
        expected_checksum = self._calculate_checksum(snapshot.data)
        return snapshot.checksum == expected_checksum
    
    def list_snapshots(
        self,
        snapshot_type: Optional[SnapshotType] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List available snapshots.
        
        Args:
            snapshot_type: Filter by type (optional)
            limit: Maximum number to return
            
        Returns:
            List of snapshot summaries
        """
        if not self.db:
            # Return from cache
            snapshots = list(self._snapshot_cache.values())
            if snapshot_type:
                snapshots = [s for s in snapshots if s.snapshot_type == snapshot_type]
            snapshots = sorted(snapshots, key=lambda s: s.created_at, reverse=True)[:limit]
            return [
                {
                    "snapshotId": s.snapshot_id,
                    "type": s.snapshot_type.value,
                    "cutoffTime": s.cutoff_time,
                    "createdAt": s.created_at
                }
                for s in snapshots
            ]
        
        # Query all snapshot collections
        results = []
        collections = self.config.get("collections", {})
        
        for coll_name in collections.values():
            if coll_name == "ta_validation_context":
                continue
                
            query = {}
            if snapshot_type:
                query["snapshot_type"] = snapshot_type.value
            
            try:
                docs = self.db[coll_name].find(query).sort("created_at", -1).limit(limit)
                for doc in docs:
                    results.append({
                        "snapshotId": doc.get("snapshot_id"),
                        "type": doc.get("snapshot_type"),
                        "cutoffTime": doc.get("cutoff_time"),
                        "createdAt": doc.get("created_at")
                    })
            except Exception:
                pass
        
        # Sort by created_at and limit
        results = sorted(results, key=lambda x: x.get("createdAt", 0), reverse=True)[:limit]
        return results
    
    def cleanup_old_snapshots(
        self,
        snapshot_type: SnapshotType,
        keep_count: Optional[int] = None
    ) -> int:
        """
        Remove old snapshots beyond retention limit.
        
        Args:
            snapshot_type: Type of snapshots to clean
            keep_count: Number to keep (uses config default if not specified)
            
        Returns:
            Number of snapshots removed
        """
        keep_count = keep_count or self.config.get("max_snapshots_per_type", 100)
        
        if not self.db:
            return 0
        
        collection_name = self._get_collection_name(snapshot_type)
        
        # Get total count
        total = self.db[collection_name].count_documents(
            {"snapshot_type": snapshot_type.value}
        )
        
        if total <= keep_count:
            return 0
        
        # Find IDs to delete (oldest ones)
        to_delete = total - keep_count
        old_docs = self.db[collection_name].find(
            {"snapshot_type": snapshot_type.value},
            {"_id": 1}
        ).sort("created_at", 1).limit(to_delete)
        
        ids_to_delete = [doc["_id"] for doc in old_docs]
        
        if ids_to_delete:
            result = self.db[collection_name].delete_many(
                {"_id": {"$in": ids_to_delete}}
            )
            return result.deleted_count
        
        return 0
    
    # ==================
    # Private methods
    # ==================
    
    def _generate_snapshot_id(
        self,
        snapshot_type: SnapshotType,
        cutoff_time: int
    ) -> str:
        """Generate unique snapshot ID"""
        type_prefix = {
            SnapshotType.STRATEGY: "strat_snap",
            SnapshotType.MEMORY: "mem_snap",
            SnapshotType.METABRAIN: "meta_snap",
            SnapshotType.CONFIG: "conf_snap",
            SnapshotType.THRESHOLD: "thresh_snap",
            SnapshotType.DISCOVERY: "disc_snap"
        }.get(snapshot_type, "snap")
        
        return f"{type_prefix}_{cutoff_time}_{int(time.time() * 1000) % 10000}"
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate MD5 checksum of data"""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()
    
    def _get_collection_name(self, snapshot_type: SnapshotType) -> str:
        """Get MongoDB collection name for snapshot type"""
        type_to_collection = {
            SnapshotType.STRATEGY: "strategy_snapshots",
            SnapshotType.MEMORY: "memory_snapshots",
            SnapshotType.METABRAIN: "metabrain_snapshots",
            SnapshotType.CONFIG: "config_snapshots",
            SnapshotType.THRESHOLD: "threshold_snapshots",
            SnapshotType.DISCOVERY: "discovery_snapshots"
        }
        key = type_to_collection.get(snapshot_type, "strategy_snapshots")
        return self.config.get("collections", {}).get(key, f"ta_{key}")
    
    def _store_snapshot(self, snapshot: ValidationSnapshot):
        """Store snapshot in MongoDB"""
        collection_name = self._get_collection_name(snapshot.snapshot_type)
        doc = {
            "snapshot_id": snapshot.snapshot_id,
            "snapshot_type": snapshot.snapshot_type.value,
            "cutoff_time": snapshot.cutoff_time,
            "created_at": snapshot.created_at,
            "data": snapshot.data,
            "checksum": snapshot.checksum,
            "metadata": snapshot.metadata
        }
        self.db[collection_name].insert_one(doc)
    
    def _load_snapshot(self, snapshot_id: str) -> Optional[ValidationSnapshot]:
        """Load snapshot from MongoDB"""
        collections = self.config.get("collections", {})
        
        for coll_key, coll_name in collections.items():
            if coll_key == "contexts":
                continue
            
            try:
                doc = self.db[coll_name].find_one({"snapshot_id": snapshot_id})
                if doc:
                    return self._doc_to_snapshot(doc)
            except Exception:
                pass
        
        return None
    
    def _doc_to_snapshot(self, doc: Dict) -> ValidationSnapshot:
        """Convert MongoDB document to ValidationSnapshot"""
        return ValidationSnapshot(
            snapshot_id=doc.get("snapshot_id", ""),
            snapshot_type=SnapshotType(doc.get("snapshot_type", "strategy")),
            cutoff_time=doc.get("cutoff_time", 0),
            created_at=doc.get("created_at", 0),
            data=doc.get("data", {}),
            checksum=doc.get("checksum", ""),
            metadata=doc.get("metadata", {})
        )
