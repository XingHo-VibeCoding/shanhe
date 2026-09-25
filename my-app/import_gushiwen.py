# -*- coding: utf-8 -*-
"""
A3（合规版）：用 chinese-gushiwen 开源数据集（1 万首，含译文/注释/赏析）
为 poems.db 补 译文/注释/赏析。本地匹配，无网络请求。
匹配规则：作者精确 + 标题精确或 base_title 前缀互配。
用法：
  python import_gushiwen.py            # 写库
  python import_gushiwen.py --dry      # 只统计，不写库
"""
import sys
import re
import json
import glob
import sqlite3

SRC_DIR = r"C:\Users\23850\AppData\Local\Temp\chinese-gushiwen\guwen"
DB = r"C:\Users\23850\WorkBuddy\vibe coding\my-app\poems.db"
DRY = "--dry" in sys.argv


def base_title(t):
    """剥掉组诗序号尾巴，与 fetch_translation_apihz.py 同规则。"""
    t = t.strip()
    t = re.sub(r"[（(][^)）]*[)）]$", "", t)
    t = re.sub(r"\s*(其[一二三四五六七八九十百]+|\d+|[一二三四五六七八九十百]+)$", "", t)
    t = re.sub(r"\s*[·•]\s*.*$", "", t)
    m = re.match(r"^(.*?)[一二三四五六七八九十\d]+首$", t)
    if m and len(m.group(1)) >= 2:
        t = m.group(1)
    return t.strip(" ··_")


def load_source():
    """加载数据集：{base_title: [entries]}，同一标题可能多篇（不同作者）。"""
    by_key = {}
    total = trans_n = 0
    for f in glob.glob(SRC_DIR + r"\*.json"):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            total += 1
            if not d.get("translation"):
                continue
            trans_n += 1
            bt = base_title(d.get("title", ""))
            if not bt:
                continue
            by_key.setdefault(bt, []).append({
                "writer": (d.get("writer") or "").strip(),
                "translation": d["translation"].strip(),
                "annotation": (d.get("remark") or "").strip(),
                "appreciation": (d.get("shangxi") or "").strip(),
            })
    return by_key, total, trans_n


def main():
    by_key, total, trans_n = load_source()
    print(f"数据集：{total} 首，其中带译文 {trans_n} 首（按标题归组 {len(by_key)} 组）")

    conn = sqlite3.connect(DB, timeout=30)
    rows = conn.execute(
        "SELECT poem_id, title, poet FROM poems WHERE (translation IS NULL OR translation='') "
        "ORDER BY popularity DESC"
    ).fetchall()
    print(f"库内缺译文：{len(rows)} 首")

    hit_exact = hit_prefix = 0
    updates = []
    for pid, title, poet in rows:
        bt = base_title(title)
        cands = by_key.get(bt)
        if not cands:
            continue
        poet_s = (poet or "").strip()
        chosen = None
        for c in cands:
            if poet_s and c["writer"] and c["writer"] != poet_s:
                continue
            chosen = c
            break
        if chosen is None:
            continue
        if chosen["writer"] and title.strip() in [k for k in (bt,)]:
            hit_exact += 1
        else:
            hit_prefix += 1
        updates.append((chosen["translation"], chosen["annotation"], chosen["appreciation"], pid))

    print(f"可匹配：{len(updates)} 首（标题精确 {hit_exact} / 前缀 {hit_prefix}）")
    if DRY:
        print("（dry-run，未写库）")
        return
    cur = conn.cursor()
    for u in updates:
        cur.execute(
            "UPDATE poems SET translation=?, annotation=?, appreciation=? WHERE poem_id=?",
            u,
        )
    conn.commit()
    print(f"已写库 {len(updates)} 首")


if __name__ == "__main__":
    main()
