# -*- coding: utf-8 -*-
"""Day 16 种子数据生成器
从本地 poems.db 抽取名诗人 + 名篇，生成幂等的 db/seed.sql（可重复执行不报错）。
"""
import sqlite3

# 12 首名篇（title 精确匹配 + poet 验证）
POEMS = [
    ("静夜思", "李白"),
    ("望庐山瀑布", "李白"),
    ("早发白帝城", "李白"),
    ("春晓", "孟浩然"),
    ("登鹳雀楼", "王之涣"),
    ("咏柳", "贺知章"),
    ("水调歌头", "苏轼"),
    ("赋得古原草送别", "白居易"),
    ("黄鹤楼", "崔颢"),
    ("望月怀远", "张九龄"),
    ("山居秋暝", "王维"),
    ("相思", "王维"),
]

def esc(v):
    """把 Python 字符串转成 PostgreSQL E'' 转义字面量；空/None 返回 NULL。"""
    if v is None or v == "":
        return "NULL"
    v = v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
    return "E'" + v + "'"

conn = sqlite3.connect("poems.db")
cur = conn.cursor()

# 作者去重（保持出现顺序）
poets_order = []
for _, poet in POEMS:
    if poet not in poets_order:
        poets_order.append(poet)

# 查作者简介 + 从诗词表补 dynasty
poet_rows = []
for poet in poets_order:
    cur.execute("SELECT intro FROM poet_info WHERE name=?", (poet,))
    r = cur.fetchone()
    intro = r[0] if r and r[0] else ""
    cur.execute("SELECT dynasty FROM poems WHERE poet=? AND dynasty IS NOT NULL AND dynasty != '' LIMIT 1", (poet,))
    d = cur.fetchone()
    dynasty = d[0] if d else ""
    poet_rows.append((poet, dynasty, intro))

# 查每首诗
poem_rows = []
for title, poet in POEMS:
    cur.execute(
        "SELECT dynasty, content, translation, annotation, background, appreciation, popularity "
        "FROM poems WHERE title=? AND poet=? ORDER BY popularity DESC LIMIT 1",
        (title, poet),
    )
    row = cur.fetchone()
    if not row:
        print(f"!! 未找到: 《{title}》{poet}")
        continue
    dynasty, content, translation, annotation, background, appreciation, popularity = row
    poem_rows.append((title, poet, dynasty or "", content, translation, annotation, background, appreciation, popularity or 0))

conn.close()

# 构造 poet_id 映射
pid = {poet: i + 1 for i, (poet, _, _) in enumerate(poet_rows)}

# ---- 生成 seed.sql ----
lines = []
lines.append("-- ============================================================")
lines.append("-- 诗迹山河 · 种子数据（Day 16）")
lines.append("-- 说明：显式指定 id，ON CONFLICT (id) DO NOTHING，重复执行不报错")
lines.append("-- ============================================================")
lines.append("")

# poets 插入：每位诗人一条（避免单条命令行过长）
for i, (name, dynasty, intro) in enumerate(poet_rows, 1):
    lines.append(
        f"INSERT INTO poets (id, name, dynasty, intro) VALUES ({i}, {esc(name)}, {esc(dynasty)}, {esc(intro)}) ON CONFLICT (id) DO NOTHING;"
    )
lines.append("")

# poems 插入：每首一条
for i, (title, poet, dynasty, content, translation, annotation, background, appreciation, popularity) in enumerate(poem_rows, 1):
    lines.append(
        f"INSERT INTO poems (id, title, poet_id, dynasty, content, translation, annotation, background, appreciation, popularity) "
        f"VALUES ({i}, {esc(title)}, {pid[poet]}, {esc(dynasty)}, {esc(content)}, {esc(translation)}, {esc(annotation)}, {esc(background)}, {esc(appreciation)}, {popularity}) "
        f"ON CONFLICT (id) DO NOTHING;"
    )
lines.append("")

seed_sql = "\n".join(lines)
with open("db/seed.sql", "w", encoding="utf-8") as f:
    f.write(seed_sql)

# ---- 打印汇总 ----
print(f"=== 诗人 {len(poet_rows)} 位 ===")
for i, (name, dynasty, intro) in enumerate(poet_rows, 1):
    print(f"  {i}. {name} [{dynasty}] intro={len(intro)}字")
print(f"=== 诗词 {len(poem_rows)} 首 ===")
for i, (title, poet, dynasty, content, translation, annotation, background, appreciation, popularity) in enumerate(poem_rows, 1):
    print(f"  {i}. 《{title}》{poet}[{dynasty}] 译={len(translation or '')} 注={len(annotation or '')} 名={popularity}")
print()
print(f"已生成 db/seed.sql（{len(seed_sql)} 字符）")
