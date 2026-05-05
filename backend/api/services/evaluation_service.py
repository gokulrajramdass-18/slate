"""
Agent Evaluation Service

Orchestrates judge agent evaluations of team execution results.
Supports both final result and per-agent output evaluation.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from open_notebook.database.repository import repo_query, repo_execute

logger = logging.getLogger(__name__)


class EvaluationService:
    """Service for managing judge agent evaluations."""

    async def get_evaluation_config(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Get evaluation configuration for a team."""
        rows = await repo_query(
            "SELECT * FROM agent_evaluation_configs WHERE team_id = :team_id",
            {"team_id": team_id}
        )
        return dict(rows[0]) if rows else None

    async def create_evaluation_config(
        self,
        team_id: str,
        enabled: bool = True,
        auto_evaluate: bool = True,
        scope: str = "all",
        scoring_scale: str = "0-10"
    ) -> str:
        """Create evaluation config for a team."""
        config_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        await repo_execute(
            """INSERT INTO agent_evaluation_configs
               (id, team_id, enabled, auto_evaluate, scope, scoring_scale, created, updated)
               VALUES (:id, :team_id, :enabled, :auto_evaluate, :scope, :scoring_scale, :created, :updated)""",
            {
                "id": config_id,
                "team_id": team_id,
                "enabled": 1 if enabled else 0,
                "auto_evaluate": 1 if auto_evaluate else 0,
                "scope": scope,
                "scoring_scale": scoring_scale,
                "created": now,
                "updated": now
            }
        )
        return config_id

    async def update_evaluation_config(
        self,
        team_id: str,
        **updates
    ) -> None:
        """Update evaluation config for a team."""
        now = datetime.utcnow().isoformat()
        updates["updated"] = now

        # Convert boolean fields to 0/1 for SQLite
        if "enabled" in updates:
            updates["enabled"] = 1 if updates["enabled"] else 0
        if "auto_evaluate" in updates:
            updates["auto_evaluate"] = 1 if updates["auto_evaluate"] else 0

        set_clause = ", ".join(f"{k} = :{k}" for k in updates.keys())
        updates["team_id"] = team_id

        await repo_execute(
            f"UPDATE agent_evaluation_configs SET {set_clause} WHERE team_id = :team_id",
            updates
        )

    async def should_evaluate(self, team_id: str, execution_id: str) -> bool:
        """Check if evaluation should be performed for this execution."""
        config = await self.get_evaluation_config(team_id)
        if not config or not config.get("enabled"):
            return False

        # Check if judge agent exists in team
        judge_rows = await repo_query(
            "SELECT id FROM agent_instances WHERE team_id = :team_id AND role = 'judge'",
            {"team_id": team_id}
        )

        return len(judge_rows) > 0 and config.get("auto_evaluate", True)

    async def trigger_evaluation(
        self,
        execution_id: str,
        team_id: str,
        llm,
        force_scope: Optional[str] = None
    ) -> List[str]:
        """
        Trigger judge evaluation of execution results.

        Returns list of evaluation IDs created.
        """
        # Get evaluation config
        config = await self.get_evaluation_config(team_id)
        if not config:
            logger.warning(f"No evaluation config for team {team_id}")
            return []

        scope = force_scope or config.get("scope", "all")

        # Get judge agent
        judge_rows = await repo_query(
            "SELECT id, name, system_prompt FROM agent_instances WHERE team_id = :team_id AND role = 'judge'",
            {"team_id": team_id}
        )
        if not judge_rows:
            logger.warning(f"No judge agent found for team {team_id}")
            return []

        judge_agent = judge_rows[0]

        # Get execution data
        execution = await self._get_execution_data(execution_id)

        evaluation_ids = []

        # Evaluate individual agent outputs
        if scope in ["agents_only", "all"]:
            for task in execution.get("tasks", []):
                if task.get("assigned_agent_id") and task.get("status") == "completed":
                    try:
                        eval_id = await self._evaluate_agent_output(
                            execution_id=execution_id,
                            team_id=team_id,
                            judge_agent_id=judge_agent["id"],
                            target_agent_id=task["assigned_agent_id"],
                            output_data=task.get("output_data", {}),
                            llm=llm,
                            judge_prompt=judge_agent.get("system_prompt")
                        )
                        evaluation_ids.append(eval_id)
                    except Exception as e:
                        logger.error(f"Failed to evaluate agent output: {e}")

        # Evaluate final result
        if scope in ["final_only", "all"]:
            try:
                eval_id = await self._evaluate_final_result(
                    execution_id=execution_id,
                    team_id=team_id,
                    judge_agent_id=judge_agent["id"],
                    result=execution.get("result"),
                    llm=llm,
                    judge_prompt=judge_agent.get("system_prompt")
                )
                evaluation_ids.append(eval_id)
            except Exception as e:
                logger.error(f"Failed to evaluate final result: {e}")

        return evaluation_ids

    async def _get_execution_data(self, execution_id: str) -> Dict[str, Any]:
        """Fetch full execution data for evaluation."""
        exec_rows = await repo_query(
            "SELECT * FROM agent_executions WHERE id = :id",
            {"id": execution_id}
        )
        if not exec_rows:
            raise ValueError(f"Execution {execution_id} not found")

        execution = dict(exec_rows[0])

        # Get tasks
        task_rows = await repo_query(
            "SELECT * FROM agent_tasks WHERE execution_id = :execution_id",
            {"execution_id": execution_id}
        )
        execution["tasks"] = [dict(t) for t in task_rows]

        # Get steps
        step_rows = await repo_query(
            "SELECT * FROM workflow_steps WHERE execution_id = :execution_id ORDER BY step_number",
            {"execution_id": execution_id}
        )
        execution["steps"] = [dict(s) for s in step_rows]

        return execution

    async def _evaluate_agent_output(
        self,
        execution_id: str,
        team_id: str,
        judge_agent_id: str,
        target_agent_id: str,
        output_data: Dict[str, Any],
        llm,
        judge_prompt: Optional[str]
    ) -> str:
        """Evaluate individual agent output."""
        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(
            target_type="agent_output",
            content=output_data,
            judge_prompt=judge_prompt
        )

        # Call LLM for evaluation
        response = await llm.ainvoke(prompt)

        # Parse evaluation from response
        evaluation = self._parse_evaluation_response(response.content)

        # Save evaluation
        eval_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        await repo_execute(
            """INSERT INTO agent_execution_evaluations
               (id, execution_id, team_id, judge_agent_id, scope, target_agent_id,
                overall_score, criteria_scores, feedback, approval_status, confidence, created)
               VALUES (:id, :execution_id, :team_id, :judge_agent_id, :scope, :target_agent_id,
                       :overall_score, :criteria_scores, :feedback, :approval_status, :confidence, :created)""",
            {
                "id": eval_id,
                "execution_id": execution_id,
                "team_id": team_id,
                "judge_agent_id": judge_agent_id,
                "scope": "agent_output",
                "target_agent_id": target_agent_id,
                "overall_score": evaluation["overall_score"],
                "criteria_scores": json.dumps(evaluation["criteria_scores"]),
                "feedback": evaluation["feedback"],
                "approval_status": evaluation["approval_status"],
                "confidence": evaluation.get("confidence", 0.9),
                "created": now
            }
        )

        return eval_id

    async def _evaluate_final_result(
        self,
        execution_id: str,
        team_id: str,
        judge_agent_id: str,
        result: str,
        llm,
        judge_prompt: Optional[str]
    ) -> str:
        """Evaluate final synthesized result."""
        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(
            target_type="final_result",
            content=result,
            judge_prompt=judge_prompt
        )

        # Call LLM for evaluation
        response = await llm.ainvoke(prompt)

        # Parse evaluation
        evaluation = self._parse_evaluation_response(response.content)

        # Save evaluation
        eval_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        await repo_execute(
            """INSERT INTO agent_execution_evaluations
               (id, execution_id, team_id, judge_agent_id, scope, target_agent_id,
                overall_score, criteria_scores, feedback, approval_status, confidence, created)
               VALUES (:id, :execution_id, :team_id, :judge_agent_id, :scope, :target_agent_id,
                       :overall_score, :criteria_scores, :feedback, :approval_status, :confidence, :created)""",
            {
                "id": eval_id,
                "execution_id": execution_id,
                "team_id": team_id,
                "judge_agent_id": judge_agent_id,
                "scope": "final_result",
                "target_agent_id": None,
                "overall_score": evaluation["overall_score"],
                "criteria_scores": json.dumps(evaluation["criteria_scores"]),
                "feedback": evaluation["feedback"],
                "approval_status": evaluation["approval_status"],
                "confidence": evaluation.get("confidence", 0.9),
                "created": now
            }
        )

        return eval_id

    def _build_evaluation_prompt(
        self,
        target_type: str,
        content: Any,
        judge_prompt: Optional[str]
    ) -> str:
        """Build prompt for judge agent evaluation."""
        base_prompt = judge_prompt or """You are a quality reviewer evaluating team outputs.

Evaluate the following content across these criteria:
1. Accuracy & Correctness (0-10)
2. Completeness & Coverage (0-10)
3. Quality & Clarity (0-10)
4. Consistency & Coherence (0-10)

Provide your evaluation in this format:
OVERALL_SCORE: [0-10]
ACCURACY: [0-10]
COMPLETENESS: [0-10]
QUALITY: [0-10]
CONSISTENCY: [0-10]
APPROVAL: [approved/needs_revision/requires_rework]
CONFIDENCE: [0.0-1.0]
FEEDBACK: [Your detailed feedback]
"""

        content_str = json.dumps(content) if isinstance(content, dict) else str(content)

        return f"""{base_prompt}

TARGET TYPE: {target_type}

CONTENT TO EVALUATE:
{content_str}
"""

    def _parse_evaluation_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured evaluation."""
        lines = response.split("\n")
        evaluation = {
            "criteria_scores": {},
            "overall_score": 0.0,
            "feedback": "",
            "approval_status": "needs_revision"
        }

        feedback_lines = []
        in_feedback = False

        for line in lines:
            line = line.strip()
            if line.startswith("OVERALL_SCORE:"):
                try:
                    evaluation["overall_score"] = float(line.split(":", 1)[1].strip())
                except:
                    evaluation["overall_score"] = 5.0
            elif line.startswith("ACCURACY:"):
                try:
                    evaluation["criteria_scores"]["accuracy"] = float(line.split(":", 1)[1].strip())
                except:
                    evaluation["criteria_scores"]["accuracy"] = 5.0
            elif line.startswith("COMPLETENESS:"):
                try:
                    evaluation["criteria_scores"]["completeness"] = float(line.split(":", 1)[1].strip())
                except:
                    evaluation["criteria_scores"]["completeness"] = 5.0
            elif line.startswith("QUALITY:"):
                try:
                    evaluation["criteria_scores"]["quality"] = float(line.split(":", 1)[1].strip())
                except:
                    evaluation["criteria_scores"]["quality"] = 5.0
            elif line.startswith("CONSISTENCY:"):
                try:
                    evaluation["criteria_scores"]["consistency"] = float(line.split(":", 1)[1].strip())
                except:
                    evaluation["criteria_scores"]["consistency"] = 5.0
            elif line.startswith("APPROVAL:"):
                approval = line.split(":", 1)[1].strip().lower()
                if "approved" in approval:
                    evaluation["approval_status"] = "approved"
                elif "rework" in approval:
                    evaluation["approval_status"] = "requires_rework"
                else:
                    evaluation["approval_status"] = "needs_revision"
            elif line.startswith("CONFIDENCE:"):
                try:
                    evaluation["confidence"] = float(line.split(":", 1)[1].strip())
                except:
                    evaluation["confidence"] = 0.8
            elif line.startswith("FEEDBACK:"):
                in_feedback = True
                feedback_lines.append(line.split(":", 1)[1].strip() if ":" in line else "")
            elif in_feedback and line:
                feedback_lines.append(line)

        evaluation["feedback"] = " ".join(feedback_lines).strip()

        # Calculate overall score from criteria if not provided
        if evaluation["overall_score"] == 0.0 and evaluation["criteria_scores"]:
            scores = list(evaluation["criteria_scores"].values())
            if scores:
                evaluation["overall_score"] = sum(scores) / len(scores)

        return evaluation

    async def get_evaluations_for_execution(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get all evaluations for an execution."""
        rows = await repo_query(
            """SELECT e.*, ai.name as judge_name, target.name as target_agent_name
               FROM agent_execution_evaluations e
               LEFT JOIN agent_instances ai ON e.judge_agent_id = ai.id
               LEFT JOIN agent_instances target ON e.target_agent_id = target.id
               WHERE e.execution_id = :execution_id
               ORDER BY e.created""",
            {"execution_id": execution_id}
        )

        evaluations = []
        for row in rows:
            eval_dict = dict(row)
            # Parse criteria_scores JSON
            if eval_dict.get("criteria_scores"):
                try:
                    eval_dict["criteria_scores"] = json.loads(eval_dict["criteria_scores"])
                except:
                    eval_dict["criteria_scores"] = {}
            evaluations.append(eval_dict)

        return evaluations


# Singleton instance
_evaluation_service = EvaluationService()


async def get_evaluation_service() -> EvaluationService:
    """Get evaluation service instance."""
    return _evaluation_service
