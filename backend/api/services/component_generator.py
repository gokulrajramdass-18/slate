"""
Component Generator Service

Maps tool execution results to UI component specifications for generative UI.
Analyzes tool output structure to determine the best visual representation
(data table, chart, metric card, JSON viewer, etc.).
"""

import logging
from typing import Any, Dict, List, Optional

from api.models import ToolResultData, UIComponentData
from api.services.chart_analyzer import ChartAnalyzer

logger = logging.getLogger(__name__)


class ComponentGenerator:
    """
    Generates UI component specifications from tool execution results.

    Analyzes the structure and content of tool results to determine
    the most appropriate frontend component for rendering.
    """

    def __init__(self):
        """Initialize ComponentGenerator with ChartAnalyzer."""
        self.chart_analyzer = ChartAnalyzer()

    def generate_components(
        self,
        tool_results: List[ToolResultData],
        message_content: str = "",
    ) -> List[UIComponentData]:
        """
        Generate UI component specs from a list of tool results.

        Args:
            tool_results: ToolResultData instances from agent execution.
            message_content: The assistant's text response (for context).

        Returns:
            List of UIComponentData ready for frontend rendering.
        """
        components: List[UIComponentData] = []

        # Extract chart type hint from message content if present
        # This allows detecting "draw a pie chart", "show bar chart", etc.
        chart_type_hint = self._extract_chart_type_from_message(message_content)

        for result in tool_results:
            # Pass chart type hint to component matching
            component = self._match_component(result, chart_type_hint)
            if component:
                components.append(component)

        return components

    def _extract_chart_type_from_message(self, message: str) -> Optional[str]:
        """
        Extract chart type from user message.

        Returns: "pie", "bar", "line", "scatter", "area", "radar", or None
        """
        if not message:
            return None

        message_lower = message.lower()

        # Check for explicit chart type mentions
        chart_types = {
            "pie": ["pie chart", "pie graph"],
            "bar": ["bar chart", "bar graph", "column chart"],
            "line": ["line chart", "line graph"],
            "scatter": ["scatter", "scatter plot"],
            "area": ["area chart", "area graph"],
            "radar": ["radar", "spider chart", "radar chart"]
        }

        for chart_type, keywords in chart_types.items():
            if any(keyword in message_lower for keyword in keywords):
                return chart_type

        return None

    def generate_from_dicts(
        self,
        raw_results: List[Dict[str, Any]],
        message_content: str = "",
    ) -> List[UIComponentData]:
        """
        Convenience wrapper that accepts raw dicts (e.g. from JSON storage).

        Args:
            raw_results: List of dicts matching ToolResultData schema.
            message_content: The assistant's text response (for context).

        Returns:
            List of UIComponentData.
        """
        parsed = [ToolResultData(**r) for r in raw_results]
        return self.generate_components(parsed, message_content)

    def _match_component(self, result: ToolResultData, chart_type_hint: Optional[str] = None) -> Optional[UIComponentData]:
        """
        Match a single tool result to a UI component specification.

        Uses result_type and tool_name to determine the best component.

        Args:
            result: A ToolResultData instance.
            chart_type_hint: Optional chart type extracted from user message

        Returns:
            UIComponentData or None if no suitable component.
        """
        result_type = result.result_type
        data = result.result

        # Skip errors and empty results
        if result_type == "error" or result_type == "empty" or data is None:
            return None

        # PRIORITY CHECK: If data has visualization_hint, treat as chart
        # This allows HANA queries and API calls to automatically render as charts
        if result.visualization_hint or (isinstance(data, dict) and data.get("visualization_hint")):
            return self._create_chart(result, chart_type_hint)

        # Route by result type
        if result_type == "chart":
            return self._create_chart(result, chart_type_hint)
        elif result_type == "tabular":
            return self._create_data_table(result)
        elif result_type == "scalar":
            component = self._create_metric_card(result)
            # Fallback to JSON viewer if metric card can't be created
            return component or self._create_json_viewer(result)
        elif result_type == "list":
            # Check if list items are dicts (tabular) or simple values
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return self._create_data_table(result)
            # MCP/API pattern: {count: N, <items_key>: [...]}
            # The _create_data_table will extract the list from the wrapper
            if isinstance(data, dict):
                mcp_list_keys = ["accounts", "opportunities", "prospects", "users", "contacts",
                               "leads", "deals", "items", "results", "data", "records", "rows"]
                for key in mcp_list_keys:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        if items and isinstance(items[0], dict):
                            return self._create_data_table(result)
            return self._create_json_viewer(result)

        # Fall back to suggested_component if available
        suggested = result.suggested_component
        if suggested == "data_table" or suggested == "hana_data_table":
            return self._create_data_table(result)
        elif suggested == "metric_card":
            component = self._create_metric_card(result)
            # Fallback to JSON viewer if metric card can't be created
            return component or self._create_json_viewer(result)
        elif suggested == "chart" or suggested == "bar_chart":
            return self._create_chart(result)
        elif suggested == "json_viewer":
            return self._create_json_viewer(result)

        # Heuristic fallback: try to detect from data shape
        return self._detect_component_from_data(result)

    def _create_data_table(self, result: ToolResultData) -> UIComponentData:
        """
        Create a data_table component from tabular tool results.

        Args:
            result: ToolResultData with tabular data.

        Returns:
            UIComponentData for hana_data_table component.
        """
        data = result.result
        tool_name = result.tool_name
        tool_input = result.tool_input

        # Extract rows
        rows = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            # Handle HANA tool response format: {"success": true, "rows": [...], "count": N, "duration_ms": X}
            if "rows" in data:
                rows = data["rows"]
            elif "data" in data:
                rows = data["data"]
            else:
                # MCP/API pattern: {count: N, <items_key>: [...]}
                # Common keys: accounts, opportunities, prospects, users, contacts, leads, deals, items, results, records
                mcp_list_keys = ["accounts", "opportunities", "prospects", "users", "contacts",
                               "leads", "deals", "items", "results", "records"]
                for key in mcp_list_keys:
                    if key in data and isinstance(data[key], list):
                        rows = data[key]
                        break

                # If still no rows found, single dict might be a single row result
                if not rows:
                    rows = [data]

        # Validate rows structure
        if not isinstance(rows, list):
            rows = []

        # Extract column names from first row and build column objects
        columns = []
        if rows and isinstance(rows[0], dict):
            column_keys = list(rows[0].keys())
            # Convert to column objects with key and label
            columns = [{"key": col, "label": col, "sortable": True} for col in column_keys]

        # Extract query from tool input
        query = None
        if tool_input:
            query = tool_input.get("query", tool_input.get("sql", ""))

        # Build props matching HANADataTable interface
        props = {
            "columns": columns,
            "rows": rows,
            "title": _make_table_title(tool_name, tool_input),
            "total_count": len(rows),
        }

        # Add optional props if available
        if query:
            props["query"] = query
        if result.execution_time_ms is not None:
            props["execution_time_ms"] = result.execution_time_ms

        # Try to extract source table name from tool_name or tool_input
        if "table" in tool_input:
            props["source_table"] = tool_input.get("table")

        return UIComponentData(
            component_type="hana_data_table",
            props=props,
            layout={
                "width": "full",
                "priority": 1,
            },
        )

    def _create_metric_card(self, result: ToolResultData) -> Optional[UIComponentData]:
        """
        Create a metric_card component from a scalar tool result.

        Args:
            result: ToolResultData with scalar data.

        Returns:
            UIComponentData for metric_card component, or None if data is not suitable.
        """
        data = result.result
        tool_name = result.tool_name
        tool_input = result.tool_input

        # Skip API response objects (they have success, status_code, content, url keys)
        if isinstance(data, dict):
            # Check if this looks like an API response object
            if "success" in data and "status_code" in data and "content" in data:
                logger.debug(f"Skipping metric card for API response object from {tool_name}")
                return None

            # Handle HANA tool response format: {"success": true, "rows": [...], ...}
            if "rows" in data:
                data = data["rows"]

        # Extract the value
        value = data
        label = tool_input.get("query", tool_name) if tool_input else tool_name

        # If data is a dict with a single key, extract it
        if isinstance(data, dict) and len(data) == 1:
            key = list(data.keys())[0]
            value = data[key]
            label = key

        # If data is a list with a single dict with a single key (e.g., COUNT query)
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
            row = data[0]
            if len(row) == 1:
                key = list(row.keys())[0]
                value = row[key]
                label = key

        # Final validation: value must be scalar (string, number, bool)
        if isinstance(value, (dict, list)):
            logger.debug(f"Skipping metric card for non-scalar value from {tool_name}: {type(value)}")
            return None

        return UIComponentData(
            component_type="metric_card",
            props={
                "value": value,
                "label": _humanize_label(label),
                "source": tool_name,
            },
            layout={
                "width": "auto",
                "priority": 2,
            },
        )

    def _create_chart(self, result: ToolResultData, chart_type_hint: Optional[str] = None) -> UIComponentData:
        """
        Create a chart component from time-series or categorical data.

        Args:
            result: ToolResultData.
            chart_type_hint: Optional chart type from user message ("pie", "bar", etc.)

        Returns:
            UIComponentData for chart component.
        """
        data = result.result
        tool_name = result.tool_name
        tool_input = result.tool_input or {}

        # Check if backend already provided chart config (from HANA/API tools)
        visualization_hint = result.visualization_hint
        chart_config_from_backend = None

        # Handle HANA tool response format
        if isinstance(data, dict):
            # First check if this is already a chart config from create_chart tool
            if "data" in data and "xKey" in data and "yKeys" in data:
                # This is a pre-configured chart from create_chart tool
                rows = data.get("data", [])
                # Extract chart config directly
                chart_config_from_backend = {
                    "xKey": data.get("xKey"),
                    "yKeys": data.get("yKeys"),
                    "colors": data.get("colors", []),
                    "legend": data.get("legend", True),
                    "grid": data.get("grid", True),
                    "stacked": data.get("stacked", False),
                }
                visualization_hint = data.get("type") or data.get("visualization_hint")
            elif "rows" in data:
                rows = data["rows"]
            else:
                rows = data if isinstance(data, list) else []

            # Extract chart config if provided by backend
            if "visualization_hint" in data:
                visualization_hint = data["visualization_hint"]
            if "chart_config" in data:
                chart_config_from_backend = data["chart_config"]
        else:
            rows = data if isinstance(data, list) else []

        # Extract metadata for chart
        metadata = {
            "title": _make_table_title(tool_name, tool_input),
        }

        # Use backend-provided config if available, otherwise analyze
        if chart_config_from_backend and visualization_hint:
            chart_type = visualization_hint
            chart_config = chart_config_from_backend
        else:
            # Prefer chart_type_hint from user message over tool hint
            user_hint = chart_type_hint or visualization_hint or tool_input.get("chart_type")

            # Use ChartAnalyzer to determine chart type and configuration
            chart_type, chart_config = self.chart_analyzer.analyze_and_suggest(
                rows,
                user_hint=user_hint
            )

        # Build component spec with analyzed configuration
        return UIComponentData(
            component_type="chart",
            props={
                "type": chart_type,
                "data": rows,
                "xKey": chart_config["xKey"],
                "yKeys": chart_config["yKeys"],
                "colors": chart_config.get("colors", []),
                "title": metadata.get("title"),
                "description": tool_input.get("description"),
                "xLabel": tool_input.get("x_label"),
                "yLabel": tool_input.get("y_label"),
                "legend": chart_config.get("legend", True),
                "grid": chart_config.get("grid", True),
                "stacked": chart_config.get("stacked", False),
            },
            layout={
                "width": "full",
                "height": "400px",
                "priority": 1,
            },
        )

    def _create_json_viewer(self, result: ToolResultData) -> UIComponentData:
        """
        Create a json_viewer component for complex/nested data.

        Args:
            result: ToolResultData.

        Returns:
            UIComponentData for json_viewer component.
        """
        data = result.result
        tool_name = result.tool_name

        return UIComponentData(
            component_type="json_viewer",
            props={
                "data": data,
                "title": f"Result from {_humanize_label(tool_name)}",
                "collapsed": True,
            },
            layout={
                "width": "full",
                "priority": 3,
            },
        )

    def _detect_component_from_data(
        self, result: ToolResultData
    ) -> Optional[UIComponentData]:
        """
        Heuristic fallback: detect the best component from data shape.

        Args:
            result: ToolResultData.

        Returns:
            UIComponentData or None.
        """
        data = result.result

        if data is None:
            return None

        # List of dicts -> data table
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return self._create_data_table(result)

        # MCP/API pattern: {count: N, <items_key>: [...]} -> data table
        # Common patterns: accounts, opportunities, prospects, users, etc.
        if isinstance(data, dict):
            # Look for list fields that might contain the actual data
            for key in ["accounts", "opportunities", "prospects", "users", "contacts",
                       "leads", "deals", "items", "results", "data", "records", "rows"]:
                if key in data:
                    items = data[key]
                    if isinstance(items, list) and items and isinstance(items[0], dict):
                        # Found a list of objects - this should be a table
                        # Modify result to point to the items list
                        result.result = items
                        return self._create_data_table(result)

        # Single number -> metric card
        if isinstance(data, (int, float)):
            component = self._create_metric_card(result)
            return component or self._create_json_viewer(result)

        # Dict with nested structure -> check for metrics first, then JSON viewer
        if isinstance(data, dict):
            # Check for single-value dict (metric)
            if len(data) == 1:
                val = list(data.values())[0]
                if isinstance(val, (int, float)):
                    component = self._create_metric_card(result)
                    return component or self._create_json_viewer(result)
            return self._create_json_viewer(result)

        # String -> no component (handled by markdown)
        if isinstance(data, str):
            return None

        return None


# ============================================================================
# Helper Functions
# ============================================================================

def _make_table_title(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Generate a human-readable title for a data table."""
    query = tool_input.get("query", tool_input.get("sql", ""))
    if query:
        # Truncate long queries
        return query[:80] + ("..." if len(query) > 80 else "")
    return _humanize_label(tool_name)


def _humanize_label(name: str) -> str:
    """Convert tool_name or key to human-readable label."""
    return name.replace("_", " ").replace("-", " ").title()


# ============================================================================
# Singleton Accessor
# ============================================================================

_generator: Optional[ComponentGenerator] = None


def get_component_generator() -> ComponentGenerator:
    """Get or create the singleton ComponentGenerator instance."""
    global _generator
    if _generator is None:
        _generator = ComponentGenerator()
    return _generator


# ============================================================================
# Convenience Functions
# ============================================================================

def generate_components(
    tool_results: List[Dict[str, Any]],
    message_content: str = "",
) -> List[Dict[str, Any]]:
    """
    Module-level convenience function for generating UI components.

    Accepts raw dicts and returns plain dicts (for callers that don't
    want to deal with Pydantic models directly).

    Args:
        tool_results: List of ToolResultData-shaped dicts.
        message_content: Optional assistant text for context.

    Returns:
        List of UIComponentData dicts.
    """
    gen = get_component_generator()
    components = gen.generate_from_dicts(tool_results, message_content)
    return [c.model_dump() for c in components]


def determine_render_mode(
    content: str,
    components: List[Dict[str, Any]],
) -> str:
    """
    Determine the appropriate render mode based on content and components.

    Args:
        content: The assistant's markdown text.
        components: List of generated UI component dicts.

    Returns:
        'markdown', 'generative_ui', or 'hybrid'.
    """
    if not components:
        return "markdown"

    # If there's substantial markdown content alongside components, use hybrid
    # "Substantial" = more than a short intro sentence (> 80 chars with formatting)
    stripped = content.strip()
    has_significant_text = (
        len(stripped) > 80
        or "\n" in stripped
        or "**" in stripped
        or "##" in stripped
        or "- " in stripped
    )

    if has_significant_text:
        return "hybrid"

    return "generative_ui"
