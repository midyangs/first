# ============================================================
# 榜单星球 · 生产环境镜像
# 构建： docker build -t rankplanet .
# 运行： docker run -d -p 8000:8000 -v ./data:/app/data rankplanet
# ============================================================
FROM python:3.11-slim

# 环境变量：Python 不缓冲输出（便于 docker logs 实时查看）
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    PORT=8000

WORKDIR /app

# 先装依赖（利用 Docker 层缓存，代码改动不会重装依赖）
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 再拷贝代码
COPY server/ ./server/
COPY src/ ./src/

# 创建非 root 用户与数据目录（安全加固）
# 降权工具使用系统自带的 setpriv（util-linux），无需额外安装
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app \
    && chmod +x /app/server/entrypoint.sh

EXPOSE 8000

# 容器健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

# 入口脚本会先修正挂载卷权限，再降权为 appuser 启动服务
ENTRYPOINT ["/app/server/entrypoint.sh"]
