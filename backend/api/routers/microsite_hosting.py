"""
Public Microsite Hosting Router

Serves published microsites to the public. In development mode this router
is mounted inside the main API app. In production mode the standalone
hosting server (api/hosting_server.py) mounts it instead.

Endpoints:
  GET /public/{slug}          - Serve published microsite HTML
  GET /public/{slug}/metadata - Public metadata for SEO / link previews
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse

from open_notebook.database.repository import repo_query

router = APIRouter(prefix="/public", tags=["Microsite Hosting"])


# ============================================================================
# Public serving endpoints
# ============================================================================

@router.get("/{slug}", response_class=HTMLResponse)
async def serve_microsite(slug: str):
    """
    Serve a published microsite by its slug.

    Status behaviour:
      - **published** with active version  -> 200 with HTML
      - **draft**                           -> 404 (not yet published)
      - **blocked**                         -> 451 (Unavailable For Legal Reasons)
      - no active version                   -> 404
    """
    results = await repo_query(
        "SELECT * FROM microsites WHERE slug = :slug",
        {"slug": slug},
    )

    if not results:
        return HTMLResponse(
            content=_error_page("Microsite not found"),
            status_code=404,
        )

    microsite = results[0]
    ms_status = microsite.get("status", "draft")

    if ms_status == "draft":
        return HTMLResponse(
            content=_error_page(
                "This microsite is not yet published",
                "The creator is still working on this content.",
            ),
            status_code=404,
        )

    if ms_status == "blocked":
        return HTMLResponse(
            content=_error_page(
                "Content Unavailable",
                "This microsite has been blocked due to moderation policies.",
            ),
            status_code=451,
        )

    # Published - need active version
    active_version_id = microsite.get("active_version_id")
    if not active_version_id:
        return HTMLResponse(
            content=_error_page("No published version available"),
            status_code=404,
        )

    version_results = await repo_query(
        "SELECT full_html FROM microsite_versions WHERE id = :id",
        {"id": active_version_id},
    )

    if not version_results or not version_results[0].get("full_html"):
        return HTMLResponse(
            content=_error_page("Version not found"),
            status_code=500,
        )

    return HTMLResponse(
        content=version_results[0]["full_html"],
        headers={
            "Cache-Control": "public, max-age=300",
            "X-Frame-Options": "SAMEORIGIN",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{slug}/metadata", response_class=JSONResponse)
async def get_microsite_metadata(slug: str):
    """
    Get public metadata for a published microsite.

    Useful for SEO crawlers, social-media link previews, and embed cards.
    """
    results = await repo_query(
        "SELECT title, description, theme, created, updated "
        "FROM microsites WHERE slug = :slug AND status = 'published'",
        {"slug": slug},
    )

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microsite not found or not published",
        )

    row = results[0]
    return {
        "title": row.get("title"),
        "description": row.get("description"),
        "theme": row.get("theme"),
        "created": row.get("created"),
        "updated": row.get("updated"),
    }


# ============================================================================
# Error page helper
# ============================================================================

def _error_page(title: str, message: str = "") -> str:
    """Generate a styled error page HTML document."""
    message_html = f"<p>{message}</p>" if message else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 2rem;
        }}
        .error-container {{
            max-width: 600px;
        }}
        h1 {{
            font-size: 3rem;
            margin-bottom: 1rem;
        }}
        p {{
            font-size: 1.25rem;
            opacity: 0.9;
        }}
    </style>
</head>
<body>
    <div class="error-container">
        <h1>{title}</h1>
        {message_html}
    </div>
</body>
</html>"""
