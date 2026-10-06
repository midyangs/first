#!/bin/sh
# ============================================================
# 容器入口脚本
# 作用：修正挂载卷权限后，以降权用户运行服务
#
# 背景：docker compose 把宿主机 ./data 挂载到 /app/data，
#       该目录属主通常是宿主机用户（root），而服务以
#       appuser(1000) 运行会因无写权限报错：
#       "attempt to write a readonly database"。
#       故先以 root 修正属主，再用 appuser 启动服务。
#
# 降权工具使用系统自带的 setpriv（util-linux 提供），
# 无需额外安装 gosu/su-exec。
#
# 端口说明：
#   容器内固定监听 8000（INTERNAL_PORT），
#   宿主机映射端口由 docker-compose 的 ${PORT} 控制，
#   二者职责分离，避免改 PORT 导致映射与监听不一致。
# ============================================================
set -e

DATA_DIR="${DATA_DIR:-/app/data}"
INTERNAL_PORT="${INTERNAL_PORT:-8000}"

mkdir -p "$DATA_DIR"

if [ "$(id -u)" = "0" ]; then
    # 修正数据目录属主（挂载卷可能属 root，导致容器内无法写入）
    chown -R appuser:appuser "$DATA_DIR" 2>/dev/null || true
    echo "[entrypoint] 已确保数据目录可写: $DATA_DIR"

    # 以 appuser 身份启动服务
    # --reuid/--regid 设定用户与组，--clear-groups 清理附加组
    exec setpriv --reuid=appuser --regid=appuser --clear-groups \
        python -m uvicorn main:app \
        --host 0.0.0.0 --port "$INTERNAL_PORT" --app-dir server
fi

exec python -m uvicorn main:app \
    --host 0.0.0.0 --port "$INTERNAL_PORT" --app-dir server
