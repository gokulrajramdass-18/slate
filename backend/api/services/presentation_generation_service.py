"""
Presentation Generation Service

Orchestrates PowerPoint presentation generation from workspace content.
Uses two-phase AI generation: outline creation → detailed slide content.
"""

import io
import uuid
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import json

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from open_notebook.domain.presentation import (
    Presentation,
    PresentationTemplate,
    PresentationContent,
    PresentationVersion,
    SlideType
)
from api.services.pptx_export_service import PPTXExportService

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    operation_name: str = "operation"
):
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay between retries
        operation_name: Name for logging

    Returns:
        Result of successful function call

    Raises:
        Last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries):
        try:
            result = await func()
            if attempt > 0:
                logger.info(f"[Retry] {operation_name} succeeded on attempt {attempt + 1}")
            return result
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(
                    f"[Retry] {operation_name} failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(
                    f"[Retry] {operation_name} failed after {max_retries} attempts: {str(e)}"
                )

    raise last_exception


class PresentationGenerationService:
    """Service for generating and managing presentations"""

    def __init__(self, db):
        self.db = db
        self.pptx_service = PPTXExportService()
        self._template_cache: Dict[str, PresentationTemplate] = {}  # Template caching for performance


    async def generate_presentation(
        self,
        presentation_id: str,
        template_id: str,
        source_ids: List[str],
        notebook_id: Optional[str],
        user_prompt: str,
        target_slide_count: int = 10
    ) -> Dict[str, Any]:
        """
        Generate presentation using two-phase AI approach.

        Phase 1: AI creates slide outline (structure)
        Phase 2: AI generates detailed content per slide

        Args:
            presentation_id: Unique presentation ID
            template_id: Template to use
            source_ids: List of source IDs for content
            notebook_id: Optional workspace ID
            user_prompt: User's generation request
            target_slide_count: Target number of slides

        Returns:
            Dict with presentation_id, slide_count, preview_html
        """
        import time
        start_time = time.time()

        try:
            # 1. Load template
            logger.info(f"[Performance] Step 1/8: Loading template '{template_id}'...")
            step_start = time.time()
            template = await self._load_template(template_id)
            if not template:
                raise ValueError(f"Template not found: {template_id}")
            logger.info(f"[Performance] Step 1 completed in {time.time() - step_start:.2f}s")

            # 2. Build source context
            logger.info(f"[Performance] Step 2/8: Building context from {len(source_ids)} sources...")
            step_start = time.time()
            context = await self._build_context(source_ids, notebook_id)
            logger.info(f"[Performance] Step 2 completed in {time.time() - step_start:.2f}s")

            # 3. Generate outline (AI determines structure)
            logger.info(f"[Performance] Step 3/8: Generating {target_slide_count}-slide outline with AI...")
            step_start = time.time()
            outline = await self._generate_outline(
                context, user_prompt, target_slide_count, template
            )
            logger.info(f"[Performance] Step 3 completed in {time.time() - step_start:.2f}s")

            # 4. Generate slides from outline (PARALLEL for performance)
            logger.info(f"[Performance] Step 4/8: Generating {len(outline)} slides in parallel...")
            step_start = time.time()
            import asyncio
            slide_tasks = [
                self._generate_slide_content(idx, slide_spec, context, template, presentation_id)
                for idx, slide_spec in enumerate(outline, start=1)
            ]

            # Execute all slide generations concurrently
            slides = await asyncio.gather(*slide_tasks)
            logger.info(f"[Performance] Step 4 completed in {time.time() - step_start:.2f}s ({len(slides)} slides in parallel)")

            # 5. Save presentation record to database
            logger.info(f"[Performance] Step 5/9: Saving presentation record...")
            step_start = time.time()
            await self._save_presentation_record(presentation_id, template_id, notebook_id, user_prompt)
            logger.info(f"[Performance] Step 5 completed in {time.time() - step_start:.2f}s")

            # 6. Save slides to database
            logger.info(f"[Performance] Step 6/9: Saving {len(slides)} slides to database...")
            step_start = time.time()
            await self._save_slides(presentation_id, slides)
            logger.info(f"[Performance] Step 6 completed in {time.time() - step_start:.2f}s")

            # 6. Create HTML preview
            logger.info(f"[Performance] Step 7/9: Generating HTML preview...")
            step_start = time.time()
            preview_html = self._generate_preview_html(slides, template)
            logger.info(f"[Performance] Step 7 completed in {time.time() - step_start:.2f}s")

            # 7. Create version snapshot
            logger.info(f"[Performance] Step 8/9: Creating version snapshot...")
            step_start = time.time()
            await self._create_version_snapshot(presentation_id, slides)
            logger.info(f"[Performance] Step 8 completed in {time.time() - step_start:.2f}s")

            # 8. Link sources
            logger.info(f"[Performance] Step 9/9: Linking {len(source_ids)} sources...")
            step_start = time.time()
            await self._link_sources(presentation_id, source_ids)
            logger.info(f"[Performance] Step 9 completed in {time.time() - step_start:.2f}s")

            total_time = time.time() - start_time
            logger.info(f"[Performance] ✅ TOTAL GENERATION TIME: {total_time:.2f}s for {len(slides)} slides")

            return {
                "presentation_id": presentation_id,
                "slide_count": len(slides),
                "preview_html": preview_html,
                "generation_time_seconds": round(total_time, 2)
            }

        except Exception as e:
            logger.error(f"Failed to generate presentation: {str(e)}")
            raise

    async def _load_template(self, template_id: str) -> Optional[PresentationTemplate]:
        """
        Load template from database with caching for performance.

        Templates are cached in memory to avoid repeated database queries.
        """
        # Check cache first
        if template_id in self._template_cache:
            logger.info(f"[Performance] Using cached template: {template_id}")
            return self._template_cache[template_id]

        # Load from database
        query = "SELECT * FROM presentation_templates WHERE id = ? AND is_active = 1"
        async with self.db.execute(query, (template_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                template = PresentationTemplate.from_db(dict(row))
                # Cache for future use
                self._template_cache[template_id] = template
                logger.info(f"[Performance] Cached template: {template_id}")
                return template
        return None


    async def _build_context(
        self,
        source_ids: List[str],
        notebook_id: Optional[str]
    ) -> str:
        """
        Build context from sources for AI generation.

        Combines content from:
        - Documents (PDFs, text files)
        - URLs (web pages)
        - HANA tables (database data)
        - Chat history
        - Notebook notes
        """
        context_parts = []

        # Fetch sources
        if source_ids:
            placeholders = ",".join("?" * len(source_ids))
            query = f"SELECT * FROM sources WHERE id IN ({placeholders})"
            async with self.db.execute(query, source_ids) as cursor:
                sources = await cursor.fetchall()

            for source in sources:
                source_dict = dict(source)
                source_type = source_dict.get("source_type")

                # Parse metadata if it's a string
                metadata_str = source_dict.get("metadata", "{}")
                if isinstance(metadata_str, str):
                    metadata = json.loads(metadata_str) if metadata_str else {}
                else:
                    metadata = metadata_str

                if source_type == "file":
                    content = await self._extract_file_content(source_dict)
                    title = source_dict.get('title', source_dict.get('name', 'Untitled'))
                    context_parts.append(f"Document: {title}\n{content}")
                elif source_type == "url":
                    content = metadata.get("content", "")
                    title = source_dict.get('title', source_dict.get('name', 'Untitled'))
                    context_parts.append(f"URL: {title}\n{content}")
                elif source_type == "hana_table":
                    # For HANA tables, include schema info
                    table_name = metadata.get("table_name", "")
                    context_parts.append(f"Database Table: {table_name}")

        # Fetch notebook notes if provided
        if notebook_id:
            notes_query = "SELECT content FROM notes WHERE notebook_id = ?"
            async with self.db.execute(notes_query, (notebook_id,)) as cursor:
                notes = await cursor.fetchall()
                for note in notes:
                    context_parts.append(f"Note:\n{note['content']}")

        return "\n\n---\n\n".join(context_parts)

    async def _extract_file_content(self, source: Dict[str, Any]) -> str:
        """Extract text content from file source"""
        # Use full_text if available, otherwise try metadata
        full_text = source.get("full_text")
        if full_text:
            return full_text

        # Fallback to metadata
        metadata_str = source.get("metadata", "{}")
        if isinstance(metadata_str, str):
            import json
            metadata = json.loads(metadata_str) if metadata_str else {}
        else:
            metadata = metadata_str

        return metadata.get("extracted_text", "")

    async def _generate_outline(
        self,
        context: str,
        prompt: str,
        target_count: int,
        template: PresentationTemplate
    ) -> List[Dict[str, Any]]:
        """
        Use AI to generate slide outline.

        Returns list of slide specifications:
        [{slide_number, type, title, bullet_points}, ...]
        """
        from api.services.settings import get_setting
        from api.routers.credentials import _credentials_store
        from litellm import acompletion

        # Get language model from settings
        language_model_id = await get_setting("language_model_id", "gpt-4o-mini")

        # Resolve model name and API key from credential if it's a UUID
        model_name = language_model_id
        api_key = None
        api_base = None
        credential: Optional[Dict[str, Any]] = None

        if language_model_id and len(language_model_id) == 36 and language_model_id.count('-') == 4:
            # It's a credential ID, resolve the actual model name and API key
            credential = _credentials_store.get(language_model_id)
            if credential:
                model_name = credential.get("model_name", language_model_id)
                api_key = credential.get("api_key")
                api_base = credential.get("base_url")
            else:
                # Fallback to default
                model_name = "gpt-4o-mini"
        elif not language_model_id:
            model_name = "gpt-4o-mini"

        # Check if using LiteLLM proxy
        using_litellm_proxy = api_base and ("litellm" in api_base.lower() or "6655" in api_base)

        # Transform custom model format for direct API calls (not proxy)
        # Format: "provider--model-name"
        if "--" in model_name:
            if using_litellm_proxy:
                # For LiteLLM proxy, keep the model name as-is (it expects provider--model format)
                logger.info(f"[PresentationGen] Using model for LiteLLM proxy: {model_name}")
            else:
                # For direct API calls, transform to standard format
                parts = model_name.split("--")
                provider = parts[0]
                model = parts[1]

                # For Anthropic direct API
                if provider == "anthropic":
                    # Transform claude-4.6-sonnet -> proper Claude model name
                    base_model = None
                    if "claude" in model:
                        # Extract model family and version
                        if "4.6-sonnet" in model or "4-6-sonnet" in model or "4.5-sonnet" in model or "4-5-sonnet" in model:
                            # Claude 4.x doesn't exist yet, use Claude 3.5 Sonnet
                            base_model = "claude-3-5-sonnet-20241022"
                        elif "4.7-opus" in model or "4-7-opus" in model:
                            # Claude 4.7 doesn't exist, use Claude 3 Opus
                            base_model = "claude-3-opus-20240229"
                        elif "3.5-sonnet" in model or "3-5-sonnet" in model:
                            base_model = "claude-3-5-sonnet-20241022"
                        elif "3-opus" in model:
                            base_model = "claude-3-opus-20240229"
                        else:
                            # Default to Claude 3.5 Sonnet
                            base_model = "claude-3-5-sonnet-20241022"
                    else:
                        base_model = "claude-3-5-sonnet-20241022"

                    # Use anthropic/ prefix for custom API keys
                    if api_key:
                        model_name = f"anthropic/{base_model}"
                    else:
                        model_name = base_model
                # For OpenAI, use direct model name
                elif provider == "openai":
                    model_name = model
                # For other providers, use provider/model format
                else:
                    model_name = f"{provider}/{model}"

        available_layouts = template.slide_layouts or [
            "title", "bullets", "two_column", "content", "image_text"
        ]

        # Build AI prompt for outline generation
        system_prompt = f"""You are an expert presentation designer. Create a professional presentation outline.

Available slide layouts: {', '.join(available_layouts)}

Guidelines:
- First slide must be "title" type with engaging title and subtitle
- Use "bullets" for key points (3-5 bullets per slide)
- Use "two_column" for comparisons or contrasts (provide 4-6 bullet points that will be split into two columns)
- Use "content" for detailed explanations (provide 2-3 paragraph points)
- Use "image_text" for visual concepts (provide 2-3 descriptive points)
- Vary slide types for visual interest
- Each slide should have clear, actionable content
- Keep titles concise and impactful (max 8 words)
- Bullet points should be concise (max 12 words each)
- IMPORTANT: ALL non-title slides MUST have "bullet_points" array with actual content

Return ONLY valid JSON array with this structure:
[
  {{
    "slide_number": 1,
    "type": "title",
    "title": "Main Title Here",
    "subtitle": "Engaging subtitle"
  }},
  {{
    "slide_number": 2,
    "type": "bullets",
    "title": "Slide Title",
    "bullet_points": ["Point 1", "Point 2", "Point 3"]
  }},
  {{
    "slide_number": 3,
    "type": "two_column",
    "title": "Comparison Title",
    "bullet_points": ["Left point 1", "Left point 2", "Right point 1", "Right point 2"]
  }},
  {{
    "slide_number": 4,
    "type": "content",
    "title": "Content Title",
    "bullet_points": ["Detailed paragraph 1", "Detailed paragraph 2"]
  }}
]"""

        # Intelligent context handling - no hard truncation
        max_context_length = 60000  # chars (roughly 15k tokens)

        if context and len(context) > max_context_length:
            logger.info(f"[PresentationGen] Context is large ({len(context)} chars), summarizing...")
            # Keep first and last portions, summarize middle
            context_snippet = context[:max_context_length]
            logger.warning(f"[PresentationGen] Context truncated to {max_context_length} chars")
        else:
            context_snippet = context if context else "No additional context provided."
            logger.info(f"[PresentationGen] Using full context ({len(context_snippet)} chars)")

        user_prompt = f"""Create a {target_count}-slide presentation outline about: {prompt}

Context/Source Material:
{context_snippet}

Generate exactly {target_count} slides with professional, engaging content. Return ONLY the JSON array."""

        try:
            from api.services.llm_client import call_llm_chat

            logger.info(f"[PresentationGen] Calling AI with model: {model_name}")
            logger.info(f"[PresentationGen] Provider: {credential.get('provider') if credential else 'unknown'}")

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            async def call_llm():
                return await call_llm_chat(
                    credential or {"provider": "openai_compat", "model_name": model_name, "api_key": api_key, "base_url": api_base},
                    messages,
                    temperature=0.7,
                    max_tokens=2000,
                )

            response_content = await retry_with_backoff(
                call_llm,
                max_retries=3,
                initial_delay=1.0,
                operation_name="LLM outline generation"
            )

            logger.info(f"[PresentationGen] AI response received successfully")

            # Extract and parse JSON with validation
            content = response_content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                parts = content.split("```")
                if len(parts) >= 2:
                    content = parts[1]
                    if content.startswith("json"):
                        content = content[4:]
                    content = content.strip()

            # Validate JSON before parsing
            if not content:
                raise ValueError("Empty response from LLM")

            try:
                outline = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.error(f"Raw content: {content[:500]}")
                raise ValueError(f"Invalid JSON response from LLM: {str(e)}")

            # Validate outline structure
            if not isinstance(outline, list):
                raise ValueError(f"Outline must be a list, got {type(outline)}")

            if len(outline) == 0:
                raise ValueError("Outline is empty")

            # Validate each slide has required fields
            for idx, slide in enumerate(outline):
                if not isinstance(slide, dict):
                    raise ValueError(f"Slide {idx} must be a dict, got {type(slide)}")
                if "type" not in slide:
                    raise ValueError(f"Slide {idx} missing required field 'type'")
                if "title" not in slide:
                    slide["title"] = f"Slide {idx + 1}"  # Add default title

            # Ensure slide numbers are sequential
            for idx, slide in enumerate(outline, start=1):
                slide["slide_number"] = idx

            return outline[:target_count]  # Limit to target count

        except Exception as e:
            logger.error(f"AI outline generation failed: {str(e)}, using fallback")
            logger.error(f"Model attempted: {model_name}, API key present: {bool(api_key)}, API base: {api_base}")

            # Provide more helpful error message based on the error type
            error_hint = ""
            error_msg = str(e).lower()
            if "sap" in error_msg or "deployment" in error_msg:
                error_hint = "Hint: SAP AI Core deployment not found. Configure an OpenAI or direct Anthropic credential instead."
            elif "api key" in error_msg or "authentication" in error_msg:
                error_hint = "Hint: API key issue. Check your credential configuration in Settings."
            elif "model" in error_msg and "not" in error_msg:
                error_hint = f"Hint: Model '{model_name}' not recognized. Try configuring a different credential."

            logger.warning(f"[PresentationGen] {error_hint}")

            # Fallback to basic outline if AI fails
            return [
                {
                    "slide_number": 1,
                    "type": "title",
                    "title": prompt[:50] if prompt else "Presentation",
                    "subtitle": "AI-Generated Presentation (Fallback Mode)"
                }
            ] + [
                {
                    "slide_number": i,
                    "type": available_layouts[(i - 2) % len(available_layouts)],
                    "title": f"Topic {i - 1}",
                    "bullet_points": ["Key insight", "Supporting detail", "Action item"]
                }
                for i in range(2, target_count + 1)
            ]

    async def _generate_slide_content(
        self,
        slide_number: int,
        spec: Dict[str, Any],
        context: str,
        template: PresentationTemplate,
        presentation_id: str
    ) -> PresentationContent:
        """Generate detailed content for one slide using AI for enrichment"""

        slide_type = spec.get("type", "content")
        title = spec.get("title", "")

        # For title slides, no need for AI enrichment
        if slide_type == "title":
            content_json = {
                "title": title,
                "subtitle": spec.get("subtitle", ""),
                "elements": [
                    {"type": "subtitle", "content": spec.get("subtitle", "")}
                ]
            }
        else:
            # For content slides, optionally enrich with AI
            # Use the outline as-is for now (already AI-generated)
            content_json = {"title": title, "elements": []}

            if slide_type == "bullets":
                bullet_points = spec.get("bullet_points", [])
                content_json["elements"] = [
                    {"type": "bullet", "content": point, "level": 0}
                    for point in bullet_points
                ]

            elif slide_type == "two_column":
                bullets = spec.get("bullet_points", [])
                # If no bullet points provided or empty list, generate placeholder content
                if not bullets or len(bullets) == 0:
                    logger.warning(f"Two-column slide {slide_number} has no bullet_points, using placeholder")
                    bullets = [
                        f"{title} - Key Point 1",
                        "Supporting detail or example",
                        f"{title} - Key Point 2",
                        "Supporting detail or example"
                    ]
                mid = len(bullets) // 2
                if mid == 0:  # Handle case where we have very few bullets
                    mid = 1
                left_bullets = bullets[:mid]
                right_bullets = bullets[mid:]

                content_json["elements"] = (
                    [{"type": "bullet", "content": p, "column": "left", "level": 0}
                     for p in left_bullets] +
                    [{"type": "bullet", "content": p, "column": "right", "level": 0}
                     for p in right_bullets]
                )

            elif slide_type == "content":
                bullets = spec.get("bullet_points", [])
                # If no bullet points or empty, use title as content
                if not bullets or len(bullets) == 0:
                    logger.warning(f"Content slide {slide_number} has no bullet_points, using title")
                    content_text = f"This slide discusses: {title}\n\nKey concepts and detailed information would be presented here in a full presentation."
                else:
                    content_text = "\n\n".join(bullets)
                content_json["elements"] = [
                    {"type": "paragraph", "content": content_text}
                ]

            elif slide_type == "image_text":
                bullets = spec.get("bullet_points", [])
                # If no bullet points or empty, use descriptive text
                if not bullets or len(bullets) == 0:
                    logger.warning(f"Image-text slide {slide_number} has no bullet_points, using description")
                    text_content = f"Visual representation of {title}\n\nThis slide would feature relevant imagery alongside descriptive content."
                else:
                    text_content = "\n\n".join(bullets)
                content_json["elements"] = [
                    {"type": "paragraph", "content": text_content},
                    {"type": "image", "content": "[Image Placeholder]"}
                ]

        # Generate HTML for preview
        content_html = self._generate_slide_html(slide_type, content_json, template)

        # Create PresentationContent object
        return PresentationContent(
            id=str(uuid.uuid4()),
            presentation_id=presentation_id,
            slide_number=slide_number,
            slide_type=slide_type,
            content_html=content_html,
            content_json=content_json,
            speaker_notes=spec.get("speaker_notes"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    def _generate_slide_html(
        self,
        slide_type: str,
        content_json: Dict[str, Any],
        template: PresentationTemplate
    ) -> str:
        """Generate HTML representation of slide for preview"""

        colors = template.get_theme_colors()
        fonts = template.get_theme_fonts()

        primary_color = colors.get("primary", "#0066cc")
        text_color = colors.get("text", "#333333")
        bg_color = colors.get("background", "#ffffff")
        heading_font = fonts.get("heading", "Arial, sans-serif")
        body_font = fonts.get("body", "Arial, sans-serif")

        title = content_json.get("title", "")
        elements = content_json.get("elements", [])

        # Build HTML based on slide type
        if slide_type == "title":
            subtitle = content_json.get("subtitle", "")
            return f"""
            <div class="slide title-slide" style="background: {bg_color}; color: {text_color};">
                <h1 style="font-family: {heading_font}; color: {primary_color};">{title}</h1>
                <h2 style="font-family: {body_font};">{subtitle}</h2>
            </div>
            """

        elif slide_type == "bullets":
            bullets_html = "\n".join([
                f'<li style="margin-left: {elem.get("level", 0) * 20}px;">{elem.get("content", "")}</li>'
                for elem in elements if elem.get("type") == "bullet"
            ])
            return f"""
            <div class="slide bullet-slide" style="background: {bg_color}; color: {text_color};">
                <h2 style="font-family: {heading_font}; color: {primary_color};">{title}</h2>
                <ul style="font-family: {body_font};">
                    {bullets_html}
                </ul>
            </div>
            """

        elif slide_type == "two_column":
            left_bullets = [e for e in elements if e.get("column") == "left"]
            right_bullets = [e for e in elements if e.get("column") == "right"]

            left_html = "\n".join([f'<li>{e.get("content", "")}</li>' for e in left_bullets])
            right_html = "\n".join([f'<li>{e.get("content", "")}</li>' for e in right_bullets])

            return f"""
            <div class="slide two-column-slide" style="background: {bg_color}; color: {text_color};">
                <h2 style="font-family: {heading_font}; color: {primary_color};">{title}</h2>
                <div style="display: flex; gap: 2rem;">
                    <div style="flex: 1;">
                        <ul style="font-family: {body_font};">{left_html}</ul>
                    </div>
                    <div style="flex: 1;">
                        <ul style="font-family: {body_font};">{right_html}</ul>
                    </div>
                </div>
            </div>
            """

        elif slide_type == "content":
            paragraphs = "\n".join([
                f'<p>{elem.get("content", "")}</p>'
                for elem in elements if elem.get("type") == "paragraph"
            ])
            return f"""
            <div class="slide content-slide" style="background: {bg_color}; color: {text_color};">
                <h2 style="font-family: {heading_font}; color: {primary_color};">{title}</h2>
                <div style="font-family: {body_font};">
                    {paragraphs}
                </div>
            </div>
            """

        else:
            return f"""
            <div class="slide" style="background: {bg_color}; color: {text_color};">
                <h2 style="font-family: {heading_font}; color: {primary_color};">{title}</h2>
            </div>
            """

    async def _save_presentation_record(
        self,
        presentation_id: str,
        template_id: str,
        notebook_id: Optional[str],
        user_prompt: str
    ):
        """Save presentation record to database"""
        from datetime import datetime

        # Extract title from user prompt (first 100 chars or until punctuation)
        title = user_prompt[:100].split('.')[0].split('?')[0].strip()
        if not title:
            title = "Untitled Presentation"

        presentation = Presentation(
            id=presentation_id,
            notebook_id=notebook_id,
            template_id=template_id,
            title=title,
            description=user_prompt if len(user_prompt) > 100 else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        pres_dict = presentation.to_dict()
        columns = ", ".join(pres_dict.keys())
        placeholders = ", ".join("?" * len(pres_dict))

        query = f"""
            INSERT OR REPLACE INTO presentations ({columns})
            VALUES ({placeholders})
        """
        await self.db.execute(query, tuple(pres_dict.values()))
        await self.db.commit()

    async def _save_slides(self, presentation_id: str, slides: List[PresentationContent]):
        """Save slides to database"""
        # First, delete any existing slides for this presentation
        delete_query = "DELETE FROM presentation_content WHERE presentation_id = ?"
        await self.db.execute(delete_query, (presentation_id,))

        # Now insert the new slides
        for slide in slides:
            slide_dict = slide.to_dict()
            columns = ", ".join(slide_dict.keys())
            placeholders = ", ".join("?" * len(slide_dict))

            query = f"""
                INSERT INTO presentation_content ({columns})
                VALUES ({placeholders})
            """
            await self.db.execute(query, tuple(slide_dict.values()))

        await self.db.commit()

    def _generate_preview_html(
        self,
        slides: List[PresentationContent],
        template: PresentationTemplate
    ) -> str:
        """Generate full HTML preview with navigation"""

        colors = template.get_theme_colors()
        primary_color = colors.get("primary", "#0066cc")

        slides_html = "\n".join([
            f'<div class="slide-container" data-slide="{slide.slide_number}">{slide.content_html}</div>'
            for slide in slides
        ])

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Presentation Preview</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: Arial, sans-serif;
                    background: #1a1a1a;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    overflow: hidden;
                }}
                .presentation-container {{
                    width: 100%;
                    max-width: 1200px;
                    aspect-ratio: 16/9;
                    position: relative;
                    background: white;
                    box-shadow: 0 10px 50px rgba(0,0,0,0.5);
                }}
                .slide-container {{
                    display: none;
                    width: 100%;
                    height: 100%;
                    padding: 3rem;
                }}
                .slide-container.active {{
                    display: flex;
                    flex-direction: column;
                }}
                .slide {{
                    width: 100%;
                    height: 100%;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    padding: 2rem;
                }}
                .slide h1 {{
                    font-size: 3rem;
                    margin-bottom: 1rem;
                    text-align: center;
                }}
                .slide h2 {{
                    font-size: 2rem;
                    margin-bottom: 1.5rem;
                    text-align: center;
                }}
                .slide ul {{
                    font-size: 1.5rem;
                    line-height: 1.8;
                    list-style-position: inside;
                }}
                .slide p {{
                    font-size: 1.25rem;
                    line-height: 1.6;
                    margin-bottom: 1rem;
                }}
                .title-slide {{
                    justify-content: center;
                    align-items: center;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="presentation-container">
                {slides_html}
            </div>
            <script>
                let currentSlide = 1;
                const totalSlides = {len(slides)};

                function showSlide(slideNumber) {{
                    document.querySelectorAll('.slide-container').forEach(el => {{
                        el.classList.remove('active');
                    }});

                    const slide = document.querySelector(`[data-slide="${{slideNumber}}"]`);
                    if (slide) {{
                        slide.classList.add('active');
                        currentSlide = slideNumber;
                    }}
                }}

                window.addEventListener('message', (event) => {{
                    if (event.data.action === 'navigateToSlide') {{
                        showSlide(event.data.slideNumber);
                    }}
                }});

                document.addEventListener('keydown', (e) => {{
                    if (e.key === 'ArrowRight' && currentSlide < totalSlides) {{
                        showSlide(currentSlide + 1);
                    }} else if (e.key === 'ArrowLeft' && currentSlide > 1) {{
                        showSlide(currentSlide - 1);
                    }}
                }});

                // Show first slide
                showSlide(1);
            </script>
        </body>
        </html>
        """

    async def _create_version_snapshot(
        self,
        presentation_id: str,
        slides: List[PresentationContent]
    ):
        """Create version snapshot for rollback"""
        # Get current version number
        query = """
            SELECT COALESCE(MAX(version_number), 0) as max_version
            FROM presentation_versions
            WHERE presentation_id = ?
        """
        async with self.db.execute(query, (presentation_id,)) as cursor:
            row = await cursor.fetchone()
            next_version = row["max_version"] + 1

        # Create snapshot
        slides_snapshot = [slide.to_dict() for slide in slides]

        version = PresentationVersion(
            id=str(uuid.uuid4()),
            presentation_id=presentation_id,
            version_number=next_version,
            slides_snapshot=slides_snapshot,
            created_at=datetime.utcnow()
        )

        version_dict = version.to_dict()
        columns = ", ".join(version_dict.keys())
        placeholders = ", ".join("?" * len(version_dict))

        insert_query = f"""
            INSERT INTO presentation_versions ({columns})
            VALUES ({placeholders})
        """
        await self.db.execute(insert_query, tuple(version_dict.values()))
        await self.db.commit()

    async def _link_sources(self, presentation_id: str, source_ids: List[str]):
        """Link presentation to source materials"""
        for source_id in source_ids:
            query = """
                INSERT OR IGNORE INTO presentation_sources (presentation_id, source_id, created_at)
                VALUES (?, ?, ?)
            """
            await self.db.execute(query, (presentation_id, source_id, datetime.utcnow().isoformat()))

        await self.db.commit()

    async def parse_refine_command(self, message: str) -> Dict[str, Any]:
        """
        Parse natural language refinement command.

        Examples:
        - "change slide 3 title to 'Market Analysis'"
        - "add a slide about competitors after slide 5"
        - "remove slide 7"
        - "make bullets on slide 4 shorter"

        Returns structured command dict.
        """
        # Placeholder for AI-based parsing
        # In production, would use LLM with JSON output

        message_lower = message.lower()

        # Extract slide number
        import re
        slide_match = re.search(r'slide\s+(\d+)', message_lower)
        slide_number = int(slide_match.group(1)) if slide_match else None

        # Detect action
        if "change" in message_lower and "title" in message_lower:
            # Extract new title
            title_match = re.search(r'title\s+to\s+["\']([^"\']+)["\']', message)
            new_title = title_match.group(1) if title_match else ""

            return {
                "action": "update_title",
                "slide_number": slide_number,
                "params": {"new_title": new_title}
            }

        elif "add" in message_lower and "slide" in message_lower:
            return {
                "action": "add_slide",
                "slide_number": slide_number,
                "params": {}
            }

        elif "remove" in message_lower or "delete" in message_lower:
            return {
                "action": "delete_slide",
                "slide_number": slide_number,
                "params": {}
            }

        elif "shorter" in message_lower:
            return {
                "action": "shorten_content",
                "slide_number": slide_number,
                "params": {}
            }

        return {"action": "unknown", "params": {}}

    async def refine_slide(
        self,
        presentation_id: str,
        command: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute refinement command on presentation"""

        action = command.get("action")
        slide_number = command.get("slide_number")
        params = command.get("params", {})

        if action == "update_title":
            new_title = params.get("new_title", "")

            # Fetch slide
            query = """
                SELECT * FROM presentation_content
                WHERE presentation_id = ? AND slide_number = ?
            """
            async with self.db.execute(query, (presentation_id, slide_number)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return {"success": False, "error": "Slide not found"}

                slide = PresentationContent.from_db(dict(row))

            # Update title
            slide.set_title(new_title)
            slide.updated_at = datetime.utcnow()

            # Save
            update_query = """
                UPDATE presentation_content
                SET content_json = ?, updated_at = ?
                WHERE id = ?
            """
            await self.db.execute(
                update_query,
                (json.dumps(slide.content_json), slide.updated_at.isoformat(), slide.id)
            )
            await self.db.commit()

            return {"success": True, "message": f"Updated title on slide {slide_number}"}

        elif action == "delete_slide":
            # Delete slide
            delete_query = """
                DELETE FROM presentation_content
                WHERE presentation_id = ? AND slide_number = ?
            """
            await self.db.execute(delete_query, (presentation_id, slide_number))

            # Renumber subsequent slides
            renumber_query = """
                UPDATE presentation_content
                SET slide_number = slide_number - 1
                WHERE presentation_id = ? AND slide_number > ?
            """
            await self.db.execute(renumber_query, (presentation_id, slide_number))
            await self.db.commit()

            return {"success": True, "message": f"Deleted slide {slide_number}"}

        return {"success": False, "error": "Unknown action"}
