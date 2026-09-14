#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

usage() {
  echo "用法: $0 {prepare|start|stop|pause|restart|status|logs|pull|build|migrate|backup|guard|doctor|update|config} [服务名]"
  echo "  prepare  创建运行目录并设置非 root 容器写权限"
  echo "  start    创建并启动全部容器"
  echo "  stop     停止并移除容器和网络，保留数据卷"
  echo "  pause    仅停止容器，保留容器本身"
  echo "  restart  重建并启动容器"
  echo "  status   查看容器状态"
  echo "  logs     查看日志，可追加服务名"
  echo "  pull     拉取 Compose 基础镜像"
  echo "  build    构建应用镜像"
  echo "  migrate  执行数据库迁移"
  echo "  backup   备份 PostgreSQL 到 backups 目录"
  echo "  guard    校验已批准架构基线和模块边界"
  echo "  doctor   检查配置、容器、迁移、健康与就绪状态"
  echo "  update   拉取 Git 代码、构建并重启"
  echo "  config   校验 Compose 配置"
}

cd "$PROJECT_DIR"
if [[ ! -f compose.yaml ]]; then
  echo "错误: $PROJECT_DIR 中没有 compose.yaml" >&2
  exit 1
fi

command="${1:-}"
service="${2:-}"
export APP_VERSION="${APP_VERSION:-$(git rev-parse --short HEAD 2>/dev/null || echo dev)}"

prepare_runtime() {
  install -d -m 0770 "$PROJECT_DIR/storage" "$PROJECT_DIR/backups"
  chown -R 10001:10001 "$PROJECT_DIR/storage" "$PROJECT_DIR/backups"
}

architecture_guard() {
  python3 "$PROJECT_DIR/scripts/check_architecture.py"
}

wait_http() {
  local url="$1"
  local attempts="${2:-15}"
  for ((index=1; index<=attempts; index++)); do
    if curl -fsS "$url"; then
      echo
      return 0
    fi
    sleep 2
  done
  echo "错误: $url 在等待窗口内未就绪" >&2
  return 1
}

case "$command" in
  prepare) prepare_runtime; echo "运行目录已准备" ;;
  start) architecture_guard; prepare_runtime; docker compose up -d --remove-orphans; docker compose ps ;;
  stop) docker compose down --remove-orphans ;;
  pause) docker compose stop ;;
  restart) architecture_guard; prepare_runtime; docker compose up -d --build --remove-orphans; docker compose up -d --force-recreate --no-deps frontend; docker compose ps ;;
  status) docker compose ps -a ;;
  logs)
    if [[ -n "$service" ]]; then docker compose logs --tail=200 -f "$service"
    else docker compose logs --tail=200 -f
    fi ;;
  pull) docker compose pull ;;
  build) architecture_guard; docker compose build ;;
  migrate) docker compose run --rm migrate ;;
  backup)
    prepare_runtime
    backup_file="backups/ecommerce_ops_$(date +%Y%m%d_%H%M%S).dump"
    docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_file"
    chown 10001:10001 "$backup_file"
    chmod 0600 "$backup_file"
    echo "数据库备份完成: $backup_file"
    ;;
  guard) architecture_guard ;;
  doctor)
    architecture_guard
    docker compose config -q
    docker compose ps
    docker compose run --rm migrate alembic current
    wait_http http://127.0.0.1/api/health
    wait_http http://127.0.0.1/api/ready
    ;;
  update)
    "$0" backup
    git pull --ff-only
    export APP_VERSION="$(git rev-parse --short HEAD 2>/dev/null || echo dev)"
    architecture_guard
    prepare_runtime
    docker compose up -d --build --remove-orphans
    docker compose up -d --force-recreate --no-deps frontend
    docker compose ps
    ;;
  config) docker compose config -q; echo "Compose 配置有效" ;;
  *) usage; exit 1 ;;
esac
