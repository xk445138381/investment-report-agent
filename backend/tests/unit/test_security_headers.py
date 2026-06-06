from starlette.responses import Response

from api.security_headers import apply_security_headers


def test_apply_security_headers_adds_defaults():
    response = apply_security_headers(Response())

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "camera=()" in response.headers["Permissions-Policy"]


def test_apply_security_headers_preserves_existing_header():
    response = Response(headers={"X-Frame-Options": "SAMEORIGIN"})

    apply_security_headers(response)

    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
