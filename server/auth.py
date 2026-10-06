"""
鉴权模块
========
- 管理员密码使用 PBKDF2-HMAC-SHA256 加盐哈希存储（不存明文）
- 登录成功后签发随机 token，存于数据库 tokens 表，24 小时过期
- 提供 FastAPI 依赖 admin_required，用于保护管理接口
"""

import os
import hmac
import time
import hashlib
import secrets

from fastapi import Header, HTTPException, Depends

from database import get_conn

TOKEN_TTL = 24 * 3600  # token 有效期 24 小时
PBKDF2_ROUNDS = 120_000

# 默认管理员账号（仅首次初始化时创建）
DEFAULT_ADMIN = "admin"
DEFAULT_ADMIN_PWD = "admin123"


# ---------------------------------------------------------------- 密码哈希
def hash_password(password: str, salt: str | None = None) -> str:
    """返回 'salt$hash' 格式的密码摘要。"""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ROUNDS)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验明文密码是否匹配存储的摘要。"""
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


# ---------------------------------------------------------------- token 表
def _ensure_token_table():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tokens (
                token      TEXT PRIMARY KEY,
                admin_id   INTEGER NOT NULL,
                expires_at REAL NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
            """
        )


def issue_token(admin_id: int) -> str:
    """签发新 token。"""
    _ensure_token_table()
    token = secrets.token_urlsafe(32)
    expires = time.time() + TOKEN_TTL
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tokens(token, admin_id, expires_at) VALUES (?,?,?)",
            (token, admin_id, expires),
        )
    return token


def revoke_token(token: str):
    _ensure_token_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM tokens WHERE token = ?", (token,))


def check_token(token: str):
    """校验 token，有效返回 admin 记录，否则返回 None。"""
    _ensure_token_table()
    # 顺带清理过期 token
    with get_conn() as conn:
        conn.execute("DELETE FROM tokens WHERE expires_at < ?", (time.time(),))
        row = conn.execute(
            """
            SELECT a.id, a.username FROM tokens t
            JOIN admins a ON a.id = t.admin_id
            WHERE t.token = ? AND t.expires_at > ?
            """,
            (token, time.time()),
        ).fetchone()
    return row


# ---------------------------------------------------------------- FastAPI 依赖
def admin_required(authorization: str = Header(default="")):
    """FastAPI 依赖：要求请求头携带 Authorization: Bearer <token>。

    校验失败抛出 401，由 FastAPI 统一返回 JSON。
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或缺少 Token")
    token = authorization[7:].strip()
    admin = check_token(token)
    if not admin:
        raise HTTPException(status_code=401, detail="Token 无效或已过期，请重新登录")
    return {"id": admin["id"], "username": admin["username"], "token": token}


def ensure_default_admin():
    """若无任何管理员，创建默认账号 admin / admin123。"""
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM admins").fetchone()["c"]
        if n == 0:
            conn.execute(
                "INSERT INTO admins(username, password_hash) VALUES (?,?)",
                (DEFAULT_ADMIN, hash_password(DEFAULT_ADMIN_PWD)),
            )
            return True
    return False


def change_password(admin_id: int, new_password: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE admins SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), admin_id),
        )
