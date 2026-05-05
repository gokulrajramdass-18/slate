"""
Chart API Router

Endpoints for creating and managing chart visualizations.
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

from api.services.tools.chart_tool import get_chart_tool

router = APIRouter(prefix="/api/charts", tags=["Charts"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ChartCreateRequest(BaseModel):
    """Request model for creating a chart"""
    data: List[Dict[str, Any]] = Field(
        ...,
        description="Data points to visualize (list of dicts with consistent keys)",
        min_length=1
    )
    chart_type: Optional[Literal["line", "bar", "pie", "scatter", "area", "radar"]] = Field(
        None,
        description="Chart type (auto-detected if not specified)"
    )
    title: Optional[str] = Field(None, description="Chart title")
    description: Optional[str] = Field(None, description="Chart description")
    x_key: Optional[str] = Field(None, description="X-axis key (auto-detected if not specified)")
    y_keys: Optional[List[str]] = Field(None, description="Y-axis keys (auto-detected if not specified)")
    x_label: Optional[str] = Field(None, description="X-axis label")
    y_label: Optional[str] = Field(None, description="Y-axis label")


class ChartResponse(BaseModel):
    """Response model for chart creation"""
    chart_type: str
    data: List[Dict[str, Any]]
    x_key: str
    y_keys: List[str]
    colors: List[str]
    title: Optional[str] = None
    description: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    legend: bool
    grid: bool
    stacked: bool


class ChartAnalysisResponse(BaseModel):
    """Response model for chart type analysis"""
    recommended_type: str
    confidence: str
    alternatives: List[str]
    config: Dict[str, Any]


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/create", response_model=ChartResponse)
async def create_chart(request: ChartCreateRequest):
    """
    Create a chart visualization from data.

    Auto-detects optimal chart type based on data structure, or uses
    user-specified type.

    **Example Request**:
    ```json
    {
      "data": [
        {"month": "Jan", "sales": 1000, "profit": 200},
        {"month": "Feb", "sales": 1500, "profit": 300}
      ],
      "chart_type": "line",
      "title": "Monthly Sales & Profit"
    }
    ```

    **Auto-Detection**:
    - Time series data → Line or Area chart
    - Categories + values → Bar or Pie chart
    - Two numeric columns → Scatter plot
    - Multiple metrics → Radar chart

    Returns chart configuration ready for frontend rendering.
    """
    try:
        chart_tool = get_chart_tool()

        # Create chart
        result = await chart_tool.create_chart(
            data=request.data,
            chart_type=request.chart_type,
            title=request.title,
            description=request.description,
            x_key=request.x_key,
            y_keys=request.y_keys,
            x_label=request.x_label,
            y_label=request.y_label,
        )

        # Check for error
        if result.result_type == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.result.get("error", "Failed to create chart")
            )

        # Extract chart data from result
        chart_data = result.result

        return ChartResponse(
            chart_type=chart_data["type"],
            data=chart_data["data"],
            x_key=chart_data["xKey"],
            y_keys=chart_data["yKeys"],
            colors=chart_data["colors"],
            title=chart_data.get("title"),
            description=chart_data.get("description"),
            x_label=chart_data.get("xLabel"),
            y_label=chart_data.get("yLabel"),
            legend=chart_data.get("legend", True),
            grid=chart_data.get("grid", True),
            stacked=chart_data.get("stacked", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating chart: {str(e)}"
        )


@router.post("/analyze", response_model=ChartAnalysisResponse)
async def analyze_chart_type(data: List[Dict[str, Any]]):
    """
    Analyze data and recommend optimal chart type.

    Does not create a chart - only analyzes the data structure and
    returns recommendations.

    **Example Request**:
    ```json
    [
      {"product": "A", "revenue": 1000},
      {"product": "B", "revenue": 1500}
    ]
    ```

    **Returns**:
    ```json
    {
      "recommended_type": "bar",
      "confidence": "high",
      "alternatives": ["pie"],
      "config": {
        "xKey": "product",
        "yKeys": ["revenue"],
        "colors": ["#3b82f6"]
      }
    }
    ```
    """
    try:
        if not data or len(data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data array cannot be empty"
            )

        chart_tool = get_chart_tool()
        chart_type, config = chart_tool.analyzer.analyze_and_suggest(data)

        # Determine alternatives based on detected type
        alternatives = []
        if chart_type in ["line", "area"]:
            alternatives = ["bar"]
        elif chart_type == "bar":
            alternatives = ["line", "pie"]
        elif chart_type == "pie":
            alternatives = ["bar"]
        elif chart_type == "scatter":
            alternatives = ["line"]

        # Determine confidence based on data characteristics
        confidence = "high"
        if len(data) < 3:
            confidence = "low"
        elif len(data) < 10:
            confidence = "medium"

        return ChartAnalysisResponse(
            recommended_type=chart_type,
            confidence=confidence,
            alternatives=alternatives,
            config=config
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing data: {str(e)}"
        )


@router.get("/types")
async def get_chart_types():
    """
    Get list of supported chart types with descriptions.

    Returns information about all available chart types and their
    use cases.
    """
    return {
        "types": [
            {
                "type": "line",
                "name": "Line Chart",
                "description": "Best for showing trends over time or continuous data",
                "use_cases": ["Time series", "Trends", "Continuous data"]
            },
            {
                "type": "bar",
                "name": "Bar Chart",
                "description": "Best for comparing values across categories",
                "use_cases": ["Category comparison", "Rankings", "Frequency distribution"]
            },
            {
                "type": "pie",
                "name": "Pie Chart",
                "description": "Best for showing proportions of a whole (< 6 categories)",
                "use_cases": ["Proportions", "Percentages", "Parts of a whole"]
            },
            {
                "type": "scatter",
                "name": "Scatter Plot",
                "description": "Best for showing relationships between two numeric variables",
                "use_cases": ["Correlation", "Distribution", "Outlier detection"]
            },
            {
                "type": "area",
                "name": "Area Chart",
                "description": "Best for showing cumulative totals over time (multiple series)",
                "use_cases": ["Stacked data", "Volume over time", "Multiple trends"]
            },
            {
                "type": "radar",
                "name": "Radar Chart",
                "description": "Best for comparing multiple metrics across items",
                "use_cases": ["Multi-dimensional comparison", "Performance metrics", "Profiles"]
            }
        ]
    }
