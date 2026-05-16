# 投资报告 Agent (Investment Report Agent)

基于多 Agent 协作的专业投资研究报告生成系统。覆盖 A 股、港股、美股，支持深度研报、快速简报、宏观周报等多种报告类型。

## 架构

```
frontend (Next.js + TypeScript)
    ↕ REST + SSE
backend (FastAPI + Python)
    ├── Agent Orchestrator (多 Agent 管线)
    │   ├── Phase 1: 数据聚合 (4 Agents 并行)
    │   ├── Phase 2: 深度分析 (4 Agents 并行)
    │   ├── Phase 3: 多空辩论 (Bull/Bear + 裁判)
    │   └── Phase 4: 统稿排版 (写作 + 图表 + 摘要)
    ├── Python 计算层 (28 财务比率 + DCF + Owner Earnings + EV/EBITDA)
    ├── Provider 数据层 (AkShare/Yahoo F./用户上传/本地缓存)
    └── Report Export (Jinja2 → HTML → PDF/Word)
```

## 快速开始

### 后端

```bash
cd backend
pip install -e ".[dev]"
cp .env.example .env   # 填入 Anthropic API Key
uvicorn src.api.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
```

### 测试

```bash
# 后端
cd backend && pytest tests/ -v

# E2E
cd frontend && npx playwright test
```

## 技术栈

- **后端**: Python / FastAPI / LangChain / Pydantic
- **前端**: Next.js / TypeScript / Tailwind CSS
- **设计**: 田中一光式东方秩序 (Ikko Tanaka · Eastern Order)
- **数据**: AkShare / Yahoo Finance / 用户上传
- **测试**: Pytest (81 unit) / Playwright (7 E2E)
- **LLM**: Claude (Anthropic) / OpenAI / DeepSeek (可配置)

## 设计系统

详见 `frontend/DESIGN.md` — 田中一光式东方秩序，和纸暖白 + 深棕墨色 + 朱砂强调。

## 项目文档

完整产品与技术方案见 `.context/saturday-may-16-foamy-shore.md`。

## License

MIT
