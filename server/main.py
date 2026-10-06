"""
榜单星球 · 管理后端
==================
FastAPI + SQLite 实现，提供：

公开接口（供小程序调用）
  GET  /api/cities                      城市列表
  GET  /api/ranks                       榜单列表（支持 city/cat/sort/status 筛选）
  GET  /api/ranks/{id}                  榜单详情（含条目）
  POST /api/ranks/{id}/view             浏览量 +1
  POST /api/ranks/{id}/entries/{seq}/like   点赞 / 取消点赞
  POST /api/ranks                       用户发布榜单（进入待审核）
  GET  /api/search?q=                   搜索榜单与店铺
  GET  /api/leaderboard                 热度排行榜

管理接口（需 Bearer Token）
  POST   /api/admin/login
  POST   /api/admin/logout
  GET    /api/admin/me
  POST   /api/admin/password            修改密码
  GET    /api/admin/stats               数据总览
  GET    /api/admin/trend?days=7        趋势数据
  GET    /api/admin/ranks               全部榜单（含待审核）
  POST   /api/admin/ranks               新建榜单
  PUT    /api/admin/ranks/{id}          编辑榜单
  DELETE /api/admin/ranks/{id}          删除榜单
  PUT    /api/admin/ranks/{id}/status   审核状态变更

启动：uvicorn main:app --host 0.0.0.0 --port 8000
文档：http://localhost:8000/docs
后台：http://localhost:8000/admin
"""

import os
import json
import time
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Header, Depends, Query, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import database as db
from database import get_conn, init_db, row_to_rank, row_to_entry
from seed import bootstrap, CITIES
import auth as auth_mod
from auth import admin_required, verify_password, issue_token, revoke_token, change_password

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(
    title="榜单星球 管理后端",
    description="同城榜单小程序配套后端：榜单管理、点赞投票、内容审核、数据统计",
    version="1.0.0",
)

# 启动时自动初始化数据库（建表 + 示例数据 + 默认管理员）
@app.on_event("startup")
def _startup():
    info = bootstrap()
    print("=" * 52)
    print(" 榜单星球 后端已启动")
    print(f"  数据库: {db.DB_PATH}")
    print(f"  初始化数据: {'已导入示例榜单' if info['seeded'] else '已有数据，跳过'}")
    print(f"  默认管理员: {auth_mod.DEFAULT_ADMIN} / {auth_mod.DEFAULT_ADMIN_PWD}"
          if info["admin_created"] else "  管理员账号已存在")
    print("=" * 52)


# ================================================================ 工具
def _now_str():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _load_rank_full(conn, rank_id, only_published=True):
    """读取榜单及其条目，返回前端结构字典。"""
    row = conn.execute("SELECT * FROM ranks WHERE id = ?", (rank_id,)).fetchone()
    if not row:
        return None
    if only_published and row["status"] != "published":
        return None
    ent_rows = conn.execute(
        "SELECT * FROM entries WHERE rank_id = ? ORDER BY seq ASC", (rank_id,)
    ).fetchall()
    return row_to_rank(row, [row_to_entry(e) for e in ent_rows])


def _total_likes(conn, rank_id):
    r = conn.execute(
        "SELECT COALESCE(SUM(likes),0) AS t FROM entries WHERE rank_id = ?", (rank_id,)
    ).fetchone()
    return r["t"]


def _log_event(conn, rank_id, action, user_token=None):
    conn.execute(
        "INSERT INTO events(rank_id, action, user_token) VALUES (?,?,?)",
        (rank_id, action, user_token or "-"),
    )


# ================================================================ 请求模型
class EntryIn(BaseModel):
    n: str
    s: float = 4.5
    p: str = ""
    r: str = ""
    a: str = ""
    e: str = "🍽️"
    tags: List[str] = Field(default_factory=list)


class RankIn(BaseModel):
    title: str
    cat: str = "food"
    city: str = "成都"
    cover: str = "📋"
    grad: int = 0
    desc: str = ""
    entries: List[EntryIn] = Field(default_factory=list)


class LoginIn(BaseModel):
    username: str
    password: str


class StatusIn(BaseModel):
    status: str  # published | pending | rejected


class PwdIn(BaseModel):
    old_password: str
    new_password: str


# ================================================================ 公开接口
@app.get("/api/cities", tags=["公开接口"], summary="城市列表")
def list_cities():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT city FROM ranks WHERE status='published'"
        ).fetchall()
    used = [r["city"] for r in rows]
    # 已启用的城市排在前面，其余按预置列表补全
    ordered = used + [c for c in CITIES if c not in used]
    return {"cities": ordered}


@app.get("/api/ranks", tags=["公开接口"], summary="榜单列表")
def list_ranks(
    city: Optional[str] = None,
    cat: Optional[str] = None,
    sort: str = "hot",          # hot | new | views
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    where = ["status = 'published'"]
    args = []
    if city:
        where.append("city = ?"); args.append(city)
    if cat and cat != "all":
        where.append("cat = ?"); args.append(cat)
    sql_where = " AND ".join(where)

    order = {
        "hot": "hotness DESC",
        "new": "created_at DESC",
        "views": "views DESC",
    }.get(sort, "hotness DESC")

    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT r.*, (SELECT COALESCE(SUM(likes),0) FROM entries e WHERE e.rank_id=r.id) AS like_sum,
                   (r.hot + (SELECT COALESCE(SUM(likes),0) FROM entries e WHERE e.rank_id=r.id)*12) AS hotness
            FROM ranks r
            WHERE {sql_where}
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            (*args, limit, offset),
        ).fetchall()

        result = []
        for r in rows:
            d = row_to_rank(r)
            d["total_likes"] = r["like_sum"]
            d["hotness"] = r["hotness"]
            cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM entries WHERE rank_id = ?", (r["id"],)
            ).fetchone()["c"]
            d["entry_count"] = cnt
            result.append(d)
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM ranks WHERE {sql_where}", args
        ).fetchone()["c"]
    return {"total": total, "items": result}


@app.get("/api/ranks/{rank_id}", tags=["公开接口"], summary="榜单详情")
def get_rank(rank_id: str):
    with get_conn() as conn:
        d = _load_rank_full(conn, rank_id)
    if not d:
        raise HTTPException(404, "榜单不存在或未发布")
    d["total_likes"] = sum(e["likes"] for e in d["entries"])
    return d


@app.post("/api/ranks/{rank_id}/view", tags=["公开接口"], summary="浏览量 +1")
def add_view(rank_id: str, x_user_token: str = Header(default="")):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM ranks WHERE id=?", (rank_id,)).fetchone()
        if not row:
            raise HTTPException(404, "榜单不存在")
        conn.execute("UPDATE ranks SET views = views + 1 WHERE id = ?", (rank_id,))
        _log_event(conn, rank_id, "view", x_user_token)
        v = conn.execute("SELECT views FROM ranks WHERE id=?", (rank_id,)).fetchone()["views"]
    return {"ok": True, "views": v}


@app.post("/api/ranks/{rank_id}/entries/{seq}/like", tags=["公开接口"], summary="点赞/取消点赞")
def like_entry(rank_id: str, seq: int, x_user_token: str = Header(default="")):
    if not x_user_token:
        raise HTTPException(400, "缺少 X-User-Token 请求头")
    with get_conn() as conn:
        e = conn.execute(
            "SELECT * FROM entries WHERE rank_id=? AND seq=?", (rank_id, seq)
        ).fetchone()
        if not e:
            raise HTTPException(404, "条目不存在")
        exist = conn.execute(
            "SELECT id FROM likes WHERE rank_id=? AND entry_seq=? AND user_token=?",
            (rank_id, seq, x_user_token),
        ).fetchone()
        if exist:
            # 取消点赞
            conn.execute("DELETE FROM likes WHERE id=?", (exist["id"],))
            conn.execute("UPDATE entries SET likes = MAX(0, likes - 1) WHERE id=?", (e["id"],))
            liked = False
            _log_event(conn, rank_id, "unlike", x_user_token)
        else:
            conn.execute(
                "INSERT INTO likes(rank_id, entry_seq, user_token) VALUES (?,?,?)",
                (rank_id, seq, x_user_token),
            )
            conn.execute("UPDATE entries SET likes = likes + 1 WHERE id=?", (e["id"],))
            liked = True
            _log_event(conn, rank_id, "like", x_user_token)
        likes = conn.execute("SELECT likes FROM entries WHERE id=?", (e["id"],)).fetchone()["likes"]
    return {"ok": True, "liked": liked, "likes": likes}


@app.post("/api/ranks", tags=["公开接口"], summary="用户发布榜单（待审核）")
def create_rank(payload: RankIn, x_user_token: str = Header(default="")):
    if not payload.title.strip():
        raise HTTPException(400, "榜单标题不能为空")
    if not payload.entries:
        raise HTTPException(400, "至少需要 1 个上榜条目")
    rank_id = "u%d" % int(time.time() * 1000)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO ranks(id,title,cat,city,cover,grad,"desc",views,hot,self,status)
               VALUES (?,?,?,?,?,?,?,0,500,1,'pending')""",
            (rank_id, payload.title.strip(), payload.cat, payload.city,
             payload.cover, payload.grad, payload.desc),
        )
        for i, e in enumerate(payload.entries, start=1):
            conn.execute(
                """INSERT INTO entries(rank_id,seq,n,s,p,r,a,e,tags,likes)
                   VALUES (?,?,?,?,?,?,?,?,?,0)""",
                (rank_id, i, e.n, e.s, e.p, e.r, e.a, e.e,
                 json.dumps(e.tags, ensure_ascii=False)),
            )
        _log_event(conn, rank_id, "create", x_user_token)
    return {"ok": True, "id": rank_id, "status": "pending", "message": "提交成功，等待管理员审核"}


@app.get("/api/search", tags=["公开接口"], summary="搜索榜单与店铺")
def search(q: str = Query(..., min_length=1)):
    kw = f"%{q.strip()}%"
    with get_conn() as conn:
        # 榜单命中：标题 / 城市 / 简介，或该榜单下的某个条目名/标签命中
        ranks = conn.execute(
            """SELECT DISTINCT r.* FROM ranks r
               LEFT JOIN entries e ON e.rank_id = r.id
               WHERE r.status='published' AND (
                     r.title LIKE ? OR r.city LIKE ? OR r."desc" LIKE ?
                     OR e.n LIKE ? OR e.tags LIKE ?
               )
               ORDER BY r.hot DESC LIMIT 30""",
            (kw, kw, kw, kw, kw),
        ).fetchall()
        rank_list = []
        for r in ranks:
            d = row_to_rank(r)
            d["total_likes"] = _total_likes(conn, r["id"])
            rank_list.append(d)

        entry_rows = conn.execute(
            """SELECT e.*, r.title AS rank_title, r.city AS rank_city
               FROM entries e JOIN ranks r ON r.id = e.rank_id
               WHERE r.status='published' AND (e.n LIKE ? OR e.tags LIKE ?)
               ORDER BY e.likes DESC LIMIT 40""",
            (kw, kw),
        ).fetchall()
        entry_list = []
        for e in entry_rows:
            d = row_to_entry(e)
            d["rank_id"] = e["rank_id"]
            d["rank_title"] = e["rank_title"]
            d["rank_city"] = e["rank_city"]
            entry_list.append(d)
    return {"q": q, "ranks": rank_list, "entries": entry_list}


@app.get("/api/leaderboard", tags=["公开接口"], summary="热度排行榜")
def leaderboard(cat: Optional[str] = None, limit: int = Query(20, ge=1, le=100)):
    where = ["status='published'"]
    args = []
    if cat and cat != "all":
        where.append("cat = ?"); args.append(cat)
    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT r.*, (r.hot + (SELECT COALESCE(SUM(likes),0) FROM entries e WHERE e.rank_id=r.id)*12) AS hotness
                FROM ranks r WHERE {' AND '.join(where)}
                ORDER BY hotness DESC LIMIT ?""",
            (*args, limit),
        ).fetchall()
        out = []
        for i, r in enumerate(rows, start=1):
            d = row_to_rank(r)
            d["rank_no"] = i
            d["hotness"] = r["hotness"]
            out.append(d)
    return {"items": out}


# ================================================================ 管理接口
@app.post("/api/admin/login", tags=["管理接口"], summary="管理员登录")
def admin_login(payload: LoginIn):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM admins WHERE username = ?", (payload.username,)
        ).fetchone()
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    token = issue_token(row["id"])
    return {"ok": True, "token": token, "username": row["username"],
            "expires_in": auth_mod.TOKEN_TTL}


@app.post("/api/admin/logout", tags=["管理接口"], summary="退出登录")
def admin_logout(admin=Depends(admin_required)):
    revoke_token(admin["token"])
    return {"ok": True}


@app.get("/api/admin/me", tags=["管理接口"], summary="当前登录管理员")
def admin_me(admin=Depends(admin_required)):
    return {"id": admin["id"], "username": admin["username"]}


@app.post("/api/admin/password", tags=["管理接口"], summary="修改密码")
def admin_change_pwd(payload: PwdIn, admin=Depends(admin_required)):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM admins WHERE id=?", (admin["id"],)).fetchone()
    if not verify_password(payload.old_password, row["password_hash"]):
        raise HTTPException(400, "原密码错误")
    if len(payload.new_password) < 6:
        raise HTTPException(400, "新密码至少 6 位")
    change_password(admin["id"], payload.new_password)
    return {"ok": True, "message": "密码修改成功，请重新登录"}


@app.get("/api/admin/stats", tags=["管理接口"], summary="数据总览")
def admin_stats(admin=Depends(admin_required)):
    with get_conn() as conn:
        g = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
        stats = {
            "rank_total":    g("SELECT COUNT(*) FROM ranks"),
            "rank_published":g("SELECT COUNT(*) FROM ranks WHERE status='published'"),
            "rank_pending":  g("SELECT COUNT(*) FROM ranks WHERE status='pending'"),
            "rank_rejected": g("SELECT COUNT(*) FROM ranks WHERE status='rejected'"),
            "entry_total":   g("SELECT COUNT(*) FROM entries"),
            "like_total":    g("SELECT COALESCE(SUM(likes),0) FROM entries"),
            "view_total":    g("SELECT COALESCE(SUM(views),0) FROM ranks"),
            "user_ranks":    g("SELECT COUNT(*) FROM ranks WHERE self=1"),
            "today_views":   g("SELECT COUNT(*) FROM events WHERE action='view' AND date(created_at)=date('now','localtime')"),
            "today_likes":   g("SELECT COUNT(*) FROM events WHERE action='like' AND date(created_at)=date('now','localtime')"),
        }
        # 分类分布
        stats["cat_food"] = g("SELECT COUNT(*) FROM ranks WHERE cat='food'")
        stats["cat_fun"]  = g("SELECT COUNT(*) FROM ranks WHERE cat='fun'")
    return stats


@app.get("/api/admin/trend", tags=["管理接口"], summary="近期趋势")
def admin_trend(days: int = Query(7, ge=1, le=30), admin=Depends(admin_required)):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT date(created_at) AS d,
                   SUM(CASE WHEN action='view' THEN 1 ELSE 0 END) AS views,
                   SUM(CASE WHEN action='like' THEN 1 ELSE 0 END) AS likes
            FROM events
            WHERE date(created_at) >= date('now','localtime', ?)
            GROUP BY d ORDER BY d ASC
            """,
            (f"-{days-1} day",),
        ).fetchall()
    return {"days": days, "items": [dict(r) for r in rows]}


@app.get("/api/admin/ranks", tags=["管理接口"], summary="全部榜单（含待审核）")
def admin_list_ranks(
    status: Optional[str] = None,
    cat: Optional[str] = None,
    q: Optional[str] = None,
    admin=Depends(admin_required),
):
    where, args = [], []
    if status and status != "all":
        where.append("r.status = ?"); args.append(status)
    if cat and cat != "all":
        where.append("r.cat = ?"); args.append(cat)
    if q:
        where.append("(r.title LIKE ? OR r.city LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    sql_where = ("WHERE " + " AND ".join(where)) if where else ""
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT r.*, (SELECT COUNT(*) FROM entries e WHERE e.rank_id=r.id) AS entry_count,
                   (SELECT COALESCE(SUM(likes),0) FROM entries e WHERE e.rank_id=r.id) AS like_sum
            FROM ranks r {sql_where}
            ORDER BY r.created_at DESC, r.id DESC
            """,
            args,
        ).fetchall()
        items = []
        for r in rows:
            d = row_to_rank(r)
            d["entry_count"] = r["entry_count"]
            d["total_likes"] = r["like_sum"]
            items.append(d)
    return {"total": len(items), "items": items}


@app.get("/api/admin/ranks/{rank_id}", tags=["管理接口"], summary="榜单详情（管理端，不限状态）")
def admin_get_rank(rank_id: str, admin=Depends(admin_required)):
    with get_conn() as conn:
        d = _load_rank_full(conn, rank_id, only_published=False)
    if not d:
        raise HTTPException(404, "榜单不存在")
    return d


@app.post("/api/admin/ranks", tags=["管理接口"], summary="新建榜单")
def admin_create_rank(payload: RankIn, admin=Depends(admin_required)):
    rank_id = "m%d" % int(time.time() * 1000)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO ranks(id,title,cat,city,cover,grad,"desc",views,hot,self,status)
               VALUES (?,?,?,?,?,?,?,0,800,0,'published')""",
            (rank_id, payload.title, payload.cat, payload.city,
             payload.cover, payload.grad, payload.desc),
        )
        for i, e in enumerate(payload.entries, start=1):
            conn.execute(
                """INSERT INTO entries(rank_id,seq,n,s,p,r,a,e,tags,likes)
                   VALUES (?,?,?,?,?,?,?,?,?,0)""",
                (rank_id, i, e.n, e.s, e.p, e.r, e.a, e.e,
                 json.dumps(e.tags, ensure_ascii=False)),
            )
    return {"ok": True, "id": rank_id}


@app.put("/api/admin/ranks/{rank_id}", tags=["管理接口"], summary="编辑榜单")
def admin_update_rank(rank_id: str, payload: RankIn, admin=Depends(admin_required)):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM ranks WHERE id=?", (rank_id,)).fetchone()
        if not row:
            raise HTTPException(404, "榜单不存在")
        conn.execute(
            """UPDATE ranks SET title=?, cat=?, city=?, cover=?, grad=?, "desc"=? WHERE id=?""",
            (payload.title, payload.cat, payload.city, payload.cover,
             payload.grad, payload.desc, rank_id),
        )
        # 条目整体替换
        conn.execute("DELETE FROM entries WHERE rank_id=?", (rank_id,))
        for i, e in enumerate(payload.entries, start=1):
            conn.execute(
                """INSERT INTO entries(rank_id,seq,n,s,p,r,a,e,tags,likes)
                   VALUES (?,?,?,?,?,?,?,?,?,0)""",
                (rank_id, i, e.n, e.s, e.p, e.r, e.a, e.e,
                 json.dumps(e.tags, ensure_ascii=False)),
            )
    return {"ok": True}


@app.delete("/api/admin/ranks/{rank_id}", tags=["管理接口"], summary="删除榜单")
def admin_delete_rank(rank_id: str, admin=Depends(admin_required)):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM ranks WHERE id=?", (rank_id,)).fetchone()
        if not row:
            raise HTTPException(404, "榜单不存在")
        conn.execute("DELETE FROM entries WHERE rank_id=?", (rank_id,))
        conn.execute("DELETE FROM likes WHERE rank_id=?", (rank_id,))
        conn.execute("DELETE FROM ranks WHERE id=?", (rank_id,))
    return {"ok": True}


@app.put("/api/admin/ranks/{rank_id}/status", tags=["管理接口"], summary="审核状态变更")
def admin_set_status(rank_id: str, payload: StatusIn, admin=Depends(admin_required)):
    if payload.status not in ("published", "pending", "rejected"):
        raise HTTPException(400, "状态值非法")
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM ranks WHERE id=?", (rank_id,)).fetchone()
        if not row:
            raise HTTPException(404, "榜单不存在")
        conn.execute("UPDATE ranks SET status=? WHERE id=?", (payload.status, rank_id))
    return {"ok": True, "status": payload.status}


# ================================================================ 后台页面 & 静态资源
@app.get("/admin", response_class=HTMLResponse, tags=["后台"], summary="管理后台页面")
def admin_page():
    path = os.path.join(STATIC_DIR, "admin.html")
    if not os.path.exists(path):
        return HTMLResponse("<h1>管理后台文件缺失</h1>", status_code=500)
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/", tags=["后台"], summary="根路径跳转后台")
def root():
    return HTMLResponse('<meta http-equiv="refresh" content="0;url=/admin">')


if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
