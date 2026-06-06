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


def _normalize_report_result(result: dict) -> dict:
    """Return a frontend-safe report result with legacy data-quality fallback."""
    def clean(value):
        if isinstance(value, dict):
            cleaned = {}
            for key, item in value.items():
                if key in {"_prices", "_financials"}:
                    continue
                cleaned_item = clean(item)
                if cleaned_item is not None:
                    cleaned[key] = cleaned_item
            return cleaned
        if isinstance(value, list):
            cleaned_items = []
            for item in value:
                cleaned_item = clean(item)
                if cleaned_item is not None:
                    cleaned_items.append(cleaned_item)
            return cleaned_items
        if isinstance(value, str) and value.startswith("<") and " object at " in value:
            return None
        return value

    normalized = clean(result or {})
    if not normalized.get("data_quality", {}).get("result"):
        normalized["data_quality"] = {
            "status": "completed",
            "phase": "compatibility",
            "result": {
                "status": "empty",
                "prices_count": 0,
                "financials_count": 0,
                "missing": ["prices", "financials"],
                "data_sources": {},
                "provider_trace": [],
                "warnings": ["legacy report missing data_quality"],
            },
        }
    return normalized


@router.post("/report/generate", status_code=201)
async def generate_report(req: GenerateRequest):
    """Start a report generation task."""
    orchestrator = Orchestrator(get_config())
    route_result = await orchestrator.route(req.ticker, {
        "preferred_template": req.template_id,
    })
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
        "events": [],
    }

    # Persist to MongoDB immediately so it survives restarts
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        await col.replace_one(
            {"_id": task_id, "_type": "task_meta"},
            {
                "_id": task_id,
                "_type": "task_meta",
                "ticker": resolved_ticker,
                "report_type": resolved_type,
                "template_id": req.template_id,
                "company_name": route_result.get("company_name") or resolved_ticker,
                "status": "queued",
                "created_at": datetime.now(),
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Task persist failed (non-fatal): {e}")

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

        # Pre-fetch data: TradingAgents(CN) → QVeris → AkShare → continue
        prices = []
        financials = []
        data_sources = {"prices": None, "financials": None}
        try:
            from datetime import date as dt_date
            end = dt_date.today()
            start = end.replace(year=end.year - 3)

            # Determine market for CN routing
            is_cn = ".SH" in resolved_ticker.upper() or ".SZ" in resolved_ticker.upper()

            # 1. CN: Try TradingAgents-astock first (direct HTTP, fastest for A-shares)
            if is_cn:
                try:
                    from providers.tradingagents_provider import TradingAgentsProvider
                    ta = TradingAgentsProvider()
                    if await ta.health_check():
                        prices = await ta.get_prices(resolved_ticker, start, end)
                        logger.info(f"TradingAgents: got {len(prices)} price records for {resolved_ticker}")
                        if prices:
                            data_sources["prices"] = "TradingAgents"
                        financials = await ta.get_financials(resolved_ticker, years=3)
                        logger.info(f"TradingAgents: got {len(financials)} financial records for {resolved_ticker}")
                        if financials:
                            data_sources["financials"] = "TradingAgents"
                except Exception as e:
                    logger.info(f"TradingAgents not available: {e}")

            # 2. CN fallback / non-CN primary: QVeris
            if not prices or not financials:
                try:
                    from providers.qveris_provider import QverisProvider
                    qv = QverisProvider()
                    if await qv.health_check():
                        if not prices:
                            prices = await qv.get_prices(resolved_ticker, start, end)
                            logger.info(f"QVeris: got {len(prices)} price records for {resolved_ticker}")
                            if prices:
                                data_sources["prices"] = "QVeris"
                        if not financials:
                            financials = await qv.get_financials(resolved_ticker, years=3) or []
                            logger.info(f"QVeris: got {len(financials)} financial records for {resolved_ticker}")
                            if financials:
                                data_sources["financials"] = "QVeris"
                except Exception as e:
                    logger.info(f"QVeris not available: {e}")

            # 2.5 CN: Try TradingAgents for financials (small-caps not in QVeris)
            if is_cn and not financials:
                try:
                    from providers.tradingagents_provider import TradingAgentsProvider
                    ta = TradingAgentsProvider()
                    if await ta.health_check():
                        financials = await ta.get_financials(resolved_ticker, years=3) or []
                        logger.info(f"TradingAgents: got {len(financials)} financial records for {resolved_ticker}")
                        if financials:
                            data_sources["financials"] = "TradingAgents"
                except Exception as e:
                    logger.info(f"TradingAgents financials not available: {e}")

            # 3. Final fallback: AkShare
            if not prices or not financials:
                try:
                    from providers.akshare_provider import AkShareProvider
                    ak = AkShareProvider()
                    if await ak.health_check():
                        if not prices:
                            prices = await ak.get_prices(resolved_ticker, start, end)
                            logger.info(f"AkShare: got {len(prices)} price records for {resolved_ticker}")
                            if prices:
                                data_sources["prices"] = "AkShare"
                        if not financials:
                            financials = await ak.get_financials(resolved_ticker)
                            logger.info(f"AkShare: got {len(financials)} financial records for {resolved_ticker}")
                            if financials:
                                data_sources["financials"] = "AkShare"
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
            ctx.state["_data_sources"] = data_sources
            missing = []
            if not prices:
                missing.append("prices")
            if not financials:
                missing.append("financials")
            data_status = "real" if not missing else "partial" if prices or financials else "empty"
            provider_trace = [
                {
                    "dataset": "prices",
                    "provider": data_sources.get("prices") or "none",
                    "status": "ok" if prices else "missing",
                    "records": len(prices),
                },
                {
                    "dataset": "financials",
                    "provider": data_sources.get("financials") or "none",
                    "status": "ok" if financials else "missing",
                    "records": len(financials),
                },
            ]
            data_quality = {
                "status": data_status,
                "resolved_ticker": resolved_ticker,
                "company_name": route_result.get("company_name") or resolved_ticker,
                "prices_count": len(prices),
                "financials_count": len(financials),
                "missing": missing,
                "data_sources": data_sources,
                "provider_trace": provider_trace,
                "as_of": datetime.now().isoformat(),
            }
            ctx.state["data_quality"] = {
                "status": "completed",
                "phase": "prefetch",
                "result": data_quality,
            }
            ctx.state["provider_trace"] = {
                "status": "completed",
                "phase": "prefetch",
                "result": provider_trace,
            }
            logger.info(f"Data fetch complete: {len(prices)} prices, {len(financials)} financials")
        except Exception as e:
            logger.warning(f"Data pre-fetch failed: {e}", exc_info=True)
            data_quality = {
                "status": "empty",
                "resolved_ticker": resolved_ticker,
                "company_name": route_result.get("company_name") or resolved_ticker,
                "prices_count": len(prices),
                "financials_count": len(financials),
                "missing": ["prices", "financials"],
                "data_sources": data_sources,
                "provider_trace": [],
                "warnings": [str(e)[:240]],
                "as_of": datetime.now().isoformat(),
            }
            ctx.state["_prices"] = []
            ctx.state["_financials"] = []
            ctx.state["_data_sources"] = data_sources
            ctx.state["data_quality"] = {
                "status": "completed",
                "phase": "prefetch",
                "result": data_quality,
            }
            ctx.state["provider_trace"] = {
                "status": "completed",
                "phase": "prefetch",
                "result": [],
            }

        async def progress_cb(phase, pct, msg):
            _tasks[task_id]["current_phase"] = phase
            _tasks[task_id]["progress_pct"] = pct
            # Update MongoDB task metadata
            try:
                from api.db import get_reports_collection
                col = await get_reports_collection()
                await col.update_one(
                    {"_id": task_id, "_type": "task_meta"},
                    {"$set": {"current_phase": phase, "progress_pct": pct, "status": "running"}},
                )
            except Exception:
                pass
            if msg and ":" in msg and len(msg) < 200:
                _tasks[task_id]["events"].append({
                    "type": "agent_completed",
                    "phase": phase,
                    "message": msg,
                    "pct": pct,
                })

        async def agent_cb(agent_name: str, status: str, detail: str = ""):
            _tasks[task_id]["events"].append({
                "type": "agent_completed",
                "agent": agent_name,
                "status": status,
                "detail": detail,
            })

        ctx.progress_callback = progress_cb
        ctx.agent_callback = agent_cb
        result = await orchestrator.execute_pipeline(ctx)

        _tasks[task_id]["status"] = "completed"
        _tasks[task_id]["result"] = result
        _tasks[task_id]["completed_at"] = datetime.now()

        # Compute multi-layer confidence
        confidence = _compute_confidence(result)
        _tasks[task_id]["result"]["_confidence"] = confidence

        # Persist to MongoDB
        try:
            from api.db import get_reports_collection
            col = await get_reports_collection()
            # Convert result to JSON-safe dict (remove non-serializable objects)
            import json as _json
            result_clean = _json.loads(_json.dumps(result, default=str))
            sections = result_clean.get("section_writer", {}).get("result", {}).get("sections", {})
            final = sections.get("final_judgment", {}) or {}
            verdict_text = final.get("content", "")
            verdict = "Unknown"
            for v in ["Too Hard", "No", "Yes"]:
                if v in verdict_text:
                    verdict = v
                    break

            await col.replace_one(
                {"_id": task_id},
                {
                    "_id": task_id,
                    "ticker": resolved_ticker,
                    "company_name": route_result.get("company_name") or resolved_ticker,
                    "report_type": resolved_type,
                    "template_id": req.template_id,
                    "verdict": verdict,
                    "verdict_conf": result_clean.get("verdict_conf", 0),
                    "upside_pct": result_clean.get("val", {}).get("weighted_upside_pct", 0),
                    "created_at": datetime.now(),
                    "result": result_clean,
                },
                upsert=True,
            )
            logger.info(f"Report {task_id} persisted to MongoDB")
        except Exception as e:
            logger.warning(f"Failed to persist report to MongoDB: {e}")

        # Generate falsifiable predictions
        try:
            import os
            from agents.analysis.llm_subprocess import call_llm
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            if api_key:
                sections = (result or {}).get("section_writer", {}).get("result", {}).get("sections", {})
                exec_text = sections.get("executive_summary", {}).get("content", "")
                fin_text = sections.get("financial_health", {}).get("content", "")
                val_text = sections.get("valuation", {}).get("content", "")
                prompt = (
                    f"基于以下研究报告内容，生成3条可在12个月后验证的定量预测。\n"
                    f"每条格式：预测内容 | 当前值 | 预测区间\n\n"
                    f"投资摘要：{exec_text[:500]}\n"
                    f"财务健康：{fin_text[:500]}\n"
                    f"估值分析：{val_text[:500]}\n\n"
                    f"返回JSON数组: [{{\"prediction\":\"...\",\"current\":\"...\",\"range\":\"...\"}}]"
                )
                predictions_raw = await asyncio.to_thread(call_llm,
                    api_key,
                    os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
                    prompt,
                    timeout=30,
                )
                if predictions_raw:
                    import json as _json
                    try:
                        predictions = _json.loads(predictions_raw)
                    except Exception:
                        predictions = [{"prediction": predictions_raw[:200], "current": "N/A", "range": "N/A"}]

                    # Update MongoDB with predictions
                    from api.db import get_reports_collection
                    col = await get_reports_collection()
                    await col.update_one({"_id": task_id}, {"$set": {"predictions": predictions}})
                    # Also update in-memory
                    _tasks[task_id]["result"]["predictions"] = predictions
        except Exception as e:
            logger.warning(f"Failed to generate predictions: {e}")

        # Create price alerts from valuation
        try:
            val = (result or {}).get("valuation", {}).get("result", {})
            current_price = val.get("current_price", 0) if isinstance(val, dict) else 0
            safety_margin = val.get("safety_margin_pct", 0) if isinstance(val, dict) else 0
            intrinsic_value = val.get("weighted_value", 0) if isinstance(val, dict) else 0
            from api.db import get_reports_collection as _get_col
            col = await _get_col()
            db = col.database
            alerts_col = db["alerts"]
            price_buy_upper = round(current_price * (1 + safety_margin / 100 * 0.6), 2) if current_price and safety_margin else None
            price_heavy = round(current_price * (1 + safety_margin / 100 * 0.3), 2) if current_price and safety_margin else None
            verdict = "Unknown"
            if verdict_text:
                for v in ["Too Hard", "No", "Yes"]:
                    if v in verdict_text:
                        verdict = v
                        break
            if price_buy_upper and verdict in ("Yes",):
                await alerts_col.replace_one(
                    {"ticker": resolved_ticker, "type": "price_entry"},
                    {
                        "ticker": resolved_ticker,
                        "company_name": route_result.get("company_name", resolved_ticker),
                        "type": "price_entry",
                        "threshold": price_buy_upper,
                        "message": f"建议低于 {price_buy_upper} 开始买入",
                        "created_at": datetime.now(),
                        "triggered": False,
                        "task_id": task_id,
                    },
                    upsert=True,
                )
            if price_heavy and verdict in ("Yes",):
                await alerts_col.replace_one(
                    {"ticker": resolved_ticker, "type": "price_heavy"},
                    {
                        "ticker": resolved_ticker,
                        "company_name": route_result.get("company_name", resolved_ticker),
                        "type": "price_heavy",
                        "threshold": price_heavy,
                        "message": f"低于 {price_heavy} 可重仓",
                        "created_at": datetime.now(),
                        "triggered": False,
                        "task_id": task_id,
                    },
                    upsert=True,
                )
        except Exception as e:
            logger.warning(f"Failed to create price alerts: {e}")

    except Exception as e:
        logger.exception(f"Task {task_id} failed")
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["error"] = str(e)


@router.get("/report/{task_id}/status")
async def task_status(task_id: str):
    """Get the current status of a report generation task."""
    task = _tasks.get(task_id)
    if not task:
        # Check MongoDB for persisted task metadata
        try:
            from api.db import get_reports_collection
            col = await get_reports_collection()
            doc = await col.find_one({"_id": task_id, "_type": "task_meta"})
            if doc:
                return {
                    "task_id": task_id,
                    "status": doc.get("status", "unknown"),
                    "current_phase": doc.get("current_phase"),
                    "progress_pct": doc.get("progress_pct", 0),
                    "started_at": doc.get("started_at"),
                    "error": doc.get("error"),
                }
        except Exception:
            pass
        raise HTTPException(404, "Task not found")
    return {
        "task_id": task_id,
        "status": task["status"],
        "current_phase": task.get("current_phase"),
        "progress_pct": task.get("progress_pct", 0),
        "started_at": task.get("started_at"),
        "error": task.get("error"),
    }


# ── Report listing (must be BEFORE /report/{task_id} to avoid routing conflict) ──

@router.get("/reports")
async def list_reports(limit: int = 20, skip: int = 0):
    """List completed reports, newest first. Lightweight metadata only (no full result body)."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        cursor = col.find(
            {},
            projection={"result": 0},  # exclude heavy result body
        ).sort("created_at", -1).skip(skip).limit(limit)
        reports = []
        async for doc in cursor:
            reports.append({
                "task_id": doc["_id"],
                "ticker": doc.get("ticker"),
                "company_name": doc.get("company_name"),
                "report_type": doc.get("report_type"),
                "template_id": doc.get("template_id"),
                "verdict": doc.get("verdict"),
                "verdict_conf": doc.get("verdict_conf"),
                "upside_pct": doc.get("upside_pct"),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            })
        total = await col.count_documents({})
        return {"reports": reports, "total": total}
    except Exception as e:
        logger.warning(f"Failed to list reports: {e}")
        return {"reports": [], "total": 0}


# ── Report task result (parameterized — keep AFTER fixed paths) ──

@router.get("/report/{task_id}")
async def task_result(task_id: str, include_charts: bool = True):
    """Get the full report result (JSON). Set include_charts=false to skip base64 PNGs.

    Checks MongoDB first (persists across restarts), then in-memory _tasks.
    """
    result = None
    
    # 1. Try MongoDB first (survives restarts)
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        doc = await col.find_one({"_id": task_id, "_type": {"$ne": "task_meta"}})
        if doc:
            result = doc.get("result", {})
    except Exception:
        pass
    
    # 2. Fallback to in-memory
    if not result:
        task = _tasks.get(task_id)
        if task and task.get("result"):
            result = task.get("result", {})
    
    if not result:
        raise HTTPException(404, "Report not found")

    result = _normalize_report_result(result)

    if not include_charts:
        # Remove heavy base64 chart data
        charts = result.get("chart_generator", {}).get("result", [])
        if isinstance(charts, list):
            for c in charts:
                c.pop("png_base64", None)
    return result


# ── Confidence computation ────────────────────────────────────

def _compute_confidence(result: dict) -> dict:
    """Aggregate multi-layer confidence from agent outputs.

    Returns dict with:
      - data: per-agent data quality summary
      - analysis: per-section analysis confidence
      - valuation: sensitivity-based valuation confidence
      - overall: 0-100 overall confidence score
    """
    data_conf = {}
    agent_keys = ["price_data", "financial_data", "news_data", "macro_data",
                  "financial_analysis", "valuation", "industry_competition",
                  "corporate_governance", "duan_case", "munger_case",
                  "bull_case", "bear_case", "risk_judge", "value_judge"]

    for key in agent_keys:
        agent_result = result.get(key, {})
        result_inner = agent_result.get("result", agent_result) if isinstance(agent_result, dict) else {}
        dq = result_inner.get("data_quality") if isinstance(result_inner, dict) else None
        if dq and isinstance(dq, dict):
            data_conf[key] = dq

    # Data confidence: average of agent quality scores
    quality_scores = []
    for dq in data_conf.values():
        q = dq.get("quality", "")
        if q == "high": quality_scores.append(100)
        elif q == "medium": quality_scores.append(60)
        elif q == "low": quality_scores.append(30)
    data_score = round(sum(quality_scores) / len(quality_scores)) if quality_scores else 50

    # Analysis confidence: based on whether LLM was used for section writing
    sw = result.get("section_writer", {})
    sw_result = sw.get("result", sw) if isinstance(sw, dict) else {}
    llm_used = bool(sw_result.get("_llm_used", True)) if isinstance(sw_result, dict) else True
    analysis_score = 80 if llm_used else 50

    # Valuation confidence: based on sensitivity spread
    val = result.get("valuation", {})
    val_result = val.get("result", val) if isinstance(val, dict) else {}
    sensitivity = val_result.get("sensitivity_matrix") if isinstance(val_result, dict) else None
    val_spread = 0
    if sensitivity and isinstance(sensitivity, dict):
        values = [v for row in sensitivity.values() if isinstance(row, dict) for v in row.values() if isinstance(v, (int, float))]
        if values:
            avg_val = sum(values) / len(values)
            val_spread = round((max(values) - min(values)) / avg_val * 100) if avg_val > 0 else 0
    valuation_score = 80 if val_spread < 30 else 60 if val_spread < 60 else 40

    overall = round((data_score * 0.35 + analysis_score * 0.35 + valuation_score * 0.30))

    return {
        "data_confidence": {"score": data_score, "agents": {k: v.get("quality", "?") for k, v in data_conf.items()}},
        "analysis_confidence": {"score": analysis_score, "llm_used": llm_used},
        "valuation_confidence": {"score": valuation_score, "sensitivity_spread_pct": val_spread},
        "overall": overall,
    }


# ── AI Q&A on reports ─────────────────────────────────────────

class AskRequest(BaseModel):
    question: str


@router.post("/report/{task_id}/ask")
async def ask_report(task_id: str, req: AskRequest):
    """Ask a follow-up question about a completed report. LLM answers with report context."""
    # Load report from MongoDB (handles post-restart access)
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        doc = await col.find_one({"_id": task_id})
        if not doc:
            raise HTTPException(404, "Report not found")
        result = doc.get("result", {})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Database error: {e}")

    # Build compact context from agent outputs
    sections_data = (result or {}).get("section_writer", {}).get("result", {}).get("sections", {})
    context_parts = []
    for sid, sdata in sections_data.items():
        title = sdata.get("title", sid)
        content = sdata.get("content", "")
        context_parts.append(f"## {title}\n{content[:800]}")
    context = "\n\n".join(context_parts[:6])  # Top 6 sections, truncated

    # Get LLM config
    import os
    from agents.analysis.llm_subprocess import call_llm
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    if not api_key:
        return {"answer": "LLM 未配置，无法回答追问。"}

    prompt = (
        f"你是一位投资分析师。以下是某只股票的研究报告内容：\n\n"
        f"{context}\n\n"
        f"用户追问：{req.question}\n\n"
        f"请基于以上报告上下文简洁回答。如果不确定就说'报告中未提供相关信息'。"
        f"用中文，控制在200字以内。"
    )
    answer = await call_llm(api_key, base_url, model, prompt, timeout=30)
    return {"answer": answer or "抱歉，无法生成回答。"}


# ── Compare mode ─────────────────────────────────────────────

class CompareRequest(BaseModel):
    tickers: list[str]  # e.g. ["600519.SH", "000858.SZ"]


@router.post("/report/compare")
async def compare_stocks(req: CompareRequest):
    """Compare key financial metrics across multiple stocks."""
    if len(req.tickers) < 2:
        raise HTTPException(400, "至少需要两只股票")
    if len(req.tickers) > 5:
        raise HTTPException(400, "最多支持5只股票对比")

    import os
    from datetime import date as dt_date

    end = dt_date.today()
    start = end.replace(year=end.year - 3)

    results = []
    for ticker in req.tickers:
        try:
            prices, financials = [], []
            is_cn = ".SH" in ticker.upper() or ".SZ" in ticker.upper()

            if is_cn:
                try:
                    from providers.tradingagents_provider import TradingAgentsProvider
                    ta = TradingAgentsProvider()
                    if await ta.health_check():
                        prices = await ta.get_prices(ticker, start, end) or []
                        financials = await ta.get_financials(ticker, years=3) or []
                except Exception:
                    pass

            if not financials:
                try:
                    from providers.qveris_provider import QverisProvider
                    qv = QverisProvider()
                    if await qv.health_check():
                        prices = await qv.get_prices(ticker, start, end) or []
                        financials = await qv.get_financials(ticker, years=3) or []
                except Exception:
                    pass

            if not financials:
                try:
                    from providers.akshare_provider import AkShareProvider
                    ak = AkShareProvider()
                    if await ak.health_check():
                        prices = await ak.get_prices(ticker, start, end) or []
                        financials = await ak.get_financials(ticker) or []
                except Exception:
                    pass

            # Build summary for this ticker
            latest = financials[-1] if financials else {}
            results.append({
                "ticker": ticker,
                "data": {
                    "prices_count": len(prices),
                    "latest_price": prices[-1].get("close") if prices else None,
                    "fin_summary": {k: v for k, v in latest.items() if isinstance(v, (int, float))},
                },
            })
        except Exception as e:
            results.append({"ticker": ticker, "error": str(e)})

    # LLM summary
    summary_text = ""
    try:
        from agents.analysis.llm_subprocess import call_llm
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if api_key:
            data = "\n".join(
                f"{r['ticker']}: {r.get('data', r.get('error', 'N/A'))}" for r in results
            )
            prompt = (
                f"以下是多只股票的基本财务数据对比：\n\n{data}\n\n"
                f"请用简洁中文总结关键差异（ROE、毛利率、负债水平等），控制在150字以内。"
            )
            summary_text = await call_llm(
                api_key,
                os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
                prompt,
                timeout=30,
            ) or ""
    except Exception:
        summary_text = "对比总结生成失败。"

    return {"comparison": results, "summary": summary_text}


# ── Watchlist CRUD ───────────────────────────────────────────

class WatchlistItem(BaseModel):
    ticker: str
    name: str | None = None


@router.get("/watchlist")
async def get_watchlist():
    """Get user's watchlist (current session / default user)."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        db = col.database
        wl_col = db["watchlist"]
        items = []
        async for doc in wl_col.find({}):
            items.append({"ticker": doc["_id"], "name": doc.get("name", "")})
        return {"watchlist": items}
    except Exception as e:
        logger.warning(f"Watchlist fetch failed: {e}")
        return {"watchlist": []}


@router.post("/watchlist")
async def add_to_watchlist(item: WatchlistItem):
    """Add a stock to watchlist."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        db = col.database
        wl_col = db["watchlist"]
        await wl_col.replace_one(
            {"_id": item.ticker},
            {"_id": item.ticker, "name": item.name or item.ticker, "added_at": datetime.now()},
            upsert=True,
        )
        return {"ok": True, "ticker": item.ticker}
    except Exception as e:
        raise HTTPException(500, f"Watchlist write failed: {e}")


@router.delete("/watchlist/{ticker}")
async def remove_from_watchlist(ticker: str):
    """Remove a stock from watchlist."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        db = col.database
        wl_col = db["watchlist"]
        await wl_col.delete_one({"_id": ticker})
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"Watchlist delete failed: {e}")


# ── Personal Research Archive ────────────────────────────────

@router.get("/archive")
async def get_archive(limit: int = 20):
    """Get user's archived research cards."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        db = col.database
        arc_col = db["archive"]
        items = []
        async for doc in arc_col.find({}).sort("archived_at", -1).limit(limit):
            items.append({
                "task_id": doc.get("task_id"),
                "ticker": doc.get("ticker"),
                "company_name": doc.get("company_name"),
                "verdict": doc.get("verdict"),
                "card_summary": doc.get("card_summary"),
                "archived_at": doc.get("archived_at").isoformat() if doc.get("archived_at") else None,
            })
        return {"archive": items, "total": await arc_col.count_documents({})}
    except Exception as e:
        return {"archive": [], "total": 0}


class ArchiveRequest(BaseModel):
    task_id: str


@router.post("/archive")
async def add_to_archive(req: ArchiveRequest):
    """Archive a report — create a research card with AI-generated summary."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        doc = await col.find_one({"_id": req.task_id})
        if not doc:
            raise HTTPException(404, "Report not found")

        # Generate card summary via LLM
        card_summary = ""
        try:
            import os
            from agents.analysis.llm_subprocess import call_llm
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            if api_key:
                sections = (doc.get("result") or {}).get("section_writer", {}).get("result", {}).get("sections", {})
                exec_summary = sections.get("executive_summary", {}).get("content", "")
                verdict_section = sections.get("final_judgment", {}).get("content", "")
                prompt = (
                    f"为以下研究报告生成一个80字以内的投研卡片摘要，包含：判定、核心理由、关键风险。\n\n"
                    f"投资摘要：{exec_summary[:500]}\n"
                    f"综合判定：{verdict_section[:500]}\n\n"
                    f"格式：判定: [Yes/No/Too Hard] | 核心理由: ... | 关键风险: ..."
                )
                card_summary = await call_llm(
                    api_key,
                    os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                    os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
                    prompt,
                    timeout=30,
                ) or ""
        except Exception:
            card_summary = ""

        db = col.database
        arc_col = db["archive"]
        verdict = doc.get("verdict", "Unknown")
        await arc_col.replace_one(
            {"_id": req.task_id},
            {
                "_id": req.task_id,
                "task_id": req.task_id,
                "ticker": doc.get("ticker"),
                "company_name": doc.get("company_name"),
                "verdict": verdict,
                "card_summary": card_summary or f"判定: {verdict} | 详情请查看完整报告",
                "archived_at": datetime.now(),
            },
            upsert=True,
        )
        return {"ok": True, "task_id": req.task_id, "card_summary": card_summary}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Archive failed: {e}")


# ── Simulated Portfolio ───────────────────────────────────────

class PortfolioPosition(BaseModel):
    ticker: str
    shares: int
    entry_price: float
    name: str | None = None
    task_id: str | None = None


@router.get("/portfolio")
async def list_portfolio():
    """List simulated portfolio positions with current market P&L."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        db = col.database
        port_col = db["portfolio"]
        items = []
        async for doc in port_col.find({}).sort("added_at", -1):
            ticker = doc["ticker"]
            entry_price = doc.get("entry_price", 0)
            shares = doc.get("shares", 0)
            cost_basis = entry_price * shares

            # Fetch current price
            current_price = None
            is_cn = ".SH" in ticker.upper() or ".SZ" in ticker.upper()
            if is_cn:
                try:
                    from providers.tradingagents_provider import TradingAgentsProvider
                    ta = TradingAgentsProvider()
                    from datetime import date as dt_date, timedelta
                    prices = await ta.get_prices(ticker, dt_date.today() - timedelta(days=5), dt_date.today())
                    if prices:
                        p = prices[-1]
                        current_price = p.get("close") if isinstance(p, dict) else p.close
                except Exception:
                    pass
            if not current_price:
                try:
                    from providers.qveris_provider import QverisProvider
                    prices = await qv.get_prices(ticker, None, None)
                    if prices and len(prices) > 0:
                        p = prices[-1]
                        current_price = p.get("close") if isinstance(p, dict) else p.close
                except Exception:
                    pass

            market_value = (current_price or 0) * shares
            pnl = market_value - cost_basis
            pnl_pct = round((pnl / cost_basis) * 100, 1) if cost_basis > 0 else 0

            items.append({
                "ticker": ticker,
                "name": doc.get("name", ticker),
                "shares": shares,
                "entry_price": entry_price,
                "current_price": current_price or 0,
                "cost_basis": round(cost_basis, 2),
                "market_value": round(market_value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": pnl_pct,
                "added_at": doc.get("added_at").isoformat() if doc.get("added_at") else None,
                "task_id": doc.get("task_id"),
            })

        total_pnl = sum(i["pnl"] for i in items)
        total_cost = sum(i["cost_basis"] for i in items)
        return {
            "positions": items,
            "summary": {
                "total_cost": round(total_cost, 2),
                "total_market_value": round(sum(i["market_value"] for i in items), 2),
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round((total_pnl / total_cost) * 100, 1) if total_cost > 0 else 0,
                "positions_count": len(items),
            }
        }
    except Exception as e:
        logger.warning(f"Portfolio list failed: {e}")
        return {"positions": [], "summary": {"total_pnl": 0, "total_pnl_pct": 0, "positions_count": 0}}


@router.post("/portfolio")
async def add_position(pos: PortfolioPosition):
    """Add a simulated position."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        db = col.database
        port_col = db["portfolio"]
        await port_col.replace_one(
            {"_id": pos.ticker},
            {
                "_id": pos.ticker,
                "ticker": pos.ticker,
                "shares": pos.shares,
                "entry_price": pos.entry_price,
                "name": pos.name or pos.ticker,
                "added_at": datetime.now(),
                "task_id": pos.task_id,
            },
            upsert=True,
        )
        return {"ok": True, "ticker": pos.ticker}
    except Exception as e:
        raise HTTPException(500, f"Portfolio add failed: {e}")


@router.delete("/portfolio/{ticker}")
async def close_position(ticker: str):
    """Close (remove) a simulated position."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        db = col.database
        port_col = db["portfolio"]
        await port_col.delete_one({"_id": ticker})
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, f"Portfolio close failed: {e}")


# ── Alerts ────────────────────────────────────────────────────

@router.get("/alerts")
async def get_alerts(limit: int = 10):
    """Get triggered price alerts, newest first."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        db = col.database
        alerts_col = db["alerts"]
        items = []
        async for doc in alerts_col.find({"triggered": True}).sort("triggered_at", -1).limit(limit):
            items.append({
                "ticker": doc.get("ticker"),
                "company_name": doc.get("company_name"),
                "type": doc.get("type"),
                "message": doc.get("message"),
                "current_price": doc.get("current_price"),
                "threshold": doc.get("threshold"),
                "triggered_at": doc.get("triggered_at").isoformat() if doc.get("triggered_at") else None,
            })
        return {"alerts": items}
    except Exception as e:
        logger.warning(f"Alerts fetch failed: {e}")
        return {"alerts": []}


@router.get("/alerts/count")
async def alert_count():
    """Get count of untriggered and recently triggered alerts."""
    try:
        from api.db import get_reports_collection
        col = await get_reports_collection()
        db = col.database
        alerts_col = db["alerts"]
        active = await alerts_col.count_documents({"triggered": False})
        recent = await alerts_col.count_documents({"triggered": True})
        return {"active": active, "recent_triggered": recent}
    except Exception as e:
        return {"active": 0, "recent_triggered": 0}


# ── SSE Stream ────────────────────────────────────────────────

@router.get("/report/{task_id}/stream")
async def task_stream(task_id: str, request: Request):
    """SSE stream for real-time progress updates."""
    async def event_generator():
        task = _tasks.get(task_id)
        if not task:
            yield f"event: error\ndata: Task not found\n\n"
            return

        last_phase = None
        last_event_idx = 0
        while task["status"] in ("queued", "running"):
            current_phase = task.get("current_phase")
            if current_phase != last_phase:
                last_phase = current_phase
                yield f"event: progress\ndata: {current_phase} ({task.get('progress_pct', 0)}%)\n\n"

            # Emit agent-level events
            events = task.get("events", [])
            while last_event_idx < len(events):
                ev = events[last_event_idx]
                last_event_idx += 1
                if ev.get("type") == "agent_completed":
                    agent = ev.get("agent", "")
                    status = ev.get("status", "")
                    detail = ev.get("detail", "")
                    import json as _json
                    yield f"event: agent_completed\ndata: {_json.dumps({'agent': agent, 'status': status, 'detail': detail}, ensure_ascii=False)}\n\n"

            if await request.is_disconnected():
                break
            await asyncio.sleep(0.5)

        if task["status"] == "completed":
            yield f"event: complete\ndata: {{\"task_id\": \"{task_id}\", \"status\": \"completed\"}}\n\n"
        elif task["status"] == "failed":
            yield f"event: error\ndata: {task.get('error', 'Unknown error')}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
