# 自动化部署指南

## 链路总览

```
git push main → GitHub Actions → 构建镜像 → 推到 GHCR
                                     → SSH 到服务器 → docker compose pull & up → 健康检查
```

MySQL 用你现有的阿里云 RDS（`art_assessment`），不放在服务器上。

---

## 一、服务器初始化（只做一次）

### 1. 安装 Docker & Docker Compose

```bash
# Ubuntu
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 重新登录生效

# 验证
docker --version
docker compose version
```

### 2. 创建部署目录 & 环境变量

```bash
sudo mkdir -p /opt/art-backend/media /opt/art-backend/staticfiles /opt/art-backend/deploy
sudo chown -R $USER:$USER /opt/art-backend
cd /opt/art-backend
```

### 3. 把仓库的关键文件传到服务器（第一次）

本地执行（或手动上传）：

```bash
# 本地 Windows PowerShell
scp -r backend/Dockerfile backend/docker-compose.prod.yml backend/entrypoint.sh backend/.dockerignore backend/deploy <user>@<服务器IP>:/opt/art-backend/
```

或者直接 `git clone` 后拷贝出来：

```bash
# 服务器上
git clone https://github.com/SJL-2006/Art-assessment-back.git /tmp/art-back
cp /tmp/art-back/backend/Dockerfile /opt/art-backend/
cp /tmp/art-back/backend/docker-compose.prod.yml /opt/art-backend/
cp /tmp/art-back/backend/entrypoint.sh /opt/art-backend/
cp /tmp/art-back/backend/.dockerignore /opt/art-backend/
cp -r /tmp/art-back/backend/deploy /opt/art-backend/
cp /tmp/art-back/backend/requirements.txt /opt/art-backend/
```

### 4. 写 `.env`（**不要提交到 git**）

```bash
cat > /opt/art-backend/.env << 'EOF'
# Django
DJANGO_SECRET_KEY=替换成生产用的随机密钥（python -c "import secrets; print(secrets.token_urlsafe(50))"）
DJANGO_ALLOWED_HOSTS=你的域名,服务器IP

# MySQL（用阿里云 RDS 或自建）
DB_NAME=art_assessment
DB_USER=root
DB_PASSWORD=你的MySQL密码
DB_HOST=rm-xxx.mysql.rds.aliyuncs.com
DB_PORT=3306

# CORS
CORS_ALLOWED_ORIGINS=https://你的前端域名,http://服务器IP:3000

# DeepSeek（可选）
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_MODEL=deepseek-chat
EOF
```

### 5. 第一次手动部署

```bash
cd /opt/art-backend

# 登录 GHCR（用 GitHub PAT）
echo ghp_xxx | docker login ghcr.io -u <你的GitHub用户名> --password-stdin

# 拉取镜像并启动
docker compose -f docker-compose.prod.yml up -d

# 看日志
docker compose -f docker-compose.prod.yml logs -f backend

# 验证
curl http://服务器IP/api/schema/
```

此时服务器已经就绪，之后就不再需要手动操作了。

---

## 二、配置 GitHub Secrets（在仓库 Settings → Secrets and variables → Actions）

需要添加以下 **Repository Secrets**：

| Secret 名 | 值 | 说明 |
| --- | --- | --- |
| `SSH_HOST` | 服务器公网 IP 或域名 | `1.2.3.4` 或 `server.example.com` |
| `SSH_USER` | SSH 登录用户 | 如 `ubuntu`、`root`、`deploy` |
| `SSH_PRIVATE_KEY` | SSH 私钥内容 | 见下方生成 |
| `SSH_PORT`（可选） | SSH 端口 | 默认 22 |
| `DEPLOY_PATH` | 服务器上的部署目录 | 如 `/opt/art-backend` |

### 生成 SSH 密钥对

```bash
# 本地执行，生成一对 GitHub Actions 专用的密钥（不要用你平时的私钥）
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/art_deploy_key -N ""

# 公钥加到服务器
cat ~/.ssh/art_deploy_key.pub
# 复制输出，在服务器上执行：
#   echo '<公钥内容>' >> ~/.ssh/authorized_keys
#   chmod 600 ~/.ssh/authorized_keys

# 私钥内容粘贴到 GitHub Secret SSH_PRIVATE_KEY
cat ~/.ssh/art_deploy_key
```

---

## 三、日常使用

```bash
git push origin main
# → 等 GitHub Actions 跑完（2-3 分钟）
# → 服务器自动 docker compose pull & up，零停机滚动更新
```

### 查看部署日志

在 GitHub 仓库页面 → Actions → `Deploy to Production`，每次提交都会有一条新 Run，点开能看每一步的实时输出。

### 回滚

最坏情况：新版本有 bug，需要回滚。

```bash
# 服务器上
cd /opt/art-backend

# 查看历史镜像 tag（每 commit SHA 一条）
docker images ghcr.io/sjl-2006/art-assessment-back

# 手动回滚到某个 tag
echo 'IMAGE_TAG=ghcr.io/sjl-2006/art-assessment-back:sha-abc123' >> .env
docker compose -f docker-compose.prod.yml up -d
```

更简单的方式：在 GitHub Actions 的 Run 页面点 **Re-run jobs**，直接回滚到上一次成功的 commit。

---

## 四、常见问题

**Q: GitHub Actions 报错 `Permission denied (publickey)`**
A: 公钥没加到服务器的 `authorized_keys`，或 `SSH_PRIVATE_KEY` Secret 没贴对（注意末尾不要多一个换行）。

**Q: 容器启动后 `DB_HOST` 连不上 MySQL**
A: RDS 需要把服务器公网 IP 加到白名单；或服务器和 RDS 在同一 VPC 用内网地址。

**Q: Nginx 报 403 Forbidden on /media/**
A: media volume 权限问题。服务器上执行 `chmod -R 755 /opt/art-backend/media`。

**Q: 服务器上空间不够**
A: 定期清理旧镜像：`docker image prune -af`，或在 crontab 里跑。

**Q: 想跳过某次 push 的部署**
A: commit message 里加 `[skip deploy]`，workflow 里暂时没加这个判断，后续可加：
```yaml
if: "!contains(github.event.head_commit.message, '[skip deploy]')"
```
