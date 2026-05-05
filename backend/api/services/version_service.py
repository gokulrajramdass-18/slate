"""
Version Management Service

Centralizes version creation and management logic for microsites.
Handles version snapshots on publish, unpublished changes detection,
and HTML/CSS building from content sections.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from open_notebook.database.repository import repo_query, repo_execute


class VersionService:
    """Service for managing microsite versions."""

    async def create_publish_version(
        self,
        microsite_id: str,
        created_by: str = "system",
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new version snapshot when publishing.

        Gets current content sections, auto-increments the version number,
        builds full HTML and CSS, creates a content snapshot, and stores
        the version in the microsite_versions table.

        Args:
            microsite_id: ID of the microsite to version
            created_by: User ID or identifier of the publisher
            message: Optional version message describing the changes

        Returns:
            The created version record as a dict

        Raises:
            ValueError: If the microsite is not found
        """
        # Get microsite details
        microsite_results = await repo_query(
            "SELECT * FROM microsites WHERE id = :id",
            {"id": microsite_id},
        )
        if not microsite_results:
            raise ValueError(f"Microsite {microsite_id} not found")

        microsite = microsite_results[0]

        # Get current content sections
        content_sections = await repo_query(
            "SELECT * FROM microsite_content WHERE microsite_id = :mid ORDER BY order_num ASC",
            {"mid": microsite_id},
        )

        # Get next version number (sequential per microsite)
        existing_versions = await repo_query(
            "SELECT MAX(version_number) as max_version FROM microsite_versions WHERE microsite_id = :mid",
            {"mid": microsite_id},
        )
        current_max = (
            existing_versions[0]["max_version"]
            if existing_versions and existing_versions[0]["max_version"]
            else 0
        )
        next_version = current_max + 1

        # Build full HTML and CSS
        full_html = await self._build_full_html(microsite, content_sections)
        full_css = await self._build_full_css(microsite)

        # Create content snapshot
        content_snapshot = {
            "sections": [
                {
                    "section_id": section.get("section_id", ""),
                    "content_html": section.get("content_html"),
                    "content_json": section.get("content_json"),
                    "order_num": section.get("order_num", 0),
                    "is_visible": bool(section.get("is_visible", True)),
                }
                for section in content_sections
            ]
        }

        # Store version record
        now = datetime.utcnow().isoformat()
        version_id = str(uuid.uuid4())

        version_data = {
            "id": version_id,
            "mid": microsite_id,
            "version_number": next_version,
            "full_html": full_html,
            "full_css": full_css,
            "content_snapshot": json.dumps(content_snapshot),
            "created_by": created_by,
            "status_at_publish": "published",
            "published_at": now,
            "created": now,
        }

        # Include message in content_snapshot metadata if provided
        if message:
            content_snapshot["message"] = message
            version_data["content_snapshot"] = json.dumps(content_snapshot)

        await repo_execute(
            """INSERT INTO microsite_versions
               (id, microsite_id, version_number, full_html, full_css,
                content_snapshot, created_by, created)
               VALUES (:id, :mid, :version_number, :full_html, :full_css,
                       :content_snapshot, :created_by, :created)""",
            version_data,
        )

        # Update published_version on the microsite record
        await repo_execute(
            "UPDATE microsites SET published_version = :v, updated = :updated WHERE id = :id",
            {"v": next_version, "updated": now, "id": microsite_id},
        )

        # Fetch and return the created version
        version_results = await repo_query(
            "SELECT * FROM microsite_versions WHERE id = :id",
            {"id": version_id},
        )

        return version_results[0] if version_results else {
            "id": version_id,
            "microsite_id": microsite_id,
            "version_number": next_version,
            "published_at": now,
            "created": now,
            "created_by": created_by,
        }

    async def has_unpublished_changes(self, microsite_id: str) -> bool:
        """
        Check if there are content changes since the last published version.

        Compares the current content sections against the content snapshot
        stored in the most recent version. Returns True if they differ or
        if no published version exists.

        Args:
            microsite_id: ID of the microsite to check

        Returns:
            True if current content differs from the active/latest version
        """
        # Get the microsite to find active_version_id or latest version
        microsite_results = await repo_query(
            "SELECT active_version_id, published_version FROM microsites WHERE id = :id",
            {"id": microsite_id},
        )
        if not microsite_results:
            return True  # No microsite = treat as having changes

        microsite = microsite_results[0]
        active_version_id = microsite.get("active_version_id")

        # Get the version to compare against
        if active_version_id:
            version_results = await repo_query(
                "SELECT content_snapshot FROM microsite_versions WHERE id = :id",
                {"id": active_version_id},
            )
        else:
            # Fall back to latest version by version_number
            version_results = await repo_query(
                "SELECT content_snapshot FROM microsite_versions WHERE microsite_id = :mid ORDER BY version_number DESC LIMIT 1",
                {"mid": microsite_id},
            )

        if not version_results or not version_results[0].get("content_snapshot"):
            return True  # No version snapshot to compare against

        # Parse the stored snapshot
        try:
            stored_snapshot = json.loads(version_results[0]["content_snapshot"])
        except (json.JSONDecodeError, TypeError):
            return True  # Invalid snapshot = treat as changed

        stored_sections = stored_snapshot.get("sections", [])

        # Get current content sections
        current_content = await repo_query(
            """SELECT section_id, content_html, content_json, order_num, is_visible
               FROM microsite_content
               WHERE microsite_id = :mid
               ORDER BY order_num ASC""",
            {"mid": microsite_id},
        )

        # Build comparable snapshot from current content
        current_sections = [
            {
                "section_id": s.get("section_id", ""),
                "content_html": s.get("content_html"),
                "content_json": s.get("content_json"),
                "order_num": s.get("order_num", 0),
                "is_visible": bool(s.get("is_visible", True)),
            }
            for s in current_content
        ]

        return stored_sections != current_sections

    async def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single version by ID."""
        results = await repo_query(
            "SELECT * FROM microsite_versions WHERE id = :id",
            {"id": version_id},
        )
        return results[0] if results else None

    async def get_latest_version(self, microsite_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the latest version for a microsite."""
        results = await repo_query(
            "SELECT * FROM microsite_versions WHERE microsite_id = :mid ORDER BY version_number DESC LIMIT 1",
            {"mid": microsite_id},
        )
        return results[0] if results else None

    async def _build_full_html(
        self, microsite: Dict[str, Any], content_sections: List[Dict[str, Any]]
    ) -> str:
        """
        Build complete HTML document from microsite data and content sections.

        Reuses the MicrositeGenerationService's _render_full_html method
        to ensure consistent rendering across generation and versioning.

        Args:
            microsite: Microsite record dict
            content_sections: List of content section records

        Returns:
            Complete HTML document string
        """
        template_id = microsite.get("template_id")
        custom_css = microsite.get("custom_css", "")
        site_title = microsite.get("title", "Microsite")

        # Parse generation_config for site settings
        generation_config_str = microsite.get("generation_config") or "{}"
        try:
            generation_config = (
                json.loads(generation_config_str)
                if isinstance(generation_config_str, str)
                else generation_config_str
            ) or {}
        except (json.JSONDecodeError, TypeError):
            generation_config = {}

        # Use site_title from generation_config if available
        if generation_config.get("site_title"):
            site_title = generation_config["site_title"]

        # Extract navigation, footer, and logo settings
        nav_items = generation_config.get("nav_items") or [
            {"label": "Home", "url": "#home"},
            {"label": "About", "url": "#about"},
            {"label": "Content", "url": "#content"},
            {"label": "Contact", "url": "#contact"},
        ]
        footer_text = generation_config.get("footer_text") or None
        logo_url = generation_config.get("logo_url") or None

        # Get template styles
        if template_id:
            template_results = await repo_query(
                "SELECT * FROM microsite_templates WHERE id = :id",
                {"id": template_id},
            )
        else:
            template_results = []

        if not template_results:
            # Use minimal defaults if no template found
            template = {"name": "default", "display_name": "Default", "default_styles": "{}"}
        else:
            template = template_results[0]

        # Parse template styles
        try:
            styles = json.loads(template.get("default_styles") or "{}")
        except (json.JSONDecodeError, TypeError):
            styles = {}

        # Override with user-customized primary color
        if generation_config.get("primary_color"):
            styles["primary_color"] = generation_config["primary_color"]

        # Include custom CSS
        styles["css"] = custom_css or ""

        # Format sections for _render_full_html
        formatted_sections = [
            {
                "section_id": s.get("section_id", ""),
                "section_type": s.get("section_id", "text").replace("_", "-"),
                "content_html": s.get("content_html", ""),
                "order_num": s.get("order_num", 0),
                "is_visible": s.get("is_visible", True),
            }
            for s in content_sections
            if s.get("is_visible", True)
        ]

        # Use the generation service's renderer for consistent output
        from api.services.microsite_generation_service import MicrositeGenerationService

        gen_service = MicrositeGenerationService()
        full_html = gen_service._render_full_html(
            sections=formatted_sections,
            styles=styles,
            template=template,
            logo_url=logo_url,
            site_title=site_title,
            nav_items=nav_items,
            footer_text=footer_text,
        )

        return full_html

    async def _build_full_css(self, microsite: Dict[str, Any]) -> str:
        """
        Build complete CSS from template defaults and custom CSS.

        Args:
            microsite: Microsite record dict

        Returns:
            Combined CSS string (template defaults + custom overrides)
        """
        template_id = microsite.get("template_id")
        custom_css = microsite.get("custom_css", "") or ""

        # Get template default styles
        template_css = ""
        if template_id:
            template_results = await repo_query(
                "SELECT default_styles FROM microsite_templates WHERE id = :id",
                {"id": template_id},
            )
            if template_results:
                try:
                    styles = json.loads(template_results[0].get("default_styles") or "{}")
                    template_css = styles.get("css", "")
                except (json.JSONDecodeError, TypeError):
                    template_css = ""

        # Combine template CSS + custom CSS
        parts = []
        if template_css:
            parts.append(f"/* Template Styles */\n{template_css}")
        if custom_css:
            parts.append(f"/* Custom Styles */\n{custom_css}")

        return "\n\n".join(parts) if parts else ""


# Singleton instance
_version_service: Optional[VersionService] = None


def get_version_service() -> VersionService:
    """Get or create the version service singleton."""
    global _version_service
    if _version_service is None:
        _version_service = VersionService()
    return _version_service


# Convenience singleton
version_service = VersionService()
