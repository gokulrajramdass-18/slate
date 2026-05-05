"""
Claude Code Agent - Native Anthropic SDK agent for regular chat queries

Uses Anthropic SDK's native tool calling instead of LangGraph for simpler
agentic loops. Maintains same interface as DataQueryAgent for compatibility.
"""

import time
import json
import logging
from datetime import datetime
from typing import List, Optional, Any, Dict
from langchain.tools import BaseTool
import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock

from api.services.tool_schema_converter import langchain_tool_to_anthropic_schema

logger = logging.getLogger(__name__)


class ClaudeCodeAgent:
    """
    Native Anthropic SDK agent for tool-calling chat queries

    Features:
    - Native Anthropic tool use protocol (simpler than LangGraph)
    - Streaming response support with SSE event mapping
    - Tool result capture for generative UI
    - Agent step tracking for UI display
    - Tool filtering integration
    - Langfuse observability integration
    - Same interface as DataQueryAgent for drop-in replacement
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
        Initialize Claude Code Agent

        Args:
            model_name: Claude model name (e.g., "claude-3-5-sonnet-20241022")
            notebook_id: Notebook UUID
            tools: List of LangChain tools (HANA + API + MCP + registry)
            session_id: Optional chat session ID for tracing
            system_message: Optional system message with context
            capture_tool_results: If True, capture tool results for generative UI
            langfuse_trace_id: Optional Langfuse trace ID for observability
            api_key: Anthropic API key
            base_url: Optional base URL for Anthropic API (for testing)
            task_description: Optional task description for tool filtering
            enable_tool_filtering: If True, filter tools based on task description
        """
        self.model_name = model_name
        self.notebook_id = notebook_id
        self.session_id = session_id
        self.system_message = system_message or ""
        self.capture_tool_results = capture_tool_results
        self.langfuse_trace_id = langfuse_trace_id
        self.task_description = task_description or "General data query task"
        self.enable_tool_filtering = enable_tool_filtering

        # Tool storage
        self.all_tools = tools  # Store all tools before filtering
        self.tools = tools  # Will be updated by filtering

        # Tool results for generative UI
        self.tool_results: List[Dict[str, Any]] = []

        # Agent execution steps for UI display
        self.agent_steps: List[Dict[str, Any]] = []

        # Create Anthropic client
        client_kwargs = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = AsyncAnthropic(**client_kwargs)

        # Langfuse service
        self.langfuse_service = None
        if langfuse_trace_id:
            try:
                from api.services.observability_service import get_langfuse_service
                self.langfuse_service = get_langfuse_service()
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")

        logger.info(f"ClaudeCodeAgent initialized with {len(tools)} tools")

    async def _apply_tool_filtering(self):
        """Apply tool filtering asynchronously if enabled"""
        if not self.enable_tool_filtering or not self.all_tools:
            return

        try:
            from deep_agents_integration.tool_filtering import get_plan_mode_filter

            logger.info(f"Applying tool filtering to {len(self.all_tools)} tools...")

            filter_instance = get_plan_mode_filter()
            filter_result = await filter_instance.filter_tools_for_query(
                query=self.task_description,
                available_tools=self.all_tools
            )

            # Update tools list
            self.tools = [t for t in self.all_tools if t.name in filter_result.selected_tool_ids]

            logger.info(
                f"Tool filtering complete: {len(self.all_tools)} → {len(self.tools)} tools. "
                f"Phase: {filter_result.phase_used}, Confidence: {filter_result.confidence:.2f}"
            )

            # Record step for UI visibility
            self.agent_steps.append({
                "step_type": "tool_filtering",
                "status": "completed",
                "content": f"Selected {len(self.tools)} of {len(self.all_tools)} tools",
                "metadata": {
                    "phase": filter_result.phase_used,
                    "confidence": filter_result.confidence,
                    "tools_before": len(self.all_tools),
                    "tools_after": len(self.tools),
                    "selected_tools": filter_result.selected_tool_ids,
                    "reasoning": filter_result.reasoning
                },
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            logger.error(f"Tool filtering failed: {e}", exc_info=True)
            # Continue with all tools on failure

    def _build_messages(
        self,
        user_message: str,
        chat_history: Optional[List[Dict]] = None
    ) -> List[Dict[str, Any]]:
        """
        Build Anthropic-compatible messages list from history + current message

        Args:
            user_message: Current user message
            chat_history: Previous messages (list of dicts with 'role' and 'content')

        Returns:
            List of Anthropic message dicts
        """
        messages = []

        # Add history (skip system messages - they go in system parameter)
        if chat_history:
            for msg in chat_history:
                if msg.get("role") != "system":
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })

        return messages

    async def _execute_tool(self, tool_use: ToolUseBlock) -> str:
        """
        Execute a tool call from Claude

        Args:
            tool_use: Anthropic ToolUseBlock with name and input

        Returns:
            Tool result as string (may be JSON)
        """
        tool_name = tool_use.name
        tool_input = tool_use.input

        # Find tool
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            error_msg = f"Tool '{tool_name}' not found in available tools"
            logger.error(error_msg)
            return json.dumps({"error": error_msg, "type": "not_found"})

        # Record tool call step
        self._record_step(
            step_type="tool_call",
            content=f"Executing: {tool_name}",
            status="running",
            metadata={"tool_name": tool_name, "input": tool_input}
        )

        try:
            start_time = time.time()

            # Execute LangChain tool
            result = await tool.ainvoke(tool_input)

            elapsed_ms = (time.time() - start_time) * 1000

            # Capture for generative UI
            if self.capture_tool_results:
                self._capture_tool_result(tool_name, tool_input, result, elapsed_ms)

            # Record completion step
            self._record_step(
                step_type="tool_result",
                content=f"Completed: {tool_name}",
                status="completed",
                metadata={
                    "tool_name": tool_name,
                    "duration_ms": round(elapsed_ms, 2)
                }
            )

            # Convert result to string if not already
            if isinstance(result, str):
                return result
            else:
                return json.dumps(result, default=str)

        except Exception as e:
            logger.error(f"Tool execution error for '{tool_name}': {e}", exc_info=True)

            # Record error step
            self._record_step(
                step_type="tool_result",
                content=f"Error: {tool_name}",
                status="error",
                metadata={"tool_name": tool_name, "error": str(e)}
            )

            return json.dumps({
                "error": str(e),
                "type": "execution_error",
                "tool_name": tool_name
            })

    def _capture_tool_result(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        result: Any,
        elapsed_ms: float
    ):
        """
        Capture tool result for generative UI rendering

        Args:
            tool_name: Name of executed tool
            tool_input: Tool input parameters
            result: Tool execution result
            elapsed_ms: Execution time in milliseconds
        """
        # Parse result
        parsed = self._format_tool_result(result)
        result_type = self._infer_result_type(parsed)
        suggested = self._suggest_component(tool_name, result_type, parsed)

        self.tool_results.append({
            "tool_name": tool_name,
            "tool_input": tool_input,
            "result": parsed,
            "result_type": result_type,
            "suggested_component": suggested,
            "execution_time_ms": round(elapsed_ms, 2)
        })

    def _record_step(
        self,
        step_type: str,
        content: str,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record an agent execution step for UI display

        Args:
            step_type: Step type ("thinking", "tool_call", "tool_result", "response")
            content: Human-readable step description
            status: Step status ("pending", "running", "completed", "error")
            metadata: Additional metadata
        """
        step = {
            "step_type": step_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "metadata": metadata or {}
        }
        self.agent_steps.append(step)

    @staticmethod
    def _format_tool_result(raw_content: Any) -> Any:
        """Parse tool output into structured Python object when possible"""
        if isinstance(raw_content, str):
            try:
                return json.loads(raw_content)
            except (json.JSONDecodeError, TypeError):
                return raw_content
        return raw_content

    @staticmethod
    def _infer_result_type(result: Any) -> str:
        """Infer a high-level type for the tool result"""
        if result is None:
            return "empty"
        if isinstance(result, dict):
            # Check for error indicators
            if "success" in result:
                if result["success"] is False or result.get("error"):
                    return "error"
            elif "error" in result and not any(k in result for k in ["result", "results", "data", "rows", "columns"]):
                return "error"
            elif "Error" in str(result.get("status", "")):
                return "error"

            # Check for tabular patterns
            if "columns" in result and ("rows" in result or "data" in result):
                return "table"
            if "rows" in result and isinstance(result["rows"], list):
                rows = result["rows"]
                if len(rows) > 0:
                    return "table"
            return "scalar"
        if isinstance(result, list):
            if len(result) == 0:
                return "empty"
            if isinstance(result[0], dict):
                return "table"
            return "list"
        if isinstance(result, (int, float, bool)):
            return "scalar"
        return "unknown"

    @staticmethod
    def _suggest_component(tool_name: str, result_type: str, result: Any) -> Optional[str]:
        """Suggest a frontend component type based on tool name and result shape"""
        # HANA query tools → data table
        hana_keywords = ["hana", "query", "sql", "database", "db"]
        if any(kw in tool_name.lower() for kw in hana_keywords):
            if result_type == "table":
                return "hana_data_table"
            if result_type == "scalar":
                return "metric_card"

        # API tools → depends on shape
        api_keywords = ["api", "rest", "http", "fetch", "request"]
        if any(kw in tool_name.lower() for kw in api_keywords):
            if result_type == "table":
                return "hana_data_table"
            if result_type == "scalar":
                return "metric_card"

        # Fallback heuristics by result type
        if result_type == "table":
            return "hana_data_table"
        if result_type == "scalar":
            return "metric_card"
        if result_type == "error":
            return "error_display"

        return None

    async def _run_agentic_loop(
        self,
        user_message: str,
        chat_history: Optional[List[Dict]] = None
    ) -> str:
        """
        Execute agentic loop: think → tool → respond (non-streaming)

        Args:
            user_message: User's message
            chat_history: Optional chat history

        Returns:
            Final response text
        """
        # Convert tools to Anthropic format
        anthropic_tools = [
            langchain_tool_to_anthropic_schema(t) for t in self.tools
        ] if self.tools else []

        # Build messages
        messages = self._build_messages(user_message, chat_history)

        # Agentic loop
        iteration = 0
        max_iterations = 10
        full_response_text = ""

        while iteration < max_iterations:
            try:
                # Call Claude
                response: Message = await self.client.messages.create(
                    model=self.model_name,
                    max_tokens=4096,
                    system=self.system_message,
                    messages=messages,
                    tools=anthropic_tools if anthropic_tools else anthropic.NOT_GIVEN
                )

                # Extract tool uses and text
                tool_uses = [block for block in response.content if isinstance(block, ToolUseBlock)]
                text_blocks = [block for block in response.content if isinstance(block, TextBlock)]

                # Accumulate text
                response_text = "".join([block.text for block in text_blocks])
                full_response_text += response_text

                # If no tools, we're done
                if not tool_uses:
                    break

                # Add assistant message to history
                messages.append({
                    "role": "assistant",
                    "content": response.content
                })

                # Execute tools
                tool_results = []
                for tool_use in tool_uses:
                    result = await self._execute_tool(tool_use)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result
                    })

                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results
                })

                iteration += 1

            except anthropic.APIError as e:
                logger.error(f"Anthropic API error: {e}", exc_info=True)
                return f"API Error: {str(e)}"
            except Exception as e:
                logger.error(f"Agentic loop error: {e}", exc_info=True)
                return f"Error: {str(e)}"

        if iteration >= max_iterations:
            logger.warning(f"Maximum iterations ({max_iterations}) reached")
            full_response_text += "\n\n_(Maximum iterations reached)_"

        return full_response_text

    async def _agentic_loop_stream(
        self,
        user_message: str,
        chat_history: Optional[List[Dict]] = None
    ):
        """
        Execute agentic loop with streaming (yields SSE events)

        Args:
            user_message: User's message
            chat_history: Optional chat history

        Yields:
            Dict events compatible with SSE format:
            - {"event": "chunk", "data": {"content": "..."}}
            - {"event": "agent_step", "data": {...}}
        """
        # Convert tools to Anthropic format
        anthropic_tools = [
            langchain_tool_to_anthropic_schema(t) for t in self.tools
        ] if self.tools else []

        # Build messages
        messages = self._build_messages(user_message, chat_history)

        # Agentic loop
        iteration = 0
        max_iterations = 10

        while iteration < max_iterations:
            try:
                # Stream Claude response
                async with self.client.messages.stream(
                    model=self.model_name,
                    max_tokens=4096,
                    system=self.system_message,
                    messages=messages,
                    tools=anthropic_tools if anthropic_tools else anthropic.NOT_GIVEN
                ) as stream:
                    tool_uses = []
                    response_content = []

                    async for event in stream:
                        # Text streaming
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, "text"):
                                yield {
                                    "event": "chunk",
                                    "data": {"content": event.delta.text}
                                }

                        # Tool call started
                        elif event.type == "content_block_start":
                            if hasattr(event, "content_block"):
                                if event.content_block.type == "tool_use":
                                    yield {
                                        "event": "agent_step",
                                        "data": {
                                            "step_type": "tool_call",
                                            "content": f"Calling tool: {event.content_block.name}",
                                            "status": "running",
                                            "timestamp": datetime.utcnow().isoformat()
                                        }
                                    }

                    # Get final message
                    final_message = await stream.get_final_message()

                    # Extract tool uses
                    tool_uses = [
                        block for block in final_message.content
                        if isinstance(block, ToolUseBlock)
                    ]

                    # If no tools, we're done
                    if not tool_uses:
                        break

                    # Add assistant message to history
                    messages.append({
                        "role": "assistant",
                        "content": final_message.content
                    })

                    # Execute tools
                    tool_results = []
                    for tool_use in tool_uses:
                        result = await self._execute_tool(tool_use)

                        # Yield tool result event
                        yield {
                            "event": "agent_step",
                            "data": {
                                "step_type": "tool_result",
                                "content": f"Completed: {tool_use.name}",
                                "status": "completed",
                                "timestamp": datetime.utcnow().isoformat()
                            }
                        }

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result
                        })

                    # Add tool results to messages
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                    iteration += 1

            except anthropic.APIError as e:
                logger.error(f"Anthropic API error: {e}", exc_info=True)
                yield {
                    "event": "error",
                    "data": {"error": f"API Error: {str(e)}"}
                }
                break
            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                yield {
                    "event": "error",
                    "data": {"error": f"Error: {str(e)}"}
                }
                break

        if iteration >= max_iterations:
            logger.warning(f"Maximum iterations ({max_iterations}) reached")
            yield {
                "event": "chunk",
                "data": {"content": "\n\n_(Maximum iterations reached)_"}
            }

    async def invoke(
        self,
        user_message: str,
        chat_history: Optional[List[Dict]] = None
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

        # Reset captured results
        self.tool_results = []
        self.agent_steps = []

        # Langfuse trace start
        generation_id = None
        if self.langfuse_service and self.langfuse_trace_id:
            try:
                generation_id = self.langfuse_service.create_generation(
                    trace_id=self.langfuse_trace_id,
                    name="claude_code_agent",
                    model=self.model_name,
                    input={"message": user_message}
                )
            except Exception as e:
                logger.warning(f"Failed to create Langfuse generation: {e}")

        try:
            # Run agentic loop
            response_text = await self._run_agentic_loop(user_message, chat_history)

            # Langfuse trace end
            if self.langfuse_service and generation_id:
                try:
                    self.langfuse_service.update_generation(
                        generation_id=generation_id,
                        output=response_text,
                        usage={}  # Anthropic doesn't provide usage in response
                    )
                except Exception as e:
                    logger.warning(f"Failed to update Langfuse generation: {e}")

            return response_text

        except Exception as e:
            # Langfuse trace error
            if self.langfuse_service and generation_id:
                try:
                    self.langfuse_service.update_generation(
                        generation_id=generation_id,
                        output=f"Error: {str(e)}",
                        level="ERROR"
                    )
                except Exception:
                    pass
            raise

    async def stream_response(
        self,
        user_message: str,
        chat_history: Optional[List[Dict]] = None
    ):
        """
        Execute agent with streaming

        Args:
            user_message: User's message
            chat_history: Optional chat history

        Yields:
            Dict events compatible with SSE format
        """
        # Apply tool filtering if enabled
        await self._apply_tool_filtering()

        # Reset captured results
        self.tool_results = []
        self.agent_steps = []

        # Stream agentic loop
        async for event in self._agentic_loop_stream(user_message, chat_history):
            yield event

    def get_tool_names(self) -> List[str]:
        """
        Get list of available tool names

        Returns:
            List of tool names
        """
        return [tool.name for tool in self.tools]

    def get_captured_tool_results(self) -> List[Dict[str, Any]]:
        """
        Return captured tool results (for generative UI)

        Returns:
            List of tool result dicts with structure:
            {
                "tool_name": str,
                "tool_input": dict,
                "result": Any,
                "result_type": str,
                "suggested_component": str | None,
                "execution_time_ms": float
            }
        """
        return self.tool_results
