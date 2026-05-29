"""
Shared LLM call helper.

Single source of truth for "make a chat-style call to the configured language
model". Branches on credential.provider:

- "sap_ai_core" -> POSTs to the standalone SAP AI Core API ({base}/chat),
  same contract as chat_sap_ai_core_sdk.py and data_query_agent.
- everything else -> POSTs to an OpenAI-compatible {base_url}/chat/completions
  with bearer auth, after normalizing base_url (fills in scheme, falls back
  to LITELLM_BASE_URL env or http://localhost:6655/litellm/v1).

Use this from any service that previously did `credential["base_url"]` +
httpx.post by hand. Keeps SAP AI Core deployments working under Docker
(host.docker.internal:5056) and avoids the recurring "Request URL is missing
an 'http://' or 'https://' protocol" error when base_url is null.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


def _resolve_sap_ai_core_base() -> str:
    base = os.environ.get("SAP_AI_CORE_API_URL")
    if base:
        return base.rstrip("/")
    in_docker = os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER") == "true"
    return "http://host.docker.internal:5056" if in_docker else "http://localhost:5056"


def _normalize_openai_base(base_url: Optional[str]) -> str:
    api_url = (base_url or "").strip()
    if not api_url:
        api_url = os.environ.get("LITELLM_BASE_URL", "http://localhost:6655/litellm/v1")
    if not api_url.startswith(("http://", "https://")):
        api_url = f"http://{api_url}"
    return api_url.rstrip("/")


async def resolve_llm_credential(model_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Look up the credential for the configured language model (or the given
    model_id). Raises RuntimeError if nothing is configured.
    """
    from api.routers.credentials import _credentials_store
    from api.services.settings import get_setting

    if not model_id:
        model_id = await get_setting("language_model_id", "")
    if not model_id:
        raise RuntimeError(
            "No language model configured. Please select a model in Settings -> Models."
        )

    credential = _credentials_store.get(model_id)
    if not credential:
        raise RuntimeError(f"Language model '{model_id}' not found in credentials.")

    return credential


async def call_llm_chat(
    credential: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: float = 60.0,
    extra_payload: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Send a non-streaming chat request and return the assistant message content.

    `messages` follows OpenAI chat format: [{"role": ..., "content": ...}, ...].
    `extra_payload` is merged into the request body (useful for tools/tool_choice).
    """
    message = await call_llm_chat_message(
        credential, messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        extra_payload=extra_payload,
    )
    return message.get("content") or ""


async def call_llm_chat_message(
    credential: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: float = 60.0,
    extra_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send a non-streaming chat request and return the full assistant message dict.

    Use this when you need tool_calls/role/etc., not just content. Shape matches
    OpenAI's `choices[0].message`: {"role": "assistant", "content": str|None,
    "tool_calls": [...]}.
    """
    if credential.get("provider") == "sap_ai_core":
        return await _call_sap_ai_core_message(
            credential, messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            extra_payload=extra_payload,
        )
    return await _call_openai_compat_message(
        credential, messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        extra_payload=extra_payload,
    )


async def _call_sap_ai_core(
    credential: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float,
    extra_payload: Optional[Dict[str, Any]],
) -> str:
    msg = await _call_sap_ai_core_message(
        credential, messages,
        temperature=temperature, max_tokens=max_tokens,
        timeout=timeout, extra_payload=extra_payload,
    )
    return msg.get("content") or ""


async def _call_sap_ai_core_message(
    credential: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float,
    extra_payload: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    deployment_id = credential.get("deployment_id")
    if not deployment_id:
        raise RuntimeError("SAP AI Core credential missing deployment_id")

    sdk_model_name = credential.get("model_name", "gpt-4o")
    api_base = _resolve_sap_ai_core_base()

    payload: Dict[str, Any] = {
        "messages": messages,
        "model_name": sdk_model_name,
        "deployment_id": deployment_id,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if extra_payload:
        payload.update(extra_payload)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{api_base}/chat", json=payload)
        if response.status_code != 200:
            raise RuntimeError(
                f"SAP AI Core API error: {response.status_code} - {response.text[:300]}"
            )
        result = response.json()
        # SAP AI Core proxy returns {content, tool_calls?, ...} flat. Reshape into
        # OpenAI-style assistant message so callers can treat both providers alike.
        return {
            "role": "assistant",
            "content": result.get("content"),
            "tool_calls": result.get("tool_calls") or [],
        }


async def _call_openai_compat(
    credential: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float,
    extra_payload: Optional[Dict[str, Any]],
) -> str:
    msg = await _call_openai_compat_message(
        credential, messages,
        temperature=temperature, max_tokens=max_tokens,
        timeout=timeout, extra_payload=extra_payload,
    )
    return msg.get("content") or ""


async def _call_openai_compat_message(
    credential: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    temperature: float,
    max_tokens: int,
    timeout: float,
    extra_payload: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    api_url = _normalize_openai_base(credential.get("base_url"))
    api_key = credential.get("api_key") or ""
    model_name = credential.get("model_name", credential.get("name", "gpt-4"))

    payload: Dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if extra_payload:
        payload.update(extra_payload)

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{api_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"LLM API error: {response.status_code} - {response.text[:300]}"
            )
        result = response.json()
        return result["choices"][0]["message"]


def build_langchain_chat_model(
    credential: Dict[str, Any],
    *,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
):
    """
    Build a LangChain BaseChatModel from a credential, branching on provider.

    For sap_ai_core returns a ChatSAPAICore wired to the standalone proxy
    (Docker-aware). Otherwise returns a ChatOpenAI with normalized base_url.
    Use this where existing code passes a LangChain `llm` to orchestrators
    or LangGraph agents.
    """
    if credential.get("provider") == "sap_ai_core":
        from open_notebook.llm.chat_sap_ai_core_sdk import ChatSAPAICore

        deployment_id = credential.get("deployment_id")
        if not deployment_id:
            raise RuntimeError("SAP AI Core credential missing deployment_id")
        kwargs: Dict[str, Any] = {
            "model_name": credential.get("model_name", "gpt-4o"),
            "deployment_id": deployment_id,
            "temperature": temperature,
            "api_base_url": _resolve_sap_ai_core_base(),
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return ChatSAPAICore(**kwargs)

    from langchain_openai import ChatOpenAI

    kwargs = {
        "model": credential.get("model_name", "gpt-4"),
        "api_key": credential.get("api_key") or "",
        "base_url": _normalize_openai_base(credential.get("base_url")),
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)
