"""
Workspace Plan Generator Service

Generates execution plans for existing workspaces by analyzing their content and structure.
Uses LLM to create phases, tasks, and agent assignments based on workspace context.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

import httpx

from open_notebook.database.repository import repo_query, repo_execute

logger = logging.getLogger(__name__)


PLAN_GENERATION_SYSTEM_PROMPT = """You are an AI workspace planner that creates structured execution plans for research and analysis workspaces.

Given information about a workspace (sources, notes, goal), you create a detailed execution plan with:
1. **Phases**: Logical stages of work (e.g., "Data Exploration", "Research & Analysis", "Documentation")
2. **Tasks**: Specific actions within each phase with clear objectives
3. **Collaboration**: How agents should work together (if applicable)

**Output Format** (strict JSON):
```json
{
  "phases": [
    {
      "phase": "Phase Name",
      "tasks": [
        {
          "name": "Task Name",
          "description": "Detailed description of what needs to be done",
          "estimated_duration": 30,
          "dependencies": [],
          "required_tools": ["tool_name"],
          "required_sources": ["source_id"]
        }
      ]
    }
  ],
  "collaboration_graph": {
    "agents": ["research_agent", "analyst_agent"],
    "coordination": "sequential"
  },
  "estimated_total_duration": 180
}
```

**Guidelines**:
- Create 2-4 phases maximum
- Each phase should have 2-5 tasks
- Tasks should be concrete and actionable
- Use realistic time estimates (minutes)
- Consider the workspace's goal and available resources
"""


class WorkspacePlanGeneratorService:
    """Service for generating execution plans for existing workspaces"""

    @staticmethod
    async def _call_llm(prompt: str, system_prompt: str) -> str:
        """
        Call the configured LLM with a prompt and return the raw text response.

        Args:
            prompt: The user prompt to send
            system_prompt: The system prompt

        Returns:
            Raw assistant message content
        """
        from api.services.llm_client import resolve_llm_credential, call_llm_chat

        credential = await resolve_llm_credential()
        return await call_llm_chat(
            credential,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
            timeout=120.0,
        )

    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from an LLM response that may contain
        markdown fences or surrounding prose.
        """
        cleaned = text.strip()

        # Strip markdown code fences
        json_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL
        )
        if json_match:
            cleaned = json_match.group(1).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fall back: find first JSON object in text
            brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

        logger.warning("Could not parse LLM JSON response: %s", cleaned[:200])
        return {}

    @staticmethod
    async def analyze_workspace_context(workspace_id: str) -> Dict[str, Any]:
        """
        Analyze workspace to gather context for plan generation.

        Returns:
            Dictionary with workspace details, sources, notes, etc.
        """
        # Get workspace details
        workspace_sql = "SELECT * FROM notebooks WHERE id = :workspace_id"
        workspace_result = await repo_query(workspace_sql, {"workspace_id": workspace_id})

        if not workspace_result:
            raise ValueError(f"Workspace {workspace_id} not found")

        workspace = dict(workspace_result[0])

        # Get sources
        sources_sql = """
            SELECT s.id, s.title, s.source_type,
                   SUBSTR(s.full_text, 1, 200) as description
            FROM sources s
            INNER JOIN notebook_source ns ON s.id = ns.source_id
            WHERE ns.notebook_id = :workspace_id
        """
        sources = await repo_query(sources_sql, {"workspace_id": workspace_id})

        # Get notes count
        notes_sql = """
            SELECT COUNT(*) as count
            FROM notebook_note nn
            WHERE nn.notebook_id = :workspace_id
        """
        notes_result = await repo_query(notes_sql, {"workspace_id": workspace_id})
        notes_count = notes_result[0]["count"] if notes_result else 0

        # Get chat sessions (indicates interactive work)
        chat_sql = """
            SELECT COUNT(*) as count
            FROM chat_sessions
            WHERE notebook_id = :workspace_id
        """
        chat_result = await repo_query(chat_sql, {"workspace_id": workspace_id})
        chat_count = chat_result[0]["count"] if chat_result else 0

        return {
            "workspace": workspace,
            "sources": [dict(s) for s in sources],
            "notes_count": notes_count,
            "chat_sessions_count": chat_count,
        }

    @staticmethod
    def build_plan_generation_prompt(context: Dict[str, Any]) -> str:
        """
        Build prompt for LLM to generate execution plan.

        Args:
            context: Workspace context from analyze_workspace_context

        Returns:
            Formatted prompt string
        """
        workspace = context["workspace"]
        sources = context["sources"]

        prompt = f"""Generate an execution plan for the following workspace:

**Workspace Details**:
- Name: {workspace['name']}
- Goal: {workspace.get('goal') or 'General research and analysis workspace'}
- Description: {workspace.get('description') or 'No specific description'}

**Available Sources** ({len(sources)} total):
"""

        for source in sources[:10]:  # Limit to first 10 sources
            prompt += f"- {source['title']} ({source['source_type']})\n"

        if len(sources) > 10:
            prompt += f"... and {len(sources) - 10} more sources\n"

        prompt += f"""
**Additional Context**:
- Notes created: {context['notes_count']}
- Chat sessions: {context['chat_sessions_count']}

**Your Task**:
Create a realistic execution plan that outlines how someone would work with this workspace.
Consider the goal, available sources, and workspace type.

Generate a plan with 2-4 phases and appropriate tasks. Return ONLY the JSON structure, no other text.
"""

        return prompt

    @staticmethod
    async def generate_plan(workspace_id: str, user_id: str) -> Dict[str, Any]:
        """
        Generate execution plan for workspace using LLM.

        Args:
            workspace_id: Workspace UUID
            user_id: User requesting plan generation

        Returns:
            Dictionary with generated plan structure
        """
        try:
            # Analyze workspace
            logger.info(f"Analyzing workspace {workspace_id} for plan generation")
            context = await WorkspacePlanGeneratorService.analyze_workspace_context(workspace_id)

            # Build prompt
            prompt = WorkspacePlanGeneratorService.build_plan_generation_prompt(context)

            # Call LLM
            logger.info(f"Calling LLM to generate plan for workspace {workspace_id}")
            response = await WorkspacePlanGeneratorService._call_llm(
                prompt=prompt,
                system_prompt=PLAN_GENERATION_SYSTEM_PROMPT,
            )

            # Parse response
            plan_data = WorkspacePlanGeneratorService._parse_json_response(response)

            # Validate plan structure
            if "phases" not in plan_data or not plan_data["phases"]:
                raise ValueError("Generated plan missing 'phases' field or phases are empty")

            logger.info(f"Successfully generated plan with {len(plan_data['phases'])} phases")

            return {
                "success": True,
                "plan": plan_data,
                "workspace_name": context["workspace"]["name"],
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {str(e)}")
            logger.error(f"Response was: {response[:500] if 'response' in locals() else 'N/A'}")
            raise ValueError(f"Failed to parse generated plan: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating plan for workspace {workspace_id}: {str(e)}")
            raise

    @staticmethod
    async def save_plan(workspace_id: str, plan_data: Dict[str, Any], user_id: str) -> str:
        """
        Save generated plan to workspace_plans table.

        Args:
            workspace_id: Workspace UUID
            plan_data: Plan structure from generate_plan
            user_id: User saving the plan

        Returns:
            Plan ID
        """
        from open_notebook.domain.guided_workspace import WorkspacePlan

        # Check if plan already exists
        existing_sql = "SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id"
        existing = await repo_query(existing_sql, {"workspace_id": workspace_id})

        if existing:
            # Update existing plan
            plan_id = existing[0]["id"]
            logger.info(f"Updating existing plan {plan_id} for workspace {workspace_id}")

            update_sql = """
                UPDATE workspace_plans
                SET phases = :phases,
                    collaboration_graph = :collaboration_graph,
                    status = :status,
                    updated_at = :updated_at
                WHERE id = :plan_id
            """
            await repo_execute(update_sql, {
                "plan_id": plan_id,
                "phases": json.dumps(plan_data.get("phases", [])),
                "collaboration_graph": json.dumps(plan_data.get("collaboration_graph", {})),
                "status": "pending",
                "updated_at": datetime.utcnow().isoformat(),
            })
        else:
            # Create new plan
            logger.info(f"Creating new plan for workspace {workspace_id}")

            plan = WorkspacePlan(
                workspace_id=workspace_id,
                goal=plan_data.get("goal", "Generated plan"),
                phases=json.dumps(plan_data.get("phases", [])),
                collaboration_graph=json.dumps(plan_data.get("collaboration_graph", {})),
                status="pending",
            )
            await plan.save()
            plan_id = plan.id

        logger.info(f"Plan saved successfully with ID: {plan_id}")
        return plan_id

    @staticmethod
    async def create_tasks_from_plan(plan_id: str, plan_data: Dict[str, Any]) -> None:
        """
        Create individual task records in workspace_plan_tasks from plan phases.

        Args:
            plan_id: Workspace plan UUID
            plan_data: Plan structure with phases and tasks
        """
        import uuid

        logger.info(f"Creating tasks from plan {plan_id}")

        phases = plan_data.get("phases", [])

        for phase in phases:
            phase_name = phase.get("phase", "Unnamed Phase")
            tasks = phase.get("tasks", [])

            for task in tasks:
                task_id = str(uuid.uuid4())
                now = datetime.utcnow().isoformat()

                # Extract task data
                task_name = task.get("name", "Unnamed Task")
                description = task.get("description", "")
                estimated_duration = task.get("estimated_duration", 30)
                dependencies = task.get("dependencies", [])
                required_tools = task.get("required_tools", [])
                required_sources = task.get("required_sources", [])

                # Insert task
                await repo_execute("""
                    INSERT INTO workspace_plan_tasks (
                        id, plan_id, phase_name, name, description,
                        assigned_agent_id, status, estimated_duration,
                        dependencies, required_tools, required_sources,
                        created, updated
                    ) VALUES (
                        :id, :plan_id, :phase_name, :name, :description,
                        :assigned_agent_id, :status, :estimated_duration,
                        :dependencies, :required_tools, :required_sources,
                        :created, :updated
                    )
                """, {
                    "id": task_id,
                    "plan_id": plan_id,
                    "phase_name": phase_name,
                    "name": task_name,
                    "description": description,
                    "assigned_agent_id": None,  # Can be set later
                    "status": "pending",
                    "estimated_duration": estimated_duration,
                    "dependencies": json.dumps(dependencies),
                    "required_tools": json.dumps(required_tools),
                    "required_sources": json.dumps(required_sources),
                    "created": now,
                    "updated": now
                })

                logger.info(f"Created task {task_id}: {task_name} in phase {phase_name}")

    @staticmethod
    async def generate_and_save_plan(workspace_id: str, user_id: str) -> Dict[str, Any]:
        """
        Complete flow: generate plan and save it to database.

        Args:
            workspace_id: Workspace UUID
            user_id: User requesting plan generation

        Returns:
            Dictionary with plan_id and plan details
        """
        # Generate plan
        result = await WorkspacePlanGeneratorService.generate_plan(workspace_id, user_id)

        # Save plan
        plan_id = await WorkspacePlanGeneratorService.save_plan(
            workspace_id=workspace_id,
            plan_data=result["plan"],
            user_id=user_id
        )

        # Create individual task records from phases
        await WorkspacePlanGeneratorService.create_tasks_from_plan(
            plan_id=plan_id,
            plan_data=result["plan"]
        )

        return {
            "plan_id": plan_id,
            "workspace_id": workspace_id,
            "workspace_name": result["workspace_name"],
            "phases_count": len(result["plan"]["phases"]),
            "plan": result["plan"],
        }
