"""
Workflow Node Executors

Implements execution logic for different node types:
- LLM nodes: Call AI models
- Tool nodes: Execute tools (HANA queries, web search, etc.)
- Conditional nodes: Evaluate conditions and route execution
- Input/Output nodes: Handle data flow
"""

import json
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from uuid import uuid4

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from open_notebook.domain.workflow import NodeConfig, NodeType
from api.services.tool_factory import ToolFactory
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

            # Try to find value in input_data first
            if var_name in input_data:
                value = input_data[var_name]
            # Then try context (node_outputs)
            elif var_name in context:
                value = context[var_name]
            else:
                # Try to extract from nested node outputs (e.g., {{notebook_id}} could be in prev-node output)
                for node_output in context.values():
                    if isinstance(node_output, dict) and var_name in node_output:
                        value = node_output[var_name]
                        break

            if value is None:
                # Keep placeholder if not found
                print(f"[BaseNodeExecutor] Warning: Variable {{{{{var_name}}}}} not found in input_data or context")
                continue

            # Convert value to string
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, indent=2)
            else:
                value_str = str(value)

            # Replace placeholder
            result = result.replace(f"{{{{{var_name}}}}}", value_str)

        return result


# ============================================================================
# LLM Node Executor
# ============================================================================

class LLMNodeExecutor(BaseNodeExecutor):
    """
    Execute LLM node - call AI model with context.

    Builds prompt from previous node outputs and calls configured LLM.
    """

    def _create_llm(self) -> ChatOpenAI:
        """Create LLM instance."""
        import os

        # Use LiteLLM proxy (same as IntelligentAgent)
        litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:6655/litellm/v1")
        litellm_api_key = os.getenv("HAI_PROXY_KEY", "")

        if not litellm_api_key:
            raise ValueError(
                "HAI_PROXY_KEY not configured. Please set it in your .env file."
            )

        model_name = self.config.model_name or "gpt-4"
        temperature = self.config.temperature or 0.3
        max_tokens = self.config.max_tokens or 4096

        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            base_url=litellm_base_url,
            api_key=litellm_api_key,
        )

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute LLM node.

        Args:
            state: Contains node_outputs (previous results), current_node_id, input_data

        Returns:
            Updated state with new node output
        """
        print(f"[LLMNodeExecutor] Executing LLM node")

        # Get previous outputs as context
        context = state.get("node_outputs", {})
        current_node_id = state.get("current_node_id")

        print(f"[LLMNodeExecutor] Current node: {current_node_id}")
        print(f"[LLMNodeExecutor] Context: {list(context.keys())}")

        # Build prompt
        system_prompt = self.config.system_prompt or "Process the following data:"

        # Format context data
        context_str = json.dumps(context, indent=2) if context else "No previous data"

        # Add input data if this is first node
        input_data = state.get("input_data", {})
        if input_data:
            context_str += f"\n\nInput Data:\n{json.dumps(input_data, indent=2)}"

        print(f"[LLMNodeExecutor] Building messages with system prompt: {system_prompt[:100]}...")

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context_str)
        ]

        # Call LLM
        print(f"[LLMNodeExecutor] Creating LLM instance...")
        llm = self._create_llm()
        print(f"[LLMNodeExecutor] Calling LLM...")
        response = await llm.ainvoke(messages)
        print(f"[LLMNodeExecutor] LLM response received: {response.content[:100]}...")

        # Store output
        new_node_outputs = {
            **state.get("node_outputs", {}),
            current_node_id: response.content
        }

        print(f"[LLMNodeExecutor] Returning updated state with output for {current_node_id}")

        return {
            **state,
            "node_outputs": new_node_outputs
        }


# ============================================================================
# Tool Node Executor
# ============================================================================

class ToolNodeExecutor(BaseNodeExecutor):
    """
    Execute tool node - call HANA, web search, calculator, etc.

    Uses ToolFactory to get and execute tools.
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute tool node.

        Args:
            state: Contains node_outputs, current_node_id

        Returns:
            Updated state with tool result
        """
        tool_name = self.config.tool_name
        tool_args = self.config.tool_args or {}
        current_node_id = state.get("current_node_id")

        if not tool_name:
            raise ValueError(f"Tool node {current_node_id} missing tool_name")

        # Get tool from factory
        factory = ToolFactory()
        tool = await factory.get_tool_by_name(tool_name)

        if not tool:
            raise ValueError(f"Tool not found: {tool_name}")

        # Execute tool
        try:
            result = await tool.ainvoke(tool_args)
        except Exception as e:
            result = {"error": str(e)}

        # Store output
        new_node_outputs = {
            **state.get("node_outputs", {}),
            current_node_id: result
        }

        return {
            **state,
            "node_outputs": new_node_outputs
        }


# ============================================================================
# Conditional Node Executor
# ============================================================================

class ConditionalNodeExecutor(BaseNodeExecutor):
    """
    Execute conditional node - evaluate condition and route.

    Supports: equals, contains, greater_than, less_than
    """

    def _extract_field(self, data: Any, field_path: str) -> Any:
        """
        Extract field from data using JSONPath-like syntax.

        Args:
            data: Data to extract from
            field_path: Path like "$.status" or "status"

        Returns:
            Extracted value or None
        """
        if not field_path:
            return data

        # Remove leading $. if present
        if field_path.startswith("$."):
            field_path = field_path[2:]

        # Simple path traversal (no arrays or complex paths)
        parts = field_path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

        return current

    def _evaluate_condition(
        self,
        field_value: Any,
        condition_type: str,
        comparison_value: Any
    ) -> bool:
        """
        Evaluate condition.

        Args:
            field_value: Value from data
            condition_type: equals, contains, greater_than, less_than
            comparison_value: Value to compare against

        Returns:
            True if condition met
        """
        if condition_type == "equals":
            return field_value == comparison_value

        elif condition_type == "contains":
            if isinstance(field_value, str):
                return comparison_value in field_value
            elif isinstance(field_value, (list, tuple)):
                return comparison_value in field_value
            return False

        elif condition_type == "greater_than":
            try:
                return float(field_value) > float(comparison_value)
            except (ValueError, TypeError):
                return False

        elif condition_type == "less_than":
            try:
                return float(field_value) < float(comparison_value)
            except (ValueError, TypeError):
                return False

        return False

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute conditional node.

        Args:
            state: Contains node_outputs, current_node_id, prev_node_id

        Returns:
            Updated state with condition result and next_node_id
        """
        current_node_id = state.get("current_node_id")
        prev_node_id = state.get("prev_node_id")

        # Get previous output
        prev_output = state.get("node_outputs", {}).get(prev_node_id)

        # Extract field value
        field_value = self._extract_field(prev_output, self.config.field_path)

        # Evaluate condition
        result = self._evaluate_condition(
            field_value,
            self.config.condition_type,
            self.config.comparison_value
        )

        # Determine next node
        next_node_id = (
            self.config.true_edge_id if result
            else self.config.false_edge_id
        )

        # Store result
        new_node_outputs = {
            **state.get("node_outputs", {}),
            current_node_id: {
                "condition_result": result,
                "field_value": field_value,
                "comparison_value": self.config.comparison_value,
                "next_node": next_node_id
            }
        }

        return {
            **state,
            "node_outputs": new_node_outputs,
            "next_node_id": next_node_id
        }


# ============================================================================
# Agent Node Executor
# ============================================================================

class AgentNodeExecutor(BaseNodeExecutor):
    """
    Execute agent node - run standalone agent or agent team.

    Integrates with existing agent system.
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent node.

        Args:
            state: Contains node_outputs, current_node_id, input_data

        Returns:
            Updated state with agent result
        """
        agent_type = self.config.agent_type
        agent_id = self.config.agent_id
        agent_name = self.config.agent_name
        prompt_template = self.config.prompt  # NEW: Get prompt template
        current_node_id = state.get("current_node_id")

        print(f"[AgentNodeExecutor] Executing agent node: {current_node_id}")
        print(f"[AgentNodeExecutor] Agent type: {agent_type}, ID: {agent_id}, Name: {agent_name}")
        print(f"[AgentNodeExecutor] Prompt template: {prompt_template}")

        if not agent_type or not agent_id:
            raise ValueError(f"Agent node {current_node_id} missing agent_type or agent_id")

        if not prompt_template:
            raise ValueError(f"Agent node {current_node_id} missing prompt field. Please configure a prompt in the node properties.")

        # Get previous outputs and input data
        context = state.get("node_outputs", {})
        input_data = state.get("input_data", {})

        print(f"[AgentNodeExecutor] Context keys: {list(context.keys())}")
        print(f"[AgentNodeExecutor] Input data keys: {list(input_data.keys())}")

        # Substitute template variables in prompt
        query = self._substitute_variables(prompt_template, input_data, context)
        print(f"[AgentNodeExecutor] Substituted query: {query[:200]}...")

        # Build additional context from previous outputs
        context_text = self._format_context(context, input_data)

        if agent_type == "standalone":
            # Execute standalone agent
            result = await self._execute_standalone_agent(agent_id, agent_name, query, context_text)
        elif agent_type == "team":
            # Execute agent team
            result = await self._execute_agent_team(agent_id, agent_name, query, context_text)
        else:
            raise ValueError(f"Unknown agent_type: {agent_type}")

        print(f"[AgentNodeExecutor] Agent execution completed, result: {result}")

        # Store output
        new_node_outputs = {
            **state.get("node_outputs", {}),
            current_node_id: result
        }

        return {
            **state,
            "node_outputs": new_node_outputs
        }

    def _format_context(self, context: Dict[str, Any], input_data: Dict[str, Any]) -> str:
        """Format context and input data for agent prompt."""
        parts = []

        if context:
            parts.append("Previous Node Outputs:")
            for node_id, output in context.items():
                parts.append(f"\n{node_id}: {json.dumps(output, indent=2)}")

        if input_data:
            parts.append("\n\nInput Data:")
            parts.append(json.dumps(input_data, indent=2))

        return "\n".join(parts) if parts else "No context available"

    async def _execute_standalone_agent(
        self,
        agent_id: str,
        agent_name: str,
        query: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Execute a standalone agent with query and context.

        Args:
            agent_id: Agent ID
            agent_name: Agent name
            query: User query/prompt (from template substitution)
            context: Formatted context from previous nodes

        Returns:
            Agent execution result
        """
        print(f"[AgentNodeExecutor] Executing standalone agent: {agent_name}")
        print(f"[AgentNodeExecutor] Query: {query[:100]}...")

        try:
            # Get agent configuration
            from open_notebook.database.repository import repo_query
            agent_rows = await repo_query(
                "SELECT * FROM standalone_agents WHERE id = :id AND status = 'active'",
                {"id": agent_id}
            )

            if not agent_rows:
                raise ValueError(f"Standalone agent {agent_id} not found or inactive")

            agent_data = agent_rows[0]
            print(f"[AgentNodeExecutor] Found agent: {agent_data['name']}")

            # Get LLM configuration
            from api.services.settings import get_setting
            from api.routers.credentials import _credentials_store

            language_model_id = await get_setting("language_model_id", "")
            model_id = agent_data.get("model_name") or language_model_id

            if not model_id:
                raise ValueError("No AI model configured")

            credential = _credentials_store.get(model_id)
            if not credential:
                raise ValueError(f"Model {model_id} not found in credentials")

            print(f"[AgentNodeExecutor] Using model: {credential['model_name']}")

            # Get data sources for context
            source_ids = json.loads(agent_data.get("data_source_ids") or "[]")
            context_content = ""

            if source_ids:
                print(f"[AgentNodeExecutor] Loading {len(source_ids)} data sources")
                param_names = [f":source_{i}" for i in range(len(source_ids))]
                placeholders = ','.join(param_names)
                sql = f"SELECT id, title, full_text, source_type FROM sources WHERE id IN ({placeholders})"
                params = {f"source_{i}": source_id for i, source_id in enumerate(source_ids)}

                sources_rows = await repo_query(sql, params)
                if sources_rows:
                    context_parts = []
                    for source in sources_rows:
                        title = source.get("title", "Untitled")
                        full_text = source.get("full_text", "")
                        context_parts.append(f"Source: {title}\n{full_text}\n")
                    context_content = "\n\n---\n\n".join(context_parts)

            # Get tools
            tool_ids = json.loads(agent_data.get("tool_ids") or "[]")
            tools = []

            if tool_ids:
                print(f"[AgentNodeExecutor] Loading {len(tool_ids)} tools")
                tool_factory = ToolFactory()
                all_registry_tools = await tool_factory._get_registry_tools()

                for tool in all_registry_tools:
                    tool_registry_id = None
                    if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict):
                        tool_registry_id = tool.metadata.get('_registry_id')

                    if tool_registry_id in tool_ids:
                        tools.append(tool)

                print(f"[AgentNodeExecutor] Loaded {len(tools)} tools")

            # Build system prompt
            system_prompt = agent_data.get("system_prompt") or f"You are a helpful {agent_data['role']} assistant."

            # Add data source context
            if context_content:
                system_prompt += f"\n\nData Sources:\n\n{context_content}"

            # Add workflow context from previous nodes
            if context and context != "No context available":
                system_prompt += f"\n\nWorkflow Context:\n\n{context}"

            # Use the provided query (already has template substitution)
            print(f"[AgentNodeExecutor] Using query: {query[:100]}...")

            print(f"[AgentNodeExecutor] Calling LLM with system prompt length: {len(system_prompt)}, query length: {len(query)}")

            # Prepare messages
            llm_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]

            # Call LLM via httpx (same pattern as standalone_agents.py)
            import httpx

            request_payload = {
                "model": credential["model_name"],
                "messages": llm_messages,
                "max_tokens": 2000,
                "temperature": 0.7,
                "stream": False  # Non-streaming for workflow execution
            }

            # Add tools if available
            if tools:
                tool_schemas = []
                for tool in tools:
                    tool_schemas.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": getattr(tool, "args_schema", {}).schema() if hasattr(tool, "args_schema") else {}
                        }
                    })
                request_payload["tools"] = tool_schemas
                print(f"[AgentNodeExecutor] Including {len(tool_schemas)} tools")

            endpoint_url = f"{credential['base_url']}/chat/completions"

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    endpoint_url,
                    json=request_payload,
                    headers={
                        "Authorization": f"Bearer {credential['api_key']}",
                        "Content-Type": "application/json"
                    }
                )

                if response.status_code != 200:
                    raise ValueError(f"LLM API error: {response.status_code} {response.text}")

                result_data = response.json()
                message = result_data["choices"][0]["message"]
                content = message.get("content", "")

                print(f"[AgentNodeExecutor] LLM response length: {len(content)}")

                # Handle tool calls if present
                tool_calls = message.get("tool_calls", [])
                tool_results = []

                if tool_calls:
                    print(f"[AgentNodeExecutor] Processing {len(tool_calls)} tool calls")
                    for tool_call in tool_calls:
                        tool_name = tool_call["function"]["name"]
                        tool_args = json.loads(tool_call["function"]["arguments"])

                        # Find and execute tool
                        tool = next((t for t in tools if t.name == tool_name), None)
                        if tool:
                            tool_result = await tool.ainvoke(tool_args)
                            tool_results.append({
                                "tool": tool_name,
                                "args": tool_args,
                                "result": tool_result
                            })

                return {
                    "agent_type": "standalone",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "status": "completed",
                    "output": content,
                    "tool_calls": tool_results,
                }

        except Exception as e:
            print(f"[AgentNodeExecutor] Agent execution failed: {e}")
            import traceback
            traceback.print_exc()

            return {
                "agent_type": "standalone",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "status": "failed",
                "error": str(e),
            }

    async def _execute_agent_team(
        self,
        team_id: str,
        team_name: str,
        query: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Execute an agent team with query and context.

        Args:
            team_id: Team ID
            team_name: Team name
            query: User query/prompt (from template substitution)
            context: Formatted context from previous nodes

        Returns:
            Team execution result
        """
        print(f"[AgentNodeExecutor] Executing agent team: {team_name}")
        print(f"[AgentNodeExecutor] Query: {query[:100]}...")

        try:
            # Get team configuration
            from open_notebook.database.repository import repo_query
            from open_notebook.domain.agent_team import AgentTeam

            team = await AgentTeam.get(team_id)
            if not team:
                raise ValueError(f"Agent team {team_id} not found")

            print(f"[AgentNodeExecutor] Found team: {team.name} with {len(team.agents)} agents")

            # Execute team using AgentManager
            from open_notebook.agents.agent_manager import AgentManager

            # Create manager
            manager = AgentManager()

            # Load existing team
            manager._buses[team.id] = MessageBus(team_id=team.id)
            manager._task_managers[team.id] = TaskManager(team_id=team.id)
            manager._agents[team.id] = {}

            # Instantiate agents
            for agent_instance in team.agents:
                agent_cls = get_agent_class(agent_instance.role)
                if not agent_cls:
                    print(f"[AgentNodeExecutor] Warning: No agent class for role {agent_instance.role}")
                    continue

                agent = agent_cls(
                    name=agent_instance.name,
                    role=agent_instance.role,
                    model_name=agent_instance.model_name or manager.model_name,
                    system_prompt=agent_instance.system_prompt,
                )
                manager._agents[team.id][agent_instance.id] = agent

            # Load existing tasks
            tasks = await TaskManager.get_tasks_for_team(team.id)
            for task in tasks:
                manager._task_managers[team.id].add_task(task)

            # Add a task for the workflow query
            workflow_task = AgentTask(
                id=str(uuid4()),
                team_id=team.id,
                name=f"Process workflow query",
                description=f"{query}\n\nAdditional Context:\n{context}",
                status="pending",
            )
            await workflow_task.save()
            manager._task_managers[team.id].add_task(workflow_task)

            print(f"[AgentNodeExecutor] Running team with {len(tasks) + 1} tasks")

            # Run team
            result = await manager.run_team(team.id)

            print(f"[AgentNodeExecutor] Team execution completed with status: {result.get('status')}")

            return {
                "agent_type": "team",
                "agent_id": team_id,
                "agent_name": team_name,
                "status": "completed",
                "output": result.get("summary", ""),
                "task_results": result.get("task_results", []),
                "metadata": result.get("metadata", {}),
            }

        except Exception as e:
            print(f"[AgentNodeExecutor] Team execution failed: {e}")
            import traceback
            traceback.print_exc()

            return {
                "agent_type": "team",
                "agent_id": team_id,
                "agent_name": team_name,
                "status": "failed",
                "error": str(e),
            }


# ============================================================================
# Input/Output Node Executors
# ============================================================================

class InputNodeExecutor(BaseNodeExecutor):
    """Input node - validates and passes through input data based on field definitions."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate input data against defined fields and pass through."""
        current_node_id = state.get("current_node_id")
        input_data = state.get("input_data", {})

        # Get field definitions from config
        input_fields = self.config.input_fields or []

        # If no fields defined, pass through all data (backward compatibility)
        if not input_fields:
            new_node_outputs = {
                **state.get("node_outputs", {}),
                current_node_id: input_data
            }
            return {**state, "node_outputs": new_node_outputs}

        # Validate and filter input data
        validated_data = {}
        errors = []

        for field_def in input_fields:
            field_name = field_def.name

            # Check if required field is present
            if field_def.required and field_name not in input_data:
                if field_def.default_value is not None:
                    validated_data[field_name] = field_def.default_value
                else:
                    errors.append(f"Required field '{field_name}' is missing")
                    continue

            # Get value or default
            value = input_data.get(field_name, field_def.default_value)

            # Type validation
            if value is not None:
                try:
                    validated_value = self._validate_type(value, field_def.type)
                    validated_data[field_name] = validated_value
                except ValueError as e:
                    errors.append(f"Field '{field_name}': {str(e)}")

        # If validation errors, fail the workflow
        if errors:
            return {
                **state,
                "error": f"Input validation failed: {'; '.join(errors)}"
            }

        # Store validated data in node outputs
        new_node_outputs = {
            **state.get("node_outputs", {}),
            current_node_id: validated_data
        }

        return {
            **state,
            "node_outputs": new_node_outputs
        }

    def _validate_type(self, value: Any, expected_type: str) -> Any:
        """Validate and coerce value to expected type."""
        if expected_type == "string":
            return str(value)
        elif expected_type == "number":
            try:
                return float(value) if isinstance(value, (int, float, str)) else value
            except (ValueError, TypeError):
                raise ValueError(f"Cannot convert '{value}' to number")
        elif expected_type == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ["true", "1", "yes"]
            return bool(value)
        elif expected_type == "array":
            if not isinstance(value, list):
                raise ValueError(f"Expected array, got {type(value).__name__}")
            return value
        elif expected_type == "object":
            if not isinstance(value, dict):
                raise ValueError(f"Expected object, got {type(value).__name__}")
            return value
        else:
            return value


class OutputNodeExecutor(BaseNodeExecutor):
    """Output node - collects final output."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Collect final output from all node outputs."""
        node_outputs = state.get("node_outputs", {})

        # Final output is all collected data
        final_output = {
            "all_outputs": node_outputs,
            "completed": True
        }

        return {
            **state,
            "final_output": final_output
        }


# ============================================================================
# Notebook Generator Node Executor
# ============================================================================

class NotebookGeneratorNodeExecutor(BaseNodeExecutor):
    """
    Execute notebook generator node - create notebooks from workflow outputs.

    Supports:
    - Template variable substitution for notebook name/description
    - 3 content extraction modes: full_output, smart_parse, json_path
    - Creating new sources or linking existing ones
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute notebook generator node.

        Args:
            state: Contains node_outputs, current_node_id, input_data

        Returns:
            Updated state with notebook creation result
        """
        current_node_id = state.get("current_node_id")
        input_data = state.get("input_data", {})
        context = state.get("node_outputs", {})

        print(f"[NotebookGeneratorNodeExecutor] Executing node: {current_node_id}")

        try:
            # Step 1: Validate prerequisites
            await self._validate_language_model_configured()

            # Step 2: Substitute template variables
            notebook_name = self._substitute_variables(
                self.config.notebook_name or "Generated Notebook",
                input_data,
                context
            )
            notebook_description = None
            if self.config.notebook_description:
                notebook_description = self._substitute_variables(
                    self.config.notebook_description,
                    input_data,
                    context
                )

            print(f"[NotebookGeneratorNodeExecutor] Creating notebook: {notebook_name}")

            # Step 3: Create notebook
            from open_notebook.domain.notebook import Notebook
            notebook = Notebook(
                name=notebook_name,
                description=notebook_description,
                folder_id=self.config.folder_id,
                tags=self.config.tags or []
            )
            notebook_id = await notebook.save()

            print(f"[NotebookGeneratorNodeExecutor] Notebook created: {notebook_id}")

            # Step 4: Handle sources
            source_ids = await self._handle_sources(notebook, state)

            # Step 5: Format output
            output = self._format_output(notebook_id, notebook_name, source_ids)

            print(f"[NotebookGeneratorNodeExecutor] Execution complete: {output}")

            return {
                **state,
                "node_outputs": {
                    **context,
                    current_node_id: output
                }
            }

        except Exception as e:
            print(f"[NotebookGeneratorNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()

            return {
                **state,
                "node_outputs": {
                    **context,
                    current_node_id: {
                        "status": "failed",
                        "error": str(e),
                        "notebook_id": None
                    }
                }
            }

    async def _validate_language_model_configured(self):
        """Validate that a language model is configured (required for notebooks)."""
        from api.services.settings import get_setting

        language_model_id = await get_setting("language_model_id", "")
        if not language_model_id:
            raise ValueError(
                "No language model configured. Please configure a language model "
                "in Settings → Models before creating notebooks."
            )

    async def _handle_sources(self, notebook, state: Dict[str, Any]) -> list:
        """
        Handle source creation and linking based on source_mode.

        Args:
            notebook: Notebook instance
            state: Workflow state

        Returns:
            List of source IDs that were created/linked
        """
        from open_notebook.domain.notebook import Source
        source_mode = self.config.source_mode or "create_from_content"
        source_ids = []

        # Create sources from content
        if source_mode in ["create_from_content", "both"]:
            if not self.config.content_source_node_id:
                # Only error if we're trying to create sources
                if source_mode == "create_from_content":
                    raise ValueError(
                        "content_source_node_id is required when source_mode is 'create_from_content'"
                    )
                # For "both" mode, skip content creation if not configured
            else:
                created_source_ids = await self._create_sources_from_content(notebook, state)
                source_ids.extend(created_source_ids)

        # Link existing sources
        if source_mode in ["use_existing", "both"]:
            existing_ids = self.config.existing_source_ids or []
            # It's OK to have an empty list - notebook can have 0 sources

            for source_id in existing_ids:
                await notebook.add_source(source_id)
                source_ids.append(source_id)

        return source_ids

    async def _create_sources_from_content(self, notebook, state: Dict[str, Any]) -> list:
        """
        Create sources from previous node output based on extraction mode.

        Args:
            notebook: Notebook instance
            state: Workflow state

        Returns:
            List of created source IDs
        """
        from open_notebook.domain.notebook import Source
        from jsonpath_ng import parse

        context = state.get("node_outputs", {})
        content_source_node_id = self.config.content_source_node_id
        extraction_mode = self.config.content_extraction_mode or "full_output"

        if content_source_node_id not in context:
            raise ValueError(
                f"Node '{content_source_node_id}' not found in previous outputs. "
                f"Available nodes: {list(context.keys())}"
            )

        output = context[content_source_node_id]
        source_title_template = self.config.source_title_template or "Generated Source"
        source_type = self.config.source_type or "text"
        source_ids = []

        if extraction_mode == "full_output":
            # Extract entire output as string
            content = json.dumps(output) if isinstance(output, (dict, list)) else str(output)
            source = Source(
                title=source_title_template,
                source_type=source_type,
                full_text=content
            )
            source_id = await source.save()
            await notebook.add_source(source_id)
            source_ids.append(source_id)

        elif extraction_mode == "smart_parse":
            # Intelligently parse structured outputs
            if isinstance(output, list):
                # Create multiple sources from array
                for i, item in enumerate(output):
                    title = f"{source_title_template} {i+1}"
                    content = json.dumps(item) if isinstance(item, dict) else str(item)
                    source = Source(
                        title=title,
                        source_type=source_type,
                        full_text=content
                    )
                    source_id = await source.save()
                    await notebook.add_source(source_id)
                    source_ids.append(source_id)
            elif isinstance(output, dict) and "content" in output:
                # Extract content field if present
                content = output["content"]
                source = Source(
                    title=source_title_template,
                    source_type=source_type,
                    full_text=str(content)
                )
                source_id = await source.save()
                await notebook.add_source(source_id)
                source_ids.append(source_id)
            else:
                # Fallback to string conversion
                content = str(output)
                source = Source(
                    title=source_title_template,
                    source_type=source_type,
                    full_text=content
                )
                source_id = await source.save()
                await notebook.add_source(source_id)
                source_ids.append(source_id)

        elif extraction_mode == "json_path":
            # Use JSONPath expression
            if not self.config.content_extraction_path:
                raise ValueError(
                    "content_extraction_path is required when content_extraction_mode is 'json_path'"
                )

            jsonpath_expr = parse(self.config.content_extraction_path)
            matches = [match.value for match in jsonpath_expr.find(output)]

            if not matches:
                raise ValueError(
                    f"JSONPath '{self.config.content_extraction_path}' returned no matches"
                )

            for i, match in enumerate(matches):
                title = f"{source_title_template} {i+1}" if len(matches) > 1 else source_title_template
                content = json.dumps(match) if isinstance(match, (dict, list)) else str(match)
                source = Source(
                    title=title,
                    source_type=source_type,
                    full_text=content
                )
                source_id = await source.save()
                await notebook.add_source(source_id)
                source_ids.append(source_id)

        return source_ids

    def _format_output(self, notebook_id: str, notebook_name: str, source_ids: list) -> dict:
        """Format output based on output_format configuration."""
        output_format = self.config.output_format or "summary"

        if output_format == "id_only":
            return {"notebook_id": notebook_id}

        elif output_format == "full_object":
            return {
                "notebook_id": notebook_id,
                "name": notebook_name,
                "description": self.config.notebook_description,
                "folder_id": self.config.folder_id,
                "tags": self.config.tags or [],
                "source_ids": source_ids,
                "source_count": len(source_ids),
                "status": "created"
            }

        else:  # summary (default)
            return {
                "notebook_id": notebook_id,
                "name": notebook_name,
                "source_count": len(source_ids),
                "status": "created"
            }


# ============================================================================
# Microsite Generator Node Executor
# ============================================================================

class MicrositeGeneratorNodeExecutor(BaseNodeExecutor):
    """
    Execute microsite generator node - create microsites from workflow outputs.

    Supports:
    - Template variable substitution for microsite title/description
    - Auto-creates notebook if not provided
    - Multiple source resolution modes
    - Moderation failure handling
    - Auto-publishing
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute microsite generator node.

        Args:
            state: Contains node_outputs, current_node_id, input_data

        Returns:
            Updated state with microsite creation result
        """
        current_node_id = state.get("current_node_id")
        input_data = state.get("input_data", {})
        context = state.get("node_outputs", {})

        print(f"[MicrositeGeneratorNodeExecutor] Executing node: {current_node_id}")

        try:
            # Step 1: Validate prerequisites
            await self._validate_language_model_configured()
            await self._validate_template_exists()

            # Step 2: Substitute template variables
            microsite_title = self._substitute_variables(
                self.config.microsite_title or "Generated Microsite",
                input_data,
                context
            )
            microsite_description = None
            if self.config.microsite_description:
                microsite_description = self._substitute_variables(
                    self.config.microsite_description,
                    input_data,
                    context
                )

            user_prompt = None
            if self.config.user_prompt:
                user_prompt = self._substitute_variables(
                    self.config.user_prompt,
                    input_data,
                    context
                )

            print(f"[MicrositeGeneratorNodeExecutor] Creating microsite: {microsite_title}")

            # Step 3: Resolve/create notebook
            notebook_id = await self._resolve_or_create_notebook(
                microsite_title,
                input_data,
                context
            )
            auto_created_notebook = self.config.auto_create_notebook and not self.config.notebook_id_template

            # Step 4: Resolve source IDs
            source_ids = await self._resolve_source_ids(notebook_id, state)

            if not source_ids:
                raise ValueError(
                    "No sources found for microsite generation. "
                    "Please provide sources via notebook, explicit IDs, or previous node."
                )

            # Step 5: Create microsite record
            from open_notebook.domain.microsite import Microsite
            microsite = await Microsite.create(
                notebook_id=notebook_id,
                title=microsite_title,
                created_by="workflow"
            )
            if microsite_description:
                microsite.description = microsite_description
                await microsite.save()

            print(f"[MicrositeGeneratorNodeExecutor] Microsite created: {microsite.id}")

            # Step 6: Generate content
            from api.services.microsite_generation_service import get_generation_service
            result = await get_generation_service().generate_microsite(
                microsite_id=microsite.id,
                template_id=self.config.template_id,
                source_ids=source_ids,
                notebook_id=notebook_id,
                user_prompt=user_prompt
            )

            print(f"[MicrositeGeneratorNodeExecutor] Content generated: {result}")

            # Step 7: Check moderation status
            moderation_status = result.get("moderation", {}).get("status", "passed")
            if moderation_status == "blocked":
                fail_on_block = self.config.fail_on_moderation_block
                if fail_on_block is None:
                    fail_on_block = True  # Default to True

                if fail_on_block:
                    raise ValueError(
                        f"Microsite generation blocked by moderation.\n"
                        f"Moderation report: {json.dumps(result.get('moderation', {}), indent=2)}\n"
                        f"To bypass, set fail_on_moderation_block=false in node configuration."
                    )

            # Step 8: Auto-publish if configured
            published = False
            if self.config.auto_publish and moderation_status != "blocked":
                version = result.get("version")
                if version:
                    await microsite.publish(version_id=version)
                    published = True
                    print(f"[MicrositeGeneratorNodeExecutor] Microsite published")

            # Step 9: Format output
            output = self._format_output(
                microsite.id,
                notebook_id,
                auto_created_notebook,
                result,
                published
            )

            print(f"[MicrositeGeneratorNodeExecutor] Execution complete: {output}")

            return {
                **state,
                "node_outputs": {
                    **context,
                    current_node_id: output
                }
            }

        except Exception as e:
            print(f"[MicrositeGeneratorNodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()

            return {
                **state,
                "node_outputs": {
                    **context,
                    current_node_id: {
                        "status": "failed",
                        "error": str(e),
                        "microsite_id": None,
                        "preview_url": None
                    }
                }
            }

    async def _validate_language_model_configured(self):
        """Validate that a language model is configured."""
        from api.services.settings import get_setting

        language_model_id = await get_setting("language_model_id", "")
        if not language_model_id:
            raise ValueError(
                "No language model configured. Please configure a language model "
                "in Settings → Models before generating microsites."
            )

    async def _validate_template_exists(self):
        """Validate that the specified template exists."""
        from open_notebook.database.repository import repo_query

        if not self.config.template_id:
            raise ValueError("template_id is required for microsite generation")

        templates = await repo_query(
            "SELECT id FROM microsite_templates WHERE id = :template_id",
            {"template_id": self.config.template_id}
        )

        if not templates:
            # Get available templates for error message
            available = await repo_query(
                "SELECT id, name FROM microsite_templates ORDER BY name",
                {}
            )
            template_list = ", ".join([f"'{t['id']}' ({t['name']})" for t in available])
            raise ValueError(
                f"Template '{self.config.template_id}' not found. "
                f"Available templates: {template_list}"
            )

    async def _resolve_or_create_notebook(
        self,
        microsite_title: str,
        input_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """
        Resolve notebook ID or create a new notebook if needed.

        Args:
            microsite_title: Microsite title (used as notebook name if auto-creating)
            input_data: Input data
            context: Node outputs context

        Returns:
            Notebook ID
        """
        from open_notebook.domain.notebook import Notebook

        # Try to get notebook_id from template or config
        notebook_id = None
        if self.config.notebook_id_template:
            notebook_id = self._substitute_variables(
                self.config.notebook_id_template,
                input_data,
                context
            )

        # Check if notebook exists
        if notebook_id:
            notebook = await Notebook.get(notebook_id)
            if notebook:
                return notebook_id

        # Auto-create notebook if enabled
        auto_create = self.config.auto_create_notebook
        if auto_create is None:
            auto_create = True  # Default to True

        if auto_create:
            print(f"[MicrositeGeneratorNodeExecutor] Auto-creating notebook: {microsite_title}")
            notebook = Notebook(
                name=microsite_title,
                description=self.config.auto_notebook_description,
                tags=[]
            )
            notebook_id = await notebook.save()
            return notebook_id

        # If not auto-creating and no valid notebook, fail
        raise ValueError(
            "Notebook not found and auto_create_notebook is disabled. "
            "Please provide a valid notebook_id or enable auto_create_notebook."
        )

    async def _resolve_source_ids(self, notebook_id: str, state: Dict[str, Any]) -> list:
        """
        Resolve source IDs based on source_mode.

        Args:
            notebook_id: Notebook ID
            state: Workflow state

        Returns:
            List of source IDs
        """
        from open_notebook.database.repository import repo_query

        source_mode = self.config.microsite_source_mode or "from_notebook"
        context = state.get("node_outputs", {})

        if source_mode == "from_notebook":
            # Query notebook_source junction table
            rows = await repo_query(
                "SELECT source_id FROM notebook_source WHERE notebook_id = :notebook_id",
                {"notebook_id": notebook_id}
            )
            return [row["source_id"] for row in rows]

        elif source_mode == "explicit_ids":
            # Use provided list
            if not self.config.microsite_source_ids:
                raise ValueError(
                    "microsite_source_ids is required when microsite_source_mode is 'explicit_ids'"
                )
            return self.config.microsite_source_ids

        elif source_mode == "from_node":
            # Extract from previous node output
            if not self.config.source_node_id:
                raise ValueError(
                    "source_node_id is required when microsite_source_mode is 'from_node'"
                )

            if self.config.source_node_id not in context:
                raise ValueError(
                    f"Node '{self.config.source_node_id}' not found in previous outputs. "
                    f"Available nodes: {list(context.keys())}"
                )

            output = context[self.config.source_node_id]

            # Try to extract source_ids from output
            if isinstance(output, dict) and "source_ids" in output:
                return output["source_ids"]
            elif isinstance(output, list):
                return output
            else:
                raise ValueError(
                    f"Could not extract source IDs from node '{self.config.source_node_id}'. "
                    f"Expected format: {{'source_ids': [...]}} or [...]. "
                    f"Got: {type(output).__name__}"
                )

        return []

    def _format_output(
        self,
        microsite_id: str,
        notebook_id: str,
        auto_created_notebook: bool,
        result: dict,
        published: bool
    ) -> dict:
        """Format output based on output_format configuration."""
        output_format = self.config.microsite_output_format or "summary"

        preview_url = f"/api/microsites/{microsite_id}/preview"
        status = "published" if published else "draft"

        if output_format == "preview_url":
            return {
                "microsite_id": microsite_id,
                "preview_url": preview_url,
                "status": status
            }

        elif output_format == "full_response":
            return {
                "microsite_id": microsite_id,
                "notebook_id": notebook_id,
                "auto_created_notebook": auto_created_notebook,
                "preview_url": preview_url,
                "status": status,
                "generation_result": result
            }

        else:  # summary (default)
            return {
                "microsite_id": microsite_id,
                "notebook_id": notebook_id,
                "auto_created_notebook": auto_created_notebook,
                "version": result.get("version"),
                "preview_url": preview_url,
                "sections_generated": len(result.get("sections", [])),
                "moderation_status": result.get("moderation", {}).get("status", "passed"),
                "status": status
            }



# ============================================================================
# Human Approval Node Executor
# ============================================================================

class HumanApprovalNodeExecutor(BaseNodeExecutor):
    """
    Executor for human approval nodes.

    Creates an approval request, pauses execution, and waits for user response.
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from open_notebook.domain.workflow_approval import WorkflowApproval
        from datetime import datetime, timedelta
        import uuid
        import json

        # Calculate timeout
        timeout_at = None
        if self.config.timeout_seconds:
            timeout_at = datetime.utcnow() + timedelta(seconds=self.config.timeout_seconds)

        # Create approval request
        approval = WorkflowApproval(
            id=str(uuid.uuid4()),
            workflow_id=state.get("workflow_id"),
            execution_id=state.get("execution_id"),
            node_id=state.get("current_node_id"),
            approval_prompt=self.config.approval_prompt or "Please review and approve",
            approval_options=json.dumps(self.config.approval_options or ["approve", "reject"]),
            required_approvers=json.dumps(self.config.required_approvers) if self.config.required_approvers else None,
            input_data=json.dumps(state.get("node_outputs", {})),
            timeout_seconds=self.config.timeout_seconds,
            timeout_action=self.config.timeout_action,
            timeout_at=timeout_at,
        )
        await approval.save()

        # Send notification to required approvers
        try:
            from api.services.notification_service import notify_approval_pending
            from open_notebook.domain.workflow import Workflow

            workflow = await Workflow.get(state.get("workflow_id"))
            workflow_name = workflow.name if workflow else "Unknown Workflow"

            required_approvers = self.config.required_approvers or []
            for user_id in required_approvers:
                await notify_approval_pending(
                    user_id=user_id,
                    workflow_name=workflow_name,
                    execution_id=state.get("execution_id"),
                    approval_id=approval.id,
                    node_name=self.config.label or "Approval Node"
                )
        except Exception as e:
            # Don't fail execution if notification fails
            import logging
            logging.error(f"Failed to send approval notification: {e}")

        # Store the approval output in state (will be saved by workflow engine)
        state["node_outputs"][state["current_node_id"]] = {
            "status": "awaiting_approval",
            "approval_id": approval.id
        }

        # Set paused flag to stop graph execution
        state["paused"] = True
        state["approval_id"] = approval.id

        # Raise a special exception to stop LangGraph execution
        # The workflow engine will handle the pause
        from open_notebook.agents.workflow_engine import WorkflowPausedException
        raise WorkflowPausedException(
            execution_id=state["execution_id"],
            approval_id=approval.id,
            message="Workflow paused for human approval"
        )


# ============================================================================
# Workspace Node Executor
# ============================================================================

class WorkspaceNodeExecutor(BaseNodeExecutor):
    """
    Executor for workspace template nodes.

    Instantiates and executes a workspace template.
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from api.services.template_instantiation_service import get_template_instantiation_service

        service = get_template_instantiation_service()

        # Instantiate template
        workspace_id = await service.instantiate_template(
            template_id=self.config.workspace_template_id,
            parameters=self.config.workspace_parameters or {},
            user_id=state.get("user_id", "default-user")
        )

        # Optionally wait for completion
        result = {"workspace_id": workspace_id, "status": "created"}

        if self.config.wait_for_completion:
            # TODO: Implement workspace completion check
            # For now, just return the workspace_id
            result["status"] = "completed"

        return {
            **state,
            "node_outputs": {
                **state.get("node_outputs", {}),
                state["current_node_id"]: result
            }
        }


# ============================================================================
# Template Node Executor
# ============================================================================

class TemplateNodeExecutor(BaseNodeExecutor):
    """
    Executor for workflow template nodes.

    Instantiates and executes a nested workflow template.
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        # Import here to avoid circular dependency
        from api.services.workflow_template_service import get_workflow_template_service

        service = get_workflow_template_service()

        # Instantiate template
        workflow_id = await service.instantiate_template(
            template_id=self.config.template_id,
            parameters=self.config.template_parameters or {},
            user_id=state.get("user_id", "default-user")
        )

        # Execute nested workflow if wait_for_completion is true
        result = {"workflow_id": workflow_id, "status": "created"}

        if self.config.wait_for_completion:
            from open_notebook.domain.workflow import Workflow
            from open_notebook.agents.workflow_engine import WorkflowEngine

            workflow = await Workflow.get(workflow_id)
            engine = WorkflowEngine(workflow)
            execution = await engine.execute()

            result = {
                "workflow_id": workflow_id,
                "execution_id": execution.id,
                "status": execution.status.value,
                "output": execution.final_output
            }

        return {
            **state,
            "node_outputs": {
                **state.get("node_outputs", {}),
                state["current_node_id"]: result
            }
        }


# ============================================================================
# Delay Node Executor
# ============================================================================

class DelayNodeExecutor(BaseNodeExecutor):
    """
    Executor for delay nodes.

    Pauses execution for a specified duration.
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        import asyncio

        # Determine delay duration
        delay = 0

        if self.config.delay_seconds:
            delay = self.config.delay_seconds
        elif self.config.delay_expression:
            # Extract delay from data using JSONPath
            try:
                import jsonpath_ng
                parser = jsonpath_ng.parse(self.config.delay_expression)
                matches = parser.find(state.get("node_outputs", {}))
                delay = matches[0].value if matches else 0
            except ImportError:
                print("[DelayNodeExecutor] jsonpath_ng not installed, using default delay of 0")
            except Exception as e:
                print(f"[DelayNodeExecutor] Error parsing JSONPath: {e}")

        # Sleep for delay duration
        if delay > 0:
            await asyncio.sleep(delay)

        return {
            **state,
            "node_outputs": {
                **state.get("node_outputs", {}),
                state["current_node_id"]: {
                    "delayed_seconds": delay
                }
            }
        }


# ============================================================================
# Webhook Node Executor
# ============================================================================

class WebhookNodeExecutor(BaseNodeExecutor):
    """
    Executor for webhook nodes.

    Sends HTTP request to external system.
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        import httpx
        from jinja2 import Template

        # Render body template with state data
        body = None
        if self.config.webhook_body_template:
            template = Template(self.config.webhook_body_template)
            body_str = template.render(state)
            try:
                body = json.loads(body_str)
            except json.JSONDecodeError:
                # If not JSON, send as text
                body = body_str

        # Prepare headers
        headers = self.config.webhook_headers or {}
        if body and isinstance(body, dict):
            headers["Content-Type"] = "application/json"

        # Add authentication
        if self.config.webhook_auth_type == "bearer" and self.config.webhook_auth_token:
            headers["Authorization"] = f"Bearer {self.config.webhook_auth_token}"
        elif self.config.webhook_auth_type == "basic" and self.config.webhook_auth_token:
            # Assuming auth_token is "username:password"
            import base64
            encoded = base64.b64encode(self.config.webhook_auth_token.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        # Send HTTP request
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if self.config.webhook_method == "GET":
                    response = await client.get(self.config.webhook_url, headers=headers)
                elif self.config.webhook_method == "POST":
                    response = await client.post(
                        self.config.webhook_url,
                        headers=headers,
                        json=body if isinstance(body, dict) else None,
                        content=body if isinstance(body, str) else None
                    )
                elif self.config.webhook_method == "PUT":
                    response = await client.put(
                        self.config.webhook_url,
                        headers=headers,
                        json=body if isinstance(body, dict) else None,
                        content=body if isinstance(body, str) else None
                    )

                response.raise_for_status()

                # Parse response
                response_data = None
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    response_data = response.json()
                else:
                    response_data = response.text

                return {
                    **state,
                    "node_outputs": {
                        **state.get("node_outputs", {}),
                        state["current_node_id"]: {
                            "status_code": response.status_code,
                            "response": response_data
                        }
                    }
                }

        except httpx.HTTPError as e:
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "error": str(e),
                        "status_code": getattr(e.response, "status_code", None) if hasattr(e, "response") else None
                    }
                },
                "error": f"Webhook request failed: {str(e)}"
            }


# ============================================================================
# Executor Factory
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
        NodeType.HUMAN_APPROVAL: HumanApprovalNodeExecutor,
        NodeType.WORKSPACE: WorkspaceNodeExecutor,
        NodeType.TEMPLATE: TemplateNodeExecutor,
        NodeType.DELAY: DelayNodeExecutor,
        NodeType.WEBHOOK: WebhookNodeExecutor,
    }

    executor_class = executors.get(node_type)
    if not executor_class:
        raise ValueError(f"Unknown node type: {node_type}")

    return executor_class(config)
