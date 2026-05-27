"""FastAPI application — investment report agent API."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
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


class ORJSONResponse(JSONResponse):
    """Fast JSON response using orjson (handles Unicode/binary properly)."""
    media_type = "application/json"

    def render(self, content) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_NON_STR_KEYS)

from api.config_accessor import get_config as _get_cfg
from api.routes import report, template, upload, user, config_routes

logger = logging.getLogger(__name__)


# Debug: expose key status (remove in production)
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
    """Quick test: call DeepSeek directly from server process."""
    import requests as req
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {"error": "No API key"}
    try:
        r = req.post("https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": "一句话介绍茅台"}],
                  "max_tokens": 100, "temperature": 0.3},
            timeout=60)
        if r.status_code == 200:
            data = r.json()
            choice0 = data.get("choices", [{}])[0] if data.get("choices") else {}
            msg = choice0.get("message", {}) if isinstance(choice0, dict) else {}
            return {"status": "ok", "model": data.get("model", "?"),
                    "finish_reason": choice0.get("finish_reason", "none") if isinstance(choice0, dict) else "no_choice",
                    "message_keys": list(msg.keys()) if msg else [],
                    "content": str(msg.get("content", ""))[:300] if msg else "NO_MESSAGE",
                    "message_type": str(type(msg))}
        return {"error": f"HTTP {r.status_code}", "body": r.text[:300]}
    except Exception as e:
        return {"error": str(e)}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Investment Report Agent API starting...")
    _get_cfg()
    yield
    logger.info("API shutting down.")


app = FastAPI(
    title="Investment Report Agent API",
    version="0.1.0",
    description="Multi-Agent Investment Report Generation System",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(report.router, prefix="/api/v1")
app.include_router(template.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(config_routes.router, prefix="/api/v1")
app.include_router(debug, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
