"""
Tests for the Memory System

Comprehensive tests covering:
- Memory creation and serialization
- Frontmatter parsing
- CRUD operations on MemoryStore
- Keyword search
- Semantic search (with mock embeddings)
- Index management
- Concurrent access safety
- Edge cases
"""

import asyncio
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml

from open_notebook.agents.memory_system import (
    Memory,
    MemoryStore,
    MemoryType,
    get_memory_store,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_memory_dir():
    """Provide a temporary directory for memory storage."""
    d = tempfile.mkdtemp(prefix="memory_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def store(temp_memory_dir):
    """Provide a MemoryStore backed by a temp directory."""
    return MemoryStore(base_dir=temp_memory_dir)


@pytest.fixture
def notebook_id():
    return "test-notebook-001"


@pytest.fixture
def sample_memory():
    """A reusable sample memory."""
    return Memory(
        name="User Prefers Concise Responses",
        description="User wants short, direct answers without verbose explanations",
        memory_type=MemoryType.USER,
        content="The user has indicated they prefer short, concise responses.\nUse bullet points and direct statements when possible.",
    )


# ---------------------------------------------------------------------------
# Memory dataclass tests
# ---------------------------------------------------------------------------

class TestMemory:
    """Tests for the Memory dataclass."""

    def test_create_memory_defaults(self):
        mem = Memory(
            name="Test",
            description="A test memory",
            memory_type=MemoryType.USER,
            content="some content",
        )
        assert mem.id  # auto-generated
        assert mem.created is not None
        assert mem.updated is not None
        assert mem.filename.startswith("user_")
        assert mem.filename.endswith(".md")

    def test_filename_generation(self):
        mem = Memory(
            name="My Complex Name!!! With Symbols",
            description="desc",
            memory_type=MemoryType.FEEDBACK,
            content="c",
        )
        assert mem.filename.startswith("feedback_")
        assert "!" not in mem.filename
        assert " " not in mem.filename

    def test_to_frontmatter(self, sample_memory):
        text = sample_memory.to_frontmatter()
        assert text.startswith("---\n")
        assert "name: User Prefers Concise Responses" in text
        assert "type: user" in text
        assert "bullet points" in text

    def test_from_frontmatter_roundtrip(self, sample_memory):
        text = sample_memory.to_frontmatter()
        parsed = Memory.from_frontmatter(text, filename=sample_memory.filename)
        assert parsed.name == sample_memory.name
        assert parsed.description == sample_memory.description
        assert parsed.memory_type == sample_memory.memory_type
        assert parsed.content == sample_memory.content
        assert parsed.id == sample_memory.id

    def test_from_frontmatter_invalid(self):
        with pytest.raises(ValueError, match="Invalid frontmatter"):
            Memory.from_frontmatter("no frontmatter here")

    def test_from_frontmatter_all_types(self):
        for mtype in MemoryType:
            text = f"---\nname: test\ndescription: d\ntype: {mtype.value}\nid: abc\n---\n\ncontent"
            mem = Memory.from_frontmatter(text)
            assert mem.memory_type == mtype

    def test_memory_type_enum(self):
        assert MemoryType.USER.value == "user"
        assert MemoryType.FEEDBACK.value == "feedback"
        assert MemoryType.PROJECT.value == "project"
        assert MemoryType.REFERENCE.value == "reference"


# ---------------------------------------------------------------------------
# MemoryStore CRUD tests
# ---------------------------------------------------------------------------

class TestMemoryStoreCRUD:
    """Tests for basic CRUD operations on MemoryStore."""

    @pytest.mark.asyncio
    async def test_save_and_get(self, store, notebook_id, sample_memory):
        saved = await store.save(notebook_id, sample_memory)
        assert saved.id == sample_memory.id

        retrieved = await store.get(notebook_id, sample_memory.id)
        assert retrieved is not None
        assert retrieved.name == sample_memory.name
        assert retrieved.content == sample_memory.content

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store, notebook_id):
        result = await store.get(notebook_id, "nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_filename(self, store, notebook_id, sample_memory):
        await store.save(notebook_id, sample_memory)
        retrieved = await store.get_by_filename(notebook_id, sample_memory.filename)
        assert retrieved is not None
        assert retrieved.id == sample_memory.id

    @pytest.mark.asyncio
    async def test_get_by_filename_nonexistent(self, store, notebook_id):
        result = await store.get_by_filename(notebook_id, "no_such_file.md")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(self, store, notebook_id):
        memories = [
            Memory(name="M1", description="d1", memory_type=MemoryType.USER, content="c1"),
            Memory(name="M2", description="d2", memory_type=MemoryType.FEEDBACK, content="c2"),
            Memory(name="M3", description="d3", memory_type=MemoryType.PROJECT, content="c3"),
        ]
        for m in memories:
            await store.save(notebook_id, m)

        all_mem = await store.list_all(notebook_id)
        assert len(all_mem) == 3

    @pytest.mark.asyncio
    async def test_list_all_filtered_by_type(self, store, notebook_id):
        await store.save(notebook_id, Memory(name="U1", description="d", memory_type=MemoryType.USER, content="c"))
        await store.save(notebook_id, Memory(name="F1", description="d", memory_type=MemoryType.FEEDBACK, content="c"))
        await store.save(notebook_id, Memory(name="U2", description="d", memory_type=MemoryType.USER, content="c"))

        user_mem = await store.list_all(notebook_id, memory_type=MemoryType.USER)
        assert len(user_mem) == 2

        feedback_mem = await store.list_all(notebook_id, memory_type=MemoryType.FEEDBACK)
        assert len(feedback_mem) == 1

    @pytest.mark.asyncio
    async def test_list_all_empty_notebook(self, store):
        result = await store.list_all("nonexistent-notebook")
        assert result == []

    @pytest.mark.asyncio
    async def test_delete(self, store, notebook_id, sample_memory):
        await store.save(notebook_id, sample_memory)
        deleted = await store.delete(notebook_id, sample_memory.id)
        assert deleted is True

        retrieved = await store.get(notebook_id, sample_memory.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store, notebook_id):
        deleted = await store.delete(notebook_id, "does-not-exist")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_from_nonexistent_notebook(self, store):
        deleted = await store.delete("no-such-notebook", "any-id")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_update_content(self, store, notebook_id, sample_memory):
        await store.save(notebook_id, sample_memory)

        updated = await store.update(
            notebook_id,
            sample_memory.id,
            content="Updated content here.",
        )
        assert updated is not None
        assert updated.content == "Updated content here."
        assert updated.name == sample_memory.name  # unchanged

    @pytest.mark.asyncio
    async def test_update_name_changes_filename(self, store, notebook_id, sample_memory):
        await store.save(notebook_id, sample_memory)
        old_filename = sample_memory.filename

        updated = await store.update(
            notebook_id,
            sample_memory.id,
            name="Brand New Name",
        )
        assert updated is not None
        assert updated.filename != old_filename
        assert "brand_new_name" in updated.filename

        # Old file should not exist
        old_path = store._notebook_dir(notebook_id) / old_filename
        assert not old_path.exists()

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, store, notebook_id):
        result = await store.update(notebook_id, "nope", content="x")
        assert result is None

    @pytest.mark.asyncio
    async def test_clear(self, store, notebook_id):
        for i in range(3):
            await store.save(
                notebook_id,
                Memory(name=f"M{i}", description="d", memory_type=MemoryType.USER, content="c"),
            )

        count = await store.clear(notebook_id)
        # 3 memory files + MEMORY.md index = 4
        assert count >= 3

        remaining = await store.list_all(notebook_id)
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_clear_nonexistent_notebook(self, store):
        count = await store.clear("no-notebook")
        assert count == 0


# ---------------------------------------------------------------------------
# Index management tests
# ---------------------------------------------------------------------------

class TestMemoryIndex:
    """Tests for MEMORY.md index management."""

    @pytest.mark.asyncio
    async def test_index_created_on_save(self, store, notebook_id, sample_memory):
        await store.save(notebook_id, sample_memory)
        index = await store.get_index(notebook_id)
        assert "User Prefers Concise Responses" in index
        assert sample_memory.filename in index

    @pytest.mark.asyncio
    async def test_index_updated_on_delete(self, store, notebook_id):
        m1 = Memory(name="Keep Me", description="d", memory_type=MemoryType.USER, content="c")
        m2 = Memory(name="Delete Me", description="d", memory_type=MemoryType.FEEDBACK, content="c")

        await store.save(notebook_id, m1)
        await store.save(notebook_id, m2)

        await store.delete(notebook_id, m2.id)

        index = await store.get_index(notebook_id)
        assert "Keep Me" in index
        assert "Delete Me" not in index

    @pytest.mark.asyncio
    async def test_index_grouped_by_type(self, store, notebook_id):
        await store.save(notebook_id, Memory(name="U", description="d", memory_type=MemoryType.USER, content="c"))
        await store.save(notebook_id, Memory(name="F", description="d", memory_type=MemoryType.FEEDBACK, content="c"))
        await store.save(notebook_id, Memory(name="P", description="d", memory_type=MemoryType.PROJECT, content="c"))

        index = await store.get_index(notebook_id)
        assert "## User" in index
        assert "## Feedback" in index
        assert "## Project" in index

    @pytest.mark.asyncio
    async def test_get_index_empty(self, store):
        index = await store.get_index("empty-notebook")
        assert index == ""


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------

class TestMemorySearch:
    """Tests for keyword and semantic search."""

    @pytest.mark.asyncio
    async def test_keyword_search_exact(self, store, notebook_id):
        await store.save(notebook_id, Memory(
            name="Python Setup",
            description="How to set up Python environment",
            memory_type=MemoryType.REFERENCE,
            content="Install Python 3.11 using pyenv. Create virtualenv with venv.",
        ))
        await store.save(notebook_id, Memory(
            name="Docker Setup",
            description="How to set up Docker",
            memory_type=MemoryType.REFERENCE,
            content="Install Docker Desktop. Run docker-compose up.",
        ))

        results = await store.search(notebook_id, "Python")
        assert len(results) >= 1
        assert results[0].name == "Python Setup"

    @pytest.mark.asyncio
    async def test_keyword_search_multi_term(self, store, notebook_id):
        await store.save(notebook_id, Memory(
            name="API Keys",
            description="How to manage API keys securely",
            memory_type=MemoryType.REFERENCE,
            content="Store API keys in encrypted vault. Never commit to git.",
        ))

        results = await store.search(notebook_id, "API keys securely")
        assert len(results) >= 1
        assert "API" in results[0].name

    @pytest.mark.asyncio
    async def test_keyword_search_no_results(self, store, notebook_id):
        await store.save(notebook_id, Memory(
            name="Test", description="d", memory_type=MemoryType.USER, content="hello"
        ))
        results = await store.search(notebook_id, "zyxwvutsrqp")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_keyword_search_with_type_filter(self, store, notebook_id):
        await store.save(notebook_id, Memory(
            name="User Pref", description="d", memory_type=MemoryType.USER, content="prefers dark mode"
        ))
        await store.save(notebook_id, Memory(
            name="Ref Link", description="d", memory_type=MemoryType.REFERENCE, content="prefers this tool"
        ))

        results = await store.search(notebook_id, "prefers", memory_type=MemoryType.USER)
        assert len(results) == 1
        assert results[0].memory_type == MemoryType.USER

    @pytest.mark.asyncio
    async def test_keyword_search_limit(self, store, notebook_id):
        for i in range(10):
            await store.save(notebook_id, Memory(
                name=f"Memory {i}", description="shared keyword", memory_type=MemoryType.PROJECT, content="shared keyword content"
            ))

        results = await store.search(notebook_id, "shared keyword", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_semantic_search_fallback(self, store, notebook_id):
        """Without an embedding function, semantic search falls back to keyword."""
        await store.save(notebook_id, Memory(
            name="Fallback Test", description="d", memory_type=MemoryType.USER, content="unique_token"
        ))

        results = await store.search_semantic(notebook_id, "unique_token", embedding_fn=None)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_semantic_search_with_mock_embeddings(self, store, notebook_id):
        """Test semantic search with a mock embedding function."""
        import numpy as np

        # Build embeddings with keyword overlap scoring
        # Texts with shared words will have higher cosine similarity
        vocab = ["neural", "network", "deep", "learning", "nlp", "pasta", "water", "cook", "boil", "ml"]

        async def mock_embed(text: str):
            text_lower = text.lower()
            vec = np.zeros(len(vocab), dtype=np.float32)
            for i, word in enumerate(vocab):
                if word in text_lower:
                    vec[i] = 1.0
            # Add small noise to avoid zero vector
            vec += 0.01
            vec = vec / np.linalg.norm(vec)
            return vec.tolist()

        await store.save(notebook_id, Memory(
            name="Machine Learning",
            description="ML concepts",
            memory_type=MemoryType.PROJECT,
            content="Neural networks and deep learning for NLP tasks.",
        ))
        await store.save(notebook_id, Memory(
            name="Cooking Recipe",
            description="Italian pasta",
            memory_type=MemoryType.REFERENCE,
            content="Boil water, add pasta, cook for 10 minutes.",
        ))

        results = await store.search_semantic(
            notebook_id,
            "deep learning neural network",
            embedding_fn=mock_embed,
            similarity_threshold=0.3,
            limit=2,
        )
        assert len(results) > 0
        # ML memory should rank higher than cooking for this query
        assert results[0].name == "Machine Learning"

    @pytest.mark.asyncio
    async def test_semantic_search_empty_notebook(self, store):
        async def dummy_embed(text):
            return [0.0] * 10

        results = await store.search_semantic("empty-nb", "query", embedding_fn=dummy_embed)
        assert results == []


# ---------------------------------------------------------------------------
# Recall tests
# ---------------------------------------------------------------------------

class TestMemoryRecall:
    """Tests for the recall convenience method."""

    @pytest.mark.asyncio
    async def test_recall_returns_relevant(self, store, notebook_id):
        await store.save(notebook_id, Memory(
            name="Dark Mode",
            description="User prefers dark mode",
            memory_type=MemoryType.USER,
            content="Always use dark theme in UI recommendations.",
        ))
        await store.save(notebook_id, Memory(
            name="Sprint Goal",
            description="Current sprint objective",
            memory_type=MemoryType.PROJECT,
            content="Finish the HANA migration by Friday.",
        ))

        results = await store.recall(notebook_id, "dark mode theme")
        assert any("Dark Mode" in m.name for m in results)

    @pytest.mark.asyncio
    async def test_recall_with_type_filter(self, store, notebook_id):
        await store.save(notebook_id, Memory(
            name="U1", description="d", memory_type=MemoryType.USER, content="keyword"
        ))
        await store.save(notebook_id, Memory(
            name="P1", description="d", memory_type=MemoryType.PROJECT, content="keyword"
        ))

        results = await store.recall(
            notebook_id,
            "keyword",
            memory_types=[MemoryType.USER],
        )
        assert all(m.memory_type == MemoryType.USER for m in results)

    @pytest.mark.asyncio
    async def test_recall_deduplicates(self, store, notebook_id):
        await store.save(notebook_id, Memory(
            name="Unique", description="unique desc", memory_type=MemoryType.USER, content="unique content"
        ))

        results = await store.recall(notebook_id, "unique")
        ids = [m.id for m in results]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Concurrent access tests
# ---------------------------------------------------------------------------

class TestMemoryConcurrency:
    """Tests for concurrent access safety."""

    @pytest.mark.asyncio
    async def test_concurrent_saves(self, store, notebook_id):
        """Multiple concurrent saves should not corrupt data."""
        memories = [
            Memory(name=f"Concurrent {i}", description="d", memory_type=MemoryType.PROJECT, content=f"content {i}")
            for i in range(10)
        ]

        tasks = [store.save(notebook_id, m) for m in memories]
        await asyncio.gather(*tasks)

        all_mem = await store.list_all(notebook_id)
        assert len(all_mem) == 10

    @pytest.mark.asyncio
    async def test_concurrent_save_and_delete(self, store, notebook_id):
        """Saves and deletes interleaved should be safe."""
        m1 = Memory(name="Keep", description="d", memory_type=MemoryType.USER, content="c")
        m2 = Memory(name="Remove", description="d", memory_type=MemoryType.USER, content="c")

        await store.save(notebook_id, m1)
        await store.save(notebook_id, m2)

        # Concurrent operations
        await asyncio.gather(
            store.save(notebook_id, Memory(name="New", description="d", memory_type=MemoryType.USER, content="c")),
            store.delete(notebook_id, m2.id),
        )

        all_mem = await store.list_all(notebook_id)
        names = {m.name for m in all_mem}
        assert "Keep" in names
        assert "New" in names
        assert "Remove" not in names


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestMemoryEdgeCases:
    """Tests for edge cases and error handling."""

    def test_memory_with_empty_content(self):
        mem = Memory(name="Empty", description="d", memory_type=MemoryType.USER, content="")
        text = mem.to_frontmatter()
        parsed = Memory.from_frontmatter(text)
        assert parsed.content == ""

    def test_memory_with_special_characters_in_name(self):
        mem = Memory(
            name="What's the deal with 'quotes' & <tags>?",
            description="d",
            memory_type=MemoryType.USER,
            content="c",
        )
        text = mem.to_frontmatter()
        parsed = Memory.from_frontmatter(text, filename=mem.filename)
        assert parsed.name == mem.name

    def test_memory_with_yaml_special_chars_in_content(self):
        mem = Memory(
            name="YAML Tricky",
            description="d",
            memory_type=MemoryType.USER,
            content="key: value\n- list item\n  nested: true",
        )
        text = mem.to_frontmatter()
        parsed = Memory.from_frontmatter(text)
        assert "key: value" in parsed.content

    def test_memory_with_frontmatter_like_content(self):
        """Content that looks like frontmatter should not break parsing."""
        mem = Memory(
            name="Tricky Content",
            description="d",
            memory_type=MemoryType.USER,
            content="Here is some text.\n---\nThis looks like a separator but isn't frontmatter.\n---\nMore text.",
        )
        text = mem.to_frontmatter()
        parsed = Memory.from_frontmatter(text)
        assert "looks like a separator" in parsed.content

    def test_memory_long_name_truncated_in_filename(self):
        long_name = "A" * 200
        mem = Memory(name=long_name, description="d", memory_type=MemoryType.USER, content="c")
        assert len(mem.filename) < 70  # type prefix + 50 char slug + .md

    @pytest.mark.asyncio
    async def test_multiple_notebooks_isolated(self, store):
        """Memories in different notebooks should not interfere."""
        nb1 = "notebook-alpha"
        nb2 = "notebook-beta"

        await store.save(nb1, Memory(name="Alpha", description="d", memory_type=MemoryType.USER, content="c"))
        await store.save(nb2, Memory(name="Beta", description="d", memory_type=MemoryType.USER, content="c"))

        alpha_mem = await store.list_all(nb1)
        beta_mem = await store.list_all(nb2)

        assert len(alpha_mem) == 1
        assert alpha_mem[0].name == "Alpha"
        assert len(beta_mem) == 1
        assert beta_mem[0].name == "Beta"

    @pytest.mark.asyncio
    async def test_save_overwrite(self, store, notebook_id):
        """Saving a memory with the same filename overwrites it."""
        m = Memory(name="Original", description="d", memory_type=MemoryType.USER, content="v1")
        await store.save(notebook_id, m)

        m.content = "v2"
        await store.save(notebook_id, m)

        retrieved = await store.get(notebook_id, m.id)
        assert retrieved.content == "v2"


# ---------------------------------------------------------------------------
# Singleton tests
# ---------------------------------------------------------------------------

class TestGetMemoryStore:
    """Tests for the module-level singleton accessor."""

    def test_get_memory_store_default(self, temp_memory_dir):
        s = get_memory_store(base_dir=temp_memory_dir)
        assert s is not None
        assert str(s.base_dir) == temp_memory_dir

    def test_get_memory_store_returns_same_instance(self, temp_memory_dir):
        s1 = get_memory_store(base_dir=temp_memory_dir)
        s2 = get_memory_store()
        # Without a new base_dir, returns the cached instance
        assert s2 is s1
