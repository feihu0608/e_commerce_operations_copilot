#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"

echo "提示：deployment/manage.sh 是兼容入口，实际执行项目根目录 manage.sh。" >&2
exec "$PROJECT_DIR/manage.sh" "$@"
