"""
Template Execution Service.

Executes templates and stores results in organized folder structures.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from open_notebook.domain.notebook import Note
from open_notebook.domain.template_execution import TemplateExecution
from open_notebook.domain.workspace_template import WorkspaceTemplate
from open_notebook.agents.autonomous_orchestrator import AutonomousOrchestrator
from api.services.template_folder_service import TemplateFolderService

logger = logging.getLogger(__name__)


class TemplateExecutionService:
    """Service for executing templates and storing results."""

    def __init__(self):
        self.folder_service = TemplateFolderService()

    async def execute_template(
        self,
        template_id: str,
        parameters: Dict[str, Any],
        user_id: str,
        target_workspace_id: Optional[str] = None
    ) -> Dict:
        """
        Execute template and store results in workspace folder.

        Args:
            template_id: Template to execute
            parameters: Runtime parameter values
            user_id: User executing template
            target_workspace_id: Where to store results (default: source workspace)

        Returns:
            {
                "execution_id": str,
                "result_note_id": str,
                "folder_id": str,
                "target_workspace_id": str,
                "note_title": str
            }

        Raises:
            ValueError: If template not found or validation fails
        """
        execution = None  # Track execution for cleanup on error

        # 0. Check if LLM is configured in settings
        from api.services.settings import get_setting

        language_model_id = await get_setting("language_model_id", "")
        if not language_model_id:
            raise ValueError(
                "Cannot execute template: No language model configured. "
                "Please select a model in Settings → Models before executing templates."
            )

        # 1. Load template
        template = await WorkspaceTemplate.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # 2. Determine target workspace
        if not target_workspace_id:
            target_workspace_id = template.source_workspace_id

        if not target_workspace_id:
            raise ValueError(
                f"Cannot execute template '{template.name}': No source workspace is linked to this template. "
                f"This template may have been created before the source workspace feature was added. "
                f"Please recreate the template from a workspace or contact support."
            )

        # 3. Validate parameters
        validation = template.validate_parameters(parameters)
        if not validation["valid"]:
            raise ValueError(f"Parameter validation failed: {', '.join(validation['errors'])}")

        # 4. Verify workspace exists before proceeding
        from open_notebook.domain.notebook import Notebook
        workspace = await Notebook.get(target_workspace_id)
        if not workspace:
            raise ValueError(f"Target workspace {target_workspace_id} not found")

        # CRITICAL: Protect the workspace from deletion during execution
        logger.info(f"🛡️  PROTECTING workspace {workspace.name} (ID: {workspace.id}) from deletion")
        workspace.protected = True
        await workspace.save()

        # 5. Create execution record FIRST to get execution ID
        execution = TemplateExecution(
            user_id=user_id,
            template_id=template_id,
            target_workspace_id=target_workspace_id,
            folder_id=None,  # Will be set after folder creation
            parameters=json.dumps(parameters),
            status='running',
            started_at=datetime.utcnow()
        )
        try:
            await execution.save()
            logger.info(f"Created execution record {execution.id}")
        except Exception as e:
            logger.error(f"Failed to create execution record: {e}")
            raise ValueError(f"Failed to create execution record: {str(e)}")

        # 6. Get or create folder with execution ID
        try:
            folder_id = await self.folder_service.get_or_create_template_folder(
                workspace_id=target_workspace_id,
                template_id=template_id,
                template_name=template.name,
                execution_id=execution.id,
                execution_timestamp=execution.started_at
            )
            logger.info(f"Created/found folder {folder_id} for execution {execution.id}")

            # Update execution with folder_id
            execution.folder_id = folder_id
            await execution.save()

            # Update workspace plan with execution_folder_id (if plan exists)
            from open_notebook.database.repository import repo_execute
            await repo_execute(
                "UPDATE workspace_plans SET execution_folder_id = :folder_id WHERE workspace_id = :workspace_id",
                {"folder_id": folder_id, "workspace_id": target_workspace_id}
            )
            logger.info(f"Updated workspace plan with execution folder {folder_id}")
        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            raise ValueError(f"Failed to create results folder: {str(e)}")

        try:
            # 7. Execute phases with configured model
            from api.routers.chat import get_model_credential
            from api.services.llm_client import build_langchain_chat_model

            # Get credential for the configured model
            credential = get_model_credential(language_model_id)
            if not credential:
                raise ValueError(f"Credential not found for model {language_model_id}")

            # Build LangChain chat model with provider-aware routing
            # (handles SAP AI Core deployment_id + Docker host.docker.internal)
            llm = build_langchain_chat_model(credential, temperature=0)

            # Execute with configured model
            orchestrator = AutonomousOrchestrator(llm=llm)
            result = await orchestrator.execute_template_phases(
                phases=template.get_phases(),
                workspace_id=target_workspace_id,
                user_id=user_id,
                parameters=parameters,
                template=template,
                execution_folder_id=folder_id  # Pass execution folder for result organization
            )

            # 8. Create note in folder
            note_title = self._build_note_title(template.name, parameters, execution.id)

            note = Note(
                notebook_id=target_workspace_id,
                folder_id=folder_id,
                title=note_title,
                content=result.get("summary", ""),
                content_html=result.get("summary_html", ""),
                metadata=json.dumps({
                    "template_id": template_id,
                    "execution_id": execution.id,
                    "parameters": parameters,
                    "execution_date": datetime.utcnow().isoformat()
                })
            )
            await note.save()

            # Link note to notebook via junction table
            from open_notebook.domain.notebook import Notebook
            notebook = await Notebook.get(target_workspace_id)
            if notebook:
                await notebook.add_note(note.id)
                logger.info(f"Linked note {note.id} to notebook {target_workspace_id}")

            # 9. Update execution record
            execution.status = 'completed'
            execution.result_note_id = note.id
            execution.completed_at = datetime.utcnow()
            execution.duration_ms = int((execution.completed_at - execution.started_at).total_seconds() * 1000)
            await execution.save()

            # 10. Update folder metadata
            await self.folder_service.increment_execution_count(folder_id)

            # 11. Increment template usage count
            await template.increment_usage()

            # CRITICAL: Unprotect the workspace after successful execution
            logger.info(f"✅ UNPROTECTING workspace {workspace.name} (ID: {workspace.id})")
            workspace.protected = False
            await workspace.save()

            return {
                "execution_id": execution.id,
                "result_note_id": note.id,
                "folder_id": folder_id,
                "target_workspace_id": target_workspace_id,
                "note_title": note_title
            }

        except Exception as e:
            # CRITICAL: Unprotect workspace on error
            try:
                workspace_for_cleanup = await Notebook.get(target_workspace_id)
                if workspace_for_cleanup and workspace_for_cleanup.protected:
                    logger.info(f"❌ UNPROTECTING workspace on error: {workspace_for_cleanup.name}")
                    workspace_for_cleanup.protected = False
                    await workspace_for_cleanup.save()
            except Exception as unprotect_error:
                logger.error(f"Failed to unprotect workspace: {unprotect_error}")

            # Update execution record with error
            if execution and execution.id:
                try:
                    execution.status = 'failed'
                    execution.error = str(e)
                    execution.completed_at = datetime.utcnow()
                    if execution.started_at:
                        execution.duration_ms = int((execution.completed_at - execution.started_at).total_seconds() * 1000)

                    # Force reload from DB to get latest state
                    existing = await TemplateExecution.get(execution.id)
                    if existing:
                        existing.status = 'failed'
                        existing.error = str(e)
                        existing.completed_at = datetime.utcnow()
                        if existing.started_at:
                            existing.duration_ms = int((existing.completed_at - existing.started_at).total_seconds() * 1000)
                        await existing.save()
                    else:
                        logger.warning(f"Execution record {execution.id} not found in DB during error handling")
                except Exception as update_error:
                    logger.error(f"Failed to update execution record with error: {update_error}")
            raise

    def _build_note_title(self, template_name: str, parameters: Dict, execution_id: str) -> str:
        """
        Build note title with execution ID and parameters.

        Args:
            template_name: Template name
            parameters: Parameter values
            execution_id: Execution ID

        Returns:
            Formatted note title
        """
        short_id = execution_id[:8]
        timestamp = datetime.utcnow().strftime('%b %d, %Y %I:%M %p')

        # Format: "Execution Results - {short_id}"
        return f"Execution Results - {short_id}"
