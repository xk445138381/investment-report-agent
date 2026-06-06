"""Minimal production observability helpers."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import PlainTextResponse

_REQUEST_TOTAL: dict[tuple[str, str, str], int] = defaultdict(int)
_REQUEST_ERRORS: dict[tuple[str, str, str], int] = defaultdict(int)
_REQUEST_DURATION_SECONDS: dict[tuple[str, str], float] = defaultdict(float)


def _normalize_path(path: str) -> str:
    if path.startswith("/api/v1/report/"):
        parts = path.split("/")
        if len(parts) >= 5 and parts[4]:
            parts[4] = "{task_id}"
            return "/".join(parts)
    if path.startswith("/api/v1/portfolio/"):
        return "/api/v1/portfolio/{ticker}"
    if path.startswith("/upload/"):
        return "/upload/{file_id}/status"
    return path


async def metrics_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started = time.perf_counter()
    method = request.method
    path = _normalize_path(request.url.path)
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    except Exception:
        _REQUEST_ERRORS[(method, path, "500")] += 1
        raise
    finally:
        elapsed = time.perf_counter() - started
        _REQUEST_TOTAL[(method, path, status_code)] += 1
        _REQUEST_DURATION_SECONDS[(method, path)] += elapsed


def metrics_response() -> PlainTextResponse:
    lines = [
        "# HELP investment_report_http_requests_total Total HTTP requests.",
        "# TYPE investment_report_http_requests_total counter",
    ]
    for (method, path, status), count in sorted(_REQUEST_TOTAL.items()):
        lines.append(
            f'investment_report_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
        )

    lines.extend([
        "# HELP investment_report_http_request_errors_total Total HTTP request exceptions.",
        "# TYPE investment_report_http_request_errors_total counter",
    ])
    for (method, path, status), count in sorted(_REQUEST_ERRORS.items()):
        lines.append(
            f'investment_report_http_request_errors_total{{method="{method}",path="{path}",status="{status}"}} {count}'
        )

    lines.extend([
        "# HELP investment_report_http_request_duration_seconds_sum Total HTTP request duration.",
        "# TYPE investment_report_http_request_duration_seconds_sum counter",
    ])
    for (method, path), seconds in sorted(_REQUEST_DURATION_SECONDS.items()):
        lines.append(
            f'investment_report_http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {seconds:.6f}'
        )

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
