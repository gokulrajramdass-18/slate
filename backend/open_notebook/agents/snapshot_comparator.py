"""
Snapshot Comparator

Fast comparison algorithms for workflow snapshots:
- Fast: Hash + statistics only (milliseconds)
- Medium: Sampling comparison (seconds)
- Full: Complete row-by-row comparison (minutes)

All comparisons include context validation to prevent
comparing incompatible datasets.
"""

import time
import json
import gzip
from typing import Dict, Any, Optional
from pathlib import Path

from open_notebook.domain.workflow_snapshot import SnapshotContext, StorageType
from open_notebook.agents.workflow_snapshots import SnapshotStorageManager


class SnapshotComparator:
    """
    Compare snapshots WITHOUT loading full data into memory.
    Uses statistical summaries, hashes, and streaming comparison.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize comparator.

        Args:
            config: Configuration dict (same as SnapshotStorageManager)
        """
        self.config = config

    async def compare_snapshots(
        self,
        snapshot1: Dict[str, Any],
        snapshot2: Dict[str, Any],
        strategy: str = "fast"
    ) -> Dict[str, Any]:
        """
        Compare two snapshots efficiently.

        Strategies:
        - fast: Hash + stats only (milliseconds)
        - medium: Sampling comparison (seconds)
        - full: Complete comparison (minutes for large data)

        Args:
            snapshot1: First snapshot dict
            snapshot2: Second snapshot dict
            strategy: Comparison strategy

        Returns:
            Comparison result dict

        Raises:
            ValueError: If contexts don't match
        """
        # Validate contexts FIRST
        self._validate_contexts(snapshot1, snapshot2)

        if strategy == "fast":
            return self._compare_fast(snapshot1, snapshot2)
        elif strategy == "medium":
            return await self._compare_sampled(snapshot1, snapshot2)
        elif strategy == "full":
            return await self._compare_full(snapshot1, snapshot2)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def _validate_contexts(
        self,
        snapshot1: Dict[str, Any],
        snapshot2: Dict[str, Any]
    ) -> None:
        """
        Validate that snapshots can be compared.

        Ensures:
        1. Same user
        2. Same context (query params, filters)

        Args:
            snapshot1: First snapshot
            snapshot2: Second snapshot

        Raises:
            ValueError: If contexts are incompatible
        """
        # Validate user isolation
        if snapshot1["user_id"] != snapshot2["user_id"]:
            raise ValueError(
                f"Cannot compare snapshots from different users: "
                f"{snapshot1['user_id']} vs {snapshot2['user_id']}"
            )

        # Validate context compatibility
        if snapshot1["context_hash"] != snapshot2["context_hash"]:
            ctx1 = json.loads(snapshot1["query_context"])
            ctx2 = json.loads(snapshot2["query_context"])

            raise ValueError(
                f"Cannot compare snapshots with different contexts:\n"
                f"Snapshot 1 query params: {ctx1.get('query_params', {})}\n"
                f"Snapshot 2 query params: {ctx2.get('query_params', {})}\n"
                f"These appear to be filtering different data."
            )

    def _compare_fast(
        self,
        snapshot1: Dict[str, Any],
        snapshot2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ultra-fast comparison using only metadata.

        Checks:
        1. Hash equality
        2. Row count difference
        3. Statistical summary differences

        No data loading required!

        Args:
            snapshot1: First snapshot
            snapshot2: Second snapshot

        Returns:
            Comparison result dict
        """
        start_time = time.time()

        # Hash comparison
        same_hash = snapshot1["data_hash"] == snapshot2["data_hash"]

        if same_hash:
            return {
                "status": "compared",
                "strategy": "fast",
                "has_changes": False,
                "change_percentage": 0.0,
                "comparison_time_ms": (time.time() - start_time) * 1000,
                "snapshot1_date": snapshot1["snapshot_date"],
                "snapshot2_date": snapshot2["snapshot_date"]
            }

        # Row count comparison
        row_diff = abs(snapshot2["row_count"] - snapshot1["row_count"])
        row_change_pct = (row_diff / snapshot1["row_count"] * 100) if snapshot1["row_count"] > 0 else 100.0

        # Stats comparison
        stats1 = json.loads(snapshot1.get("stats_summary", "{}"))
        stats2 = json.loads(snapshot2.get("stats_summary", "{}"))

        stats_diff = self._compare_statistics(stats1, stats2)

        return {
            "status": "compared",
            "strategy": "fast",
            "has_changes": True,
            "change_percentage": max(row_change_pct, stats_diff.get("max_change_pct", 0)),
            "row_diff": snapshot2["row_count"] - snapshot1["row_count"],
            "row_change_percentage": row_change_pct,
            "stats_changes": stats_diff,
            "comparison_time_ms": (time.time() - start_time) * 1000,
            "snapshot1_date": snapshot1["snapshot_date"],
            "snapshot2_date": snapshot2["snapshot_date"],
            "snapshot1_rows": snapshot1["row_count"],
            "snapshot2_rows": snapshot2["row_count"]
        }

    async def _compare_sampled(
        self,
        snapshot1: Dict[str, Any],
        snapshot2: Dict[str, Any],
        sample_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Medium-speed comparison using random sampling.

        Good balance between speed and accuracy.

        Args:
            snapshot1: First snapshot
            snapshot2: Second snapshot
            sample_size: Number of rows to sample

        Returns:
            Comparison result dict
        """
        start_time = time.time()

        storage_mgr = SnapshotStorageManager(self.config)

        # Load sample data only (not full dataset)
        sample1 = json.loads(snapshot1.get("sample_data", "[]"))
        sample2 = json.loads(snapshot2.get("sample_data", "[]"))

        # If samples are large enough, use them
        if len(sample1) >= sample_size and len(sample2) >= sample_size:
            delta = self._calculate_delta(sample1[:sample_size], sample2[:sample_size])
        else:
            # Need to load more data - stream it
            delta = await self._stream_compare(
                storage_mgr,
                snapshot1,
                snapshot2,
                sample_size
            )

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "status": "compared",
            "strategy": "sampled",
            "has_changes": delta["total_changes"] > 0,
            "change_percentage": delta["change_percentage"],
            "delta": delta,
            "comparison_time_ms": elapsed_ms,
            "note": f"Sampled {sample_size} rows",
            "snapshot1_date": snapshot1["snapshot_date"],
            "snapshot2_date": snapshot2["snapshot_date"]
        }

    async def _compare_full(
        self,
        snapshot1: Dict[str, Any],
        snapshot2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete row-by-row comparison.

        Warning: Can be slow for large datasets.

        Args:
            snapshot1: First snapshot
            snapshot2: Second snapshot

        Returns:
            Comparison result dict
        """
        start_time = time.time()

        storage_mgr = SnapshotStorageManager(self.config)

        # Load full data
        data1 = await storage_mgr.load_snapshot(snapshot1)
        data2 = await storage_mgr.load_snapshot(snapshot2)

        # Calculate delta
        delta = self._calculate_delta(data1, data2)

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "status": "compared",
            "strategy": "full",
            "has_changes": delta["total_changes"] > 0,
            "change_percentage": delta["change_percentage"],
            "delta": delta,
            "comparison_time_ms": elapsed_ms,
            "snapshot1_date": snapshot1["snapshot_date"],
            "snapshot2_date": snapshot2["snapshot_date"]
        }

    async def _stream_compare(
        self,
        storage_mgr: SnapshotStorageManager,
        snapshot1: Dict[str, Any],
        snapshot2: Dict[str, Any],
        sample_size: int
    ) -> Dict[str, Any]:
        """
        Stream-based comparison for chunked data.
        Loads only one chunk at a time.

        Args:
            storage_mgr: Storage manager
            snapshot1: First snapshot
            snapshot2: Second snapshot
            sample_size: Number of rows to compare

        Returns:
            Delta dict
        """
        storage_type = StorageType(snapshot1["storage_type"])

        if storage_type != StorageType.CHUNKED:
            # Fallback to loading full data
            data1 = await storage_mgr.load_snapshot(snapshot1)
            data2 = await storage_mgr.load_snapshot(snapshot2)
            return self._calculate_delta(data1[:sample_size], data2[:sample_size])

        # For chunked data, compare first chunk only
        base_path = Path(self.config["snapshot_storage_path"])
        chunk_dir1 = base_path / snapshot1["storage_path"]
        chunk_dir2 = base_path / snapshot2["storage_path"]

        # Load first chunk from each
        chunk1_path = chunk_dir1 / "chunk_0000.json.gz"
        chunk2_path = chunk_dir2 / "chunk_0000.json.gz"

        with gzip.open(chunk1_path, 'rt', encoding='utf-8') as f:
            chunk1_data = json.loads(f.read())

        with gzip.open(chunk2_path, 'rt', encoding='utf-8') as f:
            chunk2_data = json.loads(f.read())

        return self._calculate_delta(chunk1_data[:sample_size], chunk2_data[:sample_size])

    def _compare_statistics(self, stats1: Dict, stats2: Dict) -> Dict[str, Any]:
        """
        Compare statistical summaries.

        Args:
            stats1: First stats dict
            stats2: Second stats dict

        Returns:
            Comparison dict with changes
        """
        if not stats1 or not stats2:
            return {"max_change_pct": 0}

        changes = {}
        max_change_pct = 0.0

        # Compare each column's stats
        for col in set(stats1.keys()) | set(stats2.keys()):
            if col not in stats1 or col not in stats2:
                changes[col] = "column_added_or_removed"
                max_change_pct = 100.0
                continue

            s1 = stats1[col]
            s2 = stats2[col]

            # Compare averages
            avg1 = s1.get("avg", 0)
            avg2 = s2.get("avg", 0)

            if avg1 != 0:
                avg_change = abs(avg2 - avg1) / avg1 * 100
                changes[col] = {
                    "avg_change_pct": round(avg_change, 2),
                    "min_change": s2.get("min", 0) - s1.get("min", 0),
                    "max_change": s2.get("max", 0) - s1.get("max", 0)
                }
                max_change_pct = max(max_change_pct, avg_change)

        return {
            "column_changes": changes,
            "max_change_pct": round(max_change_pct, 2)
        }

    def _calculate_delta(self, data1: list, data2: list) -> Dict[str, Any]:
        """
        Calculate delta between two datasets.

        Args:
            data1: First dataset
            data2: Second dataset

        Returns:
            Delta dict with changes
        """
        if not isinstance(data1, list) or not isinstance(data2, list):
            return {
                "total_changes": 0 if data1 == data2 else 1,
                "change_percentage": 0.0 if data1 == data2 else 100.0
            }

        if len(data1) == 0 or len(data2) == 0:
            return {
                "total_changes": abs(len(data2) - len(data1)),
                "change_percentage": 100.0
            }

        # Use first column as ID if possible
        if isinstance(data1[0], dict):
            id_field = "id" if "id" in data1[0] else list(data1[0].keys())[0]

            dict1 = {str(row.get(id_field)): row for row in data1}
            dict2 = {str(row.get(id_field)): row for row in data2}

            added = [k for k in dict2.keys() if k not in dict1]
            removed = [k for k in dict1.keys() if k not in dict2]
            modified = [k for k in dict1.keys() if k in dict2 and dict1[k] != dict2[k]]

            total_changes = len(added) + len(removed) + len(modified)
            change_pct = (total_changes / len(dict1) * 100) if len(dict1) > 0 else 100.0

            return {
                "added_count": len(added),
                "removed_count": len(removed),
                "modified_count": len(modified),
                "total_changes": total_changes,
                "change_percentage": round(change_pct, 2),
                "added_ids": added[:10],  # First 10
                "removed_ids": removed[:10],
                "modified_ids": modified[:10]
            }

        # Fallback
        return {
            "total_changes": 0 if data1 == data2 else 1,
            "change_percentage": 0.0 if data1 == data2 else 100.0
        }
