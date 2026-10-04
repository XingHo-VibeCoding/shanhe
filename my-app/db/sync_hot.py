#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/sync_hot.py —— Day 17「真实热搜数据入库」同步任务

作用：从本地 SQLite 诗库 poems.db 抽取「知名度最高」的真实名篇（popularity=1亿，
去噪、去重），连同作者一起同步到 CloudBase PostgreSQL 的 poems/poets 表。

- 幂等：INSERT ... ON CONFLICT (id) DO NOTHING，重复执行不报错、不重复插入。
- 外键：poems.poet_id → poets.id，作者先入库（按 name 去重），诗词引用其 id。
- 不删已有 seed 数据（只增量补充新名篇）。
"""

import sqlite3
import subprocess
import json
import re
import sys

TCB = r"C:\Users\23850\.workbuddy\binaries\node\versions\22.22.2-3\tcb.cmd"
ENV = "shijishanhe-d5gmc8a0k01b1e88d"
N = 20  # 同步 TOP N 首名篇

# 噪声作者（本地库 popularity=1亿 里混入的截断/异常条目）
NOISE_POETS = {"不详", "佚名", "王", "王炎", "范协"}


def esc(s):
    """转义 SQL 单引号，None/空 返回空串。"""
    if s is None:
        return "''"
    return "'" + str(s).replace("'", "''") + "'"


def cloud_query(sql):
    """通过 tcb db execute 执行 SQL 并返回行列表（每行是 list）。"""
    r = subprocess.run([TCB, "db", "execute", "--sql", sql, "--json"], capture_output=True)
    out = r.stdout.decode("utf-8", errors="replace")
    try:
        d = json.loads(out[out.find("{"):])
        return [json.loads(x) if isinstance(x, str) else x for x in d.get("data", {}).get("Rows", [])]
    except Exception as e:
        print("  [cloud_query 失败]", out[:200], r.stderr.decode("gbk", errors="replace")[:200])
        return []


def main():
    # 1) 读本地库：取知名度最高的真实名篇，去噪 + 按 (title, poet) 去重
    conn = sqlite3.connect("poems.db")
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT title, poet, dynasty, content, translation, annotation, popularity
        FROM poems
        WHERE popularity = 100000000
          AND length(title) >= 2
          AND title NOT LIKE '%其%'
        ORDER BY poet, title
        """
    ).fetchall()
    seen = set()
    poems = []
    for title, poet, dynasty, content, translation, annotation, popularity in rows:
        if poet in NOISE_POETS:
            continue
        key = (title, poet)
        if key in seen:
            continue
        seen.add(key)
        poems.append((title, poet, dynasty, content, translation, annotation, popularity))
        if len(poems) >= N:
            break
    conn.close()
    print(f"本地抽出候选名篇 {len(poems)} 首（去噪去重后）")

    # 2) 读云端现有 poets，建 name→id 映射
    existing_poets = {}
    max_poet_id = 0
    for row in cloud_query("SELECT id, name FROM poets ORDER BY id"):
        pid, pname = int(row[0]), row[1]
        existing_poets[pname] = pid
        max_poet_id = max(max_poet_id, pid)

    # 3) 读云端现有 poems，去重（同 title+poet_id 不重复插）
    existing_poem_titles = set()
    max_poem_id = 0
    for row in cloud_query("SELECT id, title, poet_id FROM poems ORDER BY id"):
        max_poem_id = max(max_poem_id, int(row[0]))
        existing_poem_titles.add((row[1], int(row[2])))

    # 4) 计算新 id 与诗人映射，生成 SQL
    stmts = []
    next_poet_id = max_poet_id + 1
    next_poem_id = max_poem_id + 1
    new_poet_count = 0
    new_poem_count = 0
    skip_poet = 0

    for title, poet, dynasty, content, translation, annotation, popularity in poems:
        # 作者入库（name 去重）
        if poet not in existing_poets:
            pid = next_poet_id
            existing_poets[poet] = pid
            next_poet_id += 1
            new_poet_count += 1
            stmts.append(
                f"INSERT INTO poets (id, name, dynasty) VALUES ({pid}, {esc(poet)}, {esc(dynasty)}) "
                f"ON CONFLICT (id) DO NOTHING;"
            )
        else:
            pid = existing_poets[poet]

        # 诗词入库（同 title+poet_id 不重复）
        if (title, pid) in existing_poem_titles:
            skip_poet += 1
            continue
        pmid = next_poem_id
        next_poem_id += 1
        new_poem_count += 1
        stmts.append(
            f"INSERT INTO poems (id, title, poet_id, dynasty, content, translation, annotation, popularity) "
            f"VALUES ({pmid}, {esc(title)}, {pid}, {esc(dynasty)}, {esc(content)}, "
            f"{esc(translation)}, {esc(annotation)}, {popularity}) "
            f"ON CONFLICT (id) DO NOTHING;"
        )

    print(f"生成 SQL：新增诗人 {new_poet_count} 位、新增诗词 {new_poem_count} 首、跳过重复 {skip_poet} 首")

    if not stmts:
        print("没有需要同步的数据，结束。")
        return

    # 5) 逐条执行（避免单条 SQL 过长）
    ok = 0
    fail = 0
    for s in stmts:
        # 压缩空白，避免命令行过长
        compact = " ".join(s.split())
        r = subprocess.run([TCB, "db", "execute", "--sql", compact, "--json"], capture_output=True)
        out = r.stdout.decode("utf-8", errors="replace")
        if r.returncode == 0 and '"Rows"' in out:
            ok += 1
        else:
            fail += 1
            print("  [失败]", compact[:80], "|", r.stderr.decode("gbk", errors="replace")[:120])
    print(f"执行完成：成功 {ok} / 失败 {fail}")

    # 6) 验证云端行数
    for t in ["poets", "poems"]:
        rows = cloud_query(f"SELECT COUNT(*) FROM {t}")
        print(f"云端 {t} 现有行数：", rows[0][0] if rows else "?")


if __name__ == "__main__":
    main()
