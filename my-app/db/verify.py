# -*- coding: utf-8 -*-
"""Day 16 select 验证：确认两表各 >=5 行，且关联字段正确。"""
import subprocess
import json

TCB = r"C:\Users\23850\.workbuddy\binaries\node\versions\22.22.2-3\tcb.cmd"


def query(sql):
    r = subprocess.run([TCB, "db", "execute", "--sql", sql, "--json"], capture_output=True)
    out = r.stdout.decode("utf-8", errors="replace")
    if r.returncode != 0:
        return None, (r.stderr.decode("gbk", errors="replace") or out)[:300]
    start = out.find("{")
    if start == -1:
        return None, out[:300]
    try:
        return json.loads(out[start:]).get("data"), None
    except Exception as e:
        return None, f"解析失败 {e}: {out[:200]}"


def show(sql, label):
    data, err = query(sql)
    if err:
        print(f"[X] {label}\n    {err}\n")
        return
    cols = data.get("Columns", [])
    rows = [json.loads(x) for x in data.get("Rows", [])]
    print(f"[✓] {label}")
    print("    ", " | ".join(cols))
    for row in rows:
        print("    ", " | ".join(str(v) for v in row))
    print()


show("SELECT COUNT(*) AS cnt FROM poets", "poets 表总行数")
show("SELECT COUNT(*) AS cnt FROM poems", "poems 表总行数")
show("SELECT id, name, dynasty, left(intro, 18) AS intro_head FROM poets ORDER BY id", "poets 表前 10 行")
show("SELECT id, title, poet_id, dynasty, popularity FROM poems ORDER BY id", "poems 表前 12 行")
show(
    "SELECT p.id, p.title, po.name AS poet, po.dynasty AS poet_dynasty "
    "FROM poems p JOIN poets po ON p.poet_id = po.id ORDER BY p.id",
    "关联验证（JOIN poems × poets，靠 poet_id 关联）",
)
