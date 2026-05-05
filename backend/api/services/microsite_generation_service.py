"""
Microsite Generation Service

Orchestrates AI-enhanced microsite generation from workspace sources.
Loads templates, builds context, generates content per section,
runs guardrails, saves sections, creates version snapshots, and links sources.
"""

import json
import uuid
import asyncio
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from api.services.context import ContextService, get_context_service
from open_notebook.database.repository import repo_query, repo_execute, repo_create


class MicrositeGenerationService:
    """
    Service for generating AI-enhanced microsites from workspace sources.

    Flow:
    1. Load template structure (sections, layout, prompts)
    2. Build context from workspace sources (with token counting)
    3. For each section, use template prompt + AI to generate content
    4. Convert markdown to HTML and TipTap JSON
    5. Run guardrails pipeline
    6. Save content sections
    7. Create version snapshot
    8. Link sources to microsite
    """

    def __init__(
        self,
        max_context_tokens: int = 8000,
        temperature: float = 0.7,
        model: str = "gpt-4",
    ):
        self.max_context_tokens = max_context_tokens
        self.temperature = temperature
        self.model = model
        self.context_service = get_context_service(
            max_tokens=max_context_tokens, model=model
        )

    async def generate_microsite(
        self,
        microsite_id: str,
        template_id: str,
        source_ids: List[str],
        notebook_id: str,
        user_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main orchestration method for microsite generation.

        Args:
            microsite_id: ID of the microsite to populate
            template_id: Template to use for structure
            source_ids: List of source IDs to pull content from
            notebook_id: Parent notebook ID
            user_prompt: Optional user instructions for generation

        Returns:
            Dict with generation results including sections, moderation report, version
        """
        # 0. Get microsite record for title and settings
        microsite_results = await repo_query(
            "SELECT title, generation_config FROM microsites WHERE id = :id",
            {"id": microsite_id}
        )
        microsite_title = microsite_results[0].get("title", "Microsite") if microsite_results else "Microsite"
        generation_config = self._parse_json_field(microsite_results[0].get("generation_config", "{}")) if microsite_results else {}
        logo_url = generation_config.get("logo_url")

        # 1. Load template
        template = await self._load_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        structure = self._parse_json_field(template.get("structure", "{}"))
        styles = self._parse_json_field(template.get("default_styles", "{}"))

        # 2. Build context from sources
        source_context = await self._build_source_context(source_ids, notebook_id)

        # 3. Generate content for each section
        sections = structure.get("sections", [])
        generated_sections = []

        for section_def in sections:
            try:
                section_content = await self._generate_section_content(
                    section_def=section_def,
                    source_context=source_context,
                    user_prompt=user_prompt,
                    template_name=template.get("name", ""),
                )
                generated_sections.append(section_content)
            except Exception as e:
                print(f"Error generating section {section_def.get('id', '?')}: {e}")
                # Use default content as fallback
                generated_sections.append({
                    "section_id": section_def.get("id", str(uuid.uuid4())),
                    "section_type": section_def.get("type", "text"),
                    "title": section_def.get("title", "Section"),
                    "content_html": section_def.get("default_content", {}).get("html", "<p>Content generation failed. Please edit manually.</p>"),
                    "content_json": json.dumps(section_def.get("default_content", {}).get("tiptap", {"type": "doc", "content": []})),
                    "order_num": section_def.get("order", 0),
                    "is_visible": True,
                    "error": str(e),
                })

        # 4. Run guardrails
        moderation_report = {
            "status": "passed",
            "overall_score": 1.0,
            "layers": [],  # Changed from {} to [] to match ModerationReport model
            "issues": [],
            "requires_review": False
        }
        try:
            from api.services.guardrails_service import GuardrailsService
            guardrails = GuardrailsService()
            all_html = "\n".join(s.get("content_html", "") for s in generated_sections)
            raw_report = await guardrails.moderate_content(
                microsite_id=microsite_id,
                content=all_html,
                source_ids=source_ids,
            )

            # Convert layers from dict to list if needed (to match ModerationReport.layers: List[ModerationLayerResult])
            if isinstance(raw_report.get("layers"), dict):
                layers_list = []
                for layer_name, layer_data in raw_report["layers"].items():
                    layers_list.append({
                        "layer": layer_name,
                        "status": layer_data.get("status", "passed"),
                        "score": layer_data.get("score", 1.0),
                        "issues": layer_data.get("issues", []),
                        "message": layer_data.get("message"),
                    })
                raw_report["layers"] = layers_list

            # Ensure all issues have 'description' field (Pydantic model requires it)
            for issue in raw_report.get("issues", []):
                if "description" not in issue and "message" in issue:
                    issue["description"] = issue["message"]
                elif "description" not in issue:
                    issue["description"] = "No description provided"

            moderation_report = raw_report
        except Exception as e:
            print(f"Guardrails error (continuing with warning): {e}")
            moderation_report["status"] = "warning"
            moderation_report["issues"].append({
                "type": "system",
                "severity": "medium",
                "description": f"Guardrails service unavailable: {e}",
                "location": None,
            })
            moderation_report["requires_review"] = True

        # 5. Save content sections and enrich with database IDs
        now = datetime.utcnow()
        saved_sections = []
        for idx, section in enumerate(generated_sections):
            section_id = str(uuid.uuid4())
            created_iso = now.isoformat()
            updated_iso = now.isoformat()

            await repo_execute(
                """
                INSERT INTO microsite_content
                    (id, microsite_id, section_id,
                     content_html, content_json, order_num, is_visible, created, updated)
                VALUES
                    (:id, :microsite_id, :section_id,
                     :content_html, :content_json, :order_num, :is_visible, :created, :updated)
                """,
                {
                    "id": section_id,
                    "microsite_id": microsite_id,
                    "section_id": section.get("section_id", f"section_{idx}"),
                    "content_html": section.get("content_html", ""),
                    "content_json": section.get("content_json", "{}"),
                    "order_num": idx,
                    "is_visible": 1,
                    "created": created_iso,
                    "updated": updated_iso,
                },
            )

            # Build section response with all required fields for MicrositeContentSection
            saved_sections.append({
                "id": section_id,
                "microsite_id": microsite_id,
                "section_id": section.get("section_id", f"section_{idx}"),
                "order_num": idx,
                "content_html": section.get("content_html", ""),
                "content_json": section.get("content_json", "{}"),
                "is_visible": True,
                "created": created_iso,
                "updated": updated_iso,
            })

        # 6. Create version snapshot (use saved_sections which have all fields)
        full_html = self._render_full_html(
            saved_sections,
            styles,
            template,
            logo_url=logo_url,
            site_title=microsite_title
        )
        # Build content snapshot for rollback
        content_snapshot = json.dumps([{
            "section_id": s.get("section_id"),
            "content_html": s.get("content_html", ""),
            "content_json": s.get("content_json", "{}"),
            "order_num": i,
        } for i, s in enumerate(saved_sections)])

        version_number = await self._create_version_snapshot(
            microsite_id=microsite_id,
            full_html=full_html,
            full_css=styles.get("css", ""),
            content_snapshot=content_snapshot,
            created_by="system",
        )

        # 7. Link sources to microsite
        for source_id in source_ids:
            try:
                await repo_execute(
                    """
                    INSERT OR IGNORE INTO microsite_sources (microsite_id, source_id, created)
                    VALUES (:microsite_id, :source_id, :created)
                    """,
                    {
                        "microsite_id": microsite_id,
                        "source_id": source_id,
                        "created": datetime.utcnow().isoformat(),
                    },
                )
            except Exception:
                pass  # Ignore duplicate links

        # 8. Update microsite record
        moderation_status = moderation_report.get("status", "passed")
        await repo_execute(
            """
            UPDATE microsites
            SET template_id = :template_id,
                generation_config = :generation_config,
                moderation_status = :moderation_status,
                published_version = :published_version,
                last_generated = :last_generated,
                updated = :updated
            WHERE id = :id
            """,
            {
                "template_id": template_id,
                "generation_config": json.dumps({
                    "user_prompt": user_prompt,
                    "source_ids": source_ids,
                    "model": self.model,
                    "temperature": self.temperature,
                }),
                "moderation_status": moderation_status,
                "published_version": version_number,
                "last_generated": datetime.utcnow().isoformat(),
                "updated": datetime.utcnow().isoformat(),
                "id": microsite_id,
            },
        )

        return {
            "microsite_id": microsite_id,
            "version": version_number,
            "sections": saved_sections,  # Now includes id, microsite_id, created, updated
            "moderation": moderation_report,  # Now has layers as list and issues with description
            "preview_url": f"/api/microsites/{microsite_id}/preview",  # Added required preview_url
            "template": template.get("name", ""),
            "sources_linked": len(source_ids),
        }

    async def _load_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Load a template by ID."""
        results = await repo_query(
            "SELECT * FROM microsite_templates WHERE id = :id",
            {"id": template_id},
        )
        return results[0] if results else None

    async def _build_source_context(
        self, source_ids: List[str], notebook_id: str
    ) -> str:
        """
        Build combined context from multiple sources.

        Uses ContextService for token counting and truncation.
        """
        context = await self.context_service.build_notebook_context(
            notebook_id=notebook_id,
            selected_source_ids=source_ids,
            include_notes=True,
        )
        return context.get("content", "")

    async def _generate_section_content(
        self,
        section_def: Dict[str, Any],
        source_context: str,
        user_prompt: Optional[str],
        template_name: str,
    ) -> Dict[str, Any]:
        """
        Generate AI-enhanced content for a single section.

        Uses the LiteLLM proxy pattern for AI calls.
        """
        section_id = section_def.get("id", str(uuid.uuid4()))
        section_type = section_def.get("type", "text")
        prompt_template = section_def.get("prompt_template", "")
        title = section_def.get("title", section_type.replace("_", " ").title())

        # Build system prompt based on section type
        system_prompt = await self._get_section_system_prompt(
            section_type,
            template_name,
            title=title,
            user_prompt=user_prompt or "",
            source_context=source_context or ""
        )

        # Build user prompt
        user_message_parts = [
            f"Generate content for the '{title}' section of a {template_name} microsite.",
        ]
        if prompt_template:
            user_message_parts.append(f"Section guidance: {prompt_template}")
        if user_prompt:
            user_message_parts.append(f"User instructions: {user_prompt}")
        if source_context:
            # Check if final deliverable is available
            has_final_deliverable = "FINAL DELIVERABLE" in source_context
            if has_final_deliverable:
                user_message_parts.append("\n⚠️ **IMPORTANT: A comprehensive FINAL DELIVERABLE analysis is available in the sources below. This contains deep, expert-level analysis and strategic insights synthesizing all workspace data. PRIORITIZE information from the FINAL DELIVERABLE as it represents the most authoritative and comprehensive analysis.**\n")
            user_message_parts.append(f"\n--- Source Material ---\n{source_context}")

        user_message = "\n\n".join(user_message_parts)

        # Call AI via LiteLLM proxy
        markdown_content = await self._call_llm(system_prompt, user_message)

        # Convert to HTML and TipTap JSON
        content_html = self._markdown_to_html(markdown_content)
        content_json = json.dumps(self._markdown_to_tiptap(markdown_content))

        return {
            "section_id": section_id,
            "section_type": section_type,
            "title": title,
            "content_html": content_html,
            "content_json": content_json,
            "order_num": section_def.get("order", 0),
            "is_visible": True,
        }

    async def _get_section_system_prompt(self, section_type: str, template_name: str, title: str = "", user_prompt: str = "", source_context: str = "") -> str:
        """Get tailored system prompt for each section type with professional, modern tone and chart generation emphasis."""
        from api.services.prompt_loader import load_prompt

        # Common chart generation instruction to be added to all prompts
        chart_instruction = (
            "\n\n**IMPORTANT - VISUALIZE DATA WITH CHARTS:**\n"
            "- If the content contains numerical data, statistics, comparisons, trends, percentages, or time-series data, YOU MUST generate charts using Mermaid syntax\n"
            "- Look for: revenue figures, growth rates, market shares, timelines, distributions, comparisons, rankings, metrics\n"
            "- Chart types to use:\n"
            "  - Line charts: trends over time, growth trajectories, time-series data\n"
            "  - Bar charts: comparisons, rankings, categorical data\n"
            "  - Pie charts: distributions, market share, percentages that sum to 100%\n"
            "  - Gantt charts: timelines, project schedules, roadmaps\n"
            "- Format: Use Mermaid code blocks like this:\n"
            "```mermaid\n"
            "%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#0066cc'}}}%%\n"
            "graph TD\n"
            "    A[Start] --> B[Process]\n"
            "```\n"
            "- ALWAYS include %%{{init: {{'theme':'base', 'themeVariables': {{ 'primaryColor':'#0066cc'}}}}}}%% at the top of every chart\n"
            "- Place charts IMMEDIATELY after the related paragraph or section\n"
            "- Add a brief caption after each chart explaining what it shows\n"
            "- If no visualizable data exists, proceed with text content only\n"
        )

        # Hardcoded fallback prompts for backward compatibility
        fallback_prompts = {
            "hero": (
                "You are an expert copywriter creating a compelling hero section for a modern, professional website. "
                "Create a powerful headline (H1) that's 8-12 words and immediately captures the core value. "
                "Add an engaging subheadline (H2) that's 15-25 words explaining the specific benefit. "
                "Use concrete language - avoid clichés like 'innovative', 'cutting-edge', 'revolutionary'. "
                "Focus on the tangible value or outcome. "
                "Format: # Headline\\n## Subheadline\\n\\nOptional: 1-2 sentences of supporting detail. "
                "Output in Markdown format."
                + chart_instruction
            ),
            "summary": (
                "You are a business analyst creating an executive summary for decision-makers. "
                "Write 2-3 short paragraphs (3-4 sentences each) that capture: "
                "1) The main topic or challenge, 2) Key findings or approach, 3) Primary outcomes or implications. "
                "Use specific numbers and concrete examples from the source material. "
                "Write in active voice. Start with the most important information. "
                "Output in Markdown format."
                + chart_instruction
            ),
            "insights": (
                "You are a data analyst presenting key findings with visual hierarchy. "
                "Extract 4-6 insights from the source material. For each: "
                "- Use H3 heading with the insight statement (be specific, not vague) "
                "- Follow with 2-3 sentences of supporting evidence or context "
                "- Include numbers, percentages, or quotes where available "
                "Prioritize surprising or actionable insights. Use parallel structure. "
                "Output in Markdown format."
                + chart_instruction
            ),
            "features": (
                "You are a product marketer creating a features section with strong visual hierarchy. "
                "Present 3-6 features, each with: "
                "- Emoji or icon prefix (📊 🔧 🚀 💡 ⚡ 🎯) "
                "- Feature name as H3 heading (3-5 words) "
                "- 1-2 sentences focusing on USER BENEFITS (not technical specs) "
                "Use parallel sentence structure. Be specific. Avoid generic buzzwords. "
                "Output in Markdown format."
                + chart_instruction
            ),
            "call_to_action": (
                "You are a conversion specialist creating a compelling CTA section. "
                "Structure: "
                "- Headline (H2): Create urgency or emphasize the benefit (8-12 words) "
                "- Supporting text: 1-2 sentences that overcome the last objection "
                "- Button text: Wrap in **bold** and make it action-specific (e.g., '**Start Free Trial**', '**Download Guide**', '**Book Demo**') "
                "Be direct. Create urgency without being pushy. "
                "Output in Markdown format."
                + chart_instruction
            ),
            "conclusion": (
                "You are a strategic writer crafting a forward-looking conclusion. "
                "Structure (2-3 paragraphs): "
                "- Brief recap: 1 sentence summarizing the main point "
                "- Implications: 2-3 sentences on what this means or why it matters "
                "- Next steps: Specific, actionable suggestions "
                "Avoid phrases like 'in conclusion'. End with momentum, not finality. "
                "Output in Markdown format."
                + chart_instruction
            ),
            "about": (
                "You are a brand storyteller creating an engaging About section. "
                "Write 2-3 paragraphs that tell a story: "
                "- Start with the mission or 'why' (purpose-driven, not generic) "
                "- Highlight unique approach or key capabilities (specific details) "
                "- Close with credentials or track record (concrete achievements) "
                "Use first-person plural (we/our) or third-person. Be authentic. "
                "Output in Markdown format."
                + chart_instruction
            ),
            "pricing": (
                "You are a pricing strategist creating a clear, value-focused pricing section. "
                "For each pricing tier: "
                "- Tier name (H3) - e.g., 'Starter', 'Professional', 'Enterprise' "
                "- Price in bold: **$XX/month** (if available) "
                "- 4-6 bullet points of included features (use parallel structure) "
                "- Optional: Add '✨ Most Popular' badge to recommended tier "
                "Focus on value, not just features. Use benefit-oriented language. "
                "Output in Markdown format."
                + chart_instruction
            ),
            "testimonials": (
                "You are a social proof curator creating a testimonials section. "
                "If the source material contains customer feedback, quotes, or reviews: "
                "- Format each as a blockquote (> quote text) "
                "- Add attribution: **Name**, *Title*, Company "
                "- Include 2-4 testimonials that highlight different benefits "
                "If NO testimonials in source material, create a placeholder structure or skip. "
                "Output in Markdown format with proper blockquote syntax."
                + chart_instruction
            ),
            "faq": (
                "You are a UX writer creating a helpful FAQ section. "
                "Extract or infer 5-8 questions from the source material. For each: "
                "- Question as H3 (start with How/What/Why/Can/Is) "
                "- Answer in 1-3 clear, direct sentences "
                "Anticipate common objections or concerns. Use natural, conversational language. "
                "Order from most to least common. "
                "Output in Markdown format."
                + chart_instruction
            ),
            "footer": (
                "You are a minimalist designer creating footer content. "
                "Include: "
                "- Brief tagline or mission statement (1 sentence) "
                "- Optional: Key contact info or important links "
                "Keep it clean and professional. Do NOT add copyright notice (auto-generated). "
                "Output in Markdown format."
                + chart_instruction
            ),
            "toc": (
                "You are a technical writer creating a scannable table of contents. "
                "Based on the source material structure: "
                "- Use numbered lists for main sections "
                "- Use nested bullets for subsections "
                "- Make section titles descriptive (not just 'Section 1') "
                "- Include 5-10 main sections "
                "Output in Markdown format."
                + chart_instruction
            ),
            "sources_list": (
                "You are a research librarian curating a sources list. "
                "For each source: "
                "- Source title as H3 or bold text "
                "- 1-2 sentences describing what it covers "
                "- Optional: Add publication date or author if available "
                "Group by type if multiple source types exist. "
                "Output in Markdown format."
                + chart_instruction
            ),
        }

        fallback_default = (
            f"You are a professional web content writer creating a {section_type.replace('_', ' ')} section "
            f"for a modern {template_name} microsite. "
            f"Generate clear, scannable content with: "
            f"- Descriptive headings (H2/H3) that stand alone "
            f"- Short paragraphs (2-3 sentences maximum) "
            f"- Bullet points for lists (parallel structure) "
            f"- Active voice and concrete, specific examples "
            f"- Numbers and data points where available "
            f"Focus on user value and clarity. Avoid marketing fluff. "
            f"Output in Markdown format with proper hierarchy."
            + chart_instruction
        )

        # Try to load from database
        template_key = f"microsite_{section_type}" if section_type in fallback_prompts else "microsite_default"
        fallback = fallback_prompts.get(section_type, fallback_default)

        return await load_prompt(
            template_key,
            variables={
                "title": title,
                "template_name": template_name,
                "user_prompt": user_prompt,
                "source_context": source_context,
                "section_type": section_type.replace('_', ' ')
            },
            fallback=fallback
        )

    async def _call_llm(self, system_prompt: str, user_message: str) -> str:
        """
        Call the LLM via LiteLLM proxy pattern.

        Follows the same credential retrieval pattern as embedding_service.py.
        """
        try:
            from api.routers.credentials import _credentials_store
            from api.services.settings import get_setting

            model_id = await get_setting("language_model_id", "")
            if not model_id:
                raise ValueError("No language model configured. Please configure in Settings.")

            credential = _credentials_store.get(model_id)
            if not credential:
                raise ValueError(f"Language model '{model_id}' not found in credentials")

            api_url = credential["base_url"]
            api_key = credential["api_key"]
            model_name = credential.get("model_name", credential.get("name", self.model))

        except ImportError:
            raise ValueError("Credentials store not available")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": self.temperature,
                    "max_tokens": 2000,
                },
            )

            if response.status_code != 200:
                raise Exception(
                    f"LLM API error: {response.status_code} - {response.text}"
                )

            result = response.json()
            return result["choices"][0]["message"]["content"]

    def _convert_markdown_tables(self, text: str) -> str:
        """
        Convert markdown tables to HTML tables with proper styling.

        Handles tables in format:
        | Header 1 | Header 2 |
        |----------|----------|
        | Cell 1   | Cell 2   |
        """
        lines = text.split('\n')
        result_lines = []
        in_table = False
        table_lines = []

        for line in lines:
            # Check if line looks like a table row (contains |)
            if '|' in line and line.strip().startswith('|'):
                table_lines.append(line.strip())
                in_table = True
            else:
                # If we were in a table and now we're not, process the table
                if in_table and table_lines:
                    html_table = self._process_markdown_table(table_lines)
                    result_lines.append(html_table)
                    table_lines = []
                    in_table = False
                result_lines.append(line)

        # Handle table at end of text
        if table_lines:
            html_table = self._process_markdown_table(table_lines)
            result_lines.append(html_table)

        return '\n'.join(result_lines)

    def _process_markdown_table(self, table_lines: list) -> str:
        """Process a list of table lines into HTML table."""
        if not table_lines:
            return ""

        # Remove empty lines and separators
        cleaned_lines = []
        for line in table_lines:
            line = line.strip()
            if line and not all(c in '|-: ' for c in line):
                cleaned_lines.append(line)

        if not cleaned_lines:
            return ""

        # First line is header
        header_line = cleaned_lines[0]
        headers = [cell.strip() for cell in header_line.split('|')[1:-1]]  # Remove first and last empty splits

        # Rest are data rows
        data_rows = []
        for line in cleaned_lines[1:]:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if cells:  # Skip empty rows
                data_rows.append(cells)

        # Build HTML table
        html = '<table class="w-full border-collapse my-6">\n'

        # Header
        html += '  <thead>\n    <tr>\n'
        for header in headers:
            html += f'      <th class="px-4 py-2 bg-gray-100 border border-gray-300 text-left font-semibold">{header}</th>\n'
        html += '    </tr>\n  </thead>\n'

        # Body
        html += '  <tbody>\n'
        for row in data_rows:
            html += '    <tr>\n'
            for cell in row:
                html += f'      <td class="px-4 py-2 border border-gray-300">{cell}</td>\n'
            html += '    </tr>\n'
        html += '  </tbody>\n'
        html += '</table>\n'

        return html

    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        Convert markdown to professional, well-structured HTML.

        Enhanced with proper spacing, styling classes, modern formatting, and Mermaid chart support.
        """
        if not markdown_text:
            return ""

        html = markdown_text

        # Convert markdown tables to HTML first (before other conversions)
        html = self._convert_markdown_tables(html)

        # Convert Mermaid code blocks to div containers
        html = re.sub(
            r'```mermaid\n(.*?)```',
            r'<div class="mermaid-chart my-6">\1</div>',
            html,
            flags=re.DOTALL
        )

        # Headers with proper spacing classes
        html = re.sub(r'^#### (.+)$', r'<h4 class="mb-3 mt-5 text-xl font-semibold">\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3 class="mb-4 mt-6 text-2xl font-semibold">\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2 class="mb-4 mt-8 text-3xl font-bold">\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1 class="mb-6 text-4xl font-bold">\1</h1>', html, flags=re.MULTILINE)

        # Blockquotes for testimonials (with styling)
        html = re.sub(
            r'^> (.+)$',
            r'<blockquote class="border-l-4 border-primary pl-4 py-2 my-4 italic text-gray-700">\1</blockquote>',
            html,
            flags=re.MULTILINE
        )

        # Bold and italic
        html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong class="font-semibold">\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em class="italic">\1</em>', html)
        html = re.sub(r'\_\_(.+?)\_\_', r'<strong class="font-semibold">\1</strong>', html)
        html = re.sub(r'\_(.+?)\_', r'<em class="italic">\1</em>', html)

        # Links with hover styling
        html = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'<a href="\2" class="text-primary hover:underline">\1</a>',
            html
        )

        # Unordered lists with better spacing
        lines = html.split('\n')
        result_lines = []
        in_ul = False

        for i, line in enumerate(lines):
            if re.match(r'^[-*+] ', line):
                # List item
                item_content = re.sub(r'^[-*+] ', '', line)
                if not in_ul:
                    result_lines.append('<ul class="list-disc pl-6 space-y-2 my-4">')
                    in_ul = True
                result_lines.append(f'  <li class="leading-relaxed">{item_content}</li>')
            else:
                if in_ul:
                    result_lines.append('</ul>')
                    in_ul = False
                result_lines.append(line)

        if in_ul:
            result_lines.append('</ul>')

        html = '\n'.join(result_lines)

        # Ordered lists
        html = re.sub(r'^\d+\. (.+)$', r'<li class="leading-relaxed">\1</li>', html, flags=re.MULTILINE)
        html = re.sub(
            r'(<li class="leading-relaxed">.*?</li>\n?)+',
            lambda m: f'<ol class="list-decimal pl-6 space-y-2 my-4">{m.group(0)}</ol>',
            html,
            flags=re.DOTALL
        )

        # Code blocks with syntax highlighting placeholder
        html = re.sub(
            r'```(\w*)\n(.*?)```',
            r'<pre class="bg-gray-50 border border-gray-200 rounded-lg p-4 my-4 overflow-x-auto"><code class="language-\1 text-sm">\2</code></pre>',
            html,
            flags=re.DOTALL
        )

        # Inline code
        html = re.sub(
            r'`([^`]+)`',
            r'<code class="bg-gray-100 px-2 py-1 rounded text-sm font-mono">\1</code>',
            html
        )

        # Horizontal rule with spacing
        html = re.sub(
            r'^---+$',
            r'<hr class="my-8 border-t-2 border-gray-200">',
            html,
            flags=re.MULTILINE
        )

        # Paragraphs with proper spacing
        lines = html.split('\n')
        result_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                result_lines.append('')
            elif stripped.startswith('<'):
                # Already HTML tag
                result_lines.append(line)
            elif not any(stripped.startswith(tag) for tag in ['<h', '<ul', '<ol', '<blockquote', '<pre', '<hr', '<div']):
                # Plain text line - wrap in paragraph
                result_lines.append(f'<p class="mb-4 leading-relaxed">{stripped}</p>')
            else:
                result_lines.append(line)

        html = '\n'.join(result_lines)

        # Clean up excessive newlines
        html = re.sub(r'\n{3,}', '\n\n', html)

        # Preserve emojis (they should pass through unchanged)
        return html.strip()

    def _markdown_to_tiptap(self, markdown_text: str) -> Dict[str, Any]:
        """
        Convert markdown to TipTap JSON format for the WYSIWYG editor.

        Returns a basic TipTap document structure.
        """
        if not markdown_text:
            return {"type": "doc", "content": []}

        content = []
        lines = markdown_text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Headers
            if line.startswith('### '):
                content.append({
                    "type": "heading",
                    "attrs": {"level": 3},
                    "content": [{"type": "text", "text": line[4:]}],
                })
            elif line.startswith('## '):
                content.append({
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": line[3:]}],
                })
            elif line.startswith('# '):
                content.append({
                    "type": "heading",
                    "attrs": {"level": 1},
                    "content": [{"type": "text", "text": line[2:]}],
                })
            # List items
            elif line.startswith('- ') or line.startswith('* '):
                items = []
                while i < len(lines) and (lines[i].strip().startswith('- ') or lines[i].strip().startswith('* ')):
                    item_text = lines[i].strip()[2:]
                    items.append({
                        "type": "listItem",
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": item_text}],
                        }],
                    })
                    i += 1
                content.append({"type": "bulletList", "content": items})
                continue
            # Ordered list items
            elif re.match(r'^\d+\. ', line):
                items = []
                while i < len(lines) and re.match(r'^\d+\. ', lines[i].strip()):
                    item_text = re.sub(r'^\d+\. ', '', lines[i].strip())
                    items.append({
                        "type": "listItem",
                        "content": [{
                            "type": "paragraph",
                            "content": [{"type": "text", "text": item_text}],
                        }],
                    })
                    i += 1
                content.append({"type": "orderedList", "content": items})
                continue
            # Horizontal rule
            elif line.startswith('---'):
                content.append({"type": "horizontalRule"})
            # Code block
            elif line.startswith('```'):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                content.append({
                    "type": "codeBlock",
                    "content": [{"type": "text", "text": '\n'.join(code_lines)}],
                })
            # Regular paragraph
            else:
                content.append({
                    "type": "paragraph",
                    "content": self._parse_inline_marks(line),
                })

            i += 1

        return {"type": "doc", "content": content}

    def _parse_inline_marks(self, text: str) -> List[Dict[str, Any]]:
        """Parse inline markdown marks (bold, italic, links) into TipTap text nodes."""
        # Simple implementation: return as plain text
        # A full implementation would parse bold/italic/links into marked text nodes
        if not text:
            return []

        nodes = []
        # Handle bold
        parts = re.split(r'\*\*(.+?)\*\*', text)
        for idx, part in enumerate(parts):
            if not part:
                continue
            if idx % 2 == 1:
                # Bold text
                nodes.append({
                    "type": "text",
                    "text": part,
                    "marks": [{"type": "bold"}],
                })
            else:
                # Check for italic within non-bold text
                italic_parts = re.split(r'\*(.+?)\*', part)
                for j, ipart in enumerate(italic_parts):
                    if not ipart:
                        continue
                    if j % 2 == 1:
                        nodes.append({
                            "type": "text",
                            "text": ipart,
                            "marks": [{"type": "italic"}],
                        })
                    else:
                        nodes.append({"type": "text", "text": ipart})

        if not nodes:
            nodes.append({"type": "text", "text": text})

        return nodes

    def _render_full_html(
        self,
        sections: List[Dict[str, Any]],
        styles: Dict[str, Any],
        template: Dict[str, Any],
        logo_url: Optional[str] = None,
        site_title: Optional[str] = None,
        nav_items: Optional[List[Dict[str, str]]] = None,
        footer_text: Optional[str] = None,
    ) -> str:
        """Render all sections into a complete HTML document with header, banner, and footer."""
        primary_color = styles.get("primary_color", "#0066cc")
        font_heading = styles.get("font_heading", "Inter")
        font_body = styles.get("font_body", "system-ui")
        bg_color = styles.get("background_color", "#ffffff")
        text_color = styles.get("text_color", "#1a1a1a")

        # Default navigation items if none provided
        if nav_items is None:
            nav_items = [
                {"label": "Home", "url": "#home"},
                {"label": "About", "url": "#about"},
                {"label": "Content", "url": "#content"},
                {"label": "Contact", "url": "#contact"},
            ]

        # Organize sections by type
        hero_section = None
        main_sections = []
        footer_content = ""

        for section in sections:
            section_type = section.get("section_type", "text")
            section_html = section.get("content_html", "")
            section_id = section.get("section_id", "")

            if section_type == "hero":
                hero_section = f'<div class="prose">\n{section_html}\n</div>'
            elif section_type in ["footer", "conclusion"]:
                footer_content += f'<div class="footer-section" data-section-id="{section_id}">\n<div class="prose">\n{section_html}\n</div>\n</div>\n'
            else:
                main_sections.append(f'<section class="content-section section-{section_type}" data-section-id="{section_id}">\n<div class="prose">\n{section_html}\n</div>\n</section>\n')

        main_sections_html = "\n".join(main_sections)
        template_name = site_title or template.get("display_name", template.get("name", "Microsite")) if isinstance(template, dict) else "Microsite"

        # Extract RGB values from primary color for gradient calculation
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        def rgb_to_hex(r, g, b):
            return f'#{r:02x}{g:02x}{b:02x}'

        def lighten_color(hex_color, factor=0.2):
            """Lighten a color by mixing with white"""
            r, g, b = hex_to_rgb(hex_color)
            r = int(r + (255 - r) * factor)
            g = int(g + (255 - g) * factor)
            b = int(b + (255 - b) * factor)
            return rgb_to_hex(r, g, b)

        def darken_color(hex_color, factor=0.2):
            """Darken a color by mixing with black"""
            r, g, b = hex_to_rgb(hex_color)
            r = int(r * (1 - factor))
            g = int(g * (1 - factor))
            b = int(b * (1 - factor))
            return rgb_to_hex(r, g, b)

        primary_light = lighten_color(primary_color, 0.3)
        primary_dark = darken_color(primary_color, 0.2)

        # Logo rendering - use custom logo URL if provided, otherwise show letter icon
        if logo_url:
            logo_html = f'<img src="{logo_url}" alt="{template_name}" class="logo-image" />'
        else:
            logo_html = f'<div class="logo-icon">{template_name[0].upper()}</div>'

        # Generate navigation menu HTML
        nav_html = "\n".join([
            f'                    <li><a href="{item["url"]}">{item["label"]}</a></li>'
            for item in nav_items
        ])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{template_name}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'base',
            themeVariables: {{
                primaryColor: '{primary_color}',
                primaryTextColor: '#fff',
                primaryBorderColor: '{primary_dark}',
                lineColor: '{primary_color}',
                secondaryColor: '{primary_light}',
                tertiaryColor: '#f9fafb'
            }}
        }});
    </script>
    <style>
        :root {{
            --primary-color: {primary_color};
            --primary-dark: {primary_dark};
            --primary-light: {primary_light};
            --font-heading: '{font_heading}', sans-serif;
            --font-body: '{font_body}', sans-serif;
            --bg-color: {bg_color};
            --text-color: {text_color};
            --border-color: #e5e7eb;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-600: #4b5563;
            --gray-800: #1f2937;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: var(--font-body);
            color: var(--text-color);
            background-color: var(--bg-color);
            line-height: 1.6;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }}

        /* Header Styles */
        .site-header {{
            background: white;
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        }}

        .header-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 1rem 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 2rem;
        }}

        .site-logo {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary-color);
            text-decoration: none;
            font-family: var(--font-heading);
        }}

        .logo-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 1.25rem;
        }}

        .logo-image {{
            height: 40px;
            width: auto;
            object-fit: contain;
        }}

        .site-nav {{
            display: flex;
            gap: 2rem;
            list-style: none;
            align-items: center;
        }}

        .site-nav a {{
            color: var(--gray-600);
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s;
        }}

        .site-nav a:hover {{
            color: var(--primary-color);
        }}

        /* Hero/Banner Section */
        .hero-banner {{
            background: linear-gradient(135deg, var(--primary-light) 0%, var(--primary-color) 100%);
            color: white;
            padding: 4rem 2rem;
            text-align: center;
        }}

        .hero-banner h1 {{
            font-size: 3rem;
            margin-bottom: 1rem;
            font-weight: 700;
            color: white;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        /* Hide section title "Hero" in hero sections */
        .hero-banner h1:first-of-type:contains("Hero"),
        .hero-banner > .prose > h1:first-child {{
            /* If the first h1 only contains "Hero", hide it */
        }}

        /* Alternative: hide first h1 if it's just the section title */
        .section-hero .prose > h1:only-child {{
            display: none;
        }}

        .hero-banner h2 {{
            font-size: 1.5rem;
            font-weight: 400;
            opacity: 0.95;
            color: white;
            max-width: 700px;
            margin: 0 auto;
        }}

        /* Main Content Container */
        .main-content {{
            flex: 1;
            max-width: 1200px;
            width: 100%;
            margin: 0 auto;
            padding: 3rem 2rem;
        }}

        /* Content Sections */
        .content-section {{
            margin-bottom: 3rem;
            padding: 2rem;
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .content-section:last-child {{
            margin-bottom: 0;
        }}

        /* Typography */
        h1, h2, h3, h4, h5, h6 {{
            font-family: var(--font-heading);
            margin-bottom: 0.75em;
            font-weight: 600;
            line-height: 1.3;
        }}

        h1 {{ font-size: 2.5rem; color: var(--gray-800); }}
        h2 {{ font-size: 2rem; color: var(--gray-800); }}
        h3 {{ font-size: 1.5rem; color: var(--gray-800); }}
        h4 {{ font-size: 1.25rem; color: var(--gray-800); }}

        p {{
            margin-bottom: 1.25em;
            line-height: 1.75;
            color: var(--gray-600);
        }}

        /* Prose Container */
        .prose {{
            max-width: none;
        }}

        .prose > * {{
            margin-top: 0;
            margin-bottom: 1.25em;
        }}

        .prose > *:first-child {{
            margin-top: 0;
        }}

        .prose > *:last-child {{
            margin-bottom: 0;
        }}

        .prose h1,
        .prose h2,
        .prose h3 {{
            margin-top: 1.5em;
            margin-bottom: 0.75em;
        }}

        .prose h1:first-child,
        .prose h2:first-child,
        .prose h3:first-child {{
            margin-top: 0;
        }}

        .prose ul,
        .prose ol {{
            padding-left: 1.75em;
        }}

        .prose li {{
            margin-bottom: 0.5em;
        }}

        .prose blockquote {{
            border-left: 4px solid var(--primary-color);
            padding-left: 1.5em;
            margin-left: 0;
            margin-right: 0;
            font-style: italic;
            color: var(--gray-600);
        }}

        .prose strong {{
            font-weight: 600;
            color: var(--gray-800);
        }}

        .prose em {{
            font-style: italic;
        }}

        .prose code {{
            background: var(--gray-100);
            padding: 0.2em 0.4em;
            border-radius: 4px;
            font-size: 0.875em;
            font-family: 'Courier New', monospace;
        }}

        .prose pre {{
            background: var(--gray-50);
            padding: 1.25rem;
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid var(--border-color);
        }}

        .prose pre code {{
            background: none;
            padding: 0;
        }}

        .prose hr {{
            border: none;
            border-top: 2px solid var(--border-color);
            margin: 2rem 0;
        }}

        .prose a {{
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 500;
        }}

        .prose a:hover {{
            text-decoration: underline;
        }}

        /* Text Alignment from TipTap */
        .prose [style*="text-align: left"] {{
            text-align: left;
        }}

        .prose [style*="text-align: center"] {{
            text-align: center;
        }}

        .prose [style*="text-align: right"] {{
            text-align: right;
        }}

        .prose [style*="text-align: justify"] {{
            text-align: justify;
        }}

        /* Links */
        a {{
            color: var(--primary-color);
            text-decoration: none;
            font-weight: 500;
        }}

        a:hover {{
            text-decoration: underline;
            color: var(--primary-dark);
        }}

        /* Lists */
        ul, ol {{
            margin-left: 1.75em;
            margin-bottom: 1.25em;
            color: var(--gray-600);
        }}

        li {{
            margin-bottom: 0.5em;
            line-height: 1.75;
        }}

        /* Code Blocks */
        pre {{
            background: var(--gray-50);
            padding: 1.25rem;
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid var(--border-color);
            margin-bottom: 1.25em;
        }}

        code {{
            font-family: 'Courier New', monospace;
            background: var(--gray-100);
            padding: 0.2em 0.5em;
            border-radius: 4px;
            font-size: 0.9em;
        }}

        pre code {{
            background: none;
            padding: 0;
        }}

        /* Horizontal Rule */
        hr {{
            border: none;
            border-top: 2px solid var(--border-color);
            margin: 2.5rem 0;
        }}

        /* Table Styles */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
        }}

        thead {{
            background: var(--gray-50);
            border-bottom: 2px solid var(--border-color);
        }}

        th {{
            padding: 0.75rem 1rem;
            text-align: left;
            font-weight: 600;
            color: var(--gray-800);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        td {{
            padding: 0.75rem 1rem;
            border-top: 1px solid var(--border-color);
            color: var(--gray-600);
            vertical-align: top;
        }}

        tbody tr:hover {{
            background: var(--gray-50);
        }}

        /* Prose table styles */
        .prose table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
            font-size: 0.9rem;
        }}

        .prose thead {{
            background: var(--gray-50);
            border-bottom: 2px solid var(--border-color);
        }}

        .prose th {{
            padding: 0.75rem 1rem;
            text-align: left;
            font-weight: 600;
            color: var(--gray-800);
            font-size: 0.875rem;
        }}

        .prose td {{
            padding: 0.75rem 1rem;
            border-top: 1px solid var(--border-color);
            color: var(--gray-600);
            vertical-align: top;
        }}

        .prose tbody tr:hover {{
            background: var(--gray-50);
        }}

        /* Footer */
        .site-footer {{
            background: var(--gray-800);
            color: white;
            padding: 3rem 2rem 2rem;
            margin-top: auto;
        }}

        .footer-container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .footer-section {{
            margin-bottom: 2rem;
        }}

        .footer-section h3 {{
            color: white;
            font-size: 1.25rem;
            margin-bottom: 1rem;
        }}

        .footer-section p {{
            color: rgba(255, 255, 255, 0.8);
            line-height: 1.75;
        }}

        .footer-section a {{
            color: var(--primary-light);
        }}

        .footer-bottom {{
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            padding-top: 1.5rem;
            margin-top: 2rem;
            text-align: center;
            color: rgba(255, 255, 255, 0.6);
            font-size: 0.9rem;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .site-nav {{
                display: none;
            }}

            .hero-banner h1 {{
                font-size: 2rem;
            }}

            .hero-banner h2 {{
                font-size: 1.125rem;
            }}

            .content-section {{
                padding: 1.5rem;
            }}

            .main-content {{
                padding: 2rem 1rem;
            }}
        }}

        /* Utility Classes for Enhanced Content */
        .text-sm {{ font-size: 0.875rem; }}
        .text-xl {{ font-size: 1.25rem; }}
        .text-2xl {{ font-size: 1.5rem; }}
        .text-3xl {{ font-size: 1.875rem; }}
        .text-4xl {{ font-size: 2.25rem; }}

        .font-semibold {{ font-weight: 600; }}
        .font-bold {{ font-weight: 700; }}

        .italic {{ font-style: italic; }}

        .mb-3 {{ margin-bottom: 0.75rem; }}
        .mb-4 {{ margin-bottom: 1rem; }}
        .mb-6 {{ margin-bottom: 1.5rem; }}
        .mt-5 {{ margin-top: 1.25rem; }}
        .mt-6 {{ margin-top: 1.5rem; }}
        .mt-8 {{ margin-top: 2rem; }}
        .my-4 {{ margin-top: 1rem; margin-bottom: 1rem; }}
        .my-8 {{ margin-top: 2rem; margin-bottom: 2rem; }}

        .pl-4 {{ padding-left: 1rem; }}
        .pl-6 {{ padding-left: 1.5rem; }}
        .py-1 {{ padding-top: 0.25rem; padding-bottom: 0.25rem; }}
        .py-2 {{ padding-top: 0.5rem; padding-bottom: 0.5rem; }}
        .px-2 {{ padding-left: 0.5rem; padding-right: 0.5rem; }}
        .p-4 {{ padding: 1rem; }}

        .space-y-2 > * + * {{ margin-top: 0.5rem; }}

        .leading-relaxed {{ line-height: 1.75; }}

        .list-disc {{ list-style-type: disc; }}
        .list-decimal {{ list-style-type: decimal; }}

        .border-l-4 {{ border-left-width: 4px; }}
        .border-primary {{ border-color: var(--primary-color); }}
        .border-gray-200 {{ border-color: var(--gray-200); }}
        .border-t-2 {{ border-top-width: 2px; }}

        .bg-gray-50 {{ background-color: var(--gray-50); }}
        .bg-gray-100 {{ background-color: var(--gray-100); }}

        .text-gray-700 {{ color: var(--gray-600); }}

        .text-primary {{ color: var(--primary-color); }}

        .hover\:underline:hover {{ text-decoration: underline; }}

        .rounded {{ border-radius: 0.25rem; }}
        .rounded-lg {{ border-radius: 0.5rem; }}

        .overflow-x-auto {{ overflow-x: auto; }}

        .font-mono {{ font-family: 'Courier New', monospace; }}

        /* Mermaid Chart Styles */
        .mermaid-chart {{
            background: white;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 2rem;
            margin: 2rem 0;
            overflow-x: auto;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            display: flex;
            justify-content: center;
            align-items: center;
        }}

        .mermaid-chart svg {{
            max-width: 100%;
            height: auto;
        }}

        /* Chart caption styles */
        .chart-caption {{
            text-align: center;
            font-size: 0.9rem;
            color: var(--gray-600);
            font-style: italic;
            margin-top: 0.5rem;
        }}

        /* Custom Styles */
        {styles.get("css", "")}
    </style>
</head>
<body>
    <!-- Header -->
    <header class="site-header">
        <div class="header-container">
            <a href="#" class="site-logo">
                {logo_html}
                <span>{template_name}</span>
            </a>
            <nav>
                <ul class="site-nav">
{nav_html}
                </ul>
            </nav>
        </div>
    </header>

    <!-- Hero Banner -->
    {f'<div class="hero-banner">{hero_section}</div>' if hero_section else ''}

    <!-- Main Content -->
    <main class="main-content" id="content">
        {main_sections_html}
    </main>

    <!-- Footer -->
    <footer class="site-footer">
        <div class="footer-container">
            {footer_content if footer_content else '<div class="footer-section"><p>Powered by SAP Slate</p></div>'}
            <div class="footer-bottom">
                <p>{footer_text if footer_text else f'&copy; {datetime.now().year} {template_name}. All rights reserved.'}</p>
            </div>
        </div>
    </footer>
</body>
</html>"""

    async def _create_version_snapshot(
        self,
        microsite_id: str,
        full_html: str,
        full_css: str,
        content_snapshot: str = "[]",
        created_by: str = "system",
    ) -> int:
        """Create a version snapshot and return the version number."""
        # Get current max version
        results = await repo_query(
            "SELECT MAX(version_number) as max_version FROM microsite_versions WHERE microsite_id = :microsite_id",
            {"microsite_id": microsite_id},
        )
        current_max = results[0]["max_version"] if results and results[0]["max_version"] else 0
        new_version = current_max + 1

        await repo_execute(
            """
            INSERT INTO microsite_versions
                (id, microsite_id, version_number, full_html, full_css, content_snapshot, created_by, created)
            VALUES
                (:id, :microsite_id, :version_number, :full_html, :full_css, :content_snapshot, :created_by, :created)
            """,
            {
                "id": str(uuid.uuid4()),
                "microsite_id": microsite_id,
                "version_number": new_version,
                "full_html": full_html,
                "full_css": full_css,
                "content_snapshot": content_snapshot,
                "created_by": created_by,
                "created": datetime.utcnow().isoformat(),
            },
        )

        return new_version

    def _parse_json_field(self, value: Any) -> Dict[str, Any]:
        """Safely parse a JSON string field."""
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}


# Singleton
_generation_service: Optional[MicrositeGenerationService] = None


def get_generation_service(
    max_context_tokens: int = 8000,
    temperature: float = 0.7,
    model: str = "gpt-4",
) -> MicrositeGenerationService:
    """Get or create the generation service singleton."""
    global _generation_service
    if _generation_service is None:
        _generation_service = MicrositeGenerationService(
            max_context_tokens=max_context_tokens,
            temperature=temperature,
            model=model,
        )
    return _generation_service
