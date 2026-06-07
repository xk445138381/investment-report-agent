# 投资报告 Agent

多 Agent AI 投研系统，用于生成股票快速扫描和价值投资深度报告。

## 当前状态

`DEPLOYABLE_CANDIDATE`

当前版本已具备可部署候选能力：

- 后端 FastAPI 可启动并生成真实报告任务。
- 前端 Next.js 可构建并通过 smoke e2e。
- 报告失败路径不会回退到 Demo。
- Demo 报告会显式标记 `Demo 数据`。
- 报告返回 `data_quality.result`，包含 `real | partial | empty`、记录数、缺失项、数据来源和 provider trace。
- A 股 `quick_scan` 与 `value_deep_dive` 已通过真实任务复验，行情来自 TradingAgents，财报来自 QVeris。
- 前端后端地址支持环境变量配置，后端生产环境默认不暴露 debug routes。
- 仓库包含 Docker/compose 与 GitHub Actions CI 配置，compose 服务带 healthcheck，CI 会验证 Docker 镜像构建。

不把当前版本描述为生产稳定版：外部数据源、LLM key、MongoDB、网络环境和目标云平台仍会影响运行结果。

## 目录

- `backend/` - FastAPI 后端、Agent 编排、数据源、报告 API
- `frontend/` - Next.js 16 前端
- `docs/` - 测试报告、上线检查报告、实施计划

## 环境要求

- Python 3.12+
- Node.js 20+
- 可访问 DeepSeek/QVeris 等外部 API 的网络
- 可选 MongoDB；不可用时部分列表/归档持久化能力会受限

后端环境变量参考 `backend/.env.example`。本地运行至少建议配置：

```powershell
DEEPSEEK_API_KEY=...
QVERIS_API_KEY=...
INVESTMENT_REPORT_CONFIG=config.json
FRONTEND_ORIGINS=http://localhost:3000
ENABLE_RUNTIME_CONFIG_WRITES=false
REQUIRE_MONGODB=false
REQUIRED_ENV_VARS=SECRET_KEY,DEEPSEEK_API_KEY,QVERIS_API_KEY
```

前端部署时配置：

```powershell
NEXT_PUBLIC_API_URL=https://your-backend.example.com/api/v1
```

## 本地启动

后端：

```powershell
cd backend
$env:PYTHONPATH = "src"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问：`http://localhost:3000`

## 验证

后端单测：

```powershell
cd backend
python -m pytest tests/unit/ -v
```

前端检查：

```powershell
cd frontend
npm run lint
npm run build
npm run test:e2e:smoke
```

一键上线检查：

```powershell
python scripts/launch_check.py
```

目标环境 URL 预部署校验：

```powershell
python scripts/predeploy_check.py --static --production-target `
  --backend-url https://your-backend.example.com `
  --frontend-url https://your-frontend.example.com `
  --api-url https://your-backend.example.com/api/v1
```

## 容器部署预演

准备 `backend/.env` 后执行：

```powershell
docker compose -f docker-compose.prod.yml up --build
```

本地 compose 默认：

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- 后端就绪检查：`http://localhost:8000/ready`
- 后端基础指标：`http://localhost:8000/metrics`
- MongoDB：compose 内部服务 `mongo`
- compose healthcheck：MongoDB ping、后端 `/ready`、前端首页 HTTP 200
- compose 默认 `REQUIRE_MONGODB=true`，MongoDB 不可用时后端 `/ready` 不通过

生产环境需要按实际域名覆盖：

```powershell
FRONTEND_ORIGINS=https://your-frontend.example.com
NEXT_PUBLIC_API_URL=https://your-backend.example.com/api/v1
```

## 已验证核心流程

- `600519.SH quick_scan`
  - `data_quality.result.status=real`
  - `prices_count=726`
  - `financials_count=11`
- `600519.SH value_deep_dive`
  - `data_quality.result.status=real`
  - 返回价值投资 8 章结构
- 无效真实 task 报告页显示错误，不跳 Demo
- 无 task 报告页允许 Demo，但显式标记 `Demo 数据`
- `ENVIRONMENT=production` 时 `/api/v1/debug/*` 不注册，运行时写配置默认禁用
- `/ready` 会检查配置加载、必需环境变量和生产密钥占位符
- `REQUIRE_MONGODB=true` 时 `/ready` 还会 ping MongoDB
- `/metrics` 提供 Prometheus 文本格式的请求数、异常数和请求耗时汇总
- `python scripts/launch_check.py` 会校验生产保护和 compose healthcheck 配置
- GitHub Actions 包含 `launch-check` 和 `docker-build` 两个 job；`docker-build` 只构建镜像，不推送。
- `python scripts/launch_check.py` 会生成 `docs/release-manifest-latest.json` 发布清单。
- GitHub Actions 会上传 release manifest artifact，并提供手动 `Deploy Verify` workflow 验证真实部署目标。
- `python scripts/launch_check.py` 会运行 repository safety check，防止 `.env`、私钥和明显密钥样式内容进入发布。

详细结果见：

- `docs/test-report-2026-06-04.md`
- `docs/launch-readiness-2026-06-05.md`
- `docs/deployment-runbook-2026-06-05.md`
- `docs/release-manifest-latest.json`

## 已知限制

- 外部 API key 缺失会导致 LLM 或数据源不可用。
- AkShare 在当前环境可能受代理/网络限制，QVeris 是 A 股财报主要可用兜底。
- MongoDB 不可用时，报告列表、归档、组合等持久化功能可能只保留降级结果。
- 当前机器未安装 Docker，本轮已补部署配置但未本地构建镜像。
- 生产环境仍需要接入正式密钥管理、托管监控告警、日志聚合和数据库备份策略。

## 技术栈

- 后端：FastAPI / Pydantic / pytest
- 前端：Next.js 16 / React 19 / Tailwind / Playwright
- 数据源：TradingAgents / QVeris / AkShare fallback
- LLM：DeepSeek 子进程调用
