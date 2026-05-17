"""Template engine — JSON template → Jinja2 → HTML report.

Design: 田中一光式东方秩序 — warm paper, serif headings, generous white space.
"""

from jinja2 import Environment, BaseLoader, select_autoescape

REQUIRED_SECTION_FIELDS = {"id", "title", "agent", "max_words"}

BASE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{{ metadata.title }}</title>
<style>
  @page {
    size: {{ style.page.size|default('A4') }};
    margin: {{ style.page.margin_top_mm|default(25) }}mm {{ style.page.margin_right_mm|default(20) }}mm
            {{ style.page.margin_bottom_mm|default(20) }}mm {{ style.page.margin_left_mm|default(20) }}mm;
    @top-left { content: element(header-left); font-size: 8pt; color: #9E9288; }
    @top-right { content: element(header-right); font-size: 8pt; color: #9E9288; }
    @bottom-center { content: element(footer-center); font-size: 8pt; color: #9E9288; }
  }
  body {
    font-family: {{ style.fonts.body.family|default('SimSun') }}, "Noto Serif SC", serif;
    font-size: {{ style.fonts.body.size_pt|default(11) }}pt;
    line-height: 1.8;
    color: #2D2420;
    background: #FAF8F5;
  }
  h1 { font-family: {{ style.fonts.heading.family|default('SimHei') }}, "Noto Serif SC", serif;
       font-size: {{ style.fonts.heading.size_pt|default(16) }}pt; font-weight: 700;
       color: #2D2420; margin-top: 32pt; }
  h2 { font-family: {{ style.fonts.heading.family|default('SimHei') }}, serif;
       font-size: 13pt; font-weight: 600; color: #2D2420; margin-top: 24pt; }
  .cover { page-break-after: always; text-align: center; padding-top: 30%; }
  .cover h1 { font-size: 28pt; margin-bottom: 12pt; }
  .cover .subtitle { font-size: 14pt; color: #C04A1A; font-family: "Noto Serif SC", serif; }
  .cover .meta { margin-top: 48pt; font-size: 10pt; color: #9E9288; }
  .toc { page-break-after: always; }
  .toc-item { display: flex; justify-content: space-between; padding: 4pt 0;
              border-bottom: 1pt dotted #D4C5B9; }
  .section { page-break-after: always; }
  .data-headline { font-family: "Playfair Display", "Noto Serif SC", serif;
                   font-size: 24pt; font-weight: 700; color: #C04A1A; }
  .chart { margin: 16pt 0; text-align: center; }
  .chart img { max-width: 100%; height: auto; }
  .chart-caption { font-size: 9pt; color: #9E9288; margin-top: 4pt; }
  .disclaimer { font-size: 8pt; color: #9E9288; }
  .header-left { position: running(header-left); }
  .header-right { position: running(header-right); }
  .footer-center { position: running(footer-center); text-align: center; }
</style>
</head>
<body>

<div class="header-left">{{ style.header.left|replace('{{report_title}}', metadata.title) }}</div>
<div class="header-right">{{ style.header.right|replace('{{page_number}}', 'p.') }}</div>
<div class="footer-center">{{ style.footer.center }}</div>

<!-- Cover -->
<div class="cover">
  <h1>{{ metadata.title }}</h1>
  {% if metadata.subtitle %}
  <p class="subtitle">{{ metadata.subtitle }}</p>
  {% endif %}
  <p class="meta">{{ metadata.report_date }} · AI 辅助生成</p>
</div>

<!-- TOC -->
<div class="toc">
  <h1>目录</h1>
  {% for section in template.sections %}
  <div class="toc-item">
    <span>{{ loop.index }}. {{ section.title }}</span>
  </div>
  {% endfor %}
</div>

<!-- Sections -->
{% for section in template.sections %}
<div class="section">
  <h1>{{ section.title }}</h1>
  {% if sections.get(section.id) %}
  <p>{{ sections[section.id].content }}</p>
  {% endif %}

  {% for chart in charts %}
  {% if chart.position == section.id %}
  <div class="chart">
    <img src="data:image/png;base64,{{ chart.png_base64 }}" alt="{{ chart.title }}">
    <p class="chart-caption">{{ chart.caption }}</p>
  </div>
  {% endif %}
  {% endfor %}
</div>
{% endfor %}

<div class="disclaimer" style="margin-top: 48pt; border-top: 1pt solid #D4C5B9; padding-top: 12pt;">
  <p>{{ metadata.disclaimer|default('本报告由 AI 辅助生成，仅供参考，不构成投资建议。') }}</p>
</div>

</body>
</html>"""

_jinja_env = Environment(loader=BaseLoader(), autoescape=select_autoescape(default=True, default_for_string=True))


def validate_template(template: dict) -> None:
    """Validate a report template dict.

    Raises ValueError on any validation failure.
    """
    sections = template.get("sections", [])
    if not sections:
        raise ValueError("Template must have at least one section")

    seen_ids = set()
    for i, section in enumerate(sections):
        # Check required fields
        missing = REQUIRED_SECTION_FIELDS - set(section.keys())
        if missing:
            raise ValueError(
                f"Section {i} ('{section.get('id', 'unknown')}') "
                f"missing required field(s): {missing}"
            )
        # Check unique IDs
        if section["id"] in seen_ids:
            raise ValueError(f"Duplicate section id: {section['id']}")
        seen_ids.add(section["id"])


def render_report(
    template: dict,
    sections: dict,
    charts: list[dict],
    metadata: dict,
) -> str:
    """Render a complete report as HTML from template + data.

    Args:
        template: Validated template dict (from JSON).
        sections: {section_id: {title, content, word_count}}.
        charts: [ChartOutput dicts with png_base64, position, etc.].
        metadata: {title, subtitle, report_date, disclaimer?}.

    Returns:
        Complete HTML string ready for PDF conversion or web display.
    """
    validate_template(template)

    tmpl = _jinja_env.from_string(BASE_HTML_TEMPLATE)
    return tmpl.render(
        template=template,
        sections=sections,
        charts=charts,
        metadata=metadata,
        style=template.get("style", {}),
    )
