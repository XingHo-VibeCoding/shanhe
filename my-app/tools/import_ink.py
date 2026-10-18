# -*- coding: utf-8 -*-
"""
import_ink.py — 把 ink-data/<slug>.json 里的水墨画页内容导入云端 ink_pages 表
用法:
    python tools/import_ink.py                     # 导入 ink-data/ 下全部 json
    python tools/import_ink.py dielianhua-chunjing # 只导入指定的一个
依赖: tcb CLI（凭据已在 ~/.config/.cloudbase/），无需数据库密码。
逻辑: INSERT ... ON CONFLICT (slug) DO UPDATE —— 同一 slug 重复执行即更新内容，计数不清零。
"""
import glob
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # my-app/
DATA_DIR = os.path.join(BASE, "ink-data")
ENV_ID = "shijishanhe-d5gmc8a0k01b1e88d"
TCB = r"C:/Users/23850/.workbuddy/binaries/node/versions/22.22.2-6/node.exe"
TCB_CLI = r"C:/Users/23850/.workbuddy/binaries/node/workspace/node_modules/@cloudbase/cli/dist/standalone/cli.js"


def esc(s):
    """SQL 字符串转义：单引号翻倍"""
    return str(s).replace("'", "''")


def upsert(d):
    content = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    sql = (
        "INSERT INTO ink_pages (slug, title, poet, dynasty, form, cover_path, lede, content)"
        " VALUES ('{slug}', '{title}', '{poet}', '{dynasty}', '{form}', '{cover}', '{lede}', '{content}')"
        " ON CONFLICT (slug) DO UPDATE SET"
        " title=EXCLUDED.title, poet=EXCLUDED.poet, dynasty=EXCLUDED.dynasty,"
        " form=EXCLUDED.form, cover_path=EXCLUDED.cover_path, lede=EXCLUDED.lede,"
        " content=EXCLUDED.content, updated_at=now()"
    ).format(
        slug=esc(d["slug"]), title=esc(d["title"]), poet=esc(d["poet"]),
        dynasty=esc(d.get("dynasty", "")), form=esc(d.get("form", "")),
        cover=esc(d.get("cover", {}).get("src", "")),
        lede=esc(d.get("lede", "")), content=esc(content),
    )
    r = subprocess.run(
        [TCB, TCB_CLI, "db", "execute", "-e", ENV_ID, "--sql", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    ok = r.returncode == 0 and ("completed" in out or "Affected" in out)
    return ok, out.strip()


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    pattern = f"{only}.json" if only else "*.json"
    files = sorted(glob.glob(os.path.join(DATA_DIR, pattern)))
    if not files:
        print(f"没找到数据文件: {pattern}")
        sys.exit(1)
    fail = 0
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        ok, out = upsert(d)
        tag = "OK " if ok else "FAIL"
        print(f"[{tag}] {d['slug']}  {d['title']} · {d['poet']}")
        if not ok:
            fail += 1
            print(out[-800:])
    # 对账
    r = subprocess.run(
        [TCB, TCB_CLI, "db", "execute", "-e", ENV_ID, "--sql",
         "SELECT slug, title, views, likes, favs, length(content) AS content_len FROM ink_pages ORDER BY id"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    print("\n--- 云端对账 ---")
    print((r.stdout or "").strip()[-1500:])
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
