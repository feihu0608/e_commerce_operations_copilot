#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

usage() {
  echo "用法: $0 {start|stop|pause|restart|status|logs|pull|build|update|config} [服务名]"
  echo "  start    创建并启动全部容器"
  echo "  stop     停止并移除容器和网络，保留数据卷"
  echo "  pause    仅停止容器，保留容器本身"
  echo "  restart  重建并启动容器"
  echo "  status   查看容器状态"
  echo "  logs     查看日志，可追加服务名"
  echo "  pull     拉取 Compose 基础镜像"
  echo "  build    构建应用镜像"
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

case "$command" in
  start) docker compose up -d --remove-orphans; docker compose ps ;;
  stop) docker compose down --remove-orphans ;;
  pause) docker compose stop ;;
  restart) docker compose up -d --build --remove-orphans; docker compose ps ;;
  status) docker compose ps -a ;;
  logs)
    if [[ -n "$service" ]]; then docker compose logs --tail=200 -f "$service"
    else docker compose logs --tail=200 -f
    fi ;;
  pull) docker compose pull ;;
  build) docker compose build ;;
  update)
    git pull --ff-only
    docker compose up -d --build --remove-orphans
    docker compose ps
    ;;
  config) docker compose config -q; echo "Compose 配置有效" ;;
  *) usage; exit 1 ;;
esac
