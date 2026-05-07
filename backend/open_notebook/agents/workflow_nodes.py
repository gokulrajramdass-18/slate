"""
Workflow Node Executors

Implements execution logic for different node types:
- LLM nodes: Call AI models
- Tool nodes: Execute tools (HANA queries, web search, etc.)
- Conditional nodes: Evaluate conditions and route execution
- Input/Output nodes: Handle data flow
"""

import json
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from uuid import uuid4
from datetime import datetime, date, timedelta

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from open_notebook.domain.workflow import NodeConfig, NodeType
from open_notebook.agents.messaging import MessageBus
from open_notebook.agents.task_manager import TaskManager
from open_notebook.agents.agent_manager import get_agent_class


# ============================================================================
# Base Node Executor
# ============================================================================

class BaseNodeExecutor(ABC):
    """Base class for node executors."""

    def __init__(self, config: NodeConfig):
        """
        Initialize node executor.

        Args:
            config: Node configuration
        """
        self.config = config

    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the node logic.

        Args:
            state: Current workflow state

        Returns:
            Updated state dictionary
        """
        pass

    def _substitute_variables(
        self,
        template: str,
        input_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        Substitute {{variable}} placeholders with actual values.
        Supports dot notation for nested access (e.g., {{summary.modified}})

        Args:
            template: Template string with {{var}} placeholders
            input_data: Input data from input node
            context: Previous node outputs

        Returns:
            Substituted string
        """
        import re

        result = template

        # Find all {{variable}} patterns
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, template)

        for var_name in matches:
            var_name = var_name.strip()
            value = None

            # Handle dot notation (e.g., summary.modified or approval-node.compare-node.field)
            if '.' in var_name:
                parts = var_name.split('.')

                # Try direct lookup: first check if first part is a top-level key
                if parts[0] in context:
                    current = context[parts[0]]
                    found = True
                    # Navigate remaining path
                    for part in parts[1:]:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            found = False
                            break
                    if found:
                        value = current
                else:
                    # Search in all node outputs for the full path
                    for node_output in context.values():
                        if isinstance(node_output, dict):
                            # Try to navigate the path
                            current = node_output
                            found = True
                            for part in parts:
                                if isinstance(current, dict) and part in current:
                                    current = current[part]
                                else:
                                    found = False
                                    break
                            if found:
                                value = current
                                break
            else:
                # Try to find value in input_data first
                if var_name in input_data:
                    value = input_data[var_name]
                # Then try context (node_outputs)
                elif var_name in context:
                    value = context[var_name]
                else:
                    # Try to extract from nested node outputs
                    for node_output in context.values():
                        if isinstance(node_output, dict) and var_name in node_output:
                            value = node_output[var_name]
                            break

            if value is None:
                # Keep placeholder if not found
                print(f"[BaseNodeExecutor] Warning: Variable {{{{{var_name}}}}} not found in input_data or context")
                continue

            # Format value based on type
            if isinstance(value, (dict, list)):
                # Pretty print JSON for complex types
                import json
                formatted_value = json.dumps(value, indent=2)
            else:
                formatted_value = str(value)

            # Replace placeholder with value
            result = result.replace(f"{{{{{var_name}}}}}", formatted_value)

        return result


# ============================================================================
# Input Node Executor
# ============================================================================

class InputNodeExecutor(BaseNodeExecutor):
    """Execute input node - receives workflow input data."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Store input data in state."""
        input_data = state.get("input_data", {})

        # Extract input fields from config
        input_fields = self.config.input_fields or {}

        # Store in node_outputs
        return {
            **state,
            "node_outputs": {
                **state.get("node_outputs", {}),
                state["current_node_id"]: input_data
            }
        }


# ============================================================================
# Output Node Executor
# ============================================================================

class OutputNodeExecutor(BaseNodeExecutor):
    """Execute output node - returns workflow output."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract output from previous nodes."""
        node_outputs = state.get("node_outputs", {})

        # Collect all outputs for final result
        final_output = {
            "workflow_outputs": node_outputs,
            "summary": {
                "total_nodes_executed": len(node_outputs),
                "node_ids": list(node_outputs.keys())
            }
        }

        return {
            **state,
            "final_output": final_output,  # Set final_output for workflow result
            "node_outputs": {
                **node_outputs,
                state["current_node_id"]: {
                    "status": "output_collected",
                    "outputs": node_outputs
                }
            }
        }


# ============================================================================
# LLM Node Executor
# ============================================================================

class LLMNodeExecutor(BaseNodeExecutor):
    """Execute LLM node - call AI model."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Call LLM with prompt."""
        from api.services.settings import get_setting
        from api.routers.credentials import _credentials_store
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        # Get input data
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})

        # Debug: print available node outputs
        print(f"[LLMNodeExecutor] Available node_outputs keys: {list(node_outputs.keys())}")
        if 'approval-1778160383927' in node_outputs:
            print(f"[LLMNodeExecutor] Approval node output keys: {list(node_outputs['approval-1778160383927'].keys())}")

        # Build prompt
        system_prompt = self.config.system_prompt or "You are a helpful assistant."
        user_prompt = self.config.prompt or ""

        # Substitute variables in prompts
        system_prompt = self._substitute_variables(system_prompt, input_data, node_outputs)
        user_prompt = self._substitute_variables(user_prompt, input_data, node_outputs)

        # If user prompt is still empty after substitution, use a default
        if not user_prompt or not user_prompt.strip():
            # Try to use input data or a generic prompt
            if input_data:
                user_prompt = f"Process this data:\n{json.dumps(input_data, indent=2)}"
            else:
                user_prompt = "Please generate output based on the system instructions."

        print(f"[LLMNodeExecutor] System prompt: {system_prompt[:100]}...")
        print(f"[LLMNodeExecutor] User prompt: {user_prompt[:100]}...")

        # Get language model from settings
        language_model_id = await get_setting("language_model_id", "gpt-4o-mini")

        # Resolve model name and API key from credential if it's a UUID
        model_name = self.config.model_name or language_model_id
        api_key = None
        api_base = None

        # Check if language_model_id is a credential ID (UUID format)
        if language_model_id and len(language_model_id) == 36 and language_model_id.count('-') == 4:
            credential = _credentials_store.get(language_model_id)
            if credential:
                # If node doesn't have model_name configured, use credential's model
                if not self.config.model_name:
                    model_name = credential.get("model_name", language_model_id)
                api_key = credential.get("api_key")
                api_base = credential.get("base_url")
            else:
                # Fallback to default
                if not self.config.model_name:
                    model_name = "gpt-4o-mini"
        elif not model_name:
            model_name = "gpt-4o-mini"

        # Create LLM with LiteLLM proxy support
        llm = ChatOpenAI(
            model=model_name,
            openai_api_base=api_base if api_base else "http://localhost:6655/litellm/v1",
            openai_api_key=api_key if api_key else "dummy-key-for-proxy",
            temperature=self.config.temperature or 0.7,
            max_tokens=self.config.max_tokens or 4096,
        )

        # Build messages
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        # Call LLM
        try:
            response = await llm.ainvoke(messages)
            result = response.content

            return {
                **state,
                "node_outputs": {
                    **node_outputs,
                    state["current_node_id"]: {
                        "text": result,
                        "model": self.config.model_name
                    }
                }
            }
        except Exception as e:
            print(f"[LLMNodeExecutor] Error: {e}")
            return {
                **state,
                "node_outputs": {
                    **node_outputs,
                    state["current_node_id"]: {
                        "error": str(e)
                    }
                }
            }


# ============================================================================
# Tool Node Executor
# ============================================================================

class ToolNodeExecutor(BaseNodeExecutor):
    """Execute tool node - call a tool/function."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool."""
        # For now, this is a placeholder
        # Implement specific tool execution logic later

        tool_name = self.config.tool_name
        tool_args = self.config.tool_args or {}

        # Substitute variables in tool args
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})

        resolved_args = {}
        for key, value in tool_args.items():
            if isinstance(value, str):
                resolved_args[key] = self._substitute_variables(value, input_data, node_outputs)
            else:
                resolved_args[key] = value

        return {
            **state,
            "node_outputs": {
                **state.get("node_outputs", {}),
                state["current_node_id"]: {
                    "tool_name": tool_name,
                    "tool_args": resolved_args,
                    "result": "Tool execution placeholder"
                }
            }
        }


# ============================================================================
# Conditional Node Executor
# ============================================================================

class ConditionalNodeExecutor(BaseNodeExecutor):
    """Execute conditional node - evaluate condition and route."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate condition."""
        # Get condition configuration
        condition_type = self.config.condition_type  # e.g., "equals", "contains", "greater_than"
        field_path = self.config.field_path  # e.g., "node_id.field_name"
        comparison_value = self.config.comparison_value

        # Extract value from state
        node_outputs = state.get("node_outputs", {})

        # Parse field path (e.g., "previous-node.status")
        if "." in field_path:
            node_id, field_name = field_path.split(".", 1)
            if node_id in node_outputs:
                value = node_outputs[node_id].get(field_name)
            else:
                value = None
        else:
            # Direct field from input_data
            value = state.get("input_data", {}).get(field_path)

        # Evaluate condition
        result = self._evaluate_condition(condition_type, value, comparison_value)

        # Store result
        return {
            **state,
            "node_outputs": {
                **node_outputs,
                state["current_node_id"]: {
                    "condition_result": result,
                    "evaluated_value": value,
                    "comparison_value": comparison_value
                }
            }
        }

    def _evaluate_condition(self, condition_type: str, value: Any, comparison_value: Any) -> bool:
        """Evaluate condition based on type."""
        if condition_type == "equals":
            return value == comparison_value
        elif condition_type == "not_equals":
            return value != comparison_value
        elif condition_type == "contains":
            return comparison_value in str(value)
        elif condition_type == "greater_than":
            return float(value) > float(comparison_value)
        elif condition_type == "less_than":
            return float(value) < float(comparison_value)
        else:
            # Default to False for unknown conditions
            return False


# ============================================================================
# Agent Node Executor
# ============================================================================

class AgentNodeExecutor(BaseNodeExecutor):
    """Execute agent node - invoke intelligent agent."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke agent."""
        # Get agent configuration
        agent_type = self.config.agent_type
        agent_name = self.config.agent_name
        prompt = self.config.prompt or ""

        # Substitute variables in prompt
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})
        prompt = self._substitute_variables(prompt, input_data, node_outputs)

        # Get agent class
        agent_class = get_agent_class(agent_type)
        if not agent_class:
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": f"Unknown agent type: {agent_type}"
                    }
                }
            }

        # Create agent instance
        try:
            agent = agent_class(
                name=agent_name or agent_type,
                user_id=state.get("user_id", "system")
            )

            # Execute agent
            result = await agent.execute(prompt)

            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "agent_type": agent_type,
                        "result": result
                    }
                }
            }
        except Exception as e:
            print(f"[AgentNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": str(e)
                    }
                }
            }


# ============================================================================
# Notebook Generator Node Executor
# ============================================================================

class NotebookGeneratorNodeExecutor(BaseNodeExecutor):
    """Execute notebook generator node - create workspace from sources."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate notebook/workspace."""
        from open_notebook.domain.notebook import Notebook
        from open_notebook.domain.source import Source

        # Get configuration
        notebook_name = self.config.notebook_name
        notebook_description = self.config.notebook_description
        folder_id = self.config.folder_id
        tags = self.config.tags or []

        # Substitute variables
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})

        if notebook_name:
            notebook_name = self._substitute_variables(notebook_name, input_data, node_outputs)
        if notebook_description:
            notebook_description = self._substitute_variables(notebook_description, input_data, node_outputs)

        # Get user
        user_id = state.get("user_id", "system")

        # Create notebook
        try:
            notebook = Notebook(
                id=str(uuid4()),
                name=notebook_name or "Generated Notebook",
                description=notebook_description,
                created_by=user_id,
                folder_id=folder_id,
                tags=tags
            )
            await notebook.save()

            # Handle source mode
            source_mode = self.config.source_mode  # "extract" | "existing"

            if source_mode == "extract":
                # Extract content from previous node output
                content_source_node_id = self.config.content_source_node_id
                if content_source_node_id and content_source_node_id in node_outputs:
                    content = node_outputs[content_source_node_id]

                    # Extract based on mode
                    extraction_mode = self.config.content_extraction_mode  # "full" | "field"
                    if extraction_mode == "field":
                        field_path = self.config.content_extraction_path
                        if field_path and isinstance(content, dict):
                            content = content.get(field_path, content)

                    # Create source from extracted content
                    source_title = self.config.source_title_template or "Extracted Content"
                    source_title = self._substitute_variables(source_title, input_data, node_outputs)

                    source = Source(
                        id=str(uuid4()),
                        notebook_id=notebook.id,
                        type=self.config.source_type or "text",
                        url=None,
                        title=source_title,
                        content=json.dumps(content) if not isinstance(content, str) else content,
                        created_by=user_id
                    )
                    await source.save()

            elif source_mode == "existing":
                # Link existing sources to notebook
                existing_source_ids = self.config.existing_source_ids or []
                for source_id in existing_source_ids:
                    source = await Source.get(source_id)
                    if source:
                        source.notebook_id = notebook.id
                        await source.save()

            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "notebook_id": notebook.id,
                        "notebook_name": notebook.name,
                        "status": "created"
                    }
                }
            }

        except Exception as e:
            print(f"[NotebookGeneratorNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": str(e)
                    }
                }
            }


# ============================================================================
# Microsite Generator Node Executor
# ============================================================================

class MicrositeGeneratorNodeExecutor(BaseNodeExecutor):
    """Execute microsite generator node - generate static website."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate microsite."""
        from api.services.microsite_generation_service import MicrositeGenerationService
        from open_notebook.database.connection import get_db

        # Get configuration
        title = self.config.microsite_title
        description = self.config.microsite_description
        notebook_id_template = self.config.notebook_id_template
        template_id = self.config.template_id

        # Substitute variables
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})

        if title:
            title = self._substitute_variables(title, input_data, node_outputs)
        if description:
            description = self._substitute_variables(description, input_data, node_outputs)
        if notebook_id_template:
            notebook_id_template = self._substitute_variables(notebook_id_template, input_data, node_outputs)

        # Get source IDs
        source_mode = self.config.microsite_source_mode  # "from_notebook" | "specific_sources"

        if source_mode == "from_notebook":
            # Get sources from notebook
            notebook_id = notebook_id_template
            if notebook_id:
                from open_notebook.domain.source import Source
                sources = await Source.get_all(
                    filters={"notebook_id": notebook_id}
                )
                source_ids = [s.id for s in sources]
            else:
                source_ids = []
        else:
            # Use specific source IDs
            source_ids = self.config.microsite_source_ids or []

        # Generate microsite
        try:
            async with get_db() as db:
                service = MicrositeGenerationService(db)

                microsite_id = str(uuid4())

                result = await service.generate_microsite(
                    microsite_id=microsite_id,
                    template_id=template_id,
                    source_ids=source_ids,
                    notebook_id=notebook_id_template,
                    user_prompt=f"Generate a microsite about {title}",
                    auto_publish=self.config.auto_publish or False
                )

                return {
                    **state,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        state["current_node_id"]: {
                            "microsite_id": microsite_id,
                            "title": title,
                            "preview_url": f"/microsites/{microsite_id}/preview",
                            "status": "generated"
                        }
                    }
                }

        except Exception as e:
            print(f"[MicrositeGeneratorNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": str(e)
                    }
                }
            }


# ============================================================================
# Presentation Generator Node Executor
# ============================================================================

class PresentationGeneratorNodeExecutor(BaseNodeExecutor):
    """Execute presentation generator node - generate PowerPoint."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate presentation."""
        from api.services.presentation_generation_service import PresentationGenerationService
        from open_notebook.database.connection import get_db

        # Get configuration
        template_id = self.config.template_id
        source_ids = self.config.source_ids or []
        notebook_id = self.config.notebook_id
        user_prompt = self.config.user_prompt
        target_slide_count = self.config.target_slide_count or 10

        # Substitute variables
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})

        if user_prompt:
            user_prompt = self._substitute_variables(user_prompt, input_data, node_outputs)
        if notebook_id:
            notebook_id = self._substitute_variables(notebook_id, input_data, node_outputs)

        # Generate presentation
        try:
            async with get_db() as db:
                service = PresentationGenerationService(db)

                presentation_id = str(uuid4())

                result = await service.generate_presentation(
                    presentation_id=presentation_id,
                    template_id=template_id,
                    source_ids=source_ids,
                    notebook_id=notebook_id,
                    user_prompt=user_prompt,
                    target_slide_count=target_slide_count
                )

                return {
                    **state,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        state["current_node_id"]: {
                            "presentation_id": presentation_id,
                            "slide_count": result.get("slide_count", 0),
                            "download_url": f"/api/presentations/{presentation_id}/download",
                            "status": "generated"
                        }
                    }
                }

        except Exception as e:
            print(f"[PresentationGeneratorNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": str(e)
                    }
                }
            }


# ============================================================================
# Human Approval Node Executor
# ============================================================================

class HumanApprovalNodeExecutor(BaseNodeExecutor):
    """Execute human approval node - pause workflow for approval."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create approval request and wait."""
        from open_notebook.domain.workflow_approval import WorkflowApproval

        # Get configuration
        approval_type = self.config.approval_type or "manual"
        approval_prompt = self.config.approval_prompt or "Please review and approve"
        approval_options = self.config.approval_options or ["approve", "reject"]
        timeout_seconds = self.config.timeout_seconds
        timeout_action = self.config.timeout_action or "fail"  # "fail" | "approve" | "reject"

        # Substitute variables
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})
        approval_prompt = self._substitute_variables(approval_prompt, input_data, node_outputs)

        # Get execution info
        workflow_id = state.get("workflow_id")
        execution_id = state.get("execution_id")
        user_id = state.get("user_id", "system")

        # Create approval request
        from open_notebook.agents.workflow_engine import WorkflowPausedException

        try:
            approval = WorkflowApproval(
                id=str(uuid4()),
                workflow_id=workflow_id,
                execution_id=execution_id,
                node_id=state["current_node_id"],
                approval_prompt=approval_prompt,
                approval_options=json.dumps(approval_options),  # Must be JSON string
                status="pending",
                timeout_seconds=timeout_seconds,
                timeout_action=timeout_action
            )
            await approval.save()

            # Raise exception to pause workflow
            raise WorkflowPausedException(
                execution_id=execution_id,
                approval_id=approval.id,
                message=f"Workflow paused for approval: {approval_prompt}"
            )

        except WorkflowPausedException:
            # Re-raise WorkflowPausedException to let workflow engine handle it
            raise
        except Exception as e:
            print(f"[HumanApprovalNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": str(e)
                    }
                }
            }


# ============================================================================
# Workspace Node Executor
# ============================================================================

class WorkspaceNodeExecutor(BaseNodeExecutor):
    """Execute workspace node - create workspace from template."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create workspace from template."""
        from open_notebook.domain.notebook import Notebook

        # Get configuration
        workspace_template_id = self.config.workspace_template_id
        workspace_parameters = self.config.workspace_parameters or {}

        # Substitute variables in parameters
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})

        resolved_parameters = {}
        for key, value in workspace_parameters.items():
            if isinstance(value, str):
                resolved_parameters[key] = self._substitute_variables(value, input_data, node_outputs)
            else:
                resolved_parameters[key] = value

        # Create workspace
        try:
            user_id = state.get("user_id", "system")

            # For now, create a simple notebook
            # In the future, this should use workspace templates
            notebook = Notebook(
                id=str(uuid4()),
                name=resolved_parameters.get("name", "Generated Workspace"),
                description=resolved_parameters.get("description"),
                created_by=user_id
            )
            await notebook.save()

            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "workspace_id": notebook.id,
                        "workspace_name": notebook.name,
                        "status": "created"
                    }
                }
            }

        except Exception as e:
            print(f"[WorkspaceNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": str(e)
                    }
                }
            }


# ============================================================================
# Template Node Executor
# ============================================================================

class TemplateNodeExecutor(BaseNodeExecutor):
    """Execute template node - instantiate workflow template."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Instantiate workflow template."""
        # Get configuration
        template_id = self.config.template_id
        template_parameters = self.config.template_parameters or {}
        wait_for_completion = self.config.wait_for_completion or False

        # Substitute variables in parameters
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})

        resolved_parameters = {}
        for key, value in template_parameters.items():
            if isinstance(value, str):
                resolved_parameters[key] = self._substitute_variables(value, input_data, node_outputs)
            else:
                resolved_parameters[key] = value

        # Instantiate template
        try:
            from open_notebook.domain.workflow_template import WorkflowTemplate
            from open_notebook.domain.workflow import Workflow

            # Load template
            template = await WorkflowTemplate.get(template_id)
            if not template:
                raise ValueError(f"Template not found: {template_id}")

            # Create workflow from template
            workflow = await template.instantiate(
                parameters=resolved_parameters,
                user_id=state.get("user_id", "system")
            )

            # Execute workflow if wait_for_completion is True
            if wait_for_completion:
                from open_notebook.agents.workflow_engine import WorkflowEngine

                engine = WorkflowEngine(workflow)
                execution_result = await engine.execute(input_data)

                return {
                    **state,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        state["current_node_id"]: {
                            "workflow_id": workflow.id,
                            "execution_result": execution_result,
                            "status": "completed"
                        }
                    }
                }
            else:
                # Just create the workflow, don't execute
                return {
                    **state,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        state["current_node_id"]: {
                            "workflow_id": workflow.id,
                            "status": "instantiated"
                        }
                    }
                }

        except Exception as e:
            print(f"[TemplateNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": str(e)
                    }
                }
            }


# ============================================================================
# Delay Node Executor
# ============================================================================

class DelayNodeExecutor(BaseNodeExecutor):
    """Execute delay node - wait for specified duration."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for specified duration."""
        import asyncio

        # Get delay configuration
        delay_seconds = self.config.delay_seconds
        delay_expression = self.config.delay_expression

        # If expression is provided, evaluate it
        if delay_expression:
            # Substitute variables
            input_data = state.get("input_data", {})
            node_outputs = state.get("node_outputs", {})
            delay_expression = self._substitute_variables(delay_expression, input_data, node_outputs)

            # Parse expression (e.g., "5m", "1h", "30s")
            delay_seconds = self._parse_duration(delay_expression)

        # Wait
        if delay_seconds and delay_seconds > 0:
            print(f"[DelayNodeExecutor] Waiting for {delay_seconds} seconds")
            await asyncio.sleep(delay_seconds)

        return {
            **state,
            "node_outputs": {
                **state.get("node_outputs", {}),
                state["current_node_id"]: {
                    "delay_seconds": delay_seconds,
                    "status": "delay_completed"
                }
            }
        }

    def _parse_duration(self, expression: str) -> int:
        """Parse duration expression (e.g., '5m', '1h', '30s') into seconds."""
        import re

        # Parse pattern: number + unit
        match = re.match(r"(\d+)([smhd])", expression.strip().lower())
        if not match:
            return 0

        value = int(match.group(1))
        unit = match.group(2)

        if unit == "s":
            return value
        elif unit == "m":
            return value * 60
        elif unit == "h":
            return value * 3600
        elif unit == "d":
            return value * 86400
        else:
            return 0


# ============================================================================
# Webhook Node Executor
# ============================================================================

class WebhookNodeExecutor(BaseNodeExecutor):
    """Execute webhook node - send HTTP request."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Send webhook request."""
        import httpx

        # Get webhook configuration
        webhook_url = self.config.webhook_url
        webhook_method = self.config.webhook_method or "POST"
        webhook_headers = self.config.webhook_headers or {}
        webhook_body_template = self.config.webhook_body_template or ""
        webhook_auth_type = self.config.webhook_auth_type  # "none", "bearer", "basic"
        webhook_auth_token = self.config.webhook_auth_token

        # Substitute variables
        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})

        webhook_url = self._substitute_variables(webhook_url, input_data, node_outputs)
        webhook_body = self._substitute_variables(webhook_body_template, input_data, node_outputs)

        # Build headers
        headers = {**webhook_headers}
        if webhook_auth_type == "bearer" and webhook_auth_token:
            headers["Authorization"] = f"Bearer {webhook_auth_token}"
        elif webhook_auth_type == "basic" and webhook_auth_token:
            headers["Authorization"] = f"Basic {webhook_auth_token}"

        # Send request
        try:
            async with httpx.AsyncClient() as client:
                if webhook_method.upper() == "POST":
                    response = await client.post(webhook_url, content=webhook_body, headers=headers)
                elif webhook_method.upper() == "PUT":
                    response = await client.put(webhook_url, content=webhook_body, headers=headers)
                elif webhook_method.upper() == "GET":
                    response = await client.get(webhook_url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {webhook_method}")

                response.raise_for_status()

                return {
                    **state,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        state["current_node_id"]: {
                            "status_code": response.status_code,
                            "response_body": response.text,
                            "status": "webhook_sent"
                        }
                    }
                }

        except Exception as e:
            print(f"[WebhookNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": str(e)
                    }
                }
            }


# ============================================================================
# Snapshot Node Executor
# ============================================================================

class SnapshotNodeExecutor(BaseNodeExecutor):
    """
    Execute snapshot node - store workflow data snapshots.

    Features:
    - Context-aware (user + query params)
    - Tiered storage (inline/file/chunked)
    - Auto-cleanup via retention
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute snapshot storage"""
        from open_notebook.domain.workflow_snapshot import SnapshotContext, WorkflowSnapshot
        from datetime import date

        print(f"[SnapshotNode] Executing snapshot node")

        # Extract context from workflow state
        context = SnapshotContext.from_workflow_state(state)

        # Capture source node query params if available
        source_node_id = self.config.source_node_id
        if source_node_id:
            node_outputs = state.get("node_outputs", {})
            if source_node_id in node_outputs:
                source_output = node_outputs[source_node_id]
                if isinstance(source_output, dict) and "query_params" in source_output:
                    context.query_params.update(source_output["query_params"])

        print(f"[SnapshotNode] User: {context.user_id}, Context hash: {context.calculate_hash()}")

        try:
            # Get data to snapshot
            node_outputs = state.get("node_outputs", {})
            if source_node_id not in node_outputs:
                raise ValueError(f"Source node {source_node_id} not found")

            data = node_outputs[source_node_id]
            if isinstance(data, dict) and "data" in data:
                data = data["data"]

            # Create snapshot
            snapshot = await WorkflowSnapshot.create_from_data(
                workflow_id=state.get("workflow_id"),
                node_id=state.get("current_node_id"),
                execution_id=state.get("execution_id"),
                context=context,
                data=data,
                snapshot_label=self.config.snapshot_label,
                retention_days=self.config.retention_days or 30
            )

            return {
                **state,
                "node_outputs": {
                    **node_outputs,
                    state["current_node_id"]: {
                        "status": "snapshot_stored",
                        "snapshot_id": snapshot.id,
                        "storage_type": snapshot.storage_type,
                        "snapshot_date": snapshot.snapshot_date.isoformat(),
                        "context_hash": context.calculate_hash(),
                        "row_count": snapshot.row_count
                    }
                }
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._error_result(state, str(e))

    def _error_result(self, state: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Build error result"""
        return {
            **state,
            "node_outputs": {
                **state.get("node_outputs", {}),
                state["current_node_id"]: {
                    "status": "snapshot_failed",
                    "error": error_message
                }
            }
        }


# ============================================================================
# Compare Node Executor
# ============================================================================

class CompareNodeExecutor(BaseNodeExecutor):
    """
    Execute compare node - compare two data snapshots.

    Features:
    - Auto-detect source HANA node
    - Context-aware comparison (same user + query params)
    - Fast vs deep comparison strategies
    - Row-level change detection
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute comparison"""
        from open_notebook.domain.workflow_snapshot import WorkflowSnapshot, SnapshotContext
        from datetime import date, timedelta

        print(f"[CompareNode] Executing comparison node")

        # Get config (default to "previous" and "current" if not specified)
        compare_snapshot_1 = self.config.compare_snapshot_1 or "previous"  # "previous" | "snapshot_id"
        compare_snapshot_2 = self.config.compare_snapshot_2 or "current"   # "current" | "snapshot_id"
        comparison_strategy = self.config.comparison_strategy or "fast"  # "fast" | "deep"
        change_threshold = self.config.change_threshold or 0.0

        print(f"[CompareNode] Comparing {compare_snapshot_1} vs {compare_snapshot_2}")

        # Auto-detect source node if not configured
        source_node_id = self.config.source_node_id
        if not source_node_id:
            source_node_id = await self._detect_source_node(state)
            if not source_node_id:
                return self._error_result(state, "Could not detect source HANA node. Please configure source_node_id.")

        print(f"[CompareNode] Source node: {source_node_id}")

        # Get context
        context = SnapshotContext.from_workflow_state(state)

        # Capture query params from source node
        node_outputs = state.get("node_outputs", {})
        if source_node_id in node_outputs:
            source_output = node_outputs[source_node_id]
            if isinstance(source_output, dict) and "query_params" in source_output:
                context.query_params.update(source_output["query_params"])

        print(f"[CompareNode] Context hash: {context.calculate_hash()}")

        try:
            # Get current snapshot
            if compare_snapshot_2 == "current":
                # Get latest snapshot for this context
                snapshot_current = await WorkflowSnapshot.get_latest_for_context(
                    workflow_id=state.get("workflow_id"),
                    node_id=source_node_id,
                    context=context
                )
                if not snapshot_current:
                    return self._error_result(state, "No current snapshot found for this context")
            else:
                snapshot_current = await WorkflowSnapshot.get(compare_snapshot_2)
                if not snapshot_current:
                    return self._error_result(state, f"Snapshot not found: {compare_snapshot_2}")

            # Get previous snapshot
            if compare_snapshot_1 == "previous":
                # Get previous snapshot before current
                snapshot_previous = await WorkflowSnapshot.get_previous_for_context(
                    workflow_id=state.get("workflow_id"),
                    node_id=source_node_id,
                    context=context,
                    before_date=snapshot_current.snapshot_date
                )
                if not snapshot_previous:
                    return {
                        **state,
                        "node_outputs": {
                            **state.get("node_outputs", {}),
                            state["current_node_id"]: {
                                "status": "no_previous_snapshot",
                                "has_changes": True,  # Treat as changed if no previous
                                "current_snapshot_id": snapshot_current.id,
                                "current_date": snapshot_current.snapshot_date.isoformat()
                            }
                        }
                    }
            else:
                snapshot_previous = await WorkflowSnapshot.get(compare_snapshot_1)
                if not snapshot_previous:
                    return self._error_result(state, f"Snapshot not found: {compare_snapshot_1}")

            print(f"[CompareNode] Comparing snapshots: {snapshot_previous.id} vs {snapshot_current.id}")

            # Compare snapshots
            delta = await snapshot_previous.compare_with(
                snapshot_current,
                strategy=comparison_strategy
            )

            print(f"[CompareNode] Delta from compare_with: {json.dumps(delta, indent=2, default=str)}")

            # Check if changes exceed threshold
            has_changes = delta.get("changed", False) and delta.get("change_percentage", 0) > change_threshold

            # Extract changed rows
            changed_rows = self._extract_changed_rows(delta)

            print(f"[CompareNode] After _extract_changed_rows: {json.dumps(changed_rows, indent=2, default=str)}")

            # Filter changed rows by watch_columns if configured
            watch_columns = self.config.watch_columns
            if watch_columns:
                changed_rows = self._filter_by_watch_columns(changed_rows, watch_columns)
                print(f"[CompareNode] Filtered by watch_columns: {watch_columns}")

            print(f"[CompareNode] Has changes: {has_changes}, Changed rows: {len(changed_rows.get('added', [])) + len(changed_rows.get('removed', [])) + len(changed_rows.get('modified', []))}")

            # Build result
            result = {
                "status": "comparison_complete",
                "has_changes": has_changes,
                "change_percentage": delta.get("change_percentage", 0),
                "previous_snapshot_id": snapshot_previous.id,
                "current_snapshot_id": snapshot_current.id,
                "previous_date": snapshot_previous.snapshot_date.isoformat(),
                "current_date": snapshot_current.snapshot_date.isoformat(),
                "changed_rows": changed_rows,
                "summary": {
                    "added": len(changed_rows.get("added", [])),
                    "removed": len(changed_rows.get("removed", [])),
                    "modified": len(changed_rows.get("modified", []))
                }
            }

            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: result
                }
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._error_result(state, str(e))

    async def _detect_source_node(self, state: Dict[str, Any]) -> Optional[str]:
        """
        Detect source HANA node by finding previous node in workflow graph.

        Args:
            state: Workflow state with graph information

        Returns:
            Source node ID or None
        """
        # Get workflow graph to find connected nodes
        from open_notebook.domain.workflow import Workflow

        workflow_id = state.get("workflow_id")
        current_node_id = state.get("current_node_id")

        if not workflow_id or not current_node_id:
            return None

        # Load workflow to get graph
        workflow = await Workflow.get(workflow_id)
        if not workflow or not workflow.graph:
            return None

        # Find edges pointing to current node
        edges = workflow.graph.edges if hasattr(workflow.graph, 'edges') else []
        incoming_edges = [e for e in edges if getattr(e, 'target', None) == current_node_id or (isinstance(e, dict) and e.get("target") == current_node_id)]

        if not incoming_edges:
            return None

        # Get source node ID from first incoming edge
        first_edge = incoming_edges[0]
        source_node_id = getattr(first_edge, 'source', None) or (first_edge.get("source") if isinstance(first_edge, dict) else None)

        # Verify source node has snapshots enabled
        nodes = workflow.graph.nodes if hasattr(workflow.graph, 'nodes') else []
        source_node = next((n for n in nodes if (getattr(n, 'id', None) == source_node_id or (isinstance(n, dict) and n.get("id") == source_node_id))), None)

        if source_node:
            # Get config from node
            config = getattr(source_node, 'config', None) or (source_node.get("config") if isinstance(source_node, dict) else None)
            if config:
                enable_snapshots = getattr(config, 'enable_snapshots', None) or (config.get("enable_snapshots") if isinstance(config, dict) else None)
                if enable_snapshots:
                    return source_node_id

        return None

    def _extract_changed_rows(self, delta: Dict[str, Any]) -> Dict[str, list]:
        """
        Extract changed rows from comparison delta.

        Args:
            delta: Comparison delta with added/removed/modified rows

        Returns:
            Dict with added, removed, modified lists
        """
        return {
            "added": delta.get("added_rows", []),
            "removed": delta.get("removed_rows", []),
            "modified": delta.get("modified_rows", [])
        }

    def _filter_by_watch_columns(self, changed_rows: Dict[str, list], watch_columns: List[Dict[str, Any]]) -> Dict[str, list]:
        """
        Filter changed rows by watch_columns configuration.

        Args:
            changed_rows: Dict with added, removed, modified lists
            watch_columns: List of {column: str, watch_value: Optional[str]} dicts

        Returns:
            Filtered changed rows dict
        """
        if not watch_columns:
            return changed_rows

        # Build filter map: column -> watch_value (None means watch any change)
        watch_map = {}
        for wc in watch_columns:
            if isinstance(wc, dict):
                col_name = wc.get("column")
                watch_value = wc.get("watch_value")
                if col_name:
                    watch_map[col_name] = watch_value

        if not watch_map:
            return changed_rows

        print(f"[CompareNode] Watch map: {watch_map}")

        def row_matches_watch_criteria(row: Dict[str, Any], is_modified: bool = False) -> bool:
            """Check if row matches any watch column criteria"""
            # For modified rows, check the 'after' state
            check_row = row.get("after", row) if is_modified else row

            for col_name, watch_value in watch_map.items():
                if col_name not in check_row:
                    continue

                row_value = check_row[col_name]

                # If watch_value is None or empty, any change in this column counts
                if not watch_value:
                    return True

                # If watch_value is specified, check if row value matches
                if str(row_value) == str(watch_value):
                    return True

            return False

        # Filter each category
        filtered = {
            "added": [row for row in changed_rows.get("added", []) if row_matches_watch_criteria(row, False)],
            "removed": [row for row in changed_rows.get("removed", []) if row_matches_watch_criteria(row, False)],
            "modified": [row for row in changed_rows.get("modified", []) if row_matches_watch_criteria(row, True)]
        }

        print(f"[CompareNode] Filtered: added={len(filtered['added'])}, removed={len(filtered['removed'])}, modified={len(filtered['modified'])}")

        return filtered

    def _error_result(self, state: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Build error result"""
        return {
            **state,
            "node_outputs": {
                **state.get("node_outputs", {}),
                state["current_node_id"]: {
                    "status": "comparison_failed",
                    "error": error_message,
                    "has_changes": False,
                    "changed_rows": []
                }
            }
        }


# ============================================================================
# HANA Table Node Executor
# ============================================================================

class HANATableNodeExecutor(BaseNodeExecutor):
    """Execute HANA table node - query HANA database."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HANA query."""
        from hdbcli import dbapi
        from api.routers.hana_connections import decrypt_password
        from open_notebook.database.repository import repo_query
        import json

        print(f"[HANATableNodeExecutor] Executing HANA_TABLE node")

        # Get configuration
        connection_id = self.config.hana_connection_id
        table_name = self.config.hana_table_name
        custom_query = self.config.hana_query
        where_clause = self.config.hana_where_clause
        limit = self.config.hana_limit or 100
        columns = self.config.hana_columns
        conditions = self.config.conditions or []

        # Build WHERE clause from conditions if provided
        if conditions and len(conditions) > 0:
            condition_clauses = []
            for cond in conditions:
                column = cond.get("column")
                operator = cond.get("operator", "=")
                value = cond.get("value")

                if column and value is not None:
                    # Quote the value if it's a string
                    if isinstance(value, str):
                        quoted_value = f"'{value}'"
                    else:
                        quoted_value = str(value)

                    # Handle different operators
                    if operator in ["IS NULL", "IS NOT NULL"]:
                        condition_clauses.append(f'"{column}" {operator}')
                    elif operator == "IN":
                        condition_clauses.append(f'"{column}" {operator} ({quoted_value})')
                    else:
                        condition_clauses.append(f'"{column}" {operator} {quoted_value}')

            # Combine with existing where_clause if present
            if condition_clauses:
                conditions_where = " AND ".join(condition_clauses)
                if where_clause:
                    where_clause = f"({where_clause}) AND ({conditions_where})"
                else:
                    where_clause = conditions_where

                print(f"[HANATableNodeExecutor] Built WHERE clause from conditions: {where_clause}")

        # Validate configuration
        if not connection_id:
            return self._error_result(state, "HANA connection_id is required")

        if not table_name and not custom_query:
            return self._error_result(state, "Either hana_table_name or hana_query is required")

        try:
            # Get connection credentials from hana_connections table
            conn_sql = "SELECT * FROM hana_connections WHERE id = :id"
            conn_results = await repo_query(conn_sql, {"id": connection_id})

            if not conn_results:
                return self._error_result(state, f"HANA connection {connection_id} not found")

            conn = conn_results[0]

            # Decrypt password
            encrypted_password = conn.get("password_encrypted")
            if not encrypted_password:
                return self._error_result(state, f"No password stored for connection {connection_id}")

            decrypted_password = decrypt_password(encrypted_password)

            # Build SQL query
            if custom_query:
                # Use custom query (must be SELECT only)
                sql = custom_query.strip()
                if not sql.upper().startswith("SELECT"):
                    return self._error_result(state, "Custom query must be a SELECT statement")
            else:
                # Build query from table and filters
                if columns and len(columns) > 0:
                    columns_str = ", ".join(columns)
                else:
                    columns_str = "*"

                # Qualify table name with schema if not already qualified
                # If table_name doesn't contain a dot, prepend the schema from connection
                if "." not in table_name:
                    schema = conn.get("schema")
                    if schema:
                        qualified_table = f'"{schema}"."{table_name}"'
                    else:
                        # No schema in connection, use table name as-is (might fail for virtual tables)
                        qualified_table = f'"{table_name}"'
                else:
                    # Table name already has schema (e.g., "SCHEMA"."TABLE")
                    qualified_table = table_name

                sql = f"SELECT {columns_str} FROM {qualified_table}"

                if where_clause:
                    sql += f" WHERE {where_clause}"

                sql += f" LIMIT {limit}"

            print(f"[HANATableNodeExecutor] Executing SQL: {sql}")

            # Connect to HANA and execute query
            connection = None
            cursor = None

            try:
                connection_params = {
                    "address": conn["host"],
                    "port": conn["port"],
                    "user": conn["user"],
                    "password": decrypted_password,
                    "encrypt": True
                }

                connection = dbapi.connect(**connection_params)
                cursor = connection.cursor()
                cursor.execute(sql)

                # Fetch results
                column_names = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                # Convert to list of dicts
                results = [
                    {column_names[i]: self._convert_value(row[i]) for i in range(len(column_names))}
                    for row in rows
                ]

                print(f"[HANATableNodeExecutor] Query returned {len(results)} rows")

                # Store query params for context-aware snapshots
                query_params = {
                    "connection_id": connection_id,
                    "table_name": table_name,
                    "where_clause": where_clause,
                    "limit": limit
                }

                # Build output
                output = {
                    "status": "success",
                    "data": results,
                    "row_count": len(results),
                    "columns": column_names,
                    "query": sql,
                    "query_params": query_params
                }

                # If snapshots enabled, create snapshot automatically
                if self.config.enable_snapshots:
                    try:
                        from open_notebook.domain.workflow_snapshot import SnapshotContext, WorkflowSnapshot
                        from open_notebook.database.repository import repo_delete, repo_query

                        print(f"[HANATableNodeExecutor] Creating automatic snapshot (enable_snapshots=True)")

                        # Build context
                        context = SnapshotContext.from_workflow_state(state)
                        context.query_params.update(query_params)

                        # Create snapshot with HANA node's ID as the node_id
                        snapshot = await WorkflowSnapshot.create_from_data(
                            workflow_id=state.get("workflow_id"),
                            node_id=state["current_node_id"],  # Use HANA node's ID
                            execution_id=state.get("execution_id"),
                            context=context,
                            data=results,
                            snapshot_label=self.config.snapshot_label,
                            retention_days=self.config.retention_days or 30
                        )

                        # Include snapshot info in output
                        output["snapshot_id"] = snapshot.id
                        output["snapshot_created"] = True
                        print(f"[HANATableNodeExecutor] Snapshot created: {snapshot.id}")

                        # Cleanup: Keep only the 2 most recent snapshots for this workflow+node
                        try:
                            # Get all snapshots for this workflow and node, ordered by date (newest first)
                            all_snapshots = await repo_query(
                                """
                                SELECT id FROM workflow_snapshots
                                WHERE workflow_id = :workflow_id
                                AND node_id = :node_id
                                ORDER BY snapshot_date DESC
                                """,
                                {
                                    "workflow_id": state.get("workflow_id"),
                                    "node_id": state["current_node_id"]
                                }
                            )

                            # If more than 2 snapshots, delete the old ones
                            if len(all_snapshots) > 2:
                                snapshots_to_delete = all_snapshots[2:]  # Keep first 2 (newest)
                                for snap_row in snapshots_to_delete:
                                    await repo_delete("workflow_snapshots", snap_row["id"])
                                    print(f"[HANATableNodeExecutor] Deleted old snapshot: {snap_row['id']}")

                                print(f"[HANATableNodeExecutor] Cleaned up {len(snapshots_to_delete)} old snapshot(s), kept 2 most recent")

                        except Exception as cleanup_err:
                            print(f"[HANATableNodeExecutor] Warning: Failed to cleanup old snapshots: {cleanup_err}")
                            # Don't fail if cleanup fails

                    except Exception as snap_err:
                        print(f"[HANATableNodeExecutor] Warning: Failed to create snapshot: {snap_err}")
                        import traceback
                        traceback.print_exc()
                        # Don't fail the whole node if snapshot fails
                        output["snapshot_error"] = str(snap_err)

                return {
                    **state,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        state["current_node_id"]: output
                    }
                }

            finally:
                if cursor:
                    cursor.close()
                if connection:
                    connection.close()

        except Exception as e:
            print(f"[HANATableNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            return self._error_result(state, str(e))

    def _convert_value(self, value):
        """Convert database value to JSON-serializable type"""
        from datetime import datetime, date, time
        from decimal import Decimal

        if value is None:
            return None
        elif isinstance(value, (datetime, date, time)):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        else:
            return value

    def _error_result(self, state: Dict[str, Any], error_message: str) -> Dict[str, Any]:
        """Build error result"""
        return {
            **state,
            "node_outputs": {
                **state.get("node_outputs", {}),
                state["current_node_id"]: {
                    "status": "error",
                    "error": error_message,
                    "data": []
                }
            }
        }


# ============================================================================
# Node Executor Factory
# ============================================================================

def create_node_executor(node_type: NodeType, config: NodeConfig) -> BaseNodeExecutor:
    """
    Create node executor for given type.

    Args:
        node_type: Type of node
        config: Node configuration

    Returns:
        Node executor instance
    """
    executors = {
        NodeType.LLM: LLMNodeExecutor,
        NodeType.TOOL: ToolNodeExecutor,
        NodeType.CONDITIONAL: ConditionalNodeExecutor,
        NodeType.AGENT: AgentNodeExecutor,
        NodeType.INPUT: InputNodeExecutor,
        NodeType.OUTPUT: OutputNodeExecutor,
        NodeType.NOTEBOOK_GENERATOR: NotebookGeneratorNodeExecutor,
        NodeType.MICROSITE_GENERATOR: MicrositeGeneratorNodeExecutor,
        NodeType.PRESENTATION_GENERATOR: PresentationGeneratorNodeExecutor,
        NodeType.HUMAN_APPROVAL: HumanApprovalNodeExecutor,
        NodeType.WORKSPACE: WorkspaceNodeExecutor,
        NodeType.TEMPLATE: TemplateNodeExecutor,
        NodeType.DELAY: DelayNodeExecutor,
        NodeType.WEBHOOK: WebhookNodeExecutor,
        NodeType.SNAPSHOT: SnapshotNodeExecutor,
        NodeType.COMPARE: CompareNodeExecutor,
        NodeType.HANA_TABLE: HANATableNodeExecutor,
    }

    executor_class = executors.get(node_type)
    if not executor_class:
        raise ValueError(f"Unknown node type: {node_type}")

    return executor_class(config)
