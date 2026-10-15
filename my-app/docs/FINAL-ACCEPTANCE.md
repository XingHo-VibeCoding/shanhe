# 诗迹山河 · 最终验收表（Day 28 · 结营）

> 验收日期：2026-10-15　公网地址：https://shiji-shanhe.app.workbuddy.host/
> 原则：每项只写实测到的证据；未验证的内容如实标注，不把没验的说成通过。

---

## 一、评分表（按附录 J，8 项 / 100 分）

| 项目 | 分值 | 结果 | 通过证据（2026-10-15 实测） |
|---|---|---|---|
| 提示词理解与改写 | 20 | **PASS** | 3 条以上实际改写：① Day 27 整句搜索修复（差提示词"把搜索做好一点" → 按【现象/复现/期望/约束】模板改写 → 整句兜底上线，0 结果变苏轼名篇，对照见 `docs/TRIAL-SCRIPT.md`）；② Day 25 发布前检查 Skill（明确"五项体检 + 故意埋坑要能抓出来"的验收标准）；③ Day 26 发布 v1.0 + 回滚演练（按清单口径锁定回退目标与编号规则）；④ 本验收表按附录 J 原文逐项对应。复盘：`docs/FINAL-RETRO.md`（结营复盘，归档中）。 |
| 前端页面与交互 | 15 | **PASS** | 5 个页面全部 200（首页/搜索/详情/足迹/检查台）；反馈交互线上实测：联想下拉 30 元素、关键词标红 23 处、搜索历史、相关诗人条、删除二次确认；移动端截图：`probe-day28-mobile-home.png`、`probe-day28-mobile-checkins.png`（390px 视口实拍）。 |
| 云函数与 API | 15 | **PASS** | 健康：`/api/health` 200 ok:true（"service: shanhe"）；读取：`/api/checkins`、`/api/hot`、`/api/favorites` 全 200；写入：POST 打卡 ok（id=8/9）；**错误响应实测**：缺 poem_id → 400「缺少必填字段 poem_id（诗词 ID，正整数）」；PATCH/DELETE 不存在的 id → 404「打卡记录不存在」，中文人话报错。 |
| 云数据库（PostgreSQL） | 15 | **PASS** | 初始化：chinese-poetry 开源数据 32.6 万首导入（`import_poetry.py`），CloudBase 侧 poems 表供 /api/hot 查询；真实读写：两轮打卡 增→查→改→删 全绿（第 1 轮 7.9s / 第 2 轮 3.3s）；持久化：写入后重新 GET 记录仍在，DELETE 后确认消失。 |
| 第三周周成果 | 10 | **PASS** | 云端数据服务 v1：四个云函数（api-checkins/hot/favorites/health）走公网网关；检查台 `mock/index.html` 线上可用（探活面板 + 热门榜 + 打卡增删改查）；周成果文档 `docs/week3-review.md`；演示证据见 `docs/FINAL-DEMO-OUTLINE.md`。 |
| Skill 与测试 | 10 | **PASS** | Skill 调用：`tools/pre-release-check/check.py` 今日实跑 5/5 全过（Day 25 建）；**故意失败**：Day 25 负向测试，向 index.html 注入假密钥后第 1 项正确报红并定位行号（记录在 SKILL.md「验证记录」）；Bug 修复与回归：Day 24 手机端搜索间歇失败（fetchRetry）+ Day 27 整句兜底（回归测李白/月/王/将进酒全部正常）。 |
| 线上发布 | 10 | **PASS** | 公网地址可访问（HTTP 200，实测 0.5s）；线上真实读写（两轮 CRUD 走公网网关）；检查与数据库证据：`.workbuddy/reports/pre-release/report-20261014-*.md`、`report-20261015-*.md` + 本表 CRUD 记录；版本标记 v1.0 已推 GitHub（refs/tags/v1.0 = 3f3921b）。 |
| 额度、到期和备份 | 5 | **PASS**（1 项待填） | 计费状态：CloudBase 本月消费 0.00 元、可用余额 0.00（2026-10-15 控制台截图）；风险已文档化：万维易源免费额度剩 81 次约撑 5 天（超额仅影响兜底层）；数据导出说明：`docs/CLOUDBASE-RESOURCE-CHECK.md`（checkins 导出步骤 + poems.db 带日期复制）。**待填：CloudBase 套餐到期/重置具体日期**（需登录控制台套餐页查看，本表如实标注）。 |

**自评小结**：8 项全部 PASS；唯一扣分风险在第 8 项的「到期时间待填」——补看一眼控制台套餐页即可补齐，不影响任何主流程。

---

## 二、我的项目与能力底线对应表

| 能力底线 | 我的项目对应功能 | 证据 |
|---|---|---|
| 至少 3 个页面/视图 | 首页 / 搜索页 / 详情页 / 足迹页 / 检查台（共 5 个） | 发布前检查第 3 项逐页 200；线上地址见页眉 |
| 至少 1 个有反馈的交互 | 搜索联想下拉 + 关键词标红 + 相关诗人条 + 搜索历史 + 打卡增删改查（含二次确认） | playwright 线上探针数据（见评分表第 2 项） |
| 至少 1 类数据真实写入并读取 | 学习打卡（checkins）走云函数写入 PostgreSQL 并可查/改/删 | 两轮 CRUD 实测记录（见第三节） |
| 前端、云函数和数据库完整链路 | 页面 → tcloudbase.com 公网网关 → 4 个云函数 → CloudBase 数据库 | 发布前检查第 4 项四接口 ok:true；CRUD 走同链路 |
| 一次公网发布 | WorkBuddy sites 部署，v1.0 版本标记已推 GitHub | 主站 200；refs/tags/v1.0 = 3f3921b |
| 刷新后数据仍存在 | 打卡记录跨刷新持久化 | 两轮"写入 → 重新 GET 仍在"均验证 |
| 额度、到期和备份已记录 | `docs/CLOUDBASE-RESOURCE-CHECK.md`（含资源与到期说明表）+ ROLLBACK.md 备份红线 | 文档在库；计费 0 元截图 |
| 能解释提示词和验证方式 | `docs/TRIAL-SCRIPT.md` 修复提示词模板 + `docs/FINAL-DEMO-OUTLINE.md` 第 3、4 段 | 演示时可当场打开 |

---

## 三、结营交付清单

| 交付物 | 状态 | 位置 |
|---|---|---|
| 公网地址 | ✅ | https://shiji-shanhe.app.workbuddy.host/ |
| 代码仓库链接 | ✅ | https://github.com/XingHo-VibeCoding/shanhe（master + tag v1.0） |
| 3~5 分钟演示录屏 | ⏳ 待录 | 提纲已备好：`docs/FINAL-DEMO-OUTLINE.md`（约 4 分半） |
| 最终验收表和项目映射表 | ✅ | 本文件第一、二节 |
| 一条最有效的改写提示词 | ✅ | Day 27 整句搜索修复（`docs/TRIAL-SCRIPT.md` 第三节有全文） |
| 运行和技术路线说明 | ✅ | 本文件第四节 |
| 数据库、部署、额度、到期和备份说明（不含密钥） | ✅ | `docs/CLOUDBASE-RESOURCE-CHECK.md` + `docs/ROLLBACK.md`（到期日期 1 项待填） |
| 200 字以内结营总结 | ⏳ 待写 | 等"最大认知改变"定稿后一并产出（候选 A/B/C/D 已给） |

---

## 四、运行与技术路线说明

**本地运行**：
```
cd my-app
C:/Users/23850/.workbuddy/binaries/python/envs/default/Scripts/python.exe server.py   # Flask，5000 端口
```
依赖：flask / requests / flask_cors（隔离 venv）；数据：本地 `poems.db`（32.6 万首）。

**技术路线**：
- 前端：原生 HTML/CSS/JS 多页站（home / index / detail / footprints / mock），传统色古风主题，动画仅 transform/opacity
- 后端：Flask（server.py + db_access.py 分层），本地 SQLite 全文搜索（搜索顺序：作者篇名组合 → 单字姓氏聚合 → 诗人名 → 诗名 → 整句兜底 → apihz 兜底）
- 云端：腾讯云 CloudBase，静态思路收敛为 Flask 单端口托管 + 4 个云函数（打卡/热门/收藏/健康）+ PostgreSQL
- 发布：WorkBuddy sites 一键部署到 workbuddy.host；GitHub 组织仓库 master + tag v1.0
- 质量设施：发布前检查 Skill（5 项体检）、回滚手册（真实演练 73s/55s）、验收表（本文件）

---

## 附：两轮核心流程重复检测记录（2026-10-15）

| 轮次 | 耗时 | 写入 | 刷新后仍在 | PATCH 改已完成 | DELETE 后消失 |
|---|---|---|---|---|---|
| 第 1 轮 | 7.9s | ok（id=8） | ✅ | ✅ | ✅ |
| 第 2 轮 | 3.3s | ok（id=9） | ✅ | ✅ | ✅ |

测试走线上公网网关（与前端同链路），测试数据已全部删除。
