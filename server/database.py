"""
数据库连接与建表
================
使用 Python 内置 sqlite3，零额外依赖。

数据表设计严格对齐前端 src/同城榜单.html 的 rank / entry 对象结构，
便于后期前端直接对接而不必改数据结构。
"""

import os
import sqlite3
import json
from contextlib import contextmanager

# 数据库文件放在项目根目录的 data/ 下
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DB_DIR, "rankplanet.db")


def _ensure_dir():
    os.makedirs(DB_DIR, exist_ok=True)


@contextmanager
def get_conn():
    """获取数据库连接（上下文管理器，自动提交/回滚/关闭）。

    row_factory 设为 sqlite3.Row，使查询结果可按列名访问。
    """
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------- 建表 SQL
SCHEMA = """
-- 榜单表
CREATE TABLE IF NOT EXISTS ranks (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    cat         TEXT NOT NULL DEFAULT 'food',      -- food | fun
    city        TEXT NOT NULL DEFAULT '成都',
    cover       TEXT DEFAULT '📋',                  -- 封面 emoji
    grad        INTEGER DEFAULT 0,                  -- 封面色索引 0-9
    "desc"      TEXT DEFAULT '',                    -- 榜单简介（desc 是 SQL 关键字，加引号）
    views       INTEGER DEFAULT 0,                  -- 浏览量
    hot         INTEGER DEFAULT 0,                  -- 基础热度
    self        INTEGER DEFAULT 0,                  -- 是否用户发布
    status      TEXT DEFAULT 'published',           -- published | pending | rejected
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);

-- 上榜条目表
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rank_id     TEXT NOT NULL,
    seq         INTEGER NOT NULL,                   -- 名次，从 1 开始
    n           TEXT NOT NULL,                      -- 名称
    s           REAL DEFAULT 4.5,                   -- 评分
    p           TEXT DEFAULT '',                    -- 人均
    r           TEXT DEFAULT '',                    -- 上榜理由
    a           TEXT DEFAULT '',                    -- 地址
    e           TEXT DEFAULT '🍽️',                  -- 图标 emoji
    tags        TEXT DEFAULT '[]',                  -- 标签（JSON 数组字符串）
    likes       INTEGER DEFAULT 0,                  -- 点赞数
    FOREIGN KEY (rank_id) REFERENCES ranks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_entries_rank ON entries(rank_id, seq);

-- 点赞记录表（防重复点赞）
CREATE TABLE IF NOT EXISTS likes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rank_id     TEXT NOT NULL,
    entry_seq   INTEGER NOT NULL,
    user_token  TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(rank_id, entry_seq, user_token)
);

-- 管理员表
CREATE TABLE IF NOT EXISTS admins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now','localtime'))
);

-- 访客行为统计表（浏览/点赞事件，供后台出图）
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rank_id     TEXT,
    action      TEXT,                               -- view | like | unlike | create
    user_token  TEXT,
    created_at  TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
"""


def init_db():
    """初始化数据库：建表（幂等）。"""
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    return True


def count_rows(table):
    with get_conn() as conn:
        return conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]


# ---------------------------------------------------------------- 行 → 字典
def row_to_entry(row):
    """entries 行转前端 entry 结构。"""
    return {
        "id": row["id"],
        "seq": row["seq"],
        "n": row["n"],
        "s": row["s"],
        "p": row["p"],
        "r": row["r"],
        "a": row["a"],
        "e": row["e"],
        "tags": json.loads(row["tags"] or "[]"),
        "likes": row["likes"],
    }


def row_to_rank(row, entries=None):
    """ranks 行转前端 rank 结构。"""
    d = {
        "id": row["id"],
        "title": row["title"],
        "cat": row["cat"],
        "city": row["city"],
        "cover": row["cover"],
        "grad": row["grad"],
        "desc": row["desc"],
        "views": row["views"],
        "hot": row["hot"],
        "self": row["self"],
        "status": row["status"],
        "created_at": row["created_at"],
    }
    if entries is not None:
        d["entries"] = entries
    return d


if __name__ == "__main__":
    init_db()
    print(f"数据库已初始化：{DB_PATH}")
