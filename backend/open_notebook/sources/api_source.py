"""
API Source Sync

Handles periodic synchronization of data from API endpoints:
- Support for multiple auth types (None, Basic, Bearer, OAuth 2.0, API Key)
- OAuth 2.0 token refresh (automatic before expiry)
- JSON/XML response parsing
- JSONPath/XPath data extraction
- Hash-based change detection
- Rate limiting with exponential backoff
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from xml.etree import ElementTree

import httpx
from jsonpath_ng import parse as jsonpath_parse
from authlib.integrations.httpx_client import AsyncOAuth2Client

from open_notebook.database.repository import repo_query, repo_create, repo_update, repo_delete

logger = logging.getLogger(__name__)


class APIAuthManager:
    """Manages API authentication including OAuth 2.0 token refresh"""

    def __init__(self, source: Dict[str, Any]):
        self.source = source
        self.config = source.get("connection_config", {})
        if isinstance(self.config, str):
            self.config = json.loads(self.config)

    async def get_client(self) -> httpx.AsyncClient:
        """
        Get authenticated HTTP client

        Returns:
            Configured httpx.AsyncClient with authentication
        """
        auth_type = self.config.get("auth_type", "none")
        auth_config = self.config.get("auth_config", {})

        # Build base headers
        headers = dict(self.config.get("headers", {}))

        if auth_type == "none":
            return httpx.AsyncClient(headers=headers, timeout=30.0)

        elif auth_type == "basic":
            # Basic authentication
            auth = httpx.BasicAuth(
                auth_config["username"],
                auth_config["password"]
            )
            return httpx.AsyncClient(auth=auth, headers=headers, timeout=30.0)

        elif auth_type == "bearer":
            # Bearer token
            headers["Authorization"] = f"Bearer {auth_config['token']}"
            return httpx.AsyncClient(headers=headers, timeout=30.0)

        elif auth_type == "api_key":
            # API Key
            header_name = auth_config.get("header_name", "X-API-Key")
            prefix = auth_config.get("prefix", "")
            token = auth_config["key"]
            headers[header_name] = f"{prefix} {token}".strip() if prefix else token
            return httpx.AsyncClient(headers=headers, timeout=30.0)

        elif auth_type == "oauth2_client":
            # OAuth 2.0 Client Credentials Flow
            token = await self._get_oauth2_client_token(auth_config)
            headers["Authorization"] = f"Bearer {token}"
            return httpx.AsyncClient(headers=headers, timeout=30.0)

        elif auth_type == "oauth2_auth_code":
            # OAuth 2.0 Authorization Code Flow
            token = await self._get_oauth2_auth_code_token(auth_config)
            headers["Authorization"] = f"Bearer {token}"
            return httpx.AsyncClient(headers=headers, timeout=30.0)

        else:
            raise ValueError(f"Unsupported auth type: {auth_type}")

    async def _get_oauth2_client_token(self, auth_config: Dict[str, Any]) -> str:
        """
        Get OAuth 2.0 Client Credentials token with automatic refresh

        Args:
            auth_config: OAuth 2.0 client configuration

        Returns:
            Access token
        """
        # Check if we have a cached token
        stored_token = auth_config.get("_token")
        token_expiry = auth_config.get("_token_expiry")

        if stored_token and token_expiry:
            # Check if token is still valid (with 5 min buffer)
            expiry_time = datetime.fromisoformat(token_expiry)
            if datetime.utcnow() + timedelta(minutes=5) < expiry_time:
                logger.debug("Using cached OAuth 2.0 token")
                return stored_token

        logger.info("Requesting new OAuth 2.0 Client Credentials token")

        # Request new token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                auth_config["token_url"],
                data={
                    "grant_type": "client_credentials",
                    "client_id": auth_config["client_id"],
                    "client_secret": auth_config["client_secret"],
                    "scope": auth_config.get("scope", "")
                }
            )
            response.raise_for_status()
            token_data = response.json()

        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)

        # Store token and expiry
        expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
        auth_config["_token"] = access_token
        auth_config["_token_expiry"] = expiry_time.isoformat()

        # Update source config
        await self._update_auth_config(auth_config)

        return access_token

    async def _get_oauth2_auth_code_token(self, auth_config: Dict[str, Any]) -> str:
        """
        Get OAuth 2.0 Authorization Code token with refresh

        Args:
            auth_config: OAuth 2.0 auth code configuration

        Returns:
            Access token
        """
        # Check if we have a cached token
        stored_token = auth_config.get("_token")
        token_expiry = auth_config.get("_token_expiry")

        if stored_token and token_expiry:
            # Check if token is still valid (with 5 min buffer)
            expiry_time = datetime.fromisoformat(token_expiry)
            if datetime.utcnow() + timedelta(minutes=5) < expiry_time:
                logger.debug("Using cached OAuth 2.0 token")
                return stored_token

        # Try to refresh token if we have refresh token
        refresh_token = auth_config.get("_refresh_token")
        if refresh_token:
            try:
                logger.info("Refreshing OAuth 2.0 token")
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        auth_config["token_url"],
                        data={
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token,
                            "client_id": auth_config["client_id"],
                            "client_secret": auth_config["client_secret"]
                        }
                    )
                    response.raise_for_status()
                    token_data = response.json()

                access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                new_refresh_token = token_data.get("refresh_token", refresh_token)

                # Store tokens
                expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
                auth_config["_token"] = access_token
                auth_config["_token_expiry"] = expiry_time.isoformat()
                auth_config["_refresh_token"] = new_refresh_token

                # Update source config
                await self._update_auth_config(auth_config)

                return access_token

            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                # Fall through to require re-authorization

        # No valid token, require user authorization
        raise RuntimeError(
            "OAuth 2.0 authorization required. "
            "User must re-authorize the application."
        )

    async def _update_auth_config(self, auth_config: Dict[str, Any]):
        """Update source with new auth config"""
        self.config["auth_config"] = auth_config
        await repo_update(
            "sources",
            self.source["id"],
            {"connection_config": json.dumps(self.config)}
        )


async def sync_api_source(source: Dict[str, Any]) -> int:
    """
    Sync API source

    Args:
        source: Source record with connection_config

    Returns:
        Number of rows updated

    Process:
        1. Authenticate (with OAuth refresh if needed)
        2. Fetch data from API
        3. Parse response (JSON/XML)
        4. Extract data using JSONPath/XPath
        5. Hash-based change detection
        6. Update changed records
    """
    rows_updated = 0

    try:
        # Parse config
        config = source.get("connection_config", {})
        if isinstance(config, str):
            config = json.loads(config)

        url = config.get("url")
        method = config.get("method", "GET")
        query_params = config.get("query_params", {})
        body = config.get("body")
        json_path = config.get("json_path")
        pagination_config = config.get("pagination_config")

        if not url:
            raise ValueError("URL is required in connection_config")

        logger.info(f"Syncing API source: {url}")

        # Get authenticated client
        auth_manager = APIAuthManager(source)
        client = await auth_manager.get_client()

        try:
            # Fetch data with pagination support
            all_data = []
            page = 1
            max_pages = pagination_config.get("max_pages", 10) if pagination_config else 1

            while page <= max_pages:
                # Build request params
                params = dict(query_params)

                if pagination_config:
                    # Add pagination params
                    page_param = pagination_config.get("page_param", "page")
                    size_param = pagination_config.get("size_param", "size")
                    page_size = pagination_config.get("page_size", 100)

                    params[page_param] = page
                    params[size_param] = page_size

                # Make request with retry
                response = await _make_request_with_retry(
                    client, method, url, params, body
                )

                # Parse response
                if response.headers.get("content-type", "").startswith("application/json"):
                    data = response.json()
                elif response.headers.get("content-type", "").startswith("application/xml"):
                    data = _parse_xml_response(response.text)
                else:
                    # Treat as text
                    data = {"content": response.text}

                # Extract data using JSONPath if configured
                if json_path:
                    extracted = _extract_json_path(data, json_path)
                    if isinstance(extracted, list):
                        all_data.extend(extracted)
                    else:
                        all_data.append(extracted)
                else:
                    if isinstance(data, list):
                        all_data.extend(data)
                    else:
                        all_data.append(data)

                # Check if we have more pages
                if not pagination_config:
                    break

                # Check if response indicates more pages
                if isinstance(data, dict):
                    has_more = data.get(pagination_config.get("has_more_field", "has_more"))
                    if has_more is False:
                        break

                    # Or check if we got less than page size
                    items_field = pagination_config.get("items_field", "items")
                    items = data.get(items_field, [])
                    if len(items) < pagination_config.get("page_size", 100):
                        break

                page += 1

            logger.info(f"Retrieved {len(all_data)} items from API")

            # Process each item
            synced_ids = set()
            for idx, item in enumerate(all_data):
                try:
                    # Convert item to text
                    if isinstance(item, dict):
                        # Format dict as key: value pairs
                        text_parts = [f"{k}: {v}" for k, v in item.items()]
                        full_text = "\n".join(text_parts)
                        item_id = str(item.get("id", idx))
                    else:
                        # Use as-is
                        full_text = str(item)
                        item_id = str(idx)

                    synced_ids.add(item_id)

                    # Calculate hash
                    content_hash = hashlib.sha256(full_text.encode()).hexdigest()

                    # Create metadata
                    metadata = {
                        "source_id": source["id"],
                        "source_type": "api",
                        "api_url": url,
                        "item_id": item_id,
                        "synced_at": datetime.utcnow().isoformat(),
                        "raw_data": item if isinstance(item, dict) else {"content": item}
                    }

                    # Check if exists
                    existing = await repo_query(
                        """
                        SELECT id, content_hash
                        FROM source_embeddings
                        WHERE source_id = :source_id
                        AND metadata LIKE :item_filter
                        """,
                        {
                            "source_id": source["id"],
                            "item_filter": f'%"item_id":"{item_id}"%'
                        }
                    )

                    if existing:
                        # Check if changed
                        existing_record = existing[0]
                        if existing_record.get("content_hash") != content_hash:
                            await repo_update(
                                "source_embeddings",
                                existing_record["id"],
                                {
                                    "full_text": full_text,
                                    "content_hash": content_hash,
                                    "metadata": json.dumps(metadata),
                                    "embedding": None,
                                    "updated": datetime.utcnow().isoformat()
                                }
                            )
                            rows_updated += 1
                            logger.debug(f"Updated item {item_id}")
                    else:
                        # Create new
                        await repo_create(
                            "source_embeddings",
                            {
                                "source_id": source["id"],
                                "chunk_index": idx,
                                "full_text": full_text,
                                "content_hash": content_hash,
                                "metadata": json.dumps(metadata),
                                "embedding": None
                            }
                        )
                        rows_updated += 1
                        logger.debug(f"Created item {item_id}")

                except Exception as e:
                    logger.error(f"Failed to process item: {e}")
                    continue

            # Clean up deleted items
            all_embeddings = await repo_query(
                """
                SELECT id, metadata
                FROM source_embeddings
                WHERE source_id = :source_id
                """,
                {"source_id": source["id"]}
            )

            for emb in all_embeddings:
                try:
                    emb_metadata = json.loads(emb["metadata"]) if isinstance(emb["metadata"], str) else emb["metadata"]
                    emb_id = emb_metadata.get("item_id")

                    if emb_id and emb_id not in synced_ids:
                        await repo_delete("source_embeddings", emb["id"])
                        logger.debug(f"Deleted stale item {emb_id}")
                except Exception as e:
                    logger.error(f"Failed to check stale item: {e}")

            logger.info(f"API sync completed: {rows_updated} rows updated")

        finally:
            await client.aclose()

    except Exception as e:
        logger.error(f"API sync failed: {e}", exc_info=True)
        raise

    return rows_updated


async def _make_request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    params: Dict[str, Any],
    body: Optional[Dict[str, Any]],
    max_retries: int = 3,
    base_delay: float = 1.0
) -> httpx.Response:
    """
    Make HTTP request with exponential backoff retry

    Args:
        client: HTTP client
        method: HTTP method
        url: Request URL
        params: Query parameters
        body: Request body
        max_retries: Maximum retry attempts
        base_delay: Base delay in seconds

    Returns:
        HTTP response

    Raises:
        httpx.HTTPError: If all retries fail
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            if method == "GET":
                response = await client.get(url, params=params)
            else:  # POST
                response = await client.post(url, params=params, json=body)

            # Check for rate limiting
            if response.status_code == 429:
                # Rate limited, retry with backoff
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    delay = float(retry_after)
                else:
                    delay = base_delay * (2 ** attempt)

                logger.warning(f"Rate limited, retrying after {delay}s")
                await asyncio.sleep(delay)
                continue

            # Raise for other errors
            response.raise_for_status()
            return response

        except httpx.HTTPError as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}), retrying after {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Request failed after {max_retries} attempts")
                raise

    raise last_error


def _parse_xml_response(xml_text: str) -> Dict[str, Any]:
    """
    Parse XML response to dict

    Args:
        xml_text: XML string

    Returns:
        Dict representation
    """
    root = ElementTree.fromstring(xml_text)

    def element_to_dict(element):
        result = {}
        # Add attributes
        if element.attrib:
            result.update(element.attrib)
        # Add text content
        if element.text and element.text.strip():
            if result:
                result['_text'] = element.text.strip()
            else:
                return element.text.strip()
        # Add children
        for child in element:
            child_data = element_to_dict(child)
            if child.tag in result:
                # Multiple children with same tag
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child_data)
            else:
                result[child.tag] = child_data
        return result

    return {root.tag: element_to_dict(root)}


def _extract_json_path(data: Any, json_path: str) -> Any:
    """
    Extract data using JSONPath expression

    Args:
        data: JSON data
        json_path: JSONPath expression

    Returns:
        Extracted data
    """
    try:
        expr = jsonpath_parse(json_path)
        matches = expr.find(data)
        if not matches:
            return None
        if len(matches) == 1:
            return matches[0].value
        return [match.value for match in matches]
    except Exception as e:
        logger.error(f"JSONPath extraction failed: {e}")
        return data
