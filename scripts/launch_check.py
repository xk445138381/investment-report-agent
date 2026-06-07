"""Run launch-readiness checks for the investment report agent."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
NPM = "npm.cmd" if os.name == "nt" else "npm"


def run_step(name: str, cwd: Path, command: list[str]) -> float:
    print(f"\n==> {name}")
    print("    " + " ".join(command))
    start = time.time()
    completed = subprocess.run(command, cwd=cwd)
    elapsed = round(time.time() - start, 1)
    if completed.returncode != 0:
        raise SystemExit(f"{name} failed with exit code {completed.returncode}")
    return elapsed


def run_backend_production_checks() -> float:
    name = "Backend production safeguards"
    print(f"\n==> {name}")
    command = [
        sys.executable,
        "-c",
        (
            "from api.main import app, _readiness_status; "
            "routes=[getattr(r,'path','') for r in app.routes]; "
            "assert '/api/v1/debug/env' not in routes; "
            "assert '/api/v1/debug/llm' not in routes; "
            "status=_readiness_status(); "
            "assert status['status']=='ok', status; "
            "print('production_safeguards_ok')"
        ),
    ]
    print("    " + " ".join(command))
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": "src",
        "ENVIRONMENT": "production",
        "SECRET_KEY": "launch-check-secret-not-a-placeholder",
        "DEEPSEEK_API_KEY": "launch-check-deepseek-key",
        "QVERIS_API_KEY": "launch-check-qveris-key",
        "ENABLE_DEBUG_ROUTES": "false",
        "ENABLE_RUNTIME_CONFIG_WRITES": "false",
    })
    start = time.time()
    completed = subprocess.run(command, cwd=ROOT / "backend", env=env)
    elapsed = round(time.time() - start, 1)
    if completed.returncode != 0:
        raise SystemExit(f"{name} failed with exit code {completed.returncode}")
    return elapsed


def run_deployment_config_checks() -> float:
    name = "Deployment config checks"
    print(f"\n==> {name}")
    start = time.time()
    compose_path = ROOT / "docker-compose.prod.yml"
    workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
    deploy_verify_path = ROOT / ".github" / "workflows" / "deploy-verify.yml"
    predeploy_check_path = ROOT / "scripts" / "predeploy_check.py"
    frontend_config_path = ROOT / "frontend" / "next.config.ts"
    backend_dockerfile_path = ROOT / "Dockerfile.backend"
    frontend_dockerfile_path = ROOT / "Dockerfile.frontend"
    compose_env_template_path = ROOT / "deploy" / "compose.env.example"
    backend_env_template_path = ROOT / "deploy" / "backend.env.example"
    release_manifest_script_path = ROOT / "scripts" / "release_manifest.py"
    compose_text = compose_path.read_text(encoding="utf-8")
    compose = yaml.safe_load(compose_text)
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    deploy_verify = yaml.safe_load(deploy_verify_path.read_text(encoding="utf-8"))
    predeploy_check = predeploy_check_path.read_text(encoding="utf-8")
    frontend_config = frontend_config_path.read_text(encoding="utf-8")
    backend_dockerfile = backend_dockerfile_path.read_text(encoding="utf-8")
    frontend_dockerfile = frontend_dockerfile_path.read_text(encoding="utf-8")
    compose_env_template = compose_env_template_path.read_text(encoding="utf-8")
    backend_env_template = backend_env_template_path.read_text(encoding="utf-8")
    release_manifest_script = release_manifest_script_path.read_text(encoding="utf-8")
    frontend_source_files = [
        path for path in (ROOT / "frontend").rglob("*")
        if path.suffix in {".ts", ".tsx"} and "node_modules" not in path.parts and ".next" not in path.parts
    ]

    services = compose.get("services", {})
    required_services = {"backend", "frontend", "mongo"}
    missing_services = required_services - set(services)
    if missing_services:
        raise SystemExit(f"{name} failed: missing services {sorted(missing_services)}")

    for service_name in sorted(required_services):
        if "healthcheck" not in services[service_name]:
            raise SystemExit(f"{name} failed: {service_name} has no healthcheck")

    backend_env = services["backend"].get("environment", {})
    if backend_env.get("ENVIRONMENT") != "production":
        raise SystemExit(f"{name} failed: backend ENVIRONMENT is not production")
    if str(backend_env.get("ENABLE_DEBUG_ROUTES", "")).lower() != "false":
        raise SystemExit(f"{name} failed: debug routes are not disabled by default")
    if str(backend_env.get("ENABLE_RUNTIME_CONFIG_WRITES", "")).lower() != "false":
        raise SystemExit(f"{name} failed: runtime config writes are not disabled by default")
    if str(backend_env.get("REQUIRE_MONGODB", "")).lower() != "true":
        raise SystemExit(f"{name} failed: MongoDB is not required by backend readiness in compose")
    if "FRONTEND_ORIGINS: ${FRONTEND_ORIGINS:?" not in compose_text:
        raise SystemExit(f"{name} failed: production compose does not require FRONTEND_ORIGINS")
    if "NEXT_PUBLIC_API_URL: ${NEXT_PUBLIC_API_URL:?" not in compose_text:
        raise SystemExit(f"{name} failed: production compose does not require NEXT_PUBLIC_API_URL")
    if ":-http://localhost" in compose_text or ":-http://127.0.0.1" in compose_text:
        raise SystemExit(f"{name} failed: production compose still has localhost URL defaults")

    frontend_depends_on = services["frontend"].get("depends_on", {})
    if frontend_depends_on.get("backend", {}).get("condition") != "service_healthy":
        raise SystemExit(f"{name} failed: frontend does not wait for backend health")

    jobs = workflow.get("jobs", {})
    if "launch-check" not in jobs:
        raise SystemExit(f"{name} failed: CI has no launch-check job")
    if "docker-build" not in jobs:
        raise SystemExit(f"{name} failed: CI has no docker-build job")
    launch_steps = jobs["launch-check"].get("steps", [])
    launch_step_names = {step.get("name") for step in launch_steps if isinstance(step, dict)}
    if "Upload release manifest" not in launch_step_names:
        raise SystemExit(f"{name} failed: CI does not upload the release manifest")
    docker_steps = jobs["docker-build"].get("steps", [])
    docker_step_names = {step.get("name") for step in docker_steps if isinstance(step, dict)}
    if {"Build backend image", "Build frontend image"} - docker_step_names:
        raise SystemExit(f"{name} failed: CI docker-build job does not build both images")

    deploy_jobs = deploy_verify.get("jobs", {})
    if "deploy-verify" not in deploy_jobs:
        raise SystemExit(f"{name} failed: deploy-verify workflow has no deploy-verify job")
    verify_steps = deploy_jobs["deploy-verify"].get("steps", [])
    verify_step_names = {step.get("name") for step in verify_steps if isinstance(step, dict)}
    if "Verify deployed target" not in verify_step_names:
        raise SystemExit(f"{name} failed: deploy-verify workflow does not run target verification")

    for required_header in [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    ]:
        if required_header not in frontend_config:
            raise SystemExit(f"{name} failed: frontend security header missing: {required_header}")
        if required_header not in predeploy_check:
            raise SystemExit(f"{name} failed: predeploy check does not verify {required_header}")

    for path in frontend_source_files:
        if "next/font/google" in path.read_text(encoding="utf-8"):
            relative = path.relative_to(ROOT)
            raise SystemExit(f"{name} failed: frontend build depends on Google Fonts: {relative}")

    if "USER app" not in backend_dockerfile:
        raise SystemExit(f"{name} failed: backend image does not run as a non-root app user")
    if "USER node" not in frontend_dockerfile:
        raise SystemExit(f"{name} failed: frontend image does not run as the non-root node user")
    if "ARG NEXT_PUBLIC_API_URL=http://localhost" in frontend_dockerfile:
        raise SystemExit(f"{name} failed: frontend image build has a localhost API URL default")
    if 'test -n "$NEXT_PUBLIC_API_URL"' not in frontend_dockerfile:
        raise SystemExit(f"{name} failed: frontend image build does not require NEXT_PUBLIC_API_URL")

    for required_var in ["FRONTEND_ORIGINS", "NEXT_PUBLIC_API_URL", "MONGODB_DATABASE"]:
        if f"{required_var}=" not in compose_env_template:
            raise SystemExit(f"{name} failed: compose env template missing {required_var}")
    for required_var in [
        "SECRET_KEY",
        "DEEPSEEK_API_KEY",
        "QVERIS_API_KEY",
        "ENVIRONMENT=production",
        "ENABLE_DEBUG_ROUTES=false",
        "ENABLE_RUNTIME_CONFIG_WRITES=false",
        "REQUIRE_MONGODB=true",
    ]:
        if required_var not in backend_env_template:
            raise SystemExit(f"{name} failed: backend env template missing {required_var}")

    for required_manifest_entry in [
        "deploy_verify_workflow",
        "compose_env_template",
        "backend_env_template",
        "predeploy unit tests",
        "post_deploy_assertions",
        "required security headers",
        "requires api-url",
        "origins without path",
        "reject example placeholder domains",
        "CORS preflight",
        "checks.mongodb_required=true",
    ]:
        if required_manifest_entry not in release_manifest_script:
            raise SystemExit(f"{name} failed: release manifest missing {required_manifest_entry}")

    for required_predeploy_entry in [
        "_check_cors_preflight",
        "Access-Control-Request-Method",
        "access-control-allow-origin",
        "mongodb_required",
        "api-url is required for production targets",
        "must be an origin without path",
        "must not use example placeholder domains",
    ]:
        if required_predeploy_entry not in predeploy_check:
            raise SystemExit(f"{name} failed: predeploy check missing {required_predeploy_entry}")

    elapsed = round(time.time() - start, 1)
    print("deployment_config_ok")
    return elapsed


def run_predeploy_static_checks() -> float:
    name = "Predeploy static checks"
    valid_command = [
        sys.executable,
        "scripts/predeploy_check.py",
        "--static",
        "--production-target",
        "--backend-url",
        "https://api.investment-report-agent.com",
        "--frontend-url",
        "https://app.investment-report-agent.com",
        "--api-url",
        "https://api.investment-report-agent.com/api/v1",
    ]
    print(f"\n==> {name}")
    print("    " + " ".join(valid_command))
    start = time.time()
    valid = subprocess.run(valid_command, cwd=ROOT)
    if valid.returncode != 0:
        raise SystemExit(f"{name} failed with exit code {valid.returncode}")

    invalid_command = [
        sys.executable,
        "scripts/predeploy_check.py",
        "--static",
        "--production-target",
        "--backend-url",
        "http://localhost:8000",
        "--frontend-url",
        "http://localhost:3000",
        "--api-url",
        "http://localhost:8000/api/v1",
    ]
    print("    " + " ".join(invalid_command))
    invalid = subprocess.run(invalid_command, cwd=ROOT)
    if invalid.returncode == 0:
        raise SystemExit(f"{name} failed: invalid production localhost URLs were accepted")

    elapsed = round(time.time() - start, 1)
    print("predeploy_static_checks_ok")
    return elapsed


def run_predeploy_unit_tests() -> float:
    return run_step(
        "Predeploy unit tests",
        ROOT,
        [sys.executable, "-m", "pytest", "tests/", "-v"],
    )


def run_release_manifest_check() -> float:
    return run_step(
        "Release manifest",
        ROOT,
        [
            sys.executable,
            "scripts/release_manifest.py",
            "--version",
            "deployable-candidate",
            "--backend-url",
            "https://api.investment-report-agent.com",
            "--frontend-url",
            "https://app.investment-report-agent.com",
            "--output",
            "docs/release-manifest-latest.json",
        ],
    )


def run_repository_safety_check() -> float:
    return run_step(
        "Repository safety check",
        ROOT,
        [sys.executable, "scripts/repository_safety_check.py"],
    )


def wait_for_backend(timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2) as response:
                return response.status == 200
        except Exception:
            time.sleep(1)
    return False


def main() -> int:
    results: list[tuple[str, float]] = []
    backend_process: subprocess.Popen | None = None
    frontend_process: subprocess.Popen | None = None

    try:
        results.append((
            "Backend unit tests",
            run_step("Backend unit tests", ROOT / "backend", [sys.executable, "-m", "pytest", "tests/unit/", "-v"]),
        ))
        results.append(("Backend production safeguards", run_backend_production_checks()))
        results.append(("Deployment config checks", run_deployment_config_checks()))
        results.append(("Predeploy unit tests", run_predeploy_unit_tests()))
        results.append(("Predeploy static checks", run_predeploy_static_checks()))
        results.append(("Release manifest", run_release_manifest_check()))
        results.append(("Repository safety check", run_repository_safety_check()))
        results.append((
            "Frontend lint",
            run_step("Frontend lint", ROOT / "frontend", [NPM, "run", "lint"]),
        ))
        results.append((
            "Frontend build",
            run_step("Frontend build", ROOT / "frontend", [NPM, "run", "build"]),
        ))

        if not wait_for_backend(timeout_seconds=2):
            print("\n==> Start backend for smoke e2e")
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            backend_process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=ROOT / "backend",
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if not wait_for_backend():
                raise SystemExit("Backend health check failed before smoke e2e")

        print("\n==> Start frontend for smoke e2e")
        frontend_process = subprocess.Popen(
            [NPM, "run", "dev"],
            cwd=ROOT / "frontend",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:3000", timeout=2) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(1)

        results.append((
            "Frontend smoke e2e",
            run_step("Frontend smoke e2e", ROOT / "frontend", [NPM, "run", "test:e2e:smoke"]),
        ))
    finally:
        if frontend_process and frontend_process.poll() is None:
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()
        if backend_process and backend_process.poll() is None:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()

    print("\nLaunch check summary")
    for name, seconds in results:
        print(f"- {name}: PASS ({seconds}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
