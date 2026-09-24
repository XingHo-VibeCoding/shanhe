# -*- coding: utf-8 -*-
"""
import_rank.py — 计算并写入 poems.db 的 popularity（知名度）字段。

双层策略：
  1. 名篇榜（poetry_famous.json）—— 公认名篇（中小学必背 + 经典唐诗宋词）：
     tier1（超级名篇）→ 100,000,000；tier2（名篇）→ 50,000,000。
     按「作者精确 + 标题模糊」匹配，保证排在最前的一定是真名篇。
  2. 百度热度（rank/poet|ci 目录）—— 长尾兜底，用 baidu 单引擎结果条数。
     清洗规则：跳过单字标题、以「句」开头的残句（《全唐诗》里的残句集），
     避免「大」「句」这类超高频单字把冷门内容顶到前面。
"""
import glob
import json
import os
import sqlite3

import zhconv

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(BASE), "_poetry_src")
DB = os.path.join(BASE, "poems.db")
FAMOUS = os.path.join(BASE, "poetry_famous.json")

TIER_SCORE = {"tier1": 100_000_000, "tier2": 50_000_000}


def simp(s):
    return zhconv.convert(str(s), "zh-cn").strip()


def is_noise_title(title):
    """判断是否为噪声标题：单字、或残句（《全唐诗》里的『句』残句集）"""
    t = title.strip()
    if len(t) < 2:
        return True
    if t.startswith("句"):
        return True
    return False


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # ① 清空旧热度
    cur.execute("UPDATE poems SET popularity = 0")
    print("① 已清空旧热度")

    # ② 名篇榜
    famous = json.load(open(FAMOUS, encoding="utf-8"))
    hit = 0
    for tier in ("tier1", "tier2"):
        score = TIER_SCORE[tier]
        for poet, title in famous[tier]:
            # 作者精确 + 标题前缀匹配（覆盖「凉州词二首」「绝句四首」这类带序号标题，
            # 且不会误命中「三绝句」「夔州歌十绝句」这类以别的字开头的诗）
            cur.execute(
                "UPDATE poems SET popularity=? WHERE poet=? AND title LIKE ?",
                (score, poet, title + "%"),
            )
            hit += cur.rowcount
    print("② 名篇榜：%d 个条目，命中 %d 首" % (sum(len(v) for v in famous.values()), hit))

    # ③ 百度热度长尾（仅对名篇榜没命中的 popularity=0 的条目）
    n_read = 0
    n_skip = 0
    batch = []
    for pattern, title_key in (
        (os.path.join(SRC, "rank", "poet", "poet.tang.rank.*.json"), "title"),
        (os.path.join(SRC, "rank", "poet", "poet.song.rank.*.json"), "title"),
        (os.path.join(SRC, "rank", "ci", "ci.song.rank.*.json"), "rhythmic"),
    ):
        for f in glob.glob(pattern):
            for it in json.load(open(f, encoding="utf-8")):
                author = simp(it.get("author", ""))
                title = simp(it.get(title_key, ""))
                if not author or not title:
                    continue
                n_read += 1
                if is_noise_title(title):
                    n_skip += 1
                    continue
                s = it.get("baidu") or 0
                if s <= 0:
                    continue
                batch.append((s, author, title))
    print("③ 百度长尾：读取 %d 条，跳过噪声 %d 条，有效 %d 条" % (n_read, n_skip, len(batch)))

    # 只更新 popularity 仍为 0 的（名篇榜优先）
    cur.executemany(
        "UPDATE poems SET popularity=? WHERE poet=? AND title=? AND popularity=0", batch
    )
    conn.commit()

    total = cur.execute("SELECT COUNT(*) FROM poems WHERE popularity > 0").fetchone()[0]
    print("④ 完成！有热度 %d 首\n" % total)

    print("=== 全库知名度 TOP 20 ===")
    for r in cur.execute(
        "SELECT poet, title, dynasty, popularity FROM poems "
        "WHERE popularity > 0 ORDER BY popularity DESC LIMIT 20"
    ).fetchall():
        print("   %s · %s | %s | %d" % (r[0], r[1], r[2], r[3]))
    conn.close()


if __name__ == "__main__":
    main()
