"""
End-to-end integration test for the complete generative UI flow.

Tests the full pipeline:
  User query -> Chat API -> DataQueryAgent (with tool capture)
  -> ComponentGenerator -> Database persistence -> API response

Covers:
- HANA query tool returning a data_table component
- API source tool returning a json_viewer component
- Multiple tools in a single message producing hybrid render mode
- enable_generative_ui=False preserving backward compatibility
- Database column persistence of ui_components, render_mode, tool_results
"""

import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Helpers
# ============================================================================

def _make_mock_agent(response_text: str, tool_results: List[Dict[str, Any]]):
    """
    Build a mock DataQueryAgent whose invoke() returns *response_text*
    and whose get_captured_tool_results() returns *tool_results*.
    """
    agent = MagicMock()
    agent.invoke = AsyncMock(return_value=response_text)
    agent.get_captured_tool_results.return_value = tool_results
    agent.tools = [MagicMock(name="query_hana_table")]
    agent.get_tool_names.return_value = ["query_hana_table"]
    return agent


TABULAR_TOOL_RESULT = {
    "tool_name": "query_hana_table",
    "tool_input": {"query": "SELECT * FROM CUSTOMERS ORDER BY REVENUE DESC LIMIT 5"},
    "result": [
        {"CUSTOMER_NAME": "Acme Corp", "REVENUE": 500000, "REGION": "EMEA"},
        {"CUSTOMER_NAME": "Globex Inc", "REVENUE": 430000, "REGION": "NA"},
        {"CUSTOMER_NAME": "Initech", "REVENUE": 320000, "REGION": "APAC"},
        {"CUSTOMER_NAME": "Umbrella Co", "REVENUE": 290000, "REGION": "NA"},
        {"CUSTOMER_NAME": "Soylent", "REVENUE": 210000, "REGION": "EMEA"},
    ],
    "result_type": "tabular",
    "suggested_component": "hana_data_table",
    "execution_time_ms": 187.5,
}

SCALAR_TOOL_RESULT = {
    "tool_name": "get_customer_count",
    "tool_input": {"query": "SELECT COUNT(*) as total FROM CUSTOMERS"},
    "result": [{"total": 1523}],
    "result_type": "scalar",
    "suggested_component": "metric_card",
    "execution_time_ms": 34.2,
}

API_JSON_TOOL_RESULT = {
    "tool_name": "fetch_api_endpoint",
    "tool_input": {"endpoint": "/api/v2/status"},
    "result": {"status": "healthy", "uptime_hours": 2345, "services": {"db": "ok", "cache": "ok"}},
    "result_type": "unknown",
    "suggested_component": "json_viewer",
    "execution_time_ms": 412.0,
}

MOCK_CREDENTIAL = {
    "model_name": "claude-3-5-sonnet-20241022",
    "base_url": "https://api.anthropic.com",
    "api_key": "test-key",
}


def _common_patches():
    """Return a list of context managers that mock all chat endpoint dependencies."""
    return [
        patch(
            "api.services.data_query_tools.create_tools_for_notebook",
            new_callable=AsyncMock,
        ),
        patch(
            "open_notebook.agents.data_query_agent.DataQueryAgent",
        ),
        patch(
            "api.services.settings.get_setting",
            new_callable=AsyncMock,
            return_value="test-model-id",
        ),
    ]


# ============================================================================
# Test: Complete Non-Streaming Flow
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestGenerativeUIFlowNonStreaming:
    """End-to-end test: non-streaming chat with generative UI."""

    async def test_hana_query_produces_data_table(self, async_test_client):
        """
        Send a HANA query with enable_generative_ui=True.
        Expect response with hana_data_table component, render_mode=hybrid.
        """
        client = async_test_client

        # --- Setup: notebook + session ---
        nb = await client.post("/api/notebooks", json={
            "name": "E2E GenUI Test",
            "description": "Testing generative UI flow",
        })
        notebook_id = nb.json()["id"]

        # Mock get_setting for session creation too
        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id,
                "title": "HANA Query Test",
            })
        session_id = session.json()["id"]

        # --- Mock all dependencies ---
        mock_tool = MagicMock()
        mock_tool.name = "query_hana_table"
        mock_tool.description = "Query HANA table"

        agent = _make_mock_agent(
            response_text="Here are the top 5 customers by revenue.",
            tool_results=[TABULAR_TOOL_RESULT],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent) as MockAgent, \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            response = await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Show top customers",
                    "enable_generative_ui": True,
                    "stream": False,
                    "include_context": False,
                },
            )

        assert response.status_code == 200
        data = response.json()

        # --- Assert response structure ---
        assert data["session_id"] == session_id
        assert data["assistant_message"]["content"] == "Here are the top 5 customers by revenue."
        assert data["assistant_message"]["render_mode"] == "hybrid"

        ui = data["assistant_message"]["ui_components"]
        assert ui is not None
        assert len(ui) >= 1

        table_comp = ui[0]
        assert table_comp["component_type"] == "hana_data_table"
        assert "columns" in table_comp["props"]
        assert "rows" in table_comp["props"]
        assert len(table_comp["props"]["rows"]) == 5
        assert set(table_comp["props"]["columns"]) == {"CUSTOMER_NAME", "REVENUE", "REGION"}

        tr = data["assistant_message"]["tool_results"]
        assert tr is not None
        assert len(tr) == 1
        assert tr[0]["tool_name"] == "query_hana_table"

    async def test_api_call_produces_json_viewer(self, async_test_client):
        """
        Send an API-related query with enable_generative_ui=True.
        Expect json_viewer component.
        """
        client = async_test_client

        nb = await client.post("/api/notebooks", json={
            "name": "API GenUI Test", "description": "Test"
        })
        notebook_id = nb.json()["id"]

        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id, "title": "API Test"
            })
        session_id = session.json()["id"]

        mock_tool = MagicMock()
        mock_tool.name = "fetch_api_endpoint"
        mock_tool.description = "Fetch API endpoint"

        agent = _make_mock_agent(
            response_text="The service status is healthy.",
            tool_results=[API_JSON_TOOL_RESULT],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent), \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            response = await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Check API status",
                    "enable_generative_ui": True,
                    "stream": False,
                    "include_context": False,
                },
            )

        assert response.status_code == 200
        data = response.json()

        ui = data["assistant_message"]["ui_components"]
        assert ui is not None
        assert len(ui) >= 1
        assert ui[0]["component_type"] == "json_viewer"
        assert data["assistant_message"]["render_mode"] == "hybrid"

    async def test_multiple_tools_produce_hybrid_mode(self, async_test_client):
        """
        Multiple tool results in a single message should yield multiple
        UI components and render_mode='hybrid'.
        """
        client = async_test_client

        nb = await client.post("/api/notebooks", json={
            "name": "Multi-Tool GenUI", "description": "Test"
        })
        notebook_id = nb.json()["id"]

        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id, "title": "Multi-tool"
            })
        session_id = session.json()["id"]

        mock_tool = MagicMock()
        mock_tool.name = "query_hana_table"
        mock_tool.description = "Query"

        agent = _make_mock_agent(
            response_text="Here are the results and total count.",
            tool_results=[TABULAR_TOOL_RESULT, SCALAR_TOOL_RESULT],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent), \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            response = await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Show top customers and total count",
                    "enable_generative_ui": True,
                    "stream": False,
                    "include_context": False,
                },
            )

        assert response.status_code == 200
        data = response.json()

        ui = data["assistant_message"]["ui_components"]
        assert ui is not None
        assert len(ui) == 2

        types = {c["component_type"] for c in ui}
        assert "hana_data_table" in types
        assert "metric_card" in types

        assert data["assistant_message"]["render_mode"] == "hybrid"

        tr = data["assistant_message"]["tool_results"]
        assert len(tr) == 2

    async def test_generative_ui_disabled_returns_markdown(self, async_test_client):
        """
        When enable_generative_ui=False (default), response should have
        no ui_components and render_mode='markdown'.
        """
        client = async_test_client

        nb = await client.post("/api/notebooks", json={
            "name": "No GenUI Test", "description": "Test"
        })
        notebook_id = nb.json()["id"]

        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id, "title": "No GenUI"
            })
        session_id = session.json()["id"]

        mock_tool = MagicMock()
        mock_tool.name = "query_hana_table"
        mock_tool.description = "Query"

        agent = _make_mock_agent(
            response_text="Here are results in plain text.",
            tool_results=[],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent), \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            response = await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Show data",
                    "enable_generative_ui": False,
                    "stream": False,
                    "include_context": False,
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert data["assistant_message"]["ui_components"] is None
        assert data["assistant_message"]["render_mode"] == "markdown"
        assert data["assistant_message"]["tool_results"] is None


# ============================================================================
# Test: Database Persistence
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestGenerativeUIDatabasePersistence:
    """Verify that generative UI data persists correctly in the database."""

    async def test_ui_components_persisted_in_database(self, async_test_client):
        """
        After sending a message with generative UI, retrieving the session
        should return the stored ui_components, render_mode, and tool_results.
        """
        client = async_test_client

        nb = await client.post("/api/notebooks", json={
            "name": "Persistence Test", "description": "Test"
        })
        notebook_id = nb.json()["id"]

        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id, "title": "Persist Test"
            })
        session_id = session.json()["id"]

        mock_tool = MagicMock()
        mock_tool.name = "query_hana_table"
        mock_tool.description = "Query"

        agent = _make_mock_agent(
            response_text="Top customers by revenue.",
            tool_results=[TABULAR_TOOL_RESULT],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent), \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Show top customers",
                    "enable_generative_ui": True,
                    "stream": False,
                    "include_context": False,
                },
            )

        # Retrieve session and check persisted data
        session_response = await client.get(f"/api/chat/sessions/{session_id}")
        assert session_response.status_code == 200

        session_data = session_response.json()
        messages = session_data["messages"]

        # Find the assistant message
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) >= 1

        assistant_msg = assistant_msgs[0]
        assert assistant_msg["render_mode"] == "hybrid"
        assert assistant_msg["ui_components"] is not None
        assert len(assistant_msg["ui_components"]) >= 1
        assert assistant_msg["ui_components"][0]["component_type"] == "hana_data_table"

        assert assistant_msg["tool_results"] is not None
        assert len(assistant_msg["tool_results"]) >= 1
        assert assistant_msg["tool_results"][0]["tool_name"] == "query_hana_table"

    async def test_plain_messages_have_no_generative_ui_data(self, async_test_client):
        """
        Messages without generative UI should persist with render_mode=markdown
        and null ui_components/tool_results.
        """
        client = async_test_client

        nb = await client.post("/api/notebooks", json={
            "name": "Plain Persist Test", "description": "Test"
        })
        notebook_id = nb.json()["id"]

        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id, "title": "Plain Test"
            })
        session_id = session.json()["id"]

        mock_tool = MagicMock()
        mock_tool.name = "query_hana_table"
        mock_tool.description = "Query"

        agent = _make_mock_agent(
            response_text="Plain response without tools.",
            tool_results=[],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent), \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Hello",
                    "enable_generative_ui": False,
                    "stream": False,
                    "include_context": False,
                },
            )

        session_response = await client.get(f"/api/chat/sessions/{session_id}")
        messages = session_response.json()["messages"]

        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) >= 1

        assistant_msg = assistant_msgs[0]
        assert assistant_msg["render_mode"] == "markdown"
        assert assistant_msg["ui_components"] is None
        assert assistant_msg["tool_results"] is None


# ============================================================================
# Test: Component Spec Validation
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestComponentSpecValidation:
    """Validate the shape and content of generated component specs."""

    async def test_data_table_component_spec_is_valid(self, async_test_client):
        """data_table component spec should have columns, rows, queryMetadata."""
        client = async_test_client

        nb = await client.post("/api/notebooks", json={
            "name": "Spec Validation", "description": "Test"
        })
        notebook_id = nb.json()["id"]

        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id, "title": "Spec Test"
            })
        session_id = session.json()["id"]

        mock_tool = MagicMock()
        mock_tool.name = "query_hana_table"
        mock_tool.description = "Query"

        agent = _make_mock_agent(
            response_text="Customer data below.",
            tool_results=[TABULAR_TOOL_RESULT],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent), \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            response = await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Show customers",
                    "enable_generative_ui": True,
                    "stream": False,
                    "include_context": False,
                },
            )

        data = response.json()
        table = data["assistant_message"]["ui_components"][0]

        # Required props
        assert "columns" in table["props"]
        assert "rows" in table["props"]
        assert "queryMetadata" in table["props"]

        # Columns match row keys
        cols = set(table["props"]["columns"])
        row_keys = set(table["props"]["rows"][0].keys())
        assert cols == row_keys

        # Query metadata
        meta = table["props"]["queryMetadata"]
        assert "tool_name" in meta
        assert "row_count" in meta
        assert meta["row_count"] == 5

        # Layout hints
        assert "layout" in table
        assert table["layout"]["width"] == "full"

    async def test_metric_card_spec_is_valid(self, async_test_client):
        """metric_card component spec should have value and label."""
        client = async_test_client

        nb = await client.post("/api/notebooks", json={
            "name": "Metric Spec", "description": "Test"
        })
        notebook_id = nb.json()["id"]

        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id, "title": "Metric Test"
            })
        session_id = session.json()["id"]

        mock_tool = MagicMock()
        mock_tool.name = "get_customer_count"
        mock_tool.description = "Count"

        agent = _make_mock_agent(
            response_text="Total customer count is 1523.",
            tool_results=[SCALAR_TOOL_RESULT],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent), \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            response = await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "How many customers?",
                    "enable_generative_ui": True,
                    "stream": False,
                    "include_context": False,
                },
            )

        data = response.json()
        metric = data["assistant_message"]["ui_components"][0]

        assert metric["component_type"] == "metric_card"
        assert "value" in metric["props"]
        assert "label" in metric["props"]
        assert metric["props"]["value"] == 1523


# ============================================================================
# Test: Edge Cases
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestGenerativeUIEdgeCases:
    """Test edge cases in the generative UI flow."""

    async def test_no_tool_results_stays_markdown(self, async_test_client):
        """
        When generative UI is enabled but the agent does not use any tools,
        render_mode should remain 'markdown'.
        """
        client = async_test_client

        nb = await client.post("/api/notebooks", json={
            "name": "No Tools Edge", "description": "Test"
        })
        notebook_id = nb.json()["id"]

        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id, "title": "No Tools"
            })
        session_id = session.json()["id"]

        mock_tool = MagicMock()
        mock_tool.name = "query_hana_table"
        mock_tool.description = "Query"

        agent = _make_mock_agent(
            response_text="I can help with that. What table would you like to query?",
            tool_results=[],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent), \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            response = await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Hi there",
                    "enable_generative_ui": True,
                    "stream": False,
                    "include_context": False,
                },
            )

        data = response.json()
        assert data["assistant_message"]["render_mode"] == "markdown"
        assert data["assistant_message"]["ui_components"] is None

    async def test_error_tool_result_produces_no_component(self, async_test_client):
        """
        When tool execution returns an error, no UI component should be generated
        but tool_results should still be captured.
        """
        client = async_test_client

        nb = await client.post("/api/notebooks", json={
            "name": "Error Edge", "description": "Test"
        })
        notebook_id = nb.json()["id"]

        with patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"):
            session = await client.post("/api/chat/sessions", json={
                "notebook_id": notebook_id, "title": "Error Test"
            })
        session_id = session.json()["id"]

        mock_tool = MagicMock()
        mock_tool.name = "query_hana_table"
        mock_tool.description = "Query"

        error_result = {
            "tool_name": "query_hana_table",
            "tool_input": {"query": "SELECT * FROM NONEXISTENT"},
            "result": None,
            "result_type": "error",
            "suggested_component": None,
            "execution_time_ms": 12.0,
        }

        agent = _make_mock_agent(
            response_text="Sorry, the table was not found.",
            tool_results=[error_result],
        )

        with patch("api.services.data_query_tools.create_tools_for_notebook", new_callable=AsyncMock, return_value=[mock_tool]), \
             patch("open_notebook.agents.data_query_agent.DataQueryAgent", return_value=agent), \
             patch("api.services.settings.get_setting", new_callable=AsyncMock, return_value="test-model-id"), \
             patch("api.routers.credentials._credentials_store", {"test-model-id": MOCK_CREDENTIAL}):

            response = await client.post(
                f"/api/chat/sessions/{session_id}/messages",
                json={
                    "message": "Query nonexistent table",
                    "enable_generative_ui": True,
                    "stream": False,
                    "include_context": False,
                },
            )

        data = response.json()
        # No UI components for error results
        assert data["assistant_message"]["render_mode"] == "markdown"
        assert data["assistant_message"]["ui_components"] is None

        # But tool_results should still be captured
        tr = data["assistant_message"]["tool_results"]
        assert tr is not None
        assert len(tr) == 1
        assert tr[0]["result_type"] == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
