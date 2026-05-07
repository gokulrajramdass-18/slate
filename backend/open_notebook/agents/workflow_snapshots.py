"""
Snapshot Storage Manager

Handles tiered storage for workflow snapshots:
- Inline storage (< 10MB): Compressed in database
- File storage (10-100MB): Local filesystem
- Chunked storage (> 100MB): Split into multiple files

Features:
- Automatic storage strategy selection
- Compression (gzip)
- Statistical summary calculation
- Hash-based change detection
"""

import asyncio
import gzip
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from open_notebook.domain.workflow_snapshot import SnapshotContext, StorageType


class SnapshotStorageManager:
    """
    Manages tiered storage for workflow snapshots.
    Routes data to appropriate storage backend based on size.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize storage manager.

        Args:
            config: Configuration dict with:
                - snapshot_storage_path: Base path for file storage
                - inline_threshold: Max bytes for inline storage
                - file_threshold: Max bytes for file storage
                - chunk_size: Bytes per chunk for large files
        """
        self.config = config
        self.base_path = Path(config.get("snapshot_storage_path", "./data/snapshots"))
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Thresholds (bytes)
        self.inline_threshold = config.get("inline_threshold", 10 * 1024 * 1024)  # 10MB
        self.file_threshold = config.get("file_threshold", 100 * 1024 * 1024)     # 100MB

        # Chunking for very large datasets
        self.chunk_size = config.get("chunk_size", 50 * 1024 * 1024)  # 50MB chunks

    async def store_snapshot(
        self,
        workflow_id: str,
        node_id: str,
        snapshot_date: str,
        context: SnapshotContext,
        data: Any,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Store snapshot with optimal storage strategy.

        Args:
            workflow_id: Workflow ID
            node_id: Node ID
            snapshot_date: ISO date string
            context: Snapshot context
            data: Data to store
            metadata: Additional metadata

        Returns:
            Snapshot record dict for database
        """
        # Estimate data size
        data_size = self._estimate_size(data)

        print(f"[SnapshotStorage] Data size: {data_size / 1024 / 1024:.2f} MB")

        # Calculate hash and stats BEFORE storage
        data_hash = self._calculate_hash(data)
        stats_summary = self._calculate_statistics(data)
        sample_data = self._extract_sample(data, max_rows=100)

        # Choose storage strategy
        if data_size < self.inline_threshold:
            storage_type = StorageType.INLINE
            storage_path = None
            inline_data = self._compress_data(data)
            print(f"[SnapshotStorage] Using INLINE storage")

        elif data_size < self.file_threshold:
            storage_type = StorageType.FILE
            storage_path = await self._store_to_file(
                workflow_id, node_id, snapshot_date, data
            )
            inline_data = None
            print(f"[SnapshotStorage] Using FILE storage: {storage_path}")

        else:
            # Very large data - use chunking
            storage_type = StorageType.CHUNKED
            storage_path = await self._store_chunked(
                workflow_id, node_id, snapshot_date, data
            )
            inline_data = None
            print(f"[SnapshotStorage] Using CHUNKED storage: {storage_path}")

        # Extract column info
        column_count = 0
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            column_count = len(data[0])

        # Build result
        result = {
            "storage_type": storage_type.value,
            "storage_path": storage_path,
            "inline_data": inline_data,
            "data_hash": data_hash,
            "row_count": len(data) if isinstance(data, list) else 1,
            "total_size_bytes": data_size,
            "column_count": column_count,
            "stats_summary": json.dumps(stats_summary),
            "sample_data": json.dumps(sample_data)
        }

        return result

    async def load_snapshot(self, snapshot: Dict[str, Any]) -> Any:
        """
        Load snapshot data from appropriate storage.

        Args:
            snapshot: Snapshot record dict

        Returns:
            Deserialized data
        """
        storage_type = StorageType(snapshot["storage_type"])

        if storage_type == StorageType.INLINE:
            return self._decompress_data(snapshot.get("inline_data"))

        elif storage_type == StorageType.FILE:
            return await self._load_from_file(snapshot["storage_path"])

        elif storage_type == StorageType.CHUNKED:
            return await self._load_chunked(snapshot["storage_path"])

        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")

    def _estimate_size(self, data: Any) -> int:
        """
        Estimate data size in bytes.

        Args:
            data: Data to measure

        Returns:
            Size in bytes
        """
        if isinstance(data, str):
            return len(data.encode('utf-8'))

        # For structured data, serialize and measure
        data_json = json.dumps(data)
        return len(data_json.encode('utf-8'))

    def _calculate_hash(self, data: Any) -> str:
        """
        Calculate SHA256 hash of data.

        Args:
            data: Data to hash

        Returns:
            Hex digest string
        """
        data_json = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_json.encode()).hexdigest()

    def _calculate_statistics(self, data: Any) -> Dict[str, Any]:
        """
        Calculate statistical summary for fast comparison.

        For large datasets, this is MUCH faster than row-by-row comparison.

        Args:
            data: Data to analyze

        Returns:
            Statistics dict
        """
        if not isinstance(data, list) or len(data) == 0:
            return {}

        if not isinstance(data[0], dict):
            return {"row_count": len(data)}

        # Calculate stats per numeric column
        stats = {}

        # Sample 1000 rows for stats (don't process millions)
        sample_size = min(1000, len(data))
        sample = data[:sample_size]

        # Get numeric columns
        numeric_cols = []
        for col in data[0].keys():
            if isinstance(data[0].get(col), (int, float)):
                numeric_cols.append(col)

        # Calculate min/max/avg for each numeric column
        for col in numeric_cols:
            values = [row[col] for row in sample if col in row and isinstance(row[col], (int, float))]

            if values:
                stats[col] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "count": len(values)
                }

        return stats

    def _extract_sample(self, data: Any, max_rows: int = 100) -> Any:
        """
        Extract sample data for preview.

        Args:
            data: Full dataset
            max_rows: Maximum rows to sample

        Returns:
            Sample data
        """
        if isinstance(data, list):
            return data[:max_rows]
        elif isinstance(data, dict):
            return {k: v for k, v in list(data.items())[:max_rows]}
        else:
            return str(data)[:1000]

    def _compress_data(self, data: Any) -> str:
        """
        Compress data for inline storage.

        Args:
            data: Data to compress

        Returns:
            Base64 encoded compressed string
        """
        import base64

        data_json = json.dumps(data)
        compressed = gzip.compress(data_json.encode())
        return base64.b64encode(compressed).decode()

    def _decompress_data(self, compressed_data: str) -> Any:
        """
        Decompress inline data.

        Args:
            compressed_data: Base64 encoded compressed string

        Returns:
            Deserialized data
        """
        import base64

        compressed = base64.b64decode(compressed_data.encode())
        decompressed = gzip.decompress(compressed)
        return json.loads(decompressed.decode())

    async def _store_to_file(
        self,
        workflow_id: str,
        node_id: str,
        snapshot_date: str,
        data: Any
    ) -> str:
        """
        Store data to compressed file.

        Args:
            workflow_id: Workflow ID
            node_id: Node ID
            snapshot_date: ISO date string
            data: Data to store

        Returns:
            Relative path to file
        """
        # Create directory structure
        file_dir = self.base_path / workflow_id / node_id
        file_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        filename = f"snapshot_{snapshot_date}.json.gz"
        file_path = file_dir / filename

        # Write compressed JSON
        data_json = json.dumps(data)
        with gzip.open(file_path, 'wt', encoding='utf-8') as f:
            f.write(data_json)

        return str(file_path.relative_to(self.base_path))

    async def _load_from_file(self, relative_path: str) -> Any:
        """
        Load data from compressed file.

        Args:
            relative_path: Relative path from base path

        Returns:
            Deserialized data
        """
        file_path = self.base_path / relative_path

        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
            data_json = f.read()

        return json.loads(data_json)

    async def _store_chunked(
        self,
        workflow_id: str,
        node_id: str,
        snapshot_date: str,
        data: list
    ) -> str:
        """
        Store very large datasets as multiple chunks.

        Creates a manifest file + multiple chunk files.

        Args:
            workflow_id: Workflow ID
            node_id: Node ID
            snapshot_date: ISO date string
            data: List data to chunk

        Returns:
            Relative path to chunk directory
        """
        if not isinstance(data, list):
            raise ValueError("Chunked storage requires list data")

        # Calculate rows per chunk
        row_size = len(json.dumps(data[0])) if len(data) > 0 else 100
        rows_per_chunk = max(1, self.chunk_size // row_size)

        total_chunks = math.ceil(len(data) / rows_per_chunk)

        print(f"[SnapshotStorage] Chunking {len(data)} rows into {total_chunks} chunks")

        # Create directory
        chunk_dir = self.base_path / workflow_id / node_id / f"snapshot_{snapshot_date}_chunks"
        chunk_dir.mkdir(parents=True, exist_ok=True)

        # Store chunks
        chunk_files = []
        for i in range(total_chunks):
            start_idx = i * rows_per_chunk
            end_idx = min((i + 1) * rows_per_chunk, len(data))

            chunk_data = data[start_idx:end_idx]
            chunk_filename = f"chunk_{i:04d}.json.gz"
            chunk_path = chunk_dir / chunk_filename

            # Write chunk
            chunk_json = json.dumps(chunk_data)
            with gzip.open(chunk_path, 'wt', encoding='utf-8') as f:
                f.write(chunk_json)

            chunk_files.append({
                "filename": chunk_filename,
                "start_row": start_idx,
                "end_row": end_idx,
                "row_count": end_idx - start_idx
            })

        # Create manifest
        manifest = {
            "total_rows": len(data),
            "total_chunks": total_chunks,
            "rows_per_chunk": rows_per_chunk,
            "chunks": chunk_files,
            "created_at": datetime.utcnow().isoformat()
        }

        manifest_path = chunk_dir / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        return str(chunk_dir.relative_to(self.base_path))

    async def _load_chunked(self, relative_path: str) -> list:
        """
        Load chunked data.

        Args:
            relative_path: Relative path to chunk directory

        Returns:
            Combined data list
        """
        chunk_dir = self.base_path / relative_path
        manifest_path = chunk_dir / "manifest.json"

        # Load manifest
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        # Load chunks
        all_data = []
        for chunk_info in manifest["chunks"]:
            chunk_path = chunk_dir / chunk_info["filename"]

            with gzip.open(chunk_path, 'rt', encoding='utf-8') as f:
                chunk_json = f.read()
                chunk_data = json.loads(chunk_json)
                all_data.extend(chunk_data)

        return all_data
