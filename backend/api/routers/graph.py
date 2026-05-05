"""
Graph API Router - Relational Graph Visualization Endpoints

Provides endpoints for:
- Fetching graph data (global and notebook-scoped)
- Expanding neighborhoods
- Computing similarities
- Managing saved layouts
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict

from api.models import (
    GraphResponse, LayoutSaveRequest, LayoutResponse, LayoutListResponse, SourceType, EdgeType
)
from api.services import graph_service

router = APIRouter()


@router.get("/sources", response_model=GraphResponse)
async def get_global_graph(
    source_types: Optional[List[SourceType]] = Query(None),
    notebook_ids: Optional[List[str]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    semantic_threshold: float = Query(0.7, ge=0.0, le=1.0),
    min_topic_overlap: int = Query(2, ge=1),
    show_isolated: bool = Query(True),
    edge_types: Optional[List[EdgeType]] = Query(None)
):
    """
    Get global graph data for all sources.

    Includes all relationship types based on filters.
    Returns nodes and edges for visualization.
    """
    filters = {
        "source_types": source_types,
        "notebook_ids": notebook_ids,
        "tags": tags,
        "date_from": date_from,
        "date_to": date_to,
        "semantic_threshold": semantic_threshold,
        "min_topic_overlap": min_topic_overlap,
        "show_isolated": show_isolated,
        "edge_types": edge_types or [
            EdgeType.SEMANTIC, EdgeType.NOTEBOOK, EdgeType.TOPIC,
            EdgeType.NOTE_LINK, EdgeType.HANA_SCHEMA, EdgeType.API_RELATION
        ]
    }

    try:
        graph_data = await graph_service.get_graph_data("global", None, filters)
        return GraphResponse(**graph_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build graph: {str(e)}")


@router.get("/sources/notebook/{notebook_id}", response_model=GraphResponse)
async def get_notebook_graph(
    notebook_id: str,
    source_types: Optional[List[SourceType]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    semantic_threshold: float = Query(0.7, ge=0.0, le=1.0),
    min_topic_overlap: int = Query(2, ge=1),
    show_isolated: bool = Query(True),
    edge_types: Optional[List[EdgeType]] = Query(None)
):
    """
    Get notebook-scoped graph data.

    Only includes sources from the specified notebook.
    """
    filters = {
        "source_types": source_types,
        "tags": tags,
        "date_from": date_from,
        "date_to": date_to,
        "semantic_threshold": semantic_threshold,
        "min_topic_overlap": min_topic_overlap,
        "show_isolated": show_isolated,
        "edge_types": edge_types or [
            EdgeType.SEMANTIC, EdgeType.NOTEBOOK, EdgeType.TOPIC,
            EdgeType.NOTE_LINK, EdgeType.HANA_SCHEMA, EdgeType.API_RELATION
        ]
    }

    try:
        graph_data = await graph_service.get_graph_data("notebook", notebook_id, filters)
        return GraphResponse(**graph_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build notebook graph: {str(e)}")


@router.get("/sources/{source_id}/neighbors", response_model=GraphResponse)
async def get_source_neighborhood(
    source_id: str,
    depth: int = Query(1, ge=1, le=3),
    source_types: Optional[List[SourceType]] = Query(None),
    semantic_threshold: float = Query(0.7, ge=0.0, le=1.0),
    edge_types: Optional[List[EdgeType]] = Query(None)
):
    """
    Get neighborhood of a source (connected sources) up to specified depth.

    Uses BFS to expand from source, returning all discovered sources and edges.
    """
    filters = {
        "source_types": source_types,
        "semantic_threshold": semantic_threshold,
        "edge_types": edge_types or [
            EdgeType.SEMANTIC, EdgeType.NOTEBOOK, EdgeType.TOPIC,
            EdgeType.NOTE_LINK, EdgeType.HANA_SCHEMA, EdgeType.API_RELATION
        ]
    }

    try:
        graph_data = await graph_service.get_neighborhood(source_id, depth, filters)
        return GraphResponse(**graph_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get neighborhood: {str(e)}")


@router.post("/sources/similarities")
async def recompute_similarities(
    source_ids: Optional[List[str]] = None,
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    top_k: int = Query(20, ge=1, le=100)
):
    """
    Recompute semantic similarities for sources.

    If source_ids is provided, only recomputes for those sources.
    Otherwise, recomputes for all sources with embeddings.

    This is a background job that may take time for large datasets.
    """
    try:
        if source_ids:
            # Compute for specific sources
            for source_id in source_ids:
                await graph_service.compute_source_similarities(source_id, threshold, top_k)
            count = len(source_ids)
        else:
            # Compute for all sources with embeddings
            from open_notebook.database.repository import repo_query
            sources = await repo_query(
                "SELECT DISTINCT source_id FROM source_embeddings"
            )
            count = 0
            for source in sources:
                await graph_service.compute_source_similarities(source["source_id"], threshold, top_k)
                count += 1

        return {
            "message": f"Computed similarities for {count} sources",
            "count": count,
            "threshold": threshold,
            "top_k": top_k
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute similarities: {str(e)}")


# ============================================================================
# Graph Settings & Bulk Recompute
# ============================================================================

# In-memory job tracking for bulk recompute progress
_recompute_jobs: Dict[str, Dict] = {}


@router.get("/settings")
async def get_graph_settings():
    """
    Get current graph computation settings.

    Returns default thresholds and the current similarity computation status.
    """
    # Count existing similarities
    from open_notebook.database.repository import repo_query

    try:
        sim_rows = await repo_query("SELECT COUNT(*) as cnt FROM source_similarities")
        sim_count = sim_rows[0]["cnt"] if sim_rows else 0
    except Exception:
        sim_count = 0

    try:
        src_rows = await repo_query(
            "SELECT COUNT(DISTINCT source_id) as cnt FROM source_embeddings"
        )
        sources_with_embeddings = src_rows[0]["cnt"] if src_rows else 0
    except Exception:
        sources_with_embeddings = 0

    try:
        total_sources_rows = await repo_query("SELECT COUNT(*) as cnt FROM sources")
        total_sources = total_sources_rows[0]["cnt"] if total_sources_rows else 0
    except Exception:
        total_sources = 0

    return {
        "similarity_count": sim_count,
        "sources_with_embeddings": sources_with_embeddings,
        "total_sources": total_sources,
        "defaults": {
            "semantic_threshold": 0.7,
            "top_k": 20,
            "min_topic_overlap": 2,
        },
    }


@router.post("/similarities/bulk")
async def bulk_recompute_similarities(
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    top_k: int = Query(20, ge=1, le=100)
):
    """
    Start a bulk recompute of all semantic similarities.

    Returns a job ID for tracking progress via the status endpoint.
    """
    import uuid
    import asyncio

    job_id = str(uuid.uuid4())
    _recompute_jobs[job_id] = {
        "id": job_id,
        "status": "running",
        "total": 0,
        "completed": 0,
        "threshold": threshold,
        "top_k": top_k,
        "error": None,
        "started_at": None,
        "finished_at": None,
    }

    async def run_bulk():
        import datetime
        _recompute_jobs[job_id]["started_at"] = datetime.datetime.utcnow().isoformat()
        try:
            from open_notebook.database.repository import repo_query
            sources = await repo_query(
                "SELECT DISTINCT source_id FROM source_embeddings"
            )
            _recompute_jobs[job_id]["total"] = len(sources)

            for i, source in enumerate(sources):
                await graph_service.compute_source_similarities(
                    source["source_id"], threshold, top_k
                )
                _recompute_jobs[job_id]["completed"] = i + 1

            _recompute_jobs[job_id]["status"] = "completed"
        except Exception as e:
            _recompute_jobs[job_id]["status"] = "failed"
            _recompute_jobs[job_id]["error"] = str(e)
        finally:
            import datetime
            _recompute_jobs[job_id]["finished_at"] = datetime.datetime.utcnow().isoformat()

    asyncio.create_task(run_bulk())

    return {"job_id": job_id, "status": "started"}


@router.get("/similarities/bulk/{job_id}")
async def get_bulk_recompute_status(job_id: str):
    """
    Get the status of a bulk recompute job.
    """
    job = _recompute_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/similarities/bulk")
async def list_bulk_recompute_jobs():
    """
    List all bulk recompute jobs (most recent first).
    """
    jobs = sorted(
        _recompute_jobs.values(),
        key=lambda j: j.get("started_at") or "",
        reverse=True,
    )
    return {"jobs": jobs}


@router.get("/layouts", response_model=LayoutListResponse)
async def list_layouts(
    scope: str = Query(..., pattern="^(global|notebook)$"),
    scope_id: Optional[str] = None
):
    """
    List saved layouts for a scope.

    For scope='notebook', scope_id must be provided.
    """
    if scope == "notebook" and not scope_id:
        raise HTTPException(status_code=400, detail="scope_id required for notebook scope")

    try:
        layouts = await graph_service.list_layouts(scope, scope_id)
        return LayoutListResponse(
            layouts=[LayoutResponse(**layout) for layout in layouts],
            total=len(layouts)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list layouts: {str(e)}")


@router.get("/layouts/{layout_id}", response_model=LayoutResponse)
async def get_layout(layout_id: str):
    """Get a saved layout by ID."""
    try:
        layout = await graph_service.load_layout(layout_id)
        if not layout:
            raise HTTPException(status_code=404, detail="Layout not found")

        return LayoutResponse(**layout)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load layout: {str(e)}")


@router.post("/layouts", response_model=LayoutResponse)
async def save_layout(request: LayoutSaveRequest):
    """
    Save a custom node layout.

    Stores node positions for later retrieval.
    """
    if request.scope == "notebook" and not request.scope_id:
        raise HTTPException(status_code=400, detail="scope_id required for notebook scope")

    try:
        layout_id = await graph_service.save_layout(
            name=request.name,
            scope=request.scope,
            scope_id=request.scope_id,
            layout_data=request.layout_data,
            description=request.description
        )

        # Return saved layout
        layout = await graph_service.load_layout(layout_id)
        return LayoutResponse(**layout)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save layout: {str(e)}")


@router.put("/layouts/{layout_id}", response_model=LayoutResponse)
async def update_layout_positions(layout_id: str, layout_data: Dict[str, Dict[str, float]]):
    """
    Update node positions for an existing layout.
    """
    try:
        # Check layout exists
        layout = await graph_service.load_layout(layout_id)
        if not layout:
            raise HTTPException(status_code=404, detail="Layout not found")

        # Update positions
        await graph_service.update_layout(layout_id, layout_data)

        # Return updated layout
        updated_layout = await graph_service.load_layout(layout_id)
        return LayoutResponse(**updated_layout)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update layout: {str(e)}")


@router.delete("/layouts/{layout_id}")
async def delete_layout(layout_id: str):
    """Delete a saved layout."""
    try:
        # Check layout exists
        layout = await graph_service.load_layout(layout_id)
        if not layout:
            raise HTTPException(status_code=404, detail="Layout not found")

        await graph_service.delete_layout(layout_id)
        return {"message": "Layout deleted successfully", "id": layout_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete layout: {str(e)}")


# ============================================================================
# Classification Endpoints (NEW)
# ============================================================================

@router.post("/classifications/classify")
async def classify_sources(
    source_ids: List[str],
    force: bool = False
):
    """
    Trigger classification for specific sources.

    Returns pending classifications for user approval.
    """
    try:
        from api.services.classification_service import ClassificationService

        service = ClassificationService()
        results = await service.classify_multiple_sources(source_ids)

        return {
            "message": f"Classified {len(source_ids)} sources",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.post("/classifications/classify-all")
async def classify_all_sources():
    """
    Background job to classify all sources.

    Returns job status.
    """
    try:
        from fastapi import BackgroundTasks
        from api.services.classification_service import ClassificationService

        service = ClassificationService()

        # Run synchronously for now (can be backgrounded with BackgroundTasks)
        results = await service.reclassify_all_sources()

        return {
            "message": "Classification complete",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch classification failed: {str(e)}")


@router.get("/classifications")
async def get_classifications(
    classification_type: Optional[str] = Query(None),
    level: Optional[int] = Query(None, ge=0, le=2)
):
    """
    List all classification nodes.

    Filter by type (category/topic/project/subtopic) or level (0/1/2).
    """
    try:
        from open_notebook.database.repository import repo_query

        query = "SELECT * FROM classification_types WHERE 1=1"
        params = {}

        if classification_type:
            query += " AND classification_type = :classification_type"
            params["classification_type"] = classification_type

        if level is not None:
            query += " AND level = :level"
            params["level"] = level

        query += " ORDER BY level, name"

        classifications = await repo_query(query, params)
        return {"classifications": classifications}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch classifications: {str(e)}")


@router.get("/classifications/{classification_id}/sources")
async def get_classification_sources(
    classification_id: str,
    status: Optional[str] = Query("approved", regex="^(pending|approved|rejected)$")
):
    """
    Get all sources with a specific classification.

    Filter by approval status (default: approved).
    """
    try:
        from open_notebook.domain.classification import Classification

        classification = await Classification.get(classification_id)
        if not classification:
            raise HTTPException(status_code=404, detail="Classification not found")

        sources = await classification.get_sources(status=status)

        return {
            "classification": {
                "id": classification.id,
                "name": classification.name,
                "type": classification.classification_type,
                "level": classification.level
            },
            "sources": sources
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sources: {str(e)}")


@router.get("/classifications/graph", response_model=GraphResponse)
async def get_classification_graph(
    notebook_id: Optional[str] = Query(None),
    classification_levels: Optional[List[int]] = Query(None),
    show_approved: bool = Query(True),
    show_pending: bool = Query(False),
    show_hierarchy: bool = Query(True)
):
    """
    Get mixed graph with sources and classification nodes.

    Includes classification nodes at specified levels with their connections.
    """
    try:
        scope = "notebook" if notebook_id else "global"
        filters = {
            "classification_levels": classification_levels or [0, 1, 2],
            "show_approved": show_approved,
            "show_pending": show_pending,
            "show_hierarchy": show_hierarchy
        }

        graph_data = await graph_service.get_classification_graph_data(
            scope=scope,
            scope_id=notebook_id,
            filters=filters
        )

        return GraphResponse(**graph_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build classification graph: {str(e)}")


@router.put("/classifications/approve/{classification_link_id}")
async def approve_classification(
    classification_link_id: str,
    action: str = Query(..., regex="^(approve|reject)$"),
    user_id: str = Query("default-user")
):
    """
    Approve or reject a pending classification suggestion.

    Updates status in source_classifications table.
    """
    try:
        from open_notebook.domain.classification import SourceClassification

        source_classification = await SourceClassification.get(classification_link_id)
        if not source_classification:
            raise HTTPException(status_code=404, detail="Classification link not found")

        if action == "approve":
            await source_classification.approve(user_id)
        else:
            await source_classification.reject(user_id)

        return {
            "message": f"Classification {action}d successfully",
            "id": classification_link_id,
            "status": source_classification.status
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to {action} classification: {str(e)}")


@router.put("/classifications/approve-batch")
async def approve_classifications_batch(
    classification_link_ids: List[str],
    action: str = Query(..., regex="^(approve|reject)$"),
    user_id: str = Query("default-user")
):
    """
    Bulk approve/reject multiple classifications.
    """
    try:
        from open_notebook.domain.classification import SourceClassification

        results = {"success": [], "failed": []}

        for link_id in classification_link_ids:
            try:
                source_classification = await SourceClassification.get(link_id)
                if not source_classification:
                    results["failed"].append({"id": link_id, "error": "Not found"})
                    continue

                if action == "approve":
                    await source_classification.approve(user_id)
                else:
                    await source_classification.reject(user_id)

                results["success"].append(link_id)
            except Exception as e:
                results["failed"].append({"id": link_id, "error": str(e)})

        return {
            "message": f"Batch {action} complete",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch {action} failed: {str(e)}")


@router.get("/classifications/pending")
async def get_pending_classifications(
    source_id: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0)
):
    """
    Get all pending classifications for review.

    Optionally filter by source_id and minimum confidence.
    """
    try:
        from open_notebook.domain.classification import SourceClassification

        if source_id:
            pending = await SourceClassification.get_pending_for_source(source_id)
            pending_dicts = [p.model_dump() for p in pending]
        else:
            pending_dicts = await SourceClassification.get_all_pending(min_confidence)

        # Group by confidence
        high_conf = [p for p in pending_dicts if p["confidence"] >= 0.8]
        medium_conf = [p for p in pending_dicts if 0.5 <= p["confidence"] < 0.8]
        low_conf = [p for p in pending_dicts if p["confidence"] < 0.5]

        return {
            "total": len(pending_dicts),
            "high_confidence": high_conf,
            "medium_confidence": medium_conf,
            "low_confidence": low_conf
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pending classifications: {str(e)}")

