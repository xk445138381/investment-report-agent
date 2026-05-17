# 投资报告 Agent 项目审查报告

> Pipeline: run_review01 | Profile: docs | 2026-05-17

## 1. 总体评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **产品定位** | 8/10 | 清晰 — 面向机构/投行的多 Agent 研报生成，差异化明确 |
| **架构设计** | 7/10 | 分层合理，可配置架构是亮点，但 Agent 内核实为 stub |
| **代码质量** | 6/10 | 计算层干净，测试覆盖好；存在 stub、死代码、类型不一致 |
| **安全性** | 4/10 | 已修复 XSS/上传/auth 三个关键问题；剩余 CORS 硬编码 |
| **可运行性** | 5/10 | 骨架可启动，但 Agent pipeline 没有端到端实现 |
| **文档** | 7/10 | 产品方案和设计系统详尽；README 曾过度宣称（已修正） |
| **综合** | **6.2/10** | 一个高质量的脚手架，距可用产品还需 Agent 实现 |

## 2. 五个维度详细审查

### 2.1 产品定位 — 8/10

**优势**：
- 15 项产品决策通过 13 轮 grill-me 深入访谈确定，方向经得起推敲
- 竞品分析透彻 — ai-hedge-fund 和 TradingAgents-CN 的源码级拆解
- 田中一光式东方秩序设计系统是差异化亮点，在金融工具中罕见

**不足**：
- 一级市场(VC/PE)数据源计划了但无实现路径
- 商业模式（Freemium SaaS + 私有化）未经验证

### 2.2 架构设计 — 7/10

**优势**：
- `config.json` 驱动一切（LLM/数据源/管线/Agent）是正确的架构决策
- "Python 做计算 + LLM 做叙事"双轨清晰
- Provider 抽象层 + 熔断/降级设计到位
- Local-First 数据策略务实

**不足**：
- 4 个 Agent 子包(data/analysis/debate/assembly)全是空 `__init__.py`
- Orchestrator `_run_agent` 是 log-only stub
- 4 个 Provider 实现(AkShare/Yahoo/Upload/LocalDB)全不存在
- 双 LLM(deep/quick)目前用同一模型，分层未体现

### 2.3 代码质量 — 6/10

**已验证通过**：81 unit + 7 E2E = 88 tests, 0 failures

**亮点**：
- 计算层 28 财务比率 + 3 估值模型单元测试完整
- 配置系统的 Pydantic 验证 + 交叉引用检查覆盖好
- Jinja2 模板引擎 HTML→PDF 管道可用

**代码审查发现的问题（已修复）**：
- DCF 现金重复计算、EV/EBITDA 符号错误 → 已修
- Jinja2 autoescape XSS → 已修
- pyproject.toml 缺依赖 → 已补全
- upload 无大小/类型校验 → 已加
- 无认证中间件 → JWT 已加
- config.json 无效模型名 → 已修正

**剩余问题**：
- Orchestrator 进度追踪 `_internal_pct` 逻辑粗糙
- 全局 `_tasks/_uploads/_templates` dict 不可水平扩展
- 日志配置写入了但从无人读取应用
- 无 CI/CD

### 2.4 安全性 — 4/10→7/10（修复后）

| 问题 | 状态 |
|------|------|
| Jinja2 autoescape 未启用(XSS) | ✅ 已修复 |
| 上传无校验(大文件 OOM) | ✅ 已修复 |
| 无认证(JWT token) | ✅ middleware.py 已加 |
| CORS localhost 硬编码 | ⚠️ 未修复 |
| SSE 无心跳(代理超时) | ⚠️ 未修复 |
| 全局可变状态(无并发保护) | ⚠️ 未修复 |

### 2.5 可运行性 — 5/10

**可启动**：
- `uvicorn src.api.main:app` — ✅ 17 routes 可访问
- `npm run dev` — ✅ Next.js 首页可交互
- `pytest tests/` — ✅ 81/81 pass

**不可用**：
- 无法生成真正的投资报告（Agent 管线是 stub）
- ProviderManager 没有 concrete provider，无法获取任何数据
- 用户上传文件后可读取但 Agent 不消费

### 2.6 文档 — 7/10

**优势**：产品方案 `.context/*.md` 和 `frontend/DESIGN.md` 详尽专业
**不足**：README 曾宣称未实现功能，已修正为准确描述

## 3. 技术债务清单（按优先级）

| 优先级 | 债务项 | 影响 |
|--------|--------|------|
| P0 | 实现至少一个 Agent (如 financial_analysis_agent.py) | 打通端到端 |
| P0 | 实现至少一个 Provider (如 akshare_provider.py) | 获取真实数据 |
| P1 | 全局状态 → 数据库/SQLite 持久化 | 多 worker 一致性 |
| P1 | 日志系统实际初始化 | 可运维 |
| P2 | SSE 心跳 | 生产环境可用 |
| P2 | CI/CD (GitHub Actions) | 持续质量保证 |
| P3 | CORS 可配置 | 生产部署 |
| P3 | Docker/docker-compose | 私有化部署 |

## 4. 下一步建议

1. **短期(P0)**：选一个方向打穿 — 要么实现 AkShare Provider + Financial Data Agent 走通"获取茅台财务数据→生成分析"的最小闭环；要么实现单个 Debate Agent 验证辩论 Prompt 效果
2. **中期**：填完 14 个 Agent，接入 DeepSeek API，实现完整 deep_dive pipeline
3. **长期**：批量报告、Word 导出、私有化部署

## 5. 证据

- 测试: 81 unit passed, 7 E2E passed (2026-05-17)
- 前端: Next.js 构建成功, 田中一光设计系统可交互
- Git: 7 commits, clean working tree
- 代码审查: clipboard-20260517-085007.md 发现的问题已修复 5/5 高优先级项

---

*Pipeline run_review01 · 2026-05-17 · investment-report-agent*
