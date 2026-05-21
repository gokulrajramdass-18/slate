"""
Intelligent Agent - Context-aware agent with tool output analysis and conditional logic.

Capabilities:
- Automatically understands tool output schemas
- Makes decisions based on data (if/then logic)
- Chains actions dynamically
- Executes complex business workflows

Example:
    "Get my outreach opportunities, check status, if won write summary and notify sales team"

    The agent will:
    1. Call get_outreach_opportunities tool
    2. Analyze the output structure (array of objects with status field)
    3. Filter for status='won'
    4. For each won opportunity:
       - Generate summary
       - Call notify_sales_team tool
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict
from typing_extensions import Annotated

from langchain.tools import BaseTool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, add_messages
from langgraph.prebuilt import ToolNode


# ============================================================================
# State Definition
# ============================================================================

class IntelligentAgentState(TypedDict):
    """State for intelligent agent with tool result analysis"""
    messages: Annotated[List[BaseMessage], add_messages]
    notebook_id: str
    session_id: Optional[str]
    tools_available: List[str]

    # Enhanced state for intelligent decision-making
    tool_outputs: Dict[str, Any]  # Structured tool results
    analysis_context: Dict[str, Any]  # Agent's understanding of data
    next_actions: List[str]  # Planned next steps
    conditional_branches: Dict[str, Any]  # If/then logic state


# ============================================================================
# Tool Output Analyzer
# ============================================================================

class ToolOutputAnalyzer:
    """
    Analyzes tool outputs to understand structure and semantics.

    Extracts:
    - Data type (table, array, object, scalar)
    - Schema (field names and types)
    - Semantic meaning (what does this data represent?)
    - Actionable insights (what can be done with this data?)
    """

    @staticmethod
    def analyze(tool_name: str, output: Any) -> Dict[str, Any]:
        """
        Analyze tool output and return structured analysis.

        Args:
            tool_name: Name of the tool that produced output
            output: Raw tool output

        Returns:
            Dict with analysis results:
            {
                "data_type": "table" | "array" | "object" | "scalar",
                "schema": {...},
                "row_count": int,
                "fields": [...],
                "sample_row": {...},
                "semantic_type": "opportunities" | "customers" | etc,
                "actionable_fields": [...],
                "suggestions": [...]
            }
        """
        analysis = {
            "tool_name": tool_name,
            "data_type": "unknown",
            "schema": {},
            "row_count": 0,
            "fields": [],
            "sample_row": None,
            "semantic_type": ToolOutputAnalyzer._infer_semantic_type(tool_name),
            "actionable_fields": [],
            "suggestions": [],
        }

        # Detect data type and extract schema
        if isinstance(output, dict):
            if "rows" in output and isinstance(output["rows"], list):
                # Table format from HANA query
                analysis["data_type"] = "table"
                analysis["row_count"] = len(output["rows"])
                if output["rows"]:
                    analysis["sample_row"] = output["rows"][0]
                    analysis["fields"] = list(output["rows"][0].keys())
                    analysis["schema"] = ToolOutputAnalyzer._extract_schema(output["rows"])

            elif "data" in output and isinstance(output["data"], list):
                # API response with data array
                analysis["data_type"] = "array"
                analysis["row_count"] = len(output["data"])
                if output["data"]:
                    analysis["sample_row"] = output["data"][0]
                    analysis["fields"] = list(output["data"][0].keys()) if isinstance(output["data"][0], dict) else []
                    analysis["schema"] = ToolOutputAnalyzer._extract_schema(output["data"])

            else:
                # Single object
                analysis["data_type"] = "object"
                analysis["fields"] = list(output.keys())
                analysis["schema"] = {k: type(v).__name__ for k, v in output.items()}

        elif isinstance(output, list):
            # Direct array
            analysis["data_type"] = "array"
            analysis["row_count"] = len(output)
            if output and isinstance(output[0], dict):
                analysis["sample_row"] = output[0]
                analysis["fields"] = list(output[0].keys())
                analysis["schema"] = ToolOutputAnalyzer._extract_schema(output)

        else:
            # Scalar value
            analysis["data_type"] = "scalar"
            analysis["schema"] = {"value": type(output).__name__}

        # Identify actionable fields (status, priority, date, etc.)
        analysis["actionable_fields"] = ToolOutputAnalyzer._find_actionable_fields(
            analysis["fields"]
        )

        # Generate suggestions
        analysis["suggestions"] = ToolOutputAnalyzer._generate_suggestions(analysis)

        return analysis

    @staticmethod
    def _extract_schema(data: List[Dict]) -> Dict[str, str]:
        """Extract schema from list of dicts."""
        if not data:
            return {}

        schema = {}
        sample = data[0]
        for key, value in sample.items():
            schema[key] = type(value).__name__

        return schema

    @staticmethod
    def _infer_semantic_type(tool_name: str) -> str:
        """Infer semantic type from tool name."""
        name_lower = tool_name.lower()

        semantic_map = {
            "opportunity": "opportunities",
            "lead": "leads",
            "customer": "customers",
            "order": "orders",
            "invoice": "invoices",
            "product": "products",
            "user": "users",
            "ticket": "support_tickets",
            "campaign": "marketing_campaigns",
        }

        for keyword, semantic_type in semantic_map.items():
            if keyword in name_lower:
                return semantic_type

        return "unknown"

    @staticmethod
    def _find_actionable_fields(fields: List[str]) -> List[Dict[str, Any]]:
        """
        Identify fields that represent actionable data.

        Returns list of dicts with field metadata:
        [
            {"name": "status", "type": "categorical", "actions": ["filter", "group_by"]},
            {"name": "priority", "type": "ordinal", "actions": ["sort", "filter"]},
            ...
        ]
        """
        actionable = []

        # Common actionable field patterns
        status_fields = ["status", "state", "stage", "phase"]
        priority_fields = ["priority", "urgency", "severity"]
        date_fields = ["date", "created", "updated", "closed", "due"]
        amount_fields = ["amount", "value", "price", "cost", "revenue"]

        for field in fields:
            field_lower = field.lower()

            if any(sf in field_lower for sf in status_fields):
                actionable.append({
                    "name": field,
                    "type": "categorical",
                    "actions": ["filter", "group_by", "count"],
                    "suggested_logic": f"Check if {field} == 'won' or 'completed'",
                })

            elif any(pf in field_lower for pf in priority_fields):
                actionable.append({
                    "name": field,
                    "type": "ordinal",
                    "actions": ["sort", "filter", "prioritize"],
                    "suggested_logic": f"Filter by {field} == 'high'",
                })

            elif any(df in field_lower for df in date_fields):
                actionable.append({
                    "name": field,
                    "type": "temporal",
                    "actions": ["sort", "filter", "time_series"],
                    "suggested_logic": f"Filter by {field} in last 7 days",
                })

            elif any(af in field_lower for af in amount_fields):
                actionable.append({
                    "name": field,
                    "type": "numeric",
                    "actions": ["sum", "average", "filter", "sort"],
                    "suggested_logic": f"Sum {field} for total",
                })

        return actionable

    @staticmethod
    def _generate_suggestions(analysis: Dict[str, Any]) -> List[str]:
        """Generate actionable suggestions based on analysis."""
        suggestions = []

        # Suggest filtering if status field exists
        status_fields = [
            f for f in analysis["actionable_fields"]
            if f["type"] == "categorical" and "status" in f["name"].lower()
        ]
        if status_fields:
            field = status_fields[0]["name"]
            suggestions.append(f"Filter by {field} to find specific records")
            suggestions.append(f"Group by {field} to see distribution")

        # Suggest aggregation if numeric fields exist
        numeric_fields = [f for f in analysis["actionable_fields"] if f["type"] == "numeric"]
        if numeric_fields:
            field = numeric_fields[0]["name"]
            suggestions.append(f"Calculate total {field}")
            suggestions.append(f"Find records with highest {field}")

        # Suggest time-based analysis if date fields exist
        date_fields = [f for f in analysis["actionable_fields"] if f["type"] == "temporal"]
        if date_fields:
            field = date_fields[0]["name"]
            suggestions.append(f"Filter by recent {field}")
            suggestions.append(f"Group by time period using {field}")

        return suggestions


# ============================================================================
# Conditional Logic Engine
# ============================================================================

class ConditionalEngine:
    """
    Executes conditional logic (if/then/else) based on tool outputs.

    Examples:
        - If status == "won", then summarize and notify
        - If priority == "high", then escalate
        - If amount > 10000, then require approval
    """

    @staticmethod
    def evaluate_condition(
        data: Any,
        condition: str,
        field: str,
        operator: str,
        value: Any,
    ) -> List[Any]:
        """
        Evaluate a condition on data and return matching records.

        Args:
            data: Tool output (list of dicts, dict, or scalar)
            condition: Full condition string (for LLM understanding)
            field: Field name to check
            operator: Comparison operator (==, !=, >, <, >=, <=, in, contains)
            value: Value to compare against

        Returns:
            List of records that match the condition
        """
        matching = []

        # Handle different data types
        if isinstance(data, dict):
            if "rows" in data:
                records = data["rows"]
            elif "data" in data:
                records = data["data"]
            else:
                records = [data]
        elif isinstance(data, list):
            records = data
        else:
            records = [{"value": data}]

        # Evaluate condition for each record
        for record in records:
            if not isinstance(record, dict):
                continue

            record_value = record.get(field)
            if record_value is None:
                continue

            # Apply operator
            match = False
            if operator == "==":
                match = str(record_value).lower() == str(value).lower()
            elif operator == "!=":
                match = str(record_value).lower() != str(value).lower()
            elif operator == ">":
                match = float(record_value) > float(value)
            elif operator == "<":
                match = float(record_value) < float(value)
            elif operator == ">=":
                match = float(record_value) >= float(value)
            elif operator == "<=":
                match = float(record_value) <= float(value)
            elif operator == "in":
                match = str(record_value).lower() in [str(v).lower() for v in value]
            elif operator == "contains":
                match = str(value).lower() in str(record_value).lower()

            if match:
                matching.append(record)

        return matching


# ============================================================================
# Intelligent Agent
# ============================================================================

class IntelligentAgent:
    """
    Enhanced agent with tool output understanding and conditional logic.

    Usage:
        agent = IntelligentAgent(
            model_name="claude-3-5-sonnet-20241022",
            notebook_id="abc",
            tools=tools,
        )

        result = await agent.execute(
            "Get outreach opportunities, check status, if won write summary"
        )
    """

    def __init__(
        self,
        model_name: str,
        notebook_id: str,
        tools: List[BaseTool],
        session_id: Optional[str] = None,
        system_message: Optional[str] = None,
        task_description: Optional[str] = None,
        enable_tool_filtering: bool = False,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model_name = model_name
        self.notebook_id = notebook_id
        self.session_id = session_id
        self.system_message = system_message or self._default_system_message()
        self.task_description = task_description or "General task execution"
        self.enable_tool_filtering = enable_tool_filtering
        self.api_key = api_key
        self.base_url = base_url

        # Apply tool filtering if enabled
        if self.enable_tool_filtering:
            import asyncio
            try:
                from deep_agents_integration.tool_filtering import get_plan_mode_filter
            except ImportError as exc:
                print(f"⚠️ Tool filtering unavailable ({exc}); using all {len(tools)} tools")
                self.tools = list(tools)
            else:
                filter_instance = get_plan_mode_filter()
                filter_result = asyncio.run(
                    filter_instance.filter_tools_for_query(
                        query=self.task_description,
                        available_tools=tools
                    )
                )
                self.tools = [t for t in tools if t.name in filter_result.selected_tool_ids]
        else:
            self.tools = tools

        # Create LLM
        self.model = self._create_model()

        # Build workflow graph
        self.graph = self._build_graph()

        # State tracking
        self.tool_outputs = {}
        self.analysis_results = {}

    def _default_system_message(self) -> str:
        """Enhanced system message with conditional logic instructions."""
        return """You are an intelligent agent with advanced reasoning capabilities.

**Core Abilities:**
1. **Tool Understanding**: After calling a tool, analyze the output structure (table, array, object, scalar) and understand what the data represents.

2. **Conditional Logic**: Execute if/then/else logic based on data:
   - "If status == 'won', then do X"
   - "If amount > 10000, then do Y"
   - "For each record where priority == 'high', do Z"

3. **Action Chaining**: Dynamically chain multiple actions based on results:
   - Call tool A
   - Analyze results
   - If condition met, call tool B
   - Otherwise, call tool C

4. **Data Analysis**: When you receive tool output:
   - Identify the data structure (rows, columns, fields)
   - Find actionable fields (status, priority, dates, amounts)
   - Determine what actions are possible
   - Explain what you found in plain language

**Example Workflow:**
User: "Get my outreach opportunities, check status, if won write summary"

Your steps:
1. Call get_outreach_opportunities()
2. Analyze output: "Found 15 opportunities with fields: id, name, status, amount, created_date"
3. Filter: "3 opportunities have status='won'"
4. For each won opportunity:
   - Extract details (name, amount)
   - Generate summary
   - Call any follow-up tools (e.g., notify_team, update_crm)
5. Report: "Found 3 won opportunities totaling $45,000. Summaries created and team notified."

**Decision-Making:**
- Use tool outputs to make intelligent decisions
- Explain your reasoning at each step
- Handle edge cases (empty results, missing fields)
- Chain actions logically

**Available Context:**
{context}
"""

    def _create_model(self):
        """Create LLM with tools bound using LiteLLM proxy."""
        import os
        from langchain_openai import ChatOpenAI

        # Prepare model kwargs
        model_kwargs = {
            "temperature": 0.3,  # Lower for more deterministic logic
            "max_tokens": 4096,
        }

        # Check if this is a SAP AI Core model
        is_sap_ai_core = self.model_name.startswith("sap-ai-core-")

        if is_sap_ai_core:
            # SAP AI Core integration
            print(f"🔧 Creating SAP AI Core model for intelligent agent")
            print(f"   Model: {self.model_name}")

            from open_notebook.llm.chat_sap_ai_core_sdk import ChatSAPAICore
            from api.services.sap_ai_core_service import SAPAICoreService, SAPAICoreConfig
            from api.routers.credentials import _credentials_store
            import json

            # Extract deployment ID
            deployment_id = self.model_name.replace("sap-ai-core-", "")

            # Find SAP AI Core credential
            sap_credential = None
            for cred_id, cred in _credentials_store.items():
                if (cred.get("provider") == "sap_ai_core" and
                    (cred.get("model_name") == self.model_name or
                     deployment_id in cred.get("model_name", ""))):
                    sap_credential = cred
                    break

            if not sap_credential:
                raise Exception(
                    f"SAP AI Core credential not found for deployment {deployment_id}"
                )

            # Parse connection config
            try:
                connection_config = json.loads(sap_credential.get("api_key", "{}"))
            except json.JSONDecodeError:
                raise Exception("Invalid SAP AI Core credential format")

            # Create config
            config = SAPAICoreConfig(
                auth_url=connection_config.get("auth_url"),
                api_url=connection_config.get("api_url"),
                client_id=connection_config.get("client_id"),
                client_secret=connection_config.get("client_secret"),
                resource_group=connection_config.get("resource_group", "default"),
            )

            print(f"   ✅ SAP AI Core configured for intelligent agent")

            # Create model
            model = ChatSAPAICore(
                service=SAPAICoreService(config),
                deployment_id=deployment_id,
                **model_kwargs
            )

        # If base_url is provided, use it (LiteLLM proxy)
        elif self.base_url:
            model_kwargs["base_url"] = self.base_url
            model_kwargs["api_key"] = self.api_key or os.getenv("HAI_PROXY_KEY", "")

            print(f"🔧 Creating OpenAI-compatible model for LiteLLM")
            print(f"   Model: {self.model_name}")
            print(f"   Base URL: {self.base_url}")

            # Use ChatOpenAI for all models when going through LiteLLM
            model = ChatOpenAI(
                model=self.model_name,
                **model_kwargs
            )
        else:
            # No base_url provided - use environment variable approach
            litellm_base_url = os.getenv("LITELLM_BASE_URL", "http://localhost:6655/litellm/v1")
            litellm_api_key = os.getenv("HAI_PROXY_KEY", "")

            if not litellm_api_key:
                raise ValueError(
                    "HAI_PROXY_KEY not configured. Please set it in your .env file:\n"
                    "HAI_PROXY_KEY=your-key-here\n\n"
                    "This allows the agent to access all LiteLLM models without individual API keys."
                )

            model_kwargs["base_url"] = litellm_base_url
            model_kwargs["api_key"] = litellm_api_key

            print(f"🔧 Using LiteLLM proxy from environment")
            print(f"   Model: {self.model_name}")
            print(f"   Base URL: {litellm_base_url}")

            model = ChatOpenAI(
                model=self.model_name,
                **model_kwargs
            )

        # Bind tools (only if model supports function calling)
        if self.tools:
            # For SAP AI Core, check capability before binding tools
            if is_sap_ai_core:
                # Tools will be handled gracefully by ChatSAPAICore
                # It will check capabilities and skip tools if not supported
                model = model.bind_tools(self.tools)
            else:
                model = model.bind_tools(self.tools)

        return model

    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow with analysis and conditional logic."""
        workflow = StateGraph(IntelligentAgentState)

        # Nodes
        workflow.add_node("agent", self._agent_node)
        if self.tools:
            workflow.add_node("tools", ToolNode(self.tools))

        # Entry point
        workflow.set_entry_point("agent")

        # Edges - Simple flow like DataQueryAgent
        if self.tools:
            workflow.add_conditional_edges(
                "agent",
                self._should_continue,
                {
                    "continue": "tools",
                    "end": END,
                }
            )
            # After tools, go back to agent (no separate analyze node)
            workflow.add_edge("tools", "agent")
        else:
            workflow.add_edge("agent", END)

        return workflow.compile()

    def _agent_node(self, state: IntelligentAgentState) -> Dict[str, Any]:
        """Agent reasoning node."""
        messages = state["messages"]

        # Build message list for LLM
        llm_messages = []

        # Add system message if first turn
        if len(messages) == 1:
            llm_messages.append(SystemMessage(content=self.system_message))

        # Add all conversation messages
        llm_messages.extend(messages)

        # Filter out empty assistant messages (LiteLLM rejects these)
        filtered_messages = []
        for msg in llm_messages:
            # Keep all non-assistant messages
            if not isinstance(msg, AIMessage):
                filtered_messages.append(msg)
            # Keep assistant messages that have content or tool calls
            elif (hasattr(msg, 'content') and msg.content and msg.content.strip()) or \
                 (hasattr(msg, 'tool_calls') and msg.tool_calls):
                filtered_messages.append(msg)
            else:
                print(f"⚠️ Filtering out empty assistant message")

        # Call LLM with filtered messages
        response = self.model.invoke(filtered_messages)

        return {"messages": [response]}

    def _analyze_node(self, state: IntelligentAgentState) -> Dict[str, Any]:
        """Analyze tool outputs and update context."""
        messages = state["messages"]

        # Find latest tool messages
        tool_messages = [m for m in messages if hasattr(m, "name") and m.name]

        if not tool_messages:
            return {}

        # Analyze each tool output
        analyses = []
        for tool_msg in tool_messages:
            try:
                output = json.loads(tool_msg.content) if isinstance(tool_msg.content, str) else tool_msg.content
                analysis = ToolOutputAnalyzer.analyze(tool_msg.name, output)
                analyses.append(analysis)

                # Store for later reference
                self.tool_outputs[tool_msg.name] = output
                self.analysis_results[tool_msg.name] = analysis
            except Exception as e:
                print(f"Analysis failed for {tool_msg.name}: {e}")

        # Create analysis summary for agent
        if analyses:
            summary = {
                "tools_called": [a["tool_name"] for a in analyses],
                "total_records": sum(a["row_count"] for a in analyses),
                "actionable_fields": [
                    f for a in analyses for f in a["actionable_fields"]
                ],
                "suggestions": [
                    s for a in analyses for s in a["suggestions"]
                ],
            }

            return {"analysis_context": summary}

        return {}

    def _should_continue(self, state: IntelligentAgentState) -> str:
        """Decide next step after agent reasoning."""
        messages = state["messages"]
        last_message = messages[-1]

        # If agent wants to use tools, continue to tools node
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"

        # Otherwise, done
        return "end"

    async def execute(
        self,
        query: str,
        max_iterations: int = 10,
    ) -> Dict[str, Any]:
        """
        Execute query with intelligent tool usage and conditional logic.

        Args:
            query: User query (can include conditional logic)
            max_iterations: Max agent reasoning loops

        Returns:
            Dict with:
            - final_response: Agent's final answer
            - tool_outputs: All tool results
            - analysis: Tool output analyses
            - actions_taken: List of actions executed
        """
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "notebook_id": self.notebook_id,
            "session_id": self.session_id,
            "tools_available": [t.name for t in self.tools],
            "tool_outputs": {},
            "analysis_context": {},
            "next_actions": [],
            "conditional_branches": {},
        }

        # Run graph
        iteration = 0
        state = initial_state

        while iteration < max_iterations:
            state = await self.graph.ainvoke(state)

            # Check if done
            last_message = state["messages"][-1]
            if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
                break

            iteration += 1

        # Extract final response
        final_message = state["messages"][-1]
        final_response = final_message.content if hasattr(final_message, "content") else str(final_message)

        return {
            "final_response": final_response,
            "tool_outputs": self.tool_outputs,
            "analysis": self.analysis_results,
            "actions_taken": self._extract_actions(state["messages"]),
            "iterations": iteration,
        }

    def _extract_actions(self, messages: List[BaseMessage]) -> List[str]:
        """Extract list of actions taken from message history."""
        actions = []

        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    actions.append(f"Called {tc.get('name', 'unknown')}")

        return actions


# ============================================================================
# Convenience functions
# ============================================================================

async def create_intelligent_agent(
    model_name: str,
    notebook_id: str,
    user_id: str,
    session_id: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> IntelligentAgent:
    """
    Factory function to create an intelligent agent with all available tools.

    Args:
        model_name: LLM model name
        notebook_id: Notebook UUID
        user_id: User UUID for permissions
        session_id: Optional chat session ID
        api_key: Optional API key for LiteLLM proxy
        base_url: Optional base URL for LiteLLM proxy

    Returns:
        Configured IntelligentAgent
    """
    from api.services.tool_factory import ToolFactory

    factory = ToolFactory()
    tools = await factory.create_tools_for_session(notebook_id, user_id, session_id)

    return IntelligentAgent(
        model_name=model_name,
        notebook_id=notebook_id,
        tools=tools,
        session_id=session_id,
        api_key=api_key,
        base_url=base_url,
    )
