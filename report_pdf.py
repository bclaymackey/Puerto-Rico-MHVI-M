import re
from datetime import datetime
from html import escape
from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


_BRAND = HexColor("#4b0082")
_BODY = HexColor("#222222")
_MUTED = HexColor("#666666")


def _build_styles():
    base = ParagraphStyle(
        name="base",
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=_BODY,
        alignment=TA_LEFT,
    )
    return {
        "title": ParagraphStyle(
            "title", parent=base, fontName="Helvetica-Bold",
            fontSize=18, leading=22, textColor=_BRAND, spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base, fontSize=9, leading=11,
            textColor=_MUTED, spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base, fontName="Helvetica-Bold",
            fontSize=13, leading=16, textColor=_BRAND,
            spaceBefore=10, spaceAfter=4,
        ),
        "body": base,
        "bullet": ParagraphStyle(
            "bullet", parent=base, leftIndent=14, bulletIndent=4,
            spaceAfter=2,
        ),
    }


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _inline_format(text: str) -> str:
    safe = escape(text)
    return _BOLD_RE.sub(r"<b>\1</b>", safe)


def _render_markdown(text: str, styles) -> list:
    """Tiny Markdown subset: ##/# headings, -/* bullets, blank lines, paragraphs."""
    story = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            story.append(Spacer(1, 4))
            continue
        stripped = line.lstrip()
        if stripped.startswith("## "):
            story.append(Paragraph(_inline_format(stripped[3:].strip()), styles["h2"]))
        elif stripped.startswith("# "):
            story.append(Paragraph(_inline_format(stripped[2:].strip()), styles["h2"]))
        elif stripped.startswith("### "):
            story.append(Paragraph(_inline_format(stripped[4:].strip()), styles["h2"]))
        elif stripped.startswith(("- ", "* ")):
            content = stripped[2:].strip()
            story.append(
                Paragraph(f"• {_inline_format(content)}", styles["bullet"])
            )
        else:
            story.append(Paragraph(_inline_format(line), styles["body"]))
    return story


def _draw_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(_MUTED)
    canvas.drawRightString(
        doc.pagesize[0] - 1.5 * cm,
        1.0 * cm,
        f"Page {doc.page}",
    )
    canvas.restoreState()


def build_report_pdf(
    report_text: str,
    municipality: str,
    language: str = "en",
) -> bytes:
    """Render the markdown report text into PDF bytes."""
    is_es = language == "es"
    title_text = (
        f"Informe de Vulnerabilidad Municipal — {municipality}"
        if is_es else
        f"Municipality Vulnerability Report — {municipality}"
    )
    generated_label = "Generado" if is_es else "Generated"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=title_text,
    )

    styles = _build_styles()
    story = [
        Paragraph(escape(title_text), styles["title"]),
        Paragraph(f"{generated_label}: {timestamp}", styles["meta"]),
    ]
    story.extend(_render_markdown(report_text or "", styles))

    doc.build(
        story,
        onFirstPage=_draw_page_number,
        onLaterPages=_draw_page_number,
    )
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


if __name__ == "__main__":
    sample = """## Municipality Overview
This is a vulnerability report for **Arecibo**.

## Overall Vulnerability Summary
Overall score: 22.73. Higher scores indicate greater vulnerability.

## Category Breakdown
- **Education**: 7.05
- **Housing**: 3.21
- **Transportation**: 87.82

## Highest Vulnerability Areas
- Transportation
- Social & Community

## Interpretation Notes
Scores are relative.

## Conclusion
End of test report."""
    out = build_report_pdf(sample, "Arecibo", "en")
    with open("/tmp/test_report.pdf", "wb") as f:
        f.write(out)
    print(f"Wrote {len(out)} bytes to /tmp/test_report.pdf")
