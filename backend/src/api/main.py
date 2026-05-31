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
