"""
Chart Analyzer Service

Analyzes data structure and recommends optimal chart type for visualization.
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from datetime import datetime


class ChartAnalyzer:
    """Analyzes data structure and recommends optimal chart type"""

    def analyze_and_suggest(
        self,
        data: List[Dict[str, Any]],
        user_hint: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Analyze data and return (chart_type, chart_config)

        Args:
            data: List of dictionaries representing data points
            user_hint: Optional user override for chart type

        Returns:
            tuple: (chart_type, chart_config)
                chart_type: "line", "bar", "pie", "scatter", "area", "radar"
                chart_config: Configuration with xKey, yKeys, colors, etc.
        """
        if not data or len(data) == 0:
            return "bar", {"xKey": None, "yKeys": []}

        # Convert to DataFrame for analysis
        df = pd.DataFrame(data)

        # User override
        if user_hint:
            return user_hint, self._extract_config(df, user_hint)

        # Detect data characteristics
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        date_cols = self._detect_date_columns(df)
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

        # Remove date columns from categorical
        categorical_cols = [c for c in categorical_cols if c not in date_cols]

        # Decision tree for chart type
        if len(date_cols) > 0 and len(numeric_cols) > 0:
            # Time series data → Line or Area chart
            chart_type = "area" if len(numeric_cols) > 2 else "line"
            return chart_type, self._extract_config(df, chart_type, date_cols[0], numeric_cols)

        if len(categorical_cols) == 1 and len(numeric_cols) == 1:
            # Single category + single value
            # Default to BAR for comparisons (better for most use cases)
            # Only use PIE if explicitly requested or data represents percentages/proportions
            unique_categories = df[categorical_cols[0]].nunique()

            # Check if data looks like percentages/proportions
            numeric_col = numeric_cols[0]
            max_val = df[numeric_col].max()
            is_percentage = max_val <= 100 and df[numeric_col].min() >= 0

            # Prefer bar chart unless:
            # - Few categories AND looks like percentage data
            # - User explicitly requested pie
            if user_hint == "pie":
                chart_type = "pie"
            elif unique_categories <= 6 and is_percentage:
                chart_type = "pie"
            else:
                chart_type = "bar"

            return chart_type, self._extract_config(df, chart_type, categorical_cols[0], numeric_cols)

        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            # Categories + metrics → Bar chart
            return "bar", self._extract_config(df, "bar", categorical_cols[0], numeric_cols)

        if len(numeric_cols) == 2:
            # Two numeric columns → Scatter plot
            return "scatter", self._extract_config(df, "scatter", numeric_cols[0], [numeric_cols[1]])

        if len(numeric_cols) > 2:
            # Multiple metrics → Radar chart
            return "radar", self._extract_config(df, "radar", categorical_cols[0] if categorical_cols else None, numeric_cols)

        # Default fallback
        return "bar", self._extract_config(df, "bar")

    def _detect_date_columns(self, df: pd.DataFrame) -> List[str]:
        """Detect columns containing date/time values"""
        date_cols = []
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                date_cols.append(col)
            elif df[col].dtype == 'object':
                # Try parsing as date
                try:
                    pd.to_datetime(df[col].head(10), errors='raise')
                    date_cols.append(col)
                except:
                    pass
        return date_cols

    def _extract_config(
        self,
        df: pd.DataFrame,
        chart_type: str,
        x_key: Optional[str] = None,
        y_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Extract chart configuration from DataFrame"""
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()

        if not x_key:
            # Use first column as x-axis
            x_key = df.columns[0]

        if not y_keys:
            # Use all numeric columns as y-axis
            y_keys = numeric_cols if numeric_cols else [df.columns[1]] if len(df.columns) > 1 else []

        # Generate colors for each series
        colors = self._generate_color_palette(len(y_keys))

        return {
            "xKey": x_key,
            "yKeys": y_keys,
            "colors": colors,
            "stacked": False,  # Can be overridden
            "legend": len(y_keys) > 1,
            "grid": True,
        }

    def _generate_color_palette(self, n: int) -> List[str]:
        """Generate n distinct colors"""
        # Professional color palette
        base_colors = [
            "#3b82f6",  # Blue
            "#10b981",  # Green
            "#f59e0b",  # Orange
            "#ef4444",  # Red
            "#8b5cf6",  # Purple
            "#ec4899",  # Pink
            "#14b8a6",  # Teal
            "#f97316",  # Deep Orange
        ]
        # Repeat if needed
        return (base_colors * ((n // len(base_colors)) + 1))[:n]
