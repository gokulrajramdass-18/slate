"""
Folder domain model for organizing workspace content.
"""

import json
import uuid
from datetime import datetime
from typing import ClassVar, List, Optional, Dict, Any

from open_notebook.database.repository import repo_create, repo_query, repo_update, repo_delete
from open_notebook.domain.base import ObjectModel


class Folder(ObjectModel):
    """
    Folder for organizing notes and template executions within a workspace.
    """

    _table_name: ClassVar[str] = "folders"

    name: str
    notebook_id: Optional[str] = None
    parent_id: Optional[str] = None
    folder_type: str = "user"  # 'user', 'system', 'template_executions'
    metadata: Optional[str] = None  # JSON

    @classmethod
    async def get_by_name_and_workspace(cls, name: str, workspace_id: str) -> Optional["Folder"]:
        """Get folder by name within a workspace."""
        sql = """
            SELECT * FROM folders
            WHERE name = :name AND notebook_id = :workspace_id
            LIMIT 1
        """
        result = await repo_query(sql, {"name": name, "workspace_id": workspace_id}, fetch_one=True)
        if result:
            return cls(**dict(result))
        return None

    @classmethod
    async def get_by_name_and_parent(cls, name: str, parent_id: str) -> Optional["Folder"]:
        """Get folder by name within a parent folder."""
        sql = """
            SELECT * FROM folders
            WHERE name = :name AND parent_id = :parent_id
            LIMIT 1
        """
        result = await repo_query(sql, {"name": name, "parent_id": parent_id}, fetch_one=True)
        if result:
            return cls(**dict(result))
        return None

    @classmethod
    async def get_children(cls, parent_id: str) -> List["Folder"]:
        """Get all child folders of a parent."""
        sql = """
            SELECT * FROM folders
            WHERE parent_id = :parent_id
            ORDER BY name
        """
        results = await repo_query(sql, {"parent_id": parent_id})
        return [cls(**dict(row)) for row in results]

    @classmethod
    async def get_workspace_folders(cls, workspace_id: str) -> List["Folder"]:
        """Get all folders in a workspace."""
        sql = """
            SELECT * FROM folders
            WHERE notebook_id = :workspace_id
            ORDER BY name
        """
        results = await repo_query(sql, {"workspace_id": workspace_id})
        return [cls(**dict(row)) for row in results]

    def get_metadata(self) -> Dict[str, Any]:
        """Parse metadata JSON."""
        if not self.metadata:
            return {}
        try:
            return json.loads(self.metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_metadata(self, data: Dict[str, Any]):
        """Set metadata as JSON."""
        self.metadata = json.dumps(data)
