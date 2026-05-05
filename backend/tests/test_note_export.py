"""
Test script for note export endpoints
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routers.notes import get_note, export_note_markdown, export_note_pdf
from open_notebook.database.repository import repo_query, repo_execute
import uuid


async def test_note_export():
    """Test note export functionality"""

    # Create a test note
    note_id = str(uuid.uuid4())
    print(f"Creating test note with ID: {note_id}")

    await repo_execute(
        """
        INSERT INTO notes (id, title, content, content_html, created, updated)
        VALUES (:id, :title, :content, :content_html, :created, :updated)
        """,
        {
            "id": note_id,
            "title": "Test Export Note",
            "content": "This is a **test note** with some markdown content.\n\n## Features\n- Feature 1\n- Feature 2",
            "content_html": "<p>This is a <strong>test note</strong> with some markdown content.</p><h2>Features</h2><ul><li>Feature 1</li><li>Feature 2</li></ul>",
            "created": "2024-04-09T10:00:00",
            "updated": "2024-04-09T10:00:00",
        }
    )

    # Add some tags
    await repo_execute(
        "INSERT INTO note_tags (note_id, tag) VALUES (:note_id, :tag)",
        {"note_id": note_id, "tag": "test"}
    )
    await repo_execute(
        "INSERT INTO note_tags (note_id, tag) VALUES (:note_id, :tag)",
        {"note_id": note_id, "tag": "export"}
    )

    # Test markdown export
    print("\n✅ Testing Markdown export...")
    try:
        markdown_response = await export_note_markdown(note_id)
        print(f"   Markdown size: {len(markdown_response.body)} bytes")
        print(f"   Content-Type: {markdown_response.media_type}")
        assert markdown_response.media_type == "text/markdown"
        print("   ✅ Markdown export successful")
    except Exception as e:
        print(f"   ❌ Markdown export failed: {e}")
        raise

    # Test PDF export
    print("\n✅ Testing PDF export...")
    try:
        pdf_response = await export_note_pdf(note_id)
        print(f"   PDF size: {len(pdf_response.body)} bytes")
        print(f"   Content-Type: {pdf_response.media_type}")
        assert pdf_response.media_type == "application/pdf"
        print("   ✅ PDF export successful")
    except Exception as e:
        print(f"   ❌ PDF export failed: {e}")
        raise

    # Cleanup
    await repo_execute("DELETE FROM note_tags WHERE note_id = :note_id", {"note_id": note_id})
    await repo_execute("DELETE FROM notes WHERE id = :id", {"id": note_id})
    print(f"\n✅ Cleanup complete - deleted test note {note_id}")

    print("\n✅✅✅ All export endpoint tests passed!")


if __name__ == "__main__":
    asyncio.run(test_note_export())
