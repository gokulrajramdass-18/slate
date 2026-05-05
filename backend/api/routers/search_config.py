"""
Search Configuration API Router

Endpoints for managing search strategies and configuration.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from api.services.search_service import SearchService


router = APIRouter(prefix="/api/search", tags=["search-config"])


# Request/Response Models

class StrategyInfo(BaseModel):
    """Information about a search strategy."""
    name: str
    description: str
    config: Dict[str, Any]


class SearchConfigResponse(BaseModel):
    """Current search configuration."""
    default_strategy: str
    strategies: Dict[str, Dict[str, Any]]


class UpdateDefaultStrategyRequest(BaseModel):
    """Request to update default strategy."""
    strategy: str = Field(..., description="Strategy name")


class UpdateStrategyConfigRequest(BaseModel):
    """Request to update strategy configuration."""
    config: Dict[str, Any] = Field(..., description="Strategy configuration")


class TestStrategyRequest(BaseModel):
    """Request to test a strategy."""
    strategy: str = Field(..., description="Strategy name")
    test_query: str = Field(..., description="Test query")
    config_override: Optional[Dict[str, Any]] = Field(None, description="Config override")


class TestStrategyResponse(BaseModel):
    """Response from testing a strategy."""
    success: bool
    strategy: str
    query: str
    result_count: Optional[int] = None
    elapsed_seconds: Optional[float] = None
    sample_results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


# Dependency
async def get_search_service() -> SearchService:
    """Get search service instance."""
    # TODO: Replace with actual dependency injection
    from open_notebook.config import get_database

    database = await get_database()
    return SearchService(database)


# Endpoints

@router.get("/strategies", response_model=List[StrategyInfo])
async def list_strategies(
    search_service: SearchService = Depends(get_search_service)
) -> List[StrategyInfo]:
    """
    List all available search strategies with their configurations.

    Returns:
        List of strategy information
    """
    try:
        strategies = await search_service.list_strategies()
        return [
            StrategyInfo(
                name=s['name'],
                description=s['description'],
                config=s['config']
            )
            for s in strategies
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list strategies: {str(e)}")


@router.get("/config", response_model=SearchConfigResponse)
async def get_config(
    search_service: SearchService = Depends(get_search_service)
) -> SearchConfigResponse:
    """
    Get current search configuration.

    Returns:
        Current configuration including default strategy and strategy-specific settings
    """
    try:
        default_strategy = await search_service.get_default_strategy()

        strategies_config = {}
        for strategy_name in SearchService.AVAILABLE_STRATEGIES.keys():
            strategies_config[strategy_name] = await search_service.get_strategy_config(strategy_name)

        return SearchConfigResponse(
            default_strategy=default_strategy,
            strategies=strategies_config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/config/default", response_model=Dict[str, str])
async def update_default_strategy(
    request: UpdateDefaultStrategyRequest,
    search_service: SearchService = Depends(get_search_service)
) -> Dict[str, str]:
    """
    Update the default search strategy.

    Args:
        request: Request with new default strategy

    Returns:
        Confirmation message
    """
    try:
        await search_service.set_default_strategy(request.strategy)
        return {
            "message": f"Default strategy updated to {request.strategy}",
            "strategy": request.strategy
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update default strategy: {str(e)}")


@router.put("/config/strategies/{strategy_name}", response_model=Dict[str, str])
async def update_strategy_config(
    strategy_name: str,
    request: UpdateStrategyConfigRequest,
    search_service: SearchService = Depends(get_search_service)
) -> Dict[str, str]:
    """
    Update configuration for a specific strategy.

    Args:
        strategy_name: Name of the strategy
        request: New configuration

    Returns:
        Confirmation message
    """
    try:
        await search_service.update_strategy_config(strategy_name, request.config)
        return {
            "message": f"Configuration updated for {strategy_name}",
            "strategy": strategy_name
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.get("/config/strategies/{strategy_name}", response_model=Dict[str, Any])
async def get_strategy_config(
    strategy_name: str,
    search_service: SearchService = Depends(get_search_service)
) -> Dict[str, Any]:
    """
    Get configuration for a specific strategy.

    Args:
        strategy_name: Name of the strategy

    Returns:
        Strategy configuration
    """
    try:
        if strategy_name not in SearchService.AVAILABLE_STRATEGIES:
            raise HTTPException(
                status_code=404,
                detail=f"Strategy '{strategy_name}' not found"
            )

        config = await search_service.get_strategy_config(strategy_name)
        return config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get strategy config: {str(e)}")


@router.post("/test", response_model=TestStrategyResponse)
async def test_strategy(
    request: TestStrategyRequest,
    search_service: SearchService = Depends(get_search_service)
) -> TestStrategyResponse:
    """
    Test a search strategy with a query.

    Args:
        request: Test request with strategy and query

    Returns:
        Test results including timing and sample results
    """
    try:
        result = await search_service.test_strategy(
            request.strategy,
            request.test_query,
            request.config_override
        )

        return TestStrategyResponse(**result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Strategy test failed: {str(e)}")
