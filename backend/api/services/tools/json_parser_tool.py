"""
JSON Parser Tool

Provides a LangChain-compatible tool for parsing JSON strings and extracting values by path.
"""

import json
from typing import Type, Optional, Any

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class JSONParserInput(BaseModel):
    """Input schema for JSON parser tool"""
    data: str = Field(
        description="JSON string to parse"
    )
    path: Optional[str] = Field(
        default=None,
        description="Dot-separated path to extract a value (e.g. 'results.0.name'). If omitted, returns the full parsed object."
    )


def _extract_path(obj: Any, path: str) -> Any:
    """Walk a dot-separated path through nested dicts/lists."""
    for key in path.split("."):
        if isinstance(obj, dict):
            obj = obj[key]
        elif isinstance(obj, list):
            obj = obj[int(key)]
        else:
            raise KeyError(f"Cannot traverse into {type(obj).__name__} with key '{key}'")
    return obj


class JSONParserTool(BaseTool):
    """
    Parse a JSON string and optionally extract a value at a given path.
    """

    name: str = "json_parser"
    description: str = (
        "Parse a JSON string and optionally extract a nested value using a dot-separated path. "
        "For example, path 'results.0.name' gets the 'name' field of the first item in 'results'. "
        "Use this to inspect or extract data from JSON responses."
    )
    args_schema: Type[BaseModel] = JSONParserInput

    async def _arun(self, data: str, path: Optional[str] = None) -> str:
        """Parse JSON and optionally extract a path."""
        try:
            parsed = json.loads(data)

            if path:
                result = _extract_path(parsed, path)
            else:
                result = parsed

            return json.dumps({
                "success": True,
                "result": result,
            }, default=str)

        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"Invalid JSON: {e}",
            })
        except (KeyError, IndexError, ValueError) as e:
            return json.dumps({
                "success": False,
                "error": f"Path extraction failed: {e}",
            })
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
            })

    def _run(self, **kwargs) -> str:
        """Sync version not supported."""
        raise NotImplementedError("JSONParserTool only supports async execution")
