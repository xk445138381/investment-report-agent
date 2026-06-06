from argparse import Namespace

from scripts import predeploy_check


def _security_headers() -> dict[str, str]:
    return {name.lower(): value for name, value in predeploy_check.REQUIRED_SECURITY_HEADERS.items()}


def test_security_header_check_accepts_required_headers() -> None:
    assert predeploy_check._check_security_headers("target", _security_headers()) == []


def test_security_header_check_reports_missing_headers() -> None:
    errors = predeploy_check._check_security_headers("target", {})

    assert "target missing security header X-Content-Type-Options=nosniff" in errors
    assert len(errors) == len(predeploy_check.REQUIRED_SECURITY_HEADERS)


def test_static_check_requires_api_url_for_production_target() -> None:
    errors = predeploy_check._check_static(
        Namespace(
            backend_url="https://api.investment-report-agent.com",
            frontend_url="https://app.investment-report-agent.com",
            api_url=None,
            production_target=True,
        )
    )

    assert "api-url is required for production targets" in errors


def test_static_check_accepts_matching_production_api_url() -> None:
    errors = predeploy_check._check_static(
        Namespace(
            backend_url="https://api.investment-report-agent.com",
            frontend_url="https://app.investment-report-agent.com",
            api_url="https://api.investment-report-agent.com/api/v1",
            production_target=True,
        )
    )

    assert errors == []


def test_static_check_rejects_example_placeholder_domains_for_production() -> None:
    errors = predeploy_check._check_static(
        Namespace(
            backend_url="https://api.example.com",
            frontend_url="https://app.example.org",
            api_url="https://api.example.com/api/v1",
            production_target=True,
        )
    )

    assert "backend-url must not use example placeholder domains for production targets" in errors
    assert "frontend-url must not use example placeholder domains for production targets" in errors


def test_static_check_requires_backend_and_frontend_origins_for_production() -> None:
    errors = predeploy_check._check_static(
        Namespace(
            backend_url="https://api.investment-report-agent.com/backend",
            frontend_url="https://app.investment-report-agent.com/app?x=1",
            api_url="https://api.investment-report-agent.com/api/v1",
            production_target=True,
        )
    )

    assert "backend-url must be an origin without path, query, or fragment" in errors
    assert "frontend-url must be an origin without path, query, or fragment" in errors


def test_network_check_requires_backend_and_frontend_security_headers(monkeypatch) -> None:
    def fake_request(
        url: str,
        timeout: float,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        if method == "OPTIONS":
            return 200, {"access-control-allow-origin": "https://app.example.com", "access-control-allow-methods": "POST"}, ""
        if url.endswith("/health"):
            return 200, {}, '{"status":"ok"}'
        if url.endswith("/ready"):
            return 200, {}, '{"status":"ok","checks":{"mongodb_required":true}}'
        if url.endswith("/metrics"):
            return 200, {}, "investment_report_http_requests_total 1"
        return 200, {}, "研报 Agent"

    monkeypatch.setattr(predeploy_check, "_request", fake_request)

    errors = predeploy_check._check_network(
        Namespace(
            backend_url="https://api.example.com",
            frontend_url="https://app.example.com",
            timeout=1,
            production_target=True,
        )
    )

    assert any("backend /health missing security header X-Content-Type-Options=nosniff" in error for error in errors)
    assert any("frontend missing security header X-Frame-Options=DENY" in error for error in errors)


def test_network_check_passes_with_required_security_headers(monkeypatch) -> None:
    security_headers = _security_headers()

    def fake_request(
        url: str,
        timeout: float,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        if method == "OPTIONS":
            return 200, {"access-control-allow-origin": "https://app.example.com", "access-control-allow-methods": "POST"}, ""
        if url.endswith("/health"):
            return 200, security_headers, '{"status":"ok"}'
        if url.endswith("/ready"):
            return 200, {}, '{"status":"ok","checks":{"mongodb_required":true}}'
        if url.endswith("/metrics"):
            return 200, {}, "investment_report_http_requests_total 1"
        return 200, security_headers, "新建分析"

    monkeypatch.setattr(predeploy_check, "_request", fake_request)

    errors = predeploy_check._check_network(
        Namespace(
            backend_url="https://api.example.com",
            frontend_url="https://app.example.com",
            timeout=1,
            production_target=True,
        )
    )

    assert errors == []


def test_network_check_requires_mongodb_readiness_in_production(monkeypatch) -> None:
    security_headers = _security_headers()

    def fake_request(
        url: str,
        timeout: float,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        if method == "OPTIONS":
            return 200, {"access-control-allow-origin": "https://app.example.com", "access-control-allow-methods": "POST"}, ""
        if url.endswith("/health"):
            return 200, security_headers, '{"status":"ok"}'
        if url.endswith("/ready"):
            return 200, {}, '{"status":"ok","checks":{"mongodb_required":false}}'
        if url.endswith("/metrics"):
            return 200, {}, "investment_report_http_requests_total 1"
        return 200, security_headers, "新建分析"

    monkeypatch.setattr(predeploy_check, "_request", fake_request)

    errors = predeploy_check._check_network(
        Namespace(
            backend_url="https://api.example.com",
            frontend_url="https://app.example.com",
            timeout=1,
            production_target=True,
        )
    )

    assert errors == ["/ready did not require MongoDB in production target"]


def test_cors_preflight_requires_frontend_origin(monkeypatch) -> None:
    def fake_request(
        url: str,
        timeout: float,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        return 200, {"access-control-allow-origin": "https://wrong.example.com", "access-control-allow-methods": "POST"}, ""

    monkeypatch.setattr(predeploy_check, "_request", fake_request)

    errors = predeploy_check._check_cors_preflight(
        "https://api.example.com",
        "https://app.example.com",
        1,
    )

    assert errors == ["CORS preflight did not allow frontend origin"]


def test_cors_preflight_requires_post(monkeypatch) -> None:
    def fake_request(
        url: str,
        timeout: float,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        return 200, {"access-control-allow-origin": "https://app.example.com", "access-control-allow-methods": "GET"}, ""

    monkeypatch.setattr(predeploy_check, "_request", fake_request)

    errors = predeploy_check._check_cors_preflight(
        "https://api.example.com",
        "https://app.example.com",
        1,
    )

    assert errors == ["CORS preflight did not allow POST"]
