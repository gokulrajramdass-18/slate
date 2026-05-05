"""
Keyword Search Strategy

Full-text search using BM25 ranking with highlighting support.
- SQLite: Uses FTS5 with BM25 ranking
- HANA: Uses CONTAINS() or SCORE() function
"""

import re
from typing import List, Optional, Dict, Any
from open_notebook.search.strategies import (
    SearchStrategy,
    SearchResult,
    SearchFilters,
    SearchExecutionError
)


class KeywordSearch(SearchStrategy):
    """
    Keyword-based full-text search strategy.

    Configuration options:
        - title_boost: Multiplier for title matches (default: 2.0)
        - min_score: Minimum BM25 score threshold (default: 0.0)
        - snippet_length: Length of highlighted snippets in characters (default: 200)
    """

    @property
    def name(self) -> str:
        return "keyword"

    @property
    def description(self) -> str:
        return "Full-text search with BM25 ranking and highlighting"

    async def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        Execute keyword search using FTS5 (SQLite) or CONTAINS (HANA).

        Args:
            query: Search query (can include Boolean operators)
            filters: Optional filters
            limit: Maximum results

        Returns:
            List of SearchResult with highlights
        """
        if not query or not query.strip():
            return []

        query = query.strip()
        db_type = self._detect_database_type()

        if db_type == "sqlite":
            return await self._search_sqlite(query, filters, limit)
        elif db_type == "hana":
            return await self._search_hana(query, filters, limit)
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

    async def _search_sqlite(
        self,
        query: str,
        filters: Optional[SearchFilters],
        limit: int
    ) -> List[SearchResult]:
        """
        SQLite FTS5 implementation with BM25 ranking.
        """
        title_boost = self.config.get('title_boost', 2.0)
        min_score = self.config.get('min_score', 0.0)

        # Build filter conditions
        filter_clause, filter_params = self._build_filter_sql(filters)
        where_parts = [filter_clause] if filter_clause else []

        # FTS5 query - search both title and full_text
        # Use MATCH for FTS5 full-text search
        fts_query = self._sanitize_fts_query(query)

        sql = f"""
            SELECT
                s.id as source_id,
                s.title,
                s.full_text,
                s.source_type,
                s.created,
                -- BM25 score with title boost (negative values, closer to 0 is better)
                (bm25(sources_fts, 0) * :title_boost + bm25(sources_fts, 1)) as score,
                -- Snippet for highlighting
                snippet(sources_fts, 1, '<mark>', '</mark>', '...', 32) as snippet
            FROM sources s
            JOIN sources_fts ON s.rowid = sources_fts.rowid
            WHERE sources_fts MATCH :query
            {('AND ' + where_parts[0]) if where_parts else ''}
            ORDER BY score DESC
            LIMIT :limit
        """

        params = {
            'query': fts_query,
            'title_boost': title_boost,
            'limit': limit,
            **filter_params
        }

        try:
            rows = await self.database.query(sql, params)
            results = []

            for row in rows:
                try:
                    # BM25 scores are negative, convert to positive and normalize
                    raw_score = abs(row.get('score', 0) if row.get('score') is not None else 0)
                    normalized_score = min(1.0, raw_score / 10.0)  # Simple normalization

                    # Extract highlights from snippet
                    snippet = row.get('snippet', '') or ''
                    highlights = self._extract_highlights(snippet)

                    # Get full_text with fallback
                    full_text = row.get('full_text', '') or ''
                    content = snippet if snippet else full_text[:500]

                    result = SearchResult(
                        source_id=row['source_id'],
                        chunk_id=None,  # Keyword search doesn't use chunks
                        content=content,
                        score=normalized_score,
                        highlights=highlights,
                        metadata={
                            'title': row.get('title', ''),
                            'source_type': row.get('source_type', ''),
                            'created': row.get('created', '')
                        },
                        strategy=self.name
                    )
                    results.append(result)
                except Exception as row_error:
                    # Log row processing error but continue with other rows
                    print(f"Warning: Error processing search result row: {row_error}")
                    continue

            return results

        except Exception as e:
            raise SearchExecutionError(f"SQLite keyword search failed: {str(e)}")

    async def _search_hana(
        self,
        query: str,
        filters: Optional[SearchFilters],
        limit: int
    ) -> List[SearchResult]:
        """
        HANA full-text search implementation using CONTAINS() and SCORE().
        """
        title_boost = self.config.get('title_boost', 2.0)
        min_score = self.config.get('min_score', 0.0)

        # Build filter conditions
        filter_clause, filter_params = self._build_filter_sql(filters)
        where_parts = [filter_clause] if filter_clause else []

        # HANA full-text search
        sql = f"""
            SELECT
                s.id as source_id,
                s.title,
                s.full_text,
                s.source_type,
                s.created,
                -- HANA SCORE() function with title boost
                (SCORE() * :title_boost) as score,
                -- Snippet extraction (simplified, HANA has built-in highlighting)
                SUBSTRING(s.full_text, 1, 500) as snippet
            FROM sources s
            WHERE CONTAINS((title, full_text), :query, FUZZY(0.8))
            {('AND ' + where_parts[0]) if where_parts else ''}
            AND (SCORE() * :title_boost) >= :min_score
            ORDER BY score DESC
            LIMIT :limit
        """

        params = {
            'query': query,
            'title_boost': title_boost,
            'min_score': min_score,
            'limit': limit,
            **filter_params
        }

        try:
            rows = await self.database.query(sql, params)
            results = []

            for row in rows:
                # HANA SCORE() returns values typically 0-1
                normalized_score = min(1.0, max(0.0, row['score']))

                # Extract highlights (simplified - HANA has better built-in support)
                highlights = self._extract_query_terms(query)

                result = SearchResult(
                    source_id=row['source_id'],
                    chunk_id=None,
                    content=row.get('snippet', row['full_text'][:500]),
                    score=normalized_score,
                    highlights=highlights,
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
            raise SearchExecutionError(f"HANA keyword search failed: {str(e)}")

    def _sanitize_fts_query(self, query: str) -> str:
        """
        Sanitize and prepare query for FTS5.
        Remove special characters that might break FTS5 syntax.
        """
        # Remove FTS5 special characters including commas, slashes
        # These can cause "syntax error" in FTS5
        query = re.sub(r'[():\[\]{}<>*^$+?.|\\,/@#%&]', ' ', query)

        # Replace multiple spaces with single space
        query = re.sub(r'\s+', ' ', query).strip()

        # If query is empty after sanitization, return a safe default
        if not query:
            return '*'

        # Split into words and filter
        words = query.split()

        # Filter out FTS5 reserved words and wrap all terms in quotes to prevent ambiguity
        filtered_words = []
        for word in words:
            word_upper = word.upper()
            # Skip FTS5 operators if they're standalone (user didn't intend them as operators)
            if word_upper in ['AND', 'OR', 'NOT', 'NEAR']:
                continue
            # Keep word if it's meaningful (at least 2 chars)
            if len(word) >= 2:
                # Escape any remaining quotes in the word
                escaped_word = word.replace('"', '""')
                # Wrap all terms in quotes to prevent FTS5 column name confusion
                filtered_words.append(f'"{escaped_word}"')

        # If no words left, return wildcard
        if not filtered_words:
            return '*'

        # Join words with OR to match any term (more forgiving than AND)
        # This handles natural language queries better than strict phrase matching
        sanitized_query = ' OR '.join(filtered_words)

        return sanitized_query

    def _extract_highlights(self, snippet: str) -> List[str]:
        """
        Extract highlighted portions from FTS5 snippet.
        Assumes snippet uses <mark>...</mark> tags.
        """
        if not snippet:
            return []

        # Extract text between <mark> tags
        highlights = re.findall(r'<mark>(.*?)</mark>', snippet, re.IGNORECASE)

        # Deduplicate and limit
        unique_highlights = list(dict.fromkeys(highlights))
        return unique_highlights[:10]  # Limit to top 10

    def _extract_query_terms(self, query: str) -> List[str]:
        """
        Extract searchable terms from query for highlighting.
        """
        # Remove Boolean operators
        for op in ['AND', 'OR', 'NOT', 'and', 'or', 'not']:
            query = query.replace(op, ' ')

        # Remove special characters and split
        terms = re.findall(r'\w+', query)

        # Filter out very short terms and deduplicate
        terms = [t for t in terms if len(t) > 2]
        return list(dict.fromkeys(terms))[:10]
