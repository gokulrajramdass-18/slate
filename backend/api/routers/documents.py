"""
Workspace Documents API

Unified endpoint for managing documents in a workspace:
- Notes (rich text documents)
- Presentations (PowerPoint files from S3)
- Other uploaded files (PDFs, etc.)
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Header, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
import uuid
import aiosqlite
import json
import io

from open_notebook.database.repository import repo_query, repo_execute
from api.services.s3_service import S3Service

router = APIRouter(prefix="/api/documents", tags=["documents"])


# Dependency to get database connection
async def get_db():
    """Get async database connection"""
    import os
    db_path = os.getenv("SQLITE_DB_PATH", "./data/database.db")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


# Pydantic models
class DocumentResponse(BaseModel):
    id: str
    notebook_id: str
    title: str
    description: Optional[str]
    document_type: str  # 'note', 'presentation', 'pdf', etc.
    file_url: Optional[str]  # S3 URL for files, None for notes
    file_size: Optional[int]
    mime_type: Optional[str]
    metadata: Optional[dict]
    content: Optional[str]  # For notes
    content_html: Optional[str]  # For notes
    created_at: str
    updated_at: str
    created_by: Optional[str]


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    has_more: bool


@router.get("/workspace/{notebook_id}", response_model=DocumentListResponse)
async def list_workspace_documents(
    notebook_id: str,
    document_type: Optional[str] = Query(None, description="Filter by type: note, presentation, pdf, etc."),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    List all documents in a workspace (notes + uploaded files).

    Returns both notes and S3-stored documents (presentations, PDFs, etc.)
    """
    documents = []

    # Fetch uploaded documents from workspace_documents table
    doc_query = """
        SELECT * FROM workspace_documents
        WHERE notebook_id = ?
    """
    params = [notebook_id]

    if document_type and document_type != 'note':
        doc_query += " AND document_type = ?"
        params.append(document_type)

    doc_query += " ORDER BY created_at DESC"

    async with db.execute(doc_query, params) as cursor:
        rows = await cursor.fetchall()
        for row in rows:
            doc_dict = dict(row)
            # Parse metadata JSON
            if doc_dict.get('metadata'):
                try:
                    doc_dict['metadata'] = json.loads(doc_dict['metadata'])
                except:
                    doc_dict['metadata'] = {}

            documents.append(DocumentResponse(
                id=doc_dict['id'],
                notebook_id=doc_dict['notebook_id'],
                title=doc_dict['title'],
                description=doc_dict.get('description'),
                document_type=doc_dict['document_type'],
                file_url=doc_dict.get('file_url'),
                file_size=doc_dict.get('file_size'),
                mime_type=doc_dict.get('mime_type'),
                metadata=doc_dict.get('metadata'),
                content=None,
                content_html=None,
                created_at=doc_dict['created_at'],
                updated_at=doc_dict['updated_at'],
                created_by=doc_dict.get('created_by')
            ))

    # Fetch notes if not filtering by non-note type
    if not document_type or document_type == 'note':
        notes_query = """
            SELECT n.* FROM notes n
            WHERE n.notebook_id = ?
            ORDER BY n.updated DESC
        """
        async with db.execute(notes_query, (notebook_id,)) as cursor:
            note_rows = await cursor.fetchall()
            for row in note_rows:
                note_dict = dict(row)
                documents.append(DocumentResponse(
                    id=note_dict['id'],
                    notebook_id=note_dict['notebook_id'],
                    title=note_dict['title'],
                    description=note_dict.get('summary'),
                    document_type='note',
                    file_url=None,
                    file_size=None,
                    mime_type='text/html',
                    metadata=None,
                    content=note_dict.get('content'),
                    content_html=note_dict.get('content_html'),
                    created_at=note_dict['created'],
                    updated_at=note_dict['updated'],
                    created_by=None
                ))

    # Sort by updated/created timestamp
    documents.sort(key=lambda x: x.updated_at or x.created_at, reverse=True)

    # Apply pagination
    total = len(documents)
    paginated_docs = documents[skip:skip + limit]

    return DocumentListResponse(
        documents=paginated_docs,
        total=total,
        has_more=(skip + limit) < total
    )


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Get a specific document by ID"""
    # Try workspace_documents first
    doc_query = "SELECT * FROM workspace_documents WHERE id = ?"
    async with db.execute(doc_query, (document_id,)) as cursor:
        row = await cursor.fetchone()
        if row:
            doc_dict = dict(row)
            if doc_dict.get('metadata'):
                try:
                    doc_dict['metadata'] = json.loads(doc_dict['metadata'])
                except:
                    doc_dict['metadata'] = {}

            return DocumentResponse(
                id=doc_dict['id'],
                notebook_id=doc_dict['notebook_id'],
                title=doc_dict['title'],
                description=doc_dict.get('description'),
                document_type=doc_dict['document_type'],
                file_url=doc_dict.get('file_url'),
                file_size=doc_dict.get('file_size'),
                mime_type=doc_dict.get('mime_type'),
                metadata=doc_dict.get('metadata'),
                content=None,
                content_html=None,
                created_at=doc_dict['created_at'],
                updated_at=doc_dict['updated_at'],
                created_by=doc_dict.get('created_by')
            )

    # Try notes table
    note_query = "SELECT * FROM notes WHERE id = ?"
    async with db.execute(note_query, (document_id,)) as cursor:
        row = await cursor.fetchone()
        if row:
            note_dict = dict(row)
            return DocumentResponse(
                id=note_dict['id'],
                notebook_id=note_dict['notebook_id'],
                title=note_dict['title'],
                description=note_dict.get('summary'),
                document_type='note',
                file_url=None,
                file_size=None,
                mime_type='text/html',
                metadata=None,
                content=note_dict.get('content'),
                content_html=note_dict.get('content_html'),
                created_at=note_dict['created'],
                updated_at=note_dict['updated'],
                created_by=None
            )

    raise HTTPException(status_code=404, detail="Document not found")


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Download a document file from S3"""
    # Get document record
    doc_query = "SELECT * FROM workspace_documents WHERE id = ?"
    async with db.execute(doc_query, (document_id,)) as cursor:
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = dict(row)

    # Download from S3
    s3_service = S3Service()
    if not s3_service.client:
        raise HTTPException(status_code=503, detail="S3 storage not available")

    try:
        file_bytes = s3_service.download_file(doc['s3_key'])

        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=doc.get('mime_type', 'application/octet-stream'),
            headers={
                "Content-Disposition": f'attachment; filename="{doc["title"]}.pptx"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download: {str(e)}")


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Delete a document"""
    # Try workspace_documents first
    doc_query = "SELECT * FROM workspace_documents WHERE id = ?"
    async with db.execute(doc_query, (document_id,)) as cursor:
        row = await cursor.fetchone()

    if row:
        doc = dict(row)

        # Delete from S3
        s3_service = S3Service()
        if s3_service.client:
            try:
                s3_service.delete_file(doc['s3_key'])
            except Exception as e:
                # Log but don't fail if S3 delete fails
                pass

        # Delete from database
        await db.execute("DELETE FROM workspace_documents WHERE id = ?", (document_id,))
        await db.commit()

        return {"success": True, "message": "Document deleted"}

    # Try notes table
    note_query = "SELECT * FROM notes WHERE id = ?"
    async with db.execute(note_query, (document_id,)) as cursor:
        row = await cursor.fetchone()

    if row:
        await db.execute("DELETE FROM notes WHERE id = ?", (document_id,))
        await db.commit()
        return {"success": True, "message": "Note deleted"}

    raise HTTPException(status_code=404, detail="Document not found")
