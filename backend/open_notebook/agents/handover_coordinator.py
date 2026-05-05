"""
Handover Coordinator

Manages task handovers between agents using A2A protocol.
Packages results as A2A artifacts and coordinates context propagation.
"""

import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from a2a.types import Artifact, Part

from open_notebook.agents.a2a.team_message_bus import A2ATeamMessageBus
from open_notebook.agents.task_manager import TaskManager
from open_notebook.domain.agent_team import AgentTask, AgentMessage

logger = logging.getLogger(__name__)


class HandoverCoordinator:
    """
    Coordinates task handovers between agents.

    Handles:
    1. Packaging results as A2A artifacts
    2. Sending artifacts to next agent via message bus
    3. Updating task statuses
    4. Propagating context across handovers
    5. Logging handover history
    """

    def __init__(
        self,
        message_bus: A2ATeamMessageBus,
        task_manager: TaskManager
    ):
        """
        Initialize handover coordinator.

        Args:
            message_bus: A2A team message bus
            task_manager: Task manager for status updates
        """
        self.message_bus = message_bus
        self.task_manager = task_manager

    async def handover_task(
        self,
        from_agent_id: str,
        to_agent_id: str,
        completed_task_id: str,
        next_task_id: str,
        task_result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Hand over completed task result to next agent.

        Args:
            from_agent_id: Source agent ID
            to_agent_id: Target agent ID
            completed_task_id: ID of completed task
            next_task_id: ID of next task to execute
            task_result: Result from completed task
            context: Accumulated context from prior steps

        Returns:
            Handover confirmation with artifact IDs and message ID
        """
        context = context or {}

        logger.info(
            f"Handover: {from_agent_id} → {to_agent_id} "
            f"(task {completed_task_id} → {next_task_id})"
        )

        # 1. Mark completed task as done
        await self.task_manager.complete_task(
            task_id=completed_task_id,
            result=task_result
        )

        # 2. Package result as A2A artifact
        artifacts = self._create_artifacts(
            task_id=completed_task_id,
            task_result=task_result,
            context=context
        )

        # 3. Build handover message
        handover_message = self._build_handover_message(
            completed_task_id=completed_task_id,
            next_task_id=next_task_id,
            task_result=task_result,
            artifacts=artifacts,
            context=context
        )

        # 4. Send A2A message with artifacts
        try:
            response = await self.message_bus.send_message(
                sender_id=from_agent_id,
                recipient_id=to_agent_id,
                content=handover_message,
                metadata={
                    "handover": True,
                    "completed_task_id": completed_task_id,
                    "next_task_id": next_task_id,
                    "artifacts": [a.artifactId for a in artifacts],
                    "context": context
                }
            )

            logger.info(f"Handover message sent successfully")

        except Exception as e:
            logger.error(f"Handover failed: {e}")
            raise

        # 5. Assign next task to recipient agent
        await self.task_manager.assign_task(
            task_id=next_task_id,
            agent_id=to_agent_id
        )

        # 6. Log handover for observability
        await self._log_handover(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            completed_task_id=completed_task_id,
            next_task_id=next_task_id,
            artifacts=artifacts
        )

        return {
            "success": True,
            "from_agent_id": from_agent_id,
            "to_agent_id": to_agent_id,
            "completed_task_id": completed_task_id,
            "next_task_id": next_task_id,
            "artifact_ids": [a.artifactId for a in artifacts],
            "message_id": response.get("task_id"),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def broadcast_handover(
        self,
        from_agent_id: str,
        completed_task_id: str,
        task_result: Dict[str, Any],
        next_task_ids: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Broadcast handover to multiple agents (for parallel tasks).

        Args:
            from_agent_id: Source agent ID
            completed_task_id: Completed task ID
            task_result: Task result
            next_task_ids: List of next task IDs (one per recipient)
            context: Shared context

        Returns:
            List of handover confirmations
        """
        context = context or {}

        logger.info(
            f"Broadcasting handover from {from_agent_id} to "
            f"{len(next_task_ids)} agents"
        )

        # Mark completed task as done
        await self.task_manager.complete_task(
            task_id=completed_task_id,
            result=task_result
        )

        # Get recipient agents for next tasks
        handovers = []
        for next_task_id in next_task_ids:
            next_task = await AgentTask.get(next_task_id)
            if next_task and next_task.assignee_id:
                try:
                    handover = await self.handover_task(
                        from_agent_id=from_agent_id,
                        to_agent_id=next_task.assignee_id,
                        completed_task_id=completed_task_id,
                        next_task_id=next_task_id,
                        task_result=task_result,
                        context=context
                    )
                    handovers.append(handover)
                except Exception as e:
                    logger.error(f"Handover to {next_task.assignee_id} failed: {e}")
                    handovers.append({
                        "success": False,
                        "error": str(e),
                        "next_task_id": next_task_id
                    })

        return handovers

    def _create_artifacts(
        self,
        task_id: str,
        task_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[Artifact]:
        """
        Create A2A artifacts from task result.

        Args:
            task_id: Task ID
            task_result: Result data
            context: Context data

        Returns:
            List of A2A artifacts
        """
        artifacts = []

        # Main result artifact
        result_artifact = Artifact(
            artifactId=f"{task_id}-result",
            parts=[Part(text=json.dumps(task_result, indent=2))]
        )
        artifacts.append(result_artifact)

        # Context artifact (if present)
        if context:
            context_artifact = Artifact(
                artifactId=f"{task_id}-context",
                parts=[TextPart(text=json.dumps(context, indent=2))]
            )
            artifacts.append(context_artifact)

        # Output artifact (if result has specific output field)
        if "output" in task_result:
            output_artifact = Artifact(
                artifactId=f"{task_id}-output",
                parts=[TextPart(text=str(task_result["output"]))]
            )
            artifacts.append(output_artifact)

        # Data artifact (if result has data field)
        if "data" in task_result:
            data_artifact = Artifact(
                artifactId=f"{task_id}-data",
                parts=[TextPart(text=json.dumps(task_result["data"], indent=2))]
            )
            artifacts.append(data_artifact)

        return artifacts

    def _build_handover_message(
        self,
        completed_task_id: str,
        next_task_id: str,
        task_result: Dict[str, Any],
        artifacts: List[Artifact],
        context: Dict[str, Any]
    ) -> str:
        """
        Build handover message for next agent.

        Args:
            completed_task_id: Completed task ID
            next_task_id: Next task ID
            task_result: Task result
            artifacts: Artifacts created
            context: Context data

        Returns:
            Handover message text
        """
        message_parts = [
            f"Task {completed_task_id} completed successfully.",
            "",
            "**Result Summary:**"
        ]

        # Add result summary
        if "output" in task_result:
            message_parts.append(f"- Output: {task_result['output'][:200]}...")
        if "status" in task_result:
            message_parts.append(f"- Status: {task_result['status']}")

        message_parts.extend([
            "",
            f"**Next Task:** {next_task_id}",
            "",
            f"**Artifacts Available:** {len(artifacts)}",
        ])

        for artifact in artifacts:
            message_parts.append(f"  - {artifact.artifactId}")

        # Add context hints
        if context:
            message_parts.extend([
                "",
                "**Context from Previous Steps:**"
            ])
            for key in list(context.keys())[:5]:  # Show up to 5 context keys
                message_parts.append(f"  - {key}")

        message_parts.extend([
            "",
            "Please execute the next task using the provided artifacts and context."
        ])

        return "\n".join(message_parts)

    async def _log_handover(
        self,
        from_agent_id: str,
        to_agent_id: str,
        completed_task_id: str,
        next_task_id: str,
        artifacts: List[Artifact]
    ) -> None:
        """
        Log handover for observability.

        Args:
            from_agent_id: Source agent
            to_agent_id: Target agent
            completed_task_id: Completed task
            next_task_id: Next task
            artifacts: Artifacts transferred
        """
        # Get team ID from task
        completed_task = await AgentTask.get(completed_task_id)
        if not completed_task:
            return

        team_id = completed_task.team_id

        # Create handover log message
        log_message = AgentMessage(
            team_id=team_id,
            sender_id=from_agent_id,
            recipient_id=to_agent_id,
            message_type="handover",
            content=f"Handover: {completed_task_id} → {next_task_id}",
            metadata=json.dumps({
                "completed_task_id": completed_task_id,
                "next_task_id": next_task_id,
                "artifact_ids": [a.artifactId for a in artifacts],
                "artifact_count": len(artifacts),
                "timestamp": datetime.utcnow().isoformat()
            })
        )

        await log_message.save()

        logger.debug(f"Handover logged to database")

    async def merge_results(
        self,
        task_results: List[Dict[str, Any]],
        merge_strategy: str = "concat"
    ) -> Dict[str, Any]:
        """
        Merge results from multiple tasks (for synthesis).

        Args:
            task_results: List of task results to merge
            merge_strategy: Strategy for merging (concat, aggregate, select_best)

        Returns:
            Merged result dict
        """
        if not task_results:
            return {}

        if len(task_results) == 1:
            return task_results[0]

        # Apply merge strategy
        if merge_strategy == "concat":
            return self._merge_concat(task_results)
        elif merge_strategy == "aggregate":
            return self._merge_aggregate(task_results)
        elif merge_strategy == "select_best":
            return self._merge_select_best(task_results)
        else:
            logger.warning(f"Unknown merge strategy: {merge_strategy}, using concat")
            return self._merge_concat(task_results)

    def _merge_concat(self, task_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Concatenate all results."""
        merged = {
            "outputs": [],
            "data": [],
            "metadata": {
                "source_count": len(task_results),
                "merge_strategy": "concat"
            }
        }

        for result in task_results:
            if "output" in result:
                merged["outputs"].append(result["output"])
            if "data" in result:
                merged["data"].append(result["data"])

        return merged

    def _merge_aggregate(self, task_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate results with statistics."""
        merged = {
            "summary": [],
            "statistics": {},
            "metadata": {
                "source_count": len(task_results),
                "merge_strategy": "aggregate"
            }
        }

        # Collect summaries
        for result in task_results:
            if "output" in result:
                merged["summary"].append(result["output"])

        # Calculate statistics (if numeric data present)
        all_data = []
        for result in task_results:
            if "data" in result and isinstance(result["data"], list):
                all_data.extend(result["data"])

        if all_data and all(isinstance(x, (int, float)) for x in all_data):
            merged["statistics"] = {
                "count": len(all_data),
                "sum": sum(all_data),
                "avg": sum(all_data) / len(all_data),
                "min": min(all_data),
                "max": max(all_data)
            }

        return merged

    def _merge_select_best(self, task_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select best result based on confidence or score."""
        # Find result with highest confidence/score
        best_result = max(
            task_results,
            key=lambda r: r.get("confidence", r.get("score", 0))
        )

        return {
            **best_result,
            "metadata": {
                "source_count": len(task_results),
                "merge_strategy": "select_best",
                "selected_confidence": best_result.get("confidence", 0)
            }
        }


# Convenience function
async def handover_task(
    message_bus: A2ATeamMessageBus,
    task_manager: TaskManager,
    from_agent_id: str,
    to_agent_id: str,
    completed_task_id: str,
    next_task_id: str,
    task_result: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function for task handover.

    Args:
        message_bus: A2A message bus
        task_manager: Task manager
        from_agent_id: Source agent
        to_agent_id: Target agent
        completed_task_id: Completed task
        next_task_id: Next task
        task_result: Task result
        context: Context

    Returns:
        Handover confirmation
    """
    coordinator = HandoverCoordinator(message_bus, task_manager)
    return await coordinator.handover_task(
        from_agent_id=from_agent_id,
        to_agent_id=to_agent_id,
        completed_task_id=completed_task_id,
        next_task_id=next_task_id,
        task_result=task_result,
        context=context
    )
