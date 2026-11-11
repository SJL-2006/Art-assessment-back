#!/bin/bash
# 自动部署脚本：git pull + migrate + collectstatic + restart gunicorn
# 服务器上固定路径：/www/wwwroot/art-backend
# 用法：bash deploy.sh

set -e

DEPLOY_DIR="/www/wwwroot/art-backend"
VENV_PY="/www/server/pyporject_evn/art-venv/bin/python3"
GUNICORN_CONF="$DEPLOY_DIR/gunicorn_conf.py"
GUNICORN_CMD="$DEPLOY_DIR/config.wsgi:application"
LOG_FILE="/var/log/art-deploy.log"

echo "====== $(date '+%Y-%m-%d %H:%M:%S') 部署开始 ======" | sudo tee -a "$LOG_FILE"

cd "$DEPLOY_DIR"

# 1. git pull
echo "[1/5] git pull origin main..."
sudo git fetch origin
sudo git reset --hard origin/main

# 2. 安装新增依赖（如果 requirements.txt 变了）
echo "[2/5] pip install ..."
"$VENV_PY" -m pip install -r requirements.txt --quiet

# 3. 数据库迁移
echo "[3/5] migrate..."
"$VENV_PY" manage.py migrate --noinput

# 4. 收集静态文件
echo "[4/5] collectstatic..."
"$VENV_PY" manage.py collectstatic --noinput --clear

# 5. 重启 gunicorn（BT-Panel 项目管理器用的 daemon 模式）
echo "[5/5] restart gunicorn..."
sudo pkill -f "gunicorn.*config.wsgi:application" || true
sleep 2
sudo "$DEPLOY_DIR/../pyporject_evn/art-venv/bin/gunicorn" \
  -c "$GUNICORN_CONF" \
  "$GUNICORN_CMD" \
  --daemon

sleep 2

# 验证
if pgrep -f "gunicorn.*config.wsgi:application" > /dev/null; then
  echo "✅ 部署成功，gunicorn 运行中" | sudo tee -a "$LOG_FILE"
  curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/api/schema/ | sudo tee -a "$LOG_FILE"
else
  echo "❌ gunicorn 未启动，查看日志：journalctl -u gunicorn" | sudo tee -a "$LOG_FILE"
  exit 1
fi

echo "====== 部署结束 ======" | sudo tee -a "$LOG_FILE"
