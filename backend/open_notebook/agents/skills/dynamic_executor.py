"""
Dynamic Skill Executor for database-stored skills.

Interprets skill definitions based on skill_type and executes them.
Supports: prompt_template, tool_chain, workflow, custom
"""

import json
import logging
import importlib
from typing import Any, Dict, List, Optional

from open_notebook.agents.skills.base import SkillContext
from open_notebook.database.repository import repo_query

logger = logging.getLogger(__name__)


class DynamicSkillExecutor:
    """
    Executes database-stored skills by interpreting their definitions.

    Supports four skill types:
    1. prompt_template - LLM calls with variable substitution
    2. tool_chain - Sequential tool execution with data flow
    3. workflow - LangGraph-based branching workflows
    4. custom - Dynamic Python module imports
    """

    def __init__(self):
        """Initialize dynamic skill executor."""
        self._allowed_custom_modules = [
            "my_custom_skills.",
            "open_notebook.custom_skills.",
        ]

    async def execute_dynamic_skill(
        self,
        skill_id: str,
        context: SkillContext
    ) -> Dict[str, Any]:
        """
        Load skill from database and execute based on skill_type.

        Args:
            skill_id: ID of skill to execute
            context: SkillContext with input_data and resources

        Returns:
            Dict with execution results

        Raises:
            ValueError: If skill not found or unknown skill_type
        """
        # Load skill from database
        rows = await repo_query(
            "SELECT * FROM agent_skills WHERE id = :id AND enabled = 1",
            {"id": skill_id}
        )

        if not rows:
            raise ValueError(f"Skill not found or disabled: {skill_id}")

        skill_row = rows[0]
        skill_name = skill_row["name"]
        skill_type = skill_row["skill_type"]
        definition = json.loads(skill_row["definition"])

        logger.info(f"Executing dynamic skill: {skill_name} ({skill_type})")

        context.record_step(
            "skill_start",
            f"Starting {skill_type} skill: {skill_name}",
            status="running",
            metadata={"skill_id": skill_id, "skill_type": skill_type}
        )

        # Execute based on type
        try:
            if skill_type == "prompt_template":
                result = await self._execute_prompt_template(context, definition)
            elif skill_type == "tool_chain":
                result = await self._execute_tool_chain(context, definition)
            elif skill_type == "workflow":
                result = await self._execute_workflow(context, definition)
            elif skill_type == "custom":
                result = await self._execute_custom(context, definition)
            else:
                raise ValueError(f"Unknown skill_type: {skill_type}")

            context.record_step(
                "skill_complete",
                f"Skill {skill_name} completed successfully",
                status="completed"
            )

            return result

        except Exception as e:
            context.record_step(
                "skill_error",
                f"Skill {skill_name} failed: {str(e)}",
                status="error"
            )
            raise

    async def _execute_prompt_template(
        self,
        context: SkillContext,
        definition: Dict
    ) -> Dict[str, Any]:
        """
        Execute prompt_template skill.

        Definition format:
        {
            "template": "Analyze {data} and provide {analysis_type} insights",
            "variables": [
                {"name": "data", "type": "text", "required": true},
                {"name": "analysis_type", "type": "string", "required": true}
            ],
            "system_prompt": "You are an expert analyst",
            "model": "claude-3-5-sonnet",
            "temperature": 0.7,
            "max_tokens": 2000
        }

        Args:
            context: SkillContext with input_data
            definition: Skill definition from database

        Returns:
            Dict with LLM response
        """
        context.record_step(
            "prompt_template",
            "Building prompt from template",
            status="running"
        )

        # Extract template and variables
        template = definition["template"]
        variables = definition.get("variables", [])

        # Substitute variables
        prompt_vars = {}
        for var in variables:
            var_name = var["name"]
            value = context.input_data.get(var_name)

            # Handle required variables
            if var.get("required", False) and value is None:
                raise ValueError(f"Required variable '{var_name}' not provided")

            # Use default if not provided
            if value is None:
                value = var.get("default", "")

            # Type coercion
            var_type = var.get("type", "string")
            if var_type == "array" and isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            elif var_type == "json":
                value = json.dumps(value)

            prompt_vars[var_name] = value

        # Format template
        try:
            prompt = template.format(**prompt_vars)
        except KeyError as e:
            raise ValueError(f"Template variable not found: {e}")

        context.record_step(
            "prompt_generated",
            f"Generated prompt ({len(prompt)} chars)",
            status="completed",
            metadata={"prompt_length": len(prompt)}
        )

        # Get LLM config
        model = definition.get("model", "claude-3-5-sonnet")
        temperature = definition.get("temperature", 0.7)
        max_tokens = definition.get("max_tokens", 2000)
        system_prompt = definition.get("system_prompt")

        # Call LLM
        context.record_step(
            "llm_call",
            f"Calling LLM: {model}",
            status="running"
        )

        if not context.llm:
            raise ValueError("LLM not available in context")

        # Build messages
        messages = [{"role": "user", "content": prompt}]

        # Call LLM (supports various LLM providers via Esperanto)
        response = await context.llm.ainvoke(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system=system_prompt
        )

        context.record_step(
            "llm_response",
            f"Received LLM response ({len(response.content)} chars)",
            status="completed"
        )

        return {
            "output": response.content,
            "prompt_used": prompt,
            "model": model,
            "metadata": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "variables": prompt_vars
            }
        }

    async def _execute_tool_chain(
        self,
        context: SkillContext,
        definition: Dict
    ) -> Dict[str, Any]:
        """
        Execute tool_chain skill.

        Definition format:
        {
            "tools": [
                {
                    "tool_id": "hana_query",
                    "input_mapping": {
                        "source_id": "{input.source_id}",
                        "query": "{input.query}"
                    },
                    "output_key": "query_results"
                },
                {
                    "tool_id": "chart_generator",
                    "input_mapping": {
                        "data": "{steps.query_results.rows}",
                        "chart_type": "bar"
                    },
                    "output_key": "chart"
                }
            ],
            "flow": {
                "type": "sequential",
                "on_error": "stop",
                "return": "{steps.chart.url}"
            }
        }

        Args:
            context: SkillContext with tool_registry
            definition: Skill definition from database

        Returns:
            Dict with tool chain results
        """
        tools = definition.get("tools", [])
        flow = definition.get("flow", {})
        flow_type = flow.get("type", "sequential")
        on_error = flow.get("on_error", "stop")
        return_template = flow.get("return", "{steps}")

        context.record_step(
            "tool_chain_start",
            f"Executing {len(tools)} tools in {flow_type} mode",
            status="running"
        )

        # Store results from each step
        step_results = {}

        # Execute tools
        for i, tool_spec in enumerate(tools):
            tool_id = tool_spec["tool_id"]
            input_mapping = tool_spec.get("input_mapping", {})
            output_key = tool_spec.get("output_key", f"step_{i}")

            context.record_step(
                "tool_call",
                f"Executing tool: {tool_id}",
                status="running",
                metadata={"tool_id": tool_id, "step": i + 1}
            )

            # Resolve input mapping
            tool_input = {}
            for key, value_template in input_mapping.items():
                try:
                    tool_input[key] = self._resolve_template(
                        value_template,
                        context.input_data,
                        step_results
                    )
                except Exception as e:
                    raise ValueError(
                        f"Error resolving input mapping for {key}: {str(e)}"
                    )

            # Get tool from registry
            tool = context.get_tool(tool_id)
            if not tool:
                raise ValueError(f"Tool not found: {tool_id}")

            # Execute tool
            try:
                tool_result = await tool.execute(tool_input)
                step_results[output_key] = tool_result

                context.record_step(
                    "tool_result",
                    f"Tool {tool_id} completed",
                    status="completed",
                    metadata={"output_key": output_key}
                )
            except Exception as e:
                context.record_step(
                    "tool_error",
                    f"Tool {tool_id} failed: {str(e)}",
                    status="error"
                )

                if on_error == "stop":
                    raise
                elif on_error == "continue":
                    step_results[output_key] = {"error": str(e)}

        # Extract final result
        final_result = self._resolve_template(
            return_template,
            context.input_data,
            step_results
        )

        context.record_step(
            "tool_chain_complete",
            f"Tool chain completed with {len(step_results)} steps",
            status="completed"
        )

        return {
            "output": final_result,
            "steps": step_results,
            "metadata": {
                "flow_type": flow_type,
                "tools_executed": len(tools)
            }
        }

    def _resolve_template(
        self,
        template: Any,
        input_data: Dict,
        step_results: Dict
    ) -> Any:
        """
        Resolve template variables like {input.field} or {steps.step_name.field}.

        Args:
            template: Template string or value
            input_data: Input data from context
            step_results: Results from previous steps

        Returns:
            Resolved value
        """
        if not isinstance(template, str):
            return template

        # Handle {input.field}
        if template.startswith("{input."):
            field = template[7:-1]  # Extract field name
            parts = field.split(".")
            result = input_data
            for part in parts:
                if isinstance(result, dict):
                    result = result.get(part)
                else:
                    return None
            return result

        # Handle {steps.step_name.field}
        if template.startswith("{steps."):
            path = template[7:-1].split(".")  # ["step_name", "field", ...]
            result = step_results
            for key in path:
                if isinstance(result, dict):
                    result = result.get(key)
                else:
                    return None
            return result

        # Handle {steps} (return all steps)
        if template == "{steps}":
            return step_results

        # Not a template, return as-is
        return template

    async def _execute_workflow(
        self,
        context: SkillContext,
        definition: Dict
    ) -> Dict[str, Any]:
        """
        Execute workflow skill using LangGraph.

        Definition format:
        {
            "nodes": [
                {"id": "start", "type": "input"},
                {"id": "process", "type": "tool", "tool_id": "analyzer"},
                {"id": "check", "type": "condition", "condition": "{process.score} > 0.8"},
                {"id": "end", "type": "output", "return": "{process.result}"}
            ],
            "edges": [
                {"from": "start", "to": "process"},
                {"from": "process", "to": "check"},
                {"from": "check", "to": "end", "condition": "true"}
            ]
        }

        Args:
            context: SkillContext
            definition: Skill definition from database

        Returns:
            Dict with workflow results
        """
        context.record_step(
            "workflow_start",
            "Building LangGraph workflow",
            status="running"
        )

        try:
            from langgraph.graph import StateGraph, END
        except ImportError:
            raise ValueError(
                "LangGraph not installed. Install with: pip install langgraph"
            )

        nodes = definition.get("nodes", [])
        edges = definition.get("edges", [])
        max_iterations = definition.get("max_iterations", 10)

        # Build state schema
        class WorkflowState(dict):
            """State container for workflow execution."""
            pass

        # Create graph
        graph = StateGraph(WorkflowState)

        # Add nodes
        node_funcs = {}
        for node in nodes:
            node_id = node["id"]
            node_type = node["type"]

            if node_type == "input":
                # Input node just passes data
                def input_func(state):
                    return {"input": context.input_data}
                node_funcs[node_id] = input_func

            elif node_type == "tool":
                # Tool execution node
                tool_id = node["tool_id"]
                tool_input_mapping = node.get("input", {})

                async def tool_func(state, tid=tool_id, mapping=tool_input_mapping):
                    tool = context.get_tool(tid)
                    if not tool:
                        raise ValueError(f"Tool not found: {tid}")

                    tool_input = {}
                    for key, value_template in mapping.items():
                        tool_input[key] = self._resolve_template(
                            value_template,
                            context.input_data,
                            state
                        )

                    result = await tool.execute(tool_input)
                    return {node_id: result}

                node_funcs[node_id] = tool_func

            elif node_type == "output":
                # Output node extracts final result
                return_template = node.get("return", "{input}")

                def output_func(state, template=return_template):
                    result = self._resolve_template(
                        template,
                        context.input_data,
                        state
                    )
                    return {"output": result}

                node_funcs[node_id] = output_func

            # Add node to graph
            if node_id not in ["start", "end"]:
                graph.add_node(node_id, node_funcs[node_id])

        # Add edges
        for edge in edges:
            from_node = edge["from"]
            to_node = edge["to"]

            if "condition" in edge:
                # Conditional edge
                condition_value = edge["condition"]

                def condition_func(state, cond=condition_value):
                    # Simple condition evaluation
                    return cond == "true"

                graph.add_conditional_edges(
                    from_node,
                    condition_func,
                    {True: to_node, False: END}
                )
            else:
                # Regular edge
                if to_node == "end":
                    graph.add_edge(from_node, END)
                else:
                    graph.add_edge(from_node, to_node)

        # Set entry point
        graph.set_entry_point(nodes[0]["id"])

        # Compile and execute
        app = graph.compile()

        context.record_step(
            "workflow_execute",
            "Executing workflow graph",
            status="running"
        )

        result = await app.ainvoke(
            {"input": context.input_data},
            {"recursion_limit": max_iterations}
        )

        context.record_step(
            "workflow_complete",
            "Workflow completed successfully",
            status="completed"
        )

        return {
            "output": result.get("output"),
            "state": result,
            "metadata": {
                "nodes_executed": len(nodes),
                "max_iterations": max_iterations
            }
        }

    async def _execute_custom(
        self,
        context: SkillContext,
        definition: Dict
    ) -> Dict[str, Any]:
        """
        Execute custom skill by dynamically importing Python module.

        Definition format:
        {
            "module": "my_custom_skills.advanced_analytics",
            "function": "run_advanced_analysis",
            "config": {
                "algorithm": "kmeans",
                "n_clusters": 5
            }
        }

        Args:
            context: SkillContext
            definition: Skill definition from database

        Returns:
            Dict with custom function results
        """
        module_name = definition.get("module")
        function_name = definition.get("function")
        config = definition.get("config", {})

        if not module_name or not function_name:
            raise ValueError("Custom skill requires 'module' and 'function' fields")

        context.record_step(
            "custom_import",
            f"Importing {module_name}.{function_name}",
            status="running"
        )

        # Security: Only allow whitelisted modules
        if not any(module_name.startswith(prefix) for prefix in self._allowed_custom_modules):
            raise ValueError(
                f"Module not in whitelist: {module_name}. "
                f"Allowed prefixes: {self._allowed_custom_modules}"
            )

        # Import module
        try:
            module = importlib.import_module(module_name)
            func = getattr(module, function_name)
        except ImportError as e:
            raise ValueError(f"Failed to import module {module_name}: {str(e)}")
        except AttributeError:
            raise ValueError(f"Function {function_name} not found in {module_name}")

        context.record_step(
            "custom_execute",
            f"Executing {function_name}",
            status="running"
        )

        # Execute custom function
        result = await func(context, config)

        context.record_step(
            "custom_complete",
            "Custom function completed",
            status="completed"
        )

        return result


# Global singleton
_executor: Optional[DynamicSkillExecutor] = None


def get_dynamic_skill_executor() -> DynamicSkillExecutor:
    """
    Get global dynamic skill executor instance.

    Returns:
        Singleton DynamicSkillExecutor instance
    """
    global _executor
    if _executor is None:
        _executor = DynamicSkillExecutor()
    return _executor
