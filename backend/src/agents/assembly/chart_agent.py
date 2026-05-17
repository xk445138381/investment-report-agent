"""Chart Generator Agent — creates matplotlib charts for reports."""

import base64
from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


async def run_chart_agent(ticker, company_name, prices, financials, ctx_state=None):
    """Generate charts for the report. Returns list of ChartOutput dicts."""
    charts = []
    chart_id = 1

    # Price chart
    if prices:
        closes = [p.close for p in prices]
        dates = [p.date for p in prices]
        charts.append(_price_chart(ticker, dates, closes, chart_id))
        chart_id += 1

    # Simple bar chart for financial data
    if financials:
        latest = financials[-1]
        charts.append(_financial_chart(company_name, latest, chart_id))
        chart_id += 1

    return charts


def _price_chart(ticker, dates, closes, cid):
    fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
    ax.plot(range(len(closes)), closes, color="#2D2420", linewidth=1.2)
    ax.fill_between(range(len(closes)), closes, alpha=0.08, color="#C04A1A")
    ax.set_title(f"{ticker} 股价走势", fontsize=12, fontweight="bold")
    ax.set_xlabel("交易日")
    ax.set_ylabel("价格 (CNY)")
    ax.grid(alpha=0.2)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return {
        "chart_id": f"price_chart_{cid}", "title": f"{ticker} 股价走势",
        "caption": f"时间区间: {dates[0]} 至 {dates[-1]}",
        "png_base64": base64.b64encode(buf.getvalue()).decode(),
        "width_px": 800, "height_px": 400, "position": "company_overview",
    }


def _financial_chart(name, fs, cid):
    fig, ax = plt.subplots(figsize=(6, 3), dpi=100)
    labels = ["营收", "净利", "总资产", "净资产"]
    values = [fs.revenue or 0, fs.net_income or 0, fs.total_assets or 0, fs.total_equity or 0]
    # Scale to billions
    values_b = [v / 1e8 for v in values]
    colors = ["#2D2420", "#C04A1A", "#6B5E58", "#D4C5B9"]
    ax.bar(labels, values_b, color=colors)
    ax.set_title(f"{name} 核心财务指标（亿元）", fontsize=12, fontweight="bold")
    ax.grid(alpha=0.2, axis="y")
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return {
        "chart_id": f"financial_chart_{cid}", "title": f"{name} 财务概览",
        "caption": "基于最新财报数据", "png_base64": base64.b64encode(buf.getvalue()).decode(),
        "width_px": 600, "height_px": 300, "position": "financial_analysis",
    }
