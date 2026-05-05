"""
Prompt Loader Service

Central service for loading system prompt templates with caching, variable substitution, and fallback.
"""

import asyncio
from functools import lru_cache
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from open_notebook.database.repository import repo_query


class PromptLoader:
    """Loads system prompt templates with caching and graceful fallback"""

    # Cache settings
    _cache: Dict[str, tuple[str, datetime]] = {}
    _cache_ttl = timedelta(minutes=5)

    @classmethod
    async def load_template(
        cls,
        template_key: str,
        variables: Optional[Dict[str, Any]] = None,
        fallback: Optional[str] = None
    ) -> str:
        """
        Load template from database with variable substitution.

        Args:
            template_key: Unique template identifier (e.g., "chat_base_system")
            variables: Dict of variables to substitute in template
            fallback: Hardcoded prompt to use if DB fails

        Returns:
            Rendered prompt string with variables substituted

        Raises:
            ValueError: If template not found and no fallback provided
        """
        try:
            # 1. Check cache first
            if template_key in cls._cache:
                cached_prompt, cached_time = cls._cache[template_key]
                if datetime.utcnow() - cached_time < cls._cache_ttl:
                    prompt = cached_prompt
                else:
                    # Cache expired, fetch from DB
                    prompt = await cls._fetch_from_db(template_key)
                    cls._cache[template_key] = (prompt, datetime.utcnow())
            else:
                # Not in cache, fetch from DB
                prompt = await cls._fetch_from_db(template_key)
                cls._cache[template_key] = (prompt, datetime.utcnow())

            # 2. Substitute variables
            if variables:
                try:
                    prompt = prompt.format(**variables)
                except KeyError as e:
                    # Missing variable - log warning but don't crash
                    print(f"⚠️  Warning: Missing variable {e} in template {template_key}")
                    # Keep placeholder as-is
                    pass

            return prompt

        except Exception as e:
            # On any error, fall back to hardcoded prompt
            print(f"⚠️  Error loading template '{template_key}': {e}")
            if fallback:
                print(f"   Using hardcoded fallback for '{template_key}'")
                # Still substitute variables in fallback
                if variables and fallback:
                    try:
                        return fallback.format(**variables)
                    except KeyError:
                        # If fallback also has missing vars, return as-is
                        return fallback
                return fallback
            else:
                raise ValueError(f"Template '{template_key}' not found and no fallback provided")

    @classmethod
    async def _fetch_from_db(cls, template_key: str) -> str:
        """
        Fetch template from database.

        Args:
            template_key: Template key to fetch

        Returns:
            Template prompt_text

        Raises:
            ValueError: If template not found or inactive
        """
        rows = await repo_query(
            """SELECT prompt_text FROM system_prompt_templates
               WHERE template_key = :key AND is_active = 1""",
            {"key": template_key}
        )

        if not rows:
            raise ValueError(f"Template not found or inactive: {template_key}")

        return rows[0]["prompt_text"]

    @classmethod
    def invalidate_cache(cls, template_key: Optional[str] = None):
        """
        Clear cache after template updates.

        Args:
            template_key: Specific template to invalidate, or None for all
        """
        if template_key:
            if template_key in cls._cache:
                del cls._cache[template_key]
                print(f"✓ Cache invalidated for template: {template_key}")
        else:
            cls._cache.clear()
            print(f"✓ All template cache cleared ({len(cls._cache)} entries)")

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache size, TTL, and keys
        """
        return {
            "cache_size": len(cls._cache),
            "cache_ttl_minutes": cls._cache_ttl.total_seconds() / 60,
            "cached_keys": list(cls._cache.keys())
        }


# Convenience function for simpler imports
async def load_prompt(
    template_key: str,
    variables: Optional[Dict[str, Any]] = None,
    fallback: Optional[str] = None
) -> str:
    """
    Convenience function to load a prompt template.

    Args:
        template_key: Template key (e.g., "chat_base_system")
        variables: Variables to substitute
        fallback: Hardcoded fallback prompt

    Returns:
        Rendered prompt string
    """
    return await PromptLoader.load_template(template_key, variables, fallback)
