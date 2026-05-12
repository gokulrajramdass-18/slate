"""
Observability Settings Router

Admin-only endpoints for configuring MLFlow and Langfuse observability providers.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/admin/observability",
    tags=["admin", "observability"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class LangfuseConfig(BaseModel):
    """Langfuse observability configuration"""
    enabled: bool = False
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"


class MLFlowConfig(BaseModel):
    """MLFlow observability configuration"""
    enabled: bool = False
    tracking_uri: str = "http://mlflow:5000"
    experiment_name: str = "slate-agents"
    username: str = ""
    password: str = ""


class ObservabilityOptions(BaseModel):
    """Common observability options"""
    trace_level: str = "info"
    log_llm_calls: bool = True
    log_tool_calls: bool = True
    log_agent_steps: bool = True


class ObservabilityConfig(BaseModel):
    """Complete observability configuration"""
    provider: str = "none"  # "none", "langfuse", "mlflow", "both"
    langfuse: LangfuseConfig = LangfuseConfig()
    mlflow: MLFlowConfig = MLFlowConfig()
    options: ObservabilityOptions = ObservabilityOptions()


class ObservabilityConfigUpdate(BaseModel):
    """Update observability configuration (partial)"""
    provider: Optional[str] = None
    langfuse: Optional[LangfuseConfig] = None
    mlflow: Optional[MLFlowConfig] = None
    options: Optional[ObservabilityOptions] = None


class ConnectionTestRequest(BaseModel):
    """Request to test provider connection"""
    provider: str  # "langfuse" or "mlflow"


class ConnectionTestResponse(BaseModel):
    """Response from connection test"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class ProviderStatus(BaseModel):
    """Status of a single observability provider"""
    enabled: bool
    connected: bool
    tracking_uri: Optional[str] = None
    experiment_name: Optional[str] = None
    last_trace_at: Optional[str] = None
    last_run_at: Optional[str] = None
    total_traces: Optional[int] = None
    total_runs: Optional[int] = None
    storage_size_mb: Optional[float] = None
    error: Optional[str] = None


class ObservabilityStatusResponse(BaseModel):
    """Status of all observability providers"""
    langfuse: ProviderStatus
    mlflow: ProviderStatus


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/settings", response_model=ObservabilityConfig)
async def get_observability_settings():
    """
    Get current observability configuration.

    Secrets (secret_key, password) are masked with *** for security.

    Returns:
        Observability configuration with masked secrets
    """
    from api.services.settings import get_observability_config_masked

    config = await get_observability_config_masked()

    return ObservabilityConfig(
        provider=config["provider"],
        langfuse=LangfuseConfig(**config["langfuse"]),
        mlflow=MLFlowConfig(**config["mlflow"]),
        options=ObservabilityOptions(**config["options"])
    )


@router.put("/settings", response_model=ObservabilityConfig)
async def update_observability_settings(updates: ObservabilityConfigUpdate):
    """
    Update observability configuration.

    Secrets will be encrypted before storing in database.
    If secrets are masked (***), they won't be updated.

    Args:
        updates: Observability configuration to update

    Returns:
        Updated observability configuration (secrets masked)
    """
    from api.services.settings import set_observability_config, get_observability_config_masked

    # Convert to dict for settings service
    update_dict = {}

    if updates.provider is not None:
        update_dict["provider"] = updates.provider

    if updates.langfuse is not None:
        update_dict["langfuse"] = updates.langfuse.model_dump()

    if updates.mlflow is not None:
        update_dict["mlflow"] = updates.mlflow.model_dump()

    if updates.options is not None:
        update_dict["options"] = updates.options.model_dump()

    # Save to database (encrypts secrets)
    await set_observability_config(update_dict)

    # Return updated config (masked)
    config = await get_observability_config_masked()

    return ObservabilityConfig(
        provider=config["provider"],
        langfuse=LangfuseConfig(**config["langfuse"]),
        mlflow=MLFlowConfig(**config["mlflow"]),
        options=ObservabilityOptions(**config["options"])
    )


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_provider_connection(request: ConnectionTestRequest):
    """
    Test connection to an observability provider.

    Args:
        request: Provider to test ("langfuse" or "mlflow")

    Returns:
        Test result with success status and message
    """
    from api.services.settings import get_observability_config

    provider = request.provider.lower()

    if provider not in ["langfuse", "mlflow"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider: {provider}. Must be 'langfuse' or 'mlflow'"
        )

    # Get configuration
    config = await get_observability_config()

    if provider == "langfuse":
        # Test Langfuse connection
        from api.services.observability_service import get_langfuse_service

        service = get_langfuse_service()

        if not service.is_enabled():
            return ConnectionTestResponse(
                success=False,
                message="Langfuse is not enabled or keys are missing",
                details=config["langfuse"]
            )

        try:
            # Try to create a test trace
            trace_id = service.create_trace(
                session_id="connection-test",
                notebook_id="test",
                metadata={"test": True}
            )

            if trace_id:
                return ConnectionTestResponse(
                    success=True,
                    message="Successfully connected to Langfuse",
                    details={"trace_id": trace_id, "host": config["langfuse"]["host"]}
                )
            else:
                return ConnectionTestResponse(
                    success=False,
                    message="Failed to create test trace",
                    details=config["langfuse"]
                )

        except Exception as e:
            return ConnectionTestResponse(
                success=False,
                message=f"Connection failed: {str(e)}",
                details=config["langfuse"]
            )

    elif provider == "mlflow":
        # Test MLFlow connection
        from api.services.mlflow_service import get_mlflow_service

        service = get_mlflow_service()

        if not service.is_enabled():
            return ConnectionTestResponse(
                success=False,
                message="MLFlow is not enabled or tracking URI is invalid",
                details=config["mlflow"]
            )

        try:
            # Get MLFlow status
            status_info = await service.get_status()

            if status_info["connected"]:
                return ConnectionTestResponse(
                    success=True,
                    message="Successfully connected to MLFlow",
                    details=status_info
                )
            else:
                return ConnectionTestResponse(
                    success=False,
                    message=status_info.get("error", "Connection failed"),
                    details=status_info
                )

        except Exception as e:
            return ConnectionTestResponse(
                success=False,
                message=f"Connection failed: {str(e)}",
                details=config["mlflow"]
            )


@router.get("/status", response_model=ObservabilityStatusResponse)
async def get_observability_status():
    """
    Get real-time status of all observability providers.

    Returns:
        Status with connection state, last trace info, storage stats
    """
    from api.services.observability_service import get_langfuse_service
    from api.services.mlflow_service import get_mlflow_service

    # Get Langfuse status
    langfuse_service = get_langfuse_service()
    langfuse_status = ProviderStatus(
        enabled=langfuse_service.is_enabled(),
        connected=langfuse_service.is_enabled(),
        error=None if langfuse_service.is_enabled() else "Langfuse is disabled or not configured"
    )

    # Get MLFlow status
    mlflow_service = get_mlflow_service()
    mlflow_info = await mlflow_service.get_status()

    mlflow_status = ProviderStatus(
        enabled=mlflow_info["enabled"],
        connected=mlflow_info["connected"],
        tracking_uri=mlflow_info.get("tracking_uri"),
        experiment_name=mlflow_info.get("experiment_name"),
        last_run_at=mlflow_info.get("last_run_at"),
        total_runs=mlflow_info.get("total_runs"),
        error=mlflow_info.get("error")
    )

    return ObservabilityStatusResponse(
        langfuse=langfuse_status,
        mlflow=mlflow_status
    )
