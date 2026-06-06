# 个人投研工作台 MVP — 实施计划

**日期:** 2026-06-06
**项目:** investment-report-agent
**状态:** DEPLOYABLE_CANDIDATE → 个人工作台扩展
**约束:** 不重构架构、不做多用户、不做支付、不做公开发布、不做自动调度、不做复杂 CMS

---

## 1. 当前可复用模块

### 基础设施（直接可用，无需改动）

| 模块 | 说明 | 位置 |
|---|---|---|
| FastAPI + MongoDB | 异步后端 + 持久化 | `backend/src/api/` |
| Provider 链 | TradingAgents → QVeris → AkShare，含熔断器 | `backend/src/providers/` |
| LLM 子进程 | 可超时的 LLM 调用封装 | `backend/src/agents/analysis/llm_subprocess.py` |
| 财务比率计算器 | 28 项指标（ROE/ROA/D/E 等） | `backend/src/calculators/financial_ratios.py` |
| 估值引擎 | DCF 三阶段、Owner Earnings、EV/EBITDA | `backend/src/calculators/valuation_engine.py` |
| shadcn/ui 组件 | badge/button/card/dialog/input/select/separator/skeleton | `frontend/components/ui/` |
| SSE 流式进度 | 实时推送任务进度 | `frontend/lib/api.ts` + `backend/src/api/routes/report.py` |

### 现有 API（可直接复用）

| 端点 | 用途 | 备注 |
|---|---|---|
| `POST /report/generate` | 启动分析 | 支持 4 种 pipeline |
| `GET /report/{id}/status` | 查状态 | 含 `current_phase`、`progress_pct` |
| `GET /report/{id}` | 查完整报告 | 含 `data_quality`、`verdict` |
| `GET /reports` | 报告列表 | 支持 `limit`/`skip` 分页 |
| `GET/POST/DELETE /watchlist` | 自选股 CRUD | 单用户直接可用 |
| `GET/POST/DELETE /portfolio` | 模拟组合 CRUD | 含 `pnl`、`pnl_pct`、`summary` |
| `GET/POST /archive` | 归档 CRUD | 含 `card_summary`、`verdict` |
| `GET /alerts` | 已触发警报列表 | 报告生成时自动创建 |
| `POST /report/compare` | 多股对比 | 2-5 只，含 LLM 总结 |

### 现有 Agent Pipeline（直接可调度）

| Pipeline | 用途 | 耗时 |
|---|---|---|
| `quick_scan` | 技术面+财务面快速扫描 | ~1-2min |
| `value_deep_dive` | 段永平+芒格双视角价值深研 | ~5-8min |
| `deep_dive` | 牛熊辩论深研 | ~5-8min |
| `brief` | 轻量简报 | ~3-5min |

### 现有前端页面（可直接导航，部分需增强）

| 页面 | 用途 |
|---|---|
| `/` 首页 | 搜索入口 + 最近报告 + 自选股 |
| `/report` | 报告详情 + 数据质量 + 追问 |
| `/reports` | 报告列表 |
| `/portfolio` | 模拟组合 |
| `/archive` | 归档研究 |
| `/progress` | 进度 SSE |

---

## 2. 最小改动方案

### 核心理念

> 单用户工具，不建用户系统，不建权限体系。所有数据默认属于当前唯一用户。
> 以 pipeline 为执行单元，以 MongoDB 为持久化中心，在现有页面上渐进增强。

### 改动原则

1. **后端新增路由模块**，不修改现有路由（`report.py` 等不动）
2. **前端新增页面**，不重构现有页面（`page.tsx` 等只加链接不加逻辑）
3. **新增 pipeline 配置**，不改现有 4 条 pipeline
4. **使用现有 MongoDB 集合**，不加新 collection（仅加字段）
5. **不改数据 provider**，不改 agent 核心逻辑

---

## 3. 新增/修改页面

### P0 — 核心工作台

| 页面 | 操作 | 说明 |
|---|---|---|
| `/dashboard` | **新增** | 个人工作台首页：今日行情速览、最近研究、快速入口 |
| `/stock/[ticker]` | **新增** | 个股工作台：行情卡片+技术面+财务+新闻+研究记录聚合页 |
| `/report` | **增强** | 增加"另存为底稿"按钮、导出 Markdown/文本 |
| `/review` | **新增** | 日终复盘页：今日持仓回顾、自选股涨跌、市场情绪 |

### P1 — 内容生产

| 页面 | 操作 | 说明 |
|---|---|---|
| `/drafts` | **新增** | 投研底稿列表：已保存的半成品、备注、草稿 |
| `/drafts/[id]` | **新增** | 底稿编辑器：富文本+AI 辅助插入 |

### P2 — 选股辅助

| 页面 | 操作 | 说明 |
|---|---|---|
| `/screener` | **新增** | 选股器：基于技术指标/财务指标的筛选面板 |

---

## 4. 新增/修改 API

### P0 — 核心

| 端点 | 方法 | 用途 | 数据源 |
|---|---|---|---|
| `GET /dashboard/summary` | **新增** | 工作台概览：今日自选股涨跌、最近 N 份报告摘要、警报计数 | 聚合现有数据 |
| `GET /stock/{ticker}/profile` | **新增** | 个股画像：基本信息+行业+52w 范围+估值区间 | 现有 provider |
| `GET /stock/{ticker}/research` | **新增** | 个股研究记录：历史报告列表、归档笔记、持仓记录 | MongoDB: investment_reports + archive + portfolio |
| `POST /stock/{ticker}/quick-scan` | **新增** | 个股一键快速扫描（调 quick_scan pipeline） | 复用现有 `POST /report/generate` |

### P0 — 日终复盘

| 端点 | 方法 | 用途 | 数据源 |
|---|---|---|---|
| `POST /review/daily/generate` | **新增** | 生成日终复盘报告：给定 ticker 列表（默认自选股+持仓），拉取当日行情+新闻，LLM 总结 | 现有 provider + 新 agent |
| `GET /review/daily/{id}` | **新增** | 获取复盘报告 | MongoDB 持久化 |

### P1 — 投研底稿

| 端点 | 方法 | 用途 | 数据源 |
|---|---|---|---|
| `POST /drafts` | **新增** | 创建底稿（从报告另存、或空白新建） | MongoDB: `drafts` 新集合 |
| `GET /drafts` | **新增** | 底稿列表 | MongoDB: `drafts` |
| `GET /drafts/{id}` | **新增** | 底稿详情 | MongoDB: `drafts` |
| `PUT /drafts/{id}` | **新增** | 更新底稿内容 | MongoDB: `drafts` |
| `DELETE /drafts/{id}` | **新增** | 删除底稿 | MongoDB: `drafts` |
| `POST /drafts/{id}/export` | **新增** | 导出底稿（Markdown/文本） | 服务端渲染 |

### P2 — 选股

| 端点 | 方法 | 用途 | 数据源 |
|---|---|---|---|
| `POST /screener/run` | **新增** | 根据条件筛选：市值范围、PE 范围、ROE > X、技术信号（放量/突破等） | 现有 provider + 新 pipeline |
| `GET /screener/results/{id}` | **新增** | 获取筛选结果 | MongoDB 临时存储 |

### 现有 API 增强

| 端点 | 变更 |
|---|---|
| `GET /reports` | 加 `ticker` 过滤参数（查看某只股票的历史报告） |
| `GET /report/{id}` | 返回体中增加 `summary_markdown` 字段（方便导出/复制） |

---

## 5. 数据结构设计

### 新增集合: `drafts`

```json
{
  "_id": "draft-uuid",
  "title": "贵州茅台投资逻辑梳理",
  "source_type": "from_report",        // "from_report" | "blank"
  "source_task_id": "task-xxxx",       // 如果从报告另存
  "ticker": "600519.SH",
  "company_name": "贵州茅台",
  "content_md": "## 核心逻辑\n\n...",  // Markdown 正文
  "tags": ["白酒", "消费升级", "核心资产"],
  "status": "draft",                   // "draft" | "final"
  "created_at": "2026-06-06T10:00:00Z",
  "updated_at": "2026-06-06T12:00:00Z"
}
```

### 新增集合: `reviews`

```json
{
  "_id": "review-uuid",
  "type": "daily",
  "date": "2026-06-06",
  "tickers": ["600519.SH", "000858.SZ", "300750.SZ"],
  "summary_md": "## 今日复盘\n\n...",
  "sections": [
    {
      "ticker": "600519.SH",
      "company_name": "贵州茅台",
      "change_pct": 1.25,
      "close": 1580.00,
      "volume_ratio": 0.85,
      "signal": "neutral",
      "news_summary": "...",
      "verdict": "持有"
    }
  ],
  "market_sentiment": "温和看涨",
  "created_at": "2026-06-06T15:30:00Z"
}
```

### 新增集合: `screener_results`

```json
{
  "_id": "screener-uuid",
  "criteria": {
    "market": "cn",
    "pe_max": 20,
    "roe_min": 15,
    "volume_increase": true
  },
  "results": [
    {"ticker": "600519.SH", "name": "贵州茅台", "pe": 25.5, "roe": 30.1, "score": 85}
  ],
  "total_count": 50,
  "created_at": "2026-06-06T10:00:00Z",
  "expires_at": "2026-06-07T10:00:00Z"
}
```

### 现有集合扩展

**`investment_reports`** 增加可选字段：
```json
{
  "is_pinned": false,          // 置顶标记
  "personal_notes": "",        // 个人笔记
  "tags": ["白酒", "核心资产"] // 用户标签
}
```

**`watchlist`** 增加可选字段：
```json
{
  "group": "消费",             // 分组
  "notes": "关注回调机会",
  "added_reason": "北向资金加仓"
}
```

---

## 6. 分阶段实施顺序

### 第一阶段：个人工作台核心（估算 3-5 天）

**目标：** 一个可用的个人入口，替代当前的通用首页，聚合自选股、最近研究、一键扫描。

| 任务 | 文件 | 工作量 |
|---|---|---|
| 新增 `/dashboard` 页面 | `frontend/app/dashboard/page.tsx` | 1d |
| 新增 `GET /dashboard/summary` API | `backend/src/api/routes/dashboard.py` | 0.5d |
| 新增 `GET /stock/{ticker}/profile` API | `backend/src/api/routes/stock.py` | 0.5d |
| 新增 `GET /stock/{ticker}/research` API | `backend/src/api/routes/stock.py` | 0.5d |
| 新增 `/stock/[ticker]` 个股页面 | `frontend/app/stock/[ticker]/page.tsx` | 1d |
| `GET /reports` 增加 ticker 过滤 | `backend/src/api/routes/report.py` | 0.25d |
| 首页 → dashboard 重定向 | `frontend/app/page.tsx` 或路由配置 | 0.25d |

**验收标准：**
- [/] `/dashboard` 加载后显示自选股今日涨跌
- [/] `/dashboard` 显示最近 5 份报告摘要
- [/] 搜索股票后跳转到个股工作台
- [/] 个股工作台显示行情卡片 + 技术信号 + 历史报告
- [/] 个股工作台可一键发起 quick_scan
- [/] 快速扫描进度和结果正常展示

### 第二阶段：日终复盘（估算 2-3 天）

**目标：** 每天收盘后一键生成当日复盘，包含自选股和持仓回顾。

| 任务 | 文件 | 工作量 |
|---|---|---|
| 新增 `POST /review/daily/generate` API | `backend/src/api/routes/review.py` | 1d |
| 新增 `GET /review/daily/{id}` API | `backend/src/api/routes/review.py` | 0.25d |
| 新增 `sections` 等模型 | `backend/src/models/review.py` | 0.25d |
| 新增复盘 Agent（调用 price + news + LLM summary） | `backend/src/agents/review/daily_review.py` | 1d |
| 新增 `/review` 页面 | `frontend/app/review/page.tsx` | 0.5d |
| dashboard 增加复盘入口 | `frontend/app/dashboard/page.tsx` | 0.25d |

**验收标准：**
- [/] 点击"生成今日复盘"后开始生成
- [/] 复盘包含自选股+持仓的当日涨跌
- [/] 复盘包含各股新闻摘要
- [/] 复盘包含 LLM 总结的市场情绪
- [/] 复盘报告可查看历史日期（按 date 查询）

### 第三阶段：投研底稿（估算 2-3 天）

**目标：** 将报告"另存为"个人底稿，可在底稿上写笔记，导出为 Markdown。

| 任务 | 文件 | 工作量 |
|---|---|---|
| 新增 drafts 集合 CRUD API | `backend/src/api/routes/drafts.py` | 1d |
| 新增 `/drafts` 前端页面 | `frontend/app/drafts/page.tsx` | 0.5d |
| 新增 `/drafts/[id]` 编辑器页面 | `frontend/app/drafts/[id]/page.tsx` | 1d |
| 报告页增加"另存为底稿"按钮 | `frontend/app/report/page.tsx` | 0.25d |
| 新增导出 Markdown API | `backend/src/api/routes/drafts.py` | 0.5d |

**验收标准：**
- [/] 报告详情页有"另存为底稿"按钮
- [/] 底稿列表页显示所有已保存底稿
- [/] 底稿编辑器可编辑 Markdown 内容
- [/] 底稿可添加标签
- [/] 底稿可导出为 Markdown 文件下载
- [/] 从空白新建底稿

### 第四阶段：选股器 + 增强（估算 3-5 天）

**目标：** 基于技术面和财务条件的选股筛选器。

| 任务 | 文件 | 工作量 |
|---|---|---|
| 新增 screener pipeline（复用现有数据 agent） | `backend/config.json` + `backend/src/agents/screener/` | 1.5d |
| 新增 screener API | `backend/src/api/routes/screener.py` | 1d |
| 新增 `/screener` 前端页面 | `frontend/app/screener/page.tsx` | 1.5d |
| 筛选条件 UI（市值/PE/ROE/技术信号） | `frontend/app/screener/page.tsx` | 1d |
| Watchlist 分组功能 | `backend/src/api/routes/report.py` + 前端 | 0.5d |

**验收标准：**
- [/] 选股器可按市值、PE、ROE 范围筛选
- [/] 选股器可按技术信号（放量/均线突破）筛选
- [/] 选股结果列表可按分数排序
- [/] 选股结果可一键加入自选股
- [/] 选股结果可一键发起 quick_scan
- [/] 自选股支持分组

---

## 7. 每阶段验收标准

### 全局验收标准

- [ ] 所有改动不破坏现有 `launch_check.py` 全部 10 项检查
- [ ] 所有改动不破坏现有 Playwright e2e 5 项测试
- [ ] 所有新增 API 有对应的单元测试（或至少手动测试记录）
- [ ] 无 secrets/凭证提交
- [ ] 前端与后端 API 版本一致（`/api/v1/`）

### 第一阶段验收
见上方"第一阶段·验收标准"。

### 第二阶段验收
见上方"第二阶段·验收标准"。

### 第三阶段验收
见上方"第三阶段·验收标准"。

### 第四阶段验收
见上方"第四阶段·验收标准"。

### 集成验收
- [ ] 从 dashboard → 个股工作台 → quick_scan → 报告 → 另存底稿 → 导出，完整流程可走通
- [ ] 从 dashboard → 生成复盘 → 查看历史复盘，可走通
- [ ] 从 dashboard → 选股器 → 筛选 → 加入自选 → 发起扫描，可走通

---

## 8. 风险和不做项

### 明确不做

| 项 | 理由 |
|---|---|
| 多用户/登录/权限 | 个人工具，不做公开服务 |
| 支付/订阅 | 个人使用，无商业场景 |
| 自动定时任务 | 约束明确禁止 |
| 复杂 CMS 或富文本编辑器 | 轻量 Markdown 编辑即可 |
| 生产部署/HTTPS/域名 | 当前是个人工作台，非公开服务 |
| 社交/分享功能 | 个人工具 |
| 移动端适配 | 桌面优先 |
| 实时行情 WebSocket | 日终数据够用，不做实时 |
| 回测引擎 | 工作量过大，后续考虑 |
| 第三方数据源切换 UI | config.json 直接配置 |
| Docker compose 变动 | 当前 compose 已包含 mongo，工作台扩展不改变部署拓扑 |

### 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| LLM API 费用 | 复盘/选股均需调用 LLM，增加用量 | Quick scan 用 `provider_quick`（8K tokens），复盘限制 ticker ≤ 20 |
| 选股器数据量大 | A 股 5000+ 只，全量拉取慢 | 分批 + provider 缓存；先做条件过滤再做全量 |
| MongoDB 无认证 | 个人工具默认无认证，但暴露端口有风险 | 保持 compose 内网即可；若需公网访问加简单密码 |
| 复盘内容质量不稳定 | LLM 生成的质量取决于 prompt | 复盘 Agent 用结构化 JSON schema 而非自由文本 |
| 现有 pipeline 超时 | 某些复杂股票 value_deep_dive 可能超时 | 前端 SSE 正常处理超时，用户可重试 quick_scan |
| 投研底稿无版本管理 | 纯 Markdown 存 MongoDB，无 diff | MVP 不做版本管理；后续可加简单快照 |

### 已知限制

- 选股器的数据源是 TradingAgents/QVeris/AkShare，非实时行情，选股结果截至上一交易日
- 日终复盘依赖收盘后数据，建议 15:00 后使用
- 投研底稿的导出仅支持 Markdown，不支持 PDF（现有 PDF renderer 仅为报告模板）
- 所有数据存储在本地 MongoDB，无云备份
