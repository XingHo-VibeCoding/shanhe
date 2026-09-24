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
import re
import html
import sqlite3
import requests
import urllib3
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
APIHZ_ID = ENV.get("APIHZ_ID", "")
APIHZ_KEY = ENV.get("APIHZ_KEY", "")

app = Flask(__name__)
CORS(app)  # 允许前端跨端口调用（解决浏览器 CORS 拦截）

# 万维易源接口地址（3 个接入点）
SHOWAPI_BASE = "https://route.showapi.com"
APIHZ_BASE = "https://cn.apihz.cn/api/zici/poetry.php"

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

# 诗词正文数据库（由 fetch_content.py 生成，存原文/译文/注释五件套）
DB_FILE = os.path.join(FRONTEND_DIR, "poems.db")


def db_query(sql, params=()):
    """查本地 poems.db（只读）。库不存在时返回空列表。"""
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"⚠️  查询数据库失败：{e}")
        return []


# ===== 古诗文大全（apihz）数据源工具 =====
def clean_html(text):
    """把 apihz 返回的 HTML 文本清洗成纯文本（保留段落换行）"""
    if not text:
        return ""
    text = html.unescape(str(text))
    text = text.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_translation_annotation(raw):
    """从 ywjzsy（译文+注释混排）里拆出「译文」和「注释」两部分"""
    if not raw:
        return "", ""
    marked = str(raw).replace("<strong>译文</strong>", "@TRANS@").replace("<strong>注释</strong>", "@ANNO@")
    text = clean_html(marked)
    t_idx = text.find("@TRANS@")
    a_idx = text.find("@ANNO@")
    translation = ""
    annotation = ""
    if t_idx != -1:
        end = a_idx if a_idx != -1 else len(text)
        translation = text[t_idx + len("@TRANS@"):end].strip()
    if a_idx != -1:
        annotation = text[a_idx + len("@ANNO@"):].strip()
    return translation, annotation


def _apihz_fetch_page(keyword, page):
    """调一页古诗文大全接口，返回 (作品列表, 错误信息)。作品列表为 None 表示出错。"""
    try:
        resp = requests.get(
            APIHZ_BASE,
            params={"id": APIHZ_ID, "key": APIHZ_KEY, "words": keyword, "page": str(page)},
            timeout=20,
            verify=False,
        )
        data = resp.json()
    except Exception as e:
        return None, "古诗文接口调用失败：" + str(e)

    if data.get("code") != 200:
        return None, data.get("msg") or "古诗文接口返回错误"

    poem_info = []
    for it in data.get("data") or []:
        translation, annotation = split_translation_annotation(it.get("ywjzsy"))
        poem_info.append({
            "title": it.get("name", ""),
            "poet": it.get("author", ""),
            "dynasty": it.get("dynasty", ""),
            "content": clean_html(it.get("content")),
            "translation": translation,
            "annotation": annotation,
            "tag": it.get("tag", ""),
            "background": clean_html(it.get("czbj")),
            "appreciation": clean_html(it.get("sxy")),
        })
    return poem_info, None


def apihz_search(keyword, page=1):
    """调古诗文大全 API（免费、每日无上限），转成前端兼容的 poemInfo 格式。

    注意：apihz 的 words 是「全文模糊搜」——搜「杜甫」会把诗句里提到杜甫的
    别人作品也返回。所以这里加「作者精确匹配优先」：
      - 若结果里有 author 恰好等于关键词的作品（说明搜的是人名），
        就翻页把该作者本人的作品找齐，只返回 TA 的；
      - 若没有（说明搜的是诗名/词牌），保持模糊结果原样返回。
    """
    if not APIHZ_ID or not APIHZ_KEY:
        return {"ret_code": "-1", "remark": "缺少古诗文 API 的 id/key，请检查 .env"}

    page_num = int(page) if str(page).isdigit() else 1
    collected = []   # 翻页累计抓到的作品
    exact = []       # 作者精确匹配关键词的作品
    # 最多翻 5 页找「正主」作品（每页 5 首，找到 5 首即可停）
    for p in range(page_num, page_num + 5):
        more, err = _apihz_fetch_page(keyword, p)
        if err or not more:
            break
        collected.extend(more)
        exact = [x for x in collected if x["poet"] == keyword]
        if len(exact) >= 5 or len(more) < 5:
            break

    if exact:
        poem_info = exact
    else:
        # 搜的是诗名/词牌 → 返回当前页的模糊匹配结果
        start = (page_num - 1) * 5
        poem_info = collected[start:start + 5] if collected else []

    return {
        "ret_code": "0",
        "match_type": "apihz",
        "allNum": len(poem_info),
        "poemInfo": poem_info,
    }


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
    """智能搜索：先查本地库（零额度），查不到再调 API，最后按诗名兜底。

    顺序（越靠前越省额度）：
      1. 本地 poems.db 里按「诗人名」查 → 命中直接返回
      2. 本地 poems.db 里按「诗名」查 → 命中直接返回
      3. 本地标题索引「同名作品」→ 命中返回标题列表
      4. 才调 API（先按诗人名，再按诗名）
    """
    page_size = 20
    offset = (int(page) - 1) * page_size if str(page).isdigit() else 0

    # 1. 本地库按诗人名查（按知名度降序：名篇在前）
    poet_rows = db_query(
        "SELECT * FROM poems WHERE poet = ? ORDER BY popularity DESC, title LIMIT ? OFFSET ?",
        (keyword, page_size, offset),
    )
    if poet_rows:
        poet_total = db_query("SELECT COUNT(*) AS c FROM poems WHERE poet = ?", (keyword,))
        total = poet_total[0]["c"] if poet_total else len(poet_rows)
        return jsonify(_poems_from_db(poet_rows, total, page))

    # 2. 本地库按诗名查（精确匹配标题，同名里名篇在前）
    title_rows = db_query(
        "SELECT * FROM poems WHERE title = ? ORDER BY popularity DESC, title LIMIT ? OFFSET ?",
        (keyword, page_size, offset),
    )
    if title_rows:
        title_total = db_query("SELECT COUNT(*) AS c FROM poems WHERE title = ?", (keyword,))
        total = title_total[0]["c"] if title_total else len(title_rows)
        return jsonify(_poems_from_db(title_rows, total, page))

    # 3. 本地标题索引「按作者精确匹配」——搜人名直接列出 TA 的作品（零额度）
    poet_titles = find_poet_titles(keyword)
    if poet_titles:
        return jsonify({
            "ret_code": "0",
            "match_type": "titles",
            "allNum": len(poet_titles),
            "titles": poet_titles,
        })

    # 4. 本地标题索引「同名作品」（零额度）
    title_matches = find_same_titles(keyword)
    if title_matches:
        return jsonify({
            "ret_code": "0",
            "match_type": "titles",
            "allNum": len(title_matches),
            "titles": title_matches,
        })

    # 5. 古诗文大全 API 兜底（免费、每日无上限，关键词同时覆盖诗人名/诗名）
    return jsonify(apihz_search(keyword, page))


def _poems_from_db(rows, total, page):
    """把数据库查到的作品行，组装成前端可渲染的结构（兼容 API 返回格式）"""
    poem_info = []
    for r in rows:
        poem_info.append({
            "poemId": r.get("poem_id", ""),
            "title": r.get("title", ""),
            "poet": r.get("poet", ""),
            "dynasty": r.get("dynasty", ""),
            "content": r.get("content", ""),
            "translation": r.get("translation", ""),
            "annotation": r.get("annotation", ""),
        })
    return {
        "ret_code": "0",
        "match_type": "db",
        "allNum": total,
        "poemInfo": poem_info,
    }


def find_same_titles(keyword):
    """在本地标题索引里，找出所有「标题以关键词开头」的同名作品。
    返回 [{title, poet, dynasty}, ...]，去重、最多 50 条。零 API 调用。"""
    if not TITLE_INDEX or not keyword:
        return []
    result = []
    seen = set()
    for item in TITLE_INDEX:
        title = item.get("title", "")
        if title and title.startswith(keyword) and title not in seen:
            seen.add(title)
            result.append({
                "title": title,
                "poet": item.get("poet", ""),
                "dynasty": item.get("dynasty", ""),
            })
            if len(result) >= 50:
                break
    return result


def find_poet_titles(keyword):
    """在本地标题索引里，找出某位诗人的全部作品（按作者名精确匹配）。
    返回 [{title, poet, dynasty}, ...]，去重、最多 50 条。零 API 调用。
    用于搜「杜甫」「李白」这类人名 → 直接列出 TA 的作品标题。"""
    if not TITLE_INDEX or not keyword:
        return []
    result = []
    seen = set()
    for item in TITLE_INDEX:
        if item.get("poet") != keyword:
            continue
        title = item.get("title", "")
        if title and title not in seen:
            seen.add(title)
            result.append({
                "title": title,
                "poet": item.get("poet", ""),
                "dynasty": item.get("dynasty", ""),
            })
            if len(result) >= 50:
                break
    return result


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
    """按诗词名查（走古诗文大全 API）"""
    return jsonify(apihz_search(title, page))


if __name__ == "__main__":
    if not APPKEY:
        print("⚠️  警告：未在 .env 中找到 SHOWAPI_APPKEY，接口将无法调用。")
    print("诗迹山河后端启动中 → http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
