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
        workflow_id: Optional[str] = None,
        target_type: str = "agent",
        criteria: Optional[List[str]] = None,
        scoring_method: str = "llm_judge",
        created_by: Optional[str] = None
    ) -> str:
        """Create a new evaluation dataset."""
        dataset_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        await repo_execute(
            """INSERT INTO evaluation_datasets
               (id, name, description, agent_id, workflow_id, target_type, criteria, scoring_method, test_case_count, created, updated, created_by)
               VALUES (:id, :name, :description, :agent_id, :workflow_id, :target_type, :criteria, :scoring_method, 0, :created, :updated, :created_by)""",
            {
                "id": dataset_id,
                "name": name,
                "description": description,
                "agent_id": agent_id,
                "workflow_id": workflow_id,
                "target_type": target_type,
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
            # expected_tool_calls may arrive as a list (manual editor / JSON dataset)
            # or already serialised. Normalise to a JSON string for the DB; absence
            # of expectations stays NULL so result scoring can short-circuit.
            etc_raw = case.get("expected_tool_calls")
            expected_tool_calls_json: Optional[str] = None
            if etc_raw:
                expected_tool_calls_json = (
                    etc_raw if isinstance(etc_raw, str) else json.dumps(etc_raw)
                )

            await repo_execute(
                """INSERT INTO evaluation_test_cases
                   (id, dataset_id, input_prompt, expected_output, context, category, tags, metadata, expected_tool_calls, created)
                   VALUES (:id, :dataset_id, :input_prompt, :expected_output, :context, :category, :tags, :metadata, :expected_tool_calls, :created)""",
                {
                    "id": case_id,
                    "dataset_id": dataset_id,
                    "input_prompt": case["input"],
                    "expected_output": case.get("expected_output"),
                    "context": case.get("context"),
                    "category": case.get("category"),
                    "tags": json.dumps(case.get("tags", [])),
                    "metadata": json.dumps(case.get("metadata", {})),
                    "expected_tool_calls": expected_tool_calls_json,
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
                # expected_tool_calls in CSV is a JSON string in a single column;
                # left blank when no assertions are needed for the row.
                etc_raw = row.get("expected_tool_calls")
                expected_tool_calls = None
                if etc_raw:
                    try:
                        expected_tool_calls = json.loads(etc_raw)
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed expected_tool_calls cell: %r", etc_raw)
                test_case = {
                    "input": row.get("input", row.get("prompt", "")),
                    "expected_output": row.get("expected_output", row.get("output", "")),
                    "category": row.get("category", "general"),
                    "tags": row.get("tags", "").split(",") if row.get("tags") else [],
                    "expected_tool_calls": expected_tool_calls,
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
            if case.get("expected_tool_calls"):
                try:
                    case["expected_tool_calls"] = json.loads(case["expected_tool_calls"])
                except (TypeError, json.JSONDecodeError):
                    case["expected_tool_calls"] = None
            test_cases.append(case)

        return test_cases

    # ========================================================================
    # Evaluation Execution
    # ========================================================================

    async def create_evaluation_run(
        self,
        dataset_id: str,
        agent_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        target_type: str = "agent",
        run_name: Optional[str] = None,
        model_override: Optional[str] = None,
        config_override: Optional[Dict] = None,
        created_by: Optional[str] = None
    ) -> str:
        """Create a new evaluation run."""
        if target_type == "agent" and not agent_id:
            raise ValueError("agent_id is required when target_type='agent'")
        if target_type == "workflow" and not workflow_id:
            raise ValueError("workflow_id is required when target_type='workflow'")

        run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Get test case count
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        await repo_execute(
            """INSERT INTO evaluation_runs
               (id, dataset_id, agent_id, workflow_id, target_type, run_name, model_override, config_override, status,
                total_cases, started_at, created, created_by)
               VALUES (:id, :dataset_id, :agent_id, :workflow_id, :target_type, :run_name, :model_override, :config_override,
                       :status, :total_cases, :started_at, :created, :created_by)""",
            {
                "id": run_id,
                "dataset_id": dataset_id,
                "agent_id": agent_id,
                "workflow_id": workflow_id,
                "target_type": target_type,
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
            target_type = run.get("target_type", "agent")
            workflow_id = run.get("workflow_id")

            if target_type == "workflow":
                if not workflow_id:
                    raise ValueError("Workflow run is missing workflow_id")
                # Build a synthetic config object so _execute_single_test_case
                # can stay shape-compatible. The workflow target uses a tiny
                # subset of fields and ignores everything else.
                agent_config = {
                    "_target_type": "workflow",
                    "_workflow_id": workflow_id,
                    "model_name": None,
                    "tool_ids": "[]",
                }
            else:
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
            agent_result = await self._run_agent(
                agent_config=agent_config,
                input_prompt=test_case["input_prompt"],
                model_override=model_override
            )
            agent_output = agent_result["output"]
            actual_tool_calls = agent_result["tool_calls"]

            end_time = datetime.utcnow()
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            # Score the output
            score_result = await self._score_output(
                agent_output=agent_output,
                expected_output=test_case.get("expected_output"),
                scoring_method=dataset["scoring_method"],
                criteria=dataset.get("criteria", [])
            )

            # Score tool calls (None if no expectations were set)
            expected_tool_calls = test_case.get("expected_tool_calls")
            if isinstance(expected_tool_calls, str):
                # Defensive: get_test_cases decodes to list, but accept legacy raw rows.
                try:
                    expected_tool_calls = json.loads(expected_tool_calls)
                except json.JSONDecodeError:
                    expected_tool_calls = None
            tool_calls_passed = self._score_tool_calls(expected_tool_calls, actual_tool_calls)

            # Combine output pass and tool-call pass. When expectations exist and
            # are violated, the test case fails regardless of output quality.
            output_passed = bool(score_result["passed"])
            combined_passed = output_passed and (tool_calls_passed is not False)

            # Save result
            result_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            await repo_execute(
                """INSERT INTO evaluation_results
                   (id, run_id, test_case_id, agent_output, execution_time_ms,
                    passed, overall_score, criteria_scores, similarity_score, exact_match,
                    feedback, judge_reasoning, actual_tool_calls, tool_calls_passed,
                    error_occurred, created)
                   VALUES (:id, :run_id, :test_case_id, :agent_output, :execution_time_ms,
                           :passed, :overall_score, :criteria_scores, :similarity_score, :exact_match,
                           :feedback, :judge_reasoning, :actual_tool_calls, :tool_calls_passed,
                           :error_occurred, :created)""",
                {
                    "id": result_id,
                    "run_id": run_id,
                    "test_case_id": test_case["id"],
                    "agent_output": agent_output,
                    "execution_time_ms": execution_time_ms,
                    "passed": 1 if combined_passed else 0,
                    "overall_score": score_result.get("overall_score"),
                    "criteria_scores": json.dumps(score_result.get("criteria_scores", {})),
                    "similarity_score": score_result.get("similarity_score"),
                    "exact_match": 1 if score_result.get("exact_match") else 0,
                    "feedback": score_result.get("feedback"),
                    "judge_reasoning": score_result.get("reasoning"),
                    "actual_tool_calls": json.dumps(actual_tool_calls) if actual_tool_calls else None,
                    "tool_calls_passed": (1 if tool_calls_passed else 0) if tool_calls_passed is not None else None,
                    "error_occurred": 0,
                    "created": now
                }
            )

            return {
                "passed": combined_passed,
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
    ) -> Dict[str, Any]:
        """
        Execute the agent (or workflow) with given input.

        Returns a dict with:
          - output: str — agent's final textual response
          - tool_calls: list of {"tool_name", "args", "result_snippet"} captured
            from the LangChain message stream. Empty when the agent has no tools
            or no calls were made (and always empty for workflow targets in V1).
        """
        # Workflow target: hand the prompt to the workflow's first input field
        # and use the engine's `final_output` as the agent_output. Tool-call
        # assertions are not yet supported for workflows.
        if agent_config.get("_target_type") == "workflow":
            return await self._run_workflow(
                workflow_id=agent_config["_workflow_id"],
                input_prompt=input_prompt,
            )

        try:
            tool_ids = json.loads(agent_config.get("tool_ids") or "[]")
            system_prompt = (
                agent_config.get("system_prompt")
                or f"You are an AI assistant with the role: {agent_config.get('role')}"
            )
            model_name = model_override or agent_config.get("model_name")

            # When the agent has no tools, the IntelligentAgent setup is overkill
            # and would fail without a notebook context. Use the plain LLM path.
            if not tool_ids:
                llm_pool = LLMClientPool()
                llm = llm_pool.get_llm(model_name=model_name)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": input_prompt},
                ]
                response = await llm.ainvoke(messages)
                output = response.content if hasattr(response, "content") else str(response)
                return {"output": output, "tool_calls": []}

            # With tools, route through IntelligentAgent so we can observe tool
            # invocations alongside the final response.
            from api.services.tool_factory import ToolFactory  # local import to avoid cycles

            tools = []
            try:
                factory = ToolFactory()
                # Registry tools work without session/user context — sufficient for
                # evaluation purposes. Source-based tools are skipped because they
                # require a live notebook session that the eval runner doesn't have.
                tools = await factory._get_registry_tools()
                # Filter to the agent's configured tool_ids if any of them match.
                if tool_ids:
                    wanted = set(tool_ids)
                    filtered = [t for t in tools if getattr(t, "name", None) in wanted]
                    if filtered:
                        tools = filtered
            except Exception as e:
                logger.warning("Failed to build tools for eval run: %s. Falling back to no-tools path.", e)
                tools = []

            agent = IntelligentAgent(
                model_name=model_name,
                notebook_id=agent_config.get("notebook_id") or "",
                tools=tools,
                system_message=system_prompt,
                task_description=f"Evaluation: {input_prompt[:80]}",
            )
            result = await agent.execute(query=input_prompt)
            tool_calls = self._extract_tool_calls_from_result(result)
            return {
                "output": result.get("final_response") or "",
                "tool_calls": tool_calls,
            }

        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raise

    async def _run_workflow(
        self,
        workflow_id: str,
        input_prompt: str,
    ) -> Dict[str, Any]:
        """
        Execute a workflow against a single test case input.

        The test case `input` becomes the value of the workflow's first detected
        input field. We feed it as both `{first_input}: input_prompt` AND as
        `prompt`/`query`/`input` so workflows with different input field names
        still work without per-workflow configuration. The workflow's
        `final_output` (deterministic Output node, or last node's value) is
        returned as the agent_output for scoring.
        """
        from open_notebook.domain.workflow import Workflow
        from open_notebook.agents.workflow_engine import WorkflowEngine

        workflow = await Workflow.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Build a permissive input_data map so the workflow's input node finds
        # something matching its expected field name.
        input_data: Dict[str, Any] = {
            "input": input_prompt,
            "prompt": input_prompt,
            "query": input_prompt,
            "text": input_prompt,
        }

        engine = WorkflowEngine(workflow)
        execution = await engine.execute(input_data=input_data, stream=False)

        final_output = execution.final_output
        if final_output is None:
            output_text = ""
        elif isinstance(final_output, str):
            output_text = final_output
        elif isinstance(final_output, dict):
            # Heuristic: prefer common output keys before falling back to dump
            for k in ("output", "result", "response", "text", "answer"):
                if k in final_output and final_output[k] is not None:
                    output_text = str(final_output[k])
                    break
            else:
                output_text = json.dumps(final_output, default=str)
        else:
            output_text = str(final_output)

        return {"output": output_text, "tool_calls": []}

    def _extract_tool_calls_from_result(self, agent_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        IntelligentAgent.execute() returns `tool_outputs` keyed by name and
        `actions_taken` summarising each step. Re-shape into the flat list we
        store alongside the eval result.
        """
        out: List[Dict[str, Any]] = []
        tool_outputs = agent_result.get("tool_outputs") or {}
        for tool_name, payload in tool_outputs.items():
            # payload may be a dict with {"args": ..., "result": ...} or a raw value.
            if isinstance(payload, dict) and ("args" in payload or "result" in payload):
                args = payload.get("args") or {}
                result_val = payload.get("result")
            else:
                args = {}
                result_val = payload
            snippet = ""
            if result_val is not None:
                snippet = str(result_val)
                if len(snippet) > 240:
                    snippet = snippet[:240] + "…"
            out.append({"tool_name": tool_name, "args": args, "result_snippet": snippet})
        return out

    @staticmethod
    def _args_subset_match(expected: Any, actual: Any) -> bool:
        """Recursive subset match: every key/value in `expected` is present in `actual`."""
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return False
            return all(
                k in actual and AgentEvaluationService._args_subset_match(v, actual[k])
                for k, v in expected.items()
            )
        if isinstance(expected, list):
            if not isinstance(actual, list):
                return False
            # Each expected element must match SOME actual element (order-insensitive).
            return all(
                any(AgentEvaluationService._args_subset_match(e, a) for a in actual)
                for e in expected
            )
        return expected == actual

    def _score_tool_calls(
        self,
        expected: Optional[List[Dict[str, Any]]],
        actual: List[Dict[str, Any]],
    ) -> Optional[bool]:
        """
        Compare expected tool calls (assertions) against the calls the agent
        actually made.

        Returns:
          - True if every required expected call has a matching actual call.
          - False if any required expected call is missing or args don't match.
          - None when no expectations were defined (caller should ignore).
        """
        if not expected:
            return None

        actual_by_name: Dict[str, List[Dict[str, Any]]] = {}
        for ac in actual:
            actual_by_name.setdefault(ac.get("tool_name"), []).append(ac)

        for exp in expected:
            tool_name = exp.get("tool_name")
            required = exp.get("required", True)
            args_match = exp.get("args_match")

            candidates = actual_by_name.get(tool_name, [])
            if not candidates:
                if required:
                    return False
                continue

            if args_match:
                if not any(self._args_subset_match(args_match, c.get("args") or {}) for c in candidates):
                    if required:
                        return False
        return True

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
               LEFT JOIN standalone_agents a ON r.agent_id = a.id
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
            f"""SELECT r.*, t.input_prompt, t.expected_output, t.category, t.tags, t.expected_tool_calls
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
            if result.get("expected_tool_calls"):
                try:
                    result["expected_tool_calls"] = json.loads(result["expected_tool_calls"])
                except (TypeError, json.JSONDecodeError):
                    result["expected_tool_calls"] = None
            if result.get("actual_tool_calls"):
                try:
                    result["actual_tool_calls"] = json.loads(result["actual_tool_calls"])
                except (TypeError, json.JSONDecodeError):
                    result["actual_tool_calls"] = None
            # Map SQLite int → Python bool/None
            tcp = result.get("tool_calls_passed")
            if tcp is not None:
                result["tool_calls_passed"] = bool(tcp)
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
               LEFT JOIN standalone_agents a ON r.agent_id = a.id
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
