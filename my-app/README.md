# 诗迹山河 · 运行说明

这是「诗迹山河」MVP 第一版，实现「诗词查询 + 展示」功能，诗词原文来自免费的 snowtraces 古诗词 API。

## 项目结构

```
my-app/
└── index.html   # 页面（搜索框 + 诗词卡片，接 snowtraces API）
```

## 如何运行

### 方式一：直接双击打开（最简单）

双击 `my-app/index.html`，浏览器就会打开页面。

> 注意：因为页面要联网调用诗词 API，请确保电脑能正常上网。

### 方式二：用本地服务器打开（推荐，地址栏显示 localhost）

在 `my-app` 文件夹下，用 Node.js 起一个本地静态服务器：

```bash
cd my-app
npx http-server -p 8000
```

或使用 Python：

```bash
cd my-app
python -m http.server 8000
```

然后在浏览器打开：**http://localhost:8000**

## 功能说明

- **诗词查询**：输入诗人姓名（如「李白」「杜甫」「苏轼」），可列出 TA 的全部作品。
- **关键词搜索**：输入诗题关键词（如「静夜思」），可搜到相关诗词。
- **展示**：每首诗词展示原文、作者、朝代、体裁（诗/词/曲）。
- **释义/简析**：暂未收录（后续接入 AI 自动生成）。

## 数据来源

- 诗词原文来自免费开放的 [snowtraces 古诗词 API](https://github.com/snowtraces/poetry-source)，收录诗、词、曲共约 53 万首，无需申请 key。
- 诗词原文属于公有领域（古人作品），无版权问题。
- 释义、赏析等内容因涉及版权，不用他人现成内容，后续用 AI 生成。

## 技术说明

- 当前为纯静态页面（HTML + CSS + JavaScript），直接调用第三方 API，无需后端和数据库。
- 按 TECH_DESIGN.md 规划，后续会升级为「前端 Vue + 后端 Python/Flask + 数据库 SQLite」架构。
