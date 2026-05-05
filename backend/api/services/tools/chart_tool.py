"""
Chart Tool Service

Provides explicit chart creation from data with auto-detection or user-specified type.
"""

import logging
from typing import List, Dict, Any, Optional, Literal

from api.services.chart_analyzer import ChartAnalyzer
from api.models import ToolResultData

logger = logging.getLogger(__name__)

ChartType = Literal["line", "bar", "pie", "scatter", "area", "radar", "composed"]


class ChartTool:
    """Tool for creating charts from data with auto-detection."""

    def __init__(self):
        self.analyzer = ChartAnalyzer()

    async def create_chart(
        self,
        data: List[Dict[str, Any]],
        chart_type: Optional[ChartType] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        x_key: Optional[str] = None,
        y_keys: Optional[List[str]] = None,
        x_label: Optional[str] = None,
        y_label: Optional[str] = None,
    ) -> ToolResultData:
        """
        Create a chart from data with automatic or manual type selection.

        Args:
            data: List of data points (dicts with consistent keys)
            chart_type: Optional chart type override (line, bar, pie, scatter, area, radar)
            title: Optional chart title
            description: Optional chart description
            x_key: Optional x-axis key override
            y_keys: Optional y-axis keys override
            x_label: Optional x-axis label
            y_label: Optional y-axis label

        Returns:
            ToolResultData with chart configuration

        Example usage in chat:
            "Create a bar chart showing sales by region"
            "Plot revenue over time as a line chart"
            "Show customer age vs purchase amount as a scatter plot"
        """
        try:
            if not data or len(data) == 0:
                return ToolResultData(
                    tool_name="create_chart",
                    tool_input={
                        "chart_type": chart_type,
                        "title": title,
                    },
                    result={"error": "No data provided"},
                    result_type="error",
                    execution_time_ms=0,
                )

            # Auto-detect chart type and configuration if not specified
            if not chart_type or not x_key or not y_keys:
                detected_type, config = self.analyzer.analyze_and_suggest(
                    data,
                    user_hint=chart_type
                )

                # Use detected values if not provided
                chart_type = chart_type or detected_type
                x_key = x_key or config["xKey"]
                y_keys = y_keys or config["yKeys"]
                colors = config.get("colors", [])
                legend = config.get("legend", True)
                grid = config.get("grid", True)
                stacked = config.get("stacked", False)
            else:
                # User provided all details, generate colors
                colors = self.analyzer._generate_color_palette(len(y_keys))
                legend = len(y_keys) > 1
                grid = True
                stacked = False

            # Build chart result
            chart_data = {
                "type": chart_type,
                "data": data,
                "xKey": x_key,
                "yKeys": y_keys,
                "colors": colors,
                "title": title,
                "description": description,
                "xLabel": x_label,
                "yLabel": y_label,
                "legend": legend,
                "grid": grid,
                "stacked": stacked,
            }

            logger.info(f"Created {chart_type} chart with {len(data)} data points")

            return ToolResultData(
                tool_name="create_chart",
                tool_input={
                    "chart_type": chart_type,
                    "data_count": len(data),
                    "title": title,
                },
                result=chart_data,
                result_type="chart",
                visualization_hint=chart_type,
                execution_time_ms=0,  # Set by caller if timing is tracked
            )

        except Exception as e:
            logger.error(f"Error creating chart: {e}", exc_info=True)
            return ToolResultData(
                tool_name="create_chart",
                tool_input={
                    "chart_type": chart_type,
                    "title": title,
                },
                result={"error": str(e)},
                result_type="error",
                execution_time_ms=0,
            )

    def should_use_chart(
        self,
        data: List[Dict[str, Any]],
        max_rows: int = 100
    ) -> bool:
        """
        Determine if data is suitable for chart visualization.

        Args:
            data: Data to check
            max_rows: Maximum number of rows for charting (default 100)

        Returns:
            True if data should be visualized as chart
        """
        if not data or len(data) == 0:
            return False

        # Too many rows - better as table
        if len(data) > max_rows:
            return False

        # Must be list of dicts
        if not isinstance(data, list) or not isinstance(data[0], dict):
            return False

        # Check if data has numeric values (chartable)
        first_row = data[0]
        has_numeric = any(
            isinstance(val, (int, float))
            for val in first_row.values()
        )

        return has_numeric


# Singleton instance
_chart_tool: Optional[ChartTool] = None


def get_chart_tool() -> ChartTool:
    """Get or create the singleton ChartTool instance."""
    global _chart_tool
    if _chart_tool is None:
        _chart_tool = ChartTool()
    return _chart_tool


async def create_chart(
    data: List[Dict[str, Any]],
    chart_type: Optional[str] = None,
    title: Optional[str] = None,
    **kwargs
) -> ToolResultData:
    """
    Convenience function for creating charts.

    Args:
        data: List of data points
        chart_type: Optional chart type
        title: Optional title
        **kwargs: Additional chart configuration

    Returns:
        ToolResultData with chart configuration
    """
    tool = get_chart_tool()
    return await tool.create_chart(
        data=data,
        chart_type=chart_type,
        title=title,
        **kwargs
    )
