# 投资报告 Agent 技术实施任务列表

本列表将技术解决方案拆解为具体的开发任务，按模块分类，并标注了实施要点。

## 1. 事实锚定与数据校验模块
- [ ] **实现结构化数据注入逻辑**：
    - 开发数据预处理模块，将计算层输出转换为 Agent 可读的 JSON Context。
    - 在 Prompt 模板中预留 `{{context}}` 占位符。
- [ ] **更新 System Prompt 规范**：
    - 统一在所有 Agent 的 System Prompt 中加入“引用强制”指令。
    - 定义标准的数据来源标注格式（如 `[Source: XXX]`）。
- [ ] **开发输出校验器 (Output Validator)**：
    - 使用 Pydantic 定义各 Agent 的输出 Schema。
    - 实现逻辑校验函数，对比 Agent 输出数字与 Context 中的原始数据。
    - 实现自动重试机制（最多 3 次），并在重试 Prompt 中指出数据错误点。

## 2. 编排流控与稳定性模块
- [ ] **构建 LangGraph 有状态图**：
    - 定义 `AgentState` 结构，包含 `messages`, `data_context`, `metadata` 等字段。
    - 实现节点跳转逻辑，并集成 `max_turns` 计数器。
- [ ] **集成 Checkpointer 持久化**：
    - 配置 SQLite 或 Redis Checkpointer，实现节点级的状态保存与恢复。
- [ ] **实现超时与熔断机制**：
    - 为每个 Agent 调用封装 `asyncio.wait_for` 超时处理。
    - 开发熔断器装饰器，记录连续失败次数并触发降级逻辑。

## 3. 异步架构与性能优化模块
- [ ] **搭建异步任务框架**：
    - 配置 Celery Worker 处理报告生成长任务。
    - 实现 FastAPI 接口，支持任务提交、状态查询及结果获取。
- [ ] **实现多级缓存系统**：
    - 集成 `cachetools` 实现 L1 内存缓存。
    - 配置 Redis 实现 L2 分布式缓存，并定义统一的 Key 命名规范。
    - 优化数据库索引，提升 L3 持久化存储的读写性能。
- [ ] **优化并发执行逻辑**：
    - 识别编排流中的并行节点，使用 `asyncio.gather` 进行重构。
- [ ] **计算层向量化重构**：
    - 使用 NumPy/Pandas 重写核心金融指标计算函数，消除 Python 原生循环。

## 4. Prompt 工程与测试回归模块
- [ ] **建立 Prompt 管理系统**：
    - 将 Prompt 抽离至 YAML 文件，并集成至 CI/CD 流程。
- [ ] **构建标准测试集 (Golden Dataset)**：
    - 收集并标注 50 个典型标的的原始数据及预期分析结论。
- [ ] **开发自动化评估脚本**：
    - 集成语义相似度计算工具（如 Sentence-Transformers）。
    - 编写正则或 LLM 辅助脚本，校验数据提取准确率及格式合规率。
- [ ] **实现灰度发布逻辑**：
    - 在配置中心增加模型版本权重控制，支持按比例分流请求至新模型。
