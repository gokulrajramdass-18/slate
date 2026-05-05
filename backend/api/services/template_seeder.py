"""
Template Seeder Service

Seeds the database with 5 pre-built microsite templates on first startup:
1. Blog - Hero, post list, insights, author bio
2. Documentation - TOC, content sections, API reference
3. Portfolio - Hero, project grid, about, contact
4. Landing Page - Hero, features, testimonials, CTA, footer
5. Report - Executive summary, findings, data visualizations, conclusion

Only runs if no templates exist (idempotent).
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from open_notebook.database.repository import repo_query, repo_execute


class TemplateSeeder:
    """
    Seeds pre-built microsite templates into the database.

    Call seed_if_empty() on application startup. It checks whether templates
    already exist and only seeds if the table is empty.
    """

    async def seed_if_empty(self) -> bool:
        """
        Seed templates if none exist.

        Returns:
            True if templates were seeded, False if already populated
        """
        try:
            results = await repo_query(
                "SELECT COUNT(*) as count FROM microsite_templates"
            )
            count = results[0]["count"] if results else 0

            if count > 0:
                print(f"Template seeder: {count} templates already exist, skipping.")
                return False

        except Exception as e:
            print(f"Template seeder: table may not exist yet ({e}), skipping.")
            return False

        print("Template seeder: seeding 5 pre-built templates...")

        templates = self._get_template_definitions()

        for template in templates:
            try:
                await repo_execute(
                    """
                    INSERT INTO microsite_templates
                        (id, name, display_name, description, structure, default_styles,
                         preview_image, is_custom, created, updated)
                    VALUES
                        (:id, :name, :display_name, :description, :structure, :default_styles,
                         :preview_image, :is_custom, :created, :updated)
                    """,
                    {
                        "id": template["id"],
                        "name": template["name"],
                        "display_name": template["display_name"],
                        "description": template["description"],
                        "structure": json.dumps(template["structure"]),
                        "default_styles": json.dumps(template["default_styles"]),
                        "preview_image": template.get("preview_image", ""),
                        "is_custom": 0,
                        "created": datetime.utcnow().isoformat(),
                        "updated": datetime.utcnow().isoformat(),
                    },
                )
                print(f"  Seeded template: {template['name']}")
            except Exception as e:
                print(f"  Failed to seed template '{template['name']}': {e}")

        # Seed default blocklist entries
        await self._seed_default_blocklist()

        print("Template seeder: done.")
        return True

    async def _seed_default_blocklist(self) -> None:
        """Seed a small set of default blocklist entries."""
        try:
            results = await repo_query(
                "SELECT COUNT(*) as count FROM content_blocklist"
            )
            if results and results[0]["count"] > 0:
                return
        except Exception:
            return

        defaults = [
            {
                "keyword": r"\bpassword\s*[:=]\s*\S+",
                "category": "sensitive",
                "severity": "block",
                "is_regex": 1,
            },
            {
                "keyword": r"\b(api[_-]?key|apikey)\s*[:=]\s*\S+",
                "category": "sensitive",
                "severity": "block",
                "is_regex": 1,
            },
            {
                "keyword": r"\b(secret[_-]?key|secretkey)\s*[:=]\s*\S+",
                "category": "sensitive",
                "severity": "block",
                "is_regex": 1,
            },
            {
                "keyword": r"\b\d{3}-\d{2}-\d{4}\b",
                "category": "pii",
                "severity": "block",
                "is_regex": 1,
            },
            {
                "keyword": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
                "category": "pii",
                "severity": "block",
                "is_regex": 1,
            },
        ]

        for entry in defaults:
            try:
                await repo_execute(
                    """
                    INSERT INTO content_blocklist
                        (id, keyword, category, severity, is_regex, created, updated)
                    VALUES
                        (:id, :keyword, :category, :severity, :is_regex, :created, :updated)
                    """,
                    {
                        "id": str(uuid.uuid4()),
                        "keyword": entry["keyword"],
                        "category": entry["category"],
                        "severity": entry["severity"],
                        "is_regex": entry["is_regex"],
                        "created": datetime.utcnow().isoformat(),
                        "updated": datetime.utcnow().isoformat(),
                    },
                )
            except Exception as e:
                print(f"  Failed to seed blocklist entry '{entry['keyword']}': {e}")

    def _get_template_definitions(self) -> List[Dict[str, Any]]:
        """Return the 5 pre-built template definitions."""
        return [
            self._blog_template(),
            self._documentation_template(),
            self._portfolio_template(),
            self._landing_page_template(),
            self._report_template(),
        ]

    # =========================================================================
    # Template 1: Blog
    # =========================================================================

    def _blog_template(self) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "name": "blog",
            "display_name": "Blog",
            "description": "A clean blog layout with hero section, article content, key insights, and author bio. Ideal for sharing research findings and thought leadership.",
            "structure": {
                "sections": [
                    {
                        "id": "hero",
                        "type": "hero",
                        "title": "",  # Empty title - hero content speaks for itself
                        "order": 0,
                        "prompt_template": "Create an engaging headline and subtitle that captures the essence of the research. The headline should be attention-grabbing and the subtitle should provide context. Do not include the word 'Hero' in your response.",
                        "default_content": {
                            "html": "<h1>Your Research Title</h1><p>A compelling subtitle that draws readers in</p>",
                            "tiptap": {
                                "type": "doc",
                                "content": [
                                    {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Your Research Title"}]},
                                    {"type": "paragraph", "content": [{"type": "text", "text": "A compelling subtitle that draws readers in"}]},
                                ],
                            },
                        },
                    },
                    {
                        "id": "summary",
                        "type": "summary",
                        "title": "Summary",
                        "order": 1,
                        "prompt_template": "Write a concise executive summary (2-3 paragraphs) that captures the main points from the source material. Use clear, accessible language.",
                        "default_content": {
                            "html": "<h2>Summary</h2><p>Your content summary will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "insights",
                        "type": "insights",
                        "title": "Key Insights",
                        "order": 2,
                        "prompt_template": "Extract the 5-7 most important insights from the source material. Present each as a bullet point with a brief explanation. Focus on actionable and surprising findings.",
                        "default_content": {
                            "html": "<h2>Key Insights</h2><ul><li>Insight 1</li><li>Insight 2</li></ul>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "sources_list",
                        "type": "sources_list",
                        "title": "Sources",
                        "order": 3,
                        "prompt_template": "Create a well-organized reference list of the sources used. Include a brief description of what each source covers.",
                        "default_content": {
                            "html": "<h2>Sources</h2><ul><li>Source references will appear here</li></ul>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "conclusion",
                        "type": "conclusion",
                        "title": "Conclusion",
                        "order": 4,
                        "prompt_template": "Write a thoughtful conclusion (1-2 paragraphs) that synthesizes the key takeaways and suggests next steps or implications.",
                        "default_content": {
                            "html": "<h2>Conclusion</h2><p>Your conclusion will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                ],
                "layout": "vertical",
            },
            "default_styles": {
                "primary_color": "#1a73e8",
                "font_heading": "Georgia",
                "font_body": "system-ui",
                "background_color": "#ffffff",
                "text_color": "#202124",
                "css": """
                    .section-hero { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4rem 2rem; text-align: center; border-radius: 8px; margin-bottom: 2rem; }
                    .section-hero h1 { color: white; font-size: 2.5rem; }
                    .section-insights ul { list-style: none; padding: 0; }
                    .section-insights li { padding: 0.75rem 1rem; margin-bottom: 0.5rem; background: #f8f9fa; border-left: 3px solid #1a73e8; border-radius: 0 4px 4px 0; }
                """,
            },
            "preview_image": "",
        }

    # =========================================================================
    # Template 2: Documentation
    # =========================================================================

    def _documentation_template(self) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "name": "documentation",
            "display_name": "Documentation",
            "description": "A structured documentation layout with table of contents, organized content sections, and API reference. Perfect for technical documentation and knowledge bases.",
            "structure": {
                "sections": [
                    {
                        "id": "toc",
                        "type": "toc",
                        "title": "Table of Contents",
                        "order": 0,
                        "prompt_template": "Generate a table of contents based on the topics covered in the source material. Use nested lists for sub-topics. Include anchor-friendly headings.",
                        "default_content": {
                            "html": "<h2>Table of Contents</h2><ul><li>Getting Started</li><li>Core Concepts</li><li>API Reference</li></ul>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "overview",
                        "type": "summary",
                        "title": "Overview",
                        "order": 1,
                        "prompt_template": "Write a clear overview section that explains what this documentation covers, who it's for, and any prerequisites. Keep it concise but informative.",
                        "default_content": {
                            "html": "<h2>Overview</h2><p>Documentation overview will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "content",
                        "type": "insights",
                        "title": "Core Content",
                        "order": 2,
                        "prompt_template": "Organize the main content from the sources into well-structured sections with clear headings. Use code examples where relevant. Include step-by-step instructions.",
                        "default_content": {
                            "html": "<h2>Core Content</h2><p>Main documentation content will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "api_reference",
                        "type": "sources_list",
                        "title": "Reference",
                        "order": 3,
                        "prompt_template": "Create a reference section organizing key terms, APIs, configurations, or commands mentioned in the sources. Use a structured format with descriptions.",
                        "default_content": {
                            "html": "<h2>Reference</h2><p>API and reference documentation will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                ],
                "layout": "vertical",
            },
            "default_styles": {
                "primary_color": "#0d6efd",
                "font_heading": "Inter",
                "font_body": "system-ui",
                "background_color": "#ffffff",
                "text_color": "#212529",
                "css": """
                    .section-toc { background: #f8f9fa; padding: 1.5rem; border-radius: 8px; border: 1px solid #dee2e6; }
                    .section-toc ul { list-style: none; }
                    .section-toc li { padding: 0.25rem 0; }
                    .section-toc a { color: #0d6efd; }
                    code { background: #e9ecef; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
                    pre code { background: #2d2d2d; color: #f8f8f2; display: block; padding: 1rem; border-radius: 6px; }
                """,
            },
            "preview_image": "",
        }

    # =========================================================================
    # Template 3: Portfolio
    # =========================================================================

    def _portfolio_template(self) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "name": "portfolio",
            "display_name": "Portfolio",
            "description": "A visually-driven portfolio layout with hero section, project showcase grid, about section, and contact info. Great for showcasing work and research projects.",
            "structure": {
                "sections": [
                    {
                        "id": "hero",
                        "type": "hero",
                        "title": "Introduction",
                        "order": 0,
                        "prompt_template": "Create a professional introduction with a strong personal brand statement. Include a headline and a brief tagline that captures expertise.",
                        "default_content": {
                            "html": "<h1>Your Name</h1><p>Your professional tagline</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "projects",
                        "type": "features",
                        "title": "Projects",
                        "order": 1,
                        "prompt_template": "Create project showcase entries from the source material. For each project/topic, include a title, brief description, and key highlights. Format as a grid-friendly list.",
                        "default_content": {
                            "html": "<h2>Projects</h2><p>Your projects will be showcased here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "about",
                        "type": "about",
                        "title": "About",
                        "order": 2,
                        "prompt_template": "Write a compelling 'About' section based on the source material. Highlight expertise, background, and what makes this work unique. Keep it professional but personable.",
                        "default_content": {
                            "html": "<h2>About</h2><p>Your bio will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "contact",
                        "type": "conclusion",
                        "title": "Contact",
                        "order": 3,
                        "prompt_template": "Create a brief contact section with a call-to-action encouraging readers to get in touch. Keep it warm and professional.",
                        "default_content": {
                            "html": "<h2>Get in Touch</h2><p>Contact information and links.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                ],
                "layout": "vertical",
            },
            "default_styles": {
                "primary_color": "#6366f1",
                "font_heading": "Inter",
                "font_body": "system-ui",
                "background_color": "#0f172a",
                "text_color": "#e2e8f0",
                "css": """
                    body { background-color: #0f172a; color: #e2e8f0; }
                    .container { max-width: 1100px; }
                    h1, h2, h3 { color: #f1f5f9; }
                    a { color: #818cf8; }
                    .section-hero { text-align: center; padding: 5rem 2rem; }
                    .section-hero h1 { font-size: 3rem; background: linear-gradient(to right, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
                    .section-features li { background: #1e293b; padding: 1rem; border-radius: 8px; margin-bottom: 0.75rem; border: 1px solid #334155; list-style: none; }
                """,
            },
            "preview_image": "",
        }

    # =========================================================================
    # Template 4: Landing Page
    # =========================================================================

    def _landing_page_template(self) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "name": "landing_page",
            "display_name": "Landing Page",
            "description": "A high-conversion landing page with hero, features grid, testimonials, call-to-action, and footer. Optimized for presenting ideas and driving engagement.",
            "structure": {
                "sections": [
                    {
                        "id": "hero",
                        "type": "hero",
                        "title": "Hero",
                        "order": 0,
                        "prompt_template": "Create a powerful hero section with a bold headline, supporting subtitle, and a value proposition. Focus on the primary benefit derived from the source material.",
                        "default_content": {
                            "html": "<h1>Transform Your Ideas</h1><p>A powerful solution built from your research</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "features",
                        "type": "features",
                        "title": "Features",
                        "order": 1,
                        "prompt_template": "Extract 4-6 key features or benefits from the source material. Each feature should have a short title and a one-sentence description. Focus on value to the reader.",
                        "default_content": {
                            "html": "<h2>Features</h2><ul><li>Feature 1</li><li>Feature 2</li></ul>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "testimonials",
                        "type": "insights",
                        "title": "What People Say",
                        "order": 2,
                        "prompt_template": "Extract key quotes, endorsements, or notable findings from the source material. Present them as testimonial-style blocks with attribution. If no direct quotes exist, create compelling data-driven highlights.",
                        "default_content": {
                            "html": "<h2>What People Say</h2><p>Testimonials and quotes will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "cta",
                        "type": "conclusion",
                        "title": "Call to Action",
                        "order": 3,
                        "prompt_template": "Create a compelling call-to-action section. Include a strong headline, brief supporting text, and suggest a clear next step for the reader.",
                        "default_content": {
                            "html": "<h2>Ready to Get Started?</h2><p>Take the next step today.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "footer",
                        "type": "sources_list",
                        "title": "Resources & Links",
                        "order": 4,
                        "prompt_template": "Create a footer section with links to source references and additional resources. Keep it clean and organized.",
                        "default_content": {
                            "html": "<h2>Resources</h2><p>Links and references.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                ],
                "layout": "vertical",
            },
            "default_styles": {
                "primary_color": "#1e40af",
                "font_heading": "Inter",
                "font_body": "system-ui",
                "background_color": "#ffffff",
                "text_color": "#1f2937",
                "css": """
                    .section-hero { background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); color: white; padding: 5rem 2rem; text-align: center; border-radius: 12px; margin-bottom: 3rem; }
                    .section-hero h1 { color: white; font-size: 3rem; margin-bottom: 1rem; }
                    .section-hero p { font-size: 1.25rem; opacity: 0.9; }
                    .section-features ul { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; }
                    .section-features li { background: #eff6ff; padding: 1.5rem; border-radius: 8px; border: 1px solid #bfdbfe; }
                    .section-conclusion { background: #eff6ff; padding: 3rem; border-radius: 12px; text-align: center; }
                """,
            },
            "preview_image": "",
        }

    # =========================================================================
    # Template 5: Report
    # =========================================================================

    def _report_template(self) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "name": "report",
            "display_name": "Report",
            "description": "A professional report layout with executive summary, detailed findings, data highlights, and conclusion. Suitable for research reports, analysis, and business documents.",
            "structure": {
                "sections": [
                    {
                        "id": "executive_summary",
                        "type": "summary",
                        "title": "Executive Summary",
                        "order": 0,
                        "prompt_template": "Write a professional executive summary (2-3 paragraphs) suitable for stakeholders. Highlight the key findings, methodology overview, and main recommendations.",
                        "default_content": {
                            "html": "<h1>Report Title</h1><h2>Executive Summary</h2><p>Summary content will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "findings",
                        "type": "insights",
                        "title": "Key Findings",
                        "order": 1,
                        "prompt_template": "Present the main findings from the source material in a structured format. Use numbered items with clear titles and supporting evidence. Include data points where available.",
                        "default_content": {
                            "html": "<h2>Key Findings</h2><ol><li>Finding 1</li><li>Finding 2</li></ol>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "data_highlights",
                        "type": "features",
                        "title": "Data Highlights",
                        "order": 2,
                        "prompt_template": "Extract and present key data points, statistics, and metrics from the source material. Format as clear, scannable data highlights with context for each number.",
                        "default_content": {
                            "html": "<h2>Data Highlights</h2><p>Key metrics and statistics will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "sources_list",
                        "type": "sources_list",
                        "title": "References",
                        "order": 3,
                        "prompt_template": "Create a formal references section listing all sources used. Include source types and brief annotations for each reference.",
                        "default_content": {
                            "html": "<h2>References</h2><ul><li>Reference 1</li></ul>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                    {
                        "id": "conclusion",
                        "type": "conclusion",
                        "title": "Conclusion & Recommendations",
                        "order": 4,
                        "prompt_template": "Write a formal conclusion with specific recommendations. Summarize the implications of the findings and suggest concrete next steps for the reader.",
                        "default_content": {
                            "html": "<h2>Conclusion & Recommendations</h2><p>Conclusions and next steps will appear here.</p>",
                            "tiptap": {"type": "doc", "content": []},
                        },
                    },
                ],
                "layout": "vertical",
            },
            "default_styles": {
                "primary_color": "#1e40af",
                "font_heading": "Georgia",
                "font_body": "system-ui",
                "background_color": "#ffffff",
                "text_color": "#1e293b",
                "css": """
                    .container { max-width: 800px; }
                    h1 { border-bottom: 2px solid #1e40af; padding-bottom: 0.5rem; }
                    h2 { color: #1e40af; margin-top: 2rem; }
                    .section-summary { background: #eff6ff; padding: 2rem; border-radius: 8px; border-left: 4px solid #1e40af; }
                    .section-insights ol { counter-reset: finding; list-style: none; padding: 0; }
                    .section-insights li { counter-increment: finding; padding: 1rem; margin-bottom: 0.75rem; background: #f8fafc; border-radius: 4px; }
                    .section-insights li::before { content: "Finding " counter(finding); font-weight: bold; color: #1e40af; display: block; margin-bottom: 0.25rem; }
                    .section-features ul { list-style: none; padding: 0; }
                    .section-features li { background: #f0f9ff; padding: 1rem; border-radius: 8px; margin-bottom: 0.5rem; border: 1px solid #bae6fd; }
                """,
            },
            "preview_image": "",
        }


# Singleton
_template_seeder: Optional[TemplateSeeder] = None


def get_template_seeder() -> TemplateSeeder:
    """Get or create the template seeder singleton."""
    global _template_seeder
    if _template_seeder is None:
        _template_seeder = TemplateSeeder()
    return _template_seeder
