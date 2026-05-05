"""
Template Folder Management Service.

Manages folder structure for template execution results within workspaces.
Creates hierarchical structure: /Template Executions/{Template Name}/
"""

import json
from datetime import datetime
from typing import Optional

from open_notebook.domain.folder import Folder


class TemplateFolderService:
    """Manages folder structure for template executions."""

    async def get_or_create_template_folder(
        self,
        workspace_id: str,
        template_id: str,
        template_name: str,
        execution_id: Optional[str] = None,
        execution_timestamp: Optional[datetime] = None
    ) -> str:
        """
        Get or create folder for template executions.

        Creates hierarchical structure:
        1. Root "Template Executions" folder (if doesn't exist)
        2. Template-specific subfolder
        3. Execution-specific subfolder (if execution_id provided)

        Args:
            workspace_id: Target workspace ID
            template_id: Template ID
            template_name: Template name for folder
            execution_id: Optional execution ID for unique folder
            execution_timestamp: Optional timestamp for folder name

        Returns:
            folder_id where notes should be stored
        """
        # 1. Get or create root "Template Executions" folder
        root_folder = await Folder.get_by_name_and_workspace(
            name="Template Executions",
            workspace_id=workspace_id
        )

        if not root_folder:
            root_folder = Folder(
                name="Template Executions",
                notebook_id=workspace_id,
                folder_type="system",
                metadata=json.dumps({
                    "description": "Auto-generated template execution results"
                })
            )
            await root_folder.save()

        # 2. Get or create template-specific folder
        template_folder = await Folder.get_by_name_and_parent(
            name=template_name,
            parent_id=root_folder.id
        )

        if not template_folder:
            template_folder = Folder(
                name=template_name,
                notebook_id=workspace_id,
                parent_id=root_folder.id,
                folder_type="template_executions",
                metadata=json.dumps({
                    "template_id": template_id,
                    "execution_count": 0
                })
            )
            await template_folder.save()

        # 3. Create execution-specific folder if execution_id provided
        if execution_id:
            # Format: "Execution {short_id} - {timestamp}"
            short_id = execution_id[:8]  # First 8 chars of UUID
            timestamp_str = execution_timestamp.strftime("%b %d, %Y %I:%M %p") if execution_timestamp else datetime.utcnow().strftime("%b %d, %Y %I:%M %p")
            execution_folder_name = f"Execution {short_id} - {timestamp_str}"

            # Check if execution folder already exists
            existing_execution_folder = await Folder.get_by_name_and_parent(
                name=execution_folder_name,
                parent_id=template_folder.id
            )

            if not existing_execution_folder:
                execution_folder = Folder(
                    name=execution_folder_name,
                    notebook_id=workspace_id,
                    parent_id=template_folder.id,
                    folder_type="execution_results",
                    metadata=json.dumps({
                        "execution_id": execution_id,
                        "template_id": template_id,
                        "template_name": template_name,
                        "timestamp": execution_timestamp.isoformat() if execution_timestamp else datetime.utcnow().isoformat()
                    })
                )
                await execution_folder.save()
                return execution_folder.id
            else:
                return existing_execution_folder.id

        # If no execution_id, return template folder (old behavior)
        return template_folder.id

    async def increment_execution_count(self, folder_id: str) -> None:
        """
        Increment execution count in folder metadata.

        Args:
            folder_id: Folder ID to update
        """
        folder = await Folder.get(folder_id)
        if folder:
            metadata = folder.get_metadata()
            metadata["execution_count"] = metadata.get("execution_count", 0) + 1
            metadata["last_execution"] = datetime.utcnow().isoformat()
            folder.set_metadata(metadata)
            await folder.save()
