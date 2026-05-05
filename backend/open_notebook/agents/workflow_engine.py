"""
Workflow Execution Engine

Executes visual workflow graphs using LangGraph.
Converts WorkflowGraph → LangGraph StateGraph → Sequential execution
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, AsyncGenerator
from uuid import uuid4

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from open_notebook.domain.workflow import (
    Workflow,
    WorkflowExecution,
    WorkflowNode,
    WorkflowEdge,
    ExecutionStatus,
    NodeExecutionState,
    NodeType,
)
from open_notebook.agents.workflow_nodes import create_node_executor


# ============================================================================
# Custom Exceptions
# ============================================================================

class WorkflowPausedException(Exception):
    """Exception raised when workflow execution is paused for human approval."""

    def __init__(self, execution_id: str, approval_id: str, message: str):
        self.execution_id = execution_id
        self.approval_id = approval_id
        self.message = message
        super().__init__(message)


# ============================================================================
# Workflow State
# ============================================================================

class WorkflowState(BaseModel):
    """State for workflow execution."""

    class Config:
        arbitrary_types_allowed = True

    # Current execution state
    current_node_id: Optional[str] = None
    prev_node_id: Optional[str] = None
    next_node_id: Optional[str] = None

    # Node outputs
    node_outputs: Dict[str, Any] = Field(default_factory=dict)

    # Input/output
    input_data: Dict[str, Any] = Field(default_factory=dict)
    final_output: Optional[Any] = None

    # Execution tracking
    visited_nodes: list[str] = Field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 50  # Safety limit

    # Workflow and execution IDs for approval tracking
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None

    # Pause tracking (for human approval nodes)
    paused: bool = False
    approval_id: Optional[str] = None

    # Error tracking
    error: Optional[str] = None


# ============================================================================
# Workflow Engine
# ============================================================================

class WorkflowEngine:
    """
    Executes workflow graphs using LangGraph.

    Converts WorkflowGraph → LangGraph StateGraph → Execute sequentially
    """

    def __init__(self, workflow: Workflow):
        """
        Initialize workflow engine.

        Args:
            workflow: Workflow definition with graph structure
        """
        self.workflow = workflow
        self.graph = None
        self._execution: Optional[WorkflowExecution] = None

    def _build_langgraph(self):
        """
        Dynamically build LangGraph from workflow definition.

        Creates:
        - Node for each WorkflowNode
        - Edges based on WorkflowEdge list
        - Conditional edges for conditional nodes
        """
        print(f"[WorkflowEngine._build_langgraph] Building graph with {len(self.workflow.graph.nodes)} nodes")

        workflow_state = StateGraph(WorkflowState)

        # Add nodes
        for node in self.workflow.graph.nodes:
            print(f"[WorkflowEngine._build_langgraph] Adding node: {node.id} (type: {node.type})")
            executor = create_node_executor(node.type, node.config)

            # Create node function
            async def node_fn(state: WorkflowState, node_id=node.id, exec=executor):
                return await self._execute_node(state, node_id, exec)

            workflow_state.add_node(node.id, node_fn)
            print(f"[WorkflowEngine._build_langgraph] Node added: {node.id}")

        # Set entry point
        workflow_state.set_entry_point(self.workflow.graph.entry_node_id)

        # Add edges
        for edge in self.workflow.graph.edges:
            # Check if source is a conditional node
            source_node = self._get_node_by_id(edge.source)

            if source_node and source_node.type == NodeType.CONDITIONAL:
                # Conditional edge - add via conditional edges
                # Will be routed in _should_continue
                continue
            else:
                # Regular edge
                workflow_state.add_edge(edge.source, edge.target)

        # Add conditional routing for conditional nodes
        conditional_nodes = [
            n for n in self.workflow.graph.nodes
            if n.type == NodeType.CONDITIONAL
        ]

        for node in conditional_nodes:
            # Get edges from this conditional node
            true_edge = self._get_edge_for_condition(node.id, True)
            false_edge = self._get_edge_for_condition(node.id, False)

            if true_edge and false_edge:
                workflow_state.add_conditional_edges(
                    node.id,
                    lambda state, nid=node.id: self._should_continue(state, nid),
                    {
                        "true": true_edge.target,
                        "false": false_edge.target,
                        "end": END,
                    }
                )

        # Add end condition for output nodes
        output_nodes = [
            n for n in self.workflow.graph.nodes
            if n.type == NodeType.OUTPUT
        ]
        for node in output_nodes:
            workflow_state.add_edge(node.id, END)

        return workflow_state.compile()

    def _get_node_by_id(self, node_id: str) -> Optional[WorkflowNode]:
        """Get node by ID."""
        for node in self.workflow.graph.nodes:
            if node.id == node_id:
                return node
        return None

    def _get_edge_for_condition(
        self,
        source_id: str,
        condition_result: bool
    ) -> Optional[WorkflowEdge]:
        """Get edge from conditional node based on result."""
        for edge in self.workflow.graph.edges:
            if edge.source == source_id:
                # Match based on condition result
                # This is simplified - in real impl, edges would have condition metadata
                if condition_result and "true" in (edge.label or "").lower():
                    return edge
                elif not condition_result and "false" in (edge.label or "").lower():
                    return edge
        return None

    def _should_continue(self, state: WorkflowState, node_id: str) -> str:
        """
        Decide next step after conditional node.

        Args:
            state: Current state
            node_id: Conditional node ID

        Returns:
            "true", "false", or "end"
        """
        # Check for errors
        if state.error:
            return "end"

        # Check max iterations
        if state.iteration >= state.max_iterations:
            return "end"

        # Get node output
        node_output = state.node_outputs.get(node_id, {})
        condition_result = node_output.get("condition_result", False)

        return "true" if condition_result else "false"

    async def _execute_node(
        self,
        state: WorkflowState,
        node_id: str,
        executor
    ) -> Dict[str, Any]:
        """
        Execute a single node.

        Args:
            state: Current workflow state
            node_id: Node being executed
            executor: Node executor instance

        Returns:
            Updated state
        """
        print(f"[WorkflowEngine._execute_node] Executing node: {node_id}")

        # Update state
        state.current_node_id = node_id
        state.visited_nodes.append(node_id)
        state.iteration += 1

        print(f"[WorkflowEngine._execute_node] Iteration: {state.iteration}, visited: {state.visited_nodes}")

        # Update execution tracking
        if self._execution:
            node_state = NodeExecutionState(
                node_id=node_id,
                status=ExecutionStatus.RUNNING,
                started_at=datetime.utcnow(),
            )
            self._execution.node_states[node_id] = node_state
            await self._execution.save()
            print(f"[WorkflowEngine._execute_node] Node state updated: {node_id} -> RUNNING")

        try:
            # Execute node
            print(f"[WorkflowEngine._execute_node] Calling executor.execute for {node_id}")
            result = await executor.execute(state.dict())
            print(f"[WorkflowEngine._execute_node] Executor completed for {node_id}, result keys: {result.keys()}")

            # Update state from result
            for key, value in result.items():
                setattr(state, key, value)

            # Update execution tracking
            if self._execution:
                node_state = self._execution.node_states[node_id]
                node_state.status = ExecutionStatus.COMPLETED
                node_state.completed_at = datetime.utcnow()
                node_state.output_data = result.get("node_outputs", {}).get(node_id)
                await self._execution.save()
                print(f"[WorkflowEngine._execute_node] Node state updated: {node_id} -> COMPLETED")

        except WorkflowPausedException as e:
            # Handle workflow pause - this is not an error
            print(f"[WorkflowEngine._execute_node] Node {node_id} paused workflow for approval")

            # Update execution tracking with paused status
            if self._execution:
                # Set current_node_id so we know where to resume from
                self._execution.current_node_id = node_id

                node_state = self._execution.node_states[node_id]
                node_state.status = ExecutionStatus.PAUSED
                node_state.completed_at = datetime.utcnow()
                node_state.output_data = {
                    "status": "awaiting_approval",
                    "approval_id": e.approval_id
                }
                await self._execution.save()
                print(f"[WorkflowEngine._execute_node] Node state updated: {node_id} -> PAUSED")

            # Re-raise to stop workflow execution
            raise

        except Exception as e:
            # Handle error
            print(f"[WorkflowEngine._execute_node] Error executing node {node_id}: {e}")
            import traceback
            traceback.print_exc()

            state.error = str(e)

            # Update execution tracking
            if self._execution:
                node_state = self._execution.node_states[node_id]
                node_state.status = ExecutionStatus.FAILED
                node_state.completed_at = datetime.utcnow()
                node_state.error = str(e)
                await self._execution.save()
                print(f"[WorkflowEngine._execute_node] Node state updated: {node_id} -> FAILED")

        # Update prev_node_id for next node
        state.prev_node_id = node_id

        print(f"[WorkflowEngine._execute_node] Node {node_id} execution complete, returning state")
        return state.dict()

    async def execute(
        self,
        input_data: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> WorkflowExecution:
        """
        Execute workflow sequentially.

        Args:
            input_data: Initial input data
            stream: If True, stream execution events

        Returns:
            WorkflowExecution with results
        """
        print(f"[WorkflowEngine] Starting execution for workflow {self.workflow.id}")
        print(f"[WorkflowEngine] Graph has {len(self.workflow.graph.nodes)} nodes and {len(self.workflow.graph.edges)} edges")

        # Create execution record
        self._execution = WorkflowExecution(
            id=str(uuid4()),
            workflow_id=self.workflow.id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.utcnow(),
            triggered_by="manual",
        )
        await self._execution.save()
        print(f"[WorkflowEngine] Created execution record: {self._execution.id}")

        # Build graph if not already built
        if not self.graph:
            print(f"[WorkflowEngine] Building LangGraph...")
            self.graph = self._build_langgraph()
            print(f"[WorkflowEngine] LangGraph built successfully")

        # Initial state
        initial_state = WorkflowState(
            current_node_id=self.workflow.graph.entry_node_id,
            input_data=input_data or {},
            workflow_id=self.workflow.id,
            execution_id=self._execution.id,
        )
        print(f"[WorkflowEngine] Entry node: {self.workflow.graph.entry_node_id}")
        print(f"[WorkflowEngine] Starting execution...")

        try:
            # Execute graph
            if stream:
                # Stream execution (not implemented yet - needs async generator)
                final_state = await self.graph.ainvoke(initial_state.dict())
            else:
                # Non-streaming execution
                print(f"[WorkflowEngine] Calling graph.ainvoke...")
                final_state = await self.graph.ainvoke(initial_state.dict())
                print(f"[WorkflowEngine] graph.ainvoke completed")
                print(f"[WorkflowEngine] Final state: {final_state}")

            # Check if execution was paused (e.g., for approval)
            if final_state.get("paused"):
                print(f"[WorkflowEngine] Execution paused for approval: {final_state.get('approval_id')}")
                # Execution is already marked as paused by pause_workflow_execution
                # Don't mark as completed - it will be resumed later
                return self._execution

            # Update execution record
            self._execution.status = ExecutionStatus.COMPLETED
            self._execution.completed_at = datetime.utcnow()
            self._execution.final_output = final_state.get("final_output")
            print(f"[WorkflowEngine] Execution completed successfully")

            # Send notification for completion
            try:
                from api.services.notification_service import notify_execution_complete
                await notify_execution_complete(
                    user_id=self.workflow.owner_id or "default-user",
                    workflow_name=self.workflow.name,
                    execution_id=self._execution.id,
                    status="completed"
                )
            except Exception as notify_err:
                print(f"[WorkflowEngine] Failed to send completion notification: {notify_err}")

        except WorkflowPausedException as e:
            # Handle workflow pause (human approval)
            print(f"[WorkflowEngine] Workflow paused: {e.message}")
            print(f"[WorkflowEngine] Approval ID: {e.approval_id}")

            # Update execution to PAUSED status
            self._execution.status = ExecutionStatus.PAUSED
            self._execution.paused_at = datetime.utcnow()
            self._execution.paused_reason = "awaiting_approval"
            self._execution.resume_data = json.dumps({"approval_id": e.approval_id})
            await self._execution.save()
            print(f"[WorkflowEngine] Execution status saved as PAUSED")

            return self._execution

        except Exception as e:
            # Handle execution failure
            print(f"[WorkflowEngine] Execution failed: {e}")
            import traceback
            traceback.print_exc()

            self._execution.status = ExecutionStatus.FAILED
            self._execution.completed_at = datetime.utcnow()
            self._execution.error = str(e)

            # Send notification for failure
            try:
                from api.services.notification_service import notify_execution_complete
                await notify_execution_complete(
                    user_id=self.workflow.owner_id or "default-user",
                    workflow_name=self.workflow.name,
                    execution_id=self._execution.id,
                    status="failed"
                )
            except Exception as notify_err:
                print(f"[WorkflowEngine] Failed to send failure notification: {notify_err}")

        await self._execution.save()
        print(f"[WorkflowEngine] Execution saved: {self._execution.status.value}")
        return self._execution

    async def execute_streaming(
        self,
        input_data: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute workflow with streaming updates.

        Yields:
            Event dictionaries: {type, node_id, data, timestamp}
        """
        # Create execution record
        self._execution = WorkflowExecution(
            id=str(uuid4()),
            workflow_id=self.workflow.id,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.utcnow(),
            triggered_by="manual",
        )
        await self._execution.save()

        # Yield start event
        yield {
            "type": "workflow_started",
            "workflow_id": self.workflow.id,
            "execution_id": self._execution.id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Build graph if not already built
        if not self.graph:
            self.graph = self._build_langgraph()

        # Initial state
        initial_state = WorkflowState(
            current_node_id=self.workflow.graph.entry_node_id,
            input_data=input_data or {},
            workflow_id=self.workflow.id,
            execution_id=self._execution.id,
        )

        try:
            # Execute with streaming
            async for event in self.graph.astream(initial_state.dict()):
                # Extract node execution info
                node_id = event.get("current_node_id")

                if node_id:
                    # Yield node execution event
                    yield {
                        "type": "node_executed",
                        "node_id": node_id,
                        "output": event.get("node_outputs", {}).get(node_id),
                        "timestamp": datetime.utcnow().isoformat(),
                    }

            # Update execution record
            self._execution.status = ExecutionStatus.COMPLETED
            self._execution.completed_at = datetime.utcnow()
            await self._execution.save()

            # Yield complete event
            yield {
                "type": "workflow_completed",
                "execution_id": self._execution.id,
                "final_output": self._execution.final_output,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            # Handle execution failure
            self._execution.status = ExecutionStatus.FAILED
            self._execution.completed_at = datetime.utcnow()
            self._execution.error = str(e)
            await self._execution.save()

            # Yield error event
            yield {
                "type": "workflow_error",
                "execution_id": self._execution.id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
