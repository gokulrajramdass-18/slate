"""
Notebook domain models.

Includes Notebook, Source, and Note entities with their relationships.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import Field, field_validator

from open_notebook.database.repository import repo_delete, repo_query
from open_notebook.domain.base import ObjectModel


class Notebook(ObjectModel):
    """
    Notebook represents a research project or collection of sources.

    A notebook can contain multiple sources and notes, and can be organized
    into folders with tags.
    """

    _table_name = "notebooks"

    name: str
    description: Optional[str] = None
    archived: bool = False
    folder_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    goal: Optional[str] = None  # Workspace goal (optional in DB for backward compatibility)
    protected: bool = False  # Protection flag to prevent deletion during critical operations

    @field_validator('tags', mode='before')
    @classmethod
    def parse_tags(cls, v: Union[str, List[str], None]) -> List[str]:
        """Parse tags from JSON string if needed"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if not v or v == '[]':
                return []
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def model_post_init(self, __context: Any) -> None:
        """Initialize model after construction"""
        super().model_post_init(__context)

    async def save(self) -> str:
        """Override save to serialize tags as JSON"""
        from open_notebook.database.repository import repo_create, repo_update
        import uuid

        now = datetime.utcnow()

        # Convert model to dict
        data = self.model_dump(exclude_none=True)

        # Serialize tags as JSON string
        if 'tags' in data and isinstance(data['tags'], list):
            data['tags'] = json.dumps(data['tags'])

        if self.id is None:
            # Create new record
            self.id = str(uuid.uuid4())
            self.created = now
            self.updated = now

            data["id"] = self.id
            data["created"] = self.created
            data["updated"] = self.updated

            await repo_create(self._table_name, data)
        else:
            # Update existing record
            self.updated = now
            data["updated"] = self.updated

            await repo_update(self._table_name, self.id, data)

        return self.id

    async def get_sources(self) -> List["Source"]:
        """
        Get all sources in this notebook.

        Returns:
            List of Source instances
        """
        if self.id is None:
            return []

        sql = """
            SELECT s.*
            FROM sources s
            INNER JOIN notebook_source ns ON s.id = ns.source_id
            WHERE ns.notebook_id = :notebook_id
            ORDER BY ns.created DESC
        """

        results = await repo_query(sql, {"notebook_id": self.id})

        # Parse JSON fields before creating Source instances
        sources = []
        for row in results:
            row_dict = dict(row)
            # Parse JSON string fields
            for field in ['connection_config', 'sync_config', 'topics']:
                if row_dict.get(field) and isinstance(row_dict[field], str):
                    try:
                        row_dict[field] = json.loads(row_dict[field])
                    except (json.JSONDecodeError, TypeError):
                        row_dict[field] = None if field != 'topics' else []
            sources.append(Source(**row_dict))

        return sources

    async def add_source(self, source_id: str) -> None:
        """
        Add a source to this notebook.

        Args:
            source_id: Source ID to add
        """
        if self.id is None:
            raise ValueError("Cannot add source to unsaved notebook")

        from open_notebook.database.repository import repo_create

        await repo_create(
            "notebook_source",
            {
                "notebook_id": self.id,
                "source_id": source_id,
                "created": datetime.utcnow(),
            },
        )

    async def remove_source(self, source_id: str) -> None:
        """
        Remove a source from this notebook.

        Args:
            source_id: Source ID to remove
        """
        if self.id is None:
            raise ValueError("Cannot remove source from unsaved notebook")

        sql = """
            DELETE FROM notebook_source
            WHERE notebook_id = :notebook_id AND source_id = :source_id
        """

        await repo_query(sql, {"notebook_id": self.id, "source_id": source_id})

    async def get_notes(self) -> List["Note"]:
        """
        Get all notes in this notebook.

        Returns:
            List of Note instances
        """
        if self.id is None:
            return []

        sql = """
            SELECT n.*
            FROM notes n
            INNER JOIN notebook_note nn ON n.id = nn.note_id
            WHERE nn.notebook_id = :notebook_id
            ORDER BY nn.created DESC
        """

        results = await repo_query(sql, {"notebook_id": self.id})
        return [Note(**row) for row in results]

    async def add_note(self, note_id: str) -> None:
        """
        Add a note to this notebook.

        Args:
            note_id: Note ID to add
        """
        if self.id is None:
            raise ValueError("Cannot add note to unsaved notebook")

        from open_notebook.database.repository import repo_create

        await repo_create(
            "notebook_note",
            {
                "notebook_id": self.id,
                "note_id": note_id,
                "created": datetime.utcnow(),
            },
        )

    async def remove_note(self, note_id: str) -> None:
        """
        Remove a note from this notebook.

        Args:
            note_id: Note ID to remove
        """
        if self.id is None:
            raise ValueError("Cannot remove note from unsaved notebook")

        sql = """
            DELETE FROM notebook_note
            WHERE notebook_id = :notebook_id AND note_id = :note_id
        """

        await repo_query(sql, {"notebook_id": self.id, "note_id": note_id})

    async def get_chat_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all chat sessions for this notebook.

        Returns:
            List of chat session dictionaries
        """
        if self.id is None:
            return []

        sql = """
            SELECT *
            FROM chat_sessions
            WHERE notebook_id = :notebook_id
            ORDER BY updated DESC
        """

        return await repo_query(sql, {"notebook_id": self.id})

    async def get_delete_preview(self) -> Dict[str, int]:
        """
        Get count of items that will be deleted with this notebook.

        Returns:
            Dictionary with counts of sources, notes, and chat_sessions
        """
        if self.id is None:
            return {"sources": 0, "notes": 0, "chat_sessions": 0}

        # Count sources (junction table entries, not actual sources)
        sources_sql = """
            SELECT COUNT(*) as count
            FROM notebook_source
            WHERE notebook_id = :notebook_id
        """
        sources_result = await repo_query(sources_sql, {"notebook_id": self.id})

        # Count notes (junction table entries, not actual notes)
        notes_sql = """
            SELECT COUNT(*) as count
            FROM notebook_note
            WHERE notebook_id = :notebook_id
        """
        notes_result = await repo_query(notes_sql, {"notebook_id": self.id})

        # Count chat sessions (will be cascade deleted)
        sessions_sql = """
            SELECT COUNT(*) as count
            FROM chat_sessions
            WHERE notebook_id = :notebook_id
        """
        sessions_result = await repo_query(sessions_sql, {"notebook_id": self.id})

        return {
            "sources": sources_result[0]["count"] if sources_result else 0,
            "notes": notes_result[0]["count"] if notes_result else 0,
            "chat_sessions": sessions_result[0]["count"] if sessions_result else 0,
        }

    async def delete(self) -> None:
        """
        Delete the notebook and cascade delete related records.

        This will delete:
        - Junction table entries (notebook_source, notebook_note, notebook_tags)
        - Chat sessions and their messages
        - The notebook record itself

        Note: Sources and Notes are NOT deleted, only the relationships.

        CRITICAL: Protected workspaces CANNOT be deleted. This prevents accidental
        deletion during template execution or other critical operations.
        """
        if self.id is None:
            raise ValueError("Cannot delete unsaved notebook")

        # CRITICAL: Check if workspace is protected
        if self.protected:
            raise ValueError(
                f"Cannot delete workspace '{self.name}' (ID: {self.id}): "
                f"Workspace is protected. This workspace is currently being used by "
                f"a template execution or other critical operation. "
                f"Please try again later or remove protection manually."
            )

        # The database handles cascade deletes via foreign key constraints
        # So we just need to delete the notebook itself
        await repo_delete(self._table_name, self.id)


class Source(ObjectModel):
    """
    Source represents content from various sources.

    Source types:
    - file: Uploaded files (PDF, DOCX, etc.)
    - url: Web pages
    - text: Direct text input
    - youtube: YouTube videos (with transcripts)
    - hana_table: SAP HANA database table
    - api: API endpoint (with authentication)
    """

    _table_name = "sources"

    title: Optional[str] = None
    topics: Optional[List[str]] = Field(default_factory=list)
    full_text: Optional[str] = None
    source_type: str = "text"  # file, url, text, youtube, hana_table, api
    asset_type: Optional[str] = None
    asset_data: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None  # encrypted credentials
    sync_config: Optional[Dict[str, Any]] = None  # sync settings
    tags: List[str] = Field(default_factory=list)  # tags for organization

    @field_validator('tags', mode='before')
    @classmethod
    def parse_tags(cls, v: Union[str, List[str], None]) -> List[str]:
        """Parse tags from JSON string if needed"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if not v or v == '[]':
                return []
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    async def save(self) -> str:
        """
        Save the source to the database.

        Handles JSON serialization for topics, connection_config, sync_config, and tags.
        """
        # Serialize JSON fields before saving
        data = self.model_dump(exclude_none=True)

        # Convert lists and dicts to JSON strings for database storage
        if "topics" in data and data["topics"]:
            data["topics"] = json.dumps(data["topics"])

        if "connection_config" in data and data["connection_config"]:
            data["connection_config"] = json.dumps(data["connection_config"])

        if "sync_config" in data and data["sync_config"]:
            data["sync_config"] = json.dumps(data["sync_config"])

        if "tags" in data and isinstance(data["tags"], list):
            data["tags"] = json.dumps(data["tags"])

        # Call parent save with serialized data
        if self.id is None:
            import uuid
            from datetime import datetime

            self.id = str(uuid.uuid4())
            self.created = datetime.utcnow()
            self.updated = datetime.utcnow()

            data["id"] = self.id
            data["created"] = self.created
            data["updated"] = self.updated

            from open_notebook.database.repository import repo_create

            await repo_create(self._table_name, data)
        else:
            from datetime import datetime

            self.updated = datetime.utcnow()
            data["updated"] = self.updated

            record_id = data.pop("id")

            from open_notebook.database.repository import repo_update

            await repo_update(self._table_name, record_id, data)

        return self.id

    @classmethod
    async def get(cls, id: str) -> Optional["Source"]:
        """
        Get a source by ID with JSON deserialization.

        Args:
            id: Source ID

        Returns:
            Source instance or None
        """
        sql = f"SELECT * FROM {cls._table_name} WHERE id = :id"
        results = await repo_query(sql, {"id": id})

        if not results:
            return None

        row = results[0]

        # Deserialize JSON fields
        if row.get("topics") and isinstance(row["topics"], str):
            try:
                row["topics"] = json.loads(row["topics"])
            except json.JSONDecodeError:
                row["topics"] = []

        if row.get("connection_config") and isinstance(row["connection_config"], str):
            try:
                row["connection_config"] = json.loads(row["connection_config"])
            except json.JSONDecodeError:
                row["connection_config"] = None

        if row.get("sync_config") and isinstance(row["sync_config"], str):
            try:
                row["sync_config"] = json.loads(row["sync_config"])
            except json.JSONDecodeError:
                row["sync_config"] = None

        if row.get("tags") and isinstance(row["tags"], str):
            try:
                row["tags"] = json.loads(row["tags"])
            except json.JSONDecodeError:
                row["tags"] = []

        return cls(**row)

    async def get_embeddings(self) -> List[Dict[str, Any]]:
        """
        Get all embeddings for this source.

        Returns:
            List of embedding dictionaries
        """
        if self.id is None:
            return []

        sql = """
            SELECT *
            FROM source_embeddings
            WHERE source_id = :source_id
            ORDER BY order_num
        """

        return await repo_query(sql, {"source_id": self.id})

    async def delete_embeddings(self) -> None:
        """
        Delete all embeddings for this source.
        """
        if self.id is None:
            return

        sql = "DELETE FROM source_embeddings WHERE source_id = :source_id"
        await repo_query(sql, {"source_id": self.id})


class Note(ObjectModel):
    """
    Note represents user-created or AI-generated insights.

    Notes can be associated with multiple notebooks and can have
    embeddings for semantic search. Notes can be organized in folders.
    """

    _table_name = "notes"

    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    content_html: Optional[str] = None
    folder_id: Optional[str] = None  # NEW: Folder organization
    metadata: Optional[str] = None  # JSON metadata
    notebook_id: Optional[str] = None  # Primary notebook
    embedding: Optional[bytes] = None  # Serialized vector for semantic search

    async def get_notebooks(self) -> List[Notebook]:
        """
        Get all notebooks containing this note.

        Returns:
            List of Notebook instances
        """
        if self.id is None:
            return []

        sql = """
            SELECT n.*
            FROM notebooks n
            INNER JOIN notebook_note nn ON n.id = nn.notebook_id
            WHERE nn.note_id = :note_id
            ORDER BY nn.created DESC
        """

        results = await repo_query(sql, {"note_id": self.id})
        return [Notebook(**row) for row in results]
