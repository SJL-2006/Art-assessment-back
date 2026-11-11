#!/usr/bin/env bash
# 容器启动入口：先迁移 & 收集静态文件，再 exec gunicorn。
# 生产环境强烈建议 DB 迁移在部署脚本中单独执行一次，避免多容器并发迁移冲突。
# 本脚本的 migrate 仅作为兜底，部署前已执行时可加 SKIP_MIGRATE=1 跳过。

set -euo pipefail

cd /app

if [[ "${SKIP_MIGRATE:-0}" != "1" ]]; then
  echo "[entrypoint] 执行数据库迁移..."
  python manage.py migrate --noinput
fi

echo "[entrypoint] 收集静态文件..."
python manage.py collectstatic --noinput 2>/dev/null || true

echo "[entrypoint] 启动 gunicorn..."
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-4}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
