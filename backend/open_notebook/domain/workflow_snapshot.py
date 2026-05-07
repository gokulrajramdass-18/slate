"""
Workflow Snapshot Domain Models

Provides context-aware snapshot storage with:
- Multi-tenant isolation (user_id)
- Query context tracking (context_hash)
- Tiered storage (inline/file/chunked)
- Fast comparison without loading full data
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List, ClassVar
from enum import Enum
import hashlib
import json
from uuid import uuid4

from pydantic import Field as PydanticField

from open_notebook.database.repository import repo_query, repo_create, repo_update, repo_delete
from open_notebook.domain.base import ObjectModel


class StorageType(str, Enum):
    """Storage backend types for snapshot data"""
    INLINE = "inline"      # < 10MB: Store in DB
    FILE = "file"          # 10-100MB: Local filesystem
    CHUNKED = "chunked"    # > 100MB: Split into chunks


@dataclass
class SnapshotContext:
    """
    Captures execution context for proper snapshot comparison.

    Ensures we only compare snapshots with identical:
    - User (user_id)
    - Query parameters (API filters, SQL WHERE clauses)
    - Input data (workflow inputs)

    This prevents comparing incompatible datasets like:
    - User A's US sales vs User B's EU sales
    - Yesterday's filter vs Today's filter
    """
    user_id: str
    query_params: Dict[str, Any] = field(default_factory=dict)
    input_data: Dict[str, Any] = field(default_factory=dict)
    source_config: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize context to dict"""
        return {
            "user_id": self.user_id,
            "query_params": self.query_params,
            "input_data": self.input_data,
            "source_config": self.source_config
        }

    def calculate_hash(self) -> str:
        """
        Calculate deterministic hash of context.
        Only snapshots with matching hash can be compared.

        Returns:
            SHA256 hex digest of sorted JSON
        """
        context_json = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(context_json.encode()).hexdigest()

    @classmethod
    def from_workflow_state(cls, state: Dict[str, Any]) -> "SnapshotContext":
        """
        Extract context from workflow execution state.

        Args:
            state: Workflow execution state dict

        Returns:
            SnapshotContext instance
        """
        # Get user from state
        user_id = state.get("user_id", "default-user")

        # Extract query params from source node output if available
        node_outputs = state.get("node_outputs", {})

        query_params = {}

        # Check if source node stored query params
        for node_id, output in node_outputs.items():
            if isinstance(output, dict) and "query_params" in output:
                query_params.update(output["query_params"])
                break

        # Get workflow input data
        input_data = state.get("input_data", {})

        return cls(
            user_id=user_id,
            query_params=query_params,
            input_data=input_data,
            source_config=None
        )


class WorkflowSnapshot(ObjectModel):
    """
    Represents a snapshot of workflow node output.

    Features:
    - User-scoped (multi-tenant isolation)
    - Context-aware (query params tracked)
    - Tiered storage (scales to TB)
    - Fast comparison (hash + stats)

    Attributes:
        workflow_id: Parent workflow ID
        node_id: Node that produced this snapshot
        execution_id: Execution that created this snapshot
        user_id: Owner of this snapshot
        snapshot_date: Date of snapshot
        snapshot_label: Optional label (yesterday, today, baseline)
        storage_type: Storage backend (inline/file/chunked)
        storage_path: Path to external storage
        inline_data: Compressed data for inline storage
        data_hash: SHA256 of full data
        row_count: Number of rows/records
        total_size_bytes: Total size in bytes
        column_count: Number of columns (for tabular data)
        query_context: JSON string of SnapshotContext
        context_hash: SHA256 of query_context
        stats_summary: JSON statistical summary
        sample_data: JSON sample rows
        expires_at: Expiration date for cleanup
    """
    _table_name: ClassVar[str] = "workflow_snapshots"

    workflow_id: str
    node_id: str
    execution_id: Optional[str] = None
    user_id: str
    snapshot_date: datetime  # Timestamp of snapshot (changed from date to support multiple snapshots per day)
    snapshot_label: Optional[str] = None
    storage_type: StorageType
    storage_path: Optional[str] = None
    inline_data: Optional[str] = None
    data_hash: str
    row_count: int
    total_size_bytes: int
    column_count: int = 0
    query_context: str  # JSON string
    context_hash: str
    stats_summary: Optional[str] = None  # JSON string
    sample_data: Optional[str] = None    # JSON string
    expires_at: Optional[datetime] = None

    @classmethod
    async def create_from_data(
        cls,
        workflow_id: str,
        node_id: str,
        execution_id: str,
        context: SnapshotContext,
        data: Any,
        snapshot_label: Optional[str] = None,
        retention_days: int = 30
    ) -> "WorkflowSnapshot":
        """
        Create snapshot from node output data.

        Automatically:
        - Chooses optimal storage strategy
        - Calculates hashes and statistics
        - Enforces retention policy

        Args:
            workflow_id: Parent workflow
            node_id: Source node
            execution_id: Current execution
            context: Snapshot context
            data: Node output data
            snapshot_label: Optional label
            retention_days: Days until expiration

        Returns:
            Saved WorkflowSnapshot instance
        """
        from open_notebook.agents.workflow_snapshots import SnapshotStorageManager

        # Initialize storage manager
        import os
        manager = SnapshotStorageManager({
            "snapshot_storage_path": os.getenv("SNAPSHOT_STORAGE_PATH", "./data/snapshots"),
            "inline_threshold": int(os.getenv("SNAPSHOT_INLINE_THRESHOLD", 10 * 1024 * 1024)),
            "file_threshold": int(os.getenv("SNAPSHOT_FILE_THRESHOLD", 100 * 1024 * 1024)),
            "chunk_size": int(os.getenv("SNAPSHOT_CHUNK_SIZE", 50 * 1024 * 1024))
        })

        # Store data and get metadata
        result = await manager.store_snapshot(
            workflow_id=workflow_id,
            node_id=node_id,
            snapshot_date=datetime.utcnow().isoformat(),  # Use full timestamp, not just date
            context=context,
            data=data,
            metadata={}
        )

        # Check for existing snapshot with same context and label
        # This allows multiple snapshots per day with different labels
        context_hash = context.calculate_hash()
        existing = await repo_query(
            """SELECT id FROM workflow_snapshots
               WHERE workflow_id = :wf_id
               AND node_id = :node_id
               AND user_id = :user_id
               AND context_hash = :ctx_hash
               AND snapshot_label = :snap_label""",
            {
                "wf_id": workflow_id,
                "node_id": node_id,
                "user_id": context.user_id,
                "ctx_hash": context_hash,
                "snap_label": snapshot_label
            }
        )

        snapshot_id = existing[0]["id"] if existing else str(uuid4())

        # Create snapshot record
        snapshot = cls(
            id=snapshot_id,
            workflow_id=workflow_id,
            node_id=node_id,
            execution_id=execution_id,
            user_id=context.user_id,
            snapshot_date=datetime.utcnow(),  # Use full timestamp
            snapshot_label=snapshot_label,
            storage_type=StorageType(result["storage_type"]),
            storage_path=result.get("storage_path"),
            inline_data=result.get("inline_data"),
            data_hash=result["data_hash"],
            row_count=result["row_count"],
            total_size_bytes=result["total_size_bytes"],
            column_count=result.get("column_count", 0),
            query_context=json.dumps(context.to_dict()),
            context_hash=context_hash,
            stats_summary=result.get("stats_summary"),
            sample_data=result.get("sample_data"),
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=retention_days)
        )

        await snapshot.save()
        return snapshot

    @classmethod
    async def find_comparable(
        cls,
        workflow_id: str,
        node_id: str,
        context: SnapshotContext,
        target_date: date
    ) -> Optional["WorkflowSnapshot"]:
        """
        Find snapshot that can be compared with current context.

        Only returns snapshots with matching:
        - workflow_id
        - node_id
        - user_id
        - context_hash (same query params)
        - target_date

        Args:
            workflow_id: Workflow ID
            node_id: Node ID
            context: Current context
            target_date: Target snapshot date

        Returns:
            Matching snapshot or None
        """
        context_hash = context.calculate_hash()

        rows = await repo_query(
            """SELECT * FROM workflow_snapshots
               WHERE workflow_id = :wf_id
               AND node_id = :node_id
               AND user_id = :user_id
               AND context_hash = :ctx_hash
               AND snapshot_date = :target_date""",
            {
                "wf_id": workflow_id,
                "node_id": node_id,
                "user_id": context.user_id,
                "ctx_hash": context_hash,
                "target_date": target_date.isoformat()
            }
        )

        if not rows:
            return None

        return cls.from_db(rows[0])

    @classmethod
    async def list_for_workflow(
        cls,
        workflow_id: str,
        limit: int = 50
    ) -> List["WorkflowSnapshot"]:
        """
        List all snapshots for a workflow (across all users).

        Args:
            workflow_id: Workflow ID
            limit: Max results

        Returns:
            List of snapshots
        """
        rows = await repo_query(
            """SELECT * FROM workflow_snapshots
               WHERE workflow_id = :wf_id
               ORDER BY snapshot_date DESC LIMIT :limit""",
            {"wf_id": workflow_id, "limit": limit}
        )

        return [cls.from_db(row) for row in rows]

    @classmethod
    async def list_for_user(
        cls,
        user_id: str,
        workflow_id: Optional[str] = None,
        limit: int = 50
    ) -> List["WorkflowSnapshot"]:
        """
        List snapshots accessible to user.

        Args:
            user_id: User ID
            workflow_id: Optional workflow filter
            limit: Max results

        Returns:
            List of snapshots
        """
        if workflow_id:
            rows = await repo_query(
                """SELECT * FROM workflow_snapshots
                   WHERE user_id = :user_id AND workflow_id = :wf_id
                   ORDER BY snapshot_date DESC LIMIT :limit""",
                {"user_id": user_id, "wf_id": workflow_id, "limit": limit}
            )
        else:
            rows = await repo_query(
                """SELECT * FROM workflow_snapshots
                   WHERE user_id = :user_id
                   ORDER BY snapshot_date DESC LIMIT :limit""",
                {"user_id": user_id, "limit": limit}
            )

        return [cls.from_db(row) for row in rows]

    async def load_data(self) -> Any:
        """
        Load snapshot data from storage.

        Returns:
            Deserialized snapshot data
        """
        from open_notebook.agents.workflow_snapshots import SnapshotStorageManager

        import os
        manager = SnapshotStorageManager({
            "snapshot_storage_path": os.getenv("SNAPSHOT_STORAGE_PATH", "./data/snapshots")
        })

        return await manager.load_snapshot(self.model_dump())

    @classmethod
    def from_db(cls, row: dict) -> "WorkflowSnapshot":
        """Create instance from database row"""
        return cls(
            id=row["id"],
            workflow_id=row["workflow_id"],
            node_id=row["node_id"],
            execution_id=row.get("execution_id"),
            user_id=row["user_id"],
            snapshot_date=datetime.fromisoformat(row["snapshot_date"]),  # Changed to datetime
            snapshot_label=row.get("snapshot_label"),
            storage_type=StorageType(row["storage_type"]),
            storage_path=row.get("storage_path"),
            inline_data=row.get("inline_data"),
            data_hash=row["data_hash"],
            row_count=row["row_count"],
            total_size_bytes=row["total_size_bytes"],
            column_count=row.get("column_count", 0),
            query_context=row["query_context"],
            context_hash=row["context_hash"],
            stats_summary=row.get("stats_summary"),
            sample_data=row.get("sample_data"),
            created=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
            expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None
        )

    async def save(self) -> str:
        """Save snapshot to database"""
        if self.id is None:
            self.id = str(uuid4())

        now = datetime.utcnow()
        if self.created is None:
            self.created = now
        self.updated = now

        # Build data dict - explicitly map field names to column names
        # Use _at suffix for timestamp columns to match database schema
        data = {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "execution_id": self.execution_id,
            "user_id": self.user_id,
            "snapshot_date": self.snapshot_date.isoformat(),
            "snapshot_label": self.snapshot_label,
            "storage_type": self.storage_type.value,
            "storage_path": self.storage_path,
            "inline_data": self.inline_data,
            "data_hash": self.data_hash,
            "row_count": self.row_count,
            "total_size_bytes": self.total_size_bytes,
            "column_count": self.column_count,
            "query_context": self.query_context,
            "context_hash": self.context_hash,
            "stats_summary": self.stats_summary,
            "sample_data": self.sample_data,
            "created_at": self.created.isoformat() if self.created else now.isoformat(),
            "updated_at": self.updated.isoformat() if self.updated else now.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }

        print(f"[DEBUG-Save] Saving snapshot {self.id}, data keys: {list(data.keys())}")

        # Check if exists
        existing = await repo_query(
            "SELECT id FROM workflow_snapshots WHERE id = :id",
            {"id": self.id}
        )

        if existing:
            print(f"[DEBUG-Save] Updating existing snapshot")
            await repo_update(self._table_name, self.id, data)
        else:
            print(f"[DEBUG-Save] Creating new snapshot")
            await repo_create(self._table_name, data)

        print(f"[DEBUG-Save] Save completed")
        return self.id

    @classmethod
    async def get_latest_for_context(
        cls,
        workflow_id: str,
        node_id: str,
        context: SnapshotContext
    ) -> Optional["WorkflowSnapshot"]:
        """
        Get the latest snapshot for a specific context.

        Args:
            workflow_id: Workflow ID
            node_id: Node ID
            context: Snapshot context (user + query params)

        Returns:
            Latest snapshot or None if not found
        """
        context_hash = context.calculate_hash()

        rows = await repo_query(
            """SELECT * FROM workflow_snapshots
               WHERE workflow_id = :wf_id
               AND node_id = :node_id
               AND user_id = :user_id
               AND context_hash = :ctx_hash
               ORDER BY snapshot_date DESC LIMIT 1""",
            {
                "wf_id": workflow_id,
                "node_id": node_id,
                "user_id": context.user_id,
                "ctx_hash": context_hash
            }
        )

        if not rows:
            return None

        return cls.from_db(rows[0])

    @classmethod
    async def get_previous_for_context(
        cls,
        workflow_id: str,
        node_id: str,
        context: SnapshotContext,
        before_date: datetime
    ) -> Optional["WorkflowSnapshot"]:
        """
        Get the snapshot before a specific date for a context.

        Args:
            workflow_id: Workflow ID
            node_id: Node ID
            context: Snapshot context
            before_date: Get snapshot before this date

        Returns:
            Previous snapshot or None if not found
        """
        context_hash = context.calculate_hash()

        rows = await repo_query(
            """SELECT * FROM workflow_snapshots
               WHERE workflow_id = :wf_id
               AND node_id = :node_id
               AND user_id = :user_id
               AND context_hash = :ctx_hash
               AND snapshot_date < :before_date
               ORDER BY snapshot_date DESC LIMIT 1""",
            {
                "wf_id": workflow_id,
                "node_id": node_id,
                "user_id": context.user_id,
                "ctx_hash": context_hash,
                "before_date": before_date.isoformat()
            }
        )

        if not rows:
            return None

        return cls.from_db(rows[0])

    async def compare_with(
        self,
        other: "WorkflowSnapshot",
        strategy: str = "fast"
    ) -> Dict[str, Any]:
        """
        Compare this snapshot with another.

        Args:
            other: Other snapshot to compare with
            strategy: Comparison strategy (fast, medium, full)

        Returns:
            Comparison delta with changes
        """
        import logging
        logger = logging.getLogger(__name__)

        # Load data from both snapshots
        data1 = await self.load_data()
        data2 = await other.load_data()

        logger.info(f"[Compare] data1 type: {type(data1)}, length: {len(data1) if isinstance(data1, list) else 'N/A'}")
        logger.info(f"[Compare] data2 type: {type(data2)}, length: {len(data2) if isinstance(data2, list) else 'N/A'}")
        if isinstance(data1, list) and len(data1) > 0:
            logger.info(f"[Compare] data1 first row: {data1[0]}")
        if isinstance(data2, list) and len(data2) > 0:
            logger.info(f"[Compare] data2 first row: {data2[0]}")

        # Simple comparison for now
        if data1 == data2:
            logger.info("[Compare] Data is identical")
            return {
                "changed": False,
                "change_percentage": 0.0,
                "added_rows": [],
                "removed_rows": [],
                "modified_rows": []
            }

        # For list data (tables), do row-by-row comparison
        if isinstance(data1, list) and isinstance(data2, list):
            logger.info(f"[Compare] Starting row-by-row comparison")
            # Convert to dicts keyed by ID or first column for comparison
            def make_key(row):
                if isinstance(row, dict):
                    # Try exact match ID fields first
                    for id_field in ['id', 'ID', 'Id', '_id']:
                        if id_field in row:
                            key = str(row[id_field])
                            logger.info(f"[make_key] Using exact ID field '{id_field}': {key}")
                            return key

                    # Try common patterns with ID suffix (case-insensitive)
                    # Examples: ORDERID, ORDER_ID, order_id, CustomerId, etc.
                    for key_name in row.keys():
                        key_upper = key_name.upper()
                        if key_upper.endswith('ID') or '_ID' in key_upper:
                            key = str(row[key_name])
                            logger.info(f"[make_key] Using ID pattern field '{key_name}': {key}")
                            return key

                    # Try numeric columns (likely to be primary keys)
                    for key_name, value in row.items():
                        if isinstance(value, (int, float)) and value > 0:
                            key = str(value)
                            logger.info(f"[make_key] Using numeric field '{key_name}': {key}")
                            return key

                    # Use first column as fallback
                    if row:
                        first_key = list(row.keys())[0]
                        key = str(row[first_key])
                        logger.info(f"[make_key] Using first column '{first_key}': {key}")
                        return key

                    # Last resort: use all values as key
                    key = str(sorted(row.items()))
                    logger.info(f"[make_key] Using all values: {key[:100]}...")
                    return key
                return str(row)

            logger.info(f"[Compare] Building data1_dict from {len(data1)} rows")
            data1_dict = {make_key(row): row for row in data1}
            logger.info(f"[Compare] data1_dict keys: {list(data1_dict.keys())}")

            logger.info(f"[Compare] Building data2_dict from {len(data2)} rows")
            data2_dict = {make_key(row): row for row in data2}
            logger.info(f"[Compare] data2_dict keys: {list(data2_dict.keys())}")

            keys1 = set(data1_dict.keys())
            keys2 = set(data2_dict.keys())

            added_keys = keys2 - keys1
            removed_keys = keys1 - keys2
            common_keys = keys1 & keys2

            logger.info(f"[Compare] added_keys: {added_keys}")
            logger.info(f"[Compare] removed_keys: {removed_keys}")
            logger.info(f"[Compare] common_keys: {common_keys}")

            added_rows = [data2_dict[k] for k in added_keys]
            removed_rows = [data1_dict[k] for k in removed_keys]

            # Check for modifications in common rows
            modified_rows = []
            for k in common_keys:
                if data1_dict[k] != data2_dict[k]:
                    logger.info(f"[Compare] Row with key '{k}' modified:")
                    logger.info(f"  Before: {data1_dict[k]}")
                    logger.info(f"  After: {data2_dict[k]}")
                    modified_rows.append({
                        "before": data1_dict[k],
                        "after": data2_dict[k]
                    })

            total_changes = len(added_rows) + len(removed_rows) + len(modified_rows)
            total_rows = max(len(data1), len(data2), 1)
            change_percentage = (total_changes / total_rows) * 100

            result = {
                "changed": total_changes > 0,
                "change_percentage": change_percentage,
                "added_rows": added_rows,
                "removed_rows": removed_rows,
                "modified_rows": modified_rows
            }

            logger.info(f"[Compare] Final result:")
            logger.info(f"  Total changes: {total_changes}")
            logger.info(f"  Added: {len(added_rows)}")
            logger.info(f"  Removed: {len(removed_rows)}")
            logger.info(f"  Modified: {len(modified_rows)}")

            return result

        # For non-list data, just check if different
        return {
            "changed": True,
            "change_percentage": 100.0,
            "added_rows": [],
            "removed_rows": [],
            "modified_rows": []
        }

