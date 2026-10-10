# -*- coding: utf-8 -*-
"""gen_terrain.py — 预生成分层设色+山体阴影地势瓦片，并注入 footprints.html。

数据源：Mapzen Terrarium 高程瓦片（AWS 公开数据集，需网络/代理）。
输出：window.TERRAIN_TILES = { "z/x/y": "data:image/png;base64,...", ... }
写入两处：
  1) my-app/data/terrain-manifest.js（独立清单，便于检查）
  2) my-app/footprints.html 中 <script id="terrainManifest"> 标记处（页面内联，离线可用）
"""
import base64
import io
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # my-app/
HTML = os.path.join(ROOT, "footprints.html")
OUT_JS = os.path.join(ROOT, "data", "terrain-manifest.js")

# ---- 与页面图例严格一致的分层设色色带 ----
BANDS = [
    (100,   (92, 140, 86),    0.42),   # 平原     绿
    (300,   (150, 168, 92),   0.46),   # 台地     浅黄绿
    (500,   (214, 196, 116),  0.48),   # 丘陵     浅黄
    (1000,  (214, 166, 94),   0.50),   # 低山     黄褐
    (2000,  (192, 120, 74),   0.52),   # 中山     褐
    (4000,  (164, 90, 60),    0.55),   # 高山高原 深褐
    (6000,  (219, 213, 203),  0.58),   # 雪线附近 灰白
    (10**9, (245, 242, 236),  0.60),   # 极高峰   白
]
EXAG = 6.0            # 垂直夸张倍数（与上一版浏览器内算法一致）
Z_RANGE = (3, 4, 5, 6)
LNG_MIN, LNG_MAX, LAT_MAX, LAT_MIN = 95.0, 125.0, 42.0, 15.0
ALPHA_GAIN, ALPHA_CAP = 1.12, 0.68
BF_MIN, BF_MAX = 0.30, 1.55

sess = requests.Session()


def lat_to_row(lat, z):
    s = math.sin(math.radians(lat))
    return (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * (2 ** z)


def row_to_lat(yf, z):
    n = math.pi - 2 * math.pi * yf / (2 ** z)
    return math.degrees(math.atan(0.5 * (math.exp(n) - math.exp(-n))))


def tiles_for(z):
    n = 2 ** z
    xa = int(math.floor((LNG_MIN + 180) / 360 * n))
    xb = int(math.floor((LNG_MAX + 180) / 360 * n))
    ya = int(math.floor(lat_to_row(LAT_MAX, z)))
    yb = int(math.floor(lat_to_row(LAT_MIN, z)))
    return [(z, x, y) for x in range(xa, xb + 1) for y in range(ya, yb + 1)]


def band(e):
    for mx, col, a in BANDS:
        if e < mx:
            return col, a
    return BANDS[-1][1], BANDS[-1][2]


def fetch_raw(z, x, y):
    url = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{}/{}/{}.png".format(z, x, y)
    last = None
    for attempt in range(3):
        try:
            r = sess.get(url, timeout=40)
            r.raise_for_status()
            return r.content
        except Exception as ex:
            last = ex
            time.sleep(1.5 * (attempt + 1))
    raise last


def process(key):
    z, x, y = key
    raw = fetch_raw(z, x, y)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    px = img.load()

    E = [[0.0] * 256 for _ in range(256)]
    for rj in range(256):
        row = E[rj]
        for ci in range(256):
            p = px[ci, rj]
            row[ci] = p[0] * 256 + p[1] + p[2] / 256.0 - 32768

    lat_c = row_to_lat(y + 0.5, z)
    cell = 156543.03392 * math.cos(math.radians(lat_c)) / (2 ** z) / EXAG
    az, zen = math.radians(315), math.radians(45)
    lx = math.sin(az) * math.sin(zen)
    ly = math.cos(az) * math.sin(zen)
    lz = math.cos(zen)

    out = Image.new("RGBA", (256, 256))
    opx = out.load()
    for rj in range(256):
        r0 = rj - 1 if rj > 0 else 0
        r2 = rj + 1 if rj < 255 else 255
        for ci in range(256):
            c0 = ci - 1 if ci > 0 else 0
            c2 = ci + 1 if ci < 255 else 255
            e = E[rj][ci]
            if e < 0:
                continue  # 海面：保持全透明
            gx = ((E[r0][c0] + 2 * E[rj][c0] + E[r2][c0])
                  - (E[r0][c2] + 2 * E[rj][c2] + E[r2][c2])) / (8 * cell)
            gy = ((E[r0][c0] + 2 * E[r0][ci] + E[r0][c2])
                  - (E[r2][c0] + 2 * E[r2][ci] + E[r2][c2])) / (8 * cell)
            nx, ny = -gx, -gy
            nl = math.sqrt(nx * nx + ny * ny + 1)
            shade = (nx * lx + ny * ly + lz) / nl
            shade = 0 if shade < 0 else (1 if shade > 1 else shade)
            bf = shade * 1.4142
            bf = BF_MIN if bf < BF_MIN else (BF_MAX if bf > BF_MAX else bf)
            col, a = band(e)
            alpha = a * ALPHA_GAIN
            if alpha > ALPHA_CAP:
                alpha = ALPHA_CAP
            opx[ci, rj] = (
                min(255, int(col[0] * bf + 0.5)),
                min(255, int(col[1] * bf + 0.5)),
                min(255, int(col[2] * bf + 0.5)),
                int(alpha * 255 + 0.5),
            )
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return key, buf.getvalue()


def main():
    keys = []
    for z in Z_RANGE:
        ks = tiles_for(z)
        print("z{}: {} tiles".format(z, len(ks)), flush=True)
        keys += ks
    print("total:", len(keys), flush=True)

    tiles = {}
    fails = []
    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(process, k): k for k in keys}
        for f in as_completed(futs):
            k = futs[f]
            try:
                _, png = f.result()
                tiles["{}/{}/{}".format(*k)] = (
                    "data:image/png;base64," + base64.b64encode(png).decode()
                )
            except Exception as ex2:
                fails.append((k, str(ex2)))
                print("FAIL", k, ex2, flush=True)
            done += 1
            if done % 10 == 0:
                print("progress {}/{}".format(done, len(keys)), flush=True)

    print("ok: {}  fail: {}".format(len(tiles), len(fails)), flush=True)
    if not tiles:
        sys.exit("no tiles generated")

    js = "window.TERRAIN_TILES=" + json.dumps(tiles, separators=(",", ":")) + ";"
    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write(js)
    print("manifest bytes:", len(js), flush=True)

    with open(HTML, "r", encoding="utf-8") as f:
        html = f.read()
    new_html, n = re.subn(
        r'(<script id="terrainManifest">).*?(</script>)',
        lambda m: m.group(1) + js + m.group(2),
        html,
        flags=re.S,
    )
    if n != 1:
        sys.exit("marker <script id=\"terrainManifest\"> not found")
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(new_html)
    print("injected into footprints.html, new size:", len(new_html), flush=True)


if __name__ == "__main__":
    main()
