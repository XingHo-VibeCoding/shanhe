# -*- coding: utf-8 -*-
"""
import_poetry.py — 把 chinese-poetry 开源数据（_poetry_src/）导入本地 poems.db
覆盖朝代：先秦（诗经/楚辞）、汉（曹操）、唐（全唐诗）、五代（花间集/南唐）、
        宋（宋诗/宋词）、元（元曲）、清（纳兰性德）
字段对齐现有表：poems(poem_id, title, poet, dynasty, content, translation, annotation)
译文/注释留空（后续用大模型补）。
"""
import glob
import json
import os
import sqlite3
import sys

import zhconv

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(BASE), "_poetry_src")
DB = os.path.join(BASE, "poems.db")


def simp(text):
    """繁体 → 简体（简体文本经过转换不变）"""
    return zhconv.convert(str(text), "zh-cn")


def norm_poet(name):
    """作者名统一：转简体、去空格。太宗皇帝 → 李世民 这类映射可后续再补"""
    return simp(name).strip()


def collect():
    """收集所有数据源，产出 (title, poet, dynasty, content) 元组列表"""
    rows = []

    def add(title, poet, dynasty, paras):
        title = simp(title).strip()
        poet = norm_poet(poet)
        if not title or not poet or not paras:
            return
        content = "\n".join(simp(p).strip() for p in paras if str(p).strip())
        if not content:
            return
        rows.append((title, poet, dynasty, content))

    # 1. 全唐诗（繁体）
    for f in glob.glob(os.path.join(SRC, "全唐诗", "poet.tang.*.json")):
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("title", ""), it.get("author", ""), "唐代", it.get("paragraphs"))

    # 2. 全宋诗（繁体）
    for f in glob.glob(os.path.join(SRC, "全唐诗", "poet.song.*.json")):
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("title", ""), it.get("author", ""), "宋代", it.get("paragraphs"))

    # 3. 宋词（title 用词牌名，如「水调歌头」，方便按词牌搜出全部同名）
    for f in glob.glob(os.path.join(SRC, "宋词", "ci.song.*.json")):
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("rhythmic", ""), it.get("author", ""), "宋代", it.get("paragraphs"))

    # 4. 花间集（五代，排除序言文件）
    for f in glob.glob(os.path.join(SRC, "五代诗词", "huajianji", "huajianji-*.json")):
        if "preface" in f:
            continue
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("title", ""), it.get("author", ""), "五代", it.get("paragraphs"))

    # 5. 南唐二主词等（五代）
    f = os.path.join(SRC, "五代诗词", "nantang", "poetrys.json")
    if os.path.exists(f):
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("title", ""), it.get("author", ""), "五代", it.get("paragraphs"))

    # 6. 元曲
    f = os.path.join(SRC, "元曲", "yuanqu.json")
    if os.path.exists(f):
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("title", ""), it.get("author", ""), "元代", it.get("paragraphs"))

    # 7. 纳兰性德（清）
    f = os.path.join(SRC, "纳兰性德", "纳兰性德诗集.json")
    if os.path.exists(f):
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("title", ""), it.get("author", ""), "清代", it.get("para"))

    # 8. 曹操诗集（汉）
    f = os.path.join(SRC, "曹操诗集", "caocao.json")
    if os.path.exists(f):
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("title", ""), it.get("author") or "曹操", "汉代", it.get("paragraphs"))

    # 9. 楚辞（先秦）
    f = os.path.join(SRC, "楚辞", "chuci.json")
    if os.path.exists(f):
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("title", ""), it.get("author") or "屈原", "先秦", it.get("content"))

    # 10. 诗经（先秦）
    f = os.path.join(SRC, "诗经", "shijing.json")
    if os.path.exists(f):
        for it in json.load(open(f, encoding="utf-8")):
            add(it.get("title", ""), "无名氏", "先秦", it.get("content"))

    return rows


def main():
    if not os.path.isdir(SRC):
        print("❌ 找不到开源数据目录 _poetry_src/，请先克隆 chinese-poetry 仓库")
        sys.exit(1)

    print("① 读取并归一化开源数据（含繁转简，约需 1-3 分钟）……")
    rows = collect()
    print("   收集到", len(rows), "首")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 读完现有 (poet,title) 集合用于去重（DB 里已有万维易源抓的 877 首）
    existing = {(r["poet"], r["title"]) for r in cur.execute("SELECT poet, title FROM poems")}
    print("② 现有库中已有", len(existing), "组 (作者,标题)")

    # 给常用查询建索引（33 万行精确匹配提速）
    cur.execute("CREATE INDEX IF NOT EXISTS idx_poems_poet ON poems(poet)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_poems_title ON poems(title)")

    print("③ 开始入库（去重 + 批量插入）……")
    batch = []
    inserted = 0
    seq = 0
    for title, poet, dynasty, content in rows:
        key = (poet, title)
        if key in existing:
            continue
        existing.add(key)
        seq += 1
        batch.append(("cp-%06d" % seq, title, poet, dynasty, content, "", ""))
        if len(batch) >= 2000:
            cur.executemany(
                "INSERT INTO poems(poem_id,title,poet,dynasty,content,translation,annotation) "
                "VALUES (?,?,?,?,?,?,?)", batch)
            inserted += len(batch)
            batch = []
            print("   已插入", inserted, "首……")
    if batch:
        cur.executemany(
            "INSERT INTO poems(poem_id,title,poet,dynasty,content,translation,annotation) "
            "VALUES (?,?,?,?,?,?,?)", batch)
        inserted += len(batch)

    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM poems").fetchone()[0]
    dyn = cur.execute("SELECT dynasty, COUNT(*) FROM poems GROUP BY dynasty ORDER BY COUNT(*) DESC").fetchall()
    dufu = cur.execute("SELECT COUNT(*) FROM poems WHERE poet='杜甫'").fetchone()[0]
    conn.close()
    print("④ 完成！本次新插入", inserted, "首")
    print("   poems.db 现共", total, "首")
    print("   朝代分布:", [(r[0], r[1]) for r in dyn])
    print("   其中杜甫:", dufu, "首")


if __name__ == "__main__":
    main()
