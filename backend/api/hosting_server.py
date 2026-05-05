"""
Standalone Microsite Hosting Server (Production Mode)

A minimal FastAPI application dedicated to serving published microsites.
In production, this runs as a separate process/container from the main API,
allowing independent scaling and isolation of public traffic.

Usage:
    uvicorn api.hosting_server:app --host 0.0.0.0 --port 5056 --workers 4

Or via the startup script:
    ./scripts/start-hosting.sh
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.microsite_hosting import router as hosting_router
from open_notebook.config import HostingConfig
from open_notebook.database.repository import init_database
from api.services.database_service import get_database_service


# ============================================================================
# Application lifecycle
# ============================================================================

app_start_time = datetime.utcnow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown for the hosting server."""
    print("Starting Microsite Hosting Server...")

    try:
        # Initialize database (read-only serving needs DB access)
        db_instance = await init_database()
        db_service = get_database_service()
        db_service.set_database(db_instance)
        print("Database connection established")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise

    print("Hosting server ready")
    yield

    # Shutdown
    print("Shutting down Hosting Server...")
    db_service = get_database_service()
    if db_service._current_db:
        await db_service._current_db.disconnect()
    print("Hosting server stopped")


# ============================================================================
# Application setup
# ============================================================================

app = FastAPI(
    title="Open Notebook Microsite Hosting",
    description="Public microsite serving (production mode)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,      # No Swagger UI for public hosting
    redoc_url=None,      # No ReDoc for public hosting
    openapi_url=None,    # No OpenAPI spec for public hosting
)

# CORS: permissive for public hosting (read-only GET endpoints)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)

# Mount the hosting router
app.include_router(hosting_router)


# ============================================================================
# Health check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check for load balancers and container orchestration."""
    uptime_seconds = int((datetime.utcnow() - app_start_time).total_seconds())
    return {
        "status": "healthy",
        "service": "microsite-hosting",
        "uptime_seconds": uptime_seconds,
    }


# ============================================================================
# Entrypoint
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    config = HostingConfig.from_env()
    uvicorn.run(
        "api.hosting_server:app",
        host=config.hosting_host,
        port=config.hosting_port,
        log_level="info",
    )
