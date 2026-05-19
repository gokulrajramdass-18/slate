"""
SAP AI Core Credentials Import - SDK Compatible Version

Stores credentials with SDK-compatible model names (gpt-4o, claude-3-sonnet, etc.)
instead of deployment IDs.
"""

import logging
import uuid
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/credentials",
    tags=["credentials", "sap-ai-core"],
)


# Model name mapping from SAP AI Core model names to SDK model names
MODEL_NAME_MAP = {
    # GPT models
    "gpt-5": "gpt-4o",
    "gpt-5.4": "gpt-4o",
    "gpt-4.1": "gpt-4o",
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-realtime": "gpt-4o",

    # Claude models
    "anthropic--claude-4.7-opus": "claude-3-opus",
    "anthropic--claude-4.6-opus": "claude-3-opus",
    "anthropic--claude-4.5-opus": "claude-3-opus",
    "anthropic--claude-4.6-sonnet": "claude-3-sonnet",
    "anthropic--claude-4.5-sonnet": "claude-3-5-sonnet",
    "anthropic--claude-4-sonnet": "claude-3-sonnet",
    "anthropic--claude-4.5-haiku": "claude-3-haiku",

    # Gemini models
    "gemini-2.5-pro": "gemini-pro",
    "gemini-2.5-flash": "gemini-flash",
    "gemini-2.5-flash-lite": "gemini-flash",
    "gemini-3.1-flash-lite": "gemini-flash",

    # O3 models
    "o3": "gpt-4o",
    "o3-mini": "gpt-4o",

    # Amazon models
    "amazon--nova-lite": "gpt-4o",
}


def get_sdk_model_name(deployment_model_name: str) -> str:
    """
    Convert SAP AI Core model name to SDK-compatible model name.

    Args:
        deployment_model_name: Model name from deployment (e.g., "anthropic--claude-4.7-opus")

    Returns:
        SDK-compatible model name (e.g., "claude-3-opus")
    """
    # Try exact match first
    if deployment_model_name in MODEL_NAME_MAP:
        return MODEL_NAME_MAP[deployment_model_name]

    # Try prefix matching
    for key, value in MODEL_NAME_MAP.items():
        if deployment_model_name.startswith(key):
            return value

    # Default to gpt-4o for unknown models
    logger.warning(f"Unknown model '{deployment_model_name}', defaulting to gpt-4o")
    return "gpt-4o"


# ============================================================================
# Request/Response Models
# ============================================================================

class SAPAICoreImportRequest(BaseModel):
    """SAP AI Core bulk import request"""
    auth_url: str
    api_url: str
    client_id: str
    client_secret: str
    resource_group: str = "default"
    identity_zone: Optional[str] = None
    identityzoneid: Optional[str] = None


class SAPAICoreImportResponse(BaseModel):
    """SAP AI Core bulk import response"""
    success: bool
    message: str
    imported_count: int
    models: list
    errors: list


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/import-sap-ai-core", response_model=SAPAICoreImportResponse)
async def import_sap_ai_core_models(request: SAPAICoreImportRequest):
    """
    Discover and import all RUNNING models from SAP AI Core.

    Stores credentials with SDK-compatible model names for use with gen-ai-hub SDK.

    Args:
        request: SAP AI Core connection parameters

    Returns:
        Import results with count of imported models and any errors
    """
    from api.services.sap_ai_core_service import create_sap_ai_core_service
    import aiosqlite

    try:
        logger.info("[SAP AI Core Import] Starting bulk import...")

        # Create service
        service = await create_sap_ai_core_service(
            auth_url=request.auth_url,
            api_url=request.api_url,
            client_id=request.client_id,
            client_secret=request.client_secret,
            resource_group=request.resource_group,
            identity_zone=request.identity_zone,
            identityzoneid=request.identityzoneid
        )

        # Test connection
        logger.info("[SAP AI Core Import] Testing connection...")
        test_result = await service.test_connection()
        if not test_result["success"]:
            logger.error(f"[SAP AI Core Import] Connection test failed: {test_result['message']}")
            return SAPAICoreImportResponse(
                success=False,
                message=test_result["message"],
                imported_count=0,
                models=[],
                errors=[{"error": test_result["message"]}]
            )

        logger.info("[SAP AI Core Import] Connection successful, discovering models...")

        # Discover models
        models = await service.discover_models()
        logger.info(f"[SAP AI Core Import] Discovered {len(models)} total deployments")

        # Filter only RUNNING deployments
        running_models = [m for m in models if m.status == "RUNNING"]
        logger.info(f"[SAP AI Core Import] Found {len(running_models)} RUNNING deployments")

        if not running_models:
            return SAPAICoreImportResponse(
                success=True,
                message="No RUNNING deployments found in SAP AI Core",
                imported_count=0,
                models=[],
                errors=[]
            )

        # Create credentials for each model using database
        imported = []
        errors = []

        # Connect to database
        db_path = "data/database.db"
        async with aiosqlite.connect(db_path) as db:
            for model in running_models:
                try:
                    # Check for duplicates
                    cursor = await db.execute(
                        "SELECT id FROM credentials WHERE provider = 'sap_ai_core' AND deployment_id = ?",
                        (model.deployment_id,)
                    )
                    existing = await cursor.fetchone()

                    if existing:
                        logger.info(f"[SAP AI Core Import] Skipping duplicate: {model.deployment_id}")
                        continue

                    # Get SDK-compatible model name
                    sdk_model_name = get_sdk_model_name(model.name)

                    logger.info(
                        f"[SAP AI Core Import] Mapping {model.name} -> {sdk_model_name}"
                    )

                    # Debug: Log model type before insert
                    logger.info(
                        f"[SAP AI Core Import] DEBUG - Model: {model.name}, "
                        f"Type: {model.type}, "
                        f"Deployment: {model.deployment_id}"
                    )

                    # Create credential with SDK model name
                    credential_id = str(uuid.uuid4())
                    now = datetime.now(timezone.utc).isoformat()

                    await db.execute("""
                        INSERT INTO credentials (
                            id, name, provider, model_name, model_type,
                            auth_url, api_url, client_id, client_secret_encrypted,
                            resource_group, deployment_id,
                            identity_zone, identityzoneid,
                            is_active, connection_status, last_tested,
                            created, updated, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        credential_id,
                        f"SAP AI Core - {model.name}",
                        "sap_ai_core",
                        sdk_model_name,  # Store SDK model name instead of deployment ID
                        model.type,  # "language" or "embedding"
                        request.auth_url,
                        request.api_url,
                        request.client_id,
                        request.client_secret,  # TODO: Encrypt in production
                        request.resource_group,
                        model.deployment_id,
                        request.identity_zone,
                        request.identityzoneid,
                        1,  # is_active
                        "connected",
                        now,
                        now,
                        now,
                        "sap_ai_core"
                    ))

                    imported.append({
                        "id": credential_id,
                        "name": f"SAP AI Core - {model.name}",
                        "deployment_id": model.deployment_id,
                        "model_type": model.type,
                        "sdk_model_name": sdk_model_name
                    })

                    logger.info(
                        f"[SAP AI Core Import] Imported: {model.name} "
                        f"({model.deployment_id}, sdk_name={sdk_model_name}, type={model.type})"
                    )

                except Exception as e:
                    logger.error(f"[SAP AI Core Import] Failed to import {model.name}: {e}")
                    errors.append({
                        "model": model.name,
                        "deployment_id": model.deployment_id,
                        "error": str(e)
                    })

            # Commit changes
            await db.commit()

        logger.info(f"[SAP AI Core Import] Saved {len(imported)} credentials to database")

        # Build response message
        message = f"Successfully imported {len(imported)} models from SAP AI Core"
        if errors:
            message += f" ({len(errors)} failed)"

        logger.info(f"[SAP AI Core Import] Complete: {message}")

        return SAPAICoreImportResponse(
            success=True,
            message=message,
            imported_count=len(imported),
            models=imported,
            errors=errors
        )

    except Exception as e:
        logger.error(f"[SAP AI Core Import] Bulk import failed: {e}", exc_info=True)
        return SAPAICoreImportResponse(
            success=False,
            message=f"Import failed: {str(e)}",
            imported_count=0,
            models=[],
            errors=[{"error": str(e)}]
        )


@router.post("/import-sap-ai-core-auto", response_model=SAPAICoreImportResponse)
async def import_sap_ai_core_models_auto():
    """
    Automatically import all RUNNING models from SAP AI Core using environment variables.
    
    This endpoint reads SAP AI Core credentials from environment variables
    and imports all available models automatically.
    
    Returns:
        Import results with count of imported models and any errors
    """
    import os
    
    try:
        # Get credentials from environment
        auth_url = os.getenv("AICORE_AUTH_URL")
        api_url = os.getenv("AICORE_BASE_URL")
        client_id = os.getenv("AICORE_CLIENT_ID")
        client_secret = os.getenv("AICORE_CLIENT_SECRET")
        resource_group = os.getenv("AICORE_RESOURCE_GROUP", "default")
        
        # Check if credentials are configured
        if not all([auth_url, api_url, client_id, client_secret]):
            return SAPAICoreImportResponse(
                success=False,
                message="SAP AI Core credentials not configured in environment",
                imported_count=0,
                models=[],
                errors=[{"error": "Missing environment variables"}]
            )
        
        logger.info("[SAP AI Core Auto Import] Using credentials from environment")
        
        # Create request object
        request = SAPAICoreImportRequest(
            auth_url=auth_url,
            api_url=api_url,
            client_id=client_id,
            client_secret=client_secret,
            resource_group=resource_group
        )
        
        # Call the main import function
        return await import_sap_ai_core_models(request)
        
    except Exception as e:
        logger.error(f"[SAP AI Core Auto Import] Failed: {e}")
        return SAPAICoreImportResponse(
            success=False,
            message=f"Auto import failed: {str(e)}",
            imported_count=0,
            models=[],
            errors=[{"error": str(e)}]
        )
