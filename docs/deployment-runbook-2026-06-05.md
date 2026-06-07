# Deployment Runbook - 2026-06-05

## Scope

This runbook covers a deployable-candidate release of the Investment Report Agent.

It assumes:

- Backend is deployed from `Dockerfile.backend`.
- Frontend is deployed from `Dockerfile.frontend`.
- MongoDB is either the compose service or a managed MongoDB instance.
- Secrets are provided by the hosting platform, not committed files.

## Required Environment

For a local container rehearsal, use the checked-in templates:

- Copy `deploy/compose.env.example` to `.env`.
- Copy `deploy/backend.env.example` to `backend/.env`.
- Replace every placeholder with real production or staging values before starting the stack.

Backend:

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

Frontend:

```text
NEXT_PUBLIC_API_URL=https://<backend-origin>/api/v1
```

`docker-compose.prod.yml` intentionally has no localhost fallback for `FRONTEND_ORIGINS` or `NEXT_PUBLIC_API_URL`. Set both variables before building or starting the production compose stack.

## Pre-Deploy Gates

Run from repository root:

```powershell
python scripts/launch_check.py
```

For the target URLs, run static validation:

```powershell
python scripts/predeploy_check.py --static --production-target `
  --backend-url https://<backend-origin> `
  --frontend-url https://<frontend-origin> `
  --api-url https://<backend-origin>/api/v1
```

Required result:

```text
predeploy_check: PASS
```

`--backend-url` and `--frontend-url` must be real deployment origins only: no path, query string, fragment, localhost, or `example.com`/`example.org`/`example.net` placeholder domains. Put `/api/v1` only in `--api-url`.

## Deploy

Container rehearsal:

```powershell
$env:FRONTEND_ORIGINS="https://<frontend-origin>"
$env:NEXT_PUBLIC_API_URL="https://<backend-origin>/api/v1"
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

If using a managed platform, deploy backend first, then frontend. The frontend must be built with `NEXT_PUBLIC_API_URL` pointing at the deployed backend `/api/v1` URL.

## Post-Deploy Verification

Run network validation:

```powershell
python scripts/predeploy_check.py --production-target `
  --backend-url https://<backend-origin> `
  --frontend-url https://<frontend-origin> `
  --api-url https://<backend-origin>/api/v1
```

Or run GitHub Actions workflow `Deploy Verify` with:

- `backend_url=https://<backend-origin>`
- `frontend_url=https://<frontend-origin>`
- `api_url=https://<backend-origin>/api/v1`

Manual verification:

- `GET https://<backend-origin>/health` returns `{"status":"ok"}`.
- The predeploy command includes `--api-url https://<backend-origin>/api/v1`.
- `GET https://<backend-origin>/ready` returns `{"status":"ok"}`.
- If `REQUIRE_MONGODB=true`, `/ready` also requires MongoDB ping success.
- `GET https://<backend-origin>/ready` includes `checks.mongodb_required=true`.
- `GET https://<backend-origin>/metrics` includes `investment_report_http_requests_total`.
- Backend `/health` and frontend home responses include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy`.
- CORS preflight from `https://<frontend-origin>` to `https://<backend-origin>/api/v1/report/generate` allows `POST`.
- Frontend loads and shows `新建分析`.
- `/report` without a task shows `Demo 数据`.
- `/report?task=not-a-real-task-id` shows real-report failure and does not show Demo fallback.

## Smoke Report

Use a known A-share ticker:

```text
600519.SH quick_scan
```

Pass criteria:

- Report task reaches `completed`, or if an external provider fails, the UI clearly shows real-report failure.
- Successful report includes `data_quality.result.status`.
- Demo fallback is never used for a real task failure.

## Rollback

Rollback trigger examples:

- `/ready` is not `ok`.
- Frontend cannot reach backend API.
- Real report failures are replaced by Demo data.
- Error rate or latency spikes after deployment.

Rollback actions:

1. Revert frontend to previous build or release.
2. Revert backend to previous image or release.
3. Confirm `ENABLE_DEBUG_ROUTES=false` and `ENABLE_RUNTIME_CONFIG_WRITES=false`.
4. Verify `/health`, `/ready`, `/metrics`, and frontend home page.
5. Preserve logs and failed task ids for diagnosis.

## Operational Notes

- Do not deploy with `SECRET_KEY=change-me-to-a-random-string`.
- Do not expose `/api/v1/debug/*` in production.
- Do not allow runtime config writes in production unless explicitly needed for a controlled maintenance window.
- Configure uptime checks for `/health` and `/ready`.
- Configure metrics scraping for `/metrics`.
