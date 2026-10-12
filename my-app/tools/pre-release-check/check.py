# -*- coding: utf-8 -*-
"""
发布前检查 Skill · check.py
诗迹山河：发布/推送前跑一遍，五项体检，逐项报 ✓/✗。

用法（在仓库根目录执行）：
  C:/Users/23850/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
      my-app/tools/pre-release-check/check.py

零第三方依赖（只用标准库），整个 pre-release-check 文件夹拷到其他项目即可复用。
退出码：0 = 全部通过；1 = 存在异常项。
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib import request as urlreq

sys.stdout.reconfigure(encoding="utf-8")

# ---------- 路径 ----------
SKILL_DIR = Path(__file__).resolve().parent          # .../my-app/tools/pre-release-check
MYAPP = SKILL_DIR.parents[1]                         # .../my-app
ROOT = SKILL_DIR.parents[2]                          # 仓库根（vibe coding/）
REPORT_DIR = ROOT / ".workbuddy" / "reports" / "pre-release"

# ---------- 公网地址（换项目时改这里） ----------
SITE = "https://shijishanhe-d5gmc8a0k01b1e88d-1500007936.tcloudbaseapp.com/"
PAGES = ["home.html", "index.html", "detail.html", "footprints.html", "mock/index.html"]

API_BASE = "https://shijishanhe-d5gmc8a0k01b1e88d.service.tcloudbase.com/api/"
APIS = ["health", "hot", "favorites", "checkins"]

TIMEOUT = 10

# ---------- 密钥扫描规则 ----------
# 设计要点：sk- 后要跟 20 位以上连续字母数字，避免误伤文档里写的模式名「sk-」
KEY_PATTERNS = [
    ("OpenAI 风格密钥（sk-...）", r"sk-[A-Za-z0-9]{20,}"),
    ("腾讯云 SecretId（AKID...）", r"AKID[A-Za-z0-9]{16,}"),
    ("password/api_key 赋值", r"(?i)\b(password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*[\"'][^\"']{8,}[\"']"),
    ("secret/token 赋值", r"(?i)\b(secret|token)\s*[:=]\s*[\"'][A-Za-z0-9+/_-]{16,}[\"']"),
]
SCAN_EXT = {".html", ".js", ".py", ".json", ".css", ".md"}
SCAN_SKIP_DIRS = {"node_modules", "__pycache__", "pre-release-check"}  # 不扫自己
SCAN_SKIP_FILES = {"title_index.json", "fetch_progress.json", "fetch_content_progress.json"}


class Report:
    """收集五项检查结果，最后统一输出终端 + 报告文件"""

    def __init__(self):
        self.rows = []          # (编号, 名称, ok:bool, 明细行列表)

    def add(self, code, name, ok, details):
        self.rows.append((code, name, ok, details))

    @property
    def all_ok(self):
        return all(ok for _, _, ok, _ in self.rows)

    def print_and_save(self):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"# 发布前检查报告", f"- 时间：{ts}", ""]
        passed = 0
        for code, name, ok, details in self.rows:
            mark = "✅ 通过" if ok else "❌ 异常"
            if ok:
                passed += 1
            lines.append(f"## {code} {name} —— {mark}")
            for d in details:
                lines.append(f"- {d}")
            lines.append("")
        n = len(self.rows)
        verdict = f"5/5 全部通过，可以发布 ✅" if self.all_ok else f"{passed}/{n} 通过，存在异常，禁止发布 ❌"
        lines.append(f"## 结论：{verdict}")
        text = "\n".join(lines)

        print(text)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        fname = REPORT_DIR / f"report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        fname.write_text(text, encoding="utf-8")
        print(f"\n（报告已存：{fname}）")
        return fname


def git(*args):
    """在仓库根目录执行 git 命令，返回 (成功?, 输出)"""
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
        return r.returncode == 0, (r.stdout or "").strip()
    except Exception as e:
        return False, str(e)


def http_get(url):
    """返回 (状态码, 响应体文本)；异常时状态码为 0"""
    try:
        req = urlreq.Request(url, headers={"User-Agent": "pre-release-check/1.0"})
        with urlreq.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read(65536).decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


# ---------- 检查 1：密钥泄露扫描 ----------
def check_secrets():
    hits, scanned = [], 0
    for f in MYAPP.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in SCAN_EXT:
            continue
        parts = set(f.relative_to(MYAPP).parts[:-1])
        if parts & SCAN_SKIP_DIRS or f.name in SCAN_SKIP_FILES or f.name == ".env":
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned += 1
        rel = f.relative_to(ROOT)
        for i, line in enumerate(text.splitlines(), 1):
            for label, pat in KEY_PATTERNS:
                if re.search(pat, line):
                    snippet = line.strip()[:120]
                    hits.append(f"{rel}:{i}  [{label}]  {snippet}")
    detail = [f"共扫描 {scanned} 个文本文件"] + (hits if hits else ["未发现任何密钥形态的字符串"])
    return ("1", "密钥泄露扫描", not hits, detail)


# ---------- 检查 2：.env 防护 ----------
def check_env():
    candidates = [ROOT / ".env", MYAPP / ".env"]
    existing = [p for p in candidates if p.exists()]
    if not existing:
        return ("2", ".env 防护", True, ["仓库内不存在 .env 文件（无需防护）"])
    ok, details = True, []
    for p in existing:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        ignored, out = git("check-ignore", rel)
        if not ignored:
            ok = False
            details.append(f"❌ {rel} 未被 .gitignore 覆盖（有被提交的风险）")
        else:
            details.append(f"✓ {rel} 已被 .gitignore 覆盖（{out}）")
        _, tracked = git("ls-files", rel)
        if tracked:
            ok = False
            details.append(f"❌ {rel} 已被 git 跟踪：{tracked}")
        else:
            details.append(f"✓ {rel} 未被 git 跟踪")
    return ("2", ".env 防护", ok, details)


# ---------- 检查 3：公网可达 ----------
def check_pages():
    ok, details = True, []
    for page in PAGES:
        url = SITE + page
        code, _ = http_get(url)
        if code == 200:
            details.append(f"✓ {page} → 200")
        else:
            ok = False
            details.append(f"❌ {page} → HTTP {code}（{url}）")
    return ("3", "公网可达", ok, details)


# ---------- 检查 4：API 健康 ----------
def check_apis():
    ok, details = True, []
    for name in APIS:
        url = API_BASE + name
        code, body = http_get(url)
        try:
            data = json.loads(body)
            is_ok = code == 200 and isinstance(data, dict) and data.get("ok") is True
        except Exception:
            is_ok = False
        if is_ok:
            details.append(f"✓ /api/{name} → 200 且 ok:true")
        else:
            ok = False
            details.append(f"❌ /api/{name} → HTTP {code}，响应开头：{body[:80]}")
    return ("4", "API 健康", ok, details)


# ---------- 检查 5：资源引用完整 ----------
REF_RE = re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", re.I)
SKIP_PREFIX = ("http://", "https://", "//", "data:", "#", "mailto:", "javascript:", "${", "{{")
HTML_PAGES = ["home.html", "index.html", "detail.html", "footprints.html", "mock/index.html"]


def check_refs():
    missing, checked = [], 0
    for page in HTML_PAGES:
        f = MYAPP / page
        if not f.exists():
            missing.append(f"页面本身不存在：{page}")
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        base_dir = f.parent
        for m in REF_RE.finditer(text):
            raw = m.group(1).strip()
            if not raw or raw.lower().startswith(SKIP_PREFIX):
                continue
            target = raw.split("#")[0].split("?")[0].strip()
            if not target:
                continue
            checked += 1
            full = (MYAPP / target.lstrip("/")) if target.startswith("/") else (base_dir / target)
            if not full.is_file():
                missing.append(f"{page} 引用了不存在的文件：{raw}")
    ok = not missing
    detail = [f"共核对 {checked} 个本地引用"] + (missing if missing else ["全部引用都能找到对应文件"])
    return ("5", "资源引用完整", ok, detail)


def main():
    print("诗迹山河 · 发布前检查\n" + "=" * 50)
    rep = Report()
    rep.add(*check_secrets())
    rep.add(*check_env())
    rep.add(*check_pages())
    rep.add(*check_apis())
    rep.add(*check_refs())
    fname = rep.print_and_save()
    sys.exit(0 if rep.all_ok else 1)


if __name__ == "__main__":
    main()
