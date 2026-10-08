# 第 3 周验收表（Day 15–20）

> 验收日期：2026-10-08 ｜ 项目：诗迹山河 ｜ 验收人：林彬（自查）+ 墨白（交叉验证）
> 判定口径：PASS = 证据可见且可复现；FAIL = 做了但未达标；未执行 = 没做。不使用模糊表述。
> 公网入口：https://shijishanhe-d5gmc8a0k01b1e88d-1500007936.tcloudbaseapp.com/index.html

## 一、逐项验收（对应本周产出）

### 1. schema / seed 脚本 —— **PASS**

| 项目 | 内容 |
|---|---|
| 产出物 | `my-app/db/schema.sql`（79 行，三表：poets/poems/favorites，主键+外键+UNIQUE+CHECK 约束，先删后建可重复执行）、`my-app/db/seed.sql`（39 行，TRUNCATE 后插入名篇种子，可复现）、`my-app/db/gen_seed.py`（130 行，种子生成脚本） |
| 验证方法 | ① 打开文件核对表结构与契约 §2 一致；② 用 `tcb db execute --sql` 对线上库执行 `SELECT 'poets',COUNT(*) ... UNION ALL` 对账 |
| 证据（2026-10-08 19:10 现场取证） | 线上库返回：poets=20、poems=29、favorites=10 —— 三表存在、行数与种子+本周写入吻合（favorites 含 10-08 写入的 id=10《赋得古原草送别》、id=11《黄鹤楼》） |

### 2. GET / POST 公网接口 —— **PASS**

| 项目 | 内容 |
|---|---|
| 产出物 | 三个云函数（`my-app/cloudfunctions/`）：api-health、api-hot、api-favorites（GET 读 / POST 写 / OPTIONS 预检） |
| 验证方法 | ① curl 探活三个接口；② POST 真实写入一条收藏并 GET 读回；③ 重复 POST 验证防重复（409）；④ 坏请求验证错误处理 |
| 证据（2026-10-08 17:36–17:42 现场取证） | 探活：health/hot/favorites 全 **200**；写入：`POST {"poem_id":8}` → **200** 返回 id=10，`GET` 读回列表第一条即《赋得古原草送别》；防重复：重复 POST id=1/2/9 均 **409**「已收藏过这首诗」；坏请求：乱码 body → **400**、缺字段 → **400**、不存在 id=99999999 → **404**，全部中文提示，零 500 |

### 3. 分层重构 —— **PASS**

| 项目 | 内容 |
|---|---|
| 产出物 | git commit `2b4bcad`（Day 19）：新增 `my-app/db_access.py`（181 行，数据访问层）+ `my-app/server.py` 改造（-74/+180，业务逻辑与 SQL 分离） |
| 验证方法 | ① `git show 2b4bcad --stat` 看改动实物；② 重构后全接口回归 |
| 证据 | git show 输出：`db_access.py | 181 ++++`、`server.py | 180 +++++---`；回归：Day 19 当日三接口全绿（当日日志），今日 10-08 三接口复验仍全 200 |

### 4. 公网检查台 URL —— **PASS**

| 项目 | 内容 |
|---|---|
| 产出物 | CloudBase 静态托管的公网页面（含「检查台」：health / hot / favorites 三状态灯），Day 20 部署上线 |
| 验证方法 | ① curl 页面确认 200 且含检查台标记；② 页面源码反查接口地址是否公网；③ Day 20 用户 F12 亲验请求 URL 与 CORS 头 |
| 证据 | curl：`GET /index.html` → **200**（10,975 字节 / 0.6s）；源码中接口地址为 `https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com`（非 localhost）；CORS：响应头 `Access-Control-Allow-Origin: *`（Day 20 F12 截图 + 今日带 Origin 复验一致） |

### 5. api-contract.md 完整性 —— **PASS（含 1 处状态滞后，如实记录）**

| 项目 | 内容 |
|---|---|
| 产出物 | `my-app/api-contract.md`：Base URL、通用约定、三表设计、10 个接口（4 个 ✅ 已上线 + 6 个 ⏳ 占位登记）、数据模型（五件套）、实施顺序 |
| 验证方法 | ① 已上线接口 ↔ 云函数源码逐一对照（路径/入参/响应结构/错误码）；② 占位接口是否全部登记不遗漏 |
| 证据 | 逐一对照：health（§3.1）、favorites GET（§3.7）、favorites POST（§3.8，含两层防重复+错误码表）、hot（§3.10）与三个云函数源码**完全吻合**；6 个占位（/api/poems、/:id、/search、/recommend、/suggest、DELETE favorites）全部登记 |
| 如实记录的滞后 | 契约 §5 实施顺序清单中「跨域配置」「前端切换真实接口」两个复选框未勾选，但实际 Day 20 已完成 —— 属文档状态滞后，非功能缺失，已记录待勾选（记录到下周修正） |

## 二、本周未完成项（缺项如实标记）

| 缺项 | 判定 | 说明 |
|---|---|---|
| 3 分钟演示视频 | **未执行** | 余力加练，本周未录，下周补 |
| 收藏取消（DELETE /api/favorites/:id） | **未执行** | 契约已占位登记，属新功能，按规则不越界补 |
| 6 个占位接口实现 | **未执行** | 契约中 ⏳ 状态，属 Day 21 之后任务 |
| sites deploy 线上前端同步 | **未执行** | detail.html 水墨画/配画仅本地+GitHub，线上旧版，已记账下周 |
| api-contract.md §5 两个复选框勾选 | **未执行** | 文档状态滞后（见验收项 5），下周修正 |

## 三、同伴交叉验证三行结论模板

> 同伴照抄这三行、填「通过/不通过 + 一句事实」即可，不需要懂技术。

```
1. 能否打开：在浏览器打开 https://shijishanhe-d5gmc8a0k01b1e88d-1500007936.tcloudbaseapp.com/index.html
   —— 页面能否显示诗词卡片和检查台三个状态灯？（　通过 /　不通过）

2. 能否真实读写：页面上点一首诗收藏（或由演示人现场操作写入）后刷新页面
   —— 收藏数量/列表是否变化且刷新后不消失？（　通过 /　不通过）

3. 有无报错：整个浏览过程中 F12 控制台（或页面本身）有没有红色报错？
   —— （　无报错 /　有报错：__________）
```

**墨白代同伴实际填写（2026-10-08，验证方式与自查不同：Chrome UA 访问 + 源码反查 + 故意坏请求）**：

1. **能否打开**：通过 —— 换 Chrome 真实 UA 访问 200，页面源码引用的接口为公网地址，CORS 头 `*` 放行
2. **能否真实读写**：通过 —— POST 写入 200 且 GET 读回可见（id=10、id=11 两条实证）；重复写入被 409 拒绝
3. **有无报错**：无报错 —— 三类坏请求（乱码/缺字段/不存在 id）返回 400/400/404 中文提示，零 500、零超时

## 四、本周关键产物链接

- 公网页面：https://shijishanhe-d5gmc8a0k01b1e88d-1500007936.tcloudbaseapp.com/index.html
- 接口基地址：https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com
- GitHub：https://github.com/XingHo-VibeCoding/shanhe （master = e7bb458）
- 本周文件：`db/schema.sql`、`db/seed.sql`、`db/gen_seed.py`、`api-contract.md`、`cloudfunctions/api-{health,hot,favorites}/index.js`、`db_access.py`、`mock/index.html`、`docs/` 验收文档
