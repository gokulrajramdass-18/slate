"""
FastAPI Main Application

Entry point for the Open Notebook API server.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from api.middleware import OAuthRateLimitMiddleware, OAuthAuditMiddleware
from api.models import ErrorResponse, HealthCheckResponse
from api.routers import notebooks, sources, database, dashboard, chat, chat_settings, source_chat, auth, models, embedding, credentials, microsites, microsite_chat, smtp, notes, search, hana_connections, api_connections, deep_research, charts, files, tools, agents, agent_memory, agent_tools, agent_skills, mcp_servers, agent_prompts, system_prompts, user_query_prompts, standalone_agents, workflows, bookmarks, graph, mcp_oauth, workspace_guided, workspace_tasks, folders, a2a, a2a_remote, users, roles, resource_shares, entities, entity_relationships, communities, autonomous_orchestration, actions, orchestration_actions, oauth, workspace_templates, orchestration_schedules, workflow_templates, workflow_approvals, template_executions, notifications, external_notifications, api_keys, presentations, workflow_snapshots, documents, daily_brief
from api.services.database_service import get_database_service
from open_notebook.database.interface import ConnectionConfig, DatabaseError
from open_notebook.database.repository import init_database


# ============================================================================
# Application Lifecycle Management
# ============================================================================

# Track application start time
app_start_time = datetime.utcnow()

# Background tasks
background_tasks = set()
sync_service_instance = None
workflow_scheduler_instance = None
task_executor_instance = None
orchestration_scheduler_instance = None
approval_timeout_handler_instance = None
approval_cleanup_service_instance = None


async def database_health_monitor():
    """Background task to monitor database health"""
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            db_service = get_database_service()
            if db_service._current_db and db_service._current_db.is_connected:
                # Perform simple health check
                from open_notebook.database.repository import repo_query
                await repo_query("SELECT 1 as health")
        except Exception as e:
            print(f"Database health check failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events

    Handles startup and shutdown tasks:
    - Database initialization
    - Background task scheduling
    - Sync service initialization
    - Cleanup on shutdown
    """
    global sync_service_instance, workflow_scheduler_instance, orchestration_scheduler_instance, approval_timeout_handler_instance, approval_cleanup_service_instance

    # Startup
    print("🚀 Starting Open Notebook API...")

    try:
        # Phase 1: Initialize database and credentials in parallel
        print("📊 Initializing database and credentials...")

        async def _init_db():
            db_instance = await init_database()
            db_service = get_database_service()
            db_service.set_database(db_instance)
            return db_instance

        async def _init_credentials():
            from api.services.credential_manager import get_credential_manager
            from api.routers.credentials import _credentials_store
            credential_manager = get_credential_manager()
            await credential_manager.initialize()
            await credential_manager.import_from_legacy_store(_credentials_store)
            print("✅ Credential manager initialized")

        await asyncio.gather(_init_db(), _init_credentials())

        # Phase 2: Start background services in parallel (depend on DB being ready)
        print("⏰ Starting background services...")

        async def _start_sync():
            from api.services.sync_service import get_sync_service
            global sync_service_instance
            sync_service_instance = get_sync_service()
            await sync_service_instance.start()
            print("🔄 Sync service started")

        async def _start_workflow_scheduler():
            from api.services.workflow_scheduler import get_workflow_scheduler
            global workflow_scheduler_instance
            workflow_scheduler_instance = get_workflow_scheduler()
            await workflow_scheduler_instance.start()
            print("🕐 Workflow scheduler started")

        async def _start_task_executor():
            from api.services.workspace_task_executor import get_task_executor
            global task_executor_instance
            task_executor_instance = get_task_executor()
            await task_executor_instance.start()
            print("🤖 Task executor started")

        async def _start_stream_manager():
            from api.services.stream_manager import start_stream_manager
            await start_stream_manager()
            print("🌊 Stream manager started")

        async def _start_orchestration_scheduler():
            from api.services.orchestration_scheduler import get_orchestration_scheduler
            global orchestration_scheduler_instance
            orchestration_scheduler_instance = await get_orchestration_scheduler()
            print("📅 Orchestration scheduler started")

        async def _start_approval_timeout_handler():
            from api.services.approval_timeout_handler import get_approval_timeout_handler
            global approval_timeout_handler_instance
            approval_timeout_handler_instance = get_approval_timeout_handler()
            await approval_timeout_handler_instance.start()
            print("⏰ Approval timeout handler started")

        async def _start_approval_cleanup():
            from api.services.approval_cleanup_service import get_approval_cleanup_service
            global approval_cleanup_service_instance
            approval_cleanup_service_instance = get_approval_cleanup_service(interval_seconds=3600)  # 1 hour
            await approval_cleanup_service_instance.start()
            print("🧹 Approval cleanup service started")

        await asyncio.gather(
            _start_sync(),
            _start_workflow_scheduler(),
            _start_task_executor(),
            _start_stream_manager(),
            _start_orchestration_scheduler(),
            _start_approval_timeout_handler(),
            _start_approval_cleanup()
        )

        # Start database health monitor as background task
        health_task = asyncio.create_task(database_health_monitor())
        background_tasks.add(health_task)
        health_task.add_done_callback(background_tasks.discard)

        # Seed microsite templates (runs only if table is empty)
        try:
            from api.services.template_seeder import get_template_seeder
            seeder = get_template_seeder()
            await seeder.seed_if_empty()
        except Exception as e:
            print(f"Template seeder skipped: {e}")

        # Register builtin skills
        try:
            print("🛠️  Registering builtin agent skills...")
            from open_notebook.agents.skills.builtin import register_builtin_skills
            import json
            register_builtin_skills()

            # Sync builtin skills to database
            from open_notebook.agents.skills import get_skill_registry
            from open_notebook.database.repository import repo_execute, repo_query
            registry = get_skill_registry()
            skills = registry.list_skills()

            for skill in skills:
                # Check if skill exists in database
                existing = await repo_query(
                    "SELECT id FROM agent_skills WHERE id = :skill_id",
                    {"skill_id": skill.id}
                )

                if not existing:
                    # Insert builtin skill to database
                    await repo_execute(
                        """
                        INSERT INTO agent_skills
                        (id, name, description, category, skill_type, definition,
                         input_schema, output_schema, roles, tags, enabled, metadata, created, updated)
                        VALUES (:id, :name, :description, :category, :skill_type, :definition,
                                :input_schema, :output_schema, :roles, :tags, :enabled, :metadata,
                                datetime('now'), datetime('now'))
                        """,
                        {
                            "id": skill.id,
                            "name": skill.name,
                            "description": skill.description,
                            "category": skill.category.value,
                            "skill_type": "builtin",
                            "definition": "{}",
                            "input_schema": "{}",
                            "output_schema": "{}",
                            "roles": json.dumps(list(skill.allowed_roles) if skill.allowed_roles else []),
                            "tags": json.dumps(list(skill.tags) if skill.tags else []),
                            "enabled": 1 if skill.enabled else 0,
                            "metadata": "{}"
                        }
                    )
                    print(f"  ✓ Synced {skill.name} to database")

            print(f"✓ Registered and synced {len(skills)} built-in agent skills")
        except Exception as e:
            print(f"⚠️  Failed to register builtin skills: {e}")
            import traceback
            traceback.print_exc()
            # Do not fail startup if skill registration fails

        # Seed default roles and admin user
        try:
            print("👥 Seeding default roles and admin user...")
            from open_notebook.database.seeds.default_roles import seed_default_roles, seed_default_admin_user
            from open_notebook.domain.user import Role

            # Check if roles exist
            existing_roles = await Role.get_all()
            if not existing_roles:
                await seed_default_roles()
                await seed_default_admin_user()
                print("✅ Default roles and admin user seeded")
            else:
                print("✓ Default roles already exist, skipping seeding")
        except Exception as e:
            print(f"⚠️  Failed to seed default roles: {e}")
            import traceback
            traceback.print_exc()
            # Do not fail startup if seeding fails

        print("✅ Application startup complete")

    except Exception as e:
        print(f"❌ Startup failed: {e}")
        raise

    yield

    # Shutdown
    print("🛑 Shutting down Open Notebook API...")

    # Stop stream manager
    try:
        from api.services.stream_manager import stop_stream_manager
        await stop_stream_manager()
        print("⏸️  Stream manager stopped")
    except Exception as e:
        print(f"⚠️  Error stopping stream manager: {e}")

    # Stop task executor
    if task_executor_instance:
        print("⏸️  Stopping task executor...")
        await task_executor_instance.stop()

    # Stop orchestration scheduler
    if orchestration_scheduler_instance:
        print("⏸️  Stopping orchestration scheduler...")
        await orchestration_scheduler_instance.stop()

    # Stop workflow scheduler
    if workflow_scheduler_instance:
        print("⏸️  Stopping workflow scheduler...")
        await workflow_scheduler_instance.stop()

    # Stop sync service
    if sync_service_instance:
        print("⏸️  Stopping sync service...")
        await sync_service_instance.stop()

    # Stop approval timeout handler
    if approval_timeout_handler_instance:
        print("⏸️  Stopping approval timeout handler...")
        await approval_timeout_handler_instance.stop()

    # Stop approval cleanup service
    if approval_cleanup_service_instance:
        print("⏸️  Stopping approval cleanup service...")
        await approval_cleanup_service_instance.stop()

    # Cancel background tasks
    for task in background_tasks:
        task.cancel()

    # Wait for tasks to complete
    await asyncio.gather(*background_tasks, return_exceptions=True)

    # Close shared HTTP client pool
    from api.services.http_client import http_client_manager
    await http_client_manager.close()

    # Close database connection
    db_service = get_database_service()
    if db_service._current_db:
        await db_service._current_db.disconnect()

    print("👋 Shutdown complete")


# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="Open Notebook API",
    description="Privacy-focused, self-hosted alternative to Google Notebook LM with HANA DB support",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    swagger_ui_init_oauth={
        "clientId": "swagger-ui",
        "appName": "Open Notebook API",
        "usePkceWithAuthorizationCodeGrant": True,
    },
)


# ============================================================================
# Middleware
# ============================================================================

# Gzip compression for responses over 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# OAuth middleware (audit first, then rate limiting)
app.add_middleware(OAuthAuditMiddleware)
app.add_middleware(OAuthRateLimitMiddleware)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development
        "http://localhost:3001",  # Alternative port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://localhost:8080",  # a2a-inspector
        "http://127.0.0.1:8080",
        "http://localhost:5001",  # Alternative a2a-inspector port
        "http://127.0.0.1:5001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    # Log the raw body for debugging
    try:
        body = await request.body()
        print(f"DEBUG: Validation error on {request.method} {request.url.path}")
        print(f"DEBUG: Request body: {body.decode('utf-8')}")
    except Exception as e:
        print(f"DEBUG: Could not read request body: {e}")

    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    print(f"DEBUG: Validation errors: {errors}")

    response_data = {
        "error": "Validation Error",
        "detail": "Request validation failed",
        "errors": errors,
    }

    print(f"DEBUG: Returning response: {response_data}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response_data,
    )


@app.exception_handler(DatabaseError)
async def database_exception_handler(request: Request, exc: DatabaseError):
    """Handle database errors"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Database Error",
            "detail": str(exc),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions"""
    import traceback
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred",
        },
    )


# ============================================================================
# Request Logging Middleware
# ============================================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests"""
    start_time = datetime.utcnow()

    # Process request
    response = await call_next(request)

    # Calculate processing time
    process_time = (datetime.utcnow() - start_time).total_seconds()

    # Log request
    print(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )

    # Add timing header
    response.headers["X-Process-Time"] = str(process_time)

    return response


# ============================================================================
# Routers
# ============================================================================

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(roles.router)
app.include_router(resource_shares.router)
app.include_router(notebooks.router)
app.include_router(sources.router)
app.include_router(folders.router)  # Folders and tags management
app.include_router(hana_connections.router)
app.include_router(api_connections.router)
app.include_router(mcp_servers.router)  # MCP server connections
app.include_router(mcp_oauth.router)  # MCP OAuth endpoints
app.include_router(notes.router)
app.include_router(documents.router)  # Unified documents API (notes + presentations + files)
app.include_router(database.router)
app.include_router(dashboard.router)  # Analytics dashboard
app.include_router(daily_brief.router)  # Daily brief with AI summaries
app.include_router(chat.router)
app.include_router(chat_settings.router)
app.include_router(deep_research.router)  # Deep research mode
app.include_router(source_chat.router)
app.include_router(search.router)
app.include_router(charts.router)  # Chart visualization
app.include_router(models.router)
app.include_router(embedding.router)
app.include_router(credentials.router)
app.include_router(microsites.router)
app.include_router(microsite_chat.router)  # Microsite AI chat editor
app.include_router(smtp.router)
app.include_router(files.router)  # File uploads to S3/MinIO
app.include_router(tools.router)  # Tool registry management
app.include_router(agents.router)  # Agent team management
app.include_router(agent_memory.router)  # Agent memory CRUD & search
app.include_router(agent_tools.router)  # Agent tool discovery
app.include_router(agent_skills.router)  # Agent skills management
app.include_router(agent_prompts.router)  # Agent prompt templates
app.include_router(system_prompts.router)  # System prompt templates
app.include_router(user_query_prompts.router)  # User saved query prompts
app.include_router(standalone_agents.router)  # Standalone agent execution
app.include_router(workflows.router)  # Visual workflow graphs
app.include_router(workflow_templates.router)  # Workflow templates
app.include_router(workflow_approvals.router)  # Workflow approvals
app.include_router(template_executions.router)  # Template executions
app.include_router(bookmarks.router)  # User bookmarks
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])  # Graph visualization
app.include_router(entities.router)  # LightRAG entities
app.include_router(entity_relationships.router)  # LightRAG entity relationships
app.include_router(communities.router)  # LightRAG entity communities
app.include_router(workspace_guided.router)  # Guided workspace creation wizard
app.include_router(workspace_tasks.router)  # Workspace task management
app.include_router(a2a.router)  # A2A Protocol endpoints
app.include_router(a2a_remote.router)  # A2A Remote agent management
app.include_router(autonomous_orchestration.router)  # Autonomous agent orchestration
app.include_router(workspace_templates.router)  # Workspace templates
app.include_router(orchestration_schedules.router)  # Orchestration scheduling
app.include_router(actions.router)  # Actions configuration
app.include_router(orchestration_actions.router)  # Orchestration action bindings
app.include_router(oauth.router)  # OAuth application management
app.include_router(oauth.oauth_protocol_router)  # OAuth 2.0 protocol endpoints
app.include_router(notifications.router)  # Real-time notifications
app.include_router(api_keys.router)  # API key management
app.include_router(external_notifications.router)  # External notification API
app.include_router(presentations.router)  # PowerPoint presentation generation
app.include_router(workflow_snapshots.router)  # Workflow snapshot management

# Mount public hosting router in development mode
# (In production, a standalone hosting server handles this)
from open_notebook.config import HostingConfig, DeploymentMode

_hosting_config = HostingConfig.from_env()
if _hosting_config.deployment_env == DeploymentMode.DEVELOPMENT:
    from api.routers import microsite_hosting
    app.include_router(microsite_hosting.router)


# ============================================================================
# Health Check Endpoints
# ============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "message": "Open Notebook API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/health",
    }


@app.get("/api/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint

    Returns the overall health status of the application.
    """
    try:
        # Check database connection
        db_service = get_database_service()
        db_connected = (
            db_service._current_db is not None
            and db_service._current_db.is_connected
        )

        # Try a simple query if connected
        if db_connected:
            from open_notebook.database.repository import repo_query
            await repo_query("SELECT 1 as health")
            db_status = "connected"
        else:
            db_status = "disconnected"

        # Calculate uptime
        uptime_seconds = int((datetime.utcnow() - app_start_time).total_seconds())

        # Determine overall status
        if db_connected:
            overall_status = "healthy"
        else:
            overall_status = "degraded"

        return HealthCheckResponse(
            status=overall_status,
            database=db_status,
            version="1.0.0",
            uptime_seconds=uptime_seconds,
        )

    except Exception as e:
        return HealthCheckResponse(
            status="unhealthy",
            database="error",
            version="1.0.0",
            uptime_seconds=int((datetime.utcnow() - app_start_time).total_seconds()),
        )


@app.get("/api/version")
async def get_version():
    """Get API version"""
    return {
        "version": "1.0.0",
        "api_version": "v1",
        "python_version": "3.11+",
    }


# ============================================================================
# Run Application
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=5055,
        reload=True,
        log_level="info",
    )
