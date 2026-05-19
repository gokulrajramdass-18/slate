"""
SAP AI Core Proxy Endpoints

Proxies requests to standalone SAP AI Core API (port 5056).
No credentials needed - standalone API handles auth.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/credentials",
    tags=["credentials", "sap-ai-core"],
)

# Use environment variable or fall back to docker host (for local development)
SAP_AI_CORE_API_URL = os.getenv("SAP_AI_CORE_API_URL", "http://host.docker.internal:5056")

# Import credentials store from credentials router
from . import credentials as credentials_module


# Model name mapping - SAP AI Core deployment names to SDK model names
MODEL_NAME_MAP = {
    "gpt-5": "gpt-4o",
    "gpt-5.4": "gpt-4o",
    "gpt-4.1": "gpt-4o",
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o-2024-08-06-config": "gpt-4o",
    "gpt-realtime": "gpt-4o-realtime-preview",
    "anthropic--claude-4.7-opus": "claude-3-opus",
    "anthropic--claude-4.6-opus": "claude-3-opus",
    "anthropic--claude-4.5-opus": "claude-3-opus",
    "anthropic--claude-4.6-sonnet": "claude-3-sonnet",
    "anthropic--claude-4.5-sonnet": "claude-3-5-sonnet",
    "anthropic--claude-4-sonnet": "claude-3-sonnet",
    "anthropic--claude-4.5-haiku": "claude-3-haiku",
    "gemini-2.5-pro": "gemini-pro",
    "gemini-2.5-flash": "gemini-flash",
    "gemini-2.5-flash-lite": "gemini-flash",
    "gemini-3.1-flash-lite": "gemini-flash",
}


def get_sdk_model_name(deployment_model_name: str) -> str:
    """Convert SAP AI Core model name to SDK-compatible model name"""
    if deployment_model_name in MODEL_NAME_MAP:
        return MODEL_NAME_MAP[deployment_model_name]

    for key, value in MODEL_NAME_MAP.items():
        if deployment_model_name.startswith(key):
            return value

    # For unknown models, return the deployment name itself
    # This allows the SDK to try to use it directly
    logger.info(f"Unknown model '{deployment_model_name}', using deployment name as-is")
    return deployment_model_name


class SAPAICoreImportResponse(BaseModel):
    """SAP AI Core import response"""
    success: bool
    message: str
    imported_count: int
    models: list
    errors: list


@router.post("/import-sap-ai-core-auto", response_model=SAPAICoreImportResponse)
async def import_sap_ai_core_models_auto():
    """
    Discover and import SAP AI Core models from standalone API.
    No credentials required - uses standalone API's configured credentials.
    """
    import aiosqlite

    try:
        logger.info("[SAP AI Core Auto Import] Starting discovery via standalone API...")

        # Call standalone API discovery endpoint
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{SAP_AI_CORE_API_URL}/discover")
            response.raise_for_status()
            result = response.json()

        if not result.get("success"):
            logger.error(f"[SAP AI Core Auto Import] Discovery failed: {result.get('message')}")
            return SAPAICoreImportResponse(
                success=False,
                message=result.get("message", "Discovery failed"),
                imported_count=0,
                models=[],
                errors=[{"error": result.get("message", "Unknown error")}]
            )

        models = result.get("models", [])
        logger.info(f"[SAP AI Core Auto Import] Discovered {len(models)} deployments")

        # Filter deployments - accept RUNNING or UNKNOWN status
        # UNKNOWN means the SDK couldn't determine status, but deployment exists
        valid_models = [m for m in models if m.get("status") in ["RUNNING", "UNKNOWN"]]
        logger.info(f"[SAP AI Core Auto Import] Found {len(valid_models)} valid deployments")

        if not valid_models:
            return SAPAICoreImportResponse(
                success=True,
                message="No valid deployments found",
                imported_count=0,
                models=[],
                errors=[]
            )

        # Import to credentials store (shared with main credentials router)
        imported = []
        errors = []

        for model in valid_models:
            try:
                deployment_id = model.get("deployment_id")
                model_name = model.get("name", "unknown")

                # Check for duplicates in the global store
                existing = next(
                    (c for c in credentials_module._credentials_store.values()
                     if c.get("provider") == "sap_ai_core" and c.get("deployment_id") == deployment_id),
                    None
                )

                if existing:
                    logger.info(f"[SAP AI Core Auto Import] Skipping duplicate: {deployment_id}")
                    continue

                # Get SDK-compatible model name
                sdk_model_name = get_sdk_model_name(model_name)

                logger.info(f"[SAP AI Core Auto Import] Mapping {model_name} -> {sdk_model_name}")

                # Create credential
                credential_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()

                # Determine model type based on deployment name
                deployment_lower = model_name.lower()
                if any(pattern in deployment_lower for pattern in [
                    "embedding", "text-embedding", "ada-002", "ada",
                    "embedding-3", "embed-", "gemini-embedding"
                ]):
                    model_type = "embedding"
                else:
                    model_type = "language"

                credential_data = {
                    "id": credential_id,
                    "name": f"SAP AI Core - {model_name}",
                    "provider": "sap_ai_core",
                    "model_name": sdk_model_name,
                    "deployment_model_name": model_name,  # Store original deployment model name
                    "model_type": model_type,
                    "deployment_id": deployment_id,
                    "api_key": "",  # Not needed - stored in standalone API
                    "base_url": None,
                    "is_active": True,
                    "connection_status": "connected",
                    "last_tested": now,
                    "created": now,
                    "updated": now
                }

                # Add to global credentials store
                credentials_module._credentials_store[credential_id] = credential_data

                imported.append({
                    "id": credential_id,
                    "name": f"SAP AI Core - {model_name}",
                    "deployment_id": deployment_id,
                    "model_type": "language",
                    "sdk_model_name": sdk_model_name
                })

                logger.info(f"[SAP AI Core Auto Import] Imported: {model_name} ({deployment_id})")

            except Exception as e:
                logger.error(f"[SAP AI Core Auto Import] Failed to import {model.get('name')}: {e}")
                errors.append({
                    "model": model.get("name"),
                    "deployment_id": model.get("deployment_id"),
                    "error": str(e)
                })

        # Save all credentials to file using the shared save function
        credentials_module._save_credentials()

        logger.info(f"[SAP AI Core Auto Import] Saved {len(imported)} credentials")

        message = f"Successfully imported {len(imported)} models from SAP AI Core"
        if errors:
            message += f" ({len(errors)} failed)"

        return SAPAICoreImportResponse(
            success=True,
            message=message,
            imported_count=len(imported),
            models=imported,
            errors=errors
        )

    except httpx.HTTPError as e:
        logger.error(f"[SAP AI Core Auto Import] HTTP error: {e}")
        return SAPAICoreImportResponse(
            success=False,
            message=f"Failed to connect to SAP AI Core API: {str(e)}",
            imported_count=0,
            models=[],
            errors=[{"error": str(e)}]
        )
    except Exception as e:
        logger.error(f"[SAP AI Core Auto Import] Import failed: {e}", exc_info=True)
        return SAPAICoreImportResponse(
            success=False,
            message=f"Import failed: {str(e)}",
            imported_count=0,
            models=[],
            errors=[{"error": str(e)}]
        )
