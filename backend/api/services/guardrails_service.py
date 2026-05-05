"""
Guardrails Service for Content Moderation

Implements a 4-layer moderation pipeline:
1. AI Content Filtering - GPT-4 based content analysis
2. Keyword Blocklist - Regex pattern matching against blocklist table
3. Source Validation - URL reachability and file existence checks
4. User Review Workflow - Aggregate scoring and review flagging

Layers run in parallel via asyncio.gather() for performance.
"""

import asyncio
import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from open_notebook.database.repository import repo_query, repo_execute
from api.services.prompt_loader import load_prompt


# Fallback prompt for content moderation
CONTENT_MODERATION_FALLBACK = (
    "You are a content moderation assistant. Analyze the following content and check for:\n"
    "1. Misleading or factually incorrect information\n"
    "2. Personal Identifiable Information (PII) exposure (emails, phone numbers, addresses, SSNs)\n"
    "3. Bias, toxicity, or offensive language\n"
    "4. Potentially harmful or dangerous advice\n\n"
    "Respond ONLY with valid JSON in this exact format:\n"
    '{"score": 0.95, "issues": [{"type": "pii", "severity": "high", "message": "Email address found in content", "location": "paragraph 3"}]}\n\n'
    "Score: 1.0 = perfectly safe, 0.0 = completely unsafe.\n"
    "Severity levels: high, medium, low.\n"
    "If no issues found, return: {\"score\": 1.0, \"issues\": []}"
)


class GuardrailsService:
    """
    Content moderation service with 4-layer pipeline.

    Returns comprehensive reports with status, scores, issues, and review flags.
    Saves ModerationLog entries for audit trail.
    """

    # Weighted scoring: AI 50%, Keywords 30%, Sources 20%
    WEIGHT_AI = 0.50
    WEIGHT_KEYWORDS = 0.30
    WEIGHT_SOURCES = 0.20

    def __init__(self):
        pass

    async def moderate_content(
        self,
        microsite_id: str,
        content: str,
        source_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run the full 4-layer moderation pipeline.

        Args:
            microsite_id: Microsite being moderated
            content: HTML/text content to moderate
            source_ids: Optional source IDs for source validation

        Returns:
            Comprehensive moderation report
        """
        # Run layers in parallel
        ai_result, keyword_result, source_result = await asyncio.gather(
            self._layer_ai_content_filter(content),
            self._layer_keyword_blocklist(content),
            self._layer_source_validation(source_ids or []),
            return_exceptions=True,
        )

        # Handle exceptions from parallel execution
        if isinstance(ai_result, Exception):
            print(f"AI filter layer failed: {ai_result}")
            ai_result = {
                "score": 0.5,
                "status": "warning",
                "issues": [{
                    "type": "system_error",
                    "description": f"AI filter unavailable: {ai_result}",
                    "severity": "medium",
                    "location": "system",
                }],
            }

        if isinstance(keyword_result, Exception):
            print(f"Keyword blocklist layer failed: {keyword_result}")
            keyword_result = {
                "score": 1.0,
                "status": "passed",
                "issues": [],
            }

        if isinstance(source_result, Exception):
            print(f"Source validation layer failed: {source_result}")
            source_result = {
                "score": 1.0,
                "status": "passed",
                "issues": [],
            }

        # Layer 4: Aggregate and determine review workflow
        report = self._aggregate_results(ai_result, keyword_result, source_result)

        # Save moderation log
        await self._save_moderation_log(microsite_id, report)

        return report

    # =========================================================================
    # Layer 1: AI Content Filtering
    # =========================================================================

    async def _layer_ai_content_filter(self, content: str) -> Dict[str, Any]:
        """
        Use LLM to analyze content for harmful/inappropriate material.

        Detects: misleading info, PII exposure, bias/toxicity.
        Returns safety score (0.0-1.0) and specific issues.
        """
        if not content or not content.strip():
            return {"score": 1.0, "status": "passed", "issues": []}

        # Truncate content for API call (avoid token limits)
        analysis_content = content[:8000] if len(content) > 8000 else content

        try:
            from api.routers.credentials import _credentials_store
            from api.services.settings import get_setting

            model_id = await get_setting("language_model_id", "")
            if not model_id:
                return {
                    "score": 0.5,
                    "status": "warning",
                    "issues": [{
                        "type": "configuration_error",
                        "description": "No language model configured for AI content filtering",
                        "severity": "medium",
                        "location": "system",
                    }],
                }

            credential = _credentials_store.get(model_id)
            if not credential:
                return {
                    "score": 0.5,
                    "status": "warning",
                    "issues": [{
                        "type": "configuration_error",
                        "description": f"Language model '{model_id}' not found in credentials",
                        "severity": "medium",
                        "location": "system",
                    }],
                }

            api_url = credential["base_url"]
            api_key = credential["api_key"]
            model_name = credential.get("model_name", credential.get("name", "gpt-4"))

        except ImportError:
            return {
                "score": 0.5,
                "status": "warning",
                "issues": [{
                    "type": "system_error",
                    "description": "Credentials store not available",
                    "severity": "medium",
                    "location": "system",
                }],
            }

        # Load prompt from database with fallback
        system_prompt = await load_prompt(
            "safety_content_moderation",
            variables={"content": analysis_content},
            fallback=CONTENT_MODERATION_FALLBACK
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                            {"role": "user", "content": f"Analyze this content:\n\n{analysis_content}"},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1000,
                    },
                )

                if response.status_code != 200:
                    raise Exception(f"API error: {response.status_code}")

                result = response.json()
                ai_response = result["choices"][0]["message"]["content"]

                # Parse JSON from AI response
                parsed = self._parse_ai_response(ai_response)
                score = parsed.get("score", 0.5)
                issues = parsed.get("issues", [])

                # Normalize issues
                normalized_issues = []
                for issue in issues:
                    normalized_issues.append({
                        "type": issue.get("type", "general"),
                        "description": issue.get("message", issue.get("description", "Issue detected")),
                        "severity": issue.get("severity", "medium"),
                        "location": issue.get("location", ""),
                    })

                # Determine status
                if score >= 0.8:
                    status = "passed"
                elif score >= 0.5:
                    status = "warning"
                else:
                    status = "blocked"

                return {"score": score, "status": status, "issues": normalized_issues}

        except Exception as e:
            return {
                "score": 0.5,
                "status": "warning",
                "issues": [{
                    "type": "system_error",
                    "description": f"AI content filter error: {str(e)}",
                    "severity": "medium",
                    "location": "system",
                }],
            }

    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from AI response, handling markdown code blocks."""
        text = response_text.strip()

        # Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            brace_match = re.search(r'\{.*\}', text, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

        return {"score": 0.5, "issues": [{"type": "parse_error", "description": "Could not parse AI response", "severity": "medium"}]}

    # =========================================================================
    # Layer 2: Keyword Blocklist
    # =========================================================================

    async def _layer_keyword_blocklist(self, content: str) -> Dict[str, Any]:
        """
        Check content against keyword blocklist patterns from database.

        Supports regex patterns. Severity: 'block' (hard fail) or 'warning' (flag).
        """
        if not content:
            return {"score": 1.0, "status": "passed", "issues": []}

        # Load blocklist from database
        try:
            blocklist = await repo_query(
                "SELECT keyword, category, severity, is_regex FROM content_blocklist"
            )
        except Exception:
            # Table may not exist yet
            blocklist = []

        if not blocklist:
            return {"score": 1.0, "status": "passed", "issues": []}

        issues = []
        has_block = False
        content_lower = content.lower()

        for entry in blocklist:
            keyword = entry.get("keyword", "")
            is_regex = bool(entry.get("is_regex", 0))
            category = entry.get("category", "custom")
            severity = entry.get("severity", "warning")

            matched = False
            match_details = ""

            if is_regex and keyword:
                # Use keyword field as regex pattern
                try:
                    matches = re.findall(keyword, content, re.IGNORECASE)
                    if matches:
                        matched = True
                        match_count = len(matches)
                        match_details = f"Pattern matched {match_count} time(s)"
                except re.error:
                    # Invalid regex, skip
                    continue
            elif keyword:
                # Simple keyword matching
                if keyword.lower() in content_lower:
                    matched = True
                    match_count = content_lower.count(keyword.lower())
                    match_details = f"Keyword '{keyword}' found {match_count} time(s)"

            if matched:
                if severity == "block":
                    has_block = True

                issues.append({
                    "type": "keyword",
                    "description": match_details,
                    "severity": "high" if severity == "block" else "medium",
                    "location": f"category: {category}",
                })

        # Calculate score
        if has_block:
            score = 0.0
            status = "blocked"
        elif issues:
            # Deduct points per warning
            score = max(0.3, 1.0 - (len(issues) * 0.15))
            status = "warning"
        else:
            score = 1.0
            status = "passed"

        return {"score": score, "status": status, "issues": issues}

    # =========================================================================
    # Layer 3: Source Validation
    # =========================================================================

    async def _layer_source_validation(self, source_ids: List[str]) -> Dict[str, Any]:
        """
        Validate that referenced sources are accessible.

        Checks URL reachability and file existence.
        """
        if not source_ids:
            return {"score": 1.0, "status": "passed", "issues": []}

        issues = []
        total = len(source_ids)
        valid = 0

        for source_id in source_ids:
            try:
                results = await repo_query(
                    "SELECT id, title, source_type, asset_data FROM sources WHERE id = :id",
                    {"id": source_id},
                )

                if not results:
                    issues.append({
                        "type": "missing_source",
                        "description": f"Source not found: {source_id}",
                        "severity": "medium",
                        "location": source_id,
                    })
                    continue

                source = results[0]
                source_type = source.get("source_type", "")

                if source_type == "url":
                    url = source.get("asset_data", "")
                    if url:
                        is_reachable = await self._check_url_reachable(url)
                        if is_reachable:
                            valid += 1
                        else:
                            issues.append({
                                "type": "unreachable_url",
                                "description": f"URL source unreachable: {url}",
                                "severity": "low",
                                "location": source.get("title", source_id),
                            })
                    else:
                        valid += 1  # No URL to check
                elif source_type == "file":
                    # Parse asset_data to get file information
                    import json
                    import os

                    asset_data = source.get("asset_data", "")

                    # If asset_data is a JSON string with object_name, it's stored in S3/MinIO
                    if isinstance(asset_data, str) and asset_data.strip().startswith("{"):
                        try:
                            asset_json = json.loads(asset_data)
                            if "object_name" in asset_json:
                                # File is in S3/MinIO - skip local filesystem check
                                # TODO: Add S3 existence check if needed
                                valid += 1
                            else:
                                # JSON but no object_name - unexpected format, count as valid
                                valid += 1
                        except json.JSONDecodeError:
                            # Failed to parse JSON, treat as local file path
                            if asset_data and not os.path.exists(asset_data):
                                issues.append({
                                    "type": "missing_file",
                                    "description": f"File source not found: {asset_data}",
                                    "severity": "low",
                                    "location": source.get("title", source_id),
                                })
                            else:
                                valid += 1
                    else:
                        # Plain string path - check local filesystem
                        if asset_data and not os.path.exists(asset_data):
                            issues.append({
                                "type": "missing_file",
                                "description": f"File source not found: {asset_data}",
                                "severity": "low",
                                "location": source.get("title", source_id),
                            })
                        else:
                            valid += 1
                else:
                    valid += 1  # Text, youtube, etc. don't need file checks

            except Exception as e:
                issues.append({
                    "type": "validation_error",
                    "description": f"Error validating source {source_id}: {str(e)}",
                    "severity": "low",
                    "location": source_id,
                })

        # Calculate score
        score = valid / total if total > 0 else 1.0

        if score >= 0.8:
            status = "passed"
        elif score >= 0.5:
            status = "warning"
        else:
            status = "blocked"

        return {"score": score, "status": status, "issues": issues}

    async def _check_url_reachable(self, url: str) -> bool:
        """Check if a URL is reachable via HTTP HEAD request."""
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.head(url)
                return response.status_code < 400
        except Exception:
            return False

    # =========================================================================
    # Layer 4: Aggregation and Review Workflow
    # =========================================================================

    def _aggregate_results(
        self,
        ai_result: Dict[str, Any],
        keyword_result: Dict[str, Any],
        source_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Aggregate results from all layers into a comprehensive report.

        Weighted scoring: AI 50%, Keywords 30%, Sources 20%.
        """
        ai_score = ai_result.get("score", 0.5)
        keyword_score = keyword_result.get("score", 1.0)
        source_score = source_result.get("score", 1.0)

        overall_score = (
            ai_score * self.WEIGHT_AI
            + keyword_score * self.WEIGHT_KEYWORDS
            + source_score * self.WEIGHT_SOURCES
        )

        # Collect all issues
        all_issues = (
            ai_result.get("issues", [])
            + keyword_result.get("issues", [])
            + source_result.get("issues", [])
        )

        # Determine overall status
        statuses = [
            ai_result.get("status", "passed"),
            keyword_result.get("status", "passed"),
            source_result.get("status", "passed"),
        ]

        if "blocked" in statuses:
            overall_status = "blocked"
        elif "warning" in statuses:
            overall_status = "warning"
        else:
            overall_status = "passed"

        # Determine if review is required
        requires_review = (
            overall_status != "passed"
            or any(i.get("severity") == "high" for i in all_issues)
        )

        return {
            "status": overall_status,
            "overall_score": round(overall_score, 3),
            "layers": {
                "ai_filter": {
                    "score": ai_score,
                    "status": ai_result.get("status", "passed"),
                    "issue_count": len(ai_result.get("issues", [])),
                },
                "keyword_blocklist": {
                    "score": keyword_score,
                    "status": keyword_result.get("status", "passed"),
                    "issue_count": len(keyword_result.get("issues", [])),
                },
                "source_validation": {
                    "score": source_score,
                    "status": source_result.get("status", "passed"),
                    "issue_count": len(source_result.get("issues", [])),
                },
            },
            "issues": all_issues,
            "requires_review": requires_review,
        }

    # =========================================================================
    # Moderation Log Persistence
    # =========================================================================

    async def _save_moderation_log(
        self, microsite_id: str, report: Dict[str, Any]
    ) -> str:
        """Save moderation report to the audit log."""
        log_id = str(uuid.uuid4())

        try:
            await repo_execute(
                """
                INSERT INTO content_moderation_logs
                    (id, microsite_id, content_section, moderation_type, status,
                     score, issues_found, metadata, created)
                VALUES
                    (:id, :microsite_id, :content_section, :moderation_type, :status,
                     :score, :issues_found, :metadata, :created)
                """,
                {
                    "id": log_id,
                    "microsite_id": microsite_id,
                    "content_section": "full",
                    "moderation_type": "full_pipeline",
                    "status": report.get("status", "unknown"),
                    "score": report.get("overall_score", 0.0),
                    "issues_found": json.dumps(report.get("issues", [])),
                    "metadata": json.dumps({
                        "layers": report.get("layers", {}),
                        "requires_review": report.get("requires_review", True),
                    }),
                    "created": datetime.utcnow().isoformat(),
                },
            )
        except Exception as e:
            print(f"Failed to save moderation log: {e}")

        return log_id


# Singleton
_guardrails_service: Optional[GuardrailsService] = None


def get_guardrails_service() -> GuardrailsService:
    """Get or create the guardrails service singleton."""
    global _guardrails_service
    if _guardrails_service is None:
        _guardrails_service = GuardrailsService()
    return _guardrails_service
