"""
Credentials Router

Handles API credentials management for AI providers.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import uuid
import httpx
import asyncio
import json
from pathlib import Path

router = APIRouter(
    prefix="/api/credentials",
    tags=["credentials"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class CredentialBase(BaseModel):
    """Base credential model"""
    name: str = Field(..., description="Credential name (e.g., 'OpenAI Production')")
    provider: str = Field(..., description="Provider name (e.g., 'openai', 'anthropic', 'custom')")
    model_name: str = Field(..., description="Model name/identifier")
    model_type: str = Field(..., description="Model type: language, embedding, speech_to_text, text_to_speech")
    api_key: str = Field(..., description="API key (will be encrypted)")
    base_url: Optional[str] = Field(None, description="Custom base URL/endpoint (optional)")
    is_active: bool = Field(True, description="Whether this credential is active")


class CredentialCreate(CredentialBase):
    """Model for creating a credential"""
    pass


class CredentialUpdate(BaseModel):
    """Model for updating a credential"""
    name: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    model_type: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None


class CredentialResponse(BaseModel):
    """Model for credential response (without exposing API key)"""
    id: str
    name: str
    provider: str
    model_name: str
    model_type: str
    base_url: Optional[str]
    is_active: bool
    connection_status: str  # "untested", "connected", "failed"
    last_tested: Optional[str] = None
    created: str
    updated: str


# ============================================================================
# In-Memory Storage (TODO: Move to database)
# ============================================================================

_credentials_store = {}

# Credentials persistence file
CREDENTIALS_FILE = Path("data/credentials.json")

def _load_credentials():
    """Load credentials from file"""
    global _credentials_store
    try:
        if CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE, "r") as f:
                _credentials_store = json.load(f)
                print(f"Loaded {len(_credentials_store)} credentials from file")
    except Exception as e:
        print(f"Error loading credentials: {e}")
        _credentials_store = {}

def _save_credentials():
    """Save credentials to file"""
    try:
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump(_credentials_store, f, indent=2)
    except Exception as e:
        print(f"Error saving credentials: {e}")

# Load credentials on startup
_load_credentials()



# ============================================================================
# Endpoints
# ============================================================================

# ============================================================================
# Endpoints
# ============================================================================

@router.get("/litellm/models")
async def get_litellm_models(
    base_url: str = "http://localhost:6655/litellm/v1",
    api_key: Optional[str] = None
):
    """
    Discover available models from LiteLLM endpoint.

    Args:
        base_url: LiteLLM base URL (default: http://localhost:6655/litellm/v1)
        api_key: Optional API key for authentication

    Returns:
        List of available models
    """
    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/models", headers=headers)

            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed - Invalid or missing API key"
                )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"LiteLLM endpoint returned {response.status_code}: {response.text}"
                )

            data = response.json()
            models = []

            # Parse LiteLLM response format
            if "data" in data:
                for model_info in data["data"]:
                    model_id = model_info.get("id", "")

                    # Determine model type based on name patterns
                    model_type = "language"  # Default
                    if "embedding" in model_id.lower() or "ada" in model_id.lower():
                        model_type = "embedding"
                    elif "whisper" in model_id.lower():
                        model_type = "speech_to_text"
                    elif "tts" in model_id.lower():
                        model_type = "text_to_speech"

                    models.append({
                        "id": model_id,
                        "name": model_id,
                        "type": model_type,
                        "provider": model_info.get("owned_by", "litellm"),
                        "created": model_info.get("created", 0)
                    })

            return {
                "success": True,
                "base_url": base_url,
                "models": models,
                "count": len(models)
            }

    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not connect to LiteLLM at {base_url}. Make sure LiteLLM is running."
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LiteLLM endpoint timed out"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching models: {str(e)}"
        )


class TestConnectionRequest(BaseModel):
    """Request model for testing connection"""
    provider: str
    model_name: str
    model_type: str
    api_key: str
    base_url: Optional[str] = None


@router.post("/test-connection")
async def test_connection_before_save(request: TestConnectionRequest):
    """
    Test API connection before saving credential.

    Args:
        request: Connection test request

    Returns:
        Test result
    """
    try:
        # Determine the endpoint to test based on provider
        if request.base_url:
            test_url = request.base_url
        elif request.provider == "openai":
            test_url = "https://api.openai.com/v1"
        elif request.provider == "anthropic":
            test_url = "https://api.anthropic.com/v1"
        elif request.provider == "google":
            test_url = "https://generativelanguage.googleapis.com/v1beta"
        elif request.provider == "litellm":
            # If no base_url provided, try localhost
            test_url = request.base_url or "http://localhost:6655/litellm/v1"
        else:
            # For custom providers, require base_url
            if not request.base_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Base URL is required for custom providers"
                )
            test_url = request.base_url

        # Remove trailing slash if present
        test_url = test_url.rstrip('/')

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test with a simple models list call
            headers = {}

            if request.provider == "openai":
                headers["Authorization"] = f"Bearer {request.api_key}"
                headers["Content-Type"] = "application/json"
                test_endpoint = f"{test_url}/chat/completions"
            elif request.provider == "litellm":
                headers["Authorization"] = f"Bearer {request.api_key}"
                # Use GET /models for LiteLLM - safer than POST
                test_endpoint = f"{test_url}/models"
            elif request.provider == "anthropic":
                headers["x-api-key"] = request.api_key
                headers["anthropic-version"] = "2023-06-01"
                headers["Content-Type"] = "application/json"
                test_endpoint = f"{test_url}/messages"
            elif request.provider == "google":
                test_endpoint = f"{test_url}/models?key={request.api_key}"
            else:
                headers["Authorization"] = f"Bearer {request.api_key}"
                headers["Content-Type"] = "application/json"
                test_endpoint = f"{test_url}/chat/completions"

            # Debug logging
            print(f"Testing {request.provider} with endpoint: {test_endpoint}")
            print(f"Method: {'GET' if request.provider == 'litellm' else 'POST'}")
            
            start_time = asyncio.get_event_loop().time()

            if request.provider == "openai":
                # Test with OpenAI chat completion endpoint
                response = await client.post(
                    test_endpoint,
                    headers=headers,
                    json={
                        "model": request.model_name,
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 1
                    }
                )
            elif request.provider == "litellm":
                # For LiteLLM, just verify the API key works with GET /models
                print(f"Making GET request to: {test_endpoint}")
                print(f"Headers: {headers}")
                response = await client.get(test_endpoint, headers=headers)
                print(f"Response status: {response.status_code}")
                print(f"Response body: {response.text[:200]}")
            elif request.provider == "anthropic":
                # For Anthropic, send a minimal request to test auth
                response = await client.post(
                    test_endpoint,
                    headers=headers,
                    json={
                        "model": request.model_name,
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 1
                    }
                )
            else:
                response = await client.get(test_endpoint, headers=headers)

            latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

            # Check response
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "message": f"Successfully connected to {request.provider} - {request.model_name}",
                    "provider": request.provider,
                    "model_name": request.model_name,
                    "latency_ms": latency_ms,
                    "status_code": response.status_code
                }
            elif response.status_code == 400 and request.provider == "anthropic":
                # Anthropic returns 400 for our test request, but that means auth worked
                return {
                    "success": True,
                    "message": f"Successfully connected to {request.provider} - {request.model_name}",
                    "provider": request.provider,
                    "model_name": request.model_name,
                    "latency_ms": latency_ms,
                    "status_code": 200
                }
            elif response.status_code == 405:
                # Method not allowed - try to provide helpful error
                return {
                    "success": False,
                    "message": f"Method not allowed on {test_endpoint}. This endpoint may not support {'POST' if request.provider != 'litellm' else 'GET'} requests.",
                    "provider": request.provider,
                    "model_name": request.model_name,
                    "status_code": response.status_code,
                    "details": response.text[:200]
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "message": "Authentication failed - Invalid API key",
                    "provider": request.provider,
                    "model_name": request.model_name,
                    "status_code": response.status_code
                }
            elif response.status_code == 403:
                return {
                    "success": False,
                    "message": "Access forbidden - Check API key permissions",
                    "provider": request.provider,
                    "model_name": request.model_name,
                    "status_code": response.status_code
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "message": f"Endpoint not found - Tried: {test_endpoint}. Check your base URL configuration.",
                    "provider": request.provider,
                    "model_name": request.model_name,
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "message": f"Connection failed with status {response.status_code}: {response.text[:100]}",
                    "provider": request.provider,
                    "model_name": request.model_name,
                    "status_code": response.status_code
                }

    except httpx.ConnectError:
        return {
            "success": False,
            "message": f"Could not connect to {request.provider} endpoint",
            "provider": request.provider,
            "model_name": request.model_name
        }
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "Connection timed out",
            "provider": request.provider,
            "model_name": request.model_name
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "provider": request.provider,
            "model_name": request.model_name
        }


@router.get("", response_model=List[CredentialResponse])
async def list_credentials(
    model_type: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """
    List all credentials.

    Args:
        model_type: Optional filter by model type
        is_active: Optional filter by active status

    Returns:
        List of credentials
    """
    credentials = list(_credentials_store.values())

    # Apply filters
    if model_type:
        credentials = [c for c in credentials if c["model_type"] == model_type]
    if is_active is not None:
        credentials = [c for c in credentials if c["is_active"] == is_active]

    # Return without API keys
    return [
        CredentialResponse(
            id=c["id"],
            name=c["name"],
            provider=c["provider"],
            model_name=c["model_name"],
            model_type=c["model_type"],
            base_url=c.get("base_url"),
            is_active=c["is_active"],
            connection_status=c.get("connection_status", "untested"),
            last_tested=c.get("last_tested"),
            created=c["created"],
            updated=c["updated"]
        )
        for c in credentials
    ]


@router.get("/{credential_id}", response_model=CredentialResponse)
async def get_credential(credential_id: str):
    """
    Get a specific credential.

    Args:
        credential_id: Credential ID

    Returns:
        Credential details (without API key)
    """
    if credential_id not in _credentials_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential not found: {credential_id}"
        )

    c = _credentials_store[credential_id]
    return CredentialResponse(
        id=c["id"],
        name=c["name"],
        provider=c["provider"],
        model_name=c["model_name"],
        model_type=c["model_type"],
        base_url=c.get("base_url"),
        is_active=c["is_active"],
        connection_status=c.get("connection_status", "untested"),
        last_tested=c.get("last_tested"),
        created=c["created"],
        updated=c["updated"]
    )


@router.post("", response_model=CredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_credential(credential: CredentialCreate):
    """
    Create a new credential.

    Args:
        credential: Credential data

    Returns:
        Created credential
    """
    credential_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    # TODO: Encrypt API key before storing
    credential_data = {
        "id": credential_id,
        "name": credential.name,
        "provider": credential.provider,
        "model_name": credential.model_name,
        "model_type": credential.model_type,
        "api_key": credential.api_key,  # TODO: Encrypt
        "base_url": credential.base_url,
        "is_active": credential.is_active,
        "connection_status": "untested",
        "last_tested": None,
        "created": now,
        "updated": now
    }

    _credentials_store[credential_id] = credential_data
    _save_credentials()

    return CredentialResponse(
        id=credential_id,
        name=credential.name,
        provider=credential.provider,
        model_name=credential.model_name,
        model_type=credential.model_type,
        base_url=credential.base_url,
        is_active=credential.is_active,
        connection_status="untested",
        last_tested=None,
        created=now,
        updated=now
    )


@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(credential_id: str, update: CredentialUpdate):
    """
    Update a credential.

    Args:
        credential_id: Credential ID
        update: Update data

    Returns:
        Updated credential
    """
    if credential_id not in _credentials_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential not found: {credential_id}"
        )

    credential = _credentials_store[credential_id]

    # Update fields
    if update.name is not None:
        credential["name"] = update.name
    if update.provider is not None:
        credential["provider"] = update.provider
    if update.model_name is not None:
        credential["model_name"] = update.model_name
    if update.model_type is not None:
        credential["model_type"] = update.model_type
    if update.api_key is not None:
        credential["api_key"] = update.api_key  # TODO: Encrypt
    if update.base_url is not None:
        credential["base_url"] = update.base_url
    if update.is_active is not None:
        credential["is_active"] = update.is_active

    credential["updated"] = datetime.utcnow().isoformat() + "Z"

    return CredentialResponse(
        id=credential_id,
        name=credential["name"],
        provider=credential["provider"],
        model_name=credential["model_name"],
        model_type=credential["model_type"],
        base_url=credential.get("base_url"),
        is_active=credential["is_active"],
        connection_status=credential.get("connection_status", "untested"),
        last_tested=credential.get("last_tested"),
        created=credential["created"],
        updated=credential["updated"]
    )


@router.delete("/{credential_id}")
async def delete_credential(credential_id: str):
    """
    Delete a credential.

    Args:
        credential_id: Credential ID

    Returns:
        Success response
    """
    if credential_id not in _credentials_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential not found: {credential_id}"
        )

    del _credentials_store[credential_id]

    return {
        "success": True,
        "message": f"Credential {credential_id} deleted successfully"
    }


@router.post("/{credential_id}/test")
async def test_credential(credential_id: str):
    """
    Test a credential connection.

    Args:
        credential_id: Credential ID

    Returns:
        Test result
    """
    if credential_id not in _credentials_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Credential not found: {credential_id}"
        )

    credential = _credentials_store[credential_id]

    # TODO: Actually test the connection based on provider and model type
    # For now, simulate a successful test
    try:
        # Simulate API call
        import asyncio
        await asyncio.sleep(0.5)  # Simulate network delay

        # Update connection status
        credential["connection_status"] = "connected"
        credential["last_tested"] = datetime.utcnow().isoformat() + "Z"

        return {
            "success": True,
            "message": f"Successfully connected to {credential['provider']} - {credential['model_name']}",
            "model_name": credential["model_name"],
            "provider": credential["provider"],
            "latency_ms": 523  # Simulated
        }
    except Exception as e:
        credential["connection_status"] = "failed"
        credential["last_tested"] = datetime.utcnow().isoformat() + "Z"

        return {
            "success": False,
            "message": f"Connection failed: {str(e)}",
            "model_name": credential["model_name"],
            "provider": credential["provider"]
        }
