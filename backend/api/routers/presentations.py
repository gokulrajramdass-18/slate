"""
Presentations API Router

REST endpoints for PowerPoint presentation generation and management.
"""

import io
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
import aiosqlite

from open_notebook.domain.presentation import (
    Presentation,
    PresentationTemplate,
    PresentationContent,
    PresentationVersion
)
from api.services.presentation_generation_service import PresentationGenerationService
from api.services.pptx_export_service import PPTXExportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/presentations", tags=["presentations"])


# Request/Response Models

class GenerateRequest(BaseModel):
    """Request to generate a presentation"""
    template_id: str = Field(..., description="Template ID to use")
    source_ids: List[str] = Field(..., description="List of source IDs for content")
    notebook_id: Optional[str] = Field(None, description="Workspace/notebook ID")
    user_prompt: str = Field(..., description="User's generation request")
    target_slide_count: int = Field(10, ge=1, le=50, description="Target number of slides")


class UpdateSlideRequest(BaseModel):
    """Request to update a slide"""
    slide_type: Optional[str] = Field(None, description="New slide type")
    content_json: Optional[dict] = Field(None, description="New content JSON")
    speaker_notes: Optional[str] = Field(None, description="Speaker notes")


class AddSlideRequest(BaseModel):
    """Request to add a new slide"""
    slide_type: str = Field(..., description="Slide type")
    content_json: dict = Field(..., description="Content JSON")
    insert_after: int = Field(..., description="Insert after this slide number")
    speaker_notes: Optional[str] = Field(None, description="Speaker notes")


class ReorderRequest(BaseModel):
    """Request to reorder slides"""
    slide_order: List[int] = Field(..., description="New slide order (slide numbers)")


class RefineRequest(BaseModel):
    """Request to refine presentation via natural language"""
    message: str = Field(..., description="Refinement command")


class CreatePresentationRequest(BaseModel):
    """Request to create a presentation record"""
    notebook_id: Optional[str] = None
    template_id: Optional[str] = None
    title: str = "Untitled Presentation"
    description: Optional[str] = None


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


# Endpoints

@router.post("/{presentation_id}/generate")
async def generate_presentation(
    presentation_id: str,
    request: GenerateRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Generate presentation from sources using AI.

    Two-phase generation:
    1. AI creates slide outline
    2. AI generates detailed content per slide
    """
    try:
        service = PresentationGenerationService(db)
        result = await service.generate_presentation(
            presentation_id=presentation_id,
            template_id=request.template_id,
            source_ids=request.source_ids,
            notebook_id=request.notebook_id,
            user_prompt=request.user_prompt,
            target_slide_count=request.target_slide_count
        )

        return {
            "success": True,
            "presentation_id": result["presentation_id"],
            "slide_count": result["slide_count"],
            "preview_url": f"/api/presentations/{presentation_id}/preview",
            "download_url": f"/api/presentations/{presentation_id}/download"
        }

    except ValueError as e:
        # User input validation errors
        logger.error(f"Validation error in presentation generation: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Validation Error",
                "message": str(e),
                "hint": "Check your input parameters and try again."
            }
        )
    except FileNotFoundError as e:
        # Template or source not found
        logger.error(f"Resource not found in presentation generation: {str(e)}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Not Found",
                "message": str(e),
                "hint": "Check that the template and sources exist."
            }
        )
    except Exception as e:
        # Generic error with helpful hints
        logger.error(f"Failed to generate presentation: {str(e)}")
        error_msg = str(e).lower()

        # Provide context-specific error messages
        if "api key" in error_msg or "authentication" in error_msg:
            detail = {
                "error": "Authentication Error",
                "message": "API key validation failed",
                "hint": "Check your AI provider credentials in Settings."
            }
            status_code = 401
        elif "model" in error_msg and "not" in error_msg:
            detail = {
                "error": "Model Error",
                "message": str(e),
                "hint": "The configured AI model may not be available. Try a different credential."
            }
            status_code = 400
        elif "timeout" in error_msg or "timed out" in error_msg:
            detail = {
                "error": "Timeout Error",
                "message": "AI generation timed out",
                "hint": "Try again with fewer slides or simpler content."
            }
            status_code = 504
        else:
            detail = {
                "error": "Generation Error",
                "message": str(e),
                "hint": "An unexpected error occurred. Check logs for details."
            }
            status_code = 500

        raise HTTPException(status_code=status_code, detail=detail)


@router.get("/{presentation_id}/preview", response_class=HTMLResponse)
async def get_preview(
    presentation_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Get HTML preview of presentation.

    Returns interactive HTML with slide navigation.
    """
    try:
        # Fetch slides
        query = """
            SELECT * FROM presentation_content
            WHERE presentation_id = ?
            ORDER BY slide_number
        """
        async with db.execute(query, (presentation_id,)) as cursor:
            rows = await cursor.fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="Presentation not found")

        slides = [PresentationContent.from_db(dict(row)) for row in rows]

        # Fetch template
        template_query = """
            SELECT pt.* FROM presentation_templates pt
            JOIN presentations p ON p.template_id = pt.id
            WHERE p.id = ?
        """
        async with db.execute(template_query, (presentation_id,)) as cursor:
            template_row = await cursor.fetchone()

        if not template_row:
            # Use default template
            template = PresentationTemplate(
                id="default",
                name="Default",
                theme_json={"colors": {}, "fonts": {}}
            )
        else:
            template = PresentationTemplate.from_db(dict(template_row))

        # Generate HTML
        service = PresentationGenerationService(db)
        html = service._generate_preview_html(slides, template)

        return HTMLResponse(content=html)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get preview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{presentation_id}/download")
async def download_pptx(
    presentation_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Download presentation as PPTX file.

    Uses python-pptx library to generate PowerPoint file.
    """
    try:
        # Fetch presentation
        pres_query = "SELECT * FROM presentations WHERE id = ?"
        async with db.execute(pres_query, (presentation_id,)) as cursor:
            pres_row = await cursor.fetchone()

        if not pres_row:
            raise HTTPException(status_code=404, detail="Presentation not found")

        presentation = Presentation.from_db(dict(pres_row))

        # Fetch slides
        slides_query = """
            SELECT * FROM presentation_content
            WHERE presentation_id = ?
            ORDER BY slide_number
        """
        async with db.execute(slides_query, (presentation_id,)) as cursor:
            slide_rows = await cursor.fetchall()

        # Parse JSON fields in slides
        slides = []
        for row in slide_rows:
            slide_dict = dict(row)
            # Parse content_json from string to dict
            if isinstance(slide_dict.get("content_json"), str):
                slide_dict["content_json"] = json.loads(slide_dict["content_json"])
            slides.append(slide_dict)

        if not slides:
            raise HTTPException(status_code=404, detail="No slides found")

        # Fetch template
        template_query = "SELECT * FROM presentation_templates WHERE id = ?"
        async with db.execute(template_query, (presentation.template_id,)) as cursor:
            template_row = await cursor.fetchone()

        if not template_row:
            raise HTTPException(status_code=404, detail="Template not found")

        template = PresentationTemplate.from_db(dict(template_row))

        # Export to PPTX
        export_service = PPTXExportService()
        pptx_bytes = export_service.export_to_pptx(
            slides=slides,
            theme=template.theme_json,
            title=presentation.title
        )

        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(pptx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f'attachment; filename="{presentation.title}.pptx"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download PPTX: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{presentation_id}/slides")
async def list_slides(
    presentation_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """List all slides in a presentation"""
    try:
        query = """
            SELECT * FROM presentation_content
            WHERE presentation_id = ?
            ORDER BY slide_number
        """
        async with db.execute(query, (presentation_id,)) as cursor:
            rows = await cursor.fetchall()

        slides = [PresentationContent.from_db(dict(row)).to_dict() for row in rows]

        return {
            "presentation_id": presentation_id,
            "slide_count": len(slides),
            "slides": slides
        }

    except Exception as e:
        logger.error(f"Failed to list slides: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{presentation_id}/slides/{slide_number}")
async def get_slide(
    presentation_id: str,
    slide_number: int,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Get a specific slide"""
    try:
        query = """
            SELECT * FROM presentation_content
            WHERE presentation_id = ? AND slide_number = ?
        """
        async with db.execute(query, (presentation_id, slide_number)) as cursor:
            row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Slide not found")

        slide = PresentationContent.from_db(dict(row))

        return slide.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get slide: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{presentation_id}/slides/{slide_number}")
async def update_slide(
    presentation_id: str,
    slide_number: int,
    request: UpdateSlideRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Update slide content"""
    try:
        # Fetch existing slide
        query = """
            SELECT * FROM presentation_content
            WHERE presentation_id = ? AND slide_number = ?
        """
        async with db.execute(query, (presentation_id, slide_number)) as cursor:
            row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Slide not found")

        slide = PresentationContent.from_db(dict(row))

        # Update fields
        if request.slide_type is not None:
            slide.slide_type = request.slide_type

        if request.content_json is not None:
            slide.content_json = request.content_json

        if request.speaker_notes is not None:
            slide.speaker_notes = request.speaker_notes

        from datetime import datetime
        slide.updated_at = datetime.utcnow()

        # Save
        import json
        update_query = """
            UPDATE presentation_content
            SET slide_type = ?, content_json = ?, speaker_notes = ?, updated_at = ?
            WHERE id = ?
        """
        await db.execute(
            update_query,
            (
                slide.slide_type,
                json.dumps(slide.content_json),
                slide.speaker_notes,
                slide.updated_at.isoformat(),
                slide.id
            )
        )
        await db.commit()

        return {"success": True, "message": "Slide updated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update slide: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{presentation_id}/slides")
async def add_slide(
    presentation_id: str,
    request: AddSlideRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Insert a new slide"""
    try:
        import uuid
        from datetime import datetime

        # Increment slide numbers after insertion point
        update_query = """
            UPDATE presentation_content
            SET slide_number = slide_number + 1
            WHERE presentation_id = ? AND slide_number > ?
        """
        await db.execute(update_query, (presentation_id, request.insert_after))

        # Create new slide
        new_slide = PresentationContent(
            id=str(uuid.uuid4()),
            presentation_id=presentation_id,
            slide_number=request.insert_after + 1,
            slide_type=request.slide_type,
            content_json=request.content_json,
            speaker_notes=request.speaker_notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Insert
        import json
        slide_dict = new_slide.to_dict()
        columns = ", ".join(slide_dict.keys())
        placeholders = ", ".join("?" * len(slide_dict))

        insert_query = f"""
            INSERT INTO presentation_content ({columns})
            VALUES ({placeholders})
        """
        await db.execute(insert_query, tuple(slide_dict.values()))
        await db.commit()

        return {"success": True, "slide_id": new_slide.id, "slide_number": new_slide.slide_number}

    except Exception as e:
        logger.error(f"Failed to add slide: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{presentation_id}/slides/{slide_number}")
async def delete_slide(
    presentation_id: str,
    slide_number: int,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Delete a slide and renumber remaining slides"""
    try:
        # Delete slide
        delete_query = """
            DELETE FROM presentation_content
            WHERE presentation_id = ? AND slide_number = ?
        """
        await db.execute(delete_query, (presentation_id, slide_number))

        # Renumber subsequent slides
        renumber_query = """
            UPDATE presentation_content
            SET slide_number = slide_number - 1
            WHERE presentation_id = ? AND slide_number > ?
        """
        await db.execute(renumber_query, (presentation_id, slide_number))
        await db.commit()

        return {"success": True, "message": f"Slide {slide_number} deleted"}

    except Exception as e:
        logger.error(f"Failed to delete slide: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{presentation_id}/slides/reorder")
async def reorder_slides(
    presentation_id: str,
    request: ReorderRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Reorder slides based on new slide order.

    Example: [3, 1, 2] moves slide 3 to position 1
    """
    try:
        # Fetch all slides
        query = """
            SELECT * FROM presentation_content
            WHERE presentation_id = ?
            ORDER BY slide_number
        """
        async with db.execute(query, (presentation_id,)) as cursor:
            rows = await cursor.fetchall()

        slides = {row["slide_number"]: dict(row) for row in rows}

        # Validate slide order
        if len(request.slide_order) != len(slides):
            raise HTTPException(status_code=400, detail="Invalid slide order")

        if set(request.slide_order) != set(slides.keys()):
            raise HTTPException(status_code=400, detail="Invalid slide numbers")

        # Update slide numbers
        for new_number, old_number in enumerate(request.slide_order, start=1):
            update_query = """
                UPDATE presentation_content
                SET slide_number = ?
                WHERE presentation_id = ? AND id = ?
            """
            await db.execute(
                update_query,
                (new_number, presentation_id, slides[old_number]["id"])
            )

        await db.commit()

        return {"success": True, "message": "Slides reordered"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reorder slides: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{presentation_id}/refine")
async def refine_presentation(
    presentation_id: str,
    request: RefineRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Refine presentation using natural language commands.

    Examples:
    - "change slide 3 title to 'Market Analysis'"
    - "add a slide about competitors after slide 5"
    - "remove slide 7"
    """
    try:
        service = PresentationGenerationService(db)

        # Parse command
        command = await service.parse_refine_command(request.message)

        # Execute refinement
        result = await service.refine_slide(presentation_id, command)

        return result

    except Exception as e:
        logger.error(f"Failed to refine presentation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-intent")
async def detect_presentation_intent(
    request: dict,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Use AI to detect if a message is requesting presentation generation.

    Returns intent classification with extracted parameters.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        message = request.get("message", "")

        if not message or len(message.strip()) < 5:
            return {"isMatch": False}

        # Use AI to classify intent
        llm = ChatOpenAI(
            model="anthropic--claude-4.6-sonnet",
            openai_api_base="http://localhost:6655/litellm/v1",
            openai_api_key="42cf7b97-46a1-4613-a082-d5f1d60e1678",
            temperature=0.0,
            max_tokens=200
        )

        system_prompt = """You are an intent classifier. Determine if the user's message is requesting PowerPoint/presentation generation.

Return ONLY a JSON object with this exact structure:
{
  "isMatch": true/false,
  "slideCount": <number or null>,
  "topic": "<extracted topic or null>",
  "templateHint": "<business-pitch|academic-report|sales-deck|marketing-campaign|startup-pitch|null>"
}

Examples:
- "Create a presentation about AI" -> {"isMatch": true, "slideCount": null, "topic": "AI", "templateHint": null}
- "Generate 10 slides about quantum computing" -> {"isMatch": true, "slideCount": 10, "topic": "quantum computing", "templateHint": null}
- "What are the latest AI models?" -> {"isMatch": false, "slideCount": null, "topic": null, "templateHint": null}
- "Make a business pitch deck" -> {"isMatch": true, "slideCount": null, "topic": null, "templateHint": "business-pitch"}"""

        user_prompt = f"User message: \"{message}\"\n\nIs this requesting presentation generation? Return JSON only."

        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])

        content = response.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        result = json.loads(content)

        logger.info(f"[PresentationIntent] Message: {message[:50]}... -> Match: {result.get('isMatch')}")

        return result

    except Exception as e:
        logger.error(f"Intent detection failed: {str(e)}")
        return {"isMatch": False}


@router.get("/templates")
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """List available presentation templates"""
    try:
        if category:
            query = """
                SELECT * FROM presentation_templates
                WHERE category = ? AND is_active = 1
                ORDER BY name
            """
            async with db.execute(query, (category,)) as cursor:
                rows = await cursor.fetchall()
        else:
            query = """
                SELECT * FROM presentation_templates
                WHERE is_active = 1
                ORDER BY category, name
            """
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()

        templates = [PresentationTemplate.from_db(dict(row)).to_dict() for row in rows]

        return {
            "templates": templates,
            "count": len(templates)
        }

    except Exception as e:
        logger.error(f"Failed to list templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Get a specific template"""
    try:
        query = "SELECT * FROM presentation_templates WHERE id = ?"
        async with db.execute(query, (template_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Template not found")

        template = PresentationTemplate.from_db(dict(row))

        return template.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_presentation(
    request: CreatePresentationRequest,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Create a new presentation record"""
    try:
        import uuid
        from datetime import datetime

        presentation = Presentation(
            id=str(uuid.uuid4()),
            notebook_id=request.notebook_id,
            template_id=request.template_id,
            title=request.title,
            description=request.description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        pres_dict = presentation.to_dict()
        columns = ", ".join(pres_dict.keys())
        placeholders = ", ".join("?" * len(pres_dict))

        query = f"""
            INSERT INTO presentations ({columns})
            VALUES ({placeholders})
        """
        await db.execute(query, tuple(pres_dict.values()))
        await db.commit()

        return {
            "success": True,
            "presentation_id": presentation.id,
            "presentation": presentation.to_dict()
        }

    except Exception as e:
        logger.error(f"Failed to create presentation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{presentation_id}")
async def get_presentation(
    presentation_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Get presentation metadata"""
    try:
        query = "SELECT * FROM presentations WHERE id = ?"
        async with db.execute(query, (presentation_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Presentation not found")

        presentation = Presentation.from_db(dict(row))

        # Get slide count
        count_query = """
            SELECT COUNT(*) as count FROM presentation_content
            WHERE presentation_id = ?
        """
        async with db.execute(count_query, (presentation_id,)) as cursor:
            count_row = await cursor.fetchone()
            slide_count = count_row["count"]

        return {
            **presentation.to_dict(),
            "slide_count": slide_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get presentation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{presentation_id}")
async def delete_presentation(
    presentation_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Delete a presentation and all its slides"""
    try:
        # Delete slides (cascade will handle this, but explicit is clear)
        await db.execute(
            "DELETE FROM presentation_content WHERE presentation_id = ?",
            (presentation_id,)
        )

        # Delete versions
        await db.execute(
            "DELETE FROM presentation_versions WHERE presentation_id = ?",
            (presentation_id,)
        )

        # Delete source links
        await db.execute(
            "DELETE FROM presentation_sources WHERE presentation_id = ?",
            (presentation_id,)
        )

        # Delete presentation
        await db.execute(
            "DELETE FROM presentations WHERE id = ?",
            (presentation_id,)
        )

        await db.commit()

        return {"success": True, "message": "Presentation deleted"}

    except Exception as e:
        logger.error(f"Failed to delete presentation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{presentation_id}/versions")
async def list_versions(
    presentation_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """List all versions of a presentation"""
    try:
        query = """
            SELECT * FROM presentation_versions
            WHERE presentation_id = ?
            ORDER BY version_number DESC
        """
        async with db.execute(query, (presentation_id,)) as cursor:
            rows = await cursor.fetchall()

        versions = [PresentationVersion.from_db(dict(row)).to_dict() for row in rows]

        return {
            "presentation_id": presentation_id,
            "versions": versions,
            "count": len(versions)
        }

    except Exception as e:
        logger.error(f"Failed to list versions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
