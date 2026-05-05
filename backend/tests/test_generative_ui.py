"""
Integration tests for generative UI feature.

Tests cover:
- Enhanced message schema (ui_components, render_mode, tool_results fields)
- Tool result capture and serialization
- ComponentGenerator service (tool result -> component spec mapping)
- DataQueryAgent integration
- Backward compatibility with existing chat messages
- Migration 016 integrity
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_tool_result_tabular():
    """Sample tool result with tabular data (matches backend ToolResultData schema)."""
    return {
        "tool_name": "query_sales_data",
        "tool_input": {"query": "SELECT * FROM SALES_DATA LIMIT 5"},
        "result": [
            {"PRODUCT_NAME": "Widget A", "REVENUE": 150000, "QUARTER": "Q1"},
            {"PRODUCT_NAME": "Widget B", "REVENUE": 230000, "QUARTER": "Q1"},
            {"PRODUCT_NAME": "Widget C", "REVENUE": 98000, "QUARTER": "Q1"},
        ],
        "result_type": "tabular",
        "suggested_component": None,
        "execution_time_ms": 245,
    }


@pytest.fixture
def sample_tool_result_scalar():
    """Sample tool result with single scalar value."""
    return {
        "tool_name": "get_total_revenue",
        "tool_input": {"query": "SELECT SUM(REVENUE) as total FROM SALES_DATA"},
        "result": [{"total": 478000}],
        "result_type": "scalar",
        "suggested_component": "metric_card",
        "execution_time_ms": 52,
    }


@pytest.fixture
def sample_tool_result_list():
    """Sample tool result with list data."""
    return {
        "tool_name": "fetch_api_data",
        "tool_input": {"endpoint": "/api/items"},
        "result": [
            {"name": "Item 1", "value": 42},
            {"name": "Item 2", "value": 87},
        ],
        "result_type": "list",
        "suggested_component": None,
        "execution_time_ms": 310,
    }


@pytest.fixture
def sample_tool_result_error():
    """Sample tool result representing an error."""
    return {
        "tool_name": "query_hana",
        "tool_input": {"query": "SELECT * FROM MISSING_TABLE"},
        "result": None,
        "result_type": "error",
        "suggested_component": None,
        "execution_time_ms": 15,
    }


@pytest.fixture
def sample_ui_components():
    """Sample UI component specs for a data table."""
    return [
        {
            "component_type": "hana_data_table",
            "props": {
                "columns": ["PRODUCT_NAME", "REVENUE", "QUARTER"],
                "rows": [
                    {"PRODUCT_NAME": "Widget A", "REVENUE": 150000, "QUARTER": "Q1"},
                ],
                "queryMetadata": {"tool_name": "query_sales_data", "row_count": 1},
                "title": "Sales Data",
            },
            "layout": {"width": "full", "priority": 1},
        }
    ]


# ============================================================================
# Test: Enhanced Message Schema (Database Layer)
# ============================================================================

@pytest.mark.asyncio
class TestEnhancedMessageSchema:
    """Test the extended chat_messages table with generative UI fields."""

    async def test_create_message_with_ui_components(self, sqlite_db):
        """Messages with ui_components field should persist correctly."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        ui_components = json.dumps([{
            "component_type": "hana_data_table",
            "props": {"columns": [], "rows": []},
            "layout": {"width": "full"},
        }])

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Here is your data:",
            "ui_components": ui_components,
            "render_mode": "generative_ui",
        })

        results = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        assert len(results) == 1
        msg = results[0]
        assert msg["ui_components"] is not None
        assert msg["render_mode"] == "generative_ui"

        parsed = json.loads(msg["ui_components"])
        assert len(parsed) == 1
        assert parsed[0]["component_type"] == "hana_data_table"

    async def test_create_message_with_tool_results(self, sqlite_db, sample_tool_result_tabular):
        """Messages with tool_results field should persist correctly."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        tool_results = json.dumps([sample_tool_result_tabular])

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Query executed.",
            "tool_results": tool_results,
            "render_mode": "generative_ui",
        })

        results = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        assert len(results) == 1
        parsed_tr = json.loads(results[0]["tool_results"])
        assert len(parsed_tr) == 1
        assert parsed_tr[0]["tool_name"] == "query_sales_data"
        assert parsed_tr[0]["execution_time_ms"] == 245

    async def test_create_message_with_all_generative_ui_fields(
        self, sqlite_db, sample_tool_result_tabular, sample_ui_components,
    ):
        """Messages with both ui_components and tool_results should work together."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Here are the Q1 sales results:",
            "ui_components": json.dumps(sample_ui_components),
            "render_mode": "generative_ui",
            "tool_results": json.dumps([sample_tool_result_tabular]),
        })

        results = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        msg = results[0]
        assert msg["content"] == "Here are the Q1 sales results:"
        assert msg["render_mode"] == "generative_ui"

        ui = json.loads(msg["ui_components"])
        tr = json.loads(msg["tool_results"])

        assert len(ui) == 1
        assert ui[0]["component_type"] == "hana_data_table"
        assert len(tr) == 1
        assert tr[0]["result_type"] == "tabular"

    async def test_render_mode_default_value(self, sqlite_db):
        """Default render_mode should be 'markdown' for backward compatibility."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Plain text response",
        })

        results = await sqlite_db.query(
            "SELECT render_mode FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )
        assert results[0]["render_mode"] == "markdown"

    async def test_hybrid_render_mode(self, sqlite_db, sample_ui_components):
        """Messages with render_mode='hybrid' carry both text and components."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Here is a **markdown** summary with the data table:",
            "ui_components": json.dumps(sample_ui_components),
            "render_mode": "hybrid",
        })

        results = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        msg = results[0]
        assert msg["render_mode"] == "hybrid"
        assert "**markdown**" in msg["content"]
        assert msg["ui_components"] is not None

    async def test_query_messages_by_render_mode(self, sqlite_db):
        """Filter messages by render_mode using the index."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        for mode in ["markdown", "generative_ui", "hybrid", "markdown", "generative_ui"]:
            await sqlite_db.create("chat_messages", {
                "session_id": session_id,
                "role": "assistant",
                "content": f"Message with {mode}",
                "render_mode": mode,
            })

        gen_ui = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE render_mode = :mode AND session_id = :sid",
            {"mode": "generative_ui", "sid": session_id},
        )
        assert len(gen_ui) == 2

        markdown = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE render_mode = :mode AND session_id = :sid",
            {"mode": "markdown", "sid": session_id},
        )
        assert len(markdown) == 2


# ============================================================================
# Test: Backward Compatibility
# ============================================================================

@pytest.mark.asyncio
class TestBackwardCompatibility:
    """Verify existing chat functionality is not broken by generative UI additions."""

    async def test_existing_messages_work_without_new_fields(self, sqlite_db):
        """Messages without new fields should continue to work."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Compat Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Old Style Session",
            "notebook_id": notebook_id,
        })

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "user",
            "content": "What is machine learning?",
        })

        results = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        msg = results[0]
        assert msg["content"] == "What is machine learning?"
        assert msg["role"] == "user"
        assert msg.get("ui_components") is None
        assert msg.get("tool_results") is None
        assert msg.get("render_mode") in (None, "markdown")

    async def test_user_messages_never_have_generative_ui(self, sqlite_db):
        """User messages should not carry ui_components or tool_results."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "user",
            "content": "Show me sales data",
        })

        results = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        msg = results[0]
        assert msg["role"] == "user"
        assert msg.get("ui_components") is None
        assert msg.get("tool_results") is None

    async def test_session_message_count_includes_generative_ui(self, sqlite_db):
        """Message count should include generative UI messages."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "user",
            "content": "Show me the data",
        })
        await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Here is the data",
            "render_mode": "generative_ui",
            "ui_components": json.dumps([{
                "component_type": "hana_data_table",
                "props": {},
            }]),
        })
        await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "user",
            "content": "Thanks!",
        })

        results = await sqlite_db.query(
            "SELECT COUNT(*) as count FROM chat_messages WHERE session_id = :sid",
            {"sid": session_id},
        )
        assert results[0]["count"] == 3

    async def test_delete_generative_ui_messages(self, sqlite_db):
        """Generative UI messages can be deleted like any other message."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Data table",
            "render_mode": "generative_ui",
            "ui_components": json.dumps([{
                "component_type": "hana_data_table",
                "props": {"rows": [{"a": 1}]},
            }]),
            "tool_results": json.dumps([{
                "tool_name": "query",
                "tool_input": {},
                "result": [{"a": 1}],
                "result_type": "tabular",
                "execution_time_ms": 100,
            }]),
        })

        # Verify it exists
        before = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )
        assert len(before) == 1

        await sqlite_db.delete("chat_messages", message_id)

        remaining = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )
        assert len(remaining) == 0


# ============================================================================
# Test: Tool Result Data Structures
# ============================================================================

@pytest.mark.asyncio
class TestToolResultDataStructures:
    """Test ToolResultData structure validation and serialization."""

    async def test_tabular_result_structure(self, sample_tool_result_tabular):
        """Tabular tool result should have correct structure."""
        tr = sample_tool_result_tabular
        assert tr["tool_name"] == "query_sales_data"
        assert tr["result_type"] == "tabular"
        assert isinstance(tr["result"], list)
        assert len(tr["result"]) == 3
        assert isinstance(tr["result"][0], dict)
        assert "PRODUCT_NAME" in tr["result"][0]

    async def test_scalar_result_structure(self, sample_tool_result_scalar):
        """Scalar tool result should have correct structure."""
        tr = sample_tool_result_scalar
        assert tr["result_type"] == "scalar"
        assert isinstance(tr["result"], list)
        assert len(tr["result"]) == 1
        assert "total" in tr["result"][0]

    async def test_multiple_tool_results_round_trip(
        self, sqlite_db, sample_tool_result_tabular, sample_tool_result_scalar,
    ):
        """Multiple tool results should serialize and deserialize correctly."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        tool_results = [sample_tool_result_tabular, sample_tool_result_scalar]
        tool_results_json = json.dumps(tool_results)

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Multi-tool response",
            "tool_results": tool_results_json,
            "render_mode": "generative_ui",
        })

        results = await sqlite_db.query(
            "SELECT tool_results FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        parsed = json.loads(results[0]["tool_results"])
        assert len(parsed) == 2
        assert parsed[0]["tool_name"] == "query_sales_data"
        assert parsed[1]["tool_name"] == "get_total_revenue"
        assert parsed[0]["result_type"] == "tabular"
        assert parsed[1]["result_type"] == "scalar"

    async def test_error_tool_result_in_message(self, sqlite_db, sample_tool_result_error):
        """Error tool results should be captured in messages."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Error querying the database.",
            "tool_results": json.dumps([sample_tool_result_error]),
            "render_mode": "markdown",
        })

        results = await sqlite_db.query(
            "SELECT * FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        parsed_tr = json.loads(results[0]["tool_results"])
        assert parsed_tr[0]["result_type"] == "error"
        assert parsed_tr[0]["result"] is None
        assert results[0]["render_mode"] == "markdown"


# ============================================================================
# Test: ComponentGenerator Service
# ============================================================================

class TestComponentGenerator:
    """Test the ComponentGenerator service mapping tool results to UI specs."""

    def _make_generator(self):
        from api.services.component_generator import ComponentGenerator
        return ComponentGenerator()

    def _make_tool_result(self, **kwargs):
        """Create a ToolResultData Pydantic object from kwargs."""
        from api.models import ToolResultData
        return ToolResultData(**kwargs)

    def test_tabular_result_maps_to_data_table(self):
        """A tabular tool result should produce a hana_data_table component."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="query_sales_data",
            tool_input={"query": "SELECT * FROM SALES_DATA LIMIT 5"},
            result=[
                {"PRODUCT_NAME": "Widget A", "REVENUE": 150000, "QUARTER": "Q1"},
                {"PRODUCT_NAME": "Widget B", "REVENUE": 230000, "QUARTER": "Q1"},
                {"PRODUCT_NAME": "Widget C", "REVENUE": 98000, "QUARTER": "Q1"},
            ],
            result_type="tabular",
            execution_time_ms=245,
        )
        components = gen.generate_components([tr])

        assert len(components) >= 1
        table_comp = components[0]
        assert table_comp.component_type == "hana_data_table"
        assert "columns" in table_comp.props
        assert "rows" in table_comp.props
        assert len(table_comp.props["rows"]) == 3

    def test_scalar_result_maps_to_metric_card(self):
        """A scalar tool result should produce a metric_card component."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="get_total_revenue",
            tool_input={"query": "SELECT SUM(REVENUE) as total FROM SALES_DATA"},
            result=[{"total": 478000}],
            result_type="scalar",
            suggested_component="metric_card",
            execution_time_ms=52,
        )
        components = gen.generate_components([tr])

        assert len(components) >= 1
        metric_comp = components[0]
        assert metric_comp.component_type == "metric_card"
        assert "value" in metric_comp.props
        assert metric_comp.props["value"] == 478000

    def test_list_of_dicts_maps_to_data_table(self):
        """A list of dicts should produce a hana_data_table component."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="fetch_api_data",
            tool_input={"endpoint": "/api/items"},
            result=[{"name": "Item 1", "value": 42}, {"name": "Item 2", "value": 87}],
            result_type="list",
            execution_time_ms=310,
        )
        components = gen.generate_components([tr])

        assert len(components) >= 1
        comp = components[0]
        assert comp.component_type == "hana_data_table"

    def test_mixed_results_produce_mixed_components(self):
        """Multiple tool results should produce corresponding component types."""
        gen = self._make_generator()
        tabular = self._make_tool_result(
            tool_name="query_sales",
            tool_input={},
            result=[{"a": 1}],
            result_type="tabular",
        )
        scalar = self._make_tool_result(
            tool_name="get_count",
            tool_input={},
            result=[{"total": 42}],
            result_type="scalar",
            suggested_component="metric_card",
        )
        components = gen.generate_components([tabular, scalar])

        assert len(components) == 2
        types = {c.component_type for c in components}
        assert "hana_data_table" in types
        assert "metric_card" in types

    def test_empty_tool_results_produce_no_components(self):
        """Empty tool results should produce no components."""
        gen = self._make_generator()
        components = gen.generate_components([])
        assert components == []

    def test_error_result_produces_no_component(self):
        """Error tool results should not produce any component."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="query_hana",
            tool_input={"query": "SELECT * FROM MISSING"},
            result=None,
            result_type="error",
        )
        components = gen.generate_components([tr])
        assert components == []

    def test_data_table_component_has_layout_hints(self):
        """Data table components should include layout hints."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="query",
            tool_input={},
            result=[{"a": 1}],
            result_type="tabular",
        )
        components = gen.generate_components([tr])

        comp = components[0]
        assert comp.layout is not None
        assert comp.layout["width"] == "full"

    def test_data_table_has_query_metadata(self):
        """Data table components should include query metadata."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="query_sales_data",
            tool_input={"query": "SELECT * FROM SALES"},
            result=[
                {"PRODUCT_NAME": "A", "REVENUE": 100, "QUARTER": "Q1"},
                {"PRODUCT_NAME": "B", "REVENUE": 200, "QUARTER": "Q1"},
                {"PRODUCT_NAME": "C", "REVENUE": 300, "QUARTER": "Q1"},
            ],
            result_type="tabular",
            execution_time_ms=100,
        )
        components = gen.generate_components([tr])

        comp = components[0]
        metadata = comp.props.get("queryMetadata", {})
        assert metadata.get("tool_name") == "query_sales_data"
        assert metadata.get("row_count") == 3
        assert metadata.get("column_count") == 3

    def test_metric_card_has_label(self):
        """Metric card should have a human-readable label."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="get_revenue",
            tool_input={"query": "SELECT SUM(x) as total"},
            result=[{"total": 100}],
            result_type="scalar",
            suggested_component="metric_card",
        )
        components = gen.generate_components([tr])

        comp = components[0]
        assert "label" in comp.props
        assert comp.props["label"]  # Not empty

    def test_suggested_component_override(self):
        """suggested_component field should override heuristic detection."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="get_data",
            tool_input={},
            result=[{"a": 1, "b": 2}, {"a": 3, "b": 4}],
            result_type="unknown",
            suggested_component="data_table",
        )
        components = gen.generate_components([tr])
        assert len(components) >= 1
        assert components[0].component_type == "hana_data_table"

    def test_json_viewer_for_nested_data(self):
        """Complex nested data should produce a json_viewer component."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="get_config",
            tool_input={},
            result={"nested": {"deep": {"value": 42}}, "list": [1, 2, 3]},
            result_type="unknown",
            suggested_component="json_viewer",
        )
        components = gen.generate_components([tr])
        assert len(components) >= 1
        assert components[0].component_type == "json_viewer"

    def test_chart_component(self):
        """Chart suggested_component should produce a chart component."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="get_trend",
            tool_input={},
            result=[{"month": "Jan", "sales": 100}, {"month": "Feb", "sales": 150}],
            result_type="unknown",
            suggested_component="chart",
        )
        components = gen.generate_components([tr])
        assert len(components) >= 1
        assert components[0].component_type == "chart"

    def test_heuristic_list_of_dicts_detection(self):
        """Heuristic should detect list of dicts as tabular data."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="get_items",
            tool_input={},
            result=[{"name": "A", "count": 10}, {"name": "B", "count": 20}],
            result_type="unknown",
        )
        components = gen.generate_components([tr])
        assert len(components) >= 1
        assert components[0].component_type == "hana_data_table"

    def test_heuristic_single_number_detection(self):
        """Heuristic should detect single number as metric."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="get_count",
            tool_input={},
            result=42,
            result_type="unknown",
        )
        components = gen.generate_components([tr])
        assert len(components) >= 1
        assert components[0].component_type == "metric_card"

    def test_string_result_produces_no_component(self):
        """String results should not produce a component (handled by markdown)."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="get_info",
            tool_input={},
            result="Just a plain text response",
            result_type="unknown",
        )
        components = gen.generate_components([tr])
        assert components == []

    def test_none_result_produces_no_component(self):
        """None/null results should not produce a component."""
        gen = self._make_generator()
        tr = self._make_tool_result(
            tool_name="broken_tool",
            tool_input={},
            result=None,
            result_type="empty",
        )
        components = gen.generate_components([tr])
        assert components == []


# ============================================================================
# Test: Pydantic Models
# ============================================================================

class TestPydanticModels:
    """Test the Pydantic models for generative UI data."""

    def test_ui_component_data_validation(self):
        """UIComponentData should validate correctly."""
        from api.models import UIComponentData

        comp = UIComponentData(
            component_type="hana_data_table",
            props={"columns": ["a"], "rows": [{"a": 1}]},
            layout={"width": "full"},
        )

        assert comp.component_type == "hana_data_table"
        assert comp.props["columns"] == ["a"]
        assert comp.layout["width"] == "full"

    def test_ui_component_data_minimal(self):
        """UIComponentData should work with only required fields."""
        from api.models import UIComponentData

        comp = UIComponentData(component_type="metric_card")
        assert comp.component_type == "metric_card"
        assert comp.props == {}
        assert comp.layout is None

    def test_tool_result_data_validation(self):
        """ToolResultData should validate correctly."""
        from api.models import ToolResultData

        tr = ToolResultData(
            tool_name="query_sales",
            tool_input={"query": "SELECT * FROM sales"},
            result=[{"a": 1}],
            result_type="tabular",
            execution_time_ms=100,
        )

        assert tr.tool_name == "query_sales"
        assert tr.result_type == "tabular"
        assert tr.execution_time_ms == 100

    def test_tool_result_data_defaults(self):
        """ToolResultData should have sensible defaults."""
        from api.models import ToolResultData

        tr = ToolResultData(
            tool_name="test",
            result="hello",
        )

        assert tr.result_type == "unknown"
        assert tr.tool_input == {}
        assert tr.suggested_component is None
        assert tr.execution_time_ms is None

    def test_render_mode_enum(self):
        """RenderMode enum should have expected values."""
        from api.models import RenderMode

        assert RenderMode.MARKDOWN == "markdown"
        assert RenderMode.GENERATIVE_UI == "generative_ui"
        assert RenderMode.HYBRID == "hybrid"


# ============================================================================
# Test: DataQueryAgent Integration
# ============================================================================

@pytest.mark.asyncio
class TestDataQueryAgentIntegration:
    """Test DataQueryAgent captures and formats tool results for generative UI."""

    async def test_agent_state_type_definition(self):
        """DataQueryState should have the required fields."""
        from open_notebook.agents.data_query_agent import DataQueryState

        annotations = DataQueryState.__annotations__
        assert "messages" in annotations
        assert "notebook_id" in annotations
        assert "session_id" in annotations
        assert "tools_available" in annotations

    async def test_agent_format_messages(self):
        """Agent should correctly format chat history into LangChain messages."""
        from open_notebook.agents.data_query_agent import DataQueryAgent
        from langchain_core.messages import HumanMessage, AIMessage

        agent = DataQueryAgent.__new__(DataQueryAgent)
        agent.tools = []

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        messages = agent._format_messages(history, "Show me data")

        assert len(messages) == 3
        assert isinstance(messages[0], HumanMessage)
        assert isinstance(messages[1], AIMessage)
        assert isinstance(messages[2], HumanMessage)
        assert messages[2].content == "Show me data"

    async def test_agent_should_continue_with_tool_calls(self):
        """Agent should route to 'tools' when LLM requests tool calls."""
        from open_notebook.agents.data_query_agent import DataQueryAgent

        agent = DataQueryAgent.__new__(DataQueryAgent)

        mock_message = MagicMock()
        mock_message.tool_calls = [{"name": "query_sales", "args": {}}]

        state = {
            "messages": [mock_message],
            "notebook_id": "nb-1",
            "session_id": "s-1",
            "tools_available": ["query_sales"],
        }

        result = agent._should_continue(state)
        assert result == "continue"

    async def test_agent_should_end_without_tool_calls(self):
        """Agent should end when LLM does not request tool calls."""
        from open_notebook.agents.data_query_agent import DataQueryAgent

        agent = DataQueryAgent.__new__(DataQueryAgent)

        mock_message = MagicMock()
        mock_message.tool_calls = []

        state = {
            "messages": [mock_message],
            "notebook_id": "nb-1",
            "session_id": "s-1",
            "tools_available": [],
        }

        result = agent._should_continue(state)
        assert result == "end"

    async def test_agent_get_tool_names(self):
        """Agent should return list of tool names."""
        from open_notebook.agents.data_query_agent import DataQueryAgent

        agent = DataQueryAgent.__new__(DataQueryAgent)

        tool1 = MagicMock()
        tool1.name = "query_sales_data"
        tool2 = MagicMock()
        tool2.name = "fetch_api_data"

        agent.tools = [tool1, tool2]

        names = agent.get_tool_names()
        assert names == ["query_sales_data", "fetch_api_data"]

    async def test_agent_format_empty_history(self):
        """Agent should handle empty chat history."""
        from open_notebook.agents.data_query_agent import DataQueryAgent
        from langchain_core.messages import HumanMessage

        agent = DataQueryAgent.__new__(DataQueryAgent)
        agent.tools = []

        messages = agent._format_messages([], "Hello")

        assert len(messages) == 1
        assert isinstance(messages[0], HumanMessage)
        assert messages[0].content == "Hello"


# ============================================================================
# Test: Large Data Handling
# ============================================================================

@pytest.mark.asyncio
class TestLargeDataHandling:
    """Test handling of large tool results and component specs."""

    async def test_large_table_result_persists(self, sqlite_db):
        """Large table results (1000+ rows) should persist without truncation."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        large_rows = [
            {"id": i, "name": f"Product {i}", "value": i * 100}
            for i in range(1000)
        ]

        large_tool_result = {
            "tool_name": "query_all",
            "tool_input": {"query": "SELECT * FROM products"},
            "result": large_rows,
            "result_type": "tabular",
            "execution_time_ms": 500,
        }

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Large result set",
            "tool_results": json.dumps([large_tool_result]),
            "render_mode": "generative_ui",
        })

        results = await sqlite_db.query(
            "SELECT tool_results FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        parsed = json.loads(results[0]["tool_results"])
        assert len(parsed[0]["result"]) == 1000

    async def test_multiple_ui_components_persist(self, sqlite_db):
        """Multiple UI components in a single message should all persist."""
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Test Notebook",
            "archived": False,
        })
        session_id = await sqlite_db.create("chat_sessions", {
            "title": "Test Session",
            "notebook_id": notebook_id,
        })

        components = [
            {
                "component_type": "metric_card",
                "props": {"value": i * 100, "label": f"Metric {i}"},
            }
            for i in range(10)
        ]

        message_id = await sqlite_db.create("chat_messages", {
            "session_id": session_id,
            "role": "assistant",
            "content": "Dashboard metrics",
            "ui_components": json.dumps(components),
            "render_mode": "generative_ui",
        })

        results = await sqlite_db.query(
            "SELECT ui_components FROM chat_messages WHERE id = :id",
            {"id": message_id},
        )

        parsed = json.loads(results[0]["ui_components"])
        assert len(parsed) == 10
        assert all(c["component_type"] == "metric_card" for c in parsed)


# ============================================================================
# Test: Migration 016 Integrity
# ============================================================================

@pytest.mark.asyncio
class TestMigrationIntegrity:
    """Test that migration 016 correctly alters the chat_messages table."""

    async def test_new_columns_exist(self, sqlite_db):
        """Verify ui_components, render_mode, and tool_results columns exist."""
        results = await sqlite_db.query(
            "PRAGMA table_info(chat_messages)",
        )

        column_names = [r["name"] for r in results]
        assert "ui_components" in column_names
        assert "render_mode" in column_names
        assert "tool_results" in column_names

    async def test_render_mode_index_exists(self, sqlite_db):
        """Verify the render_mode index was created."""
        results = await sqlite_db.query(
            "PRAGMA index_list(chat_messages)",
        )

        index_names = [r["name"] for r in results]
        assert "idx_chat_messages_render_mode" in index_names

    async def test_new_columns_are_nullable(self, sqlite_db):
        """New columns should be nullable (notnull = 0)."""
        results = await sqlite_db.query(
            "PRAGMA table_info(chat_messages)",
        )

        for col in results:
            if col["name"] in ("ui_components", "tool_results"):
                assert col["notnull"] == 0, f"{col['name']} should be nullable"

    async def test_render_mode_has_default(self, sqlite_db):
        """render_mode should have a default value of 'markdown'."""
        results = await sqlite_db.query(
            "PRAGMA table_info(chat_messages)",
        )

        for col in results:
            if col["name"] == "render_mode":
                default = col["dflt_value"]
                assert default is not None
                assert "markdown" in str(default)
