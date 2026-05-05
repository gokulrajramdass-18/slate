"""
Domain models for the Microsite Generator feature.

Includes models for templates, content sections, versions,
moderation logs, and content blocklist entries.
All models inherit from ObjectModel for CRUD operations.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import Field, field_validator

from open_notebook.database.repository import repo_query
from open_notebook.domain.base import ObjectModel


class MicrositeTemplate(ObjectModel):
    """
    Pre-built or custom template defining microsite structure and styling.

    Built-in templates: blog, documentation, portfolio, landing_page, report.
    Users can duplicate and customize templates (is_custom=True).
    """

    _table_name = "microsite_templates"

    name: str
    display_name: str
    description: Optional[str] = None
    structure: Optional[str] = None       # JSON string: sections, layout, prompts
    default_styles: Optional[str] = None  # JSON string: CSS variables, fonts, colors
    preview_image: Optional[str] = None
    is_custom: bool = False

    @field_validator("is_custom", mode="before")
    @classmethod
    def parse_is_custom(cls, v: Any) -> bool:
        if isinstance(v, int):
            return bool(v)
        return v

    def get_structure(self) -> Dict[str, Any]:
        """Parse the structure JSON into a dictionary."""
        if not self.structure:
            return {}
        if isinstance(self.structure, dict):
            return self.structure
        try:
            return json.loads(self.structure)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_structure(self, data: Dict[str, Any]) -> None:
        """Serialize a dictionary into the structure JSON field."""
        self.structure = json.dumps(data)

    def get_styles(self) -> Dict[str, Any]:
        """Parse the default_styles JSON into a dictionary."""
        if not self.default_styles:
            return {}
        if isinstance(self.default_styles, dict):
            return self.default_styles
        try:
            return json.loads(self.default_styles)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_styles(self, data: Dict[str, Any]) -> None:
        """Serialize a dictionary into the default_styles JSON field."""
        self.default_styles = json.dumps(data)

    def get_sections(self) -> List[Dict[str, Any]]:
        """Get the list of section definitions from the template structure."""
        structure = self.get_structure()
        return structure.get("sections", [])

    async def save(self) -> str:
        """Override save to serialize JSON fields."""
        import uuid as _uuid
        from open_notebook.database.repository import repo_create, repo_update

        now = datetime.utcnow()
        data = self.model_dump(exclude_none=True)

        # Serialize dict fields to JSON strings
        for field_name in ("structure", "default_styles"):
            if field_name in data and isinstance(data[field_name], dict):
                data[field_name] = json.dumps(data[field_name])

        # Convert bool to int for SQLite
        if "is_custom" in data:
            data["is_custom"] = int(data["is_custom"])

        if self.id is None:
            self.id = str(_uuid.uuid4())
            self.created = now
            self.updated = now
            data["id"] = self.id
            data["created"] = self.created
            data["updated"] = self.updated
            await repo_create(self._table_name, data)
        else:
            self.updated = now
            data["updated"] = self.updated
            record_id = data.pop("id")
            await repo_update(self._table_name, record_id, data)

        return self.id


class MicrositeContent(ObjectModel):
    """
    Individual content section within a microsite.

    Stores content in dual format:
    - content_html: Rendered HTML for display and code editing
    - content_json: TipTap JSON for WYSIWYG editing
    """

    _table_name = "microsite_content"

    microsite_id: str
    section_id: str
    content_html: Optional[str] = None
    content_json: Optional[str] = None  # TipTap JSON string
    order_num: int = 0
    is_visible: bool = True

    @field_validator("is_visible", mode="before")
    @classmethod
    def parse_is_visible(cls, v: Any) -> bool:
        if isinstance(v, int):
            return bool(v)
        return v

    def get_tiptap_json(self) -> Dict[str, Any]:
        """Parse the content_json field into a TipTap document structure."""
        if not self.content_json:
            return {}
        if isinstance(self.content_json, dict):
            return self.content_json
        try:
            return json.loads(self.content_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_tiptap_json(self, data: Dict[str, Any]) -> None:
        """Serialize a TipTap document structure into the content_json field."""
        self.content_json = json.dumps(data)

    async def save(self) -> str:
        """Override save to handle JSON and boolean serialization."""
        import uuid as _uuid
        from open_notebook.database.repository import repo_create, repo_update

        now = datetime.utcnow()
        data = self.model_dump(exclude_none=True)

        # Serialize dict to JSON string
        if "content_json" in data and isinstance(data["content_json"], dict):
            data["content_json"] = json.dumps(data["content_json"])

        # Convert bool to int for SQLite
        if "is_visible" in data:
            data["is_visible"] = int(data["is_visible"])

        if self.id is None:
            self.id = str(_uuid.uuid4())
            self.created = now
            self.updated = now
            data["id"] = self.id
            data["created"] = self.created
            data["updated"] = self.updated
            await repo_create(self._table_name, data)
        else:
            self.updated = now
            data["updated"] = self.updated
            record_id = data.pop("id")
            await repo_update(self._table_name, record_id, data)

        return self.id

    @classmethod
    async def get_by_microsite(
        cls, microsite_id: str, visible_only: bool = False
    ) -> List["MicrositeContent"]:
        """
        Get all content sections for a microsite, ordered by order_num.

        Args:
            microsite_id: The microsite to get content for
            visible_only: If True, only return visible sections
        """
        sql = "SELECT * FROM microsite_content WHERE microsite_id = :microsite_id"
        params: Dict[str, Any] = {"microsite_id": microsite_id}

        if visible_only:
            sql += " AND is_visible = 1"

        sql += " ORDER BY order_num ASC"

        results = await repo_query(sql, params)
        return [cls(**row) for row in results]


class MicrositeVersion(ObjectModel):
    """
    Snapshot of a microsite at a point in time for rollback capability.

    Stores the complete rendered HTML/CSS and a JSON snapshot of all
    content sections at the time of creation.
    """

    _table_name = "microsite_versions"
    _exclude_fields = ["updated"]  # Versions are immutable, no updated field

    microsite_id: str
    version_number: int
    full_html: Optional[str] = None
    full_css: Optional[str] = None
    content_snapshot: Optional[str] = None  # JSON string
    created_by: Optional[str] = None

    def get_content_snapshot(self) -> List[Dict[str, Any]]:
        """Parse the content_snapshot JSON into a list of section data."""
        if not self.content_snapshot:
            return []
        if isinstance(self.content_snapshot, list):
            return self.content_snapshot
        try:
            parsed = json.loads(self.content_snapshot)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_content_snapshot(self, data: List[Dict[str, Any]]) -> None:
        """Serialize section data list into the content_snapshot JSON field."""
        self.content_snapshot = json.dumps(data)

    async def save(self) -> str:
        """Override save to handle JSON serialization."""
        import uuid as _uuid
        from open_notebook.database.repository import repo_create, repo_update

        now = datetime.utcnow()
        data = self.model_dump(exclude_none=True)

        # Serialize list/dict to JSON string
        if "content_snapshot" in data and isinstance(data["content_snapshot"], (list, dict)):
            data["content_snapshot"] = json.dumps(data["content_snapshot"])

        # Remove updated since versions are immutable
        data.pop("updated", None)

        if self.id is None:
            self.id = str(_uuid.uuid4())
            self.created = now
            data["id"] = self.id
            data["created"] = self.created
            await repo_create(self._table_name, data)
        else:
            record_id = data.pop("id")
            await repo_update(self._table_name, record_id, data)

        return self.id

    @classmethod
    async def get_latest(cls, microsite_id: str) -> Optional["MicrositeVersion"]:
        """Get the most recent version for a microsite."""
        sql = """
            SELECT * FROM microsite_versions
            WHERE microsite_id = :microsite_id
            ORDER BY version_number DESC
            LIMIT 1
        """
        results = await repo_query(sql, {"microsite_id": microsite_id})
        if not results:
            return None
        return cls(**results[0])

    @classmethod
    async def get_by_number(
        cls, microsite_id: str, version_number: int
    ) -> Optional["MicrositeVersion"]:
        """Get a specific version by microsite ID and version number."""
        sql = """
            SELECT * FROM microsite_versions
            WHERE microsite_id = :microsite_id AND version_number = :version_number
        """
        results = await repo_query(sql, {
            "microsite_id": microsite_id,
            "version_number": version_number,
        })
        if not results:
            return None
        return cls(**results[0])

    @classmethod
    async def get_all_for_microsite(cls, microsite_id: str) -> List["MicrositeVersion"]:
        """Get all versions for a microsite, ordered by version number descending."""
        sql = """
            SELECT * FROM microsite_versions
            WHERE microsite_id = :microsite_id
            ORDER BY version_number DESC
        """
        results = await repo_query(sql, {"microsite_id": microsite_id})
        return [cls(**row) for row in results]

    @classmethod
    async def get_next_version_number(cls, microsite_id: str) -> int:
        """Get the next version number for a microsite."""
        sql = """
            SELECT MAX(version_number) as max_version
            FROM microsite_versions
            WHERE microsite_id = :microsite_id
        """
        results = await repo_query(sql, {"microsite_id": microsite_id})
        if not results or results[0]["max_version"] is None:
            return 1
        return results[0]["max_version"] + 1


class ModerationLog(ObjectModel):
    """
    Audit trail entry for content moderation.

    Records the result of each moderation layer (AI filter, keyword blocklist,
    source validation, user review) applied to a microsite or section.
    """

    _table_name = "content_moderation_logs"
    _exclude_fields = ["updated"]  # Logs are immutable

    microsite_id: str
    content_section: Optional[str] = None  # Section ID or 'full'
    moderation_type: str  # ai_filter, keyword_blocklist, source_validation, user_review
    status: str  # passed, warning, blocked
    score: Optional[float] = None
    issues_found: Optional[str] = None  # JSON string
    metadata: Optional[str] = None      # JSON string

    def get_issues(self) -> List[Dict[str, Any]]:
        """Parse the issues_found JSON into a list of issue objects."""
        if not self.issues_found:
            return []
        if isinstance(self.issues_found, list):
            return self.issues_found
        try:
            parsed = json.loads(self.issues_found)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_issues(self, issues: List[Dict[str, Any]]) -> None:
        """Serialize issue objects into the issues_found JSON field."""
        self.issues_found = json.dumps(issues)

    def get_metadata(self) -> Dict[str, Any]:
        """Parse the metadata JSON into a dictionary."""
        if not self.metadata:
            return {}
        if isinstance(self.metadata, dict):
            return self.metadata
        try:
            return json.loads(self.metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_metadata(self, data: Dict[str, Any]) -> None:
        """Serialize a dictionary into the metadata JSON field."""
        self.metadata = json.dumps(data)

    async def save(self) -> str:
        """Override save to handle JSON serialization."""
        import uuid as _uuid
        from open_notebook.database.repository import repo_create, repo_update

        now = datetime.utcnow()
        data = self.model_dump(exclude_none=True)

        # Serialize list/dict to JSON strings
        for field_name in ("issues_found", "metadata"):
            if field_name in data and isinstance(data[field_name], (list, dict)):
                data[field_name] = json.dumps(data[field_name])

        # Remove updated since logs are immutable
        data.pop("updated", None)

        if self.id is None:
            self.id = str(_uuid.uuid4())
            self.created = now
            data["id"] = self.id
            data["created"] = self.created
            await repo_create(self._table_name, data)
        else:
            record_id = data.pop("id")
            await repo_update(self._table_name, record_id, data)

        return self.id

    @classmethod
    async def get_by_microsite(
        cls, microsite_id: str, moderation_type: Optional[str] = None
    ) -> List["ModerationLog"]:
        """
        Get moderation logs for a microsite.

        Args:
            microsite_id: The microsite to get logs for
            moderation_type: Optional filter by moderation type
        """
        sql = "SELECT * FROM content_moderation_logs WHERE microsite_id = :microsite_id"
        params: Dict[str, Any] = {"microsite_id": microsite_id}

        if moderation_type:
            sql += " AND moderation_type = :moderation_type"
            params["moderation_type"] = moderation_type

        sql += " ORDER BY created DESC"

        results = await repo_query(sql, params)
        return [cls(**row) for row in results]


class ContentBlocklist(ObjectModel):
    """
    Keyword or regex pattern for content blocklist filtering.

    Categories: profanity, sensitive, custom
    Severity: block (hard fail) or warning (flag for review)
    """

    _table_name = "content_blocklist"

    keyword: str
    category: str = "custom"
    severity: str = "warning"
    is_regex: bool = False

    @field_validator("is_regex", mode="before")
    @classmethod
    def parse_is_regex(cls, v: Any) -> bool:
        if isinstance(v, int):
            return bool(v)
        return v

    async def save(self) -> str:
        """Override save to convert bool to int for SQLite."""
        import uuid as _uuid
        from open_notebook.database.repository import repo_create, repo_update

        now = datetime.utcnow()
        data = self.model_dump(exclude_none=True)

        # Convert bool to int for SQLite
        if "is_regex" in data:
            data["is_regex"] = int(data["is_regex"])

        if self.id is None:
            self.id = str(_uuid.uuid4())
            self.created = now
            self.updated = now
            data["id"] = self.id
            data["created"] = self.created
            data["updated"] = self.updated
            await repo_create(self._table_name, data)
        else:
            self.updated = now
            data["updated"] = self.updated
            record_id = data.pop("id")
            await repo_update(self._table_name, record_id, data)

        return self.id

    @classmethod
    async def get_by_category(cls, category: str) -> List["ContentBlocklist"]:
        """Get all blocklist entries for a specific category."""
        sql = "SELECT * FROM content_blocklist WHERE category = :category ORDER BY keyword"
        results = await repo_query(sql, {"category": category})
        return [cls(**row) for row in results]

    @classmethod
    async def get_active_patterns(cls) -> List["ContentBlocklist"]:
        """Get all blocklist entries, useful for the moderation pipeline."""
        sql = "SELECT * FROM content_blocklist ORDER BY severity DESC, keyword"
        results = await repo_query(sql)
        return [cls(**row) for row in results]
