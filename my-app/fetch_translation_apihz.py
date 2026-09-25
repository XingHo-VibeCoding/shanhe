# -*- coding: utf-8 -*-
"""
A2：用 apihz 古诗文大全接口，按知名度从高到低批量补 译文/注释/创作背景/赏析。
策略：
  - 目标：poems.db 中 translation 为空的诗，按 popularity DESC 排序
  - 每首用「诗题」调接口（words=诗题），结果里找 标题精确匹配 + 作者匹配 的条目
  - 复用 server.py 的 clean_html / split_translation_annotation 解析
  - 顺带抓 czbj（创作背景）、sxy（赏析）写入新增列
  - 限速 0.6 秒/首；断点续跑（已补的不再查）
用法：
  python fetch_translation_apihz.py [数量]   # 默认 300
"""
import sys
import re
import time
import sqlite3
import requests
import urllib3

urllib3.disable_warnings()

sys.path.insert(0, r"C:\Users\23850\WorkBuddy\vibe coding\my-app")
from server import clean_html, split_translation_annotation  # noqa: E402

DB = r"C:\Users\23850\WorkBuddy\vibe coding\my-app\poems.db"
APIHZ_BASE = "https://cn.apihz.cn/api/zici/poetry.php"
ID, KEY = "10021403", "qwertyujkjhdsd"

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 300
SLEEP = 0.6


def ensure_columns(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(poems)").fetchall()]
    if "background" not in cols:
        conn.execute("ALTER TABLE poems ADD COLUMN background TEXT")
        print("已新增列 background")
    if "appreciation" not in cols:
        conn.execute("ALTER TABLE poems ADD COLUMN appreciation TEXT")
        print("已新增列 appreciation")
    conn.commit()


def base_title(t):
    """剥掉组诗序号尾巴：「别董大二首 一」→「别董大」，「望岳」不变。"""
    t = t.strip()
    t = re.sub(r"[（(][^)）]*[)）]$", "", t)                 # 尾括号注
    t = re.sub(r"\s*(其[一二三四五六七八九十百]+|\d+|[一二三四五六七八九十百]+)$", "", t)  # 尾序号
    t = re.sub(r"\s*[·•]\s*.*$", "", t)                     # 尾 ·其X
    m = re.match(r"^(.*?)[一二三四五六七八九十\d]+首$", t)   # 尾「N首」
    if m and len(m.group(1)) >= 2:
        t = m.group(1)
    return t.strip(" ··_")


def fetch_one(title, poet):
    """按诗题查 apihz，返回 dict 或 None（没抓到）。
    匹配：作者精确匹配 + 标题前缀互配（base 后），取译文最长者。"""
    bt = base_title(title)
    if not bt:
        return None
    best = None
    for page in (1, 2):
        try:
            resp = requests.get(
                APIHZ_BASE,
                params={"id": ID, "key": KEY, "words": bt, "page": str(page)},
                timeout=20,
                verify=False,
            )
            data = resp.json()
        except Exception:
            return best
        if data.get("code") != 200:
            return best
        rows = data.get("data") or []
        for r in rows:
            r_author = str(r.get("author", "")).strip()
            r_name = str(r.get("name", "")).strip()
            if poet and r_author and r_author != poet.strip():
                continue
            if not (r_name.startswith(bt) or bt.startswith(r_name)):
                continue
            trans, anno = split_translation_annotation(r.get("ywjzsy") or "")
            if not (trans or anno):
                continue
            score = len(trans) + len(anno)
            if best is None or score > best["_score"]:
                best = {
                    "_score": score,
                    "translation": trans,
                    "annotation": anno,
                    "background": clean_html(r.get("czbj")),
                    "appreciation": clean_html(r.get("sxy")),
                }
        if len(rows) < 5:
            break
        time.sleep(SLEEP)
    if best:
        best.pop("_score", None)
    return best


def main():
    conn = sqlite3.connect(DB)
    ensure_columns(conn)
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT poem_id, title, poet FROM poems "
        "WHERE (translation IS NULL OR translation='') "
        "ORDER BY popularity DESC LIMIT ?",
        (LIMIT,),
    ).fetchall()
    print(f"目标 {len(rows)} 首（按知名度降序）")

    ok = miss = 0
    for i, (pid, title, poet) in enumerate(rows, 1):
        got = fetch_one(title, poet)
        if got:
            cur.execute(
                "UPDATE poems SET translation=?, annotation=?, background=?, appreciation=? WHERE poem_id=?",
                (got["translation"], got["annotation"], got["background"], got["appreciation"], pid),
            )
            conn.commit()
            ok += 1
            print(f"[{i}/{len(rows)}] ✓ {title}（{poet}）译{len(got['translation'])}字 注{len(got['annotation'])}字 背{len(got['background'])}字 赏{len(got['appreciation'])}字")
        else:
            miss += 1
            print(f"[{i}/{len(rows)}] × {title}（{poet}）接口无译文")
        time.sleep(SLEEP)

    print(f"\n完成：成功 {ok} / 未命中 {miss} / 共 {len(rows)}")
    conn.close()


if __name__ == "__main__":
    main()
