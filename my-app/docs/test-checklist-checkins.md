# 诗迹山河 · 核心流程测试清单（打卡链路）

> 测试对象：检查台 `https://shijishanhe-d5gmc8a0k01b1e88d-1500007936.tcloudbaseapp.com/mock/index.html`
> 链路：页面 → 公网网关 → 云函数 `api-checkins` → CloudBase 数据库（`checkins` 表，JOIN `poems`/`poets` 带出诗名作者）
> ⚠️ 澄清：库里有 `plan_days` 表（Day 21 schema），但**本链路不读它**——检查台实际依赖 `poems` + `checkins`，按本清单测即可。
> 工具：浏览器 F12（Console + Network）；备用 `curl`（每条原因附命令）。
> 问题反馈格式：【现象 / 复现步骤 / 报错原文 / 已尝试动作】

---

## 一、核心链路测试步骤（按序执行，每步留证）

| # | 操作 | 预期现象 | 证据留法 |
|---|------|----------|----------|
| T0 | 打开检查台网址 | 页面正常渲染，无红字「加载失败」 | 整页截图（含地址栏） |
| T1 | 观察自动加载 | ①四行检查台全绿（health/hot/favorites/checkins）②诗词卡片出现 ③打卡下拉框有诗可选 ④打卡列表显示（或「还没有打卡记录」） | 四行全绿截图 + F12 Network 里 `GET /api/checkins` 返回 200 |
| T2 | 选一首诗 → 点「＋ 打卡」 | alert 不弹出；列表立刻出现新记录，状态「学习中」 | F12 看到 `POST /api/checkins` 200 + 响应体里有新 id（记下这个 **id**，后面步骤要用） |
| T3 | **按 F5 刷新页面** | 新记录**还在**（持久化成立的铁证） | 刷新后列表截图（同一 id 可见） |
| T4 | 点该记录的「标记完成」 | 状态原地变「已完成」，按钮文字变「退回学习中」 | F12 看到 `PATCH /api/checkins?id=N` 200，响应含 `before/after` 对照 |
| T5 | 点「删除」→ confirm 弹窗点确定 | 该记录从列表消失 | F12 看到 `DELETE /api/checkins?id=N` 200，响应含 `deleted` 对象 |
| T6 | 再按 F5 | 记录确实已不在（删除持久化） | 刷新后列表截图 |

### 边界快测（可选加练，刁钻输入）
| # | 操作 | 预期 |
|---|------|------|
| E1 | 不选诗（下拉空/值清空）直接点「＋ 打卡」 | alert 中文提示（poem_id 校验 400），**不**产生脏数据 |
| E2 | 快速连点「＋ 打卡」3 次 | 最多多出重复记录但不报 500；属已知可接受行为（记录下来，不当场修） |
| E3 | F12 Console 手动执行：对已删除的 id 再发 DELETE | 返回 404「打卡记录不存在（id=N），无需删除」——不静默成功 |

---

## 二、故障原因排序 → 验证方法 → 修复方案

> 按历史踩坑概率从高到低排序。先看 F12 Network 里**哪条请求红了、状态码多少**，对号入座。

### 现象 A：页面本身打不开（白屏/404）
| 排序 | 可能原因 | 验证方法 | 修复方案 |
|---|---|---|---|
| 1 | 域名输错（漏子域名 `shijishanhe-d5gmc8a0k01b1e88d-1500007936`） | 对照本清单开头的完整网址 | 用完整网址重新收藏 |
| 2 | 本地浏览器缓存了坏响应 | Ctrl+F5 强刷；或无痕窗口打开 | 强刷即可 |

### 现象 B：四行检查台有红行（某云函数不通）
| 排序 | 可能原因 | 验证方法 | 修复方案 |
|---|---|---|---|
| 1 | 云函数被重新部署时**丢了 HTTP 触发器**（Day 22 踩过：裸部署 os error 11001） | `tcb fn list` 看函数存在；浏览器直开 `https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com/api/checkins`，404/空 = 触发器丢 | 删函数后按老命令重部署：`tcb fn deploy apiCheckins --dir cloudfunctions/api-checkins --path /api/checkins --runtime Nodejs20.19 --install-dependency true --force`（管道喂 `y`） |
| 2 | 平台冷启动首请求失败 | 原样再点一次「重试」/刷新 | 若频发→给该函数也加保活 ping |
| 3 | 函数代码抛错（看 F12 Console） | 直开网关 URL 看返回体：`{"ok":false,"error":"..."}` 中文提示即函数活着但业务报错 | 按 error 文案对号入座 |

### 现象 C：`GET /api/checkins` 红（500 或超时）
| 排序 | 可能原因 | 验证方法 | 修复方案 |
|---|---|---|---|
| 1 | 数据库连接/权限异常（rdb 初始化失败） | 直开网关 URL，若返回「数据暂时不可用，请稍后再试」= GET 的 error 分支 | 腾讯云控制台查 CloudBase 数据库状态与 rdb 权限；看云函数日志（控制台 → 函数 → 日志检索）|
| 2 | `checkins` 表或 JOIN 的 `poems`/`poets` 表缺失 | 控制台数据库里确认三张表存在；`db/schema.sql` 可重建 | 重跑 schema（注意别 DROP 已有数据）|

### 现象 D：打卡失败（POST 红）
| 排序 | 可能原因 | 验证方法 | 修复方案 |
|---|---|---|---|
| 1 | poem_id 没传上（下拉框空值） | 看响应体：400「缺少必填字段 poem_id」即前端传参问题 | 检查下拉框取值逻辑（`ckPoem.value`）|
| 2 | 诗词 id 在云库不存在（本地 32 万首 vs 云库少量） | 响应体 404「该诗词不存在」 | 下拉框本就来自云库 `/api/hot`，正常不会触发；触发说明 hot 接口换了数据源 |
| 3 | 写库失败（500「写入失败」） | 云函数日志检索看插入错误 | 查 checkins 表字段约束（status CHECK）与权限 |

### 现象 E：打卡「成功」但刷新后消失
| 排序 | 可能原因 | 验证方法 | 修复方案 |
|---|---|---|---|
| 1 | 看错环境——一个页面是本地 Flask（127.0.0.1:8080/5000），另一个是云端 | 看地址栏域名；两个库是**两套独立数据** | 统一只测云端链接 |
| 2 | POST 假成功（响应 ok 但库没写入） | T2 时记下的 id 用 `curl "网关/api/checkins"` 对账 | 云函数日志 `[api-checkins] POST 成功：id =` 有打印但库里没有 → 查数据库事务/权限 |

### 现象 F：修改/删除报 404
| 排序 | 可能原因 | 验证方法 | 修复方案 |
|---|---|---|---|
| 1 | 记录已被删过（重复点删除/别人删了） | 响应体：「打卡记录不存在（id=N）」 | 属正常防御行为，刷新列表用新 id 即可 |
| 2 | id 解析失败（400「缺少记录 id」） | 看 Network 请求 URL 是否带 `?id=N` | 检查前端拼参 |

### 现象 G：F12 Console 见 CORS/Mixed Content 报错
| 排序 | 可能原因 | 验证方法 | 修复方案 |
|---|---|---|---|
| 1 | 云函数响应头丢失（重部署覆盖了代码） | `curl -s -D - -o /dev/null 网关/api/checkins` 看是否含 `Access-Control-Allow-Origin: *` | 确认部署的是仓库里的 index.js（含 headers 定义）再重部署 |
| 2 | 页面用了 http 而接口是 https | 看地址栏协议 | 统一 https |

---

## 三、回归验证清单（修复后用同一清单重跑）

1. 按 **T0→T6 全流程**重跑一遍（用新的 id 留证）
2. 边界快测 E1/E3 各跑一次（确认修复没破坏防御逻辑）
3. 填写前后对照表：

| 步骤 | 修复前（现象/报错原文） | 修复后（现象） | 结论 |
|------|------------------------|----------------|------|
| T0 | | | PASS/FAIL |
| T1 | | | |
| T2 | | | |
| T3 | | | |
| T4 | | | |
| T5 | | | |
| T6 | | | |

4. 证据归档：修复前截图 2 张 + 修复后截图 2 张，与本文件一起放 `docs/`

## 附：诊断命令速查
```bash
# 列表对账
curl -s "https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com/api/checkins"
# 新增
curl -s -X POST "...../api/checkins" -H "Content-Type: application/json" -d '{"poem_id":1}'
# 修改 / 删除
curl -s -X PATCH "...../api/checkins?id=1" -H "Content-Type: application/json" -d '{"status":"已完成"}'
curl -s -X DELETE "...../api/checkins?id=1"
# CORS 头检查
curl -s -D - -o /dev/null "...../api/checkins" | grep -i access-control
# 函数列表（看部署状态与更新时间）
tcb fn list
```
