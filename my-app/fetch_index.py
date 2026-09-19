# -*- coding: utf-8 -*-
"""
诗迹山河 - 标题索引抓取脚本

作用：从万维易源「唐诗宋词元曲查询」接口，抓取「唐代/宋代/五代」三个朝代的
      全部诗人 + 全部作品标题，生成 title_index.json，供后端做「标题前缀联想」。

产物：my-app/title_index.json
结构：
  [
    {"title": "静夜思", "poet": "李白", "dynasty": "唐代", "poemId": "..."},
    ...
  ]

特性：
  - 断点续抓：已抓到的 poetId 会跳过，中断后重跑不重复
  - 限速：每次请求间隔，避免被免费档限流
  - 进度打印：每抓完一个朝代打印统计

用法（在 my-app 目录下）：
  python fetch_index.py
"""

import os
import json
import time
import requests

SHOWAPI_BASE = "https://route.showapi.com"

# 从 .env 读 appKey
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

# 只抓这三个诗词黄金朝代（词牌名几乎都在唐宋）
DYNASTIES = [
    ("5b1de349cbf6a77b365977e8", "唐代"),
    ("5b1de348cbf6a77b365977e5", "宋代"),
    ("5b1e0c0acbf6045d055b7f4a", "五代"),
]

# 输出文件（与脚本同目录）
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "title_index.json")
# 断点续抓记录文件
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_progress.json")

# 每次请求间隔（秒），避免触发限流
SLEEP = 0.3

# 最大诗人数量保护（防止意外全库抓取，0 表示不限）
MAX_POETS_PER_DYNASTY = 0


def http_post(path, data):
    """统一的 POST 调用，带 appKey 和超时"""
    return requests.post(
        f"{SHOWAPI_BASE}/{path}",
        params={"appKey": APPKEY},
        data=data,
        headers={"content-type": "application/x-www-form-urlencoded"},
        timeout=20,
    ).json().get("showapi_res_body", {})


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


def get_poet_titles(poet_id):
    """分页拉取某诗人的全部作品标题（返回标题列表）"""
    titles = []
    page = 1
    while True:
        d = http_post("1620-5", {"poetId": poet_id, "page": str(page), "maxResult": "50"})
        if d.get("ret_code") != "0":
            break
        batch = d.get("poemInfo", [])
        if not batch:
            break
        for p in batch:
            title = (p.get("title") or "").strip()
            if title:
                titles.append({
                    "title": title,
                    "poet": p.get("poet", ""),
                    "dynasty": p.get("dynasty", ""),
                    "poemId": p.get("poemId", ""),
                })
        total_pages = int(d.get("allPages", 0) or 0)
        if page >= total_pages or total_pages == 0:
            break
        page += 1
        time.sleep(SLEEP)
    return titles


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_poets": {}, "entries": []}


def save_progress(progress):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def main():
    if not APPKEY:
        print("⚠️  未找到 SHOWAPI_APPKEY，请先配置 my-app/.env")
        return

    progress = load_progress()
    entries = progress["entries"]
    done_poets = progress["done_poets"]
    # 用 poemId 去重（同一首诗可能被重复抓到）
    seen_ids = set()
    for e in entries:
        if e.get("poemId"):
            seen_ids.add(e["poemId"])

    print(f"启动：已有 {len(entries)} 条标题，已抓 {len(done_poets)} 位诗人")
    print(f"目标朝代：{', '.join(d[1] for d in DYNASTIES)}")

    for dynasty_id, dynasty_name in DYNASTIES:
        print(f"\n=== 开始抓取【{dynasty_name}】 ===")
        poets = get_poets(dynasty_id)
        print(f"  {dynasty_name} 共 {len(poets)} 位诗人")

        if MAX_POETS_PER_DYNASTY > 0:
            poets = poets[:MAX_POETS_PER_DYNASTY]
            print(f"  已限制只抓前 {MAX_POETS_PER_DYNASTY} 位")

        new_count = 0
        for i, poet in enumerate(poets):
            poet_id = poet.get("poetId", "")
            poet_name = poet.get("poet", "")
            if poet_id in done_poets:
                continue

            titles = get_poet_titles(poet_id)
            for t in titles:
                pid = t.get("poemId")
                if pid and pid in seen_ids:
                    continue
                if pid:
                    seen_ids.add(pid)
                entries.append(t)
                new_count += 1

            done_poets[poet_id] = poet_name
            time.sleep(SLEEP)

            # 每 20 位诗人存一次进度，防止中断丢失
            if (i + 1) % 20 == 0:
                save_progress(progress)
                print(f"    [{dynasty_name}] 已处理 {i + 1}/{len(poets)} 位诗人，累计标题 {len(entries)} 条")

        save_progress(progress)
        print(f"  【{dynasty_name}】完成，本朝代新增 {new_count} 条")

    # 按标题排序，方便前缀匹配
    entries.sort(key=lambda x: x.get("title", ""))

    # 写最终索引
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)

    print(f"\n✅ 抓取完成！共 {len(entries)} 条标题，已写入 {OUT_FILE}")
    # 完成后删掉进度文件（索引已定稿）
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)


if __name__ == "__main__":
    main()
