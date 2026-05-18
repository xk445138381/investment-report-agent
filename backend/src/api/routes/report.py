"""Report generation API endpoints."""

import asyncio
import logging
from uuid import uuid4
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.orchestrator import Orchestrator, AgentContext
from api.config_accessor import get_config

logger = logging.getLogger(__name__)
router = APIRouter(tags=["report"])

# In-memory task store (replace with DB in production)
_tasks: dict = {}


class GenerateRequest(BaseModel):
    ticker: str
    report_type: str = "deep_dive"
    template_id: str = "deep_dive_default"
    start_date: str | None = None
    end_date: str | None = None


class TaskStatus(BaseModel):
    task_id: str
    status: str
    current_phase: str | None = None
    progress_pct: float = 0.0
    started_at: datetime | None = None


@router.post("/report/generate", status_code=201)
async def generate_report(req: GenerateRequest):
    """Start a report generation task."""
    orchestrator = Orchestrator(get_config())
    route_result = await orchestrator.route(req.ticker, {})
    if route_result.get("error"):
        raise HTTPException(400, route_result["error"])

    task_id = str(uuid4())
    resolved_ticker = route_result.get("ticker") or req.ticker
    resolved_type = route_result.get("pipeline_type") or req.report_type

    _tasks[task_id] = {
        "status": "queued",
        "ticker": resolved_ticker,
        "report_type": resolved_type,
        "created_at": datetime.now(),
        "result": None,
    }

    # Start background task
    asyncio.create_task(_run_generation(task_id, req, orchestrator, route_result, resolved_ticker, resolved_type))

    return {"task_id": task_id, "status": "queued"}


async def _run_generation(task_id, req, orchestrator, route_result, resolved_ticker, resolved_type):
    """Background task that executes the pipeline."""
    try:
        _tasks[task_id]["status"] = "running"
        _tasks[task_id]["started_at"] = datetime.now()

        config = get_config()
        ctx = AgentContext(
            task_id=task_id,
            ticker=resolved_ticker,
            company_name=route_result.get("company_name") or resolved_ticker,
            report_type=resolved_type,
            template_id=req.template_id,
            config=config,
        )

        # Pre-fetch data: QVeris → AkShare → continue without data
        try:
            from datetime import date as dt_date
            end = dt_date.today()
            start = end.replace(year=end.year - 3)
            prices = []
            financials = []

            # 1. Try QVeris first (routes through qveris.ai → THS iFinD / Alpha Vantage)
            try:
                from providers.qveris_provider import QverisProvider
                qv = QverisProvider()
                if await qv.health_check():
                    prices = await qv.get_prices(resolved_ticker, start, end)
                    logger.info(f"QVeris: got {len(prices)} price records for {resolved_ticker}")
                    financials = await qv.get_financials(resolved_ticker, years=3)
                    logger.info(f"QVeris: got {len(financials)} financial records for {resolved_ticker}")
            except Exception as e:
                logger.info(f"QVeris not available: {e}")

            # 2. Fall back to AkShare if QVeris returned no data
            if not prices or not financials:
                try:
                    from providers.akshare_provider import AkShareProvider
                    ak = AkShareProvider()
                    if await ak.health_check():
                        if not prices:
                            prices = await ak.get_prices(resolved_ticker, start, end)
                            logger.info(f"AkShare: got {len(prices)} price records for {resolved_ticker}")
                        if not financials:
                            financials = await ak.get_financials(resolved_ticker)
                            logger.info(f"AkShare: got {len(financials)} financial records for {resolved_ticker}")
                except Exception:
                    logger.warning("AkShare not available, proceeding without pre-fetched data")

            # Convert dicts to attribute-accessible objects (agents use latest.revenue, etc.)
            class _FallbackObj:
                """Object that returns None for missing attributes instead of AttributeError."""
                def __init__(self, **kwargs):
                    self.__dict__.update(kwargs)
                def __getattr__(self, name):
                    return None  # Missing fields → None instead of crash
            def _to_obj(d):
                if isinstance(d, dict):
                    return _FallbackObj(**{k: _to_obj(v) for k, v in d.items()})
                return d
            ctx.state["_prices"] = [_to_obj(p) for p in prices] if prices else []
            ctx.state["_financials"] = [_to_obj(f) for f in financials] if financials else []
            logger.info(f"Data fetch complete: {len(prices)} prices, {len(financials)} financials")
        except Exception as e:
            logger.warning(f"Data pre-fetch failed: {e}", exc_info=True)

        async def progress_cb(phase, pct, msg):
            _tasks[task_id]["current_phase"] = phase
            _tasks[task_id]["progress_pct"] = pct

        ctx.progress_callback = progress_cb
        result = await orchestrator.execute_pipeline(ctx)

        _tasks[task_id]["status"] = "completed"
        _tasks[task_id]["result"] = result
        _tasks[task_id]["completed_at"] = datetime.now()
    except Exception as e:
        logger.exception(f"Task {task_id} failed")
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["error"] = str(e)


@router.get("/report/{task_id}/status")
async def task_status(task_id: str):
    """Get the current status of a report generation task."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return {
        "task_id": task_id,
        "status": task["status"],
        "current_phase": task.get("current_phase"),
        "progress_pct": task.get("progress_pct", 0),
        "started_at": task.get("started_at"),
        "error": task.get("error"),
    }


@router.get("/report/{task_id}")
async def task_result(task_id: str, include_charts: bool = True):
    """Get the full report result (JSON). Set include_charts=false to skip base64 PNGs."""
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] != "completed":
        raise HTTPException(409, f"Task not completed (status: {task['status']})")
    result = task.get("result", {"note": "no result data"})
    if not include_charts:
        # Remove heavy base64 chart data
        charts = result.get("chart_generator", {}).get("result", [])
        if isinstance(charts, list):
            for c in charts:
                c.pop("png_base64", None)
    return result


@router.get("/report/{task_id}/stream")
async def task_stream(task_id: str, request: Request):
    """SSE stream for real-time progress updates."""
    async def event_generator():
        task = _tasks.get(task_id)
        if not task:
            yield f"event: error\ndata: Task not found\n\n"
            return

        last_phase = None
        while task["status"] in ("queued", "running"):
            current_phase = task.get("current_phase")
            if current_phase != last_phase:
                last_phase = current_phase
                yield f"event: progress\ndata: {current_phase} ({task.get('progress_pct', 0)}%)\n\n"

            if await request.is_disconnected():
                break
            await asyncio.sleep(0.5)

        if task["status"] == "completed":
            yield f"event: complete\ndata: {{\"task_id\": \"{task_id}\", \"status\": \"completed\"}}\n\n"
        elif task["status"] == "failed":
            yield f"event: error\ndata: {task.get('error', 'Unknown error')}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
