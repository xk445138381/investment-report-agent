from api.observability import _REQUEST_TOTAL, _normalize_path, metrics_response


def test_metrics_normalizes_dynamic_paths():
    assert _normalize_path("/api/v1/report/task-123/status") == "/api/v1/report/{task_id}/status"
    assert _normalize_path("/api/v1/report/task-123") == "/api/v1/report/{task_id}"
    assert _normalize_path("/api/v1/portfolio/600519.SH") == "/api/v1/portfolio/{ticker}"


def test_metrics_response_exposes_prometheus_text():
    _REQUEST_TOTAL[("GET", "/health", "200")] += 1

    body = metrics_response().body.decode("utf-8")

    assert "# TYPE investment_report_http_requests_total counter" in body
    assert 'investment_report_http_requests_total{method="GET",path="/health",status="200"}' in body
