"""
Microsite Chat Agent Tools

Provides tools for AI agents to edit microsites through natural language.
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from open_notebook.database.repository import repo_query, repo_execute


class MicrositeEditorTools:
    """
    Tools for AI agents to edit microsite content through natural language.

    Supports operations like:
    - Update section content
    - Change colors/styles
    - Add/remove sections
    - Update header/footer
    - Change logo
    """

    @staticmethod
    async def get_microsite_info(microsite_id: str) -> Dict[str, Any]:
        """
        Get current microsite information including all sections.

        Returns structure and content for the AI to understand what it's editing.
        """
        # Get microsite metadata
        microsite_results = await repo_query(
            "SELECT * FROM microsites WHERE id = :id",
            {"id": microsite_id}
        )
        if not microsite_results:
            raise ValueError(f"Microsite {microsite_id} not found")

        microsite = microsite_results[0]

        # Get all content sections
        sections_results = await repo_query(
            "SELECT * FROM microsite_content WHERE microsite_id = :mid ORDER BY order_num ASC",
            {"mid": microsite_id}
        )

        # Parse generation config
        generation_config = {}
        if microsite.get("generation_config"):
            try:
                generation_config = json.loads(microsite["generation_config"])
            except:
                pass

        return {
            "id": microsite["id"],
            "title": microsite["title"],
            "description": microsite.get("description"),
            "theme": microsite.get("theme", "light"),
            "template_id": microsite.get("template_id"),
            "logo_url": generation_config.get("logo_url"),
            "custom_css": microsite.get("custom_css"),
            "sections": [
                {
                    "id": s["id"],
                    "section_id": s["section_id"],
                    "section_type": s.get("section_type", "text"),
                    "order_num": s["order_num"],
                    "content_html": s.get("content_html", ""),
                    "is_visible": bool(s.get("is_visible", True))
                }
                for s in sections_results
            ]
        }

    @staticmethod
    async def update_section_content(
        microsite_id: str,
        section_id: str,
        new_content_html: str
    ) -> Dict[str, str]:
        """
        Update the HTML content of a specific section.

        Args:
            microsite_id: Microsite ID
            section_id: Section identifier (e.g., "hero", "summary", "features")
            new_content_html: New HTML content

        Returns:
            Success message
        """
        now = datetime.utcnow().isoformat()

        # Find section by section_id (not database id)
        section_results = await repo_query(
            "SELECT id FROM microsite_content WHERE microsite_id = :mid AND section_id = :sid",
            {"mid": microsite_id, "sid": section_id}
        )

        if not section_results:
            raise ValueError(f"Section '{section_id}' not found in microsite")

        db_id = section_results[0]["id"]

        # Update content
        await repo_execute(
            "UPDATE microsite_content SET content_html = :html, updated = :updated WHERE id = :id",
            {"html": new_content_html, "updated": now, "id": db_id}
        )

        # Regenerate HTML with updated content
        await MicrositeEditorTools._regenerate_html(microsite_id)

        return {
            "status": "success",
            "message": f"Updated section '{section_id}' successfully"
        }

    @staticmethod
    async def update_microsite_styles(
        microsite_id: str,
        primary_color: Optional[str] = None,
        logo_url: Optional[str] = None,
        custom_css: Optional[str] = None,
        nav_items: Optional[List[Dict[str, str]]] = None,
        footer_text: Optional[str] = None,
        site_title: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Update microsite styling (colors, logo, custom CSS, navigation, footer).

        Args:
            microsite_id: Microsite ID
            primary_color: Primary color hex code (e.g., "#0066cc")
            logo_url: URL to logo image
            custom_css: Additional custom CSS
            nav_items: List of navigation items [{"label": "Home", "url": "#home"}, ...]
            footer_text: Custom footer text
            site_title: Site title

        Returns:
            Success message
        """
        now = datetime.utcnow().isoformat()

        # Get current generation_config
        config_results = await repo_query(
            "SELECT generation_config, template_id FROM microsites WHERE id = :id",
            {"id": microsite_id}
        )

        if not config_results:
            raise ValueError(f"Microsite {microsite_id} not found")

        current_config = {}
        if config_results[0].get("generation_config"):
            try:
                current_config = json.loads(config_results[0]["generation_config"])
            except:
                pass

        # Update config
        if logo_url is not None:
            current_config["logo_url"] = logo_url
        if primary_color is not None:
            current_config["primary_color"] = primary_color
        if nav_items is not None:
            current_config["nav_items"] = nav_items
        if footer_text is not None:
            current_config["footer_text"] = footer_text

        # Build update query
        update_fields = {
            "updated": now,
            "generation_config": json.dumps(current_config),
            "id": microsite_id
        }

        if custom_css is not None:
            update_fields["custom_css"] = custom_css

        if site_title is not None:
            update_fields["title"] = site_title

        set_clauses = ", ".join([f"{k} = :{k}" for k in update_fields if k != "id"])

        await repo_execute(
            f"UPDATE microsites SET {set_clauses} WHERE id = :id",
            update_fields
        )

        # Regenerate HTML with new styles
        await MicrositeEditorTools._regenerate_html(microsite_id)

        return {
            "status": "success",
            "message": "Updated microsite styles successfully"
        }

    @staticmethod
    async def _regenerate_html(microsite_id: str) -> None:
        """
        Regenerate the HTML version snapshot after content/style changes.
        """
        from api.services.microsite_generation_service import MicrositeGenerationService

        # Get microsite data
        microsite_results = await repo_query(
            "SELECT * FROM microsites WHERE id = :id",
            {"id": microsite_id}
        )
        if not microsite_results:
            return

        microsite = microsite_results[0]

        # Get all sections
        sections_results = await repo_query(
            "SELECT * FROM microsite_content WHERE microsite_id = :mid ORDER BY order_num ASC",
            {"mid": microsite_id}
        )

        # Get template
        template_id = microsite.get("template_id")
        template_results = await repo_query(
            "SELECT * FROM microsite_templates WHERE id = :id",
            {"id": template_id}
        ) if template_id else []

        if not template_results:
            return

        template = template_results[0]

        # Parse template structure and styles
        structure = {}
        styles = {}
        try:
            if template.get("structure"):
                structure = json.loads(template["structure"])
            if template.get("default_styles"):
                styles = json.loads(template["default_styles"])
        except:
            pass

        # Parse generation config for logo and colors
        generation_config = {}
        if microsite.get("generation_config"):
            try:
                generation_config = json.loads(microsite["generation_config"])
            except:
                pass

        # Override styles with generation config
        if generation_config.get("primary_color"):
            styles["primary_color"] = generation_config["primary_color"]

        # Get navigation items and footer text from generation config
        nav_items = generation_config.get("nav_items")
        footer_text = generation_config.get("footer_text")

        # Create sections list for rendering
        sections_list = []
        for section in sections_results:
            sections_list.append({
                "id": section["id"],
                "section_id": section["section_id"],
                "section_type": section.get("section_type", "text"),
                "order_num": section["order_num"],
                "content_html": section.get("content_html", ""),
                "is_visible": bool(section.get("is_visible", True))
            })

        # Render full HTML
        gen_service = MicrositeGenerationService()
        full_html = gen_service._render_full_html(
            sections=sections_list,
            styles=styles,
            template=structure,
            logo_url=generation_config.get("logo_url"),
            site_title=microsite.get("title", "Microsite"),
            nav_items=nav_items,
            footer_text=footer_text
        )

        # Get current version number
        version_results = await repo_query(
            "SELECT MAX(version_number) as max_version FROM microsite_versions WHERE microsite_id = :mid",
            {"mid": microsite_id}
        )
        current_version = version_results[0].get("max_version", 0) if version_results else 0
        new_version = current_version + 1

        # Create new version snapshot
        from open_notebook.database.repository import repo_create
        await repo_create(
            "microsite_versions",
            {
                "microsite_id": microsite_id,
                "version_number": new_version,
                "full_html": full_html,
                "created": datetime.utcnow().isoformat()
            }
        )

    @staticmethod
    async def reorder_sections(
        microsite_id: str,
        section_order: List[str]
    ) -> Dict[str, str]:
        """
        Reorder sections by providing new order of section_ids.

        Args:
            microsite_id: Microsite ID
            section_order: List of section_ids in desired order

        Returns:
            Success message
        """
        now = datetime.utcnow().isoformat()

        for idx, section_id in enumerate(section_order):
            # Find section
            section_results = await repo_query(
                "SELECT id FROM microsite_content WHERE microsite_id = :mid AND section_id = :sid",
                {"mid": microsite_id, "sid": section_id}
            )

            if section_results:
                db_id = section_results[0]["id"]
                await repo_execute(
                    "UPDATE microsite_content SET order_num = :order, updated = :updated WHERE id = :id",
                    {"order": idx, "updated": now, "id": db_id}
                )

        return {
            "status": "success",
            "message": f"Reordered {len(section_order)} sections successfully"
        }

    @staticmethod
    async def toggle_section_visibility(
        microsite_id: str,
        section_id: str,
        visible: bool
    ) -> Dict[str, str]:
        """
        Show or hide a section.

        Args:
            microsite_id: Microsite ID
            section_id: Section identifier
            visible: True to show, False to hide

        Returns:
            Success message
        """
        now = datetime.utcnow().isoformat()

        # Find section
        section_results = await repo_query(
            "SELECT id FROM microsite_content WHERE microsite_id = :mid AND section_id = :sid",
            {"mid": microsite_id, "sid": section_id}
        )

        if not section_results:
            raise ValueError(f"Section '{section_id}' not found")

        db_id = section_results[0]["id"]

        await repo_execute(
            "UPDATE microsite_content SET is_visible = :visible, updated = :updated WHERE id = :id",
            {"visible": 1 if visible else 0, "updated": now, "id": db_id}
        )

        action = "shown" if visible else "hidden"
        return {
            "status": "success",
            "message": f"Section '{section_id}' {action} successfully"
        }

    @staticmethod
    def get_available_tools() -> List[Dict[str, Any]]:
        """
        Get tool definitions in OpenAI function calling format.

        Returns list of tool specs for AI agent to use.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_microsite_info",
                    "description": "Get current microsite structure and content. Use this first to understand what you're editing.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "microsite_id": {
                                "type": "string",
                                "description": "The microsite ID"
                            }
                        },
                        "required": ["microsite_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_section_content",
                    "description": "Update the HTML content of a specific section (hero, summary, features, etc.)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "microsite_id": {
                                "type": "string",
                                "description": "The microsite ID"
                            },
                            "section_id": {
                                "type": "string",
                                "description": "Section identifier (e.g., 'hero', 'summary', 'features')"
                            },
                            "new_content_html": {
                                "type": "string",
                                "description": "New HTML content for the section"
                            }
                        },
                        "required": ["microsite_id", "section_id", "new_content_html"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "update_microsite_styles",
                    "description": "Update microsite visual styling: colors, logo, custom CSS, navigation menu, footer text, or site title",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "microsite_id": {
                                "type": "string",
                                "description": "The microsite ID"
                            },
                            "primary_color": {
                                "type": "string",
                                "description": "Primary color hex code (e.g., '#0066cc')"
                            },
                            "logo_url": {
                                "type": "string",
                                "description": "URL to logo image"
                            },
                            "custom_css": {
                                "type": "string",
                                "description": "Additional custom CSS rules"
                            },
                            "nav_items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "label": {"type": "string", "description": "Navigation link label"},
                                        "url": {"type": "string", "description": "Navigation link URL or anchor"}
                                    },
                                    "required": ["label", "url"]
                                },
                                "description": "Navigation menu items"
                            },
                            "footer_text": {
                                "type": "string",
                                "description": "Custom footer text"
                            },
                            "site_title": {
                                "type": "string",
                                "description": "Site title shown in header and browser tab"
                            }
                        },
                        "required": ["microsite_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "reorder_sections",
                    "description": "Change the order of sections on the page",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "microsite_id": {
                                "type": "string",
                                "description": "The microsite ID"
                            },
                            "section_order": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Array of section_ids in desired order"
                            }
                        },
                        "required": ["microsite_id", "section_order"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "toggle_section_visibility",
                    "description": "Show or hide a section on the page",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "microsite_id": {
                                "type": "string",
                                "description": "The microsite ID"
                            },
                            "section_id": {
                                "type": "string",
                                "description": "Section identifier"
                            },
                            "visible": {
                                "type": "boolean",
                                "description": "true to show, false to hide"
                            }
                        },
                        "required": ["microsite_id", "section_id", "visible"]
                    }
                }
            }
        ]


# Tool executor for function calling
async def execute_microsite_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a microsite editing tool and return results."""
    tools = MicrositeEditorTools()

    try:
        if tool_name == "get_microsite_info":
            return await tools.get_microsite_info(**arguments)
        elif tool_name == "update_section_content":
            return await tools.update_section_content(**arguments)
        elif tool_name == "update_microsite_styles":
            return await tools.update_microsite_styles(**arguments)
        elif tool_name == "reorder_sections":
            return await tools.reorder_sections(**arguments)
        elif tool_name == "toggle_section_visibility":
            return await tools.toggle_section_visibility(**arguments)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    except Exception as e:
        return {"error": str(e)}
