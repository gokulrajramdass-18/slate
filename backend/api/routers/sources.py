"""
Sources API Router

Endpoints for source CRUD operations, including HANA tables and API sources.
"""

import json
import time
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status, UploadFile, File, Form, Request, Header, Depends
from fastapi.responses import JSONResponse

from api.models import (
    SourceCreate,
    SourceUpdate,
    SourceResponse,
    SourceType,
    HANATableSourceCreate,
    HANATestConnectionRequest,
    HANATestConnectionResponse,
    HANAListTablesRequest,
    HANAListTablesResponse,
    HANATableInfo,
    APISourceCreate,
    APITestRequest,
    APITestResponse,
    SyncTriggerRequest,
    SyncTriggerResponse,
    SyncStatusResponse,
    SyncHistoryResponse,
    SyncHistoryRecord,
    SyncConfigUpdateRequest,
    SyncConfigUpdateResponse,
    ErrorResponse,
    SuccessResponse,
)
from open_notebook.database.repository import repo_query, repo_create, repo_update, repo_delete, repo_execute
from api.dependencies.auth import get_current_user, require_permission
from api.services.permission_service import PermissionService
from open_notebook.domain.user import User


router = APIRouter(prefix="/api/sources", tags=["sources"])


# ============================================================================
# Helper Functions
# ============================================================================

async def get_source_by_id(source_id: str) -> Optional[dict]:
    """Get source by ID"""
    sql = "SELECT * FROM sources WHERE id = :id"
    results = await repo_query(sql, {"id": source_id})
    if results:
        source = results[0]
        # Parse JSON fields
        if source.get("tags"):
            source["tags"] = json.loads(source["tags"])
        if source.get("connection_config"):
            source["connection_config"] = json.loads(source["connection_config"])
        if source.get("sync_config"):
            source["sync_config"] = json.loads(source["sync_config"])
        return source
    return None


async def get_chunk_count(source_id: str) -> int:
    """Get count of chunks for source"""
    sql = """
        SELECT COUNT(*) as count
        FROM source_embeddings
        WHERE source_id = :source_id
    """
    results = await repo_query(sql, {"source_id": source_id})
    return results[0]["count"] if results else 0


async def enrich_source(source: dict, user_id: Optional[str] = None) -> SourceResponse:
    """Enrich source with chunk count, notebook information, and bookmark status"""
    # Only fetch chunk count if not already present in the source dict
    if "chunk_count" not in source or source["chunk_count"] is None:
        chunk_count = await get_chunk_count(source["id"])
        source["chunk_count"] = chunk_count

    # Fetch notebooks this source belongs to
    notebooks_sql = """
        SELECT n.id, n.name
        FROM notebooks n
        INNER JOIN notebook_source ns ON n.id = ns.notebook_id
        WHERE ns.source_id = :source_id
        ORDER BY n.name
    """
    notebooks = await repo_query(notebooks_sql, {"source_id": source["id"]})
    source["notebooks"] = notebooks

    # Add bookmark status if user_id provided
    if user_id:
        from open_notebook.domain.bookmark import Bookmark
        source["is_bookmarked"] = await Bookmark.is_bookmarked(
            user_id=user_id, entity_type="source", entity_id=source["id"]
        )

    return SourceResponse(**source)


# ============================================================================
# Standard CRUD Endpoints
# ============================================================================

@router.get("", response_model=List[SourceResponse])
async def list_sources(
    source_type: Optional[SourceType] = Query(None, description="Filter by source type"),
    notebook_id: Optional[str] = Query(None, description="Filter by notebook ID"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    order_by: str = Query("updated DESC", description="Order by field"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of records to return"),
    current_user: User = Depends(get_current_user),
):
    """
    List all sources with optional filtering

    - **source_type**: Filter by source type (file, url, text, youtube, hana_table, api)
    - **notebook_id**: Filter sources in specific notebook
    - **tag**: Filter sources with specific tag
    - **order_by**: Sort order
    """
    try:
        # Build query with LEFT JOINs to avoid N+1 queries
        sql = """
            SELECT s.*,
                   COUNT(DISTINCT se.id) as chunk_count,
                   CASE WHEN b.id IS NOT NULL THEN 1 ELSE 0 END as is_bookmarked
            FROM sources s
            LEFT JOIN source_embeddings se ON s.id = se.source_id
            LEFT JOIN user_bookmarks b ON b.entity_id = s.id AND b.entity_type = 'source' AND b.user_id = :current_user_id
        """
        params = {"current_user_id": current_user.id}
        joins = []
        where_clauses = []

        if notebook_id:
            joins.append("INNER JOIN notebook_source ns ON s.id = ns.source_id")
            where_clauses.append("ns.notebook_id = :notebook_id")
            params["notebook_id"] = notebook_id

        if source_type:
            where_clauses.append("s.source_type = :source_type")
            params["source_type"] = source_type.value

        if tag:
            where_clauses.append("s.tags LIKE :tag")
            params["tag"] = f"%{tag}%"

        # Permission filtering
        if not current_user.is_superadmin:
            has_read_all = await PermissionService.check_permission(
                user=current_user,
                resource_type="source",
                action="read",
            )

            if not has_read_all:
                where_clauses.append(
                    "(s.created_by = :user_id OR s.id IN ("
                    "SELECT resource_id FROM resource_shares "
                    "WHERE resource_type = 'source' AND "
                    "(shared_with_user = :user_id OR shared_with_role IN ("
                    "SELECT role_id FROM user_roles WHERE user_id = :user_id))"
                    "))"
                )
                params["user_id"] = current_user.id

        # Append additional joins
        for join in joins:
            sql += f" {join}"

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        sql += " GROUP BY s.id"
        sql += f" ORDER BY s.{order_by}"
        sql += " LIMIT :limit OFFSET :skip"
        params["limit"] = limit
        params["skip"] = skip

        # Execute query
        results = await repo_query(sql, params)

        # Parse JSON fields and build responses (no per-row queries needed)
        sources = []
        for source in results:
            if source.get("tags"):
                source["tags"] = json.loads(source["tags"])
            if source.get("connection_config"):
                source["connection_config"] = json.loads(source["connection_config"])
            if source.get("sync_config"):
                source["sync_config"] = json.loads(source["sync_config"])

            source["is_bookmarked"] = bool(source.get("is_bookmarked"))
            source["notebooks"] = []  # Notebooks omitted from list view for performance
            sources.append(SourceResponse(**source))

        return sources

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sources: {str(e)}",
        )


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    request: Request,
    source: SourceCreate,
    current_user: User = Depends(require_permission("source", "create")),
):
    """
    Create a new source (for existing types: file, url, text, youtube)

    For HANA table sources, use POST /sources/hana-table
    For API sources, use POST /sources/api

    - **name**: Source name (required)
    - **source_type**: Type of source (required)
    - **notebook_id**: Associated notebook ID (optional - defaults to "General" notebook)
    - **description**: Optional description
    - **tags**: Optional list of tags
    - **content**: For text sources
    - **url**: For URL/YouTube sources
    """
    try:
        # Debug: Log what we received
        import json as json_lib
        print(f"DEBUG: Received source data: {json_lib.dumps(source.model_dump(), indent=2)}")

        # Validate source type
        if source.source_type in [SourceType.HANA_TABLE, SourceType.API]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Use dedicated endpoint for {source.source_type.value} sources",
            )

        # Convert to dict and serialize JSON fields
        data = source.model_dump()

        # Extract notebook_id (used for junction table, not stored in sources table)
        notebook_id = data.pop("notebook_id", None)

        # If no notebook_id provided OR if it's "default", create/use default "General" notebook
        if not notebook_id or notebook_id == "default":
            from open_notebook.domain.notebook import Notebook
            result = await repo_query(
                "SELECT * FROM notebooks WHERE name = :name AND archived = :archived LIMIT 1",
                {"name": "General", "archived": False}
            )
            if result:
                notebook_id = result[0]["id"]
            else:
                # Create default notebook
                default_notebook = Notebook(
                    name="General",
                    description="Default notebook for sources"
                )
                await default_notebook.save()
                notebook_id = default_notebook.id

        # Remove fields that don't exist in sources table
        data.pop("description", None)
        data.pop("tags", None)

        # Map content to full_text
        if "content" in data:
            data["full_text"] = data.pop("content")

        # Fetch content based on source type
        url_value = data.pop("url", None)

        if url_value and source.source_type == SourceType.YOUTUBE:
            # Use YouTube extractor for video sources
            print(f"🎥 Extracting YouTube video data: {url_value}")
            try:
                from open_notebook.sources.youtube import extract_youtube_data

                youtube_data = await extract_youtube_data(url_value)

                # Store transcript in full_text
                data["full_text"] = youtube_data['transcript']

                # Store metadata in asset_data (JSON)
                asset_data = {
                    'video_id': youtube_data['video_id'],
                    'channel_id': youtube_data['channel_id'],
                    'channel_name': youtube_data['channel_name'],
                    'channel_handle': youtube_data.get('channel_handle', ''),
                    'duration_seconds': youtube_data['duration'],
                    'upload_date': youtube_data['upload_date'],
                    'view_count': youtube_data['view_count'],
                    'description': youtube_data['description'],
                    'transcript_language': youtube_data['transcript_language'],
                    'transcript_auto_generated': youtube_data['auto_generated'],
                    'transcript_available': youtube_data['transcript_available'],
                    'thumbnail_url': youtube_data['thumbnail_url'],
                    'keywords': youtube_data.get('keywords', [])
                }

                if youtube_data.get('error'):
                    asset_data['error'] = youtube_data['error']

                data["asset_data"] = json.dumps(asset_data)
                data["asset_type"] = "video"

                # Update title if not provided
                if not data.get("title") or data["title"] == "YouTube Video":
                    data["title"] = youtube_data['title']

                print(f"✅ Extracted YouTube data: {youtube_data['title']}")
                print(f"   - Transcript: {len(data['full_text'])} chars")
                print(f"   - Channel: {youtube_data['channel_name']}")
                print(f"   - Duration: {youtube_data['duration']}s")
                print(f"   - Language: {youtube_data['transcript_language']}")

            except Exception as e:
                print(f"❌ YouTube extraction failed: {e}")
                # Graceful fallback: store minimal data with failed status
                error_msg = str(e)
                data["full_text"] = f"YouTube Video: {url_value}\n\nError extracting content: {error_msg}"
                data["asset_data"] = json.dumps({
                    'error': error_msg,
                    'url': url_value
                })
                data["asset_type"] = "video"
                # Note: sync_status and error_message columns removed - errors tracked in asset_data

        elif url_value and source.source_type == SourceType.URL:
            # Use dedicated URL processor with Firecrawl
            print(f"🌐 Fetching content from URL: {url_value}")
            extraction_failed = False
            try:
                from open_notebook.sources.url_processor import extract_url_data

                # Extract URL data using Firecrawl or fallback
                url_data = await extract_url_data(url_value)

                # Store content and metadata
                data["full_text"] = url_data["full_text"]
                data["asset_type"] = url_data.get("asset_type", "webpage")

                # Store metadata as JSON
                metadata = url_data.get("metadata", {})
                data["asset_data"] = json.dumps(metadata)

                scraping_method = url_data.get("scraping_method", "unknown")
                content_length = len(data["full_text"])
                print(f"✅ Fetched {content_length} characters using {scraping_method}")

            except Exception as e:
                print(f"⚠️ Failed to fetch URL content: {e}")
                extraction_failed = True
                # Fall back to storing just the URL with error
                error_msg = str(e)
                data["full_text"] = f"URL: {url_value}\n\n(Content could not be fetched: {error_msg})"
                # Store error information in asset_data
                data["asset_data"] = json.dumps({"error": error_msg, "url": url_value})

        elif source.source_type == SourceType.FILE and data.get("connection_config"):
            # Process uploaded file - extract text from S3
            print(f"📄 Processing uploaded file...")
            try:
                from api.services.s3_service import get_s3_service
                from open_notebook.sources.file_processor import extract_text_from_file

                # Get file metadata from connection_config
                conn_config = json.loads(data["connection_config"]) if isinstance(data["connection_config"], str) else data["connection_config"]

                # Download file from S3
                s3_service = get_s3_service()
                if s3_service.client:
                    object_name = conn_config.get("object_name")
                    filename = conn_config.get("filename", "unknown")
                    content_type = conn_config.get("content_type", "application/octet-stream")

                    print(f"   Downloading: {object_name}")
                    file_content = s3_service.download_file(object_name)

                    # Extract text
                    print(f"   Extracting text from {filename}...")
                    extraction_result = await extract_text_from_file(file_content, filename, content_type)

                    # Store extracted text
                    data["full_text"] = extraction_result["text"]
                    data["asset_type"] = extraction_result["asset_type"]

                    # Merge extraction metadata with connection_config
                    conn_config.update(extraction_result["metadata"])
                    data["asset_data"] = json.dumps(conn_config)

                    print(f"✅ Extracted {len(data['full_text'])} characters from {filename}")
                    print(f"   - Type: {extraction_result['asset_type']}")
                    print(f"   - Words: {extraction_result['metadata'].get('word_count', 0)}")
                else:
                    print("⚠️ S3 not available, skipping file processing")
                    error_msg = "S3 storage unavailable"
                    data["full_text"] = f"File uploaded but not processed (S3 unavailable): {conn_config.get('filename')}"
                    # Store error in asset_data
                    data["asset_data"] = json.dumps({"error": error_msg, "filename": conn_config.get('filename')})

            except Exception as e:
                print(f"❌ File processing failed: {e}")
                # Graceful fallback with failed status
                error_msg = str(e)
                data["full_text"] = f"File uploaded but text extraction failed: {error_msg}"
                if data.get("connection_config"):
                    conn_config = json.loads(data["connection_config"]) if isinstance(data["connection_config"], str) else data["connection_config"]
                    data["full_text"] += f"\n\nFilename: {conn_config.get('filename', 'unknown')}"
                    # Store error in asset_data
                    data["asset_data"] = json.dumps({
                        "error": error_msg,
                        "filename": conn_config.get('filename', 'unknown')
                    })

        if data.get("connection_config"):
            data["connection_config"] = json.dumps(data["connection_config"])
        if data.get("sync_config"):
            data["sync_config"] = json.dumps(data["sync_config"])

        # Set created_by
        data["created_by"] = current_user.id

        # Create source
        source_id = await repo_create("sources", data)

        # Link to notebook (junction table doesn't have id/updated columns)
        await repo_execute(
            """
            INSERT INTO notebook_source (notebook_id, source_id, created)
            VALUES (:notebook_id, :source_id, :created)
            """,
            {
                "notebook_id": notebook_id,
                "source_id": source_id,
                "created": datetime.utcnow().isoformat()
            }
        )

        # Fetch created source
        created = await get_source_by_id(source_id)
        if not created:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created source",
            )

        # Trigger background embedding generation ONLY if:
        # 1. Source has content (full_text exists)
        # 2. Source doesn't have error in asset_data (extraction didn't fail)
        has_error = False
        if data.get("asset_data"):
            asset_data_dict = json.loads(data["asset_data"]) if isinstance(data["asset_data"], str) else data["asset_data"]
            has_error = asset_data_dict.get("error") is not None

        if data.get("full_text") and not has_error:
            # Note: sync_status column doesn't exist in sources table
            # Embedding status is tracked in background job system

            from api.services.embedding_service import get_embedding_service
            embedding_service = get_embedding_service()
            job_id = await embedding_service.start_background_job(source_id)
            print(f"🚀 Started background embedding job {job_id} for source {source_id}")

            # Trigger automatic classification in background
            try:
                from api.services.classification_service import ClassificationService
                classification_service = ClassificationService()
                # Run asynchronously without blocking
                import asyncio
                asyncio.create_task(classification_service.classify_source(source_id))
                print(f"🏷️ Started background classification for source {source_id}")
            except Exception as classify_error:
                print(f"⚠️ Failed to trigger classification: {classify_error}")
                # Don't fail source creation if classification fails

            # Re-fetch source with latest data
            created = await get_source_by_id(source_id)

        return await enrich_source(created)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()  # Print full traceback to logs
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create source: {str(e)}",
        )


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific source by ID

    - **source_id**: Source UUID
    """
    try:
        source = await get_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Check permission
        await PermissionService.require_permission(
            user=current_user,
            resource_type="source",
            action="read",
            resource_id=source_id,
            resource_owner=source.get("created_by"),
        )

        return await enrich_source(source, user_id=current_user.id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get source: {str(e)}",
        )


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: str,
    source: SourceUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing source

    - **source_id**: Source UUID
    - Only provided fields will be updated
    """
    try:
        # Check if source exists
        existing = await get_source_by_id(source_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Check permission
        await PermissionService.require_permission(
            user=current_user,
            resource_type="source",
            action="update",
            resource_id=source_id,
            resource_owner=existing.get("created_by"),
        )

        # Prepare update data
        data = source.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update",
            )

        # Serialize JSON fields
        if "tags" in data:
            data["tags"] = json.dumps(data["tags"])
        if "connection_config" in data:
            data["connection_config"] = json.dumps(data["connection_config"])
        if "sync_config" in data:
            data["sync_config"] = json.dumps(data["sync_config"])

        # Update source
        await repo_update("sources", source_id, data)

        # Fetch updated source
        updated = await get_source_by_id(source_id)
        return await enrich_source(updated)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update source: {str(e)}",
        )


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a source

    - **source_id**: Source UUID
    - Cascade deletes associated embeddings via database constraints
    - Deletes associated files from S3/MinIO if source type is 'file'
    """
    try:
        # Check if source exists
        existing = await get_source_by_id(source_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Check permission
        await PermissionService.require_permission(
            user=current_user,
            resource_type="source",
            action="delete",
            resource_id=source_id,
            resource_owner=existing.get("created_by"),
        )

        # If it's a file source, delete from S3
        if existing.get("source_type") == "file" and existing.get("connection_config"):
            try:
                from api.services.s3_service import get_s3_service

                conn_config = json.loads(existing["connection_config"]) if isinstance(existing["connection_config"], str) else existing["connection_config"]
                object_name = conn_config.get("object_name")

                if object_name:
                    s3_service = get_s3_service()
                    if s3_service.client:
                        print(f"🗑️  Deleting file from S3: {object_name}")
                        s3_service.delete_file(object_name)
                        print(f"✅ File deleted from S3: {object_name}")
                    else:
                        print(f"⚠️  S3 not available, file not deleted: {object_name}")

            except Exception as e:
                # Log error but don't fail the delete
                print(f"❌ Failed to delete file from S3: {e}")
                # Continue with source deletion even if S3 delete fails

        # Delete source (cascade will handle related records)
        await repo_delete("sources", source_id)

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete source: {str(e)}",
        )


@router.post("/{source_id}/regenerate-embeddings", response_model=dict)
async def regenerate_embeddings(source_id: str):
    """
    Regenerate embeddings for a source

    - **source_id**: Source UUID
    - Triggers background embedding generation
    - Returns job status
    """
    try:
        # Check if source exists
        existing = await get_source_by_id(source_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Check if source has content
        source_data = await repo_query(
            "SELECT full_text FROM sources WHERE id = :id",
            {"id": source_id}
        )

        if not source_data or not source_data[0].get("full_text"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Source has no content to embed",
            )

        # Note: sync_status column doesn't exist in sources table
        # Embedding status tracked by background job system

        # Trigger background embedding generation
        from api.services.embedding_service import get_embedding_service
        embedding_service = get_embedding_service()
        job_id = await embedding_service.start_background_job(source_id)

        print(f"🚀 Started embedding regeneration job {job_id} for source {source_id}")

        return {
            "success": True,
            "job_id": job_id,
            "source_id": source_id,
            "message": "Embedding generation started"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate embeddings: {str(e)}",
        )


# ============================================================================
# HANA Table Source Endpoints
# ============================================================================

@router.post("/hana-table/test-connection", response_model=HANATestConnectionResponse)
async def test_hana_connection(request: HANATestConnectionRequest):
    """
    Test HANA database connection

    - **connection**: HANA connection configuration
    """
    try:
        from hdbcli import dbapi

        # Build connection parameters
        conn_params = {
            'address': request.connection.host,
            'port': request.connection.port,
            'user': request.connection.user,
            'password': request.connection.password,
            'encrypt': request.connection.encrypt,
            'sslValidateCertificate': False  # For development; set to True in production
        }

        # Test connection
        start_time = time.time()

        connection = dbapi.connect(**conn_params)
        cursor = connection.cursor()

        latency_ms = (time.time() - start_time) * 1000

        # Get version
        cursor.execute("SELECT VERSION FROM SYS.M_DATABASE")
        result = cursor.fetchone()
        server_version = result[0] if result else None

        cursor.close()
        connection.close()

        return HANATestConnectionResponse(
            success=True,
            message="Successfully connected to HANA database",
            server_version=server_version,
            latency_ms=round(latency_ms, 2),
        )

    except Exception as e:
        return HANATestConnectionResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
        )


@router.post("/hana-table/list-tables", response_model=HANAListTablesResponse)
async def list_hana_tables(request: HANAListTablesRequest):
    """
    List available tables from HANA database after successful connection

    - **connection**: HANA connection configuration
    - **schema_filter**: Optional schema name to filter tables

    Returns list of tables with:
    - Schema name
    - Table name
    - Table type (TABLE, VIEW, etc.)
    - Record count
    - Available columns
    """
    try:
        from hdbcli import dbapi

        # Build connection parameters
        conn_params = {
            'address': request.connection.host,
            'port': request.connection.port,
            'user': request.connection.user,
            'password': request.connection.password,
            'encrypt': request.connection.encrypt,
            'sslValidateCertificate': False  # For development
        }

        # Connect using hdbcli directly (synchronous)
        connection = dbapi.connect(**conn_params)
        cursor = connection.cursor()

        # Determine schema to query
        schema_filter = request.schema_filter or request.connection.schema or request.connection.user.upper()

        # First, let's see what schemas are available
        schema_check_query = "SELECT DISTINCT SCHEMA_NAME FROM SYS.TABLES ORDER BY SCHEMA_NAME"
        cursor.execute(schema_check_query)
        available_schemas = [row[0] for row in cursor.fetchall()]
        print(f"Available schemas: {available_schemas}")
        print(f"Looking for schema: {schema_filter}")

        # Query to get tables and views - simplified with no restrictive filters
        # Note: We query SYS.TABLES for metadata and optionally M_TABLES for row counts
        tables_query = """
            SELECT
                SCHEMA_NAME,
                TABLE_NAME,
                TABLE_TYPE
            FROM SYS.TABLES
            WHERE SCHEMA_NAME = ?
            ORDER BY TABLE_NAME
        """

        cursor.execute(tables_query, (schema_filter,))
        print(f"Executed query for schema: {schema_filter}")
        tables_rows = cursor.fetchall()
        print(f"Found {len(tables_rows)} tables/views in schema {schema_filter}")

        tables = []
        for row in tables_rows:
            schema_name, table_name, table_type = row
            print(f"Processing table: {schema_name}.{table_name} ({table_type})")

            # Try to get record count from M_TABLES (monitoring view)
            # This may not be available for all tables, especially views
            record_count = None
            try:
                count_query = """
                    SELECT RECORD_COUNT
                    FROM M_TABLES
                    WHERE SCHEMA_NAME = ?
                        AND TABLE_NAME = ?
                """
                cursor.execute(count_query, (schema_name, table_name))
                count_result = cursor.fetchone()
                if count_result:
                    record_count = count_result[0]
            except Exception:
                # M_TABLES might not be accessible or table might be a view
                pass

            # Get columns for this table
            columns_query = """
                SELECT COLUMN_NAME
                FROM SYS.TABLE_COLUMNS
                WHERE SCHEMA_NAME = ?
                    AND TABLE_NAME = ?
                ORDER BY POSITION
            """
            cursor.execute(columns_query, (schema_name, table_name))
            columns_rows = cursor.fetchall()

            columns = [col[0] for col in columns_rows]

            tables.append(HANATableInfo(
                schema_name=schema_name,
                table_name=table_name,
                table_type=table_type,
                record_count=record_count,
                columns=columns
            ))

        cursor.close()
        connection.close()

        print(f"Returning {len(tables)} tables in response")
        for table in tables:
            print(f"  - {table.schema_name}.{table.table_name}: {len(table.columns or [])} columns")

        return HANAListTablesResponse(
            success=True,
            message=f"Found {len(tables)} tables in schema '{schema_filter}'",
            tables=tables,
            total_count=len(tables)
        )

    except Exception as e:
        print(f"Error listing tables: {str(e)}")
        import traceback
        traceback.print_exc()
        return HANAListTablesResponse(
            success=False,
            message=f"Failed to list tables: {str(e)}",
            tables=[],
            total_count=0
        )


@router.post("/hana-table", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_hana_table_source(
    source: HANATableSourceCreate,
    current_user: User = Depends(require_permission("source", "create")),
):
    """
    Create a HANA table source

    - **name**: Source name
    - **notebook_id**: Associated notebook ID (optional)
    - **config**: HANA table configuration (with connection_id or connection)
    - **sync_frequency**: How often to sync (manual, hourly, daily, weekly)
    """
    try:
        # Resolve connection if connection_id is provided
        if source.config.connection_id:
            # Fetch connection from hana_connections table
            conn_sql = "SELECT * FROM hana_connections WHERE id = :id"
            conn_results = await repo_query(conn_sql, {"id": source.config.connection_id})

            if not conn_results:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"HANA connection {source.config.connection_id} not found"
                )

            conn = conn_results[0]

            # Decrypt password
            from open_notebook.config import get_encryption_key
            from cryptography.fernet import Fernet
            import base64

            key = get_encryption_key()
            password = conn["password_encrypted"]
            if key:
                try:
                    fernet = Fernet(key.encode())
                    encrypted_bytes = base64.b64decode(password.encode())
                    decrypted = fernet.decrypt(encrypted_bytes)
                    password = decrypted.decode()
                except:
                    pass  # Use encrypted value if decryption fails

            # Build connection config from saved connection
            connection_config = {
                "host": conn["host"],
                "port": conn["port"],
                "database": conn["database"],
                "user": conn["user"],
                "password": password,
                "encrypt": bool(conn["encrypt"]),
                "schema": conn.get("schema"),
            }
        elif source.config.connection:
            # Use direct connection config
            connection_config = source.config.connection.model_dump()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either connection_id or connection must be provided"
            )

        # Build full config with resolved connection
        full_config = {
            "connection": connection_config,
            "table_name": source.config.table_name,
            "query": source.config.query,
            "key_column": source.config.key_column,
            "content_columns": source.config.content_columns,
        }
        if source.config.connection_id:
            full_config["connection_id"] = source.config.connection_id

        # Create source data
        sync_freq = source.sync_frequency if isinstance(source.sync_frequency, str) else source.sync_frequency.value
        data = {
            "title": source.name,  # Database column is 'title', not 'name'
            "source_type": SourceType.HANA_TABLE.value,
            "connection_config": json.dumps(full_config),
            "sync_config": json.dumps({"frequency": sync_freq}),
            "created_by": current_user.id,
        }

        # Create source
        source_id = await repo_create("sources", data)

        # Link to notebook if notebook_id is provided
        if source.notebook_id:
            await repo_create(
                "notebook_source",
                {"notebook_id": source.notebook_id, "source_id": source_id},
            )

        # Fetch created source
        created = await get_source_by_id(source_id)
        if not created:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created source",
            )

        return await enrich_source(created)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR creating HANA table source: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create HANA table source: {str(e)}",
        )


# ============================================================================
# API Source Endpoints
# ============================================================================

@router.post("/api/test", response_model=APITestResponse)
async def test_api_connection(request: APITestRequest):
    """
    Test API connection and authentication

    - **config**: API source configuration including auth
    """
    try:
        import httpx

        # Build headers
        headers = dict(request.config.headers) if request.config.headers else {}

        # Add authentication
        auth_type = request.config.auth_type
        auth_config = request.config.auth_config

        if auth_type == "basic" and auth_config:
            from httpx import BasicAuth
            auth = BasicAuth(auth_config["username"], auth_config["password"])
        elif auth_type == "bearer" and auth_config:
            headers["Authorization"] = f"Bearer {auth_config['token']}"
            auth = None
        elif auth_type == "api_key" and auth_config:
            header_name = auth_config.get("header_name", "X-API-Key")
            prefix = auth_config.get("prefix", "")
            token = auth_config["key"]
            headers[header_name] = f"{prefix} {token}".strip() if prefix else token
            auth = None
        else:
            auth = None

        # Make request
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()

            if request.config.method == "GET":
                response = await client.get(
                    request.config.url,
                    headers=headers,
                    params=request.config.query_params,
                    auth=auth,
                )
            else:  # POST
                response = await client.post(
                    request.config.url,
                    headers=headers,
                    params=request.config.query_params,
                    json=request.config.body,
                    auth=auth,
                )

            latency_ms = (time.time() - start_time) * 1000

        # Parse response
        try:
            response_data = response.json()
            sample_data = response_data if isinstance(response_data, dict) else {"data": response_data}
        except:
            sample_data = None

        if response.status_code >= 400:
            return APITestResponse(
                success=False,
                message=f"API request failed with status {response.status_code}",
                status_code=response.status_code,
                latency_ms=round(latency_ms, 2),
            )

        return APITestResponse(
            success=True,
            message="Successfully connected to API",
            status_code=response.status_code,
            response_size=len(response.content),
            latency_ms=round(latency_ms, 2),
            sample_data=sample_data,
        )

    except Exception as e:
        return APITestResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
        )


@router.post("/api", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_api_source(
    source: APISourceCreate,
    current_user: User = Depends(require_permission("source", "create")),
):
    """
    Create an API source

    - **name**: Source name
    - **notebook_id**: Associated notebook ID (optional)
    - **config**: API configuration (with connection_id or direct config)
    - **sync_frequency**: How often to sync (manual, hourly, daily, weekly)
    """
    try:
        # Resolve connection if connection_id is provided
        if source.config.connection_id:
            # Fetch connection from api_connections table
            conn_sql = "SELECT * FROM api_connections WHERE id = :id"
            conn_results = await repo_query(conn_sql, {"id": source.config.connection_id})

            if not conn_results:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"API connection {source.config.connection_id} not found"
                )

            conn = conn_results[0]

            # Decrypt auth config
            from open_notebook.config import get_encryption_key
            from cryptography.fernet import Fernet
            import base64

            auth_config = None
            if conn.get("auth_config_encrypted"):
                key = get_encryption_key()
                if key:
                    try:
                        fernet = Fernet(key.encode())
                        encrypted_bytes = base64.b64decode(conn["auth_config_encrypted"].encode())
                        decrypted = fernet.decrypt(encrypted_bytes)
                        auth_config = json.loads(decrypted.decode())
                    except:
                        pass  # Use None if decryption fails

            # Build config from saved connection
            full_config = {
                "connection_id": source.config.connection_id,
                "url": conn["endpoint"],
                "method": conn.get("method", "GET"),
                "auth_type": conn["auth_type"],
                "auth_config": auth_config,
                "headers": json.loads(conn.get("headers") or "{}"),
                "query_params": json.loads(conn.get("query_params") or "{}"),
                "body": json.loads(conn["request_body"]) if conn.get("request_body") else None,
                "json_path": conn.get("data_path"),
            }
        else:
            # Use direct config (legacy)
            full_config = source.config.model_dump()

        # Create source data
        sync_freq = source.sync_frequency if isinstance(source.sync_frequency, str) else source.sync_frequency.value
        data = {
            "title": source.name,
            "source_type": SourceType.API.value,
            "connection_config": json.dumps(full_config),
            "sync_config": json.dumps({"frequency": sync_freq}),
            "created_by": current_user.id,
        }

        # Create source
        source_id = await repo_create("sources", data)

        # Link to notebook if notebook_id is provided
        if source.notebook_id:
            await repo_create(
                "notebook_source",
                {"notebook_id": source.notebook_id, "source_id": source_id},
            )

        # Fetch created source
        created = await get_source_by_id(source_id)
        if not created:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created source",
            )

        return await enrich_source(created)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API source: {str(e)}",
        )


# ============================================================================
# Source Sync Endpoints
# ============================================================================

@router.post("/{source_id}/sync", response_model=SyncTriggerResponse)
async def trigger_source_sync(source_id: str, request: SyncTriggerRequest = SyncTriggerRequest()):
    """
    Trigger sync for a source (manual execution)

    - **source_id**: Source UUID
    - **force**: Force sync even if recently synced or already in progress

    Works for:
    - HANA table sources
    - API sources
    """
    try:
        # Check if source exists
        source = await get_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Check if source type supports sync
        if source["source_type"] not in ["hana_table", "api"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Source type '{source['source_type']}' does not support sync",
            )

        # Get sync service
        from api.services.sync_service import get_sync_service
        sync_service = get_sync_service()

        # Execute sync
        history_id = await sync_service.execute_sync(source_id, force=request.force)

        return SyncTriggerResponse(
            success=True,
            message="Sync job started successfully",
            job_id=history_id,
            estimated_time=60,  # Rough estimate
        )

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger sync: {str(e)}",
        )


@router.get("/{source_id}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(source_id: str):
    """
    Get sync status for a source

    - **source_id**: Source UUID

    Returns:
    - Current sync status
    - Last sync time
    - Latest sync details
    - Scheduled job info (if any)
    """
    try:
        # Check if source exists
        source = await get_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Get sync service
        from api.services.sync_service import get_sync_service
        sync_service = get_sync_service()

        # Get status
        sync_status = await sync_service.get_sync_status(source_id)
        if not sync_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No sync status found for source {source_id}",
            )

        return SyncStatusResponse(**sync_status)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}",
        )


@router.get("/{source_id}/sync/history", response_model=SyncHistoryResponse)
async def get_sync_history(
    source_id: str,
    limit: int = Query(10, ge=1, le=100, description="Number of records to return")
):
    """
    Get sync history for a source

    - **source_id**: Source UUID
    - **limit**: Maximum number of records (default: 10, max: 100)

    Returns list of past sync operations with:
    - Status (completed, failed, etc.)
    - Timestamp
    - Rows updated
    - Duration
    - Error messages (if any)
    """
    try:
        # Check if source exists
        source = await get_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Get sync service
        from api.services.sync_service import get_sync_service
        sync_service = get_sync_service()

        # Get history
        history = await sync_service.get_sync_history(source_id, limit=limit)

        # Convert to response models
        records = [SyncHistoryRecord(**record) for record in history]

        return SyncHistoryResponse(
            source_id=source_id,
            history=records,
            total=len(records)
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync history: {str(e)}",
        )


@router.put("/{source_id}/sync/config", response_model=SyncConfigUpdateResponse)
async def update_sync_config(source_id: str, request: SyncConfigUpdateRequest):
    """
    Update sync configuration for a source

    - **source_id**: Source UUID
    - **frequency**: Sync frequency (manual, hourly, daily, weekly)

    This will:
    - Update the source's sync_config
    - Schedule/cancel background sync jobs
    - Return next scheduled run time

    Note: Set frequency to 'manual' to disable automatic sync
    """
    try:
        # Check if source exists
        source = await get_source_by_id(source_id)
        if not source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source {source_id} not found",
            )

        # Check if source type supports sync
        if source["source_type"] not in ["hana_table", "api"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Source type '{source['source_type']}' does not support sync",
            )

        # Get sync service
        from api.services.sync_service import get_sync_service
        sync_service = get_sync_service()

        # Schedule sync
        result = await sync_service.schedule_sync(source_id, request.frequency.value)

        return SyncConfigUpdateResponse(
            success=True,
            message=result.get("message", "Sync configuration updated"),
            source_id=source_id,
            frequency=request.frequency.value,
            cron=result.get("cron"),
            next_run=result.get("next_run"),
            scheduled=result.get("scheduled", False)
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update sync config: {str(e)}",
        )

