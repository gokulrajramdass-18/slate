"""
Settings Lookups Router

Admin-managed lookup lists for configurable dropdowns across the app.

Each lookup list is stored as a single JSON document in the `settings` table
under the key `lookup.{key}`, e.g. `lookup.workflow_template_categories`.

Public consumers fetch active items via `GET /options`. Admins manage the full
list (incl. inactive items) via the other endpoints.
"""

import re
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.services.settings import get_setting, set_setting

router = APIRouter(prefix="/api/settings/lookups", tags=["settings", "lookups"])


SLUG_PATTERN = re.compile(r"^[a-z0-9_-]+$")
LOOKUP_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")
STORAGE_PREFIX = "lookup."


# Placeholder admin dependency, mirrors roles.py / users.py.
def require_admin():
    pass


# ============================================================================
# Models
# ============================================================================


class LookupItem(BaseModel):
    value: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    active: bool = True
    sort_order: int = 0


class LookupItemUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    active: Optional[bool] = None
    sort_order: Optional[int] = None


class LookupList(BaseModel):
    title: str = ""
    description: str = ""
    items: List[LookupItem] = []


class LookupListSummary(BaseModel):
    key: str
    title: str
    description: str
    item_count: int
    active_count: int


class LookupOption(BaseModel):
    value: str
    label: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    sort_order: int = 0


# ============================================================================
# Helpers
# ============================================================================


def _validate_lookup_key(key: str) -> None:
    if not LOOKUP_KEY_PATTERN.match(key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lookup key must match [a-z0-9_]+",
        )


def _validate_slug(value: str) -> None:
    if not SLUG_PATTERN.match(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item value '{value}' is not slug-safe (allowed: a-z, 0-9, _, -)",
        )


def _storage_key(key: str) -> str:
    return f"{STORAGE_PREFIX}{key}"


async def _load_list(key: str) -> Optional[Dict[str, Any]]:
    """Return raw JSON document or None if not registered."""
    return await get_setting(_storage_key(key), default=None)


async def _save_list(key: str, doc: Dict[str, Any]) -> None:
    await set_setting(
        _storage_key(key),
        doc,
        value_type="json",
        description=f"Lookup list: {key}",
    )


def _normalize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort by sort_order then label, ensure required fields present."""
    normalized = []
    for item in items:
        normalized.append({
            "value": item["value"],
            "label": item["label"],
            "description": item.get("description"),
            "icon": item.get("icon"),
            "color": item.get("color"),
            "active": item.get("active", True),
            "sort_order": item.get("sort_order", 0),
        })
    normalized.sort(key=lambda x: (x["sort_order"], x["label"].lower()))
    return normalized


# ============================================================================
# Public consumer endpoint
# ============================================================================


@router.get("/{key}/options", response_model=List[LookupOption])
async def get_options(key: str):
    """Public: return only active items in sort order. No auth required."""
    _validate_lookup_key(key)
    doc = await _load_list(key)
    if not doc:
        return []

    items = _normalize_items(doc.get("items", []))
    return [
        LookupOption(
            value=i["value"],
            label=i["label"],
            description=i.get("description"),
            icon=i.get("icon"),
            color=i.get("color"),
            sort_order=i["sort_order"],
        )
        for i in items
        if i.get("active", True)
    ]


# ============================================================================
# Admin endpoints
# ============================================================================


@router.get("", response_model=List[LookupListSummary])
async def list_lookups(_: None = Depends(require_admin)):
    """List all registered lookup lists with item counts."""
    import aiosqlite
    import json
    import os

    db_path = os.getenv("SQLITE_DB_PATH", "./data/database.db")
    summaries: List[LookupListSummary] = []

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT key, value FROM settings WHERE key LIKE ? ORDER BY key",
            (f"{STORAGE_PREFIX}%",),
        )
        rows = await cursor.fetchall()

    for storage_key, raw_value in rows:
        key = storage_key[len(STORAGE_PREFIX):]
        try:
            doc = json.loads(raw_value) if raw_value else {}
        except json.JSONDecodeError:
            doc = {}
        items = doc.get("items", [])
        summaries.append(LookupListSummary(
            key=key,
            title=doc.get("title", key),
            description=doc.get("description", ""),
            item_count=len(items),
            active_count=sum(1 for i in items if i.get("active", True)),
        ))

    return summaries


@router.get("/{key}", response_model=LookupList)
async def get_lookup(key: str, _: None = Depends(require_admin)):
    """Fetch full list including inactive items (admin)."""
    _validate_lookup_key(key)
    doc = await _load_list(key)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lookup list '{key}' not registered",
        )
    return LookupList(
        title=doc.get("title", key),
        description=doc.get("description", ""),
        items=[LookupItem(**i) for i in _normalize_items(doc.get("items", []))],
    )


@router.put("/{key}", response_model=LookupList)
async def replace_lookup(
    key: str,
    payload: LookupList,
    _: None = Depends(require_admin),
):
    """Replace the full list. Creates the list if it doesn't exist."""
    _validate_lookup_key(key)

    seen = set()
    for item in payload.items:
        _validate_slug(item.value)
        if item.value in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate item value '{item.value}'",
            )
        seen.add(item.value)

    doc = {
        "title": payload.title,
        "description": payload.description,
        "items": _normalize_items([i.model_dump() for i in payload.items]),
    }
    await _save_list(key, doc)
    return LookupList(
        title=doc["title"],
        description=doc["description"],
        items=[LookupItem(**i) for i in doc["items"]],
    )


@router.post("/{key}/items", response_model=LookupItem, status_code=status.HTTP_201_CREATED)
async def add_item(
    key: str,
    item: LookupItem,
    _: None = Depends(require_admin),
):
    _validate_lookup_key(key)
    _validate_slug(item.value)

    doc = await _load_list(key) or {"title": key, "description": "", "items": []}
    items = doc.get("items", [])
    if any(i["value"] == item.value for i in items):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Item '{item.value}' already exists",
        )
    items.append(item.model_dump())
    doc["items"] = _normalize_items(items)
    await _save_list(key, doc)
    return item


@router.patch("/{key}/items/{value}", response_model=LookupItem)
async def update_item(
    key: str,
    value: str,
    patch: LookupItemUpdate,
    _: None = Depends(require_admin),
):
    _validate_lookup_key(key)
    _validate_slug(value)

    doc = await _load_list(key)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lookup list '{key}' not registered",
        )

    items = doc.get("items", [])
    target = next((i for i in items if i["value"] == value), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item '{value}' not found",
        )

    for field, new_value in patch.model_dump(exclude_unset=True).items():
        target[field] = new_value

    doc["items"] = _normalize_items(items)
    await _save_list(key, doc)
    return LookupItem(**target)


@router.delete("/{key}/items/{value}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    key: str,
    value: str,
    _: None = Depends(require_admin),
):
    _validate_lookup_key(key)
    _validate_slug(value)

    doc = await _load_list(key)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lookup list '{key}' not registered",
        )

    items = doc.get("items", [])
    new_items = [i for i in items if i["value"] != value]
    if len(new_items) == len(items):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item '{value}' not found",
        )

    doc["items"] = _normalize_items(new_items)
    await _save_list(key, doc)
