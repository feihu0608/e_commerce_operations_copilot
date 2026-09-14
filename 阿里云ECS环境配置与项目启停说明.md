# 阿里云 ECS 环境配置与项目启停说明

配置日期：2026 年 9 月 12 日  
应用部署更新：2026 年 9 月 14 日  
项目：电商运营助手  
服务器公网地址：`<ECS_PUBLIC_IP>`  
SSH：`root@<ECS_PUBLIC_IP>:22`  
服务器项目目录：`/root/myproject/e_commerce_operations_copilot`

> 本文不保存服务器密码、模型密钥或数据库密码。连接时请输入当前服务器密码。由于 root 密码曾通过聊天发送，完成部署验证后应更换密码，并逐步改用 SSH 密钥登录。

## 1 当前状态

服务器基础环境与电商运营助手容器已经配置并实际验证。项目使用 GitHub 仓库管理，工作目录为 `/root/myproject/e_commerce_operations_copilot`。PostgreSQL、Redis、Alembic Migrator、FastAPI、Outbox Dispatcher、Celery Worker 和前端 Nginx 均由该目录的 Compose 配置管理。

服务器内部及公网均已验证首页返回 HTTP 200，`/api/health` 返回数据库正常，`/api/ready` 同时验证 PostgreSQL 与 Redis。文本、图片和视频均配置为 `live`；已完成真实诊断、真实图片持久化和真实 MP4 播放验证。Git 仓库中的文档使用 `<ECS_PUBLIC_IP>` 占位，真实地址不提交到公开仓库。

GitHub `main` 与 ECS `origin/main` 已对齐，服务器工作区干净。

已验证的服务器资源：

| 项目 | 当前值 |
| --- | --- |
| 操作系统 | Ubuntu 22.04.5 LTS x86_64 |
| CPU | 2 核 |
| 内存 | 约 3.5 GiB 可用总量 |
| 系统盘 | 40 GB，配置时已使用约 3.6 GB |
| Swap | 2 GiB，已启用并设置开机挂载 |
| 时区 | Asia/Shanghai |
| 公网入口 | Nginx 监听 80；阿里云安全组已放行 80/TCP；公网访问已验证 |

### 1.1 已运行的应用容器

| Compose 服务 | 镜像/组件 | 当前用途与验证 |
| --- | --- | --- |
| `postgres` | PostgreSQL 16 Alpine | 业务数据、任务状态和初始化演示数据；健康检查通过；按需映射主机 5432 供开发机连接 |
| `redis` | Redis 7 Alpine | Celery Broker 与 Result Backend；`PING` 返回 `PONG` |
| `backend` | Python 3.12、FastAPI、Uvicorn、SQLAlchemy、psycopg | `/api/health` 与登录接口通过，容器健康 |
| `worker` | Celery 5.5，单 Worker 并发 1 | 已完成一次商品诊断异步任务并写回 PostgreSQL |
| `dispatcher` | Transactional Outbox Dispatcher | 扫描数据库 Outbox、退避重试投递并恢复过期视频轮询 |
| `migrate` | Alembic | 一次性迁移服务；成功退出后 API、Worker、Dispatcher 才启动 |
| `frontend` | Nginx 1.27 Alpine、React 静态产物 | 服务器内部首页返回 HTTP 200，映射主机 80 端口 |

后端镜像通过固定版本的 `uv` 和 `backend/uv.lock` 安装锁定依赖。前端先在本机执行 `pnpm build`，再将 `frontend/dist` 装入 Nginx 镜像，避免 ECS 构建期间依赖 npm 官方仓库连接。

## 2 软件与配置记录

### 2.1 已预装并确认可用

| 软件 | 版本或状态 | 用途 |
| --- | --- | --- |
| Docker Engine | 29.8.0 | 运行项目容器 |
| Docker Compose | 5.5.1 | 编排前端、API、数据库、Redis 和 Worker |
| Git | 2.34.1 | 拉取或管理代码 |
| curl | 7.81.0 | 健康检查和接口测试 |
| jq | 已安装 | 查看与处理 JSON |
| rsync | 已安装 | 增量上传项目文件 |
| CA certificates | 已安装并为当前软件源最新版本 | HTTPS 证书校验 |

### 2.2 本次新增

安装了 `unzip`，用于解压部署包。执行过 `apt-get update` 以刷新软件包索引，但没有执行系统全量升级，避免在项目部署前引入内核或服务重启。配置时系统仍提示存在 56 个可升级软件包，可在后续维护窗口处理。

### 2.3 Swap

创建了 `/swapfile`：

- 容量：2 GiB。
- 权限：仅 root 可读写。
- `/etc/fstab` 已配置开机自动挂载。
- `vm.swappiness=10`，配置文件为 `/etc/sysctl.d/99-myproject.conf`。

Swap 用于缓解 4 GiB 实例在构建镜像、启动 PostgreSQL 或执行异步任务时的瞬时内存压力。Swap 不能替代内存；如果持续大量使用，应减少容器并发或升级实例。

### 2.4 Docker

Docker 服务已设为开机启动并处于运行状态。服务器原有的镜像加速地址全部保留，额外加入了以下日志限制：

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

实际配置文件：`/etc/docker/daemon.json`。  
修改前备份：`/etc/docker/daemon.json.pre-myproject-20260912`。  
项目目录中留有本次策略副本：`/root/myproject/e_commerce_operations_copilot/deployment/docker-daemon-log-policy.json`。

配置合并后已经通过 `dockerd --validate`，Docker 服务重启成功，并通过 `docker run --rm hello-world` 完成镜像拉取和容器运行验证。

### 2.5 防火墙

Ubuntu UFW 已启用并设置开机启动，只增加了以下入站规则：

| 端口 | 用途 |
| --- | --- |
| 22/TCP | SSH 管理 |
| 80/TCP | HTTP 访问，由 Nginx 提供 |
| 443/TCP | HTTPS 访问，由 Nginx 提供 |
| 5432/TCP | PostgreSQL 开发机直连；仅临时开放并限制来源 IP |

Redis 的 `6379` 以及对象存储管理端口没有开放公网。PostgreSQL 的 `5432` 已按开发调试需要映射到 ECS 主机；必须在阿里云安全组中把 5432 的来源限制为开发机公网 IP，禁止长期对 `0.0.0.0/0` 开放。

UFW 只负责服务器内部防火墙。还需要在阿里云 ECS 控制台的安全组中允许：

- 22/TCP：建议来源限制为自己的固定公网 IP；调试阶段至少避免长期对全网开放。
- 80/TCP：应用需要 HTTP 访问时开放。
- 443/TCP：配置域名和 HTTPS 后开放。
- 5432/TCP：仅开发机直连 PostgreSQL 时开放，来源必须限制为开发机公网 IP；不用时立即删除规则。

本机已在 UFW 启用后再次测试公网 SSH，`<ECS_PUBLIC_IP>:22` 连接成功。

## 3 服务器目录

已经创建：

```text
/root/myproject/
└── e_commerce_operations_copilot/   本项目 Git 仓库
    ├── manage.sh
    ├── compose.yaml
    ├── .env
    ├── backend/
    ├── frontend/
    ├── database/
    ├── deployment/
    ├── backups/
    └── storage/
```

父目录 `/root/myproject` 只用于容纳多个独立项目，不直接堆放本项目代码。旧的散放文件已移动到 `/root/myproject/_legacy_ecommerce_root_20260914`，权限为 `700`，作为短期可恢复归档；确认新目录长期稳定并完成独立备份后再删除。

项目仓库内部结构：

```text
/root/myproject/e_commerce_operations_copilot/
├── manage.sh          项目管理脚本
├── deployment/        部署配置与配置备份
├── backups/           应用数据备份
├── logs/              需要落盘的应用日志
└── storage/           开发演示阶段的本地素材存储
```

以上目录权限为 `root:root`，普通用户不能访问。代码上传后，推荐形成以下结构：

```text
/root/myproject/e_commerce_operations_copilot/
├── compose.yaml
├── .env
├── .env.example
├── backend/
├── frontend/
├── manage.sh
├── deployment/
├── backups/
├── logs/
└── storage/
```

`.env` 中保存数据库密码和模型服务密钥，上传后执行：

```bash
chmod 600 /root/myproject/e_commerce_operations_copilot/.env
```

不要把真实 `.env` 提交到 Git，也不要在终端截图、日志或本文中记录密钥。

## 4 连接服务器

在本机 PowerShell 中执行：

```powershell
ssh -p 22 root@<ECS_PUBLIC_IP>
```

输入密码时终端不会显示字符，这是正常现象。登录后进入项目目录：

```bash
cd /root/myproject/e_commerce_operations_copilot
```

## 5 上传项目

### 5.0 开发与测试边界

- 本机：编辑代码，使用 `uv` 管理后端环境并执行静态检查、编译检查和不依赖数据库的单元测试。
- 阿里云 ECS：使用 Docker Compose 运行 PostgreSQL、Redis、FastAPI、Celery Worker 和前端 Nginx，并承担完整集成测试。
- 本机不需要 Docker Desktop，也不在 Windows 上单独安装 PostgreSQL、Redis 或运行 Celery Worker。
- 所谓“本地测试完整链路”，是指在本机浏览器或 API 客户端访问 ECS 上的容器环境；数据库和 Redis 仍只在 ECS 内网中提供服务。

本机首次准备后端 uv 环境：

```powershell
Set-Location -LiteralPath 'F:\尚硅谷大模型\项目实战\电商运营助手\backend'
$env:UV_CACHE_DIR = '..\.deployment-state\uv-cache'
uv sync --frozen
uv run python -m compileall -q app migrations
uv run pytest -q
```

`uv.lock` 已存在时应使用 `--frozen` 保证安装内容与锁文件一致。新增或升级依赖后，先在 `backend/pyproject.toml` 中修改依赖并运行 `uv lock --project backend`，验证后提交新的 `uv.lock`。

### 5.1 第一次上传

当前代码已经推送到 GitHub。服务器使用项目专用 Deploy Key 克隆，后续也通过该密钥拉取。首次部署等价命令为：

```bash
cd /root/myproject
GIT_SSH_COMMAND="ssh -i /root/.ssh/github_ecommerce_ed25519 -o IdentitiesOnly=yes" \
  git clone git@github.com:feihu0608/e_commerce_operations_copilot.git \
  /root/myproject/e_commerce_operations_copilot
```

如果项目包含 `node_modules`、`.venv`、缓存、测试截图或大量本地素材，先排除这些内容，避免上传依赖和无关文件。生产部署需要上传源码、Dockerfile、`compose.yaml`、迁移文件和必要配置模板。

当前本地目录已经包含后端、前端、数据库初始化 SQL 和 `compose.yaml`。首次上传时仍应先执行代码检查和 Compose 配置检查；应用是否可用以 ECS 上实际构建、健康检查和完整业务冒烟测试为准。

### 5.2 后续更新

日常更新按以下顺序进行：

```powershell
# 本机项目目录中
git add -A
git commit -m "说明本次改动"
git push origin main
```

然后登录 ECS：

```bash
cd /root/myproject/e_commerce_operations_copilot
./manage.sh update
```

`update` 会先创建 PostgreSQL 格式化备份，再执行 `git pull --ff-only`、构建、Alembic 迁移和 Compose 重启。更新后执行 `./manage.sh doctor`。不要直接在 ECS 修改受 Git 管理的源码，否则后续拉取会因工作区冲突停止。

## 6 管理脚本

服务器已经安装：

```text
/root/myproject/e_commerce_operations_copilot/manage.sh
```

仓库根目录包含唯一实现的 `manage.sh`；`deployment/manage.sh` 只是兼容入口并转发到根脚本，避免两份运维逻辑漂移。

### 6.1 首次启动

上传代码并创建 `.env` 后执行：

```bash
cd /root/myproject/e_commerce_operations_copilot
./manage.sh config
./manage.sh pull
./manage.sh prepare
./manage.sh start
./manage.sh doctor
```

面向当前公网演示服务器，`.env` 中应设置 `APP_PORT=80`。后端镜像会在构建阶段复制固定版本的 `uv`，并执行 `uv sync --frozen --no-dev --no-install-project`，因此 ECS 宿主机无需额外安装 Python、pip 或 uv。

`config` 会展开并检查 Compose 配置。确认没有缺失环境变量后再执行 `start`。

### 6.2 查看状态

```bash
cd /root/myproject/e_commerce_operations_copilot
./manage.sh status
```

预期所有必要服务为 `running` 或 `healthy`。只有容器处于运行状态不代表应用可用，还应检查 HTTP：

```bash
curl -I http://127.0.0.1/
curl -fsS http://127.0.0.1/api/health
curl -fsS http://127.0.0.1/api/ready
```

`/api/health` 用于存活检查；`/api/ready` 验证 PostgreSQL 和 Redis，Compose 容器健康检查使用就绪接口。

### 6.3 查看日志

查看全部服务最近 200 行并持续跟踪：

```bash
cd /root/myproject/e_commerce_operations_copilot
./manage.sh logs
```

只查看一个服务，例如 API：

```bash
./manage.sh logs backend
```

按 `Ctrl+C` 退出日志查看，不会停止容器。

### 6.4 重启项目

```bash
cd /root/myproject/e_commerce_operations_copilot
./manage.sh restart
```

脚本会基于当前代码重新构建并启动需要更新的容器；PostgreSQL、Redis 命名数据卷和仓库 `storage` 目录不会删除。

数据库迁移、备份和一键诊断：

```bash
./manage.sh migrate
./manage.sh backup
./manage.sh doctor
```

备份文件写入项目 `backups` 目录。破坏性迁移不做自动 downgrade；回滚前应先停止写入，并从升级前备份恢复到经过验证的新实例或维护窗口。

### 6.5 完全关闭项目

```bash
cd /root/myproject/e_commerce_operations_copilot
./manage.sh stop
```

`stop` 实际执行 `docker compose down --remove-orphans`，会停止并移除项目容器及应用网络，但保留命名数据卷和仓库 `storage` 中的数据。脚本没有使用 `-v`，因此不会删除数据库卷。

如果只是短暂停止并保留现有容器：

```bash
./manage.sh pause
```

再次启动仍使用：

```bash
./manage.sh start
```

停止应用不等于停止 ECS 计费。需要节省免费试用额度时，在确认数据已落盘、应用已关闭后，再到阿里云控制台停止 ECS 实例，并留意页面显示的停机收费规则。

### 6.6 公网访问

浏览器直接打开：

```text
http://<ECS_PUBLIC_IP>
```

健康检查地址：

```text
http://<ECS_PUBLIC_IP>/api/health
```

当前仅启用 HTTP。未配置域名和 TLS 证书前不要使用 `https://<ECS_PUBLIC_IP>`。如果 ECS 重新分配公网 IP，应更新私有部署记录，不要把真实地址提交到公开仓库。

### 6.7 AI 模式

当前服务器 `.env` 中的有效模式为：

```env
AI_MODE=live
MEDIA_MODE=live
TEXT_MODEL=Qwen/Qwen3.6-27B
```

硅基流动密钥只保存在服务器项目目录的 `.env` 中，权限为 `600`。文本、图片和视频均已完成真实调用；视频使用 submit/poll 短任务并保存供应商任务标识。每次真实图片或视频生成都会产生费用。

登录页支持注册普通运营账号。内置 `operator`、`manager` 账号的密码不写入代码、文档或 Git；如需重新设置，应通过安全的服务器维护流程更新数据库密码哈希，并把新值仅保存在受限的私有密码管理位置。

### 6.8 从本机连接 PostgreSQL

Compose 将 ECS 主机的 `5432` 映射到 PostgreSQL 容器。连接参数中的用户名、数据库名和密码保存在服务器私有 `.env` 中，可登录 ECS 后查看：

```bash
cd /root/myproject/e_commerce_operations_copilot
grep -E '^(POSTGRES_DB|POSTGRES_USER|POSTGRES_PASSWORD)=' .env
```

本机数据库工具的参数：

```text
Host: <ECS_PUBLIC_IP>
Port: 5432
Database: 以上命令显示的 POSTGRES_DB
Username: 以上命令显示的 POSTGRES_USER
Password: 以上命令显示的 POSTGRES_PASSWORD
SSL mode: prefer（当前未单独配置数据库 TLS）
```

验证结束后如果不再需要直连，应从阿里云安全组删除 5432 规则，并删除 Compose 中的 `postgres.ports` 映射后重新部署。更安全的长期方案是保持 5432 不公开，通过 SSH 隧道连接。

## 7 2 核 4 GiB 部署约束

建议只运行以下核心容器：

- Nginx 或前端静态站点。
- FastAPI API。
- PostgreSQL。
- Redis。
- 一个 AI 或媒体异步 Worker，初始并发为 1。
- 一个轻量 Outbox Dispatcher；迁移容器只在发布阶段短暂运行。

图片和视频调用外部服务，不在 ECS 上部署本地大模型或本地视频生成模型。演示阶段不必同时运行 MinIO；少量素材可以放 `/root/myproject/e_commerce_operations_copilot/storage`，正式使用时再接阿里云 OSS。

Compose 中建议设置容器内存上限，避免某个 Worker 占满服务器。初始参考值如下，最终以项目实测为准：

| 服务 | 初始内存上限参考 |
| --- | ---: |
| PostgreSQL | 768 MiB |
| Redis | 192 MiB |
| FastAPI | 512 MiB |
| 异步 Worker | 768 MiB |
| 前端与 Nginx | 128 MiB |

构建镜像时不要同时执行多个前后端构建任务。若部署期间经常发生 Swap 大量增长或 OOM，应先降低 Worker 并发，再考虑将数据库迁往托管服务或升级 ECS。

## 8 推荐的 Compose 安全边界

编写 `compose.yaml` 时遵守以下规则：

- Nginx 映射主机的 `80:80` 和后续的 `443:443`；开发期 PostgreSQL 可按需映射 `5432:5432`。
- FastAPI 可以只使用 `expose`，由 Nginx 通过内部网络转发。
- Redis 不配置公网 `ports`；PostgreSQL 仅在开发期按需映射 5432，并由安全组限制来源 IP。
- 数据库和 Redis 使用命名卷或明确的持久化挂载。
- 每个服务配置健康检查、日志限制和重启策略。
- API、Worker、Dispatcher 和迁移容器使用 UID 10001 非 root 账户，并启用 `no-new-privileges`；`manage.sh prepare` 负责存储目录权限。
- 密码和模型密钥从 `.env` 或专用 Secret 注入，不写入镜像。
- Worker 初始并发设为 1；图片和视频任务可以分队列，但轻量演示不必启动多个 Worker 进程。

阿里云安全组、UFW 和 Compose 端口映射共同决定公网暴露面；其中任意一层开放数据库端口都会增加风险。

## 9 日常检查与维护

查看服务器资源：

```bash
free -h
swapon --show
df -h /
docker stats --no-stream
```

查看 Docker 磁盘使用：

```bash
docker system df
```

不要直接运行带 `-a` 的镜像清理或删除数据卷命令，除非已经确认目标和备份。数据库备份应写入 `/root/myproject/e_commerce_operations_copilot/backups`，并定期下载到本地或 OSS；只放在同一系统盘不算可靠备份。

计划安装安全更新时：

```bash
apt list --upgradable
apt-get upgrade
```

更新前先备份和停止应用，并预留可能重启服务器的维护时间。

## 10 账户安全后续操作

当前可以继续使用 root 密码登录，但建议部署验证完成后执行：

1. 在本机生成 SSH 密钥。
2. 将公钥加入服务器 `/root/.ssh/authorized_keys`。
3. 新开一个终端验证密钥可以登录，保持旧会话不要关闭。
4. 更换已经分享过的 root 密码。
5. 确认密钥登录稳定后，再评估是否关闭 SSH 密码登录。

更换密码使用：

```bash
passwd
```

不要在本文或聊天中发送新密码。关闭密码登录前必须先验证密钥登录，否则可能失去服务器访问能力。

## 11 本次未执行的事项

- 尚未配置域名、HTTPS 证书和阿里云 OSS；当前使用公网 IP 的 HTTP 演示入口。
- 未安装本地 Python、Node.js、PostgreSQL、Redis 或 Nginx；后续统一由 Docker 镜像提供，避免宿主机版本冲突。
- Redis 和应用管理端口未开放；PostgreSQL 5432 因本机开发连接需求暂时映射，只应在阿里云安全组中允许固定开发机 IP。
- 未配置域名、HTTPS 证书和阿里云 OSS。
- 未执行 56 个系统软件包的全量升级。
- 已添加 GitHub 项目专用 Deploy Key，并允许该仓库读写；ECS 仓库已经配置为使用 `/root/.ssh/github_ecommerce_ed25519`。尚未更换已经暴露过的 root 密码，也尚未关闭 SSH 密码登录。

阿里云安全组已经放行 HTTP 80。截图中还包含 MySQL 3306、Oracle 1521、SQL Server 1433、Redis 6379 和 RDP 3389 等本项目不需要的公网规则，应删除。PostgreSQL 5432 在本次本机开发期间保留，但来源必须限制为开发机公网 IP；不再直连后立即删除。长期只保留 SSH 22、HTTP 80 以及后续真正启用 HTTPS 时的 443。

这些事项应在应用代码、域名及实际外部服务确定后继续配置。
