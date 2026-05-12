"""
Guided Workspace Creation Router

Endpoints for AI-powered workspace creation wizard.
Supports an 8-step flow: goal analysis, clarification, resource discovery,
plan generation, workspace creation, and session management.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header, status, Depends
from pydantic import BaseModel, Field

from open_notebook.database.repository import (
    repo_query,
    repo_create,
    repo_update,
    repo_delete,
    repo_execute,
)
from api.dependencies.auth import get_current_user, require_permission
from api.services.permission_service import PermissionService
from open_notebook.domain.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces/guided", tags=["guided-workspace"])


# ============================================================================
# Pydantic Models
# ============================================================================

class GoalAnalysisRequest(BaseModel):
    """Request to analyze a user's workspace goal"""
    goal: str = Field(..., min_length=20, max_length=5000, description="User's workspace goal description")
    context: Optional[Dict] = Field(None, description="Additional context (domain, constraints, etc.)")


class GoalAnalysisResponse(BaseModel):
    """Response from goal analysis"""
    session_id: str
    analysis: Dict
    needs_clarification: bool
    questions: Optional[List[Dict]] = None


class ClarificationRequest(BaseModel):
    """Request to provide answers to clarification questions"""
    session_id: str
    answers: Dict = Field(..., description="Answers keyed by question text")


class ClarificationResponse(BaseModel):
    """Response after processing clarification answers"""
    updated_analysis: Dict
    ready_for_discovery: bool
    follow_up_questions: Optional[List[Dict]] = None


class ResourceDiscoveryRequest(BaseModel):
    """Request to discover available resources for the workspace"""
    session_id: str
    source_limit: Optional[int] = Field(10, description="Max data sources to return")
    tool_limit: Optional[int] = Field(5, description="Max tools to return")
    agent_limit: Optional[int] = Field(5, description="Max agents to return")
    team_limit: Optional[int] = Field(3, description="Max teams to return")


class DiscoveredResource(BaseModel):
    """A single discovered resource"""
    id: str
    name: str
    type: str
    description: Optional[str] = None
    relevance_score: Optional[float] = None
    metadata: Optional[Dict] = None


class DiscoveredResourcesResponse(BaseModel):
    """Response with discovered resources grouped by type"""
    data_sources: List[Dict]
    tools: List[Dict]
    agents: List[Dict]
    teams: List[Dict]


class PlanGenerationRequest(BaseModel):
    """Request to generate an execution plan"""
    session_id: str
    selected_resources: Dict = Field(..., description="User-selected resources by type")


class PlanPhase(BaseModel):
    """A phase in the workspace execution plan"""
    phase_number: int
    name: str
    description: str
    tasks: List[Dict]
    estimated_duration: Optional[int] = None
    dependencies: Optional[List[int]] = None


class WorkspacePlanResponse(BaseModel):
    """Response with the generated workspace plan"""
    phases: List[Dict]
    total_duration: int = Field(..., description="Total estimated duration in minutes")
    collaboration_graph: Dict = Field(default_factory=dict, description="Agent/team collaboration structure")
    recommendations: Optional[List[str]] = None


class CreateWorkspaceRequest(BaseModel):
    """Request to create the workspace from the plan"""
    session_id: str
    name: str = Field(..., min_length=1, max_length=255)
    goal: str
    selected_resources: Dict
    plan: Dict
    auto_start: bool = Field(default=False, description="Automatically start initial tasks")


class WorkspaceCreatedResponse(BaseModel):
    """Response after workspace creation"""
    workspace_id: str
    status: str
    initialization_tasks: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)


class GuidedSessionResponse(BaseModel):
    """Response for a guided workspace session"""
    id: str
    user_id: str
    goal: str
    status: str
    current_step: Optional[str] = None
    analysis: Optional[Dict] = None
    clarification_answers: Optional[Dict] = None
    discovered_resources: Optional[Dict] = None
    selected_resources: Optional[Dict] = None
    plan: Optional[Dict] = None
    workspace_id: Optional[str] = None
    created: str
    updated: str
    expires_at: str


class GuidedSessionUpdate(BaseModel):
    """Request to update a guided session"""
    goal: Optional[str] = None
    current_step: Optional[str] = None
    selected_resources: Optional[Dict] = None


# ============================================================================
# Helper Functions
# ============================================================================

async def create_session(user_id: str, goal: str) -> str:
    """Create a new guided workspace session"""
    session_id = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(hours=24)).isoformat()

    session_data = {
        "id": session_id,
        "user_id": user_id,
        "goal": goal,
        "status": "draft",  # Changed from 'active' to 'draft' for in-progress sessions
        "current_step": "goal_analysis",
        "created": datetime.utcnow().isoformat(),
        "updated": datetime.utcnow().isoformat(),
        "expires_at": expires_at,
    }

    await repo_create("guided_workspace_sessions", session_data)
    return session_id


async def get_session(session_id: str) -> Optional[Dict]:
    """Get a draft or completed session by ID"""
    sql = "SELECT * FROM guided_workspace_sessions WHERE id = :id AND status IN ('draft', 'completed')"
    results = await repo_query(sql, {"id": session_id})
    if not results:
        return None

    session = results[0]
    # Parse JSON fields
    for field in ("analysis", "clarification_answers", "discovered_resources", "selected_resources", "plan"):
        if session.get(field) and isinstance(session[field], str):
            try:
                session[field] = json.loads(session[field])
            except (json.JSONDecodeError, TypeError):
                pass

    return session


async def update_session(session_id: str, updates: Dict) -> None:
    """Update a session with new data, serializing dicts to JSON"""
    updates["updated"] = datetime.utcnow().isoformat()

    # Serialize dict fields to JSON strings for storage
    for field in ("analysis", "clarification_answers", "discovered_resources", "selected_resources", "plan"):
        if field in updates and isinstance(updates[field], dict):
            updates[field] = json.dumps(updates[field])

    await repo_update("guided_workspace_sessions", session_id, updates)


async def validate_session(session_id: str) -> Dict:
    """Validate and return a session, raising 404 if not found or expired"""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guided session {session_id} not found or expired",
        )

    # Check expiration
    expires_at = session.get("expires_at", "")
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at)
            if datetime.utcnow() > expiry:
                await update_session(session_id, {"status": "expired"})
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Guided session has expired. Please start a new session.",
                )
        except ValueError:
            pass

    return session


# ============================================================================
# Step 1: Goal Analysis
# ============================================================================

@router.post("/analyze-goal", response_model=GoalAnalysisResponse)
async def analyze_goal(
    request: GoalAnalysisRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Step 1: Analyze user's goal with AI

    Extracts intent, domain, complexity, keywords, and requirements
    from the user's natural language goal description. May return
    clarification questions if the goal is ambiguous.
    """
    try:
        # Create session
        session_id = await create_session(current_user.id, request.goal)
        logger.info(f"Created guided session {session_id} for user {current_user.id}")

        # Call goal analysis service
        try:
            from api.services.goal_analysis_service import GoalAnalysisService
            service = GoalAnalysisService()
            # analyze_goal returns the analysis dict directly
            analysis = await service.analyze_goal(request.goal, request.context)
            # Generate clarification questions based on the analysis
            questions = await service.generate_clarification_questions(analysis)
            needs_clarification = len(questions) > 0
        except ImportError:
            logger.info("GoalAnalysisService not yet implemented, using placeholder")
            analysis = {
                "intent": "analysis",
                "domain": "general",
                "complexity": "moderate",
                "keywords": _extract_keywords(request.goal),
                "requirements": [],
                "suggested_name": request.goal[:50],
            }
            needs_clarification = False
            questions = None

        # Save analysis to session
        await update_session(session_id, {
            "analysis": analysis,
            "current_step": "clarification" if needs_clarification else "resource_discovery",
        })

        return GoalAnalysisResponse(
            session_id=session_id,
            analysis=analysis,
            needs_clarification=needs_clarification,
            questions=questions,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze goal: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze goal: {str(e)}",
        )


# ============================================================================
# Step 2: Clarification
# ============================================================================

@router.post("/clarify", response_model=ClarificationResponse)
async def clarify_goal(
    request: ClarificationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Step 2: Provide answers to clarification questions

    Refines the goal analysis based on user answers. May return
    additional follow-up questions or mark the session as ready
    for resource discovery.
    """
    session = await validate_session(request.session_id)

    try:
        # Merge new answers with existing
        existing_answers = session.get("clarification_answers") or {}
        if isinstance(existing_answers, str):
            existing_answers = json.loads(existing_answers)
        merged_answers = {**existing_answers, **request.answers}

        # Call service
        try:
            from api.services.goal_analysis_service import GoalAnalysisService
            service = GoalAnalysisService()
            # refine_analysis takes (analysis, answers) -- not goal
            updated_analysis = await service.refine_analysis(
                session.get("analysis", {}),
                merged_answers,
            )
            ready = True
            follow_up = None
        except ImportError:
            logger.info("GoalAnalysisService not yet implemented, using placeholder")
            updated_analysis = session.get("analysis", {})
            updated_analysis["clarification_context"] = merged_answers
            ready = True
            follow_up = None

        # Update session
        next_step = "resource_discovery" if ready else "clarification"
        await update_session(request.session_id, {
            "analysis": updated_analysis,
            "clarification_answers": merged_answers,
            "current_step": next_step,
        })

        return ClarificationResponse(
            updated_analysis=updated_analysis,
            ready_for_discovery=ready,
            follow_up_questions=follow_up,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process clarification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process clarification: {str(e)}",
        )


# ============================================================================
# Step 3: Resource Discovery
# ============================================================================

@router.post("/discover-resources", response_model=DiscoveredResourcesResponse)
async def discover_resources(
    request: ResourceDiscoveryRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Step 3: Discover available resources for the workspace

    Searches existing data sources, tools, agents, and teams
    that are relevant to the user's goal. Returns ranked
    suggestions for each resource type.
    """
    session = await validate_session(request.session_id)

    try:
        # Get analysis from session
        analysis = session.get("analysis", {})
        if isinstance(analysis, str):
            analysis = json.loads(analysis)

        # Call discovery service
        try:
            from api.services.resource_discovery_service import ResourceDiscoveryService
            service = ResourceDiscoveryService()
            # discover_* methods take (analysis, limit)
            data_sources = await service.discover_data_sources(analysis, request.source_limit)
            tools = await service.discover_tools(analysis, request.tool_limit)
            agents = await service.discover_agents(analysis, request.agent_limit)
            teams = await service.discover_teams(analysis, request.team_limit)
        except ImportError:
            logger.info("ResourceDiscoveryService not yet implemented, using placeholder")
            # Discover existing resources from the database
            data_sources = await _discover_existing_sources(current_user.id)
            tools = await _discover_existing_tools()
            agents = await _discover_existing_agents()
            teams = await _discover_existing_teams()

        discovered = {
            "data_sources": data_sources,
            "tools": tools,
            "agents": agents,
            "teams": teams,
        }

        # Save to session
        await update_session(request.session_id, {
            "discovered_resources": discovered,
            "current_step": "plan_generation",
        })

        return DiscoveredResourcesResponse(**discovered)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to discover resources: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover resources: {str(e)}",
        )


# ============================================================================
# Step 4: Plan Generation
# ============================================================================

@router.post("/generate-plan", response_model=WorkspacePlanResponse)
async def generate_plan(
    request: PlanGenerationRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Step 4: Generate an execution plan for the workspace

    Creates a phased plan with tasks, timelines, and agent
    collaboration structure based on the goal and selected resources.
    """
    print(f"[generate_plan] Endpoint called! User: {current_user.id}, Session: {request.session_id}")
    logger.info(f"[generate_plan] Endpoint called! User: {current_user.id}, Session: {request.session_id}")
    session = await validate_session(request.session_id)

    try:
        # Get goal and analysis from session
        goal = session.get("goal", "")
        analysis = session.get("analysis", {})
        if isinstance(analysis, str):
            analysis = json.loads(analysis)

        # Call plan generation service
        try:
            import asyncio
            from api.services.plan_generation_service import PlanGenerationService
            service = PlanGenerationService()

            # Add a 5-second timeout to avoid hanging
            async def generate_with_timeout():
                return await service.generate_task_plan(
                    goal,
                    request.selected_resources,
                    analysis,
                )

            plan = await asyncio.wait_for(generate_with_timeout(), timeout=5.0)

            # Estimate durations on the plan
            plan = service.estimate_durations(plan)
            phases = plan.get("phases", [])
            total_duration = sum(
                t.get("estimated_duration", 0)
                for p in phases
                for t in p.get("tasks", [])
            )
            # Build collaboration graph if agents or teams are selected
            agent_ids = request.selected_resources.get("agent_ids", [])
            team_ids = request.selected_resources.get("team_ids", [])

            # Combine agents and teams for collaboration graph
            all_agents = []

            # Fetch standalone agents
            if agent_ids:
                from open_notebook.database.repository import repo_query
                agents = await repo_query(
                    """
                    SELECT id, name, role, system_prompt, model_name,
                           tool_ids, skill_ids, mcp_server_ids, data_source_ids
                    FROM standalone_agents
                    WHERE id IN ({placeholders})
                    """.format(placeholders=", ".join(f":agent_{i}" for i in range(len(agent_ids)))),
                    {f"agent_{i}": agent_id for i, agent_id in enumerate(agent_ids)}
                )
                all_agents.extend([
                    {
                        "id": a["id"],
                        "name": a["name"],
                        "type": "agent",
                        "role": a.get("role"),
                        "skills": []  # Placeholder for skills
                    }
                    for a in agents
                ])

            # Fetch teams
            if team_ids:
                from open_notebook.database.repository import repo_query
                teams = await repo_query(
                    """
                    SELECT id, name, description
                    FROM agent_teams
                    WHERE id IN ({placeholders})
                    """.format(placeholders=", ".join(f":team_{i}" for i in range(len(team_ids)))),
                    {f"team_{i}": team_id for i, team_id in enumerate(team_ids)}
                )
                all_agents.extend([
                    {
                        "id": t["id"],
                        "name": t["name"],
                        "type": "team",
                        "role": "team",
                        "skills": []
                    }
                    for t in teams
                ])

            if all_agents:
                plan = await service.assign_agents_to_tasks(plan, all_agents)
                collaboration_graph = service.build_collaboration_graph(plan, all_agents)
            else:
                collaboration_graph = {"nodes": [], "edges": []}
            recommendations = None
        except (ImportError, asyncio.TimeoutError, RuntimeError, Exception) as e:
            logger.info(f"PlanGenerationService failed ({type(e).__name__}: {str(e)[:100]}), using placeholder")
            phases = _generate_default_phases(session.get("goal", ""), request.selected_resources)
            total_duration = sum(p.get("estimated_duration", 10) for p in phases)
            collaboration_graph = {"nodes": [], "edges": []}
            recommendations = [
                "Review the generated plan before creating the workspace",
                "Consider adding more data sources for better results",
            ]

        plan_data = {
            "phases": phases,
            "total_duration": total_duration,
            "collaboration_graph": collaboration_graph,
            "recommendations": recommendations,
        }

        # Save to session
        await update_session(request.session_id, {
            "selected_resources": request.selected_resources,
            "plan": plan_data,
            "current_step": "workspace_creation",
        })

        return WorkspacePlanResponse(
            phases=phases,
            total_duration=total_duration,
            collaboration_graph=collaboration_graph,
            recommendations=recommendations,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate plan: {str(e)}",
        )


# ============================================================================
# Step 5: Workspace Creation
# ============================================================================

@router.post("/create", response_model=WorkspaceCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: CreateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Step 5: Create the workspace from the generated plan

    Creates the notebook, links selected resources, initializes
    agents/teams, and optionally auto-starts initial tasks.
    """
    logger.info(f"=== RECEIVED WORKSPACE CREATION REQUEST ===")
    logger.info(f"Session ID: {request.session_id}")
    logger.info(f"Name: {request.name}")
    logger.info(f"Goal: {request.goal[:100]}...")
    logger.info(f"Selected Resources: {request.selected_resources}")
    logger.info(f"Plan phases: {len(request.plan.get('phases', []))}")

    session = await validate_session(request.session_id)

    try:
        # Call workspace initialization service
        try:
            logger.info("=== ATTEMPTING TO IMPORT WorkspaceInitializationService ===")
            from api.services.workspace_initialization_service import WorkspaceInitializationService
            logger.info("=== IMPORT SUCCESSFUL ===")
            service = WorkspaceInitializationService()
            logger.info("=== SERVICE INSTANTIATED ===")

            # create_workspace_from_plan(plan, name, user_id, goal)
            logger.info(f"=== CREATING WORKSPACE: name={request.name}, goal={request.goal[:50]}... ===")
            workspace_id = await service.create_workspace_from_plan(
                plan=request.plan,
                name=request.name,
                user_id=current_user.id,
                goal=request.goal,
            )
            logger.info(f"=== WORKSPACE CREATED: {workspace_id} ===")

            # Link resources
            resource_ids = {
                "source_ids": [s.get("id") for s in request.selected_resources.get("data_sources", []) if s.get("id")],
                "tool_ids": [t.get("id") for t in request.selected_resources.get("tools", []) if t.get("id")],
                "agent_ids": [a.get("id") for a in request.selected_resources.get("agents", []) if a.get("id")],
                "team_ids": [t.get("id") for t in request.selected_resources.get("teams", []) if t.get("id")],
            }
            logger.info(f"=== LINKING RESOURCES: {len(resource_ids['source_ids'])} sources, {len(resource_ids['tool_ids'])} tools, {len(resource_ids['agent_ids'])} agents ===")
            await service.link_resources(workspace_id, resource_ids)
            logger.info("=== RESOURCES LINKED ===")

            # Initialize tasks from plan
            logger.info(f"=== INITIALIZING TASKS: {len(request.plan.get('phases', []))} phases ===")
            await service.initialize_tasks(workspace_id, request.plan)
            logger.info("=== TASKS INITIALIZED ===")

            # Configure agent-to-task assignments
            # Transform from task->agent format to agent->tasks format
            agent_to_tasks: Dict[str, List[str]] = {}
            for phase in request.plan.get("phases", []):
                for task in phase.get("tasks", []):
                    agent_id = task.get("assigned_agent_id")
                    task_id = task.get("id")
                    if agent_id and task_id:
                        if agent_id not in agent_to_tasks:
                            agent_to_tasks[agent_id] = []
                        agent_to_tasks[agent_id].append(task_id)

            if agent_to_tasks:
                logger.info(f"=== CONFIGURING ASSIGNMENTS FOR {len(agent_to_tasks)} AGENT(S) ===")
                await service.configure_agents(workspace_id, agent_to_tasks)
                logger.info("=== AGENT ASSIGNMENTS CONFIGURED ===")
            else:
                logger.warning("=== NO AGENT ASSIGNMENTS FOUND IN PLAN ===")

            init_tasks = ["Workspace created", "Resources linked", "Tasks initialized"]
            next_steps = [
                "Open the workspace to start working",
                "Add more sources as needed",
                "Start a chat session to interact with your data",
            ]
        except ImportError as ie:
            logger.error(f"=== IMPORT ERROR: {ie} ===", exc_info=True)
            # Create a notebook as the workspace
            workspace_id = await _create_workspace_notebook(
                request.name, request.goal, request.plan, request.selected_resources, current_user.id
            )
            init_tasks = ["Workspace notebook created", "Sources linked"]
            next_steps = [
                "Open the workspace to start working",
                "Add more sources as needed",
                "Start a chat session to interact with your data",
            ]
        except Exception as ex:
            logger.error(f"=== WORKSPACE CREATION ERROR: {ex} ===", exc_info=True)
            raise

        # Mark session as completed
        await update_session(request.session_id, {
            "workspace_id": workspace_id,
            "status": "completed",
            "current_step": "completed",
        })

        logger.info(f"Workspace {workspace_id} created from guided session {request.session_id}")

        return WorkspaceCreatedResponse(
            workspace_id=workspace_id,
            status="created",
            initialization_tasks=init_tasks,
            next_steps=next_steps,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create workspace: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create workspace: {str(e)}",
        )


# ============================================================================
# Session Management
# ============================================================================

@router.get("/sessions", response_model=List[GuidedSessionResponse])
async def list_guided_sessions(
    current_user: User = Depends(get_current_user),
    session_status: Optional[str] = None,
):
    """
    List guided workspace sessions for the current user

    Query parameters:
    - session_status: Filter by status ('draft', 'completed', 'abandoned', 'expired')
              If omitted, returns all non-expired sessions
    """
    try:
        if session_status:
            sql = """
                SELECT * FROM guided_workspace_sessions
                WHERE user_id = :user_id AND status = :status
                ORDER BY updated DESC
            """
            params = {"user_id": current_user.id, "status": session_status}
        else:
            sql = """
                SELECT * FROM guided_workspace_sessions
                WHERE user_id = :user_id AND status != 'expired'
                ORDER BY updated DESC
            """
            params = {"user_id": current_user.id}

        results = await repo_query(sql, params)

        sessions = []
        for row in results:
            # Parse JSON fields
            session = dict(row)
            for field in ("analysis", "clarification_answers", "discovered_resources", "selected_resources", "plan"):
                if session.get(field) and isinstance(session[field], str):
                    try:
                        session[field] = json.loads(session[field])
                    except (json.JSONDecodeError, TypeError):
                        pass

            sessions.append(GuidedSessionResponse(
                id=session["id"],
                user_id=session["user_id"],
                goal=session["goal"],
                status=session["status"],
                current_step=session.get("current_step"),
                analysis=session.get("analysis"),
                clarification_answers=session.get("clarification_answers"),
                discovered_resources=session.get("discovered_resources"),
                selected_resources=session.get("selected_resources"),
                plan=session.get("plan"),
                workspace_id=session.get("workspace_id"),
                created=session["created"],
                updated=session["updated"],
                expires_at=session.get("expires_at", ""),
            ))

        return sessions

    except Exception as e:
        logger.error(f"Failed to list guided sessions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list guided sessions: {str(e)}",
        )


@router.get("/sessions/{session_id}", response_model=GuidedSessionResponse)
async def get_guided_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Get a guided workspace session by ID

    Returns the full session state including analysis, discovered
    resources, selected resources, and plan.
    """
    session = await validate_session(session_id)

    # Check ownership
    if session["user_id"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this session"
        )

    return GuidedSessionResponse(
        id=session["id"],
        user_id=session["user_id"],
        goal=session["goal"],
        status=session["status"],
        current_step=session.get("current_step"),
        analysis=session.get("analysis"),
        clarification_answers=session.get("clarification_answers"),
        discovered_resources=session.get("discovered_resources"),
        selected_resources=session.get("selected_resources"),
        plan=session.get("plan"),
        workspace_id=session.get("workspace_id"),
        created=session["created"],
        updated=session["updated"],
        expires_at=session.get("expires_at", ""),
    )


@router.put("/sessions/{session_id}", response_model=GuidedSessionResponse)
async def update_guided_session(
    session_id: str,
    request: GuidedSessionUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Update a guided workspace session

    Allows updating the goal, current step, and selected resources.
    """
    session = await validate_session(session_id)

    # Check ownership
    if session["user_id"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this session"
        )

    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    await update_session(session_id, updates)

    # Return updated session
    updated = await get_session(session_id)
    return GuidedSessionResponse(
        id=updated["id"],
        user_id=updated["user_id"],
        goal=updated["goal"],
        status=updated["status"],
        current_step=updated.get("current_step"),
        analysis=updated.get("analysis"),
        clarification_answers=updated.get("clarification_answers"),
        discovered_resources=updated.get("discovered_resources"),
        selected_resources=updated.get("selected_resources"),
        plan=updated.get("plan"),
        workspace_id=updated.get("workspace_id"),
        created=updated["created"],
        updated=updated["updated"],
        expires_at=updated.get("expires_at", ""),
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guided_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Delete a guided workspace session

    Marks the session as cancelled. Does not delete the workspace
    if one was already created.
    """
    session = await validate_session(session_id)

    # Check ownership
    if session["user_id"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this session"
        )

    try:
        await repo_delete("guided_workspace_sessions", session_id)
        logger.info(f"Deleted guided session {session_id}")
        return None
    except Exception as e:
        logger.error(f"Failed to delete session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}",
        )


# ============================================================================
# Internal Helpers (placeholder implementations)
# ============================================================================

def _extract_keywords(goal: str) -> List[str]:
    """Extract simple keywords from goal text"""
    stop_words = {
        "i", "want", "to", "a", "an", "the", "for", "and", "or", "that",
        "this", "with", "from", "on", "in", "of", "my", "me", "is", "be",
        "create", "build", "make", "need", "would", "like", "can", "will",
    }
    words = goal.lower().split()
    return [w.strip(".,!?") for w in words if w.strip(".,!?") not in stop_words and len(w) > 2][:10]


async def _discover_existing_sources(user_id: str) -> List[Dict]:
    """Discover existing sources the user has access to"""
    try:
        sql = "SELECT id, title, source_type, created, updated FROM sources ORDER BY updated DESC LIMIT 20"
        results = await repo_query(sql)
        return [
            {
                "id": s["id"],
                "name": s.get("title", "Untitled"),
                "type": s.get("source_type", "unknown"),
                "description": f"{s.get('source_type', 'unknown')} source",
                "metadata": {"created": s.get("created"), "updated": s.get("updated")},
            }
            for s in results
        ]
    except Exception as e:
        logger.warning(f"Failed to discover sources: {e}")
        return []


async def _discover_existing_tools() -> List[Dict]:
    """Discover existing tools from the registry"""
    try:
        sql = "SELECT id, name, tool_type, description, category FROM tool_registry WHERE enabled = 1 ORDER BY name LIMIT 20"
        results = await repo_query(sql)
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "type": t.get("tool_type", "unknown"),
                "description": t.get("description", ""),
                "metadata": {"category": t.get("category")},
            }
            for t in results
        ]
    except Exception as e:
        logger.warning(f"Failed to discover tools: {e}")
        return []


async def _discover_existing_agents() -> List[Dict]:
    """Discover existing standalone agents"""
    try:
        sql = "SELECT id, name, role, description FROM standalone_agents WHERE status = 'active' ORDER BY name LIMIT 20"
        results = await repo_query(sql)
        return [
            {
                "id": a["id"],
                "name": a["name"],
                "type": a.get("role", "custom"),
                "description": a.get("description", ""),
            }
            for a in results
        ]
    except Exception as e:
        logger.warning(f"Failed to discover agents: {e}")
        return []


async def _discover_existing_teams() -> List[Dict]:
    """Discover existing agent teams"""
    try:
        sql = "SELECT id, name, description, status FROM agent_teams WHERE status != 'archived' ORDER BY name LIMIT 10"
        results = await repo_query(sql)
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "type": "team",
                "description": t.get("description", ""),
                "metadata": {"status": t.get("status")},
            }
            for t in results
        ]
    except Exception as e:
        logger.warning(f"Failed to discover teams: {e}")
        return []


def _generate_default_phases(goal: str, selected_resources: Dict) -> List[Dict]:
    """
    Generate a default phased plan with user-actionable tasks only.
    System tasks (embeddings, indexing, workspace creation) happen automatically
    and should not be included in the user-facing plan.
    """
    # Extract key info from goal for simple task suggestions
    goal_lower = goal.lower()

    # Phase 1: Initial Analysis/Exploration
    phase1_tasks = [
        {
            "name": "Review uploaded data sources",
            "description": "Examine the content and structure of your data sources",
            "type": "user",
            "estimated_minutes": 15
        },
        {
            "name": "Identify key insights and patterns",
            "description": "Look for trends, outliers, or important findings in the data",
            "type": "user",
            "estimated_minutes": 30
        },
    ]

    # Add analysis-specific tasks based on goal
    if "swot" in goal_lower or "analysis" in goal_lower:
        phase1_tasks.append({
            "name": "Conduct initial SWOT analysis",
            "description": "Identify strengths, weaknesses, opportunities, and threats",
            "type": "user",
            "estimated_minutes": 45
        })

    phases = [
        {
            "phase_number": 1,
            "name": "Data Exploration",
            "description": "Review and analyze your data sources",
            "tasks": phase1_tasks,
            "estimated_duration": sum(t["estimated_minutes"] for t in phase1_tasks),
            "dependencies": [],
        }
    ]

    # Phase 2: Research & Synthesis (if applicable)
    if "research" in goal_lower or "report" in goal_lower or "presentation" in goal_lower:
        phases.append({
            "phase_number": 2,
            "name": "Research & Documentation",
            "description": "Conduct additional research and document findings",
            "tasks": [
                {
                    "name": "Gather external research",
                    "description": "Use web search and other tools to supplement your data",
                    "type": "user",
                    "estimated_minutes": 60
                },
                {
                    "name": "Synthesize findings",
                    "description": "Combine internal data with external research",
                    "type": "user",
                    "estimated_minutes": 45
                },
            ],
            "estimated_duration": 105,
            "dependencies": [1],
        })

    # Final Phase: Deliverable Creation
    final_phase_num = len(phases) + 1
    phases.append({
        "phase_number": final_phase_num,
        "name": "Create Deliverable",
        "description": "Compile your analysis into the final output",
        "tasks": [
            {
                "name": "Draft initial report/presentation",
                "description": "Create the first version of your deliverable",
                "type": "user",
                "estimated_minutes": 90
            },
            {
                "name": "Review and refine",
                "description": "Polish and finalize your work",
                "type": "user",
                "estimated_minutes": 30
            },
        ],
        "estimated_duration": 120,
        "dependencies": [final_phase_num - 1],
    })

    return phases


async def _create_workspace_notebook(
    name: str, goal: str, plan: Dict, selected_resources: Dict, user_id: str
) -> str:
    """Create a notebook to serve as the workspace"""
    notebook_data = {
        "name": name,
        "description": f"Guided workspace: {goal[:200]}",
    }
    notebook_id = await repo_create("notebooks", notebook_data)

    # Link selected data sources
    source_ids = [s.get("id") for s in selected_resources.get("data_sources", []) if s.get("id")]
    for source_id in source_ids:
        try:
            await repo_execute(
                """
                INSERT INTO notebook_source (notebook_id, source_id, created)
                VALUES (:notebook_id, :source_id, :created)
                """,
                {
                    "notebook_id": notebook_id,
                    "source_id": source_id,
                    "created": datetime.utcnow().isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Failed to link source {source_id} to notebook: {e}")

    logger.info(f"Created workspace notebook {notebook_id} with {len(source_ids)} sources")
    return notebook_id
