"""
Unit tests for domain models.

Tests cover:
- Notebook model CRUD
- Source model with different types
- Note model operations
- Relationship queries (get_sources, get_notes)
- Cascade deletes
"""

import json
import uuid
from datetime import datetime

import pytest

from open_notebook.domain.notebook import Notebook, Source, Note
from open_notebook.domain.base import ObjectModel


@pytest.mark.asyncio
class TestNotebookModel:
    """Test Notebook domain model."""

    async def test_notebook_create(self, sqlite_db):
        """Test creating a new notebook."""
        notebook = Notebook(
            name="Research Project",
            description="My research notebook",
            archived=False
        )

        await notebook.save()

        assert notebook.id is not None
        assert len(notebook.id) == 36  # UUID
        assert notebook.created is not None
        assert notebook.updated is not None

    async def test_notebook_get_all(self, sqlite_db):
        """Test retrieving all notebooks."""
        # Create multiple notebooks
        for i in range(5):
            notebook = Notebook(
                name=f"Notebook {i}",
                description=f"Description {i}",
                archived=(i % 2 == 0)
            )
            await notebook.save()

        # Get all notebooks
        notebooks = await Notebook.get_all()

        assert len(notebooks) >= 5
        assert all(isinstance(nb, Notebook) for nb in notebooks)

    async def test_notebook_get_all_with_filter(self, sqlite_db):
        """Test retrieving notebooks with filter."""
        # Create notebooks
        for i in range(3):
            notebook = Notebook(
                name=f"Active Notebook {i}",
                archived=False
            )
            await notebook.save()

        for i in range(2):
            notebook = Notebook(
                name=f"Archived Notebook {i}",
                archived=True
            )
            await notebook.save()

        # Get only active notebooks
        active_notebooks = await Notebook.get_all(
            filters={"archived": False}
        )

        assert len(active_notebooks) >= 3
        assert all(nb.archived == False for nb in active_notebooks)

    async def test_notebook_get_by_id(self, sqlite_db):
        """Test retrieving notebook by ID."""
        # Create notebook
        notebook = Notebook(
            name="Test Notebook",
            description="Test description"
        )
        await notebook.save()

        # Retrieve by ID
        retrieved = await Notebook.get(notebook.id)

        assert retrieved is not None
        assert retrieved.id == notebook.id
        assert retrieved.name == notebook.name
        assert retrieved.description == notebook.description

    async def test_notebook_get_nonexistent(self, sqlite_db):
        """Test retrieving non-existent notebook."""
        fake_id = str(uuid.uuid4())

        retrieved = await Notebook.get(fake_id)

        assert retrieved is None

    async def test_notebook_update(self, sqlite_db):
        """Test updating a notebook."""
        # Create notebook
        notebook = Notebook(
            name="Original Name",
            description="Original description",
            archived=False
        )
        await notebook.save()

        original_updated = notebook.updated

        # Update notebook
        notebook.name = "Updated Name"
        notebook.description = "Updated description"
        notebook.archived = True

        await notebook.save()

        # Verify update
        retrieved = await Notebook.get(notebook.id)

        assert retrieved.name == "Updated Name"
        assert retrieved.description == "Updated description"
        assert retrieved.archived == True
        assert retrieved.updated > original_updated

    async def test_notebook_delete(self, sqlite_db):
        """Test deleting a notebook."""
        # Create notebook
        notebook = Notebook(
            name="To Be Deleted",
            archived=False
        )
        await notebook.save()

        notebook_id = notebook.id

        # Delete notebook
        await notebook.delete()

        # Verify deletion
        retrieved = await Notebook.get(notebook_id)
        assert retrieved is None

    async def test_notebook_get_sources(self, sqlite_db):
        """Test retrieving sources associated with a notebook."""
        # Create notebook
        notebook = Notebook(name="Test Notebook")
        await notebook.save()

        # Create sources
        source1 = Source(
            title="Document 1",
            source_type="text",
            full_text="Content 1"
        )
        await source1.save()

        source2 = Source(
            title="Document 2",
            source_type="text",
            full_text="Content 2"
        )
        await source2.save()

        # Link sources to notebook
        await notebook.add_source(source1.id)
        await notebook.add_source(source2.id)

        # Get sources
        sources = await notebook.get_sources()

        assert len(sources) == 2
        assert all(isinstance(s, Source) for s in sources)
        assert set(s.id for s in sources) == {source1.id, source2.id}

    async def test_notebook_get_notes(self, sqlite_db):
        """Test retrieving notes associated with a notebook."""
        # Create notebook
        notebook = Notebook(name="Test Notebook")
        await notebook.save()

        # Create notes
        note1 = Note(
            title="Note 1",
            content="Content 1"
        )
        await note1.save()

        note2 = Note(
            title="Note 2",
            content="Content 2"
        )
        await note2.save()

        # Link notes to notebook
        await notebook.add_note(note1.id)
        await notebook.add_note(note2.id)

        # Get notes
        notes = await notebook.get_notes()

        assert len(notes) == 2
        assert all(isinstance(n, Note) for n in notes)
        assert set(n.id for n in notes) == {note1.id, note2.id}

    async def test_notebook_cascade_delete(self, sqlite_db):
        """Test cascade delete of notebook relationships."""
        # Create notebook with sources and notes
        notebook = Notebook(name="Test Notebook")
        await notebook.save()

        source = Source(
            title="Test Source",
            source_type="text",
            full_text="Content"
        )
        await source.save()
        await notebook.add_source(source.id)

        note = Note(
            title="Test Note",
            content="Note content"
        )
        await note.save()
        await notebook.add_note(note.id)

        # Delete notebook
        await notebook.delete()

        # Verify relationships are deleted (but not the source/note themselves)
        sources = await notebook.get_sources()
        notes = await notebook.get_notes()

        assert len(sources) == 0
        assert len(notes) == 0

        # Source and note should still exist
        assert await Source.get(source.id) is not None
        assert await Note.get(note.id) is not None

    async def test_notebook_folder_support(self, sqlite_db):
        """Test notebook folder organization."""
        folder_id = str(uuid.uuid4())

        notebook = Notebook(
            name="Organized Notebook",
            folder_id=folder_id
        )
        await notebook.save()

        # Retrieve and verify
        retrieved = await Notebook.get(notebook.id)
        assert retrieved.folder_id == folder_id


@pytest.mark.asyncio
class TestSourceModel:
    """Test Source domain model with different types."""

    async def test_source_create_text(self, sqlite_db):
        """Test creating a text source."""
        source = Source(
            title="Text Document",
            source_type="text",
            full_text="This is plain text content.",
            topics=["testing", "documentation"]
        )

        await source.save()

        assert source.id is not None
        assert source.source_type == "text"

    async def test_source_create_file(self, sqlite_db):
        """Test creating a file source."""
        source = Source(
            title="PDF Document",
            source_type="file",
            full_text="Extracted text from PDF",
            asset_type="pdf",
            asset_data="/path/to/file.pdf"
        )

        await source.save()

        assert source.source_type == "file"
        assert source.asset_type == "pdf"

    async def test_source_create_url(self, sqlite_db):
        """Test creating a URL source."""
        source = Source(
            title="Web Page",
            source_type="url",
            full_text="Scraped content from web page",
            asset_data="https://example.com/article"
        )

        await source.save()

        assert source.source_type == "url"

    async def test_source_create_youtube(self, sqlite_db):
        """Test creating a YouTube source."""
        source = Source(
            title="YouTube Video",
            source_type="youtube",
            full_text="Video transcript content",
            asset_data="https://youtube.com/watch?v=abc123"
        )

        await source.save()

        assert source.source_type == "youtube"

    async def test_source_create_hana_table(self, sqlite_db, sample_hana_table_source):
        """Test creating a HANA table source."""
        source = Source(
            title=sample_hana_table_source["title"],
            source_type=sample_hana_table_source["source_type"],
            full_text="Synced data from HANA table",
            connection_config=sample_hana_table_source["connection_config"],
            sync_config=sample_hana_table_source["sync_config"]
        )

        await source.save()

        assert source.source_type == "hana_table"
        assert source.connection_config is not None
        assert source.sync_config is not None

        # Verify JSON serialization
        retrieved = await Source.get(source.id)
        assert retrieved.connection_config["table"] == "SALES_DATA"
        assert retrieved.sync_config["frequency"] == "0 */6 * * *"

    async def test_source_create_api(self, sqlite_db, sample_api_source):
        """Test creating an API source."""
        source = Source(
            title=sample_api_source["title"],
            source_type=sample_api_source["source_type"],
            full_text="Data from API",
            connection_config=sample_api_source["connection_config"],
            sync_config=sample_api_source["sync_config"]
        )

        await source.save()

        assert source.source_type == "api"
        assert source.connection_config["endpoint"] is not None
        assert source.connection_config["auth_type"] == "bearer"

    async def test_source_topics_as_json(self, sqlite_db):
        """Test storing topics as JSON."""
        topics = ["machine learning", "neural networks", "AI"]

        source = Source(
            title="ML Document",
            source_type="text",
            full_text="Content about ML",
            topics=topics
        )

        await source.save()

        # Retrieve and verify
        retrieved = await Source.get(source.id)
        assert retrieved.topics == topics

    async def test_source_update_sync_config(self, sqlite_db, sample_api_source):
        """Test updating sync configuration."""
        source = Source(
            title="API Source",
            source_type="api",
            connection_config=sample_api_source["connection_config"],
            sync_config={"status": "idle", "last_sync": None}
        )
        await source.save()

        # Update sync config
        source.sync_config["status"] = "syncing"
        source.sync_config["last_sync"] = datetime.utcnow().isoformat()

        await source.save()

        # Verify update
        retrieved = await Source.get(source.id)
        assert retrieved.sync_config["status"] == "syncing"
        assert retrieved.sync_config["last_sync"] is not None

    async def test_source_get_notebooks(self, sqlite_db):
        """Test retrieving notebooks associated with a source."""
        # Create source
        source = Source(
            title="Shared Source",
            source_type="text",
            full_text="Content"
        )
        await source.save()

        # Create notebooks and link
        notebook1 = Notebook(name="Notebook 1")
        await notebook1.save()
        await notebook1.add_source(source.id)

        notebook2 = Notebook(name="Notebook 2")
        await notebook2.save()
        await notebook2.add_source(source.id)

        # Get notebooks
        notebooks = await source.get_notebooks()

        assert len(notebooks) == 2
        assert set(nb.id for nb in notebooks) == {notebook1.id, notebook2.id}

    async def test_source_delete_orphan_check(self, sqlite_db):
        """Test that deleting a source doesn't delete notebooks."""
        # Create notebook and source
        notebook = Notebook(name="Test Notebook")
        await notebook.save()

        source = Source(
            title="Test Source",
            source_type="text",
            full_text="Content"
        )
        await source.save()
        await notebook.add_source(source.id)

        # Delete source
        await source.delete()

        # Notebook should still exist
        retrieved_notebook = await Notebook.get(notebook.id)
        assert retrieved_notebook is not None

        # Source should be gone
        retrieved_source = await Source.get(source.id)
        assert retrieved_source is None


@pytest.mark.asyncio
class TestNoteModel:
    """Test Note domain model."""

    async def test_note_create(self, sqlite_db):
        """Test creating a note."""
        note = Note(
            title="Research Finding",
            summary="Key insight from research",
            content="Detailed content of the note"
        )

        await note.save()

        assert note.id is not None
        assert note.created is not None

    async def test_note_update(self, sqlite_db):
        """Test updating a note."""
        note = Note(
            title="Original Title",
            content="Original content"
        )
        await note.save()

        # Update
        note.title = "Updated Title"
        note.content = "Updated content"
        await note.save()

        # Verify
        retrieved = await Note.get(note.id)
        assert retrieved.title == "Updated Title"
        assert retrieved.content == "Updated content"

    async def test_note_get_notebooks(self, sqlite_db):
        """Test retrieving notebooks associated with a note."""
        # Create note
        note = Note(
            title="Shared Note",
            content="Content"
        )
        await note.save()

        # Create notebooks and link
        notebook1 = Notebook(name="Notebook 1")
        await notebook1.save()
        await notebook1.add_note(note.id)

        notebook2 = Notebook(name="Notebook 2")
        await notebook2.save()
        await notebook2.add_note(note.id)

        # Get notebooks
        notebooks = await note.get_notebooks()

        assert len(notebooks) == 2


@pytest.mark.asyncio
class TestRelationshipQueries:
    """Test relationship queries between models."""

    async def test_many_to_many_notebook_source(self, sqlite_db):
        """Test many-to-many relationship between notebooks and sources."""
        # Create notebooks
        notebook1 = Notebook(name="Notebook 1")
        await notebook1.save()

        notebook2 = Notebook(name="Notebook 2")
        await notebook2.save()

        # Create sources
        source1 = Source(title="Source 1", source_type="text", full_text="Content 1")
        await source1.save()

        source2 = Source(title="Source 2", source_type="text", full_text="Content 2")
        await source2.save()

        # Link notebook1 to both sources
        await notebook1.add_source(source1.id)
        await notebook1.add_source(source2.id)

        # Link notebook2 to source1 only
        await notebook2.add_source(source1.id)

        # Verify notebook1 sources
        notebook1_sources = await notebook1.get_sources()
        assert len(notebook1_sources) == 2

        # Verify notebook2 sources
        notebook2_sources = await notebook2.get_sources()
        assert len(notebook2_sources) == 1

        # Verify source1 notebooks
        source1_notebooks = await source1.get_notebooks()
        assert len(source1_notebooks) == 2

    async def test_remove_relationship(self, sqlite_db):
        """Test removing relationships without deleting entities."""
        notebook = Notebook(name="Test Notebook")
        await notebook.save()

        source = Source(title="Test Source", source_type="text", full_text="Content")
        await source.save()

        # Add relationship
        await notebook.add_source(source.id)

        sources = await notebook.get_sources()
        assert len(sources) == 1

        # Remove relationship
        await notebook.remove_source(source.id)

        sources = await notebook.get_sources()
        assert len(sources) == 0

        # Both entities should still exist
        assert await Notebook.get(notebook.id) is not None
        assert await Source.get(source.id) is not None

    async def test_get_delete_preview(self, sqlite_db):
        """Test delete preview showing what will be deleted."""
        # Create notebook with related entities
        notebook = Notebook(name="Test Notebook")
        await notebook.save()

        # Add sources
        for i in range(3):
            source = Source(title=f"Source {i}", source_type="text", full_text="Content")
            await source.save()
            await notebook.add_source(source.id)

        # Add notes
        for i in range(2):
            note = Note(title=f"Note {i}", content="Content")
            await note.save()
            await notebook.add_note(note.id)

        # Get delete preview
        preview = await notebook.get_delete_preview()

        assert preview["notebook_id"] == notebook.id
        assert preview["source_count"] == 3
        assert preview["note_count"] == 2
        assert preview["cascade_relationships"] == True


@pytest.mark.asyncio
class TestModelValidation:
    """Test model validation and error handling."""

    async def test_notebook_required_fields(self, sqlite_db):
        """Test that required fields are validated."""
        with pytest.raises(ValueError):
            notebook = Notebook()  # Missing required 'name'
            await notebook.save()

    async def test_source_invalid_type(self, sqlite_db):
        """Test validation of source_type enum."""
        source = Source(
            title="Test",
            source_type="invalid_type",  # Invalid
            full_text="Content"
        )

        with pytest.raises(ValueError):
            await source.save()

    async def test_source_type_validation(self, sqlite_db):
        """Test that source type is validated."""
        valid_types = ["file", "url", "text", "youtube", "hana_table", "api"]

        for source_type in valid_types:
            source = Source(
                title=f"Test {source_type}",
                source_type=source_type,
                full_text="Content"
            )
            await source.save()
            assert source.id is not None


@pytest.mark.asyncio
class TestTimestamps:
    """Test automatic timestamp management."""

    async def test_created_timestamp_automatic(self, sqlite_db):
        """Test that created timestamp is set automatically."""
        notebook = Notebook(name="Test")
        await notebook.save()

        assert notebook.created is not None
        assert isinstance(notebook.created, datetime)

    async def test_updated_timestamp_on_create(self, sqlite_db):
        """Test that updated timestamp is set on creation."""
        notebook = Notebook(name="Test")
        await notebook.save()

        assert notebook.updated is not None
        assert notebook.updated >= notebook.created

    async def test_updated_timestamp_on_update(self, sqlite_db):
        """Test that updated timestamp changes on update."""
        notebook = Notebook(name="Original")
        await notebook.save()

        original_updated = notebook.updated

        # Wait a moment and update
        import asyncio
        await asyncio.sleep(0.1)

        notebook.name = "Updated"
        await notebook.save()

        assert notebook.updated > original_updated

    async def test_created_timestamp_immutable(self, sqlite_db):
        """Test that created timestamp doesn't change on update."""
        notebook = Notebook(name="Test")
        await notebook.save()

        original_created = notebook.created

        # Update
        notebook.name = "Updated"
        await notebook.save()

        assert notebook.created == original_created
