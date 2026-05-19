"""
SAP AI Core Service

Handles discovery and integration with SAP AI Core deployments.
Uses the gen-ai-hub SDK for model discovery and inference.
"""

import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import httpx
import logging

logger = logging.getLogger(__name__)


@dataclass
@dataclass
class SAPAICoreConfig:
    """SAP AI Core connection configuration"""
    auth_url: str
    api_url: str
    client_id: str
    client_secret: str
    resource_group: str = "default"
    identity_zone: Optional[str] = None
    identityzoneid: Optional[str] = None


@dataclass
class SAPAICoreModel:
    """SAP AI Core model information"""
    id: str
    name: str
    deployment_id: str
    scenario_id: str
    execution_id: Optional[str]
    status: str
    model_name: str
    model_version: Optional[str]
    created_at: Optional[str]
    capabilities: List[str]
    type: str  # language, embedding, etc.


class SAPAICoreService:
    """Service for interacting with SAP AI Core"""

    def __init__(self, config: SAPAICoreConfig):
        self.config = config
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def _get_access_token(self) -> str:
        """Get OAuth 2.0 access token from SAP AI Core"""
        if self._access_token and self._token_expires_at:
            # Check if token is still valid (with 5 minute buffer)
            from datetime import timedelta
            if datetime.now() < self._token_expires_at - timedelta(minutes=5):
                return self._access_token

        # Normalize auth URL - ensure it ends with /oauth/token
        auth_url = self.config.auth_url.rstrip('/')
        if not auth_url.endswith('/oauth/token'):
            auth_url = f"{auth_url}/oauth/token"

        # Request new token
        logger.info(f"[SAPAICore] Requesting OAuth token from: {auth_url}")
        logger.info(f"[SAPAICore] Client ID: {self.config.client_id[:15]}... (length: {len(self.config.client_id)})")
        logger.info(f"[SAPAICore] Client Secret: ****** (length: {len(self.config.client_secret)})")
        logger.info(f"[SAPAICore] Resource Group: {self.config.resource_group}")

        async with httpx.AsyncClient(follow_redirects=False) as client:
            # Try method 1: Form-encoded body (most common for OAuth)
            token_data = {
                "grant_type": "client_credentials",
                "client_id": self.config.client_id.strip(),  # Strip any whitespace
                "client_secret": self.config.client_secret.strip(),
            }

            try:
                logger.info("[SAPAICore] Attempting OAuth with form-encoded credentials...")
                response = await client.post(
                    auth_url,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )

                if response.status_code == 401:
                    # Try method 2: Basic Auth header (alternative method)
                    logger.info("[SAPAICore] Form auth failed, trying Basic Auth...")
                    import base64
                    credentials = f"{self.config.client_id.strip()}:{self.config.client_secret.strip()}"
                    encoded_credentials = base64.b64encode(credentials.encode()).decode()

                    response = await client.post(
                        auth_url,
                        data={"grant_type": "client_credentials"},
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Authorization": f"Basic {encoded_credentials}"
                        },
                        timeout=30.0,
                    )

                if response.status_code == 302:
                    logger.error(f"[SAPAICore] Got redirect (302) - wrong OAuth URL or credentials")
                    logger.error(f"[SAPAICore] Redirect location: {response.headers.get('location')}")
                    raise Exception(f"OAuth endpoint returned redirect. Check the authentication URL and credentials.")

                response.raise_for_status()
                data = response.json()

                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                from datetime import timedelta
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

                logger.info(f"[SAPAICore] OAuth token obtained successfully, expires in {expires_in}s")
                return self._access_token

            except httpx.HTTPStatusError as e:
                logger.error(f"[SAPAICore] OAuth request failed: {e.response.status_code}")
                logger.error(f"[SAPAICore] Response body: {e.response.text}")
                logger.error(f"[SAPAICore] Request URL: {auth_url}")

                # Provide helpful error messages
                if "invalid_client" in e.response.text:
                    error_msg = "Invalid client credentials. Please verify:\n"
                    error_msg += "1. Client ID is correct (should start with 'sb-' or similar)\n"
                    error_msg += "2. Client Secret is correct (copy exactly without spaces)\n"
                    error_msg += "3. OAuth URL is correct (should end with /oauth/token)\n"
                    error_msg += f"4. Current OAuth URL: {auth_url}"
                    raise Exception(error_msg)

                raise Exception(f"OAuth authentication failed: {e.response.text}")
            except Exception as e:
                logger.error(f"[SAPAICore] OAuth request error: {str(e)}")
                raise

    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to SAP AI Core"""
        try:
            logger.info("[SAPAICore] Testing connection...")
            token = await self._get_access_token()
            logger.info("[SAPAICore] OAuth token obtained successfully")

            # Test API access by listing deployments
            async with httpx.AsyncClient() as client:
                # Ensure api_url doesn't have trailing slash
                api_base = self.config.api_url.rstrip('/')
                # Add /v2 prefix if not already present
                if not api_base.endswith('/v2'):
                    api_base = f"{api_base}/v2"

                deployments_url = f"{api_base}/lm/deployments"
                logger.info(f"[SAPAICore] Testing API access at: {deployments_url}")

                response = await client.get(
                    deployments_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "AI-Resource-Group": self.config.resource_group,
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                logger.info("[SAPAICore] Connection test successful")

            return {
                "success": True,
                "message": "Successfully connected to SAP AI Core",
                "resource_group": self.config.resource_group,
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"SAP AI Core connection test failed: {e}")
            return {
                "success": False,
                "message": f"HTTP error: {e.response.status_code} - {e.response.text}",
            }
        except Exception as e:
            logger.error(f"SAP AI Core connection test failed: {e}")
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}",
            }

    async def discover_models(self) -> List[SAPAICoreModel]:
        """
        Discover available models from SAP AI Core deployments.

        Returns models from:
        1. Active deployments
        2. Available model configurations
        """
        try:
            logger.info("[SAPAICore] Discovering models...")
            token = await self._get_access_token()
            models = []

            async with httpx.AsyncClient() as client:
                # Ensure api_url doesn't have trailing slash
                api_base = self.config.api_url.rstrip('/')
                # Add /v2 prefix if not already present
                if not api_base.endswith('/v2'):
                    api_base = f"{api_base}/v2"

                deployments_url = f"{api_base}/lm/deployments"
                logger.info(f"[SAPAICore] Fetching deployments from: {deployments_url}")

                # Get deployments
                response = await client.get(
                    deployments_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "AI-Resource-Group": self.config.resource_group,
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                deployments_data = response.json()
                logger.info(f"[SAPAICore] Found {len(deployments_data.get('resources', []))} deployments")

                # Parse deployments
                for deployment in deployments_data.get("resources", []):
                    deployment_id = deployment.get("id")
                    status = deployment.get("status")
                    scenario_id = deployment.get("scenarioId") or deployment.get("scenario_id")
                    configuration_name = deployment.get("configurationName") or deployment.get("configuration_name", "Unknown")
                    executable_id = deployment.get("executableId") or deployment.get("executable_id")

                    # Log deployment details for debugging
                    logger.info(f"[SAPAICore] Processing deployment: id={deployment_id}, "
                              f"configurationName={configuration_name}, "
                              f"scenarioId={scenario_id}, "
                              f"status={status}, "
                              f"executableId={executable_id}")

                    # Extract model info from deployment details
                    details = deployment.get("details", {})
                    model_name = details.get("model", configuration_name)
                    model_version = details.get("modelVersion")

                    # Use configuration name as the display name (this is what users see in BTP)
                    display_name = configuration_name if configuration_name != "Unknown" else deployment_id

                    # Determine capabilities from scenario or deployment
                    capabilities = self._parse_capabilities(deployment)
                    # Pass configuration_name to help determine type from deployment name
                    model_type = self._determine_model_type(scenario_id, capabilities, configuration_name)

                    model = SAPAICoreModel(
                        id=f"sap-ai-core-{deployment_id}",
                        name=display_name,  # Use configuration name
                        deployment_id=deployment_id,
                        scenario_id=scenario_id or "unknown",
                        execution_id=executable_id,
                        status=status or "UNKNOWN",
                        model_name=model_name,
                        model_version=model_version,
                        created_at=deployment.get("createdAt") or deployment.get("created_at"),
                        capabilities=capabilities,
                        type=model_type,
                    )
                    models.append(model)
                    logger.info(f"[SAPAICore] Added model: {display_name} (type: {model_type})")

            logger.info(f"[SAPAICore] Successfully discovered {len(models)} models")
            return models

        except Exception as e:
            logger.error(f"Failed to discover SAP AI Core models: {e}")
            raise

    def _parse_capabilities(self, deployment: Dict[str, Any]) -> List[str]:
        """Parse capabilities from deployment metadata"""
        capabilities = []

        # Check scenario ID for capability hints
        scenario_id = deployment.get("scenarioId", "").lower()
        if "chat" in scenario_id or "completion" in scenario_id:
            capabilities.append("chat")
        if "embedding" in scenario_id:
            capabilities.append("embeddings")
        if "stream" in scenario_id:
            capabilities.append("streaming")
        if "function" in scenario_id or "tool" in scenario_id:
            capabilities.append("function_calling")

        # Check deployment details for more hints
        details = deployment.get("details", {})
        if details.get("streaming", False):
            capabilities.append("streaming")
        if details.get("functionCalling", False):
            capabilities.append("function_calling")

        return list(set(capabilities)) if capabilities else ["chat"]

    def _determine_model_type(self, scenario_id: str, capabilities: List[str], deployment_name: str = "") -> str:
        """Determine model type from scenario, capabilities, and deployment name"""
        scenario_lower = (scenario_id or "").lower()
        deployment_lower = (deployment_name or "").lower()

        logger.info(f"[SAPAICore] Determining model type: scenario_id='{scenario_id}', deployment_name='{deployment_name}', capabilities={capabilities}")

        # Check deployment name first (most reliable for SAP AI Core)
        # Check for common embedding model patterns
        embedding_patterns = [
            "embedding",
            "text-embedding",
            "ada-002",           # OpenAI text-embedding-ada-002
            "ada",               # Short form
            "embedding-3",       # OpenAI text-embedding-3-small/large
            "embed-",            # Common prefix
        ]

        if any(pattern in deployment_lower for pattern in embedding_patterns):
            logger.info(f"[SAPAICore] Detected embedding model from deployment name: '{deployment_name}'")
            return "embedding"

        # Check scenario ID
        if "embedding" in scenario_lower or "embeddings" in capabilities:
            logger.info(f"[SAPAICore] Detected embedding model from scenario/capabilities")
            return "embedding"
        elif "speech" in scenario_lower or "tts" in scenario_lower or "text-to-speech" in deployment_lower:
            return "text_to_speech"
        elif "transcription" in scenario_lower or "stt" in scenario_lower or "speech-to-text" in deployment_lower:
            return "speech_to_text"
        else:
            logger.info(f"[SAPAICore] Defaulting to language model")
            return "language"

    async def get_deployment_details(self, deployment_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific deployment"""
        try:
            token = await self._get_access_token()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.config.api_url}/lm/deployments/{deployment_id}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "AI-Resource-Group": self.config.resource_group,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"Failed to get deployment details: {e}")
            raise

    async def invoke_model(
        self,
        deployment_id: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke a deployed model for inference (non-streaming).

        Args:
            deployment_id: SAP AI Core deployment ID
            messages: Chat messages in OpenAI format
            **kwargs: Additional model parameters (temperature, max_tokens, etc.)

        Returns:
            Model response in OpenAI-compatible format
        """
        try:
            token = await self._get_access_token()
            logger.info(f"[SAPAICore] Invoke request - Deployment: {deployment_id}")
            logger.info(f"[SAPAICore] Invoke request - Resource Group: {self.config.resource_group}")
            logger.info(f"[SAPAICore] Invoke request - Token (first 20 chars): {token[:20]}...")

            # Build request payload (ensure stream is False)
            payload = {
                "messages": messages,
                **kwargs
            }
            # Explicitly disable streaming for this method
            payload["stream"] = False

            # Ensure api_url doesn't have trailing slash and has /v2
            api_base = self.config.api_url.rstrip('/')
            if not api_base.endswith('/v2'):
                api_base = f"{api_base}/v2"

            url = f"{api_base}/inference/deployments/{deployment_id}/chat"
            logger.info(f"[SAPAICore] Invoke request - URL: {url}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "AI-Resource-Group": self.config.resource_group,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120.0,
                )
                logger.info(f"[SAPAICore] Invoke response status: {response.status_code}")
                if response.status_code != 200:
                    logger.error(f"[SAPAICore] Error response: {response.text}")
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"Failed to invoke model: {e}")
            raise

    async def stream_model(
        self,
        deployment_id: str,
        messages: List[Dict[str, str]],
        **kwargs
    ):
        """
        Stream responses from a deployed model.

        Args:
            deployment_id: SAP AI Core deployment ID
            messages: Chat messages in OpenAI format
            **kwargs: Additional model parameters (temperature, max_tokens, etc.)

        Yields:
            Server-Sent Event chunks in format: "data: {json}"
        """
        try:
            token = await self._get_access_token()
            logger.info(f"[SAPAICore] Stream request - Deployment: {deployment_id}")
            logger.info(f"[SAPAICore] Stream request - Resource Group: {self.config.resource_group}")
            logger.info(f"[SAPAICore] Stream request - Token (first 20 chars): {token[:20]}...")

            # Build request payload with streaming enabled
            payload = {
                "messages": messages,
                **kwargs
            }
            payload["stream"] = True

            # Ensure api_url doesn't have trailing slash and has /v2
            api_base = self.config.api_url.rstrip('/')
            if not api_base.endswith('/v2'):
                api_base = f"{api_base}/v2"

            url = f"{api_base}/inference/deployments/{deployment_id}/chat"
            logger.info(f"[SAPAICore] Stream request - URL: {url}")

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "AI-Resource-Group": self.config.resource_group,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120.0,
                ) as response:
                    logger.info(f"[SAPAICore] Stream response status: {response.status_code}")
                    if response.status_code != 200:
                        response_text = await response.aread()
                        logger.error(f"[SAPAICore] Error response: {response_text.decode()}")
                    response.raise_for_status()

                    # Stream SSE (Server-Sent Events) chunks
                    async for line in response.aiter_lines():
                        if line:
                            yield line

        except Exception as e:
            logger.error(f"Failed to stream model: {e}")
            raise

    async def check_model_capabilities(self, deployment_id: str) -> Dict[str, bool]:
        """
        Check capabilities of a specific model deployment.

        Args:
            deployment_id: SAP AI Core deployment ID

        Returns:
            Dict with capability flags:
            - supports_function_calling: Whether model supports function/tool calls
            - supports_streaming: Whether model supports streaming responses
        """
        try:
            details = await self.get_deployment_details(deployment_id)

            scenario_id = (details.get("scenarioId") or "").lower()
            details_obj = details.get("details", {})

            # Check for function calling support
            supports_function_calling = (
                "function" in scenario_id or
                "tool" in scenario_id or
                details_obj.get("functionCalling", False) or
                details_obj.get("function_calling", False)
            )

            # Check for streaming support (default to True)
            supports_streaming = (
                "stream" in scenario_id or
                details_obj.get("streaming", True)
            )

            logger.info(
                f"[SAPAICore] Deployment {deployment_id} capabilities: "
                f"function_calling={supports_function_calling}, "
                f"streaming={supports_streaming}"
            )

            return {
                "supports_function_calling": supports_function_calling,
                "supports_streaming": supports_streaming,
            }

        except Exception as e:
            logger.warning(
                f"[SAPAICore] Failed to check capabilities for {deployment_id}: {e}"
            )
            # Return safe defaults
            return {
                "supports_function_calling": False,
                "supports_streaming": True,
            }


async def create_sap_ai_core_service(
    auth_url: str,
    api_url: str,
    client_id: str,
    client_secret: str,
    resource_group: str = "default",
    identity_zone: str = None,
    identityzoneid: str = None
) -> SAPAICoreService:
    """Factory function to create SAP AI Core service"""
    config = SAPAICoreConfig(
        auth_url=auth_url,
        api_url=api_url,
        client_id=client_id,
        client_secret=client_secret,
        resource_group=resource_group,
        identity_zone=identity_zone,
        identityzoneid=identityzoneid
    )
    return SAPAICoreService(config)
