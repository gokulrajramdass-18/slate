"""
Workflow Execution Engine

Executes visual workflow graphs using LangGraph.
Converts WorkflowGraph → LangGraph StateGraph → Sequential execution
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, AsyncGenerator, Annotated
from uuid import uuid4

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field


def _last_write_wins(_old, new):
    """LangGraph reducer: take the latest write when parallel branches update the same key."""
    return new


def _max_int(old, new):
    """LangGraph reducer: take the largest integer when parallel branches update the same key."""
    if old is None:
        return new
    if new is None:
        return old
    return max(old, new)


def _merge_dicts(old, new):
    """LangGraph reducer: shallow-merge dicts when parallel branches each contribute keys."""
    if not old:
        return new or {}
    if not new:
        return old
    merged = dict(old)
    merged.update(new)
    return merged


def _append_unique(old, new):
    """LangGraph reducer: append new items to a list, skipping duplicates."""
    old_list = list(old or [])
    if new is None:
        return old_list
    if isinstance(new, list):
        for item in new:
            if item not in old_list:
                old_list.append(item)
    else:
        if new not in old_list:
            old_list.append(new)
    return old_list

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

    # Current execution state (parallel-safe via reducers — concurrent branches
    # may all write these, so LangGraph would otherwise raise INVALID_CONCURRENT_GRAPH_UPDATE)
    current_node_id: Annotated[Optional[str], _last_write_wins] = None
    prev_node_id: Annotated[Optional[str], _last_write_wins] = None
    next_node_id: Annotated[Optional[str], _last_write_wins] = None

    # Node outputs — parallel branches each write their own node's key, so merge
    node_outputs: Annotated[Dict[str, Any], _merge_dicts] = Field(default_factory=dict)

    # Input/output
    input_data: Dict[str, Any] = Field(default_factory=dict)
    final_output: Annotated[Optional[Any], _last_write_wins] = None

    # Execution tracking — visited list grows, iteration counts up
    visited_nodes: Annotated[list[str], _append_unique] = Field(default_factory=list)
    iteration: Annotated[int, _max_int] = 0
    max_iterations: int = 50  # Safety limit

    # Workflow and execution IDs for approval tracking
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    user_email: Optional[str] = None

    # Pause tracking (for human approval nodes)
    paused: Annotated[bool, _last_write_wins] = False
    approval_id: Annotated[Optional[str], _last_write_wins] = None

    # Error tracking
    error: Annotated[Optional[str], _last_write_wins] = None


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

        # Pre-compute ForEach mapping. The ForEach node has two source handles:
        #   - "each": fires once per item (consumed inline by ForEachNodeExecutor)
        #   - "done": fires once after all items are processed (the LangGraph successor)
        # We skip every node reachable from the `each` handle at compile time so
        # LangGraph never tries to run them as normal successors. They're invoked
        # in-process by the ForEach executor instead.
        each_chain_ids: set[str] = set()              # nodes reachable only via the each-chain
        foreach_done_target: Dict[str, Optional[str]] = {}  # foreach_id -> node connected via "done" handle (or None for END)
        for fnode in self.workflow.graph.nodes:
            if fnode.type == NodeType.FOREACH:
                # Walk the each-chain
                each_start = None
                for e in self.workflow.graph.edges:
                    if e.source == fnode.id and e.sourceHandle == "each":
                        each_start = e.target
                        break
                    if e.source == fnode.id and e.sourceHandle is None and each_start is None:
                        # Backwards compat: if no handle specified, treat as each
                        each_start = e.target
                if each_start:
                    cursor = each_start
                    seen: set = set()
                    while cursor and cursor not in seen and cursor != fnode.id:
                        seen.add(cursor)
                        each_chain_ids.add(cursor)
                        next_id = None
                        for e in self.workflow.graph.edges:
                            if e.source == cursor:
                                next_id = e.target
                                break
                        cursor = next_id
                    print(f"[WorkflowEngine._build_langgraph] ForEach {fnode.id} each-chain: {seen}")

                # Find the done target
                done_target = None
                for e in self.workflow.graph.edges:
                    if e.source == fnode.id and e.sourceHandle == "done":
                        done_target = e.target
                        break
                foreach_done_target[fnode.id] = done_target
                print(f"[WorkflowEngine._build_langgraph] ForEach {fnode.id} done target: {done_target}")

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

        # Group regular edges by source so a single node with multiple
        # outgoing edges (parallel fan-out) gets one combined router.
        regular_edges_by_source: Dict[str, list] = {}
        for edge in self.workflow.graph.edges:
            source_node = self._get_node_by_id(edge.source)

            if source_node and source_node.type == NodeType.CONDITIONAL:
                continue
            if source_node and source_node.type == NodeType.FOREACH and edge.sourceHandle == "each":
                print(f"[WorkflowEngine._build_langgraph] Skipping ForEach->each edge {edge.source}->{edge.target} (each-chain runs inline)")
                continue
            if source_node and source_node.type == NodeType.FOREACH and edge.sourceHandle == "done":
                continue
            if source_node and source_node.type == NodeType.FOREACH and edge.sourceHandle is None and edge.target in each_chain_ids:
                print(f"[WorkflowEngine._build_langgraph] Skipping ForEach->each (legacy unhandled) edge {edge.source}->{edge.target}")
                continue
            if edge.source in each_chain_ids:
                print(f"[WorkflowEngine._build_langgraph] Skipping each-chain internal edge {edge.source}->{edge.target}")
                continue

            regular_edges_by_source.setdefault(edge.source, []).append(edge.target)

        # Each grouped source becomes a guarded conditional router so that a
        # failed node short-circuits to END instead of feeding the next node.
        for source_id, targets in regular_edges_by_source.items():
            unique_targets = list(dict.fromkeys(targets))  # preserve order, dedupe

            def _route(state, _tgts=unique_targets):
                if getattr(state, "error", None):
                    return END
                # Single target -> string; multiple targets -> list (parallel)
                return _tgts[0] if len(_tgts) == 1 else _tgts

            mapping = {t: t for t in unique_targets}
            mapping[END] = END
            workflow_state.add_conditional_edges(source_id, _route, mapping)

        # Add ForEach -> done-target successor edges (guarded the same way)
        for foreach_id, done_target in foreach_done_target.items():
            if done_target:
                workflow_state.add_conditional_edges(
                    foreach_id,
                    lambda state, tgt=done_target: END if getattr(state, "error", None) else tgt,
                    {done_target: done_target, END: END},
                )
                print(f"[WorkflowEngine._build_langgraph] Added ForEach->done edge {foreach_id}->{done_target}")
            else:
                workflow_state.add_edge(foreach_id, END)
                print(f"[WorkflowEngine._build_langgraph] Added ForEach->END edge for {foreach_id} (no done handle wired)")

        # Each-chain nodes still need a terminal edge so LangGraph can compile
        for chain_id in each_chain_ids:
            workflow_state.add_edge(chain_id, END)
            print(f"[WorkflowEngine._build_langgraph] Added each-chain->END edge for {chain_id} (unreachable normally; defensive)")

        # Add conditional routing for conditional nodes
        conditional_nodes = [
            n for n in self.workflow.graph.nodes
            if n.type == NodeType.CONDITIONAL
        ]

        for node in conditional_nodes:
            # Get edges from this conditional node
            true_edge = self._get_edge_for_condition(node.id, True)
            false_edge = self._get_edge_for_condition(node.id, False)

            print(f"[WorkflowEngine] Setting up conditional edges for {node.id}")
            print(f"[WorkflowEngine]   True edge: {true_edge.target if true_edge else 'None'}")
            print(f"[WorkflowEngine]   False edge: {false_edge.target if false_edge else 'None'}")

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
            elif true_edge:
                # Only true edge exists
                workflow_state.add_conditional_edges(
                    node.id,
                    lambda state, tgt=true_edge.target: END if getattr(state, "error", None) else tgt,
                    {true_edge.target: true_edge.target, END: END},
                )
                print(f"[WorkflowEngine]   Added single edge (true only)")
            elif false_edge:
                # Only false edge exists
                workflow_state.add_conditional_edges(
                    node.id,
                    lambda state, tgt=false_edge.target: END if getattr(state, "error", None) else tgt,
                    {false_edge.target: false_edge.target, END: END},
                )
                print(f"[WorkflowEngine]   Added single edge (false only)")

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
                # Check both label and edge ID for "true" or "false"
                edge_text = f"{edge.label or ''} {edge.id}".lower()

                if condition_result and "true" in edge_text:
                    return edge
                elif not condition_result and "false" in edge_text:
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
            # Make execution tracker available to executors (e.g. ForEach uses it
            # to record aggregated node_states for inline chain nodes).
            executor._execution = self._execution
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
        stream: bool = False,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        user_email: Optional[str] = None,
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
            user_id=user_id or self.workflow.created_by,
            username=username,
            user_email=user_email,
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
                    user_id=self.workflow.created_by or "default-user",
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
                    user_id=self.workflow.created_by or "default-user",
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
        input_data: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        user_email: Optional[str] = None,
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
            user_id=user_id or self.workflow.created_by,
            username=username,
            user_email=user_email,
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
