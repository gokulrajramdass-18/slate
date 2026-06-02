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

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# Bounded retry policy for transient upstream failures.
#
# We retry only on signals that strongly suggest the *next* attempt has a
# real chance of succeeding without changing inputs:
#   - HTTP 5xx (server-side blips, including the OpenAI `server_error`
#     SAP AI Core relays as 500)
#   - HTTP 429 (rate-limit; backoff is the protocol-level remedy)
#   - httpx connect errors / connect timeouts / protocol drops (network
#     jitter; safe because the request never reached the server)
# We do NOT retry 4xx other than 429 (those are caller-fixable bugs),
# successful responses with bad bodies (changing nothing won't help), or
# `httpx.ReadTimeout` (the request reached the server and may already be
# processing — retries on a non-idempotent LLM call would duplicate work
# and waste tokens).
#
# Different providers warrant different aggressiveness:
#
# - SAP AI Core: the OpenAI SDK *inside* the proxy already retries 5xx
#   internally (we set max_retries=0 on the proxy client to disable that
#   behaviour, but if/when that's reverted, we don't want the backend
#   layering its own retries on top). 1 attempt here means: if the
#   upstream returns 500 once, surface it to the user — no silent
#   ~30-60s wait stacking SDK retries × backend retries.
# - OpenAI-compat (LiteLLM, OpenAI direct, Anthropic via proxy): the
#   helper makes raw httpx calls with no SDK in between, so a single
#   genuinely-transient blip benefits from one retry. Keep this small.
#
# Total worst-case extra wait stays under ~2 s so the user isn't kept
# waiting on a truly dead upstream.
_LLM_RETRY_ATTEMPTS_SAP_AI_CORE = 1                # no retries; SDK does its own
_LLM_RETRY_ATTEMPTS_OPENAI_COMPAT = 2              # 1 initial + 1 retry
_LLM_RETRY_BACKOFFS = (1.5,)                       # seconds between attempts
_LLM_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def _retryable_status(status: int) -> bool:
    return status in _LLM_RETRYABLE_STATUSES


def _retryable_exception(exc: BaseException) -> bool:
    """
    True for transport-layer transient errors worth retrying.

    Notably we do NOT include `httpx.ReadTimeout`. A read timeout means
    the request *did* reach the server and may already be processing —
    LLM calls are non-idempotent (each retry consumes tokens and may
    return a different answer), and the SAP AI Core proxy in particular
    has been observed to keep generating after the client gives up. So
    we let read timeouts surface to the caller; they should bump the
    per-attempt timeout instead.

    Connect errors / connect timeouts / protocol drops mean the request
    never landed, so retrying them is safe.
    """
    return isinstance(
        exc,
        (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.RemoteProtocolError,
        ),
    )


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

    last_error: Optional[str] = None
    attempts = _LLM_RETRY_ATTEMPTS_SAP_AI_CORE
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(f"{api_base}/chat", json=payload)
            except Exception as exc:
                # Transport-layer error (timeout, connection drop). Retry
                # if it's the kind we expect to be transient; otherwise
                # bubble up immediately so we don't mask programmer bugs.
                if _retryable_exception(exc) and attempt < attempts - 1:
                    delay = _LLM_RETRY_BACKOFFS[attempt]
                    logger.warning(
                        "SAP AI Core transport error (attempt %d/%d): %s — "
                        "retrying in %.1fs",
                        attempt + 1, attempts, exc, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            if response.status_code == 200:
                result = response.json()
                # SAP AI Core proxy returns {content, tool_calls?, ...} flat.
                # Reshape into OpenAI-style assistant message so callers can
                # treat both providers alike.
                return {
                    "role": "assistant",
                    "content": result.get("content"),
                    "tool_calls": result.get("tool_calls") or [],
                }

            # Non-200. Retry only on transient statuses (5xx, 429); 4xx
            # other than 429 mean we sent something the proxy/upstream
            # rejects, and retrying won't help.
            last_error = (
                f"SAP AI Core API error: {response.status_code} - "
                f"{response.text[:300]}"
            )
            if (
                _retryable_status(response.status_code)
                and attempt < attempts - 1
            ):
                delay = _LLM_RETRY_BACKOFFS[attempt]
                logger.warning(
                    "SAP AI Core %d (attempt %d/%d) — retrying in %.1fs: %s",
                    response.status_code, attempt + 1, attempts,
                    delay, response.text[:300],
                )
                await asyncio.sleep(delay)
                continue
            raise RuntimeError(last_error)

    # Loop exhausted only if every attempt was a retryable failure.
    raise RuntimeError(last_error or "SAP AI Core API error: unknown")


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

    last_error: Optional[str] = None
    attempts = _LLM_RETRY_ATTEMPTS_OPENAI_COMPAT
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(attempts):
            try:
                response = await client.post(
                    f"{api_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            except Exception as exc:
                if _retryable_exception(exc) and attempt < attempts - 1:
                    delay = _LLM_RETRY_BACKOFFS[attempt]
                    logger.warning(
                        "LLM transport error (attempt %d/%d): %s — "
                        "retrying in %.1fs",
                        attempt + 1, attempts, exc, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]

            last_error = (
                f"LLM API error: {response.status_code} - "
                f"{response.text[:300]}"
            )
            if (
                _retryable_status(response.status_code)
                and attempt < attempts - 1
            ):
                delay = _LLM_RETRY_BACKOFFS[attempt]
                logger.warning(
                    "LLM %d (attempt %d/%d) — retrying in %.1fs: %s",
                    response.status_code, attempt + 1, attempts,
                    delay, response.text[:300],
                )
                await asyncio.sleep(delay)
                continue
            raise RuntimeError(last_error)

    raise RuntimeError(last_error or "LLM API error: unknown")


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
