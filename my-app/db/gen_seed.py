# -*- coding: utf-8 -*-
"""Day 16 种子数据生成器
从本地 poems.db 抽取名诗人 + 名篇，生成 db/seed.sql。
策略：先 TRUNCATE 清空三表并重置自增，再显式 id 插入 —— 可复现、可重复执行。
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

# 5 条收藏记录（poem 用 (title, poet) 定位到 POEMS 里的 id；时间固定保证可复现）
FAVORITES = [
    ("静夜思", "李白", "2026-10-04 01:00:00+00"),
    ("望庐山瀑布", "李白", "2026-10-04 01:20:00+00"),
    ("春晓", "孟浩然", "2026-10-04 01:05:00+00"),
    ("登鹳雀楼", "王之涣", "2026-10-04 01:10:00+00"),
    ("山居秋暝", "王维", "2026-10-04 01:15:00+00"),
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

# 构造 poet_id 映射（poets 按 poets_order 顺序 1-based）
pid = {poet: i + 1 for i, (poet, _, _) in enumerate(poet_rows)}

# 构造 poem_id 映射（poems 按 POEMS 顺序 1-based）
poem_id = {title: i + 1 for i, (title, _) in enumerate(POEMS)}

# ---- 生成 seed.sql ----
lines = []
lines.append("-- ============================================================")
lines.append("-- 诗迹山河 · 种子数据（三张表）")
lines.append("-- 可重复执行：先 TRUNCATE 清空并重置自增，再显式 id 插入（可复现）")
lines.append("-- ============================================================")
lines.append("")
lines.append("-- 先删：清空三表 + 重置 SERIAL 自增 + CASCADE 处理外键依赖")
lines.append("TRUNCATE TABLE favorites, poems, poets RESTART IDENTITY CASCADE;")
lines.append("")
lines.append("-- 后建：作者表 poets（每位一条，避免单条命令行过长）")
for i, (name, dynasty, intro) in enumerate(poet_rows, 1):
    lines.append(
        f"INSERT INTO poets (id, name, dynasty, intro) VALUES ({i}, {esc(name)}, {esc(dynasty)}, {esc(intro)});"
    )
lines.append("")

lines.append("-- 诗词表 poems（每首一条）")
for i, (title, poet, dynasty, content, translation, annotation, background, appreciation, popularity) in enumerate(poem_rows, 1):
    lines.append(
        f"INSERT INTO poems (id, title, poet_id, dynasty, content, translation, annotation, background, appreciation, popularity) "
        f"VALUES ({i}, {esc(title)}, {pid[poet]}, {esc(dynasty)}, {esc(content)}, {esc(translation)}, {esc(annotation)}, {esc(background)}, {esc(appreciation)}, {popularity});"
    )
lines.append("")

lines.append("-- 收藏记录表 favorites（5 条，poem_id 关联 poems.id）")
for i, (title, poet, ts) in enumerate(FAVORITES, 1):
    lines.append(
        f"INSERT INTO favorites (id, poem_id, created_at) VALUES ({i}, {poem_id[title]}, E'{ts}');"
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
print(f"=== 收藏 {len(FAVORITES)} 条 ===")
for i, (title, poet, ts) in enumerate(FAVORITES, 1):
    print(f"  {i}. poem_id={poem_id[title]} 《{title}》{poet} @ {ts}")
print()
print(f"已生成 db/seed.sql（{len(seed_sql)} 字符）")
