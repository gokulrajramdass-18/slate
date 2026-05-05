"""
Intelligent Source Selector

Analyzes the user's query and available sources to determine which sources
are most relevant to answering the question.
"""

from typing import List, Dict, Any, Optional
import re
from langchain_openai import ChatOpenAI
from api.services.settings import get_setting


class IntelligentSourceSelector:
    """
    Selects the most relevant sources for a given query.

    Uses a small, fast LLM to determine which sources (data sources, notes, etc.)
    are most relevant to the user's question.
    """

    def __init__(self):
        """
        Initialize the intelligent source selector.

        Uses the configured language model from settings.
        """
        pass

    async def select_sources(
        self,
        query: str,
        available_sources: List[Dict[str, Any]],
        available_notes: List[Dict[str, Any]],
        max_sources: int = 3
    ) -> Dict[str, Any]:
        """
        Analyze the query and select the most relevant sources.

        Args:
            query: User's question/message
            available_sources: List of data sources with metadata
            available_notes: List of notes with metadata
            max_sources: Maximum number of sources to select

        Returns:
            Dict with:
                - selected_source_ids: List[str] - IDs of selected data sources
                - selected_note_ids: List[str] - IDs of selected notes
                - reasoning: str - Why these sources were selected
                - confidence: float - Confidence score (0-1)
        """
        # Build source descriptions for the LLM
        source_descriptions = []

        # Add data sources
        for idx, source in enumerate(available_sources, 1):
            desc = f"{idx}. **Data Source**: {source.get('title', 'Untitled')}"
            if source.get('source_type'):
                desc += f" (Type: {source['source_type']})"
            if source.get('summary'):
                desc += f"\n   Summary: {source['summary'][:200]}"
            desc += f"\n   ID: {source['id']}"
            source_descriptions.append(desc)

        # Add notes (with special marking for final deliverable)
        note_offset = len(available_sources)
        for idx, note in enumerate(available_notes, note_offset + 1):
            is_final = "FINAL DELIVERABLE" in note.get('title', '')
            desc = f"{idx}. **{'🎯 Final Deliverable' if is_final else 'Note'}**: {note.get('title', 'Untitled')}"
            if note.get('summary'):
                desc += f"\n   Summary: {note['summary'][:200]}"
            elif is_final:
                desc += "\n   Summary: Comprehensive AI-generated analysis with insights, recommendations, and strategic guidance"
            desc += f"\n   ID: {note['id']}"
            source_descriptions.append(desc)

        sources_text = "\n\n".join(source_descriptions)

        # Create prompt for source selection
        prompt = f"""You are an intelligent source selector. Analyze the user's question and determine which sources are most relevant to answer it.

**User's Question:**
{query}

**Available Sources:**
{sources_text}

**Instructions:**
1. Analyze the user's question to understand what they're asking about
2. Consider these priorities:
   - If asking about "final deliverable", "AI analysis", "comprehensive analysis", "insights", "recommendations" → Select the Final Deliverable note
   - If asking about specific data, metrics, or raw information → Select relevant data sources
   - If asking to "elaborate" or "expand on" analysis → Select the Final Deliverable note
   - If asking for charts/graphs based on insights → Select the Final Deliverable note first
   - If asking for charts/graphs based on raw data → Select the data sources
3. Select up to {max_sources} most relevant sources
4. The Final Deliverable should be prioritized for analytical questions
5. Raw data sources should be prioritized for specific data queries

**Output Format (JSON):**
{{
    "selected_ids": ["id1", "id2", ...],
    "reasoning": "Explanation of why these sources were selected",
    "confidence": 0.95
}}

Respond with ONLY the JSON object, no other text."""

        try:
            # Resolve model from configured settings
            from api.routers.credentials import _credentials_store

            model_id = await get_setting("language_model_id", "")
            if not model_id:
                print("[IntelligentSourceSelector] No language model configured, using fallback")
                return self._fallback_selection(query, available_sources, available_notes, max_sources)

            credential = _credentials_store.get(model_id)
            if not credential:
                print(f"[IntelligentSourceSelector] Credential not found for {model_id}, using fallback")
                return self._fallback_selection(query, available_sources, available_notes, max_sources)

            model_name = credential["model_name"]
            api_key = credential["api_key"]
            base_url = credential.get("base_url", "https://api.openai.com/v1")

            llm = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url,
            )

            response = await llm.ainvoke(prompt)
            response_text = response.content

            # Parse JSON response
            import json
            # Extract JSON from response (handle markdown code blocks)
            json_str = response_text.strip()
            if json_str.startswith("```"):
                # Remove markdown code blocks
                json_str = re.sub(r"```json\s*|\s*```", "", json_str).strip()

            result = json.loads(json_str)

            # Separate source IDs from note IDs
            selected_source_ids = []
            selected_note_ids = []

            source_id_map = {s['id']: 'source' for s in available_sources}
            note_id_map = {n['id']: 'note' for n in available_notes}

            for selected_id in result.get('selected_ids', []):
                if selected_id in source_id_map:
                    selected_source_ids.append(selected_id)
                elif selected_id in note_id_map:
                    selected_note_ids.append(selected_id)

            return {
                'selected_source_ids': selected_source_ids,
                'selected_note_ids': selected_note_ids,
                'reasoning': result.get('reasoning', 'No reasoning provided'),
                'confidence': result.get('confidence', 0.5)
            }

        except Exception as e:
            print(f"[IntelligentSourceSelector] Error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: Use simple heuristics
            return self._fallback_selection(query, available_sources, available_notes, max_sources)

    def _fallback_selection(
        self,
        query: str,
        available_sources: List[Dict[str, Any]],
        available_notes: List[Dict[str, Any]],
        max_sources: int
    ) -> Dict[str, Any]:
        """
        Fallback selection using simple keyword matching.
        """
        query_lower = query.lower()

        # Keywords that suggest wanting the final deliverable
        analysis_keywords = [
            'final', 'deliverable', 'analysis', 'insights', 'recommendations',
            'elaborate', 'expand', 'comprehensive', 'strategic', 'summary'
        ]

        # Keywords that suggest wanting raw data
        data_keywords = [
            'raw', 'data', 'table', 'specific', 'exact', 'numbers', 'values',
            'row', 'column', 'record', 'entry'
        ]

        wants_analysis = any(kw in query_lower for kw in analysis_keywords)
        wants_data = any(kw in query_lower for kw in data_keywords)

        selected_source_ids = []
        selected_note_ids = []
        reasoning = []

        # Find final deliverable
        final_deliverable = None
        for note in available_notes:
            if "FINAL DELIVERABLE" in note.get('title', ''):
                final_deliverable = note
                break

        if wants_analysis or (not wants_data and final_deliverable):
            # Prioritize final deliverable
            if final_deliverable:
                selected_note_ids.append(final_deliverable['id'])
                reasoning.append("Selected Final Deliverable for analytical insights")

        if wants_data or not final_deliverable:
            # Include data sources
            for source in available_sources[:max_sources]:
                selected_source_ids.append(source['id'])
            if selected_source_ids:
                reasoning.append(f"Selected {len(selected_source_ids)} data source(s) for raw data")

        return {
            'selected_source_ids': selected_source_ids,
            'selected_note_ids': selected_note_ids,
            'reasoning': '; '.join(reasoning) if reasoning else 'Using all available sources',
            'confidence': 0.7
        }
