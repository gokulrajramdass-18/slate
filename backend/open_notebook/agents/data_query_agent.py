"""
Data Query Agent - LangGraph agent for querying HANA and API sources

Uses LangGraph to orchestrate tool calls for HANA database queries and
REST API calls with automatic retry logic and state management.
"""

import time
from datetime import datetime
from typing import TypedDict, List, Optional, Any, Dict
from typing_extensions import Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, add_messages
from langgraph.prebuilt import ToolNode
from langchain.tools import BaseTool
import json


# ============================================================================
# State Definition
# ============================================================================

class DataQueryState(TypedDict):
    """State for data query agent workflow"""
    messages: Annotated[List[BaseMessage], add_messages]
    notebook_id: str
    session_id: Optional[str]
    tools_available: List[str]


# ============================================================================
# Data Query Agent
# ============================================================================

class DataQueryAgent:
    """
    LangGraph agent for querying HANA and API data sources

    Features:
    - Automatic tool execution with parallel support
    - Conversation state management
    - Streaming response support
    - Multi-model support (Claude, GPT)
    - Error handling and retries
    - Tool result capture for generative UI
    """

    def __init__(
        self,
        model_name: str,
        notebook_id: str,
        tools: List[BaseTool],
        session_id: Optional[str] = None,
        system_message: Optional[str] = None,
        capture_tool_results: bool = False,
        langfuse_trace_id: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        task_description: Optional[str] = None,
        enable_tool_filtering: bool = False,
    ):
        """
        Initialize agent

        Args:
            model_name: LLM model name (e.g., "claude-3-5-sonnet-20241022", "gpt-4")
            notebook_id: Notebook UUID
            tools: List of LangChain tools (HANA + API)
            session_id: Optional chat session ID for tracing
            system_message: Optional system message with context
            capture_tool_results: If True, capture tool results for generative UI
            langfuse_trace_id: Optional Langfuse trace ID for observability
            api_key: Optional API key for LiteLLM/model provider
            base_url: Optional base URL for LiteLLM proxy (e.g., http://localhost:6655/litellm/v1)
            task_description: Optional task description for tool filtering
            enable_tool_filtering: If True, filter tools based on task description
        """
        self.model_name = model_name
        self.notebook_id = notebook_id
        self.session_id = session_id
        self.system_message = system_message
        self.capture_tool_results = capture_tool_results
        self.langfuse_trace_id = langfuse_trace_id
        self.api_key = api_key
        self.base_url = base_url
        self.task_description = task_description or "General data query task"
        self.enable_tool_filtering = enable_tool_filtering
        self.all_tools = tools  # Store all tools before filtering

        # Tool filtering will be applied in an async method
        # For now, use all tools (filtering happens in _apply_tool_filtering if enabled)
        self.tools = tools

        # Accumulated tool results (populated when capture_tool_results is True)
        self.tool_results: List[Dict[str, Any]] = []

        # Agent execution steps for UI display
        self.agent_steps: List[Dict[str, Any]] = []

        # Create LLM with tools
        self.model = self._create_model()

        # Build workflow
        self.graph = self._build_graph()

        print(f"DataQueryAgent initialized with {len(tools)} tools")

    async def _apply_tool_filtering(self):
        """Apply tool filtering asynchronously if enabled"""
        if self.enable_tool_filtering and hasattr(self, 'all_tools'):
            from deep_agents_integration.tool_filtering import get_plan_mode_filter

            print(f"🔍 Applying tool filtering to {len(self.all_tools)} tools...")

            filter_instance = get_plan_mode_filter()
            filter_result = await filter_instance.filter_tools_for_query(
                query=self.task_description,
                available_tools=self.all_tools
            )

            # Update tools list
            self.tools = [t for t in self.all_tools if t.name in filter_result.selected_tool_ids]

            print(f"✅ Tool filtering complete:")
            print(f"   Phase: {filter_result.phase_used}")
            print(f"   Confidence: {filter_result.confidence:.2f}")
            print(f"   Tools: {len(self.all_tools)} → {len(self.tools)}")
            print(f"   Selected: {', '.join(filter_result.selected_tool_ids)}")
            print(f"   Reasoning: {filter_result.reasoning}")

            # Add to agent steps for UI visibility
            self.agent_steps.append({
                "type": "tool_filtering",
                "status": "completed",
                "title": "Tool Filtering",
                "description": f"Selected {len(self.tools)} of {len(self.all_tools)} tools",
                "data": {
                    "phase": filter_result.phase_used,
                    "confidence": filter_result.confidence,
                    "tools_before": len(self.all_tools),
                    "tools_after": len(self.tools),
                    "selected_tools": filter_result.selected_tool_ids,
                    "reasoning": filter_result.reasoning
                },
                "timestamp": datetime.now().isoformat()
            })

            # Rebind tools to model
            if self.tools:
                self.model = self.model.bind_tools(self.tools)

    def _create_model(self):
        """Create LLM model with tool binding"""
        # Get Langfuse callback handler if trace_id is provided
        callbacks = []
        if self.langfuse_trace_id:
            try:
                from api.services.observability_service import get_langfuse_service
                langfuse_service = get_langfuse_service()
                callback = langfuse_service.get_langchain_callback_handler(self.langfuse_trace_id)
                if callback:
                    callbacks.append(callback)
            except Exception as e:
                print(f"⚠️ Failed to create Langfuse callback: {e}")

        # Prepare model kwargs
        model_kwargs = {
            "temperature": 0.7,
            "max_tokens": 4096,
            "streaming": True,  # Enable streaming
            "callbacks": callbacks,
        }

        # Check if this is a SAP AI Core model (starts with sap-ai-core-)
        is_sap_ai_core = self.model_name.startswith("sap-ai-core-")

        if is_sap_ai_core:
            # For SAP AI Core, we cannot use async in __init__
            # Instead, pass the deployment info and let the agent handle auth
            print(f"🔧 Creating SAP AI Core model wrapper")
            print(f"   Model: {self.model_name}")

            # Extract deployment ID
            deployment_id = self.model_name.replace("sap-ai-core-", "")

            # Get SAP AI Core credentials from store
            from api.routers.credentials import _credentials_store
            import json

            sap_credential = None
            for cred_id, cred in _credentials_store.items():
                if cred.get("provider") == "sap_ai_core":
                    sap_credential = cred
                    break

            if not sap_credential:
                raise Exception("SAP AI Core credential not found")

            connection_config = json.loads(sap_credential.get("api_key", "{}"))
            api_url = connection_config.get("api_url", "")

            # For now, use ChatOpenAI as a wrapper
            # We'll intercept the calls and route them through SAP AI Core
            # This requires custom handling which we'll add later
            print(f"   ⚠️  SAP AI Core models not yet fully supported in chat")
            print(f"   Please use a LiteLLM or direct provider model for now")

            # Fallback to error
            raise Exception(
                "SAP AI Core models are not yet supported for chat. "
                "Please select a different model (OpenAI, Anthropic, or LiteLLM) in Settings → Models."
            )

        # Add API key and base URL if provided (for LiteLLM integration)
        elif self.api_key:
            model_kwargs["api_key"] = self.api_key

            # If base_url is provided, use OpenAI-compatible client (works with LiteLLM)
            # LiteLLM provides OpenAI-compatible endpoints for all providers
            if self.base_url:
                # For LiteLLM, keep the base_url as-is (should be http://localhost:6655/litellm/v1)
                # LiteLLM uses /litellm/v1/chat/completions which is OpenAI-compatible
                model_kwargs["base_url"] = self.base_url

                print(f"🔧 Creating OpenAI-compatible model for LiteLLM")
                print(f"   Model: {self.model_name}")
                print(f"   Base URL: {self.base_url}")
                print(f"   API key: {self.api_key[:20]}..." if self.api_key else "   API key: None")

                # Use ChatOpenAI for all models when going through LiteLLM
                model = ChatOpenAI(
                    model=self.model_name,
                    **model_kwargs
                )
        else:
            # No base_url provided - use native clients with environment variables
            is_anthropic = any(x in self.model_name.lower() for x in ["claude", "anthropic"])
            is_openai = any(x in self.model_name.lower() for x in ["gpt", "openai"])

            print(f"🔧 Creating native client (no base_url provided)")

            if is_anthropic:
                model = ChatAnthropic(
                    model=self.model_name,
                    **model_kwargs
                )
            elif is_openai:
                model = ChatOpenAI(
                    model=self.model_name,
                    **model_kwargs
                )
            else:
                # Default to OpenAI
                print(f"Unknown model {self.model_name}, defaulting to OpenAI client")
                model = ChatOpenAI(
                    model=self.model_name,
                    **model_kwargs
                )

        # Bind tools to model if available
        if self.tools:
            model = model.bind_tools(self.tools)

        return model

    def _build_graph(self):
        """Build LangGraph workflow"""
        # Create workflow
        workflow = StateGraph(DataQueryState)

        # Create tool node (executes tools in parallel)
        if self.tools:
            base_tool_node = ToolNode(self.tools)

            if self.capture_tool_results:
                # Wrap tool node to capture results
                async def capturing_tool_node(state: DataQueryState):
                    start = time.monotonic()
                    result = await base_tool_node.ainvoke(state)
                    elapsed_ms = (time.monotonic() - start) * 1000

                    # Extract ToolMessages from result
                    new_messages = result.get("messages", [])
                    for msg in new_messages:
                        if isinstance(msg, ToolMessage):
                            self._capture_tool_message(msg, state, elapsed_ms)

                    return result

                workflow.add_node("tools", capturing_tool_node)
            else:
                workflow.add_node("tools", base_tool_node)

        # Add agent node
        workflow.add_node("agent", self._agent_node)

        # Set entry point
        workflow.set_entry_point("agent")

        # Add conditional edges
        if self.tools:
            workflow.add_conditional_edges(
                "agent",
                self._should_continue,
                {
                    "continue": "tools",
                    "end": END
                }
            )
            workflow.add_edge("tools", "agent")
        else:
            # No tools, just end after agent
            workflow.add_edge("agent", END)

        return workflow.compile()

    def _capture_tool_message(
        self,
        tool_msg: ToolMessage,
        state: DataQueryState,
        elapsed_ms: float,
    ) -> None:
        """Capture a ToolMessage into self.tool_results."""
        # Find the matching tool_call in the preceding AIMessage
        tool_input = {}
        tool_name = tool_msg.name or "unknown"
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    if tc.get("id") == tool_msg.tool_call_id:
                        tool_name = tc.get("name", tool_name)
                        tool_input = tc.get("args", {})
                        break
                break

        result = self._format_tool_result(tool_msg.content)
        result_type = self._infer_result_type(result)
        suggested = self._suggest_component(tool_name, result_type, result)

        # Log tool result for debugging
        if result_type == "unknown" and isinstance(result, str):
            print(f"⚠️  Tool '{tool_name}' returned error string: {result[:200]}...")

        self.tool_results.append({
            "tool_name": tool_name,
            "tool_input": tool_input,
            "result": result,
            "result_type": result_type,
            "suggested_component": suggested,
            "execution_time_ms": round(elapsed_ms, 2),
        })

        # Update the existing "running" step to "completed" instead of creating a new one
        # Find the matching "tool_call" step that's still in "running" state
        matching_step = None
        for step in reversed(self.agent_steps):
            if (step.get("step_type") == "tool_call" and
                step.get("status") == "running" and
                step.get("metadata", {}).get("tool_name") == tool_name):
                matching_step = step
                break

        if matching_step:
            # Update the existing step
            step_status = "error" if result_type == "error" else "completed"
            matching_step["status"] = step_status
            matching_step["metadata"]["duration_ms"] = round(elapsed_ms, 2)
            matching_step["metadata"]["result_type"] = result_type

            # Add result preview to metadata for UI display
            if result_type == "table" and isinstance(result, dict):
                # For table results, show row count
                row_count = len(result.get("rows", []))
                matching_step["metadata"]["result_summary"] = f"{row_count} rows"
                matching_step["content"] = f"{tool_name} ({row_count} rows)"
            elif result_type == "scalar" and isinstance(result, dict):
                # For scalar results, show the value
                value = result.get("result", result.get("value", ""))
                matching_step["metadata"]["result_summary"] = str(value)
                matching_step["content"] = f"{tool_name}: {value}"
            elif result_type == "error":
                # For errors, show error message
                error_msg = result.get("error", "Unknown error") if isinstance(result, dict) else str(result)
                matching_step["metadata"]["error_message"] = error_msg
                matching_step["content"] = f"{tool_name} (Error)"
            else:
                # Generic completion message
                matching_step["content"] = f"{tool_name}"

            # Add error details if this is an error
            if result_type == "error" and isinstance(result, dict):
                if "error_type" in result:
                    matching_step["metadata"]["error_type"] = result["error_type"]
                if "query_params" in result:
                    matching_step["metadata"]["query_params"] = result["query_params"]
                if "table_name" in result:
                    matching_step["metadata"]["table_name"] = result["table_name"]
        else:
            # Fallback: create a new step if we couldn't find the matching one
            # This shouldn't happen in normal operation but provides safety
            step_status = "error" if result_type == "error" else "completed"
            step_content = f"Error: {tool_name}" if result_type == "error" else f"Completed: {tool_name}"

            step_metadata = {
                "tool_name": tool_name,
                "duration_ms": round(elapsed_ms, 2),
                "result_type": result_type,
            }

            if result_type == "error" and isinstance(result, dict):
                if "error" in result:
                    step_metadata["error_message"] = result["error"]
                if "error_type" in result:
                    step_metadata["error_type"] = result["error_type"]
                if "query_params" in result:
                    step_metadata["query_params"] = result["query_params"]
                if "table_name" in result:
                    step_metadata["table_name"] = result["table_name"]

            self._record_step(
                step_type="tool_result",
                content=step_content,
                status=step_status,
                metadata=step_metadata
            )

    def _record_step(
        self,
        step_type: str,
        content: str,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record an agent execution step for UI display.

        Args:
            step_type: Step type ("thinking", "tool_call", "tool_result", "response")
            content: Human-readable step description
            status: Step status ("pending", "running", "completed", "error")
            metadata: Additional metadata (tool_name, duration_ms, etc.)

        Returns:
            The created step dict
        """
        step = {
            "step_type": step_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "metadata": metadata or {},
        }
        self.agent_steps.append(step)
        return step

    @staticmethod
    def _format_tool_result(raw_content: Any) -> Any:
        """Parse tool output into a structured Python object when possible."""
        if isinstance(raw_content, str):
            try:
                return json.loads(raw_content)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"[DataQueryAgent] Failed to parse tool result as JSON: {e}")
                print(f"[DataQueryAgent] Raw content (first 500 chars): {raw_content[:500]}")
                return raw_content
        return raw_content

    @staticmethod
    def _infer_result_type(result: Any) -> str:
        """Infer a high-level type for the tool result."""
        if result is None:
            return "empty"
        if isinstance(result, dict):
            # Check for explicit success/error indicators first
            if "success" in result:
                if result["success"] is False or result.get("error"):
                    return "error"
            # Check for error-only indicators
            elif "error" in result and not any(k in result for k in ["result", "results", "data", "rows", "columns"]):
                return "error"
            # Check for "Error" in status field
            elif "Error" in str(result.get("status", "")):
                return "error"

            # Check for tabular patterns (list of rows, or columns+data)
            if "columns" in result and ("rows" in result or "data" in result):
                return "table"  # Changed from "tabular" to match frontend registry
            # HANA query tools return {"rows": [...], "count": N, "duration_ms": X}
            # Even without explicit columns, multiple rows = tabular
            if "rows" in result and isinstance(result["rows"], list):
                rows = result["rows"]
                if len(rows) > 0:
                    return "table"  # Changed from "tabular" to match frontend registry

            # MCP/API pattern: {count: N, <items_key>: [...]}
            # Common keys: accounts, opportunities, prospects, users, contacts, leads, deals, items, results, data, records
            mcp_list_keys = ["accounts", "opportunities", "prospects", "users", "contacts",
                           "leads", "deals", "items", "results", "data", "records"]
            for key in mcp_list_keys:
                if key in result and isinstance(result[key], list):
                    items = result[key]
                    if len(items) > 0 and isinstance(items[0], dict):
                        return "list"  # Will be converted to table by component generator

            return "scalar"
        if isinstance(result, list):
            if len(result) == 0:
                return "empty"
            if isinstance(result[0], dict):
                return "table"  # Changed from "tabular" to match frontend registry
            return "list"
        if isinstance(result, (int, float, bool)):
            return "scalar"
        return "unknown"

    @staticmethod
    def _suggest_component(tool_name: str, result_type: str, result: Any) -> Optional[str]:
        """Suggest a frontend component type based on tool name and result shape."""
        # HANA query tools -> data table
        hana_keywords = ["hana", "query", "sql", "database", "db"]
        if any(kw in tool_name.lower() for kw in hana_keywords):
            if result_type == "table":  # Changed from "tabular"
                return "hana_data_table"
            if result_type == "scalar":
                return "metric_card"

        # API tools -> depends on shape
        api_keywords = ["api", "rest", "http", "fetch", "request"]
        if any(kw in tool_name.lower() for kw in api_keywords):
            if result_type == "tabular":
                return "hana_data_table"
            if result_type == "scalar":
                return "metric_card"

        # Fallback heuristics by result type
        if result_type == "tabular":
            return "hana_data_table"
        if result_type == "scalar":
            return "metric_card"
        if result_type == "error":
            return "error_display"

        return None

    async def _agent_node(self, state: DataQueryState):
        """
        Agent reasoning node

        Calls LLM with conversation history and decides whether to use tools.
        """
        messages = state["messages"]

        # Record thinking step
        self._record_step(
            step_type="thinking",
            content="Analyzing query and available tools",
            status="running",
        )

        # Add system message if provided
        if self.system_message and (not messages or messages[0].type != "system"):
            from langchain_core.messages import SystemMessage
            messages = [SystemMessage(content=self.system_message)] + messages

        # Invoke model
        response = await self.model.ainvoke(messages)

        # Check if agent is calling tools
        if hasattr(response, "tool_calls") and response.tool_calls:
            # Update thinking step to completed
            if self.agent_steps and self.agent_steps[-1]["step_type"] == "thinking":
                self.agent_steps[-1]["status"] = "completed"

            # Record tool call steps
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "unknown")
                self._record_step(
                    step_type="tool_call",
                    content=f"Executing: {tool_name}",
                    status="running",
                    metadata={"tool_name": tool_name},
                )
        else:
            # No tools, mark thinking as completed
            if self.agent_steps and self.agent_steps[-1]["step_type"] == "thinking":
                self.agent_steps[-1]["status"] = "completed"

        # Return updated messages
        return {"messages": [response]}

    def _should_continue(self, state: DataQueryState):
        """
        Decide whether to continue with tools or end

        Returns:
            "continue" if LLM wants to use tools, "end" otherwise
        """
        messages = state["messages"]
        last_message = messages[-1]

        # Check if LLM made tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"

        return "end"

    async def invoke(
        self,
        user_message: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> str:
        """
        Execute agent (non-streaming)

        Args:
            user_message: User's message
            chat_history: Optional chat history (list of dicts with 'role' and 'content')

        Returns:
            Assistant's response text
        """
        # Apply tool filtering if enabled
        await self._apply_tool_filtering()

        # Reset captured results for this invocation
        self.tool_results = []

        # Build messages
        messages = self._format_messages(chat_history or [], user_message)

        # Create initial state
        initial_state: DataQueryState = {
            "messages": messages,
            "notebook_id": self.notebook_id,
            "session_id": self.session_id,
            "tools_available": [tool.name for tool in self.tools]
        }

        # Execute workflow with higher recursion limit
        # Default is 25, but complex queries may need more tool-calling iterations
        final_state = await self.graph.ainvoke(
            initial_state,
            config={"recursion_limit": 50}
        )

        # Extract final response
        final_messages = final_state["messages"]
        last_message = final_messages[-1]

        if isinstance(last_message, AIMessage):
            return last_message.content
        else:
            return str(last_message.content)

    async def stream_response(self, user_message: str, chat_history: Optional[List[Dict]] = None):
        """
        Execute agent with streaming

        Args:
            user_message: User's message
            chat_history: Optional chat history

        Yields:
            Dict events from LangGraph execution
        """
        # Apply tool filtering if enabled
        await self._apply_tool_filtering()

        # Reset captured results for this invocation
        self.tool_results = []

        # Build messages
        messages = self._format_messages(chat_history or [], user_message)

        # Create initial state
        initial_state: DataQueryState = {
            "messages": messages,
            "notebook_id": self.notebook_id,
            "session_id": self.session_id,
            "tools_available": [tool.name for tool in self.tools]
        }

        # Stream workflow execution with token-level events and higher recursion limit
        # Use astream_events to get LLM token streaming, not just node events
        async for event in self.graph.astream_events(
            initial_state,
            version="v2",
            config={"recursion_limit": 50}
        ):
            kind = event.get("event")

            if kind == "on_chat_model_stream":
                # This is a token from the LLM
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    # Extract text from content
                    # Content can be a string or a list of content blocks
                    content_text = ""
                    if isinstance(chunk.content, str):
                        content_text = chunk.content
                    elif isinstance(chunk.content, list):
                        # Extract text from content blocks
                        for block in chunk.content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                content_text += block.get("text", "")

                    if content_text:
                        # Yield in the format expected by the handler
                        # Create a simple message object with string content
                        class SimpleMessage:
                            def __init__(self, text):
                                self.content = text

                        yield {
                            "agent": {
                                "messages": [SimpleMessage(content_text)]
                            }
                        }
            elif kind == "on_tool_end":
                # Capture tool results for generative UI
                if self.capture_tool_results:
                    tool_data = event.get("data", {})
                    output = tool_data.get("output")

                    if output:
                        # Parse and capture the tool result
                        result = self._format_tool_result(output)
                        result_type = self._infer_result_type(result)
                        tool_name = event.get("name", "unknown")
                        suggested = self._suggest_component(tool_name, result_type, result)

                        self.tool_results.append({
                            "tool_name": tool_name,
                            "tool_input": tool_data.get("input", {}),
                            "result": result,
                            "result_type": result_type,
                            "suggested_component": suggested,
                            "execution_time_ms": 0,  # Not available in streaming
                        })

                # Yield tool event - convert to serializable format
                tool_data = event.get("data", {})
                serializable_data = {}
                for key, value in tool_data.items():
                    # Skip non-serializable objects
                    if key == "output":
                        # Tool output should be a string
                        if isinstance(value, str):
                            serializable_data[key] = value
                        else:
                            serializable_data[key] = str(value)
                    elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        serializable_data[key] = value

                yield {
                    "tools": {
                        "event": kind,
                        "data": serializable_data
                    }
                }
            elif kind == "on_tool_start":
                # Yield tool events - convert to serializable format
                tool_data = event.get("data", {})
                serializable_data = {}
                for key, value in tool_data.items():
                    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        serializable_data[key] = value

                yield {
                    "tools": {
                        "event": kind,
                        "data": serializable_data
                    }
                }

    def _format_messages(
        self,
        chat_history: List[Dict],
        user_message: str
    ) -> List[BaseMessage]:
        """
        Format chat history and user message to LangChain message format

        Args:
            chat_history: List of dicts with 'role' and 'content'
            user_message: Current user message

        Returns:
            List of BaseMessage objects
        """
        messages = []

        # Convert history to LangChain messages
        for msg in chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            # Skip system messages (handled separately)

        # Add current user message
        messages.append(HumanMessage(content=user_message))

        return messages

    def get_tool_names(self) -> List[str]:
        """Get list of available tool names"""
        return [tool.name for tool in self.tools]

    def get_captured_tool_results(self) -> List[Dict[str, Any]]:
        """Return captured tool results from the last invocation, ensuring JSON serializability."""
        import json
        serializable_results = []
        for result in self.tool_results:
            try:
                # Test if the result is JSON serializable
                json.dumps(result)
                serializable_results.append(result)
            except (TypeError, ValueError):
                # If not serializable, convert to strings
                safe_result = {}
                for key, value in result.items():
                    try:
                        json.dumps(value)
                        safe_result[key] = value
                    except (TypeError, ValueError):
                        # Convert non-serializable to string
                        safe_result[key] = str(value)
                serializable_results.append(safe_result)
        return serializable_results
