"""
Notebooks API Router

Endpoints for notebook CRUD operations and source management.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status, Header, Depends
from fastapi.responses import JSONResponse

from api.models import (
    NotebookCreate,
    NotebookUpdate,
    NotebookResponse,
    SourceResponse,
    ErrorResponse,
    SuccessResponse,
)
from open_notebook.database.repository import repo_query, repo_create, repo_update, repo_delete, repo_execute
from open_notebook.domain.user import User
from api.dependencies.auth import get_current_user, require_permission
from api.services.permission_service import PermissionService


router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================

async def get_notebook_by_id(notebook_id: str) -> Optional[dict]:
    """Get notebook by ID"""
    sql = "SELECT * FROM notebooks WHERE id = :id"
    results = await repo_query(sql, {"id": notebook_id})
    return results[0] if results else None


async def get_source_count(notebook_id: str) -> int:
    """Get count of sources in notebook (only existing sources)"""
    sql = """
        SELECT COUNT(*) as count
        FROM notebook_source ns
        INNER JOIN sources s ON ns.source_id = s.id
        WHERE ns.notebook_id = :notebook_id
    """
    results = await repo_query(sql, {"notebook_id": notebook_id})
    return results[0]["count"] if results else 0


async def get_note_count(notebook_id: str) -> int:
    """Get count of notes in notebook"""
    sql = """
        SELECT COUNT(*) as count
        FROM notebook_note
        WHERE notebook_id = :notebook_id
    """
    results = await repo_query(sql, {"notebook_id": notebook_id})
    return results[0]["count"] if results else 0


async def enrich_notebook(notebook: dict, user_id: Optional[str] = None) -> NotebookResponse:
    """Enrich notebook with counts and bookmark status"""
    source_count = await get_source_count(notebook["id"])
    note_count = await get_note_count(notebook["id"])

    # Check if workspace has a plan (AI-guided)
    plan_sql = "SELECT COUNT(*) as count FROM workspace_plans WHERE workspace_id = :notebook_id"
    plan_results = await repo_query(plan_sql, {"notebook_id": notebook["id"]})
    has_plan = plan_results[0]["count"] > 0 if plan_results else False

    # Add bookmark status if user_id provided
    is_bookmarked = None
    if user_id:
        from open_notebook.domain.bookmark import Bookmark
        is_bookmarked = await Bookmark.is_bookmarked(
            user_id=user_id, entity_type="notebook", entity_id=notebook["id"]
        )

    return NotebookResponse(
        **notebook,
        source_count=source_count,
        note_count=note_count,
        is_bookmarked=is_bookmarked,
        has_plan=has_plan,
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=List[NotebookResponse])
async def list_notebooks(
    folder_id: Optional[str] = Query(None, description="Filter by folder ID"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    order_by: str = Query("updated DESC", description="Order by field (e.g., 'name ASC', 'created DESC')"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of records to return"),
    current_user: User = Depends(get_current_user),
):
    """
    List notebooks accessible to current user

    Shows:
    - User's own notebooks
    - Notebooks shared with user
    - All notebooks if user has 'read all' permission

    - **folder_id**: Filter notebooks in specific folder
    - **tag**: Filter notebooks with specific tag
    - **order_by**: Sort order (default: most recently updated)
    """
    try:
        # Build query with LEFT JOINs to avoid N+1 queries
        sql = """
            SELECT n.*,
                   COUNT(DISTINCT ns.source_id) as source_count,
                   COUNT(DISTINCT nn.note_id) as note_count,
                   CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END as is_bookmarked
            FROM notebooks n
            LEFT JOIN notebook_source ns ON n.id = ns.notebook_id
            LEFT JOIN notebook_note nn ON n.id = nn.notebook_id
            LEFT JOIN user_bookmarks b ON b.entity_id = n.id AND b.entity_type = 'notebook' AND b.user_id = :current_user_id
        """
        params = {"current_user_id": current_user.id}
        where_clauses = []

        # Permission filtering
        if not current_user.is_superadmin:
            # Check if user has 'read all' permission
            has_read_all = await PermissionService.check_permission(
                user=current_user,
                resource_type="workspace",
                action="read",
            )

            if not has_read_all:
                # Only show own notebooks and shared notebooks
                where_clauses.append(
                    "(n.created_by = :user_id OR n.id IN ("
                    "SELECT resource_id FROM resource_shares "
                    "WHERE resource_type = 'workspace' "
                    "AND (shared_with_user = :user_id OR shared_with_role IN ("
                    "SELECT role_id FROM user_roles WHERE user_id = :user_id))"
                    "))"
                )
                params["user_id"] = current_user.id

        if folder_id:
            where_clauses.append("n.folder_id = :folder_id")
            params["folder_id"] = folder_id

        if tag:
            where_clauses.append("n.tags LIKE :tag")
            params["tag"] = f"%{tag}%"

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        sql += " GROUP BY n.id"
        sql += f" ORDER BY n.{order_by}"
        sql += " LIMIT :limit OFFSET :skip"
        params["limit"] = limit
        params["skip"] = skip

        # Execute query
        results = await repo_query(sql, params)

        # Build responses (no per-row queries needed)
        notebooks = []
        for notebook in results:
            if notebook.get("tags"):
                import json
                notebook["tags"] = json.loads(notebook["tags"])
            notebook["is_bookmarked"] = bool(notebook.get("is_bookmarked"))
            notebooks.append(NotebookResponse(**notebook))

        return notebooks

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list notebooks: {str(e)}",
        )


@router.post("", response_model=NotebookResponse, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    notebook: NotebookCreate,
    current_user: User = Depends(require_permission("workspace", "create")),
):
    """
    Create a new notebook

    Requires 'create' permission on 'workspace' resource type.

    - **name**: Notebook name (required)
    - **description**: Optional description
    - **folder_id**: Optional folder ID for organization
    - **tags**: Optional list of tags

    Requires at least one language model to be configured.
    """
    # Check that a language model is configured
    from api.services.settings import get_setting

    language_model_id = await get_setting("language_model_id", "")
    if not language_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No language model configured. Please select a model in Settings → Models before creating a notebook."
        )

    try:
        # Convert tags list to JSON string for storage
        data = notebook.model_dump()
        if data.get("tags"):
            import json
            data["tags"] = json.dumps(data["tags"])

        # Convert empty strings to None for foreign key fields
        if data.get("folder_id") == "":
            data["folder_id"] = None

        # Set owner
        data["created_by"] = current_user.id

        # Create notebook
        notebook_id = await repo_create("notebooks", data)

        # Fetch created notebook
        created = await get_notebook_by_id(notebook_id)
        if not created:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created notebook",
            )

        # Parse tags back to list
        if created.get("tags"):
            import json
            created["tags"] = json.loads(created["tags"])

        return await enrich_notebook(created, user_id=current_user.id)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR creating notebook: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notebook: {str(e)}",
        )


@router.post("/{notebook_id}/duplicate", response_model=NotebookResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_notebook(
    notebook_id: str,
    current_user: User = Depends(require_permission("workspace", "create")),
):
    """
    Duplicate an existing notebook with all its sources and tasks

    Creates a copy of the notebook with:
    - Same name (with " (Copy)" suffix)
    - Same description, tags, and folder
    - All linked sources
    - All workspace plan and tasks (reset to pending status)
    - Does NOT copy notes, chat sessions, or execution history

    Requires 'create' permission on 'workspace' resource type.
    """
    try:
        import uuid
        import json
        from datetime import datetime

        # Get the original notebook
        original = await get_notebook_by_id(notebook_id)
        if not original:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook {notebook_id} not found"
            )

        # Create new notebook with copied data
        new_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Parse tags if stored as JSON
        tags = original.get("tags")
        if tags and isinstance(tags, str):
            tags = json.loads(tags)

        new_data = {
            "id": new_id,
            "name": f"{original['name']} (Copy)",
            "description": original.get("description"),
            "folder_id": original.get("folder_id"),
            "tags": json.dumps(tags) if tags else None,
            "goal": original.get("goal"),
            "archived": False,
            "created_by": current_user.id,
            "created": now,
            "updated": now
        }

        # Insert new notebook
        await repo_execute("""
            INSERT INTO notebooks (id, name, description, folder_id, tags, goal, archived, created_by, created, updated)
            VALUES (:id, :name, :description, :folder_id, :tags, :goal, :archived, :created_by, :created, :updated)
        """, new_data)

        # Copy source associations
        sources = await repo_query("""
            SELECT source_id FROM notebook_source WHERE notebook_id = :notebook_id
        """, {"notebook_id": notebook_id})

        for source in sources:
            await repo_execute("""
                INSERT OR IGNORE INTO notebook_source (notebook_id, source_id, created)
                VALUES (:notebook_id, :source_id, :created)
            """, {
                "notebook_id": new_id,
                "source_id": source["source_id"],
                "created": now
            })

        # Copy workspace plan and tasks (if exists)
        plan = await repo_query("""
            SELECT id, goal, phases, collaboration_graph, status, progress
            FROM workspace_plans
            WHERE workspace_id = :workspace_id
        """, {"workspace_id": notebook_id}, fetch_one=True)

        if plan:
            # Create new plan for duplicated workspace
            new_plan_id = str(uuid.uuid4())
            await repo_execute("""
                INSERT INTO workspace_plans (id, workspace_id, goal, phases, collaboration_graph, status, progress, created, updated)
                VALUES (:id, :workspace_id, :goal, :phases, :collaboration_graph, :status, :progress, :created, :updated)
            """, {
                "id": new_plan_id,
                "workspace_id": new_id,
                "goal": plan["goal"],
                "phases": plan["phases"],
                "collaboration_graph": plan.get("collaboration_graph"),
                "status": "pending",  # Reset status to pending
                "progress": None,  # Clear progress
                "created": now,
                "updated": now
            })

            # Copy tasks from the original plan
            tasks = await repo_query("""
                SELECT phase_name, name, description, assigned_agent_id,
                       estimated_duration, dependencies, required_tools, required_sources
                FROM workspace_plan_tasks
                WHERE plan_id = :plan_id
                ORDER BY created
            """, {"plan_id": plan["id"]})

            # Create mapping of old task IDs to new task IDs for dependencies
            task_id_mapping = {}

            for task in tasks:
                old_task_id = str(uuid.uuid4())  # Generate ID for mapping
                new_task_id = str(uuid.uuid4())
                task_id_mapping[old_task_id] = new_task_id

                # Parse dependencies to update them later
                import json
                dependencies = json.loads(task.get("dependencies") or "[]")

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
                    "id": new_task_id,
                    "plan_id": new_plan_id,
                    "phase_name": task["phase_name"],
                    "name": task["name"],
                    "description": task["description"],
                    "assigned_agent_id": task.get("assigned_agent_id"),
                    "status": "pending",  # Reset status to pending
                    "estimated_duration": task.get("estimated_duration"),
                    "dependencies": task.get("dependencies", "[]"),
                    "required_tools": task.get("required_tools", "[]"),
                    "required_sources": task.get("required_sources", "[]"),
                    "created": now,
                    "updated": now
                })

        # Fetch the created notebook
        created = await get_notebook_by_id(new_id)
        if not created:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve duplicated notebook"
            )

        # Parse tags back to list
        if created.get("tags"):
            created["tags"] = json.loads(created["tags"])

        return await enrich_notebook(created, user_id=current_user.id)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR duplicating notebook: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to duplicate notebook: {str(e)}"
        )



@router.get("/with-plans", response_model=List[NotebookResponse])
async def list_workspaces_with_plans(
    order_by: str = Query("updated DESC", description="Order by field"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    """
    List workspaces that have execution plans.
    
    Only returns workspaces with workspace_plans entries - suitable for template creation.
    """
    try:
        sql = """
            SELECT DISTINCT n.*,
                   COUNT(DISTINCT ns.source_id) as source_count,
                   COUNT(DISTINCT nn.note_id) as note_count,
                   CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END as is_bookmarked
            FROM notebooks n
            INNER JOIN workspace_plans wp ON n.id = wp.workspace_id
            LEFT JOIN notebook_source ns ON n.id = ns.notebook_id
            LEFT JOIN notebook_note nn ON n.id = nn.notebook_id
            LEFT JOIN user_bookmarks b ON b.entity_id = n.id AND b.entity_type = 'notebook' AND b.user_id = :current_user_id
        """
        params = {"current_user_id": current_user.id}
        where_clauses = []

        # Permission filtering
        if not current_user.is_superadmin:
            has_read_all = await PermissionService.check_permission(
                user=current_user,
                resource_type="workspace",
                action="read",
            )

            if not has_read_all:
                where_clauses.append(
                    "(n.created_by = :user_id OR n.id IN ("
                    "SELECT resource_id FROM resource_shares "
                    "WHERE resource_type = 'workspace' "
                    "AND (shared_with_user = :user_id OR shared_with_role IN ("
                    "SELECT role_id FROM user_roles WHERE user_id = :user_id))"
                    "))"
                )
                params["user_id"] = current_user.id

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        sql += f" GROUP BY n.id ORDER BY n.{order_by} LIMIT :limit OFFSET :skip"
        params["limit"] = limit
        params["skip"] = skip

        results = await repo_query(sql, params)

        # Convert to NotebookResponse
        notebooks = []
        for row in results:
            row_dict = dict(row)
            row_dict["is_bookmarked"] = bool(row_dict.get("is_bookmarked", 0))
            notebooks.append(NotebookResponse(**row_dict))

        return notebooks

    except Exception as e:
        import traceback
        logger.error(f"Failed to list workspaces with plans: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list workspaces with plans: {str(e)}",
        )


@router.get("/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(
    notebook_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific notebook by ID

    Requires 'read' permission on the notebook.

    - **notebook_id**: Notebook UUID
    """
    try:
        notebook = await get_notebook_by_id(notebook_id)
        if not notebook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook {notebook_id} not found",
            )

        # Check permission
        await PermissionService.require_permission(
            user=current_user,
            resource_type="workspace",
            action="read",
            resource_id=notebook_id,
            resource_owner=notebook.get("created_by"),
        )

        # Parse tags
        if notebook.get("tags"):
            import json
            notebook["tags"] = json.loads(notebook["tags"])

        return await enrich_notebook(notebook, user_id=current_user.id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notebook: {str(e)}",
        )


@router.put("/{notebook_id}", response_model=NotebookResponse)
async def update_notebook(
    notebook_id: str,
    notebook: NotebookUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing notebook

    Requires 'update' permission on the notebook.

    - **notebook_id**: Notebook UUID
    - Only provided fields will be updated
    """
    try:
        # Check if notebook exists
        existing = await get_notebook_by_id(notebook_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook {notebook_id} not found",
            )

        # Check permission
        await PermissionService.require_permission(
            user=current_user,
            resource_type="workspace",
            action="update",
            resource_id=notebook_id,
            resource_owner=existing.get("created_by"),
        )

        # Prepare update data (only include fields that were provided)
        data = notebook.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )

        # Convert tags to JSON string
        if "tags" in data:
            import json
            data["tags"] = json.dumps(data["tags"])

        # Convert empty strings to None for foreign key fields
        if data.get("folder_id") == "":
            data["folder_id"] = None

        # Update notebook
        await repo_update("notebooks", notebook_id, data)

        # Fetch updated notebook
        updated = await get_notebook_by_id(notebook_id)
        if updated and updated.get("tags"):
            import json
            updated["tags"] = json.loads(updated["tags"])

        return await enrich_notebook(updated, user_id=current_user.id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notebook: {str(e)}",
        )


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(
    notebook_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a notebook

    Requires 'delete' permission on the notebook.

    - **notebook_id**: Notebook UUID
    - Cascade deletes associated sources and notes via database constraints
    """
    try:
        logger.warning(f"DELETE WORKSPACE CALLED: workspace_id={notebook_id}, user={current_user.id if current_user else 'None'}")

        # Check if notebook exists
        existing = await get_notebook_by_id(notebook_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook {notebook_id} not found",
            )

        # Check permission
        await PermissionService.require_permission(
            user=current_user,
            resource_type="workspace",
            action="delete",
            resource_id=notebook_id,
            resource_owner=existing.get("created_by"),
        )

        # Check for running template executions
        running_executions_sql = """
            SELECT COUNT(*) as count
            FROM template_executions
            WHERE target_workspace_id = :workspace_id
            AND status IN ('pending', 'running')
        """
        running_result = await repo_query(running_executions_sql, {"workspace_id": notebook_id})
        running_count = running_result[0]["count"] if running_result else 0

        if running_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete workspace: {running_count} template execution(s) currently running. Please wait for them to complete or cancel them first.",
            )

        # Comprehensive cleanup before deletion
        logger.info(f"Starting comprehensive cleanup for workspace {notebook_id}")

        # 1. Find templates that use this workspace as source
        templates = await repo_query(
            "SELECT id FROM workspace_templates WHERE source_workspace_id = :workspace_id",
            {"workspace_id": notebook_id}
        )
        template_ids = [t["id"] for t in templates] if templates else []

        if template_ids:
            logger.info(f"Found {len(template_ids)} templates to delete")

        # 2. For each template, delete its executions and result notes
        for template_id in template_ids:
            # Get all executions for this template
            executions = await repo_query(
                "SELECT id, result_note_id, folder_id FROM template_executions WHERE template_id = :template_id",
                {"template_id": template_id}
            )

            if executions:
                logger.info(f"Deleting {len(executions)} executions for template {template_id}")

                # Delete execution result notes
                for exec in executions:
                    if exec.get("result_note_id"):
                        try:
                            await repo_execute(
                                "DELETE FROM notes WHERE id = :note_id",
                                {"note_id": exec["result_note_id"]}
                            )
                        except Exception as e:
                            logger.warning(f"Failed to delete result note {exec['result_note_id']}: {e}")

                # Delete all executions for this template
                await repo_execute(
                    "DELETE FROM template_executions WHERE template_id = :template_id",
                    {"template_id": template_id}
                )

            # Delete the template itself
            await repo_execute(
                "DELETE FROM workspace_templates WHERE id = :template_id",
                {"template_id": template_id}
            )

        logger.info(f"Deleted {len(template_ids)} templates and their executions")

        # 3. Delete workspace plan tasks
        plan_result = await repo_query(
            "SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": notebook_id}
        )

        if plan_result:
            plan_id = plan_result[0]["id"]
            await repo_execute(
                "DELETE FROM workspace_plan_tasks WHERE plan_id = :plan_id",
                {"plan_id": plan_id}
            )
            await repo_execute(
                "DELETE FROM workspace_plans WHERE id = :plan_id",
                {"plan_id": plan_id}
            )
            logger.info(f"Deleted workspace plan and tasks")

        # 4. Delete execution folders (if any remain)
        execution_folders = await repo_query(
            """SELECT id FROM folders
               WHERE name LIKE 'Execution %'
               AND notebook_id = :notebook_id""",
            {"notebook_id": notebook_id}
        )

        if execution_folders:
            for folder in execution_folders:
                # Delete notes in folder
                await repo_execute(
                    "DELETE FROM notes WHERE folder_id = :folder_id",
                    {"folder_id": folder["id"]}
                )
                # Delete folder
                await repo_execute(
                    "DELETE FROM folders WHERE id = :folder_id",
                    {"folder_id": folder["id"]}
                )
            logger.info(f"Deleted {len(execution_folders)} execution folders")

        # 5. Delete notebook (cascade will handle remaining notes, sources, etc.)
        await repo_delete("notebooks", notebook_id)

        logger.info(f"Workspace {notebook_id} and all associated data deleted successfully")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete notebook {notebook_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete notebook: {str(e)}",
        )


@router.get("/{notebook_id}/sources", response_model=List[SourceResponse])
async def list_notebook_sources(notebook_id: str):
    """
    List all sources in a notebook

    - **notebook_id**: Notebook UUID
    """
    try:
        # Check if notebook exists
        notebook = await get_notebook_by_id(notebook_id)
        if not notebook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook {notebook_id} not found",
            )

        # Get sources
        sql = """
            SELECT s.*
            FROM sources s
            INNER JOIN notebook_source ns ON s.id = ns.source_id
            WHERE ns.notebook_id = :notebook_id
            ORDER BY s.updated DESC
        """
        results = await repo_query(sql, {"notebook_id": notebook_id})

        # Parse JSON fields
        import json
        for source in results:
            if source.get("tags"):
                source["tags"] = json.loads(source["tags"])
            if source.get("connection_config"):
                source["connection_config"] = json.loads(source["connection_config"])
            if source.get("sync_config"):
                source["sync_config"] = json.loads(source["sync_config"])

        return [SourceResponse(**source) for source in results]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sources: {str(e)}",
        )


@router.post("/{notebook_id}/sources/{source_id}", response_model=SuccessResponse)
async def add_source_to_notebook(notebook_id: str, source_id: str):
    """
    Add an existing source to a notebook

    - **notebook_id**: Notebook UUID
    - **source_id**: Source UUID
    """
    try:
        # Check if notebook exists
        notebook = await get_notebook_by_id(notebook_id)
        if not notebook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook {notebook_id} not found",
            )

        # Check if source exists
        source_sql = "SELECT * FROM sources WHERE id = :id"
        source_results = await repo_query(source_sql, {"id": source_id})
        if not source_results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Check if already linked
        check_sql = """
            SELECT * FROM notebook_source
            WHERE notebook_id = :notebook_id AND source_id = :source_id
        """
        existing = await repo_query(
            check_sql, {"notebook_id": notebook_id, "source_id": source_id}
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Source already added to notebook",
            )

        # Add link (using direct SQL since notebook_source is a junction table without id/updated)
        from datetime import datetime
        link_sql = """
            INSERT INTO notebook_source (notebook_id, source_id, created)
            VALUES (:notebook_id, :source_id, :created)
        """
        from open_notebook.database.repository import repo_execute
        await repo_execute(
            link_sql,
            {
                "notebook_id": notebook_id,
                "source_id": source_id,
                "created": datetime.utcnow().isoformat()
            }
        )

        return SuccessResponse(
            success=True,
            message=f"Source {source_id} added to notebook {notebook_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR adding source to notebook: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add source to notebook: {str(e)}",
        )


@router.delete("/{notebook_id}/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_source_from_notebook(notebook_id: str, source_id: str):
    """
    Remove a source from a notebook

    - **notebook_id**: Notebook UUID
    - **source_id**: Source UUID
    - Does not delete the source, only removes the association
    """
    try:
        # Check if link exists
        check_sql = """
            SELECT id FROM notebook_source
            WHERE notebook_id = :notebook_id AND source_id = :source_id
        """
        existing = await repo_query(
            check_sql, {"notebook_id": notebook_id, "source_id": source_id}
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source not found in notebook",
            )

        # Delete link
        link_id = existing[0]["id"]
        await repo_delete("notebook_source", link_id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove source from notebook: {str(e)}",
        )


@router.get("/{notebook_id}/plan")
async def get_workspace_plan(
    notebook_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get execution plan for workspace if it exists.

    - **notebook_id**: Workspace UUID
    - Returns plan details or 404 if no plan exists
    """
    try:
        # Check if notebook exists
        notebook = await get_notebook_by_id(notebook_id)
        if not notebook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace {notebook_id} not found",
            )

        # Get plan
        plan_sql = "SELECT id, workspace_id, goal, phases, collaboration_graph, status, created_at, updated_at FROM workspace_plans WHERE workspace_id = :workspace_id"
        plan_result = await repo_query(plan_sql, {"workspace_id": notebook_id})

        if not plan_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No execution plan found for workspace",
            )

        return dict(plan_result[0])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get plan: {str(e)}",
        )


@router.post("/{notebook_id}/generate-plan")
async def generate_workspace_plan(
    notebook_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Generate execution plan for existing workspace using LLM analysis.

    - **notebook_id**: Workspace UUID
    - Analyzes workspace sources, notes, and goal to create structured plan
    - Returns generated plan with phases, tasks, and agent assignments
    """
    from api.services.workspace_plan_generator import WorkspacePlanGeneratorService

    try:
        # Check if notebook exists
        notebook = await get_notebook_by_id(notebook_id)
        if not notebook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace {notebook_id} not found",
            )

        # Check if plan already exists
        existing_plan_sql = "SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id"
        existing_plan = await repo_query(existing_plan_sql, {"workspace_id": notebook_id})

        if existing_plan:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workspace already has an execution plan. Use update endpoint to modify it.",
            )

        # Generate and save plan
        result = await WorkspacePlanGeneratorService.generate_and_save_plan(
            workspace_id=notebook_id,
            user_id=current_user.id
        )

        return {
            "success": True,
            "message": "Execution plan generated successfully",
            "plan_id": result["plan_id"],
            "workspace_id": result["workspace_id"],
            "workspace_name": result["workspace_name"],
            "phases_count": result["phases_count"],
            "plan": result["plan"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate plan: {str(e)}",
        )


@router.get("/{notebook_id}/chat-sessions")
async def get_notebook_chat_sessions(notebook_id: str):
    """
    Get all chat sessions for a notebook

    - **notebook_id**: Notebook UUID
    - Returns list of chat sessions associated with this notebook
    """
    try:
        # Check if notebook exists
        notebook = await get_notebook_by_id(notebook_id)
        if not notebook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook {notebook_id} not found",
            )

        # Get chat sessions
        sql = """
            SELECT id, title, notebook_id, created, updated
            FROM chat_sessions
            WHERE notebook_id = :notebook_id
            ORDER BY updated DESC
        """
        sessions = await repo_query(sql, {"notebook_id": notebook_id})

        return sessions

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat sessions: {str(e)}",
        )

