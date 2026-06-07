# Launch Remaining Work - 2026-06-06

## Current Status

Status: `DEPLOYABLE_CANDIDATE`

The repository has repeatable local checks, production Dockerfiles, production compose config, CI workflow definitions, deploy verification workflow, predeploy validation, trusted-report behavior, security headers, readiness, metrics, and deployment docs.

It is not yet a production-proven release because the remaining evidence depends on an external deployment environment, Docker runtime, GitHub Actions execution, real secrets, real MongoDB, real HTTPS domains, and hosted observability.

## Working Rule For Other Agents

- Do not add new product features.
- Do not refactor unrelated code.
- Do not commit secrets, `.env` files, private keys, tokens, or screenshots containing secrets.
- Prefer verification evidence over code changes.
- If a check fails because of missing external infrastructure, record it as `BLOCKED` with exact reason.
- If code changes are needed, keep them surgical and include the verification command.

## Work Package 1: Docker Build And Compose Rehearsal

Goal: prove the production containers build and start outside local dev.

Scope:

- Run Docker in an environment where Docker is installed.
- Build backend and frontend images from `Dockerfile.backend` and `Dockerfile.frontend`.
- Start `docker-compose.prod.yml` with non-production but realistic staging values.
- Confirm backend, frontend, and MongoDB healthchecks.

Commands:

```powershell
$env:FRONTEND_ORIGINS="https://<staging-frontend-origin>"
$env:NEXT_PUBLIC_API_URL="https://<staging-backend-origin>/api/v1"
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=200
```

Acceptance Criteria:

- Backend image builds successfully.
- Frontend image builds successfully with `NEXT_PUBLIC_API_URL`.
- Containers run as non-root users.
- Compose services become healthy or failure reason is clearly identified.
- No production config falls back to localhost.

Evidence To Return:

- Build exit code.
- `docker compose ps` output summary.
- Relevant healthcheck/log excerpts.
- Any required fixes with file paths.

My Review Focus:

- No accidental dev-only defaults.
- No leaked secrets in logs/docs.
- Healthcheck failures are not papered over.

## Work Package 2: GitHub Actions CI Verification

Goal: prove the repository passes CI in GitHub, not only locally.

Scope:

- Push work to a branch only after explicit approval.
- Run `.github/workflows/ci.yml`.
- Verify both `launch-check` and `docker-build` jobs.
- Confirm release manifest artifact upload.

Commands:

```powershell
gh workflow run ci.yml --ref <branch>
gh run list --workflow ci.yml --limit 5
gh run view <run-id> --log
```

Acceptance Criteria:

- `launch-check` job passes.
- `docker-build` job passes.
- `docs/release-manifest-latest.json` is uploaded as an artifact.
- Any CI-only failure is fixed or documented.

Evidence To Return:

- GitHub Actions run URL.
- Job statuses.
- Key failure logs if any.

My Review Focus:

- CI results match local launch expectations.
- Docker build is genuinely executed in CI.
- Fixes do not bypass checks.

## Work Package 3: Staging Deployment

Goal: deploy the candidate to real HTTPS staging URLs.

Scope:

- Deploy backend and frontend to real staging origins.
- Use real staging secrets from the hosting platform.
- Configure `NEXT_PUBLIC_API_URL=https://<backend-origin>/api/v1`.
- Configure backend `FRONTEND_ORIGINS=https://<frontend-origin>`.
- Keep debug routes and runtime config writes disabled.

Required Backend Env:

```text
ENVIRONMENT=production
SECRET_KEY=<strong random secret>
DEEPSEEK_API_KEY=<real key>
QVERIS_API_KEY=<real key>
FRONTEND_ORIGINS=https://<frontend-origin>
ENABLE_DEBUG_ROUTES=false
ENABLE_RUNTIME_CONFIG_WRITES=false
REQUIRE_MONGODB=true
REQUIRED_ENV_VARS=SECRET_KEY,DEEPSEEK_API_KEY,QVERIS_API_KEY
MONGODB_HOST=<mongo host>
MONGODB_PORT=27017
MONGODB_DATABASE=tradingagents
```

Required Frontend Env:

```text
NEXT_PUBLIC_API_URL=https://<backend-origin>/api/v1
```

Acceptance Criteria:

- Backend is reachable over HTTPS.
- Frontend is reachable over HTTPS.
- Frontend calls the deployed backend, not localhost.
- `/health`, `/ready`, `/metrics` respond as expected.

Evidence To Return:

- Backend URL.
- Frontend URL.
- Deployment platform/runtime.
- Sanitized env summary without secret values.
- Deployment logs around startup.

My Review Focus:

- Correct origin/API URL separation.
- No placeholder domains.
- No exposed debug routes.
- Runtime env values are not baked incorrectly.

## Work Package 4: Post-Deploy Predeploy Check

Goal: prove the deployed staging target satisfies production-facing checks.

Command:

```powershell
python scripts/predeploy_check.py --production-target `
  --backend-url https://<backend-origin> `
  --frontend-url https://<frontend-origin> `
  --api-url https://<backend-origin>/api/v1
```

Acceptance Criteria:

- Command exits 0.
- Backend `/health` returns `status=ok`.
- Backend `/ready` returns `status=ok`.
- `/ready` includes `checks.mongodb_required=true`.
- `/metrics` exposes `investment_report_http_requests_total`.
- Backend and frontend responses include required security headers.
- CORS preflight from frontend origin to backend report generation route allows `POST`.
- Frontend renders the app shell.

Evidence To Return:

- Full command.
- Exit code.
- Key output.

My Review Focus:

- Failures are fixed at the source, not by weakening `predeploy_check.py`.
- MongoDB readiness remains enforced for production target.

## Work Package 5: Real Report Smoke On Staging

Goal: prove the actual product flow works with real external providers.

Scope:

- Use staging frontend or API.
- Generate at least one quick scan and one value deep dive.
- Prefer known A-share ticker `600519.SH`.
- Verify trusted-report behavior.

Flows:

```text
600519.SH quick_scan
600519.SH value_deep_dive
/report?task=<real-task-id>
/report?task=not-a-real-task-id
/report
```

Acceptance Criteria:

- Successful real report shows `data_quality.result.status`.
- Data credibility card is visible on real report page.
- Real task failure never falls back to Demo.
- Invalid real task shows error page.
- `/report` without task is allowed but clearly marked `Demo 数据`.
- Provider/data failures are visible as partial/empty state, not hidden.

Evidence To Return:

- Task IDs.
- Final task statuses.
- Data quality summary: status, prices count, financials count, missing fields, data sources.
- Any user-visible failure text.

My Review Focus:

- No Demo fallback for real task failure.
- Data source and missing-data disclosure is clear.
- The UI remains usable when providers fail.

## Work Package 6: MongoDB Persistence Verification

Goal: prove report, portfolio, archive/list behavior survives process restart.

Scope:

- Use staging MongoDB or compose MongoDB.
- Create report(s), portfolio item(s), and archive/list entries if supported.
- Restart backend.
- Verify data is still present.

Acceptance Criteria:

- `/ready` reports MongoDB required and ready.
- Report retrieval by task ID works after restart.
- Report list page behavior is correct.
- Portfolio and archive pages either persist data or are documented as not applicable/currently local-only.

Evidence To Return:

- MongoDB mode: managed or compose volume.
- Restart steps.
- Before/after task IDs or record counts.
- Any persistence gaps.

My Review Focus:

- Persistence claims match implementation.
- Missing persistence is documented honestly.
- MongoDB connection failures degrade visibly.

## Work Package 7: Observability And Operations

Goal: make staging operable before any public traffic.

Scope:

- Configure uptime checks.
- Configure log access.
- Configure metrics scraping or at least documented pull checks.
- Define alert thresholds.
- Verify rollback procedure.

Minimum Checks:

- Uptime: `/health`
- Readiness: `/ready`
- Metrics: `/metrics`
- Frontend home page
- Report generation failure rate
- Backend 5xx rate
- Task latency

Acceptance Criteria:

- Someone can see whether the service is up.
- Someone can see why it is failing.
- Someone knows how to roll back.
- Alerts exist for service down and readiness failure.

Evidence To Return:

- Monitoring tool/platform.
- Check URLs.
- Alert thresholds.
- Rollback command/procedure used by the platform.

My Review Focus:

- `/health` and `/ready` are treated differently.
- Alerts are actionable, not just dashboards.
- Rollback is realistic for the chosen platform.

## Work Package 8: Release Hygiene And Final Candidate

Goal: produce a clean reviewable release candidate branch.

Scope:

- Review git status.
- Separate unrelated deletions or generated artifacts.
- Confirm no large accidental directories are included.
- Confirm docs point to current manifest and runbook.
- Run final local launch check.

Commands:

```powershell
git status --short
python scripts/launch_check.py
python scripts/repository_safety_check.py
```

Acceptance Criteria:

- Dirty files are intentional.
- No secrets or local-only generated folders are included.
- Final launch check passes.
- Release manifest is current.
- README/runbook/readiness docs match actual behavior.

Evidence To Return:

- `git status --short`.
- Launch check output summary.
- Any files intentionally excluded or reverted.

My Review Focus:

- Accidental files such as temporary cloned data, screenshots, local docs, or stale generated outputs.
- Deleted legacy docs/scripts that may not be intended.
- Consistency between code, docs, CI, and manifest.

## Suggested Agent Assignment

Use separate agents only where work can run independently:

| Agent | Work Packages |
|---|---|
| Agent A | Docker Build And Compose Rehearsal |
| Agent B | GitHub Actions CI Verification |
| Agent C | Staging Deployment + Post-Deploy Predeploy Check |
| Agent D | Real Report Smoke + MongoDB Persistence |
| Agent E | Observability And Operations |
| Agent F | Release Hygiene And Final Candidate |

Do not let multiple agents edit the same files at the same time unless they coordinate through a branch/PR.

## Final Review Gate

Before public launch, I should review:

- Final diff.
- `docs/launch-readiness-2026-06-05.md`.
- `docs/deployment-runbook-2026-06-05.md`.
- `docs/release-manifest-latest.json`.
- CI run URL.
- Deploy Verify run URL.
- Staging predeploy command output.
- Staging real report task IDs.
- Monitoring/rollback evidence.

Public launch should not proceed unless all required items are `PASS`, or every remaining item is explicitly accepted as a known risk.
