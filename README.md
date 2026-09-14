# 电商运营助手

本项目采用“Windows 本机开发 + 阿里云 ECS 容器化集成测试与演示”的工作方式。

## 环境约定

- Python 依赖统一由 `uv` 和 `backend/uv.lock` 管理。
- 本机不使用 Docker Desktop。
- PostgreSQL、Redis、FastAPI、Celery Worker 和前端 Nginx 均在阿里云 ECS 的 Docker Compose 中运行。
- ECS 项目目录为 `/root/myproject/e_commerce_operations_copilot`，公网入口为 `http://<ECS_PUBLIC_IP>`。
- 只有前端 Nginx 映射公网端口；PostgreSQL 和 Redis 不开放公网端口。
- 默认 `AI_MODE=mock`；收到硅基流动 Key 并完成最小调用验证后再切换真实模式。

## 本机后端检查

```powershell
Set-Location -LiteralPath 'F:\尚硅谷大模型\项目实战\电商运营助手'
uv sync --project backend --frozen
uv run --project backend python -m compileall -q backend/app
```

## 同步并在 ECS 启动

先在本机执行 `pnpm --dir frontend build` 生成并验证 `frontend/dist`。前端镜像只将此静态产物装入 Nginx，避免 ECS 构建时访问 npm 仓库。代码提交到 GitHub 后，在 ECS 的独立目录拉取，在服务器中创建真实 `.env` 并执行 `chmod 600 .env`。随后运行：

```bash
cd /root/myproject/e_commerce_operations_copilot
./manage.sh config
./manage.sh start
./manage.sh status
curl -fsS http://127.0.0.1/api/health
```

以后发布新版本：

```bash
cd /root/myproject/e_commerce_operations_copilot
./manage.sh update
```

常用启停命令及安全注意事项见 [阿里云ECS环境配置与项目启停说明.md](./阿里云ECS环境配置与项目启停说明.md)。
