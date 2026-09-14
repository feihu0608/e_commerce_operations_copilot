# 电商运营助手

面向课程实战、求职作品集和小范围公网演示的准生产级 AI 应用。项目覆盖商品运营、AI 诊断与创意、真实主图/视频生成、素材结果查看、投放方案创建与主管审批、经营指标复盘及表格导入。

当前边界：系统生成投放建议并保留人工审批记录，不连接淘宝、京东或抖音广告扣费接口；演示业务数据来自幂等初始化和导入样例。

## 架构

- React + TypeScript + Vite 前端，由 Nginx 提供同源入口和限流、安全响应头。
- FastAPI 模块化单体 API，PostgreSQL 是业务与任务状态事实来源。
- Redis + Celery Worker 执行 AI 和媒体任务。
- LangGraph 使用 Typed State 编排诊断、创意、投放建议和经营复盘；生产检查点保存在 PostgreSQL。
- Transactional Outbox Dispatcher 在数据库提交后可靠投递任务。
- `task_attempts`、`task_events` 记录执行尝试与时间线，重复消息不会重复执行已领取任务。
- 文本 AI 输出经过 Pydantic Schema 校验，最多执行一次结构修复。
- 文本模型超时、最大输出和思考模式可配置，并受 Worker 租约预算校验；嵌套 JSON Schema 同时约束初次生成与 repair。
- 供应商媒体即使返回通用二进制类型，也必须通过受支持格式的文件签名校验后才能持久化。
- 供应商余额、鉴权、限流和请求错误会分类为用户可执行的提示；额度/权限错误禁止盲目重试且不会静默降级为 Mock。
- 视频采用 submit/poll 两阶段短任务，不占用 Worker 循环等待。
- Alembic 管理数据库版本；部署时先迁移，再启动 API、Worker 和 Dispatcher。
- 审计日志、请求 ID、模型调用元数据、健康与就绪探针支持问题追踪。
- 后端按 `api/core/domain/infrastructure/integrations/services/workflows/workers` 分包；根入口保持薄适配。
- `python scripts/check_architecture.py` 校验批准文档哈希、关键组件、模块目录和入口体积，阻止静默架构漂移。

完整设计见 [电商运营助手架构设计文档.md](./电商运营助手架构设计文档.md)，准生产升级范围和证据见 [准生产级升级与验收说明.md](./准生产级升级与验收说明.md)。

## 本机开发检查

Python 依赖统一使用 `uv` 和 `backend/uv.lock`：

```powershell
Set-Location -LiteralPath 'F:\尚硅谷大模型\项目实战\电商运营助手\backend'
$env:UV_CACHE_DIR = '..\.deployment-state\uv-cache'
uv sync --frozen
uv run python -m compileall -q app migrations
uv run pytest -q

Set-Location -LiteralPath '..'
python scripts/check_architecture.py

Set-Location -LiteralPath 'frontend'
pnpm install --frozen-lockfile
pnpm build
```

本机不使用 Docker Desktop。PostgreSQL、Redis、API、Worker、Dispatcher 和 Nginx 的完整集成测试在阿里云 ECS Docker Compose 环境运行。

## ECS 启动和更新

项目位于 `/root/myproject/e_commerce_operations_copilot`，真实 `.env` 仅保存在服务器且权限应为 `600`。

```bash
cd /root/myproject/e_commerce_operations_copilot
./manage.sh config
./manage.sh prepare
./manage.sh start
./manage.sh doctor
```

日常更新会先备份数据库，再拉取、构建、迁移和重启：

```bash
./manage.sh update
```

常用命令：

```bash
./manage.sh status
./manage.sh guard
./manage.sh logs backend
./manage.sh logs worker
./manage.sh logs dispatcher
./manage.sh backup
./manage.sh migrate
./manage.sh restart
./manage.sh pause
./manage.sh stop
```

详细运维步骤见 [阿里云ECS环境配置与项目启停说明.md](./阿里云ECS环境配置与项目启停说明.md)。

## API 运行状态

- `GET /api/health`：进程和数据库存活状态、AI/媒体模式、部署版本。
- `GET /api/ready`：数据库与 Redis 就绪状态；容器健康检查使用该接口。
- `GET /api/tasks/{id}/events`：任务状态时间线。
- `GET /api/audit-logs`：主管查看关键操作审计记录。

图片和视频真实生成会产生模型费用。Mock 结果与 live 结果始终通过 `provider_mode` 区分，Mock 通过不能替代真实供应商验收。

2026 年 9 月 14 日的实测任务、模型耗时、媒体大小、审批状态和浏览器截图见 [准生产级升级与验收说明.md](./准生产级升级与验收说明.md)。
