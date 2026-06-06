"""Validate deployment targets before or after release.

Static mode validates URL/env configuration without network access.
Network mode probes the deployed backend and frontend.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
PLACEHOLDER_DOMAINS = {"example.com", "example.org", "example.net"}
REQUIRED_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def _parse_url(name: str, value: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute http(s) URL: {value}")
    return parsed


def _is_local(parsed: urllib.parse.ParseResult) -> bool:
    hostname = (parsed.hostname or "").lower()
    return hostname in LOCAL_HOSTS


def _is_placeholder_domain(parsed: urllib.parse.ParseResult) -> bool:
    hostname = (parsed.hostname or "").lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in PLACEHOLDER_DOMAINS)


def _has_path_query_or_fragment(parsed: urllib.parse.ParseResult) -> bool:
    return parsed.path not in {"", "/"} or bool(parsed.query) or bool(parsed.fragment)


def _join(base: str, path: str) -> str:
    return urllib.parse.urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def _request(
    url: str,
    timeout: float,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], str]:
    request_headers = {"User-Agent": "investment-report-agent-predeploy"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            headers = {name.lower(): value for name, value in response.headers.items()}
            body = response.read().decode("utf-8", errors="replace")
            return response.status, headers, body
    except urllib.error.HTTPError as exc:
        headers = {name.lower(): value for name, value in exc.headers.items()}
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, headers, body


def _check_security_headers(label: str, headers: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for name, expected in REQUIRED_SECURITY_HEADERS.items():
        actual = headers.get(name.lower())
        if actual != expected:
            errors.append(f"{label} missing security header {name}={expected}")
    return errors


def _check_cors_preflight(backend_url: str, frontend_url: str, timeout: float) -> list[str]:
    errors: list[str] = []
    status, headers, body = _request(
        _join(backend_url, "/api/v1/report/generate"),
        timeout,
        method="OPTIONS",
        headers={
            "Origin": frontend_url.rstrip("/"),
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    if status not in {200, 204}:
        errors.append(f"CORS preflight returned HTTP {status}: {body[:200]}")
        return errors

    allow_origin = headers.get("access-control-allow-origin")
    if allow_origin != frontend_url.rstrip("/"):
        errors.append("CORS preflight did not allow frontend origin")
    allow_methods = headers.get("access-control-allow-methods", "")
    if "POST" not in allow_methods and "*" not in allow_methods:
        errors.append("CORS preflight did not allow POST")
    return errors


def _check_static(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    backend = _parse_url("backend-url", args.backend_url)
    frontend = _parse_url("frontend-url", args.frontend_url)

    if args.api_url:
        api = _parse_url("api-url", args.api_url)
        if not api.path.rstrip("/").endswith("/api/v1"):
            errors.append("api-url must end with /api/v1")
        if api.scheme != backend.scheme or api.netloc != backend.netloc:
            errors.append("api-url must use the same origin as backend-url")

    if args.production_target:
        if not args.api_url:
            errors.append("api-url is required for production targets")
        for name, parsed in {"backend-url": backend, "frontend-url": frontend}.items():
            if parsed.scheme != "https":
                errors.append(f"{name} must use https for production targets")
            if _is_local(parsed):
                errors.append(f"{name} must not point to localhost for production targets")
            if _is_placeholder_domain(parsed):
                errors.append(f"{name} must not use example placeholder domains for production targets")
            if _has_path_query_or_fragment(parsed):
                errors.append(f"{name} must be an origin without path, query, or fragment")
        if backend.netloc == frontend.netloc:
            errors.append("backend-url and frontend-url should be separate origins in production")

    return errors


def _check_network(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    timeout = args.timeout

    health_status, health_headers, health_body = _request(_join(args.backend_url, "/health"), timeout)
    if health_status != 200:
        errors.append(f"/health returned HTTP {health_status}")
    else:
        errors.extend(_check_security_headers("backend /health", health_headers))
        try:
            if json.loads(health_body).get("status") != "ok":
                errors.append("/health did not return status=ok")
        except json.JSONDecodeError:
            errors.append("/health did not return JSON")

    ready_status, _, ready_body = _request(_join(args.backend_url, "/ready"), timeout)
    if ready_status != 200:
        errors.append(f"/ready returned HTTP {ready_status}: {ready_body[:200]}")
    else:
        try:
            ready_payload = json.loads(ready_body)
            if ready_payload.get("status") != "ok":
                errors.append("/ready did not return status=ok")
            if args.production_target and ready_payload.get("checks", {}).get("mongodb_required") is not True:
                errors.append("/ready did not require MongoDB in production target")
        except json.JSONDecodeError:
            errors.append("/ready did not return JSON")

    metrics_status, _, metrics_body = _request(_join(args.backend_url, "/metrics"), timeout)
    if metrics_status != 200:
        errors.append(f"/metrics returned HTTP {metrics_status}")
    elif "investment_report_http_requests_total" not in metrics_body:
        errors.append("/metrics did not expose investment_report_http_requests_total")

    errors.extend(_check_cors_preflight(args.backend_url, args.frontend_url, timeout))

    frontend_status, frontend_headers, frontend_body = _request(args.frontend_url, timeout)
    if frontend_status != 200:
        errors.append(f"frontend returned HTTP {frontend_status}")
    else:
        errors.extend(_check_security_headers("frontend", frontend_headers))
        if "新建分析" not in frontend_body and "研报 Agent" not in frontend_body:
            errors.append("frontend response did not contain expected app text")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate deployment target readiness.")
    parser.add_argument("--backend-url", required=True, help="Backend origin, for example https://api.example.com")
    parser.add_argument("--frontend-url", required=True, help="Frontend origin, for example https://app.example.com")
    parser.add_argument("--api-url", help="Public frontend API URL, expected to end with /api/v1")
    parser.add_argument("--production-target", action="store_true", help="Reject localhost and non-HTTPS URLs")
    parser.add_argument("--static", action="store_true", help="Only validate URL/config shape, skip network probes")
    parser.add_argument("--timeout", type=float, default=5.0, help="Network request timeout in seconds")
    args = parser.parse_args(argv)

    errors = _check_static(args)
    if not args.static:
        errors.extend(_check_network(args))

    if errors:
        print("predeploy_check: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("predeploy_check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
