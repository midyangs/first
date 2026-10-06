# 榜单星球 后端 API 文档

Base URL：`http://localhost:8000`

- 交互式文档（Swagger）：`http://localhost:8000/docs`
- 管理后台：`http://localhost:8000/admin`

## 鉴权说明

| 角色 | 方式 | 说明 |
|---|---|---|
| 管理员 | 请求头 `Authorization: Bearer <token>` | 通过 `/api/admin/login` 获取，24h 有效 |
| 终端用户 | 请求头 `X-User-Token: <任意唯一字符串>` | 客户端首次打开时生成（如 UUID），用于点赞防重 |

---

## 公开接口

### GET /api/cities

城市列表（有榜单的城市排前面）。

```bash
curl http://localhost:8000/api/cities
```

### GET /api/ranks

榜单列表。

| 参数 | 类型 | 说明 |
|---|---|---|
| `city` | string | 按城市筛选，可选 |
| `cat` | string | `food` / `fun` / `all`，默认全部 |
| `sort` | string | `hot`（默认，热度=基础热度+点赞×12）/ `new` / `views` |
| `limit` / `offset` | int | 分页，默认 50 / 0 |

```bash
curl "http://localhost:8000/api/ranks?city=成都&cat=food&sort=hot&limit=10"
```

响应：

```json
{
  "total": 6,
  "items": [
    {
      "id": "s1", "title": "成都必吃十大苍蝇馆子", "cat": "food",
      "city": "成都", "cover": "🌶️", "grad": 0, "desc": "...",
      "views": 12841, "hot": 9860, "self": 0, "status": "published",
      "created_at": "2026-10-06 19:16:xx",
      "entry_count": 10, "total_likes": 2, "hotness": 9884
    }
  ]
}
```

### GET /api/ranks/{id}

榜单详情，含全部条目（按名次排序）。仅返回 `published` 状态的榜单，否则 404。

### POST /api/ranks/{id}/view

浏览量 +1。请求头可带 `X-User-Token` 用于行为统计。

### POST /api/ranks/{id}/entries/{seq}/like

点赞 / 取消点赞（幂等切换）。需要 `X-User-Token` 头，同一用户对同一条目只能点赞一次。

```bash
curl -X POST "http://localhost:8000/api/ranks/s1/entries/1/like" \
     -H "X-User-Token: user-abc-123"
# → {"ok":true,"liked":true,"likes":1}
```

### POST /api/ranks

用户发布榜单。**进入待审核**（`status=pending`），审核通过后才会出现在公开列表。

```bash
curl -X POST http://localhost:8000/api/ranks \
  -H "Content-Type: application/json" \
  -H "X-User-Token: user-abc-123" \
  -d '{
    "title": "成都深夜食堂 TOP3",
    "cat": "food",
    "city": "成都",
    "desc": "凌晨两点还亮着灯的地方",
    "entries": [
      {"n": "马路边边麻辣烫", "s": 4.7, "p": "¥45", "r": "深夜麻辣烫巅峰", "a": "武侯区致民路", "e": "🍲", "tags": ["夜宵"]}
    ]
  }'
# → {"ok":true,"id":"u1791...","status":"pending","message":"提交成功，等待管理员审核"}
```

### GET /api/search?q=关键词

同时搜索榜单（标题/城市/简介/条目名/标签）与店铺（名称/标签），返回两组结果。

### GET /api/leaderboard?cat=&limit=20

全城热度排行榜，`items[].rank_no` 为名次（1 开始）。

---

## 管理接口

以下接口均需请求头 `Authorization: Bearer <token>`。

### POST /api/admin/login

```bash
curl -X POST http://localhost:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
# → {"ok":true,"token":"...","username":"admin","expires_in":86400}
```

> 默认账号 `admin / admin123`，**首次登录后请立即在后台「账号设置」中修改**。

### POST /api/admin/logout

注销当前 token。

### GET /api/admin/me

当前登录管理员信息。

### POST /api/admin/password

修改密码：`{"old_password":"...","new_password":"..."}`，新密码至少 6 位。修改后需重新登录。

### GET /api/admin/stats

数据总览，返回：

```json
{
  "rank_total": 7, "rank_published": 7, "rank_pending": 0, "rank_rejected": 0,
  "entry_total": 49, "like_total": 2, "view_total": 50162,
  "user_ranks": 1, "today_views": 2, "today_likes": 3,
  "cat_food": 4, "cat_fun": 3
}
```

### GET /api/admin/trend?days=7

近 N 日浏览/点赞趋势（基于 events 表）。

### GET /api/admin/ranks

管理端榜单列表（**含待审核/已驳回**），支持 `status` / `cat` / `q` 筛选。

### POST /api/admin/ranks

新建榜单（直接 `published`），请求体同用户发布接口。

### PUT /api/admin/ranks/{id}

编辑榜单基本信息并**整体替换**条目列表。

### DELETE /api/admin/ranks/{id}

删除榜单及其条目、点赞记录（级联，不可恢复）。

### PUT /api/admin/ranks/{id}/status

审核状态变更：`{"status":"published"}` / `"pending"` / `"rejected"`。

```bash
TOKEN=<你的token>
curl -X PUT http://localhost:8000/api/admin/ranks/u1791.../status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"published"}'
```

---

## 错误格式

所有错误返回 `{"detail": "错误信息"}`：

| 状态码 | 场景 |
|---|---|
| 400 | 参数缺失/非法、缺少 X-User-Token |
| 401 | 未登录 / Token 无效或过期 / 密码错误 |
| 404 | 榜单或条目不存在 |

## 数据库

SQLite 文件：`data/rankplanet.db`，表结构见 `server/database.py`：

- `ranks` 榜单 · `entries` 条目 · `likes` 点赞记录 · `admins` 管理员 · `tokens` 登录令牌 · `events` 行为事件

> 备份：直接复制 `data/rankplanet.db` 文件即可。
