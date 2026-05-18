"""FastAPI application — investment report agent API."""

import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()  # Load .env file into os.environ

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
