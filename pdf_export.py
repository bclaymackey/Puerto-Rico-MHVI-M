from datetime import datetime
from html import escape
from io import BytesIO

from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_USER_BG = HexColor("#4b0082")
_USER_FG = white
_AI_BG = HexColor("#f0f0f0")
_AI_FG = HexColor("#333333")
_BRAND = HexColor("#4b0082")
_BODY = HexColor("#222222")
_MUTED = HexColor("#666666")

_BUBBLE_MAX_WIDTH_RATIO = 0.75
_BUBBLE_CORNER_RADIUS = 8


def _build_styles():
    base = ParagraphStyle(
        name="base",
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=_BODY,
    )
    return {
        "title": ParagraphStyle(
            "title", parent=base, fontName="Helvetica-Bold",
            fontSize=18, leading=22, textColor=_BRAND, spaceAfter=2,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base, fontSize=9, leading=11,
            textColor=_MUTED, spaceAfter=14,
        ),
        "user_text": ParagraphStyle(
            "user_text", parent=base, textColor=_USER_FG, alignment=TA_LEFT,
        ),
        "ai_text": ParagraphStyle(
            "ai_text", parent=base, textColor=_AI_FG, alignment=TA_LEFT,
        ),
    }


def _bubble_flowable(text, role, frame_width, styles):
    """A chat bubble: a single-cell rounded Table aligned left or right."""
    is_user = role == "user"
    para_style = styles["user_text"] if is_user else styles["ai_text"]
    bg = _USER_BG if is_user else _AI_BG
    h_align = "RIGHT" if is_user else "LEFT"

    safe = escape(text or "").replace("\n", "<br/>")
    if not safe:
        safe = "&nbsp;"
    para = Paragraph(safe, para_style)

    table = Table(
        [[para]],
        colWidths=[frame_width * _BUBBLE_MAX_WIDTH_RATIO],
        hAlign=h_align,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROUNDEDCORNERS", [_BUBBLE_CORNER_RADIUS] * 4),
    ]))
    return table


def build_pdf_bytes(messages, language="en"):
    """Render the structured chat history as PDF bytes."""
    is_es = language == "es"
    title_text = "Transcripción del Chat" if is_es else "Chat Transcript"
    generated_label = "Generado" if is_es else "Generated"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=title_text,
    )

    styles = _build_styles()
    frame_width = doc.width

    story = [
        Paragraph(title_text, styles["title"]),
        Paragraph(f"{generated_label}: {timestamp}", styles["meta"]),
    ]

    for msg in (messages or []):
        role = "user" if msg.get("role") == "user" else "assistant"
        story.append(_bubble_flowable(msg.get("text", ""), role, frame_width, styles))
        story.append(Spacer(1, 6))

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _draw_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(_MUTED)
    page_label = f"Page {doc.page}"
    canvas.drawRightString(
        doc.pagesize[0] - 1.5 * cm,
        1.0 * cm,
        page_label,
    )
    canvas.restoreState()
