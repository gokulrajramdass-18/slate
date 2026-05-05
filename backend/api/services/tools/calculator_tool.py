"""
Calculator Tool

Provides a LangChain-compatible tool for evaluating math expressions using sympy.
"""

import json
from typing import Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class CalculatorInput(BaseModel):
    """Input schema for calculator tool"""
    expression: str = Field(
        description="Mathematical expression to evaluate (e.g. '2 + 2', 'sqrt(16)', 'sin(pi/4)')"
    )


class CalculatorTool(BaseTool):
    """
    Evaluate mathematical expressions safely using sympy.

    Supports arithmetic, trigonometry, logarithms, and other standard math functions.
    """

    name: str = "calculator"
    description: str = (
        "Evaluate a mathematical expression. "
        "Supports arithmetic (+, -, *, /, **), functions (sqrt, sin, cos, tan, log, exp), "
        "and constants (pi, e). Use this for any calculation the user needs."
    )
    args_schema: Type[BaseModel] = CalculatorInput

    async def _arun(self, expression: str) -> str:
        """Evaluate the math expression."""
        try:
            import sympy

            result = sympy.sympify(expression)
            evaluated = float(result.evalf())

            return json.dumps({
                "success": True,
                "result": evaluated,
                "expression": expression,
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
            })

    def _run(self, **kwargs) -> str:
        """Sync version not supported."""
        raise NotImplementedError("CalculatorTool only supports async execution")
