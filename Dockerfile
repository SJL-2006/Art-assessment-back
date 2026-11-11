# ---- 构建阶段：编译依赖 ----
FROM python:3.11-slim AS builder

WORKDIR /build

# pip 换源加速
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- 运行阶段：最终镜像 ----
FROM python:3.11-slim

LABEL maintainer="art-assessment" \
      description="艺术测评系统后端"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# 安装系统依赖（PyMySQL 可选；media 文件服务不需要额外库）
RUN apt-get update && apt-get install -y --no-install-recommends \
        tini \
        ca-certificates \
        bash \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app

# 先复制依赖列表利用缓存；复制代码在后
COPY . /app/
RUN chmod +x /app/entrypoint.sh

# 创建 media 目录并赋权（容器内运行用户非 root 时用得到）
RUN mkdir -p media staticfiles \
    && groupadd -r django && useradd -r -g django django \
    && chown -R django:django /app

USER django

EXPOSE 8000

# 健康检查：每 30s 探一次 Django 应用是否能启动（不带 --deploy 避免 ALLOWED_HOSTS=* 报错）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python manage.py check || exit 1

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
CMD []
