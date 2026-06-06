# 个人投研工作台 MVP — 实施计划

**日期:** 2026-06-06
**项目:** investment-report-agent
**状态:** DEPLOYABLE_CANDIDATE → 个人工作台扩展
**约束:** 不重构架构、不做多用户、不做支付、不做公开发布、不做自动调度、不做复杂 CMS

---

## 1. 当前可复用模块

### 基础设施（直接可用）

| 模块 | 位置 |
|---|---|
| FastAPI + MongoDB | `backend/src/api/` |
| Provider 链（TradingAgents → QVeris → AkShare） | `backend/src/providers/` |
| LLM 子进程 | `backend/src/agents/analysis/llm_subprocess.py` |
| 财务比率计算器（28 项指标） | `backend/src/calculators/financial_ratios.py` |
| 估值引擎（DCF/OE/EV-EBITDA） | `backend/src/calculators/valuation_engine.py` |
| shadcn/ui 组件 | `frontend/components/ui/` |
| SSE 流式进度 | `frontend/lib/api.ts` + `backend/src/api/routes/report.py` |

### 现有 API（直接复用）

| 端点 | 用途 |
|---|---|
| `POST /report/generate` | 启动 4 种 pipeline（quick_scan / value_deep_dive / deep_dive / brief） |
| `GET /report/{id}/status` | 含 `current_phase`、`progress_pct` |
| `GET /report/{id}` | 含 `data_quality`、`verdict`、完整章节 |
| `GET /reports` | 列表，支持 `limit`/`skip` 分页 |
| `GET/POST/DELETE /watchlist` | 自选股 CRUD |
| `GET/POST/DELETE /portfolio` | 模拟组合，含 `pnl`、`summary` |
| `GET/POST /archive` | 归档 CRUD |
| `GET /alerts` | 已触发警报 |
| `POST /report/compare` | 多股对比（2-5 只） |

### 现有 Agent Pipeline

| Pipeline | 用途 | 耗时 |
|---|---|---|
| `quick_scan` | 技术面+财务面快速扫描 | ~1-2min |
| `value_deep_dive` | 段永平+芒格双视角价值深研 | ~5-8min |
| `deep_dive` | 牛熊辩论深研 | ~5-8min |
| `brief` | 轻量简报 | ~3-5min |

### 现有前端页面

| 页面 | 用途 |
|---|---|
| `/` 首页 | 搜索入口 + 最近报告 + 自选股展示 |
| `/report` | 报告详情 + 数据质量卡片 + 追问 |
| `/reports` | 报告列表，可搜索 |
| `/portfolio` | 模拟组合 P&L |
| `/archive` | 归档研究卡片 |
| `/progress` | 任务进度 SSE 实时展示 |

---

## 2. 设计原则

1. **不改现有路由文件** — 新增路由写在独立文件中，report.py/watchlist.py 等只做最小增强（加查询参数）
2. **不新增 MongoDB 集合** — Phase 1 所有数据用现有 5 个集合（investment_reports / watchlist / archive / portfolio / alerts）
3. **不新增前端页面** — Phase 1 只增强现有页面，不加新 route
4. **不改 provider / agent 核心逻辑** — 仅加配置或复用
5. **不新增 pipeline** — 日终复盘用现有 quick_scan + LLM 后处理，不走大框架

---

## 3. Phase 1 改动清单

### 3.1 后端 API

#### 3.1.1 新增：`GET /api/v1/home/summary`

**用途：** 首页聚合数据接口，替代前端多次串行调用。

**文件：** `backend/src/api/routes/home.py`（新增）

**返回：**
```json
{
  "watchlist": [
    {"ticker": "600519.SH", "name": "贵州茅台", "close": 1580.00, "change_pct": 1.25, "signal": "neutral"}
  ],
  "recent_reports": [
    {"task_id": "...", "ticker": "600519.SH", "company_name": "贵州茅台",
     "report_type": "quick_scan", "verdict": "BUY", "created_at": "..."}
  ],
  "portfolio_summary": {"positions_count": 3, "total_pnl_pct": 5.2},
  "alert_count": 1,
  "report_count_this_month": 12
}
```

**逻辑：** 聚合 `/watchlist`（启调用 provider 查现价）、`/reports?limit=5`、`/portfolio`（仅 summary）、`/alerts/count`。无新数据源。

#### 3.1.2 新增：`POST /api/v1/report/{task_id}/export-markdown`

**用途：** 将报告导出为 Markdown 文本，用于"复制到剪贴板"或保存为本地文件。

**文件：** `backend/src/api/routes/report.py`（最小增强：加一个新路由，不修改现有逻辑）

**返回：** `{"markdown": "# 贵州茅台 600519.SH 投资价值深度分析\n\n...全文 Markdown..."}`

**逻辑：** 读取已有报告结果，拼接 `ReportState` 中各章节 + 图表说明，格式化为 Markdown 字符串。无新依赖。

#### 3.1.3 新增：`POST /api/v1/review/daily`

**用途：** 手动触发日终复盘生成。

**文件：** `backend/src/api/routes/review.py`（新增）

**请求：**
```json
{
  "tickers": ["600519.SH", "000858.SZ", "300750.SZ"],
  "date": "2026-06-06"
}
```
tickers 不传则默认取当前自选股 + 持仓股。

**返回：**
```json
{
  "task_id": "review-uuid",
  "status": "running"
}
```

**后端逻辑：**
1. 对每个 ticker，调用现有 provider 获取当日行情（`get_prices`）和新闻（`get_news`）
2. 调用 LLM（复用 `llm_subprocess.py`）生成个股小结
3. 汇总为 Markdown 报告
4. 存入 `investment_reports` 集合（加 `_type: "daily_review"` 区分），不新增集合

**无新 pipeline** — 这是一个轻量函数，不走 agent orchestrator 大框架。直接用 httpx 调用 provider，直接调用 LLM subprocess。

#### 3.1.4 新增：`GET /api/v1/review/daily/{id}`

**用途：** 获取已生成的日终复盘。

**文件：** `backend/src/api/routes/review.py`

**返回：** 完整 Markdown 复盘文本 + JSON 结构化数据（各股涨跌、信号、新闻摘要）。

#### 3.1.5 现有 API 最小增强

| 端点 | 改动 | 文件 |
|---|---|---|
| `GET /reports` | 增加 `ticker` 查询参数过滤 | `report.py` 加 ~3 行 |
| `GET /watchlist` | 返回体增加 `group`、`notes` 字段 | 前端已显示，后端已有字段 |

### 3.2 前端改动

#### 3.2.1 首页增强（替代独立 /dashboard）

**文件：** `frontend/app/page.tsx`

**改动量：** 中（~100 行新增，不删现有代码）

**改动内容：**

| 区域 | 当前行为 | 改为 |
|---|---|---|
| 自选股区域 | 仅显示名称列表 | 显示表格：名称 + 现价 + 涨跌幅 + 技术信号（从 `/home/summary` 取），点击直接跳到 quick_scan |
| 报告列表 | 显示最近报告 | 增加报告类型标签（quick_scan / deep_dive）、判定标签（BUY/HOLD/SELL） |
| 顶部统计 | 无 | 加小字统计：本月报告数、持仓数、自选股数、活跃警报 |
| 操作入口 | 仅搜索框 | 加"一键复盘"按钮（调 `POST /review/daily`），生成后弹窗展示或跳转到复盘视图 |

**不做的：**
- 不重新设计布局，在现有卡片/列表基础上增强
- 不加新图表组件（后续可追加）
- 不改 CSS 框架

#### 3.2.2 报告页增强

**文件：** `frontend/app/report/page.tsx`

**改动量：** 小（~30 行）

**改动内容：**
- 报告顶部加"复制 Markdown"按钮
- 点击后调 `POST /report/{task_id}/export-markdown`，将返回文本写入剪贴板
- 成功后提示"已复制到剪贴板"

#### 3.2.3 复盘查看页（轻量）

**文件：** 可用 `/report` 页复用（因为复盘存储在 investment_reports 集合，加 `_type=daily_review`），或新增一个极简内联视图。

**方案：** 复用 `/report` 页。复盘生成的 Markdown 存在 `investment_reports` 的 `result` 字段中，`/report/{id}` 接口读取后前端 Markdown 渲染展示。**不新增独立页面。**

### 3.3 数据

**无新 MongoDB 集合。** 所有新增数据写入现有集合：
- 日终复盘 → `investment_reports`（`_type: "daily_review"`）
- 各字段增补 → 现有集合加可选字段

### 3.4 文件变更汇总

| 文件 | 操作 | 改动量 |
|---|---|---|
| `backend/src/api/routes/home.py` | 新增 | ~60 行 |
| `backend/src/api/routes/review.py` | 新增 | ~150 行 |
| `backend/src/api/routes/report.py` | +1 路由 | ~30 行 |
| `backend/src/api/routes/report.py` | `GET /reports` + ticker 过滤 | ~3 行 |
| `frontend/app/page.tsx` | 增强首页 | ~100 行 |
| `frontend/app/report/page.tsx` | +"复制 Markdown"按钮 | ~30 行 |
| `frontend/lib/api.ts` | +homeSummary / exportMarkdown / dailyReview 函数 | ~15 行 |

**总计：新增 ~2 文件，修改 ~5 文件，约 400 行净新增。**

---

## 4. 不做项（当前 Phase 不做的，未来可能做）

| 项 | 原因 |
|---|---|
| 独立 /dashboard 页面 | 首页增强即可满足 |
| 独立 /stock/[ticker] 页面 | 搜索→报告流程已可用 |
| drafts 集合 + 编辑器 | 复制 Markdown 到本地文件即"底稿" |
| screener 选股器 | 工作量 > 3d，排后 |
| 自选股分组 UI | 后端已支持 group 字段，前端下拉筛选后续加 |
| 实时行情 | 个人工具日终数据够用 |
| 自动定时复盘 | 约束明确禁止 |
| 复盘新 pipeline | 轻量函数即可，不走 orchestrator |

---

## 5. 分阶段总览

| 阶段 | 内容 | 新增路由 | 新增页面 | 新增集合 | 工作量 |
|---|---|---|---|---|---|
| **Phase 1** | 首页增强 + Markdown 导出 + 手动日终复盘 | 2 个（home + review） | 0 | 0 | **~3-4d** |
| Phase 2 | 投研底稿：drafts 集合 + 列表 + Markdown 编辑器 | 1 个（drafts） | 2 个 | 1 个（drafts） | 2-3d |
| Phase 3 | 选股器 + 自选股分组 + /stock/ticker 页面 | 2 个（screener + stock） | 2 个 | 1 个（screener_results） | 3-4d |

---

## 6. 验收标准

### Phase 1 验收

- [ ] 首页加载后显示自选股现价 + 涨跌幅（从 `/home/summary`）
- [ ] 首页显示最近 5 份报告 + 类型标签 + 判定标签
- [ ] 首页显示统计小字（报告数、持仓数、警报数）
- [ ] 首页"一键复盘"按钮可点击
- [ ] 点击后生成日终复盘（含自选股+持仓当日行情 + LLM 小结）
- [ ] 复盘结果可查看（复用 `/report` 页）
- [ ] 报告详情页有"复制 Markdown"按钮
- [ ] 点击后成功复制报告全文为 Markdown
- [ ] 按 ticker 过滤报告列表生效
- [ ] 现有功能完全不受影响
- [ ] `launch_check.py` 全部 10 项 PASS
- [ ] Playwright e2e 全部 5 项 PASS

### 验收方式

| 项 | 方式 |
|---|---|
| API 功能 | `curl` 或前端操作 |
| 前端渲染 | 浏览器直观确认 |
| 回归 | 执行 `python scripts/launch_check.py` |
| E2E | `npm run test:e2e:smoke` |

---

## 7. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 首页 `/home/summary` 调用 provider 查现价可能慢 | 首页加载延迟 | 加 `timeout=3s`，超时则不显示价格 |
| 日终复盘 LLM 调用可能失败 | 复盘不完整 | 降级为仅显示数据表格，不加 LLM 文本 |
| 现有页面增强时误改现有逻辑 | 功能退化 | 不改现有 export 函数，只加新 block |
| 报告 Markdown 导出可能丢失格式 | 导出内容混乱 | 先从 quick_scan 短报告做，确认格式再推广 |
