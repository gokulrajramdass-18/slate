"""
Presentation Generator Node Executor

Workflow node for generating PowerPoint presentations.
Follows the pattern of MicrositeGeneratorNodeExecutor.
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from abc import ABC

from open_notebook.domain.workflow import NodeConfig

logger = logging.getLogger(__name__)


class PresentationGeneratorNodeExecutor:
    """
    Workflow node executor for PowerPoint presentation generation.

    Configuration:
    - template_id: Template ID to use (or template_id_var for dynamic)
    - source_ids: List of source IDs (or source_resolution_mode)
    - notebook_id: Workspace ID (or notebook_id_var)
    - user_prompt: Generation prompt (or prompt_var)
    - target_slide_count: Number of slides to generate (default: 10)
    - auto_download: Whether to include download URL in output (default: false)
    - output_var: Variable name to store presentation ID (default: "{node_id}_presentation_id")

    Source Resolution Modes:
    - "all_active": Use all active sources in notebook
    - "explicit": Use source_ids list
    - "from_var": Use source IDs from state variable

    Outputs to state:
    - {output_var}: Presentation ID
    - {node_id}_slide_count: Number of slides generated
    - {node_id}_preview_url: URL to HTML preview
    - {node_id}_download_url: URL to download PPTX
    """

    def __init__(self, config: NodeConfig):
        """Initialize executor with configuration"""
        self.config = config
        self.db = None  # Will be set by workflow engine

    async def execute(self, state: Dict[str, Any], node_id: str) -> Dict[str, Any]:
        """Execute presentation generation"""
        try:
            # Import here to avoid circular import
            from api.services.presentation_generation_service import PresentationGenerationService

            config = self.config

            # Resolve template
            template_id = await self._resolve_template(config, state)

            # Resolve sources
            source_ids = await self._resolve_sources(config, state)

            # Resolve notebook
            notebook_id = self._resolve_variable(
                config.get("notebook_id"),
                config.get("notebook_id_var"),
                state
            )

            # Resolve prompt
            prompt = self._resolve_variable(
                config.get("user_prompt"),
                config.get("prompt_var"),
                state
            )

            if not prompt:
                raise ValueError("user_prompt or prompt_var must be provided")

            # Get slide count
            target_slide_count = config.get("target_slide_count", 10)

            # Generate presentation ID
            presentation_id = str(uuid.uuid4())

            # Initialize service
            service = PresentationGenerationService(self.db)

            # Generate presentation
            logger.info(f"Generating presentation {presentation_id} with {target_slide_count} slides")

            result = await service.generate_presentation(
                presentation_id=presentation_id,
                template_id=template_id,
                source_ids=source_ids,
                notebook_id=notebook_id,
                user_prompt=prompt,
                target_slide_count=target_slide_count
            )

            logger.info(
                f"Successfully generated presentation {presentation_id} "
                f"with {result['slide_count']} slides"
            )

            # Determine output variable name
            output_var = config.get("output_var", f"{node_id}_presentation_id")

            # Update state
            state[output_var] = presentation_id
            state[f"{node_id}_slide_count"] = result["slide_count"]
            state[f"{node_id}_preview_url"] = f"/api/presentations/{presentation_id}/preview"
            state[f"{node_id}_download_url"] = f"/api/presentations/{presentation_id}/download"

            # Add metadata
            state[f"{node_id}_output"] = {
                "presentation_id": presentation_id,
                "slide_count": result["slide_count"],
                "template_id": template_id,
                "prompt": prompt,
                "preview_url": f"/api/presentations/{presentation_id}/preview",
                "download_url": f"/api/presentations/{presentation_id}/download",
            }

            return state

        except Exception as e:
            logger.error(f"Presentation generation failed: {str(e)}")
            raise

    async def _resolve_template(self, config: Dict[str, Any], state: Dict[str, Any]) -> str:
        """Resolve template ID from config or state"""
        template_id = config.get("template_id")
        template_id_var = config.get("template_id_var")

        if template_id:
            return template_id
        elif template_id_var and template_id_var in state:
            return state[template_id_var]
        else:
            # Default to business pitch
            return "business-pitch"

    async def _resolve_sources(self, config: Dict[str, Any], state: Dict[str, Any]) -> List[str]:
        """Resolve source IDs based on resolution mode"""
        mode = config.get("source_resolution_mode", "explicit")

        if mode == "explicit":
            # Use explicit source_ids list
            return config.get("source_ids", [])

        elif mode == "from_var":
            # Get from state variable
            var_name = config.get("source_ids_var")
            if var_name and var_name in state:
                sources = state[var_name]
                if isinstance(sources, list):
                    return sources
                return []
            return []

        elif mode == "all_active":
            # Fetch all active sources from notebook
            notebook_id = config.get("notebook_id")
            if not notebook_id:
                return []

            query = """
                SELECT id FROM sources
                WHERE notebook_id = ? AND is_active = 1
            """
            async with self.db.execute(query, (notebook_id,)) as cursor:
                rows = await cursor.fetchall()
                return [row["id"] for row in rows]

        return []

    def _resolve_variable(
        self,
        direct_value: Optional[Any],
        var_name: Optional[str],
        state: Dict[str, Any]
    ) -> Optional[Any]:
        """Resolve value from direct config or state variable"""
        if direct_value is not None:
            return direct_value
        elif var_name and var_name in state:
            return state[var_name]
        return None

    def get_input_schema(self) -> Dict[str, Any]:
        """Get JSON schema for node configuration"""
        return {
            "type": "object",
            "properties": {
                "template_id": {
                    "type": "string",
                    "title": "Template ID",
                    "description": "Presentation template to use",
                    "enum": [
                        "business-pitch",
                        "academic-report",
                        "sales-deck",
                        "marketing-campaign",
                        "quarterly-report",
                        "startup-pitch",
                        "minimalist-dark",
                        "creative-portfolio",
                    ],
                },
                "template_id_var": {
                    "type": "string",
                    "title": "Template ID Variable",
                    "description": "State variable containing template ID",
                },
                "source_resolution_mode": {
                    "type": "string",
                    "title": "Source Resolution Mode",
                    "enum": ["explicit", "all_active", "from_var"],
                    "default": "explicit",
                },
                "source_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "Source IDs",
                    "description": "List of source IDs to include",
                },
                "source_ids_var": {
                    "type": "string",
                    "title": "Source IDs Variable",
                    "description": "State variable containing source IDs",
                },
                "notebook_id": {
                    "type": "string",
                    "title": "Notebook ID",
                    "description": "Workspace ID",
                },
                "notebook_id_var": {
                    "type": "string",
                    "title": "Notebook ID Variable",
                    "description": "State variable containing notebook ID",
                },
                "user_prompt": {
                    "type": "string",
                    "title": "Generation Prompt",
                    "description": "What the presentation should be about",
                },
                "prompt_var": {
                    "type": "string",
                    "title": "Prompt Variable",
                    "description": "State variable containing prompt",
                },
                "target_slide_count": {
                    "type": "integer",
                    "title": "Number of Slides",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
                "output_var": {
                    "type": "string",
                    "title": "Output Variable",
                    "description": "Variable name to store presentation ID",
                },
            },
            "required": [],
        }

    def get_output_schema(self) -> Dict[str, Any]:
        """Get JSON schema for node outputs"""
        return {
            "type": "object",
            "properties": {
                "{node_id}_presentation_id": {
                    "type": "string",
                    "description": "Generated presentation ID",
                },
                "{node_id}_slide_count": {
                    "type": "integer",
                    "description": "Number of slides generated",
                },
                "{node_id}_preview_url": {
                    "type": "string",
                    "description": "URL to HTML preview",
                },
                "{node_id}_download_url": {
                    "type": "string",
                    "description": "URL to download PPTX",
                },
            },
        }
