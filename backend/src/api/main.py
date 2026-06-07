"""FastAPI application — investment report agent API."""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import orjson

# Load .env from backend root (parent of src/api/), strip CRLF on Windows
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_ENV_PATH)
# Ensure no \r contamination from Windows CRLF
for key in list(os.environ.keys()):
    val = os.environ[key]
    if isinstance(val, str) and '\r' in val:
        os.environ[key] = val.replace('\r', '')
logger = logging.getLogger(__name__)
logger.info(f"Loaded .env from {_ENV_PATH} (DEEPSEEK_KEY={'set' if os.getenv('DEEPSEEK_API_KEY') else 'MISSING'})")


def _csv_env(name: str, default: str) -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _environment() -> str:
    return os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).strip().lower()


def _required_env_vars() -> list[str]:
    default = "SECRET_KEY,DEEPSEEK_API_KEY,QVERIS_API_KEY" if _environment() in {"production", "prod"} else ""
    return _csv_env("REQUIRED_ENV_VARS", default)


def _secret_is_placeholder(value: str) -> bool:
    return value.strip() in {"", "change-me-to-a-random-string", "dev-secret-change-in-production"}


def _readiness_status() -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    env = _environment()

    try:
        config = _get_cfg()
    except Exception as exc:
        errors.append(f"config_load_failed: {exc}")
        config = None

    for name in _required_env_vars():
        if not os.getenv(name, ""):
            errors.append(f"missing_env:{name}")

    secret_key = os.getenv("SECRET_KEY", "")
    if env in {"production", "prod"} and _secret_is_placeholder(secret_key):
        errors.append("unsafe_secret_key")

    if config:
        missing_llm_keys = []
        for provider_id, provider_cfg in getattr(config, "llm_providers", {}).items():
            source = getattr(provider_cfg, "api_key_source", "")
            if source.startswith("env:"):
                key_name = source.replace("env:", "", 1)
                if not os.getenv(key_name, ""):
                    missing_llm_keys.append(f"{provider_id}:{key_name}")
        if missing_llm_keys:
            warnings.append("missing_llm_provider_keys:" + ",".join(missing_llm_keys))

    origins = _cors_origins if "_cors_origins" in globals() else _csv_env("FRONTEND_ORIGINS", "")
    if env in {"production", "prod"} and origins and all("localhost" in origin or "127.0.0.1" in origin for origin in origins):
        warnings.append("production_frontend_origins_are_local_only")

    return {
        "status": "ok" if not errors else "not_ready",
        "environment": env,
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "config_loaded": config is not None,
            "required_env_vars": _required_env_vars(),
            "debug_routes_enabled": env not in {"production", "prod"} or _env_enabled("ENABLE_DEBUG_ROUTES"),
            "runtime_config_writes_enabled": env not in {"production", "prod"} or _env_enabled("ENABLE_RUNTIME_CONFIG_WRITES"),
            "mongodb_required": _env_enabled("REQUIRE_MONGODB"),
        },
    }


async def _mongodb_readiness_status() -> tuple[bool, str | None]:
    if not _env_enabled("REQUIRE_MONGODB"):
        return True, None
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        await col.database.command("ping")
        return True, None
    except Exception as exc:
        return False, f"mongodb_unavailable: {exc}"


class ORJSONResponse(JSONResponse):
    """Fast JSON response using orjson (handles Unicode/binary properly)."""
    media_type = "application/json"

    def render(self, content) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS)

from api.config_accessor import get_config as _get_cfg
from api.observability import metrics_middleware, metrics_response
from api.security_headers import security_headers_middleware
from api.routes import report, template, upload, user, config_routes

logger = logging.getLogger(__name__)


# Debug diagnostics. Registered only outside production unless explicitly enabled.
from fastapi import APIRouter
debug = APIRouter(tags=["debug"])

@debug.get("/debug/env")
def env_status():
    ds = os.environ.get("DEEPSEEK_API_KEY", "")
    qv = os.environ.get("QVERIS_API_KEY", "")
    return {
        "deepseek_key": f"set ({len(ds)} chars)" if ds else "MISSING",
        "qveris_key": f"set ({len(qv)} chars)" if qv else "MISSING",
        "env_path": str(_ENV_PATH),
        "env_exists": _ENV_PATH.exists(),
    }

@debug.get("/debug/llm")
def test_llm():
    """Quick test: call DeepSeek via subprocess from server process."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"error": "No API key"}
    import sys, subprocess, json as j
    prompt = "用段永平的视角，一句话评价贵州茅台这家公司。"
    script = f'''
import sys, json
import urllib.request
api_key = {j.dumps(api_key)}
body = json.dumps({{"model": "deepseek-v4-pro", "messages": [{{"role": "user", "content": {j.dumps(prompt)}}}], "max_tokens": 200}}).encode()
req = urllib.request.Request("https://api.deepseek.com/v1/chat/completions", data=body, headers={{"Authorization": f"Bearer {{api_key}}", "Content-Type": "application/json"}}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode())
    print(resp["choices"][0]["message"]["content"])
except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
'''
    try:
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=90)
        return {"ok": result.returncode == 0,
                "stdout": result.stdout[:300],
                "stderr": result.stderr[:200],
                "rc": result.returncode}
    except Exception as e:
        return {"error": str(e)}


async def _alert_checker():
    """Background task: check price alerts every 15 minutes."""
    while True:
        try:
            from api.db import get_reports_collection
            col = await get_reports_collection()
            db = col.database
            alerts_col = db["alerts"]
            active_alerts = await alerts_col.find({"triggered": False}).to_list(length=100)
            for alert in active_alerts:
                try:
                    ticker = alert["ticker"]
                    threshold = alert["threshold"]
                    alert_type = alert["type"]

                    # Fetch current price via TradingAgents or QVeris
                    current_price = None
                    is_cn = ".SH" in ticker.upper() or ".SZ" in ticker.upper()
                    if is_cn:
                        try:
                            from providers.tradingagents_provider import TradingAgentsProvider
                            ta = TradingAgentsProvider()
                            if await ta.health_check():
                                from datetime import date as dt_date, timedelta
                                prices = await ta.get_prices(ticker, dt_date.today() - timedelta(days=5), dt_date.today())
                                if prices:
                                    current_price = prices[-1].get("close") if hasattr(prices[-1], 'get') else prices[-1].close
                        except Exception:
                            pass
                    if not current_price:
                        try:
                            from providers.qveris_provider import QverisProvider
                            qv = QverisProvider()
                            prices = await qv.get_prices(ticker, None, None)
                            if prices and isinstance(prices, list) and len(prices) > 0:
                                p = prices[-1]
                                current_price = p.get("close") if isinstance(p, dict) else p.close
                        except Exception:
                            pass

                    if current_price and current_price <= threshold:
                        await alerts_col.update_one(
                            {"_id": alert["_id"]},
                            {"$set": {"triggered": True, "triggered_at": datetime.now(), "current_price": current_price}}
                        )
                        logger.info(f"Alert triggered: {ticker} {alert_type} at {current_price} <= {threshold}")
                except Exception as e:
                    logger.warning(f"Alert check failed for {alert.get('ticker')}: {e}")
        except Exception as e:
            logger.warning(f"Alert checker error: {e}")
        await asyncio.sleep(900)  # 15 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Investment Report Agent API starting...")
    _get_cfg()
    task = asyncio.create_task(_alert_checker())
    yield
    task.cancel()
    logger.info("API shutting down.")
    # Close MongoDB connection on shutdown
    try:
        from api.db import close_db
        await close_db()
    except Exception:
        pass


app = FastAPI(
    title="Investment Report Agent API",
    version="0.1.0",
    description="Multi-Agent Investment Report Generation System",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)

_cors_origins = _csv_env("FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(metrics_middleware)
app.middleware("http")(security_headers_middleware)

app.include_router(report.router, prefix="/api/v1")
app.include_router(template.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(config_routes.router, prefix="/api/v1")
if _environment() not in {"production", "prod"} or _env_enabled("ENABLE_DEBUG_ROUTES"):
    app.include_router(debug, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/ready")
async def ready(response: Response):
    status = _readiness_status()
    mongodb_ok, mongodb_error = await _mongodb_readiness_status()
    status["checks"]["mongodb_available"] = mongodb_ok
    if mongodb_error:
        status["errors"].append(mongodb_error)
        status["status"] = "not_ready"
    if status["status"] != "ok":
        response.status_code = 503
    return status


@app.get("/metrics")
async def metrics():
    return metrics_response()
