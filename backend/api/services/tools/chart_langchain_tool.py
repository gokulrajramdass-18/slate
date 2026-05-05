"""
LangChain Tool Wrapper for Chart Visualization

Provides a structured tool that agents can call to create chart visualizations
from data extracted from the final deliverable or other sources.
"""

import logging
from typing import Optional, List, Dict, Any, Type
from pydantic import BaseModel, Field
from langchain.tools import BaseTool

from api.services.tools.chart_tool import get_chart_tool
from api.models import ToolResultData

logger = logging.getLogger(__name__)


class ChartInput(BaseModel):
    """Input schema for chart visualization tool."""

    data: List[Dict[str, Any]] = Field(
        ...,
        description="Array of data points to visualize. Each point should be a dict with consistent keys. Example: [{'month': 'Jan', 'revenue': 1000}, {'month': 'Feb', 'revenue': 1500}]"
    )
    chart_type: Optional[str] = Field(
        None,
        description="Type of chart to create: 'line', 'bar', 'pie', 'scatter', 'area', 'radar'. If not specified, will auto-detect based on data."
    )
    title: Optional[str] = Field(
        None,
        description="Title for the chart"
    )
    description: Optional[str] = Field(
        None,
        description="Optional description or subtitle for the chart"
    )
    x_key: Optional[str] = Field(
        None,
        description="Key in the data to use for x-axis. Auto-detected if not provided."
    )
    y_keys: Optional[List[str]] = Field(
        None,
        description="Keys in the data to use for y-axis (can be multiple for multi-line charts). Auto-detected if not provided."
    )
    x_label: Optional[str] = Field(
        None,
        description="Label for x-axis"
    )
    y_label: Optional[str] = Field(
        None,
        description="Label for y-axis"
    )


class ChartVisualizationTool(BaseTool):
    """
    Tool for creating interactive chart visualizations from data.

    Use this tool when the user asks to visualize data as a chart, graph, or plot.
    The tool automatically detects the best chart type and configuration from the data structure.

    Examples:
    - "Create a bar chart showing revenue by region"
    - "Plot sales over time"
    - "Show a pie chart of customer segments"
    - "Visualize temperature trends as a line chart"
    """

    name: str = "create_chart"
    description: str = """Create interactive charts and visualizations from data.

Use this tool whenever you need to visualize data as a chart. The tool supports:
- Line charts (for trends over time)
- Bar charts (for comparing categories)
- Pie charts (for showing proportions)
- Scatter plots (for relationships between variables)
- Area charts (for cumulative values)
- Radar charts (for multivariate data)

The tool will automatically detect the best chart type if not specified.
Pass an array of data points where each point is a dictionary with consistent keys.

Example input:
{
  "data": [
    {"month": "January", "revenue": 12000, "costs": 8000},
    {"month": "February", "revenue": 15000, "costs": 9000}
  ],
  "chart_type": "line",
  "title": "Revenue vs Costs Over Time"
}
"""

    args_schema: Type[BaseModel] = ChartInput

    def _run(
        self,
        data: List[Dict[str, Any]],
        chart_type: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        x_key: Optional[str] = None,
        y_keys: Optional[List[str]] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
    ) -> str:
        """Synchronous version - not implemented."""
        raise NotImplementedError("Use async version")

    async def _arun(
        self,
        data: List[Dict[str, Any]],
        chart_type: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        x_key: Optional[str] = None,
        y_keys: Optional[List[str]] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
    ) -> str:
        """
        Create a chart visualization from data.

        Returns a JSON string with chart configuration that will be
        rendered as an interactive chart in the UI.
        """
        try:
            import json
            tool = get_chart_tool()

            result: ToolResultData = await tool.create_chart(
                data=data,
                chart_type=chart_type,
                title=title,
                description=description,
                x_key=x_key,
                y_keys=y_keys,
                x_label=x_label,
                y_label=y_label,
            )

            if result.result_type == "error":
                return json.dumps({"error": str(result.result)})

            # Return the chart configuration as JSON
            # The DataQueryAgent will parse this and capture it for the component generator
            chart_config = result.result

            # Return JSON with metadata for the agent to capture
            response = {
                "type": chart_config.get("type"),
                "data": chart_config.get("data"),
                "xKey": chart_config.get("xKey"),
                "yKeys": chart_config.get("yKeys"),
                "colors": chart_config.get("colors"),
                "title": chart_config.get("title"),
                "description": chart_config.get("description"),
                "xLabel": chart_config.get("xLabel"),
                "yLabel": chart_config.get("yLabel"),
                "legend": chart_config.get("legend"),
                "grid": chart_config.get("grid"),
                "stacked": chart_config.get("stacked"),
                "visualization_hint": chart_config.get("type"),  # Signal this is a chart
            }

            return json.dumps(response)

        except Exception as e:
            logger.error(f"Error in ChartVisualizationTool: {e}", exc_info=True)
            import json
            return json.dumps({"error": str(e)})
