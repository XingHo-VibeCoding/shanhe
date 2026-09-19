# -*- coding: utf-8 -*-
"""
诗迹山河 - 后端服务（Flask）

作用：
  1. 作为「密钥保险柜」：appKey 只存在本地 .env，不暴露给浏览器、不进 GitHub。
  2. 作为「诗词数据中转」：接收前端请求 → 调万维易源接口 → 返回诗词数据。

启动方式（在 my-app 目录下）：
  python server.py
然后浏览器打开 http://localhost:5000
"""

import os
import json
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# 从 .env 文件读取 appKey（密钥不进代码、不进仓库）
def load_env():
    """读取 my-app/.env 里的环境变量（简单解析，不依赖第三方库）"""
    env = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env

ENV = load_env()
APPKEY = ENV.get("SHOWAPI_APPKEY", "")

app = Flask(__name__)
CORS(app)  # 允许前端跨端口调用（解决浏览器 CORS 拦截）

# 万维易源接口地址（3 个接入点）
SHOWAPI_BASE = "https://route.showapi.com"

# 前端页面所在的目录（与 server.py 同级）
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))

# 标题索引文件（由 fetch_index.py 生成，用于标题前缀联想）
TITLE_INDEX_FILE = os.path.join(FRONTEND_DIR, "title_index.json")

# 启动时加载标题索引（若尚未生成则跳过，联想接口会返回空）
TITLE_INDEX = []
try:
    if os.path.exists(TITLE_INDEX_FILE):
        with open(TITLE_INDEX_FILE, "r", encoding="utf-8") as f:
            TITLE_INDEX = json.load(f)
except Exception as e:
    print(f"⚠️  加载标题索引失败：{e}")
    TITLE_INDEX = []


@app.route("/")
def home():
    """直接返回前端页面，让前后端同源，彻底避免跨域"""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/suggest")
def suggest():
    """
    标题联想接口：根据用户输入的前几个字，返回匹配的完整篇名列表。

    参数：
      q - 用户输入的关键词（如「临江仙」「水调歌」）
    返回：
      { "ret_code": "0", "suggestions": [ {title, poet, dynasty}, ... ] }

    匹配规则：
      1. 先找「标题以关键词开头」的（前缀匹配，最符合直觉）
      2. 再补充「标题包含关键词」的（中间包含）
      最多返回 20 条。
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"ret_code": "0", "suggestions": []})

    if not TITLE_INDEX:
        return jsonify({"ret_code": "0", "suggestions": [],
                        "remark": "标题索引尚未生成，请先运行 fetch_index.py"})

    prefix_hits = []
    contain_hits = []
    seen_titles = set()

    for item in TITLE_INDEX:
        title = item.get("title", "")
        if not title or title in seen_titles:
            continue
        # 前缀匹配（优先级最高）
        if title.startswith(q):
            prefix_hits.append(item)
            seen_titles.add(title)
        # 包含匹配（次优先级，且不重复）
        elif q in title:
            contain_hits.append(item)
            seen_titles.add(title)

    # 前缀优先，包含补充，去重后最多 20 条
    suggestions = (prefix_hits + contain_hits)[:20]

    return jsonify({
        "ret_code": "0",
        "suggestions": [
            {"title": s.get("title"), "poet": s.get("poet"), "dynasty": s.get("dynasty")}
            for s in suggestions
        ],
    })


@app.route("/search")
def search():
    """
    核心搜索接口（智能判断版）。
    参数：
      keyword - 关键词，可以是「诗人名」也可以是「诗名」，自动判断
      poet    - （兼容旧调用）诗人名
      title   - （兼容旧调用）诗词名
      page    - 页码，默认 1

    智能逻辑：收到 keyword 后，先按「诗人名」查；若查不到该诗人，
    就自动改按「诗名」查。这样用户输人名、诗名都能出结果，无需自己区分。
    """
    keyword = request.args.get("keyword", "").strip()
    poet = request.args.get("poet", "").strip() or keyword
    title = request.args.get("title", "").strip()
    page = request.args.get("page", "1")

    if not APPKEY:
        return jsonify({"ret_code": "-1", "remark": "后端缺少 appKey，请检查 .env 文件"}), 500

    # 情况 1：明确给了诗名 → 直接按诗名查
    if title:
        return search_by_title(title, page)

    # 情况 2：按诗人名查（兼容旧调用）；查不到诗人就自动转按诗名查
    if poet:
        return search_smart(poet, page)

    return jsonify({"ret_code": "-1", "remark": "请输入诗人名或诗词名"}), 400


def search_smart(keyword, page):
    """智能搜索：先按诗人名查，查不到该诗人就转按诗名查"""
    # 先尝试按诗人名查（1620-4）
    try:
        poet_resp = requests.post(
            f"{SHOWAPI_BASE}/1620-4",
            params={"appKey": APPKEY},
            data={"poet": keyword, "maxResult": "5"},
            headers={"content-type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        poet_data = poet_resp.json().get("showapi_res_body", {})
    except Exception as e:
        poet_data = {"ret_code": "-1", "remark": str(e)}

    # 若按诗人名查到了，就走诗人作品列表
    if poet_data.get("ret_code") == "0":
        poet_list = poet_data.get("poetInfo", [])
        if poet_list:
            return search_by_poet_with_info(poet_list[0], page)

    # 查不到诗人 → 转按诗名查
    return search_by_title(keyword, page)


def search_by_poet_with_info(poet_info, page):
    """已知诗人信息，查 TA 的全部诗词（分页），并附诗人简介"""
    poet_id = poet_info.get("poetId", "")
    poem_resp = requests.post(
        f"{SHOWAPI_BASE}/1620-5",
        params={"appKey": APPKEY},
        data={"poetId": poet_id, "page": page, "maxResult": "20"},
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    poem_data = poem_resp.json().get("showapi_res_body", {})

    poem_data["poetInfo"] = {
        "poet": poet_info.get("poet"),
        "dynasty": poet_info.get("dynasty"),
        "biography": poet_info.get("biography"),
    }
    return jsonify(poem_data)


def search_by_title(title, page):
    """按诗词名查"""
    resp = requests.post(
        f"{SHOWAPI_BASE}/1620-5",
        params={"appKey": APPKEY},
        data={"title": title, "page": page, "maxResult": "20"},
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    return jsonify(resp.json().get("showapi_res_body", {}))


if __name__ == "__main__":
    if not APPKEY:
        print("⚠️  警告：未在 .env 中找到 SHOWAPI_APPKEY，接口将无法调用。")
    print("诗迹山河后端启动中 → http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
