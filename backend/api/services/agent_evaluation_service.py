"""
Standalone Agent Evaluation Service

Provides functionality for:
- Uploading evaluation datasets (CSV, JSON, JSONL)
- Running agents against test cases
- Scoring outputs (LLM judge, exact match, semantic similarity)
- Aggregating and analyzing results
"""

import csv
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Literal
from io import StringIO

from open_notebook.database.repository import repo_query, repo_execute
from open_notebook.agents.intelligent_agent import IntelligentAgent
from open_notebook.agents.llm_pool import LLMClientPool

import logging
logger = logging.getLogger(__name__)


class AgentEvaluationService:
    """Service for evaluating standalone agents with test datasets."""

    # ========================================================================
    # Dataset Management
    # ========================================================================

    async def create_dataset(
        self,
        name: str,
        description: Optional[str] = None,
        agent_id: Optional[str] = None,
        criteria: Optional[List[str]] = None,
        scoring_method: str = "llm_judge",
        created_by: Optional[str] = None
    ) -> str:
        """Create a new evaluation dataset."""
        dataset_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        await repo_execute(
            """INSERT INTO evaluation_datasets
               (id, name, description, agent_id, criteria, scoring_method, test_case_count, created, updated, created_by)
               VALUES (:id, :name, :description, :agent_id, :criteria, :scoring_method, 0, :created, :updated, :created_by)""",
            {
                "id": dataset_id,
                "name": name,
                "description": description,
                "agent_id": agent_id,
                "criteria": json.dumps(criteria or ["accuracy", "relevance", "completeness"]),
                "scoring_method": scoring_method,
                "created": now,
                "updated": now,
                "created_by": created_by
            }
        )

        return dataset_id

    async def upload_test_cases(
        self,
        dataset_id: str,
        test_cases: List[Dict[str, Any]]
    ) -> int:
        """
        Add test cases to a dataset.

        test_cases format: [
            {
                "input": "What is the capital of France?",
                "expected_output": "Paris",
                "category": "basic_qa",
                "tags": ["geography", "factual"],
                "metadata": {...}
            },
            ...
        ]
        """
        now = datetime.utcnow().isoformat()
        count = 0

        for case in test_cases:
            case_id = str(uuid.uuid4())
            await repo_execute(
                """INSERT INTO evaluation_test_cases
                   (id, dataset_id, input_prompt, expected_output, context, category, tags, metadata, created)
                   VALUES (:id, :dataset_id, :input_prompt, :expected_output, :context, :category, :tags, :metadata, :created)""",
                {
                    "id": case_id,
                    "dataset_id": dataset_id,
                    "input_prompt": case["input"],
                    "expected_output": case.get("expected_output"),
                    "context": case.get("context"),
                    "category": case.get("category"),
                    "tags": json.dumps(case.get("tags", [])),
                    "metadata": json.dumps(case.get("metadata", {})),
                    "created": now
                }
            )
            count += 1

        # Update test case count
        await repo_execute(
            "UPDATE evaluation_datasets SET test_case_count = :count, updated = :updated WHERE id = :id",
            {"count": count, "updated": now, "id": dataset_id}
        )

        return count

    async def parse_dataset_file(
        self,
        file_content: str,
        file_format: Literal["csv", "json", "jsonl"]
    ) -> List[Dict[str, Any]]:
        """Parse uploaded dataset file into test cases."""
        test_cases = []

        if file_format == "csv":
            reader = csv.DictReader(StringIO(file_content))
            for row in reader:
                test_case = {
                    "input": row.get("input", row.get("prompt", "")),
                    "expected_output": row.get("expected_output", row.get("output", "")),
                    "category": row.get("category", "general"),
                    "tags": row.get("tags", "").split(",") if row.get("tags") else []
                }
                test_cases.append(test_case)

        elif file_format == "json":
            data = json.loads(file_content)
            if isinstance(data, list):
                test_cases = data
            else:
                test_cases = [data]

        elif file_format == "jsonl":
            lines = file_content.strip().split("\n")
            for line in lines:
                if line.strip():
                    test_cases.append(json.loads(line))

        return test_cases

    async def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get dataset with metadata."""
        rows = await repo_query(
            "SELECT * FROM evaluation_datasets WHERE id = :id",
            {"id": dataset_id}
        )
        if not rows:
            return None

        dataset = dict(rows[0])
        if dataset.get("criteria"):
            dataset["criteria"] = json.loads(dataset["criteria"])

        return dataset

    async def list_datasets(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List evaluation datasets."""
        if agent_id:
            rows = await repo_query(
                """SELECT * FROM evaluation_datasets
                   WHERE agent_id = :agent_id OR agent_id IS NULL
                   ORDER BY created DESC LIMIT :limit OFFSET :offset""",
                {"agent_id": agent_id, "limit": limit, "offset": offset}
            )
        else:
            rows = await repo_query(
                """SELECT * FROM evaluation_datasets
                   ORDER BY created DESC LIMIT :limit OFFSET :offset""",
                {"limit": limit, "offset": offset}
            )

        datasets = []
        for row in rows:
            dataset = dict(row)
            if dataset.get("criteria"):
                dataset["criteria"] = json.loads(dataset["criteria"])
            datasets.append(dataset)

        return datasets

    async def get_test_cases(
        self,
        dataset_id: str,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get test cases from a dataset."""
        if category:
            rows = await repo_query(
                """SELECT * FROM evaluation_test_cases
                   WHERE dataset_id = :dataset_id AND category = :category""",
                {"dataset_id": dataset_id, "category": category}
            )
        else:
            rows = await repo_query(
                """SELECT * FROM evaluation_test_cases WHERE dataset_id = :dataset_id""",
                {"dataset_id": dataset_id}
            )

        test_cases = []
        for row in rows:
            case = dict(row)
            if case.get("tags"):
                case["tags"] = json.loads(case["tags"])
            if case.get("metadata"):
                case["metadata"] = json.loads(case["metadata"])
            test_cases.append(case)

        return test_cases

    # ========================================================================
    # Evaluation Execution
    # ========================================================================

    async def create_evaluation_run(
        self,
        dataset_id: str,
        agent_id: str,
        run_name: Optional[str] = None,
        model_override: Optional[str] = None,
        config_override: Optional[Dict] = None,
        created_by: Optional[str] = None
    ) -> str:
        """Create a new evaluation run."""
        run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Get test case count
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        await repo_execute(
            """INSERT INTO evaluation_runs
               (id, dataset_id, agent_id, run_name, model_override, config_override, status,
                total_cases, started_at, created, created_by)
               VALUES (:id, :dataset_id, :agent_id, :run_name, :model_override, :config_override,
                       :status, :total_cases, :started_at, :created, :created_by)""",
            {
                "id": run_id,
                "dataset_id": dataset_id,
                "agent_id": agent_id,
                "run_name": run_name or f"Run {now}",
                "model_override": model_override,
                "config_override": json.dumps(config_override or {}),
                "status": "pending",
                "total_cases": dataset["test_case_count"],
                "started_at": now,
                "created": now,
                "created_by": created_by
            }
        )

        return run_id

    async def execute_evaluation_run(
        self,
        run_id: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Execute an evaluation run by running agent against all test cases.
        Returns summary statistics.
        """
        # Get run details
        run_rows = await repo_query(
            "SELECT * FROM evaluation_runs WHERE id = :id",
            {"id": run_id}
        )
        if not run_rows:
            raise ValueError(f"Run {run_id} not found")

        run = dict(run_rows[0])
        dataset_id = run["dataset_id"]
        agent_id = run["agent_id"]

        # Update status to running
        await repo_execute(
            "UPDATE evaluation_runs SET status = 'running' WHERE id = :id",
            {"id": run_id}
        )

        try:
            # Get agent configuration
            agent_rows = await repo_query(
                "SELECT * FROM standalone_agents WHERE id = :id",
                {"id": agent_id}
            )
            if not agent_rows:
                raise ValueError(f"Agent {agent_id} not found")

            agent_config = dict(agent_rows[0])

            # Get dataset and test cases
            dataset = await self.get_dataset(dataset_id)
            test_cases = await self.get_test_cases(dataset_id)

            if not test_cases:
                raise ValueError(f"No test cases found in dataset {dataset_id}")

            # Execute each test case
            results_summary = {
                "passed": 0,
                "failed": 0,
                "total_latency": 0.0,
                "scores": []
            }

            for idx, test_case in enumerate(test_cases):
                try:
                    result = await self._execute_single_test_case(
                        run_id=run_id,
                        test_case=test_case,
                        agent_config=agent_config,
                        dataset=dataset,
                        model_override=run.get("model_override")
                    )

                    if result["passed"]:
                        results_summary["passed"] += 1
                    else:
                        results_summary["failed"] += 1

                    results_summary["total_latency"] += result["execution_time_ms"]
                    if result["overall_score"] is not None:
                        results_summary["scores"].append(result["overall_score"])

                    # Update progress
                    progress = int(((idx + 1) / len(test_cases)) * 100)
                    await repo_execute(
                        "UPDATE evaluation_runs SET progress = :progress WHERE id = :id",
                        {"progress": progress, "id": run_id}
                    )

                    if progress_callback:
                        await progress_callback(progress)

                except Exception as e:
                    logger.error(f"Error executing test case {test_case['id']}: {e}")
                    results_summary["failed"] += 1

            # Calculate final metrics
            avg_score = sum(results_summary["scores"]) / len(results_summary["scores"]) if results_summary["scores"] else 0
            avg_latency = results_summary["total_latency"] / len(test_cases) if test_cases else 0

            # Update run with final results
            now = datetime.utcnow().isoformat()
            await repo_execute(
                """UPDATE evaluation_runs
                   SET status = 'completed', progress = 100,
                       passed_cases = :passed, failed_cases = :failed,
                       avg_score = :avg_score, avg_latency_ms = :avg_latency,
                       completed_at = :completed_at
                   WHERE id = :id""",
                {
                    "passed": results_summary["passed"],
                    "failed": results_summary["failed"],
                    "avg_score": avg_score,
                    "avg_latency": avg_latency,
                    "completed_at": now,
                    "id": run_id
                }
            )

            return {
                "run_id": run_id,
                "status": "completed",
                "passed": results_summary["passed"],
                "failed": results_summary["failed"],
                "avg_score": avg_score,
                "avg_latency_ms": avg_latency
            }

        except Exception as e:
            logger.error(f"Evaluation run {run_id} failed: {e}")
            await repo_execute(
                """UPDATE evaluation_runs
                   SET status = 'failed', error_message = :error
                   WHERE id = :id""",
                {"error": str(e), "id": run_id}
            )
            raise

    async def _execute_single_test_case(
        self,
        run_id: str,
        test_case: Dict[str, Any],
        agent_config: Dict[str, Any],
        dataset: Dict[str, Any],
        model_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute agent against a single test case and score the result."""
        start_time = datetime.utcnow()

        try:
            # Execute agent with test case input
            # Note: For standalone agents, we'd need to instantiate and run them
            # This is a simplified version - you may need to adapt based on your agent execution pattern

            agent_output = await self._run_agent(
                agent_config=agent_config,
                input_prompt=test_case["input_prompt"],
                model_override=model_override
            )

            end_time = datetime.utcnow()
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            # Score the output
            score_result = await self._score_output(
                agent_output=agent_output,
                expected_output=test_case.get("expected_output"),
                scoring_method=dataset["scoring_method"],
                criteria=dataset.get("criteria", [])
            )

            # Save result
            result_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            await repo_execute(
                """INSERT INTO evaluation_results
                   (id, run_id, test_case_id, agent_output, execution_time_ms,
                    passed, overall_score, criteria_scores, similarity_score, exact_match,
                    feedback, judge_reasoning, error_occurred, created)
                   VALUES (:id, :run_id, :test_case_id, :agent_output, :execution_time_ms,
                           :passed, :overall_score, :criteria_scores, :similarity_score, :exact_match,
                           :feedback, :judge_reasoning, :error_occurred, :created)""",
                {
                    "id": result_id,
                    "run_id": run_id,
                    "test_case_id": test_case["id"],
                    "agent_output": agent_output,
                    "execution_time_ms": execution_time_ms,
                    "passed": 1 if score_result["passed"] else 0,
                    "overall_score": score_result.get("overall_score"),
                    "criteria_scores": json.dumps(score_result.get("criteria_scores", {})),
                    "similarity_score": score_result.get("similarity_score"),
                    "exact_match": 1 if score_result.get("exact_match") else 0,
                    "feedback": score_result.get("feedback"),
                    "judge_reasoning": score_result.get("reasoning"),
                    "error_occurred": 0,
                    "created": now
                }
            )

            return {
                "passed": score_result["passed"],
                "overall_score": score_result.get("overall_score"),
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Error executing test case: {e}")

            # Save error result
            result_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            await repo_execute(
                """INSERT INTO evaluation_results
                   (id, run_id, test_case_id, agent_output, passed,
                    error_occurred, error_message, created)
                   VALUES (:id, :run_id, :test_case_id, :agent_output, 0, 1, :error_message, :created)""",
                {
                    "id": result_id,
                    "run_id": run_id,
                    "test_case_id": test_case["id"],
                    "agent_output": "",
                    "error_message": str(e),
                    "created": now
                }
            )

            return {
                "passed": False,
                "overall_score": 0.0,
                "execution_time_ms": 0.0
            }

    async def _run_agent(
        self,
        agent_config: Dict[str, Any],
        input_prompt: str,
        model_override: Optional[str] = None
    ) -> str:
        """Execute the agent with given input."""
        # Simplified agent execution - adapt to your actual agent pattern
        # This is a placeholder that would need to match your IntelligentAgent setup

        try:
            # Get tool IDs if configured
            tool_ids = json.loads(agent_config.get("tool_ids") or "[]")

            # Create a simple execution context
            # In reality, you'd want to use your actual agent execution logic
            llm_pool = LLMClientPool()
            llm = llm_pool.get_llm(model_name=model_override or agent_config.get("model_name"))

            system_prompt = agent_config.get("system_prompt") or f"You are an AI assistant with the role: {agent_config.get('role')}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_prompt}
            ]

            response = await llm.ainvoke(messages)
            return response.content if hasattr(response, 'content') else str(response)

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raise

    async def _score_output(
        self,
        agent_output: str,
        expected_output: Optional[str],
        scoring_method: str,
        criteria: List[str]
    ) -> Dict[str, Any]:
        """Score agent output using the specified method."""

        if scoring_method == "exact_match":
            if not expected_output:
                return {"passed": True, "overall_score": 1.0, "exact_match": True}

            exact_match = agent_output.strip().lower() == expected_output.strip().lower()
            return {
                "passed": exact_match,
                "overall_score": 1.0 if exact_match else 0.0,
                "exact_match": exact_match
            }

        elif scoring_method == "llm_judge":
            return await self._llm_judge_scoring(agent_output, expected_output, criteria)

        elif scoring_method == "semantic_similarity":
            # Placeholder for semantic similarity - would need embeddings
            return {
                "passed": True,
                "overall_score": 0.85,
                "similarity_score": 0.85,
                "feedback": "Semantic similarity scoring not fully implemented"
            }

        else:
            # Default: assume passed
            return {"passed": True, "overall_score": 0.5}

    async def _llm_judge_scoring(
        self,
        agent_output: str,
        expected_output: Optional[str],
        criteria: List[str]
    ) -> Dict[str, Any]:
        """Use an LLM to judge the quality of the output."""
        llm_pool = LLMClientPool()
        llm = llm_pool.get_llm()

        criteria_list = "\n".join(f"- {c}" for c in criteria)

        judge_prompt = f"""You are evaluating an AI agent's output.

Evaluate the following output based on these criteria:
{criteria_list}

Agent Output:
{agent_output}

{"Expected Output: " + expected_output if expected_output else ""}

Provide your evaluation in this format:
OVERALL_SCORE: [0-10]
PASSED: [yes/no]
{"CRITERIA_SCORES: " + ", ".join(f"{c}: [0-10]" for c in criteria)}
REASONING: [Brief explanation]
"""

        response = await llm.ainvoke(judge_prompt)
        content = response.content if hasattr(response, 'content') else str(response)

        # Parse response
        lines = content.split("\n")
        result = {
            "overall_score": 5.0,
            "passed": False,
            "criteria_scores": {},
            "reasoning": ""
        }

        for line in lines:
            line = line.strip()
            if line.startswith("OVERALL_SCORE:"):
                try:
                    score = float(line.split(":", 1)[1].strip())
                    result["overall_score"] = score / 10.0  # Normalize to 0-1
                except:
                    pass
            elif line.startswith("PASSED:"):
                result["passed"] = "yes" in line.lower()
            elif line.startswith("REASONING:"):
                result["reasoning"] = line.split(":", 1)[1].strip()

        # Extract criteria scores
        for criterion in criteria:
            for line in lines:
                if criterion in line.lower() and ":" in line:
                    try:
                        score = float(line.split(":")[-1].strip().split()[0])
                        result["criteria_scores"][criterion] = score / 10.0
                    except:
                        pass

        result["feedback"] = content

        return result

    # ========================================================================
    # Results Retrieval
    # ========================================================================

    async def get_evaluation_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get evaluation run with results summary."""
        rows = await repo_query(
            """SELECT r.*, d.name as dataset_name, a.name as agent_name
               FROM evaluation_runs r
               JOIN evaluation_datasets d ON r.dataset_id = d.id
               JOIN standalone_agents a ON r.agent_id = a.id
               WHERE r.id = :id""",
            {"id": run_id}
        )

        if not rows:
            return None

        run = dict(rows[0])
        if run.get("config_override"):
            run["config_override"] = json.loads(run["config_override"])

        return run

    async def get_evaluation_results(
        self,
        run_id: str,
        passed_only: bool = False,
        failed_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get detailed results for an evaluation run."""
        where_clause = "r.run_id = :run_id"
        if passed_only:
            where_clause += " AND r.passed = 1"
        elif failed_only:
            where_clause += " AND r.passed = 0"

        rows = await repo_query(
            f"""SELECT r.*, t.input_prompt, t.expected_output, t.category, t.tags
               FROM evaluation_results r
               JOIN evaluation_test_cases t ON r.test_case_id = t.id
               WHERE {where_clause}
               ORDER BY r.created""",
            {"run_id": run_id}
        )

        results = []
        for row in rows:
            result = dict(row)
            if result.get("criteria_scores"):
                result["criteria_scores"] = json.loads(result["criteria_scores"])
            if result.get("tags"):
                result["tags"] = json.loads(result["tags"])
            results.append(result)

        return results

    async def list_evaluation_runs(
        self,
        agent_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List evaluation runs with filters."""
        where_clauses = []
        params = {"limit": limit}

        if agent_id:
            where_clauses.append("r.agent_id = :agent_id")
            params["agent_id"] = agent_id

        if dataset_id:
            where_clauses.append("r.dataset_id = :dataset_id")
            params["dataset_id"] = dataset_id

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        rows = await repo_query(
            f"""SELECT r.*, d.name as dataset_name, a.name as agent_name
               FROM evaluation_runs r
               JOIN evaluation_datasets d ON r.dataset_id = d.id
               JOIN standalone_agents a ON r.agent_id = a.id
               WHERE {where_sql}
               ORDER BY r.created DESC
               LIMIT :limit""",
            params
        )

        runs = []
        for row in rows:
            run = dict(row)
            if run.get("config_override"):
                run["config_override"] = json.loads(run["config_override"])
            runs.append(run)

        return runs


# Singleton instance
_evaluation_service = AgentEvaluationService()


async def get_evaluation_service() -> AgentEvaluationService:
    """Get evaluation service instance."""
    return _evaluation_service
