#!/usr/bin/env bash
# 艺术测评系统 - 测评限时自动提交（cron 周期调用）
# 依赖：python 在 PATH 中；日志追加到 backend/auto_submit_exams.log
set -euo pipefail
cd "$(dirname "$0")/.."
python manage.py auto_submit_exams >> auto_submit_exams.log 2>&1
