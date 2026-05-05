"""
A2A Message Handler

Handles incoming A2A message requests and maps to local skill execution.
"""

import json
import logging
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from a2a.types import (
    Artifact,
    Message,
    Part,
    SendMessageRequest,
    SendMessageResponse,
    SubscribeToTaskRequest as MessageStreamRequest,
    TaskStatus,
)

from open_notebook.agents.a2a.task_manager import A2ATaskManager
from open_notebook.agents.skills.base import SkillContext, SkillExecutionResult
from open_notebook.agents.skills.executor import get_skill_executor
from open_notebook.agents.skills.registry import get_skill_registry

logger = logging.getLogger(__name__)


class A2AMessageHandler:
    """
    Handle incoming A2A message requests and map to local execution.

    Supports both synchronous (message/send) and streaming (message/stream) modes.
    """

    def __init__(self):
        self.skill_registry = get_skill_registry()
        self.skill_executor = get_skill_executor()
        self.task_manager = A2ATaskManager()

    async def handle_message_send(
        self,
        request: SendMessageRequest,
    ) -> SendMessageResponse:
        """
        Handle synchronous message/send request.

        Maps to local skill execution via SkillExecutor.

        Args:
            request: A2A SendMessageRequest

        Returns:
            A2A SendMessageResponse with results
        """
        # 1. Extract context and skill info
        task_id = str(uuid.uuid4())
        context_id = request.contextId or str(uuid.uuid4())
        skill_id, input_data = self._parse_message_for_skill(request.message)

        logger.info(
            f"Handling A2A message/send - task_id={task_id}, "
            f"skill_id={skill_id}, context_id={context_id}"
        )

        # 2. Create task
        task = await self.task_manager.create_task(
            task_id=task_id,
            context_id=context_id,
            direction="incoming",
            skill_id=skill_id,
        )

        # Append request to history
        await self.task_manager.append_to_history(
            task_id,
            self._message_to_dict(request.message),
        )

        # 3. Execute skill
        try:
            await self.task_manager.mark_task_running(task_id)

            result = await self._execute_skill(
                skill_id=skill_id,
                input_data=input_data,
                context_id=context_id,
                task_id=task_id,
            )

            # 4. Mark task completed
            artifacts = self._result_to_artifacts(result)
            await self.task_manager.mark_task_completed(task_id, artifacts)

            # Build response
            response = MessageSendResponse(
                taskId=task_id,
                status=TaskStatus(state="completed", progress=1.0),
                artifacts=artifacts,
            )

            logger.info(f"A2A message/send completed - task_id={task_id}")
            return response

        except Exception as e:
            # Mark task failed
            error_msg = f"{type(e).__name__}: {e}"
            await self.task_manager.mark_task_failed(task_id, error_msg)

            logger.error(f"A2A message/send failed - task_id={task_id}: {e}")

            # Return error response
            return MessageSendResponse(
                taskId=task_id,
                status=TaskStatus(
                    state="failed",
                    message=error_msg,
                ),
                artifacts=[],
            )

    async def handle_message_stream(
        self,
        request: MessageStreamRequest,
    ) -> AsyncIterator[str]:
        """
        Handle streaming message/stream request.

        Yields Server-Sent Events (SSE) as skill executes.

        Args:
            request: A2A MessageStreamRequest

        Yields:
            SSE-formatted strings
        """
        # 1. Extract context and skill info
        task_id = str(uuid.uuid4())
        context_id = request.contextId or str(uuid.uuid4())
        skill_id, input_data = self._parse_message_for_skill(request.message)

        logger.info(
            f"Handling A2A message/stream - task_id={task_id}, "
            f"skill_id={skill_id}, context_id={context_id}"
        )

        # 2. Create task
        task = await self.task_manager.create_task(
            task_id=task_id,
            context_id=context_id,
            direction="incoming",
            skill_id=skill_id,
        )

        # Yield initial event
        yield self._sse_event("task.created", {
            "taskId": task_id,
            "status": {"state": "queued"},
        })

        try:
            # 3. Mark running and yield event
            await self.task_manager.mark_task_running(task_id)
            yield self._sse_event("task.updated", {
                "taskId": task_id,
                "status": {"state": "running", "progress": 0.0},
            })

            # 4. Execute skill and stream progress
            result = await self._execute_skill_streaming(
                skill_id=skill_id,
                input_data=input_data,
                context_id=context_id,
                task_id=task_id,
            )

            # Yield progress events from skill execution
            async for progress_event in result["events"]:
                await self.task_manager.update_task_status(
                    task_id,
                    "running",
                    progress=progress_event.get("progress", 0.5),
                    message=progress_event.get("message"),
                )

                yield self._sse_event("task.updated", {
                    "taskId": task_id,
                    "status": {
                        "state": "running",
                        "progress": progress_event.get("progress", 0.5),
                        "message": progress_event.get("message"),
                    },
                })

            # 5. Mark completed and yield final event
            artifacts = self._result_to_artifacts(result["result"])
            await self.task_manager.mark_task_completed(task_id, artifacts)

            yield self._sse_event("task.completed", {
                "taskId": task_id,
                "status": {"state": "completed", "progress": 1.0},
                "artifacts": [a.model_dump() for a in artifacts],
            })

            logger.info(f"A2A message/stream completed - task_id={task_id}")

        except Exception as e:
            # Mark failed and yield error event
            error_msg = f"{type(e).__name__}: {e}"
            await self.task_manager.mark_task_failed(task_id, error_msg)

            yield self._sse_event("task.failed", {
                "taskId": task_id,
                "status": {
                    "state": "failed",
                    "message": error_msg,
                },
            })

            logger.error(f"A2A message/stream failed - task_id={task_id}: {e}")

    def _parse_message_for_skill(
        self,
        message: Message,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Extract skill ID and input data from A2A message.

        Args:
            message: A2A Message

        Returns:
            Tuple of (skill_id, input_data)
        """
        # Get first text part
        text_content = None
        for part in message.parts:
            if hasattr(part, 'text') and part.text:
                text_content = part.text
                break

        if not text_content:
            raise ValueError("No text content in message")

        # Try to parse as JSON
        try:
            data = json.loads(text_content)
            skill_id = data.get("skill_id")
            input_data = data.get("input", {})

            if not skill_id:
                # If no explicit skill_id, use the text as input
                # and let orchestrator choose skill
                return "auto", {"query": text_content}

            return skill_id, input_data

        except json.JSONDecodeError:
            # Plain text - use as query
            return "auto", {"query": text_content}

    async def _execute_skill(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        context_id: str,
        task_id: str,
    ) -> SkillExecutionResult:
        """
        Execute skill synchronously.

        Args:
            skill_id: Skill identifier
            input_data: Skill input
            context_id: Context ID
            task_id: Task ID

        Returns:
            SkillExecutionResult
        """
        # Build context
        context = SkillContext(
            agent_id="a2a-server",
            agent_role="server",
            skill_id=skill_id,
            execution_id=task_id,
            input_data=input_data,
        )

        # Execute
        result = await self.skill_executor.execute(skill_id, context)
        return result

    async def _execute_skill_streaming(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        context_id: str,
        task_id: str,
    ) -> Dict[str, Any]:
        """
        Execute skill with streaming progress updates.

        Args:
            skill_id: Skill identifier
            input_data: Skill input
            context_id: Context ID
            task_id: Task ID

        Returns:
            Dict with 'result' and 'events' (async generator)
        """
        # TODO: Implement streaming execution
        # For now, execute synchronously and fake streaming

        async def progress_generator():
            """Yield progress events."""
            yield {"progress": 0.2, "message": "Starting execution"}
            yield {"progress": 0.5, "message": "Processing"}
            yield {"progress": 0.8, "message": "Finalizing"}

        result = await self._execute_skill(skill_id, input_data, context_id, task_id)

        return {
            "result": result,
            "events": progress_generator(),
        }

    def _result_to_artifacts(
        self,
        result: SkillExecutionResult,
    ) -> List[Artifact]:
        """
        Convert SkillExecutionResult to A2A Artifacts.

        Args:
            result: Skill execution result

        Returns:
            List of A2A Artifacts
        """
        artifacts = []

        # Main result artifact
        if result.success and result.result:
            # Determine MIME type
            if isinstance(result.result, dict) or isinstance(result.result, list):
                mime_type = "application/json"
                content = json.dumps(result.result)
            else:
                mime_type = "text/plain"
                content = str(result.result)

            artifacts.append(Artifact(
                id=str(uuid.uuid4()),
                mimeType=mime_type,
                content=content,
            ))

        # Add steps as separate artifact (optional)
        if result.steps:
            artifacts.append(Artifact(
                id=str(uuid.uuid4()),
                mimeType="application/json",
                content=json.dumps({"steps": result.steps}),
            ))

        return artifacts

    def _message_to_dict(self, message: Message) -> Dict[str, Any]:
        """Convert A2A Message to dict."""
        return message.model_dump(mode="json")

    def _sse_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """
        Format Server-Sent Event.

        Args:
            event_type: Event type name
            data: Event data

        Returns:
            SSE-formatted string
        """
        return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
