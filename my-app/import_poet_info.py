# -*- coding: utf-8 -*-
"""
B：把 chinese-gushiwen 的作者简介（3983 位，全带 simpleIntro）导入 poems.db 新表 poet_info。
表结构：poet_info(name TEXT PRIMARY KEY, dynasty TEXT, intro TEXT)
用法：python import_poet_info.py
"""
import json
import glob
import sqlite3

SRC_DIR = r"C:\Users\23850\AppData\Local\Temp\chinese-gushiwen\writer"
DB = r"C:\Users\23850\WorkBuddy\vibe coding\my-app\poems.db"


def main():
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS poet_info ("
        "name TEXT PRIMARY KEY, dynasty TEXT, intro TEXT)"
    )
    n = dup = 0
    cur = conn.cursor()
    for f in glob.glob(SRC_DIR + r"\*.json"):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            name = (d.get("name") or "").strip()
            intro = (d.get("simpleIntro") or "").strip()
            if not name or not intro:
                continue
            try:
                cur.execute(
                    "INSERT INTO poet_info(name, dynasty, intro) VALUES(?,?,?)",
                    (name, (d.get("dynasty") or "").strip() if "dynasty" in d else "", intro),
                )
                n += 1
            except sqlite3.IntegrityError:
                dup += 1
    conn.commit()
    total = cur.execute("SELECT count(*) FROM poet_info").fetchone()[0]
    print(f"新增 {n} 位作者，重名跳过 {dup} 位，poet_info 现有 {total} 位")
    conn.close()


if __name__ == "__main__":
    main()
