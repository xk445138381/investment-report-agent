"""PDF renderer — HTML → WeasyPrint → PDF bytes."""

from .template_engine import render_report


def render_pdf(
    template: dict,
    sections: dict,
    charts: list[dict],
    metadata: dict,
) -> bytes:
    """Render a complete report as PDF bytes.

    Uses WeasyPrint for HTML → PDF conversion with CSS print styles.
    """
    from weasyprint import HTML

    html_str = render_report(template, sections, charts, metadata)
    doc = HTML(string=html_str, base_url=".")
    return doc.write_pdf()
