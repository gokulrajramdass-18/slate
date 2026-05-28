"""
SAP AI Core Chat Model Wrapper (HTTP Client)

LangChain-compatible chat model for SAP AI Core deployments. Talks to the
standalone SAP AI Core API (port 5056) via HTTP. Supports OpenAI-compatible
function calling: bind_tools forwards tool schemas to the proxy and the
streaming path emits ToolCallChunks so LangGraph's ToolNode can execute them.
"""

import json
import logging
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Sequence, Union

import httpx
from langchain_core.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.tool import ToolCallChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

logger = logging.getLogger(__name__)


class ChatSAPAICore(BaseChatModel):
    """
    LangChain chat model wrapper for SAP AI Core deployments.

    Routes through the standalone API (port 5056). The standalone API handles
    OAuth + deployment routing; this wrapper is responsible for translating
    LangChain message/tool objects to OpenAI-format payloads and translating
    streamed NDJSON deltas back into AIMessageChunk / ToolCallChunk.
    """

    model_name: str = Field(description="Model name (e.g., gpt-4o, claude-3-sonnet)")
    deployment_id: str = Field(description="SAP AI Core deployment ID")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: int = Field(default=4096, description="Maximum tokens to generate")
    streaming: bool = Field(default=True, description="Whether to stream responses")
    api_base_url: str = Field(
        default="http://host.docker.internal:5056",
        description="Standalone SAP AI Core API URL",
    )
    bound_tools: Optional[List[Dict[str, Any]]] = Field(default=None)
    bound_tool_choice: Optional[Any] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "sap-ai-core"

    def bind_tools(
        self,
        tools: Sequence[Any],
        *,
        tool_choice: Optional[Any] = None,
        **kwargs: Any,
    ) -> "ChatSAPAICore":
        """
        Bind tools to this model in OpenAI function-calling format.
        Returns a new ChatSAPAICore so isinstance checks and field reads
        keep working downstream.
        """
        formatted = [convert_to_openai_tool(t) for t in tools]
        data = self.model_dump()
        data["bound_tools"] = formatted
        data["bound_tool_choice"] = tool_choice
        return ChatSAPAICore(**data)

    def _build_payload(
        self,
        messages: List[BaseMessage],
        stream: bool,
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        tools = kwargs.get("tools", self.bound_tools)
        tool_choice = kwargs.get("tool_choice", self.bound_tool_choice)
        payload: Dict[str, Any] = {
            "messages": self._messages_to_openai(messages),
            "model_name": self.model_name,
            "deployment_id": self.deployment_id,
            "stream": stream,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        return payload

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._build_payload(messages, stream=False, kwargs=kwargs)
        logger.info("[SAP AI Core HTTP] generate (sync, non-stream)")

        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{self.api_base_url}/chat", json=payload)
            response.raise_for_status()
            result = response.json()

        message = self._build_ai_message(result)
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._build_payload(messages, stream=False, kwargs=kwargs)
        logger.info("[SAP AI Core HTTP] generate (async, non-stream)")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.api_base_url}/chat", json=payload)
            response.raise_for_status()
            result = response.json()

        message = self._build_ai_message(result)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        payload = self._build_payload(messages, stream=True, kwargs=kwargs)
        logger.info("[SAP AI Core HTTP] stream (sync)")

        with httpx.Client(timeout=60.0) as client:
            with client.stream("POST", f"{self.api_base_url}/chat", json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    chunk = self._parse_line(line)
                    if chunk is None:
                        continue
                    if run_manager and chunk.message.content:
                        run_manager.on_llm_new_token(chunk.message.content, chunk=chunk)
                    yield chunk

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        payload = self._build_payload(messages, stream=True, kwargs=kwargs)
        logger.info("[SAP AI Core HTTP] stream (async)")

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", f"{self.api_base_url}/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    chunk = self._parse_line(line)
                    if chunk is None:
                        continue
                    if run_manager and chunk.message.content:
                        await run_manager.on_llm_new_token(chunk.message.content, chunk=chunk)
                    yield chunk

    def _parse_line(self, line: str) -> Optional[ChatGenerationChunk]:
        """
        Parse one NDJSON event into a ChatGenerationChunk. Returns None for
        lines that produce no chunk (e.g. finish events, blank lines).
        Raises on error events so astream surfaces failures cleanly.
        """
        if not line or not line.strip():
            return None

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            logger.warning("[SAP AI Core HTTP] could not parse line: %r", line[:200])
            return None

        etype = event.get("type")

        if etype == "content_delta":
            content = event.get("content", "")
            return ChatGenerationChunk(message=AIMessageChunk(content=content))

        if etype == "tool_call_delta":
            tcc = ToolCallChunk(
                name=event.get("name"),
                args=event.get("arguments"),
                id=event.get("id"),
                index=event.get("index", 0),
            )
            return ChatGenerationChunk(
                message=AIMessageChunk(content="", tool_call_chunks=[tcc])
            )

        if etype == "finish":
            return None

        if etype == "error":
            raise RuntimeError(event.get("message", "Upstream SAP AI Core error"))

        logger.debug("[SAP AI Core HTTP] unknown event type: %r", etype)
        return None

    def _build_ai_message(self, result: Dict[str, Any]) -> AIMessage:
        """Convert a non-streaming /chat response into an AIMessage."""
        content = result.get("content") or ""
        raw_tool_calls = result.get("tool_calls") or []

        tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function") or {}
            args_str = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                logger.warning("[SAP AI Core HTTP] tool call args were not valid JSON: %r", args_str[:200])
                args = {}
            tool_calls.append({
                "name": fn.get("name", ""),
                "args": args,
                "id": tc.get("id"),
            })

        return AIMessage(content=content, tool_calls=tool_calls)

    def _messages_to_openai(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """Convert LangChain messages to OpenAI chat format."""
        out: List[Dict[str, Any]] = []
        for message in messages:
            if isinstance(message, SystemMessage):
                out.append({"role": "system", "content": message.content})
            elif isinstance(message, HumanMessage):
                out.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                entry: Dict[str, Any] = {
                    "role": "assistant",
                    "content": message.content or "",
                }
                if message.tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": json.dumps(tc.get("args") or {}),
                            },
                        }
                        for tc in message.tool_calls
                    ]
                out.append(entry)
            elif isinstance(message, ToolMessage):
                out.append({
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": str(message.content),
                })
            else:
                out.append({"role": "user", "content": str(message.content)})
        return out
