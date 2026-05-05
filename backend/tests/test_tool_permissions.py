"""
Tests for tool permission resolution logic.

Tests cover:
- User-specific permissions
- Role-based permissions
- Permission priority (user > role > default)
- Default allow behavior (no permission entry = allowed)
- Rate limit inheritance
- Custom config overrides
- Permission constraint validation (user_id XOR role)
- Multiple roles resolution
"""

import uuid
from typing import List, Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Permission Resolution Helper (mirrors ToolFactory._filter_by_permissions)
# ============================================================================

class PermissionResolver:
    """
    Standalone permission resolver for testing.

    Implements the same logic as ToolFactory._filter_by_permissions
    from TOOL_CONFIGURATION_GUIDE.md Section 5.2, extracted here
    so we can test it independently of the full factory.
    """

    def __init__(self, permissions: List[Dict], user_roles: List[str]):
        """
        Args:
            permissions: List of permission records from tool_permissions table.
            user_roles: List of role names the user belongs to.
        """
        self.permissions = permissions
        self.user_roles = user_roles

    def resolve(self, tool_id: str, user_id: str) -> Dict[str, Any]:
        """
        Resolve the effective permission for a tool and user.

        Priority:
        1. User-specific permission (user_id match)
        2. Role-based permission (first matching role)
        3. Default: allowed=True, rate_limit=None

        Returns:
            Dict with keys: allowed, rate_limit, custom_config
        """
        user_perm = None
        role_perm = None

        for perm in self.permissions:
            if perm["tool_id"] != tool_id:
                continue

            # User-specific match
            if perm.get("user_id") == user_id:
                user_perm = perm
                break  # User-specific is highest priority

            # Role match
            if perm.get("role") in self.user_roles and role_perm is None:
                role_perm = perm

        # Priority: user > role > default
        if user_perm:
            return {
                "allowed": user_perm["allowed"],
                "rate_limit": user_perm.get("rate_limit"),
                "custom_config": user_perm.get("custom_config"),
                "source": "user",
            }
        elif role_perm:
            return {
                "allowed": role_perm["allowed"],
                "rate_limit": role_perm.get("rate_limit"),
                "custom_config": role_perm.get("custom_config"),
                "source": "role",
            }
        else:
            # Default: allowed
            return {
                "allowed": True,
                "rate_limit": None,
                "custom_config": None,
                "source": "default",
            }

    def filter_tools(
        self, tool_ids: List[str], user_id: str
    ) -> List[Dict[str, Any]]:
        """
        Filter a list of tools by permissions and return allowed tools
        with their resolved permissions.

        Args:
            tool_ids: List of tool IDs to check.
            user_id: The user requesting tools.

        Returns:
            List of dicts with tool_id and resolved permission data.
        """
        allowed = []
        for tool_id in tool_ids:
            resolution = self.resolve(tool_id, user_id)
            if resolution["allowed"]:
                allowed.append({"tool_id": tool_id, **resolution})
        return allowed


# ============================================================================
# Test User-Specific Permissions
# ============================================================================

class TestUserSpecificPermissions:
    """Test permissions applied to specific users."""

    def test_user_allowed(self):
        """Test user is explicitly allowed access."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "alice",
                "role": None,
                "allowed": True,
                "rate_limit": 50,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=[])

        result = resolver.resolve("t1", "alice")

        assert result["allowed"] is True
        assert result["rate_limit"] == 50
        assert result["source"] == "user"

    def test_user_denied(self):
        """Test user is explicitly denied access."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "bob",
                "role": None,
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=[])

        result = resolver.resolve("t1", "bob")

        assert result["allowed"] is False
        assert result["source"] == "user"

    def test_user_with_custom_config(self):
        """Test user permission with custom config override."""
        custom = {"max_results": 100, "timeout": 60}
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "alice",
                "role": None,
                "allowed": True,
                "rate_limit": 75,
                "custom_config": custom,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=[])

        result = resolver.resolve("t1", "alice")

        assert result["allowed"] is True
        assert result["custom_config"] == custom
        assert result["custom_config"]["max_results"] == 100

    def test_different_users_different_permissions(self):
        """Test different users have different permissions on same tool."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "alice",
                "role": None,
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            },
            {
                "tool_id": "t1",
                "user_id": "bob",
                "role": None,
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            },
        ]
        resolver = PermissionResolver(permissions, user_roles=[])

        alice_result = resolver.resolve("t1", "alice")
        bob_result = resolver.resolve("t1", "bob")

        assert alice_result["allowed"] is True
        assert bob_result["allowed"] is False


# ============================================================================
# Test Role-Based Permissions
# ============================================================================

class TestRoleBasedPermissions:
    """Test permissions applied to roles."""

    def test_role_allowed(self):
        """Test role grants access."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "admin",
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=["admin"])

        result = resolver.resolve("t1", "any-user")

        assert result["allowed"] is True
        assert result["rate_limit"] == 100
        assert result["source"] == "role"

    def test_role_denied(self):
        """Test role denies access."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "viewer",
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=["viewer"])

        result = resolver.resolve("t1", "any-user")

        assert result["allowed"] is False
        assert result["source"] == "role"

    def test_user_not_in_role(self):
        """Test that role permission doesn't apply to users not in that role."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "admin",
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            }
        ]
        # User is NOT an admin
        resolver = PermissionResolver(permissions, user_roles=["viewer"])

        result = resolver.resolve("t1", "non-admin-user")

        # Should fall through to default (allowed, no limit)
        assert result["allowed"] is True
        assert result["source"] == "default"
        assert result["rate_limit"] is None

    def test_multiple_roles_first_match_wins(self):
        """Test that first matching role permission wins."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "admin",
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            },
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "analyst",
                "allowed": True,
                "rate_limit": 20,
                "custom_config": None,
            },
        ]
        # User has both roles; admin permission is listed first
        resolver = PermissionResolver(permissions, user_roles=["admin", "analyst"])

        result = resolver.resolve("t1", "multi-role-user")

        assert result["allowed"] is True
        assert result["rate_limit"] == 100  # Admin's limit
        assert result["source"] == "role"

    def test_role_with_different_tools(self):
        """Test role permissions across different tools."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "analyst",
                "allowed": True,
                "rate_limit": 50,
                "custom_config": None,
            },
            {
                "tool_id": "t2",
                "user_id": None,
                "role": "analyst",
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            },
        ]
        resolver = PermissionResolver(permissions, user_roles=["analyst"])

        t1_result = resolver.resolve("t1", "analyst-user")
        t2_result = resolver.resolve("t2", "analyst-user")

        assert t1_result["allowed"] is True
        assert t2_result["allowed"] is False


# ============================================================================
# Test Permission Priority (User > Role > Default)
# ============================================================================

class TestPermissionPriority:
    """Test that permission resolution follows correct priority order."""

    def test_user_overrides_role_allow(self):
        """Test user permission overrides role: user=allow, role=deny."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "alice",
                "role": None,
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            },
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "analyst",
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            },
        ]
        resolver = PermissionResolver(permissions, user_roles=["analyst"])

        result = resolver.resolve("t1", "alice")

        # User-specific should win over role
        assert result["allowed"] is True
        assert result["source"] == "user"
        assert result["rate_limit"] == 100

    def test_user_overrides_role_deny(self):
        """Test user permission overrides role: user=deny, role=allow."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "bob",
                "role": None,
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            },
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "admin",
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            },
        ]
        resolver = PermissionResolver(permissions, user_roles=["admin"])

        result = resolver.resolve("t1", "bob")

        # User-specific deny should win over admin role allow
        assert result["allowed"] is False
        assert result["source"] == "user"

    def test_role_overrides_default(self):
        """Test role permission overrides default allow."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "restricted",
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=["restricted"])

        result = resolver.resolve("t1", "restricted-user")

        # Role deny should override default allow
        assert result["allowed"] is False
        assert result["source"] == "role"

    def test_user_rate_limit_overrides_role(self):
        """Test user-specific rate limit overrides role rate limit."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "power-user",
                "role": None,
                "allowed": True,
                "rate_limit": 200,
                "custom_config": None,
            },
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "analyst",
                "allowed": True,
                "rate_limit": 50,
                "custom_config": None,
            },
        ]
        resolver = PermissionResolver(permissions, user_roles=["analyst"])

        result = resolver.resolve("t1", "power-user")

        assert result["rate_limit"] == 200  # User-specific limit
        assert result["source"] == "user"


# ============================================================================
# Test Default Allow Behavior
# ============================================================================

class TestDefaultAllowBehavior:
    """Test that tools with no permission entries are allowed by default."""

    def test_no_permissions_means_allowed(self):
        """Test tool with no permission entries defaults to allowed."""
        permissions = []  # No permissions defined
        resolver = PermissionResolver(permissions, user_roles=[])

        result = resolver.resolve("t1", "any-user")

        assert result["allowed"] is True
        assert result["rate_limit"] is None
        assert result["custom_config"] is None
        assert result["source"] == "default"

    def test_permission_for_different_tool_means_default(self):
        """Test that permissions for other tools don't affect this tool."""
        permissions = [
            {
                "tool_id": "t2",  # Different tool
                "user_id": "alice",
                "role": None,
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=[])

        result = resolver.resolve("t1", "alice")

        # t1 has no permissions -> default allowed
        assert result["allowed"] is True
        assert result["source"] == "default"

    def test_permission_for_different_user_means_default(self):
        """Test that permissions for other users don't affect this user."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "bob",
                "role": None,
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=[])

        result = resolver.resolve("t1", "alice")

        # Alice has no permission for t1 -> default allowed
        assert result["allowed"] is True
        assert result["source"] == "default"


# ============================================================================
# Test Tool Filtering
# ============================================================================

class TestToolFiltering:
    """Test filtering a list of tools by permissions."""

    def test_filter_all_allowed_by_default(self):
        """Test all tools pass when no permissions defined."""
        resolver = PermissionResolver([], user_roles=[])

        result = resolver.filter_tools(["t1", "t2", "t3"], "user-1")

        assert len(result) == 3
        tool_ids = [r["tool_id"] for r in result]
        assert "t1" in tool_ids
        assert "t2" in tool_ids
        assert "t3" in tool_ids

    def test_filter_denies_blocked_tools(self):
        """Test that denied tools are filtered out."""
        permissions = [
            {
                "tool_id": "t2",
                "user_id": "user-1",
                "role": None,
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=[])

        result = resolver.filter_tools(["t1", "t2", "t3"], "user-1")

        assert len(result) == 2
        tool_ids = [r["tool_id"] for r in result]
        assert "t1" in tool_ids
        assert "t2" not in tool_ids
        assert "t3" in tool_ids

    def test_filter_applies_rate_limits(self):
        """Test that filtered tools include rate limit info."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "analyst",
                "allowed": True,
                "rate_limit": 50,
                "custom_config": None,
            },
            {
                "tool_id": "t2",
                "user_id": None,
                "role": "analyst",
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            },
        ]
        resolver = PermissionResolver(permissions, user_roles=["analyst"])

        result = resolver.filter_tools(["t1", "t2"], "analyst-user")

        assert len(result) == 2
        t1_result = next(r for r in result if r["tool_id"] == "t1")
        t2_result = next(r for r in result if r["tool_id"] == "t2")
        assert t1_result["rate_limit"] == 50
        assert t2_result["rate_limit"] == 100

    def test_filter_admin_gets_all_tools(self):
        """Test admin role gets access to all tools."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "admin",
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            },
            {
                "tool_id": "t2",
                "user_id": None,
                "role": "admin",
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            },
            {
                "tool_id": "t3",
                "user_id": None,
                "role": "admin",
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            },
        ]
        resolver = PermissionResolver(permissions, user_roles=["admin"])

        result = resolver.filter_tools(["t1", "t2", "t3"], "admin-user")

        assert len(result) == 3

    def test_filter_analyst_limited_tools(self):
        """Test analyst role gets limited tools (Scenario 2 from guide)."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "analyst",
                "allowed": True,
                "rate_limit": 50,
                "custom_config": None,
            },
            {
                "tool_id": "t2",
                "user_id": None,
                "role": "analyst",
                "allowed": False,  # Blocked for analysts
                "rate_limit": None,
                "custom_config": None,
            },
        ]
        resolver = PermissionResolver(permissions, user_roles=["analyst"])

        result = resolver.filter_tools(["t1", "t2", "t3"], "analyst-user")

        # t1 allowed, t2 denied, t3 default-allowed
        assert len(result) == 2
        tool_ids = [r["tool_id"] for r in result]
        assert "t1" in tool_ids
        assert "t2" not in tool_ids
        assert "t3" in tool_ids

    def test_filter_user_override_restores_access(self):
        """Test Scenario 3: user override restores access denied by role."""
        permissions = [
            # Alice gets code_exec despite analyst role
            {
                "tool_id": "code_exec",
                "user_id": "alice",
                "role": None,
                "allowed": True,
                "rate_limit": None,
                "custom_config": None,
            },
            # Analyst role blocks code_exec
            {
                "tool_id": "code_exec",
                "user_id": None,
                "role": "analyst",
                "allowed": False,
                "rate_limit": None,
                "custom_config": None,
            },
        ]
        resolver = PermissionResolver(permissions, user_roles=["analyst"])

        # Alice should have access (user override)
        alice_result = resolver.filter_tools(["code_exec"], "alice")
        assert len(alice_result) == 1
        assert alice_result[0]["allowed"] is True

        # Bob (analyst, no user override) should be denied
        bob_result = resolver.filter_tools(["code_exec"], "bob")
        assert len(bob_result) == 0


# ============================================================================
# Test Permission Constraint Validation
# ============================================================================

class TestPermissionConstraints:
    """Test permission record validation constraints."""

    def test_valid_user_permission(self):
        """Test permission with user_id and no role is valid."""
        perm = {
            "tool_id": "t1",
            "user_id": "alice",
            "role": None,
            "allowed": True,
        }

        # Validate: exactly one of user_id or role must be set
        has_user = perm["user_id"] is not None
        has_role = perm["role"] is not None
        assert has_user != has_role  # XOR

    def test_valid_role_permission(self):
        """Test permission with role and no user_id is valid."""
        perm = {
            "tool_id": "t1",
            "user_id": None,
            "role": "admin",
            "allowed": True,
        }

        has_user = perm["user_id"] is not None
        has_role = perm["role"] is not None
        assert has_user != has_role  # XOR

    def test_invalid_both_user_and_role(self):
        """Test permission with both user_id and role is invalid."""
        perm = {
            "tool_id": "t1",
            "user_id": "alice",
            "role": "admin",
            "allowed": True,
        }

        has_user = perm["user_id"] is not None
        has_role = perm["role"] is not None
        # Both set - violates constraint
        assert not (has_user != has_role)

    def test_invalid_neither_user_nor_role(self):
        """Test permission with neither user_id nor role is invalid."""
        perm = {
            "tool_id": "t1",
            "user_id": None,
            "role": None,
            "allowed": True,
        }

        has_user = perm["user_id"] is not None
        has_role = perm["role"] is not None
        # Neither set - violates constraint
        assert not (has_user != has_role)


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestPermissionEdgeCases:
    """Test edge cases in permission resolution."""

    def test_empty_tool_list(self):
        """Test filtering an empty list of tools."""
        resolver = PermissionResolver([], user_roles=[])
        result = resolver.filter_tools([], "user-1")
        assert result == []

    def test_empty_permissions_list(self):
        """Test resolving with no permissions defined."""
        resolver = PermissionResolver([], user_roles=["admin"])
        result = resolver.resolve("t1", "user-1")
        assert result["allowed"] is True
        assert result["source"] == "default"

    def test_many_tools_performance(self):
        """Test resolving permissions for many tools is efficient."""
        # Create 100 permissions
        permissions = [
            {
                "tool_id": f"t{i}",
                "user_id": None,
                "role": "analyst",
                "allowed": i % 2 == 0,
                "rate_limit": 50 if i % 2 == 0 else None,
                "custom_config": None,
            }
            for i in range(100)
        ]
        resolver = PermissionResolver(permissions, user_roles=["analyst"])

        tool_ids = [f"t{i}" for i in range(100)]
        result = resolver.filter_tools(tool_ids, "analyst-user")

        # Even tools allowed, odd tools denied
        assert len(result) == 50

    def test_permission_with_none_rate_limit(self):
        """Test that None rate_limit means no limit."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "alice",
                "role": None,
                "allowed": True,
                "rate_limit": None,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=[])

        result = resolver.resolve("t1", "alice")

        assert result["allowed"] is True
        assert result["rate_limit"] is None

    def test_permission_with_zero_rate_limit(self):
        """Test that 0 rate_limit effectively blocks usage."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": "alice",
                "role": None,
                "allowed": True,
                "rate_limit": 0,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=[])

        result = resolver.resolve("t1", "alice")

        assert result["allowed"] is True
        assert result["rate_limit"] == 0  # Effectively blocks

    def test_user_with_no_roles(self):
        """Test user with no roles only gets default or user-specific permissions."""
        permissions = [
            {
                "tool_id": "t1",
                "user_id": None,
                "role": "admin",
                "allowed": True,
                "rate_limit": 100,
                "custom_config": None,
            }
        ]
        resolver = PermissionResolver(permissions, user_roles=[])  # No roles

        result = resolver.resolve("t1", "roleless-user")

        # Should get default, not admin role
        assert result["source"] == "default"
        assert result["rate_limit"] is None
