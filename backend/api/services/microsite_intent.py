"""
Microsite Intent Detection for Chat Integration

Detects when a user's chat message expresses intent to create/generate a microsite.
Extracts template hints and workspace references from natural language.
"""

import re
from typing import Optional

from pydantic import BaseModel


class MicrositeIntent(BaseModel):
    """Result of microsite intent detection"""
    is_match: bool = False
    template_hint: Optional[str] = None
    workspace_hint: Optional[str] = None
    action: Optional[str] = None  # "create", "generate", "update", etc.


# Patterns that indicate microsite generation intent
_GENERATION_PATTERNS = [
    re.compile(
        r"(?:create|generate|make|build)\s+(?:a\s+)?(?:new\s+)?"
        r"(?:blog|landing\s*page|portfolio|documentation|report|docs)\s+"
        r"(?:micro)?site",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:create|generate|make|build)\s+(?:a\s+)?(?:new\s+)?(?:micro)?site\s+(?:from|using|with)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:create|generate|make|build)\s+(?:a\s+)?(?:new\s+)?(?:micro)?site",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:turn|convert)\s+(?:my\s+)?(?:research|notes|sources|workspace)\s+into\s+(?:a\s+)?(?:micro)?site",
        re.IGNORECASE,
    ),
]

# Template keyword mapping
_TEMPLATE_MAP = {
    "blog": "blog",
    "landing page": "landing",
    "landing": "landing",
    "portfolio": "portfolio",
    "documentation": "documentation",
    "docs": "documentation",
    "report": "report",
}


def detect_microsite_intent(message: str) -> MicrositeIntent:
    """
    Analyze a chat message for microsite generation intent.

    Args:
        message: User's chat message

    Returns:
        MicrositeIntent with detection results
    """
    lower = message.lower().strip()

    # Check against generation patterns
    matched = any(p.search(lower) for p in _GENERATION_PATTERNS)
    if not matched:
        return MicrositeIntent(is_match=False)

    # Determine action
    action = "create"
    if "generate" in lower:
        action = "generate"
    elif "build" in lower:
        action = "build"
    elif "update" in lower or "change" in lower:
        action = "update"

    # Extract template hint
    template_hint = None
    for keyword, template_name in _TEMPLATE_MAP.items():
        if keyword in lower:
            template_hint = template_name
            break

    # Extract workspace/notebook hint
    workspace_hint = None
    from_match = re.search(
        r"(?:from|using|with)\s+(?:my\s+)?[\"']?(.+?)[\"']?\s*(?:workspace|notebook|sources|$)",
        lower,
    )
    if from_match:
        workspace_hint = from_match.group(1).strip().rstrip(".")

    return MicrositeIntent(
        is_match=True,
        template_hint=template_hint,
        workspace_hint=workspace_hint,
        action=action,
    )
