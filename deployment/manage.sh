#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"

usage() {
  echo "用法: $0 {start|stop|pause|restart|status|logs|pull|config} [服务名]"
  echo "  start    创建并启动全部容器"
  echo "  stop     完全停止并移除应用容器和应用网络，保留数据卷"
  echo "  pause    仅停止容器，保留容器本身"
  echo "  restart  完全停止后重新启动"
  echo "  status   查看容器状态"
  echo "  logs     查看日志，可追加服务名"
  echo "  pull     拉取 compose 中声明的镜像"
  echo "  config   校验并展开 Compose 配置"
}

require_project() {
  if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "错误: 项目目录不存在: $PROJECT_DIR" >&2
    exit 1
  fi
  cd "$PROJECT_DIR"
  if [[ ! -f compose.yaml && ! -f compose.yml && ! -f docker-compose.yaml && ! -f docker-compose.yml ]]; then
    echo "错误: $PROJECT_DIR 中尚未放置 Compose 配置文件。" >&2
    exit 1
  fi
}

command="${1:-}"
service="${2:-}"

case "$command" in
  start)
    require_project
    docker compose up -d --remove-orphans
    docker compose ps
    ;;
  stop)
    require_project
    docker compose down --remove-orphans
    ;;
  pause)
    require_project
    docker compose stop
    ;;
  restart)
    require_project
    docker compose down --remove-orphans
    docker compose up -d --remove-orphans
    docker compose ps
    ;;
  status)
    require_project
    docker compose ps -a
    ;;
  logs)
    require_project
    if [[ -n "$service" ]]; then
      docker compose logs --tail=200 -f "$service"
    else
      docker compose logs --tail=200 -f
    fi
    ;;
  pull)
    require_project
    docker compose pull
    ;;
  config)
    require_project
    docker compose config
    ;;
  *)
    usage
    exit 1
    ;;
esac
