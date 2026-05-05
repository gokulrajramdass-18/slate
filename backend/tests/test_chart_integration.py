"""
Integration tests for chart generation end-to-end flow.

Tests the complete flow from data analysis to component generation.
"""

import pytest
from api.services.chart_analyzer import ChartAnalyzer
from api.services.component_generator import ComponentGenerator
from api.models import ToolResultData


@pytest.mark.asyncio
async def test_line_chart_generation():
    """Test time series data generates line chart"""
    data = [
        {"date": "2024-01", "sales": 1000, "profit": 200},
        {"date": "2024-02", "sales": 1500, "profit": 300},
        {"date": "2024-03", "sales": 1200, "profit": 250},
    ]

    # Step 1: Analyze data
    analyzer = ChartAnalyzer()
    chart_type, config = analyzer.analyze_and_suggest(data)

    # For non-datetime data, should default to bar chart
    assert chart_type in ["bar", "line"]
    assert config["xKey"] == "date"
    assert "sales" in config["yKeys"]
    assert "profit" in config["yKeys"]

    # Step 2: Generate component
    generator = ComponentGenerator()
    tool_result = ToolResultData(
        tool_name="query_sales",
        tool_input={"query": "SELECT * FROM sales"},
        result=data,
        result_type="chart",
        execution_time_ms=150.5
    )

    component = generator._create_chart(tool_result)

    # Verify component structure
    assert component.component_type == "chart"
    assert component.props["type"] == chart_type
    assert len(component.props["data"]) == 3
    assert component.props["xKey"] == "date"
    assert "sales" in component.props["yKeys"]
    assert len(component.props["colors"]) == 2


@pytest.mark.asyncio
async def test_bar_chart_generation():
    """Test categorical data generates bar chart"""
    data = [
        {"category": "A", "value": 10},
        {"category": "B", "value": 20},
        {"category": "C", "value": 15},
    ]

    analyzer = ChartAnalyzer()
    chart_type, config = analyzer.analyze_and_suggest(data)

    # Single category + single value should be pie or bar
    assert chart_type in ["pie", "bar"]
    assert config["xKey"] == "category"
    assert "value" in config["yKeys"]


@pytest.mark.asyncio
async def test_scatter_plot_generation():
    """Test two numeric columns generate scatter plot"""
    data = [
        {"height": 170, "weight": 65},
        {"height": 180, "weight": 75},
        {"height": 165, "weight": 60},
    ]

    analyzer = ChartAnalyzer()
    chart_type, config = analyzer.analyze_and_suggest(data)

    assert chart_type == "scatter"
    assert config["xKey"] == "height"
    assert "weight" in config["yKeys"]


@pytest.mark.asyncio
async def test_multi_metric_radar_chart():
    """Test multiple numeric metrics generate appropriate chart"""
    data = [
        {"player": "A", "speed": 80, "strength": 70, "skill": 90, "defense": 60},
        {"player": "B", "speed": 70, "strength": 85, "skill": 75, "defense": 80},
    ]

    analyzer = ChartAnalyzer()
    chart_type, config = analyzer.analyze_and_suggest(data)

    # With categorical + multiple metrics, should be bar chart
    # Radar charts require specific structure or user override
    assert chart_type == "bar"
    assert len(config["yKeys"]) == 4  # speed, strength, skill, defense
    assert config["xKey"] == "player"

    # Test user can override to radar
    chart_type, config = analyzer.analyze_and_suggest(data, user_hint="radar")
    assert chart_type == "radar"


@pytest.mark.asyncio
async def test_user_override():
    """Test user can override chart type"""
    data = [
        {"month": "Jan", "sales": 1000},
        {"month": "Feb", "sales": 1500},
    ]

    analyzer = ChartAnalyzer()
    chart_type, config = analyzer.analyze_and_suggest(data, user_hint="pie")

    # User override should be respected
    assert chart_type == "pie"


@pytest.mark.asyncio
async def test_color_palette_generation():
    """Test color palette is generated for multiple series"""
    data = [
        {"month": "Jan", "a": 10, "b": 20, "c": 30},
        {"month": "Feb", "a": 15, "b": 25, "c": 35},
    ]

    analyzer = ChartAnalyzer()
    _, config = analyzer.analyze_and_suggest(data)

    # Should have 3 colors for 3 series
    assert len(config["colors"]) == 3
    assert all(color.startswith("#") for color in config["colors"])


@pytest.mark.asyncio
async def test_empty_data_handling():
    """Test empty data returns default config"""
    data = []

    analyzer = ChartAnalyzer()
    chart_type, config = analyzer.analyze_and_suggest(data)

    # Should return bar chart with empty config
    assert chart_type == "bar"
    assert config["xKey"] is None
    assert config["yKeys"] == []


@pytest.mark.asyncio
async def test_hana_result_format():
    """Test handling HANA tool response format"""
    # Simulating HANA query result wrapper
    hana_result = {
        "success": True,
        "rows": [
            {"product": "A", "revenue": 1000},
            {"product": "B", "revenue": 1500},
        ],
        "count": 2,
        "duration_ms": 45.2
    }

    generator = ComponentGenerator()
    tool_result = ToolResultData(
        tool_name="query_hana",
        tool_input={"query": "SELECT product, SUM(revenue) FROM sales GROUP BY product"},
        result=hana_result,
        result_type="chart",
        execution_time_ms=45.2
    )

    component = generator._create_chart(tool_result)

    # Should extract rows from wrapper
    assert component.component_type == "chart"
    assert len(component.props["data"]) == 2
    assert component.props["xKey"] == "product"
    assert "revenue" in component.props["yKeys"]


@pytest.mark.asyncio
async def test_component_routing_chart_type():
    """Test ComponentGenerator routes chart result_type correctly"""
    generator = ComponentGenerator()

    tool_result = ToolResultData(
        tool_name="get_chart_data",
        result=[{"x": 1, "y": 10}, {"x": 2, "y": 20}],
        result_type="chart",
        execution_time_ms=50
    )

    component = generator._match_component(tool_result)

    assert component is not None
    assert component.component_type == "chart"
