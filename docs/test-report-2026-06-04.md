# 测试报告 - 2026-06-04

## 1. 测试结论

本轮按“本地闭环”执行，覆盖后端单测、前端 lint/build、本地服务启动、核心 API、主要页面路由、报告可信度数据、SSE、组合与归档接口。

总体状态：`PASS_WITH_DATA_LIMITATIONS`

核心基础能力可运行：后端健康检查、前端页面路由、报告任务创建、任务状态、SSE、报告读取、报告列表、组合增删、归档、配置、自选股接口均有实测通过项。修复后复验结果：

- `FIXED` 中文公司名 `贵州茅台` 现在可创建报告任务，返回 201。
- `FIXED` 旧持久化报告现在会补 `data_quality.result`，并移除 `_prices/_financials` 原始对象字段。
- `FIXED` LLM subprocess 已改为通过 stdin 传 prompt，单测覆盖 Windows 长命令风险；AAPL deep_dive 复跑最终进入 `completed / complete / 100%`。
- `FIXED` Playwright Chromium 已安装，DOM 级页面断言已完成。
- `FIXED` QVeris A 股财报不再依赖硬编码 ticker 映射，合法 `600xxx.SH/000xxx.SZ` 可直接查询；真实复验 `601318.SH` 返回 11 条财报。
- `PASS_FIXED` 重新生成 `600519.SH quick_scan`，新 task `08d50fc2-4fc1-42d8-9096-172d1d0d16d2` 的 `data_quality.result.status=real`，`prices_count=726`，`financials_count=11`。
- `PASS_FIXED` 重新生成 `600519.SH value_deep_dive`，新 task `e24e6592-b4de-4177-8516-ef2efeb730bc` 的 `data_quality.result.status=real`，并返回价值投资 8 章结构。
- `FIXED` LLM report engine 价值报告解析只返回 6 章的问题；现在缺失章节会按 `value_investor` contract 补齐到 8 章。
- `PASS` 已新增可重复执行的页面 smoke e2e：`npm run test:e2e:smoke`，5 条 DOM/错误路径断言通过。

## 2. 测试环境

| 项目 | 结果 |
|---|---|
| 工作区 | `C:\Users\Admin\.proma\agent-workspaces\default\99ea9c20-17d3-4ade-9bab-a932bf3e2dbe` |
| 后端目录 | `backend` |
| 前端目录 | `frontend` |
| Python | `3.12.10` |
| 后端测试框架 | `pytest 9.0.3` |
| 前端框架 | Next.js 16.2.6 / React 19 |
| 后端服务 | `http://127.0.0.1:8000` |
| 前端服务 | `http://127.0.0.1:3000` |

## 3. 自动化验证结果

| 检查项 | 命令 | 状态 | 关键输出 |
|---|---|---|---|
| 后端 unit tests | `python -m pytest tests/unit/ -v` | `PASS` | `88 passed, 1 skipped, 1 warning in 17.45s` |
| 前端 lint | `npm run lint` | `PASS` | exit 0，输出为空，0 error / 0 warning |
| 前端 build | `npm run build` | `PASS` | `Compiled successfully`，生成 9 条 app route，包括 `/`, `/archive`, `/portfolio`, `/progress`, `/report`, `/reports`, `/settings`, `/templates` |
| 前端 smoke e2e | `npm run test:e2e:smoke` | `PASS` | `5 passed (7.3s)` |

## 4. 服务启动与健康检查

| 检查项 | 状态 | 证据 |
|---|---|---|
| 后端启动 | `PASS` | `python -m uvicorn api.main:app --host 127.0.0.1 --port 8000` 启动成功 |
| 前端启动 | `PASS` | `npm.cmd run dev -- -p 3000` 启动成功 |
| 后端 health | `PASS` | `GET /health` 返回 200：`{"status":"ok","version":"0.1.0"}` |
| `/api/v1/health` | `NOT_APPLICABLE` | 返回 404，实际 health endpoint 是根路径 `/health` |
| 前端首页 HTTP | `PASS` | `GET /` 返回 200 HTML |

## 5. API 功能覆盖矩阵

| 功能 | 请求 | 状态 | 结果说明 |
|---|---|---|---|
| 健康检查 | `GET /health` | `PASS` | 200 OK |
| 报告生成 quick scan | `POST /api/v1/report/generate`，`600519.SH + quick_scan` | `PASS` | 201 Created，task `3b82877c-6754-48ce-b817-1872c53a9963` |
| 报告生成 quick scan - 财报修复后复验 | `POST /api/v1/report/generate`，`600519.SH + quick_scan` | `PASS_FIXED` | task `08d50fc2-4fc1-42d8-9096-172d1d0d16d2` 完成，`data_quality.result.status=real` |
| 报告生成 value deep dive | `POST /api/v1/report/generate`，`600519.SH + value_deep_dive` | `PASS` | 201 Created，task `8aec5852-6d09-45e0-be0b-590ae89f25da` |
| 报告生成 value deep dive - 财报与章节修复后复验 | `POST /api/v1/report/generate`，`600519.SH + value_deep_dive` | `PASS_FIXED` | task `e24e6592-b4de-4177-8516-ef2efeb730bc` 完成，`data_quality.result.status=real`，返回 8 章 |
| 报告生成 deep dive | `POST /api/v1/report/generate`，`AAPL + deep_dive` | `PASS_FIXED` | 修复后复跑 task `e05ddd28-369c-4bdd-904b-46fa0ce157cc`，最终 `completed / complete / 100%` |
| 中文名称生成 | `POST /api/v1/report/generate`，`贵州茅台 + quick_scan` | `PASS_FIXED` | 修复后返回 201，task `a4470b9e-7ee1-439e-98f5-fc928bf315e9` |
| 任务状态 | `GET /api/v1/report/{taskId}/status` | `PASS` | quick/value/deep 均返回 200 |
| SSE 进度 | `GET /api/v1/report/{taskId}/stream` | `PASS` | 返回 `event: progress` 和多条 `agent_completed` |
| 报告读取 - 新 value task | `GET /api/v1/report/8aec...` | `PASS` | 200，包含 `data_quality.result`、8 个章节、`value_judge` |
| 报告读取 - 新 quick task | `GET /api/v1/report/3b82...` | `PASS` | 200，包含 `data_quality.result`，quick scan 不含 section_writer 属预期 |
| 报告读取 - 无效 task | `GET /api/v1/report/not-a-real-task-id` | `PASS` | 404 `Report not found` |
| 报告列表 | `GET /api/v1/reports?limit=5` | `PASS` | 200，返回 3 条报告元数据 |
| 组合读取 | `GET /api/v1/portfolio` | `PASS` | 200，空组合 summary 正确 |
| 组合新增 | `POST /api/v1/portfolio` | `PASS` | 200，测试持仓 `TEST` 新增成功 |
| 组合删除 | `DELETE /api/v1/portfolio/TEST` | `PASS` | 200，删除后组合恢复为空 |
| 归档新增 | `POST /api/v1/archive` | `PASS` | 200，归档 task `8aec...` 成功 |
| 归档列表 | `GET /api/v1/archive` | `PASS` | 200，返回 2 条归档 |
| 配置接口 | `GET /api/v1/config` | `PASS` | 200，返回 pipelines、providers、agents |
| 自选股 | `GET /api/v1/watchlist` | `PASS` | 200，返回空 watchlist |

## 6. 数据可信度验证

| 报告 | 状态 | 结果 |
|---|---|---|
| 新 quick task `3b82877c...` | `PASS` | `data_quality.result.status=partial`，`prices_count=725`，`financials_count=0`，`missing=["financials"]` |
| 修复后新 quick task `08d50fc2...` | `PASS_FIXED` | `data_quality.result.status=real`，`prices_count=726`，`financials_count=11`，`data_sources.prices=TradingAgents`，`data_sources.financials=QVeris` |
| 新 value task `8aec5852...` | `PASS` | `data_quality.result.status=partial`，有 `provider_trace`，有 8 个章节和 `value_judge` |
| 修复后新 value task `e24e6592...` | `PASS_FIXED` | `data_quality.result.status=real`，`prices_count=726`，`financials_count=11`，8 个章节：`executive_summary/business_model/corporate_character/financial_health/valuation/inversion_checklist/dual_verdict/final_judgment` |
| 旧持久化 task `952eea35...` | `PASS_FIXED` | 修复后补 `data_quality.result.status=empty`，并移除 `_prices/_financials` |
| QVeris A 股财报 provider | `PASS_FIXED` | `601318.SH` 真实复验返回 11 条财报；`600519.SH` 真实复验返回 11 条财报 |

新报告的数据可信度链路已经能输出真实状态；旧报告通过兼容层补齐可信度字段。

## 7. 页面功能覆盖矩阵

页面已通过 Playwright Chromium 做 DOM 级断言。注意：Next dev server 应使用 `http://localhost:3000` 访问；用 `127.0.0.1:3000` 会触发 Next dev 的 `allowedDevOrigins` 限制，导致 HMR/客户端行为不可靠。

已沉淀可重复执行入口：`npm run test:e2e:smoke`。

| 页面 / 流程 | 状态 | 证据 |
|---|---|---|
| `/` 首页 | `PASS_DOM` | 找到 `新建分析`、`开始分析` |
| `/report` 无 task | `PASS_DOM` | 找到 `Demo 数据`、`贵州茅台` |
| `/report?task=not-a-real-task-id` | `PASS_DOM` | 找到 `真实报告读取失败`、`不会用 Demo 报告替代真实结果` |
| `/progress?ticker=bad-input-for-test...` | `PASS_DOM` | 找到 `真实报告未生成`，未跳 Demo |
| `/reports` | `PASS_DOM` | 找到 `报告列表` |
| `/portfolio` | `PASS_DOM` | 找到 `模拟组合` |
| `/archive` | `PASS_DOM` | 找到 `投研档案` |
| `/settings` | `PASS_DOM` | 找到 `模型与配置` |

## 8. 已发现问题

### P1: AAPL deep_dive 任务长时间停在 running/progress 100

- 状态：`FIXED`
- 复现步骤：
  1. `POST /api/v1/report/generate`，body 为 `{"ticker":"AAPL","report_type":"deep_dive","template_id":"deep_dive_default"}`。
  2. 轮询 `GET /api/v1/report/09b95a6a-f993-4a30-9a91-89f70faa265e/status`。
- 实际结果：
  - 任务创建成功。
  - 修复前任务 `09b95a6a...` 多次查询仍为 `status=running`，`current_phase=phase_4`，`progress_pct=100`。
  - 修复后最终复跑任务 `e05ddd28...` 进入 `status=completed`，`current_phase=complete`，`progress_pct=100`。
  - 修复前后端日志出现 `LLM subprocess error: [WinError 206] 文件名或扩展名太长`；修复后复跑未再出现该错误，但仍有 Bull/Bear/Judge LLM fallback。
- 预期结果：
  - phase_4 完成后任务应转为 `completed`，或失败时明确转为 `failed` 并暴露 error。
- 建议：
  - 已将 LLM subprocess prompt 改为 stdin 传参，并用单测覆盖长 prompt 不进入命令行参数。
  - 已给 orchestrator 增加 agent 级 timeout/exception 收口；单个 agent 超时会记录 failed 并允许 pipeline 继续完成。

### P1: 旧持久化报告缺少可信度字段且包含对象字符串

- 状态：`FIXED`
- 复现步骤：
  1. `GET /api/v1/report/952eea35-fbd3-4158-9961-dae463f15a6a`。
  2. 检查 `data_quality.result` 和 `_prices`。
- 实际结果：
  - `data_quality.result` 不存在。
  - `_prices` 数组包含 Python object repr 字符串。
- 预期结果：
  - 旧报告要么兼容生成默认 `data_quality.result.status=empty/partial`，要么前端明确显示“旧报告未记录数据可信度”。
  - API 不应向前端返回 Python object repr。
- 建议：
  - 已在报告读取时做兼容补齐：无 `data_quality` 时构造 `empty` 状态。
  - 已从报告 API 响应中剥离 `_prices/_financials` 原始对象字段。

### P2: 中文公司名无法生成报告

- 状态：`FIXED`
- 复现步骤：
  1. `POST /api/v1/report/generate`，ticker 为 `贵州茅台`。
- 实际结果：
  - 返回 400：无法识别公司名称或股票代码。
- 预期结果：
  - 错误提示中写明支持 `贵州茅台`，实际应解析为 `600519.SH`。
- 建议：
  - 已修复 orchestrator 的裸中文公司名映射。
  - 运行时复验：`贵州茅台 + quick_scan` 返回 201。

### P3: Playwright 缺少浏览器二进制

- 状态：`FIXED`
- 复现步骤：
  1. 通过 Playwright 启动 Chromium。
- 实际结果：
  - 报错：`Executable doesn't exist ... chromium_headless_shell...`
  - 提示需要运行 `npx playwright install`。
- 预期结果：
  - 能执行 DOM 级页面断言和截图。
- 建议：
  - 已执行 `npx playwright install chromium`。
  - 已完成 DOM 级验证。

### P2: QVeris A 股财报只支持硬编码 ticker

- 状态：`FIXED`
- 复现步骤：
  1. 调用 `QverisProvider().get_financials("601318.SH", years=3)`。
  2. 检查返回财报条数。
- 实际结果：
  - 修复前：非 `TICKER_MAP` 预置代码会直接返回空数组。
  - 修复后：合法 A 股代码直接传给 QVeris；真实复验 `601318.SH` 返回 11 条财报。
- 预期结果：
  - 用户输入合法 A 股代码时，不应要求先写入本地硬编码映射。
- 建议：
  - 已增加单测 `test_cn_financials_accept_unmapped_valid_a_share_ticker`。
  - 已收紧 `data_sources`：只有实际拿到记录时才标记 provider 来源。

### P2: value_deep_dive 价值报告只返回 6 章

- 状态：`FIXED`
- 复现步骤：
  1. 生成 `600519.SH + value_deep_dive + value_investor`。
  2. 读取 `GET /api/v1/report/{taskId}`。
  3. 检查 `section_writer.result.sections`。
- 实际结果：
  - 修复前 task `96857800-da90-425e-9036-b5b361b5888f` 可信度为 `real`，但只返回 6 章，缺少 `corporate_character` 与 `final_judgment`。
  - 修复后 task `e24e6592-b4de-4177-8516-ef2efeb730bc` 返回 8 章。
- 预期结果：
  - `value_investor` 模板承诺 8 章，LLM report engine 即使无法可靠拆分某章，也必须按 contract 补齐。
- 建议：
  - 已增强 `report_engine._parse_sections()`，新增企业文化与综合判定识别。
  - 已增加缺失章节补齐逻辑和单测 `test_value_report_parser_returns_all_eight_sections`。

## 9. 环境限制

| 限制 | 影响 |
|---|---|
| AkShare 当前受代理/网络限制不可用 | AkShare fallback 无法作为稳定兜底；QVeris 财报路径已可用 |
| 既有测试任务是在修复前生成 | 报告中早期 task 仍保留 `financials_count=0` 的历史结果；修复后新 quick/value task 已验证为 `real` |

## 10. 下一步建议

1. 把当前改动整理为一次明确提交，避免和历史无关脏改混在一起。
2. 后续可把 smoke e2e 扩展为 CI 流程，覆盖真实 task 报告页的数据可信度卡片。
3. 可考虑在 `next.config.js` 加 `allowedDevOrigins: ['127.0.0.1']`，方便以后用 127 地址测试 Next dev server。
