"""
Standalone SAP AI Core API using gen-ai-hub SDK
Isolated from main application to avoid dependency conflicts
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="SAP AI Core API")

class ChatRequest(BaseModel):
    message: str
    model_name: str = "gpt-4o"
    deployment_id: str
    stream: bool = False

class ChatResponse(BaseModel):
    response: str
    deployment_id: str

class DiscoveryResponse(BaseModel):
    success: bool
    models: list
    message: str = ""

class EmbeddingRequest(BaseModel):
    input: str | list[str]
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

        # Get proxy client (uses env vars)
        proxy_client = get_proxy_client("gen-ai-hub")

        # Get all deployments
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
    Chat using native gen-ai-hub SDK (OpenAI-compatible).
    No LangChain dependencies needed.

    ALWAYS uses gpt-4o regardless of requested model.
    """
    from gen_ai_hub.proxy.native.openai import OpenAI

    # HARDCODE gpt-4o - ignore requested model
    default_model = "gpt-4o"

    print(f"[Chat] Request: deployment={request.deployment_id}, model={request.model_name}")
    print(f"[Chat] USING DEFAULT: {default_model}")
    print(f"[Chat] Stream requested: {request.stream}")

    # Get OpenAI-compatible client from gen-ai-hub
    # The client auto-discovers deployment from env vars
    client = OpenAI()

    if request.stream:
        print(f"[Chat] Returning streaming response")
        async def generate():
            try:
                # Get synchronous stream from OpenAI client - ALWAYS use gpt-4o
                stream = client.chat.completions.create(
                    model=default_model,  # HARDCODED
                    messages=[{"role": "user", "content": request.message}],
                    stream=True,
                    max_tokens=4096,
                    temperature=0.7,
                )

                print(f"[Chat] Stream created, iterating chunks...")
                chunk_count = 0

                # Iterate over synchronous stream
                for chunk in stream:
                    # Check if choices exist and have content
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            chunk_count += 1
                            print(f"[Chat] Yielding chunk {chunk_count}: {delta.content[:30]}")
                            yield delta.content

                print(f"[Chat] Streaming complete, yielded {chunk_count} chunks")
            except Exception as e:
                print(f"[Chat] Streaming error: {e}")
                yield f"Error: {str(e)}"

        return StreamingResponse(generate(), media_type="text/plain")
    else:
        print(f"[Chat] Returning non-streaming response")
        response = client.chat.completions.create(
            model=default_model,  # HARDCODED
            messages=[{"role": "user", "content": request.message}],
            stream=False,
            max_tokens=4096,
            temperature=0.7,
        )
        # Extract content from response
        content = response.choices[0].message.content if response.choices else ""
        return ChatResponse(
            response=content,
            deployment_id=request.deployment_id
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

    # Get OpenAI-compatible client
    client = OpenAI()

    # Convert input to list if string
    inputs = [request.input] if isinstance(request.input, str) else request.input

    print(f"[Embeddings] Processing {len(inputs)} inputs with model: {request.model}")

    try:
        # Generate embeddings using the specified model
        response = client.embeddings.create(
            model=request.model,
            input=inputs
        )

        print(f"[Embeddings] Generated {len(response.data)} embeddings")

        # Return in OpenAI format
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
