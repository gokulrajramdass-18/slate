"""
Service for exporting notes to different formats (Markdown, PDF)
"""
from typing import Optional, List
from datetime import datetime
from io import BytesIO
import markdown
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from bs4 import BeautifulSoup


class NoteExportService:
    """Service for exporting notes to various formats"""

    @staticmethod
    def export_to_markdown(
        note_title: str,
        note_content: str,
        tags: Optional[List[str]] = None,
        linked_notes: Optional[List[dict]] = None,
        created: Optional[str] = None,
        updated: Optional[str] = None,
    ) -> str:
        """
        Export note to Markdown format

        Args:
            note_title: Title of the note
            note_content: Content of the note (markdown)
            tags: List of tags
            linked_notes: List of linked notes
            created: Creation timestamp
            updated: Last update timestamp

        Returns:
            Formatted markdown string
        """
        lines = []

        # Title
        lines.append(f"# {note_title}\n")

        # Metadata
        if tags or created or updated:
            lines.append("---\n")
            if tags:
                lines.append(f"**Tags:** {', '.join(tags)}\n")
            if created:
                lines.append(f"**Created:** {created}\n")
            if updated:
                lines.append(f"**Updated:** {updated}\n")
            lines.append("---\n")

        # Content
        lines.append("\n")
        lines.append(note_content)
        lines.append("\n")

        # Linked notes
        if linked_notes and len(linked_notes) > 0:
            lines.append("\n---\n")
            lines.append("## Linked Notes\n\n")
            for linked in linked_notes:
                lines.append(f"- {linked.get('title', 'Untitled')}\n")

        return "\n".join(lines)

    @staticmethod
    def export_to_pdf(
        note_title: str,
        note_content: str,
        note_content_html: Optional[str] = None,
        tags: Optional[List[str]] = None,
        linked_notes: Optional[List[dict]] = None,
        created: Optional[str] = None,
        updated: Optional[str] = None,
    ) -> bytes:
        """
        Export note to PDF format

        Args:
            note_title: Title of the note
            note_content: Content of the note (markdown)
            note_content_html: HTML version of content
            tags: List of tags
            linked_notes: List of linked notes
            created: Creation timestamp
            updated: Last update timestamp

        Returns:
            PDF file as bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        # Container for the 'Flowable' objects
        elements = []

        # Define styles
        styles = getSampleStyleSheet()

        # Custom title style
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor='#1a1a1a',
            spaceAfter=30,
            alignment=TA_CENTER,
        )

        # Custom metadata style
        meta_style = ParagraphStyle(
            'MetaData',
            parent=styles['Normal'],
            fontSize=10,
            textColor='#666666',
            spaceAfter=6,
        )

        # Custom tag style
        tag_style = ParagraphStyle(
            'TagStyle',
            parent=styles['Normal'],
            fontSize=9,
            textColor='#4a5568',
            spaceAfter=12,
        )

        # Custom body style
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=11,
            leading=16,
            spaceAfter=12,
        )

        # Title
        elements.append(Paragraph(note_title, title_style))
        elements.append(Spacer(1, 12))

        # Metadata
        if tags:
            tag_text = f"<b>Tags:</b> {', '.join(tags)}"
            elements.append(Paragraph(tag_text, tag_style))

        if created:
            elements.append(Paragraph(f"<b>Created:</b> {created}", meta_style))

        if updated:
            elements.append(Paragraph(f"<b>Updated:</b> {updated}", meta_style))

        elements.append(Spacer(1, 20))

        # Separator line
        elements.append(Paragraph("_" * 80, meta_style))
        elements.append(Spacer(1, 20))

        # Content
        # If we have HTML content, use it; otherwise convert markdown to HTML
        if note_content_html:
            html_content = note_content_html
        else:
            html_content = markdown.markdown(
                note_content,
                extensions=['extra', 'codehilite', 'tables']
            )

        # Clean and format HTML for PDF
        soup = BeautifulSoup(html_content, 'html.parser')

        # Process content blocks
        for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'li']):
            text = element.get_text()

            if element.name == 'h1':
                style = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=18, spaceAfter=12)
                elements.append(Paragraph(text, style))
            elif element.name == 'h2':
                style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=16, spaceAfter=10)
                elements.append(Paragraph(text, style))
            elif element.name == 'h3':
                style = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=14, spaceAfter=8)
                elements.append(Paragraph(text, style))
            elif element.name in ['ul', 'ol']:
                # Skip list containers, process individual items
                continue
            elif element.name == 'li':
                bullet_style = ParagraphStyle('Bullet', parent=body_style, leftIndent=20)
                elements.append(Paragraph(f"• {text}", bullet_style))
            else:
                # Regular paragraph
                elements.append(Paragraph(text, body_style))

        # Linked notes
        if linked_notes and len(linked_notes) > 0:
            elements.append(Spacer(1, 30))
            elements.append(Paragraph("_" * 80, meta_style))
            elements.append(Spacer(1, 12))

            header_style = ParagraphStyle('LinkedHeader', parent=styles['Heading2'], fontSize=14)
            elements.append(Paragraph("Linked Notes", header_style))
            elements.append(Spacer(1, 8))

            for linked in linked_notes:
                linked_style = ParagraphStyle('Linked', parent=body_style, leftIndent=20)
                elements.append(Paragraph(f"• {linked.get('title', 'Untitled')}", linked_style))

        # Build PDF
        doc.build(elements)

        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    @staticmethod
    def export_multiple_notes_to_pdf(notes: List[dict]) -> bytes:
        """
        Export multiple notes to a single PDF file

        Args:
            notes: List of note dictionaries

        Returns:
            PDF file as bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )

        elements = []
        styles = getSampleStyleSheet()

        for idx, note in enumerate(notes):
            # Add page break between notes (except for first note)
            if idx > 0:
                elements.append(PageBreak())

            # Export individual note
            note_title = note.get('title', 'Untitled')
            note_content = note.get('content', '')
            note_content_html = note.get('content_html')
            tags = note.get('tags', [])
            linked_notes = note.get('linked_notes', [])
            created = note.get('created')
            updated = note.get('updated')

            # Use the same formatting as single note export
            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=20,
                textColor='#1a1a1a',
                spaceAfter=20,
            )
            elements.append(Paragraph(note_title, title_style))

            # Metadata
            meta_style = ParagraphStyle(
                'MetaData',
                parent=styles['Normal'],
                fontSize=9,
                textColor='#666666',
                spaceAfter=6,
            )

            if tags:
                elements.append(Paragraph(f"<b>Tags:</b> {', '.join(tags)}", meta_style))
            if created:
                elements.append(Paragraph(f"<b>Created:</b> {created}", meta_style))
            if updated:
                elements.append(Paragraph(f"<b>Updated:</b> {updated}", meta_style))

            elements.append(Spacer(1, 12))

            # Content
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontSize=11,
                leading=16,
                spaceAfter=12,
            )

            if note_content_html:
                html_content = note_content_html
            else:
                html_content = markdown.markdown(note_content, extensions=['extra'])

            soup = BeautifulSoup(html_content, 'html.parser')
            for element in soup.find_all(['p', 'h1', 'h2', 'h3', 'li']):
                text = element.get_text()
                if element.name == 'li':
                    elements.append(Paragraph(f"• {text}", body_style))
                else:
                    elements.append(Paragraph(text, body_style))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes
