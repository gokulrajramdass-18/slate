"""
Microsite API endpoints

Includes:
- CRUD for microsites
- Public access with OTP flow
- Generation, content management, moderation, templates, versions (generator feature)
"""
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime

from open_notebook.domain.microsite import Microsite, MicrositeAccess, MicrositeOTP
from open_notebook.domain.notebook import Notebook
from open_notebook.config import get_database
from open_notebook.database.repository import repo_query, repo_execute, repo_create
from api.services.smtp_service import SMTPService
from api.services.version_service import version_service
from api.models import (
    MicrositeGenerateRequest,
    MicrositeGenerateResponse,
    MicrositeContentResponse,
    MicrositeContentSection,
    MicrositeContentUpdate,
    MicrositeContentUpdateResponse,
    ModerationRequest,
    ModerationReport,
    ModerationHistoryResponse,
    ModerationLogEntry,
    MicrositeTemplateResponse,
    MicrositeTemplateListResponse,
    MicrositeVersionResponse,
    MicrositeVersionListResponse,
    MicrositeRollbackRequest,
    MicrositeRollbackResponse,
    MicrositePublishRequest,
    MicrositePublishResponse,
    MicrositeBlockRequest,
    MicrositeAccessCheckResponse,
    MicrositeActiveVersionResponse,
    MicrositeStatus,
)

router = APIRouter(prefix="/api/microsites", tags=["microsites"])


# ============================================================================
# Local Pydantic models (existing, kept for backward compatibility)
# ============================================================================

class MicrositeCreate(BaseModel):
    notebook_id: str
    title: str
    description: Optional[str] = None
    theme: str = "light"


class MicrositeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[str] = None
    is_active: Optional[bool] = None


class MicrositeResponse(BaseModel):
    id: str
    notebook_id: str
    title: str
    description: Optional[str]
    slug: str
    theme: str
    is_active: bool
    status: Optional[str] = "draft"
    created_by: Optional[str] = None
    active_version_id: Optional[str] = None
    created: str
    updated: str
    access_url: str
    allowed_emails: List[str]
    generation_config: Optional[str] = None  # JSON string with site settings


class MicrositeAccessAdd(BaseModel):
    email: EmailStr


class OTPRequest(BaseModel):
    email: EmailStr


class OTPVerify(BaseModel):
    email: EmailStr
    otp_code: str


class MicrositePublicResponse(BaseModel):
    title: str
    description: Optional[str]
    theme: str
    notebook_name: str
    notebook_description: Optional[str]
    sources: List[dict]


# ============================================================================
# Helper: verify microsite exists
# ============================================================================

async def _get_microsite_or_404(microsite_id: str) -> Dict[str, Any]:
    """Fetch a microsite by ID or raise 404."""
    results = await repo_query(
        "SELECT * FROM microsites WHERE id = :id",
        {"id": microsite_id}
    )
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microsite not found",
        )
    return results[0]


# ============================================================================
# Template endpoints (MUST be before /{microsite_id} routes)
# ============================================================================

@router.get("/templates", response_model=MicrositeTemplateListResponse)
async def list_templates(
    name: Optional[str] = Query(None, description="Filter by template name: blog, documentation, portfolio, landing_page, report"),
    is_custom: Optional[bool] = Query(None, description="Filter by custom templates"),
):
    """List available microsite templates"""
    sql = "SELECT * FROM microsite_templates WHERE 1=1"
    params = {}

    if name is not None:
        sql += " AND name = :name"
        params["name"] = name

    if is_custom is not None:
        sql += " AND is_custom = :is_custom"
        params["is_custom"] = 1 if is_custom else 0

    sql += " ORDER BY name ASC"

    try:
        results = await repo_query(sql, params)
    except Exception as e:
        # Table may not exist yet if migration hasn't run
        print(f"Error fetching templates: {e}")
        return MicrositeTemplateListResponse(templates=[])

    templates = [
        MicrositeTemplateResponse(
            id=row["id"],
            name=row["name"],
            display_name=row.get("display_name", row["name"]),
            description=row.get("description"),
            structure=row.get("structure"),
            default_styles=row.get("default_styles"),
            preview_image=row.get("preview_image"),
            is_custom=bool(row.get("is_custom", False)),
            created=row.get("created"),
        )
        for row in results
    ]

    return MicrositeTemplateListResponse(templates=templates)


@router.get("/templates/{template_id}", response_model=MicrositeTemplateResponse)
async def get_template(template_id: str):
    """Get a single microsite template by ID"""
    sql = "SELECT * FROM microsite_templates WHERE id = :id"
    try:
        results = await repo_query(sql, {"id": template_id})
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    row = results[0]
    return MicrositeTemplateResponse(
        id=row["id"],
        name=row["name"],
        display_name=row.get("display_name", row["name"]),
        description=row.get("description"),
        structure=row.get("structure"),
        default_styles=row.get("default_styles"),
        preview_image=row.get("preview_image"),
        is_custom=bool(row.get("is_custom", False)),
        created=row.get("created"),
    )


# ============================================================================
# Existing CRUD endpoints
# ============================================================================

@router.post("", response_model=MicrositeResponse, status_code=status.HTTP_201_CREATED)
async def create_microsite(microsite_data: MicrositeCreate):
    """Create a new microsite for a notebook"""
    # Verify notebook exists
    notebook_query = "SELECT id FROM notebooks WHERE id = :id"
    notebook_results = await repo_query(notebook_query, {"id": microsite_data.notebook_id})
    if not notebook_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found"
        )

    # Create microsite using Pydantic model
    user_id = get_current_user_id()
    microsite = Microsite(
        notebook_id=microsite_data.notebook_id,
        title=microsite_data.title,
        description=microsite_data.description,
        theme=microsite_data.theme,
        status="draft",
        created_by=user_id,
    )

    # Convert to dict for repo_create
    microsite_dict = microsite.model_dump()

    # Convert datetime objects to ISO strings for database
    if isinstance(microsite_dict.get("created"), datetime):
        microsite_dict["created"] = microsite_dict["created"].isoformat()
    if isinstance(microsite_dict.get("updated"), datetime):
        microsite_dict["updated"] = microsite_dict["updated"].isoformat()
    if isinstance(microsite_dict.get("expires_at"), datetime):
        microsite_dict["expires_at"] = microsite_dict["expires_at"].isoformat()

    # Create in database
    microsite_id = await repo_create("microsites", microsite_dict)

    # Fetch created microsite
    created_query = "SELECT * FROM microsites WHERE id = :id"
    created_result = await repo_query(created_query, {"id": microsite_id})

    if not created_result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create microsite"
        )

    created_microsite = created_result[0]

    return MicrositeResponse(
        **created_microsite,
        access_url=f"/site/view/public/{created_microsite['slug']}",
        allowed_emails=[]
    )


@router.get("", response_model=List[MicrositeResponse])
async def list_microsites(notebook_id: Optional[str] = None):
    """List all microsites, optionally filtered by notebook"""
    if notebook_id:
        query = "SELECT * FROM microsites WHERE notebook_id = :notebook_id ORDER BY created DESC"
        results = await repo_query(query, {"notebook_id": notebook_id})
    else:
        query = "SELECT * FROM microsites ORDER BY created DESC"
        results = await repo_query(query, {})

    microsites = []
    for row in results:
        # Get allowed emails
        access_query = "SELECT email FROM microsite_access WHERE microsite_id = :microsite_id"
        access_results = await repo_query(access_query, {"microsite_id": row["id"]})
        allowed_emails = [a["email"] for a in access_results]

        microsites.append(MicrositeResponse(
            **row,
            access_url=f"/site/view/public/{row['slug']}",
            allowed_emails=allowed_emails
        ))

    return microsites


@router.get("/{microsite_id}", response_model=MicrositeResponse)
async def get_microsite(microsite_id: str):
    """Get a specific microsite"""
    microsite = await _get_microsite_or_404(microsite_id)

    # Get allowed emails
    access_query = "SELECT email FROM microsite_access WHERE microsite_id = :microsite_id"
    access_results = await repo_query(access_query, {"microsite_id": microsite_id})
    allowed_emails = [a["email"] for a in access_results]

    return MicrositeResponse(
        id=microsite["id"],
        title=microsite["title"],
        description=microsite.get("description"),
        slug=microsite["slug"],
        notebook_id=microsite.get("notebook_id"),
        theme=microsite.get("theme", "light"),
        is_active=bool(microsite.get("is_active", True)),
        status=microsite.get("status", "draft"),
        created_by=microsite.get("created_by"),
        active_version_id=microsite.get("active_version_id"),
        generation_config=microsite.get("generation_config"),
        created=microsite.get("created"),
        updated=microsite.get("updated"),
        access_url=f"/site/view/public/{microsite['slug']}",
        allowed_emails=allowed_emails
    )


@router.put("/{microsite_id}", response_model=MicrositeResponse)
async def update_microsite(microsite_id: str, update_data: MicrositeUpdate):
    """Update a microsite"""
    microsite = await _get_microsite_or_404(microsite_id)

    # Build update query
    update_fields = {}
    if update_data.title is not None:
        update_fields["title"] = update_data.title
    if update_data.description is not None:
        update_fields["description"] = update_data.description
    if update_data.theme is not None:
        update_fields["theme"] = update_data.theme
    if update_data.is_active is not None:
        update_fields["is_active"] = 1 if update_data.is_active else 0

    if update_fields:
        update_fields["updated"] = datetime.utcnow().isoformat()
        update_fields["id"] = microsite_id

        set_clauses = ", ".join([f"{k} = :{k}" for k in update_fields if k != "id"])
        await repo_execute(
            f"UPDATE microsites SET {set_clauses} WHERE id = :id",
            update_fields
        )

    # Fetch updated microsite
    updated_microsite = await _get_microsite_or_404(microsite_id)

    # Get allowed emails
    access_query = "SELECT email FROM microsite_access WHERE microsite_id = :microsite_id"
    access_results = await repo_query(access_query, {"microsite_id": microsite_id})
    allowed_emails = [a["email"] for a in access_results]

    return MicrositeResponse(
        id=updated_microsite["id"],
        title=updated_microsite["title"],
        description=updated_microsite.get("description"),
        slug=updated_microsite["slug"],
        notebook_id=updated_microsite.get("notebook_id"),
        theme=updated_microsite.get("theme", "light"),
        is_active=bool(updated_microsite.get("is_active", True)),
        status=updated_microsite.get("status", "draft"),
        created_by=updated_microsite.get("created_by"),
        active_version_id=updated_microsite.get("active_version_id"),
        generation_config=updated_microsite.get("generation_config"),
        created=updated_microsite.get("created"),
        updated=updated_microsite.get("updated"),
        access_url=f"/site/view/public/{updated_microsite['slug']}",
        allowed_emails=allowed_emails
    )


@router.delete("/{microsite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_microsite(microsite_id: str):
    """Delete a microsite"""
    query = "DELETE FROM microsites WHERE id = :id"
    await repo_execute(query, {"id": microsite_id})


# ============================================================================
# Generation endpoint
# ============================================================================

@router.post("/{microsite_id}/generate", response_model=MicrositeGenerateResponse)
async def generate_microsite(microsite_id: str, request: MicrositeGenerateRequest):
    """
    Trigger AI-powered microsite generation.

    Uses the specified template and sources to generate content sections
    with AI enhancement, then runs the guardrails pipeline.
    """
    microsite = await _get_microsite_or_404(microsite_id)

    # Verify template exists
    template_results = await repo_query(
        "SELECT * FROM microsite_templates WHERE id = :id",
        {"id": request.template_id},
    )
    if not template_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Verify all source IDs exist (can be sources or notes)
    for source_id in request.source_ids:
        # Check in sources table
        source_results = await repo_query(
            "SELECT id FROM sources WHERE id = :id",
            {"id": source_id},
        )
        if not source_results:
            # If not a source, check in notes table
            note_results = await repo_query(
                "SELECT id FROM notes WHERE id = :id",
                {"id": source_id},
            )
            if not note_results:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Source or note not found: {source_id}",
                )

    # Call generation service
    from api.services.microsite_generation_service import MicrositeGenerationService

    service = MicrositeGenerationService()
    try:
        result = await service.generate_microsite(
            microsite_id=microsite_id,
            template_id=request.template_id,
            source_ids=request.source_ids,
            notebook_id=microsite.get("notebook_id"),
            user_prompt=request.user_prompt,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        )

    return result


# ============================================================================
# Site Settings Update (without content regeneration)
# ============================================================================

@router.put("/{microsite_id}/settings")
async def update_site_settings(microsite_id: str, settings: Dict[str, Any]):
    """
    Update site-level settings (title, logo, colors, nav items, footer text).

    This updates the generation_config and triggers a new version snapshot
    WITHOUT regenerating content via AI.
    """
    await _get_microsite_or_404(microsite_id)

    # Get current generation_config
    microsite_results = await repo_query(
        "SELECT generation_config, title FROM microsites WHERE id = :id",
        {"id": microsite_id}
    )
    if not microsite_results:
        raise HTTPException(status_code=404, detail="Microsite not found")

    microsite = microsite_results[0]
    current_config_str = microsite.get("generation_config", "{}")

    try:
        current_config = json.loads(current_config_str) if isinstance(current_config_str, str) else current_config_str
    except:
        current_config = {}

    # Update settings in generation_config
    if "site_title" in settings:
        current_config["site_title"] = settings["site_title"]
    if "logo_url" in settings:
        current_config["logo_url"] = settings["logo_url"]
    if "primary_color" in settings:
        current_config["primary_color"] = settings["primary_color"]
    if "footer_text" in settings:
        current_config["footer_text"] = settings["footer_text"]
    if "nav_items" in settings:
        current_config["nav_items"] = settings["nav_items"]

    # Update microsite record
    update_fields = {
        "generation_config": json.dumps(current_config),
        "updated": datetime.utcnow().isoformat(),
        "id": microsite_id
    }

    # Also update title if provided
    if "site_title" in settings:
        update_fields["title"] = settings["site_title"]

    set_clauses = ", ".join([f"{k} = :{k}" for k in update_fields if k != "id"])
    await repo_execute(
        f"UPDATE microsites SET {set_clauses} WHERE id = :id",
        update_fields
    )

    # Create new version snapshot with updated settings (without changing content)
    version = await version_service.create_publish_version(microsite_id)
    new_version = version.get("version_number", 0) if isinstance(version, dict) else 0

    return {
        "message": "Site settings updated successfully",
        "new_version": new_version
    }


# ============================================================================
# Preview endpoint (public)
# ============================================================================

@router.get("/{microsite_id}/preview", response_class=HTMLResponse)
async def preview_microsite(
    microsite_id: str,
    version: Optional[int] = Query(None, description="Version number (default: latest)"),
):
    """
    Get full HTML preview of a microsite.

    Returns the rendered HTML document. If version is specified, returns
    that version's snapshot; otherwise returns the latest version.

    Access control: blocked microsites return 403, draft microsites
    require the creator to be the current user.
    """
    microsite = await _get_microsite_or_404(microsite_id)

    # Check access control
    user_id = get_current_user_id()
    ms_status = microsite.get("status", "draft")
    if ms_status == "blocked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This microsite has been blocked",
        )
    if ms_status == "draft":
        created_by = microsite.get("created_by")
        if created_by and created_by != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Draft microsites are only accessible to their creator",
            )

    if version is not None:
        # Fetch specific version snapshot
        version_results = await repo_query(
            "SELECT * FROM microsite_versions WHERE microsite_id = :mid AND version_number = :vn",
            {"mid": microsite_id, "vn": version},
        )
        if not version_results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version} not found",
            )
        html_content = version_results[0].get("full_html", "")
    else:
        # Fetch latest version
        version_results = await repo_query(
            "SELECT * FROM microsite_versions WHERE microsite_id = :mid ORDER BY version_number DESC LIMIT 1",
            {"mid": microsite_id},
        )
        if not version_results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No versions found for this microsite",
            )
        html_content = version_results[0].get("full_html", "")

    # Return with no-cache headers to ensure fresh content
    return HTMLResponse(
        content=html_content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


# ============================================================================
# Content management endpoints
# ============================================================================

@router.get("/{microsite_id}/content", response_model=MicrositeContentResponse)
async def get_microsite_content_sections(microsite_id: str):
    """Get all content sections for a microsite"""
    await _get_microsite_or_404(microsite_id)
    # Get microsite metadata (template_id, custom_css)
    microsite_row = await repo_query(
        "SELECT template_id, custom_css FROM microsites WHERE id = :id",
        {"id": microsite_id},
    )
    template_id = microsite_row[0].get("template_id") if microsite_row else None
    custom_css = microsite_row[0].get("custom_css") if microsite_row else None

    # Get content sections
    sections_results = await repo_query(
        "SELECT * FROM microsite_content WHERE microsite_id = :mid ORDER BY order_num ASC",
        {"mid": microsite_id},
    )

    sections = [
        MicrositeContentSection(
            id=row["id"],
            microsite_id=row["microsite_id"],
            section_id=row.get("section_id", ""),
            order_num=row.get("order_num", 0),
            content_html=row.get("content_html"),
            content_json=row.get("content_json"),
            is_visible=bool(row.get("is_visible", True)),
            created=row.get("created"),
            updated=row.get("updated"),
        )
        for row in sections_results
    ]

    return MicrositeContentResponse(
        microsite_id=microsite_id,
        template_id=template_id,
        custom_css=custom_css,
        sections=sections,
    )


@router.put("/{microsite_id}/content", response_model=MicrositeContentUpdateResponse)
async def update_microsite_content(microsite_id: str, update: MicrositeContentUpdate):
    """
    Update content sections of a microsite (partial updates supported).

    Creates a new version snapshot after updating.
    """
    await _get_microsite_or_404(microsite_id)
    updated_sections = []
    now = datetime.utcnow().isoformat()

    # Update custom CSS if provided
    if update.custom_css is not None:
        await repo_execute(
            "UPDATE microsites SET custom_css = :css, updated = :updated WHERE id = :id",
            {"css": update.custom_css, "updated": now, "id": microsite_id}
        )

    for section_update in update.sections:
        # Verify section exists and belongs to this microsite
        existing = await repo_query(
            "SELECT * FROM microsite_content WHERE id = :id AND microsite_id = :mid",
            {"id": section_update.section_id, "mid": microsite_id},
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Section not found: {section_update.section_id}",
            )

        # Build update fields
        update_fields = {}
        if section_update.content_html is not None:
            update_fields["content_html"] = section_update.content_html
        if section_update.content_json is not None:
            update_fields["content_json"] = section_update.content_json

        if update_fields:
            update_fields["updated"] = now
            set_clauses = ", ".join(f"{k} = :{k}" for k in update_fields)
            update_fields["id"] = section_update.section_id
            await repo_execute(
                f"UPDATE microsite_content SET {set_clauses} WHERE id = :id",
                update_fields,
            )

        # Fetch updated section
        refreshed = await repo_query(
            "SELECT * FROM microsite_content WHERE id = :id",
            {"id": section_update.section_id},
        )
        if refreshed:
            row = refreshed[0]
            updated_sections.append(
                MicrositeContentSection(
                    id=row["id"],
                    microsite_id=row["microsite_id"],
                    section_id=row.get("section_id", ""),
                    order_num=row.get("order_num", 0),
                    content_html=row.get("content_html"),
                    content_json=row.get("content_json"),
                    is_visible=bool(row.get("is_visible", True)),
                    created=row.get("created"),
                    updated=row.get("updated"),
                )
            )

    # Create new version snapshot
    version = await version_service.create_publish_version(microsite_id)
    new_version = version.get("version_number", 0) if isinstance(version, dict) else 0

    return MicrositeContentUpdateResponse(
        updated_sections=updated_sections,
        new_version=new_version,
    )


# ============================================================================
# Moderation endpoints
# ============================================================================

@router.post("/{microsite_id}/moderate", response_model=ModerationReport)
async def moderate_microsite(microsite_id: str, request: Optional[ModerationRequest] = None):
    """
    Run the 4-layer guardrails pipeline on microsite content.

    Optionally specify section IDs to moderate only specific sections.
    """
    await _get_microsite_or_404(microsite_id)
    # Fetch content sections to moderate
    if request and request.section_ids:
        # Only moderate specific sections
        placeholders = ", ".join(f":sid_{i}" for i in range(len(request.section_ids)))
        params = {"mid": microsite_id}
        params.update({f"sid_{i}": sid for i, sid in enumerate(request.section_ids)})
        sections = await repo_query(
            f"SELECT * FROM microsite_content WHERE microsite_id = :mid AND id IN ({placeholders})",
            params,
        )
    else:
        sections = await repo_query(
            "SELECT * FROM microsite_content WHERE microsite_id = :mid ORDER BY order_num ASC",
            {"mid": microsite_id},
        )

    if not sections:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No content sections found to moderate",
        )

    # Combine HTML content for moderation
    all_html = "\n".join(s.get("content_html", "") for s in sections if s.get("content_html"))

    # Get linked source IDs for source validation layer
    source_results = await repo_query(
        "SELECT source_id FROM microsite_sources WHERE microsite_id = :mid",
        {"mid": microsite_id},
    )
    source_ids = [r["source_id"] for r in source_results] if source_results else []

    from api.services.guardrails_service import GuardrailsService

    service = GuardrailsService()
    try:
        report = await service.moderate_content(
            microsite_id=microsite_id,
            content=all_html,
            source_ids=source_ids,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Moderation failed: {str(e)}",
        )

    return report


@router.get("/{microsite_id}/moderation-history", response_model=ModerationHistoryResponse)
async def get_moderation_history(microsite_id: str):
    """Get moderation history logs for a microsite"""
    await _get_microsite_or_404(microsite_id)
    try:
        results = await repo_query(
            "SELECT * FROM content_moderation_logs WHERE microsite_id = :mid ORDER BY created DESC",
            {"mid": microsite_id},
        )
    except Exception:
        return ModerationHistoryResponse(microsite_id=microsite_id, logs=[], summary=None)

    logs = [
        ModerationLogEntry(
            id=row["id"],
            microsite_id=row["microsite_id"],
            content_section=row.get("content_section"),
            moderation_type=row.get("moderation_type", ""),
            status=row.get("status", ""),
            score=float(row.get("score", 0.0)),
            issues_found=row.get("issues_found"),
            metadata=row.get("metadata"),
            created=row.get("created"),
        )
        for row in results
    ]

    # Build summary
    summary = None
    if logs:
        total_runs = len(logs)
        passed = sum(1 for log in logs if log.status == "passed")
        warnings = sum(1 for log in logs if log.status == "warning")
        blocked = sum(1 for log in logs if log.status == "blocked")
        summary = {
            "total_runs": total_runs,
            "passed": passed,
            "warnings": warnings,
            "blocked": blocked,
        }

    return ModerationHistoryResponse(
        microsite_id=microsite_id,
        logs=logs,
        summary=summary,
    )


# ============================================================================
# Version management endpoints
# ============================================================================

@router.get("/{microsite_id}/versions", response_model=MicrositeVersionListResponse)
async def list_versions(microsite_id: str):
    """List all version snapshots for a microsite"""
    await _get_microsite_or_404(microsite_id)
    try:
        results = await repo_query(
            "SELECT id, microsite_id, version_number, content_snapshot, created_by, created FROM microsite_versions WHERE microsite_id = :mid ORDER BY version_number DESC",
            {"mid": microsite_id},
        )
    except Exception:
        return MicrositeVersionListResponse(microsite_id=microsite_id, versions=[])

    versions = [
        MicrositeVersionResponse(
            id=row["id"],
            microsite_id=row["microsite_id"],
            version_number=row.get("version_number", 0),
            content_snapshot=row.get("content_snapshot"),
            created_by=row.get("created_by"),
            created=row.get("created"),
        )
        for row in results
    ]

    return MicrositeVersionListResponse(
        microsite_id=microsite_id,
        versions=versions,
    )


@router.post("/{microsite_id}/rollback", response_model=MicrositeRollbackResponse)
async def rollback_version(microsite_id: str, request: MicrositeRollbackRequest):
    """
    Rollback a microsite to a specific version.

    Restores content sections from the version snapshot and creates a
    new version representing the rollback.
    """
    await _get_microsite_or_404(microsite_id)
    # Fetch the target version
    version_results = await repo_query(
        "SELECT * FROM microsite_versions WHERE microsite_id = :mid AND version_number = :vn",
        {"mid": microsite_id, "vn": request.version_number},
    )
    if not version_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {request.version_number} not found",
        )

    version_data = version_results[0]
    snapshot_json = version_data.get("content_snapshot")

    if not snapshot_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Version snapshot is empty and cannot be restored",
        )

    # Parse snapshot and restore content sections
    import json
    import uuid

    try:
        snapshot = json.loads(snapshot_json) if isinstance(snapshot_json, str) else snapshot_json
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse version snapshot",
        )

    # Delete current content sections
    await repo_execute(
        "DELETE FROM microsite_content WHERE microsite_id = :mid",
        {"mid": microsite_id},
    )

    # Restore sections from snapshot
    now = datetime.utcnow().isoformat()
    restored_sections = []
    sections_data = snapshot.get("sections", [])

    for idx, section in enumerate(sections_data):
        section_id = str(uuid.uuid4())
        await repo_execute(
            """INSERT INTO microsite_content
               (id, microsite_id, section_id, content_html, content_json, order_num, is_visible, created, updated)
               VALUES (:id, :mid, :section_id, :content_html, :content_json, :order_num, :is_visible, :created, :updated)""",
            {
                "id": section_id,
                "mid": microsite_id,
                "section_id": section.get("section_id", ""),
                "content_html": section.get("content_html"),
                "content_json": section.get("content_json"),
                "order_num": section.get("order_num", idx),
                "is_visible": 1 if section.get("is_visible", True) else 0,
                "created": now,
                "updated": now,
            },
        )
        restored_sections.append(
            MicrositeContentSection(
                id=section_id,
                microsite_id=microsite_id,
                section_id=section.get("section_id", ""),
                order_num=section.get("order_num", idx),
                content_html=section.get("content_html"),
                content_json=section.get("content_json"),
                is_visible=section.get("is_visible", True),
                created=now,
                updated=now,
            )
        )

    # Create a new version snapshot representing the rollback
    version = await version_service.create_publish_version(microsite_id)
    new_version = version.get("version_number", 0) if isinstance(version, dict) else 0

    return MicrositeRollbackResponse(
        microsite_id=microsite_id,
        restored_version=request.version_number,
        new_version=new_version,
        sections=restored_sections,
    )


# ============================================================================
# Status management helpers
# ============================================================================

def get_current_user_id() -> str:
    """Get current authenticated user ID (placeholder - integrate with auth system).

    TODO: Integrate with actual authentication system (JWT/session).
    """
    return "system"


async def check_microsite_access(
    microsite_id: str,
    user_id: Optional[str] = None,
) -> tuple:
    """Check if user can access a microsite.

    Returns:
        Tuple of (microsite_dict, has_access).
    Raises:
        HTTPException 404 if microsite not found.
    """
    microsite = await _get_microsite_or_404(microsite_id)

    ms_status = microsite.get("status", "draft")
    created_by = microsite.get("created_by")

    if ms_status == "published":
        return microsite, True
    if ms_status == "draft" and user_id and user_id == created_by:
        return microsite, True
    return microsite, False


# ============================================================================
# Status management endpoints
# ============================================================================

@router.post("/{microsite_id}/publish", response_model=MicrositePublishResponse)
async def publish_microsite(
    microsite_id: str,
    request: MicrositePublishRequest,
):
    """
    Publish a microsite. Creates a new version snapshot and sets it as active.
    Only the creator can publish their microsite.
    """
    user_id = get_current_user_id()
    microsite = await _get_microsite_or_404(microsite_id)

    if microsite.get("created_by") and microsite["created_by"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator can publish this microsite",
        )

    if microsite.get("status") == "blocked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot publish a blocked microsite",
        )

    # Create version snapshot from current content
    version = await version_service.create_publish_version(
        microsite_id=microsite_id,
        created_by=user_id,
        message=request.version_message,
    )

    version_id = version["id"] if isinstance(version, dict) else str(version)
    version_number = version.get("version_number", 0) if isinstance(version, dict) else 0

    # Update microsite status to published with active version
    now = datetime.utcnow().isoformat()
    await repo_execute(
        "UPDATE microsites SET status = :status, active_version_id = :vid, updated = :updated WHERE id = :id",
        {"status": "published", "vid": version_id, "updated": now, "id": microsite_id},
    )

    return MicrositePublishResponse(
        microsite_id=microsite_id,
        status=MicrositeStatus.PUBLISHED,
        active_version_id=version_id,
        version_number=version_number,
        published_at=now,
    )


@router.post("/{microsite_id}/unpublish")
async def unpublish_microsite(microsite_id: str):
    """
    Unpublish a microsite (revert to draft status).
    Only the creator can unpublish.
    """
    user_id = get_current_user_id()
    microsite = await _get_microsite_or_404(microsite_id)

    if microsite.get("created_by") and microsite["created_by"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator can unpublish this microsite",
        )

    now = datetime.utcnow().isoformat()
    await repo_execute(
        "UPDATE microsites SET status = :status, active_version_id = NULL, updated = :updated WHERE id = :id",
        {"status": "draft", "updated": now, "id": microsite_id},
    )

    return {"success": True, "status": "draft"}


@router.post("/{microsite_id}/block")
async def block_microsite(
    microsite_id: str,
    request: MicrositeBlockRequest,
):
    """
    Block a microsite (moderation action).
    """
    user_id = get_current_user_id()
    microsite = await _get_microsite_or_404(microsite_id)

    now = datetime.utcnow().isoformat()
    await repo_execute(
        "UPDATE microsites SET status = :status, active_version_id = NULL, updated = :updated WHERE id = :id",
        {"status": "blocked", "updated": now, "id": microsite_id},
    )

    return {"success": True, "status": "blocked", "reason": request.reason}


@router.get("/{microsite_id}/access-check", response_model=MicrositeAccessCheckResponse)
async def check_access(microsite_id: str):
    """Check if the current user can access this microsite."""
    user_id = get_current_user_id()
    microsite, has_access = await check_microsite_access(microsite_id, user_id)

    reason = None
    if not has_access:
        ms_status = microsite.get("status", "draft")
        if ms_status == "draft":
            reason = "Microsite is in draft status and only visible to creator"
        elif ms_status == "blocked":
            reason = "Microsite has been blocked by moderation"

    return MicrositeAccessCheckResponse(
        has_access=has_access,
        status=MicrositeStatus(microsite.get("status", "draft")),
        reason=reason,
    )


@router.get("/{microsite_id}/active-version", response_model=MicrositeActiveVersionResponse)
async def get_active_version(microsite_id: str):
    """Get the currently active/published version of a microsite."""
    microsite = await _get_microsite_or_404(microsite_id)

    active_version_id = microsite.get("active_version_id")
    if not active_version_id:
        return MicrositeActiveVersionResponse(
            microsite_id=microsite_id,
            active_version_id=None,
            version_number=None,
            published_at=None,
            full_html=None,
        )

    # Fetch active version details
    version_results = await repo_query(
        "SELECT * FROM microsite_versions WHERE id = :id",
        {"id": active_version_id},
    )

    if not version_results:
        return MicrositeActiveVersionResponse(
            microsite_id=microsite_id,
            active_version_id=None,
            version_number=None,
            published_at=None,
            full_html=None,
        )

    version = version_results[0]
    return MicrositeActiveVersionResponse(
        microsite_id=microsite_id,
        active_version_id=version["id"],
        version_number=version.get("version_number"),
        published_at=version.get("published_at") or version.get("created"),
        full_html=version.get("full_html"),
    )


# ============================================================================
# Access control endpoints (existing)
# ============================================================================

@router.post("/{microsite_id}/access", status_code=status.HTTP_201_CREATED)
async def add_microsite_access(microsite_id: str, access_data: MicrositeAccessAdd):
    """Add an email address to the allowed list"""
    microsite = await _get_microsite_or_404(microsite_id)

    # Check if already exists
    check_query = "SELECT * FROM microsite_access WHERE microsite_id = :microsite_id AND email = :email"
    existing = await repo_query(check_query, {
        "microsite_id": microsite_id,
        "email": access_data.email
    })

    if existing:
        return {"message": "Email already has access"}

    # Add access
    access = MicrositeAccess(
        microsite_id=microsite_id,
        email=access_data.email.lower()
    )
    await access.save()

    return {"message": "Access granted", "email": access_data.email}


@router.delete("/{microsite_id}/access/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_microsite_access(microsite_id: str, email: str):
    """Remove an email address from the allowed list"""
    query = "DELETE FROM microsite_access WHERE microsite_id = :microsite_id AND email = :email"
    await repo_execute(query, {"microsite_id": microsite_id, "email": email.lower()})


# ============================================================================
# Public endpoints (no authentication)
# ============================================================================

@router.get("/public/{slug}", response_class=HTMLResponse)
async def get_public_microsite(slug: str):
    """
    Serve the public microsite HTML directly (no authentication required for now).

    In production, you may want to add OTP-based authentication.
    """
    # Get microsite by slug
    query = "SELECT * FROM microsites WHERE slug = :slug AND is_active = 1"
    results = await repo_query(query, {"slug": slug})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microsite not found"
        )

    microsite = results[0]

    # Check status: only published microsites are publicly accessible
    if microsite.get("status", "draft") != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This microsite is not published",
        )

    microsite_id = microsite["id"]

    # Get latest version
    version_query = """
        SELECT full_html
        FROM microsite_versions
        WHERE microsite_id = :mid
        ORDER BY version_number DESC
        LIMIT 1
    """
    version_results = await repo_query(version_query, {"mid": microsite_id})

    if not version_results or not version_results[0].get("full_html"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microsite content not generated yet"
        )

    html_content = version_results[0]["full_html"]

    return HTMLResponse(
        content=html_content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@router.post("/public/{slug}/request-otp")
async def request_otp(slug: str, otp_request: OTPRequest):
    """Request an OTP code for microsite access"""
    # Get microsite by slug
    query = "SELECT * FROM microsites WHERE slug = :slug AND is_active = 1"
    results = await repo_query(query, {"slug": slug})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microsite not found"
        )

    microsite = results[0]

    # Check if email has access
    access_query = "SELECT * FROM microsite_access WHERE microsite_id = :microsite_id AND email = :email"
    access_results = await repo_query(access_query, {
        "microsite_id": microsite["id"],
        "email": otp_request.email.lower()
    })

    if not access_results:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not authorized to access this microsite"
        )

    # Generate OTP
    otp = MicrositeOTP(
        microsite_id=microsite["id"],
        email=otp_request.email.lower()
    )
    await otp.save()

    # Send email with OTP code
    email_sent = await SMTPService.send_otp_email(
        to_email=otp_request.email,
        otp_code=otp.otp_code,
        microsite_title=microsite["title"]
    )

    if not email_sent:
        # Fallback: print to console for development
        print(f"OTP for {otp_request.email}: {otp.otp_code}")
        return {
            "message": "SMTP not configured. OTP printed to console.",
            "expires_in_minutes": 15,
            "otp_code": otp.otp_code  # REMOVE IN PRODUCTION
        }

    return {
        "message": "OTP sent to email",
        "expires_in_minutes": 15
    }


@router.post("/public/{slug}/verify-otp")
async def verify_otp(slug: str, verify_data: OTPVerify):
    """Verify OTP code and grant access"""
    # Get microsite by slug
    query = "SELECT * FROM microsites WHERE slug = :slug AND is_active = 1"
    results = await repo_query(query, {"slug": slug})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microsite not found"
        )

    microsite = results[0]

    # Find valid OTP
    otp_query = """
        SELECT * FROM microsite_otp
        WHERE microsite_id = :microsite_id
        AND email = :email
        AND otp_code = :otp_code
        AND verified = 0
        ORDER BY created DESC
        LIMIT 1
    """
    otp_results = await repo_query(otp_query, {
        "microsite_id": microsite["id"],
        "email": verify_data.email.lower(),
        "otp_code": verify_data.otp_code
    })

    if not otp_results:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP code"
        )

    otp_data = otp_results[0]

    # Check if expired
    expires_at = datetime.fromisoformat(otp_data["expires_at"])
    if datetime.utcnow() > expires_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OTP code has expired"
        )

    # Mark as verified
    update_query = "UPDATE microsite_otp SET verified = 1 WHERE id = :id"
    await repo_execute(update_query, {"id": otp_data["id"]})

    return {
        "message": "Access granted",
        "access_token": f"{microsite['id']}:{verify_data.email.lower()}",  # Simple token for demo
        "microsite_slug": slug
    }


@router.get("/public/{slug}/content", response_model=MicrositePublicResponse)
async def get_microsite_content(slug: str, token: str):
    """Get microsite content (requires valid access token)"""
    # Get microsite by slug
    query = "SELECT * FROM microsites WHERE slug = :slug AND is_active = 1"
    results = await repo_query(query, {"slug": slug})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microsite not found"
        )

    microsite = results[0]

    # Verify token (simple validation for demo)
    try:
        microsite_id, email = token.split(":")
        if microsite_id != microsite["id"]:
            raise ValueError("Invalid token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )

    # Get notebook
    notebook = await Notebook.get(microsite["notebook_id"])
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notebook not found"
        )

    # Get sources
    sources_query = """
        SELECT s.* FROM sources s
        JOIN notebook_source ns ON s.id = ns.source_id
        WHERE ns.notebook_id = :notebook_id
        ORDER BY s.created DESC
    """
    sources = await repo_query(sources_query, {"notebook_id": notebook.id})

    return MicrositePublicResponse(
        title=microsite["title"],
        description=microsite["description"],
        theme=microsite["theme"],
        notebook_name=notebook.name,
        notebook_description=notebook.description,
        sources=[dict(s) for s in sources]
    )


# ============================================================================
# Internal helpers
# ============================================================================

# Version snapshot creation is now handled by api.services.version_service
