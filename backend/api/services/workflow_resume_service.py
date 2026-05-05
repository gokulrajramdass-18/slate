"""
Workflow Resume Service

Handles pausing and resuming workflow executions for human-in-the-loop approvals.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional


async def pause_workflow_execution(
    execution_id: str,
    reason: str,
    approval_id: Optional[str] = None
):
    """
    Pause a workflow execution.

    Args:
        execution_id: Execution to pause
        reason: Reason for pause (e.g., "awaiting_approval")
        approval_id: Optional approval ID if pausing for approval
    """
    from open_notebook.domain.workflow import WorkflowExecution, ExecutionStatus

    execution = await WorkflowExecution.get(execution_id)
    if not execution:
        raise ValueError(f"Execution {execution_id} not found")

    # Update execution status to paused
    execution.status = ExecutionStatus.PAUSED
    execution.paused_at = datetime.utcnow()
    execution.paused_reason = reason

    if approval_id:
        execution.resume_data = json.dumps({"approval_id": approval_id})

    await execution.save()
    print(f"[WorkflowResumeService] Paused execution {execution_id}: {reason}")


async def resume_workflow_execution(
    execution_id: str,
    resume_data: Optional[Dict[str, Any]] = None
):
    """
    Resume a paused workflow execution.

    Args:
        execution_id: Execution to resume
        resume_data: Optional data to inject (e.g., approval response)
    """
    from open_notebook.domain.workflow import WorkflowExecution, Workflow, ExecutionStatus
    from open_notebook.domain.workflow_approval import WorkflowApproval
    from open_notebook.agents.workflow_engine import WorkflowEngine

    # Load execution
    execution = await WorkflowExecution.get(execution_id)
    if not execution:
        raise ValueError(f"Execution {execution_id} not found")

    if not execution.paused_at:
        raise ValueError(f"Execution {execution_id} is not paused")

    # Get approval response
    approval_response = resume_data.get("approval_response") if resume_data else None
    approval_id = json.loads(execution.resume_data).get("approval_id") if execution.resume_data else None

    # Update the approval record
    if approval_id:
        approval = await WorkflowApproval.get(approval_id)
        if approval:
            approval.status = "approved" if approval_response == "approve" else "rejected"
            approval.response = approval_response
            approval.comment = resume_data.get("approval_comment")
            approval.approved_by = resume_data.get("approved_by")
            approval.responded_at = datetime.utcnow()
            await approval.save()
            print(f"[WorkflowResumeService] Approval {approval_id} updated to {approval.status}")

    # Update the approval node's output
    approval_node_id = execution.current_node_id
    if approval_node_id and approval_node_id in execution.node_states:
        node_state = execution.node_states[approval_node_id]

        # If rejected, mark execution as COMPLETED (workflow stops without error)
        if approval_response == "reject":
            print(f"[WorkflowResumeService] Workflow rejected, completing without proceeding")

            node_state.output_data = {
                "status": "rejected",
                "approval_response": approval_response,
                "approval_comment": resume_data.get("approval_comment"),
                "approved_by": resume_data.get("approved_by"),
                "approved": False,
            }
            node_state.status = ExecutionStatus.COMPLETED
            node_state.completed_at = datetime.utcnow()

            # Mark execution as COMPLETED (not FAILED - rejection is a valid outcome)
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.utcnow()
            execution.final_output = {
                "status": "rejected_by_user",
                "rejected_at_node": approval_node_id,
                "rejected_by": resume_data.get("approved_by", "user"),
                "comment": resume_data.get("approval_comment")
            }
            execution.paused_at = None
            execution.paused_reason = None
            execution.resume_data = None
            await execution.save()

            print(f"[WorkflowResumeService] Execution completed with rejection")
            return

        # If approved, update node and continue execution
        print(f"[WorkflowResumeService] Workflow approved, continuing to next node")

        node_state.output_data = {
            "status": "approved",
            "approval_response": approval_response,
            "approval_comment": resume_data.get("approval_comment"),
            "approved_by": resume_data.get("approved_by"),
            "approved": True,
            "data": {
                node_id: state.output_data
                for node_id, state in execution.node_states.items()
                if node_id != approval_node_id  # Exclude the approval node itself
            }
        }
        node_state.status = ExecutionStatus.COMPLETED
        node_state.completed_at = datetime.utcnow()

    # Load workflow to get graph structure
    workflow = await Workflow.get(execution.workflow_id)

    # Find the next node after approval node
    next_nodes = [
        edge.target
        for edge in workflow.graph.edges
        if edge.source == approval_node_id
    ]

    # If no next nodes, mark as completed
    if not next_nodes:
        print(f"[WorkflowResumeService] No next nodes after approval, marking as completed")
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.utcnow()
        execution.final_output = {
            node_id: state.output_data
            for node_id, state in execution.node_states.items()
        }
        execution.paused_at = None
        execution.paused_reason = None
        execution.resume_data = None
        await execution.save()
        return

    # Continue execution from next node
    # We need to rebuild and execute remaining nodes
    print(f"[WorkflowResumeService] Continuing to next node: {next_nodes[0]}")

    # Create a new workflow engine and execute remaining nodes
    # NOTE: This is a simplified implementation - ideally we'd resume the graph mid-execution
    from open_notebook.agents.workflow_nodes import create_node_executor

    # Update execution to running
    execution.status = ExecutionStatus.RUNNING
    execution.paused_at = None
    execution.paused_reason = None
    execution.resume_data = None
    await execution.save()

    # Build state from current execution
    state = {
        "workflow_id": execution.workflow_id,
        "execution_id": execution.id,
        "current_node_id": next_nodes[0],
        "node_outputs": {
            node_id: state.output_data
            for node_id, state in execution.node_states.items()
        },
        "visited_nodes": list(execution.node_states.keys()),
        "iteration": len(execution.node_states),
        "max_iterations": 50,
        "input_data": {},
        "final_output": None,
        "paused": False,
        "approval_id": None,
        "error": None,
    }

    # Execute remaining nodes sequentially
    try:
        current_node_id = next_nodes[0]
        visited = set(execution.node_states.keys())

        while current_node_id:
            # Prevent infinite loops
            if current_node_id in visited:
                print(f"[WorkflowResumeService] Loop detected at node {current_node_id}, stopping")
                break

            visited.add(current_node_id)

            # Find node definition
            node_def = next((n for n in workflow.graph.nodes if n.id == current_node_id), None)
            if not node_def:
                print(f"[WorkflowResumeService] Node {current_node_id} not found, stopping")
                break

            print(f"[WorkflowResumeService] Executing node: {current_node_id}")

            # Create and execute node
            executor = create_node_executor(node_def.type, node_def.config)

            # Create node state
            from open_notebook.domain.workflow import NodeExecutionState
            node_state = NodeExecutionState(
                node_id=current_node_id,
                status=ExecutionStatus.RUNNING,
                started_at=datetime.utcnow(),
            )
            execution.node_states[current_node_id] = node_state
            await execution.save()

            # Execute node
            state["current_node_id"] = current_node_id
            result = await executor.execute(state)

            # Update state
            for key, value in result.items():
                state[key] = value

            # Get node's output data
            node_output = result.get("node_outputs", {}).get(current_node_id)

            # If this is an output node, use final_output instead
            if node_def.type.value == "output" and "final_output" in result:
                node_output = result["final_output"]

            # Update node state
            node_state.status = ExecutionStatus.COMPLETED
            node_state.completed_at = datetime.utcnow()
            node_state.output_data = node_output
            await execution.save()

            print(f"[WorkflowResumeService] Node {current_node_id} completed with output: {node_output}")

            # Find next node
            next_edges = [e for e in workflow.graph.edges if e.source == current_node_id]
            if not next_edges:
                print(f"[WorkflowResumeService] No more nodes, execution complete")
                break

            current_node_id = next_edges[0].target

        # Mark execution as completed
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.utcnow()
        execution.final_output = state.get("final_output") or state.get("node_outputs")
        await execution.save()

        print(f"[WorkflowResumeService] Execution resumed and completed successfully")

    except Exception as e:
        print(f"[WorkflowResumeService] Error during resume: {e}")
        import traceback
        traceback.print_exc()

        execution.status = ExecutionStatus.FAILED
        execution.completed_at = datetime.utcnow()
        execution.error = str(e)
        await execution.save()

        raise


def _rebuild_state_from_execution(execution) -> Dict[str, Any]:
    """Rebuild workflow state from execution record."""
    return {
        "workflow_id": execution.workflow_id,
        "execution_id": execution.id,
        "current_node_id": execution.current_node_id,
        "node_outputs": {
            node_id: state.output_data
            for node_id, state in execution.node_states.items()
        },
        "visited_nodes": list(execution.node_states.keys()),
    }
