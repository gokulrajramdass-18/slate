"""
DateTime Tool

Provides a LangChain-compatible tool for getting current time and converting timezones.
"""

import json
from datetime import datetime, timezone
from typing import Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class DateTimeInput(BaseModel):
    """Input schema for datetime tool"""
    action: str = Field(
        default="now",
        description="Action to perform: 'now' for current time, 'timestamp' for Unix timestamp"
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone name (e.g. 'UTC', 'US/Eastern', 'Europe/Berlin', 'Asia/Tokyo')"
    )
    format: str = Field(
        default="%Y-%m-%d %H:%M:%S %Z",
        description="Output format string (strftime format)"
    )


class DateTimeTool(BaseTool):
    """
    Get the current date/time or convert between timezones.
    """

    name: str = "datetime"
    description: str = (
        "Get the current date and time, or a Unix timestamp. "
        "Supports timezone conversion using standard timezone names "
        "(e.g. 'UTC', 'US/Eastern', 'Europe/Berlin'). "
        "Use this when the user asks about the current time or needs time conversions."
    )
    args_schema: Type[BaseModel] = DateTimeInput

    async def _arun(
        self,
        action: str = "now",
        timezone: str = "UTC",
        format: str = "%Y-%m-%d %H:%M:%S %Z",
    ) -> str:
        """Get current time or timestamp."""
        try:
            import pytz

            # Validate timezone
            try:
                tz = pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                return json.dumps({
                    "success": False,
                    "error": f"Unknown timezone: {timezone}. Use standard timezone names like 'UTC', 'US/Eastern', 'Europe/Berlin'",
                })

            now = datetime.now(tz)

            if action == "timestamp":
                result = str(int(now.timestamp()))
            else:
                result = now.strftime(format)

            return json.dumps({
                "success": True,
                "result": result,
                "timezone": timezone,
                "action": action,
            })

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"[DateTimeTool] Error: {e}")
            print(f"[DateTimeTool] Traceback: {error_details}")
            return json.dumps({
                "success": False,
                "error": f"DateTime tool error: {str(e)}",
            })

    def _run(self, **kwargs) -> str:
        """Sync version not supported."""
        raise NotImplementedError("DateTimeTool only supports async execution")
