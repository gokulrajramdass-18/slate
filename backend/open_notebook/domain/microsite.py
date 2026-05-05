"""
Domain model for Microsites
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
import uuid
import secrets
import string

from open_notebook.domain.base import ObjectModel


class Microsite(ObjectModel):
    """A public microsite sharing notebook content"""
    notebook_id: str
    title: str
    description: Optional[str] = None
    slug: Optional[str] = None
    theme: str = "light"
    is_active: bool = True

    # Status management
    status: str = "draft"  # draft, published, blocked
    created_by: Optional[str] = None  # User ID or email
    active_version_id: Optional[str] = None  # FK to microsite_versions

    # Generator fields (added by migration 011)
    template_id: Optional[str] = None
    custom_css: Optional[str] = None
    custom_js: Optional[str] = None
    generation_config: Optional[str] = None      # JSON string
    moderation_status: str = "pending"  # pending, passed, needs_review, blocked
    published_version: Optional[int] = None
    last_generated: Optional[str] = None

    _table_name = "microsites"

    def model_post_init(self, __context: Any) -> None:
        """Pydantic v2 hook called after model initialization"""
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.slug:
            self.slug = self._generate_slug()
        if not self.created:
            self.created = datetime.utcnow()
        if not self.updated:
            self.updated = datetime.utcnow()

    def _generate_slug(self) -> str:
        """Generate a unique URL-safe slug using UUID"""
        # Use a shorter UUID format (first 12 characters)
        return str(uuid.uuid4())[:12]

    def get_generation_config(self) -> Dict[str, Any]:
        """Parse the generation_config JSON into a dictionary."""
        if not self.generation_config:
            return {}
        if isinstance(self.generation_config, dict):
            return self.generation_config
        try:
            return json.loads(self.generation_config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_generation_config(self, config: Dict[str, Any]) -> None:
        """Serialize a dictionary into the generation_config JSON field."""
        self.generation_config = json.dumps(config)

    @classmethod
    async def create(
        cls,
        notebook_id: str,
        title: str,
        created_by: str,
        **kwargs: Any,
    ) -> "Microsite":
        """Create a new microsite (always starts as draft).

        Args:
            notebook_id: The notebook this microsite belongs to.
            title: Display title.
            created_by: User ID or email of the creator.
            **kwargs: Additional field overrides (description, theme, etc.).

        Returns:
            The saved Microsite instance.
        """
        microsite = cls(
            notebook_id=notebook_id,
            title=title,
            status="draft",
            created_by=created_by,
            **kwargs,
        )
        await microsite.save()
        return microsite

    async def can_access(self, user_id: Optional[str] = None) -> bool:
        """Check if a user can access this microsite.

        - Published microsites are publicly accessible.
        - Draft microsites are only accessible to their creator.
        - Blocked microsites are not accessible (admin check is external).
        """
        if self.status == "published":
            return True
        if self.status == "draft" and user_id and user_id == self.created_by:
            return True
        return False

    async def publish(self, version_id: str) -> None:
        """Publish the microsite with a specific version.

        Sets status to published and records the active version.
        """
        self.status = "published"
        self.active_version_id = version_id
        await self.save()

    async def unpublish(self) -> None:
        """Unpublish the microsite (revert to draft status)."""
        self.status = "draft"
        self.active_version_id = None
        await self.save()

    async def block(self, reason: Optional[str] = None) -> None:
        """Block the microsite (moderation action).

        Args:
            reason: Optional reason for blocking (for logging purposes).
        """
        self.status = "blocked"
        self.active_version_id = None
        await self.save()


class MicrositeAccess(ObjectModel):
    """Email addresses allowed to access a microsite"""
    microsite_id: str
    email: str

    _table_name = "microsite_access"

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created:
            self.created = datetime.utcnow()


class MicrositeOTP(ObjectModel):
    """One-time password for microsite access"""
    microsite_id: str
    email: str
    otp_code: Optional[str] = None
    expires_at: Optional[datetime] = None
    verified: bool = False

    _table_name = "microsite_otp"

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.otp_code:
            self.otp_code = self._generate_otp()
        if not self.expires_at:
            # OTP expires in 15 minutes
            self.expires_at = datetime.utcnow() + timedelta(minutes=15)
        if not self.created:
            self.created = datetime.utcnow()

    def _generate_otp(self) -> str:
        """Generate a 6-digit OTP code"""
        return "".join(secrets.choice(string.digits) for _ in range(6))

    def is_valid(self) -> bool:
        """Check if OTP is still valid"""
        if self.verified:
            return False
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.utcnow() < expires
