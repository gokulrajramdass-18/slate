"""
Bookmark Embedding Service

Handles generation of embeddings for bookmarks to enable natural language search.
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

from open_notebook.database.repository import repo_query, repo_execute


class BookmarkEmbeddingService:
    """
    Service for generating and managing bookmark embeddings.

    Combines bookmark metadata (custom_note, reason, tags, category)
    with entity context (title, description) to create searchable text.
    """

    def __init__(self, model_id: Optional[str] = None):
        """
        Initialize bookmark embedding service.

        Args:
            model_id: Embedding model credential ID (uses default if not provided)
        """
        self.model_id = model_id

    async def _get_embedding_model_credentials(self) -> tuple[str, str, str]:
        """
        Get embedding model credentials from settings.

        Returns:
            Tuple of (api_url, api_key, model_name)
        """
        from api.routers.credentials import _credentials_store
        from api.services.settings import get_setting

        # Get the embedding model ID from settings or use provided
        embedding_model_id = self.model_id or await get_setting("embedding_model_id", "")

        if not embedding_model_id:
            raise ValueError("No embedding model configured. Configure in Settings → Models.")

        credential = _credentials_store.get(embedding_model_id)
        if not credential:
            raise ValueError(f"Embedding model '{embedding_model_id}' not found in credentials")

        api_url = credential["base_url"]
        api_key = credential["api_key"]
        model_name = credential.get("model_name", credential.get("name", "text-embedding-ada-002"))

        return api_url, api_key, model_name

    async def _generate_embedding(self, text: str, api_url: str, api_key: str, model_name: str) -> List[float]:
        """
        Generate embedding for text using configured model.

        Args:
            text: Text to embed
            api_url: API endpoint URL
            api_key: API key
            model_name: Model name

        Returns:
            Embedding vector as list of floats
        """
        import httpx

        # Check if this is SAP AI Core
        if model_name and model_name.startswith("sap-ai-core-"):
            try:
                from gen_ai_hub.proxy.langchain import OpenAIEmbeddings
                from gen_ai_hub.proxy import get_proxy_client

                deployment_id = model_name.replace("sap-ai-core-", "")
                proxy_client = get_proxy_client('gen-ai-hub')
                embedding_model = OpenAIEmbeddings(
                    proxy_model_name=deployment_id,
                    proxy_client=proxy_client
                )
                embedding = await embedding_model.aembed_query(text)
                return embedding

            except ImportError:
                raise Exception("gen-ai-hub SDK not installed. Install with: pip install generative-ai-hub-sdk")
            except Exception as e:
                raise Exception(f"SAP AI Core embedding error: {str(e)}")

        # LiteLLM proxy or OpenAI-compatible API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{api_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "input": text
                }
            )

            if response.status_code != 200:
                raise Exception(f"Embedding API error: {response.status_code} - {response.text}")

            result = response.json()
            return result["data"][0]["embedding"]

    async def _build_bookmark_context(self, bookmark: Dict[str, Any]) -> str:
        """
        Build searchable text context from bookmark and its entity.

        Combines:
        - Entity title and description
        - Bookmark custom_note and reason
        - Tags and category

        Args:
            bookmark: Bookmark record dict

        Returns:
            Concatenated searchable text
        """
        parts = []

        entity_type = bookmark["entity_type"]
        entity_id = bookmark["entity_id"]

        # Get entity details
        if entity_type == "source":
            rows = await repo_query(
                "SELECT title, source_type FROM sources WHERE id = :id",
                {"id": entity_id}
            )
            if rows:
                parts.append(f"Source: {rows[0]['title']}")
                parts.append(f"Type: {rows[0]['source_type']}")

        elif entity_type == "note":
            rows = await repo_query(
                "SELECT title, content FROM notes WHERE id = :id",
                {"id": entity_id}
            )
            if rows:
                parts.append(f"Note: {rows[0]['title']}")
                # Include snippet of content
                content_snippet = rows[0].get('content', '')[:200]
                if content_snippet:
                    parts.append(content_snippet)

        elif entity_type == "notebook":
            rows = await repo_query(
                "SELECT name, description FROM notebooks WHERE id = :id",
                {"id": entity_id}
            )
            if rows:
                parts.append(f"Notebook: {rows[0]['name']}")
                if rows[0].get('description'):
                    parts.append(rows[0]['description'])

        # Add bookmark metadata
        if bookmark.get('custom_note'):
            parts.append(f"Note: {bookmark['custom_note']}")

        if bookmark.get('reason'):
            parts.append(f"Reason: {bookmark['reason']}")

        # Add tags
        if bookmark.get('tags'):
            try:
                tags = json.loads(bookmark['tags']) if isinstance(bookmark['tags'], str) else bookmark['tags']
                if tags:
                    parts.append(f"Tags: {', '.join(tags)}")
            except:
                pass

        # Add category
        if bookmark.get('category'):
            parts.append(f"Category: {bookmark['category']}")

        return " | ".join(parts)

    async def generate_embedding_for_bookmark(self, bookmark_id: str) -> Dict[str, Any]:
        """
        Generate embedding for a single bookmark.

        Args:
            bookmark_id: Bookmark ID

        Returns:
            Dict with success status and details
        """
        try:
            # Get bookmark
            bookmark_rows = await repo_query(
                "SELECT * FROM user_bookmarks WHERE id = :id",
                {"id": bookmark_id}
            )

            if not bookmark_rows:
                return {
                    "success": False,
                    "error": f"Bookmark not found: {bookmark_id}"
                }

            bookmark = bookmark_rows[0]

            # Get credentials
            api_url, api_key, model_name = await self._get_embedding_model_credentials()

            # Build searchable context
            context = await self._build_bookmark_context(bookmark)

            if not context.strip():
                return {
                    "success": False,
                    "error": "No content to embed for bookmark"
                }

            # Generate embedding
            embedding = await self._generate_embedding(context, api_url, api_key, model_name)

            # Delete existing embedding
            await repo_execute(
                "DELETE FROM bookmark_embeddings WHERE bookmark_id = :bookmark_id",
                {"bookmark_id": bookmark_id}
            )

            # Store embedding as JSON string
            embedding_str = json.dumps(embedding)

            # Insert new embedding
            now = datetime.utcnow().isoformat()
            await repo_execute(
                """
                INSERT INTO bookmark_embeddings (id, bookmark_id, content, embedding, created)
                VALUES (:id, :bookmark_id, :content, :embedding, :created)
                """,
                {
                    "id": str(uuid.uuid4()),
                    "bookmark_id": bookmark_id,
                    "content": context,
                    "embedding": embedding_str,
                    "created": now
                }
            )

            return {
                "success": True,
                "bookmark_id": bookmark_id,
                "context_length": len(context),
                "message": "Embedding generated successfully"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to generate embedding: {str(e)}"
            }

    async def regenerate_all_embeddings(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Regenerate embeddings for all bookmarks.

        Args:
            user_id: Optional user ID to filter bookmarks (regenerates all if None)

        Returns:
            Dict with success count and errors
        """
        # Get all bookmarks
        if user_id:
            bookmarks = await repo_query(
                "SELECT id FROM user_bookmarks WHERE user_id = :user_id",
                {"user_id": user_id}
            )
        else:
            bookmarks = await repo_query("SELECT id FROM user_bookmarks", {})

        results = {
            "total": len(bookmarks),
            "success": 0,
            "failed": 0,
            "errors": []
        }

        for bookmark in bookmarks:
            result = await self.generate_embedding_for_bookmark(bookmark["id"])
            if result["success"]:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append({
                    "bookmark_id": bookmark["id"],
                    "error": result.get("error", "Unknown error")
                })

        return results

    async def search_bookmarks(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search bookmarks using natural language query.

        Args:
            query: Natural language search query
            user_id: User ID to filter bookmarks
            limit: Maximum results to return
            threshold: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of bookmark results with similarity scores
        """
        try:
            import numpy as np

            # Get credentials and generate query embedding
            api_url, api_key, model_name = await self._get_embedding_model_credentials()
            query_embedding = await self._generate_embedding(query, api_url, api_key, model_name)

            # Fetch all bookmark embeddings for user
            rows = await repo_query(
                """
                SELECT
                    be.id,
                    be.bookmark_id,
                    be.content,
                    be.embedding,
                    ub.entity_type,
                    ub.entity_id,
                    ub.custom_note,
                    ub.reason,
                    ub.tags,
                    ub.category,
                    ub.bookmarked_at
                FROM bookmark_embeddings be
                JOIN user_bookmarks ub ON be.bookmark_id = ub.id
                WHERE ub.user_id = :user_id
                """,
                {"user_id": user_id}
            )

            if not rows:
                return []

            # Calculate similarities
            query_vec = np.array(query_embedding, dtype=np.float32)
            query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-8)

            results = []

            for row in rows:
                # Deserialize embedding
                embedding_data = row['embedding']
                if isinstance(embedding_data, str):
                    doc_vec = np.array(json.loads(embedding_data), dtype=np.float32)
                elif isinstance(embedding_data, bytes):
                    doc_vec = np.frombuffer(embedding_data, dtype=np.float32)
                else:
                    doc_vec = np.array(embedding_data, dtype=np.float32)

                # Cosine similarity
                doc_norm = doc_vec / (np.linalg.norm(doc_vec) + 1e-8)
                similarity = float(np.dot(query_norm, doc_norm))
                similarity = max(0.0, min(1.0, similarity))  # Clip to [0, 1]

                if similarity >= threshold:
                    results.append({
                        "bookmark_id": row["bookmark_id"],
                        "entity_type": row["entity_type"],
                        "entity_id": row["entity_id"],
                        "custom_note": row["custom_note"],
                        "reason": row["reason"],
                        "tags": row["tags"],
                        "category": row["category"],
                        "bookmarked_at": row["bookmarked_at"],
                        "content": row["content"],
                        "similarity": similarity
                    })

            # Sort by similarity (descending)
            results.sort(key=lambda x: x["similarity"], reverse=True)

            # Apply limit
            return results[:limit]

        except Exception as e:
            raise Exception(f"Bookmark search failed: {str(e)}")


# Singleton instance
_bookmark_embedding_service: Optional[BookmarkEmbeddingService] = None


def get_bookmark_embedding_service() -> BookmarkEmbeddingService:
    """Get or create bookmark embedding service instance."""
    global _bookmark_embedding_service
    if _bookmark_embedding_service is None:
        _bookmark_embedding_service = BookmarkEmbeddingService()
    return _bookmark_embedding_service
