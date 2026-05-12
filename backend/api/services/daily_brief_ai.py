"""
Daily Brief AI Service

Generates AI-powered summaries for daily brief using LiteLLM.
"""

import os
import asyncio
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from api.services.settings import get_setting


async def generate_summary(brief_data: Dict[str, Any]) -> str:
    """
    Generate AI-powered summary from daily brief data.

    Args:
        brief_data: Daily brief data dictionary

    Returns:
        Natural language summary string
    """
    try:
        # Get LLM configuration
        model_id = await get_setting("language_model_id", "gpt-4o-mini")
        api_base = os.getenv("LITELLM_BASE_URL", "http://localhost:6655")
        api_key = os.getenv("OPENAI_API_KEY", "dummy-key-for-proxy")

        # Initialize LLM
        llm = ChatOpenAI(
            model=model_id,
            openai_api_base=f"{api_base}/litellm/v1" if "/litellm/v1" not in api_base else api_base,
            openai_api_key=api_key,
            temperature=0.7,
            max_tokens=500,
            timeout=30,
        )

        # Build prompt
        system_prompt = """You are a helpful assistant generating daily briefs for users.
Your job is to create a friendly, concise summary highlighting the most important information.
Keep summaries to 3-5 sentences maximum. Focus on actionable items and notable changes."""

        user_prompt = _build_prompt(brief_data)

        # Generate summary
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        response = await llm.ainvoke(messages)
        summary = response.content.strip()

        return summary

    except asyncio.TimeoutError:
        # Timeout - return fallback
        return _generate_fallback_summary(brief_data)
    except Exception as e:
        print(f"Error generating AI summary: {e}")
        # Error - return fallback
        return _generate_fallback_summary(brief_data)


def _build_prompt(brief_data: Dict[str, Any]) -> str:
    """Build prompt for AI summary generation"""
    user_name = brief_data.get("user_name", "User")
    time_since_login = brief_data.get("time_since_login", "recently")

    # Execution stats
    executions = brief_data.get("executions_since_login", {})
    exec_total = executions.get("total", 0)
    exec_completed = executions.get("completed", 0)
    exec_failed = executions.get("failed", 0)
    exec_success_rate = executions.get("success_rate", 0)

    # Approvals
    approvals = brief_data.get("pending_approvals", [])
    approval_count = len(approvals)

    # Notifications
    notifications = brief_data.get("notifications", {})
    notif_count = notifications.get("total", 0)
    notif_unread = notifications.get("unread", 0)

    # Schedules
    schedules = brief_data.get("upcoming_schedules", [])
    schedule_count = len(schedules)

    # Orchestrations
    orchestrations = brief_data.get("orchestrations", {})
    orch_total = orchestrations.get("total", 0)
    orch_completed = orchestrations.get("completed", 0)
    orch_failed = orchestrations.get("failed", 0)

    prompt = f"""Generate a daily brief summary for {user_name}.

Last login: {time_since_login}

Activity since last login:
- {exec_total} workflow executions ({exec_completed} completed, {exec_failed} failed, {exec_success_rate}% success rate)
- {approval_count} pending approvals requiring attention
- {notif_count} new notifications ({notif_unread} unread)
- {schedule_count} upcoming scheduled workflows
- {orch_total} orchestration runs ({orch_completed} completed, {orch_failed} failed)

Generate a friendly, concise summary (3-5 sentences) highlighting the most important items that need attention."""

    return prompt


def _generate_fallback_summary(brief_data: Dict[str, Any]) -> str:
    """Generate fallback text summary when AI fails"""
    user_name = brief_data.get("user_name", "User")
    time_since_login = brief_data.get("time_since_login", "recently")

    # Build structured summary
    parts = [f"Welcome back, {user_name}! You were last here {time_since_login}."]

    # Execution stats
    executions = brief_data.get("executions_since_login", {})
    exec_total = executions.get("total", 0)
    if exec_total > 0:
        exec_completed = executions.get("completed", 0)
        exec_failed = executions.get("failed", 0)
        parts.append(
            f"Your workflows ran {exec_total} times with {exec_completed} successful and {exec_failed} failed executions."
        )

    # Approvals
    approvals = brief_data.get("pending_approvals", [])
    approval_count = len(approvals)
    if approval_count > 0:
        parts.append(
            f"You have {approval_count} pending approval{'s' if approval_count != 1 else ''} waiting for your review."
        )

    # Notifications
    notifications = brief_data.get("notifications", {})
    notif_unread = notifications.get("unread", 0)
    if notif_unread > 0:
        parts.append(f"You have {notif_unread} unread notification{'s' if notif_unread != 1 else ''}.")

    # Schedules
    schedules = brief_data.get("upcoming_schedules", [])
    if schedules:
        next_schedule = schedules[0]
        parts.append(
            f"Your next scheduled workflow '{next_schedule.get('workflow_name')}' is coming up soon."
        )

    # If nothing happened
    if len(parts) == 1:
        parts.append("No new activity since your last login. Everything is running smoothly!")

    return " ".join(parts)
