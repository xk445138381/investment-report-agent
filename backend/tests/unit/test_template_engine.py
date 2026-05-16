"""T19: Template engine tests (TDD)."""

import json
import pytest
from pathlib import Path


@pytest.fixture
def sample_template_dict():
    return {
        "template_id": "test_deep",
        "name": "Test Deep Dive",
        "version": "1.0",
        "sections": [
            {"id": "exec_summary", "title": "投资摘要", "agent": "section_writer", "max_words": 500},
            {"id": "company_overview", "title": "公司概况", "agent": "section_writer", "max_words": 800},
            {"id": "valuation", "title": "估值分析", "agent": "section_writer", "max_words": 1200,
             "charts": ["valuation_waterfall"]},
        ],
        "style": {
            "page": {"size": "A4", "margin_top_mm": 25},
            "fonts": {"heading": {"family": "SimHei", "size_pt": 16}, "body": {"family": "SimSun", "size_pt": 11}},
            "header": {"left": "{{report_title}}", "right": "{{page_number}}"},
            "footer": {"center": "AI 辅助生成 · 仅供参考"},
        }
    }


class TestTemplateParsing:
    def test_section_ids_are_unique(self):
        """Given: template with duplicate section IDs
           When: validate_template
           Then: ValidationError"""
        from export.template_engine import validate_template

        template = {
            "template_id": "dup", "name": "Dup", "version": "1.0",
            "sections": [
                {"id": "same", "title": "A", "agent": "w", "max_words": 100},
                {"id": "same", "title": "B", "agent": "w", "max_words": 100},
            ],
        }
        with pytest.raises(ValueError, match="Duplicate section id"):
            validate_template(template)

    def test_template_missing_sections_rejected(self):
        """Given: template JSON without sections
           When: validate_template
           Then: ValidationError"""
        from export.template_engine import validate_template

        template = {"template_id": "bad", "name": "Bad", "version": "1.0", "sections": []}
        with pytest.raises(ValueError, match="at least one section"):
            validate_template(template)

    def test_each_section_has_required_fields(self):
        """Given: section missing 'agent' field
           When: validate_template
           Then: ValidationError"""
        from export.template_engine import validate_template

        template = {
            "template_id": "bad", "name": "Bad", "version": "1.0",
            "sections": [{"id": "s1", "title": "T", "max_words": 100}],
        }
        with pytest.raises(ValueError, match="missing required field"):
            validate_template(template)


class TestTemplateRendering:
    def test_variable_interpolation(self, sample_template_dict):
        """Given: template with {{report_title}} variable
           When: render with context
           Then: title is interpolated"""
        from export.template_engine import render_report

        sections = {
            "exec_summary": {"title": "投资摘要", "content": "核心观点...", "word_count": 100},
            "company_overview": {"title": "公司概况", "content": "公司介绍...", "word_count": 200},
            "valuation": {"title": "估值分析", "content": "估值结果...", "word_count": 300},
        }
        html = render_report(
            template=sample_template_dict,
            sections=sections,
            charts=[],
            metadata={"title": "测试报告", "subtitle": "测试副标题", "report_date": "2026-05-17"},
        )
        assert "测试报告" in html
        assert "核心观点" in html
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_chart_images_embedded(self, sample_template_dict):
        """Given: a chart with base64 PNG data
           When: render report
           Then: img tag with data URI is present"""
        from export.template_engine import render_report

        sections = {"exec_summary": {"title": "S", "content": "C", "word_count": 100},
                     "company_overview": {"title": "S", "content": "C", "word_count": 100},
                     "valuation": {"title": "S", "content": "C", "word_count": 100}}

        charts = [{"chart_id": "chart1", "title": "Price Chart", "caption": "Price trend",
                    "png_base64": "iVBORw0KGgo_test", "position": "valuation"}]

        html = render_report(sample_template_dict, sections, charts,
                             metadata={"title": "T", "subtitle": "", "report_date": "2026-01-01"})
        assert "iVBORw0KGgo_test" in html
        assert 'data:image/png;base64' in html

    def test_sections_order_preserved(self, sample_template_dict):
        """Given: template with section order A, B, C
           When: render
           Then: sections appear in template-defined order"""
        from export.template_engine import render_report

        sections = {
            "exec_summary": {"title": "Exec Summary", "content": "Content A", "word_count": 10},
            "company_overview": {"title": "Company", "content": "Content B", "word_count": 10},
            "valuation": {"title": "Valuation", "content": "Content C", "word_count": 10},
        }
        html = render_report(sample_template_dict, sections, [],
                             metadata={"title": "T", "subtitle": "", "report_date": "2026-01-01"})
        # Template section titles are in order: exec_summary, company_overview, valuation
        a_idx = html.index("Content A")
        b_idx = html.index("Content B")
        c_idx = html.index("Content C")
        assert a_idx < b_idx < c_idx


class TestPDFRenderer:
    @pytest.mark.skip(reason="WeasyPrint requires GTK3 runtime on Windows")
    def test_pdf_generated_with_valid_content(self, sample_template_dict):
        """Given: valid report HTML
           When: render pdf
           Then: returns bytes with PDF header"""
        from export.pdf_renderer import render_pdf

        sections = {"exec_summary": {"title": "S", "content": "Test content", "word_count": 100},
                     "company_overview": {"title": "S", "content": "Test", "word_count": 100},
                     "valuation": {"title": "S", "content": "Test", "word_count": 100}}

        pdf_bytes = render_pdf(
            template=sample_template_dict,
            sections=sections,
            charts=[],
            metadata={"title": "Test Report", "subtitle": "", "report_date": "2026-05-17"},
        )
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_disclaimer_in_output(self, sample_template_dict):
        """Given: template with footer disclaimer
           When: render html
           Then: disclaimer text is present"""
        from export.template_engine import render_report

        sections = {"exec_summary": {"title": "S", "content": "C", "word_count": 100},
                     "company_overview": {"title": "S", "content": "C", "word_count": 100},
                     "valuation": {"title": "S", "content": "C", "word_count": 100}}

        html = render_report(sample_template_dict, sections, [],
                             metadata={"title": "T", "subtitle": "", "report_date": "2026-01-01"})
        assert "仅供参考" in html
