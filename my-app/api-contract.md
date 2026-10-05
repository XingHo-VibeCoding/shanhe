# 诗迹山河 · 接口契约（API Contract）

> 本文档是「诗迹山河」前后端之间的接口约定书，也是**第 3 周建表和写接口的唯一依据**。
> 前端按这里的路径和参数调用，后端按这里的数据结构返回；前后端照这份文档写，就不会「参数对不上 / 字段读不到」。
>
> - 更新日期：2026-10-04（Day 16，第 3 周开始）
> - 状态图例：✅ 已上线可用　⏳ 占位登记（今天只登记，不实现）

---

## 1. 通用约定

### 1.1 Base URL（两个公网地址）

| 用途 | 地址 |
|------|------|
| 后端接口（云函数网关） | `https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com` |
| 前端页面（静态托管） | `https://shijishanhe-d5gmc8a0k01b1e88d-1500007936.tcloudbaseapp.com` |

> 文中所有 `GET /api/xxx` 均指「后端 Base URL + 路径」。

### 1.2 通用响应结构（业务接口共用）

业务接口统一返回以下顶层结构：

```json
{
  "ret_code": "0",
  "match_type": "db",
  "allNum": 20,
  "poemInfo": [ { ...单首诗词... } ],
  "poetInfo": { ...作者简介（可选）... }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `ret_code` | string | `"0"` 成功，`"-1"` 失败 |
| `match_type` | string | 结果来源：`db`（本地库）/ `apihz`（API 兜底）/ `titles`（标题列表）/ `recommend`（推荐） |
| `allNum` | number | 符合条件的总条数 |
| `poemInfo` | array | 单首诗词数组，元素结构见 §4 |
| `poetInfo` | object | 可选，作者简介（`name` / `dynasty` / `intro`） |

### 1.3 错误返回约定

| HTTP 状态码 | 含义 | 返回体 |
|-------------|------|--------|
| 200 | 成功 | 正常数据 |
| 400 | 参数错误（缺关键词等） | `{ "ret_code": "-1", "remark": "原因" }` |
| 404 | 资源不存在 | `{ "ret_code": "-1", "remark": "未找到该诗词" }` |
| 500 | 服务器错误 | `{ "ret_code": "-1", "remark": "服务器内部错误" }` |

---

## 2. 数据表设计（第 3 周建表依据）

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `poems` | 诗词表（核心数据） | `id`, `title`, `poet_id`(外键→poets.id), `dynasty`, `content`, `translation`, `annotation`, `background`, `appreciation`, `popularity` |
| `poets` | 作者表 | `id`, `name`, `dynasty`, `intro` |
| `favorites` | 收藏记录表（用户收藏行为） | `id`, `poem_id`(外键→poems.id), `created_at` |

> 说明：
> - 三表靠外键关联：`poems.poet_id → poets.id`（一对多：一位作者名下多首诗）、`favorites.poem_id → poems.id`（一条收藏对应一首诗）。
> - `favorites` 就是本项目「记录表」——对应课程的「列表读取案例 GET /api/favorites」，用于记录用户收藏了哪些诗。
> - 建表 SQL 见 `db/schema.sql`（先删后建，含主键/外键/约束/字段注释），种子数据见 `db/seed.sql`（先 TRUNCATE 再插入，可复现）。

---

## 3. 接口清单

### 3.1 健康检查 ✅ 已上线

**`GET /api/health`**

不做业务，只回答「服务是否活着」。

**返回示例**

```json
{ "ok": true, "service": "shanhe" }
```

---

### 3.2 诗词列表读取 ⏳ 占位（★列表读取）

**`GET /api/poems`**

分页拉取诗词列表，支持按朝代 / 作者筛选。

**请求参数（Query）**

| 参数 | 必填 | 说明 |
|------|------|------|
| `page` | 否 | 页码，默认 1 |
| `pageSize` | 否 | 每页条数，默认 20 |
| `dynasty` | 否 | 按朝代筛选（如「唐」「宋」） |
| `poet` | 否 | 按作者筛选 |

**响应 JSON 形状**

```json
{
  "ret_code": "0",
  "allNum": 326665,
  "page": 1,
  "poemInfo": [ { ...单首诗词（§4）... } ]
}
```

**错误返回**：400（参数非法）、500。

---

### 3.3 诗词详情 ⏳ 占位

**`GET /api/poems/:id`**

按诗词 ID 取单首完整数据（五件套 + 背景 + 赏析）。

**请求参数（Path）**：`id`（诗词 ID）

**响应 JSON 形状**

```json
{
  "ret_code": "0",
  "poemInfo": { ...单首诗词完整字段（§4）... }
}
```

**错误返回**：404（`id` 不存在）。

---

### 3.4 搜索 ⏳ 占位

**`GET /api/search`**

接收关键词自动判断「诗人名」还是「诗名」。

**请求参数（Query）**

| 参数 | 必填 | 说明 |
|------|------|------|
| `keyword` | 是* | 诗人名或诗名，自动判断 |
| `title` | 否 | 明确按诗名查（优先级最高） |
| `page` | 否 | 页码，默认 1 |

> * `keyword` 与 `title` 至少提供一个。

**响应 JSON 形状**：见 §1.2 通用结构，`poemInfo` 为命中列表。

**错误返回**：400（缺关键词）。

---

### 3.5 推荐 ⏳ 占位

**`GET /api/recommend`**

首页 / 查询页无输入时展示的名篇推荐。

**请求参数**：无（可选 `limit`，默认 8）。

**响应 JSON 形状**：见 §1.2，`match_type = "recommend"`，`poemInfo` 为 8 首名篇。

**错误返回**：500。

---

### 3.6 标题联想 ⏳ 占位

**`GET /api/suggest`**

输入前几个字返回完整篇名下拉建议。

**请求参数（Query）**：`q`（必填，关键词）

**响应 JSON 形状**

```json
{
  "ret_code": "0",
  "suggestions": [
    { "title": "临江仙·滚滚长江东逝水", "poet": "杨慎", "dynasty": "明" }
  ]
}
```

**错误返回**：400（缺 `q`）。

---

### 3.7 收藏列表读取 ✅ 已上线（★记录表读取）

**`GET /api/favorites`**

读取当前用户的收藏记录列表（含对应诗词摘要）。`favorites` 表只存 `poem_id`（外键数字），`title`/`poet` 靠 JOIN `poems`、`poets` 补出。

**请求参数（Query）**：无

**响应 JSON 形状**（第 3 周云函数接口统一 `{ ok, data, error }` 三字段：成功 `ok:true` + `data` 有值 + `error:null`；失败 `ok:false` + `data:null` + `error` 有值）

```json
{
  "ok": true,
  "data": [
    { "id": 1, "poem_id": 1001, "title": "静夜思", "poet": "李白", "dynasty": "唐代", "created_at": "2026-10-04T01:00:00+08:00" }
  ],
  "error": null
}
```

**公网地址**：`GET https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com/api/favorites`

**错误返回**：500。

---

### 3.8 添加收藏 ✅ 已实现（★写入接口，防重复提交）

**`POST /api/favorites`**

添加一条收藏记录。同一首诗只收藏一次，重复提交会被拒。

**请求体（JSON）**

```json
{ "poem_id": 6 }
```

**响应 JSON 形状**（三字段统一）

```json
{
  "ok": true,
  "data": { "id": 7, "poem_id": 6, "created_at": "2026-10-05T08:19:28.06+08:00" },
  "error": null
}
```

**公网地址**：`POST https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com/api/favorites`

**错误返回**（错误提示均为中文）：

| 状态码 | 场景 | error |
|--------|------|-------|
| 400 | 缺 `poem_id` / 非正整数 | 缺少必填字段 poem_id（诗词 ID） |
| 404 | 诗词不存在 | 该诗词不存在 |
| 409 | 重复收藏 | 已收藏过这首诗 |
| 500 | 服务器错误 | … |

**防重复机制（两层）**：① 应用层先查后插，给中文提示；② 数据库 `UNIQUE(poem_id)` 约束兜底，防并发漏判。

---

### 3.9 取消收藏 ⏳ 占位

**`DELETE /api/favorites/:id`**

**请求参数（Path）**：`id`（收藏记录 ID）

**响应 JSON 形状**

```json
{ "ret_code": "0" }
```

**错误返回**：404（记录不存在）、500。

---

### 3.10 热门诗词榜 ✅ 已上线（★真实热搜数据）

**`GET /api/hot`**

按知名度 `popularity` 降序返回热门诗词榜（真实热搜数据，来自同步入 `poems` 表的名篇）。

**请求参数（Query）**

| 参数 | 必填 | 说明 |
|------|------|------|
| `limit` | 否 | 返回条数，默认 10，上限 50 |

**响应 JSON 形状**（三字段统一，同上）

```json
{
  "ok": true,
  "data": [
    { "id": 1, "title": "静夜思", "poet": "李白", "dynasty": "唐代", "content": "床前看月光…", "popularity": 100000000 }
  ],
  "error": null
}
```

**公网地址**：`GET https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com/api/hot`

**错误返回**：500。

---

## 4. 数据模型：单首诗词（poemInfo 元素）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | number | 诗词唯一标识 |
| `title` | string | 诗名 |
| `poet` | string | 作者名（展示字段，由 `poet_id` JOIN `poets.name` 得到） |
| `dynasty` | string | 朝代 |
| `content` | string | 原文 |
| `translation` | string | 译文（可能为空） |
| `annotation` | string | 注释（可能为空） |
| `background` | string | 创作背景 |
| `appreciation` | string | 赏析 |

**五件套约定**（前端展示最低要求）：原文 `content` / 译文 `translation` / 注释 `annotation` / 作者 `poet` / 朝代 `dynasty`。

---

## 5. 第 3 周实施顺序（占位，后续执行）

- [x] 建表：`poems` / `poets` / `favorites`（CloudBase PostgreSQL，含种子数据，见 `db/schema.sql` + `db/seed.sql`）
- [ ] 按 §3 逐个实现接口（先列表读取 → 详情 → 搜索 → 收藏读写）
- [ ] 跨域配置（前端调后端接口的 CORS）
- [ ] 前端从 mock 切换为真实接口
