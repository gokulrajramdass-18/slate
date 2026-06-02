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

from open_notebook.domain.workflow import NodeConfig, NodeType, NodeExecutionState, ExecutionStatus
from open_notebook.agents.messaging import MessageBus
from open_notebook.agents.task_manager import TaskManager
from open_notebook.agents.agent_manager import get_agent_class


# Sentinel returned by direct lookups when a {{...}} reference resolves to nothing.
# Distinct from None because None is a legitimate resolved value.
_SENTINEL_UNRESOLVED = object()


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

    def _lookup_variable(
        self,
        var_name: str,
        input_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Any:
        """Resolve ``{{var}}``-style reference to its raw Python value.

        Returns the value (which may be a dict, list, str, etc.) without
        stringifying it and without applying the SQL-injection screen — the
        screen belongs at SQL boundaries, not at every variable lookup. Use
        this when you need to feed an upstream node's output into something
        that expects native types (e.g. jq input).

        Returns ``_SENTINEL_UNRESOLVED`` when the path can't be resolved so
        callers can distinguish "missing" from "resolved to None".
        """
        if "." in var_name:
            parts = var_name.split(".")
            head, rest = parts[0], parts[1:]

            def _walk(start: Any) -> Any:
                current = start
                for part in rest:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return _SENTINEL_UNRESOLVED
                return current

            if head in input_data:
                walked = _walk(input_data[head])
                if walked is not _SENTINEL_UNRESOLVED:
                    return walked
            if head in context:
                walked = _walk(context[head])
                if walked is not _SENTINEL_UNRESOLVED:
                    return walked
            # Try walking the full path inside each top-level node output
            for node_output in context.values():
                if isinstance(node_output, dict):
                    current = node_output
                    ok = True
                    for part in parts:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            ok = False
                            break
                    if ok:
                        return current
            return _SENTINEL_UNRESOLVED

        if var_name in input_data:
            return input_data[var_name]
        if var_name in context:
            return context[var_name]
        for node_output in context.values():
            if isinstance(node_output, dict) and var_name in node_output:
                return node_output[var_name]
        return _SENTINEL_UNRESOLVED

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
        context: Dict[str, Any],
        sql_context: bool = False,
    ) -> str:
        """
        Substitute {{variable}} placeholders with actual values.
        Supports dot notation for nested access (e.g., {{summary.modified}})

        Args:
            template: Template string with {{var}} placeholders
            input_data: Input data from input node
            context: Previous node outputs
            sql_context: When True, apply the SQL-injection guard to substituted
                values. Only enable for values that will be concatenated into
                SQL — LLM prompts, email bodies, webhook payloads, etc. are
                free-form text and should not trip the guard.

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

                # Try direct lookup: first check if first part is in input_data
                # (covers ForEach iteration variables like {{item.CAMPAIGN_ID}}, {{index}}, etc.)
                if parts[0] in input_data:
                    current = input_data[parts[0]]
                    found = True
                    for part in parts[1:]:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            found = False
                            break
                    if found:
                        value = current
                # Then check if first part is a top-level key in context
                elif parts[0] in context:
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
                raise ValueError(
                    f"Variable {{{{{var_name}}}}} could not be resolved from input_data or node outputs"
                )

            # Format value based on type
            if isinstance(value, (dict, list)):
                # Pretty print JSON for complex types
                import json
                formatted_value = json.dumps(value, indent=2)
            else:
                formatted_value = str(value)

            # Reject empty resolved values (e.g. "", "   ") — they almost always
            # indicate a misconfigured upstream node and produce broken SQL/URLs.
            if formatted_value.strip() == "":
                raise ValueError(
                    f"Variable {{{{{var_name}}}}} resolved to an empty value"
                )

            # Lightweight SQL-injection screen on substituted values. Only
            # applied when the caller declared this substitution targets SQL —
            # otherwise legitimate punctuation in LLM/email/webhook content
            # (e.g. ';' inside JSON or prose) would be rejected.
            if sql_context:
                self._reject_if_sql_injection(var_name, formatted_value)

            # Replace placeholder with value
            result = result.replace(f"{{{{{var_name}}}}}", formatted_value)

        return result

    @staticmethod
    def _reject_if_sql_injection(var_name: str, value: str) -> None:
        """Raise ValueError if `value` looks like a SQL-injection payload.

        Heuristic, not a substitute for parameterized queries — we still want
        to fail loudly when an upstream node produces something like
        `' OR 1=1 --` so it never lands in a query.
        """
        import re

        lowered = value.lower()
        # Comment markers and statement terminators
        if "--" in value or "/*" in value or "*/" in value:
            raise ValueError(
                f"Variable {{{{{var_name}}}}} contains SQL comment markers; rejected as potential injection"
            )
        if ";" in value:
            raise ValueError(
                f"Variable {{{{{var_name}}}}} contains ';'; rejected as potential injection"
            )
        # Classic boolean-bypass patterns and stacked-statement keywords.
        # Word-boundary match so we don't flag legitimate text like "or" inside a name.
        injection_patterns = [
            r"\bunion\s+select\b",
            r"\bor\s+1\s*=\s*1\b",
            r"\band\s+1\s*=\s*1\b",
            r"\bdrop\s+table\b",
            r"\bdelete\s+from\b",
            r"\binsert\s+into\b",
            r"\bupdate\s+\S+\s+set\b",
            r"\bexec(?:ute)?\s*\(",
            r"\bxp_cmdshell\b",
        ]
        for pat in injection_patterns:
            if re.search(pat, lowered):
                raise ValueError(
                    f"Variable {{{{{var_name}}}}} matches SQL-injection pattern '{pat}'; rejected"
                )


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
        from api.services.llm_client import call_llm_chat

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

        # Resolve credential the same way chat does. Prefer the model the node
        # was configured with; fall back to the global language_model_id setting.
        # Going through llm_client.call_llm_chat means sap_ai_core deployments
        # hit POST /chat on the standalone proxy (chat_sap_ai_core_sdk path),
        # while other providers go through the OpenAI-compatible /chat/completions.
        # This is the same branching the rest of the app uses — see
        # backend/api/services/llm_client.py.
        configured_model_id = self.config.model_name
        credential: Optional[Dict[str, Any]] = None
        if configured_model_id and len(configured_model_id) == 36 and configured_model_id.count('-') == 4:
            credential = _credentials_store.get(configured_model_id)

        if credential is None:
            language_model_id = await get_setting("language_model_id", "")
            if language_model_id:
                credential = _credentials_store.get(language_model_id)

        if credential is None:
            raise RuntimeError(
                "LLM node has no usable credential: configure a model on the node "
                "or set a default in Settings -> Models."
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Call LLM via the shared helper
        try:
            result = await call_llm_chat(
                credential,
                messages,
                temperature=self.config.temperature if self.config.temperature is not None else 0.7,
                max_tokens=self.config.max_tokens or 4096,
            )

            return {
                **state,
                "node_outputs": {
                    **node_outputs,
                    state["current_node_id"]: {
                        "text": result,
                        "model": credential.get("model_name") or self.config.model_name,
                    }
                }
            }
        except Exception as e:
            # Surface the LLM failure to the workflow engine so the node is
            # marked FAILED and downstream nodes don't blindly try to read
            # {{node.text}} (which would only re-fail with a confusing
            # "variable could not be resolved" message). Other executors
            # in this file (api, hana_table, email) follow the same
            # raise-on-error contract — see workflow_engine.py:460.
            print(f"[LLMNodeExecutor] Error: {e}")
            raise RuntimeError(f"LLM call failed: {e}") from e


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

        # Parse field path (e.g., "previous-node.status").
        # If unconfigured, evaluated value is None — _evaluate_condition handles that.
        if not field_path:
            value = None
        elif "." in field_path:
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
            return self._loose_equals(value, comparison_value)
        elif condition_type == "not_equals":
            return not self._loose_equals(value, comparison_value)
        elif condition_type == "contains":
            if comparison_value is None or value is None:
                return False
            return str(comparison_value) in str(value)
        elif condition_type in ("greater_than", "less_than"):
            try:
                if condition_type == "greater_than":
                    return float(value) > float(comparison_value)
                return float(value) < float(comparison_value)
            except (TypeError, ValueError):
                return False
        else:
            # Unknown or unconfigured — default to False
            return False

    @staticmethod
    def _loose_equals(value: Any, comparison_value: Any) -> bool:
        """Equality that tolerates the UI's string-typed comparison values.

        The PropertyPanel collects `comparison_value` as a string, but upstream
        node outputs are typed (bool/int/float/None). Direct `==` would say
        `True == "true"` is False. Coerce common scalar pairs before comparing,
        falling back to strict `==` when no sensible coercion applies.
        """
        if value == comparison_value:
            return True
        if value is None or comparison_value is None:
            return value is None and comparison_value is None
        if isinstance(value, bool) or isinstance(comparison_value, bool):
            def to_bool(v: Any):
                if isinstance(v, bool):
                    return v
                if isinstance(v, str):
                    s = v.strip().lower()
                    if s in ("true", "1", "yes"):
                        return True
                    if s in ("false", "0", "no", ""):
                        return False
                return None
            b1, b2 = to_bool(value), to_bool(comparison_value)
            if b1 is not None and b2 is not None:
                return b1 == b2
        if isinstance(value, (int, float)) and isinstance(comparison_value, str):
            try:
                return float(value) == float(comparison_value)
            except ValueError:
                pass
        if isinstance(comparison_value, (int, float)) and isinstance(value, str):
            try:
                return float(value) == float(comparison_value)
            except ValueError:
                pass
        return str(value) == str(comparison_value)


# ============================================================================
# Agent Node Executor
# ============================================================================

class AgentNodeExecutor(BaseNodeExecutor):
    """Execute agent node — invoke a standalone agent or a legacy registered agent."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        agent_type = self.config.agent_type
        agent_id = self.config.agent_id
        agent_name = self.config.agent_name
        prompt = self.config.prompt or ""

        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})
        current_node_id = state["current_node_id"]

        # Build the user query. If `prompt` is set use it (with substitution).
        # Otherwise, fall back to the workflow's input_data (most common shape:
        # input node feeds the agent directly), serialized to a readable string.
        if prompt:
            user_query = self._substitute_variables(prompt, input_data, node_outputs)
        elif input_data:
            user_query = (
                input_data.get("query")
                or input_data.get("prompt")
                or input_data.get("text")
                or json.dumps(input_data, indent=2, default=str)
            )
        else:
            user_query = "Please proceed with your analysis based on the available context."

        # ---------- Standalone-agent path (DB-backed agent record) ----------
        if agent_type == "standalone" and agent_id:
            try:
                from open_notebook.database.repository import repo_query
                from api.services.settings import get_setting
                from api.routers.credentials import _credentials_store

                rows = await repo_query(
                    "SELECT * FROM standalone_agents WHERE id = :id AND status = 'active'",
                    {"id": agent_id},
                )
                if not rows:
                    raise RuntimeError(f"Standalone agent not found or inactive: {agent_id}")
                agent_row = rows[0]

                system_prompt = agent_row.get("system_prompt") or f"You are a helpful {agent_row.get('role') or 'assistant'}."

                # Resolve model: agent override → workspace default
                language_model_id = await get_setting("language_model_id", "")
                model_id = agent_row.get("model_name") or language_model_id
                credential = _credentials_store.get(model_id) if model_id else None
                if not credential and language_model_id:
                    credential = _credentials_store.get(language_model_id)
                if not credential:
                    raise RuntimeError(
                        "No LLM credential resolved for agent — set a default model in Settings → Models."
                    )

                # Optional config overrides on the agent row
                cfg_raw = agent_row.get("config")
                cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else (cfg_raw or {})
                temperature = float(cfg.get("temperature", self.config.temperature or 0.3))
                max_tokens = int(cfg.get("max_tokens", self.config.max_tokens or 2000))

                import httpx
                payload = {
                    "model": credential["model_name"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_query},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                }
                endpoint = f"{credential['base_url'].rstrip('/')}/chat/completions"
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {credential['api_key']}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    if resp.status_code != 200:
                        raise RuntimeError(f"LLM API {resp.status_code}: {resp.text[:500]}")
                    data = resp.json()

                text = ""
                try:
                    text = data["choices"][0]["message"]["content"] or ""
                except (KeyError, IndexError, TypeError):
                    text = json.dumps(data)[:2000]

                return {
                    **state,
                    "node_outputs": {
                        **node_outputs,
                        current_node_id: {
                            "agent_type": "standalone",
                            "agent_id": agent_id,
                            "agent_name": agent_name or agent_row.get("name"),
                            "text": text,
                            "result": text,
                        },
                    },
                }

            except Exception as e:
                print(f"[AgentNodeExecutor] standalone agent error: {e}")
                import traceback
                traceback.print_exc()
                raise

        # ---------- Legacy registered-agent path ----------
        agent_class = get_agent_class(agent_type) if agent_type else None
        if not agent_class:
            raise RuntimeError(
                f"Agent node misconfigured: agent_type='{agent_type}' agent_id='{agent_id}'. "
                f"Set agent_type='standalone' and pick an agent in the property panel."
            )

        try:
            agent = agent_class(
                name=agent_name or agent_type,
                user_id=state.get("user_id", "system"),
            )
            result = await agent.execute(user_query)
            return {
                **state,
                "node_outputs": {
                    **node_outputs,
                    current_node_id: {
                        "agent_type": agent_type,
                        "result": result,
                    },
                },
            }
        except Exception as e:
            print(f"[AgentNodeExecutor] legacy agent error: {e}")
            import traceback
            traceback.print_exc()
            raise


# ============================================================================
# Notebook Generator Node Executor
# ============================================================================

class NotebookGeneratorNodeExecutor(BaseNodeExecutor):
    """Execute notebook generator node - create workspace from sources."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate notebook/workspace."""
        from open_notebook.domain.notebook import Notebook, Source

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
                name=notebook_name or "Generated Notebook",
                description=notebook_description,
                folder_id=folder_id,
                tags=tags
            )
            await notebook.save()

            # Handle source mode — accept legacy ("extract" | "existing") and
            # workflow-template values ("create_from_content" | ...).
            source_mode = self.config.source_mode

            if source_mode in ("extract", "create_from_content"):
                # Extract content from previous node output
                content_source_node_id = self.config.content_source_node_id
                if content_source_node_id and content_source_node_id in node_outputs:
                    content = node_outputs[content_source_node_id]

                    extraction_mode = self.config.content_extraction_mode
                    if extraction_mode == "field":
                        field_path = self.config.content_extraction_path
                        if field_path and isinstance(content, dict):
                            content = content.get(field_path, content)
                    elif extraction_mode == "full_output" and isinstance(content, dict):
                        # Prefer the LLM "text" field if present; else dump whole dict
                        content = content.get("text", content)

                    source_title = self.config.source_title_template or "Extracted Content"
                    source_title = self._substitute_variables(source_title, input_data, node_outputs)

                    source = Source(
                        title=source_title,
                        source_type=self.config.source_type or "text",
                        full_text=content if isinstance(content, str) else json.dumps(content),
                    )
                    await source.save()
                    await notebook.add_source(source.id)

            elif source_mode == "existing":
                # Link existing sources to notebook via junction table
                existing_source_ids = self.config.existing_source_ids or []
                for source_id in existing_source_ids:
                    await notebook.add_source(source_id)

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
            # Surface failure to the engine so the node is marked FAILED and
            # downstream nodes don't read ghost outputs. See LLMNodeExecutor.
            raise RuntimeError(f"Notebook generator failed: {e}") from e


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
                from open_notebook.domain.notebook import Source
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
            raise RuntimeError(f"Microsite generator failed: {e}") from e


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
            raise RuntimeError(f"Presentation generator failed: {e}") from e


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

            # Broadcast notification so the user sees a popup/toast
            try:
                from api.services.notification_service import notify_approval_pending
                from open_notebook.database.repository import repo_query

                workflow_name = "Workflow"
                node_label = state.get("current_node_id") or "Approval"
                try:
                    rows = await repo_query(
                        "SELECT name, graph_json FROM workflows WHERE id = :id",
                        {"id": workflow_id},
                    )
                    if rows:
                        workflow_name = rows[0].get("name") or workflow_name
                        graph_raw = rows[0].get("graph_json")
                        if graph_raw:
                            graph = json.loads(graph_raw) if isinstance(graph_raw, str) else graph_raw
                            for n in graph.get("nodes", []):
                                if n.get("id") == state.get("current_node_id"):
                                    node_label = n.get("label") or node_label
                                    break
                except Exception as lookup_err:
                    print(f"[HumanApprovalNodeExecutor] Could not resolve workflow/node names: {lookup_err}")

                if user_id and user_id != "system":
                    await notify_approval_pending(
                        user_id=user_id,
                        workflow_name=workflow_name,
                        execution_id=execution_id,
                        approval_id=approval.id,
                        node_name=node_label,
                    )
                    print(f"[HumanApprovalNodeExecutor] notify_approval_pending broadcast for user {user_id}, approval {approval.id}")
                else:
                    print(f"[HumanApprovalNodeExecutor] Skipping notification — no resolved user_id (got '{user_id}')")
            except Exception as notify_err:
                print(f"[HumanApprovalNodeExecutor] Failed to broadcast approval notification: {notify_err}")
                import traceback
                traceback.print_exc()

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
            raise RuntimeError(f"Approval node failed: {e}") from e


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
            raise RuntimeError(f"Workspace node failed: {e}") from e


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
            raise RuntimeError(f"Template node failed: {e}") from e


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
            raise RuntimeError(f"Webhook node failed: {e}") from e


# ============================================================================
# Email Node Executor
# ============================================================================

class EmailNodeExecutor(BaseNodeExecutor):
    """Execute email node - send email via SMTP using Settings → SMTP config."""

    def _resolve_recipients(
        self,
        raw: Optional[List[str]],
        input_data: Dict[str, Any],
        node_outputs: Dict[str, Any],
    ) -> List[str]:
        if not raw:
            return []
        resolved: List[str] = []
        for entry in raw:
            substituted = self._substitute_variables(entry or "", input_data, node_outputs)
            for piece in substituted.split(","):
                addr = piece.strip()
                if addr:
                    resolved.append(addr)
        return resolved

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email to each configured recipient using SMTPService."""
        from api.services.smtp_service import SMTPService

        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})
        current_node_id = state["current_node_id"]

        subject = self._substitute_variables(self.config.email_subject or "", input_data, node_outputs)
        body = self._substitute_variables(self.config.email_body or "", input_data, node_outputs)
        is_html = bool(self.config.email_is_html) if self.config.email_is_html is not None else True

        to_list = self._resolve_recipients(self.config.email_to, input_data, node_outputs)
        cc_list = self._resolve_recipients(self.config.email_cc, input_data, node_outputs)
        bcc_list = self._resolve_recipients(self.config.email_bcc, input_data, node_outputs)

        if not to_list:
            return {
                **state,
                "node_outputs": {
                    **node_outputs,
                    current_node_id: {
                        "error": "Email node requires at least one recipient in 'To'",
                        "status": "email_failed",
                    },
                },
            }

        recipients = to_list + cc_list + bcc_list
        sent: List[str] = []
        failed: List[Dict[str, str]] = []

        for recipient in recipients:
            try:
                await SMTPService.send_email_strict(
                    to_email=recipient,
                    subject=subject,
                    body=body,
                    is_html=is_html,
                )
                sent.append(recipient)
            except Exception as e:
                print(f"[EmailNodeExecutor] Error sending to {recipient}: {e}")
                failed.append({"recipient": recipient, "error": str(e)})

        status = "email_sent" if sent and not failed else ("email_partial" if sent else "email_failed")

        # If every recipient failed, raise so the engine marks this node FAILED
        # rather than silently completing green with a bad payload downstream.
        if failed and not sent:
            error_summary = "; ".join(
                f"{f['recipient']}: {f['error']}" for f in failed
            )
            raise RuntimeError(f"Email send failed for all recipients — {error_summary}")

        return {
            **state,
            "node_outputs": {
                **node_outputs,
                current_node_id: {
                    "status": status,
                    "subject": subject,
                    "sent_to": sent,
                    "failed": failed,
                    "to": to_list,
                    "cc": cc_list,
                    "bcc": bcc_list,
                },
            },
        }


# ============================================================================
# API Node Executor
# ============================================================================

class APINodeExecutor(BaseNodeExecutor):
    """
    Execute API node - fetch data from REST API with optional snapshots.

    Features:
    - HTTP requests (GET, POST, PUT, DELETE)
    - Authentication (bearer, API key, basic)
    - JSONPath extraction from responses
    - Automatic snapshot creation
    - Context-aware comparison support
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HTTP API call and optionally create snapshot."""
        import httpx
        from jsonpath_ng import parse as jsonpath_parse
        from datetime import datetime

        print(f"[APINodeExecutor] Executing API node")

        # Check if using API connection or raw config
        api_connection_id = self.config.api_connection_id

        if api_connection_id:
            # Load API connection from database
            print(f"[APINodeExecutor] Loading API connection: {api_connection_id}")
            from open_notebook.database.repository import repo_query
            import json

            connection_sql = "SELECT * FROM api_connections WHERE id = :id"
            connection_rows = await repo_query(connection_sql, {"id": api_connection_id})

            if not connection_rows:
                raise ValueError(f"API connection not found: {api_connection_id}")

            conn = connection_rows[0]

            # Parse JSON fields from TEXT columns
            headers = json.loads(conn.get("headers") or "{}") if isinstance(conn.get("headers"), str) else (conn.get("headers") or {})
            query_params = json.loads(conn.get("query_params") or "{}") if isinstance(conn.get("query_params"), str) else (conn.get("query_params") or {})
            request_body = json.loads(conn.get("request_body")) if conn.get("request_body") and isinstance(conn.get("request_body"), str) else conn.get("request_body")
            auth_config_encrypted = conn.get("auth_config_encrypted")

            # Decrypt auth_config if encrypted. Any failure here yields a
            # specific, actionable message — not a downstream NoneType error.
            if auth_config_encrypted:
                from api.routers.api_connections import (
                    decrypt_auth_config,
                    AuthConfigDecryptionError,
                )
                try:
                    auth_config = decrypt_auth_config(auth_config_encrypted)
                except AuthConfigDecryptionError as e:
                    raise ValueError(
                        f"API connection '{conn.get('name')}' "
                        f"({api_connection_id}): {e}"
                    )
                if auth_config is None:
                    raise ValueError(
                        f"API connection '{conn.get('name')}' "
                        f"({api_connection_id}): stored auth_config decrypted to None. "
                        f"Re-create the connection so credentials are re-encrypted."
                    )
            else:
                auth_config = {}

            # Use connection settings
            endpoint = conn.get("endpoint")
            method = (conn.get("method") or "GET").upper()
            data_path = conn.get("data_path") or "$"
            auth_type = conn.get("auth_type") or "none"
            timeout = 30

            # Append custom path if provided
            api_path = self.config.api_path
            if api_path:
                # Ensure proper URL joining
                endpoint = endpoint.rstrip('/') + '/' + api_path.lstrip('/')
                print(f"[APINodeExecutor] Appended path: {api_path}")

            print(f"[APINodeExecutor] Using connection '{conn.get('name')}': {method} {endpoint}")
        else:
            # Use raw configuration (legacy/fallback)
            endpoint = self.config.api_endpoint
            if not endpoint:
                raise ValueError("api_endpoint or api_connection_id is required")

            method = (self.config.api_method or "GET").upper()
            headers = dict(self.config.api_headers or {})
            query_params = dict(self.config.api_query_params or {})
            request_body = self.config.api_request_body
            timeout = self.config.api_timeout or 30
            data_path = self.config.api_response_data_path or "$"
            auth_type = self.config.api_auth_type or "none"
            auth_config = {"token": self.config.api_auth_token} if self.config.api_auth_token else {}

            print(f"[APINodeExecutor] Using raw config: {method} {endpoint}")

        # Resolve {{node-id.path}} placeholders in URL, headers, query params, and body.
        # Without this, literal "{{...}}" gets sent to upstream APIs (Outreach silently
        # ignores unknown filter values and returns an unfiltered page).
        input_data = state.get("input_data", {}) or {}
        node_outputs = state.get("node_outputs", {}) or {}

        def _sub_str(value):
            if isinstance(value, str) and "{{" in value:
                return self._substitute_variables(value, input_data, node_outputs)
            return value

        def _sub_deep(value):
            if isinstance(value, str):
                return _sub_str(value)
            if isinstance(value, dict):
                return {k: _sub_deep(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_sub_deep(v) for v in value]
            return value

        endpoint = _sub_str(endpoint)
        headers = {k: _sub_str(v) for k, v in (headers or {}).items()}
        query_params = {k: _sub_str(v) for k, v in (query_params or {}).items()}
        if request_body is not None:
            request_body = _sub_deep(request_body)
        print(f"[APINodeExecutor] Resolved endpoint: {endpoint}")

        # Handle authentication. For each auth_type that needs credentials,
        # surface a clear "what's missing" error rather than silently skipping
        # auth and letting the upstream API return an opaque 401.
        auth = None
        if auth_type == "bearer":
            token = auth_config.get("token") or auth_config.get("bearer_token")
            if not token:
                raise ValueError(
                    f"Bearer auth requires 'token' or 'bearer_token' in "
                    f"auth_config, got keys: {list(auth_config.keys()) or 'none'}"
                )
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            token = auth_config.get("token") or auth_config.get("api_key")
            if not token:
                raise ValueError(
                    f"API key auth requires 'token' or 'api_key' in "
                    f"auth_config, got keys: {list(auth_config.keys()) or 'none'}"
                )
            headers["X-API-Key"] = token
        elif auth_type == "basic":
            username = auth_config.get("username", "")
            password = auth_config.get("password", "")
            if not (username and password):
                raise ValueError(
                    f"Basic auth requires 'username' and 'password' in "
                    f"auth_config, got keys: {list(auth_config.keys()) or 'none'}"
                )
            auth = (username, password)
        elif auth_type == "client_credentials":
            from api.routers.api_connections import fetch_client_credentials_token
            try:
                token = await fetch_client_credentials_token(auth_config)
            except Exception as e:
                # fetch_client_credentials_token raises HTTPException; unwrap
                # detail for a readable workflow error.
                detail = getattr(e, "detail", None) or str(e)
                raise ValueError(f"OAuth client_credentials token request failed: {detail}")
            headers["Authorization"] = f"Bearer {token}"

        try:
            # httpx wipes the URL's existing query string when params={} is
            # passed — pass None when there are no extra params so any query
            # already baked into the URL (e.g. ?filter[customId]=…) survives.
            def _send_params(qp):
                return qp if qp else None

            async def _perform_request(client, qp, target_endpoint=None):
                """Issue one HTTP call and return (response, response_json, extracted_data).

                Factored out so the same path covers the single-call and
                batched-fan-out flows. `qp` is the query params for THIS call
                (already substituted, batch slice applied if any).
                `target_endpoint` overrides the outer `endpoint` — used by the
                URL-rewrite batching path so each batch hits a per-chunk URL.
                """
                ep = target_endpoint if target_endpoint is not None else endpoint
                send_params = _send_params(qp)
                if method == "GET":
                    resp = await client.get(ep, headers=headers, params=send_params, auth=auth)
                elif method == "POST":
                    resp = await client.post(ep, headers=headers, params=send_params, json=request_body, auth=auth)
                elif method == "PUT":
                    resp = await client.put(ep, headers=headers, params=send_params, json=request_body, auth=auth)
                elif method == "DELETE":
                    resp = await client.delete(ep, headers=headers, params=send_params, auth=auth)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                expected_codes = self.config.api_expected_status_codes
                if expected_codes:
                    if resp.status_code not in expected_codes:
                        raise ValueError(
                            f"API returned HTTP {resp.status_code}, expected one of {expected_codes}. "
                            f"Body preview: {resp.text[:300]}"
                        )
                else:
                    resp.raise_for_status()
                resp_json = resp.json()

                # Extract array from response using JSONPath
                jp_expr = jsonpath_parse(data_path)
                jp_matches = jp_expr.find(resp_json)
                if not jp_matches:
                    raise ValueError(f"No data found at JSONPath: {data_path}")
                extracted = jp_matches[0].value

                # Ensure list-of-dicts shape, mirroring the original behavior
                # so downstream nodes/snapshots see the same structure.
                if not isinstance(extracted, list):
                    if isinstance(extracted, dict):
                        extracted = [extracted]
                    else:
                        raise ValueError(
                            f"Extracted data must be array or object, got {type(extracted)}"
                        )
                return resp, resp_json, extracted

            async def _perform_request_to(client, target_endpoint, qp):
                """Convenience wrapper for batches that rewrite the URL."""
                return await _perform_request(client, qp, target_endpoint=target_endpoint)

            # Decide single vs batched. Batching activates only when
            # api_batch_param names a query param whose value is a list (or a
            # separator-joined string) longer than the configured batch size.
            batch_param = self.config.api_batch_param
            batch_separator = self.config.api_batch_separator or ","
            batch_size = max(1, int(self.config.api_batch_size or 50))
            batch_concurrency = max(1, int(self.config.api_batch_concurrency or 4))

            batch_items: Optional[List[Any]] = None
            # `endpoint_no_batch_qs` is the URL with the batch param stripped
            # out of its query string; per-batch, we re-attach the chunked
            # value as the only change. None means "param wasn't found in URL,
            # no rewrite needed."
            endpoint_no_batch_qs: Optional[str] = None
            url_extra_qs: str = ""  # other query params already baked into URL

            if batch_param:
                # 1) Look in query_params dict (the canonical place).
                if batch_param in (query_params or {}):
                    raw = query_params.get(batch_param)
                    if isinstance(raw, list):
                        batch_items = [str(x) for x in raw]
                    elif isinstance(raw, str):
                        parts = [p.strip() for p in raw.split(batch_separator) if p.strip() != ""]
                        if len(parts) > 1:
                            batch_items = parts

                # 2) Also look in the endpoint URL's own query string. This
                # covers the (common) case where users put the filter inline
                # in api_path (e.g. "/accounts?filter[customId]={{ids}}") so
                # the IDs end up baked into `endpoint` after substitution
                # rather than in the query_params dict.
                if batch_items is None and "?" in endpoint:
                    from urllib.parse import urlsplit, parse_qsl, urlunsplit, urlencode

                    parts = urlsplit(endpoint)
                    # parse_qsl with keep_blank_values + no decoding of the
                    # key, so "filter[customId]" survives intact.
                    qsl_pairs = parse_qsl(parts.query, keep_blank_values=True)

                    matched_value: Optional[str] = None
                    remaining_pairs: List[tuple] = []
                    for k, v in qsl_pairs:
                        if k == batch_param and matched_value is None:
                            matched_value = v
                        else:
                            remaining_pairs.append((k, v))

                    if matched_value is not None:
                        items = [
                            p.strip()
                            for p in matched_value.split(batch_separator)
                            if p.strip() != ""
                        ]
                        if len(items) > 1:
                            batch_items = items
                            # Save the URL minus the batch param. Other query
                            # params (e.g. `count=true`) survive untouched.
                            url_extra_qs = urlencode(remaining_pairs, safe="[]")
                            endpoint_no_batch_qs = urlunsplit((
                                parts.scheme, parts.netloc, parts.path,
                                "", parts.fragment
                            ))

            async with httpx.AsyncClient(timeout=timeout) as client:
                if not batch_items or len(batch_items) <= batch_size:
                    # Single call (covers no-batching configs and small lists
                    # that fit in one request).
                    response, response_json, data = await _perform_request(client, query_params)
                    merged_status_code = response.status_code
                    merged_elapsed_ms = int(response.elapsed.total_seconds() * 1000)
                    output_query_params = query_params
                else:
                    # Fan out: chunk the batch param value, fire requests with a
                    # concurrency cap, and concatenate per-batch lists. Mirrors
                    # the asyncio.gather + Semaphore pattern in
                    # deep_research_agent.py.
                    import asyncio

                    chunks: List[List[Any]] = [
                        batch_items[i:i + batch_size]
                        for i in range(0, len(batch_items), batch_size)
                    ]
                    source_label = "URL" if endpoint_no_batch_qs else "query_params"
                    print(
                        f"[APINodeExecutor] Batching '{batch_param}' (from {source_label}): "
                        f"{len(batch_items)} items → {len(chunks)} requests "
                        f"(size={batch_size}, concurrency={batch_concurrency})"
                    )

                    sem = asyncio.Semaphore(batch_concurrency)

                    if endpoint_no_batch_qs is not None:
                        # URL-embedded param: stitch each batch into the URL
                        # string directly. This preserves the raw, unencoded
                        # bracket syntax that Outreach uses for
                        # `filter[customId]` — round-tripping via httpx
                        # `params=` would percent-encode the brackets.
                        async def _one(chunk):
                            async with sem:
                                joined = batch_separator.join(chunk)
                                qs = f"{batch_param}={joined}"
                                if url_extra_qs:
                                    qs = f"{url_extra_qs}&{qs}"
                                chunk_endpoint = f"{endpoint_no_batch_qs}?{qs}"
                                # Issue the call with the rewritten URL and
                                # whatever query_params dict was already set
                                # (typically empty when the param was in URL).
                                return await _perform_request_to(client, chunk_endpoint, query_params)
                    else:
                        # Dict-based path: rewrite the chunked value in
                        # query_params and let httpx serialize it normally.
                        async def _one(chunk):
                            async with sem:
                                chunk_qp = dict(query_params)
                                chunk_qp[batch_param] = batch_separator.join(chunk)
                                return await _perform_request(client, chunk_qp)

                    results = await asyncio.gather(
                        *[_one(c) for c in chunks],
                        return_exceptions=False,
                    )

                    # Concat extracted lists. Use the first response's
                    # metadata for status_code/elapsed so the output stays
                    # representative; row_count reflects the merged total.
                    response, response_json, _ = results[0]
                    data = []
                    for _resp, _rj, extracted in results:
                        data.extend(extracted)
                    merged_status_code = response.status_code
                    merged_elapsed_ms = sum(
                        int(r.elapsed.total_seconds() * 1000) for r, _, _ in results
                    )
                    # Show the un-chunked param in output so the user sees
                    # what was logically requested, not the last chunk.
                    output_query_params = dict(query_params or {})

            # Empty-check happens AFTER any merge — empty means zero across
            # all batches.
            if self.config.api_fail_on_empty:
                explicit_check_path = self.config.api_empty_check_path
                if explicit_check_path:
                    check_path_label = explicit_check_path
                    check_matches = jsonpath_parse(explicit_check_path).find(response_json)
                    check_value = check_matches[0].value if check_matches else None
                else:
                    # Default: check the merged data list. The original logic
                    # peeked inside a JSON:API-style {data: [...]} envelope; we
                    # preserve that for the single-call case where data_path
                    # points at the envelope rather than the inner array.
                    check_value = data
                    check_path_label = data_path
                    if (
                        len(data) == 1
                        and isinstance(data[0], dict)
                        and "data" in data[0]
                        and isinstance(data[0]["data"], (list, dict, str))
                    ):
                        check_value = data[0]["data"]
                        check_path_label = f"{data_path}.data"

                is_empty = (
                    check_value is None
                    or (isinstance(check_value, (list, dict, str)) and len(check_value) == 0)
                    or check_value == 0
                )
                if is_empty:
                    raise ValueError(
                        f"API node failed: response is empty at path '{check_path_label}'. "
                        f"Endpoint: {endpoint}"
                    )

            # Build output
            output = {
                "status": "success",
                "data": data,
                "row_count": len(data),
                "columns": list(data[0].keys()) if data and isinstance(data[0], dict) else [],
                "endpoint": endpoint,
                "query_params": output_query_params,
                "status_code": merged_status_code,
                "response_time_ms": merged_elapsed_ms,
            }

            # Create snapshot if enabled
            if self.config.enable_snapshots:
                from open_notebook.domain.workflow_snapshot import WorkflowSnapshot, SnapshotContext

                try:
                    # Build snapshot context with API params
                    context = SnapshotContext.from_workflow_state(state)
                    context.query_params.update({
                        "endpoint": endpoint,
                        "method": method,
                        "query_params": query_params,
                        "data_path": data_path
                    })

                    print(f"[APINodeExecutor] Creating snapshot with context: {context.calculate_hash()}")

                    # Create snapshot
                    snapshot = await WorkflowSnapshot.create_from_data(
                        workflow_id=state.get("workflow_id"),
                        node_id=state["current_node_id"],
                        execution_id=state.get("execution_id"),
                        context=context,
                        data=data,
                        snapshot_label=self.config.snapshot_label,
                        retention_days=self.config.retention_days or 30
                    )

                    output["snapshot_id"] = snapshot.id
                    output["snapshot_created"] = True
                    output["snapshot_date"] = snapshot.snapshot_date.isoformat()

                    print(f"[APINodeExecutor] Snapshot created: {snapshot.id}")

                    # Cleanup old snapshots (keep only 2 most recent)
                    await self._cleanup_old_snapshots(
                        state.get("workflow_id"),
                        state["current_node_id"],
                        snapshot.id
                    )

                except Exception as e:
                    print(f"[APINodeExecutor] Snapshot creation failed (non-fatal): {e}")
                    import traceback
                    traceback.print_exc()
                    output["snapshot_error"] = str(e)

            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: output
                }
            }

        except httpx.HTTPStatusError as e:
            print(f"[APINodeExecutor] HTTP error: {e.response.status_code}")
            raise ValueError(
                f"HTTP {e.response.status_code} from {endpoint}. "
                f"Body preview: {e.response.text[:300]}"
            )
        except Exception as e:
            print(f"[APINodeExecutor] Error: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _cleanup_old_snapshots(self, workflow_id, node_id, current_snapshot_id):
        """Keep only 2 most recent snapshots for this node."""
        from open_notebook.domain.workflow_snapshot import WorkflowSnapshot

        try:
            # Get all snapshots for this workflow+node
            snapshots = await WorkflowSnapshot.find_all_for_node(workflow_id, node_id)

            # Sort by date (newest first)
            snapshots_sorted = sorted(snapshots, key=lambda s: s.snapshot_date, reverse=True)

            # Keep current + 1 previous (total 2)
            to_delete = [s for s in snapshots_sorted[2:] if s.id != current_snapshot_id]

            for snapshot in to_delete:
                print(f"[APINodeExecutor] Deleting old snapshot: {snapshot.id}")
                await snapshot.delete()

            if to_delete:
                print(f"[APINodeExecutor] Cleaned up {len(to_delete)} old snapshots")
        except Exception as e:
            print(f"[APINodeExecutor] Snapshot cleanup failed (non-fatal): {e}")


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
            has_changes = bool(delta.get("changed", False)) and delta.get("change_percentage", 0) > change_threshold

            # Extract changed rows
            changed_rows = self._extract_changed_rows(delta)

            print(f"[CompareNode] After _extract_changed_rows: {json.dumps(changed_rows, indent=2, default=str)}")

            # Capture pre-filter counts so the output explains why changed_rows
            # may be empty when has_changes is true (the watch_columns filter
            # can strip every diff row, which previously looked like a bug).
            pre_filter_summary = {
                "added": len(changed_rows.get("added", [])),
                "removed": len(changed_rows.get("removed", [])),
                "modified": len(changed_rows.get("modified", [])),
            }

            # Filter changed rows by watch_columns if configured
            watch_columns = self.config.watch_columns
            filter_applied = bool(watch_columns)
            if watch_columns:
                changed_rows = self._filter_by_watch_columns(changed_rows, watch_columns)
                print(f"[CompareNode] Filtered by watch_columns: {watch_columns}")

            post_filter_total = (
                len(changed_rows.get("added", []))
                + len(changed_rows.get("removed", []))
                + len(changed_rows.get("modified", []))
            )

            # When a watch_columns filter is configured, treat has_changes as
            # "are there matching changes?" so downstream conditional nodes act
            # on filter-relevant diffs only.
            if filter_applied:
                has_changes = has_changes and post_filter_total > 0

            print(f"[CompareNode] Has changes: {has_changes}, Changed rows: {post_filter_total}")

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
                    "modified": len(changed_rows.get("modified", [])),
                },
                "pre_filter_summary": pre_filter_summary,
                "watch_columns_applied": watch_columns or [],
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
# ForEach Node Executor
# ============================================================================

class ForEachNodeExecutor(BaseNodeExecutor):
    """Iterate over a list, running the chain wired to the `each` handle once per item.

    The ForEach node has two output handles:
        - `each`: chain of nodes that runs once per item
        - `done`: chain that runs once after all items are processed

    Config:
        foreach_source: "{{some-node.rows}}" — must resolve to a Python list.
        foreach_on_error: "continue" (default) or "fail".
        foreach_max_items: hard cap on iterations (default 1000).

    Per iteration the each-chain sees:
        input_data["item"]   — the current row
        input_data["index"]  — 0-based position
        input_data["total"]  — total rows being iterated

    Output (in node_outputs[<foreach-id>]):
        results: [...] — one entry per iteration, the LAST node of each chain's output
        errors:  [{"index": int, "error": str}, ...]
        count, succeeded, failed
    """

    def _resolve_list(self, template: str, input_data: Dict[str, Any], node_outputs: Dict[str, Any]):
        """Resolve a {{...}} reference to its raw Python value (preferring list)."""
        import re
        if not template:
            return None
        match = re.fullmatch(r'\s*\{\{([^}]+)\}\}\s*', template)
        if not match:
            # Not a single placeholder — substitute, then JSON-decode
            substituted = self._substitute_variables(template, input_data, node_outputs)
            try:
                return json.loads(substituted)
            except Exception:
                return None
        var_name = match.group(1).strip()

        def _walk(parts, root):
            current = root
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            return current

        if '.' in var_name:
            parts = var_name.split('.')
            if parts[0] in node_outputs:
                value = _walk(parts[1:], node_outputs[parts[0]])
                if value is not None:
                    return value
            for output in node_outputs.values():
                if isinstance(output, dict):
                    value = _walk(parts, output)
                    if value is not None:
                        return value
            if parts[0] in input_data:
                value = _walk(parts[1:], input_data[parts[0]])
                if value is not None:
                    return value
            return None
        else:
            if var_name in input_data:
                return input_data[var_name]
            if var_name in node_outputs:
                return node_outputs[var_name]
            for output in node_outputs.values():
                if isinstance(output, dict) and var_name in output:
                    return output[var_name]
            return None

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from open_notebook.domain.workflow import NodeConfig as _NodeConfig
        from open_notebook.database.repository import repo_query

        node_id = state.get("current_node_id")
        node_outputs = dict(state.get("node_outputs", {}))
        input_data = dict(state.get("input_data", {}))

        source_template = self.config.foreach_source or ""
        on_error = self.config.foreach_on_error or "continue"
        max_items = self.config.foreach_max_items if self.config.foreach_max_items is not None else 1000

        print(f"[ForEachNodeExecutor] Node {node_id} starting. source='{source_template}', on_error='{on_error}', max_items={max_items}")

        if not source_template:
            return self._fail(state, node_id, "foreach_source is empty")

        # Resolve source list
        items = self._resolve_list(source_template, input_data, node_outputs)
        if items is None:
            return self._fail(state, node_id, f"Could not resolve source '{source_template}' to a value")
        if not isinstance(items, list):
            return self._fail(state, node_id, f"Source resolved to {type(items).__name__}, expected list")

        # Apply max_items cap
        original_count = len(items)
        if max_items and original_count > max_items:
            print(f"[ForEachNodeExecutor] Capping iterations at {max_items} (source had {original_count})")
            items = items[:max_items]

        # Load workflow graph so we can walk the `each` subgraph
        try:
            rows = await repo_query(
                "SELECT graph_json FROM workflows WHERE id = :id",
                {"id": state.get("workflow_id")},
            )
            if not rows:
                return self._fail(state, node_id, "Could not load workflow graph")
            graph_raw = rows[0].get("graph_json")
            graph = json.loads(graph_raw) if isinstance(graph_raw, str) else graph_raw
        except Exception as lookup_err:
            return self._fail(state, node_id, f"Could not load workflow graph: {lookup_err}")

        all_nodes = {n["id"]: n for n in graph.get("nodes", [])}
        all_edges = graph.get("edges", [])

        # Walk the chain reachable from the `each` handle. The terminal of this
        # chain is the boundary where the `each`-subgraph ends — when we hit a
        # node with no outgoing edges within the subgraph, or we loop back to
        # the foreach itself, we stop.
        each_chain_start = None
        for e in all_edges:
            if e.get("source") == node_id and (e.get("sourceHandle") in ("each", None) and e.get("sourceHandle") != "done"):
                # First edge whose handle is "each" (or unspecified — for backwards compat with single-handle wires)
                if e.get("sourceHandle") == "each":
                    each_chain_start = e.get("target")
                    break
                elif e.get("sourceHandle") is None and each_chain_start is None:
                    each_chain_start = e.get("target")

        if not each_chain_start:
            return self._fail(state, node_id, "ForEach has no chain wired to the `each` output handle")

        # Compute the linear order of node IDs in the each-chain.
        # We walk from each_chain_start, following the first non-foreach outgoing
        # edge each time, until we hit a dead end or revisit ourselves.
        chain_ids: List[str] = []
        seen: set = set()
        cursor = each_chain_start
        while cursor and cursor not in seen and cursor != node_id:
            seen.add(cursor)
            if cursor not in all_nodes:
                return self._fail(state, node_id, f"each-chain references unknown node '{cursor}'")
            chain_ids.append(cursor)
            # Find the next node — first outgoing edge
            next_id = None
            for e in all_edges:
                if e.get("source") == cursor:
                    next_id = e.get("target")
                    break
            cursor = next_id

        if not chain_ids:
            return self._fail(state, node_id, "each-chain is empty")

        print(f"[ForEachNodeExecutor] each-chain resolved: {chain_ids}")

        # Build executors for each chain node up front
        chain_executors: List[tuple] = []  # (node_id, executor)
        for cid in chain_ids:
            cnode = all_nodes[cid]
            try:
                cconfig = _NodeConfig(**(cnode.get("config") or {}))
                cexec = create_node_executor(NodeType(cnode.get("type")), cconfig)
                chain_executors.append((cid, cexec))
            except Exception as build_err:
                return self._fail(state, node_id, f"Failed to build executor for chain node '{cid}': {build_err}")

        results = []
        errors = []
        succeeded = 0
        failed = 0

        # Per-chain-node aggregation across all iterations.
        # Lets the UI render execution details for nodes that run inside a ForEach.
        chain_agg: Dict[str, Dict[str, Any]] = {
            cid: {
                "iterations": [],         # one entry per iteration: output or {"error": str}
                "succeeded": 0,
                "failed": 0,
                "started_at": None,       # earliest iteration start (datetime)
                "completed_at": None,     # latest iteration end (datetime)
                "first_error": None,
            }
            for cid in chain_ids
        }

        total = len(items)
        for index, item in enumerate(items):
            iter_input = {**input_data, "item": item, "index": index, "total": total}
            iter_outputs = {**node_outputs}
            # Clear scratch space for chain nodes so each iteration starts clean
            for cid in chain_ids:
                iter_outputs.pop(cid, None)

            iter_state = {
                **state,
                "input_data": iter_input,
                "node_outputs": iter_outputs,
            }

            iter_failed_at_cid: Optional[str] = None
            iter_failed_err: Optional[str] = None

            try:
                last_output = None
                for cid, cexec in chain_executors:
                    iter_state = {
                        **iter_state,
                        "current_node_id": cid,
                    }
                    cstart = datetime.utcnow()
                    try:
                        result_state = await cexec.execute(iter_state)
                    except Exception as cnode_err:
                        cend = datetime.utcnow()
                        agg = chain_agg[cid]
                        agg["failed"] += 1
                        agg["iterations"].append({"error": str(cnode_err)})
                        if agg["started_at"] is None or cstart < agg["started_at"]:
                            agg["started_at"] = cstart
                        if agg["completed_at"] is None or cend > agg["completed_at"]:
                            agg["completed_at"] = cend
                        if agg["first_error"] is None:
                            agg["first_error"] = str(cnode_err)
                        iter_failed_at_cid = cid
                        iter_failed_err = str(cnode_err)
                        raise
                    cend = datetime.utcnow()
                    iter_state = {**iter_state, **(result_state or {})}
                    cnode_output = (result_state or {}).get("node_outputs", {}).get(cid)
                    last_output = cnode_output

                    agg = chain_agg[cid]
                    agg["succeeded"] += 1
                    agg["iterations"].append(cnode_output)
                    if agg["started_at"] is None or cstart < agg["started_at"]:
                        agg["started_at"] = cstart
                    if agg["completed_at"] is None or cend > agg["completed_at"]:
                        agg["completed_at"] = cend
                results.append(last_output)
                succeeded += 1
            except Exception as iter_err:
                failed += 1
                err_str = iter_failed_err or str(iter_err)
                print(f"[ForEachNodeExecutor] Iteration {index} failed at '{iter_failed_at_cid}': {err_str}")
                if on_error == "fail":
                    return self._fail(state, node_id, f"Iteration {index} failed: {err_str}")
                results.append({"error": err_str})
                errors.append({"index": index, "error": err_str})

        print(f"[ForEachNodeExecutor] Node {node_id} complete: total={total} succeeded={succeeded} failed={failed}")

        # Aggregate output. Surface per-chain-node aggregates so the UI can show
        # execution details for nodes inside the ForEach. Without this, inner
        # nodes appear "never run" because the engine only tracks state for
        # nodes it dispatches via LangGraph.
        new_outputs = {**node_outputs}
        new_outputs[node_id] = {
            "results": results,
            "errors": errors,
            "count": total,
            "source_count": original_count,
            "succeeded": succeeded,
            "failed": failed,
        }

        # Write aggregated node_outputs and execution.node_states for chain nodes
        execution = getattr(self, "_execution", None)
        for cid in chain_ids:
            agg = chain_agg[cid]
            iterations = agg["iterations"]
            sample = next((it for it in iterations if not (isinstance(it, dict) and "error" in it)), None)
            agg_output = {
                "foreach_aggregate": True,
                "foreach_node_id": node_id,
                "iterations": len(iterations),
                "succeeded": agg["succeeded"],
                "failed": agg["failed"],
                "sample": sample,
                "all": iterations,
            }
            new_outputs[cid] = agg_output

            if execution is not None:
                try:
                    if agg["failed"] == 0:
                        cstatus = ExecutionStatus.COMPLETED
                    elif agg["succeeded"] == 0:
                        cstatus = ExecutionStatus.FAILED
                    else:
                        # Mixed: keep COMPLETED but surface errors via output_data + error
                        cstatus = ExecutionStatus.COMPLETED
                    execution.node_states[cid] = NodeExecutionState(
                        node_id=cid,
                        status=cstatus,
                        started_at=agg["started_at"],
                        completed_at=agg["completed_at"],
                        output_data=agg_output,
                        error=agg["first_error"],
                    )
                except Exception as save_err:
                    print(f"[ForEachNodeExecutor] Failed to record node_state for {cid}: {save_err}")

        if execution is not None:
            try:
                await execution.save()
            except Exception as save_err:
                print(f"[ForEachNodeExecutor] Failed to save execution after recording chain states: {save_err}")

        return {
            **state,
            "input_data": input_data,
            "node_outputs": new_outputs,
        }

    def _fail(self, state, node_id, message):
        print(f"[ForEachNodeExecutor] FAIL: {message}")
        new_outputs = {**state.get("node_outputs", {})}
        new_outputs[node_id] = {"error": message, "results": [], "count": 0, "succeeded": 0, "failed": 0}
        return {
            **state,
            "node_outputs": new_outputs,
            "error": message,
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
        limit = self.config.hana_limit or 10000
        columns = self.config.hana_columns
        conditions = self.config.conditions or []

        # Parameter values for the WHERE clause that we build from `conditions`.
        # Built alongside the SQL fragment, then passed to cursor.execute(sql, params)
        # so values are never interpolated into the query string.
        condition_params: List[Any] = []

        # Build WHERE clause from conditions if provided
        if conditions and len(conditions) > 0:
            # Build a substitution map for user tokens from engine state
            user_subs = {
                "{{user.username}}": state.get("username") or "",
                "{{user.email}}": state.get("user_email") or "",
                "{{user.id}}": state.get("user_id") or "",
            }
            input_data = state.get("input_data", {}) or {}
            node_outputs = state.get("node_outputs", {}) or {}

            condition_clauses = []
            for cond in conditions:
                column = cond.get("column")
                operator = (cond.get("operator") or "=").upper()
                value = cond.get("value")

                # Substitute user tokens and any other {{...}} references in value.
                # _substitute_variables raises on unresolved/empty placeholders or
                # SQL-injection-shaped payloads — we let that bubble up so the
                # iteration fails loudly instead of silently building bad SQL.
                if isinstance(value, str):
                    original_value = value
                    for token, replacement in user_subs.items():
                        if token in value:
                            value = value.replace(token, str(replacement))
                    value = self._substitute_variables(value, input_data, node_outputs, sql_context=True)
                    if original_value != value:
                        print(f"[HANATableNodeExecutor] Substituted condition value for '{column}': {original_value!r} -> {value!r} (type={type(value).__name__})")

                # IS NULL / IS NOT NULL take no value
                if operator in ("IS NULL", "IS NOT NULL"):
                    if column:
                        condition_clauses.append(f'"{column}" {operator}')
                    continue

                if not column or value is None:
                    continue

                # IN expects a list-like value; we expand to N placeholders.
                if operator == "IN":
                    if isinstance(value, str):
                        stripped = value.strip()
                        # Upstream {{node.field}} that resolved to a list comes
                        # in as a JSON-array string (because _substitute_variables
                        # always returns a string). Try parsing it first so we
                        # don't shred the array on commas inside JSON literals.
                        if stripped.startswith("[") and stripped.endswith("]"):
                            try:
                                parsed = json.loads(stripped)
                            except json.JSONDecodeError:
                                parsed = None
                            if isinstance(parsed, list):
                                items = parsed
                            else:
                                items = [v.strip() for v in value.split(",") if v.strip()]
                        else:
                            # Back-compat: comma-separated string like "a, b, c"
                            items = [v.strip() for v in value.split(",") if v.strip()]
                    elif isinstance(value, (list, tuple)):
                        items = list(value)
                    else:
                        items = [value]

                    if not items:
                        continue

                    placeholders = ", ".join(["?"] * len(items))
                    condition_clauses.append(f'"{column}" IN ({placeholders})')
                    condition_params.extend(items)
                    continue

                # Standard binary operators (=, !=, <, >, LIKE, etc.) — bind value as ?
                condition_clauses.append(f'"{column}" {operator} ?')
                condition_params.append(value)

            # Combine with existing where_clause if present
            if condition_clauses:
                conditions_where = " AND ".join(condition_clauses)
                if where_clause:
                    where_clause = f"({where_clause}) AND ({conditions_where})"
                else:
                    where_clause = conditions_where

                print(f"[HANATableNodeExecutor] Built parameterized WHERE clause: {where_clause} (params={condition_params})")

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
            if not custom_query and condition_params:
                print(f"[HANATableNodeExecutor] With params: {condition_params}")

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
                # Custom queries are pass-through (no parameterization layer here);
                # the SELECT-only check upstream is the guardrail. Everything built
                # from `conditions[]` uses ? placeholders + bound params, so values
                # cannot escape the value slot regardless of input.
                if custom_query:
                    cursor.execute(sql)
                elif condition_params:
                    cursor.execute(sql, condition_params)
                else:
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

                if self.config.hana_fail_on_empty and not results:
                    raise ValueError(
                        f"HANA node failed: query returned 0 rows. "
                        f"Table: {table_name}, where: {where_clause or 'none'}"
                    )

                # Store query params for context-aware snapshots.
                # We include the bound parameter values so execution details
                # show exactly what was sent to HANA — useful for debugging
                # when a query returns 0 rows.
                query_params = {
                    "connection_id": connection_id,
                    "table_name": table_name,
                    "where_clause": where_clause,
                    "bound_params": condition_params if not custom_query else [],
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
# JQ Node Executor
# ============================================================================

class JQNodeExecutor(BaseNodeExecutor):
    """Execute jq node - transform JSON using a jq expression."""

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import jq  # type: ignore
        except ImportError:
            return {
                **state,
                "node_outputs": {
                    **state.get("node_outputs", {}),
                    state["current_node_id"]: {
                        "status": "error",
                        "error": "The 'jq' Python package is not installed. Run: pip install jq",
                    },
                },
            }

        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})
        current_node_id = state["current_node_id"]

        expression = (self.config.jq_expression or "").strip()
        if not expression:
            return {
                **state,
                "node_outputs": {
                    **node_outputs,
                    current_node_id: {
                        "status": "error",
                        "error": "jq node requires a non-empty expression",
                    },
                },
            }

        json_input = self._resolve_input(input_data, node_outputs)

        try:
            program = jq.compile(expression)
            results = program.input(json_input).all()
        except Exception as e:
            hint = self._diagnose_input_mismatch(json_input, expression)
            error_msg = f"jq evaluation failed: {e}"
            if hint:
                error_msg += f" — {hint}"
            if self.config.jq_on_error == "null":
                return {
                    **state,
                    "node_outputs": {
                        **node_outputs,
                        current_node_id: {
                            "status": "jq_completed",
                            "expression": expression,
                            "result": None,
                            "warning": error_msg,
                            "input_type": type(json_input).__name__,
                        },
                    },
                }
            return {
                **state,
                "node_outputs": {
                    **node_outputs,
                    current_node_id: {
                        "status": "error",
                        "error": error_msg,
                        "expression": expression,
                        "input_type": type(json_input).__name__,
                        "input_keys": list(json_input.keys()) if isinstance(json_input, dict) else None,
                    },
                },
            }

        mode = self.config.jq_output_mode or "first"
        if mode == "all":
            output_value: Any = results
        else:
            output_value = results[0] if results else None

        return {
            **state,
            "node_outputs": {
                **node_outputs,
                current_node_id: {
                    "status": "jq_completed",
                    "expression": expression,
                    "result": output_value,
                    "result_count": len(results),
                },
            },
        }

    def _resolve_input(
        self,
        input_data: Dict[str, Any],
        node_outputs: Dict[str, Any],
    ) -> Any:
        """Pick the JSON value to feed into jq.

        Priority:
        1. ``jq_input_source`` template (e.g. ``{{node-id.field}}``) if configured.
        2. Most recently produced upstream node output.
        3. Empty dict as a safe default.

        Supports two configured shapes:
        - **Single reference**: ``{{node-id}}`` or ``{{node-id.field}}`` — the
          value is fetched directly and returned as-is (preserves dict/list).
        - **Multi-input JSON literal**: a JSON object/array whose string values
          are ``{{...}}`` placeholders, e.g.
          ``{"campaigns": "{{hana-1.data}}", "accounts": "{{api-1.data}}"}``.
          Each placeholder is resolved via ``_lookup_variable`` (no SQL screen,
          no JSON round-trip), giving the jq expression named inputs to work
          with.
        """
        source = (self.config.jq_input_source or "").strip()
        if source:
            # Fast path: when the source is a single {{...}} reference, resolve it
            # directly so the value stays a dict/list. Going through
            # _substitute_variables would round-trip via json.dumps -> json.loads
            # and also subject the data to the SQL-injection screen, which
            # legitimately rejects values like "Decision Maker;User" that have
            # nothing to do with SQL.
            import re as _re
            single_ref = _re.fullmatch(r"\s*\{\{\s*([^{}]+?)\s*\}\}\s*", source)
            if single_ref:
                var_name = single_ref.group(1).strip()
                resolved_direct = self._lookup_variable(var_name, input_data, node_outputs)
                if resolved_direct is not _SENTINEL_UNRESOLVED:
                    return resolved_direct
                # Fall through to the legacy path so the user gets the existing
                # "could not be resolved" diagnostics.

            # Multi-input path: treat ``source`` as a JSON literal whose string
            # leaves may be ``{{node-id[.path]}}`` placeholders.
            stripped = source.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if parsed is not None:
                    return self._resolve_placeholders(parsed, input_data, node_outputs)

            try:
                resolved = self._substitute_variables(source, input_data, node_outputs)
            except ValueError:
                resolved = source
            if isinstance(resolved, str):
                stripped = resolved.strip()
                if stripped.startswith("{") or stripped.startswith("["):
                    try:
                        return json.loads(stripped)
                    except json.JSONDecodeError:
                        return resolved
            return resolved

        if node_outputs:
            last_key = list(node_outputs.keys())[-1]
            return node_outputs[last_key]

        return input_data or {}

    def _resolve_placeholders(
        self,
        value: Any,
        input_data: Dict[str, Any],
        node_outputs: Dict[str, Any],
    ) -> Any:
        """Recursively replace ``{{node-id[.path]}}`` strings with their resolved values.

        - A string that is exactly one placeholder becomes the raw value
          (dict / list / scalar) — never stringified.
        - Strings with placeholders mixed into other text fall through to
          ``_substitute_variables`` (which stringifies and applies the SQL screen).
        - Dicts and lists are walked.
        """
        import re as _re
        if isinstance(value, str):
            single = _re.fullmatch(r"\s*\{\{\s*([^{}]+?)\s*\}\}\s*", value)
            if single:
                resolved = self._lookup_variable(single.group(1).strip(), input_data, node_outputs)
                if resolved is _SENTINEL_UNRESOLVED:
                    raise ValueError(
                        f"jq_input_source placeholder {{{{ {single.group(1).strip()} }}}} could not be resolved"
                    )
                return resolved
            if "{{" in value:
                return self._substitute_variables(value, input_data, node_outputs)
            return value
        if isinstance(value, list):
            return [self._resolve_placeholders(v, input_data, node_outputs) for v in value]
        if isinstance(value, dict):
            return {k: self._resolve_placeholders(v, input_data, node_outputs) for k, v in value.items()}
        return value

    @staticmethod
    def _diagnose_input_mismatch(json_input: Any, expression: str) -> str:
        """Produce a one-line hint when jq fails so users know what to fix.

        The most common mistake is feeding a HANA/API result *envelope*
        (e.g. ``{status, data: [...], row_count}``) into an expression that
        expects the underlying array. jq's native error ("Cannot index
        string with string") is not actionable; this hint is.
        """
        if isinstance(json_input, dict):
            array_fields = [k for k, v in json_input.items() if isinstance(v, list)]
            if array_fields:
                # Prefer 'data' / 'rows' / 'items' / 'results' which are the conventional names
                preferred = next(
                    (k for k in ("data", "rows", "items", "results") if k in array_fields),
                    array_fields[0],
                )
                return (
                    f"input is an object with keys {sorted(json_input.keys())}; "
                    f"if you meant to operate on the array, set jq_input_source to "
                    f"'{{{{<node-id>.{preferred}}}}}'"
                )
        if isinstance(json_input, str):
            return (
                "input resolved to a string; check that jq_input_source is "
                "'{{node-id}}' or '{{node-id.field}}' and that the upstream node has run"
            )
        return ""


# ============================================================================
# Node Executor Factory
# ============================================================================

class NotifyNodeExecutor(BaseNodeExecutor):
    """Fire-and-forget user notification — inbox entry + WebSocket toast.

    Unlike HumanApprovalNodeExecutor, this does NOT pause the workflow.
    Used to inform a human ("brief is ready", "anomaly detected") while
    the graph keeps executing.
    """

    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        from open_notebook.domain.notification import (
            Notification,
            NotificationCategory,
            NotificationPriority,
            NotificationType,
        )
        from api.services.notification_service import get_notification_service

        input_data = state.get("input_data", {})
        node_outputs = state.get("node_outputs", {})
        current_node_id = state["current_node_id"]

        title = self._substitute_variables(self.config.notify_title or "Workflow notification", input_data, node_outputs)
        message = self._substitute_variables(self.config.notify_message or "", input_data, node_outputs)
        action_url = self._substitute_variables(self.config.notify_action_url or "", input_data, node_outputs) or None
        action_label = self.config.notify_action_label

        priority_map = {
            "low": NotificationPriority.LOW,
            "normal": NotificationPriority.NORMAL,
            "high": NotificationPriority.HIGH,
            "urgent": NotificationPriority.URGENT,
        }
        priority = priority_map.get((self.config.notify_priority or "normal").lower(), NotificationPriority.NORMAL)

        # Recipients: explicit override → workflow user fallback
        recipients = self.config.notify_user_ids or []
        if not recipients:
            workflow_user = state.get("user_id")
            if workflow_user and workflow_user != "system":
                recipients = [workflow_user]

        if not recipients:
            return {
                **state,
                "node_outputs": {
                    **node_outputs,
                    current_node_id: {
                        "status": "skipped",
                        "reason": "no recipient resolved (workflow user unknown and notify_user_ids empty)",
                    },
                },
            }

        sent: List[str] = []
        failed: List[Dict[str, str]] = []
        notification_service = get_notification_service()

        for user_id in recipients:
            try:
                notification = await Notification.create(
                    user_id=user_id,
                    type=NotificationType.SYSTEM,
                    title=title,
                    message=message,
                    category=NotificationCategory.WORKFLOW,
                    priority=priority,
                    entity_type="workflow_execution",
                    entity_id=state.get("execution_id"),
                    action_url=action_url,
                    action_label=action_label,
                    metadata={
                        "workflow_id": state.get("workflow_id"),
                        "node_id": current_node_id,
                    },
                )
                await notification_service.broadcast_notification(notification)
                sent.append(user_id)
            except Exception as e:
                print(f"[NotifyNodeExecutor] Failed for user {user_id}: {e}")
                failed.append({"user_id": user_id, "error": str(e)})

        return {
            **state,
            "node_outputs": {
                **node_outputs,
                current_node_id: {
                    "status": "notified" if sent and not failed else ("partial" if sent else "failed"),
                    "title": title,
                    "sent_to": sent,
                    "failed": failed,
                },
            },
        }


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
        NodeType.EMAIL: EmailNodeExecutor,
        NodeType.API: APINodeExecutor,
        NodeType.SNAPSHOT: SnapshotNodeExecutor,
        NodeType.COMPARE: CompareNodeExecutor,
        NodeType.HANA_TABLE: HANATableNodeExecutor,
        NodeType.FOREACH: ForEachNodeExecutor,
        NodeType.JQ: JQNodeExecutor,
        NodeType.NOTIFY: NotifyNodeExecutor,
    }

    executor_class = executors.get(node_type)
    if not executor_class:
        raise ValueError(f"Unknown node type: {node_type}")

    return executor_class(config)
