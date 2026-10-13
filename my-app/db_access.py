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


# ===== 通用：脏作者名判定 / 「佚名沉底」排序键 =====

# 「脏作者名」= 数据源残缺的名字：空名、单字残名（如被截断的「王」）、含占位符/替换符的名字。
# 这类名字不代表真实作者，对用户一律显示「佚名」，排序时也一并沉到末尾。
_DIRT_NAME = (
    "(poet IS NULL OR trim(poet) = '' OR length(trim(poet)) <= 1 "
    "OR trim(poet) IN ('佚名', '不详', '缺名') OR poet LIKE '无名%' "
    "OR poet LIKE '%□%' OR poet LIKE '%�%' OR poet LIKE '%?%')"
)

# 排序键：脏名（佚名）记 1 排最后，真实作者记 0 排前面
ANON_LAST = f"CASE WHEN {_DIRT_NAME} THEN 1 ELSE 0 END"


# ===== 推荐 / 每日荐诗 =====

_POET_FAME_CACHE = None


def poet_fame():
    """每位诗人的「名气分」= 该诗人全部作品的 popularity 之和（越大越有名）。

    为什么不用单首的 popularity：名篇的 popularity 大量并列（很多都是 1 亿），
    单看它分不出高下；把一位诗人所有作品的人气加起来，才能体现「这个人有多有名」。
    结果缓存在内存里，整个进程只算一次。
    """
    global _POET_FAME_CACHE
    if _POET_FAME_CACHE is None:
        rows = db_query(
            "SELECT poet, SUM(popularity) AS s FROM poems GROUP BY poet"
        )
        _POET_FAME_CACHE = {r["poet"]: int(r["s"] or 0) for r in rows}
    return _POET_FAME_CACHE


def _pick_recommend(rows, limit, fame, skip_poets=None):
    """从候选行里挑推荐：名诗人优先 → 佚名最后 → 名篇优先，且每位诗人只取 1 首。

    排序键（从主到次）：
      1. 是否佚名（含单字残名）：佚名排到最后；
      2. 诗人名气分（取负值，让大的排前面）；
      3. 这一首自己的 popularity（取负值）；
      4. 标题短的优先（并列时更可能是名篇正题，避免「其一/其二」这类分首）。
    """
    used = set(skip_poets or ())

    def sort_key(r):
        poet = (r.get("poet") or "").strip()
        anon = 1 if (poet == "佚名" or len(poet) <= 1) else 0
        return (
            anon,
            -fame.get(poet, 0),
            -int(r.get("popularity") or 0),
            len(r.get("title") or ""),
            r.get("title") or "",
        )

    picked = []
    for r in sorted(rows, key=sort_key):
        poet = (r.get("poet") or "").strip()
        if poet in used:
            continue
        used.add(poet)
        picked.append(r)
        if len(picked) >= limit:
            break
    return picked


def get_recommend_pool(limit=8):
    """推荐接口候选：名诗人优先、佚名靠后、名篇靠前，每位诗人最多 1 首。

    优先取「有译文」的五件套完整篇目（这样点进详情页有译文/注释），
    不足 limit 时再用其他名篇补齐。
    """
    fame = poet_fame()
    pool = db_query(
        "SELECT * FROM poems WHERE content != '' AND translation != ''"
    )
    picked = _pick_recommend(pool, limit, fame)

    if len(picked) < limit:
        seen = {(r.get("title"), r.get("poet")) for r in picked}
        used_poets = {(r.get("poet") or "").strip() for r in picked}
        extra = [
            r
            for r in db_query(
                "SELECT * FROM poems WHERE content != '' "
                "ORDER BY popularity DESC LIMIT 2000"
            )
            if (r.get("title"), r.get("poet")) not in seen
        ]
        picked += _pick_recommend(extra, limit - len(picked), fame, skip_poets=used_poets)
    return picked[:limit]


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
    """标题联想：前缀优先（如「临」→《临江仙》在前），再包含；去重同名按知名度降序，最多 20 条。"""
    return db_query(
        "SELECT title, poet, dynasty, MAX(popularity) AS popularity FROM poems "
        "WHERE title LIKE ? "
        "GROUP BY title "
        "ORDER BY CASE WHEN title LIKE ? THEN 0 ELSE 1 END, popularity DESC LIMIT 20",
        (f"%{keyword}%", f"{keyword}%"),
    )


def suggest_poets(keyword, limit=6):
    """诗人名联想：前缀优先（如「李」→ 李白/李清照/李贺），按总人气排序更符合名气直觉；包含型最多 3 条。
    过滤单字残名（如数据源截断的「李」）与带占位符的脏名（如「赵必□」），这类不是真实诗人。"""
    prefix = db_query(
        "SELECT poet, dynasty, COUNT(*) AS cnt, SUM(popularity) AS pop FROM poems "
        f"WHERE poet LIKE ? AND NOT {_DIRT_NAME} GROUP BY poet, dynasty ORDER BY pop DESC LIMIT ?",
        (f"{keyword}%", limit),
    )
    contains = db_query(
        "SELECT poet, dynasty, COUNT(*) AS cnt, SUM(popularity) AS pop FROM poems "
        f"WHERE poet LIKE ? AND poet NOT LIKE ? AND NOT {_DIRT_NAME} "
        "GROUP BY poet, dynasty ORDER BY pop DESC LIMIT 3",
        (f"%{keyword}%", f"{keyword}%"),
    )
    return prefix + contains


# ===== 搜索（/search） =====

def poet_exists(name):
    """判断某诗人名在本地库里是否存在。"""
    return bool(db_query("SELECT 1 AS ok FROM poems WHERE poet = ? LIMIT 1", (name,)))


def get_poems_by_poet(keyword, page_size, offset):
    """按诗人名查全部作品（知名度降序，名篇在前），分页。"""
    return db_query(
        f"SELECT * FROM poems WHERE poet = ? ORDER BY {ANON_LAST}, popularity DESC, title LIMIT ? OFFSET ?",
        (keyword, page_size, offset),
    )


def count_poems_by_poet(keyword):
    """按诗人名统计作品总数。"""
    rows = db_query("SELECT COUNT(*) AS c FROM poems WHERE poet = ?", (keyword,))
    return rows[0]["c"] if rows else 0


def get_poems_by_title_like(keyword, page_size, offset):
    """按标题「包含」关键词查作品（知名度降序、佚名沉底），分页。"""
    return db_query(
        f"SELECT * FROM poems WHERE title LIKE ? ORDER BY {ANON_LAST}, popularity DESC, title LIMIT ? OFFSET ?",
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
        f"ORDER BY CASE WHEN title LIKE ? THEN 0 ELSE 1 END, {ANON_LAST}, popularity DESC, title "
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
    """按标题「精确」匹配查作品（同名按知名度降序、佚名沉底），分页。"""
    return db_query(
        f"SELECT * FROM poems WHERE title = ? ORDER BY {ANON_LAST}, popularity DESC, title LIMIT ? OFFSET ?",
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


# ===== 单字姓氏聚合（搜「王」→ 先给王姓名家代表作，再给含「王」字的诗）=====

# 常见单字姓氏（含复姓首字），用于判断一个字该不该按「姓氏」聚合
SURNAME_CHARS = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏窦章苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑"
    "薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧"
    "尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴宋茅庞熊纪舒屈项祝董梁杜阮蓝闵"
    "席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯"
    "管卢莫房裘解应宗丁宣邓郁单杭洪包诸左石崔吉龚程邢裴陆荣翁荀羊惠甄"
    "曲封芮羿储靳汲邴松井段富巫乌焦巴弓牧隗山谷车侯全郗班仰秋仲伊宫宁"
    "仇栾暴甘厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸"
    "籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍桑桂濮"
    "牛寿通边扈燕冀浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖"
    "庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩聂晁勾敖"
    "融冷辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓"
)


def is_surname_char(ch):
    """判断一个字是不是「姓氏」——决定单字搜索要不要按姓氏聚合。

    两个条件取或：① 在常见姓氏表里；② 以它开头的诗人名够多（≥30 位）。
    这样「王」「李」会聚合，而「月」「风」（0 位诗人）不会。
    """
    if len(ch) != 1:
        return False
    if ch in SURNAME_CHARS:
        return True
    rows = db_query(
        "SELECT COUNT(DISTINCT poet) AS c FROM poems WHERE poet LIKE ? AND length(poet) > 1",
        (ch + "%",),
    )
    return bool(rows and rows[0]["c"] >= 30)


def top_poets_by_prefix(ch, limit=24):
    """以某字开头的诗人，按总人气（名气）降序。搜「王」→ 王昌龄/王安石/王维…"""
    return db_query(
        "SELECT poet, dynasty, COUNT(*) AS cnt, SUM(popularity) AS pop FROM poems "
        f"WHERE poet LIKE ? AND NOT {_DIRT_NAME} "
        "GROUP BY poet ORDER BY pop DESC LIMIT ?",
        (ch + "%", limit),
    )


def best_poem_of_poet(poet):
    """某位诗人人气最高的一首代表作（标题短的优先，避开「其一/其二」这类分首）。"""
    rows = db_query(
        "SELECT * FROM poems WHERE poet = ? AND content != '' "
        "ORDER BY popularity DESC, LENGTH(title), title LIMIT 1",
        (poet,),
    )
    return rows[0] if rows else None


def poems_containing(ch, limit=20):
    """标题或正文含某字的诗，按人气降序、佚名沉底。"""
    return db_query(
        "SELECT * FROM poems WHERE content != '' AND (title LIKE ? OR content LIKE ?) "
        f"ORDER BY {ANON_LAST}, popularity DESC, title LIMIT ?",
        (f"%{ch}%", f"%{ch}%", limit),
    )


def surname_showcase(ch, poet_limit=8, total=20):
    """单字姓氏聚合：先给该姓「有名诗人的代表作」（每位 1 首、按名气排，优先级更高），
    再用「含该字的诗」补够 total 首。"""
    rows, seen = [], set()

    for p in top_poets_by_prefix(ch, poet_limit * 3):
        if len(rows) >= poet_limit:
            break
        poem = best_poem_of_poet(p["poet"])
        if not poem:
            continue
        key = (poem.get("title"), poem.get("poet"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(poem)

    if len(rows) < total:
        for poem in poems_containing(ch, limit=(total - len(rows)) * 3):
            key = (poem.get("title"), poem.get("poet"))
            if key in seen:
                continue
            seen.add(key)
            rows.append(poem)
            if len(rows) >= total:
                break
    return rows
