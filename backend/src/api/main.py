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


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
