"""
Search API Router

Endpoints for executing searches with different strategies.
Includes unified search combining main search and bookmarks.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Header
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from api.services.search_service import SearchService
from api.services.unified_search_service import get_unified_search_service
from open_notebook.search.strategies import SearchFilters


router = APIRouter(prefix="/api/search", tags=["search"])


# Request/Response Models

class SearchRequest(BaseModel):
    """Search request model."""
    query: str = Field(..., description="Search query")
    strategy: Optional[str] = Field(None, description="Search strategy (keyword, vector, hybrid, agentic_rag)")
    filters: Optional[Dict[str, Any]] = Field(None, description="Search filters")
    limit: int = Field(10, ge=1, le=100, description="Maximum results")
    config_override: Optional[Dict[str, Any]] = Field(None, description="Strategy config override")


class SearchResultResponse(BaseModel):
    """Individual search result."""
    source_id: str
    id: str  # Alias for source_id for frontend compatibility
    chunk_id: Optional[str] = None
    title: str  # From metadata
    content: str
    source_type: str  # From metadata
    score: float
    highlights: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    strategy: Optional[str] = None


class UnifiedSearchRequest(BaseModel):
    """Unified search request model."""
    query: str = Field(..., description="Search query")
    strategy: Optional[str] = Field("hybrid", description="Main search strategy (keyword, vector, hybrid, agentic_rag)")
    filters: Optional[Dict[str, Any]] = Field(None, description="Search filters")
    limit: int = Field(20, ge=1, le=100, description="Maximum results")
    include_bookmarks: bool = Field(True, description="Include bookmark search results")
    bookmark_boost: float = Field(1.5, ge=1.0, le=5.0, description="Score multiplier for bookmarked items")
    config_override: Optional[Dict[str, Any]] = Field(None, description="Strategy config override")


class UnifiedSearchResultResponse(BaseModel):
    """Individual unified search result with bookmark info."""
    id: str
    entity_type: str  # source, note, notebook
    entity_id: str
    chunk_id: Optional[str] = None
    title: str
    content: str
    source_type: str
    score: float
    highlights: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    strategy: str
    result_source: str  # main_search or bookmarks
    is_bookmarked: bool
    bookmark_id: Optional[str] = None
    custom_note: Optional[str] = None
    created: Optional[str] = None


class UnifiedSearchResponse(BaseModel):
    """Unified search response with metadata."""
    query: str
    strategy: str
    total_results: int
    results: List[UnifiedSearchResultResponse]
    sources: Dict[str, int]  # Counts by source (main_search, bookmarks)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Search response with metadata."""
    query: str
    strategy: str
    total_results: int
    results: List[SearchResultResponse]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Dependency: Get search service
async def get_search_service() -> SearchService:
    """
    Get search service instance.
    Uses the database from the repository.
    """
    from api.services.database_service import get_database_service

    db_service = get_database_service()
    if not db_service._current_db:
        raise HTTPException(status_code=503, detail="Database not initialized")

    return SearchService(db_service._current_db)


# Endpoints

@router.post("/", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    search_service: SearchService = Depends(get_search_service)
) -> SearchResponse:
    """
    Execute search with specified or default strategy.

    Args:
        request: Search request with query and options

    Returns:
        Search results with metadata
    """
    try:
        # Determine strategy
        strategy_name = request.strategy
        if not strategy_name:
            strategy_name = await search_service.get_default_strategy()

        # Build filters
        filters = None
        if request.filters:
            filters = SearchFilters(
                notebook_ids=request.filters.get('notebook_ids'),
                source_types=request.filters.get('source_types'),
                date_from=datetime.fromisoformat(request.filters['date_from']) if request.filters.get('date_from') else None,
                date_to=datetime.fromisoformat(request.filters['date_to']) if request.filters.get('date_to') else None,
                tags=request.filters.get('tags')
            )

        # Get strategy
        strategy = await search_service.get_search_strategy(
            strategy_name,
            request.config_override
        )

        # Execute search
        results = await strategy.search(
            request.query,
            filters,
            request.limit
        )

        # Convert to response
        result_responses = [
            SearchResultResponse(
                source_id=r.source_id,
                id=r.source_id,  # Alias for frontend
                chunk_id=r.chunk_id,
                title=r.metadata.get('title', 'Untitled'),
                content=r.content,
                source_type=r.metadata.get('source_type', 'text'),
                score=r.score,
                highlights=r.highlights,
                metadata=r.metadata,
                strategy=r.strategy
            )
            for r in results
        ]

        return SearchResponse(
            query=request.query,
            strategy=strategy_name,
            total_results=len(result_responses),
            results=result_responses,
            metadata={
                'filters_applied': filters is not None,
                'config_override': request.config_override is not None
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Search error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/", response_model=SearchResponse)
async def search_get(
    query: str = Query(..., description="Search query"),
    strategy: Optional[str] = Query(None, description="Search strategy"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    notebook_ids: Optional[str] = Query(None, description="Comma-separated notebook IDs"),
    source_types: Optional[str] = Query(None, description="Comma-separated source types"),
    search_service: SearchService = Depends(get_search_service)
) -> SearchResponse:
    """
    Execute search via GET request (simplified).

    Args:
        query: Search query
        strategy: Optional strategy name
        limit: Maximum results
        notebook_ids: Optional notebook filter
        source_types: Optional source type filter

    Returns:
        Search results
    """
    # Build filters from query params
    filters_dict = {}
    if notebook_ids:
        filters_dict['notebook_ids'] = notebook_ids.split(',')
    if source_types:
        filters_dict['source_types'] = source_types.split(',')

    # Convert to POST request
    request = SearchRequest(
        query=query,
        strategy=strategy,
        filters=filters_dict if filters_dict else None,
        limit=limit
    )

    return await search(request, search_service)


@router.post("/unified", response_model=UnifiedSearchResponse)
async def unified_search(
    request: UnifiedSearchRequest,
    x_user_id: Optional[str] = Header(None),
    search_service: SearchService = Depends(get_search_service)
) -> UnifiedSearchResponse:
    """
    Execute unified search combining main search and bookmarks.

    Searches across:
    - All sources (via main search strategies)
    - User's bookmarked items (sources, notes, notebooks)

    Bookmarked items get a score boost and are merged with main results.

    Args:
        request: Unified search request
        x_user_id: User ID from header (for bookmark search)

    Returns:
        Unified search results with bookmark integration
    """
    try:
        user_id = x_user_id or "default_user"

        # Build filters
        filters = None
        if request.filters:
            filters = SearchFilters(
                notebook_ids=request.filters.get('notebook_ids'),
                source_types=request.filters.get('source_types'),
                date_from=datetime.fromisoformat(request.filters['date_from']) if request.filters.get('date_from') else None,
                date_to=datetime.fromisoformat(request.filters['date_to']) if request.filters.get('date_to') else None,
                tags=request.filters.get('tags')
            )

        # Get unified search service
        unified_service = get_unified_search_service(
            search_service.database,
            user_id
        )

        # Execute unified search
        result = await unified_service.search(
            query=request.query,
            strategy=request.strategy,
            filters=filters,
            limit=request.limit,
            include_bookmarks=request.include_bookmarks,
            bookmark_boost=request.bookmark_boost,
            config_override=request.config_override
        )

        # Convert to response
        result_responses = [
            UnifiedSearchResultResponse(**r)
            for r in result["results"]
        ]

        return UnifiedSearchResponse(
            query=result["metadata"]["query"],
            strategy=result["metadata"]["strategy"],
            total_results=result["total_results"],
            results=result_responses,
            sources=result["sources"],
            metadata=result["metadata"]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Unified search error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Unified search failed: {str(e)}")
