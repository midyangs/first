# 开发与二次开发指南

本文件面向后期维护者，说明代码结构、关键函数与常见改造点。

---

## 一、代码总览

`src/同城榜单.html` 单文件，自上而下分四段：

| 段落 | 内容 | 大致位置 |
|---|---|---|
| `<style>` | CSS 变量主题 + 全部样式 | 文件头部 |
| `<body>` | 6 个视图（home / rank / pub / search / me / detail）+ 底部导航 + 城市弹层 + toast | 中部 |
| `<script>` 数据层 | 常量、SEED 示例数据、state、持久化、工具函数 | 尾部上部 |
| `<script>` 逻辑层 | 视图路由 + 各模块渲染与交互 | 尾部下部 |

---

## 二、关键数据结构

### 榜单对象（rank）

```js
{
  id: 's1',            // 内置榜单 s 开头；用户发布 u + 时间戳
  title: '成都必吃十大苍蝇馆子',
  cat: 'food',         // 'food' | 'fun'
  city: '成都',
  cover: '🌶️',        // 封面 emoji
  grad: 0,             // 封面渐变索引（对应 GRADS 数组）
  desc: '榜单简介',
  views: 12840,        // 浏览量
  hot: 9860,           // 基础热度
  self: 0,             // 1 = 用户自己发布
  entries: [ { n, s, p, r, a, e, tags, likes } ]
}
```

### 条目对象（entry）

```js
{
  n: '明婷饭店',        // 名称
  s: 4.8,              // 评分
  p: '¥35',            // 人均
  r: '脑花豆腐一绝...', // 上榜理由
  a: '锦江区水井坊街',  // 地址
  e: '🍲',             // 图标 emoji
  tags: ['川菜','排队王'],
  likes: 0             // 点赞数
}
```

---

## 三、关键函数索引

### 视图与路由

| 函数 | 作用 |
|---|---|
| `go(view, opts)` | 切换视图；`view` ∈ home/rank/pub/search/me/detail；detail 会自动隐藏底部 tabbar |
| `openDetail(id, opts)` | 打开榜单详情；`opts.keepViews` 可阻止浏览量重复累加 |
| `openCity() / pickCity(c) / closeCity()` | 城市选择弹层 |

### 各模块渲染

| 函数 | 作用 |
|---|---|
| `renderCats()` / `setCat(k)` | 首页分类 chips |
| `renderHome()` | 首页榜单列表 |
| `renderRankCat()` / `renderRankList()` | 榜单广场 |
| `renderMe()` / `showMine(type)` | 我的页统计与列表 |
| `doSearch()` | 搜索渲染 |

### 交互

| 函数 | 作用 |
|---|---|
| `toggleLike(rid, idx, ev)` | 条目点赞（**局部更新 DOM**，不整页重绘，保持滚动位置） |
| `toggleFav()` | 收藏榜单 |
| `addEntry() / delEntry(id) / renumber()` | 发布页条目编辑器 |
| `submitRank()` | 提交发布 |
| `clearAll()` | 清除本地数据 |

### 工具与算法

| 函数 | 作用 |
|---|---|
| `loadUser()` / `saveUser()` | localStorage 读写 |
| `hotOf(r)` | **热度算法**：`(r.hot \|\| 0) + 总点赞数 × 12` |
| `totalLikes(r)` | 榜单总点赞数 |
| `gradOf(r)` | 取封面渐变 |
| `fmtNum(n)` | 数字格式化（1.3w） |
| `esc(s)` | XSS 转义（所有用户输入输出都应经过它） |

---

## 四、常见改造点

### 1. 调整主题色

修改 `:root` 中的 CSS 变量：

```css
:root{
  --primary:#FF6B00;          /* 主色 */
  --primary-light:#FF8A2B;
  --primary-grad:linear-gradient(135deg,#FF8A00 0%,#FF5E00 100%);
}
```

### 2. 修改热度算法

找到 `hotOf()`：

```js
function hotOf(r){ return (r.hot||0) + totalLikes(r)*12; }
```

点赞权重 `12` 可按需调整；若要加入浏览量权重，改成
`(r.hot||0) + totalLikes(r)*12 + (r.views||0)*0.1`。

### 3. 新增分类（如「购物」「景点」）

需要改 3 处：

1. `HOME_CATS` 和 `RANK_CATS` 数组增加项
2. `catName(c)` 增加映射：`c==='shop'?'购物':...`
3. 发布页 `#pubCat` 增加一个 `.seg-item`，`data-v="shop"`

### 4. 新增城市

1. `CITIES` 数组加城市名
2. 如需该城市有内置数据，在 `SEED` 中新增榜单对象（`city` 字段填新城市名）

### 5. 增加内置示例榜单

在 `SEED` 数组中追加对象即可，注意：
- `id` 不能重复
- `grad` 取值 0–9（对应 `GRADS` 长度）
- 记得给 `entries` 里每个条目加 `tags` 数组

### 6. 换掉 emoji 占位图，改用真实图片

当前 `cover` 和 `entry.e` 是 emoji，配 `gradOf()` 渐变底色。改造思路：

```js
// 数据里增加 img 字段
{ cover:'🌶️', img:'https://cdn.example.com/cover.jpg' }

// 渲染处改为
`<div class="rc-cover" style="background:${gradOf(r)}">
   ${r.img ? `<img src="${esc(r.img)}" style="width:100%;height:100%;object-fit:cover">` : `<span>${r.cover}</span>`}
 </div>`
```

### 7. 接入后端（重要演进）

当前数据全在 `localStorage`，仅本机可见。要多人共享数据，需替换 `loadUser` / `saveUser` 为 API 调用：

```js
// 伪代码
async function loadRanks(){ state.ranks = await fetch('/api/ranks').then(r=>r.json()); }
async function saveUser(){ await fetch('/api/likes', {method:'POST', body: JSON.stringify({...})}); }
```

推荐方案：**微信云开发**、**LeanCloud**、**Supabase**（都有免费额度，且提供现成的登录/存储）。

---

## 五、工程化重构建议（可选）

当前单文件约 1000 行，若继续膨胀，建议拆分：

```
src/
├── index.html
├── css/
│   ├── base.css        变量、重置、通用组件
│   └── views.css       各视图样式
├── js/
│   ├── store.js        state + 持久化
│   ├── data.js         SEED + 常量
│   ├── router.js       视图路由
│   ├── views/          home.js / detail.js / pub.js ...
│   └── utils.js        工具函数
└── assets/
```

拆分后建议引入 Vite 打包，但**注意**：拆分前请确认目标是浏览器直接打开还是要工程化部署，若主要面向「双击即用」的分发场景，保持单文件反而更优。

---

## 六、迁移为微信小程序

单文件 H5 迁移到小程序的核心映射：

| H5 | 微信小程序 |
|---|---|
| `<div>` | `<view>` |
| `<span>` | `<text>` |
| `onclick="fn()"` | `bindtap="fn"` |
| `localStorage` | `wx.setStorageSync / getStorageSync` |
| CSS 类名 | 基本通用（flex 布局可直接迁移） |
| `<input>` | `<input bindinput="...">` |

建议新建小程序工程后，**按视图逐个迁移**（先首页，再详情页），复用本项目的 CSS 与数据结构，逻辑层 JS 改动不大。

---

## 七、已知限制

1. 数据仅存本地，跨设备不同步（需接后端）
2. 无用户登录体系，所有行为匿名
3. 图片为 emoji 占位，未接入真实图床
4. 搜索为前端内存过滤，数据量大时需改服务端搜索
5. 点赞无防刷机制，仅前端记录

---

## 八、验证清单（改完后自测）

- [ ] 首页分类切换正常，榜单卡片渲染无报错
- [ ] 点击榜单进入详情，名次排列正确
- [ ] 条目点赞数字变化，刷新后仍在
- [ ] 发布新榜单，返回首页可见
- [ ] 搜索能命中榜单与店铺
- [ ] 「我的」页三项统计准确
- [ ] 刷新浏览器后用户数据保留
- [ ] 移动端宽度下布局正常
