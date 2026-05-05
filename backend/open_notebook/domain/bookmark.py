"""
Bookmark domain model.

Provides user-specific bookmarking across entity types (sources, notes, notebooks).
Follows the ObjectModel pattern with user isolation via user_id.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from open_notebook.database.repository import repo_execute, repo_query


class EntityType(str, Enum):
    SOURCE = "source"
    NOTE = "note"
    NOTEBOOK = "notebook"


class Bookmark:
    """
    Bookmark represents a user's saved reference to a source, note, or notebook.

    Uses direct SQL via repo_query/repo_execute rather than ObjectModel inheritance
    to keep the toggle/check operations efficient and match the user_query_prompts pattern.
    """

    _table_name = "user_bookmarks"

    @staticmethod
    async def toggle(
        user_id: str,
        entity_type: str,
        entity_id: str,
        custom_note: Optional[str] = None,
        reason: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Toggle bookmark on/off for a given entity.

        If bookmark exists, delete it. If not, create it.

        Returns:
            Dict with is_bookmarked, bookmark (if created), and message
        """
        # Check if bookmark already exists
        existing = await repo_query(
            """SELECT * FROM user_bookmarks
               WHERE user_id = :user_id AND entity_type = :entity_type AND entity_id = :entity_id""",
            {"user_id": user_id, "entity_type": entity_type, "entity_id": entity_id},
        )

        if existing:
            # Remove bookmark
            await repo_execute(
                "DELETE FROM user_bookmarks WHERE id = :id",
                {"id": existing[0]["id"]},
            )
            return {
                "is_bookmarked": False,
                "bookmark": None,
                "message": "Bookmark removed",
            }
        else:
            # Create bookmark
            import json
            now = datetime.utcnow().isoformat()
            bookmark_id = str(uuid.uuid4())

            # Serialize tags as JSON if provided
            tags_json = json.dumps(tags) if tags else None

            await repo_execute(
                """INSERT INTO user_bookmarks
                   (id, user_id, entity_type, entity_id, custom_note, reason, tags, category, bookmarked_at, created, updated)
                   VALUES (:id, :user_id, :entity_type, :entity_id, :custom_note, :reason, :tags, :category, :bookmarked_at, :created, :updated)""",
                {
                    "id": bookmark_id,
                    "user_id": user_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "custom_note": custom_note,
                    "reason": reason,
                    "tags": tags_json,
                    "category": category,
                    "bookmarked_at": now,
                    "created": now,
                    "updated": now,
                },
            )

            # Fetch created bookmark
            rows = await repo_query(
                "SELECT * FROM user_bookmarks WHERE id = :id",
                {"id": bookmark_id},
            )

            # Generate embedding in background (fire and forget)
            try:
                import asyncio
                from api.services.bookmark_embedding_service import get_bookmark_embedding_service

                service = get_bookmark_embedding_service()
                asyncio.create_task(service.generate_embedding_for_bookmark(bookmark_id))
            except Exception as embed_error:
                # Don't fail bookmark creation if embedding fails
                print(f"Warning: Failed to generate embedding for bookmark {bookmark_id}: {embed_error}")

            return {
                "is_bookmarked": True,
                "bookmark": rows[0] if rows else None,
                "message": "Bookmark added",
            }

    @staticmethod
    async def is_bookmarked(user_id: str, entity_type: str, entity_id: str) -> bool:
        """Check if an entity is bookmarked by a user."""
        rows = await repo_query(
            """SELECT id FROM user_bookmarks
               WHERE user_id = :user_id AND entity_type = :entity_type AND entity_id = :entity_id""",
            {"user_id": user_id, "entity_type": entity_type, "entity_id": entity_id},
        )
        return len(rows) > 0

    @staticmethod
    async def get_user_bookmarks(
        user_id: str,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get all bookmarks for a user, optionally filtered by entity type.

        Returns raw bookmark rows (enrichment happens at the API layer).
        """
        conditions = ["user_id = :user_id"]
        params: Dict[str, Any] = {"user_id": user_id, "limit": limit, "offset": offset}

        if entity_type:
            conditions.append("entity_type = :entity_type")
            params["entity_type"] = entity_type

        where_clause = " AND ".join(conditions)

        rows = await repo_query(
            f"""SELECT * FROM user_bookmarks
                WHERE {where_clause}
                ORDER BY bookmarked_at DESC
                LIMIT :limit OFFSET :offset""",
            params,
        )
        return rows

    @staticmethod
    async def count_user_bookmarks(
        user_id: str,
        entity_type: Optional[str] = None,
    ) -> int:
        """Count bookmarks for a user, optionally filtered by entity type."""
        conditions = ["user_id = :user_id"]
        params: Dict[str, Any] = {"user_id": user_id}

        if entity_type:
            conditions.append("entity_type = :entity_type")
            params["entity_type"] = entity_type

        where_clause = " AND ".join(conditions)

        rows = await repo_query(
            f"SELECT COUNT(*) as count FROM user_bookmarks WHERE {where_clause}",
            params,
        )
        return rows[0]["count"] if rows else 0

    @staticmethod
    async def get_by_id(bookmark_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single bookmark by ID, scoped to user."""
        rows = await repo_query(
            "SELECT * FROM user_bookmarks WHERE id = :id AND user_id = :user_id",
            {"id": bookmark_id, "user_id": user_id},
        )
        return rows[0] if rows else None

    @staticmethod
    async def update(
        bookmark_id: str,
        user_id: str,
        custom_note: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update bookmark metadata (custom_note, reason)."""
        now = datetime.utcnow().isoformat()

        updates = ["updated = :updated"]
        params: Dict[str, Any] = {
            "id": bookmark_id,
            "user_id": user_id,
            "updated": now,
        }

        if custom_note is not None:
            updates.append("custom_note = :custom_note")
            params["custom_note"] = custom_note

        if reason is not None:
            updates.append("reason = :reason")
            params["reason"] = reason

        sql = f"UPDATE user_bookmarks SET {', '.join(updates)} WHERE id = :id AND user_id = :user_id"
        await repo_execute(sql, params)

        # Regenerate embedding after update (fire and forget)
        try:
            import asyncio
            from api.services.bookmark_embedding_service import get_bookmark_embedding_service

            service = get_bookmark_embedding_service()
            asyncio.create_task(service.generate_embedding_for_bookmark(bookmark_id))
        except Exception as embed_error:
            print(f"Warning: Failed to regenerate embedding for bookmark {bookmark_id}: {embed_error}")

        return await Bookmark.get_by_id(bookmark_id, user_id)

    @staticmethod
    async def delete(bookmark_id: str, user_id: str) -> bool:
        """Delete a bookmark, scoped to user. Returns True if deleted."""
        existing = await Bookmark.get_by_id(bookmark_id, user_id)
        if not existing:
            return False

        await repo_execute(
            "DELETE FROM user_bookmarks WHERE id = :id AND user_id = :user_id",
            {"id": bookmark_id, "user_id": user_id},
        )
        return True

    @staticmethod
    async def bulk_check(
        user_id: str,
        entity_type: str,
        entity_ids: List[str],
    ) -> Dict[str, bool]:
        """
        Check bookmark status for multiple entities at once.

        Returns dict mapping entity_id -> is_bookmarked.
        """
        if not entity_ids:
            return {}

        # Build IN clause with named parameters
        placeholders = []
        params: Dict[str, Any] = {"user_id": user_id, "entity_type": entity_type}
        for i, eid in enumerate(entity_ids):
            param_name = f"eid_{i}"
            placeholders.append(f":{param_name}")
            params[param_name] = eid

        in_clause = ", ".join(placeholders)

        rows = await repo_query(
            f"""SELECT entity_id FROM user_bookmarks
                WHERE user_id = :user_id
                AND entity_type = :entity_type
                AND entity_id IN ({in_clause})""",
            params,
        )

        bookmarked_ids = {row["entity_id"] for row in rows}
        return {eid: eid in bookmarked_ids for eid in entity_ids}
