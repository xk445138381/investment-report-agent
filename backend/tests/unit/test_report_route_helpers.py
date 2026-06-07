from api.routes.report import _normalize_report_result


def test_normalize_report_result_adds_legacy_data_quality_and_strips_object_repr():
    result = {
        "_prices": ["<api.routes.report.Obj object at 0x123>"],
        "section_writer": {"result": {"sections": {}}},
    }

    normalized = _normalize_report_result(result)

    assert "_prices" not in normalized
    assert normalized["data_quality"]["result"]["status"] == "empty"
    assert "prices" in normalized["data_quality"]["result"]["missing"]

