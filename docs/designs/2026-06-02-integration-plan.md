# TradingAgents-CN + 投资报告 Agent 整合规划

## 一、现状

### 两个项目的定位

| | TradingAgents-CN (TACN) | 投资报告 Agent (IRA) |
|---|---|---|
| 地位 | **主体** | 功能来源 |
| 技术栈 | FastAPI + Vue 3 + Element Plus | FastAPI + Next.js + shadcn/ui |
| 功能 | 数据同步、筛选、用户、配置、LangGraph Agent | 段永平/芒格管线、AI追问、组合、提醒、档案 |
| 代码量 | ~10 万行 | ~2 万行 |
| 状态 | 功能齐全，代码冗余 | 代码干净，功能不全 |

### 问题

1. TACN 没有价值投资视角（段永平/芒格）
2. IRA 的 AI 追问、报告引擎质量好但困在独立项目里
3. TACN 前端用 Vue + Element Plus（重），IRA 前端用 Next.js + shadcn（轻）
4. 两个项目的后端有大量重复（MongoDB 连接、Provider 管理、LLM 配置）

---

## 二、整合方案

### 方案选型：后端合并 + 前端二选一

### 后端合并

以 TACN 的 FastAPI 后端为基础，把 IRA 的功能作为**新模块**合并进去：

```
tradingagents-cn/app/
├── routers/           ← 保留全部现有 40+ 路由
│   ├── analysis.py    ← TACN 的 LangGraph 分析
│   └── ... (39 more)
├── services/
│   ├── ... (existing)
│   └── value_investing/    ← 新增：价值投资服务
│       ├── __init__.py
│       ├── pipeline.py     ← 段永平/芒格/裁决管线
│       ├── report_engine.py ← LLM 驱动报告生成（已写好）
│       └── prompts.py      ← 基于 48 份行研的提示词
├── models/
│   └── value_report.py     ← 价值投资报告数据模型
```

新增的路由：

| 路由 | 功能 | 来源 |
|------|------|------|
| `POST /api/v1/value-analysis` | 触发价值投资管线 | IRA |
| `GET /api/v1/reports/{id}` | 获取报告 | IRA |
| `POST /api/v1/reports/{id}/ask` | AI 追问 | IRA |
| `GET /api/v1/alerts` | 价格提醒 | IRA |
| `POST /api/v1/portfolio` | 模拟组合 | IRA |
| `POST /api/v1/archive` | 投研档案 | IRA |

### 前端选择：两个方案

#### 方案 A：保留 Vue 3（推荐）

```
优势：
- TACN 现有功能完整迁移，不需要重写
- 路由、状态管理、组件体系现成的
- Element Plus 功能全，开发快

劣势：
- 跟 IRA 的 Next.js 前端脱离
- Element Plus 重，性能一般
- 需要学 Vue（如果你不熟）
```

#### 方案 B：替换为 Next.js

```
优势：
- 统一技术栈（如果团队 React 熟练）
- shadcn/ui 轻量现代
- TailAdmin 风格已有雏形

劣势：
- TACN 的 Vue 页面全部要重写（40+ 页面）
- Vuex/Pinia 状态管理要重构
- 开发周期长 3-5 倍
```

### 报告引擎

新的报告引擎（`report_engine.py`）是纯后端代码，无论前端选哪个方案都能直接使用。

---

## 三、实施阶段

### Phase 1：基础整合（1-2 天）

1. 把 IRA 的后端代码复制到 TACN 的 `app/services/value_investing/`
2. 加新的 API 路由
3. 测试后端可用性
4. 跑通一次完整的价值投资管线

### Phase 2：前端扩展（2-3 天）

取决于方案选 A 还是 B：
- **方案 A**：在 Vue 里加新的页面组件
- **方案 B**：把 TACN 的核心功能（登录、筛选、数据同步）搬到 Next.js

### Phase 3：报告引擎（1 天）

1. 优化 LLM 调用（并行化，把 7 次串行降到 3 次并行）
2. 跑通完整报告输出
3. 加自审环节

### Phase 4：打磨（持续）

1. 修复 MongoDB 连接问题
2. 改善前端体验
3. 加测试

---

## 四、风险

| 风险 | 级别 | 应对 |
|------|------|------|
| MongoDB 未运行 | 🔴 | 先确认环境，或者改用文件持久化 |
| LLM 调用太慢 | 🟡 | 并行化 + 更短的 prompt |
| Vue 前端不熟 | 🟡 | 方案 A 可沿用现有 Vue 代码 |
| 两个项目数据模型冲突 | 🟡 | 统一用 TACN 的 MongoDB collection 命名 |
