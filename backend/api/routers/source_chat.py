"""
Source Chat Router

Chat functionality scoped to individual sources.
Allows chatting with a single source without needing a full notebook.
"""

import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from api.models import (
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    SuccessResponse
)
from api.services.context import get_context_service
from open_notebook.domain.notebook import Source


router = APIRouter(
    prefix="/api/sources",
    tags=["source-chat"],
    responses={404: {"model": ErrorResponse}},
)


# ============================================================================
# Source Chat Models
# ============================================================================

class SourceChatRequest(ChatRequest):
    """Chat request for source-scoped chat"""
    # Inherits from ChatRequest but selected_source_ids is not used
    pass


# ============================================================================
# Source Chat Endpoints
# ============================================================================

@router.post("/sources/{source_id}/chat")
async def chat_with_source(source_id: str, request: SourceChatRequest):
    """
    Chat with a single source (stateless).

    This endpoint provides a simplified chat experience without persistent sessions.
    Context is built from the specified source only.

    Args:
        source_id: Source ID
        request: Chat request

    Returns:
        Chat response or streaming response
    """
    # Verify source exists
    source = await Source.get(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source not found: {source_id}"
        )

    # Build context from source
    context_info = None
    system_message = None

    if request.include_context:
        context_service = get_context_service(
            max_tokens=request.max_context_tokens or 4000,
            model="gpt-4"
        )

        try:
            context_data = await context_service.build_source_context(source_id)

            context_info = {
                "tokens": context_data["tokens"],
                "chunks_included": context_data["chunks_included"],
                "chunks_total": context_data["chunks_total"]
            }

            system_message = f"""You are a helpful AI assistant with access to the following content from "{source.name}":

{context_data['content']}

Use this information to answer the user's questions accurately. If the information provided doesn't contain the answer, say so clearly."""

        except Exception as e:
            print(f"Error building source context: {e}")
            # Continue without context

    # Handle streaming vs non-streaming
    if request.stream:
        return EventSourceResponse(
            stream_source_chat_response(
                source=source,
                user_message=request.message,
                system_message=system_message,
                context_info=context_info
            )
        )
    else:
        # Non-streaming response
        assistant_content = await generate_source_chat_response(
            user_message=request.message,
            system_message=system_message
        )

        # Note: No messages are saved for stateless source chat
        return {
            "source_id": source_id,
            "source_name": source.name,
            "user_message": request.message,
            "assistant_message": assistant_content,
            "context_info": context_info
        }


@router.post("/sources/{source_id}/chat/ask")
async def ask_source_question(source_id: str, question: str):
    """
    Quick question endpoint for source chat (non-streaming, simplified).

    Args:
        source_id: Source ID
        question: Question to ask

    Returns:
        Simple response with answer
    """
    # Verify source exists
    source = await Source.get(source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source not found: {source_id}"
        )

    # Build context
    context_service = get_context_service(max_tokens=4000, model="gpt-4")

    try:
        context_data = await context_service.build_source_context(source_id)

        system_message = f"""Answer the following question based on this content from "{source.name}":

{context_data['content']}

Question: {question}

Provide a clear, concise answer. If the content doesn't contain the answer, say so."""

        answer = await generate_source_chat_response(
            user_message=question,
            system_message=system_message
        )

        return {
            "question": question,
            "answer": answer,
            "source_id": source_id,
            "source_name": source.name,
            "tokens_used": context_data["tokens"]
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating answer: {str(e)}"
        )


# ============================================================================
# Helper Functions
# ============================================================================

async def generate_source_chat_response(
    user_message: str,
    system_message: Optional[str]
) -> str:
    """
    Generate a chat response for source chat.

    Args:
        user_message: User's message
        system_message: Optional system message with context

    Returns:
        Assistant's response
    """
    # Build messages for LLM
    llm_messages = []

    if system_message:
        llm_messages.append({"role": "system", "content": system_message})

    llm_messages.append({"role": "user", "content": user_message})

    # TODO: Replace with actual LLM call via Esperanto or direct API
    try:
        from langchain.chat_models import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        llm = ChatOpenAI(temperature=0.7, model="gpt-4")

        lc_messages = []
        for msg in llm_messages:
            if msg["role"] == "system":
                lc_messages.append(SystemMessage(content=msg["content"]))
            elif msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))

        response = await llm.agenerate([lc_messages])
        return response.generations[0][0].text

    except Exception as e:
        print(f"Error generating response: {e}")
        return "I apologize, but I encountered an error generating a response. Please try again."


async def stream_source_chat_response(
    source: Source,
    user_message: str,
    system_message: Optional[str],
    context_info: Optional[dict]
):
    """
    Stream source chat response using Server-Sent Events.

    Args:
        source: Source object
        user_message: User's message
        system_message: Optional system message with context
        context_info: Context information

    Yields:
        SSE events with response chunks
    """
    try:
        # Send initial metadata event
        yield {
            "event": "metadata",
            "data": json.dumps({
                "source_id": source.id,
                "source_name": source.name,
                "context_info": context_info
            })
        }

        # Generate response
        full_response = await generate_source_chat_response(user_message, system_message)

        # Simulate streaming by chunking the response
        words = full_response.split()
        chunk_size = 3

        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if i > 0:
                chunk = " " + chunk

            yield {
                "event": "chunk",
                "data": json.dumps({"content": chunk})
            }

        # Send completion event
        yield {
            "event": "done",
            "data": json.dumps({
                "total_tokens": len(full_response.split())
            })
        }

    except Exception as e:
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)})
        }
