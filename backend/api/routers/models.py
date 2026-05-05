"""
Models Router

Handles AI model configuration and selection.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/models",
    tags=["models"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class ModelInfo(BaseModel):
    """Information about an available AI model"""
    id: str
    name: str
    provider: str
    type: str  # language (for chat), embedding, speech_to_text, text_to_speech
    context_length: Optional[int] = None
    supports_streaming: bool = True
    supports_functions: bool = False
    credential_id: Optional[str] = None
    created: str = "2024-01-01T00:00:00Z"
    updated: str = "2024-01-01T00:00:00Z"


class ModelDefaults(BaseModel):
    """Default model selections"""
    language_model_id: Optional[str] = "gpt-4"
    embedding_model_id: Optional[str] = "text-embedding-ada-002"
    tts_model_id: Optional[str] = None
    stt_model_id: Optional[str] = None


class EmbeddingConfig(BaseModel):
    """Embedding configuration"""
    model: str = "text-embedding-ada-002"
    chunk_size: int = 1500
    chunk_overlap: int = 150
    batch_size: int = 100


class SAPAICoreConnectionRequest(BaseModel):
    """SAP AI Core connection request"""
    auth_url: str
    api_url: str
    client_id: str
    client_secret: str
    resource_group: str = "default"
    identity_zone: Optional[str] = None
    identityzoneid: Optional[str] = None


# ============================================================================
# In-Memory Storage (TODO: Move to database)
# ============================================================================

# Default configuration
_model_defaults = ModelDefaults()
_embedding_config = EmbeddingConfig()

# Available models (TODO: Load from credentials/providers)
_available_models = [
    ModelInfo(
        id="gpt-4",
        name="GPT-4",
        provider="openai",
        type="language",
        context_length=8192,
        supports_streaming=True,
        supports_functions=True
    ),
    ModelInfo(
        id="gpt-3.5-turbo",
        name="GPT-3.5 Turbo",
        provider="openai",
        type="language",
        context_length=4096,
        supports_streaming=True,
        supports_functions=True
    ),
    ModelInfo(
        id="claude-3-opus-20240229",
        name="Claude 3 Opus",
        provider="anthropic",
        type="language",
        context_length=200000,
        supports_streaming=True,
        supports_functions=True
    ),
    ModelInfo(
        id="claude-3-sonnet-20240229",
        name="Claude 3 Sonnet",
        provider="anthropic",
        type="language",
        context_length=200000,
        supports_streaming=True,
        supports_functions=True
    ),
    ModelInfo(
        id="text-embedding-ada-002",
        name="Ada 002",
        provider="openai",
        type="embedding",
        context_length=8191
    ),
    ModelInfo(
        id="text-embedding-3-small",
        name="Embedding 3 Small",
        provider="openai",
        type="embedding",
        context_length=8191
    ),
    ModelInfo(
        id="text-embedding-3-large",
        name="Embedding 3 Large",
        provider="openai",
        type="embedding",
        context_length=8191
    ),
]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=List[ModelInfo])
async def list_models(model_type: Optional[str] = None):
    """
    List available AI models from active credentials only.

    Args:
        model_type: Optional filter by type (language, embedding, etc.)

    Returns:
        List of available models from credentials only
    """
    from api.routers.credentials import _credentials_store

    models = []

    # Get models from active credentials only
    for cred_id, cred in _credentials_store.items():
        if cred.get("is_active") and cred.get("connection_status") == "connected":
            # Create model info from credential
            model = ModelInfo(
                id=cred_id,  # Use credential ID as model ID
                name=cred["model_name"],
                provider=cred["provider"],
                type=cred["model_type"],
                credential_id=cred_id,
                created=cred["created"],
                updated=cred["updated"]
            )
            models.append(model)

    # Apply type filter
    if model_type:
        models = [m for m in models if m.type == model_type]

    return models


@router.get("/defaults", response_model=ModelDefaults)
async def get_model_defaults():
    """
    Get current default model selections from database.

    Returns:
        Default model configuration
    """
    from api.services.settings import get_model_defaults as get_db_defaults
    defaults = await get_db_defaults()
    return ModelDefaults(**defaults)


@router.put("/defaults", response_model=ModelDefaults)
async def update_model_defaults(defaults: ModelDefaults):
    """
    Update default model selections in database.

    Args:
        defaults: New default model configuration

    Returns:
        Updated configuration
    """
    from api.services.settings import set_model_defaults

    # Validate that at least language model is set
    if not defaults.language_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Language model must be selected"
        )

    # Save to database
    await set_model_defaults(
        language_model_id=defaults.language_model_id,
        embedding_model_id=defaults.embedding_model_id,
        tts_model_id=defaults.tts_model_id,
        stt_model_id=defaults.stt_model_id
    )

    return defaults


@router.get("/available", response_model=List[ModelInfo])
async def get_available_models():
    """
    Get all available models from configured credentials.

    Returns:
        List of available models
    """
    return _available_models


@router.post("/{model_id}/test")
async def test_model(model_id: str, test_prompt: str = "Hello, world!"):
    """
    Test a specific model with a sample query.

    Args:
        model_id: Model ID to test
        test_prompt: Optional test prompt

    Returns:
        Test result
    """
    from api.routers.credentials import _credentials_store

    # Find model in credentials first (active models from credentials)
    credential = _credentials_store.get(model_id)
    if credential and credential.get("is_active") and credential.get("connection_status") == "connected":
        return {
            "success": True,
            "model_id": model_id,
            "model_name": credential["model_name"],
            "provider": credential["provider"],
            "message": f"Model {credential['model_name']} is available and connected"
        }

    # Fallback to static models list
    model = next((m for m in _available_models if m.id == model_id), None)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model not found: {model_id}"
        )

    # TODO: Actually test the model with Esperanto
    return {
        "success": True,
        "model_id": model_id,
        "model_name": model.name,
        "provider": model.provider,
        "message": f"Model {model.name} is available (test not implemented yet)"
    }


# ============================================================================
# Embedding Configuration Endpoints
# ============================================================================

@router.get("/embedding/config", response_model=EmbeddingConfig)
async def get_embedding_config():
    """
    Get current embedding configuration.

    Returns:
        Embedding configuration
    """
    return _embedding_config


@router.put("/embedding/config", response_model=EmbeddingConfig)
async def update_embedding_config(config: EmbeddingConfig):
    """
    Update embedding configuration.

    Args:
        config: New embedding configuration

    Returns:
        Updated configuration
    """
    global _embedding_config
    _embedding_config = config
    return _embedding_config


@router.post("/embedding/rebuild")
async def rebuild_embeddings(source_ids: Optional[List[str]] = None):
    """
    Trigger re-embedding of sources with new model/configuration.

    Args:
        source_ids: Optional list of source IDs to re-embed. If None, re-embeds all.

    Returns:
        Job status
    """
    # TODO: Implement actual re-embedding job
    count = len(source_ids) if source_ids else "all"

    return {
        "success": True,
        "message": f"Re-embedding job started for {count} sources",
        "job_id": "rebuild-001",  # TODO: Generate actual job ID
        "status": "queued"
    }


# ============================================================================
# LiteLLM Models Endpoint (Public - No Auth Required)
# ============================================================================

@router.get("/litellm/models")
async def get_litellm_models(
    base_url: Optional[str] = "http://localhost:6655/litellm/v1",
    api_key: Optional[str] = None
):
    """
    Get available models from LiteLLM proxy.

    This endpoint is public (no authentication required) to allow
    the Intelligent Workflows UI to discover available models.

    Args:
        base_url: LiteLLM endpoint URL
        api_key: Optional API key for LiteLLM

    Returns:
        List of available models from LiteLLM
    """
    import httpx

    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Query LiteLLM /models endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/models",
                headers=headers,
                timeout=10.0
            )
            response.raise_for_status()

            data = response.json()

            # Parse LiteLLM response format
            models = []
            if isinstance(data, dict) and "data" in data:
                # OpenAI-compatible format
                for model in data["data"]:
                    models.append({
                        "id": model.get("id", ""),
                        "name": model.get("id", "").replace("--", " ").replace("-", " ").title(),
                        "type": "language",  # Assume language model
                        "provider": model.get("owned_by", "unknown")
                    })
            elif isinstance(data, list):
                # Simple list format
                for model in data:
                    if isinstance(model, str):
                        models.append({
                            "id": model,
                            "name": model.replace("--", " ").replace("-", " ").title(),
                            "type": "language",
                            "provider": "litellm"
                        })
                    elif isinstance(model, dict):
                        models.append({
                            "id": model.get("id", model.get("model", "")),
                            "name": model.get("name", model.get("id", "")).replace("--", " ").replace("-", " ").title(),
                            "type": model.get("type", "language"),
                            "provider": model.get("provider", "litellm")
                        })

            return {
                "success": True,
                "base_url": base_url,
                "models": models,
                "count": len(models)
            }

    except httpx.HTTPError as e:
        # LiteLLM not available or error - return empty list
        return {
            "success": False,
            "base_url": base_url,
            "models": [],
            "count": 0,
            "error": str(e)
        }
    except Exception as e:
        # Unexpected error
        return {
            "success": False,
            "base_url": base_url,
            "models": [],
            "count": 0,
            "error": str(e)
        }


# ============================================================================
# SAP AI Core Models Endpoint (Public - No Auth Required)
# ============================================================================

@router.post("/sap-ai-core/test-connection")
async def test_sap_ai_core_connection(request: SAPAICoreConnectionRequest):
    """
    Test connection to SAP AI Core.

    Args:
        request: SAP AI Core connection parameters

    Returns:
        Connection test result
    """
    from api.services.sap_ai_core_service import create_sap_ai_core_service

    try:
        service = await create_sap_ai_core_service(
            auth_url=request.auth_url,
            api_url=request.api_url,
            client_id=request.client_id,
            client_secret=request.client_secret,
            resource_group=request.resource_group,
            identity_zone=request.identity_zone,
            identityzoneid=request.identityzoneid
        )

        result = await service.test_connection()
        return result

    except Exception as e:
        logger.error(f"SAP AI Core connection test failed: {e}")
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}"
        }


@router.post("/sap-ai-core/discover")
async def discover_sap_ai_core_models(request: SAPAICoreConnectionRequest):
    """
    Discover available models from SAP AI Core deployments.

    This endpoint is public (no authentication required) to allow
    the API Keys UI to discover available models.

    Args:
        request: SAP AI Core connection parameters

    Returns:
        List of available models from SAP AI Core
    """
    from api.services.sap_ai_core_service import create_sap_ai_core_service

    try:
        service = await create_sap_ai_core_service(
            auth_url=request.auth_url,
            api_url=request.api_url,
            client_id=request.client_id,
            client_secret=request.client_secret,
            resource_group=request.resource_group,
            identity_zone=request.identity_zone,
            identityzoneid=request.identityzoneid
        )

        # Test connection first
        test_result = await service.test_connection()
        if not test_result["success"]:
            return {
                "success": False,
                "message": test_result["message"],
                "models": [],
                "count": 0
            }

        # Discover models
        models = await service.discover_models()

        # Convert to API response format
        model_list = [
            {
                "id": m.id,
                "name": m.name,
                "deployment_id": m.deployment_id,
                "scenario_id": m.scenario_id,
                "status": m.status,
                "model_name": m.model_name,
                "model_version": m.model_version,
                "type": m.type,
                "capabilities": m.capabilities,
                "created_at": m.created_at,
                "provider": "sap_ai_core"
            }
            for m in models
        ]

        return {
            "success": True,
            "resource_group": request.resource_group,
            "models": model_list,
            "count": len(model_list)
        }

    except Exception as e:
        logger.error(f"SAP AI Core model discovery failed: {e}")
        return {
            "success": False,
            "message": f"Model discovery failed: {str(e)}",
            "models": [],
            "count": 0,
            "error": str(e)
        }

