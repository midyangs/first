# 榜单星球 · 同城榜单

一个**同城美食 / 娱乐榜单**类小程序（H5 网页版），模仿微信小程序交互体验。用户可以浏览榜单、按分类筛选、发布自己的榜单、给上榜店铺点赞投票，并管理个人收藏。

> 当前为**纯前端零依赖单文件应用**，数据存放在浏览器 `localStorage`，无需后端即可运行。

---

## 一、快速开始

> ☁️ **要部署到云服务器？** 跳到 [docs/DEPLOY.md](docs/DEPLOY.md)，`./deploy.sh` 一条命令搞定。

### 方式 1：直接打开（最简单）

双击 `src/同城榜单.html`，用浏览器打开即可，无需任何环境。

### 方式 2：本地服务器（推荐，行为与线上一致）

```bash
cd src
python3 -m http.server 8899
# 浏览器访问 http://localhost:8899/同城榜单.html
```

建议用 Chrome / Edge / Safari 的**移动端调试模式**（F12 → 切换设备工具栏），选择 iPhone 尺寸，视觉效果最佳。

---

## 二、项目结构

```
.
├── README.md              项目说明（本文件）
├── CHANGELOG.md           版本变更记录
├── .gitignore             忽略规则
├── Dockerfile             ★ Docker 镜像构建
├── docker-compose.yml     ★ 服务编排（端口/卷/健康检查）
├── .env.example           ★ 部署配置模板（复制为 .env 使用）
├── deploy.sh              ★ 一键部署脚本
├── src/
│   └── 同城榜单.html       前端应用（HTML + CSS + JS 单文件）
├── server/                ★ 管理后端（FastAPI + SQLite）
│   ├── main.py            API 路由（公开接口 + 管理接口 + 前端托管）
│   ├── config.py          环境变量配置中心
│   ├── database.py        SQLite 连接与建表
│   ├── auth.py            密码哈希与 Token 鉴权
│   ├── seed.py            示例数据初始化
│   ├── entrypoint.sh      容器入口（卷权限修正 + 降权）
│   ├── static/admin.html  可视化管理后台
│   └── requirements.txt
├── data/
│   └── rankplanet.db      SQLite 数据库（运行后生成，已 gitignore）
└── docs/
    ├── DEV.md             前端开发与二次开发指南
    ├── API.md             后端 API 接口文档
    └── DEPLOY.md          ★ 云服务器一键部署手册
```

**为什么用单文件？** 便于分发、双击即用、无构建步骤、无依赖风险。若后期要工程化拆分，参见 `docs/DEV.md` 的重构建议。

---

## 三、管理后端（v2.0 新增）

```bash
cd server
pip3 install -r requirements.txt
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

| 入口 | 地址 |
|---|---|
| 管理后台 | http://localhost:8000/admin （默认账号 `admin` / `admin123`） |
| API 文档 | http://localhost:8000/docs （Swagger 交互式） |

功能：数据总览（9 项统计 + 7 日趋势图）、榜单增删改查、用户内容审核（通过/驳回）、内容检索、修改密码。

首次启动自动建表并导入 6 份示例榜单。接口详情见 `docs/API.md`。

---

---

## 四、功能清单

| 模块 | 功能 |
|---|---|
| 首页 | 城市切换（12 城）、搜索入口、美食/娱乐/全部分类切换、榜单卡片流 |
| 榜单详情 | 渐变头图、榜单简介、按名次排列的条目（金/银/铜牌徽章、评分、人均、标签、上榜理由、地址）、条目点赞、榜单收藏 |
| 榜单广场 | 全城榜单热度排行榜，前三名高亮 |
| 发布榜单 | 标题、简介、分类、城市 + 动态增删多个上榜条目 |
| 搜索 | 模糊匹配榜单标题、店铺名、标签、城市，分组展示结果 |
| 我的 | 发布/点赞/收藏统计与列表、清除本地数据 |

---

## 五、技术栈

- **HTML5 + CSS3 + 原生 JavaScript (ES6)**，无任何框架、无 CDN 依赖
- **数据持久化**：`localStorage`，键名 `rankplanet_v1`
- **主题色**：美团/大众点评风橙色系（`--primary: #FF6B00`）
- **图片方案**：CSS 渐变 + emoji 图标，避免网络图片加载失败
- **适配**：移动端优先，`max-width: 480px` 居中模拟手机屏

---

## 六、数据说明

### 内置示例数据（`SEED`）

6 份成都榜单，共 45+ 条目：

1. 成都必吃十大苍蝇馆子（美食）
2. 成都最火的 8 家咖啡小馆（美食）
3. 成都夜生活必去的 6 家酒吧（娱乐）
4. 成都周末遛娃好去处 TOP7（娱乐）
5. 成都必打卡的 8 个文化地标（娱乐）
6. 成都人均 50 以下的宝藏小店（美食）

### 用户数据

用户发布的榜单、点赞记录、收藏记录自动保存到 `localStorage`。**清除浏览器数据会丢失**，若需长期保存请接入后端（见 `docs/DEV.md`）。

### localStorage 结构

```json
{
  "myLikes": { "s1::0": true },   // "榜单ID::条目序号" → 已点赞
  "myFavs":  { "s1": true },      // 榜单ID → 已收藏
  "userRanks": [ { "id": "u1712...", "self": 1, "...": "..." } ]
}
```

---

## 七、版本管理

本项目已纳入 Git 管理。

```bash
git log --oneline      # 查看提交历史
git status             # 查看改动
```

后期改进时建议：

```bash
git checkout -b feature/xxx    # 新功能开分支
# ...开发...
git add -A && git commit -m "feat: xxx"
```

---

## 八、后续演进方向

- [x] ~~接入后端实现多用户共享榜单数据~~（v2.0 已完成 FastAPI 后端）
- [ ] **前端对接后端 API**：将 `src/同城榜单.html` 的 localStorage 数据层替换为 `fetch` 调用（字段已对齐，改 `loadUser/saveUser` 即可）
- [ ] 用户系统：注册登录、头像昵称、关注他人榜单
- [ ] 图片上传（当前为 emoji + 渐变占位）
- [ ] 榜单评论、分享海报生成
- [ ] 迁移为**微信小程序**源码结构（WXML/WXSS/JS）
- [ ] 榜单排序算法优化（当前为热度加权：`hot + 总点赞×12`）
- [ ] 生产部署：HTTPS、Gunicorn/Uvicorn 多 worker、数据库定期备份

详细开发指引见 `docs/DEV.md`，接口说明见 `docs/API.md`。
