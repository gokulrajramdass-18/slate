"""
Base domain model for Open Notebook.

Provides ObjectModel base class with common functionality for all domain entities.
"""

import uuid
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, Field

from open_notebook.database.repository import (
    repo_create,
    repo_delete,
    repo_query,
    repo_update,
)

T = TypeVar("T", bound="ObjectModel")


class ObjectModel(BaseModel):
    """
    Base class for all domain models.

    Provides common functionality:
    - UUID generation for new records
    - Automatic timestamp management
    - CRUD operations via repository pattern
    - Type-safe database interface
    """

    # Class variable defining the table name (must be overridden by subclasses)
    _table_name: ClassVar[str] = ""
    # Optional: fields to exclude from database operations
    _exclude_fields: ClassVar[List[str]] = []

    # Fields common to all models
    id: Optional[str] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    class Config:
        """Pydantic configuration."""
        from_attributes = True
        arbitrary_types_allowed = True

    @classmethod
    async def get_all(
        cls: Type[T],
        order_by: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[T]:
        """
        Get all records from the database.

        Args:
            order_by: Column to order by (e.g., "created DESC", "name ASC")
            filters: Dictionary of field=value filters to apply

        Returns:
            List of model instances
        """
        if not cls._table_name:
            raise ValueError(f"{cls.__name__} must define _table_name")

        # Build SQL query
        sql = f"SELECT * FROM {cls._table_name}"
        params = {}

        # Add filters if provided
        if filters:
            where_clauses = []
            for i, (field, value) in enumerate(filters.items()):
                param_name = f"filter_{i}"
                where_clauses.append(f"{field} = :{param_name}")
                params[param_name] = value
            sql += " WHERE " + " AND ".join(where_clauses)

        # Add ordering
        if order_by:
            sql += f" ORDER BY {order_by}"

        # Execute query
        results = await repo_query(sql, params)

        # Convert to model instances
        return [cls(**row) for row in results]

    @classmethod
    async def get(cls: Type[T], id: str) -> Optional[T]:
        """
        Get a single record by ID.

        Args:
            id: Record ID (UUID)

        Returns:
            Model instance or None if not found
        """
        if not cls._table_name:
            raise ValueError(f"{cls.__name__} must define _table_name")

        sql = f"SELECT * FROM {cls._table_name} WHERE id = :id"
        results = await repo_query(sql, {"id": id})

        if not results:
            return None

        return cls(**results[0])

    async def save(self) -> str:
        """
        Save the model to the database.

        Creates a new record if id is None, otherwise updates existing record.
        Automatically manages timestamps.

        Returns:
            Record ID (UUID)
        """
        if not self._table_name:
            raise ValueError(f"{self.__class__.__name__} must define _table_name")

        now = datetime.utcnow()

        # Build exclude set from _exclude_fields
        exclude_set = set(self._exclude_fields) if self._exclude_fields else set()

        # Convert model to dict, excluding None values and excluded fields
        data = self.model_dump(exclude_none=True, exclude=exclude_set)

        if self.id is None:
            # Create new record
            self.id = str(uuid.uuid4())
            data["id"] = self.id

            # Only set created if not in exclude list
            if 'created' not in self._exclude_fields:
                self.created = now
                data["created"] = self.created.isoformat()

            # Only set updated if not in exclude list
            if 'updated' not in self._exclude_fields:
                self.updated = now
                data["updated"] = self.updated.isoformat()

            await repo_create(self._table_name, data)
        else:
            # Update existing record
            if 'updated' not in self._exclude_fields:
                self.updated = now
                data["updated"] = self.updated.isoformat()

            # Remove id from update data
            record_id = data.pop("id")

            await repo_update(self._table_name, record_id, data)

        return self.id

    async def delete(self) -> None:
        """
        Delete the record from the database.

        Raises:
            ValueError: If id is None (record not saved yet)
        """
        if self.id is None:
            raise ValueError("Cannot delete unsaved record")

        if not self._table_name:
            raise ValueError(f"{self.__class__.__name__} must define _table_name")

        # DEBUG: Log all deletions
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"🗑️ DELETING {self.__class__.__name__} with id={self.id}")
        import traceback
        logger.warning(f"Delete called from:\n{''.join(traceback.format_stack())}")

        await repo_delete(self._table_name, self.id)

    @classmethod
    async def count(cls, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records matching filters.

        Args:
            filters: Dictionary of field=value filters to apply

        Returns:
            Count of matching records
        """
        if not cls._table_name:
            raise ValueError(f"{cls.__name__} must define _table_name")

        sql = f"SELECT COUNT(*) as count FROM {cls._table_name}"
        params = {}

        if filters:
            where_clauses = []
            for i, (field, value) in enumerate(filters.items()):
                param_name = f"filter_{i}"
                where_clauses.append(f"{field} = :{param_name}")
                params[param_name] = value
            sql += " WHERE " + " AND ".join(where_clauses)

        results = await repo_query(sql, params)
        return results[0]["count"] if results else 0

    async def refresh(self) -> None:
        """
        Refresh the model from the database.

        Raises:
            ValueError: If id is None or record not found
        """
        if self.id is None:
            raise ValueError("Cannot refresh unsaved record")

        refreshed = await self.__class__.get(self.id)
        if refreshed is None:
            raise ValueError(f"Record {self.id} not found")

        # Update all fields
        for field, value in refreshed.model_dump().items():
            setattr(self, field, value)
