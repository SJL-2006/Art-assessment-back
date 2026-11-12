#!/bin/bash
# 自动部署脚本：git pull + migrate + collectstatic + restart gunicorn (systemd)
# 路径：/www/wwwroot/art-backend
# 服务：art-backend.service
# 用法：sudo bash deploy.sh

set -e

DEPLOY_DIR="/www/wwwroot/art-backend"
VENV_PY="/www/server/pyporject_evn/art-venv/bin/python3"
SERVICE_NAME="art-backend"
LOG_FILE="/var/log/art-deploy.log"

echo "====== $(date '+%Y-%m-%d %H:%M:%S') 部署开始 ======" | sudo tee -a "$LOG_FILE"

cd "$DEPLOY_DIR"

# 1. git pull（服务器首次已 git clone）
echo "[1/5] git pull origin main..."
sudo git fetch origin && sudo git reset --hard origin/main

# 2. pip install
echo "[2/5] pip install ..."
"$VENV_PY" -m pip install -r requirements.txt --quiet

# 3. migrate
echo "[3/5] migrate..."
"$VENV_PY" manage.py migrate --noinput

# 4. collectstatic
echo "[4/5] collectstatic..."
"$VENV_PY" manage.py collectstatic --noinput --clear

# 5. systemd 重启 gunicorn
echo "[5/5] systemctl restart $SERVICE_NAME ..."
sudo systemctl restart "$SERVICE_NAME"

sleep 3

# 验证
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/schema/)
  echo "✅ 部署成功 HTTP=$STATUS" | sudo tee -a "$LOG_FILE"
else
  echo "❌ $SERVICE_NAME 未启动，journalctl -u $SERVICE_NAME" | sudo tee -a "$LOG_FILE"
  sudo journalctl -u "$SERVICE_NAME" --no-pager -n 30
  exit 1
fi

echo "====== 部署结束 ======" | sudo tee -a "$LOG_FILE"
