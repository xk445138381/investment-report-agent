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

    task_id = str(uuid4())
    _tasks[task_id] = {
        "status": "queued",
        "ticker": req.ticker,
        "report_type": req.report_type,
        "created_at": datetime.now(),
        "result": None,
    }

    # Start background task
    asyncio.create_task(_run_generation(task_id, req, orchestrator, route_result))

    return {"task_id": task_id, "status": "queued"}


async def _run_generation(task_id, req, orchestrator, route_result):
    """Background task that executes the pipeline."""
    try:
        _tasks[task_id]["status"] = "running"
        _tasks[task_id]["started_at"] = datetime.now()

        config = get_config()
        ctx = AgentContext(
            task_id=task_id,
            ticker=req.ticker,
            company_name=route_result.get("company_name") or req.ticker,
            report_type=req.report_type,
            template_id=req.template_id,
            config=config,
        )

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
    }


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
            yield f"event: complete\ndata: report generated\n\n"
        elif task["status"] == "failed":
            yield f"event: error\ndata: {task.get('error', 'Unknown error')}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
