"""
Folders API Router

Endpoints for managing workspace folders and tags for organization.
"""

from fastapi import APIRouter, HTTPException, Header
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid

from open_notebook.database.repository import repo_query, repo_create, repo_update, repo_delete

router = APIRouter(prefix="/api/folders", tags=["folders"])


# ==================== Models ====================

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None


class FolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None


class FolderResponse(BaseModel):
    id: str
    name: str
    parent_id: Optional[str]
    notebook_count: int
    created: str
    updated: str


class TagCreate(BaseModel):
    name: str


class TagResponse(BaseModel):
    id: str
    name: str
    notebook_count: int


# ==================== Tag Endpoints (must come before /{folder_id}) ====================

@router.post("/tags", response_model=TagResponse)
async def create_tag(
    tag: TagCreate,
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Create a new tag for categorizing workspaces.

    - **name**: Tag name (e.g., "urgent", "data-analysis", "q1-2026")
    """
    # Check if tag already exists
    existing = await repo_query(
        "SELECT id FROM tags WHERE name = :name",
        {"name": tag.name}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Tag already exists")

    tag_id = str(uuid.uuid4())

    # Tags table only has id, name, and color columns
    await repo_query(
        "INSERT INTO tags (id, name, color) VALUES (:id, :name, :color)",
        {"id": tag_id, "name": tag.name, "color": None}
    )

    return TagResponse(
        id=tag_id,
        name=tag.name,
        notebook_count=0,
    )


@router.get("/tags", response_model=List[TagResponse])
async def list_tags(
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """
    List all tags with workspace counts.
    """
    tags = await repo_query(
        """
        SELECT
            t.id,
            t.name,
            COUNT(nt.notebook_id) as notebook_count
        FROM tags t
        LEFT JOIN notebook_tags nt ON nt.tag_id = t.id
        GROUP BY t.id, t.name
        ORDER BY t.name
        """
    )

    return [
        TagResponse(
            id=tag["id"],
            name=tag["name"],
            notebook_count=tag["notebook_count"] or 0,
        )
        for tag in tags
    ]


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Delete a tag. This will remove it from all workspaces that use it.
    """
    # Check if tag exists
    existing = await repo_query(
        "SELECT id FROM tags WHERE id = :tag_id",
        {"tag_id": tag_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Tag not found")

    # Delete tag (cascade will remove notebook_tags entries)
    await repo_delete("tags", tag_id)

    return {"message": "Tag deleted successfully"}


# ==================== Folder Endpoints ====================

@router.post("", response_model=FolderResponse)
async def create_folder(
    folder: FolderCreate,
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Create a new folder for organizing workspaces.

    - **name**: Folder name (e.g., "Client Projects", "Q1 2026")
    - **parent_id**: Optional parent folder ID for nested folders
    """
    folder_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    data = {
        "id": folder_id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "created": now,
        "updated": now,
    }

    await repo_create("folders", data)

    return FolderResponse(
        id=folder_id,
        name=folder.name,
        parent_id=folder.parent_id,
        notebook_count=0,
        created=now,
        updated=now,
    )


@router.get("", response_model=List[FolderResponse])
async def list_folders(
    notebook_id: Optional[str] = None,
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """
    List all folders with workspace counts.

    Args:
        notebook_id: Optional filter to get folders for a specific workspace
    """
    # Build query with optional notebook_id filter
    if notebook_id:
        query = """
            SELECT
                f.id,
                f.name,
                f.parent_id,
                f.created,
                f.updated,
                0 as notebook_count
            FROM folders f
            WHERE f.notebook_id = :notebook_id
            ORDER BY f.name
        """
        folders = await repo_query(query, {"notebook_id": notebook_id})
    else:
        folders = await repo_query(
            """
            SELECT
                f.id,
                f.name,
                f.parent_id,
                f.created,
                f.updated,
                COUNT(n.id) as notebook_count
            FROM folders f
            LEFT JOIN notebooks n ON n.folder_id = f.id
            GROUP BY f.id, f.name, f.parent_id, f.created, f.updated
            ORDER BY f.name
            """
        )

    return [
        FolderResponse(
            id=folder["id"],
            name=folder["name"],
            parent_id=folder["parent_id"],
            notebook_count=folder.get("notebook_count") or 0,
            created=folder["created"],
            updated=folder["updated"],
        )
        for folder in folders
    ]


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Get a specific folder by ID.
    """
    folders = await repo_query(
        """
        SELECT
            f.id,
            f.name,
            f.parent_id,
            f.created,
            f.updated,
            COUNT(n.id) as notebook_count
        FROM folders f
        LEFT JOIN notebooks n ON n.folder_id = f.id
        WHERE f.id = :folder_id
        GROUP BY f.id, f.name, f.parent_id, f.created, f.updated
        """,
        {"folder_id": folder_id}
    )

    if not folders:
        raise HTTPException(status_code=404, detail="Folder not found")

    folder = folders[0]
    return FolderResponse(
        id=folder["id"],
        name=folder["name"],
        parent_id=folder["parent_id"],
        notebook_count=folder["notebook_count"] or 0,
        created=folder["created"],
        updated=folder["updated"],
    )


@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    folder_update: FolderUpdate,
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Update a folder's name or parent.
    """
    # Check if folder exists
    existing = await repo_query(
        "SELECT id FROM folders WHERE id = :folder_id",
        {"folder_id": folder_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Build update data
    update_data = {}

    if folder_update.name is not None:
        update_data["name"] = folder_update.name

    if folder_update.parent_id is not None:
        update_data["parent_id"] = folder_update.parent_id

    if update_data:
        update_data["updated"] = datetime.utcnow().isoformat()
        await repo_update("folders", folder_id, update_data)

    # Return updated folder
    return await get_folder(folder_id, x_user_id)


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
):
    """
    Delete a folder. Workspaces in this folder will have their folder_id set to NULL.
    """
    # Check if folder exists
    existing = await repo_query(
        "SELECT id FROM folders WHERE id = :folder_id",
        {"folder_id": folder_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Remove folder_id from notebooks
    await repo_query(
        "UPDATE notebooks SET folder_id = NULL WHERE folder_id = :folder_id",
        {"folder_id": folder_id}
    )

    # Delete folder
    await repo_delete("folders", folder_id)

    return {"message": "Folder deleted successfully"}
