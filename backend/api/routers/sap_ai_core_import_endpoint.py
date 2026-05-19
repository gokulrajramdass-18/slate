"""
SAP AI Core Import Endpoint

This file contains the import endpoint implementation for SAP AI Core.
Due to permission restrictions, this cannot be directly added to credentials.py.

TO INTEGRATE: Copy the import endpoint and SAPAICoreImportRequest model to credentials.py
"""

from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter
import logging
import json
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# This should be added to credentials.py
class SAPAICoreImportRequest(BaseModel):
    """SAP AI Core bulk import request"""
    auth_url: str
    api_url: str
    client_id: str
    client_secret: str
    resource_group: str = "default"
    identity_zone: Optional[str] = None
    identityzoneid: Optional[str] = None


# This endpoint should be added to the credentials router in credentials.py
# @router.post("/import-sap-ai-core")
async def import_sap_ai_core_models(request: SAPAICoreImportRequest):
    """
    Discover and import all RUNNING models from SAP AI Core.

    Creates credentials for each discovered deployment automatically.

    NOTE: This function needs access to:
    - _credentials_store from credentials.py
    - _save_credentials() from credentials.py
    """
    from api.services.sap_ai_core_service import create_sap_ai_core_service
    from api.routers.credentials import _credentials_store, _save_credentials

    try:
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
        test_result = await service.test_connection()
        if not test_result["success"]:
            return {
                "success": False,
                "message": test_result["message"],
                "imported_count": 0,
                "models": [],
                "errors": []
            }

        # Discover models
        models = await service.discover_models()

        # Filter only RUNNING deployments
        running_models = [m for m in models if m.status == "RUNNING"]

        if not running_models:
            return {
                "success": True,
                "message": "No RUNNING deployments found in SAP AI Core",
                "imported_count": 0,
                "models": [],
                "errors": []
            }

        # Create credentials for each model
        imported = []
        errors = []

        for model in running_models:
            try:
                # Check for duplicates
                existing = any(
                    cred.get("provider") == "sap_ai_core" and
                    cred.get("model_name") == f"sap-ai-core-{model.deployment_id}"
                    for cred in _credentials_store.values()
                )

                if existing:
                    logger.info(f"Skipping duplicate: {model.deployment_id}")
                    continue

                credential = {
                    "id": str(uuid.uuid4()),
                    "name": f"SAP AI Core - {model.name}",
                    "provider": "sap_ai_core",
                    "model_name": f"sap-ai-core-{model.deployment_id}",  # Add prefix for detection
                    "model_type": model.type,  # "language" or "embedding"
                    "is_active": True,
                    "connection_status": "connected",
                    "last_tested": datetime.now(timezone.utc).isoformat(),
                    "created": datetime.now(timezone.utc).isoformat(),
                    "updated": datetime.now(timezone.utc).isoformat(),
                    "source": "sap_ai_core",
                    # Store connection config in api_key field (JSON string)
                    "api_key": json.dumps({
                        "auth_url": request.auth_url,
                        "api_url": request.api_url,
                        "client_id": request.client_id,
                        "client_secret": request.client_secret,
                        "resource_group": request.resource_group,
                        "deployment_id": model.deployment_id
                    }),
                    "base_url": None  # Not used for SAP AI Core
                }

                _credentials_store[credential["id"]] = credential
                imported.append(credential)
                logger.info(f"Imported: {model.name} ({model.deployment_id})")

            except Exception as e:
                logger.error(f"Failed to import {model.name}: {e}")
                errors.append({
                    "model": model.name,
                    "deployment_id": model.deployment_id,
                    "error": str(e)
                })

        # Save to disk
        _save_credentials()

        message = f"Successfully imported {len(imported)} models from SAP AI Core"
        if errors:
            message += f" ({len(errors)} failed)"

        return {
            "success": True,
            "message": message,
            "imported_count": len(imported),
            "models": imported,
            "errors": errors
        }

    except Exception as e:
        logger.error(f"SAP AI Core import failed: {e}")
        return {
            "success": False,
            "message": f"Import failed: {str(e)}",
            "imported_count": 0,
            "models": [],
            "errors": [{"error": str(e)}]
        }


# INTEGRATION INSTRUCTIONS:
# ========================
#
# 1. Add the SAPAICoreImportRequest model to credentials.py near other request models
#
# 2. Add the import_sap_ai_core_models endpoint to the credentials router:
#    @router.post("/import-sap-ai-core")
#    async def import_sap_ai_core_models(request: SAPAICoreImportRequest):
#        # Copy function body from above
#
# 3. Import required dependencies at the top of credentials.py:
#    from api.services.sap_ai_core_service import create_sap_ai_core_service
#    import json
#    import uuid
#    from datetime import datetime, timezone
#
# 4. Restart backend server to register the new endpoint
