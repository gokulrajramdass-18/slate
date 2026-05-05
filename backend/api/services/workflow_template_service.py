"""
Workflow Template Service

Handles instantiation and execution of workflow templates.
"""

import json
from typing import Dict, Any, Optional
from datetime import datetime


class WorkflowTemplateService:
    """Service for managing workflow template instantiation and execution."""

    async def instantiate_template(
        self,
        template_id: str,
        parameters: Dict[str, Any],
        user_id: str,
        name: Optional[str] = None
    ) -> str:
        """
        Instantiate a workflow from a template.

        Args:
            template_id: Template to instantiate
            parameters: Parameter values
            user_id: User creating the workflow
            name: Optional custom name

        Returns:
            Created workflow ID
        """
        from open_notebook.domain.workflow_template import WorkflowTemplate
        from open_notebook.domain.workflow import Workflow, WorkflowGraph

        # Load and validate template
        template = await WorkflowTemplate.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        validation = template.validate_parameters(parameters)
        if not validation["valid"]:
            raise ValueError(f"Parameter validation failed: {', '.join(validation['errors'])}")

        # Parse graph
        graph_data = json.loads(template.graph_json)

        # Replace placeholders in graph
        graph_json_str = template.graph_json
        for key, value in parameters.items():
            graph_json_str = graph_json_str.replace(f"{{{{{key}}}}}", str(value))

        # Replace built-in placeholders
        graph_json_str = graph_json_str.replace("{{TODAY}}", datetime.now().strftime("%Y-%m-%d"))
        graph_json_str.replace("{{NOW}}", datetime.now().isoformat())
        graph_json_str = graph_json_str.replace("{{USER_ID}}", user_id)

        # Parse resolved graph
        graph_data = json.loads(graph_json_str)
        graph = WorkflowGraph(**graph_data)

        # Create workflow
        workflow = Workflow(
            id=None,
            name=name or f"{template.name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            description=f"Created from template: {template.name}",
            graph=graph,
            created_by=user_id,
            tags=template.get_tags()
        )
        await workflow.save()

        # Increment usage count
        await template.increment_usage()

        # Track execution
        from open_notebook.domain.workflow import WorkflowExecution
        execution_tracking = {
            "template_id": template_id,
            "workflow_id": workflow.id,
            "parameters": json.dumps(parameters),
            "status": "instantiated",
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat()
        }

        # Store in workflow_template_executions
        from open_notebook.database.repository import repo_execute
        import uuid

        tracking_id = str(uuid.uuid4())

        await repo_execute(
            """
            INSERT INTO workflow_template_executions
            (id, template_id, workflow_id, parameters, status, user_id, created_at)
            VALUES (:id, :template_id, :workflow_id, :parameters, :status, :user_id, :created_at)
            """,
            {
                "id": tracking_id,
                **execution_tracking
            }
        )

        return workflow.id

    async def execute_template(
        self,
        template_id: str,
        parameters: Dict[str, Any],
        user_id: str,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Instantiate and execute a workflow template.

        Args:
            template_id: Template to execute
            parameters: Template parameters
            user_id: User executing
            input_data: Input data for workflow execution

        Returns:
            Execution result with workflow_id and execution_id
        """
        from open_notebook.domain.workflow import Workflow
        from open_notebook.agents.workflow_engine import WorkflowEngine

        # Instantiate template
        workflow_id = await self.instantiate_template(
            template_id=template_id,
            parameters=parameters,
            user_id=user_id
        )

        # Execute workflow
        workflow = await Workflow.get(workflow_id)
        engine = WorkflowEngine(workflow)
        execution = await engine.execute(input_data=input_data or {})

        return {
            "workflow_id": workflow_id,
            "execution_id": execution.id,
            "status": execution.status.value,
            "final_output": execution.final_output,
            "error": execution.error
        }

    async def create_template_from_workflow(
        self,
        workflow_id: str,
        name: str,
        description: Optional[str],
        parameters: list,
        category: Optional[str],
        is_public: bool,
        tags: Optional[list],
        user_id: str
    ) -> str:
        """
        Create a template from an existing workflow.

        Args:
            workflow_id: Source workflow
            name: Template name
            description: Template description
            parameters: Parameter definitions
            category: Template category
            is_public: Whether to publish publicly
            tags: Template tags
            user_id: User creating template

        Returns:
            Created template ID
        """
        from open_notebook.domain.workflow import Workflow
        from open_notebook.domain.workflow_template import WorkflowTemplate
        import uuid

        # Load workflow
        workflow = await Workflow.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")

        # Create template
        template = WorkflowTemplate(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            category=category,
            source_workflow_id=workflow_id,
            graph_json=json.dumps(workflow.graph.dict()),
            parameters=json.dumps([p if isinstance(p, dict) else p.dict() for p in parameters]),
            version=1,
            is_public=is_public,
            tags=json.dumps(tags) if tags else None,
            usage_count=0,
            created=datetime.utcnow(),
            updated=datetime.utcnow()
        )

        await template.save()
        return template.id


# Singleton instance
_service: Optional[WorkflowTemplateService] = None


def get_workflow_template_service() -> WorkflowTemplateService:
    """Get the singleton workflow template service."""
    global _service
    if _service is None:
        _service = WorkflowTemplateService()
    return _service
