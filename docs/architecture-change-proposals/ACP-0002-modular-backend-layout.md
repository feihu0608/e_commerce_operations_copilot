# ACP-0002 后端模块化目录与编排分层

- 状态：Approved
- 日期：2026-09-14
- 批准者：项目所有者（本次对话明确要求）
- 影响范围：后端目录、导入边界、LangGraph 编排、Worker 入口、架构检查、Skill

## 背景

后端实现长期集中在 `app` 根目录，API、模型适配、任务执行和工作流编排边界不清晰。随着准生产能力增加，继续堆叠会提高修改冲突、循环依赖和测试定位成本。

## 已批准决策

1. 按 API、core、domain、infrastructure、integrations、workflows、workers 分包。
2. LangGraph 的 State、节点、图构建、检查点和运行服务分别归档。
3. FastAPI、Celery 和 Dispatcher 根入口保留为薄兼容适配器，部署命令可以平滑迁移。
4. 架构守卫增加目录和入口体积检查，防止再次退化为单文件堆叠。
5. 完成模块重构后继续 ACP-0001 的 LangGraph、真实模型和 ECS 验收。
