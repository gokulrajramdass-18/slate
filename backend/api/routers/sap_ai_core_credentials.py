"""
SAP AI Core Credentials Import - FIXED VERSION

This version properly stores credentials in the new database schema columns.
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

    FIXED VERSION: Properly stores credentials in database schema columns
    instead of JSON in api_key field.

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

                    # Create credential - FIXED: Use schema columns instead of JSON
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
                        f"sap-ai-core-{model.deployment_id}",  # Model name with prefix
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
                        "model_type": model.type
                    })

                    logger.info(
                        f"[SAP AI Core Import] Imported: {model.name} "
                        f"({model.deployment_id}, type={model.type})"
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
