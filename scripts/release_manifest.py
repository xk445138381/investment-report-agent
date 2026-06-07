"""Generate a release manifest for deployment handoff."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _git_value(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def build_manifest(version: str, backend_url: str | None, frontend_url: str | None) -> dict:
    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git": {
            "commit": _git_value(["rev-parse", "HEAD"]),
            "branch": _git_value(["branch", "--show-current"]),
            "dirty": bool(_git_value(["status", "--short"])),
        },
        "artifacts": {
            "backend_image": "Dockerfile.backend",
            "frontend_image": "Dockerfile.frontend",
            "compose_file": "docker-compose.prod.yml",
            "ci_workflow": ".github/workflows/ci.yml",
            "deploy_verify_workflow": ".github/workflows/deploy-verify.yml",
            "compose_env_template": "deploy/compose.env.example",
            "backend_env_template": "deploy/backend.env.example",
        },
        "required_checks": [
            "python scripts/launch_check.py",
            "python -m pytest tests/ -v",
            "GitHub Actions launch-check",
            "GitHub Actions docker-build",
            "GitHub Actions Deploy Verify",
        ],
        "launch_check_coverage": [
            "backend unit tests",
            "backend production safeguards",
            "deployment config checks",
            "predeploy unit tests",
            "predeploy static checks",
            "release manifest generation",
            "repository safety check",
            "frontend lint",
            "frontend production build",
            "frontend smoke e2e",
        ],
        "runtime_endpoints": {
            "backend_health": f"{backend_url.rstrip('/')}/health" if backend_url else None,
            "backend_ready": f"{backend_url.rstrip('/')}/ready" if backend_url else None,
            "backend_metrics": f"{backend_url.rstrip('/')}/metrics" if backend_url else None,
            "frontend": frontend_url,
        },
        "post_deploy_assertions": [
            "backend /health returns status=ok",
            "production predeploy check requires api-url ending with /api/v1",
            "production backend-url and frontend-url are origins without path, query, or fragment",
            "production backend-url and frontend-url reject example placeholder domains",
            "backend /ready returns status=ok",
            "backend /ready reports checks.mongodb_required=true",
            "backend /metrics exposes investment_report_http_requests_total",
            "backend /health includes required security headers",
            "backend CORS preflight allows the frontend origin to call /api/v1/report/generate",
            "frontend includes required security headers",
            "frontend renders the application shell",
        ],
        "post_deploy_check": (
            "python scripts/predeploy_check.py --production-target "
            "--backend-url <backend-origin> --frontend-url <frontend-origin> "
            "--api-url <backend-origin>/api/v1"
        ),
        "rollback_reference": "docs/deployment-runbook-2026-06-05.md#rollback",
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release manifest JSON.")
    parser.add_argument("--version", default="deployable-candidate", help="Release version or tag.")
    parser.add_argument("--backend-url", help="Target backend origin.")
    parser.add_argument("--frontend-url", help="Target frontend origin.")
    parser.add_argument("--output", default="docs/release-manifest-latest.json")
    args = parser.parse_args()

    manifest = build_manifest(args.version, args.backend_url, args.frontend_url)
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"release_manifest: wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
