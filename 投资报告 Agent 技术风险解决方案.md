# 投资报告 Agent 技术风险解决方案

## 1. 针对“Agent 输出幻觉”的解决方案：事实锚定架构 (Fact-Anchored Architecture)

### 1.1 核心原理
通过将 LLM 的推理过程与确定性的 Python 计算层解耦，确保所有输出的数字和关键结论都有据可查。

### 1.2 实施方案
-   **数据注入 (Data Injection)**：在调用 Agent 前，系统先通过 Python 计算层获取结构化数据（JSON 格式），并将其作为 `Context` 强制注入 Prompt。
-   **引用强制 (Mandatory Citation)**：在 System Prompt 中要求 Agent 在引用任何数字或结论时，必须标注数据来源（如 `[Source: Financial_Statement_Q3]`）。
-   **输出校验 (Output Validation)**：使用 Pydantic 对 Agent 的输出进行 Schema 校验。如果输出中包含的数字与注入的数据不符，系统将自动触发重试（Retry）或报错。
-   **思维链约束 (CoT Constraints)**：要求 Agent 先列出计算过程或逻辑步骤，再给出最终结论，以便于人工或系统审计。

## 2. 针对“编排逻辑死锁”的解决方案：有状态图管理与熔断机制

### 2.1 核心原理
利用 LangGraph 的有状态图（Stateful Graph）管理 Agent 协作流，并引入显式的终止条件和熔断器。

### 2.2 实施方案
-   **最大迭代限制 (Max Iteration Limit)**：在 LangGraph 的节点跳转逻辑中，为每个循环（如辩论轮次）设置 `max_turns` 参数。一旦超过阈值，系统强制跳转至“总结节点”。
-   **超时控制 (Timeout Control)**：为每个 Agent 节点设置 `request_timeout`。如果单个 Agent 响应时间过长，系统将记录错误并尝试切换至备用模型或返回降级结果。
-   **状态快照 (State Snapshot)**：利用 LangGraph 的 Checkpointer 功能，在每个节点执行后保存状态快照。如果发生死锁或崩溃，系统可以从最近的稳定状态恢复。
-   **熔断器模式 (Circuit Breaker)**：如果某个 Agent 连续失败次数超过设定值，系统将自动熔断该路径，并通知主编排器（Orchestrator）采取备选方案。

## 3. 针对“性能瓶颈”的解决方案：异步并发与多级缓存体系

### 3.1 核心原理
通过异步非阻塞架构处理长耗时任务，并利用多级缓存减少重复计算和 API 调用。

### 3.2 实施方案
-   **异步任务队列 (Asynchronous Task Queue)**：使用 FastAPI + Celery + Redis 架构。用户提交报告请求后立即返回 `task_id`，报告生成过程在后台异步执行。
-   **多级缓存策略 (Multi-level Caching)**：
    -   **L1 (Memory)**：缓存高频访问的基础配置和元数据。
    -   **L2 (Redis)**：缓存 Agent 的中间输出结果和计算层的结构化数据。
    -   **L3 (SQLite/PostgreSQL)**：持久化存储已生成的完整报告和历史行情数据。
-   **并发执行 (Parallel Execution)**：在编排逻辑中，对于互不依赖的 Agent（如 Market Analyst 和 News Analyst），使用 `asyncio.gather` 进行并发调用，显著缩短总耗时。
-   **计算层优化**：使用 NumPy 和 Pandas 进行向量化计算，替代 Python 原生循环，提升金融指标计算速度。

## 4. 针对“模型版本迭代”的解决方案：Prompt 单元测试与回归体系

### 4.1 核心原理
建立一套独立于业务逻辑的 Prompt 评估与回归测试框架，确保模型升级后的稳定性。

### 4.2 实施方案
-   **Prompt 模板化与版本化**：将所有 Prompt 存储在独立的 YAML 文件中，并使用 Git 进行版本控制。
-   **标准测试集 (Golden Dataset)**：构建包含 50-100 个典型案例的测试集，涵盖不同行业、不同市场环境的标的。
-   **自动化评估指标**：
    -   **语义相似度**：比较新旧模型输出的语义一致性。
    -   **数据提取准确率**：校验新模型从文本中提取关键指标的准确性。
    -   **格式合规率**：校验输出是否符合预定的 Markdown 或 JSON 格式。
-   **灰度发布 (Canary Deployment)**：在升级底层模型（如从 Sonnet 3.0 升级到 3.5）时，先在 10% 的请求中试用新模型，监控各项指标无误后再全量切换。

## 5. 总结

本技术解决方案通过“事实锚定”解决准确性问题，通过“有状态图”解决稳定性问题，通过“异步缓存”解决性能问题，通过“回归体系”解决可持续性问题。这些方案的实施将为“投资报告 Agent”提供坚实的技术底座。
