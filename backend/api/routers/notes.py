"""
Notes API endpoints
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Header, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import uuid

from open_notebook.database.repository import repo_query, repo_execute
from api.services.note_export_service import NoteExportService

router = APIRouter(prefix="/api/notes", tags=["notes"])


# Helper function for filename sanitization
def sanitize_filename(title: str, extension: str) -> str:
    """
    Sanitize a filename to be safe for HTTP headers (ASCII-only).
    Removes emojis and special characters.
    """
    # Keep only alphanumeric, spaces, hyphens, and underscores
    safe_title = ''.join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)
    # Replace spaces with underscores and convert to lowercase
    safe_title = safe_title.replace(' ', '_').lower()
    # Limit length to 50 characters
    safe_title = safe_title[:50].rstrip('_')
    # Ensure we have a non-empty filename
    if not safe_title:
        safe_title = "note"
    return f"{safe_title}.{extension}"


# Pydantic models
class NoteCreate(BaseModel):
    title: str
    content: str
    content_html: Optional[str] = None
    notebook_id: Optional[str] = None  # Optional - note may not be linked to a notebook
    tags: Optional[List[str]] = []
    linked_note_ids: Optional[List[str]] = []


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    content_html: Optional[str] = None
    tags: Optional[List[str]] = None


class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    content_html: Optional[str]
    notebook_id: Optional[str]  # Optional - note may not be linked to a notebook
    folder_id: Optional[str] = None  # Folder for organization
    tags: List[str]
    linked_notes: List[dict]
    backlinks: List[dict]
    is_bookmarked: Optional[bool] = None
    created: str
    updated: str


class NoteLinkCreate(BaseModel):
    target_note_id: str


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(note_data: NoteCreate):
    """Create a new note"""
    note_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Create note (notes table doesn't have notebook_id column)
    insert_query = """
        INSERT INTO notes (id, title, content, content_html, created, updated)
        VALUES (:id, :title, :content, :content_html, :created, :updated)
    """
    await repo_execute(insert_query, {
        "id": note_id,
        "title": note_data.title,
        "content": note_data.content,
        "content_html": note_data.content_html,
        "created": now,
        "updated": now,
    })

    # Link to notebook via junction table
    if note_data.notebook_id:
        notebook_link_query = """
            INSERT INTO notebook_note (notebook_id, note_id, created)
            VALUES (:notebook_id, :note_id, :created)
        """
        await repo_execute(notebook_link_query, {
            "notebook_id": note_data.notebook_id,
            "note_id": note_id,
            "created": now,
        })

    # Add tags
    if note_data.tags:
        for tag in note_data.tags:
            tag_query = """
                INSERT INTO note_tags (note_id, tag)
                VALUES (:note_id, :tag)
            """
            await repo_execute(tag_query, {"note_id": note_id, "tag": tag})

    # Add note links
    if note_data.linked_note_ids:
        for target_id in note_data.linked_note_ids:
            link_query = """
                INSERT INTO note_links (id, source_note_id, target_note_id, created)
                VALUES (:id, :source_note_id, :target_note_id, :created)
            """
            await repo_execute(link_query, {
                "id": str(uuid.uuid4()),
                "source_note_id": note_id,
                "target_note_id": target_id,
                "created": now,
            })

    # Fetch and return the created note
    return await get_note(note_id)


@router.get("", response_model=List[NoteResponse])
async def list_notes(
    notebook_id: Optional[str] = None,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of records to return"),
    x_user_id: Optional[str] = Header(None),
):
    """List all notes, optionally filtered by notebook"""
    user_id = x_user_id or "default_user"

    if notebook_id:
        query = """
            SELECT n.*, nn.notebook_id FROM notes n
            JOIN notebook_note nn ON n.id = nn.note_id
            WHERE nn.notebook_id = :notebook_id
            ORDER BY n.updated DESC
            LIMIT :limit OFFSET :skip
        """
        notes = await repo_query(query, {"notebook_id": notebook_id, "limit": limit, "skip": skip})
    else:
        query = "SELECT * FROM notes ORDER BY updated DESC LIMIT :limit OFFSET :skip"
        notes = await repo_query(query, {"limit": limit, "skip": skip})

    result = []
    for note in notes:
        # Get tags
        tags_query = "SELECT tag FROM note_tags WHERE note_id = :note_id"
        tags_results = await repo_query(tags_query, {"note_id": note["id"]})
        tags = [t["tag"] for t in tags_results]

        # Get linked notes
        linked_query = """
            SELECT n.id, n.title FROM notes n
            JOIN note_links nl ON n.id = nl.target_note_id
            WHERE nl.source_note_id = :note_id
        """
        linked_notes = await repo_query(linked_query, {"note_id": note["id"]})

        # Get backlinks
        backlinks_query = """
            SELECT n.id, n.title FROM notes n
            JOIN note_links nl ON n.id = nl.source_note_id
            WHERE nl.target_note_id = :note_id
        """
        backlinks = await repo_query(backlinks_query, {"note_id": note["id"]})

        # Check bookmark status
        from open_notebook.domain.bookmark import Bookmark
        is_bookmarked = await Bookmark.is_bookmarked(
            user_id=user_id, entity_type="note", entity_id=note["id"]
        )

        result.append(NoteResponse(
            id=note["id"],
            title=note["title"],
            content=note["content"],
            content_html=note.get("content_html"),
            notebook_id=note.get("notebook_id"),  # Use .get() since it might not be present for unfiltered queries
            folder_id=note.get("folder_id"),  # Include folder for organization
            tags=tags,
            linked_notes=[dict(n) for n in linked_notes],
            backlinks=[dict(n) for n in backlinks],
            is_bookmarked=is_bookmarked,
            created=note["created"],
            updated=note["updated"],
        ))

    return result


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(note_id: str):
    """Get a specific note"""
    # Join with notebook_note to get notebook_id
    query = """
        SELECT n.*, nn.notebook_id
        FROM notes n
        LEFT JOIN notebook_note nn ON n.id = nn.note_id
        WHERE n.id = :id
    """
    results = await repo_query(query, {"id": note_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    note = results[0]

    # Get tags
    tags_query = "SELECT tag FROM note_tags WHERE note_id = :note_id"
    tags_results = await repo_query(tags_query, {"note_id": note_id})
    tags = [t["tag"] for t in tags_results]

    # Get linked notes
    linked_query = """
        SELECT n.id, n.title FROM notes n
        JOIN note_links nl ON n.id = nl.target_note_id
        WHERE nl.source_note_id = :note_id
    """
    linked_notes = await repo_query(linked_query, {"note_id": note_id})

    # Get backlinks
    backlinks_query = """
        SELECT n.id, n.title FROM notes n
        JOIN note_links nl ON n.id = nl.source_note_id
        WHERE nl.target_note_id = :note_id
    """
    backlinks = await repo_query(backlinks_query, {"note_id": note_id})

    return NoteResponse(
        id=note["id"],
        title=note["title"],
        content=note["content"],
        content_html=note.get("content_html"),
        notebook_id=note.get("notebook_id"),  # May be None if not linked to notebook
        folder_id=note.get("folder_id"),  # Include folder for organization
        tags=tags,
        linked_notes=[dict(n) for n in linked_notes],
        backlinks=[dict(n) for n in backlinks],
        created=note["created"],
        updated=note["updated"],
    )


@router.put("/{note_id}", response_model=NoteResponse)
async def update_note(note_id: str, update_data: NoteUpdate):
    """Update a note"""
    # Check if note exists
    check_query = "SELECT * FROM notes WHERE id = :id"
    existing = await repo_query(check_query, {"id": note_id})

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )

    # Build update query
    updates = []
    params = {"id": note_id, "updated": datetime.utcnow().isoformat()}

    if update_data.title is not None:
        updates.append("title = :title")
        params["title"] = update_data.title

    if update_data.content is not None:
        updates.append("content = :content")
        params["content"] = update_data.content

    if update_data.content_html is not None:
        updates.append("content_html = :content_html")
        params["content_html"] = update_data.content_html

    updates.append("updated = :updated")

    if len(updates) > 1:  # More than just 'updated'
        query = f"UPDATE notes SET {', '.join(updates)} WHERE id = :id"
        await repo_execute(query, params)

    # Update tags if provided
    if update_data.tags is not None:
        # Delete existing tags
        await repo_execute("DELETE FROM note_tags WHERE note_id = :note_id", {"note_id": note_id})
        # Add new tags
        for tag in update_data.tags:
            tag_query = "INSERT INTO note_tags (note_id, tag) VALUES (:note_id, :tag)"
            await repo_execute(tag_query, {"note_id": note_id, "tag": tag})

    return await get_note(note_id)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: str):
    """Delete a note"""
    query = "DELETE FROM notes WHERE id = :id"
    await repo_execute(query, {"id": note_id})


@router.post("/{note_id}/links", status_code=status.HTTP_201_CREATED)
async def add_note_link(note_id: str, link_data: NoteLinkCreate):
    """Add a link from this note to another note"""
    # Check both notes exist
    check_query = "SELECT id FROM notes WHERE id IN (:note_id, :target_id)"
    results = await repo_query(check_query, {
        "note_id": note_id,
        "target_id": link_data.target_note_id
    })

    if len(results) < 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both notes not found"
        )

    # Check if link already exists
    check_link_query = """
        SELECT * FROM note_links
        WHERE source_note_id = :source_id AND target_note_id = :target_id
    """
    existing = await repo_query(check_link_query, {
        "source_id": note_id,
        "target_id": link_data.target_note_id
    })

    if existing:
        return {"message": "Link already exists"}

    # Create link
    insert_query = """
        INSERT INTO note_links (id, source_note_id, target_note_id, created)
        VALUES (:id, :source_note_id, :target_note_id, :created)
    """
    await repo_execute(insert_query, {
        "id": str(uuid.uuid4()),
        "source_note_id": note_id,
        "target_note_id": link_data.target_note_id,
        "created": datetime.utcnow().isoformat(),
    })

    return {"message": "Link created"}


@router.delete("/{note_id}/links/{target_note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_note_link(note_id: str, target_note_id: str):
    """Remove a link between notes"""
    query = """
        DELETE FROM note_links
        WHERE source_note_id = :source_id AND target_note_id = :target_id
    """
    await repo_execute(query, {
        "source_id": note_id,
        "target_id": target_note_id
    })


@router.get("/{note_id}/export/markdown")
async def export_note_markdown(note_id: str):
    """Export a single note as Markdown"""
    # Get note with all details
    note_data = await get_note(note_id)

    # Generate markdown
    markdown_content = NoteExportService.export_to_markdown(
        note_title=note_data.title,
        note_content=note_data.content,
        tags=note_data.tags,
        linked_notes=note_data.linked_notes,
        created=note_data.created,
        updated=note_data.updated,
    )

    # Sanitize filename
    filename = sanitize_filename(note_data.title, "md")

    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.get("/{note_id}/export/pdf")
async def export_note_pdf(note_id: str):
    """Export a single note as PDF"""
    # Get note with all details
    note_data = await get_note(note_id)

    # Generate PDF
    pdf_bytes = NoteExportService.export_to_pdf(
        note_title=note_data.title,
        note_content=note_data.content,
        note_content_html=note_data.content_html,
        tags=note_data.tags,
        linked_notes=note_data.linked_notes,
        created=note_data.created,
        updated=note_data.updated,
    )

    # Sanitize filename
    filename = sanitize_filename(note_data.title, "pdf")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/export/markdown")
async def export_multiple_notes_markdown(note_ids: List[str]):
    """Export multiple notes as a combined Markdown file"""
    markdown_parts = []

    for note_id in note_ids:
        try:
            note_data = await get_note(note_id)

            markdown_content = NoteExportService.export_to_markdown(
                note_title=note_data.title,
                note_content=note_data.content,
                tags=note_data.tags,
                linked_notes=note_data.linked_notes,
                created=note_data.created,
                updated=note_data.updated,
            )

            markdown_parts.append(markdown_content)
            markdown_parts.append("\n\n---\n\n")  # Separator between notes

        except HTTPException:
            # Skip notes that don't exist
            continue

    combined_markdown = "".join(markdown_parts)

    return Response(
        content=combined_markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=notes_export.md"}
    )


@router.post("/export/pdf")
async def export_multiple_notes_pdf(note_ids: List[str]):
    """Export multiple notes as a combined PDF file"""
    notes_data = []

    for note_id in note_ids:
        try:
            note_data = await get_note(note_id)
            notes_data.append({
                'title': note_data.title,
                'content': note_data.content,
                'content_html': note_data.content_html,
                'tags': note_data.tags,
                'linked_notes': note_data.linked_notes,
                'created': note_data.created,
                'updated': note_data.updated,
            })
        except HTTPException:
            # Skip notes that don't exist
            continue

    if not notes_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid notes found"
        )

    # Generate combined PDF
    pdf_bytes = NoteExportService.export_multiple_notes_to_pdf(notes_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=notes_export.pdf"}
    )

