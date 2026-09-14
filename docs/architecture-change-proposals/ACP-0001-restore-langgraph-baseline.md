# ACP-0001 恢复 LangGraph 架构基线

- 状态：Approved
- 日期：2026-09-14
- 批准者：项目所有者（本次对话明确要求）
- 影响范围：AI 编排、状态恢复、依赖、测试、架构文档

## 背景

原 V1 架构已经明确选择四类有边界的 LangGraph 工作流和 Typed State。实现阶段未落地该设计，随后又未经项目所有者确认把文档改成“暂不引入 LangGraph”，造成架构基线被实现反向覆盖。

## 已批准决策

项目所有者明确要求按准生产级架构修正，并要求建立机制，禁止代理自行静默修改架构。因此恢复并落实以下基线：

1. DiagnosisGraph、CreativeGraph、StrategyGraph、ReviewGraph 使用 LangGraph StateGraph。
2. 使用 Typed GenerationState 和有界 `load_context → generate → validate → repair/persist` 节点。
3. 生产使用 PostgreSQL Checkpointer；业务表仍是审批、任务和内容事实的唯一权威。
4. Celery 保留异步调度职责，图片/视频继续使用供应商 submit/poll 状态机。
5. 后续物质性架构变化必须先提交 ACP 并取得项目所有者明确批准。

## 验收证据

- 代码存在真实 StateGraph、条件边、Typed State 和四类 Schema。
- 单元测试覆盖正常路径、一次有限修复、策略草稿和复盘内容持久化。
- ECS 存在 LangGraph checkpoint 表并完成真实工作流验收。
- 架构基线检查在提交、部署和交付前通过。
