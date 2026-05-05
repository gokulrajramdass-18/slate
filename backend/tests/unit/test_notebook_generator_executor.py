"""
Unit tests for NotebookGeneratorNodeExecutor.

Tests:
- Notebook creation with template substitution
- All 3 content extraction modes (full_output, smart_parse, json_path)
- Source linking (create_from_content, use_existing, both)
- Validation errors (no language model, missing required fields)
- Output format variations (id_only, full_object, summary)
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from open_notebook.domain.workflow import NodeConfig, NodeType
from open_notebook.agents.workflow_nodes import NotebookGeneratorNodeExecutor


@pytest.fixture
def mock_language_model_configured():
    """Mock language model as configured."""
    with patch("api.services.settings.get_setting", new_callable=AsyncMock) as mock:
        mock.return_value = "gpt-4"
        yield mock


@pytest.fixture
def mock_notebook():
    """Mock Notebook domain model."""
    with patch("open_notebook.domain.notebook.Notebook") as MockNotebook:
        mock_instance = MagicMock()
        mock_instance.save = AsyncMock(return_value="nb-test-123")
        mock_instance.add_source = AsyncMock()
        MockNotebook.return_value = mock_instance
        yield MockNotebook, mock_instance


@pytest.fixture
def mock_source():
    """Mock Source domain model."""
    with patch("open_notebook.domain.notebook.Source") as MockSource:
        mock_instance = MagicMock()
        mock_instance.save = AsyncMock(return_value="src-test-456")
        MockSource.return_value = mock_instance
        yield MockSource, mock_instance


# ============================================================================
# Test: Basic Notebook Creation
# ============================================================================

@pytest.mark.asyncio
async def test_create_notebook_basic(mock_language_model_configured, mock_notebook):
    """Test basic notebook creation without sources."""
    MockNotebook, mock_notebook_instance = mock_notebook

    config = NodeConfig(
        notebook_name="Test Notebook",
        notebook_description="Test Description",
        source_mode="use_existing",
        existing_source_ids=[]
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {}
    }

    result = await executor.execute(state)

    # Verify notebook was created with correct parameters
    MockNotebook.assert_called_once_with(
        name="Test Notebook",
        description="Test Description",
        folder_id=None,
        tags=[]
    )
    mock_notebook_instance.save.assert_called_once()

    # Verify output
    assert result["node_outputs"]["nb-gen-1"]["status"] == "created"
    assert result["node_outputs"]["nb-gen-1"]["notebook_id"] == "nb-test-123"
    assert result["node_outputs"]["nb-gen-1"]["source_count"] == 0


# ============================================================================
# Test: Template Variable Substitution
# ============================================================================

@pytest.mark.asyncio
async def test_template_substitution_from_input_data(mock_language_model_configured, mock_notebook):
    """Test template variable substitution from input_data."""
    MockNotebook, mock_notebook_instance = mock_notebook

    config = NodeConfig(
        notebook_name="{{quarter}} {{year}} Analysis",
        notebook_description="Analysis for {{quarter}}",
        source_mode="use_existing",
        existing_source_ids=[]
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {"quarter": "Q1", "year": "2024"},
        "node_outputs": {}
    }

    result = await executor.execute(state)

    # Verify substitution
    MockNotebook.assert_called_once_with(
        name="Q1 2024 Analysis",
        description="Analysis for Q1",
        folder_id=None,
        tags=[]
    )


@pytest.mark.asyncio
async def test_template_substitution_from_context(mock_language_model_configured, mock_notebook):
    """Test template variable substitution from node_outputs context."""
    MockNotebook, mock_notebook_instance = mock_notebook

    config = NodeConfig(
        notebook_name="Notebook for {{notebook_id}}",
        source_mode="use_existing",
        existing_source_ids=[]
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {
            "prev-node": {"notebook_id": "previous-nb-789"}
        }
    }

    result = await executor.execute(state)

    MockNotebook.assert_called_once_with(
        name="Notebook for previous-nb-789",
        description=None,
        folder_id=None,
        tags=[]
    )


# ============================================================================
# Test: Content Extraction Mode - full_output
# ============================================================================

@pytest.mark.asyncio
async def test_content_extraction_full_output(mock_language_model_configured, mock_notebook, mock_source):
    """Test full_output content extraction mode."""
    MockNotebook, mock_notebook_instance = mock_notebook
    MockSource, mock_source_instance = mock_source

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="create_from_content",
        content_source_node_id="agent-1",
        content_extraction_mode="full_output",
        source_title_template="Agent Output",
        source_type="text"
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {
            "agent-1": {
                "status": "completed",
                "output": "# Q1 Analysis\n\nRevenue up 15%"
            }
        }
    }

    result = await executor.execute(state)

    # Verify source was created with full output as JSON string
    assert MockSource.call_count == 1
    call_args = MockSource.call_args[1]
    assert call_args["title"] == "Agent Output"
    assert call_args["source_type"] == "text"
    assert "status" in call_args["full_text"]
    assert "output" in call_args["full_text"]

    # Verify source was linked to notebook
    mock_notebook_instance.add_source.assert_called_once_with("src-test-456")


# ============================================================================
# Test: Content Extraction Mode - smart_parse
# ============================================================================

@pytest.mark.asyncio
async def test_content_extraction_smart_parse_array(mock_language_model_configured, mock_notebook, mock_source):
    """Test smart_parse with array output (creates multiple sources)."""
    MockNotebook, mock_notebook_instance = mock_notebook
    MockSource, mock_source_instance = mock_source

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="create_from_content",
        content_source_node_id="agent-1",
        content_extraction_mode="smart_parse",
        source_title_template="Report",
        source_type="text"
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {
            "agent-1": [
                {"title": "Q1 Report", "content": "Q1 data"},
                {"title": "Q2 Report", "content": "Q2 data"}
            ]
        }
    }

    result = await executor.execute(state)

    # Should create 2 sources
    assert MockSource.call_count == 2
    assert mock_notebook_instance.add_source.call_count == 2

    # Verify titles are numbered
    first_call = MockSource.call_args_list[0][1]
    assert first_call["title"] == "Report 1"

    second_call = MockSource.call_args_list[1][1]
    assert second_call["title"] == "Report 2"


@pytest.mark.asyncio
async def test_content_extraction_smart_parse_with_content_field(mock_language_model_configured, mock_notebook, mock_source):
    """Test smart_parse with dict containing 'content' field."""
    MockNotebook, mock_notebook_instance = mock_notebook
    MockSource, mock_source_instance = mock_source

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="create_from_content",
        content_source_node_id="agent-1",
        content_extraction_mode="smart_parse",
        source_title_template="Report",
        source_type="text"
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {
            "agent-1": {
                "status": "completed",
                "content": "This is the main content"
            }
        }
    }

    result = await executor.execute(state)

    # Should extract just the content field
    call_args = MockSource.call_args[1]
    assert call_args["full_text"] == "This is the main content"


# ============================================================================
# Test: Content Extraction Mode - json_path
# ============================================================================

@pytest.mark.asyncio
async def test_content_extraction_json_path(mock_language_model_configured, mock_notebook, mock_source):
    """Test json_path content extraction mode."""
    MockNotebook, mock_notebook_instance = mock_notebook
    MockSource, mock_source_instance = mock_source

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="create_from_content",
        content_source_node_id="agent-1",
        content_extraction_mode="json_path",
        content_extraction_path="$.results[*].content",
        source_title_template="Extracted",
        source_type="text"
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {
            "agent-1": {
                "results": [
                    {"title": "A", "content": "Content A"},
                    {"title": "B", "content": "Content B"}
                ]
            }
        }
    }

    result = await executor.execute(state)

    # Should create 2 sources from JSONPath matches
    assert MockSource.call_count == 2

    first_call = MockSource.call_args_list[0][1]
    assert first_call["full_text"] == "Content A"

    second_call = MockSource.call_args_list[1][1]
    assert first_call["full_text"] == "Content A"


# ============================================================================
# Test: Source Mode - use_existing
# ============================================================================

@pytest.mark.asyncio
async def test_source_mode_use_existing(mock_language_model_configured, mock_notebook):
    """Test linking existing sources."""
    MockNotebook, mock_notebook_instance = mock_notebook

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="use_existing",
        existing_source_ids=["src-1", "src-2", "src-3"]
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {}
    }

    result = await executor.execute(state)

    # Verify sources were linked
    assert mock_notebook_instance.add_source.call_count == 3
    mock_notebook_instance.add_source.assert_any_call("src-1")
    mock_notebook_instance.add_source.assert_any_call("src-2")
    mock_notebook_instance.add_source.assert_any_call("src-3")

    assert result["node_outputs"]["nb-gen-1"]["source_count"] == 3


# ============================================================================
# Test: Source Mode - both
# ============================================================================

@pytest.mark.asyncio
async def test_source_mode_both(mock_language_model_configured, mock_notebook, mock_source):
    """Test creating sources AND linking existing ones."""
    MockNotebook, mock_notebook_instance = mock_notebook
    MockSource, mock_source_instance = mock_source

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="both",
        content_source_node_id="agent-1",
        content_extraction_mode="full_output",
        source_title_template="Generated",
        existing_source_ids=["src-existing-1"]
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {
            "agent-1": "Some content"
        }
    }

    result = await executor.execute(state)

    # Should create 1 new source and link 1 existing
    assert MockSource.call_count == 1
    assert mock_notebook_instance.add_source.call_count == 2

    assert result["node_outputs"]["nb-gen-1"]["source_count"] == 2


# ============================================================================
# Test: Validation Errors
# ============================================================================

@pytest.mark.asyncio
async def test_validation_error_no_language_model():
    """Test error when no language model is configured."""
    with patch("api.services.settings.get_setting", new_callable=AsyncMock) as mock_get_setting:
        mock_get_setting.return_value = ""  # No model configured

        config = NodeConfig(
            notebook_name="Test Notebook",
            source_mode="use_existing",
            existing_source_ids=[]
        )

        executor = NotebookGeneratorNodeExecutor(config)

        state = {
            "current_node_id": "nb-gen-1",
            "input_data": {},
            "node_outputs": {}
        }

        result = await executor.execute(state)

        # Should return error
        assert result["node_outputs"]["nb-gen-1"]["status"] == "failed"
        assert "language model" in result["node_outputs"]["nb-gen-1"]["error"].lower()


@pytest.mark.asyncio
async def test_validation_error_missing_content_source_node_id(mock_language_model_configured, mock_notebook):
    """Test error when content_source_node_id is missing in create_from_content mode."""
    MockNotebook, mock_notebook_instance = mock_notebook

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="create_from_content",
        # content_source_node_id missing!
        content_extraction_mode="full_output"
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {}
    }

    result = await executor.execute(state)

    assert result["node_outputs"]["nb-gen-1"]["status"] == "failed"
    assert "content_source_node_id" in result["node_outputs"]["nb-gen-1"]["error"]


@pytest.mark.asyncio
async def test_validation_error_node_not_found(mock_language_model_configured, mock_notebook):
    """Test error when referenced node not in outputs."""
    MockNotebook, mock_notebook_instance = mock_notebook

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="create_from_content",
        content_source_node_id="missing-node",
        content_extraction_mode="full_output"
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {
            "agent-1": "Some data"
        }
    }

    result = await executor.execute(state)

    assert result["node_outputs"]["nb-gen-1"]["status"] == "failed"
    assert "missing-node" in result["node_outputs"]["nb-gen-1"]["error"]


# ============================================================================
# Test: Output Format Variations
# ============================================================================

@pytest.mark.asyncio
async def test_output_format_id_only(mock_language_model_configured, mock_notebook):
    """Test id_only output format."""
    MockNotebook, mock_notebook_instance = mock_notebook

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="use_existing",
        existing_source_ids=[],
        output_format="id_only"
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {}
    }

    result = await executor.execute(state)

    output = result["node_outputs"]["nb-gen-1"]
    assert output == {"notebook_id": "nb-test-123"}


@pytest.mark.asyncio
async def test_output_format_full_object(mock_language_model_configured, mock_notebook):
    """Test full_object output format."""
    MockNotebook, mock_notebook_instance = mock_notebook

    config = NodeConfig(
        notebook_name="Test Notebook",
        notebook_description="Test Description",
        folder_id="folder-123",
        tags=["research", "urgent"],
        source_mode="use_existing",
        existing_source_ids=["src-1"],
        output_format="full_object"
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {}
    }

    result = await executor.execute(state)

    output = result["node_outputs"]["nb-gen-1"]
    assert output["notebook_id"] == "nb-test-123"
    assert output["name"] == "Test Notebook"
    assert output["description"] == "Test Description"
    assert output["folder_id"] == "folder-123"
    assert output["tags"] == ["research", "urgent"]
    assert output["source_ids"] == ["src-1"]
    assert output["source_count"] == 1
    assert output["status"] == "created"


@pytest.mark.asyncio
async def test_output_format_summary_default(mock_language_model_configured, mock_notebook):
    """Test summary output format (default)."""
    MockNotebook, mock_notebook_instance = mock_notebook

    config = NodeConfig(
        notebook_name="Test Notebook",
        source_mode="use_existing",
        existing_source_ids=["src-1", "src-2"]
        # output_format not specified, defaults to "summary"
    )

    executor = NotebookGeneratorNodeExecutor(config)

    state = {
        "current_node_id": "nb-gen-1",
        "input_data": {},
        "node_outputs": {}
    }

    result = await executor.execute(state)

    output = result["node_outputs"]["nb-gen-1"]
    assert output["notebook_id"] == "nb-test-123"
    assert output["name"] == "Test Notebook"
    assert output["source_count"] == 2
    assert output["status"] == "created"
    # Should not include description, folder_id, tags, source_ids
    assert "description" not in output
    assert "folder_id" not in output
