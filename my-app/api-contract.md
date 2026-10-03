# 诗迹山河 · 接口契约（API Contract）

> 本文档是「诗迹山河」前后端之间的接口约定书：前端按这里的路径和参数调用，后端按这里的数据结构返回。
> 前后端各自照着这份文档写代码，就不会出现「参数对不上 / 字段读不到」的接不上问题。
>
> - 更新日期：2026-10-03（Day 15）
> - 状态图例：✅ 已上线可用　⏳ 待实现（Day 16–20）

---

## 1. 通用约定

### 1.1 Base URL（两个公网地址）

| 用途 | 地址 |
|------|------|
| 后端接口（云函数网关） | `https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com` |
| 前端页面（静态托管） | `https://shijishanhe-d5gmc8a0k01b1e88d-1500007936.tcloudbaseapp.com` |

> 本文档中所有 `GET /xxx` 都指「后端 Base URL + 路径」，例如 `/api/health` 完整地址为
> `https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com/api/health`。

### 1.2 通用返回结构（业务接口共用）

业务接口（搜索 / 推荐）统一返回以下顶层结构：

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
| `ret_code` | string | `"0"` 成功，`"-1"` 失败（配合 `remark` 说明原因） |
| `match_type` | string | 结果来源：`db`（本地库）/ `apihz`（古诗文 API 兜底）/ `titles`（标题列表）/ `recommend`（推荐） |
| `allNum` | number | 符合条件的总条数 |
| `poemInfo` | array | 单首诗词数组，结构见 §3 |
| `poetInfo` | object | 可选，作者简介（含 `name` / `dynasty` / `intro`） |

### 1.3 错误处理约定

- 业务成功：`ret_code = "0"`，HTTP 状态码 200。
- 业务失败：`ret_code = "-1"`，附 `remark` 字段说明原因（如「请输入诗人名或诗词名」），HTTP 状态码 400 或 500。

---

## 2. 接口清单

### 2.1 健康检查 ✅ 已上线

**`GET /api/health`**

后端探活接口，不做业务，只回答「我在，现在几点」。前端 / 手机端用它确认后端是否真的活着。

**返回示例**

```json
{
  "status": "ok",
  "service": "shiji-shanhe-api",
  "time": "2026-10-03T12:56:14.126Z"
}
```

| 字段 | 说明 |
|------|------|
| `status` | `"ok"` 表示服务正常 |
| `service` | 服务标识 |
| `time` | 服务器当前时间（ISO 8601），证明是「此刻真实运行」而非缓存 |

---

### 2.2 搜索 ⏳ 待实现（Day 16–20）

**`GET /api/search`**

核心搜索接口，接收关键词自动判断是「诗人名」还是「诗名」。

**请求参数（Query）**

| 参数 | 必填 | 说明 |
|------|------|------|
| `keyword` | 是* | 关键词，可为诗人名或诗名，自动判断 |
| `title` | 否 | 明确按诗名查（优先级最高） |
| `page` | 否 | 页码，默认 1，每页 20 条 |

> * `keyword` 与 `title` 至少提供一个。

**返回**：见 §1.2 通用结构；`poemInfo` 为命中诗词列表。

---

### 2.3 推荐 ⏳ 待实现（Day 16–20）

**`GET /api/recommend`**

首页 / 查询页无输入时展示的名篇推荐。

**请求参数**：无（可选 `limit`，默认 8）。

**返回**：见 §1.2 通用结构，`match_type = "recommend"`，`poemInfo` 为 8 首名篇（优先带译文，按知名度降序）。

---

### 2.4 标题联想 ⏳ 待实现（Day 16–20）

**`GET /api/suggest`**

用户输入前几个字时，返回匹配的完整篇名下拉建议。

**请求参数**

| 参数 | 必填 | 说明 |
|------|------|------|
| `q` | 是 | 输入的关键词（如「临江仙」「水调歌」） |

**返回示例**

```json
{
  "ret_code": "0",
  "suggestions": [
    { "title": "临江仙·滚滚长江东逝水", "poet": "杨慎", "dynasty": "明" }
  ]
}
```

匹配规则：先「标题以关键词开头」（前缀优先），再「标题包含关键词」，去重后最多 20 条。

---

### 2.5 诗词详情 ⏳ 待实现（Day 16–20）

**`GET /api/search?title=<诗名>`（现状复用）**

详情页通过 `title` 精确匹配拿单首完整数据，取 `poemInfo[0]` 渲染五件套（原文/译文/注释/背景/赏析）。

> 备注：Day 16–20 可评估是否抽出专门接口 `GET /api/poem/:id`（按 `poemId` 查），当前复用 `/api/search?title=` 即可。

---

## 3. 数据模型：单首诗词（poemInfo 元素）

| 字段 | 类型 | 说明 |
|------|------|------|
| `poemId` | string | 诗词唯一标识（本地库 poem_id） |
| `title` | string | 诗名 |
| `poet` | string | 作者 |
| `dynasty` | string | 朝代 |
| `content` | string | 原文 |
| `translation` | string | 译文（可能为空，覆盖未达 100%） |
| `annotation` | string | 注释（可能为空） |
| `background` | string | 创作背景 |
| `appreciation` | string | 赏析 |

**五件套约定**（前端展示最低要求）：原文 `content` / 译文 `translation` / 注释 `annotation` / 作者 `poet` / 朝代 `dynasty`。

---

## 4. Day 16–20 待办清单

- [ ] 把 §2.2–2.5 的业务接口部署为云函数（迁移 `server.py` 的本地逻辑 + `poems.db` 数据）
- [ ] 接入云数据库（CloudBase PostgreSQL）存储诗词数据
- [ ] 跨域配置（前端页面调后端接口的 CORS）
- [ ] 前端从 mock 假数据切换为真实接口调用
