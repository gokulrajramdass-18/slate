"""
Workspace Documents Upload API

Handles uploading documents (PDF, DOCX, XLS, PPT) to workspaces
"""
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
import uuid
import os
from datetime import datetime
import aiosqlite
import json

from api.services.s3_service import get_s3_service

router = APIRouter(prefix="/api/workspace-documents", tags=["workspace-documents"])


# Dependency to get database connection
async def get_db():
    """Get async database connection"""
    db_path = os.getenv("SQLITE_DB_PATH", "./data/database.db")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


# Allowed file types
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt'}
MIME_TYPES = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.ppt': 'application/vnd.ms-powerpoint',
}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    notebook_id: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Upload a document to a workspace (PDF, DOCX, XLS, PPT only)

    Args:
        file: The file to upload
        notebook_id: Workspace ID
        title: Optional custom title (defaults to filename)
        description: Optional description

    Returns:
        Document metadata including URL and ID
    """
    try:
        # Validate file extension
        if not file.filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Only PDF, DOCX, XLS, and PPT files are allowed. Got: {file_extension}"
            )

        # Verify workspace exists
        async with db.execute("SELECT id FROM notebooks WHERE id = ?", (notebook_id,)) as cursor:
            workspace = await cursor.fetchone()
            if not workspace:
                raise HTTPException(status_code=404, detail="Workspace not found")

        # Get S3 service
        s3_service = get_s3_service()
        if not s3_service.client:
            raise HTTPException(
                status_code=503,
                detail="S3 storage is not available. Please start MinIO (Docker Desktop) or configure AWS S3."
            )

        # Generate unique ID and S3 key
        document_id = str(uuid.uuid4())
        s3_key = f"workspace-documents/{notebook_id}/{document_id}{file_extension}"

        # Upload to S3
        file_content = await file.read()
        from io import BytesIO

        file_obj = BytesIO(file_content)
        file_size = len(file_content)

        # Determine MIME type
        mime_type = MIME_TYPES.get(file_extension, file.content_type or 'application/octet-stream')

        # Upload file
        file_url = s3_service.upload_file(
            file_obj=file_obj,
            object_name=s3_key,
            content_type=mime_type
        )

        # Determine document type
        doc_type_map = {
            '.pdf': 'pdf',
            '.docx': 'word',
            '.doc': 'word',
            '.xlsx': 'excel',
            '.xls': 'excel',
            '.pptx': 'powerpoint',
            '.ppt': 'powerpoint',
        }
        document_type = doc_type_map.get(file_extension, 'document')

        # Use custom title or filename
        doc_title = title if title else os.path.splitext(file.filename)[0]

        # Store in database
        now = datetime.utcnow().isoformat()
        metadata = json.dumps({
            "original_filename": file.filename,
            "manually_uploaded": True
        })

        await db.execute("""
            INSERT INTO workspace_documents (
                id, notebook_id, title, description, document_type,
                file_url, file_size, s3_key, mime_type, metadata,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id, notebook_id, doc_title, description, document_type,
            file_url, file_size, s3_key, mime_type, metadata,
            now, now
        ))
        await db.commit()

        # Update workspace note_count
        await db.execute("""
            UPDATE notebooks
            SET note_count = (
                SELECT COUNT(*) FROM notes WHERE notebook_id = ?
            ) + (
                SELECT COUNT(*) FROM workspace_documents WHERE notebook_id = ?
            ),
            updated = ?
            WHERE id = ?
        """, (notebook_id, notebook_id, now, notebook_id))
        await db.commit()

        return {
            "id": document_id,
            "notebook_id": notebook_id,
            "title": doc_title,
            "description": description,
            "document_type": document_type,
            "file_url": file_url,
            "file_size": file_size,
            "mime_type": mime_type,
            "original_filename": file.filename,
            "created_at": now,
            "manually_uploaded": True
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document upload failed: {str(e)}")
