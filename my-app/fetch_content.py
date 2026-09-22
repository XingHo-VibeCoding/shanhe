# -*- coding: utf-8 -*-
"""
诗迹山河 - 诗词正文抓取脚本（抓原文/译文/注释，进 SQLite 数据库）

作用：从万维易源「唐诗宋词元曲查询」接口，遍历全部朝代的诗人，
      拉取每首诗的完整内容（原文、译文、注释），写入本地 SQLite 数据库。

产物：my-app/poems.db（表 poems）
表结构：
  poem_id      TEXT PRIMARY KEY   诗词唯一 ID
  title        TEXT               标题
  poet         TEXT               作者
  dynasty      TEXT               朝代
  content      TEXT               原文（全文，逐句以换行拼接）
  translation  TEXT               译文（全文）
  annotation   TEXT               注释（全文）

特性：
  - 遍历全部 15 个朝代（按作品量多的朝代优先）
  - 断点续抓：已抓取的作品 poem_id 会跳过，中断后重跑不重复
  - 额度耗尽自动保存：检测到免费额度用完，立即提交已抓数据并退出，下次继续
  - 限速：每次请求间隔，避免触发限流

用法（在 my-app 目录下）：
  python fetch_content.py
"""

import os
import json
import time
import sqlite3
import requests

SHOWAPI_BASE = "https://route.showapi.com"


def load_env():
    env = {}
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


APPKEY = load_env().get("SHOWAPI_APPKEY", "")

# 全部朝代（按诗人数量从多到少排序，优先抓大户）
DYNASTIES = [
    ("5b1de348cbf6a77b365977e5", "宋代"),
    ("5b1de349cbf6a77b365977e8", "唐代"),
    ("5b1e0b75cbf6045d055b7f38", "清代"),
    ("5b1e0c75cbf6045d055b7f60", "明代"),
    ("5b1dee9ccbf697031f6e0e8f", "元代"),
    ("5b1de34ecbf6a77b365977ed", "南北朝"),
    ("5b1df365cbf6da563c277b7b", "两汉"),
    ("5b1f2118cbf6c9d75a261526", "隋代"),
    ("5b1f7cb9cbf6b4612a51e921", "未知"),
    ("5b1df40bcbf6ee813e50d2cb", "现代"),
    ("5b1e0c0acbf6045d055b7f4a", "五代"),
    ("5b1e1884cbf6cbe3b05f3596", "魏晋"),
    ("5b1e1f7acbf668d3b4b122ae", "金朝"),
    ("5b1f21eccbf6c9d75a261537", "先秦"),
    ("5b1f2a18cbf6c9d75a2615b7", "近代"),
]

# 数据库文件（与脚本同目录）
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poems.db")
# 断点续抓记录文件
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_content_progress.json")

# 每次请求间隔（秒）
SLEEP = 0.3


class QuotaExhausted(Exception):
    """免费额度耗尽"""
    pass


def http_post(path, data):
    """统一的 POST 调用，带 appKey 和超时；额度耗尽时抛 QuotaExhausted"""
    resp = requests.post(
        f"{SHOWAPI_BASE}/{path}",
        params={"appKey": APPKEY},
        data=data,
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=20,
    ).json()
    err = str(resp.get("showapi_res_error", ""))
    if resp.get("showapi_res_code") == -7 or "次数" in err or "流量" in err or "资源包" in err:
        raise QuotaExhausted(err or "可调用次数为 0")
    return resp.get("showapi_res_body", {})


def init_db():
    """建库建表"""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS poems (
            poem_id     TEXT PRIMARY KEY,
            title       TEXT,
            poet        TEXT,
            dynasty     TEXT,
            content     TEXT,
            translation TEXT,
            annotation  TEXT
        )
    """)
    conn.commit()
    return conn


def get_poets(dynasty_id):
    """分页拉取某朝代的全部诗人"""
    poets = []
    page = 1
    while True:
        d = http_post("1620-4", {"dynastyId": dynasty_id, "page": str(page), "maxResult": "50"})
        if d.get("ret_code") != "0":
            break
        batch = d.get("poetInfo", [])
        if not batch:
            break
        poets.extend(batch)
        total_pages = int(d.get("allPages", 0) or 0)
        if page >= total_pages or total_pages == 0:
            break
        page += 1
        time.sleep(SLEEP)
    return poets


def get_poet_poems(poet_id):
    """分页拉取某诗人的全部作品（含正文三件套），返回作品列表"""
    poems = []
    page = 1
    while True:
        d = http_post("1620-5", {"poetId": poet_id, "page": str(page), "maxResult": "50"})
        if d.get("ret_code") != "0":
            break
        batch = d.get("poemInfo", [])
        if not batch:
            break
        poems.extend(batch)
        total_pages = int(d.get("allPages", 0) or 0)
        if page >= total_pages or total_pages == 0:
            break
        page += 1
        time.sleep(SLEEP)
    return poems


def parse_poem(p):
    """从接口返回的单首作品里，抽出五件套"""
    contentlist = p.get("contentlist", []) or []
    content_parts = []
    trans_parts = []
    ann_parts = []
    for seg in contentlist:
        # 原文
        c = seg.get("content") or seg.get("original") or ""
        if c:
            content_parts.append(c)
        # 译文
        t = seg.get("translation") or seg.get("trans") or ""
        if t:
            trans_parts.append(t)
        # 注释
        a = seg.get("annotation") or seg.get("ann") or seg.get("note") or ""
        if a:
            ann_parts.append(a)

    return {
        "poem_id": p.get("poemId", ""),
        "title": p.get("title", ""),
        "poet": p.get("poet", ""),
        "dynasty": p.get("dynasty", ""),
        "content": "\n".join(content_parts),
        "translation": "\n".join(trans_parts),
        "annotation": "\n".join(ann_parts),
    }


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_poets": []}


def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def main():
    if not APPKEY:
        print("⚠️  未找到 SHOWAPI_APPKEY，请先配置 my-app/.env")
        return

    conn = init_db()
    cur = conn.cursor()
    progress = load_progress()
    done_poets = set(progress.get("done_poets", []))

    # 统计已有作品数
    cur.execute("SELECT COUNT(*) FROM poems")
    existing = cur.fetchone()[0]
    print(f"启动：数据库已有 {existing} 首诗词，已完整抓 {len(done_poets)} 位诗人")

    try:
        for dynasty_id, dynasty_name in DYNASTIES:
            print(f"\n=== 开始抓取【{dynasty_name}】 ===")
            poets = get_poets(dynasty_id)
            print(f"  {dynasty_name} 共 {len(poets)} 位诗人")

            for i, poet in enumerate(poets):
                poet_id = poet.get("poetId", "")
                if poet_id in done_poets:
                    continue

                poems = get_poet_poems(poet_id)
                inserted = 0
                for p in poems:
                    parsed = parse_poem(p)
                    if not parsed["poem_id"]:
                        continue
                    cur.execute(
                        "INSERT OR IGNORE INTO poems VALUES (?,?,?,?,?,?,?)",
                        (parsed["poem_id"], parsed["title"], parsed["poet"],
                         parsed["dynasty"], parsed["content"],
                         parsed["translation"], parsed["annotation"]),
                    )
                    inserted += 1
                conn.commit()

                done_poets.add(poet_id)
                time.sleep(SLEEP)

                if (i + 1) % 10 == 0:
                    save_progress({"done_poets": sorted(done_poets)})
                    cur.execute("SELECT COUNT(*) FROM poems")
                    total = cur.fetchone()[0]
                    print(f"    [{dynasty_name}] 已处理 {i + 1}/{len(poets)} 位诗人，累计 {total} 首")

            save_progress({"done_poets": sorted(done_poets)})
            cur.execute("SELECT COUNT(*) FROM poems")
            total = cur.fetchone()[0]
            print(f"  【{dynasty_name}】完成，当前累计 {total} 首")

    except QuotaExhausted as e:
        print(f"\n⚠️ 免费额度耗尽：{e}")
        cur.execute("SELECT COUNT(*) FROM poems")
        total = cur.fetchone()[0]
        print(f"本次累计 {total} 首，已保存，下次运行会从这里继续。")
    finally:
        conn.commit()
        save_progress({"done_poets": sorted(done_poets)})
        cur.execute("SELECT COUNT(*) FROM poems")
        total = cur.fetchone()[0]
        print(f"\n完成。数据库 poems.db 共 {total} 首诗词。")
        conn.close()


if __name__ == "__main__":
    main()
