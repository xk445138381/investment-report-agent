# 投资报告 Agent — 完整产品与架构方案

> 基于 13 轮决策访谈 + ai-hedge-fund / TradingAgents-CN 深度源码分析
> 最后更新: 2026-05-16

---

## 目录

1. [产品决策汇总](#一产品决策汇总)
2. [竞品深度解剖](#二竞品深度解剖)
3. [数据来源详细规格](#三数据来源详细规格)
4. [系统架构](#四系统架构)
5. [Agent 详细设计](#五agent-详细设计)
6. [Python 计算层规格](#六python-计算层规格)
7. [API 与数据模型](#七api-与数据模型)
8. [UI/UX 交互设计](#八uiux-交互设计)
9. [报告模板系统](#九报告模板系统)
10. [测试与质量保证策略](#十测试与质量保证策略)
11. [MVP Phase 1 交付物清单](#十一mvp-phase-1-交付物清单)
12. [风险与缓解](#十二风险与缓解)

---

## 一、产品决策汇总

| # | 决策维度 | 结论 | 理由 |
|---|---------|------|------|
| 1 | 投资标的 | 一级市场 + 股票（A/港/美）+ 宏观/大类资产 | 覆盖完整投资链条，从早期到二级到顶层配置 |
| 2 | 目标用户 | 专业机构（PE/VC/基金/券商研究员）+ 投行/FA | 付费意愿最强、需求最高频、ROI 最直接 |
| 3 | 核心工作流 | 全能力覆盖，MVP 以**个股深度报告**为突破口 | 个股研报是研究员最大日常痛点，最标准化 |
| 4 | 数据来源 | 混合策略：用户上传 + 公开源 + 后续接专业终端 | MVP 零外部依赖验证 PMF，架构预留 provider 接口 |
| 5 | 产品形态 | Web 应用（对话 + 预览 + 下载），后期加 API | 分发成本最低、跨平台、对话式交互最友好 |
| 6 | 报告生成架构 | **多 Agent 管线 + 模板引擎** | 质量可控、格式一致、可审计 |
| 7 | Agent 框架 | **Claude Agent SDK**（SubAgent / Skill / Worktree） | 已在此生态，天然支持多 Agent 编排和 Skill 复用 |
| 8 | 输出格式 | Web 预览 + PDF + Word | 机构内部流转靠 Word，对外分发靠 PDF |
| 9 | 商业模式 | Freemium SaaS（免费 3 份/月）+ 私有化部署 | 先 SaaS 验证 PMF，大客户谈私有化大单 |
| 10 | 技术栈 | Python 后端（FastAPI）+ React 前端（Next.js） | Python 金融生态无可替代，React 交互体验最佳 |
| 11 | MVP 范围 | Phase 1: 单标的深度报告（4-6 周） | Phase 2 批量+交易材料，Phase 3 私有化+API |
| 12 | 模板灵活度 | 用户自定义模板（JSON 定义章节结构） | 机构报告格式有强定制需求，模板即产品功能 |
| 13 | 部署策略 | 先 SaaS 快跑验证 PMF，Day 1 架构预留私有化 | 出海前先跑通，不做过度工程 |
| 14 | 可配置架构 | JSON 配置驱动一切 + Web UI 可视化编辑 (Phase 2) | Agent/LLM/数据源/工作流全部可编辑，低门槛与灵活性兼得 |
| 15 | 数据查询策略 | 本地数据库优先 (Local-First) → 外部 API → 缓存兜底 | 减少外部依赖、提速、降成本、离线可用 |

---

## 二、竞品深度解剖

### 2.1 ai-hedge-fund — 完整架构分析

#### 2.1.1 项目概况

- **定位**：教育性质的 AI 对冲基金模拟，非实盘
- **Star**：~7k，社区活跃
- **语言**：Python 62.3% + TypeScript 33.8%
- **许可证**：MIT
- **核心依赖**：LangGraph + LangChain + Poetry + Docker

#### 2.1.2 文件结构

```
src/
├── agents/           # 22 个 Agent 文件
│   ├── valuation.py          # 估值 Agent — 4 模型纯 Python 计算
│   ├── fundamentals.py       # 基本面 — 4 维度评分（ROE/负债率/利润率/流动比率）
│   ├── sentiment.py          # 市场情绪
│   ├── technicals.py         # 技术分析
│   ├── news_sentiment.py     # 新闻情绪（LLM 驱动）
│   ├── risk_manager.py       # 风控 — 波动率+相关性双重调整
│   ├── portfolio_manager.py  # 组合经理 — 最终决策，Pydantic schema 约束
│   ├── growth_agent.py       # 增长型投资者人格
│   └── [13 个投资大师 Agent]  # Buffett、Graham、Lynch、Dalio...
├── graph/
│   ├── state.py              # AgentState: messages + data + metadata
│   └── [LangGraph 图定义在 main.py 中动态构建]
├── tools/
│   └── api.py                # Financial Datasets API 封装 + 缓存
├── llm/
│   └── models.py             # LLM 抽象层（OpenAI / Groq / Anthropic / DeepSeek）
├── backtesting/              # 回测引擎
├── main.py                   # CLI 入口 + StateGraph 构建
└── backtester.py             # 回测 CLI
```

#### 2.1.3 Agent 源码逐层拆解

**State 设计** — `src/graph/state.py`：

```python
def merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]  # 累加模式
    data: Annotated[dict[str, any], merge_dicts]              # 合并模式
    metadata: Annotated[dict[str, any], merge_dicts]
```

- `messages` 用 `operator.add` 做 append-only 累加。每个 Agent 追加自己的 HumanMessage，形成完整的推理链条。
- `data` 用 dict merge（后者覆盖前者）。当前 Agent 可以覆盖之前 Agent 的同名字段。
- `metadata` 同 data。
- **设计评价**：简单够用，但所有 Agent 共享一个扁平 dict 做通信，key 名完全靠约定（如 `analyst_signals`）。没有编译期类型检查。对于报告生成场景（需要多个不同类型的结构化产出），建议用嵌套 State 分离关注点。

**估值 Agent 源码分析** — `src/agents/valuation.py`：

核心函数 `valuation_analyst_agent(state)` 的执行流：

```
1. 遍历 state["data"]["tickers"]
2. 对每个 ticker:
   a. 调用 get_financial_metrics(ticker) → 获取 ROE、净利润率、FCF 等
   b. 调用 search_line_items(ticker, ["free_cash_flow", "net_income", ...])
      → 获取详细财报行项目
   c. 运行 4 个估值模型（纯 Python，不经过 LLM）：
      
      模型 1: Owner Earnings (Buffett 风格)
      ─────────────────────────────────────
      owner_earnings = net_income + depreciation - maintenance_capex - Δworking_capital
      用 5 年 DCF + 永续增长终端价值
      折现率 9%，margin_of_safety = 25%
      
      模型 2: Enhanced DCF（三阶段增长）
      ─────────────────────────────────────
      WACC 通过 CAPM 计算:
        cost_of_equity = risk_free + beta * equity_risk_premium
        cost_of_debt = 利息覆盖率映射
      FCF 增长率: 高增长期 5 年 → 过渡期 5 年 → 永续
      三种情景（熊/基/牛）概率加权 (20/60/20)
      熊: growth × 0.8, WACC × 1.2
      牛: growth × 1.2, WACC × 0.8
      
      模型 3: EV/EBITDA（市场法）
      ─────────────────────────────────────
      median_ev_ebitda = 同行业/市场历史中位数
      implied_enterprise_value = median_ev_ebitda × EBITDA
      equity_value = enterprise_value - net_debt
      
      模型 4: Residual Income（Edwards-Bell-Ohlson）
      ─────────────────────────────────────
      residual_income = net_income - (equity_capital × cost_of_equity)
      terminal_value 用永续增长折现
      margin_of_safety = 20%
      
   d. 加权聚合:
      weighted_value = 0.35×DCF + 0.35×Owner_Earnings + 0.20×EV_EBITDA + 0.10×RI
      gap = (weighted_value - market_cap) / market_cap
      
   e. 信号生成:
      gap > 15% → bullish, confidence = min(100, gap×100)
      gap < -15% → bearish, confidence = min(100, -gap×100)
      否则 → neutral
      
   f. 结果写入 state["data"]["analyst_signals"][ticker]["valuation"]
```

**估值计算的辅助函数**（都在 Python 中，不经过 LLM）：

- `calculate_owner_earnings_value()` — 5 年显式 DCF + 终端价值
- `calculate_intrinsic_value()` — 经典恒定增长 DCF
- `calculate_ev_ebitda_value()` — 行业中位数方法
- `calculate_residual_income_value()` — RI 模型 + 终端价值
- `calculate_wacc()` — CAPM（权益成本）+ 利息覆盖率映射（债务成本）
- `calculate_fcf_volatility()` — 变异系数
- `calculate_enhanced_dcf_value()` — 三阶段增长模型
- `calculate_dcf_scenarios()` — 熊/基/牛三情景

**关键洞察**：这些计算全是 `statistics.mean()`、`sum()`、`math.pow()` 级别的操作。没有用到任何专业金融库。这说明：对于 MVP，不需要 Bloomberg Terminal 级别的建模精度，核心公式手写即可。但这也意味着：参数（WACC、增长假设、倍率）写死在代码里，不可配。

**巴菲特 Agent 源码分析** — `src/agents/warren_buffett.py`：

该 Agent 是"Python 评分 + LLM 叙事"的最佳案例：

```python
class WarrenBuffettSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: int  # 0-100
    reasoning: str

def warren_buffett_agent(state, agent_id):
    for ticker in tickers:
        metrics = get_financial_metrics(ticker)
        line_items = search_line_items(ticker, [...])

        # ── 5 个纯 Python 评分函数 ──
        scores = {}
        scores["fundamentals"] = analyze_fundamentals(metrics)
            # ROE > 15% → 3pts, 负债率 < 0.5 → 3pts,
            # 营业利润率 > 15% → 2pts, 流动比率 > 1.5 → 2pts
            # 满分 10pts

        scores["moat"] = analyze_moat(metrics)
            # ROE 3年均值>15% → 2pts, 利润率稳定性 → 1pt,
            # 资产效率(收入/资产>0.8) → 1pt, 稳定性指标 → 1pt
            # 满分 5pts

        scores["consistency"] = analyze_consistency(line_items)
            # 收入同比增长趋势 → 2pts, EPS 增长稳定性 → 1pt
            # 满分 3pts

        scores["management"] = analyze_management_quality(line_items)
            # 股票回购(净减少) → 1pt, 股息支付历史 → 1pt
            # 满分 2pts

        scores["pricing_power"] = analyze_pricing_power(line_items, metrics)
            # 毛利率 > 40% → 3pts, 毛利率趋势上升 → 2pts
            # 满分 5pts

        owner_earnings = calculate_owner_earnings(line_items)
        intrinsic_value = calculate_intrinsic_value(line_items, owner_earnings)
        book_value_growth = analyze_book_value_growth(line_items)

        # ── LLM 调用：综合评分 + 生成 reasoning ──
        analysis_data = {
            "scores": scores,
            "owner_earnings": owner_earnings,
            "intrinsic_value": intrinsic_value,
            "book_value_growth": book_value_growth,
        }
        signal = generate_buffett_output(ticker, analysis_data, state, agent_id)
        # → LLM 看到的是完整的结构化评分，任务只是"用 Buffett 风格总结"
```

**prompt 结构**（`generate_buffett_output`）：
```
System: 你是 Warren Buffett，以价值投资视角评估 {ticker}。
        以下是对这家公司的完整分析数据：
        - 基本面评分: {scores}
        - Owner Earnings: {owner_earnings}
        - 内在价值: {intrinsic_value} vs 当前市值: {market_cap}
        
        请给出你的投资判断：买入/卖出/持有，以及推理。
        输出格式必须遵守给定的 JSON schema。

Human: 这是分析数据，请给出你的判断。
```

**组合经理 Agent** — `src/agents/portfolio_manager.py`：

这是最终决策 Agent，展示了如何用 Pydantic 约束 LLM 输出：

```python
class PortfolioDecision(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int
    confidence: int          # 0-100
    reasoning: str           # max 100 chars

class PortfolioManagerOutput(BaseModel):
    decisions: dict[str, PortfolioDecision]  # ticker → decision

def portfolio_management_agent(state, agent_id):
    # 1. 提取前面所有 Agent 的信号
    signals_by_ticker = compress_signals(state["data"]["analyst_signals"])
    # 只保留 {agent_name: {signal, confidence}}，去掉长 reasoning
    
    # 2. 计算每个 ticker 的允许操作
    # - buy: 受限于可用现金
    # - sell: 受限于现有持仓
    # - short: 受限于保证金要求
    # 去掉容量为 0 的操作，但总是保留 "hold"
    
    # 3. 如果某 ticker 只有 "hold" 可选，预填充并从 LLM prompt 中移除
    # 减少 LLM 的决策空间
    
    # 4. 构建 prompt → LLM → 解析 PortfolioDecision
    # Pydantic 做类型校验，失败则 fallback 到 "hold"
```

**风控 Agent** — `src/agents/risk_manager.py`：

纯 Python 风控计算引擎，不经过 LLM：

```
1. 获取所有 ticker 的价格数据 → calculate_volatility_metrics()
   - 最近 60 天日收益率 → 年化波动率
   - 30 天滚动波动率 vs 历史滚动波动率的百分位排名
   - 数据不足时 fallback 到默认 5% 日波动率

2. 相关性矩阵计算（需要至少 2 个 ticker 和 5 个观测值）
   - NaN 处理：缺失数据取 0.5 中等相关性

3. 组合净清算价值 = 现金 + 多头市值 - 空头市值

4. 波动率调整限额:
   base = 组合价值的 20%
   multiplier = f(年化波动率)
     波动率 < 20% → ×1.25
     波动率 20-40% → ×1.0
     波动率 40-60% → ×0.67
     波动率 60-80% → ×0.5
     波动率 > 80% → ×0.25
   limit = base × multiplier  (最终在 5%-25% 之间)

5. 相关性调整:
   avg_corr > 0.8 → ×0.7   (与现有持仓高度相关，降低仓位)
   avg_corr 0.2-0.8 → ×1.0
   avg_corr < 0.2 → ×1.10  (低相关，分散化加分)

6. 最终 remaining_position_limit = min(vol_limit, corr_limit, available_cash)
```

#### 2.1.4 数据层分析

**`src/tools/api.py`** — 所有数据通过 Financial Datasets API 单一入口：

```
函数签名：
  get_prices(ticker, start_date, end_date) → list[Price] → pd.DataFrame
  get_financial_metrics(ticker, period, limit) → list[FinancialMetrics]
  search_line_items(ticker, line_items, period, limit) → list[LineItem]
  get_insider_trades(ticker, start_date, end_date) → list[InsiderTrade]
  get_company_news(ticker, start_date, end_date) → list[CompanyNews]
  get_market_cap(ticker, end_date) → float

缓存策略：
  - 每个函数的缓存 key = f"{func_name}:{ticker}:{params_hash}"
  - 所有 GET 函数缓存结果（包括 get_financial_metrics / get_prices）
  - 唯一不缓存的是 search_line_items（因为行项目数据"太动态"）
  
限流处理：
  - HTTP 429 → 线性退避，起始 60s
  - 重试逻辑在 _make_api_request() 中统一处理

Pydantic 数据模型：
  Price(time, open, high, low, close, volume)
  FinancialMetrics(ticker, report_period, period, currency,
    market_cap, enterprise_value, price_to_earnings_ratio, 
    price_to_book_ratio, price_to_sales_ratio,
    enterprise_value_to_ebitda, enterprise_value_to_revenue,
    free_cash_flow_yield, peg_ratio, gross_margin,
    operating_margin, net_margin, current_ratio, 
    debt_to_equity, return_on_equity, return_on_assets,
    return_on_invested_capital, asset_turnover,
    free_cash_flow_to_revenue, revenue_growth,
    earnings_growth, book_value_growth,
    earnings_per_share, eps_diluted,
    payout_ratio, tangible_asset_value,
    net_debt_to_ebitda, interest_coverage, working_capital)
  LineItem(ticker, report_period, period, line_item, value, unit, currency)
  InsiderTrade(ticker, issuer, name, title, is_board_director, 
    transaction_date, transaction_shares, transaction_price_per_share,
    transaction_value, shares_owned_before_transaction,
    shares_owned_after_transaction, security_title, filing_date)
  CompanyNews(ticker, title, author, source, date, url, sentiment)
```

**数据层的局限**：
- 单一 API 供应商绑定，API key 过期/限额则整个系统不可用
- 没有多数据源降级
- 中国 A 股数据完全无法获取（Financial Datasets 不支持中国市场）
- `search_line_items` 不支持缓存 → 同一 ticker 重复查询每次都要请求 API

#### 2.1.5 图编排分析

**图构建**（`src/main.py` 中的 `create_workflow(selected_analysts)`）：

```python
workflow = StateGraph(AgentState)
workflow.add_node("start", start)          # no-op
for analyst in selected_analysts:
    workflow.add_node(analyst, agent_func)
workflow.add_node("risk_manager", risk_management_agent)
workflow.add_node("portfolio_manager", portfolio_management_agent)

workflow.add_edge(START, "start")
for i, analyst in enumerate(selected_analysts):
    if i == 0:
        workflow.add_edge("start", analyst)
    else:
        workflow.add_edge(selected_analysts[i-1], analyst)
workflow.add_edge(selected_analysts[-1], "risk_manager")
workflow.add_edge("risk_manager", "portfolio_manager")
workflow.add_edge("portfolio_manager", END)
```

**关键特征**：
- 所有分析师 **串行执行**（不是并行）。前一个 Agent 的输出通过 `messages` 字段传递给下一个
- 没有条件边（conditional edge）— 所有 Agent 总是执行，没有跳过逻辑
- 没有工具节点（ToolNode）— Agent 直接调 API 函数，不通过 LangGraph 的工具调用机制
- 没有辩论循环 — Agent 之间单向传递，无反馈

#### 2.1.6 LLM 抽象层

支持的 LLM 提供商（通过环境变量切换）：
```
OpenAI (gpt-4o, gpt-4o-mini)
Groq (llama-3.3-70b)
Anthropic (claude-3-5-sonnet, claude-3-opus)
DeepSeek (deepseek-chat)
Ollama (本地模型，通过 --ollama flag)
```

用一个 `models.py` 统一所有 LLM 调用，`call_llm(prompt, model_config)` 函数屏蔽底层差异。

### 2.2 TradingAgents-CN — 完整架构分析

#### 2.2.1 项目概况

- **定位**：中文多 Agent 股票分析学习平台，覆盖 A 股/港股/美股
- **Star**：~4k
- **语言**：Python 82.1% + Vue 10.0% + TypeScript 1.9%
- **许可证**：核心 `tradingagents/` Apache 2.0，`app/` + `frontend/` 专有（商业需授权）
- **核心依赖**：LangGraph + LangChain + FastAPI + Vue 3 + MongoDB + Redis + Docker
- **v2.0 状态**：已闭源（因盗版问题）
- **部署**：Docker 多架构（amd64 + arm64），GitHub Actions 自动构建

#### 2.2.2 完整文件结构

```
TradingAgents-CN/
├── tradingagents/              # 核心多 Agent 框架（开源，Apache 2.0）
│   ├── agents/
│   │   ├── analysts/           # 4 个数据采集分析 Agent
│   │   │   ├── market_analyst.py           # 技术指标 + 行情分析
│   │   │   ├── fundamentals_analyst.py     # 基本面（PE/PB/ROE...）
│   │   │   ├── news_analyst.py             # 新闻分析
│   │   │   ├── social_media_analyst.py     # 社交媒体情绪
│   │   │   └── china_market_analyst.py     # A 股专用行情分析
│   │   ├── researchers/        # 2 个辩论 Agent
│   │   │   ├── bull_researcher.py         # 看涨研究员
│   │   │   └── bear_researcher.py         # 看跌研究员
│   │   ├── managers/           # 2 个裁判 Agent
│   │   │   ├── research_manager.py        # 辩论裁判（投资组合经理）
│   │   │   └── risk_manager.py            # 风控裁判
│   │   ├── trader/
│   │   │   └── trader.py                  # 交易执行 Agent
│   │   ├── risk_mgmt/          # 3 个风控辩手
│   │   │   ├── aggresive_debator.py       # 激进风控观点
│   │   │   ├── conservative_debator.py    # 保守风控观点
│   │   │   └── neutral_debator.py         # 中性风控观点
│   │   └── utils/              # Agent 工具函数
│   ├── graph/                  # LangGraph 图定义和编排
│   │   ├── trading_graph.py              # 主编排类 TradingAgentsGraph
│   │   ├── setup.py                       # GraphSetup — 图构建
│   │   ├── conditional_logic.py           # 6 个路由条件函数
│   │   ├── propagation.py                 # 状态传播
│   │   ├── reflection.py                  # 反思与记忆更新
│   │   └── signal_processing.py           # 三级 fallback 信号处理
│   ├── dataflows/              # 数据层（最核心的差异化能力）
│   │   ├── providers/          # 数据源适配器
│   │   │   ├── china/
│   │   │   │   ├── tushare.py            # Tushare 接口
│   │   │   │   ├── akshare.py            # AkShare 接口
│   │   │   │   ├── baostock.py           # BaoStock 接口
│   │   │   │   ├── tdx.py                # 通达信接口
│   │   │   │   └── fundamentals_snapshot.py  # 基本面快照
│   │   │   ├── hk/
│   │   │   │   ├── hk_stock.py
│   │   │   │   └── improved_hk.py
│   │   │   ├── us/
│   │   │   │   ├── yfinance.py
│   │   │   │   ├── finnhub.py
│   │   │   │   └── optimized.py
│   │   │   └── base_provider.py          # Provider 抽象基类
│   │   ├── cache/             # 多层缓存
│   │   │   ├── file_cache.py
│   │   │   ├── db_cache.py
│   │   │   ├── adaptive.py
│   │   │   ├── integrated.py
│   │   │   ├── app_adapter.py
│   │   │   └── mongodb_cache_adapter.py
│   │   ├── news/
│   │   │   ├── google_news.py
│   │   │   ├── realtime_news.py
│   │   │   ├── reddit.py
│   │   │   └── chinese_finance.py
│   │   ├── technical/
│   │   │   └── stockstats.py
│   │   ├── data_source_manager.py        # 数据源路由和降级
│   │   ├── data_completeness_checker.py  # 数据完整性检查
│   │   ├── interface.py                  # 统一接口
│   │   └── stock_api.py                  # StockAPI 入口
│   ├── tools/                # Agent 工具
│   │   ├── analysis/
│   │   └── unified_news_tool.py
│   ├── llm_clients/          # LLM 客户端抽象
│   ├── models/               # 数据模型
│   ├── config/               # 配置管理
│   └── utils/                # 工具函数
├── app/                      # FastAPI 后端（专有）
├── frontend/                 # Vue 3 前端（专有）
├── cli/                      # CLI 工具
├── config/                   # 全局配置
├── docker/                   # Docker 编排
├── scripts/                  # 运维脚本
├── tests/                    # 测试
└── reports/                  # 生成的报告存储
```

#### 2.2.3 图编排 — 最核心的架构层

**`setup.py: GraphSetup.setup_graph()` 完整图结构：**

```
START
  │
  ▼
┌─────────────┐     ┌──────────┐     ┌─────────────┐    ┌──────────────┐
│  Market      │────▶│  Msg     │────▶│  Social     │───▶│  Msg         │
│  Analyst     │     │  Clear   │     │  Media      │    │  Clear       │
│              │◀───▶│          │     │  Analyst    │◀──▶│              │
│              │(loop)│          │     │             │(lp)│              │
└─────────────┘     └──────────┘     └─────────────┘    └──────────────┘
       │                                                         │
       │  tool calls ≤ 3 次 + report > 100 chars                  │
       │  满足条件 → 跳转到下一个分析师                               │
       ▼                                                         ▼
┌─────────────┐     ┌──────────┐     ┌──────────────┐   ┌──────────────┐
│  News        │────▶│  Msg     │────▶│ Fundamentals │──▶│  Msg         │
│  Analyst     │     │  Clear   │     │  Analyst     │   │  Clear       │
│              │◀───▶│          │     │              │◀─▶│              │
│              │(loop│          │     │(max 1 tool   │   │              │
└─────────────┘     └──────────┘     │  call)       │   └──────────────┘
                                     └──────────────┘         │
                                                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                     辩论阶段                                       │
    │  ┌──────────────┐          ┌──────────────┐                      │
    │  │  Bull         │─────────▶│  Bear        │  ← should_continue_ │
    │  │  Researcher   │          │  Researcher  │    _debate():       │
    │  │               │◀─────────│              │    交替路由直到      │
    │  └──────────────┘          └──────────────┘    count ≥ 2×N轮     │
    │        │                          │                              │
    │        └──────────┬───────────────┘                              │
    │                   ▼                                              │
    │          ┌────────────────┐                                      │
    │          │  Research       │  ← deep_thinking_llm                │
    │          │  Manager        │     裁决辩论、输出投资计划             │
    │          │  (辩论裁判)      │     包含目标价格（1/3/6月）            │
    │          └────────────────┘                                      │
    └──────────────────────┬───────────────────────────────────────────┘
                           ▼
                    ┌──────────┐
                    │  Trader   │  ← 交易员根据投资计划制定具体执行方案
                    └──────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                     风控辩论阶段                                    │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
    │  │  Risky        │─▶│  Safe         │─▶│  Neutral      │          │
    │  │  Analyst      │  │  Analyst      │  │  Analyst      │          │
    │  │  (激进)       │◀─│  (保守)       │◀─│  (中性)       │          │
    │  └──────────────┘  └──────────────┘  └──────────────┘            │
    │        │                  │                  │                    │
    │        └──────────────────┼──────────────────┘                    │
    │                           ▼                                      │
    │                  ┌────────────────┐                              │
    │                  │  Risk Judge     │  ← deep_thinking_llm         │
    │                  │  (风控裁判)      │     终审判定风险              │
    │                  └────────────────┘                              │
    └──────────────────────────┬───────────────────────────────────────┘
                               ▼
                              END
```

**每个分析师节点的内部循环逻辑**（以 Market Analyst 为例）：

```
Market Analyst → LLM 调用（可能产生 tool_call）
  → conditional edge: should_continue_market()
    ├─ 有 tool_call 且 tool_call_count < 3 → tools_market → Market Analyst (循环)
    └─ 无 tool_call 或 count >= 3 → Msg Clear Market → 下一个分析师
```

每个分析师在跳转到下一个之前会先经过一个 `Msg Clear` 节点（去掉中间消息以节省上下文），然后才进入下一个分析师。

**辩论路由逻辑** — `conditional_logic.py: should_continue_debate()`：

```python
def should_continue_debate(self, state):
    count = state["investment_debate_state"]["count"]
    current_response = state["investment_debate_state"]["current_response"]
    
    if count >= 2 * self.max_debate_rounds:  # 默认 2 轮
        return "Research Manager"             # 辩论结束 → 裁判
    
    if current_response == "Bear Researcher":
        return "Bull Researcher"              # 熊发完 → 牛回应
    else:
        return "Bear Researcher"              # 牛发完 → 熊回应
```

**风控辩论路由逻辑** — `should_continue_risk_analysis()`：

```python
def should_continue_risk_analysis(self, state):
    count = state["risk_debate_state"]["count"]
    current_response = state["risk_debate_state"]["current_response"]
    
    if count >= 3 * self.max_risk_discuss_rounds:  # 3 个辩手 × N 轮
        return "Risk Judge"
    
    # 三人循环: risky → safe → neutral → risky → ...
    speakers = {
        "Risky Analyst": "Safe Analyst",
        "Safe Analyst": "Neutral Analyst", 
        "Neutral Analyst": "Risky Analyst"
    }
    return speakers.get(current_response, "Risky Analyst")
```

#### 2.2.4 Agent Prompt 逐层分析

**Bull Researcher 的 prompt 结构**（精简版还原）：

```
你是 {看涨/看跌} 分析师。

## 约束
- 始终使用公司名称 "{company_name}" 而不是股票代码
- 价格使用 {currency} 计价 ({currency_symbol})
- 用中文回复

## 分析要求（5 个维度）
1. 增长潜力 — 公司的核心增长驱动因素
2. 竞争优势 — 护城河在哪里 
3. 积极/消极指标 — 数据支撑
4. 反驳对方观点 — 用具体数据和合理推理批判性分析
5. 参与讨论 — 以对话风格直接回应对方

## 可用资源
- 市场研究报告: {market_report}
- 情绪分析: {sentiment_report}
- 新闻分析: {news_report}
- 基本面分析: {fundamentals_report}
- 辩论历史: {history}
- 上一次对方论点: {current_response}
- 历史反思: {past_memory_str}

## 标的约束
{instrument_context}  # 包含市场、货币、交易规则等
```

**Research Manager（辩论裁判）的 prompt 结构**：

```
作为投资组合经理和辩论主持人，评估这轮辩论并做出明确决策：
支持看跌、看涨，或持有——仅在双方论据均衡且无强力证据时选择持有。

## 要求
1. 总结双方关键观点
2. 给出明确建议：买入、卖出或持有
3. 解释为什么这些论据导致了你的结论
4. 制定详细投资计划：
   - 战略行动的具体步骤
   - 目标价格分析（1个月、3个月、6个月）
     - 基于基本面报告的估值
     - 考虑新闻驱动的预期调整
     - 情绪驱动的价格调整
     - 技术支撑/阻力位
     - 风险调整价格情景（保守、基准、乐观）
   - **必须提供具体目标价格数值**
5. 考虑类似情况下的历史错误

## 输入
- 历史反思: {past_memory_str}
- 标的约束: {instrument_context}
- 市场研究: {market_report}
- 情绪分析: {sentiment_report}
- 新闻分析: {news_report}
- 基本面分析: {fundamentals_report}
- 辩论历史: {history}
```

#### 2.2.5 双 LLM 策略

`TradingAgentsGraph.__init__()` 中的核心设计：

```python
# 从配置读取双模型参数
deep_model = config["deep_thinking_model"]   # 如 deepseek-v3
quick_model = config["quick_thinking_model"] # 如 deepseek-v2.5

# 创建两套 LLM 实例
self.deep_thinking_llm = create_llm_by_provider(provider, deep_model, ...)
self.quick_thinking_llm = create_llm_by_provider(provider, quick_model, ...)

# 使用分配：
# quick_thinking_llm → 分析师（数据聚合、简单分析）
# deep_thinking_llm → 裁判（Research Manager、Risk Manager）
# 辩论双方 → quick_thinking_llm（辩论的深度来自多轮交锋，而非单轮推理深度）
```

#### 2.2.6 数据层 — 三层降级链

```
请求: get_stock_price("600519")
  │
  ├─ 1st attempt: Tushare
  │   └─ FAIL (token 过期 / 额度耗尽 / 数据缺失)
  │
  ├─ 2nd attempt: AkShare
  │   └─ FAIL (接口限流 / 数据格式变更)
  │
  ├─ 3rd attempt: BaoStock
  │   └─ SUCCESS → return data
  │
  └─ All failed → raise DataUnavailableError

实时行情降级链（更细粒度）：
  stock_bid_ask_em → stock_zh_a_spot → stock_zh_a_spot_em → stock_zh_a_hist
```

缓存架构：
```
L1: Memory Cache (Python dict, 进程内)
L2: File Cache (pickle/sqlite, 进程外，持久)
L3: Adaptive Cache (根据数据类型自动选择策略)
L4: Integrated Cache (整合 L1+L2+L3)
L5: MongoDB Cache (分布式场景)
L6: App-level Cache Adapter (应用层缓存适配)
```

#### 2.2.7 信号处理 — 三级 Fallback

`signal_processing.py: SignalProcessor.process_signal()`：

```
输入: LLM 产生的原始文本信号

Tier 1: LLM JSON 解析
  ├─ 调用 quick_thinking_llm 从文本中提取结构化 JSON
  ├─ 正则提取 { ... } 块
  ├─ action 标准化: "buy"→"买入", "sell"→"卖出", "BUY"→"买入"
  └─ 成功 → 返回结构化信号

Tier 2: 正则提取 (_extract_simple_decision)
  ├─ 关键词检测: "买入" | "BUY" | "卖出" | "SELL" | "持有" | "HOLD"
  ├─ 目标价正则: 14 种价格模式 (如 "目标价位: XX", "$XX", "上涨到XX")
  └─ 成功 → 返回（confidence 默认 0.7, risk 默认 0.5）

Tier 3: 智能价格估算 (_smart_price_estimation)
  ├─ 扫描"当前价格"/"现价" → current_price
  ├─ 扫描"上涨N%"/"涨幅N%" → percentage
  ├─ 买入: target = current_price × (1 + percentage)
  ├─ 卖出: target = current_price × (1 - percentage)
  ├─ 无百分比数据: A股默认 +15%/-5%, 美股 +12%/-8%
  └─ 完全失败: target_price = None

Tier 4: 硬编码默认值 (_get_default_decision)
  └─ action="持有", target_price=None, confidence=0.5, risk_score=0.5
```

#### 2.2.8 记忆系统

5 个 FinancialSituationMemory 实例：

```python
self.bull_memory = FinancialSituationMemory("bull")
self.bear_memory = FinancialSituationMemory("bear")
self.trader_memory = FinancialSituationMemory("trader")
self.invest_judge_memory = FinancialSituationMemory("invest_judge")
self.risk_manager_memory = FinancialSituationMemory("risk_manager")

# 在 reflect_and_remember() 中:
# 每个角色独立反思自己的判断，提取经验教训
# 下次同类决策时通过 prompt 注入历史反思
past_memories = memory.get_memories(curr_situation, n_matches=2)
prompt += f"以下是您对错误的过去反思：\n{past_memory_str}"
```

### 2.3 两个项目的核心差异总结

| 维度 | ai-hedge-fund | TradingAgents-CN | 我们的产品应该 |
|------|--------------|-----------------|--------------|
| **Agent 交互** | 串行管道，Agent 间无反馈 | 多轮辩论 + 三层风控 + 裁判 | **辩论 + 裁判，但简化为 2 轮** |
| **数据建模** | Python 手写公式（4 估值模型） | LLM 做分析 + 正则兜底 | **Python 做计算，LLM 做叙事** |
| **数据源** | 单一 API 绑定 | 3 层降级 + 6 层缓存 | **Provider 抽象 + 2 层缓存 (MVP)** |
| **State** | 扁平 dict | 嵌套 State（3 层） | **嵌套 State（3 层）+ Pydantic 约束** |
| **LLM 策略** | 单模型 | 双模型（deep + quick） | **双模型（Opus + Haiku）** |
| **报告** | 无 | 对话 dump 导出 | **模板引擎驱动的专业研报（核心差异化）** |
| **容错** | 几乎没有 | 三级 fallback | **Pydantic schema + 正则 fallback + 默认值** |
| **部署** | CLI + Docker | Docker 多架构 + CI/CD | **SaaS (Vercel/Railway) + Docker 私有化** |
| **中国市场** | 不支持 | 深度优化 | **Day 1 支持 A/港/美三地** |

---

## 三、数据来源详细规格

### 3.1 数据源全景矩阵

| 数据类别 | 数据项 | 公开免费源 | 专业付费源（Phase 2） | 用户上传补充 |
|---------|--------|-----------|---------------------|------------|
| **行情** | 日线 OHLCV | AkShare / Yahoo Finance | Wind / Bloomberg | Excel |
| **行情** | 分钟线 | AkShare | Wind / 恒生聚源 | — |
| **财务** | 三表（BS/IS/CF） | AkShare / 巨潮 / SEC EDGAR | Wind / Bloomberg / Choice | PDF 年报 / Excel |
| **财务** | 财务比率 | AkShare (部分) | Wind 衍生指标 | — |
| **估值** | PE/PB/PS/EV-EBITDA | AkShare / Yahoo F. | Wind 一致性预期 | — |
| **新闻** | 公司公告/新闻 | 巨潮(公告) / Google News / 东方财富 | Bloomberg News / 财新 | — |
| **宏观** | GDP/CPI/PMI/M2 | 国家统计局 / 央行 / 东方财富 | Wind EDB | — |
| **行业** | 行业分类/对标公司 | 申万行业 / 证监会 / GICS | Wind / FactSet | — |
| **IPO** | 招股书/发行数据 | 港交所 / SEC / 巨潮 | Wind IPO / Dealogic | PDF 招股书 |
| **一级市场** | 融资/估值数据 | IT 桔子 / 企查查(部分) / Crunchbase | PitchBook / CVSource | — |

### 3.2 中国市场数据源详情

#### AkShare（MVP 首选）

```python
# 覆盖范围
A 股个股行情:       ✅ (stock_zh_a_hist, stock_zh_a_spot_em)
A 股财务数据:        ✅ (stock_financial_abstract, stock_financial_analysis_indicator)
A 股公告:           ✅ (stock_notice_report)
基金数据:           ✅ (fund_*)
宏观经济:           ✅ (macro_china_*)
港股:               ✅ (stock_hk_hist, stock_hk_financial)
美股:               ⚠️ 不直接支持，需接 Yahoo Finance

# 特点
- 完全免费，无需注册 token
- 数据来源主要是东方财富、新浪财经等
- 接口稳定性一般，字段名/API 签名可能随上游变化
- 无 QPS 保证
- 日线数据回溯时间长（10+ 年）
- 分钟线支持有限

# MVP 使用策略
- 作为 A 股主数据源
- 所有获取调用包裹 try/except + 重试（最多 3 次）
- 遇到字段缺失用默认值填充，不阻断 pipeline
```

#### Tushare（MVP 备选 + Phase 2 升级路径）

```python
# 需要免费注册获取 token
# 基础接口免费，高级接口需积分（如分钟线、龙虎榜）
# 数据质量 > AkShare，接口稳定性 > AkShare
# 积分获取需要社区贡献或付费

# MVP 使用策略
- 注册免费 token 作为 AkShare 的 fallback
- 优先用 AkShare（零门槛），失败时降级到 Tushare
```

#### 用户上传（万能 Fallback）

```python
# 支持的格式
- PDF 年报/半年报/季报
  → pdfplumber 提取文本 + 表格
  → 结构化提取关键财务数据（营业收入、净利润、资产负债...）
  
- Excel 财务模型
  → pandas 读取
  → 识别标准字段名（中英文映射）
  
- CSV 行情数据
  → pandas 读取，自动识别日期列和 OHLCV 列

# 处理流程
1. 用户上传文件 → 前端预览 + 确认
2. 后端解析 → 提取结构化数据
3. Agent 在看到解析结果的同时也能看到原始文本
   （以防解析有误，LLM 可以交叉验证）
```

### 3.3 美股数据源

#### Yahoo Finance（MVP 首选）

```python
# 通过 yfinance 库
# 免费、无需注册、数据质量好
# 覆盖：行情(OHLCV)、基本面、财务报表、股息、拆股
# 限制：无显式 QPS 限制但高频调用可能被临时封 IP

# MVP 使用策略
- 作为美股主数据源
- 添加 1-2s 调用间隔
- 缓存所有结果（TTL: 日线 24h，分钟线 1h）
```

#### SEC EDGAR（财报补充）

```python
# 10-K/10-Q 直接从 SEC 获取
# 使用 sec-edgar-api 或直接调 EDGAR REST API
# 数据最权威但格式不统一（XBRL/HTML）
# 用于交叉验证 Yahoo Finance 的财务数据
```

### 3.4 港股数据源

```python
# AkShare 支持港股日线行情和基本财务数据
# Yahoo Finance 支持港股 (.HK 后缀)
# 港交所披露易 (hketnews) 可以爬公告和年报

# MVP 策略：AkShare + Yahoo Finance 双源，取交集
```

### 3.5 Provider 接口设计

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
import pandas as pd

@dataclass
class PriceData:
    """标准化行情数据"""
    ticker: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    currency: str  # CNY / HKD / USD

@dataclass  
class FinancialStatement:
    """标准化财务报表"""
    ticker: str
    report_date: date
    fiscal_year: int
    fiscal_quarter: int
    currency: str
    # 利润表
    revenue: Optional[float]
    operating_income: Optional[float]
    net_income: Optional[float]
    eps_basic: Optional[float]
    eps_diluted: Optional[float]
    # 资产负债表
    total_assets: Optional[float]
    total_liabilities: Optional[float]
    total_equity: Optional[float]
    current_assets: Optional[float]
    current_liabilities: Optional[float]
    cash_and_equivalents: Optional[float]
    goodwill: Optional[float]
    intangible_assets: Optional[float]
    # 现金流量表
    operating_cash_flow: Optional[float]
    capex: Optional[float]
    free_cash_flow: Optional[float]
    # 衍生指标（由 calculator 层计算，不从 API 取）
    # roe, roa, gross_margin, net_margin, debt_to_equity, current_ratio...

@dataclass
class NewsItem:
    """标准化新闻条目"""
    ticker: str
    title: str
    source: str
    url: str
    published_at: datetime
    summary: Optional[str]
    sentiment: Optional[float]  # -1 到 1
    category: str  # earnings / mna / regulatory / market / other

class DataProvider(ABC):
    """所有数据源的抽象基类"""
    
    provider_name: str
    
    @abstractmethod
    async def health_check(self) -> bool:
        """检查数据源是否可用"""
        ...
    
    @abstractmethod
    async def get_prices(
        self, ticker: str, start_date: date, end_date: date
    ) -> list[PriceData]:
        """获取日线行情"""
        ...
    
    @abstractmethod
    async def get_financials(
        self, ticker: str, years: int = 5
    ) -> list[FinancialStatement]:
        """获取历年财务报表"""
        ...
    
    @abstractmethod
    async def get_news(
        self, ticker: str, days: int = 30
    ) -> list[NewsItem]:
        """获取近期新闻"""
        ...
    
    @abstractmethod
    def supports_market(self, market: str) -> bool:
        """检查是否支持特定市场 (CN/HK/US)"""
        ...
```

### 3.6 缓存策略详细规格

```python
# L1: 内存缓存 (Python lru_cache + TTL dict)
# 用途：同一请求内的重复调用
# TTL: 请求生命周期
# 最大容量: 1000 entries

# L2: 文件缓存 (SQLite)
# 用途：跨请求的数据复用
# 位置: ~/.investment_report_agent/cache.db
# 表结构:
#   cache_entries(key TEXT PRIMARY KEY, value BLOB, created_at TIMESTAMP, ttl_seconds INT)
#   cache_hits(key TEXT, hit_at TIMESTAMP)  -- 命中统计

# TTL 策略:
#   行情数据: 300s (5min) 盘中 / 3600s (1h) 收盘后
#   财报数据: 86400s (24h)，财报发布日强制刷新
#   新闻数据: 1800s (30min)
#   估值结果: 86400s (24h)，输入数据 hash 变化时失效
#   行业分类: 604800s (7d)
#   宏观数据: 86400s (24h)

# 失效检测:
#   财报发布日历 → 已知的财报日前后 3 天，财务缓存 TTL 降为 0
#   交易日历 → 盘后刷新时行情缓存 TTL 延长
```

### 3.7 数据清洗 Pipeline

```
原始数据 (AkShare / Yahoo F. / 用户上传)
  │
  ▼
Step 1: 标准化 (Standardizer)
  ├─ 字段名映射: 中文→英文, snake_case
  ├─ 统一货币单位: 元/美元/港元 → 保留原始货币，附加 currency 字段
  ├─ 统一日期格式: YYYY-MM-DD
  └─ 数值清洗: 字符串→float, 处理 "--"/"N/A"/"不适用"
  
  ▼
Step 2: 完整性检查 (CompletenessChecker)
  ├─ 必需字段不为 NaN
  ├─ 财报数据覆盖最近 3 年（< 3 年 → 标记为低置信度）
  ├─ 价格数据覆盖最近 1 年（< 1 年 → 标记为数据不足）
  └─ 输出: DataQualityReport { score: 0-100, missing_fields: [...], warnings: [...] }
  
  ▼
Step 3: 交叉验证 (CrossValidator)
  ├─ 多个数据源取到的财务数据对比（差异 > 10% → 标记）
  ├─ 价格数据一致性检查
  └─ 输出: ValidationReport { discrepancies: [...] }
  
  ▼
Step 4: 计算衍生指标 (DerivedMetricsCalculator)
  ├─ ROE, ROA, ROIC
  ├─ Gross/Operating/Net Margins
  ├─ Debt-to-Equity, Current Ratio
  ├─ Revenue/Earnings Growth (YoY, 3Y CAGR)
  ├─ FCF Yield
  └─ 输出: DerivedMetrics
  
  ▼
清洗后的结构化数据 → 传入 Agent 管线
```

### 3.8 一级市场（VC/PE）数据源

一级市场数据极度分散，不像二级市场有标准化行情和财报。MVP 阶段策略：**用户上传为主 + 公开爬取为辅**。

```python
# 一级市场数据源矩阵
PRIMARY_MARKET_SOURCES = {
    "cn": {
        "itjuzi": {
            "url": "https://www.itjuzi.com",
            "type": "web_scraping",
            "coverage": ["融资事件", "公司估值", "投资机构", "行业报告"],
            "api": False,  # 无公开 API
            "rate_limit": "严格控制, 建议 5req/min",
            "data_quality": "中等, 依赖人工录入",
            "mvp_use": "手动参考, 不作为自动化数据源"
        },
        "qichacha": {
            "url": "https://www.qcc.com", 
            "type": "web_scraping",
            "coverage": ["工商信息", "股权结构", "对外投资", "法律诉讼"],
            "api": True,  # 有付费 API
            "rate_limit": "付费后 1000req/day",
            "data_quality": "高 (官方工商数据)",
            "mvp_use": "API 查询公司基本信息"
        },
        "cvsource": {
            "note": "投中数据, 付费数据库, Phase 2 考虑",
            "coverage": ["PE/VC 交易", "基金募资", "退出事件", "LP 信息"]
        },
        "pedaily": {
            "url": "https://www.pedaily.cn",
            "type": "web_scraping",
            "coverage": ["投资快讯", "行业分析", "投资人观点"],
            "mvp_use": "新闻/公告 Agent 的补充新闻源"
        }
    },
    "global": {
        "crunchbase": {
            "url": "https://www.crunchbase.com",
            "api": True,
            "rate_limit": "付费 $99/mo 起, 5000req/mo",
            "coverage": ["融资轮次", "投资机构", "收购", "IPO"],
            "data_quality": "高, 结构化好",
            "mvp_use": "Phase 2 接入 API"
        },
        "pitchbook": {
            "note": "业界标准 PE/VC 数据库, 费用极高 (~$25K/yr), Phase 3",
            "coverage": ["完整交易数据", "LP 配置", "基金业绩", "估值基准"]
        },
        "sec_form_d": {
            "url": "https://www.sec.gov",
            "api": True,  # EDGAR API 免费
            "coverage": ["美国私募融资 Form D 申报"],
            "data_quality": "官方, 但信息有延迟且不完整",
            "mvp_use": "美股一级市场数据补充"
        }
    }
}
```

**一级市场报告的数据处理策略**：

```
一级市场报告的 Agent 管线与二级市场不同：

Pipeline: ipo_analysis
  Phase 1: 用户上传 (必须, 招股书/融资材料) + 公开信息爬取
  Phase 2: 财务分析 (招股书财务数据提取) + 行业分析 (赛道分析)
  Phase 3: 估值分析 (可比交易法 / 可比公司法, 非 DCF)
  Phase 4: 风险分析 (监管/市场/技术/团队)
  Phase 5: 统稿 (含交易结构分析章节)

关键差异：
  - 没有行情数据 Agent (一级市场无公开行情)
  - 财务数据依赖用户上传的招股书/融资材料
  - 估值方法不同 (可比交易 > 可比公司 > DCF)
  - 增加"团队分析"章节 (创始人背景、核心团队)
```

### 3.9 数据稳定性与 SLA 策略

```python
# 数据源健康监控

class DataProviderHealthMonitor:
    """
    每个数据源的状态持续追踪，决定降级决策。
    """
    
    # 追踪指标
    success_rate_window: int = 100         # 最近 100 次请求的统计窗口
    latency_p50_ms: float = 0
    latency_p99_ms: float = 0
    error_rate_1h: float = 0
    consecutive_failures: int = 0
    
    def is_healthy(self) -> bool:
        """数据源被视为 '健康' 的条件"""
        return (
            self.success_rate_window > 0.95       # 成功率 > 95%
            and self.consecutive_failures < 3      # 连续失败 < 3 次
            and self.latency_p99_ms < 10000        # P99 < 10s
        )
    
    def should_circuit_break(self) -> bool:
        """熔断: 连续失败 5 次 → 暂停使用 5 分钟后重试"""
        if self.consecutive_failures >= 5:
            return True
        return False

# 降级决策树

class FallbackDecisionEngine:
    """
    查询失败时的决策:
    
    1. Primary (AkShare) 失败
       ├─ 原因: 网络超时 → retry (max 3 times, exponential backoff)
       ├─ 原因: 接口报错 → 立即降级到 fallback (Tushare)
       ├─ 原因: 返回空数据 → 检查本地缓存 → 如无, 降级
       └─ 原因: 熔断激活 → 跳过, 直接降级
    
    2. Fallback (Tushare) 失败
       ├─ → 再降级到第二 fallback (Yahoo F. for CN) 或
       ├─ → 返回本地数据库中陈旧但可用的数据 (标记 stale=True)
       └─ → 全部失败 → Agent 显式标注 "数据不可用", 基于用户上传文件继续
    
    3. 降级链上的每步都会记录日志:
       {
         "timestamp": "2026-05-17T10:30:00Z",
         "ticker": "600519.SH",
         "query_type": "prices",
         "provider_chain": ["akshare", "tushare", "local_cache"],
         "result": "local_cache_hit_stale",
         "stale_age_seconds": 86450,
         "latency_ms": 5
       }
    """
```

### 3.10 数据处理的会计准则映射

```python
# 中美会计准则差异映射 (CAS vs US GAAP vs IFRS)

ACCOUNTING_STANDARD_MAPPING = {
    "revenue": {
        "CAS": ["营业收入", "营业总收入"],
        "US_GAAP": ["Revenue", "Total Revenue", "Net Sales"],
        "IFRS": ["Revenue", "Revenue from contracts with customers"],
        "unit": "元 (CNY) / USD / HKD",
    },
    "cost_of_revenue": {
        "CAS": ["营业成本"],
        "US_GAAP": ["Cost of Revenue", "Cost of Goods Sold", "Cost of Sales"],
        "IFRS": ["Cost of Sales"],
    },
    "operating_expenses": {
        "CAS": ["销售费用", "管理费用", "研发费用", "财务费用"],
        "US_GAAP": ["Selling, General and Administrative", "Research and Development"],
        "IFRS": ["Selling Expenses", "Administrative Expenses", "R&D Expenses"],
        "note": "中国将研发费用单独列示, US GAAP 可能含在 SG&A 中"
    },
    "operating_income": {
        "CAS": ["营业利润"],
        "US_GAAP": ["Operating Income", "Income from Operations"],
        "IFRS": ["Operating Profit", "Profit from Operations"],
    },
    "net_income": {
        "CAS": ["净利润", "归属于母公司所有者的净利润"],
        "US_GAAP": ["Net Income", "Net Income Attributable to Common Shareholders"],
        "IFRS": ["Profit for the Period", "Profit Attributable to Owners of the Parent"],
    },
    "total_assets": {
        "CAS": ["资产总计", "总资产"],
        "US_GAAP": ["Total Assets"],
        "IFRS": ["Total Assets"],
    },
    "total_equity": {
        "CAS": ["所有者权益合计", "归属于母公司所有者权益合计"],
        "US_GAAP": ["Total Stockholders' Equity", "Total Shareholders' Equity"],
        "IFRS": ["Total Equity", "Equity Attributable to Owners of the Parent"],
    },
    "operating_cash_flow": {
        "CAS": ["经营活动产生的现金流量净额"],
        "US_GAAP": ["Net Cash Provided by Operating Activities"],
        "IFRS": ["Cash Flows from Operating Activities"],
    },
    "capex": {
        "CAS": ["购建固定资产、无形资产和其他长期资产支付的现金"],
        "US_GAAP": ["Capital Expenditures", "Purchases of Property, Plant and Equipment"],
        "IFRS": ["Purchase of Property, Plant and Equipment", "Capital Expenditure"],
        "note": "中国现金流量表间接法, 需从'投资活动'中查找"
    },
    "goodwill": {
        "CAS": ["商誉"],
        "US_GAAP": ["Goodwill"],
        "IFRS": ["Goodwill"],
        "note": "US GAAP 允许商誉摊销 (私营公司可选), IFRS/CAS 仅减值测试"
    },
    "depreciation": {
        "CAS": ["固定资产折旧", "折旧"],
        "US_GAAP": ["Depreciation", "Depreciation and Amortization"],
        "IFRS": ["Depreciation", "Depreciation and Amortisation"],
        "note": "中国单独列示折旧和摊销, US GAAP/IFRS 常合并"
    },
}

# 单位标准化

class UnitNormalizer:
    """
    中国财报的常见单位问题:
    - 母公司报表用"元", 合并报表用"万元"或"亿元"
    - 部分 wind 导出用"万元", 部分用"元"
    - 有些字段是"亿元"有些是"万元"混在同一个文件
    
    标准化策略:
    1. 检测单位关键词: "万元" / "亿元" / "元" / "million" / "billion" / "thousand"
    2. 统一转换为: 元 (CNY) / USD / HKD
    3. 检测方法: 
       - 如果同一文件内不同字段用不同单位 → 标记 warning
       - 如果 Number × 10^8 ≈ 行业典型值 → "亿元" 
       - 如果 Number × 10^4 ≈ 行业典型值 → "万元"
       - 否则 → 标记为不可信, 让 Agent 自行判断
    """
    
    UNIT_PATTERNS = {
        "CNY_yuan": re.compile(r"[(（]元[)）]|单位[：:]\s*元"),
        "CNY_wan": re.compile(r"[(（]万元[)）]|单位[：:]\s*万元"),
        "CNY_yi": re.compile(r"[(（]亿元[)）]|单位[：:]\s*亿元"),
        "USD": re.compile(r"in millions|in thousands|in billions", re.I),
    }
    
    def detect_and_convert(self, value: float, context: str, market: str) -> tuple[float, str, float]:
        """
        Returns: (normalized_value, detected_unit, confidence)
        """
        ...
```

---

## 四、系统架构

### 4.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                    Web Frontend (Next.js 14)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ 对话界面  │  │ 报告预览  │  │ 模板编辑器│  │ 用户/订阅管理     │ │
│  │ (Chat)   │  │(Preview) │  │(Template)│  │ (Account)        │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
│                                                                  │
│  State: React Context + react-query (server state)               │
│  UI: Tailwind CSS + shadcn/ui                                    │
│  Report Preview: react-markdown + recharts + @react-pdf-viewer   │
└────────────────────────┬─────────────────────────────────────────┘
                         │ HTTP REST + SSE (Server-Sent Events)
                         │ Auth: JWT (access + refresh token)
┌────────────────────────┴─────────────────────────────────────────┐
│                  API Gateway (FastAPI + Uvicorn)                   │
│                                                                   │
│  /api/v1/report/generate     POST  → 启动报告生成 (返回 task_id)     │
│  /api/v1/report/{id}/status  GET   → 查询生成进度                   │
│  /api/v1/report/{id}/stream  GET   → SSE 流式进度推送               │
│  /api/v1/report/{id}         GET   → 获取完整报告 (JSON)            │
│  /api/v1/report/{id}/pdf     GET   → 下载 PDF                      │
│  /api/v1/report/{id}/docx    GET   → 下载 Word                     │
│  /api/v1/template/*          CRUD  → 模板管理                       │
│  /api/v1/user/*              CRUD  → 用户/订阅管理                   │
│  /api/v1/upload              POST  → 上传财报/数据文件               │
│                                                                   │
│  Middleware: Auth, Rate Limit, CORS, Request Logging              │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────┴─────────────────────────────────────────┐
│              Agent Orchestrator (Claude Agent SDK 集成)            │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    主编排 Agent (Orchestrator)                 │ │
│  │                                                               │ │
│  │  职责: 路由请求到正确的 Pipeline                               │ │
│  │  输入: 用户消息 + 上下文 (ticker, template_id, uploaded_files) │ │
│  │  输出: TaskSpec { pipeline_type, params, template }           │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│              ┌───────────────┼───────────────┐                    │
│              ▼               ▼               ▼                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ 个股深度报告  │  │ 快速简报     │  │ 宏观周报     │  ...       │
│  │ Pipeline     │  │ Pipeline     │  │ Pipeline     │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                   │
│  每个 Pipeline 内部:                                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  4 阶段多 Agent 管线:                                         │ │
│  │  Phase 1: 数据聚合 (4 SubAgents 并行)                         │ │
│  │  Phase 2: 深度分析 (4 SubAgents 并行)                         │ │
│  │  Phase 3: 辩论 + 裁判 (3 SubAgents 串行辩论)                   │ │
│  │  Phase 4: 统稿 + 排版 (3 SubAgents + 模板引擎)                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────┴─────────────────────────────────────────┐
│                  Python 计算层 (非 LLM)                            │
│                                                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐ │
│  │ 财务比率   │  │ 估值引擎   │  │ 图表生成   │  │ 数据清洗   │ │
│  │ 计算器     │  │ (3 models) │  │ (matplot)  │  │ (pandas)   │ │
│  │            │  │            │  │            │  │            │ │
│  │ ROE, ROA  │  │ DCF        │  │ 营收趋势图 │  │ 缺失值填充 │ │
│  │ ROIC       │  │ Owner Earn │  │ 盈利能力图 │  │ 异常值标记 │ │
│  │ 利润率     │  │ EV/EBITDA  │  │ 估值区间图 │  │ 标准化     │ │
│  │ 增长率     │  │            │  │ 同业对比图 │  │ 交叉验证   │ │
│  │ 负债指标   │  │            │  │            │  │            │ │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────┴─────────────────────────────────────────┐
│                  Data Provider Layer                               │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   ProviderManager                             │ │
│  │   get_prices(ticker, start, end) → PriceData[]               │ │
│  │   get_financials(ticker, years) → FinancialStatement[]       │ │
│  │   get_news(ticker, days) → NewsItem[]                        │ │
│  │   get_macro(indicators) → MacroData                           │ │
│  │                                                               │ │
│  │   内部逻辑: market_detect(ticker) → route to correct provider │ │
│  │            primary.try() → fallback1.try() → fallback2.try() │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│     ┌────────┬────────┬──────┴──────┬─────────┬──────────┐       │
│     ▼        ▼        ▼             ▼         ▼          ▼       │
│  ┌──────┐┌──────┐┌──────┐┌──────────┐┌──────┐┌──────────┐      │
│  │AkShare││Tushare││Yahoo ││SEC EDGAR ││用户  ││(预留)    │      │
│  │(A股) ││(A股) ││Finance││(美股财报)││上传  ││Wind等    │      │
│  └──────┘└──────┘│(美/港)│└──────────┘└──────┘└──────────┘      │
│                  └──────┘                                         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                   Cache Layer                                 │ │
│  │  L1: Memory (请求级)  L2: SQLite (跨请求)  L3: Redis (可选)  │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 部署架构

```
MVP (SaaS):
┌────────────────────────────────────────────────────┐
│  Vercel / Railway                                  │
│  ┌──────────────────┐  ┌─────────────────────────┐ │
│  │ Next.js Frontend  │  │ FastAPI Backend          │ │
│  │ (static + SSR)   │  │ (Docker container)       │ │
│  └──────────────────┘  │  - API routes             │ │
│                        │  - Agent orchestrator     │ │
│                        │  - Python calculator layer │ │
│  ┌──────────────────┐  │  - Provider layer         │ │
│  │ SQLite (本地文件) │  └─────────────────────────┘ │
│  └──────────────────┘                              │
│  ┌──────────────────┐                              │
│  │ Anthropic API    │ (LLM 调用通过 Anthropic SDK) │
│  └──────────────────┘                              │
└────────────────────────────────────────────────────┘

Phase 3 (私有化部署):
┌────────────────────────────────────────────────────┐
│  客户 VPC / 内网服务器                               │
│  ┌──────────────────────────────────────────────┐  │
│  │ Docker Compose                                │  │
│  │  ├─ frontend (Next.js, port 3000)             │  │
│  │  ├─ backend (FastAPI, port 8000)              │  │
│  │  ├─ postgresql (port 5432, 替代 SQLite)       │  │
│  │  ├─ redis (port 6379, 可选)                   │  │
│  │  └─ nginx (reverse proxy, port 80/443)        │  │
│  └──────────────────────────────────────────────┘  │
│  LLM: 客户自己的 API key 或本地部署的模型            │
│  数据: 完全不出客户内网                             │
└────────────────────────────────────────────────────┘
```

---

## 五、Agent 详细设计

### 5.1 Agent 全景图

```
主编排 Agent (Orchestrator)
  │ 职责: 意图识别 → Pipeline 路由 → 进度追踪 → 异常处理
  │ LLM: Claude Haiku (路由判断不需要 Opus)
  │
  ├── Phase 1: 数据聚合 (4 SubAgents, 并行执行)
  │   ├── 行情数据 Agent     — 获取日线/分钟线，计算技术指标
  │   ├── 财报数据 Agent     — 获取三表，清洗，计算衍生比率
  │   ├── 公告新闻 Agent     — 获取近期公告和新闻，提取关键事件
  │   └── 宏观行业 Agent     — 获取宏观指标，行业分类，同业对标
  │
  ├── Phase 2: 深度分析 (4 SubAgents, 并行执行)
  │   ├── 财务分析 Agent     — 盈利能力/成长性/偿债能力/运营效率 4 维度评分
  │   ├── 估值建模 Agent     — DCF / Owner Earnings / EV-EBITDA / 敏感性分析
  │   ├── 行业竞争 Agent     — 波特五力 / 市场份额 / 竞争格局 / 壁垒
  │   └── 公司治理 Agent     — 管理层评估 / 股权结构 / 分红政策 / ESG
  │
  ├── Phase 3: 辩论与裁判 (3 SubAgents, 串行辩论)
  │   ├── 多头论点 Agent     — N 轮论证看涨逻辑
  │   ├── 空头论点 Agent     — N 轮论证看跌逻辑
  │   └── 风险裁判 Agent     — 评估双方论据，输出关键风险与机遇
  │
  └── Phase 4: 统稿与排版 (3 SubAgents + 模板引擎)
      ├── 章节撰写 Agent     — 将结构化分析转化为专业研报文字
      ├── 图表生成 Agent     — 生成 matplotlib 图表并嵌入报告
      ├── 标题摘要 Agent     — 生成报告标题、投资摘要、核心结论
      └── 模板引擎 (非 LLM)  — Jinja2 渲染 HTML → WeasyPrint → PDF
```

### 5.2 Agent 详细规格

#### Agent 0: 主编排 Agent (Orchestrator)

```
职责: 请求路由 + Pipeline 编排 + 进度追踪
LLM: Claude Haiku (仅做意图分类，不需要深度推理)

输入:
  - user_message: str  # 如 "分析贵州茅台，生成深度研报"
  - context:
    - uploaded_files: [FileInfo]  # 用户上传的文件列表
    - preferred_template: str | None
    - user_subscription_tier: str  # "free" | "pro" | "enterprise"

输出:
  - pipeline_type: "deep_dive" | "brief" | "macro_weekly" | "ipo" | "pitch_book"
  - params:
    - tickers: [str]  # 从用户消息中提取的股票代码/公司名
    - report_date: date
    - language: "zh-CN" | "en"
  - template_id: str
  - task_id: UUID

处理逻辑:
  1. 解析用户消息，提取公司名/股票代码
     - 支持中文公司名 → ticker 映射 (通过 AkShare/Tushare 查询)
     - 支持多标的批量模式识别
  2. 判断报告类型: 
     - "深度研报" / "深度" / "分析报告" → deep_dive
     - "简报" / "快报" / "速览" → brief
     - "宏观" / "周报" → macro_weekly
     - "IPO" / "新股" / "上市" → ipo
     - "Pitch" / "Teaser" / "投行" → pitch_book
  3. 选择模板: 用户指定 > 历史偏好 > 默认模板
  4. 创建 task_id，返回 TaskSpec
  5. 调用对应 Pipeline 执行
  6. 通过 SSE 推送进度更新

Prompt 模板 (简化版):
"""
你是一个投资研究助手，负责理解用户的研究需求并路由到正确的报告生成流程。

用户消息: {user_message}
可用模板: {available_templates}
用户上传文件: {uploaded_files_summary}

请从用户消息中提取:
1. 公司名称或股票代码
2. 期望的报告类型
3. 任何特殊要求

输出 JSON:
{
  "tickers": ["600519.SH"],
  "company_names": ["贵州茅台"],
  "report_type": "deep_dive",
  "special_requirements": null
}
"""
```

#### Agent 1-4: 数据聚合层

**Agent 1: 行情数据 Agent**

```
职责: 获取行情数据 + 计算技术分析指标
模型: Claude Haiku (只是解释数据，不做复杂推理)
Python 计算: pandas 技术指标计算

输入:
  - ticker: str
  - start_date: date  # 默认 3 年前
  - end_date: date    # 默认今天

Python 计算 (非 LLM):
  技术指标:
    - MA (5/10/20/60/120/250 日均线)
    - MACD (DIF, DEA, 柱状)
    - RSI (14 日)
    - Bollinger Bands (20 日, 2σ)
    - ATR (14 日)  # 波动率指标
    - Volume profile  # 成交量分布
  
  统计指标:
    - 期间涨跌幅 (1M/3M/6M/1Y/3Y)
    - 年化波动率
    - 最大回撤
    - Sharpe 比率 (β=无风险利率)
    - Beta (相对沪深300/标普500)
    - 日均成交额

输出 schema:
{
  "ticker": "600519.SH",
  "company_name": "贵州茅台",
  "market": "A股",
  "currency": "CNY",
  "price_summary": {
    "latest_price": 1680.00,
    "52w_high": 1920.00,
    "52w_low": 1420.50,
    "ytd_return_pct": -5.2,
    "returns": {"1m": 3.1, "3m": -2.3, "6m": 8.7, "1y": -10.5, "3y": 15.2},
    "annualized_volatility": 28.5,
    "max_drawdown_1y": -22.3,
    "sharpe_ratio": 0.45,
    "beta": 0.85,
    "avg_daily_volume": 2_500_000_000  # 25 亿
  },
  "technical_signals": {
    "ma_trend": "短期均线空头排列，中长期多头",
    "macd": {"signal": "bearish", "description": "DIF 下穿 DEA"},
    "rsi": {"value": 42.3, "signal": "neutral"},
    "bollinger": {"position": "middle_band", "signal": "neutral"}
  },
  "price_chart_data": "base64_encoded_or_path"
}
```

**Agent 2: 财报数据 Agent**

```
职责: 获取三表 + 清洗 + 计算衍生财务指标
模型: Claude Haiku (数据验证和异常标注)
Python 计算: 所有比率计算

处理流程:
  1. 获取原始财报 (最近 5 年, 季/年)
  2. 数据清洗:
     - 单位统一 (万元→元)
     - 缺失值: 标记但不推断
     - 异常值: 标注 (如单季度净利润 > 全年，说明有非经常性损益)
  3. Python 计算 (不经过 LLM):
     
     盈利能力:
       ROE = Net Income / Avg Equity
       ROA = Net Income / Avg Total Assets
       ROIC = NOPAT / Invested Capital
       Gross Margin = (Revenue - COGS) / Revenue
       Operating Margin = Operating Income / Revenue
       Net Margin = Net Income / Revenue
     
     成长性:
       Revenue Growth (YoY, 3Y CAGR, 5Y CAGR)
       Earnings Growth (YoY, 3Y CAGR, 5Y CAGR)
       FCF Growth (YoY)
       Total Assets Growth (YoY)
     
     偿债能力:
       Debt-to-Equity = Total Liabilities / Total Equity
       Interest Coverage = EBIT / Interest Expense
       Current Ratio = Current Assets / Current Liabilities
       Quick Ratio = (CA - Inventory) / Current Liabilities
       Net Debt / EBITDA
     
     运营效率:
       Asset Turnover = Revenue / Avg Total Assets
       Inventory Turnover = COGS / Avg Inventory
       Receivable Days = Avg AR / Revenue × 365
       Payable Days = Avg AP / COGS × 365
       Cash Conversion Cycle = Receivable Days + Inventory Days - Payable Days
     
     盈利质量:
       FCF / Net Income (比值 > 0.8 为佳)
       Operating Cash Flow / Revenue
       Accruals Ratio

  4. 将计算结果格式化为 Agent 可消费的结构化 JSON

输出 schema:
{
  "ticker": "600519.SH",
  "data_quality": {
    "years_covered": 5,
    "latest_fiscal_year": 2025,
    "completeness_score": 95,     # 0-100
    "missing_fields": ["intangible_assets_2020"],
    "warnings": ["2024Q4 净利润含大额非经常性损益"]
  },
  "profitability": {
    "latest_roe": 28.5,
    "latest_roa": 18.2,
    "latest_roic": 24.1,
    "roe_trend": [25.0, 26.2, 27.1, 27.8, 28.5],  # 近 5 年
    "gross_margin": 91.2,       # %
    "gross_margin_trend": [90.5, 90.8, 91.0, 91.1, 91.2],
    "net_margin": 52.3,
    "industry_avg_roe": 12.5,   # 行业均值
    "industry_avg_gross_margin": 65.0
  },
  "growth": {
    "revenue_growth_yoy": 15.2,    # %
    "revenue_growth_3y_cagr": 12.8,
    "earnings_growth_yoy": 18.5,
    "earnings_growth_3y_cagr": 15.2,
    "fcf_growth_yoy": 22.1
  },
  "financial_health": {
    "debt_to_equity": 0.15,
    "interest_coverage": 85.2,
    "current_ratio": 3.5,
    "quick_ratio": 2.8,
    "net_debt_to_ebitda": -0.5  # 净现金 > 有息负债
  },
  "efficiency": {
    "asset_turnover": 0.65,
    "inventory_turnover": 0.35,
    "cash_conversion_cycle": 120.5  # 天
  },
  "earnings_quality": {
    "fcf_to_net_income": 0.92,
    "ocf_to_revenue": 0.55
  },
  "financial_chart_data": {
    "revenue_chart": "base64_or_path",
    "profitability_chart": "base64_or_path",
    "margin_trend_chart": "base64_or_path"
  }
}
```

**Agent 3: 公告新闻 Agent**

```
职责: 聚合近期公告和新闻，提取关键事件
模型: Claude Haiku (摘要 + 情感分析)

数据来源:
  - A股: 巨潮资讯 (公告) + 东方财富 (新闻)
  - 港股: 港交所披露易 + Google News
  - 美股: SEC EDGAR (8-K) + Yahoo Finance News

处理流程:
  1. 获取最近 30 天公告和新闻
  2. 按重要性分类:
     - CRITICAL: 业绩预告/快报、重大资产重组、控制权变更
     - HIGH: 股东增减持、分红公告、高管变动
     - MEDIUM: 经营数据、战略合作、行业政策
     - LOW: 日常经营公告
  3. 每家公司的新闻聚合为一条时间线
  4. 提取关键数字 (如有): 如"预计净利润增长 XX%"

输出 schema:
{
  "ticker": "600519.SH",
  "recent_events": [
    {
      "date": "2026-05-15",
      "type": "earnings_release",
      "importance": "CRITICAL",
      "title": "2025 年年度报告",
      "summary": "全年营收 1680 亿，同比+15.2%，净利润 880 亿，同比+18.5%",
      "key_numbers": {"revenue": 168_000_000_000, "net_income": 88_000_000_000},
      "sentiment": 0.7  # -1 到 1
    },
    ...
  ],
  "sentiment_summary": {
    "overall": 0.4,  # 略偏正面
    "news_count_positive": 12,
    "news_count_neutral": 8,
    "news_count_negative": 3,
    "key_themes": ["白酒消费升级持续", "直销占比提升", "行业监管趋严"]
  },
  "upcoming_events": [
    {"date": "2026-06-15", "type": "dividend_ex_date", "detail": "每股派息 25.8 元"}
  ]
}
```

**Agent 4: 宏观行业 Agent**

```
职责: 获取宏观指标 + 行业分类 + 同业对标
模型: Claude Haiku (解释宏观环境对标的的影响)

数据来源:
  - 宏观: AkShare macro_china_* (GDP/CPI/PMI/M2/社融/利率)
  - 行业分类: 申万行业 2021 版
  - 同业: 同一申万三级行业中市值相近的公司

处理流程:
  1. 确定标的的行业分类 (申万一级/二级/三级)
  2. 获取行业关键指标:
     - 行业 PE/PB 中位数和分位数
     - 行业营收增速中位数
     - 行业 ROE 中位数
  3. 选出 5-8 家可比公司 (同三级行业 + 市值 ±50%)
  4. 获取宏观指标 (GDP 增速、CPI、PMI、10Y 国债、社融增速、人民币汇率)
  5. 将标的在行业中的位置可视化 (散点图: 市值 vs PE)

输出 schema:
{
  "ticker": "600519.SH",
  "industry": {
    "shenwan_l1": "食品饮料",
    "shenwan_l2": "白酒",
    "shenwan_l3": "白酒",
    "industry_pe_median": 25.5,
    "industry_pe_percentile": 72,  # 标的 PE 在行业中的分位数
    "industry_pb_median": 5.2,
    "industry_roe_median": 18.5,
    "industry_revenue_growth_median": 10.2
  },
  "peers": [
    {
      "ticker": "000858.SZ",
      "name": "五粮液",
      "market_cap": 580_000_000_000,
      "pe": 20.5,
      "roe": 22.3,
      "revenue_growth_3y": 10.5
    },
    ... // 5-8 家
  ],
  "macro": {
    "gdp_growth_yoy": 5.2,       # %
    "cpi_yoy": 0.3,              # %
    "pmi_manufacturing": 50.2,
    "10y_bond_yield": 1.72,      # %
    "social_financing_growth": 8.5,
    "cny_usd": 7.25,
    "macro_sentiment": "弱复苏，货币政策宽松，消费信心缓慢恢复",
    "policy_tailwinds": ["促消费政策", "减税降费"],
    "policy_headwinds": ["白酒行业监管", "反腐"]
  },
  "positioning_chart": "base64_or_path"  # 标的在行业中的定位散点图
}
```

#### Agent 5-8: 深度分析层

**Agent 5: 财务分析 Agent**

```
职责: 综合评估财务健康状况，四维度评分
模型: Claude Opus (需要综合判断财务质量)
Python 计算: 所有评分和阀值

四维度评分体系 (参考 ai-hedge-fund 的 Buffett Agent 做法):

维度 1: 盈利能力评分 (满分 10)
  ROE > 20% → 4pts, 15-20% → 3pts, 10-15% → 2pts, 5-10% → 1pt
  ROE 连续 5 年 > 15% → +2pts
  Gross Margin > 行业均值 → 2pts
  Net Margin > 行业均值 → 2pts

维度 2: 成长性评分 (满分 8)
  Revenue Growth 3Y CAGR > 20% → 4pts, 10-20% → 3pts, 5-10% → 2pts
  Earnings Growth 3Y CAGR > 20% → 4pts, 10-20% → 3pts, 5-10% → 2pts

维度 3: 财务健康评分 (满分 8)
  Debt/Equity < 0.3 → 3pts, 0.3-0.7 → 2pts, 0.7-1.0 → 1pt
  Interest Coverage > 20 → 2pts, 10-20 → 1pt
  Current Ratio > 2 → 2pts, 1-2 → 1pt
  FCF/Net Income > 0.8 → 1pt

维度 4: 盈利质量评分 (满分 6)
  FCF 连续 3 年 > 0 → 3pts
  OCF/Revenue 稳定 → 2pts
  非经常性损益/净利润 < 10% → 1pt

综合得分: 0-32 分
  ≥ 25 → EXCELLENT
  18-24 → GOOD
  10-17 → FAIR
  < 10 → POOR

输出 schema:
{
  "ticker": "600519.SH",
  "financial_health_score": {
    "total": 28,
    "rating": "EXCELLENT",
    "breakdown": {
      "profitability": {"score": 8, "max": 10, "details": "ROE 28.5%, 连续5年>15%"},
      "growth": {"score": 6, "max": 8, "details": "营收CAGR 12.8%, 净利CAGR 15.2%"},
      "health": {"score": 8, "max": 8, "details": "D/E 0.15, 利息覆盖率85x, 流动比率3.5"},
      "quality": {"score": 6, "max": 6, "details": "FCF/净利润 0.92, OCF/营收 0.55"}
    },
    "industry_percentile": 92  # 在行业中排名前 8%
  },
  "key_strengths": [
    "超高 ROE (28.5%)，远超行业均值 (12.5%)",
    "轻资产运营，几乎零负债",
    "FCF 与净利润高度匹配，盈利质量极高"
  ],
  "key_weaknesses": [
    "营收增速放缓 (3Y CAGR 12.8%，低于 5 年前的 20%+)",
    "资产周转率偏低 (0.65)，资本效率有待提升"
  ],
  "red_flags": [],  # 财务造假预警
  "narrative": "贵州茅台展现出极致的盈利能力..."  # LLM 生成的财务分析叙事
}
```

**Agent 6: 估值建模 Agent**

```
职责: 多模型估值 + 敏感性分析
模型: Claude Opus (解读估值结果 + 给出投资建议)
Python 计算: 所有估值模型 + Monte Carlo

估值模型 (Python 计算):

模型 1: 三阶段 DCF
  阶段 1 (高增长, 5Y): growth_rate = min(3Y FCF CAGR × 0.8, 15%)
  阶段 2 (过渡, 5Y): growth_rate 线性衰减到永续增长率
  阶段 3 (永续): growth_rate = 3% (名义 GDP 增速代理)
  WACC 计算:
    Cost of Equity = Rf + β × ERP
      Rf = 10Y CGB (中国) / 10Y UST (美国/香港)
      ERP = 6% (中国) / 5% (美国) / 6.5% (香港)
    Cost of Debt = 利息支出 / 有息负债 (如有), 否则用 Rf + 信用利差
    WACC = E/(E+D) × Ke + D/(E+D) × Kd × (1-t)
  终端价值 = FCF_T+1 / (WACC - g_terminal)
  企业价值 = Σ PV(FCF) + PV(终端价值)
  股权价值 = 企业价值 - 净负债 + 现金 + 非核心资产 - 少数股东权益
  每股价值 = 股权价值 / 总股本

模型 2: Owner Earnings (Buffett)
  Owner Earnings = Net Income + D&A - Maintenance Capex - Δ Net Working Capital
  Maintenance Capex = median(总Capex×0.85, D&A, D&A×历年Capex/D&A中位数)
  5Y DCF + Terminal Value (g = 3%), 折现率 9%
  Margin of Safety = 25%

模型 3: EV/EBITDA 行业对标
  取同业可比公司的 EV/EBITDA 中位数
  Implied EV = EBITDA × 行业 EV/EBITDA 中位数
  根据标的的 ROE/成长性 vs 行业中位数的溢价/折价调整:
    标的 ROE > 行业中位数 2× → 溢价 15%
    标的 Growth > 行业中位数 → 溢价 10%
  股权价值 = EV - 净负债 + 少数股东 + 优先股 - 非控股权益

模型 4 (可选, Phase 2): Residual Income
  RI = Net Income - Equity_Capital × Ke
  Terminal Value = RI_T+1 / (Ke - g)
  Book Value + PV(RI) + PV(TV)
  Margin of Safety = 20%

加权:
  35% × DCF + 35% × Owner Earnings + 20% × EV/EBITDA + 10% × RI
  如缺少数据导致某模型无法计算，权重等比重新分配

敏感性分析:
  WACC ± 1% ↔ Terminal Growth ± 0.5% 的矩阵
  输出 3×3 矩阵: 每股价值范围

Monte Carlo (可选, Phase 2):
  参数: Revenue Growth (正态分布), WACC (对数正态), Terminal Growth (对数正态)
  迭代: 10,000 次
  输出: 概率分布的区间 (P10/P50/P90)

输出 schema:
{
  "ticker": "600519.SH",
  "current_price": 1680.00,
  "market_cap": 2_100_000_000_000,  # 2.1 万亿
  "valuation_results": {
    "dcf": {
      "per_share_value": 1950.00,
      "upside_pct": 16.1,
      "key_assumptions": {
        "wacc": 8.5, "terminal_growth": 3.0,
        "stage1_growth": 12.0, "stage1_years": 5,
        "stage2_years": 5
      }
    },
    "owner_earnings": {
      "per_share_value": 2100.00,
      "upside_pct": 25.0,
      "key_assumptions": {"discount_rate": 9.0, "mos": 0.25}
    },
    "ev_ebitda": {
      "per_share_value": 1850.00,
      "upside_pct": 10.1,
      "key_assumptions": {"industry_ev_ebitda": 18.5, "premium_adj": 1.05}
    },
    "weighted_value": 1970.25,
    "weighted_upside_pct": 17.3
  },
  "sensitivity_matrix": {
    # WACC × Terminal Growth 9 格
    "wacc_range": [7.5, 8.5, 9.5],
    "growth_range": [2.5, 3.0, 3.5],
    "values": [
      [2250, 2050, 1900],
      [2100, 1950, 1800],
      [1980, 1850, 1720]
    ]
  },
  "valuation_charts": {
    "dcf_waterfall": "base64_or_path",
    "peer_comps_chart": "base64_or_path",
    "sensitivity_heatmap": "base64_or_path"
  },
  "valuation_narrative": "当前股价 1680 元，相对加权内在价值 1970 元有 17.3% 的上行空间..."
}
```

**Agent 7: 行业竞争 Agent**

```
职责: 分析行业结构和竞争格局
模型: Claude Opus (定性分析为主)

分析框架:
  1. 波特五力
     - 新进入者威胁 (进入壁垒高低)
     - 供应商议价能力
     - 买方议价能力
     - 替代品威胁
     - 现有竞争者之间的竞争强度
  
  2. 市场份额与定位
     - 标的在行业中的份额及趋势
     - 竞争地图 (高端/中端/低端分别是谁)
  
  3. 竞争壁垒 (Moat)
     - 品牌壁垒
     - 规模效应
     - 网络效应
     - 转换成本
     - 专利/技术壁垒
     - 监管壁垒 (牌照等)
  
  4. 行业生命周期
     - 导入期 / 成长期 / 成熟期 / 衰退期
     - 未来 3-5 年的行业 CAGR 预测

输出 schema:
{
  "porter_five_forces": {
    "new_entrants": {"level": "LOW", "score": 8, "reasoning": "品牌壁垒极高..."},
    "suppliers": {"level": "MEDIUM", "score": 5, "reasoning": "..."},
    "buyers": {"level": "LOW", "score": 7, "reasoning": "..."},
    "substitutes": {"level": "MEDIUM", "score": 5, "reasoning": "..."},
    "rivalry": {"level": "HIGH", "score": 3, "reasoning": "..."},
    "overall_attractiveness": 5.6  # 平均分
  },
  "market_position": {
    "market_share": 18.5,  # %
    "share_trend": "stable",  # growing / stable / declining
    "rank": 1,
    "competitive_landscape": "寡头格局，CR5 > 80%"
  },
  "moat_assessment": {
    "brand": {"score": 10, "evidence": "中国最具价值白酒品牌..."},
    "scale": {"score": 8, "evidence": "毛利率 91%..."},
    "switching_cost": {"score": 6, "evidence": "..."},
    "regulatory": {"score": 7, "evidence": "白酒生产许可..."},
    "overall_moat_width": "WIDE"  # WIDE / NARROW / NONE
  },
  "industry_lifecycle": {
    "stage": "成熟期",
    "industry_growth_forecast_3y": "5-8%",
    "disruption_risk": "LOW"
  }
}
```

**Agent 8: 公司治理 Agent** (仅用于深度研报，快速简报可跳过)

```
职责: 评估管理层质量、股权结构、ESG
模型: Claude Opus

分析维度:
  1. 管理层质量
     - 核心管理层履历
     - 战略执行力 (收入/利润是否持续达到指引)
     - 资本配置能力 (并购/回购/分红的 track record)
  
  2. 股权结构
     - 实际控制人/控股股东
     - 股权质押比例
     - 机构持股比例
     - 近期增减持
  
  3. ESG 概要
     - E: 碳排放/能耗
     - S: 员工/社会责任
     - G: 董事会独立性/信息披露
```

#### Agent 9-11: 辩论与裁判层

**Agent 9 & 10: 牛/熊辩论**

```
这两个 Agent 的实现高度对称，放在一起描述。

Agent 9: 多头论点 Agent (Bull Case Agent)
Agent 10: 空头论点 Agent (Bear Case Agent)

模型: Claude Opus
辩论轮次: 2 轮 (MVP)

辩论协议:
  Round 1:
    Bull 产出: 3-5 个核心看涨论点，每个附带证据 (数据/事实)
    Bear 产出: 3-5 个核心看跌论点，每个附带证据
    
  Round 2:
    Bull 看到 Bear 的论点后:
      - 对 Bear 的每个论点逐一反驳/削弱
      - 强化自己的论点 (补充新证据)
    
    Bear 看到 Bull 的论点后:
      - 对 Bull 的每个论点逐一反驳/削弱
      - 强化自己的论点

  关键设计:
    - 双方看到的是对方的完整输出，不是摘要
    - 第 2 轮必须引用第 1 轮对方的具体论点
    - 不允许重复自己的第 1 轮观点（必须深化或补充）
    - 每个论点标注置信度 (0-100)

输入:
  - 前面所有 Agent 的产出 (财务分析、估值结果、行业分析、新闻摘要)
  - 对方的第 1 轮论点 (仅 Round 2)

输出 schema:
{
  "side": "bull",  // "bull" | "bear"
  "round": 2,
  "arguments": [
    {
      "id": "bull_arg_1",
      "thesis": "超高 ROE 和宽阔的护城河支撑估值溢价",
      "evidence": [
        "ROE 28.5% 连续 5 年增长，行业均值仅 12.5%",
        "品牌壁垒为行业最强，消费者价格弹性极低",
        "DCF 估值显示 17.3% 上行空间"
      ],
      "confidence": 85,
      "rebuttal_to": "bear_arg_3",  # 针对对方的哪个论点
      "rebuttal_text": "空方关于白酒需求下降的担忧被夸大..."
    },
    ...
  ],
  "key_narrative": "茅台作为稀缺的中国奢侈品消费标的..."
}
```

**Agent 11: 风险裁判 Agent**

```
职责: 
  1. 评估牛熊双方论据的可信度和证据强度
  2. 综合判断，输出关键风险和关键机遇
  3. 给出最终的投资建议倾向

模型: Claude Opus (需要最高推理质量)

评估标准:
  - 证据质量: 是硬数据还是软判断？(quantitative vs qualitative)
  - 逻辑链条: 论据→结论的推理是否严密？
  - 历史验证: 类似情景下该论据的预测准确度？
  - 风险定价: 当前估值是否已经反映了这些风险/机遇？

输出 schema:
{
  "verdict": "BUY",  // STRONG_BUY | BUY | HOLD | SELL | STRONG_SELL
  "verdict_confidence": 72,  # 0-100
  
  "key_risks": [
    {
      "risk": "消费降级趋势下高端白酒需求持续下滑",
      "probability": "MEDIUM",  # LOW / MEDIUM / HIGH
      "impact": "HIGH",          # LOW / MEDIUM / HIGH
      "time_horizon": "中长期 (1-3年)",
      "mitigation": "茅台在高端政务/商务场合的不可替代性部分对冲此风险",
      "source": "bear_arg_1"
    },
    ...  # 3-5 个
  ],
  
  "key_opportunities": [
    {
      "opportunity": "直销占比提升 (当前45% → 目标60%) 将直接推升净利率",
      "probability": "HIGH",
      "impact": "MEDIUM",
      "estimated_eps_boost_pct": 5.2,
      "source": "bull_arg_2"
    },
    ...  # 3-5 个
  ],
  
  "risk_reward_assessment": {
    "upside_potential_pct": 17.3,    # 基于估值模型
    "downside_risk_pct": -15.0,      # 下行风险估计
    "risk_reward_ratio": 1.15,       # 上行/下行
    "kelly_criterion_allocation": 13.2  # % 组合配置建议
  },
  
  "confidence_intervals": {
    "pessimistic_price": 1428,   # 熊情景
    "base_price": 1970,          # 基准情景
    "optimistic_price": 2520     # 牛情景
  },
  
  "judge_narrative": "综合牛熊双方论据，我们认为..."  # LLM 综合论述
}
```

#### Agent 12-14: 统稿与排版层

**Agent 12: 章节撰写 Agent**

```
职责: 将聚合的结构化数据/分析结果转化为专业报告文字
模型: Claude Opus

这是所有 Agent 产出汇总的关键环节。它不产生新的分析洞察，
只负责将已有分析转化为流畅、专业、符合报告风格的文字。

输入: 完整的 ReportState (前面所有阶段的产出)
输出: 每个章节的完整文字内容

写作约束:
  - 使用专业但不过于晦涩的金融中文
  - 每章开头有 TL;DR (1-2 句核心要点)
  - 关键数字必须附带解释 (如 "ROE 28.5%，意味着每 100 元股东权益产生 28.5 元净利润")
  - 引用分析来源 (如 "根据我们的 DCF 估值...")
  - 风险提示用加粗/高亮标记
  - 不超过章节模板定义的字数上限

输出 schema:
{
  "sections": {
    "executive_summary": {
      "title": "投资摘要",
      "tldr": "贵州茅台——中国白酒龙头，稀缺的奢侈品消费标的。当前估值偏低...",
      "content": "...",
      "word_count": 350
    },
    "company_overview": {
      "title": "公司概况",
      "tldr": "...",
      "content": "...",
      "word_count": 500
    },
    "industry_analysis": {
      "title": "行业分析",
      "content": "...",
      "word_count": 800
    },
    "financial_analysis": {
      "title": "财务分析", 
      "content": "...",
      "word_count": 1200
    },
    "valuation": {
      "title": "估值分析",
      "content": "...",
      "word_count": 1000
    },
    "risk_assessment": {
      "title": "风险提示",
      "content": "...",
      "word_count": 600
    },
    "investment_recommendation": {
      "title": "投资建议",
      "content": "...",
      "word_count": 400
    }
  },
  "report_title": "贵州茅台 (600519.SH) 深度研究报告",
  "report_subtitle": "护城河坚固，估值具备吸引力",
  "report_date": "2026-05-17"
}
```

**Agent 13: 图表生成 Agent**

```
职责: 根据分析数据生成 matplotlib 图表
模型: 不需要 LLM！纯 Python + matplotlib/seaborn
(但有 LLM 接口用于理解"该生成什么图")

图表目录:

必需的图表 (深度研报):
  1. 股价走势图 (含关键事件标注)
  2. 营收/净利润趋势图 (双 Y 轴: 柱状图 + 增长率线)
  3. 盈利能力对比图 (ROE/ROA vs 同业)
  4. 估值区间图 (瀑布图: 从估值模型到目标价)
  5. 同业估值对比散点图 (市值 vs PE, 标的突出显示)
  6. 财务健康雷达图 (6 个维度)
  7. DCF 敏感性热力图 (3×3 矩阵)

可选图表:
  8. 毛利率 vs 净利率趋势
  9. 现金流构成瀑布图
  10. 杜邦分析拆解图

图表标准:
  - DPI: 150 (平衡清晰度和文件大小)
  - 格式: PNG base64 嵌入 HTML → PDF
  - 颜色: 统一色板 (#1a1a2e 深色系 + #e94560 强调)
  - 中文字体: SimHei / Microsoft YaHei
  - 尺寸: 宽度 800px, 高度自适应

输出 schema:
[
  {
    "chart_id": "price_chart",
    "title": "贵州茅台股价走势",
    "caption": "过去 3 年股价走势，标注了关键事件",
    "data": "base64_encoded_png",
    "position": "section_company_overview",
    "width_px": 800,
    "height_px": 400
  },
  ...
]
```

**Agent 14: 标题摘要 Agent**

```
职责: 生成报告标题、副标题、一页摘要、标签、SEO 元数据
模型: Claude Haiku (标题不需要深度推理)

输出 schema:
{
  "title": "贵州茅台 (600519.SH): 护城河坚固，估值具备吸引力",
  "subtitle": "深度研究报告 | 2026年5月",
  "one_liner": "中国最具护城河的白酒企业，当前估值提供 17.3% 上行空间",
  "tags": ["白酒", "消费", "价值投资", "高ROE", "股息"],
  "rating": {
    "overall": "买入",
    "financial_health": "优秀",
    "valuation": "低估",
    "growth": "稳健",
    "risk": "中等"
  },
  "disclaimer": "本报告由 AI 辅助生成，仅供参考，不构成投资建议..."
}
```

#### 模板引擎 (非 Agent，纯渲染管道)

```
技术栈:
  Jinja2 → HTML (带 CSS 打印样式)
  WeasyPrint → PDF
  python-docx → Word

Jinja2 模板变量:
  - {{ report_title }}, {{ subtitle }}
  - {{ disclaimer }}
  - {% for section in sections %}
    - {{ section.title }}, {{ section.tldr }}, {{ section.content }}
    - {% for chart in section.charts %}
      - {{ chart.data }} (base64 img)
      - {{ chart.caption }}
  - {{ analyst_name }}, {{ report_date }}

PDF 样式:
  - 纸张: A4
  - 页边距: 2.5cm (上下) 2cm (左右)
  - 字体: SimSun (正文) / SimHei (标题)
  - 字号: 11pt (正文) / 16pt (章标题) / 13pt (节标题)
  - 页眉: 报告标题 + 页码
  - 页脚: 免责声明 (小字 8pt)
  - 封面: 标题 + 副标题 + 日期 + 分析师 + 公司 logo
  - 目录: 自动生成 (从 h1/h2 提取)
```

### 5.3 可配置架构设计（核心架构决策 #14）

**设计原则**：一切皆可配置，不做硬编码。Agent 管线、LLM 选择、数据源链路、工作流编排全部通过 JSON 配置文件驱动。

#### 5.3.1 全局配置结构 (config.json)

```json
{
  "version": "1.0",
  "global": {
    "language": "zh-CN",
    "default_market": "auto",
    "data_priority": "local_first",
    "cache_root": "~/.investment_report_agent/cache",
    "max_report_token_budget": 200000
  },
  "llm_providers": {
    "provider_deep": {
      "provider": "anthropic",
      "model": "claude-opus-4-7",
      "temperature": 0.3,
      "max_tokens": 16000,
      "api_key_source": "env:ANTHROPIC_API_KEY",
      "timeout_seconds": 120
    },
    "provider_quick": {
      "provider": "anthropic",
      "model": "claude-haiku-4-5-20251001",
      "temperature": 0.3,
      "max_tokens": 8000,
      "api_key_source": "env:ANTHROPIC_API_KEY",
      "timeout_seconds": 60
    },
    "provider_openai_deep": {
      "provider": "openai",
      "model": "gpt-4o",
      "temperature": 0.3,
      "max_tokens": 16000,
      "api_key_source": "env:OPENAI_API_KEY"
    },
    "provider_deepseek": {
      "provider": "deepseek",
      "model": "deepseek-chat",
      "temperature": 0.3,
      "max_tokens": 16000,
      "api_key_source": "env:DEEPSEEK_API_KEY"
    },
    "provider_local": {
      "provider": "ollama",
      "model": "llama3.1:70b",
      "temperature": 0.3,
      "max_tokens": 16000,
      "base_url": "http://localhost:11434"
    }
  },
  "data_providers": {
    "providers": {
      "akshare": {
        "enabled": true,
        "priority": 1,
        "markets": ["CN"],
        "timeout_seconds": 30,
        "retry_count": 3,
        "cooldown_seconds": 2
      },
      "tushare": {
        "enabled": false,
        "priority": 2,
        "markets": ["CN"],
        "api_key_source": "env:TUSHARE_TOKEN",
        "timeout_seconds": 20,
        "retry_count": 2
      },
      "yahoo_finance": {
        "enabled": true,
        "priority": 1,
        "markets": ["US", "HK"],
        "timeout_seconds": 20,
        "retry_count": 2,
        "cooldown_seconds": 1.5
      },
      "sec_edgar": {
        "enabled": true,
        "priority": 2,
        "markets": ["US"],
        "timeout_seconds": 30,
        "retry_count": 2
      },
      "user_upload": {
        "enabled": true,
        "priority": 0,
        "markets": ["CN", "US", "HK"]
      },
      "wind": {
        "enabled": false,
        "priority": 1,
        "markets": ["CN"],
        "api_key_source": "env:WIND_API_KEY",
        "note": "Phase 2 启用"
      },
      "bloomberg": {
        "enabled": false,
        "priority": 1,
        "markets": ["US", "HK"],
        "api_key_source": "env:BLOOMBERG_API_KEY",
        "note": "Phase 2 启用"
      }
    },
    "fallback_chain": {
      "CN": ["user_upload", "akshare", "tushare"],
      "US": ["user_upload", "yahoo_finance", "sec_edgar"],
      "HK": ["user_upload", "yahoo_finance"]
    },
    "local_database": {
      "enabled": true,
      "path": "~/.investment_report_agent/local_data",
      "engines": ["sqlite", "duckdb"],
      "auto_sync_sources": ["akshare", "yahoo_finance"],
      "sync_schedule": "daily_at_20:00",
      "ttl_config": {
        "prices_daily": 86400,
        "prices_intraday": 300,
        "financials_quarterly": 86400,
        "financials_annual": 604800,
        "news": 1800,
        "macro": 86400,
        "industry_classification": 604800
      }
    }
  },
  "pipelines": {
    "deep_dive": {
      "name": "深度研报",
      "phases": {
        "phase_1_data_aggregation": {
          "parallel": true,
          "agents": ["price_data", "financial_data", "news_data", "macro_data"]
        },
        "phase_2_analysis": {
          "parallel": true,
          "agents": ["financial_analysis", "valuation", "industry_competition", "corporate_governance"]
        },
        "phase_3_debate": {
          "parallel": false,
          "agents": ["bull_case", "bear_case", "risk_judge"],
          "debate_rounds": 2
        },
        "phase_4_assembly": {
          "parallel": false,
          "agents": ["section_writer", "chart_generator", "title_summary"],
          "export": ["pdf", "docx"]
        }
      }
    },
    "brief": {
      "name": "快速简报",
      "phases": {
        "phase_1_data_aggregation": {
          "parallel": true,
          "agents": ["price_data", "financial_data", "news_data"]
        },
        "phase_2_analysis": {
          "parallel": true,
          "agents": ["financial_analysis", "valuation"]
        },
        "phase_3_debate": {
          "parallel": false,
          "agents": ["bull_case", "bear_case", "risk_judge"],
          "debate_rounds": 1
        },
        "phase_4_assembly": {
          "parallel": false,
          "agents": ["section_writer", "title_summary"],
          "export": ["pdf"]
        }
      }
    }
  },
  "agents": {
    "financial_analysis": {
      "llm": "provider_deep",
      "python_calculator": "financial_health_calculator",
      "tools": ["get_financial_metrics", "get_derived_ratios"],
      "output_schema": "FinancialHealthResult",
      "timeout_seconds": 120
    },
    "valuation": {
      "llm": "provider_deep",
      "python_calculator": "valuation_engine",
      "tools": ["get_financials_for_dcf", "get_peer_comps"],
      "output_schema": "ValuationResult",
      "timeout_seconds": 180
    },
    "bull_case": {
      "llm": "provider_deep",
      "tools": ["query_additional_data"],
      "output_schema": "DebateArguments",
      "timeout_seconds": 120
    },
    "section_writer": {
      "llm": "provider_deep",
      "tools": [],
      "output_schema": "ReportSections",
      "timeout_seconds": 300
    },
    "news_data": {
      "llm": "provider_quick",
      "tools": ["get_recent_news", "get_announcements"],
      "output_schema": "NewsAggregation",
      "timeout_seconds": 60
    },
    "title_summary": {
      "llm": "provider_quick",
      "tools": [],
      "output_schema": "ReportMetadata",
      "timeout_seconds": 30
    }
  },
  "templates_dir": "~/.investment_report_agent/templates",
  "reports_output_dir": "~/.investment_report_agent/reports",
  "logging": {
    "level": "INFO",
    "output": ["console", "file"],
    "file_path": "~/.investment_report_agent/logs/agent.log"
  }
}
```

#### 5.3.2 可配置架构的核心抽象

```
config.json
    │
    ▼
ConfigManager.load()
    │
    ├── LLMRegistry ──────── 按 agent 名称路由 LLM 实例
    │   内部: Dict[agent_name, ChatModel]
    │   agent_name → llm_provider_id → ChatModel 实例
    │
    ├── PipelineFactory ──── 根据 pipelines 配置构建 Agent 图
    │   内部: Phase[] → AgentNode[] → 执行图 (DAG)
    │   Phase.parallel: true → 并行执行; false → 串行执行
    │
    ├── DataProviderManager ─ 按 market 路由数据源，处理降级
    │   内部: Dict[market, [ProviderWrapper]]
    │   priority=0 (user_upload) → 永远最先查询
    │   后续按 priority 排序 + fallback_chain 降级
    │
    ├── LocalDatabaseManager ─ 管理本地 SQLite/DuckDB 数据库
    │   auto_sync 定时从配置的 sources 拉取数据
    │   查询时 always check local → miss → external API → save local
    │
    └── TemplateManager ───── 管理和验证报告模板
        内部: Dict[template_id, TemplateSpec]
        从 templates_dir 加载所有 .json 模板文件
```

#### 5.3.3 本地优先数据策略（Local-First）

```python
class LocalFirstDataProvider:
    """
    所有数据查询遵循: 本地 DB → 外部 API → 缓存
    
    用户上传的数据优先插入本地 DB，
    后续查询自动命中。
    """
    
    async def query(self, query: DataQuery) -> DataResult:
        # Step 1: 查本地数据库
        local_result = await self.local_db.query(query)
        if local_result and self._is_fresh(local_result, query.ttl):
            return local_result  # ← 本地命中，不调外部 API
        
        # Step 2: 查外部数据源（带降级）
        for provider in self.get_providers_for_market(query.market):
            try:
                external_result = await provider.query(query)
                if external_result:
                    # 写入本地 DB 供后续查询
                    await self.local_db.upsert(query.cache_key, external_result)
                    return external_result
            except ProviderError:
                continue  # 降级到下一个 provider
        
        # Step 3: 全部失败 → 返回本地陈旧数据 + 标记
        stale_result = await self.local_db.query(query, allow_stale=True)
        if stale_result:
            return DataResult(
                data=stale_result,
                stale=True,
                warnings=["所有外部数据源不可用，使用本地缓存数据"]
            )
        
        raise DataUnavailableError(f"无法获取 {query} 的数据")

    def _is_fresh(self, result, ttl_seconds):
        return (now() - result.created_at).seconds < ttl_seconds
```

#### 5.3.4 工作流编辑与版本管理

```
用户对 config.json 的修改：
  1. 直接编辑 JSON 文件 (MVP)
  2. Web UI 可视化编辑 (Phase 2)
  3. 对话式配置生成 (Phase 2)

配置版本管理：
  - config.json 纳入 git 管理
  - 每次报告生成时记录 config_hash → 可复现性
  - 提供预设配置模板:
    - config.quick.json  → 快速模式 (少 agents, 用 Haiku)
    - config.deep.json   → 深度模式 (所有 agents, 用 Opus)
    - config.cn.json     → A 股优化 (AkShare + Tushare)
    - config.us.json     → 美股优化 (Yahoo F. + SEC)
  
  用户自定义模板存放于 ~/.investment_report_agent/templates/
  预设模板存放于 系统安装目录
```

---

## 六、Python 计算层规格

### 6.1 计算层总览

所有涉及数学/统计的计算都在 Python 层完成，LLM 只消费计算结果。计算层是无状态的纯函数。

```
计算层模块结构:
calculators/
├── __init__.py
├── financial_ratios.py    # 财务比率计算 (28 个指标)
├── growth_metrics.py      # 增长率计算
├── valuation_engine.py    # 估值模型 (DCF / Owner Earnings / EV-EBITDA)
├── risk_metrics.py        # 风险指标 (波动率/Beta/最大回撤/Sharpe)
├── technical_indicators.py # 技术指标 (MA/MACD/RSI/Bollinger/ATR)
├── industry_comps.py      # 同业对比计算
├── sensitivity.py         # 敏感性分析矩阵
├── chart_data.py          # 图表数据准备
├── data_quality.py        # 数据质量评分
└── unit_normalizer.py     # 单位标准化 (万元→元, 港元→人民币)
```

### 6.2 财务比率计算详细规格 (financial_ratios.py)

```python
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class FinancialRatios:
    """28 个核心财务比率"""
    ticker: str
    report_date: str
    
    # === 盈利能力 (6) ===
    roe: Optional[float]              # Net Income / Avg Equity
    roa: Optional[float]              # Net Income / Avg Total Assets
    roic: Optional[float]             # NOPAT / Invested Capital
    gross_margin: Optional[float]     # (Revenue - COGS) / Revenue
    operating_margin: Optional[float]  # Operating Income / Revenue
    net_margin: Optional[float]       # Net Income / Revenue
    
    # === 成长性 (4) ===
    revenue_growth_yoy: Optional[float]
    earnings_growth_yoy: Optional[float]
    revenue_growth_3y_cagr: Optional[float]
    earnings_growth_3y_cagr: Optional[float]
    
    # === 偿债能力 (5) ===
    debt_to_equity: Optional[float]
    interest_coverage: Optional[float]
    current_ratio: Optional[float]
    quick_ratio: Optional[float]
    net_debt_to_ebitda: Optional[float]
    
    # === 运营效率 (4) ===
    asset_turnover: Optional[float]
    inventory_turnover: Optional[float]
    receivable_days: Optional[float]
    cash_conversion_cycle: Optional[float]
    
    # === 盈利质量 (4) ===
    fcf_to_net_income: Optional[float]
    ocf_to_revenue: Optional[float]
    accruals_ratio: Optional[float]   # (NI - OCF) / Avg Assets
    revenue_quality: Optional[float]  # OCF / Revenue
    
    # === 估值倍数 (5) ===
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    ps_ratio: Optional[float]
    ev_to_ebitda: Optional[float]
    fcf_yield: Optional[float]        # FCF / Market Cap


def calculate_all_ratios(
    income_statement: dict,
    balance_sheet: dict,
    cash_flow: dict,
    market_data: dict
) -> FinancialRatios:
    """
    从标准化的三表输入计算所有 28 个比率。
    
    输入格式 (从 DataProvider 层标准化后):
      income_statement: {
        "revenue": float, "cogs": float, "operating_income": float,
        "net_income": float, "eps_basic": float, "eps_diluted": float,
        "interest_expense": float, "tax_rate": float,
        "ebit": float, "ebitda": float
      }
      balance_sheet: {
        "total_assets": float, "total_liabilities": float,
        "total_equity": float, "current_assets": float,
        "current_liabilities": float, "cash_and_equivalents": float,
        "total_debt": float, "inventory": float,
        "accounts_receivable": float, "accounts_payable": float,
        "goodwill": float, "intangible_assets": float
      }
      cash_flow: {
        "operating_cash_flow": float,
        "capex": float,
        "free_cash_flow": float  # 或 OCF - Capex
      }
      market_data: {
        "market_cap": float,
        "enterprise_value": float,
        "shares_outstanding": float,
        "current_price": float
      }
    
    所有计算处理:
      - 分母为 0 → None (而不是除零错误)
      - 缺失输入 → 对应的比率标记为 None
      - 负值 → 保留（如负 ROE）
    """
    i, b, c, m = income_statement, balance_sheet, cash_flow, market_data
    
    # 辅助: 计算平均值 (处理缺失)
    def avg(a, b_val):
        if a is None or b_val is None:
            return None
        return (a + b_val) / 2
    
    # 盈利能力
    roe = i["net_income"] / avg(b["total_equity"], prev_year["total_equity"]) \
        if all([i.get("net_income"), b.get("total_equity")]) else None
    
    gross_margin = (i["revenue"] - i["cogs"]) / i["revenue"] \
        if i.get("revenue") and i.get("cogs") and i["revenue"] != 0 else None
    
    # ... (28 个比率的完整计算逻辑)
    
    return FinancialRatios(...)
```

### 6.3 估值引擎详细规格 (valuation_engine.py)

```python
from dataclasses import dataclass
from enum import Enum
import numpy as np

class ValuationModel(Enum):
    DCF_THREE_STAGE = "dcf_three_stage"
    OWNER_EARNINGS = "owner_earnings"
    EV_EBITDA = "ev_ebitda"
    RESIDUAL_INCOME = "residual_income"

@dataclass
class ValuationParams:
    """估值参数 — 可在 config.json 中覆盖"""
    # DCF 参数
    risk_free_rate_cn: float = 0.0172     # 中国 10Y 国债
    risk_free_rate_us: float = 0.0425     # 美国 10Y 国债
    risk_free_rate_hk: float = 0.0350     # 香港 10Y 国债
    equity_risk_premium_cn: float = 0.06
    equity_risk_premium_us: float = 0.05
    equity_risk_premium_hk: float = 0.065
    terminal_growth: float = 0.03         # 永续增长率
    stage1_years: int = 5
    stage1_growth_cap: float = 0.15       # 高增长上限
    stage2_years: int = 5
    
    # Owner Earnings 参数
    owner_earnings_discount: float = 0.09
    owner_earnings_mos: float = 0.25      # Margin of Safety
    
    # EV/EBITDA 参数
    premium_for_roe_2x: float = 0.15      # ROE 超行业 2 倍 → 溢价 15%
    premium_for_growth_edge: float = 0.10  # 增长领先 → 溢价 10%
    
    # RI 参数
    ri_mos: float = 0.20
    
    # 权重
    weight_dcf: float = 0.35
    weight_owner_earnings: float = 0.35
    weight_ev_ebitda: float = 0.20
    weight_ri: float = 0.10

@dataclass
class ValuationResult:
    ticker: str
    current_price: float
    market_cap: float
    models: dict  # {model_name: {per_share_value, upside_pct, assumptions}}
    weighted_value: float
    weighted_upside_pct: float
    sensitivity_matrix: dict  # {wacc_range, growth_range, values[][]}
    signal: str  # "undervalued" / "fair" / "overvalued"


def calculate_dcf_three_stage(
    free_cash_flows: list[float],
    params: ValuationParams,
    market: str  # "CN" | "US" | "HK"
) -> dict:
    """
    三阶段 DCF 模型:
    
    Stage 1 (高增长, params.stage1_years 年):
      growth = min(historical_FCF_CAGR × 0.8, params.stage1_growth_cap)
      FCF_t = FCF_0 × (1 + growth)^t
    
    Stage 2 (过渡, params.stage2_years 年):
      growth 线性衰减到 terminal_growth
      每年: g_t = g_stage1 + t × (g_terminal - g_stage1) / stage2_years
    
    Stage 3 (永续):
      终端价值 = FCF_stage2_last × (1 + g_terminal) / (WACC - g_terminal)
    """
    # 选择无风险利率
    rf = {
        "CN": params.risk_free_rate_cn,
        "US": params.risk_free_rate_us,
        "HK": params.risk_free_rate_hk,
    }.get(market, params.risk_free_rate_us)
    
    # 计算 WACC
    cost_of_equity = rf + beta * params.equity_risk_premium_cn
    cost_of_debt = (interest_expense / total_debt) if total_debt > 0 else rf + 0.02
    wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))
    
    # Stage 1 投影
    stage1_growth = min(historical_fcf_cagr * 0.8, params.stage1_growth_cap)
    stage1_fcfs = [last_fcf * (1 + stage1_growth)**t for t in range(1, params.stage1_years + 1)]
    
    # Stage 2 投影
    stage2_fcfs = []
    for t in range(1, params.stage2_years + 1):
        g = stage1_growth + t * (params.terminal_growth - stage1_growth) / params.stage2_years
        prev = stage2_fcfs[-1] if stage2_fcfs else stage1_fcfs[-1]
        stage2_fcfs.append(prev * (1 + g))
    
    # 终端价值
    terminal_fcf = stage2_fcfs[-1] * (1 + params.terminal_growth)
    terminal_value = terminal_fcf / (wacc - params.terminal_growth)
    
    # 折现所有现金流
    all_cashflows = stage1_fcfs + stage2_fcfs + [terminal_value]
    pv_fcfs = sum(cf / (1 + wacc)**(i+1) for i, cf in enumerate(all_cashflows[:-1]))
    pv_terminal = terminal_value / (1 + wacc)**(params.stage1_years + params.stage2_years)
    
    enterprise_value = pv_fcfs + pv_terminal
    equity_value = enterprise_value - net_debt + cash - minority_interest
    per_share_value = equity_value / shares_outstanding
    
    return {
        "per_share_value": round(per_share_value, 2),
        "wacc": round(wacc * 100, 2),  # 百分比
        "stage1_growth": round(stage1_growth * 100, 2),
        "terminal_value_share": round(pv_terminal / enterprise_value * 100, 1),
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
    }


def calculate_owner_earnings_value(
    financial_data: dict,
    params: ValuationParams,
) -> dict:
    """
    Buffett 风格 Owner Earnings 估值:
    
    Owner Earnings = Net Income 
                   + Depreciation & Amortization
                   - Maintenance Capex
                   - Change in Net Working Capital
    
    Maintenance Capex 估算（三种方法的中间值）:
      1. Total Capex × 0.85
      2. Depreciation (维持性 = 折旧)
      3. Total Capex × avg(历年 D&A/Capex 比率)
    """
    # 计算 Owner Earnings
    net_income = financial_data["net_income"]
    da = financial_data["depreciation_amortization"]
    total_capex = financial_data["capex"]
    
    # 三种 Maintenance Capex 估算
    maint1 = total_capex * 0.85
    maint2 = da
    # 历史比率
    historical_ratios = [
        d / c for d, c in zip(historical_da, historical_capex) if c > 0
    ]
    avg_ratio = np.median(historical_ratios) if historical_ratios else 1.0
    maint3 = total_capex * avg_ratio
    
    maintenance_capex = np.median([maint1, maint2, maint3])
    
    # NWC 变动
    nwc_current = financial_data["current_assets"] - financial_data["current_liabilities"]
    nwc_previous = prev_financial_data["current_assets"] - prev_financial_data["current_liabilities"]
    delta_nwc = nwc_current - nwc_previous
    
    owner_earnings = net_income + da - maintenance_capex - delta_nwc
    
    # 5 年 DCF + 终端价值 (折现率 9%, 永续增长 3%)
    discount = params.owner_earnings_discount
    terminal_growth = params.terminal_growth
    
    oe_projections = [owner_earnings * (1 + terminal_growth)**t for t in range(1, 6)]
    terminal_value = oe_projections[-1] * (1 + terminal_growth) / (discount - terminal_growth)
    
    pv_projections = sum(oe / (1 + discount)**(i+1) for i, oe in enumerate(oe_projections))
    pv_terminal = terminal_value / (1 + discount)**5
    
    intrinsic_value = (pv_projections + pv_terminal) * (1 - params.owner_earnings_mos)
    per_share_value = intrinsic_value / shares_outstanding
    
    return {
        "per_share_value": round(per_share_value, 2),
        "owner_earnings": round(owner_earnings, 2),
        "maintenance_capex": round(maintenance_capex, 2),
        "mos_applied": params.owner_earnings_mos,
    }


def calculate_sensitivity_matrix(
    base_wacc: float,
    base_growth: float,
    base_value: float,
    valuation_func,
    wacc_range: tuple = (0.075, 0.095, 0.01),
    growth_range: tuple = (0.025, 0.035, 0.005),
) -> dict:
    """
    3×3 敏感性矩阵:
    
    行: WACC (base - 1%, base, base + 1%)
    列: Terminal Growth (base - 0.5%, base, base + 0.5%)
    值: 每股价值
    
    输出格式:
    {
      "wacc_values": [7.5, 8.5, 9.5],         # %
      "growth_values": [2.5, 3.0, 3.5],       # %
      "matrix": [
        [2250, 2050, 1900],
        [2100, 1950, 1800],
        [1980, 1850, 1720]
      ]
    }
    """
    waccs = [base_wacc + i * wacc_range[2] for i in [-1, 0, 1]]
    growths = [base_growth + i * growth_range[2] for i in [-0.5, 0.5]]
    
    matrix = []
    for w in waccs:
        row = []
        for g in growths:
            val = valuation_func(wacc=w, growth=g)
            row.append(round(val["per_share_value"], 2))
        matrix.append(row)
    
    return {
        "wacc_values": waccs,
        "growth_values": growths,
        "matrix": matrix,
    }
```

### 6.4 技术指标计算规格 (technical_indicators.py)

```python
import pandas as pd
import numpy as np

def calculate_ma(df: pd.DataFrame, periods: list[int] = [5,10,20,60,120,250]) -> dict:
    """移动平均线"""
    result = {}
    for p in periods:
        result[f"MA{p}"] = df["close"].rolling(p).mean().iloc[-1]
        result[f"MA{p}_trend"] = "up" if result[f"MA{p}"] > df["close"].iloc[-1] else "down"
    return result

def calculate_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> dict:
    """MACD 指标"""
    ema_fast = df["close"].ewm(span=fast).mean()
    ema_slow = df["close"].ewm(span=slow).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal).mean()
    histogram = 2 * (dif - dea)
    
    latest = {
        "dif": round(dif.iloc[-1], 4),
        "dea": round(dea.iloc[-1], 4),
        "histogram": round(histogram.iloc[-1], 4),
        "signal": "golden_cross" if dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]
             else "death_cross" if dif.iloc[-1] < dea.iloc[-1] and dif.iloc[-2] >= dea.iloc[-2]
             else "bullish" if dif.iloc[-1] > dea.iloc[-1]
             else "bearish"
    }
    return latest

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> dict:
    """RSI 指标"""
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/period).mean()
    avg_loss = loss.ewm(alpha=1/period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    val = rsi.iloc[-1]
    return {
        "value": round(val, 2),
        "signal": "overbought" if val > 70 else "oversold" if val < 30 else "neutral"
    }

def calculate_bollinger_bands(df: pd.DataFrame, period=20, std=2.0) -> dict:
    """布林带"""
    ma = df["close"].rolling(period).mean()
    std_dev = df["close"].rolling(period).std()
    upper = ma + std * std_dev
    lower = ma - std * std_dev
    
    current = df["close"].iloc[-1]
    upper_val, lower_val = upper.iloc[-1], lower.iloc[-1]
    
    return {
        "upper": round(upper_val, 2),
        "middle": round(ma.iloc[-1], 2),
        "lower": round(lower_val, 2),
        "bandwidth_pct": round((upper_val - lower_val) / ma.iloc[-1] * 100, 2),
        "position": "above_upper" if current > upper_val
               else "below_lower" if current < lower_val
               else "inside"
    }

def calculate_beta(df_stock: pd.DataFrame, df_benchmark: pd.DataFrame, period=252) -> float:
    """Beta 系数"""
    returns_stock = df_stock["close"].pct_change().dropna()
    returns_benchmark = df_benchmark["close"].pct_change().dropna()
    aligned = pd.concat([returns_stock, returns_benchmark], axis=1).dropna()
    cov = aligned.cov().iloc[0, 1]
    var = aligned.iloc[:, 1].var()
    return round(cov / var, 2) if var > 0 else None

def calculate_sharpe_ratio(returns: pd.Series, rf_annual: float = 0.03) -> float:
    """夏普比率 (年化)"""
    excess = returns - rf_annual / 252
    return round(np.sqrt(252) * excess.mean() / returns.std(), 2)

def calculate_max_drawdown(returns: pd.Series) -> dict:
    """最大回撤"""
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = drawdown.min()
    max_dd_date = drawdown.idxmin()
    return {
        "max_drawdown_pct": round(max_dd * 100, 2),
        "date": max_dd_date,
        "recovery_days": (cumulative[drawdown.idxmin():].idxmax() - max_dd_date).days
    }
```

### 6.5 图表数据准备规格 (chart_data.py)

```python
from dataclasses import dataclass
from typing import Optional
import base64
from io import BytesIO
import matplotlib
matplotlib.use("Agg")  # 非 GUI 后端
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

# 统一视觉配置
CHART_STYLE = {
    "font_family": "sans-serif",
    "font_sans_serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
    "color_palette": ["#1a1a2e", "#16213e", "#0f3460", "#e94560", "#533483"],
    "bg_color": "#ffffff",
    "grid_color": "#e0e0e0",
    "dpi": 150,
    "figsize_default": (10, 5),
}

plt.rcParams.update({
    "font.family": CHART_STYLE["font_family"],
    "font.sans-serif": CHART_STYLE["font_sans_serif"],
    "axes.grid": True,
    "grid.alpha": 0.3,
})

@dataclass
class ChartOutput:
    chart_id: str
    title: str
    caption: str
    png_base64: str
    width_px: int
    height_px: int

def make_price_chart(df: pd.DataFrame, ticker: str, events: list[dict] = None) -> ChartOutput:
    """
    股价走势图:
    - 收盘价折线
    - 填充背景
    - 关键事件竖线标注
    - 右侧价格标尺
    """
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    
    ax.plot(df.index, df["close"], color=CHART_STYLE["color_palette"][0], linewidth=1.5)
    ax.fill_between(df.index, df["close"], alpha=0.1, color=CHART_STYLE["color_palette"][0])
    
    # 关键事件标注
    if events:
        for event in events:
            ax.axvline(x=event["date"], color=CHART_STYLE["color_palette"][3], 
                      linestyle="--", alpha=0.7, linewidth=1)
            ax.annotate(event["label"], xy=(event["date"], df["close"].max()),
                       rotation=90, fontsize=8, color="#e94560")
    
    ax.set_title(f"{ticker} 股价走势", fontsize=14, fontweight="bold")
    ax.set_xlabel("日期", fontsize=10)
    ax.set_ylabel("价格", fontsize=10)
    
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    
    return ChartOutput(
        chart_id="price_chart",
        title=f"{ticker} 股价走势",
        caption=f"时间区间: {df.index[0].strftime('%Y-%m-%d')} 至 {df.index[-1].strftime('%Y-%m-%d')}",
        png_base64=base64.b64encode(buf.getvalue()).decode(),
        width_px=1000,
        height_px=500,
    )
```

---

## 七、API 与数据模型

### 7.1 REST API 设计

```
Base URL: /api/v1

认证: Bearer <jwt_token> (Authorization header)

════════════════════════════════════════════════
报告生成
════════════════════════════════════════════════

POST   /report/generate          → 创建报告任务
  Body: {
    "ticker": "600519.SH",
    "report_type": "deep_dive",      # deep_dive|brief|macro_weekly|ipo
    "template_id": "default_deep",   # 模板 ID
    "start_date": "2020-01-01",      # 分析起始日, optional
    "end_date": "2026-05-17",        # 分析截止日, optional
    "uploaded_file_ids": ["f1", "f2"],  # 用户上传文件引用
    "custom_params": {                # 覆盖全局配置
      "debate_rounds": 3,
      "llm_provider": "provider_openai_deep",
      "valuation_models": ["dcf", "owner_earnings"],
    }
  }
  → 201 { "task_id": "uuid", "status": "queued", "estimated_seconds": 120 }

GET    /report/{task_id}/status  → 查询任务状态
  → 200 {
    "task_id": "uuid",
    "status": "running",               # queued|running|completed|failed
    "current_phase": "phase_3_debate", # 当前阶段
    "progress_pct": 72,
    "current_agent": "bear_case",      # 当前执行的 agent
    "started_at": "2026-05-17T10:30:00Z",
    "estimated_completion": "2026-05-17T10:32:00Z"
  }

GET    /report/{task_id}/stream  → SSE 流式进度
  event: progress
  data: {"phase": "phase_2_analysis", "agent": "valuation", "progress_pct": 55}
  
  event: agent_output
  data: {"agent": "valuation", "partial_result": {...}}
  
  event: complete
  data: {"task_id": "uuid", "report_id": "rpt_xxx"}

GET    /report/{report_id}       → 获取完整报告 (JSON)
  → 200 { ReportState }

GET    /report/{report_id}/pdf   → 下载 PDF
GET    /report/{report_id}/docx  → 下载 Word

════════════════════════════════════════════════
模板管理
════════════════════════════════════════════════

GET    /template                 → 列出所有模板
POST   /template                 → 创建新模板
GET    /template/{template_id}   → 获取模板详情
PUT    /template/{template_id}   → 更新模板
DELETE /template/{template_id}   → 删除模板（仅用户创建的）

════════════════════════════════════════════════
数据上传
════════════════════════════════════════════════

POST   /upload                   → 上传文件
  Content-Type: multipart/form-data
  Fields: file, ticker, file_type (annual_report|quarterly_report|financial_model|csv_data)
  → 201 { "file_id": "uuid", "file_name": "xxx.pdf", "status": "processing" }

GET    /upload/{file_id}/status  → 查询解析状态
  → 200 { "status": "ready", "extracted_data": {...}, "warnings": [...] }

════════════════════════════════════════════════
用户与订阅
════════════════════════════════════════════════

POST   /auth/register            → 注册
POST   /auth/login               → 登录 → { access_token, refresh_token }
GET    /user/me                  → 当前用户信息
GET    /user/usage               → 本月用量: { reports_generated: 3, reports_limit: 10 }
PUT    /user/settings            → 更新设置 (默认 LLM provider、语言等)

════════════════════════════════════════════════
配置管理
════════════════════════════════════════════════

GET    /config                   → 获取当前生效配置
PUT    /config                   → 更新部分配置 (merge)
POST   /config/validate          → 验证配置文件
GET    /config/presets           → 列出预设配置 (quick/deep/cn/us)
POST   /config/presets/{name}/activate → 激活预设配置
```

### 7.2 SSE 进度协议

```
Client: GET /report/{task_id}/stream
Server:
  HTTP/1.1 200 OK
  Content-Type: text/event-stream
  Cache-Control: no-cache
  Connection: keep-alive
  
  event: phase_start
  data: {"phase": "phase_1_data_aggregation", "timestamp": "..."}
  
  event: agent_start
  data: {"phase": "phase_1_data_aggregation", "agent": "price_data", "agent_id": 1}
  
  event: agent_progress
  data: {"agent": "price_data", "progress_pct": 50, "message": "正在获取行情数据..."}
  
  event: agent_complete
  data: {"agent": "price_data", "duration_seconds": 3.2, "summary": "获取 5 年日线数据成功"}
  
  event: agent_output
  data: {"agent": "financial_analysis", "partial": {"roe": 28.5, "rating": "EXCELLENT"}}
  
  event: debate_round
  data: {"round": 1, "bull_argument_count": 4, "bear_argument_count": 3}
  
  event: error
  data: {"agent": "news_data", "error": "数据源超时，使用本地缓存", "severity": "warning"}
  
  event: complete
  data: {"report_id": "rpt_abc123", "total_duration_seconds": 85.3}
```

### 7.3 核心 Pydantic 模型

```python
from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, Literal
from uuid import UUID, uuid4

class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: str
    subscription_tier: Literal["free", "pro", "enterprise"]
    reports_this_month: int = 0
    reports_limit: int = 3  # free tier
    preferred_language: str = "zh-CN"
    created_at: datetime

class ReportTask(BaseModel):
    task_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    ticker: str
    report_type: Literal["deep_dive", "brief", "macro_weekly", "ipo"]
    template_id: str
    status: Literal["queued", "running", "completed", "failed"]
    current_phase: Optional[str]
    progress_pct: float = 0.0
    config_hash: str  # 配置快照，保证可复现
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result_report_id: Optional[UUID]

class FileUpload(BaseModel):
    file_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    original_filename: str
    file_type: str  # annual_report, quarterly_report, financial_model, csv_data
    ticker: str
    status: Literal["uploading", "processing", "ready", "failed"]
    extracted_data: Optional[dict]  # 解析后结构化数据
    page_count: Optional[int]
    warnings: list[str] = []
```

---

## 八、UI/UX 交互设计

### 8.1 页面结构

```
┌──────────────────────────────────────────────────────────────┐
│  Header                                                       │
│  [Logo] Investment Report Agent    [模板] [配置] [用户] [设置] │
├──────────┬───────────────────────────────────────────────────┤
│          │                                                    │
│  侧边栏   │              主内容区                               │
│          │                                                    │
│  📁 报告  │   ┌─────────────────────────────────────────────┐ │
│  ├ 最近  │   │  对话窗口 (Chat)                             │ │
│  ├ 全部  │   │  ┌───────────────────────────────────────┐   │ │
│  └ 归档  │   │  │ User: 分析贵州茅台，生成深度研报       │   │ │
│          │   │  │ AI: 好的，我将为您生成贵州茅台的深度   │   │ │
│  📊 模板  │   │  │     研究报告。请稍候...               │   │ │
│  ├ 预设  │   │  │                                       │   │ │
│  └ 我的  │   │  │ 📊 Phase 1: 数据采集 [████████░░] 75% │   │ │
│          │   │  │    ✓ 行情数据 (3.2s)                  │   │ │
│  ⚙ 配置  │   │  │    ✓ 财报数据 (5.1s)                  │   │ │
│  ├ LLM   │   │  │    ⏳ 新闻公告 (进行中...)            │   │ │
│  ├ 数据源 │   │  │    ⏸ 宏观行业 (等待中)              │   │ │
│  ├ 管线  │   │  │                                       │   │ │
│  └ 缓存  │   │  │ 生成完成后:                            │   │ │
│          │   │  │ ┌─────────────────────────────────┐    │   │ │
│  💬 用量  │   │  │ │ 📄 报告已生成 [预览] [PDF] [Word]│   │   │ │
│  3/10本月│   │  │ └─────────────────────────────────┘    │   │ │
│          │   │  └───────────────────────────────────────┘   │ │
│          │   │                                               │ │
│          │   │  [输入框: 输入公司名或股票代码...] [📎上传]     │ │
│          │   └─────────────────────────────────────────────┘ │
│          │                                                    │
└──────────┴───────────────────────────────────────────────────┘
```

### 8.2 报告预览页面

```
┌──────────────────────────────────────────────┐
│ ← 返回对话     [PDF 导出]  [Word 导出]  [分享] │
├──────────────────────────────────────────────┤
│                                               │
│   ┌───────────────────────────────────────┐  │
│   │          报告封面                       │  │
│   │  贵州茅台 (600519.SH)                  │  │
│   │  护城河坚固，估值具备吸引力             │  │
│   │  深度研究报告 | 2026年5月              │  │
│   └───────────────────────────────────────┘  │
│                                               │
│   ┌───────────────────────────────────────┐  │
│   │  目录 (可点击跳转)                     │  │
│   │  1. 投资摘要 ───────────────── p.2    │  │
│   │  2. 公司概况 ───────────────── p.3    │  │
│   │  3. 行业分析 ───────────────── p.5    │  │
│   │  4. 财务分析 ───────────────── p.8    │  │
│   │  5. 估值分析 ───────────────── p.12   │  │
│   │  6. 风险提示 ───────────────── p.16   │  │
│   │  7. 投资建议 ───────────────── p.18   │  │
│   └───────────────────────────────────────┘  │
│                                               │
│   ┌───────────────────────────────────────┐  │
│   │  1. 投资摘要                            │  │
│   │  ┌─────────────────────────────────┐  │  │
│   │  │ TL;DR: 贵州茅台——中国白酒龙头...  │  │  │
│   │  │                                  │  │  │
│   │  │ [评分卡片]                        │  │  │
│   │  │ 财务健康: ★★★★★ 优秀             │  │  │
│   │  │ 估值水平: ★★★★☆ 低估             │  │  │
│   │  │ 成长前景: ★★★☆☆ 稳健             │  │  │
│   │  │ 风险等级: ★★★☆☆ 中等             │  │  │
│   │  │ 综合评级: 买入                    │  │  │
│   │  └─────────────────────────────────┘  │  │
│   │  ...                                  │  │
│   └───────────────────────────────────────┘  │
│                                               │
│   ┌───────────────────────────────────────┐  │
│   │  4. 财务分析                            │  │
│   │                                       │  │
│   │  [营收/净利润趋势图]                    │  │
│   │  ┌─────────────────────────────────┐  │  │
│   │  │   ▲                              │  │  │
│   │  │   │    ██  ██                    │  │  │
│   │  │   │ ██  ██  ██  ██              │  │  │
│   │  │   └──────────────────────────    │  │  │
│   │  │   2021 2022 2023 2024 2025       │  │  │
│   │  └─────────────────────────────────┘  │  │
│   │                                       │  │
│   │  [盈利能力对比表 (vs 行业)]            │  │
│   │  ┌──────────┬───────┬───────┬──────┐  │  │
│   │  │   指标    │ 茅台  │ 行业均值│ 评价 │  │  │
│   │  │ ROE      │ 28.5% │ 12.5% │ ★★★ │  │  │
│   │  │ 毛利率    │ 91.2% │ 65.0% │ ★★★ │  │  │
│   │  └──────────┴───────┴───────┴──────┘  │  │
│   └───────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### 8.3 模板编辑器 (Phase 2)

```
┌──────────────────────────────────────────────────────┐
│ 模板编辑器                                            │
├──────────┬───────────────────────────────────────────┤
│          │                                            │
│  组件库   │         画布 (拖拽编辑)                     │
│          │  ┌─────────────────────────────────────┐  │
│  📝 章节  │  │ 1. 投资摘要                          │  │
│  ├ 标题  │  │    类型: executive_summary            │  │
│  ├ 正文  │  │    Agent: summary_agent               │  │
│  ├ TLDR │  │    字数限制: 400                       │  │
│  └ 列表  │  │    [编辑] [删除] [上移] [下移]          │  │
│          │  ├─────────────────────────────────────┤  │
│  📊 图表  │  │ 2. 公司概况                          │  │
│  ├ 走势图 │  │    ...                               │  │
│  ├ 雷达图 │  ├─────────────────────────────────────┤  │
│  ├ 散点图 │  │ 3. 行业分析                          │  │
│  └ 瀑布图 │  │    ...                               │  │
│          │  └─────────────────────────────────────┘  │
│  📋 表格  │                                            │
│  ├ 对比表 │  [+ 添加新章节]                             │
│  └ 评分表 │                                            │
│          │                                            │
│  🏷 标签  │  章节属性面板                               │
│  └ 评分  │  ┌─────────────────────────────────────┐  │
│          │  │ 章节 ID:   executive_summary         │  │
│          │  │ 标题:     投资摘要                    │  │
│          │  │ Agent:    [summary_agent ▼]         │  │
│          │  │ 字数限制:  [400]                     │  │
│          │  │ 必含内容:  [TLDR, 核心结论, 评级]     │  │
│          │  │ 关联图表:  [无]                      │  │
│          │  └─────────────────────────────────────┘  │
└──────────┴───────────────────────────────────────────┘
```

---

## 九、报告模板系统

### 9.1 模板 JSON Schema

```json
{
  "$schema": "https://investment-report-agent.dev/schemas/template-v1.json",
  "template_id": "deep_dive_default",
  "name": "深度研报 (默认)",
  "version": "1.0",
  "author": "system",
  "description": "适用于 A 股/港股/美股的个股深度研究报告",
  "applicable_markets": ["CN", "HK", "US"],
  "report_type": "deep_dive",
  
  "structure": {
    "cover": {
      "elements": [
        {"type": "logo", "src": "{{company_logo}}", "width": 120},
        {"type": "title", "text": "{{report_title}}", "font_size": 28, "bold": true},
        {"type": "subtitle", "text": "{{report_subtitle}}", "font_size": 16},
        {"type": "meta_line", "text": "{{report_date}} | {{analyst_name}}"},
        {"type": "disclaimer", "text": "{{disclaimer}}", "font_size": 8}
      ]
    },
    
    "toc": {
      "enabled": true,
      "max_depth": 2
    },
    
    "sections": [
      {
        "id": "executive_summary",
        "title": "投资摘要",
        "agent": "section_writer",
        "subagent_override": "summary_agent",
        "max_words": 500,
        "required_elements": [
          {"type": "tldr", "label": "核心观点"},
          {"type": "rating_card", "label": "综合评分"},
          {"type": "key_numbers", "label": "关键数据", "fields": ["当前价格", "目标价格", "上行空间", "评级"]}
        ],
        "charts": []
      },
      {
        "id": "company_overview",
        "title": "公司概况",
        "agent": "section_writer",
        "max_words": 800,
        "required_elements": [
          {"type": "text", "label": "公司简介"},
          {"type": "text", "label": "业务结构"},
          {"type": "text", "label": "股权结构"},
          {"type": "text", "label": "管理层简介"}
        ],
        "charts": ["price_chart"]
      },
      {
        "id": "industry_analysis",
        "title": "行业分析",
        "agent": "section_writer",
        "max_words": 1200,
        "required_elements": [
          {"type": "text", "label": "行业概况"},
          {"type": "text", "label": "波特五力分析"},
          {"type": "text", "label": "竞争格局"},
          {"type": "text", "label": "行业趋势"}
        ],
        "charts": ["peer_comparison_scatter", "market_share_pie"]
      },
      {
        "id": "financial_analysis",
        "title": "财务分析",
        "agent": "section_writer",
        "max_words": 1500,
        "required_elements": [
          {"type": "text", "label": "盈利能力分析"},
          {"type": "table", "label": "核心财务指标", "source": "financial_ratios"},
          {"type": "text", "label": "成长性分析"},
          {"type": "text", "label": "财务健康度评估"},
          {"type": "text", "label": "盈利质量评估"}
        ],
        "charts": ["revenue_earnings_trend", "profitability_radar", "margin_trend"]
      },
      {
        "id": "valuation",
        "title": "估值分析",
        "agent": "section_writer",
        "max_words": 1200,
        "required_elements": [
          {"type": "text", "label": "估值方法概述"},
          {"type": "table", "label": "估值结果汇总", "source": "valuation_results"},
          {"type": "text", "label": "敏感性分析"},
          {"type": "text", "label": "同业估值对比"}
        ],
        "charts": ["valuation_waterfall", "sensitivity_heatmap", "peer_valuation_scatter"]
      },
      {
        "id": "risk_assessment",
        "title": "风险提示",
        "agent": "section_writer",
        "subagent_override": "risk_writer",
        "max_words": 800,
        "required_elements": [
          {"type": "text", "label": "核心风险"},
          {"type": "text", "label": "风险缓解因素"},
          {"type": "table", "label": "风险矩阵", "source": "key_risks"}
        ],
        "charts": []
      },
      {
        "id": "investment_recommendation",
        "title": "投资建议",
        "agent": "section_writer",
        "max_words": 500,
        "required_elements": [
          {"type": "rating_box", "label": "投资评级"},
          {"type": "text", "label": "核心逻辑"},
          {"type": "text", "label": "催化剂"},
          {"type": "text", "label": "目标价格及情景分析"}
        ],
        "charts": []
      }
    ],
    
    "appendix": {
      "enabled": true,
      "sections": [
        {"id": "disclaimer", "title": "免责声明"},
        {"id": "methodology", "title": "分析方法说明"},
        {"id": "glossary", "title": "术语表"}
      ]
    }
  },
  
  "style": {
    "page": {
      "size": "A4",
      "margin_top_mm": 25,
      "margin_bottom_mm": 20,
      "margin_left_mm": 20,
      "margin_right_mm": 20
    },
    "fonts": {
      "heading": {"family": "SimHei", "size_pt": 16, "color": "#1a1a2e"},
      "subheading": {"family": "SimHei", "size_pt": 13, "color": "#16213e"},
      "body": {"family": "SimSun", "size_pt": 11, "color": "#333333"},
      "caption": {"family": "SimSun", "size_pt": 9, "color": "#666666"},
      "footer": {"family": "SimSun", "size_pt": 8, "color": "#999999"}
    },
    "header": {
      "left": "{{report_title}}",
      "right": "{{page_number}}"
    },
    "footer": {
      "center": "本报告由 AI 辅助生成，仅供参考，不构成投资建议。请参阅文末免责声明。"
    },
    "colors": {
      "primary": "#1a1a2e",
      "secondary": "#16213e",
      "accent": "#e94560",
      "buy": "#00b894",
      "sell": "#e94560",
      "hold": "#fdcb6e",
      "background": "#ffffff"
    }
  }
}
```

### 9.2 预设模板一览

| 模板名称 | 适用场景 | 章节数 | 图表数 | 字数估算 |
|---------|---------|--------|--------|---------|
| 深度研报 (默认) | 个股全面分析 | 7 章 | 10 | ~7000 字 |
| 快速简报 | 快速覆盖一个标的 | 4 章 | 4 | ~2500 字 |
| 新股覆盖 (IPO) | 新股上市分析 | 6 章 | 6 | ~5000 字 |
| 宏观周报 | 一周宏观总结 | 5 章 | 5 | ~4000 字 |
| 同业对比 | 多家同业横评 | 5 章 | 6 | ~6000 字 |
| Pitch Book | 投行交易材料 | 8 章 | 8 | ~5000 字 |

---

## 十、测试与质量保证策略

### 10.1 测试金字塔

```
                    ┌──────────────┐
                    │   E2E 测试    │  ← 10%: 完整报告生成 + PDF 验证
                    │  (少量, 关键)  │
                    ├──────────────┤
                    │  集成测试     │  ← 30%: Agent 协作正确性
                    │  (Agent 管线) │
                    ├──────────────┤
                    │   单元测试    │  ← 60%: Python 计算层
                    │  (纯函数)     │
                    └──────────────┘
```

### 10.2 单元测试规格 (Python 计算层)

```python
# tests/calculators/test_financial_ratios.py

class TestFinancialRatios:
    def test_roe_zero_equity_returns_none(self):
        """分母为 0 时返回 None 而非除零错误"""
        ...
    
    def test_all_inputs_none_all_outputs_none(self):
        """所有输入缺失时所有输出为 None"""
        ...
    
    def test_roe_matches_hand_calculation(self):
        """ROE 计算结果与手工计算一致"""
        ...
    
    def test_negative_roe_preserved(self):
        """亏损企业的负 ROE 正确保留"""
        ...

# tests/calculators/test_valuation_engine.py

class TestDCF:
    def test_zero_growth_equals_perpetuity(self):
        """零增长 DCF 等价于永续年金"""
        ...
    
    def test_terminal_value_dominates_long_horizon(self):
        """长期限 DCF 中终端价值占比合理 (>50%)"""
        ...
    
    def test_negative_fcf_handling(self):
        """负 FCF 的企业估值标记为 N/A 而非崩掉"""
        ...
    
    def test_wacc_boundary(self):
        """WACC ≈ 永续增长率时估值不爆炸"""
        ...
    
    def test_sensitivity_matrix_shape(self):
        """敏感性分析矩阵始终是 3×3"""
        ...
```

### 10.3 报告质量评估标准

```python
# 自动评估维度 (每次生成的报告都会过这 5 关)

class ReportQualityGate:
    """
    5 个自动质量门，任一未通过 → 报告标记为 DRAFT 而非 FINAL
    """
    
    def check_factual_consistency(self, report: ReportState) -> GateResult:
        """
        门 1: 事实一致性
        - 报告中的数字与 Python 计算结果一致（差异 < 1%）
        - 公司名称/股票代码在报告中始终一致
        - 日期、货币单位格式正确
        """
        errors = []
        # 逐字段比对 Python 输出 vs 报告文本
        for field in ["roe", "revenue", "net_income", "pe_ratio"]:
            calc_value = report.analysis_results.get(field)
            text_value = self._extract_number_from_text(report.sections, field)
            if calc_value and text_value:
                diff = abs(calc_value - text_value) / abs(calc_value)
                if diff > 0.01:  # 超过 1% 偏差
                    errors.append(f"{field}: calc={calc_value}, text={text_value}, diff={diff:.2%}")
        
        return GateResult(
            passed=len(errors) == 0,
            errors=errors,
            gate="factual_consistency"
        )
    
    def check_section_completeness(self, report: ReportState, template: TemplateSpec) -> GateResult:
        """
        门 2: 章节完整性
        - 所有必填章节都已生成
        - 每章字数在模板范围内
        - TL;DR 存在
        """
        ...
    
    def check_chart_integrity(self, report: ReportState) -> GateResult:
        """
        门 3: 图表完整性
        - 所有 required_charts 已生成
        - base64 图片可解码
        - 图表标题和说明文字存在
        """
        ...
    
    def check_disclaimer_presence(self, report: ReportState) -> GateResult:
        """
        门 4: 合规检查
        - 免责声明存在
        - 分析日期存在
        - 不包含投资承诺性语言 ("保证", "一定涨")
        """
        forbidden_phrases = ["保证收益", "稳赚", "一定涨", "绝对安全", "无风险"]
        ...
    
    def check_format_consistency(self, report: ReportState) -> GateResult:
        """
        门 5: 格式一致性
        - 不包含 markdown 格式错误 (未闭合的 **, 错误的表格格式)
        - 章节编号连续
        - 图表引用指向存在的图表
        """
        ...
```

### 10.4 幻觉检测策略

```python
class HallucinationDetector:
    """
    三层幻觉检测:
    """
    
    def layer_1_factual_reference(self, report_text: str, analysis_results: dict) -> list[Hallucination]:
        """
        L1: 事实引用检查
        提取报告中的所有数字声明，与 Python 计算结果比对
        """
        number_claims = self._extract_number_claims(report_text)
        # number_claims: [{"claim": "ROE 为 35%", "value": 35, "field": "roe"}, ...]
        hallucinations = []
        for claim in number_claims:
            if claim["field"] in analysis_results:
                expected = analysis_results[claim["field"]]
                if abs(claim["value"] - expected) / abs(expected) > 0.05:
                    hallucinations.append(Hallucination(
                        claim=claim["claim"],
                        expected=expected,
                        actual=claim["value"],
                        severity="HIGH" if abs(claim["value"] - expected) / abs(expected) > 0.20 else "MEDIUM"
                    ))
        return hallucinations
    
    def layer_2_source_trace(self, report_text: str, source_data: dict) -> list[Hallucination]:
        """
        L2: 来源追溯
        报告中声称的数据点能否在原始数据中找到
        """
        ...
    
    def layer_3_entity_consistency(self, report_text: str, state: ReportState) -> list[Hallucination]:
        """
        L3: 实体一致性
        公司名、股票代码、行业分类在跨章节中是否一致
        """
        ...
```

### 10.5 回归测试策略

```
每次 Agent prompt / LLM 模型 / 估值参数变更后:

1. "黄金集"回归测试 (5 个标的):
   - 贵州茅台 (600519.SH) — 高 ROE, 轻资产, 成熟期
   - 宁德时代 (300750.SZ) — 高增长, 重资产, 制造业
   - 腾讯控股 (0700.HK) — 互联网, 多元化, 港股
   - Apple (AAPL) — 美股, 高现金, 回购大户
   - 某亏损标的 — 边界测试

2. 评估维度:
   - 评分一致性 (financial_health_score 波动 < ±2pts)
   - 估值结果稳定性 (weighted_value 波动 < ±10%)
   - 报告长度稳定性 (总字数波动 < ±20%)
   - 质量门通过率 (5/5)

3. 通过标准:
   - 5 个标的全部通过 5 个质量门
   - 评分波动在阈值内
   - 无崩溃、无超时
```

---

## 十一、MVP Phase 1 交付物清单

### 11.1 MVP 收束（细化版）

**时间估算**: 4-6 周 (全职 1 人)

**必须交付** (Must Have):

| 模块 | 交付物 | 完成标准 |
|------|--------|---------|
| **项目骨架** | FastAPI 项目 + Next.js 项目 + 配置系统 | `uvicorn main:app --reload` 可启动 |
| **Provider 层** | AkShare + Yahoo Finance 两个 provider | 能获取 600519.SH 的 5 年日线和财报 |
| **File Upload** | PDF/Excel/CSV 上传 + 解析 | 上传一份茅台年报 PDF，能提取营收和净利润 |
| **Local DB** | SQLite 本地数据库 + 自动缓存 | 同一 ticker 第二次查询命中本地缓存 |
| **计算层** | 28 个财务比率 + DCF + Owner Earnings | 所有 Python 函数通过单元测试 (覆盖率 > 80%) |
| **Agent 管线** | Phase 1-4 完整管线 (12 个 SubAgent) | 从输入 ticker 到输出 ReportState 全程无报错 |
| **辩论** | 2 轮牛/熊辩论 + 风险裁判 | 辩论历史正确传递，裁判输出结构化结论 |
| **PDF 导出** | HTML→WeasyPrint PDF | 包含封面、目录、页眉页脚、图表嵌入 |
| **Web 前端** | 对话界面 + 报告预览 | 输入 ticker → 看到流式进度 → 预览报告 → 下载 PDF |
| **用户系统** | 注册/登录/用量限制 | free 用户每月 3 份封顶 |
| **模板系统** | 2 个预设模板 + JSON 自定义 | 深度研报和快速简报两个模板可用 |
| **配置系统** | config.json 驱动所有组件 | 修改 LLM provider 无需改代码 |

**明确不做** (Will NOT Do):

| 项目 | 理由 |
|------|------|
| 批量报告生成 | Phase 2 |
| Pitch Book / Teaser | Phase 2 |
| Word 导出 | Phase 2 |
| 可视化模板编辑器 | Phase 2 |
| 私有化部署 | Phase 3 |
| API 服务 | Phase 3 |
| 多用户协作 | Phase 3 |
| Wind/Bloomberg 接入 | Phase 2 |
| 一级市场数据 | Phase 2 (Crunchbase/PitchBook API) |
| 实时行情推送 | Phase 2 |
| 移动端适配 | Phase 3 |

### 11.2 里程碑

```
Week 1-2: 基础架构
  ✓ FastAPI 骨架 + Provider 抽象层 + AkShare/Yahoo F. 实现
  ✓ Next.js 骨架 + 对话界面 MVP
  ✓ 配置系统 (config.json 加载和验证)
  ✓ 本地 SQLite 数据库 + 缓存逻辑

Week 3-4: 核心计算 + Agent 管线
  ✓ Python 计算层 (28 比率 + DCF + Owner Earnings)
  ✓ 数据聚合 4 Agent (行情/财报/新闻/宏观)
  ✓ 深度分析 4 Agent (财务/估值/行业/治理)
  ✓ 辩论 3 Agent (牛/熊/裁判)
  ✓ 统稿 3 Agent (章节/图表/摘要)

Week 5: 报告输出 + 前端
  ✓ 模板引擎 (Jinja2 → HTML → WeasyPrint → PDF)
  ✓ 报告预览页面 (react-markdown + recharts)
  ✓ SSE 流式进度推送
  ✓ 用户系统 (注册/登录/用量限制)

Week 6: 集成 + 质量
  ✓ 端到端集成测试 (5 个黄金标的)
  ✓ 质量门实现和调优
  ✓ 幻觉检测集成
  ✓ 上线部署 (Railway/Vercel)
```

---

## 十二、风险与缓解

| # | 风险 | 概率 | 影响 | 缓解措施 | 负责人 |
|---|------|------|------|---------|--------|
| 1 | **LLM 财务数据幻觉** | 高 | 高 | Python 计算锚定 + L1 事实引用检查 + 质量门阻断 | — |
| 2 | **报告质量不一致** | 高 | 高 | 模板约束结构 + Pydantic schema + 5 质量门 + 黄金集回归 | — |
| 3 | **AkShare API 不稳定** | 中 | 中 | Tushare fallback + 用户上传兜底 + 本地缓存延长 TTL | — |
| 4 | **LLM API 延迟过高** | 中 | 中 | 双 LLM (Haiku 做轻任务) + 并行化 SubAgent + SSE 进度让用户不焦虑 | — |
| 5 | **PDF 中文排版问题** | 中 | 中 | SimHei/SimSun 字体嵌入 + WeasyPrint 已知坑预研 | — |
| 6 | **单 token 成本过高** | 中 | 高 | Haiku 做聚合/摘要 + 上下文窗口管理 + 缓存重用 | — |
| 7 | **用户不愿意付费** | 中 | 高 | Freemium 快速验证 + 免费用户产出的报告带"AI 生成"水印 + Pro 报告质量差异 | — |
| 8 | **PDF 财报解析准确率低** | 中 | 中 | pdfplumber + Camelot 双引擎 + LLM 交叉验证 + 用户确认环节 | — |
| 9 | **辩论陷入循环** | 低 | 中 | max_rounds 硬限制 + 辩论计数追踪 + 超时强制终止 | — |
| 10 | **合规风险 (AI 投资建议)** | 低 | 高 | 隐含声明嵌入每页 + 不提供具体买卖建议措辞 + Phase 2 咨询监管 | — |
| 11 | **SubAgent 并行状态竞争** | 低 | 中 | Phase 间严格的数据依赖声明 + 不可变 State 更新 (copy-on-write) | — |
| 12 | **供应商锁定 (Anthropic API)** | 低 | 高 | LLM provider 抽象层支持多厂商 + config.json 一键切换 | — |

---

## 附录 A: 竞品 Prompt 深度拆解（新增）

### A.1 ai-hedge-fund 的 LLM 调用模式

分析 3 类 Agent 的 LLM 使用模式：

**类型 1: 纯 Python Agent (无 LLM 调用)**
- `technical_analyst_agent` — 所有技术指标在 pandas 中计算，不使用 LLM
- `sentiment_agent` — 内部人交易和新闻情绪用 `np.where` 做加权投票，不使用 LLM
- `risk_management_agent` — 波动率/相关性全 Python 计算，不使用 LLM
- 结论：ai-hedge-fund 的所有数学 Agent 都不经过 LLM，这直接验证了"Python 计算 + LLM 叙事"的架构正确性

**类型 2: LLM 包装 Agent (Python 计算 + LLM 叙事)**
- `warren_buffett_agent` — 5 个 Python 评分函数 → LLM 生成 reasoning
- `valuation_analyst_agent` — 4 个 Python 估值模型 → LLM 生成 summary signal
- `fundamentals_analyst_agent` — 4 个 Python 评分维度 → LLM 生成综合判断

**类型 3: 纯 LLM Agent (完全依赖 LLM 推理)**
- `news_sentiment_agent` — 逐条新闻通过 LLM 分析情感
- `portfolio_management_agent` — LLM 综合所有信号做出最终决策

### A.2 TradingAgents-CN Prompt 工程精华

**分析师层的 Prompt 设计模式**（以 Market Analyst 为例）：

```
System Prompt 结构 (还原版):

1. 角色定义段:
   "你是一位专业的股票技术分析师，与其他分析师协作完成全面的投资研究。"
   
2. 工具使用强制段:
   "重要的是使用工具获取最新数据。如果没有数据，就不能进行分析。"
   
3. 参数指导段:
   "使用 get_stock_market_data_unified 工具，参数:
    - symbol: '{ticker}'
    - start_date: '2022-01-01'  
    - end_date: '2026-05-17'"
   
4. 协作约束段:
   "作为团队的一员，你只在市场技术分析方面贡献你的专业知识。"
   "不要对基本面、新闻情绪或其他领域做出判断。"
   
5. 格式要求段:
   "请用中文撰写所有分析内容。使用 {currency_name} ({currency_symbol}) 作为货币。"

Analysis Prompt 结构 (LLM 第二步调用，生成报告):

"现在请基于上述工具获取的数据，生成详细的技术分析报告。
报告应包含以下几个部分，并使用 ❗ 标记方式：

一、股票基本信息
  - 公司名称、股票代码、所属市场、当前股价

二、技术指标分析
  1. 移动平均线 (MA) 分析
     - 5日/10日/20日/60日/120日/250日均线位置
     - 均线排列状态 (多头/空头/交织)
     - 金叉/死叉信号
  2. MACD 指标分析
     - DIF/DEA/柱状线 当前值
     - MACD 信号判断
  3. RSI 指标分析
     - 当前 RSI 值及所在区域
  4. 布林带分析
     - 当前价格在布林带中的位置
     - 带宽分析 (扩张/收缩)

三、价格趋势分析
  1. 短期趋势 (1-4周)
  2. 中期趋势 (1-6月)
  3. 长期趋势 (6月以上)

四、投资建议
  1. 综合技术判断
  2. 关键支撑位和阻力位
  3. 基于技术分析的操作建议"
```

**关键洞察**: TradingAgents-CN 的 prompt 设计是"指令式"而非"对话式"——它精确指定了报告的章节结构、每个子节的内容、甚至格式标记 (❗)。这种"结构化输出要求用自然语言嵌入 prompt"的模式（而非 function calling / JSON schema）是其报告产出的核心驱动方式。

**辩论 Agent Prompt 的本质**:
Bull/Bear Researcher 的 prompt 本质是一个"受限辩论引擎"：
- 5 个分析维度（增长/竞争/指标/反驳/讨论）确保辩论覆盖面
- 历史论点注入（debate history + last opponent argument）确保增量论证
- 对话风格要求（"以对话风格呈现你的论点，直接回应对方"）确保可读性
- 工具/数据注入（4 份报告 + 标的约束 + 历史反思）确保论据有据可查

**对投资报告 Agent 的 Prompt 启示**:
1. 统稿 Agent 的 prompt 应该精确指定章节结构和每节内容要求（学习 TradingAgents-CN）
2. 分析 Agent 应强制使用工具获取数据，拒绝空口分析（学习 Fundamentals Analyst 的强制 tool call）
3. 辩论 Agent 必须看到对方的完整输出，同时注入结构化分析结果作为论据基础
4. 所有输出数字必须可追溯到 Python 计算层的输出（事实锚定）
5. Prompt 中嵌入格式标记（如 `❗`、`🚨`、`🔴`）不是装饰，是格式控制的低开销手段

---

## 附录 B: 数据合规与版权注意事项

### B.1 数据来源法律状态

| 数据源 | 授权方式 | 商业使用 | 分发限制 | 注意事项 |
|--------|---------|---------|---------|---------|
| AkShare | MIT 开源 | ✅ | 无 | 数据来源于东方财富/新浪等公开接口，二次分发需注意上游 TOS |
| Tushare | 免费注册 + 积分 | ⚠️ 需授权 | 禁止直接转售原始数据 | 商业使用需与技术团队确认 |
| Yahoo Finance | 免费 API | ⚠️ 条款限制 | 禁止再分发原始数据 | 仅用于内部分析，不直接转售数据 |
| SEC EDGAR | 美国政府公开数据 | ✅ | 无限制 | 最安全的数据源 |
| 用户上传 | 用户授权 | ✅ | — | 需在 ToS 中明确数据使用范围 |
| Wind | 商业授权 | ✅ (付费后) | 受合同约束 | 通常不允许缓存/再分发原始数据 |

### B.2 合规建议

1. **ToS 必须包含**: AI 生成内容免责声明、数据使用授权条款、用户上传数据的处理方式
2. **报告标注**: 每页页脚标注"AI 辅助生成，仅供参考"
3. **数据缓存**: 不缓存商业数据源 (Wind/Bloomberg) 的原始数据，仅缓存计算结果
4. **开源数据**: 标注数据来源 (如 "数据来源: AkShare/Yahoo Finance")

---

# 附录 C: TDD 详细实施计划

> 原则: 每个模块先写测试 → 跑红 → 写最小实现 → 跑绿 → 重构。Playwright 做端到端验收。

## C.1 项目根目录文件结构（目标）

```
investment-report-agent/
├── backend/
│   ├── pyproject.toml              # Python 包 + 依赖
│   ├── .env.example                # 环境变量模板
│   ├── Dockerfile                  # 后端容器
│   ├── config.json                 # 全局配置
│   ├── src/
│   │   ├── __init__.py
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── schema.py           # 配置 JSON Schema (Pydantic)
│   │   │   ├── loader.py           # config.json 加载 + 验证
│   │   │   ├── defaults.py         # 默认配置值
│   │   │   └── preset_cn.json      # A股预设
│   │   │   └── preset_us.json      # 美股预设
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── financial.py        # PriceData, FinancialStatement, NewsItem
│   │   │   ├── valuation.py        # ValuationResult, ValuationParams
│   │   │   ├── report.py           # ReportState, ReportSection, ChartOutput
│   │   │   ├── agent.py            # AgentTask, AgentResult, TaskSpec
│   │   │   └── user.py             # User, Subscription
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # DataProvider ABC
│   │   │   ├── manager.py          # ProviderManager (路由+降级+熔断)
│   │   │   ├── akshare_provider.py # AkShare 实现
│   │   │   ├── yahoo_provider.py   # Yahoo Finance 实现
│   │   │   ├── upload_provider.py  # 用户上传文件 Provider
│   │   │   ├── local_db.py         # SQLite 本地数据库
│   │   │   └── health.py           # 健康监控 + 熔断器
│   │   ├── calculators/
│   │   │   ├── __init__.py
│   │   │   ├── financial_ratios.py # 28 财务比率
│   │   │   ├── valuation_engine.py # DCF + Owner Earnings + EV/EBITDA
│   │   │   ├── technical_indicators.py # MA/MACD/RSI/Bollinger
│   │   │   ├── growth_metrics.py   # CAGR/YoY 增长
│   │   │   ├── sensitivity.py      # 敏感性矩阵
│   │   │   ├── chart_data.py       # matplotlib 图表生成
│   │   │   ├── unit_normalizer.py  # 单位标准化
│   │   │   ├── accounting_mapping.py # CAS/US GAAP/IFRS 映射
│   │   │   └── data_quality.py     # 数据质量评分
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py     # 主编排: 路由+调度+进度
│   │   │   ├── data/               # Phase 1: 数据聚合
│   │   │   │   ├── price_agent.py
│   │   │   │   ├── financial_agent.py
│   │   │   │   ├── news_agent.py
│   │   │   │   └── macro_agent.py
│   │   │   ├── analysis/           # Phase 2: 深度分析
│   │   │   │   ├── financial_analysis_agent.py
│   │   │   │   ├── valuation_agent.py
│   │   │   │   ├── industry_agent.py
│   │   │   │   └── governance_agent.py
│   │   │   ├── debate/             # Phase 3: 辩论
│   │   │   │   ├── bull_agent.py
│   │   │   │   ├── bear_agent.py
│   │   │   │   └── judge_agent.py
│   │   │   └── assembly/           # Phase 4: 统稿
│   │   │       ├── section_writer_agent.py
│   │   │       ├── chart_agent.py
│   │   │       └── summary_agent.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── main.py             # FastAPI app + lifespan
│   │   │   ├── routes/
│   │   │   │   ├── report.py       # /report/*
│   │   │   │   ├── template.py     # /template/*
│   │   │   │   ├── upload.py       # /upload/*
│   │   │   │   ├── user.py         # /auth/*, /user/*
│   │   │   │   └── config.py       # /config/*
│   │   │   ├── middleware.py       # Auth, Rate Limit, CORS
│   │   │   └── sse.py             # SSE 进度推送工具
│   │   ├── export/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_renderer.py     # Jinja2 → HTML → WeasyPrint → PDF
│   │   │   ├── docx_renderer.py    # python-docx 生成
│   │   │   └── template_engine.py  # JSON 模板 → Jinja2 上下文
│   │   └── templates/
│   │       ├── deep_dive.json      # 深度研报模板
│   │       ├── brief.json          # 快速简报模板
│   │       ├── ipo.json            # 新股覆盖模板
│   │       └── base.jinja2         # Jinja2 HTML 基础模板
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py             # pytest fixtures
│       ├── unit/
│       │   ├── __init__.py
│       │   ├── test_config.py
│       │   ├── test_models.py
│       │   ├── test_providers.py
│       │   ├── test_financial_ratios.py
│       │   ├── test_valuation_engine.py
│       │   ├── test_technical_indicators.py
│       │   ├── test_sensitivity.py
│       │   ├── test_data_quality.py
│       │   ├── test_unit_normalizer.py
│       │   └── test_accounting_mapping.py
│       ├── integration/
│       │   ├── __init__.py
│       │   ├── test_provider_pipeline.py
│       │   ├── test_agent_pipeline.py
│       │   ├── test_api_routes.py
│       │   └── test_report_generation.py
│       └── e2e/
│           ├── __init__.py
│           ├── test_deep_dive_report.spec.ts    # Playwright
│           ├── test_brief_report.spec.ts
│           ├── test_template_editor.spec.ts
│           └── test_user_flow.spec.ts
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx              # 对话主页
│   │   ├── report/[id]/page.tsx  # 报告预览
│   │   ├── templates/page.tsx    # 模板管理
│   │   └── settings/page.tsx     # 用户设置
│   ├── components/
│   │   ├── Chat/
│   │   ├── ReportPreview/
│   │   ├── TemplateEditor/
│   │   └── ui/                   # shadcn/ui 组件
│   └── lib/
│       ├── api.ts                # 后端 API 客户端
│       └── sse.ts                # SSE 事件处理
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## C.2 Phase 1: 项目骨架搭建 — TDD 详细执行

### 执行顺序

| 步骤 | 文件 | 类型 | 描述 |
|------|------|------|------|
| T01 | `backend/tests/unit/test_config.py` | 测试 | 配置系统测试 |
| S01 | `backend/src/config/schema.py` | 源文件 | 配置 Pydantic schema |
| S02 | `backend/src/config/defaults.py` | 源文件 | 默认配置 |
| S03 | `backend/src/config/loader.py` | 源文件 | 配置加载器 |
| T02 | `backend/tests/unit/test_config.py` | 测试 | 追加 LLM registry 测试 |
| S04 | `backend/src/config/llm_registry.py` | 源文件 | LLM Provider 注册 |
| S05 | `backend/pyproject.toml` | 配置 | Python 包 + 依赖 |
| S06 | `backend/.env.example` | 配置 | 环境变量模板 |
| S07 | `backend/config.json` | 配置 | 默认全局配置 |
| S08 | `frontend/package.json` | 配置 | Next.js 初始化 |
| S09 | `frontend/playwright.config.ts` | 配置 | Playwright 配置 |

### T01: 配置系统测试用例

```python
# tests/unit/test_config.py

class TestConfigSchema:
    """Given: 一个配置 JSON 字符串
       When: 用 ConfigSchema 解析
       Then: 返回验证后的配置对象 或 报错"""

    def test_load_minimal_config(self):
        """Given: 只包含 version 的最简 JSON
           When: ConfigSchema.model_validate_json(json_str)
           Then: 返回 Config 对象，version="1.0"，其余字段为默认值"""

    def test_missing_required_version_raises_error(self):
        """Given: 缺少 version 字段的 JSON
           When: ConfigSchema.model_validate_json(json_str)
           Then: 抛出 ValidationError"""

    def test_llm_provider_resolves_env_var(self):
        """Given: api_key_source="env:MY_KEY"，环境变量 MY_KEY=sk-xxx
           When: 加载配置并调用 resolve_api_key()
           Then: 返回 "sk-xxx" """

    def test_data_provider_orders_by_priority(self):
        """Given: 3 个 data provider，priority 分别为 2, 1, 3
           When: 加载后查看 data_providers 列表
           Then: 按 priority 升序排列 [1, 2, 3]"""

    def test_invalid_llm_provider_name_raises_error(self):
        """Given: agent 引用了不存在的 llm_provider_id
           When: 验证配置
           Then: 抛出 ConfigurationError("Unknown llm_provider: xxx")"""

    def test_fallback_chain_references_valid_providers(self):
        """Given: fallback_chain.CN 引用了未启用的 provider
           When: 验证配置
           Then: 抛出 ConfigurationError"""

    def test_pipeline_phase_agents_reference_valid_agents(self):
        """Given: pipeline 中引用了不存在的 agent
           When: 验证配置
           Then: 抛出 ConfigurationError"""

    def test_local_db_sync_schedule_is_valid_cron(self):
        """Given: sync_schedule = "daily_at_20:00"
           When: 加载配置
           Then: 解析为 crontab "0 20 * * *" """
```

### S01-S03: 配置系统模块接口

```python
# src/config/schema.py — 接口契约

class LLMProviderConfig(BaseModel):
    provider: Literal["anthropic", "openai", "deepseek", "ollama", "groq", "google"]
    model: str
    temperature: float = 0.3
    max_tokens: int = 16000
    api_key_source: str  # "env:VAR_NAME" 或 "plain:text"
    timeout_seconds: int = 120
    base_url: Optional[str] = None

class DataProviderConfig(BaseModel):
    enabled: bool = True
    priority: int = 10
    markets: list[str]  # ["CN", "US", "HK"]
    timeout_seconds: int = 30
    retry_count: int = 3
    api_key_source: Optional[str] = None
    cooldown_seconds: Optional[float] = None

class PipelinePhaseConfig(BaseModel):
    parallel: bool = False
    agents: list[str]
    debate_rounds: Optional[int] = None
    export: Optional[list[str]] = None

class PipelineConfig(BaseModel):
    name: str
    phases: dict[str, PipelinePhaseConfig]

class AgentConfig(BaseModel):
    llm: str  # provider ID
    python_calculator: Optional[str]
    tools: list[str] = []
    output_schema: str
    timeout_seconds: int = 120

class Config(BaseModel):
    version: str
    global_: GlobalConfig = Field(alias="global")
    llm_providers: dict[str, LLMProviderConfig]
    data_providers: DataProvidersSection
    pipelines: dict[str, PipelineConfig]
    agents: dict[str, AgentConfig]
    templates_dir: str = "~/.investment_report_agent/templates"
    reports_output_dir: str = "~/.investment_report_agent/reports"
    logging: LoggingConfig
```

### T02: LLM Registry 测试用例

```python
# 追加到 tests/unit/test_config.py

class TestLLMRegistry:
    """Given: 已加载的 Config
       When: LLMRegistry.get_model(agent_name)
       Then: 返回正确的 LangChain ChatModel 实例"""

    def test_resolve_anthropic_model(self):
        """Given: agent 配置 llm="provider_deep", provider=anthropic
           When: get_model("financial_analysis")
           Then: 返回 ChatAnthropic 实例，model="claude-opus-4-7" """

    def test_resolve_openai_model(self):
        """Given: agent 配置 llm="provider_openai_deep"
           When: get_model("some_agent")
           Then: 返回 ChatOpenAI 实例"""

    def test_falls_back_to_default_when_agent_not_in_config(self):
        """Given: 某 agent 没有在 agents 节中配置
           When: get_model("unknown_agent")
           Then: 返回 provider_quick 对应的 model"""

    def test_respects_temperature_from_config(self):
        """Given: agent 配置了 temperature=0.7
           When: get_model 创建实例
           Then: model.temperature == 0.7"""
```

---

## C.3 Phase 2: 核心数据模型 — TDD 详细执行

### 执行顺序

| 步骤 | 文件 | 类型 | 描述 |
|------|------|------|------|
| T03 | `backend/tests/unit/test_models.py` | 测试 | 数据模型验证测试 |
| S10 | `backend/src/models/financial.py` | 源文件 | PriceData, FinancialStatement, NewsItem |
| S11 | `backend/src/models/valuation.py` | 源文件 | ValuationParams, ValuationResult |
| S12 | `backend/src/models/report.py` | 源文件 | ReportState, ReportSection, ChartOutput |
| S13 | `backend/src/models/agent.py` | 源文件 | TaskSpec, AgentResult |
| S14 | `backend/src/models/user.py` | 源文件 | User, Subscription |

### T03: 数据模型测试用例

```python
# tests/unit/test_models.py

class TestPriceData:
    """Given: 标准化的行情数据
       When: 创建 PriceData 实例
       Then: 字段类型正确，可选字段为 None 时合法"""

    def test_create_valid_price_data(self):
        """Given: 完整的 OHLCV 数据
           When: PriceData(ticker="600519.SH", date=date(2026,5,17), open=1680.0, ...)
           Then: 创建成功，所有字段值匹配"""

    def test_volume_can_be_none(self):
        """Given: 部分数据源不提供成交量
           When: PriceData(..., volume=None)
           Then: 创建成功"""

    def test_negative_price_rejected(self):
        """Given: close=-1680.0
           When: PriceData(...)
           Then: ValidationError (价格必须 >= 0)"""

    def test_date_in_future_rejected(self):
        """Given: date 在 2030 年
           When: PriceData(...)
           Then: ValidationError (日期不能在未来)"""

    def test_currency_must_be_known(self):
        """Given: currency="EUR"
           When: PriceData(...)
           Then: ValidationError (仅支持 CNY/USD/HKD)"""


class TestFinancialStatement:
    """Given: 标准化财务报表数据
       When: 创建 FinancialStatement 实例
       Then: 正确处理不同会计准则的数据映射"""

    def test_revenue_and_net_income_mandatory_at_least_one(self):
        """Given: revenue=None AND net_income=None
           When: FinancialStatement(...)
           Then: ValidationError (至少需要一个财务数据)"""

    def test_all_optional_fields_can_be_none(self):
        """Given: 只有 ticker, report_date, fiscal_year
           When: FinancialStatement(...)
           Then: 创建成功，其余字段为 None"""

    def test_fiscal_quarter_range(self):
        """Given: fiscal_quarter=5
           When: FinancialStatement(...)
           Then: ValidationError (季度必须 1-4)"""


class TestReportState:
    """Given: 报告生成的不同阶段
       When: ReportState 更新
       Then: 保持不可变性 (copy-on-write)"""

    def test_phase_transition_preserves_previous_data(self):
        """Given: Phase 1 产出有 raw_data 的 state
           When: 创建新 state 合并 Phase 2 产出
           Then: raw_data 不丢失，analysis_results 新增"""

    def test_debate_state_tracks_rounds(self):
        """Given: DebateState(round=1, bull_arguments=[...])
           When: 进入 Round 2
           Then: round=2, history 包含 Round 1"""

    def test_report_sections_match_template(self):
        """Given: 模板要求 7 个章节
           When: ReportState.sections 只有 6 个
           Then: completeness_check() 返回 False + 缺失节名称"""
```

---

## C.4 Phase 3: Provider 数据层 — TDD 详细执行

### 执行顺序

| 步骤 | 文件 | 类型 | 描述 |
|------|------|------|------|
| T04 | `tests/unit/test_providers.py` | 测试 | Provider 基类 + Manager 测试 |
| S15 | `src/providers/base.py` | 源文件 | DataProvider ABC |
| S16 | `src/providers/manager.py` | 源文件 | ProviderManager |
| S17 | `src/providers/health.py` | 源文件 | 熔断器 + 健康监控 |
| T05 | `tests/unit/test_local_db.py` | 测试 | 本地数据库测试 |
| S18 | `src/providers/local_db.py` | 源文件 | SQLite 本地数据库 |
| T06 | `tests/integration/test_provider_pipeline.py` | 集成测试 | 完整数据获取链 |
| S19 | `src/providers/akshare_provider.py` | 源文件 | AkShare 实现 |
| S20 | `src/providers/yahoo_provider.py` | 源文件 | Yahoo Finance 实现 |
| S21 | `src/providers/upload_provider.py` | 源文件 | 用户上传 Provider |

### T04: Provider 层测试用例

```python
# tests/unit/test_providers.py

class TestDataProviderABC:
    """Given: DataProvider 抽象基类
       When: 子类未实现抽象方法
       Then: 实例化报错"""

    def test_cannot_instantiate_abstract_provider(self):
        """Given: 继承 DataProvider 但未实现 get_prices
           When: 尝试实例化
           Then: TypeError"""

    def test_concrete_provider_must_implement_all_methods(self):
        """Given: 只实现了 get_prices 和 get_financials
           When: 实例化
           Then: TypeError (还缺 get_news, supports_market, health_check)"""


class TestProviderManager:
    """Given: ProviderManager 管理多个 DataProvider
       When: 按 query 路由到正确的 provider
       Then: 按 priority + fallback_chain 选择"""

    def test_routes_to_highest_priority_healthy_provider(self):
        """Given: akshare(priority=1, healthy), tushare(priority=2, healthy)
           When: query("600519.SH", "prices")
           Then: 使用 akshare"""

    def test_falls_back_when_primary_unhealthy(self):
        """Given: akshare unhealthy, tushare healthy
           When: query("600519.SH", "prices")
           Then: 使用 tushare，记录降级日志"""

    def test_falls_back_when_primary_timeout(self):
        """Given: akshare timeout, yahoo_finance healthy
           When: query("AAPL", "prices")
           Then: 使用 yahoo_finance"""

    def test_all_providers_unhealthy_raises_error(self):
        """Given: 所有 provider unhealthy
           When: query("600519.SH", "prices")
           Then: DataUnavailableError，附带所有失败原因"""

    def test_local_db_returns_stale_when_all_external_fail(self):
        """Given: 外部全失败，本地 DB 有 26h 前的数据
           When: query("600519.SH", "prices")
           Then: 返回本地数据 + stale=True + warnings"""

    def test_circuit_breaker_activated_after_5_consecutive_failures(self):
        """Given: akshare 连续失败 5 次
           When: 第 6 次 query
           Then: 跳过 akshare，直接用 fallback，记录熔断日志"""

    def test_circuit_breaker_resets_after_5_minutes(self):
        """Given: akshare 熔断已激活, 过了 6 分钟
           When: query
           Then: 重新尝试 akshare (半开状态)"""

    def test_market_detection_routes_correctly(self):
        """Given: ticker="0700.HK"
           When: get_providers_for_market
           Then: 返回 HK 市场对应的 fallback_chain"""
```

### T05: 本地数据库测试用例

```python
# tests/unit/test_local_db.py

class TestLocalDatabase:
    def test_upsert_new_data(self):
        """Given: 空数据库
           When: upsert("prices:600519:2026-05-17", price_data)
           Then: 数据库中新增一条记录"""

    def test_query_returns_fresh_data(self):
        """Given: 1 小时前写入的数据，TTL=86400
           When: query with ttl=86400
           Then: 返回数据，stale=False"""

    def test_query_returns_none_for_expired_data(self):
        """Given: 25 小时前写入的数据，TTL=86400
           When: query with ttl=86400
           Then: 返回 None (过期)"""

    def test_query_returns_stale_when_allow_stale(self):
        """Given: 25 小时前的数据
           When: query with allow_stale=True
           Then: 返回数据 + stale=True"""

    def test_bulk_upsert_then_query_all(self):
        """Given: 50 条价格记录批量写入
           When: query_range("prices:600519:*")
           Then: 返回 50 条记录"""

    def test_clear_expired_entries(self):
        """Given: 100 条记录，70 条已过期
           When: clean_expired()
           Then: 剩余 30 条"""
```

---

## C.5 Phase 4: Python 计算层 — TDD 详细执行

### 执行顺序

| 步骤 | 文件 | 类型 | 描述 |
|------|------|------|------|
| T07 | `tests/unit/test_financial_ratios.py` | 测试 | 28 个财务比率 |
| S22 | `src/calculators/financial_ratios.py` | 源文件 | 财务比率计算器 |
| T08 | `tests/unit/test_valuation_engine.py` | 测试 | 估值模型 |
| S23 | `src/calculators/valuation_engine.py` | 源文件 | DCF + OE + EV/EBITDA |
| T09 | `tests/unit/test_technical_indicators.py` | 测试 | 技术指标 |
| S24 | `src/calculators/technical_indicators.py` | 源文件 | MA/MACD/RSI/Bollinger |
| T10 | `tests/unit/test_sensitivity.py` | 测试 | 敏感性矩阵 |
| S25 | `src/calculators/sensitivity.py` | 源文件 | 敏感性分析 |
| T11 | `tests/unit/test_data_quality.py` | 测试 | 数据质量 |
| S26 | `src/calculators/data_quality.py` | 源文件 | 数据质量评分 |
| T12 | `tests/unit/test_accounting_mapping.py` | 测试 | 会计准则映射 |
| S27 | `src/calculators/accounting_mapping.py` | 源文件 | CAS/US GAAP/IFRS |
| T13 | `tests/unit/test_unit_normalizer.py` | 测试 | 单位标准化 |
| S28 | `src/calculators/unit_normalizer.py` | 源文件 | 万元/亿元/元 |
| S29 | `src/calculators/growth_metrics.py` | 源文件 | CAGR/YoY |
| S30 | `src/calculators/chart_data.py` | 源文件 | matplotlib 图表 |

### T07: 财务比率测试用例

```python
# tests/unit/test_financial_ratios.py

class TestProfitability:
    def test_roe_calculation(self):
        """Given: NI=100, AvgEquity=500
           When: calculate_roe(net_income=100, avg_equity=500)
           Then: 0.20 (20%)"""

    def test_roe_negative_when_ni_negative(self):
        """Given: NI=-100, AvgEquity=500
           When: calculate_roe(-100, 500)
           Then: -0.20"""

    def test_roe_none_when_equity_zero(self):
        """Given: AvgEquity=0
           When: calculate_roe(100, 0)
           Then: None (不是除零错误)"""

    def test_roe_none_when_net_income_none(self):
        """Given: NI=None
           When: calculate_roe(None, 500)
           Then: None"""

    def test_gross_margin(self):
        """Given: Revenue=1000, COGS=400
           When: calculate_gross_margin(1000, 400)
           Then: 0.60 (60%)"""

    def test_gross_margin_zero_revenue(self):
        """Given: Revenue=0, COGS=400
           When: calculate_gross_margin(0, 400)
           Then: None"""

    def test_all_28_ratios_handle_missing_inputs(self):
        """Given: 所有输入为 None
           When: calculate_all_ratios({}, {}, {}, {})
           Then: 所有 28 个比率字段为 None，不抛出异常"""


class TestGrowth:
    def test_yoy_growth(self):
        """Given: current=120, previous=100
           When: yoy_growth(120, 100)
           Then: 0.20"""

    def test_yoy_growth_negative(self):
        """Given: current=80, previous=100
           When: yoy_growth(80, 100)
           Then: -0.20"""

    def test_3y_cagr(self):
        """Given: start=100, end=133.1
           When: cagr(start=100, end=133.1, years=3)
           Then: ~0.10 (10%)"""

    def test_cagr_negative_end(self):
        """Given: start=100, end=-50
           When: cagr(100, -50, 3)
           Then: None (不支持负值 CAGR)"""


class TestFinancialHealth:
    def test_debt_to_equity(self):
        """Given: Total Liabilities=200, Total Equity=800
           When: debt_to_equity(200, 800)
           Then: 0.25"""

    def test_interest_coverage(self):
        """Given: EBIT=500, Interest Expense=25
           When: interest_coverage(500, 25)
           Then: 20.0"""

    def test_interest_coverage_zero_interest(self):
        """Given: Interest Expense=0
           When: interest_coverage(500, 0)
           Then: float('inf')"""
```

### T08: 估值引擎测试用例

```python
# tests/unit/test_valuation_engine.py

class TestDCFThreeStage:
    def test_zero_growth_equals_perpetuity(self):
        """Given: FCF=[100]*10, growth=0, wacc=0.10
           When: calculate_dcf_three_stage(...)
           Then: 每股价值 ≈ 100/0.10 = 1000 """

    def test_positive_growth_increases_value(self):
        """Given: growth=5% vs growth=0%
           When: 分别计算 DCF
           Then: 5% 的估值 > 0% 的估值"""

    def test_higher_wacc_decreases_value(self):
        """Given: wacc=12% vs wacc=8%
           When: 分别计算 DCF
           Then: 12% 的估值 < 8% 的估值"""

    def test_terminal_value_share_above_fifty_pct(self):
        """Given: 标准参数
           When: DCF 计算
           Then: 终端价值占比 > 50%"""

    def test_negative_fcf_returns_none(self):
        """Given: 历史 FCF 为负
           When: calculate_dcf_three_stage(...)
           Then: 返回 {"error": "negative_fcf", "per_share_value": None}"""

    def test_wacc_equals_growth_raises_error(self):
        """Given: WACC=8%, Terminal Growth=8%
           When: calculate_dcf_three_stage(...)
           Then: ValuationError("WACC cannot equal terminal growth rate")"""


class TestOwnerEarnings:
    def test_owner_earnings_formula(self):
        """Given: NI=100, D&A=20, Capex=15, ΔNWC=5
           When: calculate_owner_earnings(NI=100, DA=20, maint_capex=12, delta_nwc=5)
           Then: 100 + 20 - 12 - 5 = 103"""

    def test_maintenance_capex_median_of_three_methods(self):
        """Given: 三种方法: 85%×Capex=127.5, D&A=100, avg_ratio×Capex=110
           When: calculate_maintenance_capex(...)
           Then: median(127.5, 100, 110) = 110"""

    def test_mos_applied_to_final_value(self):
        """Given: 未打折估值=200, MOS=25%
           When: apply_mos(200, 0.25)
           Then: 200 × 0.75 = 150"""


class TestEVEBITDA:
    def test_ev_ebitda_basic(self):
        """Given: EBITDA=500, Industry EV/EBITDA=15, Net Debt=1000
           When: calculate_ev_ebitda(500, 15, 1000)
           Then: Equity Value = 500×15 - 1000 = 6500"""

    def test_roe_premium_adjustment(self):
        """Given: 标的 ROE=30%, 行业 ROE=15%
           When: 计算溢价调整
           Then: premium_factor > 1.0 (有溢价)"""


class TestWeightedAggregation:
    def test_default_weights_sum_to_one(self):
        """Given: 4 个估值模型的默认权重
           When: sum(weights)
           Then: 1.0"""

    def test_missing_model_redistributes_weight(self):
        """Given: RI 模型无法计算 (缺少数据), 原权重 35/35/20/10
           When: redistribute_weights([35,35,20,None])
           Then: [0.389, 0.389, 0.222, 0]"""

    def test_weighted_value_calculation(self):
        """Given: DCF=200, OE=210, EV/EBITDA=185, RI=None
           When: 计算加权值 (0.389/0.389/0.222)
           Then: 200×0.389 + 210×0.389 + 185×0.222 = ~200.6"""


class TestSensitivityMatrix:
    def test_matrix_is_3x3(self):
        """Given: 任意输入
           When: calculate_sensitivity_matrix(...)
           Then: len(values)==3, all(len(row)==3 for row in values)"""

    def test_base_case_in_center(self):
        """Given: base_wacc=8.5, base_growth=3.0, base_value=1970
           When: calculate_sensitivity_matrix(...)
           Then: matrix[1][1] ≈ base_value"""

    def test_higher_growth_higher_value(self):
        """Given: 标准参数
           When: calculate_sensitivity_matrix(...)
           Then: matrix[0][2] (低WACC高增长率) > matrix[1][1] (基准)"""
```

---

## C.6 Phase 5: Agent 管线 — TDD 详细执行

### 执行顺序

| 步骤 | 文件 | 类型 | 描述 |
|------|------|------|------|
| T14 | `tests/unit/test_agent_orchestrator.py` | 测试 | 主编排路由 |
| S31 | `src/agents/orchestrator.py` | 源文件 | 主编排 Agent |
| T15 | `tests/unit/test_agents_data.py` | 测试 | 数据聚合 Agent |
| S32 | `src/agents/data/price_agent.py` | 源文件 | 行情 Agent |
| S33 | `src/agents/data/financial_agent.py` | 源文件 | 财报 Agent |
| S34 | `src/agents/data/news_agent.py` | 源文件 | 新闻 Agent |
| S35 | `src/agents/data/macro_agent.py` | 源文件 | 宏观 Agent |
| T16 | `tests/unit/test_agents_analysis.py` | 测试 | 分析 Agent |
| S36 | `src/agents/analysis/financial_analysis_agent.py` | 源文件 | 财务分析 |
| S37 | `src/agents/analysis/valuation_agent.py` | 源文件 | 估值 |
| S38 | `src/agents/analysis/industry_agent.py` | 源文件 | 行业竞争 |
| S39 | `src/agents/analysis/governance_agent.py` | 源文件 | 公司治理 |
| T17 | `tests/unit/test_agents_debate.py` | 测试 | 辩论 Agent |
| S40 | `src/agents/debate/bull_agent.py` | 源文件 | 多头 |
| S41 | `src/agents/debate/bear_agent.py` | 源文件 | 空头 |
| S42 | `src/agents/debate/judge_agent.py` | 源文件 | 裁判 |
| T18 | `tests/unit/test_agents_assembly.py` | 测试 | 统稿 Agent |
| S43 | `src/agents/assembly/section_writer_agent.py` | 源文件 | 章节撰写 |
| S44 | `src/agents/assembly/chart_agent.py` | 源文件 | 图表生成 |
| S45 | `src/agents/assembly/summary_agent.py` | 源文件 | 标题摘要 |

### T14: 主编排 Agent 测试用例

```python
# tests/unit/test_agent_orchestrator.py

class TestOrchestratorRouting:
    def test_routes_deep_dive_from_user_message(self):
        """Given: user_message="分析贵州茅台，生成深度研报"
           When: orchestrator.route(user_message, context)
           Then: pipeline_type="deep_dive" """

    def test_routes_brief_from_user_message(self):
        """Given: user_message="快速看下五粮液"
           When: orchestrator.route(user_message, context)
           Then: pipeline_type="brief" """

    def test_extracts_ticker_from_chinese_name(self):
        """Given: user_message="分析茅台"
           When: orchestrator._extract_tickers(user_message)
           Then: ["600519.SH"] (通过名称映射)"""

    def test_extracts_multiple_tickers(self):
        """Given: user_message="对比茅台和五粮液"
           When: orchestrator._extract_tickers(user_message)
           Then: ["600519.SH", "000858.SZ"]"""

    def test_returns_error_when_ticker_not_found(self):
        """Given: user_message="分析不存在的公司"
           When: orchestrator._extract_tickers(user_message)
           Then: TaskSpec 包含 error="无法识别公司名称" """

    def test_respects_user_preferred_template(self):
        """Given: user 已设置 preferred_template="brief"
           When: orchestrator.route without explicit template
           Then: template_id="brief" """

    def test_explicit_template_overrides_preference(self):
        """Given: user asks "用深度模板分析茅台"
           When: orchestrator.route(...)
           Then: template_id="deep_dive" """
```

### T17: 辩论 Agent 测试用例

```python
# tests/unit/test_agents_debate.py

class TestBullBearDebate:
    def test_bull_produces_arguments_with_evidence(self):
        """Given: 财务分析结果 + 估值结果 + 行业分析
           When: bull_agent.run(state)
           Then: 输出包含 3-5 个论点，每个有 evidence 字段"""

    def test_bear_produces_arguments_with_evidence(self):
        """Given: 财务分析结果 + 估值结果 + 行业分析
           When: bear_agent.run(state)
           Then: 输出包含 3-5 个论点，每个有 evidence 字段"""

    def test_round2_references_opponent_arguments(self):
        """Given: Round 1, bear 的论点为 ["arg1", "arg2", "arg3"]
           When: bull_agent.run(state, round=2)
           Then: bull 输出中 rebuttal_to 字段引用 bear 的论点 ID"""

    def test_confidence_score_in_range(self):
        """Given: 正常输入
           When: bull_agent or bear_agent
           Then: 每个 argument.confidence 在 0-100 之间"""

    def test_debate_stops_at_max_rounds(self):
        """Given: max_rounds=2
           When: debate loop 执行
           Then: 最多 2 轮后停止，不无限循环"""


class TestRiskJudge:
    def test_judge_evaluates_both_sides(self):
        """Given: bull_arguments + bear_arguments
           When: judge_agent.run(state)
           Then: key_risks 非空，key_opportunities 非空"""

    def test_judge_produces_price_confidence_intervals(self):
        """Given: 完整的辩论输出
           When: judge_agent.run(state)
           Then: confidence_intervals 包含 pessimistic/base/optimistic 三个价格"""

    def test_judge_risk_reward_ratio(self):
        """Given: upside=17.3%, downside=-15.0%
           When: judge_agent.run(state)
           Then: risk_reward_ratio ≈ 1.15"""

    def test_judge_verdict_is_never_empty(self):
        """Given: 空输入
           When: judge_agent.run(state)
           Then: verdict="HOLD", confidence=0"""
```

---

## C.7 Phase 6: 报告渲染引擎 — TDD 详细执行

### 执行顺序

| 步骤 | 文件 | 类型 | 描述 |
|------|------|------|------|
| T19 | `tests/unit/test_template_engine.py` | 测试 | 模板解析 |
| S46 | `src/export/template_engine.py` | 源文件 | JSON→Jinja2 上下文 |
| T20 | `tests/unit/test_pdf_renderer.py` | 测试 | PDF 渲染 |
| S47 | `src/export/pdf_renderer.py` | 源文件 | HTML→PDF |
| S48 | `src/templates/deep_dive.json` | 模板 | 深度研报模板 |
| S49 | `src/templates/brief.json` | 模板 | 快速简报模板 |
| S50 | `src/templates/base.jinja2` | 模板 | HTML 基础模板 |

### T19: 模板引擎测试用例

```python
# tests/unit/test_template_engine.py

class TestTemplateParsing:
    def test_load_valid_template_json(self):
        """Given: deep_dive.json 文件存在且格式正确
           When: TemplateEngine.load("deep_dive")
           Then: 返回 TemplateSpec 对象，sections 列表非空"""

    def test_template_validation_rejects_missing_required_fields(self):
        """Given: JSON 模板缺少 sections 字段
           When: TemplateEngine.load(...)
           Then: TemplateValidationError"""

    def test_section_ids_are_unique(self):
        """Given: 模板中两个 section 有相同 id
           When: TemplateEngine.load(...)
           Then: TemplateValidationError("Duplicate section id: xxx")"""

    def test_template_variable_interpolation(self):
        """Given: 模板中有 {{report_title}}
           When: render(context={"report_title": "Test"})
           Then: 输出包含 "Test" """

    def test_sections_order_preserved(self):
        """Given: 模板中 sections = [A, B, C]
           When: render
           Then: 输出中 A 在 B 之前，B 在 C 之前"""


class TestPDFRenderer:
    def test_pdf_generated_with_cover_page(self):
        """Given: 完整的 ReportState
           When: PDFRenderer.render(state, template)
           Then: 返回 bytes，文件头为 %PDF-"""

    def test_pdf_contains_toc(self):
        """Given: report 有 7 个章节
           When: render PDF
           Then: PDF 中包含目录页"""

    def test_chart_images_embedded_as_base64(self):
        """Given: report 有 3 个 charts (base64 PNG)
           When: render PDF
           Then: PDF 中可见图片"""

    def test_disclaimer_on_every_page(self):
        """Given: template style.footer 配置了免责声明
           When: render PDF
           Then: 每一页底部都包含免责声明文本"""
```

---

## C.8 Phase 7: FastAPI 后端 — TDD 详细执行

### 执行顺序

| 步骤 | 文件 | 类型 | 描述 |
|------|------|------|------|
| T21 | `tests/integration/test_api_routes.py` | 集成测试 | API 路由 |
| S51 | `src/api/main.py` | 源文件 | FastAPI app |
| S52 | `src/api/middleware.py` | 源文件 | Auth/CORS/RateLimit |
| S53 | `src/api/routes/report.py` | 源文件 | 报告端点 |
| S54 | `src/api/routes/template.py` | 源文件 | 模板端点 |
| S55 | `src/api/routes/upload.py` | 源文件 | 上传端点 |
| S56 | `src/api/routes/user.py` | 源文件 | 用户端点 |
| S57 | `src/api/routes/config.py` | 源文件 | 配置端点 |
| S58 | `src/api/sse.py` | 源文件 | SSE 工具 |

### T21: API 集成测试用例

```python
# tests/integration/test_api_routes.py

class TestReportAPI:
    def test_generate_report_returns_task_id(self, client, mock_orchestrator):
        """Given: 有效 ticker
           When: POST /api/v1/report/generate {"ticker":"600519.SH","report_type":"deep_dive"}
           Then: 201, {"task_id": "uuid", "status": "queued"}"""

    def test_generate_report_invalid_ticker(self, client):
        """Given: 无效 ticker
           When: POST /api/v1/report/generate {"ticker":"INVALID"}
           Then: 400, {"error": "Cannot resolve ticker"}"""

    def test_task_status_returns_progress(self, client, mock_task):
        """Given: 运行中的 task
           When: GET /api/v1/report/{task_id}/status
           Then: 200, {"status":"running", "current_phase":"phase_2_analysis", "progress_pct":45}"""

    def test_sse_stream_emits_progress_events(self, client, mock_task):
        """Given: 运行中的 task
           When: GET /api/v1/report/{task_id}/stream (SSE)
           Then: 收到 event:agent_start, event:agent_progress, event:complete"""

    def test_pdf_download_returns_pdf_bytes(self, client, mock_report):
        """Given: 已完成的 report
           When: GET /api/v1/report/{report_id}/pdf
           Then: 200, Content-Type: application/pdf"""

    def test_free_tier_limit_enforced(self, client, mock_user_free):
        """Given: free 用户本月已生成 3 份报告
           When: POST /api/v1/report/generate
           Then: 429, {"error":"Monthly limit reached. Upgrade to Pro."}"""

    def test_unauthorized_request_returns_401(self, client):
        """Given: 无 Authorization header
           When: GET /api/v1/report/{id}
           Then: 401"""


class TestTemplateAPI:
    def test_list_templates(self, client):
        """Given: 系统中 2 个预设模板
           When: GET /api/v1/template
           Then: 200, templates 列表含 2 个"""

    def test_create_custom_template(self, client):
        """Given: 有效的模板 JSON
           When: POST /api/v1/template
           Then: 201, template_id 为新 UUID"""

    def test_delete_template_only_own(self, client, mock_other_user_template):
        """Given: 另一个用户的模板
           When: DELETE /api/v1/template/{other_user_template_id}
           Then: 403, {"error": "Can only delete own templates"}"""


class TestUploadAPI:
    def test_upload_pdf(self, client, mock_pdf_file):
        """Given: 一份 PDF 年报
           When: POST /api/v1/upload (multipart)
           Then: 201, {"file_id": "uuid", "status": "processing"}"""

    def test_upload_status_queries(self, client, mock_processed_file):
        """Given: 已处理的文件
           When: GET /api/v1/upload/{file_id}/status
           Then: 200, {"status": "ready", "extracted_data": {...}}"""
```

---

## C.9 Phase 8: Next.js 前端 — Playwright E2E 测试优先

### Playwright E2E 测试场景

```typescript
// tests/e2e/test_deep_dive_report.spec.ts

test.describe('Deep Dive Report Generation', () => {
  
  test('Complete flow: user types ticker → gets report → downloads PDF', async ({ page }) => {
    // Given: 已登录用户在对话页面
    await page.goto('/');
    await page.fill('[data-testid="chat-input"]', '分析贵州茅台，生成深度研报');
    await page.click('[data-testid="send-button"]');
    
    // When: 报告生成中
    // Then: 看到进度条
    await expect(page.locator('[data-testid="progress-bar"]')).toBeVisible();
    await expect(page.locator('text=Phase 1: 数据采集')).toBeVisible();
    await expect(page.locator('text=✓ 行情数据')).toBeVisible({ timeout: 30000 });
    
    // Then: 进度实时更新
    await expect(page.locator('text=Phase 2: 深度分析')).toBeVisible({ timeout: 60000 });
    await expect(page.locator('text=Phase 3: 多空辩论')).toBeVisible({ timeout: 90000 });
    
    // Then: 看到完成消息和下载按钮
    await expect(page.locator('text=报告已生成')).toBeVisible({ timeout: 120000 });
    await expect(page.locator('[data-testid="download-pdf"]')).toBeVisible();
    await expect(page.locator('[data-testid="preview-report"]')).toBeVisible();
  });

  test('Report preview displays all sections', async ({ page }) => {
    // Given: 打开已完成报告的预览页
    await page.goto('/report/mock-report-id');
    
    // Then: 所有章节可见
    await expect(page.locator('text=投资摘要')).toBeVisible();
    await expect(page.locator('text=公司概况')).toBeVisible();
    await expect(page.locator('text=行业分析')).toBeVisible();
    await expect(page.locator('text=财务分析')).toBeVisible();
    await expect(page.locator('text=估值分析')).toBeVisible();
    await expect(page.locator('text=风险提示')).toBeVisible();
    await expect(page.locator('text=投资建议')).toBeVisible();
  });

  test('Charts render correctly in report preview', async ({ page }) => {
    await page.goto('/report/mock-report-id');
    
    // Then: 图表可见
    await expect(page.locator('img[alt="股价走势图"]')).toBeVisible();
    await expect(page.locator('img[alt="营收/净利润趋势图"]')).toBeVisible();
    await expect(page.locator('img[alt="估值区间瀑布图"]')).toBeVisible();
  });

  test('PDF download works', async ({ page }) => {
    await page.goto('/report/mock-report-id');
    
    // When: 点击下载 PDF
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="download-pdf"]'),
    ]);
    
    // Then: 下载的文件是 PDF
    expect(download.suggestedFilename()).toContain('.pdf');
  });

  test('Free tier limit message shows after 3 reports', async ({ page }) => {
    // Given: 模拟 free 用户已用 3 次
    // (通过 mock API 返回)
    await page.goto('/');
    await page.fill('[data-testid="chat-input"]', '分析宁德时代');
    await page.click('[data-testid="send-button"]');
    
    // Then: 显示升级提示
    await expect(page.locator('text=本月免费额度已用完')).toBeVisible();
    await expect(page.locator('[data-testid="upgrade-button"]')).toBeVisible();
  });
});


test.describe('Template Management', () => {
  
  test('User can view preset templates', async ({ page }) => {
    await page.goto('/templates');
    await expect(page.locator('text=深度研报')).toBeVisible();
    await expect(page.locator('text=快速简报')).toBeVisible();
  });

  test('User can create custom template', async ({ page }) => {
    await page.goto('/templates');
    await page.click('[data-testid="new-template"]');
    await page.fill('[data-testid="template-name"]', '我的定制模板');
    await page.fill('[data-testid="template-json-editor"]', JSON.stringify({
      name: "Custom",
      sections: [
        { id: "summary", title: "Summary", agent: "section_writer", max_words: 300 }
      ]
    }));
    await page.click('[data-testid="save-template"]');
    
    await expect(page.locator('text=我的定制模板')).toBeVisible();
  });
});


test.describe('User Flow', () => {
  
  test('Registration and login', async ({ page }) => {
    await page.goto('/register');
    await page.fill('[data-testid="email"]', 'test@example.com');
    await page.fill('[data-testid="password"]', 'Test123456');
    await page.click('[data-testid="register-button"]');
    
    await expect(page.locator('text=注册成功')).toBeVisible();
    await expect(page).toHaveURL('/');
  });

  test('Usage counter updates', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('[data-testid="usage-counter"]')).toContainText('0/3');
    
    // 触发一次报告生成 (mock 快速完成)
    // ...
    
    await expect(page.locator('[data-testid="usage-counter"]')).toContainText('1/3');
  });
});
```

---

## C.10 全局文件创建顺序总览

```
Day 1-2 (Phase 1):
  T01→S01→S02→S03→T02→S04→S05→S06→S07→S09
  产出: 可加载配置, LLM Registry 可用, pyproject.toml 可 pip install -e .

Day 3-4 (Phase 2):
  T03→S10→S11→S12→S13→S14
  产出: 所有 Pydantic 模型通过单元测试

Day 5-7 (Phase 3):
  T04→S15→S16→S17→T05→S18→(T06→S19→S20→S21)
  产出: AkShare/Yahoo F. 数据可获取, 本地 DB 可读写, 熔断器工作

Day 8-10 (Phase 4):
  T07→S22→T08→S23→T09→S24→T10→S25→T11→S26→T12→S27→T13→S28→S29→S30
  产出: 28 比率 + 3 估值模型 + 技术指标 + 敏感性 + 数据质量 + 单位标准化 全部通过测试

Day 11-15 (Phase 5):
  T14→S31→T15→S32-35→T16→S36-39→T17→S40-42→T18→S43-45
  产出: 完整 Agent 管线可端到端产出 ReportState

Day 16-18 (Phase 6):
  T19→S46→T20→S47→S48→S49→S50
  产出: 可从 ReportState 渲染出 PDF

Day 19-21 (Phase 7):
  T21→S51→S52→S53→S54→S55→S56→S57→S58
  产出: FastAPI 后端所有端点通过集成测试

Day 22-24 (Phase 8):
  S08→前端界面 + Playwright E2E 测试
  产出: Next.js 对话界面 + 报告预览 + Playwright 通过

Day 25-28 (Phase 9):
  质量门实现 + 幻觉检测 + 黄金集回归
  产出: 5/5 质量门通过, 5 个黄金标的回归测试通过
```

---

## C.11 Playwright CI/CD 集成

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  e2e:
    runs-on: ubuntu-latest
    services:
      backend:
        image: investment-report-agent-backend:latest
        ports: [8000]
      frontend:
        image: investment-report-agent-frontend:latest
        ports: [3000]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd frontend && npm ci
      - run: cd frontend && npx playwright install --with-deps chromium
      - run: cd frontend && npx playwright test
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: frontend/playwright-report/
```

---

## C.12 开发环境启动命令

```bash
# 后端
cd backend
pip install -e ".[dev]"
cp .env.example .env  # 编辑填入 API Keys
uvicorn src.api.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev  # localhost:3000

# 测试
cd backend
pytest tests/unit/ -v          # 单元测试
pytest tests/integration/ -v   # 集成测试 (需要后端运行)
pytest tests/ -v --cov=src     # 全量 + 覆盖率

# E2E
cd frontend
npx playwright test            # 运行所有 E2E
npx playwright test --ui       # 交互式调试
```
5. **投行材料**: Pitch Book 场景需要更严格的内部合规审查流程
