# 投资报告 Agent

## 项目概述

多 Agent AI 投研系统。两个核心 pipeline：**价值投资深度研报**（段永平+芒格双视角 14 Agent / 8 章）和**快速扫描**（技术面+资金面+LLM 一句话总结 6 Agent / 单页卡片）。额外保留传统多空辩论深度研报 pipeline。

- **仓库**: https://github.com/xk445138381/investment-report-agent
- **Python**: >=3.12
- **前端**: Next.js 16 + React 19 + Tailwind
- **后端**: FastAPI + uvicorn
- **LLM**: DeepSeek V4 Pro（子进程调用，绕过 uvicorn/asyncio 问题）

## 架构

### Pipeline 全景

```
┌──────────────────────────────────────────────────┐
│ quick_scan (6 Agent, ~30s)                       │
│ Phase 1: 行情+财报+技术+资金+新闻 (并行)           │
│ Phase 2: LLM一句话总结                            │
├──────────────────────────────────────────────────┤
│ value_deep_dive (14 Agent, ~3min)                │
│ Phase 1: 行情+财报+新闻+宏观 (并行)               │
│ Phase 2: 财务分析+估值+行业+治理 (并行)           │
│ Phase 3a: 段永平+芒格 (并行 LLM)                  │
│ Phase 3b: 双视角裁决 (LLM)                        │
│ Phase 4: 统稿+图表+摘要                           │
├──────────────────────────────────────────────────┤
│ deep_dive (14 Agent, ~2min)                      │
│ Phase 1-2: 同上                                  │
│ Phase 3: 多头+空头+裁判 (传统辩论)                 │
│ Phase 4: 同上                                    │
└──────────────────────────────────────────────────┘
```

### 数据源（CN 优先走 TradingAgents，QVeris fallback）

| 市场 | 行情 | 财报 | 治理 | 新闻 | 宏观 | 资金流 |
|------|------|------|------|------|------|--------|
| A股 | TradingAgents(Sina HTTP) / QVeris(THS) | QVeris(THS) / TradingAgents(Sina) | AkShare 前十大股东 | Caidazi | Caidazi | TradingAgents(东财) |
| 港股 | QVeris(PolySource 日线) | AkShare(指标推导BS) | AkShare(公司信息) | Caidazi | Caidazi | — |
| 美股 | Alpha Vantage | Alpha Vantage | Yahoo Finance | Caidazi | Caidazi | — |

**数据获取链**: TradingAgents(CN only) → QVeris → AkShare → continue without data

### 关键路径

- `backend/src/agents/orchestrator.py` — 主编排，dispatch→agent 实现
- `backend/src/agents/analysis/duan_agent.py` — 段永平视角 LLM Agent
- `backend/src/agents/analysis/munger_agent.py` — 芒格视角 LLM Agent
- `backend/src/agents/analysis/llm_subprocess.py` — 子进程 LLM 调用（绕过 uvicorn 网络问题）
- `backend/src/agents/assembly/section_writer_agent.py` — 报告章节渲染（value/deep_dive 两套）
- `backend/src/providers/qveris_provider.py` — QVeris API 数据网关
- `backend/src/providers/tradingagents_provider.py` — TradingAgents-astock 数据包装
- `backend/src/config/loader.py` — 配置加载 + LLMRegistry
- `backend/config.json` — 全局配置（pipeline/agent/LLM 全可配）
- `frontend/app/page.tsx` — 首页（三模式选择）
- `frontend/app/report/page.tsx` — 报告页（value/deep/scan 自适应）
- `H:\TradingAgents-astock-0.2.11\tradingagents\dataflows\a_stock.py` — CN 数据源（mootdx/腾讯/东财/新浪/同花顺/财联社 直连 HTTP）
- `H:\TradingAgents-astock-0.2.11\tradingagents\agents\analysts\` — 7 个 A 股特化 Analyst（可复用）

### LLM 调用

所有 Agent 的 LLM 调用走 `llm_subprocess.py`——启独立 Python 子进程调 DeepSeek API，输出通过 stdout 捕获。避开了 uvicorn 下 httpx/asyncio 的 CancelledError。

`call_llm(api_key, base_url, model, prompt, timeout)` → `str | None`

关键修复：`subprocess.run(encoding="utf-8")` + `PYTHONUTF8=1` —— Windows 默认 GBK 会导致中文乱码。

### 报告模板

- `backend/src/templates/value_investor.json` — 8 章：摘要/商业模式/企业文化/财务/估值/逆向风险/双视角裁决/综合判定
- `backend/src/templates/deep_dive.json` — 7 章传统研报

## 已知问题

### LLM 网络（DeepSeek）
DeepSeek API 在 uvicorn 内 httpx 异步调用会触发 CancelledError（HTTP 200 但 body 读中断）。已通过子进程方案解决。备选方案：拿到 GPT-4o/Claude key 切 provider_heavy。

### mootdx TCP 不可用
TradingAgents 的 `resolve_ticker` 依赖 mootdx(TCP 7709)，当前环境不一定通。health_check 已改用腾讯 HTTP。价格数据自动 fallback 到 Sina HTTP。

### Windows 环境
- `subprocess.run(text=True)` 默认 GBK 编码 → 必须显式 `encoding="utf-8"`
- `Start-Process` 不自动继承 `$env:` 变量 → 用 `load_dotenv()` 处理或 Bash `export`
- .env 文件 CRLF 换行 → shell 提取 key 需 `tr -d '\r'`

### 东财接口限流
TradingAgents-astock 的 `a_stock.py` 对 eastmoney.com 做了节流（`_em_get()`，默认 1.0s 间隔 + 抖动）。批量调用时注意。

## 开发规范

- 改动后跑 `python -m pytest tests/unit/ -v` 确保 81/82 通过
- config.json 驱动一切，新增 pipeline/agent 优先改配置
- 报告模板放 `backend/src/templates/`，JSON 定义章节结构
- LLM 调用走 `llm_subprocess.call_llm()`，不要直接用 langchain
- 数据 Agent 不需要 LLM（纯数据获取/计算）
- 环境变量从 `backend/.env` 加载，key 命名 `*_API_KEY`
