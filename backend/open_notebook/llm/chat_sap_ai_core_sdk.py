"""
SAP AI Core Chat Model Wrapper (HTTP Client)

LangChain-compatible chat model for SAP AI Core deployments.
Calls the standalone SAP AI Core API (running on port 5056) via HTTP.
This avoids dependency conflicts with gen-ai-hub SDK.

Supports both streaming (for chat UI) and non-streaming (for workflows/agents) modes.
"""

import logging
from typing import Any, AsyncIterator, Iterator, List, Optional

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
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import Field

logger = logging.getLogger(__name__)


class ChatSAPAICore(BaseChatModel):
    """
    LangChain chat model wrapper for SAP AI Core deployments.

    This wrapper calls the standalone SAP AI Core API via HTTP.
    The standalone API handles:
    - OAuth authentication with gen-ai-hub SDK
    - Correct API endpoint routing
    - Model compatibility and token management

    Supports:
    - Streaming responses (for chat UI)
    - Non-streaming responses (for workflows/agents)
    """

    model_name: str = Field(description="Model name (e.g., gpt-4o, claude-3-sonnet)")
    deployment_id: str = Field(description="SAP AI Core deployment ID")
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: int = Field(default=4096, description="Maximum tokens to generate")
    streaming: bool = Field(default=True, description="Whether to stream responses")
    api_base_url: str = Field(
        default="http://host.docker.internal:5056",
        description="Standalone SAP AI Core API URL"
    )

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        """Return identifier string"""
        return "sap-ai-core"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Synchronous generation (non-streaming).
        Used for workflows and agents.
        """
        # Convert messages to prompt
        prompt = self._messages_to_prompt(messages)

        logger.info(f"[SAP AI Core HTTP] Generating response (non-streaming)")

        # Call standalone API via HTTP
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.api_base_url}/chat",
                json={
                    "message": prompt,
                    "model_name": self.model_name,
                    "deployment_id": self.deployment_id,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()

        # Convert response to ChatResult
        message = AIMessage(content=result["response"])
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        Async generation (non-streaming).
        Used for workflows and agents.
        """
        # Convert messages to prompt
        prompt = self._messages_to_prompt(messages)

        logger.info(f"[SAP AI Core HTTP] Generating async response (non-streaming)")

        # Call standalone API via HTTP
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.api_base_url}/chat",
                json={
                    "message": prompt,
                    "model_name": self.model_name,
                    "deployment_id": self.deployment_id,
                    "stream": False
                }
            )
            response.raise_for_status()
            result = response.json()

        # Convert response to ChatResult
        message = AIMessage(content=result["response"])
        generation = ChatGeneration(message=message)

        return ChatResult(generations=[generation])

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """
        Synchronous streaming.
        Used for chat UI.
        """
        # Convert messages to prompt
        prompt = self._messages_to_prompt(messages)

        logger.info(f"[SAP AI Core HTTP] Streaming response (sync)")

        # Call standalone API via HTTP with streaming
        with httpx.Client(timeout=60.0) as client:
            with client.stream(
                "POST",
                f"{self.api_base_url}/chat",
                json={
                    "message": prompt,
                    "model_name": self.model_name,
                    "deployment_id": self.deployment_id,
                    "stream": True
                }
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_text():
                    if chunk:
                        message_chunk = AIMessageChunk(content=chunk)
                        generation_chunk = ChatGenerationChunk(message=message_chunk)

                        if run_manager:
                            run_manager.on_llm_new_token(chunk, chunk=generation_chunk)

                        yield generation_chunk

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """
        Async streaming.
        Used for chat UI with async endpoints.
        """
        # Convert messages to prompt
        prompt = self._messages_to_prompt(messages)

        logger.info(f"[SAP AI Core HTTP] _astream called! Streaming response (async)")
        print(f"[SAP AI Core HTTP] _astream called! Starting streaming request")

        # Call standalone API via HTTP with streaming
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.api_base_url}/chat",
                json={
                    "message": prompt,
                    "model_name": self.model_name,
                    "deployment_id": self.deployment_id,
                    "stream": True
                }
            ) as response:
                response.raise_for_status()
                print(f"[SAP AI Core HTTP] Starting to iterate chunks...")
                chunk_count = 0
                async for chunk_bytes in response.aiter_raw():
                    if chunk_bytes:
                        chunk_count += 1
                        chunk = chunk_bytes.decode('utf-8')
                        print(f"[SAP AI Core HTTP] Chunk {chunk_count}: {chunk[:50]}")
                        message_chunk = AIMessageChunk(content=chunk)
                        generation_chunk = ChatGenerationChunk(message=message_chunk)

                        if run_manager:
                            await run_manager.on_llm_new_token(chunk, chunk=generation_chunk)

                        yield generation_chunk
                print(f"[SAP AI Core HTTP] Finished streaming, total chunks: {chunk_count}")

    def _messages_to_prompt(self, messages: List[BaseMessage]) -> str:
        """
        Convert LangChain messages to a prompt string.

        The SDK's init_llm returns a LangChain-compatible model,
        so we can pass messages directly or convert to string.
        For simplicity, we convert to string format.
        """
        parts = []
        for message in messages:
            if isinstance(message, SystemMessage):
                parts.append(f"System: {message.content}")
            elif isinstance(message, HumanMessage):
                parts.append(f"Human: {message.content}")
            elif isinstance(message, AIMessage):
                parts.append(f"Assistant: {message.content}")
            else:
                parts.append(str(message.content))

        return "\n\n".join(parts)
