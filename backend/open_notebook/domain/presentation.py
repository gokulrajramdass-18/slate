"""
Domain models for Presentation Generator feature.

This module defines the data structures for presentations, including:
- PresentationTemplate: Slide layouts and visual themes
- PresentationContent: Individual slide content
- PresentationVersion: Version snapshots for rollback
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json


class SlideType(str, Enum):
    """Available slide layout types"""
    TITLE = "title"
    BULLETS = "bullets"
    TWO_COLUMN = "two_column"
    CONTENT = "content"
    IMAGE_TEXT = "image_text"
    CHART = "chart"


class TemplateCategory(str, Enum):
    """Presentation template categories"""
    BUSINESS = "business"
    ACADEMIC = "academic"
    SALES = "sales"
    PITCH = "pitch"
    REPORT = "report"
    MARKETING = "marketing"


@dataclass
class PresentationTemplate:
    """
    Defines slide layouts and visual themes for presentations.

    Attributes:
        id: Unique identifier
        name: Display name (e.g., "Business Pitch")
        description: Template description
        category: Template category
        theme_json: Theme configuration with colors, fonts, layouts
        slide_layouts: Available slide layout types
        is_active: Whether template is active
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    theme_json: Dict[str, Any] = field(default_factory=dict)
    slide_layouts: List[str] = field(default_factory=list)
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "theme_json": json.dumps(self.theme_json) if isinstance(self.theme_json, dict) else self.theme_json,
            "slide_layouts": json.dumps(self.slide_layouts) if isinstance(self.slide_layouts, list) else self.slide_layouts,
            "is_active": 1 if self.is_active else 0,
            "created_at": self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else datetime.utcnow().isoformat()
        }

    @classmethod
    def from_db(cls, row: Dict[str, Any]) -> "PresentationTemplate":
        """Create instance from database row"""
        return cls(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
            category=row.get("category"),
            theme_json=json.loads(row["theme_json"]) if isinstance(row["theme_json"], str) else row["theme_json"],
            slide_layouts=json.loads(row["slide_layouts"]) if isinstance(row.get("slide_layouts"), str) else row.get("slide_layouts", []),
            is_active=bool(row.get("is_active", 1)),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None
        )

    def get_theme_colors(self) -> Dict[str, str]:
        """Get theme colors"""
        return self.theme_json.get("colors", {})

    def get_theme_fonts(self) -> Dict[str, str]:
        """Get theme fonts"""
        return self.theme_json.get("fonts", {})


@dataclass
class SlideElement:
    """
    Individual element within a slide (bullet, paragraph, image, etc.)

    Attributes:
        type: Element type (bullet, paragraph, heading, image)
        content: Element content/text
        position: Optional position data for layout
        style: Optional styling information
        level: For bullets, the indentation level (0-based)
    """
    type: str
    content: str
    position: Optional[Dict[str, Any]] = None
    style: Optional[Dict[str, Any]] = None
    level: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.type,
            "content": self.content,
            "position": self.position,
            "style": self.style,
            "level": self.level
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlideElement":
        """Create instance from dictionary"""
        return cls(
            type=data["type"],
            content=data["content"],
            position=data.get("position"),
            style=data.get("style"),
            level=data.get("level", 0)
        )


@dataclass
class PresentationContent:
    """
    Individual slide content within a presentation.

    Attributes:
        id: Unique identifier
        presentation_id: Parent presentation ID
        slide_number: 1-based slide number
        slide_type: Type of slide layout
        content_html: HTML representation for preview
        content_json: Structured data for PPTX export
        speaker_notes: Optional speaker notes
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    id: str
    presentation_id: str
    slide_number: int
    slide_type: str
    content_html: Optional[str] = None
    content_json: Dict[str, Any] = field(default_factory=dict)
    speaker_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "presentation_id": self.presentation_id,
            "slide_number": self.slide_number,
            "slide_type": self.slide_type,
            "content_html": self.content_html,
            "content_json": json.dumps(self.content_json) if isinstance(self.content_json, dict) else self.content_json,
            "speaker_notes": self.speaker_notes,
            "created_at": self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else datetime.utcnow().isoformat()
        }

    @classmethod
    def from_db(cls, row: Dict[str, Any]) -> "PresentationContent":
        """Create instance from database row"""
        return cls(
            id=row["id"],
            presentation_id=row["presentation_id"],
            slide_number=row["slide_number"],
            slide_type=row["slide_type"],
            content_html=row.get("content_html"),
            content_json=json.loads(row["content_json"]) if isinstance(row.get("content_json"), str) else row.get("content_json", {}),
            speaker_notes=row.get("speaker_notes"),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None
        )

    def get_title(self) -> str:
        """Get slide title"""
        return self.content_json.get("title", "")

    def get_elements(self) -> List[SlideElement]:
        """Get slide elements"""
        elements_data = self.content_json.get("elements", [])
        return [SlideElement.from_dict(elem) for elem in elements_data]

    def set_title(self, title: str):
        """Set slide title"""
        self.content_json["title"] = title

    def set_elements(self, elements: List[SlideElement]):
        """Set slide elements"""
        self.content_json["elements"] = [elem.to_dict() for elem in elements]


@dataclass
class PresentationVersion:
    """
    Version snapshot for presentation rollback.

    Attributes:
        id: Unique identifier
        presentation_id: Parent presentation ID
        version_number: Sequential version number
        slides_snapshot: JSON array of all slide content
        created_at: Creation timestamp
        created_by: User who created this version
    """
    id: str
    presentation_id: str
    version_number: int
    slides_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "presentation_id": self.presentation_id,
            "version_number": self.version_number,
            "slides_snapshot": json.dumps(self.slides_snapshot) if isinstance(self.slides_snapshot, list) else self.slides_snapshot,
            "created_at": self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat(),
            "created_by": self.created_by
        }

    @classmethod
    def from_db(cls, row: Dict[str, Any]) -> "PresentationVersion":
        """Create instance from database row"""
        return cls(
            id=row["id"],
            presentation_id=row["presentation_id"],
            version_number=row["version_number"],
            slides_snapshot=json.loads(row["slides_snapshot"]) if isinstance(row.get("slides_snapshot"), str) else row.get("slides_snapshot", []),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            created_by=row.get("created_by")
        )


@dataclass
class Presentation:
    """
    Main presentation entity.

    Attributes:
        id: Unique identifier
        notebook_id: Associated workspace/notebook
        template_id: Template used
        title: Presentation title
        description: Optional description
        created_at: Creation timestamp
        updated_at: Last update timestamp
        created_by: User who created presentation
    """
    id: str
    notebook_id: Optional[str] = None
    template_id: Optional[str] = None
    title: str = "Untitled Presentation"
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "id": self.id,
            "notebook_id": self.notebook_id,
            "template_id": self.template_id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else datetime.utcnow().isoformat(),
            "created_by": self.created_by
        }

    @classmethod
    def from_db(cls, row: Dict[str, Any]) -> "Presentation":
        """Create instance from database row"""
        return cls(
            id=row["id"],
            notebook_id=row.get("notebook_id"),
            template_id=row.get("template_id"),
            title=row.get("title", "Untitled Presentation"),
            description=row.get("description"),
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None,
            created_by=row.get("created_by")
        )
