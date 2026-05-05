"""
File Upload Router - Handle file uploads to S3/MinIO storage
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Optional
import uuid
import os
from datetime import datetime

from api.services.s3_service import get_s3_service

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    notebook_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    """
    Upload a file to S3 storage

    Args:
        file: The file to upload
        notebook_id: Optional notebook ID to associate the file with
        description: Optional file description

    Returns:
        File metadata including URL and ID
    """
    try:
        s3_service = get_s3_service()

        # Check if S3 is available
        if not s3_service.client:
            raise HTTPException(
                status_code=503,
                detail="S3 storage is not available. Please start MinIO (Docker Desktop) or configure AWS S3 in environment variables."
            )

        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
        file_id = str(uuid.uuid4())
        object_name = f"uploads/{file_id}{file_extension}"

        # Upload to S3
        file_content = await file.read()
        from io import BytesIO

        file_obj = BytesIO(file_content)
        url = s3_service.upload_file(
            file_obj=file_obj, object_name=object_name, content_type=file.content_type
        )

        # Get file size
        file_size = len(file_content)

        return {
            "id": file_id,
            "filename": file.filename,
            "object_name": object_name,
            "url": url,
            "size": file_size,
            "content_type": file.content_type,
            "uploaded_at": datetime.utcnow().isoformat(),
            "notebook_id": notebook_id,
            "description": description,
        }

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


@router.get("/{file_id}")
async def get_file_url(file_id: str):
    """
    Get presigned URL for a file

    Args:
        file_id: The file ID

    Returns:
        Presigned URL to download the file
    """
    try:
        s3_service = get_s3_service()

        # Find file with this ID (search in uploads folder)
        # Note: In production, you'd look this up in database
        # For now, we'll assume object_name pattern
        object_name = f"uploads/{file_id}"

        # Check multiple extensions
        for ext in ["", ".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"]:
            test_name = f"{object_name}{ext}"
            if s3_service.file_exists(test_name):
                url = s3_service.get_file_url(test_name)
                metadata = s3_service.get_file_metadata(test_name)

                return {
                    "id": file_id,
                    "url": url,
                    "size": metadata["size"],
                    "content_type": metadata["content_type"],
                    "last_modified": metadata["last_modified"].isoformat(),
                }

        raise HTTPException(status_code=404, detail="File not found")

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Failed to get file: {str(e)}")


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    """
    Delete a file from S3 storage

    Args:
        file_id: The file ID

    Returns:
        Success message
    """
    try:
        s3_service = get_s3_service()

        # Find and delete file
        object_name = f"uploads/{file_id}"

        # Check multiple extensions
        deleted = False
        for ext in ["", ".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"]:
            test_name = f"{object_name}{ext}"
            if s3_service.file_exists(test_name):
                s3_service.delete_file(test_name)
                deleted = True
                break

        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")

        return {"message": "File deleted successfully", "id": file_id}

    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=500, detail=f"Failed to delete file: {str(e)}"
        )


@router.get("/")
async def list_files(notebook_id: Optional[str] = None):
    """
    List uploaded files

    Args:
        notebook_id: Optional filter by notebook ID

    Returns:
        List of files (placeholder - implement with database)
    """
    # TODO: Implement with database lookup
    return {
        "files": [],
        "message": "File listing requires database integration. Coming soon.",
    }
