# 投资报告 Agent (Investment Report Agent)

基于多 Agent 协作的专业投资研究报告生成系统（MVP 脚手架）。

## 状态

⚠️ **早期开发阶段** — 核心架构和计算层已完成，Agent 管线为 stub 实现。

## 已实现

- **配置系统**: JSON 驱动的可配置架构 (LLM/数据源/管线/Agent)
- **数据模型**: Pydantic schemas (PriceData, FinancialStatement, ReportState, etc.)
- **Provider 抽象层**: DataProvider ABC, ProviderManager (路由+降级+熔断)
- **Python 计算层**: 财务比率, DCF/Owner Earnings/EV-EBITDA 估值, 敏感性矩阵
- **Agent 编排**: Orchestrator (意图路由, 管线调度, SSE 进度)
- **报告渲染**: Jinja2 模板引擎, HTML→PDF (WeasyPrint)
- **API**: FastAPI (17 routes: 报告/模板/上传/用户/配置)
- **前端**: Next.js + 田中一光式东方秩序设计系统
- **测试**: 81 unit + 7 Playwright E2E

## 待实现 (Planned)

- [ ] 具体 Provider 实现 (AkShare/Yahoo Finance)
- [ ] Agent 子模块实现 (data/analysis/debate/assembly agents)
- [ ] 辩论多伦循环
- [ ] 用户认证 (token-based)
- [ ] 数据源具体接入
- [ ] CI/CD (GitHub Actions)

## 快速开始

```bash
# 后端
cd backend
pip install -e ".[dev]"
cp .env.example .env
uvicorn src.api.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev            # http://localhost:3000
```

## 测试

```bash
cd backend && pytest tests/ -v   # 后端单元测试
cd frontend && npx playwright test  # E2E 测试
```

## 技术栈

- **后端**: Python / FastAPI / Pydantic / LangChain
- **前端**: Next.js 16 / TypeScript / Tailwind CSS
- **设计**: 田中一光式东方秩序
- **测试**: Pytest + Playwright

## License

MIT
