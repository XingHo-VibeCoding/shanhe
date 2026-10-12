---
name: pre-release-check
description: 诗迹山河发布前检查 Skill。每次发布/推送前手动运行，五项体检：密钥泄露、.env 防护、公网可达、API 健康、资源引用完整。零第三方依赖，整个文件夹拷走即可复用到其他项目。
---

# 发布前检查 Skill（pre-release-check）

## 这是什么

一个「发布前体检」脚本：发布网站或推送代码**之前**跑一遍，自动检查五类最容易翻车的问题，逐项报告 ✓/✗，并生成一份带时间戳的报告文件（可截图留证）。

诞生背景（Day 25）：此前踩过的坑——密钥险些外泄、线上页面 404、手机端 API 间歇失败、git 已推送但线上忘了部署。本 Skill 把这些教训固化成机器检查，不再靠人脑记。

## 何时运行

- 每次改完代码准备**发布/重新部署**前
- 每次向 GitHub **推送**前
- 怀疑线上出问题时（快速定位是页面挂了还是接口挂了）

## 怎么运行

在仓库根目录执行（venv python，也可用任何装了标准库的 Python 3.8+）：

```
C:/Users/23850/.workbuddy/binaries/python/envs/default/Scripts/python.exe my-app/tools/pre-release-check/check.py
```

退出码：`0` = 全部通过；`1` = 存在异常（脚本里逐项看哪一项红）。

## 五项检查

| # | 检查项 | 查什么 | 判红条件 |
|---|--------|--------|----------|
| 1 | 密钥泄露扫描 | 扫 my-app 下 html/js/py/json/css/md 里的密钥形态字符串（sk-20位以上、AKID、password/api_key/secret/token 赋值） | 任一文件命中 |
| 2 | .env 防护 | .env 必须被 .gitignore 覆盖且未被 git 跟踪 | 任一条件不满足 |
| 3 | 公网可达 | 腾讯云单链接 5 个页面（home/index/detail/footprints/mock）HTTP 200 | 任一非 200 或超时 |
| 4 | API 健康 | 4 个云函数网关（/api/health、hot、favorites、checkins）返回 200 且 ok:true | 任一异常 |
| 5 | 资源引用完整 | 各页面 src/href 引用的本地文件真实存在 | 任一引用指向不存在的文件 |

防误伤设计：`sk-` 后要求 20 位以上连续字母数字，所以文档里写到「sk-」这个模式名不会触发；扫描自动跳过本 Skill 自己的文件和 .env 本体（后者由第 2 项单独管）。

## 结果在哪

- **终端**：直接打印逐项结果 + 结论行（「5/5 全部通过，可以发布」或「N/5 通过，禁止发布」）
- **报告文件**：`.workbuddy/reports/pre-release/report-<日期-时间>.md`（.workbuddy 本就不入库，不会弄脏 git status）

## 换项目复用

1. 把整个 `pre-release-check/` 文件夹拷到新项目的工具目录
2. 改 check.py 开头三处配置：`SITE`（站点首页）、`PAGES`（要检查的页面列表）、`API_BASE`/`APIS`（接口网关）
3. 没有接口的纯静态项目可把 `APIS` 置空；密钥规则不适用可删对应条目

## 验证记录（Skill 自身的证据）

- Day 25（2026-10-12）三轮实跑：
  1. **干净跑**：5/5 全绿（扫 45 个文件、5 页公网 200、4 个 API ok:true、21 个资源引用齐全）；
  2. **负向测试**：向 index.html 第 766 行注入假密钥 `sk-FAKE1234567890abcdef123456`（26 位，符合真实密钥形态），重跑后第 1 项「密钥泄露扫描」**正确报红**，精确定位到 `my-app\index.html:766` 并打印该行内容，结论变「4/5 通过，存在异常，禁止发布」，退出码 1；
  3. **回归**：删除注入行恢复原状，重跑恢复 5/5 全绿。
- 证明：Skill 不会虚报通过——真有问题时能抓出来、能定位、能拦住发布。
- 三份报告存于 `.workbuddy/reports/pre-release/`（report-20261012-171600 / 171630 / 171650.md）。
