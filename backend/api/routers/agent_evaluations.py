"""
Agent Evaluation Router

Endpoints for:
- Creating and managing evaluation datasets
- Uploading test cases (CSV, JSON, JSONL)
- Running evaluations against agents
- Viewing evaluation results and analytics
"""

import json
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse

from api.models import (
    EvaluationDatasetCreate,
    EvaluationDatasetResponse,
    EvaluationTestCaseUpload,
    EvaluationRunCreate,
    EvaluationRunResponse,
    EvaluationRunListResponse,
    EvaluationResultResponse
)
from api.services.agent_evaluation_service import get_evaluation_service

router = APIRouter(prefix="/api/agent-evaluations", tags=["agent-evaluations"])
logger = logging.getLogger(__name__)


# ============================================================================
# Dataset Management
# ============================================================================

@router.post("/datasets", response_model=EvaluationDatasetResponse, status_code=201)
async def create_evaluation_dataset(dataset: EvaluationDatasetCreate):
    """Create a new evaluation dataset."""
    service = await get_evaluation_service()

    try:
        dataset_id = await service.create_dataset(
            name=dataset.name,
            description=dataset.description,
            agent_id=dataset.agent_id,
            workflow_id=dataset.workflow_id,
            target_type=dataset.target_type,
            criteria=dataset.criteria,
            scoring_method=dataset.scoring_method
        )

        result = await service.get_dataset(dataset_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create dataset")

        return EvaluationDatasetResponse(**result)

    except Exception as e:
        logger.error(f"Failed to create evaluation dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/upload", response_model=EvaluationDatasetResponse, status_code=201)
async def upload_evaluation_dataset(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    agent_id: Optional[str] = Form(None),
    workflow_id: Optional[str] = Form(None),
    target_type: str = Form("agent"),
    criteria: Optional[str] = Form(None),  # JSON array
    scoring_method: str = Form("llm_judge"),
    file: UploadFile = File(...)
):
    """
    Upload an evaluation dataset file (CSV, JSON, or JSONL).

    CSV format: columns [input, expected_output, category, tags]
    JSON format: array of test case objects
    JSONL format: one test case object per line
    """
    service = await get_evaluation_service()

    try:
        # Determine file format
        file_name = file.filename or "dataset"
        if file_name.endswith(".csv"):
            file_format = "csv"
        elif file_name.endswith(".jsonl"):
            file_format = "jsonl"
        elif file_name.endswith(".json"):
            file_format = "json"
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Use .csv, .json, or .jsonl"
            )

        # Read file content
        content = await file.read()
        file_content = content.decode("utf-8")

        # Parse test cases
        test_cases = await service.parse_dataset_file(file_content, file_format)

        if not test_cases:
            raise HTTPException(status_code=400, detail="No test cases found in file")

        # Parse criteria if provided
        criteria_list = json.loads(criteria) if criteria else ["accuracy", "relevance", "completeness"]

        # Create dataset
        dataset_id = await service.create_dataset(
            name=name,
            description=description,
            agent_id=agent_id,
            workflow_id=workflow_id,
            target_type=target_type,
            criteria=criteria_list,
            scoring_method=scoring_method
        )

        # Upload test cases
        await service.upload_test_cases(dataset_id, test_cases)

        # Update dataset metadata
        from open_notebook.database.repository import repo_execute
        await repo_execute(
            """UPDATE evaluation_datasets
               SET file_name = :file_name, file_format = :file_format
               WHERE id = :id""",
            {"file_name": file_name, "file_format": file_format, "id": dataset_id}
        )

        result = await service.get_dataset(dataset_id)
        return EvaluationDatasetResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets", response_model=List[EvaluationDatasetResponse])
async def list_evaluation_datasets(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """List all evaluation datasets."""
    service = await get_evaluation_service()

    try:
        datasets = await service.list_datasets(agent_id=agent_id, limit=limit, offset=offset)
        return [EvaluationDatasetResponse(**d) for d in datasets]

    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasets/{dataset_id}", response_model=EvaluationDatasetResponse)
async def get_evaluation_dataset(dataset_id: str):
    """Get a specific evaluation dataset."""
    service = await get_evaluation_service()

    dataset = await service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return EvaluationDatasetResponse(**dataset)


@router.get("/datasets/{dataset_id}/test-cases")
async def get_dataset_test_cases(
    dataset_id: str,
    category: Optional[str] = Query(None, description="Filter by category")
):
    """Get test cases from a dataset."""
    service = await get_evaluation_service()

    try:
        test_cases = await service.get_test_cases(dataset_id, category=category)
        return {"dataset_id": dataset_id, "test_cases": test_cases, "count": len(test_cases)}

    except Exception as e:
        logger.error(f"Failed to get test cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/datasets/{dataset_id}/test-cases", status_code=201)
async def add_test_cases(dataset_id: str, upload: EvaluationTestCaseUpload):
    """Add test cases to an existing dataset."""
    service = await get_evaluation_service()

    try:
        # Verify dataset exists
        dataset = await service.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        count = await service.upload_test_cases(dataset_id, upload.test_cases)

        return {"dataset_id": dataset_id, "added_count": count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add test cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/datasets/{dataset_id}", status_code=204)
async def delete_evaluation_dataset(dataset_id: str):
    """Delete an evaluation dataset and all its test cases."""
    from open_notebook.database.repository import repo_execute, repo_query

    # Check if dataset exists
    rows = await repo_query(
        "SELECT id FROM evaluation_datasets WHERE id = :id",
        {"id": dataset_id}
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Dataset not found")

    try:
        await repo_execute(
            "DELETE FROM evaluation_datasets WHERE id = :id",
            {"id": dataset_id}
        )

    except Exception as e:
        logger.error(f"Failed to delete dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Evaluation Runs
# ============================================================================

@router.post("/runs", response_model=EvaluationRunResponse, status_code=201)
async def create_evaluation_run(run: EvaluationRunCreate):
    """Create and start a new evaluation run."""
    service = await get_evaluation_service()

    try:
        # Create the run
        run_id = await service.create_evaluation_run(
            dataset_id=run.dataset_id,
            agent_id=run.agent_id,
            workflow_id=run.workflow_id,
            target_type=run.target_type,
            run_name=run.run_name,
            model_override=run.model_override,
            config_override=run.config_override
        )

        # Start execution in background
        # Note: In production, you'd want to use a task queue like Celery
        import asyncio
        asyncio.create_task(service.execute_evaluation_run(run_id))

        result = await service.get_evaluation_run(run_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create run")

        return EvaluationRunResponse(**result)

    except Exception as e:
        logger.error(f"Failed to create evaluation run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs", response_model=EvaluationRunListResponse)
async def list_evaluation_runs(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    dataset_id: Optional[str] = Query(None, description="Filter by dataset ID"),
    limit: int = Query(50, ge=1, le=200)
):
    """List evaluation runs with optional filters."""
    service = await get_evaluation_service()

    try:
        runs = await service.list_evaluation_runs(
            agent_id=agent_id,
            dataset_id=dataset_id,
            limit=limit
        )

        return EvaluationRunListResponse(
            runs=[EvaluationRunResponse(**r) for r in runs],
            total=len(runs)
        )

    except Exception as e:
        logger.error(f"Failed to list runs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation_run(run_id: str):
    """Get a specific evaluation run with summary."""
    service = await get_evaluation_service()

    run = await service.get_evaluation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return EvaluationRunResponse(**run)


@router.get("/runs/{run_id}/results", response_model=List[EvaluationResultResponse])
async def get_evaluation_results(
    run_id: str,
    passed_only: bool = Query(False, description="Show only passed cases"),
    failed_only: bool = Query(False, description="Show only failed cases")
):
    """Get detailed results for an evaluation run."""
    service = await get_evaluation_service()

    try:
        results = await service.get_evaluation_results(
            run_id=run_id,
            passed_only=passed_only,
            failed_only=failed_only
        )

        return [EvaluationResultResponse(**r) for r in results]

    except Exception as e:
        logger.error(f"Failed to get results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/runs/{run_id}", status_code=204)
async def delete_evaluation_run(run_id: str):
    """Delete an evaluation run and all its results."""
    from open_notebook.database.repository import repo_execute, repo_query

    # Check if run exists
    rows = await repo_query(
        "SELECT id FROM evaluation_runs WHERE id = :id",
        {"id": run_id}
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Run not found")

    try:
        await repo_execute(
            "DELETE FROM evaluation_runs WHERE id = :id",
            {"id": run_id}
        )

    except Exception as e:
        logger.error(f"Failed to delete run: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Analytics and Reporting
# ============================================================================

@router.get("/agents/{agent_id}/evaluation-summary")
async def get_agent_evaluation_summary(agent_id: str):
    """
    Get evaluation summary for an agent across all runs.

    Returns:
    - Total runs
    - Average pass rate
    - Average score
    - Performance trends
    """
    from open_notebook.database.repository import repo_query

    try:
        # Get all runs for this agent
        runs = await repo_query(
            """SELECT id, avg_score, passed_cases, failed_cases, total_cases, completed_at
               FROM evaluation_runs
               WHERE agent_id = :agent_id AND status = 'completed'
               ORDER BY completed_at DESC""",
            {"agent_id": agent_id}
        )

        if not runs:
            return {
                "agent_id": agent_id,
                "total_runs": 0,
                "avg_pass_rate": 0.0,
                "avg_score": 0.0,
                "runs": []
            }

        # Calculate aggregates
        total_runs = len(runs)
        pass_rates = []
        scores = []

        for run in runs:
            if run["total_cases"] > 0:
                pass_rate = run["passed_cases"] / run["total_cases"]
                pass_rates.append(pass_rate)

            if run["avg_score"] is not None:
                scores.append(run["avg_score"])

        avg_pass_rate = sum(pass_rates) / len(pass_rates) if pass_rates else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return {
            "agent_id": agent_id,
            "total_runs": total_runs,
            "avg_pass_rate": avg_pass_rate,
            "avg_score": avg_score,
            "recent_runs": [dict(r) for r in runs[:10]]  # Last 10 runs
        }

    except Exception as e:
        logger.error(f"Failed to get agent evaluation summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
