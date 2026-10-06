"""
集中配置
========
所有可通过环境变量覆盖的参数集中在此，便于容器化部署。
未设置时使用括号内的默认值（适合本地开发）。

环境变量一览：
    DB_PATH         SQLite 数据库文件路径   (./data/rankplanet.db)
    ADMIN_USER      初始管理员账号          (admin)
    ADMIN_PASSWORD  初始管理员密码          (admin123)
    TOKEN_TTL       登录令牌有效期（秒）     (86400 = 24 小时)
    PORT            容器内服务端口          (8000)
    SEED_DATA       是否导入示例数据        (1 = 导入)
"""

import os


def _env(key: str, default: str) -> str:
    v = os.environ.get(key)
    return v if v not in (None, "") else default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, "") or default)
    except ValueError:
        return default


def _env_bool(key: str, default: bool = True) -> bool:
    v = os.environ.get(key)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on", "y")


# ---------------------------------------------------------------- 数据库
# 相对路径以「项目根目录」为基准（server/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = _env("DB_PATH", os.path.join(BASE_DIR, "data", "rankplanet.db"))

# ---------------------------------------------------------------- 管理员
ADMIN_USER = _env("ADMIN_USER", "admin")
ADMIN_PASSWORD = _env("ADMIN_PASSWORD", "admin123")
TOKEN_TTL = _env_int("TOKEN_TTL", 24 * 3600)

# ---------------------------------------------------------------- 服务
# 容器内监听端口（固定 8000，由容器入口脚本使用；
# 宿主机对外端口由 docker-compose 的 PORT 环境变量控制）
INTERNAL_PORT = _env_int("INTERNAL_PORT", 8000)
SEED_DATA = _env_bool("SEED_DATA", True)

# 生产环境提示：仍在使用默认密码时给出警告
USING_DEFAULT_PASSWORD = ADMIN_PASSWORD == "admin123"
