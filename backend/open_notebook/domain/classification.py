"""
Classification domain models.

Represents hierarchical classification taxonomy for sources with approval workflow.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import Field, field_validator

from open_notebook.database.repository import repo_create, repo_delete, repo_query, repo_update
from open_notebook.domain.base import ObjectModel


class Classification(ObjectModel):
    """
    Classification represents a taxonomy node (category/topic/project/subtopic).

    Hierarchical structure:
    - Level 0: Categories (e.g., "Engineering", "Marketing")
    - Level 1: Topics/Projects (e.g., "Machine Learning", "Customer Dashboard")
    - Level 2: Subtopics (e.g., "Neural Networks", "User Auth")
    """

    _table_name = "classification_types"

    name: str
    description: Optional[str] = None
    classification_type: str  # 'category', 'topic', 'project', 'subtopic'
    parent_id: Optional[str] = None
    level: int = 0  # 0, 1, or 2
    color: Optional[str] = None
    icon: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('metadata', mode='before')
    @classmethod
    def parse_metadata(cls, v: Union[str, Dict, None]) -> Dict[str, Any]:
        """Parse metadata from JSON string if needed"""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            if not v or v == '{}':
                return {}
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    async def save(self) -> str:
        """Override save to serialize metadata as JSON"""
        now = datetime.utcnow()

        # Convert model to dict
        data = self.model_dump(exclude_none=True)

        # Serialize metadata as JSON string
        if 'metadata' in data and isinstance(data['metadata'], dict):
            data['metadata'] = json.dumps(data['metadata'])

        if self.id is None:
            # Create new record
            self.id = str(uuid.uuid4())
            self.created = now
            self.updated = now

            data["id"] = self.id
            data["created"] = self.created.isoformat()
            data["updated"] = self.updated.isoformat()

            await repo_create(self._table_name, data)
        else:
            # Update existing record
            self.updated = now
            data["updated"] = self.updated.isoformat()

            await repo_update(self._table_name, self.id, data)

        return self.id

    @staticmethod
    async def get_by_name(name: str, classification_type: str, level: Optional[int] = None) -> Optional["Classification"]:
        """
        Get classification by name and type, or create if doesn't exist.

        Args:
            name: Classification name
            classification_type: Type (category, topic, project, subtopic)
            level: Optional level filter

        Returns:
            Classification instance or None
        """
        query = """
            SELECT * FROM classification_types
            WHERE name = :name AND classification_type = :classification_type
        """
        params = {"name": name, "classification_type": classification_type}

        if level is not None:
            query += " AND level = :level"
            params["level"] = level

        query += " LIMIT 1"

        results = await repo_query(query, params)
        if results:
            return Classification(**results[0])
        return None

    @staticmethod
    async def get_or_create(
        name: str,
        classification_type: str,
        level: int,
        parent_id: Optional[str] = None,
        **kwargs
    ) -> "Classification":
        """
        Get existing classification or create new one.

        Args:
            name: Classification name
            classification_type: Type
            level: Hierarchy level (0-2)
            parent_id: Optional parent classification ID
            **kwargs: Additional fields (description, color, icon, metadata)

        Returns:
            Classification instance
        """
        existing = await Classification.get_by_name(name, classification_type, level)
        if existing:
            return existing

        # Create new classification
        classification = Classification(
            name=name,
            classification_type=classification_type,
            level=level,
            parent_id=parent_id,
            **kwargs
        )
        await classification.save()
        return classification

    async def get_sources(self, status: Optional[str] = "approved") -> List[Dict[str, Any]]:
        """
        Get all sources linked to this classification.

        Args:
            status: Filter by approval status ('pending', 'approved', 'rejected', None for all)

        Returns:
            List of source dictionaries with classification metadata
        """
        if self.id is None:
            return []

        query = """
            SELECT s.*, sc.confidence, sc.status, sc.approved_by, sc.approved_at
            FROM sources s
            INNER JOIN source_classifications sc ON s.id = sc.source_id
            WHERE sc.classification_id = :classification_id
        """
        params = {"classification_id": self.id}

        if status:
            query += " AND sc.status = :status"
            params["status"] = status

        query += " ORDER BY sc.confidence DESC, s.created DESC"

        return await repo_query(query, params)

    async def get_children(self) -> List["Classification"]:
        """
        Get child classifications (one level down in hierarchy).

        Returns:
            List of child Classification instances
        """
        if self.id is None:
            return []

        results = await repo_query(
            "SELECT * FROM classification_types WHERE parent_id = :parent_id ORDER BY name",
            {"parent_id": self.id}
        )
        return [Classification(**row) for row in results]

    async def get_related_classifications(self, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get related classification nodes via classification_relationships table.

        Args:
            relationship_type: Filter by type ('parent_child', 'related', 'similar', None for all)

        Returns:
            List of classification dicts with relationship metadata
        """
        if self.id is None:
            return []

        query = """
            SELECT c.*, cr.relationship_type, cr.strength
            FROM classification_types c
            INNER JOIN classification_relationships cr ON (
                c.id = cr.target_classification_id OR c.id = cr.source_classification_id
            )
            WHERE (cr.source_classification_id = :classification_id OR cr.target_classification_id = :classification_id)
            AND c.id != :classification_id
        """
        params = {"classification_id": self.id}

        if relationship_type:
            query += " AND cr.relationship_type = :relationship_type"
            params["relationship_type"] = relationship_type

        return await repo_query(query, params)


class SourceClassification(ObjectModel):
    """
    Links a source to a classification with approval workflow.
    """

    _table_name = "source_classifications"

    source_id: str
    classification_id: str
    confidence: float = 0.0  # 0.0-1.0
    status: str = "pending"  # 'pending', 'approved', 'rejected'
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('metadata', mode='before')
    @classmethod
    def parse_metadata(cls, v: Union[str, Dict, None]) -> Dict[str, Any]:
        """Parse metadata from JSON string if needed"""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            if not v or v == '{}':
                return {}
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    async def save(self) -> str:
        """Override save to serialize metadata as JSON"""
        now = datetime.utcnow()

        # Convert model to dict
        data = self.model_dump(exclude_none=True)

        # Serialize metadata as JSON string
        if 'metadata' in data and isinstance(data['metadata'], dict):
            data['metadata'] = json.dumps(data['metadata'])

        # Convert datetime to ISO string
        if 'approved_at' in data and data['approved_at']:
            data['approved_at'] = data['approved_at'].isoformat() if isinstance(data['approved_at'], datetime) else data['approved_at']

        if self.id is None:
            # Create new record
            self.id = str(uuid.uuid4())
            self.created = now
            self.updated = now

            data["id"] = self.id
            data["created"] = self.created.isoformat()
            data["updated"] = self.updated.isoformat()

            await repo_create(self._table_name, data)
        else:
            # Update existing record
            self.updated = now
            data["updated"] = self.updated.isoformat()

            await repo_update(self._table_name, self.id, data)

        return self.id

    async def approve(self, user_id: str) -> None:
        """Approve this classification"""
        self.status = "approved"
        self.approved_by = user_id
        self.approved_at = datetime.utcnow()
        await self.save()

    async def reject(self, user_id: str) -> None:
        """Reject this classification"""
        self.status = "rejected"
        self.approved_by = user_id
        self.approved_at = datetime.utcnow()
        await self.save()

    @staticmethod
    async def get_pending_for_source(source_id: str) -> List["SourceClassification"]:
        """Get all pending classifications for a source"""
        results = await repo_query(
            "SELECT * FROM source_classifications WHERE source_id = :source_id AND status = 'pending' ORDER BY confidence DESC",
            {"source_id": source_id}
        )
        return [SourceClassification(**row) for row in results]

    @staticmethod
    async def get_all_pending(min_confidence: float = 0.0) -> List[Dict[str, Any]]:
        """
        Get all pending classifications with classification details.

        Args:
            min_confidence: Minimum confidence threshold

        Returns:
            List of dicts with source_classification + classification_type data
        """
        query = """
            SELECT sc.*, ct.name, ct.description, ct.classification_type, ct.level, ct.parent_id
            FROM source_classifications sc
            INNER JOIN classification_types ct ON sc.classification_id = ct.id
            WHERE sc.status = 'pending' AND sc.confidence >= :min_confidence
            ORDER BY sc.confidence DESC, sc.created DESC
        """
        return await repo_query(query, {"min_confidence": min_confidence})
