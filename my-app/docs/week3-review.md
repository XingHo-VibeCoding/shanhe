# 第 3 周验收表（Day 15–20）

> 验收日期：2026-10-08 ｜ 项目：诗迹山河 ｜ 验收人：林彬（自查）+ 墨白（交叉验证）  
> 公网入口：<https://shijishanhe-d5gmc8a0k01b1e88d-1500007936.tcloudbaseapp.com/index.html>

## 一、逐项验收

| #  | 验收项             | 证据形式                    | 证据内容（现场取证时间 2026-10-08 17:36–17:38）                                                                                                       | 结论              |
| -- | --------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| 1  | 公网可访问           | curl 命令输出               | `GET /index.html` → **HTTP 200**，10,975 字节，耗时 0.6s                                                                                        | **PASS**        |
| 2  | 云函数探活           | curl 命令输出               | `/api/health` 200 ｜ `/api/hot` 200 ｜ `/api/favorites` 200                                                                                 | **PASS**        |
| 3  | 真实读取（数据库→接口→页面） | curl + 页面截图（Day 20 打卡图） | `/api/hot?limit=5` 返回 poems 表真实数据（榜首《静夜思》，人气 1 亿）；公网页面渲染同数据，截图含完整地址栏                                                                      | **PASS**        |
| 4  | 真实写入（POST→读回）   | curl 命令输出               | `POST /api/favorites {"poem_id":8}` → **200**，返回 `{"ok":true,"data":{"id":10,...}}`；紧跟 `GET` 读回，列表第一条即《赋得古原草送别》（id=10，白居易·唐代，17:37:26 写入） | **PASS**        |
| 5  | 写入防重复           | curl 命令输出               | 重复 `POST {"poem_id":2}`、`{"poem_id":1}` 均被拒 → **HTTP 409**，`"已收藏过这首诗"`（应用层先查后插 + 数据库 UNIQUE 约束双层防护）                                       | **PASS**        |
| 6  | 跨域配置            | F12 截图（Day 20）          | 页面域 `tcloudbaseapp.com` → 接口域 `service.tcloudbase.com`，响应头 `Access-Control-Allow-Origin: *`（用户 F12 亲验，见 Day 20 打卡截图）                      | **PASS**        |
| 7  | 数据库变、页面跟着变      | 操作记录（Day 20）+ Day 20 截图 | `UPDATE poems SET title='静夜思·改过' WHERE id=1` 后公网强刷即变，随后已还原。操作日志：`.workbuddy/memory/2026-10-07.md`                                         | **PASS**        |
| 8  | 代码分层与回归         | git 提交                  | `2b4bcad` Day 19｜拆出数据访问层，全接口回归通过（本地三接口全绿）                                                                                                 | **PASS**        |
| 9  | 响应格式统一          | curl 命令输出（见第 4/5 项）     | 所有响应均为 `{ok, data, error}` 三字段；成功 `ok:true`，失败带中文 `error`                                                                                 | **PASS**        |
| 10 | 无报错演示           | 演示走通记录（`docs/demo-outline.md`） | 按提纲四段完整走通：首页 200 → health/hot 正常 → POST 黄鹤楼 200 并读回 → 重复 409 → 乱码 400，全程无报错 | **PASS**        |

## 二、缺项如实标记

| 缺项                    | 状态            | 说明                                                                                 |
| --------------------- | ------------- | ---------------------------------------------------------------------------------- |
| 3 分钟演示视频              | **FAIL（未执行）** | 属余力加练，本周未录。已记录，下周补                                                                 |
| 收藏取消功能                | **FAIL（未实现）** | favorites 只有写入无删除，属新功能，按规则不越界补                                                     |
| 详情页线上版同步 sites deploy | **FAIL（未部署）** | detail.html 的水墨画/暮江吟配画仅本地与 GitHub，线上 shiji-shanhe.app.workbuddy.host 仍是旧版。已记账，下周处理 |

## 三、本周关键产物链接

- 公网页面（CloudBase 静态托管）：<https://shijishanhe-d5gmc8a0k01b1e88d-1500007936.tcloudbaseapp.com/index.html>
- 接口基地址：<https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com> （/api/health、/api/hot、/api/favorites）
- GitHub：<https://github.com/XingHo-VibeCoding/shanhe> （master = 5e8559e）
- 云函数源码：`my-app/cloudfunctions/api-health|api-hot|api-favorites/index.js`

## 四、同伴交叉验证结论（墨白，2026-10-08 17:39–17:41）

> 验证方式与自查不同：换 Chrome 真实 UA 访问、从公网页面源码反查接口地址、带页面 Origin 核对 CORS 头、故意发三类坏请求看会不会崩。

1. **可打开**：公网页面用浏览器 UA 访问 200，页面源码里引用的接口地址就是公网 `service.tcloudbase.com`（不是 localhost），CORS 头 `Access-Control-Allow-Origin: *` 放行 —— **通过**
2. **可读写**：读（/api/hot、/api/favorites 返回真实库数据）+ 写（POST id=8 → 200 且读回可见）+ 防重复（重复 POST → 409）—— **通过**
3. **无报错**：三类坏请求（乱码 body → 400、缺字段 → 400、不存在 id → 404）全部返回统一 `{ok:false, error:中文提示}`，无一次 500 或超时 —— **通过**
