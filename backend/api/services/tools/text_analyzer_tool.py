"""
Text Analyzer Tool

Provides a LangChain-compatible tool for computing text statistics.
"""

import json
import re
from typing import Type

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class TextAnalyzerInput(BaseModel):
    """Input schema for text analyzer tool"""
    text: str = Field(
        description="Text to analyze for statistics"
    )


class TextAnalyzerTool(BaseTool):
    """
    Compute basic statistics about a piece of text: character count, word count,
    sentence count, average word length, and average sentence length.
    """

    name: str = "text_analyzer"
    description: str = (
        "Analyze text and return statistics including character count, word count, "
        "sentence count, average word length, and average sentence length. "
        "Use this when the user wants to know about the size or structure of a text."
    )
    args_schema: Type[BaseModel] = TextAnalyzerInput

    async def _arun(self, text: str) -> str:
        """Compute text statistics."""
        try:
            character_count = len(text)
            words = text.split()
            word_count = len(words)

            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            sentence_count = len(sentences)

            avg_word_length = (
                round(sum(len(w) for w in words) / word_count, 2)
                if word_count > 0 else 0
            )
            avg_sentence_length = (
                round(word_count / sentence_count, 2)
                if sentence_count > 0 else 0
            )

            return json.dumps({
                "success": True,
                "character_count": character_count,
                "word_count": word_count,
                "sentence_count": sentence_count,
                "avg_word_length": avg_word_length,
                "avg_sentence_length": avg_sentence_length,
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
            })

    def _run(self, **kwargs) -> str:
        """Sync version not supported."""
        raise NotImplementedError("TextAnalyzerTool only supports async execution")
