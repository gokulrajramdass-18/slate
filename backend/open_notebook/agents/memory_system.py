"""
Memory System for Open Notebook Agents

A file-based persistent memory system that stores memories as markdown files
with YAML frontmatter. Memories are organized per-notebook and support semantic
search for recall. Inspired by Claude Code's memory architecture.

Memory Types:
- USER: Information about user preferences, role, and knowledge
- FEEDBACK: Guidance on approach — corrections and confirmed patterns
- PROJECT: Context about ongoing work, goals, and initiatives
- REFERENCE: Pointers to external resources and systems

Directory Structure:
    data/memory/{notebook_id}/
        MEMORY.md           # Index of all memories
        user_*.md           # User memories
        feedback_*.md       # Feedback memories
        project_*.md        # Project memories
        reference_*.md      # Reference memories
"""

import asyncio
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class MemoryType(str, Enum):
    """Types of memory that can be stored."""
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


@dataclass
class Memory:
    """A single memory entry with frontmatter metadata and content."""
    name: str
    description: str
    memory_type: MemoryType
    content: str
    id: str = ""
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    filename: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        if not self.created:
            self.created = datetime.utcnow()
        if not self.updated:
            self.updated = self.created
        if not self.filename:
            slug = re.sub(r'[^a-z0-9]+', '_', self.name.lower()).strip('_')[:50]
            self.filename = f"{self.memory_type.value}_{slug}.md"

    def to_frontmatter(self) -> str:
        """Serialize memory to markdown with YAML frontmatter."""
        frontmatter = {
            "name": self.name,
            "description": self.description,
            "type": self.memory_type.value,
            "id": self.id,
            "created": self.created.isoformat() if self.created else None,
            "updated": self.updated.isoformat() if self.updated else None,
        }
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_str}---\n\n{self.content}\n"

    @classmethod
    def from_frontmatter(cls, text: str, filename: str = "") -> "Memory":
        """Parse a memory from markdown with YAML frontmatter."""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL)
        if not match:
            raise ValueError("Invalid frontmatter format")

        yaml_str, content = match.groups()
        meta = yaml.safe_load(yaml_str)

        created = meta.get("created")
        if isinstance(created, str):
            created = datetime.fromisoformat(created)
        elif not isinstance(created, datetime):
            created = None

        updated = meta.get("updated")
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated)
        elif not isinstance(updated, datetime):
            updated = None

        return cls(
            name=meta.get("name", ""),
            description=meta.get("description", ""),
            memory_type=MemoryType(meta.get("type", "project")),
            content=content.strip(),
            id=meta.get("id", str(uuid.uuid4())[:8]),
            created=created,
            updated=updated,
            filename=filename,
        )


class MemoryStore:
    """
    File-based memory store organized by notebook.

    Stores memories as markdown files with YAML frontmatter in:
        {base_dir}/{notebook_id}/

    Maintains a MEMORY.md index file for quick reference.
    Thread-safe via asyncio locks per notebook.
    """

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize the memory store.

        Args:
            base_dir: Root directory for memory storage.
                      Defaults to data/memory/ relative to project root.
        """
        if base_dir is None:
            project_root = Path(__file__).parent.parent.parent
            base_dir = str(project_root / "data" / "memory")
        self.base_dir = Path(base_dir)
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, notebook_id: str) -> asyncio.Lock:
        """Get or create an asyncio lock for a specific notebook."""
        if notebook_id not in self._locks:
            self._locks[notebook_id] = asyncio.Lock()
        return self._locks[notebook_id]

    def _notebook_dir(self, notebook_id: str) -> Path:
        """Get the directory path for a notebook's memories."""
        return self.base_dir / notebook_id

    def _ensure_dir(self, notebook_id: str) -> Path:
        """Ensure the notebook memory directory exists."""
        path = self._notebook_dir(notebook_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def save(self, notebook_id: str, memory: Memory) -> Memory:
        """
        Save a memory to the file system.

        Creates or overwrites the memory file and updates the MEMORY.md index.

        Args:
            notebook_id: Notebook this memory belongs to
            memory: Memory to save

        Returns:
            The saved Memory with updated timestamps
        """
        async with self._get_lock(notebook_id):
            directory = self._ensure_dir(notebook_id)
            memory.updated = datetime.utcnow()

            file_path = directory / memory.filename
            file_path.write_text(memory.to_frontmatter(), encoding="utf-8")

            await self._rebuild_index(notebook_id)
            return memory

    async def get(self, notebook_id: str, memory_id: str) -> Optional[Memory]:
        """
        Retrieve a memory by its ID.

        Args:
            notebook_id: Notebook the memory belongs to
            memory_id: Memory ID to look up

        Returns:
            Memory if found, None otherwise
        """
        memories = await self.list_all(notebook_id)
        for mem in memories:
            if mem.id == memory_id:
                return mem
        return None

    async def get_by_filename(self, notebook_id: str, filename: str) -> Optional[Memory]:
        """
        Retrieve a memory by its filename.

        Args:
            notebook_id: Notebook the memory belongs to
            filename: Memory filename (e.g., "user_preferences.md")

        Returns:
            Memory if found, None otherwise
        """
        directory = self._notebook_dir(notebook_id)
        file_path = directory / filename
        if not file_path.exists():
            return None
        text = file_path.read_text(encoding="utf-8")
        return Memory.from_frontmatter(text, filename=filename)

    async def list_all(
        self,
        notebook_id: str,
        memory_type: Optional[MemoryType] = None,
    ) -> List[Memory]:
        """
        List all memories for a notebook, optionally filtered by type.

        Args:
            notebook_id: Notebook to list memories for
            memory_type: Optional type filter

        Returns:
            List of Memory objects sorted by creation time (newest first)
        """
        directory = self._notebook_dir(notebook_id)
        if not directory.exists():
            return []

        memories = []
        for file_path in directory.glob("*.md"):
            if file_path.name == "MEMORY.md":
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
                mem = Memory.from_frontmatter(text, filename=file_path.name)
                if memory_type is None or mem.memory_type == memory_type:
                    memories.append(mem)
            except (ValueError, yaml.YAMLError):
                continue

        memories.sort(key=lambda m: m.created or datetime.min, reverse=True)
        return memories

    async def delete(self, notebook_id: str, memory_id: str) -> bool:
        """
        Delete a memory by its ID.

        Args:
            notebook_id: Notebook the memory belongs to
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        async with self._get_lock(notebook_id):
            directory = self._notebook_dir(notebook_id)
            if not directory.exists():
                return False

            for file_path in directory.glob("*.md"):
                if file_path.name == "MEMORY.md":
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8")
                    mem = Memory.from_frontmatter(text, filename=file_path.name)
                    if mem.id == memory_id:
                        file_path.unlink()
                        await self._rebuild_index(notebook_id)
                        return True
                except (ValueError, yaml.YAMLError):
                    continue
            return False

    async def search(
        self,
        notebook_id: str,
        query: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> List[Memory]:
        """
        Search memories by keyword matching against name, description, and content.

        Uses simple text matching. For semantic search, use search_semantic().

        Args:
            notebook_id: Notebook to search in
            query: Search query string
            memory_type: Optional type filter
            limit: Maximum results to return

        Returns:
            List of matching Memory objects, ranked by relevance
        """
        all_memories = await self.list_all(notebook_id, memory_type=memory_type)
        query_lower = query.lower()
        query_terms = query_lower.split()

        scored: List[tuple] = []
        for mem in all_memories:
            score = 0
            searchable = f"{mem.name} {mem.description} {mem.content}".lower()

            # Exact phrase match in content
            if query_lower in searchable:
                score += 10

            # Individual term matches
            for term in query_terms:
                if term in mem.name.lower():
                    score += 5
                if term in mem.description.lower():
                    score += 3
                if term in mem.content.lower():
                    score += 1

            if score > 0:
                scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:limit]]

    async def search_semantic(
        self,
        notebook_id: str,
        query: str,
        embedding_fn=None,
        memory_type: Optional[MemoryType] = None,
        limit: int = 5,
        similarity_threshold: float = 0.5,
    ) -> List[Memory]:
        """
        Search memories using semantic similarity with embeddings.

        Falls back to keyword search if no embedding function is provided.

        Args:
            notebook_id: Notebook to search in
            query: Search query
            embedding_fn: Async callable that takes text and returns a list of floats.
                          If None, falls back to keyword search.
            memory_type: Optional type filter
            limit: Maximum results
            similarity_threshold: Minimum cosine similarity (0-1)

        Returns:
            List of matching Memory objects, ranked by semantic similarity
        """
        if embedding_fn is None:
            return await self.search(notebook_id, query, memory_type=memory_type, limit=limit)

        all_memories = await self.list_all(notebook_id, memory_type=memory_type)
        if not all_memories:
            return []

        try:
            import numpy as np
        except ImportError:
            return await self.search(notebook_id, query, memory_type=memory_type, limit=limit)

        query_embedding = await embedding_fn(query)
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        scored: List[tuple] = []
        for mem in all_memories:
            mem_text = f"{mem.name}. {mem.description}. {mem.content}"
            mem_embedding = await embedding_fn(mem_text)
            mem_vec = np.array(mem_embedding, dtype=np.float32)
            mem_norm = np.linalg.norm(mem_vec)
            if mem_norm == 0:
                continue

            similarity = float(np.dot(query_vec, mem_vec) / (query_norm * mem_norm))
            if similarity >= similarity_threshold:
                scored.append((similarity, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:limit]]

    async def _rebuild_index(self, notebook_id: str) -> None:
        """
        Rebuild the MEMORY.md index file for a notebook.

        The index contains one line per memory for quick reference.
        """
        directory = self._notebook_dir(notebook_id)
        memories = await self.list_all(notebook_id)

        lines = [f"# Memory Index — {notebook_id}\n\n"]

        # Group by type
        by_type: Dict[MemoryType, List[Memory]] = {}
        for mem in memories:
            by_type.setdefault(mem.memory_type, []).append(mem)

        for mtype in MemoryType:
            type_memories = by_type.get(mtype, [])
            if not type_memories:
                continue
            lines.append(f"## {mtype.value.title()}\n\n")
            for mem in type_memories:
                desc = mem.description[:100] if mem.description else ""
                lines.append(f"- [{mem.name}]({mem.filename}) — {desc}\n")
            lines.append("\n")

        index_path = directory / "MEMORY.md"
        index_path.write_text("".join(lines), encoding="utf-8")

    async def get_index(self, notebook_id: str) -> str:
        """
        Read the MEMORY.md index for a notebook.

        Returns:
            Contents of MEMORY.md, or empty string if not found
        """
        index_path = self._notebook_dir(notebook_id) / "MEMORY.md"
        if not index_path.exists():
            return ""
        return index_path.read_text(encoding="utf-8")

    async def clear(self, notebook_id: str) -> int:
        """
        Delete all memories for a notebook.

        Args:
            notebook_id: Notebook to clear

        Returns:
            Number of memories deleted
        """
        async with self._get_lock(notebook_id):
            directory = self._notebook_dir(notebook_id)
            if not directory.exists():
                return 0

            count = 0
            for file_path in directory.glob("*.md"):
                file_path.unlink()
                count += 1

            return count

    async def update(
        self,
        notebook_id: str,
        memory_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        content: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
    ) -> Optional[Memory]:
        """
        Update an existing memory's fields.

        Only provided fields are updated; others remain unchanged.

        Args:
            notebook_id: Notebook the memory belongs to
            memory_id: Memory ID to update
            name: New name (optional)
            description: New description (optional)
            content: New content (optional)
            memory_type: New type (optional)

        Returns:
            Updated Memory, or None if not found
        """
        existing = await self.get(notebook_id, memory_id)
        if existing is None:
            return None

        # Track whether filename needs to change
        old_filename = existing.filename
        if name is not None:
            existing.name = name
        if description is not None:
            existing.description = description
        if content is not None:
            existing.content = content
        if memory_type is not None:
            existing.memory_type = memory_type

        # If name or type changed, regenerate filename
        if name is not None or memory_type is not None:
            slug = re.sub(r'[^a-z0-9]+', '_', existing.name.lower()).strip('_')[:50]
            existing.filename = f"{existing.memory_type.value}_{slug}.md"

            # Remove old file if filename changed
            if old_filename != existing.filename:
                old_path = self._notebook_dir(notebook_id) / old_filename
                if old_path.exists():
                    old_path.unlink()

        return await self.save(notebook_id, existing)

    async def recall(
        self,
        notebook_id: str,
        context: str,
        memory_types: Optional[List[MemoryType]] = None,
        limit: int = 5,
    ) -> List[Memory]:
        """
        Recall relevant memories given a context string.

        Convenience method that searches across specified memory types
        and returns the most relevant memories.

        Args:
            notebook_id: Notebook to search in
            context: Context string (e.g., current user message or task description)
            memory_types: Types to search (defaults to all)
            limit: Maximum memories to return

        Returns:
            List of relevant memories
        """
        if memory_types is None:
            memory_types = list(MemoryType)

        results: List[Memory] = []
        for mtype in memory_types:
            matches = await self.search(
                notebook_id, context, memory_type=mtype, limit=limit
            )
            results.extend(matches)

        # De-duplicate by ID and sort by relevance (search already sorted)
        seen = set()
        unique = []
        for mem in results:
            if mem.id not in seen:
                seen.add(mem.id)
                unique.append(mem)

        return unique[:limit]


# Module-level singleton
_memory_store: Optional[MemoryStore] = None


def get_memory_store(base_dir: Optional[str] = None) -> MemoryStore:
    """
    Get or create the global MemoryStore instance.

    Args:
        base_dir: Override base directory (mainly for testing)

    Returns:
        MemoryStore singleton
    """
    global _memory_store
    if _memory_store is None or base_dir is not None:
        _memory_store = MemoryStore(base_dir=base_dir)
    return _memory_store
