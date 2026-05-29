"""
Microsite Chat Router

Provides AI-powered chat interface for editing microsites through natural language.
"""

import json
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.services.microsite_chat_tools import MicrositeEditorTools, execute_microsite_tool
from open_notebook.database.repository import repo_query
import httpx

router = APIRouter(
    prefix="/api/microsites",
    tags=["microsites", "chat"],
)


class MicrositeChatRequest(BaseModel):
    """Request to chat with microsite editor AI"""
    message: str
    microsite_id: str


class MicrositeChatResponse(BaseModel):
    """Response from microsite editor AI"""
    response: str
    changes_made: list[dict]
    preview_url: str


@router.post("/{microsite_id}/chat", response_model=MicrositeChatResponse)
async def chat_with_microsite_editor(
    microsite_id: str,
    request: MicrositeChatRequest
):
    """
    Chat with AI to edit the microsite using natural language.

    Examples:
    - "Change the hero section to say 'Welcome to our platform'"
    - "Make the primary color blue (#0000ff)"
    - "Hide the testimonials section"
    - "Add a logo from https://example.com/logo.png"
    - "Reorder sections: hero, features, conclusion"
    """
    # Verify microsite exists
    microsite_results = await repo_query(
        "SELECT id, title FROM microsites WHERE id = :id",
        {"id": microsite_id}
    )
    if not microsite_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Microsite not found"
        )

    # Get credentials for AI model
    try:
        from api.services.llm_client import resolve_llm_credential

        credential = await resolve_llm_credential()

    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load AI credentials: {str(e)}"
        )

    # Get available tools
    tools = MicrositeEditorTools.get_available_tools()

    # System prompt for microsite editing
    from api.services.prompt_loader import load_prompt

    FALLBACK_EDITOR_PROMPT = """You are a helpful AI assistant that edits microsites through natural language.

IMPORTANT: The microsite you are editing has ID: {microsite_id}
You MUST use this exact ID when calling any tools.

You have access to tools to:
- Get current microsite structure and content
- Update section content (hero, summary, features, etc.)
- Change colors, logos, and styling
- Customize navigation menu items (add, edit, remove)
- Update footer text
- Change site title
- Reorder or hide/show sections

When the user asks to edit something:
1. First get the current microsite info using microsite_id="{microsite_id}"
2. Make the requested changes using the appropriate tools (always pass microsite_id="{microsite_id}")
3. Explain what you did clearly

Be concise and helpful. Focus on making the changes the user requests.

Remember: Always use microsite_id="{microsite_id}" in all tool calls.
"""

    system_prompt = await load_prompt(
        "microsite_editor_chat",
        variables={"microsite_id": microsite_id},
        fallback=FALLBACK_EDITOR_PROMPT
    )

    # Call AI with function calling
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.message}
    ]

    changes_made = []
    max_iterations = 5
    iteration = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        from api.services.llm_client import call_llm_chat_message
        while iteration < max_iterations:
            iteration += 1

            # Call AI (provider-aware: SAP AI Core or OpenAI-compat)
            assistant_message = await call_llm_chat_message(
                credential,
                messages,
                temperature=0.7,
                max_tokens=2000,
                timeout=60.0,
                extra_payload={"tools": tools} if tools else None,
            )

            # Add assistant response to messages
            messages.append(assistant_message)

            # Check if AI wants to call tools
            if assistant_message.get("tool_calls"):
                # Execute each tool call
                for tool_call in assistant_message["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])

                    # Execute tool
                    tool_result = await execute_microsite_tool(tool_name, arguments)

                    # Track changes (skip get_microsite_info)
                    if tool_name != "get_microsite_info":
                        changes_made.append({
                            "action": tool_name,
                            "details": arguments,
                            "result": tool_result
                        })

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(tool_result)
                    })

                # Continue loop to get AI's next response
                continue
            else:
                # AI finished - no more tool calls
                final_response = assistant_message.get("content", "Changes applied successfully!")
                break
        else:
            # Max iterations reached
            final_response = "I've made the requested changes, but reached the maximum number of operations."

    return MicrositeChatResponse(
        response=final_response,
        changes_made=changes_made,
        preview_url=f"/api/microsites/{microsite_id}/preview"
    )
