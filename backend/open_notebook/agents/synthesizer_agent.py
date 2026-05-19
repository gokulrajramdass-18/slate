"""
Synthesizer Agent - Combines results from multiple agents into a unified response.

Takes findings, tool results, and messages from multiple agents and produces
a coherent synthesis with citations, resolved contradictions, and merged data.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from api.services.prompt_loader import load_prompt


# Fallback prompt
SYNTHESIS_SYSTEM_PROMPT = """You are a synthesis agent. Your job is to combine findings from multiple research agents into a single, coherent response.

Rules:
1. Merge overlapping information without repetition.
2. When agents disagree, note the contradiction and present both perspectives.
3. Cite which agent or source provided each piece of information using [Agent: name] notation.
4. Prioritize data from tool results (database queries, API calls) over general knowledge.
5. Structure the output clearly with sections if the combined content warrants it.
6. If tool results contain tabular data, summarize key insights rather than repeating raw data.

Output a well-structured markdown response."""


class SynthesizerAgent:
    """
    Combines results from multiple agents into a unified response.

    Responsibilities:
    - Merge findings from researcher and analyst agents
    - Resolve contradictions between agent outputs
    - Generate unified response with citations
    - Merge tool results from different agents
    """

    def __init__(
        self,
        model_name: str,
        agent_steps_callback: Optional[callable] = None,
    ):
        """
        Initialize synthesizer.

        Args:
            model_name: LLM model name for synthesis
            agent_steps_callback: Optional callback(step_dict) for streaming steps
        """
        self.model_name = model_name
        self.agent_steps_callback = agent_steps_callback
        self.model = self._create_model()

    def _create_model(self):
        """Create LLM model."""
        # Check for SAP AI Core model
        is_sap_ai_core = self.model_name.startswith("sap-ai-core-")

        if is_sap_ai_core:
            # SAP AI Core integration
            from open_notebook.llm.chat_sap_ai_core_sdk import ChatSAPAICore
            from api.services.sap_ai_core_service import SAPAICoreService, SAPAICoreConfig
            from api.routers.credentials import _credentials_store
            import json

            # Extract deployment ID
            deployment_id = self.model_name.replace("sap-ai-core-", "")

            # Find credential
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

            # Parse config
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

            return ChatSAPAICore(
                service=SAPAICoreService(config),
                deployment_id=deployment_id,
                temperature=0.3,
                max_tokens=4096,
            )

        # Check for Anthropic
        is_anthropic = any(x in self.model_name.lower() for x in ["claude", "anthropic"])

        if is_anthropic:
            return ChatAnthropic(
                model=self.model_name,
                temperature=0.3,
                max_tokens=4096,
            )
        else:
            return ChatOpenAI(
                model=self.model_name,
                temperature=0.3,
                max_tokens=4096,
            )

    def _emit_step(
        self,
        step_type: str,
        content: str,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Emit an agent step for UI streaming."""
        step = {
            "step_type": step_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "metadata": metadata or {},
        }
        if self.agent_steps_callback:
            try:
                self.agent_steps_callback(step)
            except Exception:
                pass
        return step

    async def synthesize(
        self,
        original_query: str,
        agent_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Synthesize results from multiple agents.

        Args:
            original_query: The user's original question
            agent_results: List of dicts with keys:
                - agent_name: str
                - agent_role: str
                - response_text: str
                - tool_results: List[dict] (optional)
                - agent_steps: List[dict] (optional)

        Returns:
            Dict with:
                - content: synthesized markdown text
                - tool_results: merged tool results from all agents
                - agent_steps: merged agent steps
                - citations: list of citation dicts
        """
        self._emit_step(
            "synthesizing",
            "Combining results from all agents into a unified response",
            status="running",
            metadata={"agent_count": len(agent_results)},
        )

        # Build context from all agent results
        context_parts = []
        all_tool_results = []
        all_agent_steps = []

        for result in agent_results:
            agent_name = result.get("agent_name", "unknown")
            agent_role = result.get("agent_role", "agent")
            response = result.get("response_text", "")
            tool_results = result.get("tool_results", [])
            steps = result.get("agent_steps", [])

            context_parts.append(
                f"## Agent: {agent_name} (Role: {agent_role})\n\n{response}"
            )

            # Prefix tool results with agent name for traceability
            for tr in tool_results:
                tr_copy = dict(tr)
                tr_copy["source_agent"] = agent_name
                all_tool_results.append(tr_copy)

            for step in steps:
                step_copy = dict(step)
                step_copy.setdefault("metadata", {})["source_agent"] = agent_name
                all_agent_steps.append(step_copy)

        combined_context = "\n\n---\n\n".join(context_parts)

        # Summarize tool results for the LLM
        tool_summary = ""
        if all_tool_results:
            summaries = []
            for tr in all_tool_results:
                name = tr.get("tool_name", "unknown")
                rtype = tr.get("result_type", "unknown")
                agent = tr.get("source_agent", "unknown")
                summaries.append(f"- Tool '{name}' from {agent}: {rtype} result")
            tool_summary = "\n\nTool Results Summary:\n" + "\n".join(summaries)

        prompt = f"""Synthesize the following agent outputs into a single coherent response.

Original User Query: {original_query}

Agent Outputs:
{combined_context}
{tool_summary}

Create a unified response that:
1. Directly answers the user's question
2. Merges insights from all agents
3. Notes any contradictions
4. Cites which agent provided key information using [Agent: name] notation"""

        try:
            # Load system prompt from database
            system_prompt = await load_prompt(
                "agent_synthesis",
                variables={},
                fallback=SYNTHESIS_SYSTEM_PROMPT
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ]
            response = await self.model.ainvoke(messages)
            content = response.content

            self._emit_step(
                "synthesizing",
                f"Synthesis complete ({len(content)} chars)",
                status="completed",
                metadata={"agent_count": len(agent_results), "output_length": len(content)},
            )

            # Extract citations from agent results
            citations = [
                {"agent_name": r.get("agent_name", "unknown"), "agent_role": r.get("agent_role", "agent")}
                for r in agent_results
            ]

            return {
                "content": content,
                "tool_results": all_tool_results,
                "agent_steps": all_agent_steps,
                "citations": citations,
            }

        except Exception as e:
            self._emit_step(
                "synthesizing",
                f"Synthesis failed: {e}",
                status="error",
            )
            # Fallback: concatenate agent responses
            fallback_parts = []
            for result in agent_results:
                name = result.get("agent_name", "Agent")
                text = result.get("response_text", "")
                fallback_parts.append(f"**{name}:**\n{text}")

            return {
                "content": "\n\n---\n\n".join(fallback_parts),
                "tool_results": all_tool_results,
                "agent_steps": all_agent_steps,
                "citations": [],
            }
