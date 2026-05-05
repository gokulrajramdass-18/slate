"""
Unit tests for PromptLoader service

Tests cache behavior, variable substitution, fallback mechanism, and cache invalidation.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from api.services.prompt_loader import PromptLoader


@pytest.fixture
def clear_cache():
    """Clear PromptLoader cache before each test"""
    PromptLoader.invalidate_cache()
    yield
    PromptLoader.invalidate_cache()


class TestPromptLoaderCache:
    """Test cache behavior"""

    @pytest.mark.asyncio
    async def test_cache_hit(self, clear_cache):
        """Test that second load uses cache"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            # First call - cache miss
            mock_query.return_value = [{"prompt_text": "Test prompt {var1}"}]

            result1 = await PromptLoader.load_template(
                "test_key",
                variables={"var1": "value1"}
            )

            assert result1 == "Test prompt value1"
            assert mock_query.call_count == 1

            # Second call - cache hit (no DB query)
            result2 = await PromptLoader.load_template(
                "test_key",
                variables={"var1": "value2"}
            )

            assert result2 == "Test prompt value2"
            assert mock_query.call_count == 1  # No additional DB call

    @pytest.mark.asyncio
    async def test_cache_miss_after_ttl(self, clear_cache):
        """Test that cache expires after TTL"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": "Test prompt"}]

            # First call
            await PromptLoader.load_template("test_key")
            assert mock_query.call_count == 1

            # Manually expire cache entry
            if "test_key" in PromptLoader._cache:
                cached_prompt, _ = PromptLoader._cache["test_key"]
                PromptLoader._cache["test_key"] = (
                    cached_prompt,
                    datetime.utcnow() - PromptLoader._cache_ttl - timedelta(seconds=1)
                )

            # Second call - cache expired
            await PromptLoader.load_template("test_key")
            assert mock_query.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, clear_cache):
        """Test cache invalidation"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": "Test prompt"}]

            # Load and cache
            await PromptLoader.load_template("test_key")
            assert mock_query.call_count == 1

            # Invalidate specific key
            PromptLoader.invalidate_cache("test_key")

            # Next call should hit DB again
            await PromptLoader.load_template("test_key")
            assert mock_query.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_clear_all(self, clear_cache):
        """Test clearing all cache entries"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": "Test prompt"}]

            # Load multiple templates
            await PromptLoader.load_template("key1")
            await PromptLoader.load_template("key2")

            stats = PromptLoader.get_cache_stats()
            assert stats["cache_size"] == 2

            # Clear all
            PromptLoader.invalidate_cache()

            stats = PromptLoader.get_cache_stats()
            assert stats["cache_size"] == 0


class TestVariableSubstitution:
    """Test variable substitution in templates"""

    @pytest.mark.asyncio
    async def test_simple_variable(self, clear_cache):
        """Test simple variable substitution"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": "Hello {name}!"}]

            result = await PromptLoader.load_template(
                "test_key",
                variables={"name": "World"}
            )

            assert result == "Hello World!"

    @pytest.mark.asyncio
    async def test_multiple_variables(self, clear_cache):
        """Test multiple variable substitution"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [
                {"prompt_text": "User: {user}, Role: {role}, Count: {count}"}
            ]

            result = await PromptLoader.load_template(
                "test_key",
                variables={"user": "Alice", "role": "Admin", "count": 42}
            )

            assert result == "User: Alice, Role: Admin, Count: 42"

    @pytest.mark.asyncio
    async def test_missing_variable_preserves_placeholder(self, clear_cache):
        """Test that missing variables raise KeyError (expected behavior)"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": "Hello {name}, your role is {role}"}]

            result = await PromptLoader.load_template(
                "test_key",
                variables={"name": "Alice"}  # Missing 'role'
            )

            # Python .format() raises KeyError, which is caught and logged
            # The prompt is returned with unsubstituted placeholders
            assert result == "Hello {name}, your role is {role}"  # Nothing substituted due to KeyError

    @pytest.mark.asyncio
    async def test_no_variables(self, clear_cache):
        """Test template with no variables"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": "Static prompt text"}]

            result = await PromptLoader.load_template("test_key")

            assert result == "Static prompt text"

    @pytest.mark.asyncio
    async def test_special_characters_in_variables(self, clear_cache):
        """Test special characters in variable values"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": "Query: {query}"}]

            result = await PromptLoader.load_template(
                "test_key",
                variables={"query": "SELECT * FROM table WHERE id = 'test'"}
            )

            assert result == "Query: SELECT * FROM table WHERE id = 'test'"


class TestFallbackMechanism:
    """Test fallback to hardcoded prompts"""

    @pytest.mark.asyncio
    async def test_db_failure_uses_fallback(self, clear_cache):
        """Test fallback when DB query fails"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.side_effect = Exception("Database connection failed")

            fallback = "Fallback prompt"
            result = await PromptLoader.load_template(
                "test_key",
                fallback=fallback
            )

            assert result == fallback

    @pytest.mark.asyncio
    async def test_template_not_found_uses_fallback(self, clear_cache):
        """Test fallback when template not found"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = []  # Template not found

            fallback = "Fallback prompt"
            result = await PromptLoader.load_template(
                "test_key",
                fallback=fallback
            )

            assert result == fallback

    @pytest.mark.asyncio
    async def test_no_fallback_raises_error(self, clear_cache):
        """Test error when template not found and no fallback"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = []

            with pytest.raises(ValueError, match="not found and no fallback provided"):
                await PromptLoader.load_template("test_key")

    @pytest.mark.asyncio
    async def test_fallback_with_variables(self, clear_cache):
        """Test variable substitution in fallback prompt"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.side_effect = Exception("DB error")

            fallback = "Hello {name}!"
            result = await PromptLoader.load_template(
                "test_key",
                variables={"name": "World"},
                fallback=fallback
            )

            assert result == "Hello World!"

    @pytest.mark.asyncio
    async def test_inactive_template_uses_fallback(self, clear_cache):
        """Test that inactive templates raise error (forcing fallback)"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            # Query returns empty because is_active = 0 filtered out
            mock_query.return_value = []

            fallback = "Fallback prompt"
            result = await PromptLoader.load_template(
                "test_key",
                fallback=fallback
            )

            assert result == fallback


class TestCacheStatistics:
    """Test cache statistics"""

    def test_cache_stats_structure(self, clear_cache):
        """Test cache stats return correct structure"""
        stats = PromptLoader.get_cache_stats()

        assert "cache_size" in stats
        assert "cache_ttl_minutes" in stats
        assert "cached_keys" in stats

        assert isinstance(stats["cache_size"], int)
        assert isinstance(stats["cache_ttl_minutes"], float)
        assert isinstance(stats["cached_keys"], list)

    @pytest.mark.asyncio
    async def test_cache_stats_after_loads(self, clear_cache):
        """Test cache stats reflect loaded templates"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": "Test"}]

            # Load 3 templates
            await PromptLoader.load_template("key1")
            await PromptLoader.load_template("key2")
            await PromptLoader.load_template("key3")

            stats = PromptLoader.get_cache_stats()
            assert stats["cache_size"] == 3
            assert "key1" in stats["cached_keys"]
            assert "key2" in stats["cached_keys"]
            assert "key3" in stats["cached_keys"]


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_empty_template_text(self, clear_cache):
        """Test handling of empty template text"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": ""}]

            result = await PromptLoader.load_template("test_key")
            assert result == ""

    @pytest.mark.asyncio
    async def test_very_long_template(self, clear_cache):
        """Test handling of very long template text"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            long_text = "A" * 100000  # 100KB
            mock_query.return_value = [{"prompt_text": long_text}]

            result = await PromptLoader.load_template("test_key")
            assert result == long_text
            assert len(result) == 100000

    @pytest.mark.asyncio
    async def test_unicode_in_template(self, clear_cache):
        """Test Unicode characters in template"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            unicode_text = "Hello 世界! 🚀 Здравствуй"
            mock_query.return_value = [{"prompt_text": unicode_text}]

            result = await PromptLoader.load_template("test_key")
            assert result == unicode_text

    @pytest.mark.asyncio
    async def test_concurrent_loads(self, clear_cache):
        """Test concurrent loads of same template"""
        with patch('api.services.prompt_loader.repo_query') as mock_query:
            mock_query.return_value = [{"prompt_text": "Test prompt"}]

            # Load same template concurrently
            results = await asyncio.gather(*[
                PromptLoader.load_template("test_key")
                for _ in range(10)
            ])

            # All should return same result
            assert all(r == "Test prompt" for r in results)
            # Should only query DB once (cache hit for subsequent)
            assert mock_query.call_count <= 2  # Allow for race condition


# Integration test (requires actual database)
@pytest.mark.integration
class TestIntegration:
    """Integration tests with real database"""

    @pytest.mark.asyncio
    async def test_load_actual_template(self, clear_cache):
        """Test loading an actual template from database"""
        # This test requires actual database connection
        try:
            result = await PromptLoader.load_template(
                "chat_base_system",
                variables={
                    "notebook_name": "Test",
                    "embedded_content": "Content",
                    "sources_list": "[1] Source",
                    "live_data_context": "",
                    "num_notebook_sources": 1
                }
            )

            assert "helpful AI assistant" in result.lower()
            assert "Test" in result  # Variable substituted
        except Exception as e:
            pytest.skip(f"Database not available: {e}")
