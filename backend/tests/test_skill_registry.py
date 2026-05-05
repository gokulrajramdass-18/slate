"""
Unit tests for SkillRegistry

Tests skill registration, retrieval, filtering, and search functionality.
"""

import pytest
from unittest.mock import AsyncMock

from open_notebook.agents.skills.base import Skill, SkillCategory, SkillContext
from open_notebook.agents.skills.registry import SkillRegistry, get_skill_registry


# Test handlers
async def dummy_handler(context: SkillContext):
    """Dummy handler for testing."""
    return {"result": "success"}


async def another_handler(context: SkillContext):
    """Another dummy handler."""
    return {"result": "another"}


@pytest.fixture
def registry():
    """Create a fresh registry instance for each test."""
    reg = SkillRegistry()
    reg.clear()  # Clear any existing skills
    return reg


@pytest.fixture
def sample_skill():
    """Create a sample skill for testing."""
    return Skill(
        id="test_skill",
        name="Test Skill",
        description="A skill for testing purposes",
        category=SkillCategory.ANALYSIS,
        handler=dummy_handler,
        tags=["test", "example"],
        version="1.0.0",
        enabled=True
    )


@pytest.fixture
def sample_skill_with_role():
    """Create a skill with role restrictions."""
    return Skill(
        id="restricted_skill",
        name="Restricted Skill",
        description="Only for analysts",
        category=SkillCategory.DATA_QUERY,
        handler=another_handler,
        allowed_roles={"analyst", "data_scientist"},
        tags=["restricted"],
        version="1.0.0",
        enabled=True
    )


@pytest.fixture
def disabled_skill():
    """Create a disabled skill."""
    return Skill(
        id="disabled_skill",
        name="Disabled Skill",
        description="This skill is disabled",
        category=SkillCategory.TOOLS,
        handler=dummy_handler,
        tags=["disabled"],
        version="1.0.0",
        enabled=False
    )


class TestSkillRegistryBasics:
    """Test basic registry operations."""

    def test_singleton_pattern(self):
        """Test that SkillRegistry is a singleton."""
        reg1 = SkillRegistry()
        reg2 = SkillRegistry()
        assert reg1 is reg2

    def test_get_skill_registry_returns_singleton(self):
        """Test get_skill_registry returns the singleton instance."""
        reg1 = get_skill_registry()
        reg2 = get_skill_registry()
        assert reg1 is reg2

    def test_register_skill(self, registry, sample_skill):
        """Test registering a skill."""
        registry.register_skill(sample_skill)

        retrieved = registry.get_skill("test_skill")
        assert retrieved is not None
        assert retrieved.id == "test_skill"
        assert retrieved.name == "Test Skill"

    def test_register_duplicate_overwrites(self, registry, sample_skill):
        """Test that registering duplicate skill overwrites existing one."""
        registry.register_skill(sample_skill)

        # Create another skill with same ID but different name
        duplicate = Skill(
            id="test_skill",
            name="Updated Test Skill",
            description="Updated",
            category=SkillCategory.ANALYSIS,
            handler=another_handler
        )
        registry.register_skill(duplicate)

        retrieved = registry.get_skill("test_skill")
        assert retrieved.name == "Updated Test Skill"

    def test_unregister_skill(self, registry, sample_skill):
        """Test unregistering a skill."""
        registry.register_skill(sample_skill)
        assert registry.get_skill("test_skill") is not None

        result = registry.unregister_skill("test_skill")
        assert result is True
        assert registry.get_skill("test_skill") is None

    def test_unregister_nonexistent_skill(self, registry):
        """Test unregistering a skill that doesn't exist."""
        result = registry.unregister_skill("nonexistent")
        assert result is False

    def test_get_nonexistent_skill(self, registry):
        """Test getting a skill that doesn't exist."""
        result = registry.get_skill("nonexistent")
        assert result is None

    def test_get_skill_count(self, registry, sample_skill, sample_skill_with_role):
        """Test getting total skill count."""
        assert registry.get_skill_count() == 0

        registry.register_skill(sample_skill)
        assert registry.get_skill_count() == 1

        registry.register_skill(sample_skill_with_role)
        assert registry.get_skill_count() == 2

    def test_clear_registry(self, registry, sample_skill, sample_skill_with_role):
        """Test clearing all skills from registry."""
        registry.register_skill(sample_skill)
        registry.register_skill(sample_skill_with_role)
        assert registry.get_skill_count() == 2

        registry.clear()
        assert registry.get_skill_count() == 0


class TestSkillListing:
    """Test skill listing and filtering."""

    def test_list_all_skills(self, registry, sample_skill, sample_skill_with_role):
        """Test listing all skills."""
        registry.register_skill(sample_skill)
        registry.register_skill(sample_skill_with_role)

        skills = registry.list_skills()
        assert len(skills) == 2
        skill_ids = [s.id for s in skills]
        assert "test_skill" in skill_ids
        assert "restricted_skill" in skill_ids

    def test_list_skills_excludes_disabled(self, registry, sample_skill, disabled_skill):
        """Test that list_skills excludes disabled skills by default."""
        registry.register_skill(sample_skill)
        registry.register_skill(disabled_skill)

        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0].id == "test_skill"

    def test_list_skills_includes_disabled_when_requested(self, registry, sample_skill, disabled_skill):
        """Test that list_skills can include disabled skills."""
        registry.register_skill(sample_skill)
        registry.register_skill(disabled_skill)

        skills = registry.list_skills(include_disabled=True)
        assert len(skills) == 2
        skill_ids = [s.id for s in skills]
        assert "disabled_skill" in skill_ids


class TestCategoryFiltering:
    """Test filtering skills by category."""

    def test_get_skills_by_category(self, registry):
        """Test getting skills by category."""
        skill1 = Skill(
            id="search_skill",
            name="Search",
            description="Search skill",
            category=SkillCategory.SEARCH,
            handler=dummy_handler
        )
        skill2 = Skill(
            id="analysis_skill",
            name="Analysis",
            description="Analysis skill",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler
        )
        skill3 = Skill(
            id="another_search",
            name="Another Search",
            description="Another search skill",
            category=SkillCategory.SEARCH,
            handler=dummy_handler
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)
        registry.register_skill(skill3)

        search_skills = registry.get_skills_by_category(SkillCategory.SEARCH)
        assert len(search_skills) == 2

        analysis_skills = registry.get_skills_by_category(SkillCategory.ANALYSIS)
        assert len(analysis_skills) == 1

    def test_get_skills_by_category_excludes_disabled(self, registry):
        """Test that category filtering excludes disabled skills."""
        skill1 = Skill(
            id="enabled_search",
            name="Enabled Search",
            description="Enabled",
            category=SkillCategory.SEARCH,
            handler=dummy_handler,
            enabled=True
        )
        skill2 = Skill(
            id="disabled_search",
            name="Disabled Search",
            description="Disabled",
            category=SkillCategory.SEARCH,
            handler=dummy_handler,
            enabled=False
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)

        search_skills = registry.get_skills_by_category(SkillCategory.SEARCH)
        assert len(search_skills) == 1
        assert search_skills[0].id == "enabled_search"

    def test_get_skills_by_empty_category(self, registry, sample_skill):
        """Test getting skills from category with no skills."""
        registry.register_skill(sample_skill)

        memory_skills = registry.get_skills_by_category(SkillCategory.MEMORY)
        assert len(memory_skills) == 0


class TestRoleFiltering:
    """Test filtering skills by role."""

    def test_get_skills_for_role(self, registry):
        """Test getting skills accessible to a role."""
        skill1 = Skill(
            id="public_skill",
            name="Public Skill",
            description="Available to all",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler,
            allowed_roles=set()  # Empty = all roles
        )
        skill2 = Skill(
            id="analyst_skill",
            name="Analyst Skill",
            description="Only for analysts",
            category=SkillCategory.DATA_QUERY,
            handler=dummy_handler,
            allowed_roles={"analyst", "data_scientist"}
        )
        skill3 = Skill(
            id="researcher_skill",
            name="Researcher Skill",
            description="Only for researchers",
            category=SkillCategory.SEARCH,
            handler=dummy_handler,
            allowed_roles={"researcher"}
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)
        registry.register_skill(skill3)

        # Analyst should see public + analyst skills
        analyst_skills = registry.get_skills_for_role("analyst")
        assert len(analyst_skills) == 2
        skill_ids = [s.id for s in analyst_skills]
        assert "public_skill" in skill_ids
        assert "analyst_skill" in skill_ids

        # Researcher should see public + researcher skills
        researcher_skills = registry.get_skills_for_role("researcher")
        assert len(researcher_skills) == 2
        skill_ids = [s.id for s in researcher_skills]
        assert "public_skill" in skill_ids
        assert "researcher_skill" in skill_ids

        # Unknown role should only see public skills
        other_skills = registry.get_skills_for_role("other")
        assert len(other_skills) == 1
        assert other_skills[0].id == "public_skill"

    def test_get_skills_for_role_excludes_disabled(self, registry):
        """Test that role filtering excludes disabled skills."""
        skill1 = Skill(
            id="enabled_public",
            name="Enabled Public",
            description="Enabled",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler,
            allowed_roles=set(),
            enabled=True
        )
        skill2 = Skill(
            id="disabled_public",
            name="Disabled Public",
            description="Disabled",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler,
            allowed_roles=set(),
            enabled=False
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)

        skills = registry.get_skills_for_role("any_role")
        assert len(skills) == 1
        assert skills[0].id == "enabled_public"


class TestSearch:
    """Test skill search functionality."""

    def test_search_by_name(self, registry):
        """Test searching skills by name."""
        skill1 = Skill(
            id="skill1",
            name="Data Analysis",
            description="Analyze data",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler
        )
        skill2 = Skill(
            id="skill2",
            name="Text Search",
            description="Search text",
            category=SkillCategory.SEARCH,
            handler=dummy_handler
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)

        results = registry.search_skills("Analysis")
        assert len(results) == 1
        assert results[0].id == "skill1"

        results = registry.search_skills("Search")
        assert len(results) == 1
        assert results[0].id == "skill2"

    def test_search_by_description(self, registry):
        """Test searching skills by description."""
        skill1 = Skill(
            id="skill1",
            name="Skill One",
            description="This is for data analysis",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler
        )
        skill2 = Skill(
            id="skill2",
            name="Skill Two",
            description="This handles text processing",
            category=SkillCategory.TOOLS,
            handler=dummy_handler
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)

        results = registry.search_skills("analysis")
        assert len(results) == 1
        assert results[0].id == "skill1"

        results = registry.search_skills("processing")
        assert len(results) == 1
        assert results[0].id == "skill2"

    def test_search_by_tags(self, registry):
        """Test searching skills by tags."""
        skill1 = Skill(
            id="skill1",
            name="Skill One",
            description="First skill",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler,
            tags=["python", "data", "analytics"]
        )
        skill2 = Skill(
            id="skill2",
            name="Skill Two",
            description="Second skill",
            category=SkillCategory.TOOLS,
            handler=dummy_handler,
            tags=["javascript", "web"]
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)

        results = registry.search_skills("python")
        assert len(results) == 1
        assert results[0].id == "skill1"

        results = registry.search_skills("web")
        assert len(results) == 1
        assert results[0].id == "skill2"

    def test_search_case_insensitive(self, registry, sample_skill):
        """Test that search is case insensitive."""
        registry.register_skill(sample_skill)

        results = registry.search_skills("TEST")
        assert len(results) == 1
        assert results[0].id == "test_skill"

        results = registry.search_skills("test")
        assert len(results) == 1

        results = registry.search_skills("TeSt")
        assert len(results) == 1

    def test_search_excludes_disabled(self, registry):
        """Test that search excludes disabled skills by default."""
        skill1 = Skill(
            id="enabled",
            name="Enabled Test Skill",
            description="Enabled",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler,
            enabled=True
        )
        skill2 = Skill(
            id="disabled",
            name="Disabled Test Skill",
            description="Disabled",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler,
            enabled=False
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)

        results = registry.search_skills("Test")
        assert len(results) == 1
        assert results[0].id == "enabled"

    def test_search_includes_disabled_when_requested(self, registry):
        """Test that search can include disabled skills."""
        skill1 = Skill(
            id="enabled",
            name="Enabled Test Skill",
            description="Enabled",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler,
            enabled=True
        )
        skill2 = Skill(
            id="disabled",
            name="Disabled Test Skill",
            description="Disabled",
            category=SkillCategory.ANALYSIS,
            handler=dummy_handler,
            enabled=False
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)

        results = registry.search_skills("Test", include_disabled=True)
        assert len(results) == 2

    def test_search_no_results(self, registry, sample_skill):
        """Test search with no matching results."""
        registry.register_skill(sample_skill)

        results = registry.search_skills("nonexistent")
        assert len(results) == 0

    def test_search_empty_query(self, registry, sample_skill):
        """Test search with empty query."""
        registry.register_skill(sample_skill)

        results = registry.search_skills("")
        # Empty query should match nothing since it's a substring search
        assert len(results) == 0


class TestThreadSafety:
    """Test thread safety of registry operations."""

    def test_concurrent_registration(self, registry):
        """Test that concurrent registration is thread-safe."""
        import threading

        def register_skills(start_id):
            for i in range(10):
                skill = Skill(
                    id=f"skill_{start_id}_{i}",
                    name=f"Skill {start_id} {i}",
                    description="Test skill",
                    category=SkillCategory.ANALYSIS,
                    handler=dummy_handler
                )
                registry.register_skill(skill)

        threads = []
        for i in range(5):
            t = threading.Thread(target=register_skills, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have 50 skills registered (5 threads × 10 skills)
        assert registry.get_skill_count() == 50
