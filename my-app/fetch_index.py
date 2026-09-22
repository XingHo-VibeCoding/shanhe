# -*- coding: utf-8 -*-
"""
诗迹山河 - 标题索引抓取脚本

作用：从万维易源「唐诗宋词元曲查询」接口，抓取「宋代/五代/唐代」三个朝代的
      诗人 + 作品标题，生成 title_index.json，供后端做「标题前缀联想」。

产物：my-app/title_index.json
结构：
  [
    {"title": "静夜思", "poet": "李白", "dynasty": "唐代", "poemId": "..."},
    ...
  ]

特性：
  - 优先抓宋代（词牌名最丰富），再五代，最后唐代
  - 断点续抓：已完整抓取的诗人会跳过，中断后重跑不重复
  - 额度耗尽自动保存：检测到免费额度用完，立即保存已抓数据并退出，下次继续
  - 限速：每次请求间隔，避免触发限流

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

# 抓取顺序：宋代词牌名最丰富优先，五代次之，唐代最后（上次已抓部分唐诗）
DYNASTIES = [
    ("5b1de348cbf6a77b365977e5", "宋代"),
    ("5b1e0c0acbf6045d055b7f4a", "五代"),
    ("5b1de349cbf6a77b365977e8", "唐代"),
]

# 输出文件（与脚本同目录）
OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "title_index.json")
# 断点续抓记录文件
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fetch_progress.json")

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
    # 额度耗尽：showapi_res_code == -7，或错误信息里提到「次数/流量」
    err = str(resp.get("showapi_res_error", ""))
    if resp.get("showapi_res_code") == -7 or "次数" in err or "流量" in err or "资源包" in err:
        raise QuotaExhausted(err or "可调用次数为 0")
    return resp.get("showapi_res_body", {})


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

    # 若进度文件为空，但 title_index.json 已有历史数据，用历史数据做去重基础
    if not entries and os.path.exists(OUT_FILE):
        with open(OUT_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)

    seen_ids = {e.get("poemId") for e in entries if e.get("poemId")}

    print(f"启动：已有 {len(entries)} 条标题，已完整抓 {len(done_poets)} 位诗人")
    print(f"抓取顺序：{' → '.join(d[1] for d in DYNASTIES)}")

    try:
        for dynasty_id, dynasty_name in DYNASTIES:
            print(f"\n=== 开始抓取【{dynasty_name}】 ===")
            poets = get_poets(dynasty_id)
            print(f"  {dynasty_name} 共 {len(poets)} 位诗人")

            new_count = 0
            for i, poet in enumerate(poets):
                poet_id = poet.get("poetId", "")
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

                done_poets[poet_id] = poet.get("poet", "")
                time.sleep(SLEEP)

                if (i + 1) % 10 == 0:
                    save_progress(progress)
                    print(f"    [{dynasty_name}] 已处理 {i + 1}/{len(poets)} 位诗人，累计标题 {len(entries)} 条")

            save_progress(progress)
            print(f"  【{dynasty_name}】完成，本朝代新增 {new_count} 条")

    except QuotaExhausted as e:
        print(f"\n⚠️ 免费额度耗尽：{e}")
        print(f"本次累计 {len(entries)} 条标题，已保存进度，下次运行会从这里继续。")
    finally:
        # 写最终索引（保留进度文件，供下次断点续抓）
        entries.sort(key=lambda x: x.get("title", ""))
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=1)
        save_progress(progress)
        print(f"\n已写入 {OUT_FILE}（共 {len(entries)} 条标题）")


if __name__ == "__main__":
    main()
