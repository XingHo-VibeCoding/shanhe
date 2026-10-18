# Remove bottom-right "AI生成 WORKBUDDY" watermark by patching
# clean paper texture from directly above, with feathered edges.
# Backs up originals to ink-paintings/_originals/ first.
import os, shutil
from PIL import Image, ImageFilter

BASE = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(BASE, 'ink-paintings')
BAK_DIR = os.path.join(SRC_DIR, '_originals')
os.makedirs(BAK_DIR, exist_ok=True)

files = ['cover.png', 'v1.png', 'v2.png', 'v3.png', 'v4.png', 'v5.png', 'v6.png']

# patch region (relative to bottom-right corner)
PW, PH = 180, 78   # patch width/height
SRC_DY = 100       # take clean texture this many px above the patch
FEATHER = 14       # edge feather in px

for name in files:
    path = os.path.join(SRC_DIR, name)
    bak = os.path.join(BAK_DIR, name)
    if not os.path.exists(bak):
        shutil.copy2(path, bak)

    im = Image.open(path).convert('RGB')
    w, h = im.size
    # region to cover
    x0, y0 = w - PW, h - PH
    # clean source: same x, shifted up
    patch = im.crop((x0, y0 - SRC_DY, x0 + PW, y0 - SRC_DY + PH))
    # slight blur to kill any repeating detail
    patch = patch.filter(ImageFilter.GaussianBlur(0.6))

    # feathered alpha mask (white=opaque patch, soft edges)
    mask = Image.new('L', (PW, PH), 255)
    px = mask.load()
    for yy in range(PH):
        for xx in range(PW):
            d = min(xx, yy, PW - 1 - xx, PH - 1 - yy)
            if d < FEATHER:
                px[xx, yy] = int(255 * d / FEATHER)
    im.paste(patch, (x0, y0), mask)
    im.save(path, 'PNG')
    print('done', name, im.size)

print('ALL OK, originals backed up in', BAK_DIR)
