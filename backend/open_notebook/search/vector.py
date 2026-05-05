"""
Vector Search Strategy

Semantic search using embeddings and cosine similarity.
- SQLite: NumPy-based cosine similarity (Python)
- HANA: Native COSINE_SIMILARITY() function
"""

import numpy as np
from typing import List, Optional, Dict, Any
from open_notebook.search.strategies import (
    SearchStrategy,
    SearchResult,
    SearchFilters,
    SearchExecutionError
)
from open_notebook.search.cache import get_embedding_cache


class VectorSearch(SearchStrategy):
    """
    Vector-based semantic search strategy using embeddings.

    Configuration options:
        - threshold: Minimum similarity threshold (0.0-1.0, default: 0.7)
        - rerank: Whether to rerank results (default: False)
        - embedding_model: Model to use for query embedding (required)
    """

    @property
    def name(self) -> str:
        return "vector"

    @property
    def description(self) -> str:
        return "Semantic search using embeddings and cosine similarity"

    async def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        Execute vector search using embeddings.

        Args:
            query: Search query to embed
            filters: Optional filters
            limit: Maximum results

        Returns:
            List of SearchResult sorted by similarity
        """
        if not query or not query.strip():
            return []

        # Get embedding model from config
        embedding_model = self.config.get('embedding_model')
        if not embedding_model:
            # Return empty results instead of raising error (for hybrid fallback)
            print("Warning: No embedding_model configured for vector search - returning empty results")
            return []

        # Generate query embedding
        try:
            query_embedding = await self._generate_embedding(query, embedding_model)
        except Exception as e:
            # Return empty results instead of raising error (for hybrid fallback)
            print(f"Warning: Failed to generate query embedding: {str(e)} - returning empty results")
            return []

        db_type = self._detect_database_type()

        if db_type == "sqlite":
            return await self._search_sqlite(query_embedding, filters, limit)
        elif db_type == "hana":
            return await self._search_hana(query_embedding, filters, limit)
        else:
            raise SearchExecutionError(f"Unsupported database type: {db_type}")

    def _detect_database_type(self) -> str:
        """Detect whether we're using SQLite or HANA."""
        db_class_name = self.database.__class__.__name__
        if "SQLite" in db_class_name:
            return "sqlite"
        elif "HANA" in db_class_name:
            return "hana"
        return "unknown"

    async def _generate_embedding(self, text: str, model_id: str) -> List[float]:
        """
        Generate embedding for the query text using configured model.

        Args:
            text: Text to embed
            model_id: Model credential ID

        Returns:
            List of floats representing the embedding
        """
        # Get credentials for the embedding model
        try:
            from api.routers.credentials import _credentials_store

            credential = _credentials_store.get(model_id)
            if not credential:
                raise SearchExecutionError(f"Embedding model credential not found: {model_id}")

            api_url = credential["base_url"]
            api_key = credential["api_key"]

            # Default model name (this should ideally be configurable)
            model_name = credential.get("model_name", "text-embedding-ada-002")

        except Exception as e:
            raise SearchExecutionError(f"Failed to get embedding credentials: {str(e)}")

        # Check embedding cache first
        cache = get_embedding_cache()
        cached = cache.get(text, model_id)
        if cached is not None:
            return cached

        # Generate embedding via API
        try:
            from api.services.http_client import http_client_manager
            client = http_client_manager.get_client()
            response = await client.post(
                f"{api_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_name,
                    "input": text
                },
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(f"Embedding API error: {response.status_code} - {response.text}")

            result = response.json()
            embedding = result["data"][0]["embedding"]

            # Store in cache
            cache.set(text, model_id, embedding)

            return embedding

        except SearchExecutionError:
            raise
        except Exception as e:
            raise SearchExecutionError(f"Failed to generate embedding: {str(e)}")

    async def _search_sqlite(
        self,
        query_embedding: List[float],
        filters: Optional[SearchFilters],
        limit: int
    ) -> List[SearchResult]:
        """
        SQLite vector search using NumPy cosine similarity.

        Process:
        1. Fetch all embeddings (with filters)
        2. Calculate cosine similarity in Python
        3. Filter by threshold
        4. Sort and limit
        """
        threshold = self.config.get('threshold', 0.7)

        # Build filter conditions
        filter_clause, filter_params = self._build_filter_sql(filters)
        where_clause = f"WHERE {filter_clause}" if filter_clause else ""

        # Fetch all embeddings
        sql = f"""
            SELECT
                e.id as chunk_id,
                e.source_id,
                e.content,
                e.embedding,
                s.title,
                s.source_type,
                s.created
            FROM source_embeddings e
            JOIN sources s ON e.source_id = s.id
            {where_clause}
        """

        try:
            rows = await self.database.query(sql, filter_params)

            if not rows:
                return []

            # Calculate similarities in Python
            query_vec = np.array(query_embedding, dtype=np.float32)
            results = []

            for row in rows:
                # Deserialize embedding (stored as BLOB in SQLite)
                embedding_blob = row['embedding']
                if isinstance(embedding_blob, bytes):
                    doc_vec = np.frombuffer(embedding_blob, dtype=np.float32)
                elif isinstance(embedding_blob, str):
                    # Handle string representation
                    doc_vec = np.array(eval(embedding_blob), dtype=np.float32)
                else:
                    doc_vec = np.array(embedding_blob, dtype=np.float32)

                # Cosine similarity
                similarity = self._cosine_similarity(query_vec, doc_vec)

                if similarity >= threshold:
                    result = SearchResult(
                        source_id=row['source_id'],
                        chunk_id=row['chunk_id'],
                        content=row['content'],
                        score=float(similarity),
                        highlights=[],  # Vector search doesn't have highlights
                        metadata={
                            'title': row['title'],
                            'source_type': row['source_type'],
                            'created': row['created']
                        },
                        strategy=self.name
                    )
                    results.append(result)

            # Sort by similarity (descending)
            results.sort(key=lambda x: x.score, reverse=True)

            # Apply limit
            return results[:limit]

        except Exception as e:
            raise SearchExecutionError(f"SQLite vector search failed: {str(e)}")

    async def _search_hana(
        self,
        query_embedding: List[float],
        filters: Optional[SearchFilters],
        limit: int
    ) -> List[SearchResult]:
        """
        HANA vector search using native COSINE_SIMILARITY() function.

        HANA can perform similarity calculation in the database,
        which is much faster for large datasets.
        """
        threshold = self.config.get('threshold', 0.7)

        # Build filter conditions
        filter_clause, filter_params = self._build_filter_sql(filters)
        where_parts = []
        if filter_clause:
            where_parts.append(filter_clause)

        # Add threshold filter
        where_parts.append("COSINE_SIMILARITY(e.embedding, TO_REAL_VECTOR(:query_embedding)) >= :threshold")

        where_clause = "WHERE " + " AND ".join(where_parts)

        # HANA vector search with COSINE_SIMILARITY
        sql = f"""
            SELECT
                e.id as chunk_id,
                e.source_id,
                e.content,
                COSINE_SIMILARITY(e.embedding, TO_REAL_VECTOR(:query_embedding)) as similarity,
                s.title,
                s.source_type,
                s.created
            FROM source_embeddings e
            JOIN sources s ON e.source_id = s.id
            {where_clause}
            ORDER BY similarity DESC
            LIMIT :limit
        """

        # Convert embedding to string format for HANA
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'

        params = {
            'query_embedding': embedding_str,
            'threshold': threshold,
            'limit': limit,
            **filter_params
        }

        try:
            rows = await self.database.query(sql, params)
            results = []

            for row in rows:
                result = SearchResult(
                    source_id=row['source_id'],
                    chunk_id=row['chunk_id'],
                    content=row['content'],
                    score=float(row['similarity']),
                    highlights=[],
                    metadata={
                        'title': row['title'],
                        'source_type': row['source_type'],
                        'created': row['created']
                    },
                    strategy=self.name
                )
                results.append(result)

            return results

        except Exception as e:
            raise SearchExecutionError(f"HANA vector search failed: {str(e)}")

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize vectors
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)

        # Dot product of normalized vectors
        similarity = np.dot(vec1_norm, vec2_norm)

        # Clip to [0, 1] range (handles floating point errors)
        return float(np.clip(similarity, 0.0, 1.0))
