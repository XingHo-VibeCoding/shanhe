# 诗迹山河 · 发布清单（v1.0）

> 用途：每次发布 / 重新部署前，照着这张单子从头到尾走一遍。
> 原则：**检查不过不发布，发布完必须验证**。配套文档：`docs/ROLLBACK.md`（出问题时用）。

---

## 一、版本标记

| 项 | 内容 |
|---|---|
| 当前正式版 | **v1.0** → 提交 `3f3921b` |
| 标记类型 | 附注标签（annotated tag） |
| 建立命令 | `git tag -a v1.0 -m "诗迹山河 v1.0 首个正式版"` |
| 推送命令 | `git push origin v1.0` |
| 验证命令 | `git tag -l`（本地）、`git ls-remote --tags origin`（远端） |

> 规矩：每个对外发布的里程碑都打一个 tag（v1.1、v2.0…），tag 名一旦推上远端就不改。

---

## 二、发布前验证项（五项体检）

一条命令跑完五项（venv python）：

```
C:/Users/23850/.workbuddy/binaries/python/envs/default/Scripts/python.exe my-app/tools/pre-release-check/check.py
```

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 密钥泄露扫描 | 扫描全部文本文件，无密钥形态字符串 |
| 2 | .env 防护 | `.env` 被 .gitignore 覆盖且未被 git 跟踪 |
| 3 | 公网可达 | home / index / detail / footprints / mock 五页全部 HTTP 200 |
| 4 | API 健康 | `/api/health`、`/api/hot`、`/api/favorites`、`/api/checkins` 全部 200 且 ok:true |
| 5 | 资源引用完整 | 页面引用的本地文件全部真实存在 |

**结论必须是「5/5 全部通过，可以发布」才继续**；报告自动存 `.workbuddy/reports/pre-release/`。

另加三件人工确认：

- [ ] `git status --short` 已跟踪文件干净（不夹带未提交改动）
- [ ] `.env`、`poems.db` 等敏感/大文件没被意外 `git add`
- [ ] 要推 GitHub 时，Watt Toolkit 加速器在线（进程 + 443 监听 + hosts 三证齐全）

---

## 三、发布步骤（按顺序）

1. **收尾代码**：确认当天任务全部做完、文件清单核对过
2. **提交**：`git add <文件>` → `git commit -m "Day X｜一句话说明"`
3. **推送 GitHub**：清代理变量后 `git push origin master`（需加速器在线）
4. **打 / 推 tag**（里程碑版才做）：`git tag -a vX.Y -m "..."` → `git push origin vX.Y`
5. **部署上线**：用 WorkBuddy「发布为应用」重新部署 `my-app`（Flask 单端口 5000）
6. **发布后验证**：见下节，全过才算发布成功

> 提醒：**git 推送 ≠ 线上更新**。第 5 步不做，线上永远是旧版。

---

## 四、发布后验证

| 验证项 | 做法 | 通过标准 |
|---|---|---|
| 主页可达 | 浏览器打开 `https://shiji-shanhe.app.workbuddy.host/` | 页面正常渲染 |
| 五项体检复跑 | 再跑一次 `check.py` | 5/5 全过 |
| 功能靶子 | 搜「李」 | 李白《将进酒》排第一（v1.0 特征） |
| 线上接口 | 搜「无名氏」 | 作者字段显示「佚名」 |

> 靶子的意义：能**一眼区分新旧版**，避免"部署了但没生效"的假象。

---

## 五、代码与数据备份方式

### 代码（三重）

| 层 | 方式 |
|---|---|
| 主备份 | GitHub 远端仓库 `XingHo-VibeCoding/shanhe`（master 分支 + tag） |
| 本地 | 工作区 `C:\Users\23850\WorkBuddy\vibe coding\my-app`（每天收尾 push） |
| 里程碑 | tag 固定版本点，随时可 `git checkout v1.0` 回看 |

### 数据

| 数据 | 备份方式 | 节奏 |
|---|---|---|
| `poems.db`（32.6 万首，*.db 不进 GitHub） | 复制一份带日期：先建 `backups/` 文件夹，再 `cp my-app/poems.db backups/poems-YYYYMMDD.db` | 大规模导数据后必做，平时每周一次 |
| 云数据库（checkins / favorites） | CloudBase 控制台 → 数据库 → 对应集合 → 导出 | 改动云函数数据结构前做 |
| `.env`（SiliconFlow 等密钥） | **绝不进 git**；在本地安全位置（密码管理器/加密盘）另存一份 | 密钥变更时 |

### 红线

- 密钥、`.env`、数据库连接串：不进代码、不进提交
- 恢复任何数据前，先备份当前状态（见 `ROLLBACK.md` 路径 C）
