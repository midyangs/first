# 一键部署手册

把本项目部署到云服务器，全程只需**一条命令**。本手册面向没有运维经验的用户，照着做即可。

---

## 零、准备工作

### 服务器配置建议

| 项目 | 建议 |
|---|---|
| 系统 | Ubuntu 22.04 LTS（最省心） |
| 配置 | 1 核 2G 起步（本项目很轻量，2G 足够） |
| 带宽 | 1-3 Mbps 即可 |
| 磁盘 | 20GB 以上 |

常见云厂商：阿里云、腾讯云、华为云、京东云等，新用户通常有较大优惠。购买时选 **Ubuntu 22.04** 系统镜像。

> 如果暂时不想买服务器，可以先跳过，在**本地电脑**上用同样的步骤跑起来验证。

---

## 一、连接服务器

购买后会拿到 **公网 IP** 和 **登录密码**（或密钥文件）。用 SSH 连接：

```bash
# Windows：可用 PowerShell、Xshell、FinalShell
# macOS / Linux：直接用终端
ssh root@你的服务器IP
```

首次连接问 `Are you sure you want to continue connecting?` 输入 `yes`，然后输入密码。

---

## 二、安装 Docker（一条命令）

在服务器上执行：

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
```

验证安装成功：

```bash
docker --version
# 应输出类似：Docker version 27.x.x, build xxxxx
```

> **国内服务器网络慢**的话，可先配置镜像加速，再执行上面的安装命令。或在安装后编辑 `/etc/docker/daemon.json`：
> ```json
> { "registry-mirrors": ["https://docker.m.daocloud.io"] }
> ```
> 然后 `systemctl restart docker`。

---

## 三、上传项目

### 方式 A：从 Git 仓库克隆（推荐）

```bash
cd /opt
git clone <你的仓库地址> rankplanet
cd rankplanet
```

### 方式 B：本地打包上传

在**本地电脑**项目目录下打包（排除数据与缓存）：

```bash
tar --exclude='./data' --exclude='./.git' --exclude='__pycache__' \
    -czf rankplanet.tar.gz .
```

上传到服务器：

```bash
scp rankplanet.tar.gz root@你的服务器IP:/opt/
```

在服务器上解压：

```bash
mkdir -p /opt/rankplanet && cd /opt/rankplanet
tar -xzf /opt/rankplanet.tar.gz
```

---

## 四、一键部署

```bash
cd /opt/rankplanet
chmod +x deploy.sh
./deploy.sh
```

脚本会自动完成：

1. 检查 Docker 环境
2. 首次运行生成 `.env` 配置，并**自动生成随机管理员密码**
3. 构建镜像
4. 启动容器
5. 健康检查，等待服务就绪
6. 打印访问地址与管理员密码

看到如下输出即成功：

```
================= 部署完成 =================
  小程序首页 ： http://1.2.3.4:8000/
  管理后台   ： http://1.2.3.4:8000/admin
  接口文档   ： http://1.2.3.4:8000/docs

  管理账号   ： admin / rp1a2b3c4d5e6
============================================
```

> ⚠️ **请立即记下这个随机密码**，登录后可在后台「账号设置」中修改。

---

## 五、放行端口（最容易漏的一步！）

如果浏览器打不开，**九成是云服务器安全组没放行端口**。步骤如下：

1. 登录云厂商控制台
2. 找到你的服务器实例 → **安全组 / 防火墙** 设置
3. 添加**入方向**规则：
   - 协议：`TCP`
   - 端口：`8000`（或你在 `.env` 里自定义的 `PORT`）
   - 来源：`0.0.0.0/0`（允许所有 IP 访问）
4. 保存

部分系统（如 CentOS、部分 Ubuntu 镜像）还开了 `ufw`/`firewalld`，一并放行：

```bash
# Ubuntu (ufw)
ufw allow 8000/tcp

# CentOS (firewalld)
firewall-cmd --permanent --add-port=8000/tcp && firewall-cmd --reload
```

---

## 六、访问验证

浏览器打开：

| 地址 | 内容 |
|---|---|
| `http://服务器IP:8000/` | 同城榜单小程序（用户端） |
| `http://服务器IP:8000/admin` | 管理后台（用上面的账号密码登录） |
| `http://服务器IP:8000/docs` | API 交互式文档 |

---

## 七、常用管理命令

在项目目录 `/opt/rankplanet` 下执行：

| 命令 | 作用 |
|---|---|
| `./deploy.sh` | 一键部署 / 重新构建启动 |
| `./deploy.sh status` | 查看运行状态与健康检查 |
| `./deploy.sh logs` | 实时查看日志（Ctrl+C 退出） |
| `./deploy.sh restart` | 重启服务 |
| `./deploy.sh stop` | 停止服务（数据保留） |
| `./deploy.sh update` | 拉取最新代码并重新部署 |
| `./deploy.sh backup` | 备份数据库到项目目录 |
| `./deploy.sh password` | 重置管理员密码为新的随机密码 |
| `./deploy.sh uninstall` | 卸载容器与镜像（数据保留在 `./data`） |

---

## 八、修改配置

编辑项目根目录的 `.env` 文件，改完执行 `./deploy.sh restart`（改端口用 `./deploy.sh` 重新部署）。

```bash
# 服务端口（宿主机对外端口；改完记得同步放行新端口）
PORT=8000

# 初始管理员账号（仅首次启动、数据库为空时生效）
ADMIN_USER=admin
ADMIN_PASSWORD=admin123

# 登录有效期（秒），默认 24 小时
TOKEN_TTL=86400

# 是否导入内置示例榜单（1=导入，0=空库）
SEED_DATA=1
```

> **想改已生效的管理员密码**：直接用 `./deploy.sh password` 重置，或登录后台在「账号设置」里改。
> `.env` 里的 `ADMIN_PASSWORD` 只在**数据库为空时**创建管理员使用，不会覆盖已有密码。

---

## 九、数据备份与恢复

数据库文件在 `./data/rankplanet.db`（已挂载到宿主机，容器删除也不丢）。

**备份**：

```bash
./deploy.sh backup          # 生成 backup_rankplanet_日期时间.db
```

**恢复**：

```bash
./deploy.sh stop
cp backup_rankplanet_20261006_120000.db data/rankplanet.db
./deploy.sh restart
```

**建议**：给服务器加个定时任务，每天自动备份：

```bash
crontab -e
# 加入下面一行（每天凌晨 3 点备份）
0 3 * * * cd /opt/rankplanet && ./deploy.sh backup >> /var/log/rp_backup.log 2>&1
```

---

## 十、可选：绑定域名与 HTTPS

有域名后可以配置 Nginx 反向代理 + 免费证书：

```bash
# 1. 安装 Nginx 与 Certbot
apt install -y nginx certbot python3-certbot-nginx

# 2. 新建站点配置
cat > /etc/nginx/sites-available/rankplanet <<'EOF'
server {
    listen 80;
    server_name 你的域名.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF
ln -sf /etc/nginx/sites-available/rankplanet /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 3. 申请免费 HTTPS 证书（自动配置 443）
certbot --nginx -d 你的域名.com
```

完成后用 `https://你的域名.com` 访问，记得放行 **80 和 443** 端口。

---

## 十一、常见问题

**Q1：浏览器打不开，一直转圈**
→ 99% 是安全组没放行端口，见第五节。也可能是 `ufw`/`firewalld` 未放行。

**Q2：`./deploy.sh` 报 "permission denied"**
→ 执行 `chmod +x deploy.sh` 后再运行。

**Q3：报错 "Cannot connect to the Docker daemon"**
→ 执行 `systemctl start docker`；若提示权限不足，执行 `usermod -aG docker $USER` 后**重新登录** SSH。

**Q4：构建卡在下载依赖**
→ 网络问题，配置 Docker 镜像加速（见第二步说明）后重试。

**Q5：怎么升级到最新版本？**
→ `./deploy.sh update`（会自动 `git pull`、重新构建并启动）。

**Q6：忘记管理员密码了？**
→ 在服务器项目目录执行 `./deploy.sh password`。

**Q7：想换个端口（比如 80）？**
→ 改 `.env` 里 `PORT=80`，执行 `./deploy.sh restart`，并放行 80 端口。
（`PORT` 是宿主机对外端口，容器内部固定 8000，二者自动映射，无需关心内部细节）
（注意：用 80 端口时建议同时配置域名，否则部分云厂商需备案）
