"""
Tests for Input Node Validation

Verifies that input nodes correctly validate and process input data
based on defined field schemas.
"""

import pytest
from open_notebook.agents.workflow_nodes import InputNodeExecutor
from open_notebook.domain.workflow import NodeConfig, InputFieldDefinition


@pytest.mark.asyncio
async def test_input_node_validates_required_fields():
    """Test that input node validates required fields."""
    config = NodeConfig(
        input_fields=[
            InputFieldDefinition(name="query", type="string", required=True)
        ]
    )

    executor = InputNodeExecutor(config=config)

    # Missing required field
    state = {
        "current_node_id": "input-1",
        "input_data": {},
        "node_outputs": {}
    }

    result = await executor.execute(state)
    assert "error" in result
    assert "query" in result["error"]
    assert "missing" in result["error"].lower()


@pytest.mark.asyncio
async def test_input_node_applies_defaults():
    """Test that input node applies default values."""
    config = NodeConfig(
        input_fields=[
            InputFieldDefinition(
                name="limit",
                type="number",
                required=False,
                default_value=10
            )
        ]
    )

    executor = InputNodeExecutor(config=config)

    state = {
        "current_node_id": "input-1",
        "input_data": {},
        "node_outputs": {}
    }

    result = await executor.execute(state)
    assert "error" not in result
    assert result["node_outputs"]["input-1"]["limit"] == 10


@pytest.mark.asyncio
async def test_input_node_type_coercion():
    """Test that input node coerces types correctly."""
    config = NodeConfig(
        input_fields=[
            InputFieldDefinition(name="count", type="number", required=True),
            InputFieldDefinition(name="enabled", type="boolean", required=True),
        ]
    )

    executor = InputNodeExecutor(config=config)

    # String inputs that should be coerced
    state = {
        "current_node_id": "input-1",
        "input_data": {
            "count": "42",
            "enabled": "true"
        },
        "node_outputs": {}
    }

    result = await executor.execute(state)
    assert "error" not in result
    assert result["node_outputs"]["input-1"]["count"] == 42.0
    assert result["node_outputs"]["input-1"]["enabled"] is True


@pytest.mark.asyncio
async def test_input_node_invalid_type():
    """Test that input node rejects invalid types."""
    config = NodeConfig(
        input_fields=[
            InputFieldDefinition(name="items", type="array", required=True)
        ]
    )

    executor = InputNodeExecutor(config=config)

    # Pass a string instead of array
    state = {
        "current_node_id": "input-1",
        "input_data": {
            "items": "not an array"
        },
        "node_outputs": {}
    }

    result = await executor.execute(state)
    assert "error" in result
    assert "items" in result["error"]


@pytest.mark.asyncio
async def test_input_node_backward_compatibility():
    """Test that input nodes without field definitions work as before."""
    config = NodeConfig(
        input_fields=None  # No fields defined
    )

    executor = InputNodeExecutor(config=config)

    # Arbitrary input data
    state = {
        "current_node_id": "input-1",
        "input_data": {
            "foo": "bar",
            "baz": 123,
            "nested": {"key": "value"}
        },
        "node_outputs": {}
    }

    result = await executor.execute(state)
    assert "error" not in result
    # All data should pass through
    assert result["node_outputs"]["input-1"] == state["input_data"]


@pytest.mark.asyncio
async def test_input_node_mixed_required_optional():
    """Test input node with mix of required and optional fields."""
    config = NodeConfig(
        input_fields=[
            InputFieldDefinition(name="query", type="string", required=True),
            InputFieldDefinition(name="limit", type="number", required=False, default_value=10),
            InputFieldDefinition(name="filters", type="object", required=False),
        ]
    )

    executor = InputNodeExecutor(config=config)

    # Provide only required field
    state = {
        "current_node_id": "input-1",
        "input_data": {
            "query": "test search"
        },
        "node_outputs": {}
    }

    result = await executor.execute(state)
    assert "error" not in result
    assert result["node_outputs"]["input-1"]["query"] == "test search"
    assert result["node_outputs"]["input-1"]["limit"] == 10
    # Optional field without default should not be in output
    assert "filters" not in result["node_outputs"]["input-1"]
