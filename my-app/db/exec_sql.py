# -*- coding: utf-8 -*-
"""Day 16 SQL 执行器
读取 .sql 文件，去掉注释行，按分号拆分语句，逐条通过 tcb db execute 执行。
"""
import sys
import subprocess

TCB = r"C:\Users\23850\.workbuddy\binaries\node\versions\22.22.2-3\tcb.cmd"


def run_sql(sql):
    sql = sql.strip()
    if not sql:
        return True
    one = " ".join(sql.split())  # 合并换行为空格，单行传给 CLI
    if '"' in one:
        print("[SKIP] 含 ASCII 双引号:", one[:60])
        return False
    r = subprocess.run(
        [TCB, "db", "execute", "--sql", one, "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    head = one[:52]
    if r.returncode == 0:
        print(f"[OK]   {head}...")
        return True
    print(f"[FAIL] {head}...")
    print((r.stderr + r.stdout)[-800:])
    return False


def main(path):
    s = open(path, encoding="utf-8").read()
    lines = [l for l in s.split("\n") if not l.strip().startswith("--")]
    s = "\n".join(lines)
    stmts = [x.strip() for x in s.split(";") if x.strip()]
    print(f"== {path} 共 {len(stmts)} 条语句 ==")
    ok = sum(1 for st in stmts if run_sql(st))
    print(f"== 成功 {ok}/{len(stmts)} ==")


if __name__ == "__main__":
    main(sys.argv[1])
