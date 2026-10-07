# -*- coding: utf-8 -*-
"""
诗迹山河 - 大模型批量补译文/注释脚本

作用：用硅基流动（SiliconFlow）的 DeepSeek 模型，给 poems.db 里
      translation 为空的诗词，逐首生成「译文 + 注释」，写回数据库。

策略：
  - 按 popularity（知名度）降序，先补最出名的诗
  - 每首让模型严格输出 JSON：{"translation": "...", "annotation": "..."}
  - 断点续跑：translation 非空的诗自动跳过，重跑不重复
  - 限速 + 失败重试（最多 2 次），网络抖动自动跳过不崩

用法（在 my-app 目录下）：
  python fetch_llm_translation.py [数量]   # 默认 100 首

密钥：读 my-app/.env 里的 SILICONFLOW_API_KEY（已被 .gitignore 忽略）
"""
import os
import re
import sys
import time
import json
import sqlite3
import requests

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "poems.db")
ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

API_BASE = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "deepseek-ai/DeepSeek-V3.2"

# 每次请求间隔（秒），避免触发限流
SLEEP = 0.5
# 单首失败最大重试次数
MAX_RETRY = 2

# 默认补多少首（命令行第一个参数覆盖）
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 100


def load_env():
    env = {}
    if os.path.exists(ENV):
        with open(ENV, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


API_KEY = load_env().get("SILICONFLOW_API_KEY", "")

SYSTEM_PROMPT = (
    "你是一位精通中国古代诗词的学者。请把用户提供的古诗翻译成现代白话文，"
    "并给出简明的字词注释（解释难懂的字词、典故、地名、人名）。"
    "要求：译文通顺自然、忠实原意；注释精炼、直击要点。"
    "严格只输出一个 JSON 对象，不要输出任何其他文字、解释或 markdown 代码块，格式如下：\n"
    '{"translation": "现代白话译文", "annotation": "字词注释，逐条简要说明"}'
)


def call_llm(title, poet, dynasty, content):
    """调用 DeepSeek，返回 (translation, annotation) 或 None"""
    user_prompt = (
        f"【诗题】{title}\n【作者】{poet}（{dynasty}）\n【原文】\n{content}\n\n"
        "请按 JSON 格式输出译文和注释。"
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    last_err = None
    for attempt in range(MAX_RETRY + 1):
        try:
            resp = requests.post(API_BASE, json=payload, headers=headers, timeout=60)
            if resp.status_code != 200:
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                time.sleep(1)
                continue
            data = resp.json()
            content_out = data["choices"][0]["message"]["content"]
            parsed = parse_json(content_out)
            if parsed:
                return parsed["translation"], parsed["annotation"]
            last_err = f"JSON 解析失败: {content_out[:200]}"
            time.sleep(1)
        except Exception as e:
            last_err = str(e)
            time.sleep(1)
    return None


def parse_json(text):
    """从模型输出里稳健地抽出 JSON（容错：去掉可能的 markdown 代码块包裹）"""
    text = text.strip()
    # 去掉可能的 ```json ... ``` 包裹
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        # 再尝试直接解析
        try:
            obj = json.loads(text)
        except Exception:
            return None
    trans = obj.get("translation", "")
    anno = obj.get("annotation", "")
    if not trans and not anno:
        return None
    return {"translation": str(trans).strip(), "annotation": str(anno).strip()}


def main():
    if not API_KEY:
        print("⚠️  未找到 SILICONFLOW_API_KEY，请先在 my-app/.env 里配置")
        return

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM poems WHERE translation IS NOT NULL AND translation != ''")
    has_trans = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM poems")
    total = cur.fetchone()[0]
    print(f"启动：数据库共 {total} 首，已有译文 {has_trans} 首，待补 {total - has_trans} 首")

    rows = cur.execute(
        "SELECT poem_id, title, poet, dynasty, content FROM poems "
        "WHERE (translation IS NULL OR translation = '') "
        "ORDER BY popularity DESC LIMIT ?",
        (LIMIT,),
    ).fetchall()
    print(f"本次目标：补 {len(rows)} 首（按知名度降序）\n")

    ok = fail = 0
    for i, (pid, title, poet, dynasty, content) in enumerate(rows, 1):
        if not content or not content.strip():
            fail += 1
            print(f"[{i}/{len(rows)}] × {title}（{poet}）无原文，跳过")
            continue

        got = call_llm(title, poet, dynasty, content)
        if got:
            trans, anno = got
            cur.execute(
                "UPDATE poems SET translation=?, annotation=? WHERE poem_id=?",
                (trans, anno, pid),
            )
            conn.commit()
            ok += 1
            print(f"[{i}/{len(rows)}] ✓ {title}（{poet}）译{len(trans)}字 注{len(anno)}字")
        else:
            fail += 1
            print(f"[{i}/{len(rows)}] × {title}（{poet}）调用失败")

        time.sleep(SLEEP)

    print(f"\n完成：成功 {ok} / 失败 {fail} / 共 {len(rows)}")
    cur.execute("SELECT COUNT(*) FROM poems WHERE translation IS NOT NULL AND translation != ''")
    print(f"当前数据库已有译文总数：{cur.fetchone()[0]} 首")
    conn.close()


if __name__ == "__main__":
    main()
