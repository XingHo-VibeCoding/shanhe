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


@app.route("/")
def home():
    """直接返回前端页面，让前后端同源，彻底避免跨域"""
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/search")
def search():
    """
    核心搜索接口。
    参数：
      poet   - 诗人名（如「李白」），可选
      title  - 诗词名（如「静夜思」），可选
      page   - 页码，默认 1
    逻辑：优先按诗人名查（先拿 poetId，再查他全部作品）；
          否则按诗词名查。
    """
    poet = request.args.get("poet", "").strip()
    title = request.args.get("title", "").strip()
    page = request.args.get("page", "1")

    if not APPKEY:
        return jsonify({"ret_code": "-1", "remark": "后端缺少 appKey，请检查 .env 文件"}), 500

    # 情况 1：按诗人名查
    if poet:
        return search_by_poet(poet, page)

    # 情况 2：按诗词名查
    if title:
        return search_by_title(title, page)

    return jsonify({"ret_code": "-1", "remark": "请提供诗人名或诗词名"}), 400


def search_by_poet(poet, page):
    """按诗人名：先查诗人拿到 poetId，再查他的全部诗词"""
    # 第一步：查诗人，拿到 poetId
    poet_resp = requests.post(
        f"{SHOWAPI_BASE}/1620-4",
        params={"appKey": APPKEY},
        data={"poet": poet, "maxResult": "5"},
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    poet_data = poet_resp.json().get("showapi_res_body", {})
    if poet_data.get("ret_code") != "0":
        return jsonify({"ret_code": poet_data.get("ret_code"),
                        "remark": poet_data.get("remark", "查诗人失败")}), 500

    poet_list = poet_data.get("poetInfo", [])
    if not poet_list:
        return jsonify({"ret_code": "0", "remark": "未找到该诗人",
                        "poemInfo": [], "allNum": 0})

    # 取第一个匹配的诗人（通常名字是唯一的）
    poet_info = poet_list[0]
    poet_id = poet_info.get("poetId", "")

    # 第二步：按 poetId 查他的全部诗词（分页）
    poem_resp = requests.post(
        f"{SHOWAPI_BASE}/1620-5",
        params={"appKey": APPKEY},
        data={"poetId": poet_id, "page": page, "maxResult": "20"},
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    poem_data = poem_resp.json().get("showapi_res_body", {})

    # 把诗人信息也一并返回，方便前端展示生平
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
