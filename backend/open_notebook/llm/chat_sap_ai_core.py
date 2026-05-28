"""
SAP AI Core Chat Model Wrapper

LangChain-compatible chat model for SAP AI Core deployments.
Supports both streaming (for chat UI) and non-streaming (for workflows/agents) modes.
"""

import logging
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
import json

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
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

from api.services.sap_ai_core_service import SAPAICoreService

logger = logging.getLogger(__name__)


class ChatSAPAICore(BaseChatModel):
    """
    LangChain chat model wrapper for SAP AI Core deployments.

    Supports:
    - Streaming responses (for chat UI)
    - Non-streaming responses (for workflows/agents)
    - Dynamic function calling capability detection
    - OAuth token management via SAPAICoreService
    """

    service: SAPAICoreService = Field(description="SAP AI Core service instance")
    deployment_id: str = Field(description="SAP AI Core deployment ID")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: int = Field(default=4096, description="Maximum tokens to generate")
    supports_function_calling: Optional[bool] = Field(
        default=None, description="Whether model supports function calling"
    )
    proxy_url: Optional[str] = Field(
        default=None, description="Optional proxy URL (e.g., http://host.docker.internal:5056)"
    )
    model_name: Optional[str] = Field(
        default="gpt-4o", description="Model name for proxy requests"
    )

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        """Return type of language model."""
        return "sap-ai-core"

    def _convert_messages_to_sap_format(
        self, messages: List[BaseMessage]
    ) -> List[Dict[str, str]]:
        """
        Convert LangChain messages to SAP AI Core format.

        SAP AI Core expects OpenAI-compatible format:
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, ...]
        """
        converted = []
        for message in messages:
            if isinstance(message, SystemMessage):
                converted.append({"role": "system", "content": message.content})
            elif isinstance(message, HumanMessage):
                converted.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                converted.append({"role": "assistant", "content": message.content})
            else:
                # Fallback for other message types
                converted.append({"role": "user", "content": str(message.content)})

        return converted

    async def _check_capabilities(self) -> Dict[str, bool]:
        """
        Check model capabilities from SAP AI Core deployment metadata.

        Returns:
            Dict with capability flags (supports_function_calling, supports_streaming)
        """
        try:
            # Get deployment details to check capabilities
            details = await self.service.get_deployment_details(self.deployment_id)

            # Parse capabilities from deployment metadata
            # SAP AI Core may provide this in details or scenario metadata
            scenario_id = details.get("scenarioId", "").lower()
            details_obj = details.get("details", {})

            supports_function_calling = (
                "function" in scenario_id or
                "tool" in scenario_id or
                details_obj.get("functionCalling", False)
            )

            supports_streaming = (
                "stream" in scenario_id or
                details_obj.get("streaming", True)  # Default to True
            )

            logger.info(
                f"[ChatSAPAICore] Deployment {self.deployment_id} capabilities: "
                f"function_calling={supports_function_calling}, "
                f"streaming={supports_streaming}"
            )

            return {
                "supports_function_calling": supports_function_calling,
                "supports_streaming": supports_streaming,
            }
        except Exception as e:
            logger.warning(
                f"[ChatSAPAICore] Failed to check capabilities for {self.deployment_id}: {e}"
            )
            # Default to safe values
            return {
                "supports_function_calling": False,
                "supports_streaming": True,
            }

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Synchronous generation (non-streaming).

        This is a blocking wrapper around the async method.
        Used when LangChain calls the model synchronously.
        """
        import asyncio

        # Run async method in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self._agenerate(messages, stop=stop, run_manager=None, **kwargs)
        )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Async generation (non-streaming).

        Used for workflows and agents where we need the complete response.
        """
        logger.info(
            f"[ChatSAPAICore] Non-streaming generation for deployment {self.deployment_id}"
        )

        # Convert messages to SAP AI Core format
        sap_messages = self._convert_messages_to_sap_format(messages)

        # Build request parameters
        params = {
            "temperature": kwargs.get("temperature", self.temperature),
            "max_completion_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        # Add stop sequences if provided
        if stop:
            params["stop"] = stop

        # Add function calling if supported and tools provided
        if "functions" in kwargs or "tools" in kwargs:
            # Check if model supports function calling
            if self.supports_function_calling is None:
                capabilities = await self._check_capabilities()
                self.supports_function_calling = capabilities["supports_function_calling"]

            if self.supports_function_calling:
                # Pass through function/tool definitions
                if "functions" in kwargs:
                    params["functions"] = kwargs["functions"]
                if "tools" in kwargs:
                    params["tools"] = kwargs["tools"]
                logger.info("[ChatSAPAICore] Function calling enabled")
            else:
                logger.warning(
                    f"[ChatSAPAICore] Model {self.deployment_id} does not support "
                    "function calling. Tools will be ignored."
                )

        try:
            # Invoke SAP AI Core model
            response = await self.service.invoke_model(
                deployment_id=self.deployment_id,
                messages=sap_messages,
                **params
            )

            # Parse response (SAP AI Core should return OpenAI-compatible format)
            # Expected: {"choices": [{"message": {"role": "assistant", "content": "..."}}]}
            choices = response.get("choices", [])
            if not choices:
                raise ValueError("No choices in SAP AI Core response")

            message_data = choices[0].get("message", {})
            content = message_data.get("content", "")

            # Create AIMessage
            message = AIMessage(content=content)

            # Handle function calls if present
            if "function_call" in message_data:
                message.additional_kwargs["function_call"] = message_data["function_call"]
            if "tool_calls" in message_data:
                message.additional_kwargs["tool_calls"] = message_data["tool_calls"]

            # Create generation
            generation = ChatGeneration(message=message)

            logger.info(
                f"[ChatSAPAICore] Generated response: {len(content)} chars"
            )

            return ChatResult(generations=[generation])

        except Exception as e:
            logger.error(f"[ChatSAPAICore] Generation failed: {e}")
            raise

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """
        Async streaming generation.

        Used for chat UI where we want real-time response display.
        """
        logger.info(
            f"[ChatSAPAICore] Streaming generation for deployment {self.deployment_id}"
        )

        # Convert messages to SAP AI Core format
        sap_messages = self._convert_messages_to_sap_format(messages)

        # Build request parameters
        params = {
            "temperature": kwargs.get("temperature", self.temperature),
            "max_completion_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": True,  # Enable streaming
        }

        # Add stop sequences if provided
        if stop:
            params["stop"] = stop

        try:
            # Use proxy if available (Docker environment)
            if self.proxy_url:
                logger.info(f"[ChatSAPAICore] Using proxy at {self.proxy_url}")
                async for chunk in self._stream_via_proxy(sap_messages, params):
                    yield chunk
            else:
                # Use direct SAP AI Core service connection
                async for chunk in self._stream_via_service(sap_messages, params, run_manager):
                    yield chunk

            logger.info("[ChatSAPAICore] Streaming complete")

        except Exception as e:
            logger.error(f"[ChatSAPAICore] Streaming failed: {e}")
            raise

    async def _stream_via_proxy(
        self,
        messages: List[Dict[str, str]],
        params: Dict[str, Any],
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Stream via simple HTTP proxy (for Docker environment)"""
        import httpx

        # The proxy doesn't support streaming yet, so we'll use non-streaming
        # and return the full response at once
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.proxy_url}/chat",
                json={
                    "message": messages[-1]["content"] if messages else "",
                    "model_name": self.model_name or "gpt-4o",
                    "deployment_id": self.deployment_id,
                    "stream": False
                },
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("response", "")

            if content:
                message_chunk = AIMessageChunk(content=content)
                yield ChatGenerationChunk(message=message_chunk)

    async def _stream_via_service(
        self,
        messages: List[Dict[str, str]],
        params: Dict[str, Any],
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Stream via SAP AI Core service (direct API connection)"""
        async for chunk in self.service.stream_model(
            deployment_id=self.deployment_id,
            messages=messages,
            **params
        ):
            # Parse SSE chunk (Server-Sent Events format)
            # Expected: data: {"choices": [{"delta": {"content": "..."}}]}

            if chunk.startswith("data: "):
                chunk_data = chunk[6:]  # Remove "data: " prefix

                if chunk_data.strip() == "[DONE]":
                    break

                try:
                    data = json.loads(chunk_data)
                    choices = data.get("choices", [])

                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")

                        if content:
                            # Create chunk
                            message_chunk = AIMessageChunk(content=content)
                            generation_chunk = ChatGenerationChunk(message=message_chunk)

                            # Send to callback if available
                            if run_manager:
                                await run_manager.on_llm_new_token(content)

                            yield generation_chunk

                except json.JSONDecodeError:
                    logger.warning(f"[ChatSAPAICore] Failed to parse chunk: {chunk_data}")
                    continue

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """
        Synchronous streaming (not typically used).

        This is a blocking wrapper around the async streaming method.
        """
        import asyncio

        # Run async method in event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _async_generator():
            async for chunk in self._astream(messages, stop=stop, run_manager=None, **kwargs):
                yield chunk

        # Convert async generator to sync
        async_gen = _async_generator()
        while True:
            try:
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
            except StopAsyncIteration:
                break
