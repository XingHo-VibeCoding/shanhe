# -*- coding: utf-8 -*-
"""
诗迹山河 - 数据访问层（db_access.py）

职责：
  只负责「查本地 poems.db / poet_info 表」，把 SQL 封装成一个个名字好懂的
  具名函数。路由层（server.py）不再直接写 SQL，而是调用这里的函数。

  这样做的目的（分层思路）：
    - 路由层只管「接请求 → 调数据访问层 → 拼返回」，不碰数据库细节；
    - 以后要改库、加缓存、换存储，只改这一个文件，接口层不动。

说明：
  - 这里只做「读」操作（SELECT），不写数据库；写库由 fetch_*.py 脚本负责。
  - 底层统一走 db_query() 这一条连接通道，方便统一处理异常。
"""

import os
import sqlite3

# 诗词正文数据库（与 server.py 同级，存原文/译文/注释等五件套）
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(FRONTEND_DIR, "poems.db")


def db_query(sql, params=()):
    """查本地 poems.db（只读）。库不存在或查询失败时返回空列表。"""
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"⚠️  查询数据库失败：{e}")
        return []


# ===== 推荐 / 每日荐诗 =====

def get_recommend_pool(limit=8):
    """推荐接口候选：优先取「有译文」的名篇（五件套完整），
    不足 limit 时用其他名篇补齐，返回恰好 limit 条（去重同名同作者）。"""
    rows = db_query(
        "SELECT * FROM poems WHERE content != '' AND translation != '' "
        "ORDER BY popularity DESC, title LIMIT ?",
        (limit,),
    )
    if len(rows) < limit:
        seen = {(r.get("title"), r.get("poet")) for r in rows}
        extra = db_query(
            "SELECT * FROM poems WHERE content != '' "
            "ORDER BY popularity DESC, title LIMIT 50"
        )
        for r in extra:
            key = (r.get("title"), r.get("poet"))
            if key in seen:
                continue
            rows.append(r)
            seen.add(key)
            if len(rows) >= limit:
                break
    return rows


def get_daily_pool(size=300):
    """每日荐诗候选池：优先取「有译文」名篇，不足时退回按知名度取名篇兜底。"""
    rows = db_query(
        "SELECT * FROM poems WHERE content != '' AND translation != '' "
        "ORDER BY popularity DESC, title LIMIT ?",
        (size,),
    )
    if len(rows) < size:
        rows = db_query(
            "SELECT * FROM poems WHERE content != '' "
            "ORDER BY popularity DESC, title LIMIT ?",
            (size,),
        )
    return rows


# ===== 标题联想（/suggest） =====

def suggest_poet_titles(poet, title_part):
    """「作者，篇名」组合联想：只联想某作者名下、标题含关键词的篇名。"""
    return db_query(
        "SELECT title, poet, dynasty, MAX(popularity) AS popularity FROM poems "
        "WHERE poet = ? AND title LIKE ? "
        "GROUP BY title ORDER BY CASE WHEN title LIKE ? THEN 0 ELSE 1 END, popularity DESC LIMIT 20",
        (poet, f"%{title_part}%", f"{title_part}%"),
    )


def suggest_titles(keyword):
    """标题「包含」关键词联想，去重同名后按知名度降序，最多 20 条。"""
    return db_query(
        "SELECT title, poet, dynasty, MAX(popularity) AS popularity FROM poems "
        "WHERE title LIKE ? GROUP BY title ORDER BY popularity DESC LIMIT 20",
        (f"%{keyword}%",),
    )


# ===== 搜索（/search） =====

def poet_exists(name):
    """判断某诗人名在本地库里是否存在。"""
    return bool(db_query("SELECT 1 AS ok FROM poems WHERE poet = ? LIMIT 1", (name,)))


def get_poems_by_poet(keyword, page_size, offset):
    """按诗人名查全部作品（知名度降序，名篇在前），分页。"""
    return db_query(
        "SELECT * FROM poems WHERE poet = ? ORDER BY popularity DESC, title LIMIT ? OFFSET ?",
        (keyword, page_size, offset),
    )


def count_poems_by_poet(keyword):
    """按诗人名统计作品总数。"""
    rows = db_query("SELECT COUNT(*) AS c FROM poems WHERE poet = ?", (keyword,))
    return rows[0]["c"] if rows else 0


def get_poems_by_title_like(keyword, page_size, offset):
    """按标题「包含」关键词查作品（知名度降序），分页。"""
    return db_query(
        "SELECT * FROM poems WHERE title LIKE ? ORDER BY popularity DESC, title LIMIT ? OFFSET ?",
        (f"%{keyword}%", page_size, offset),
    )


def count_poems_by_title_like(keyword):
    """按标题「包含」关键词统计总数。"""
    rows = db_query("SELECT COUNT(*) AS c FROM poems WHERE title LIKE ?", (f"%{keyword}%",))
    return rows[0]["c"] if rows else 0


def get_poems_by_poet_and_title(poet, title_part, page_size, offset):
    """「作者，篇名」组合搜索：查某作者名下标题匹配的作品。"""
    like_all, like_pre = f"%{title_part}%", f"{title_part}%"
    return db_query(
        "SELECT * FROM poems WHERE poet = ? AND title LIKE ? "
        "ORDER BY CASE WHEN title LIKE ? THEN 0 ELSE 1 END, popularity DESC, title "
        "LIMIT ? OFFSET ?",
        (poet, like_all, like_pre, page_size, offset),
    )


def count_poems_by_poet_and_title(poet, title_part):
    """「作者，篇名」组合搜索的总数统计。"""
    rows = db_query(
        "SELECT COUNT(*) AS c FROM poems WHERE poet = ? AND title LIKE ?",
        (poet, f"%{title_part}%"),
    )
    return rows[0]["c"] if rows else 0


def get_poems_by_title_exact(title, page_size, offset):
    """按标题「精确」匹配查作品（同名按知名度降序），分页。"""
    return db_query(
        "SELECT * FROM poems WHERE title = ? ORDER BY popularity DESC, title LIMIT ? OFFSET ?",
        (title, page_size, offset),
    )


def count_poems_by_title_exact(title):
    """按标题「精确」匹配统计总数。"""
    rows = db_query("SELECT COUNT(*) AS c FROM poems WHERE title = ?", (title,))
    return rows[0]["c"] if rows else 0


def get_poet_info(name):
    """查某位诗人的简介（poet_info 表），返回单条 dict 或 None。"""
    rows = db_query(
        "SELECT name, dynasty, intro FROM poet_info WHERE name = ?", (name,)
    )
    return rows[0] if rows else None
