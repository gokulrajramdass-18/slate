"""
Search Service

Factory and management service for search strategies.
Includes search result caching with TTL.
"""

import json
import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import Dict, Any, Optional, List
from open_notebook.search.strategies import SearchStrategy, SearchFilters, SearchResult
from open_notebook.search.keyword import KeywordSearch
from open_notebook.search.vector import VectorSearch
from open_notebook.search.hybrid import HybridSearch
from open_notebook.search.agentic_rag import AgenticRAGSearch
from open_notebook.search.entity_vector import EntityVectorSearch
from open_notebook.search.lightrag_hybrid import LightRAGHybridSearch


class SearchResultCache:
    """LRU cache with TTL for search results."""

    def __init__(self, max_size: int = 200, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple] = OrderedDict()
        self._lock = Lock()

    @staticmethod
    def _make_key(query: str, filters: Optional[SearchFilters], limit: int, strategy: str) -> str:
        raw = json.dumps({
            "q": query,
            "f": filters.dict() if filters else None,
            "l": limit,
            "s": strategy,
        }, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, query: str, filters: Optional[SearchFilters], limit: int, strategy: str) -> Optional[List]:
        key = self._make_key(query, filters, limit, strategy)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            results, ts = entry
            if time.monotonic() - ts > self.ttl_seconds:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return results

    def set(self, query: str, filters: Optional[SearchFilters], limit: int, strategy: str, results: List) -> None:
        key = self._make_key(query, filters, limit, strategy)
        with self._lock:
            if key in self._cache:
                self._cache[key] = (results, time.monotonic())
                self._cache.move_to_end(key)
            else:
                while len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)
                self._cache[key] = (results, time.monotonic())

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


# Module-level search result cache singleton
_search_result_cache = SearchResultCache(max_size=200, ttl_seconds=300)


class SearchService:
    """
    Search service managing strategy selection and configuration.
    """

    AVAILABLE_STRATEGIES = {
        'keyword': KeywordSearch,
        'vector': VectorSearch,
        'hybrid': HybridSearch,
        'agentic_rag': AgenticRAGSearch,
        'entity_vector': EntityVectorSearch,
        'lightrag_hybrid': LightRAGHybridSearch
    }

    def __init__(self, database, config_repository=None):
        """
        Initialize search service.

        Args:
            database: Database interface instance
            config_repository: Repository for loading/saving config
        """
        self.database = database
        self.config_repository = config_repository
        self._default_config = None

    async def get_search_strategy(
        self,
        strategy_name: str,
        config_override: Optional[Dict[str, Any]] = None
    ) -> SearchStrategy:
        """
        Get search strategy instance by name.

        Args:
            strategy_name: Name of strategy ('keyword', 'vector', 'hybrid', 'agentic_rag')
            config_override: Optional config to override defaults

        Returns:
            SearchStrategy instance

        Raises:
            ValueError if strategy name is invalid
        """
        if strategy_name not in self.AVAILABLE_STRATEGIES:
            raise ValueError(
                f"Invalid strategy: {strategy_name}. "
                f"Available: {', '.join(self.AVAILABLE_STRATEGIES.keys())}"
            )

        # Load default config if not cached
        if self._default_config is None:
            self._default_config = await self._load_default_config()

        # Get strategy-specific config
        strategy_config = self._default_config.get('strategies', {}).get(strategy_name, {})

        # Apply override
        if config_override:
            strategy_config = {**strategy_config, **config_override}

        # Create strategy instance
        strategy_class = self.AVAILABLE_STRATEGIES[strategy_name]
        return strategy_class(self.database, strategy_config)

    async def cached_search(
        self,
        strategy_name: str,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 10,
        config_override: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        Execute a search with result caching (300s TTL).

        Returns cached results when available; otherwise delegates to the
        strategy and stores the results before returning them.
        """
        cached = _search_result_cache.get(query, filters, limit, strategy_name)
        if cached is not None:
            return cached

        strategy = await self.get_search_strategy(strategy_name, config_override)
        results = await strategy.search(query, filters, limit)
        _search_result_cache.set(query, filters, limit, strategy_name, results)
        return results

    async def get_default_strategy(self) -> str:
        """
        Get the default strategy name from config.

        Returns:
            Strategy name (default: 'hybrid')
        """
        config = await self._load_default_config()
        return config.get('default_strategy', 'hybrid')

    async def set_default_strategy(self, strategy_name: str) -> None:
        """
        Set the default strategy.

        Args:
            strategy_name: Strategy name

        Raises:
            ValueError if strategy name is invalid
        """
        if strategy_name not in self.AVAILABLE_STRATEGIES:
            raise ValueError(f"Invalid strategy: {strategy_name}")

        config = await self._load_default_config()
        config['default_strategy'] = strategy_name
        await self._save_config(config)

        # Invalidate cache
        self._default_config = None

    async def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific strategy.

        Args:
            strategy_name: Strategy name

        Returns:
            Configuration dict
        """
        config = await self._load_default_config()
        return config.get('strategies', {}).get(strategy_name, {})

    async def update_strategy_config(
        self,
        strategy_name: str,
        config: Dict[str, Any]
    ) -> None:
        """
        Update configuration for a specific strategy.

        Args:
            strategy_name: Strategy name
            config: New configuration
        """
        if strategy_name not in self.AVAILABLE_STRATEGIES:
            raise ValueError(f"Invalid strategy: {strategy_name}")

        full_config = await self._load_default_config()

        if 'strategies' not in full_config:
            full_config['strategies'] = {}

        full_config['strategies'][strategy_name] = config
        await self._save_config(full_config)

        # Invalidate cache
        self._default_config = None

    async def list_strategies(self) -> List[Dict[str, Any]]:
        """
        List all available search strategies with metadata.

        Returns:
            List of strategy info dicts
        """
        strategies = []

        for name, strategy_class in self.AVAILABLE_STRATEGIES.items():
            # Create temporary instance to get metadata
            temp_instance = strategy_class(self.database, {})

            strategies.append({
                'name': name,
                'description': temp_instance.description,
                'config': await self.get_strategy_config(name)
            })

        return strategies

    async def _load_default_config(self) -> Dict[str, Any]:
        """
        Load default search configuration from database.

        Returns:
            Configuration dict
        """
        # Get embedding model from settings
        embedding_model_id = None
        chat_model_id = None
        try:
            sql = "SELECT key, value FROM settings WHERE key IN ('embedding_model_id', 'language_model_id')"
            results = await self.database.query(sql, {})
            for row in results:
                if row['key'] == 'embedding_model_id':
                    embedding_model_id = row['value']
                elif row['key'] == 'language_model_id':
                    chat_model_id = row['value']
        except Exception as e:
            print(f"Failed to load model settings: {e}")

        if not self.config_repository:
            return self._get_fallback_config(embedding_model_id, chat_model_id)

        try:
            # Query search_config table
            sql = "SELECT config FROM search_config WHERE user_id IS NULL ORDER BY created DESC LIMIT 1"
            results = await self.database.query(sql, {})

            if results:
                config_json = results[0]['config']
                config = json.loads(config_json) if isinstance(config_json, str) else config_json

                # Inject models into strategy configs if needed
                if embedding_model_id or chat_model_id:
                    if 'strategies' not in config:
                        config['strategies'] = {}

                    # Vector search needs embedding model
                    if 'vector' not in config['strategies']:
                        config['strategies']['vector'] = {}
                    if embedding_model_id:
                        config['strategies']['vector']['embedding_model'] = embedding_model_id

                    # Hybrid search needs both models
                    if 'hybrid' not in config['strategies']:
                        config['strategies']['hybrid'] = {}
                    if 'vector_config' not in config['strategies']['hybrid']:
                        config['strategies']['hybrid']['vector_config'] = {}
                    if embedding_model_id:
                        config['strategies']['hybrid']['vector_config']['embedding_model'] = embedding_model_id

                    # Agentic RAG needs both models
                    if 'agentic_rag' not in config['strategies']:
                        config['strategies']['agentic_rag'] = {}
                    if 'vector_config' not in config['strategies']['agentic_rag']:
                        config['strategies']['agentic_rag']['vector_config'] = {}
                    if embedding_model_id:
                        config['strategies']['agentic_rag']['vector_config']['embedding_model'] = embedding_model_id
                    if chat_model_id:
                        config['strategies']['agentic_rag']['llm_model'] = chat_model_id

                return config

        except Exception as e:
            print(f"Failed to load search config: {e}")

        return self._get_fallback_config(embedding_model_id, chat_model_id)

    async def _save_config(self, config: Dict[str, Any]) -> None:
        """
        Save search configuration to database.

        Args:
            config: Configuration dict
        """
        if not self.config_repository:
            print("No config repository, skipping save")
            return

        try:
            import uuid
            from datetime import datetime

            config_json = json.dumps(config)

            # Upsert into search_config table
            sql = """
                INSERT INTO search_config (id, user_id, default_strategy, config, created, updated)
                VALUES (:id, NULL, :default_strategy, :config, :created, :updated)
                ON CONFLICT (id) DO UPDATE SET
                    default_strategy = :default_strategy,
                    config = :config,
                    updated = :updated
            """

            params = {
                'id': str(uuid.uuid4()),
                'default_strategy': config.get('default_strategy', 'hybrid'),
                'config': config_json,
                'created': datetime.utcnow().isoformat(),
                'updated': datetime.utcnow().isoformat()
            }

            await self.database.query(sql, params)

        except Exception as e:
            print(f"Failed to save search config: {e}")

    def _get_fallback_config(self, embedding_model_id: Optional[str] = None, chat_model_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get fallback configuration when database is unavailable.

        Args:
            embedding_model_id: Optional embedding model ID from settings
            chat_model_id: Optional chat model ID from settings

        Returns:
            Default configuration
        """
        return {
            'default_strategy': 'hybrid',
            'strategies': {
                'keyword': {
                    'title_boost': 2.0,
                    'min_score': 0.0,
                    'snippet_length': 200
                },
                'vector': {
                    'threshold': 0.7,
                    'rerank': False,
                    'embedding_model': embedding_model_id
                },
                'hybrid': {
                    'keyword_weight': 0.4,
                    'vector_weight': 0.6,
                    'rrf_k': 60,
                    'keyword_config': {
                        'title_boost': 2.0,
                        'min_score': 0.0
                    },
                    'vector_config': {
                        'threshold': 0.7,
                        'embedding_model': embedding_model_id
                    }
                },
                'agentic_rag': {
                    'max_iterations': 5,
                    'relevance_threshold': 0.6,
                    'max_sub_queries': 5,
                    'llm_model': chat_model_id,
                    'keyword_config': {},
                    'vector_config': {
                        'embedding_model': embedding_model_id
                    },
                    'hybrid_config': {}
                }
            }
        }

    async def test_strategy(
        self,
        strategy_name: str,
        test_query: str,
        config_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Test a search strategy with a query.

        Args:
            strategy_name: Strategy name
            test_query: Test query
            config_override: Optional config override

        Returns:
            Test results including timing and result count
        """
        import time

        try:
            strategy = await self.get_search_strategy(strategy_name, config_override)

            start_time = time.time()
            results = await strategy.search(test_query, limit=10)
            elapsed = time.time() - start_time

            return {
                'success': True,
                'strategy': strategy_name,
                'query': test_query,
                'result_count': len(results),
                'elapsed_seconds': round(elapsed, 3),
                'sample_results': [
                    {
                        'source_id': r.source_id,
                        'score': r.score,
                        'content_preview': r.content[:100]
                    }
                    for r in results[:3]
                ]
            }

        except Exception as e:
            return {
                'success': False,
                'strategy': strategy_name,
                'query': test_query,
                'error': str(e)
            }
