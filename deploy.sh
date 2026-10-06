#!/usr/bin/env bash
# ============================================================
# 榜单星球 · 一键部署脚本
#
# 用法：
#   ./deploy.sh            一键部署（构建 + 启动 + 自检）
#   ./deploy.sh update     拉取最新代码后重新部署
#   ./deploy.sh restart    重启服务
#   ./deploy.sh logs       查看实时日志
#   ./deploy.sh status     查看运行状态
#   ./deploy.sh stop       停止服务
#   ./deploy.sh down       停止并删除容器（保留数据）
#   ./deploy.sh backup     备份数据库
#   ./deploy.sh password   重新生成随机管理员密码
#   ./deploy.sh uninstall  停止并删除容器与镜像（保留数据）
# ============================================================
set -euo pipefail

# ------------------------- 路径与常量 -------------------------
cd "$(dirname "$0")"
ROOT_DIR="$(pwd)"
ENV_FILE="$ROOT_DIR/.env"
ENV_EXAMPLE="$ROOT_DIR/.env.example"
DATA_DIR="$ROOT_DIR/data"
COMPOSE="docker compose"

# ------------------------- 输出着色 -------------------------
if [ -t 1 ]; then
  R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;36m'; N='\033[0m'; BOLD='\033[1m'
else
  R=''; G=''; Y=''; B=''; N=''; BOLD=''
fi
info(){ printf "${B}[信息]${N} %s\n" "$*"; }
ok(){   printf "${G}[完成]${N} %s\n" "$*"; }
warn(){ printf "${Y}[注意]${N} %s\n" "$*"; }
err(){  printf "${R}[错误]${N} %s\n" "$*" >&2; }
step(){ printf "\n${BOLD}${B}▶ %s${N}\n" "$*"; }

# ------------------------- 工具检测 -------------------------
need_docker(){
  if ! command -v docker >/dev/null 2>&1; then
    err "未检测到 Docker。请先安装 Docker："
    echo "  官方一键安装脚本（Ubuntu/Debian/CentOS）："
    echo "    curl -fsSL https://get.docker.com | sh"
    echo "    systemctl enable --now docker"
    echo "  详见 docs/DEPLOY.md 第二步"
    exit 1
  fi
  if ! $COMPOSE version >/dev/null 2>&1; then
    err "未检测到 docker compose 插件（v2）。"
    echo "  Docker 20.10+ 一般自带；若缺失可在服务器上执行："
    echo "    curl -fsSL https://get.docker.com | sh"
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    err "无法连接 Docker 守护进程。可能原因："
    echo "  · 未启动服务：sudo systemctl start docker"
    echo "  · 当前用户无权限：sudo usermod -aG docker \$USER 后重新登录"
    exit 1
  fi
}

# ------------------------- 读取端口 -------------------------
get_port(){
  if [ -f "$ENV_FILE" ]; then
    grep -E '^PORT=' "$ENV_FILE" | head -1 | cut -d= -f2 | tr -d '[:space:]'
  fi
}
SERVER_IP(){
  # 尝试获取本机公网/内网地址，仅用于提示
  local ip
  ip=$(curl -fsS --max-time 3 https://api.ipify.org 2>/dev/null || true)
  [ -z "$ip" ] && ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  [ -z "$ip" ] && ip="<服务器IP>"
  echo "$ip"
}

# ------------------------- 生成 .env -------------------------
ensure_env(){
  if [ ! -f "$ENV_FILE" ]; then
    if [ ! -f "$ENV_EXAMPLE" ]; then
      err "缺少 .env.example，无法生成配置文件"
      exit 1
    fi
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    # 生成随机密码，避免默认弱密码上公网
    if command -v openssl >/dev/null 2>&1; then
      RAND_PWD="rp$(openssl rand -hex 6)"
    else
      RAND_PWD="rp$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 12)"
    fi
    if grep -q '^ADMIN_PASSWORD=' "$ENV_FILE"; then
      sed -i.bak "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${RAND_PWD}|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
    fi
    GENERATED_PWD="$RAND_PWD"
  fi
  mkdir -p "$DATA_DIR"
}

# ------------------------- 命令实现 -------------------------
cmd_deploy(){
  step "1/5 检查运行环境"
  need_docker; ok "Docker 环境正常（$(docker --version | cut -d, -f1)）"

  step "2/5 准备配置文件"
  ensure_env
  local port; port="$(get_port)"; port="${port:-8000}"
  if [ -n "${GENERATED_PWD:-}" ]; then
    warn "已自动生成 .env，并设置了随机管理员密码："
    printf "        ${BOLD}%s${N}\n" "$GENERATED_PWD"
    warn "请立即记录下来，登录后可在后台修改密码。"
  else
    info "配置文件 .env 已存在，沿用其中设置"
  fi
  ok "对外端口：${port}"

  step "3/5 构建镜像"
  $COMPOSE build

  step "4/5 启动服务"
  $COMPOSE up -d

  step "5/5 等待服务就绪"
  local i ready=0
  for i in $(seq 1 30); do
    if curl -fsS --max-time 2 "http://localhost:${port}/api/health" >/dev/null 2>&1; then
      ready=1; break
    fi
    printf "."; sleep 2
  done
  echo

  if [ "$ready" = "1" ]; then
    ok "服务已就绪 🎉"
  else
    warn "健康检查未在 60 秒内通过，请查看日志：./deploy.sh logs"
  fi

  local ip; ip="$(SERVER_IP)"
  printf "\n${BOLD}${G}================= 部署完成 =================${N}\n"
  printf "  小程序首页 ： ${B}http://%s:%s/${N}\n" "$ip" "$port"
  printf "  管理后台   ： ${B}http://%s:%s/admin${N}\n" "$ip" "$port"
  printf "  接口文档   ： ${B}http://%s:%s/docs${N}\n" "$ip" "$port"
  printf "\n"
  if [ -n "${GENERATED_PWD:-}" ]; then
    printf "  管理账号   ： admin / ${BOLD}%s${N}\n" "$GENERATED_PWD"
  else
    printf "  管理账号   ： 见 .env 中的 ADMIN_USER / ADMIN_PASSWORD\n"
  fi
  printf "\n  ${Y}※ 若浏览器打不开，请到云控制台「安全组」放行 %s 端口${N}\n" "$port"
  printf "${BOLD}${G}============================================${N}\n\n"
}

cmd_update(){
  step "更新部署"
  need_docker
  if [ -d "$ROOT_DIR/.git" ]; then
    info "拉取最新代码..."
    git pull --ff-only || warn "git pull 失败，跳过（将使用当前代码）"
  fi
  $COMPOSE up -d --build
  ok "更新完成"
  $COMPOSE ps
}

cmd_restart(){ need_docker; step "重启服务"; $COMPOSE restart; ok "已重启"; }
cmd_logs(){    need_docker; $COMPOSE logs -f --tail=100; }
cmd_status(){  need_docker; $COMPOSE ps; local p; p="$(get_port)"; p="${p:-8000}"
  echo; info "健康检查："; curl -fsS "http://localhost:${p}/api/health" && echo || warn "无法访问 /api/health" ; }
cmd_stop(){    need_docker; step "停止服务"; $COMPOSE stop; ok "已停止（数据保留）"; }
cmd_down(){    need_docker; step "停止并移除容器"; $COMPOSE down; ok "已移除（数据保留在 ./data）"; }
cmd_uninstall(){ need_docker; step "卸载"; $COMPOSE down --rmi local 2>/dev/null || $COMPOSE down
  ok "容器与本地镜像已移除，数据仍保留在 ./data"; }

cmd_backup(){
  step "备份数据库"
  local src="$DATA_DIR/rankplanet.db"
  if [ ! -f "$src" ]; then err "未找到数据库文件：$src"; exit 1; fi
  local dst="$ROOT_DIR/backup_rankplanet_$(date +%Y%m%d_%H%M%S).db"
  cp "$src" "$dst"
  ok "已备份到：$dst"
  ls -lh "$dst"
}

cmd_password(){
  step "重置管理员密码"
  ensure_env
  local newpwd
  if command -v openssl >/dev/null 2>&1; then
    newpwd="rp$(openssl rand -hex 6)"
  else
    newpwd="rp$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 12)"
  fi
  warn "重置密码需要清空数据库中的管理员账号，将删除现有管理员记录。"
  read -r -p "确认继续？(y/N) " ans
  if [ "${ans:-N}" != "y" ] && [ "${ans:-N}" != "Y" ]; then info "已取消"; return 0; fi

  sed -i.bak "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${newpwd}|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
  need_docker
  docker exec rankplanet python -c "
import sqlite3
c = sqlite3.connect('/app/data/rankplanet.db')
c.execute('DELETE FROM admins')
c.execute('DELETE FROM tokens')
c.commit(); c.close()
print('已清除原管理员')
" 2>/dev/null || warn "清除管理员失败（容器可能未运行）"
  $COMPOSE up -d --force-recreate >/dev/null
  ok "新密码：${BOLD}${newpwd}${N}（已写入 .env）"
}

cmd_help(){
  cat <<'HELP'
榜单星球 · 一键部署脚本

用法：
  ./deploy.sh            一键部署（构建 + 启动 + 自检）
  ./deploy.sh update     拉取最新代码后重新部署
  ./deploy.sh restart    重启服务
  ./deploy.sh logs       查看实时日志
  ./deploy.sh status     查看运行状态
  ./deploy.sh stop       停止服务
  ./deploy.sh down       停止并删除容器（保留数据）
  ./deploy.sh backup     备份数据库
  ./deploy.sh password   重新生成随机管理员密码
  ./deploy.sh uninstall  停止并删除容器与镜像（保留数据）
HELP
}

# ------------------------- 入口 -------------------------
case "${1:-deploy}" in
  deploy|"")  cmd_deploy ;;
  update)     cmd_update ;;
  restart)    cmd_restart ;;
  logs)       cmd_logs ;;
  status)     cmd_status ;;
  stop)       cmd_stop ;;
  down)       cmd_down ;;
  backup)     cmd_backup ;;
  password)   cmd_password ;;
  uninstall)  cmd_uninstall ;;
  help|-h|--help) cmd_help ;;
  *) err "未知命令：$1"; echo; cmd_help; exit 1 ;;
esac
