"""
A2A Protocol Client

Client for invoking remote A2A agents.
"""

import json
import logging
import uuid
from typing import Any, AsyncIterator, Dict, Optional

import httpx
from a2a.types import (
    AgentCard,
    Artifact,
    Message,
    SendMessageRequest,
    SendMessageResponse,
    MessageSendConfiguration,
    Part,
)

from open_notebook.domain.a2a import A2ARemoteAgent, A2ATask, A2AExecutionMetric

logger = logging.getLogger(__name__)


class OpenNotebookA2AClient:
    """
    Client wrapper for calling remote A2A agents.

    Handles:
    - JSON-RPC message formatting
    - HTTP/HTTPS transport
    - Streaming responses (SSE)
    - Error handling and retries
    - Metrics collection
    """

    def __init__(
        self,
        remote_agent: A2ARemoteAgent,
        timeout: int = 30,
    ):
        """
        Initialize A2A client.

        Args:
            remote_agent: Remote agent to connect to
            timeout: Request timeout in seconds
        """
        self.agent = remote_agent
        self.card = AgentCard.model_validate_json(remote_agent.agent_card)
        self.timeout = timeout

        # Get endpoint URL
        self.endpoint_url = remote_agent.endpoint_url

        # HTTP client
        self.http_client = httpx.AsyncClient(timeout=timeout)

    async def send_message(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        context_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send synchronous message to remote agent.

        Args:
            skill_id: Remote skill ID
            input_data: Input data for skill
            context_id: Optional context ID

        Returns:
            Result dictionary

        Raises:
            httpx.HTTPError: If request fails
            ValueError: If response is invalid
        """
        import time
        start_time = time.time()

        context_id = context_id or str(uuid.uuid4())

        # Create A2A message
        message = self._create_message(skill_id, input_data)

        # Build A2A request
        request = SendMessageRequest(
            message=message,
            metadata={"contextId": context_id},
        )

        logger.info(
            f"Sending A2A message to {self.agent.name} "
            f"(skill={skill_id}, context={context_id})"
        )

        # Send request
        try:
            response = await self.http_client.post(
                self.endpoint_url,
                json=request.model_dump(mode="json", exclude_none=True),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            latency_ms = (time.time() - start_time) * 1000

            # Parse response
            response_data = response.json()
            a2a_response = SendMessageResponse.model_validate(response_data)

            # Extract the actual response from the union (root field)
            actual_response = a2a_response.root

            # Record success metric
            task_id = request_id
            if hasattr(actual_response, 'result') and hasattr(actual_response.result, 'id'):
                task_id = str(actual_response.result.id)

            await A2AExecutionMetric.record_execution(
                agent_id=self.agent.id,
                task_id=task_id,
                skill_id=skill_id,
                success=True,
                latency_ms=latency_ms,
            )

            # Extract result from artifacts
            result = self._extract_result(actual_response)

            logger.info(f"A2A message completed successfully (latency={latency_ms:.0f}ms)")
            return result

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000

            # Record error metric
            error_type = type(e).__name__
            await A2AExecutionMetric.record_execution(
                agent_id=self.agent.id,
                task_id=request_id,
                skill_id=skill_id,
                success=False,
                latency_ms=latency_ms,
                error_type=error_type,
                error_message=str(e),
            )

            logger.error(f"A2A message failed: {e}")
            raise

    async def stream_message(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        context_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream message to remote agent (SSE).

        Args:
            skill_id: Remote skill ID
            input_data: Input data
            context_id: Optional context ID

        Yields:
            Progress events and results

        Raises:
            httpx.HTTPError: If request fails
        """
        context_id = context_id or str(uuid.uuid4())

        # Create message
        message = self._create_message(skill_id, input_data)

        # Build streaming request
        request_id = str(uuid.uuid4())
        # Note: A2A SDK might have different streaming request format
        # This is a placeholder - adjust based on actual A2A v0.3 spec
        request_data = {
            "id": request_id,
            "jsonrpc": "2.0",
            "method": "message/stream",
            "params": {
                "message": message.model_dump(mode="json"),
                "metadata": {"contextId": context_id},
            },
        }

        logger.info(f"Streaming A2A message to {self.agent.name}")

        async with self.http_client.stream(
            "POST",
            self.endpoint_url.replace("/send", "/stream"),  # Adjust URL
            json=request_data,
            headers={"Content-Type": "application/json"},
        ) as response:
            response.raise_for_status()

            # Parse SSE events
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        yield {
                            "event_type": data.get("event", "unknown"),
                            "data": data,
                        }
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse SSE data: {line}")

    def _create_message(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
    ) -> Message:
        """
        Create A2A Message from skill invocation.

        Args:
            skill_id: Skill ID
            input_data: Input data

        Returns:
            A2A Message
        """
        # Wrap input in JSON
        content = json.dumps({
            "skill_id": skill_id,
            "input": input_data,
        })

        return Message(
            messageId=str(uuid.uuid4()),
            role="user",
            parts=[Part(text=content)],
        )

    def _extract_result(
        self,
        response,  # SendMessageSuccessResponse or SendMessageErrorResponse
    ) -> Dict[str, Any]:
        """
        Extract result from A2A response.

        Args:
            response: SendMessageSuccessResponse or SendMessageErrorResponse

        Returns:
            Result dictionary
        """
        # Check if response has result (success response)
        if not hasattr(response, 'result') or not response.result:
            return {}

        result_obj = response.result

        # Extract artifacts
        if hasattr(result_obj, 'artifacts') and result_obj.artifacts:
            artifacts = result_obj.artifacts

            # Iterate through artifacts
            for artifact in artifacts:
                if hasattr(artifact, 'parts') and artifact.parts:
                    # Concatenate all text parts
                    content = "".join(
                        part.text for part in artifact.parts
                        if hasattr(part, 'text') and part.text
                    )

                    # Try to parse as JSON first
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        # Return as text if not JSON
                        return {"text": content}

        return {}

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
