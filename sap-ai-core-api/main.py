"""
Standalone SAP AI Core API using gen-ai-hub SDK
Isolated from main application to avoid dependency conflicts

Supports OpenAI-compatible function calling: forwards messages, tools, and
tool_choice verbatim to gen_ai_hub.proxy.native.openai. Streams NDJSON events
so the LangChain wrapper can faithfully reconstruct AIMessageChunks with
ToolCallChunks.
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="SAP AI Core API")


class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    model_name: str = "gpt-5.4"
    deployment_id: str
    stream: bool = False
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    temperature: float = 0.7
    max_tokens: int = 4096


class ChatResponse(BaseModel):
    content: str
    tool_calls: List[Dict[str, Any]] = []
    finish_reason: Optional[str] = None
    deployment_id: str


class DiscoveryResponse(BaseModel):
    success: bool
    models: list
    message: str = ""


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list
    model: str
    usage: dict


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/discover")
async def discover_models():
    """
    Discover all available SAP AI Core deployments.
    Uses credentials from .env file.
    """
    try:
        from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client

        proxy_client = get_proxy_client("gen-ai-hub")
        deployments = proxy_client.get_deployments()

        models = []
        for deployment in deployments:
            models.append({
                "deployment_id": deployment.deployment_id,
                "name": deployment.model_name,
                "status": deployment.status if hasattr(deployment, 'status') else "UNKNOWN",
                "scenario_id": deployment.scenario_id if hasattr(deployment, 'scenario_id') else None,
            })

        return DiscoveryResponse(
            success=True,
            models=models,
            message=f"Found {len(models)} deployments"
        )
    except Exception as e:
        return DiscoveryResponse(
            success=False,
            models=[],
            message=f"Discovery failed: {str(e)}"
        )


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    OpenAI-compatible chat completion via gen-ai-hub SDK.

    Forwards `messages`, `tools`, and `tool_choice` straight through to the
    OpenAI-compatible client. Model is pinned to gpt-5.4 and the deployment
    selection is left to the env-configured proxy client (request.model_name
    and request.deployment_id are accepted but not forwarded for now).
    """
    from gen_ai_hub.proxy.native.openai import OpenAI

    default_model = "gpt-5.4"

    print(f"[Chat] deployment={request.deployment_id} model_requested={request.model_name} -> using {default_model}")
    print(f"[Chat] messages={len(request.messages)} tools={len(request.tools) if request.tools else 0} stream={request.stream}")

    client = OpenAI()

    create_kwargs: Dict[str, Any] = {
        "model": default_model,
        "messages": request.messages,
        "temperature": request.temperature,
    }
    # Note: max_completion_tokens not supported by gen-ai-hub SDK 4.12.4
    # Omit it to use model defaults
    if request.tools:
        create_kwargs["tools"] = request.tools
    if request.tool_choice is not None:
        create_kwargs["tool_choice"] = request.tool_choice

    if request.stream:
        async def generate():
            try:
                stream = await asyncio.to_thread(
                    client.chat.completions.create,
                    stream=True,
                    **create_kwargs,
                )

                def _next(it):
                    try:
                        return next(it)
                    except StopIteration:
                        return None

                iterator = iter(stream)
                chunk_count = 0
                final_finish_reason: Optional[str] = None

                while True:
                    chunk = await asyncio.to_thread(_next, iterator)
                    if chunk is None:
                        break
                    if not chunk.choices:
                        continue

                    choice = chunk.choices[0]
                    delta = choice.delta

                    content = getattr(delta, "content", None)
                    if content:
                        chunk_count += 1
                        yield json.dumps({"type": "content_delta", "content": content}) + "\n"

                    tool_call_deltas = getattr(delta, "tool_calls", None) or []
                    for tc in tool_call_deltas:
                        event: Dict[str, Any] = {
                            "type": "tool_call_delta",
                            "index": tc.index if tc.index is not None else 0,
                        }
                        tc_id = getattr(tc, "id", None)
                        if tc_id:
                            event["id"] = tc_id
                        fn = getattr(tc, "function", None)
                        if fn is not None:
                            name = getattr(fn, "name", None)
                            if name:
                                event["name"] = name
                            args = getattr(fn, "arguments", None)
                            if args:
                                event["arguments"] = args
                        chunk_count += 1
                        yield json.dumps(event) + "\n"

                    if choice.finish_reason:
                        final_finish_reason = choice.finish_reason

                yield json.dumps({"type": "finish", "finish_reason": final_finish_reason or "stop"}) + "\n"
                print(f"[Chat] streaming complete: {chunk_count} events, finish={final_finish_reason}")
            except Exception as e:
                print(f"[Chat] streaming error: {e}")
                import traceback
                traceback.print_exc()
                yield json.dumps({"type": "error", "message": str(e)}) + "\n"
                yield json.dumps({"type": "finish", "finish_reason": "error"}) + "\n"

        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",
            headers={"X-Accel-Buffering": "no"},
        )

    response = await asyncio.to_thread(
        client.chat.completions.create,
        stream=False,
        **create_kwargs,
    )

    if not response.choices:
        return ChatResponse(content="", tool_calls=[], finish_reason=None, deployment_id=request.deployment_id)

    choice = response.choices[0]
    msg = choice.message
    content = msg.content or ""

    tool_calls: List[Dict[str, Any]] = []
    raw_tool_calls = getattr(msg, "tool_calls", None) or []
    for tc in raw_tool_calls:
        fn = getattr(tc, "function", None)
        tool_calls.append({
            "id": getattr(tc, "id", None),
            "type": "function",
            "function": {
                "name": getattr(fn, "name", "") if fn else "",
                "arguments": getattr(fn, "arguments", "") if fn else "",
            },
        })

    return ChatResponse(
        content=content,
        tool_calls=tool_calls,
        finish_reason=choice.finish_reason,
        deployment_id=request.deployment_id,
    )


@app.post("/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    """
    Generate embeddings using native gen-ai-hub SDK.
    Compatible with OpenAI embeddings API format.
    """
    from gen_ai_hub.proxy.native.openai import OpenAI

    print(f"[Embeddings] Request: model={request.model}")
    print(f"[Embeddings] Input type: {type(request.input)}")

    client = OpenAI()

    inputs = [request.input] if isinstance(request.input, str) else request.input

    print(f"[Embeddings] Processing {len(inputs)} inputs with model: {request.model}")

    try:
        response = client.embeddings.create(
            model=request.model,
            input=inputs
        )

        print(f"[Embeddings] Generated {len(response.data)} embeddings")

        return EmbeddingResponse(
            object="list",
            data=[
                {
                    "object": "embedding",
                    "embedding": item.embedding,
                    "index": item.index
                }
                for item in response.data
            ],
            model=request.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if hasattr(response, 'usage') else 0,
                "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') else 0
            }
        )

    except Exception as e:
        print(f"[Embeddings] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5056)
