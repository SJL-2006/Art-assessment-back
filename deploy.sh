#!/bin/bash
# 自动部署脚本：git pull + migrate + collectstatic + restart gunicorn (systemd)
# 路径：/www/wwwroot/art-backend
# 服务：art-backend.service
# 用法：sudo bash deploy.sh

set -e

DEPLOY_DIR="/www/wwwroot/art-backend"
SERVICE_NAME="art-backend"
LOG_FILE="/var/log/art-deploy.log"

# 优先用项目内 venv；兼容宝塔 Python 项目管理器创建的虚拟环境
if [ -x "$DEPLOY_DIR/venv/bin/python3" ]; then
  VENV_PY="$DEPLOY_DIR/venv/bin/python3"
elif [ -x "/www/server/pyporject_evn/art-venv/bin/python3" ]; then
  VENV_PY="/www/server/pyporject_evn/art-venv/bin/python3"
else
  echo "❌ 找不到 Python 虚拟环境：$DEPLOY_DIR/venv 或 /www/server/pyporject_evn/art-venv"
  exit 1
fi

echo "====== $(date '+%Y-%m-%d %H:%M:%S') 部署开始 ======" | sudo tee -a "$LOG_FILE"

cd "$DEPLOY_DIR"

# 1. git pull（服务器首次已 git clone）
echo "[1/5] git pull origin main..."
sudo git fetch origin && sudo git reset --hard origin/main

# 2. pip install
echo "[2/5] pip install ..."
"$VENV_PY" -m pip install -r requirements.txt --quiet --no-cache-dir \
  -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. migrate
echo "[3/5] migrate..."
"$VENV_PY" manage.py migrate --noinput

# 4. collectstatic
echo "[4/5] collectstatic..."
"$VENV_PY" manage.py collectstatic --noinput --clear

# 媒体目录持久化，确保 gunicorn 运行用户可以写入
mkdir -p "$DEPLOY_DIR/media"
if id www >/dev/null 2>&1; then
  chown -R www:www "$DEPLOY_DIR/media"
fi

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
