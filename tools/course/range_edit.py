"""A close-up aerial of the driving range (the field south of the cart road, west of the clubhouse lot), to paint it on.
Writes out/range_edit.png (5 px per metre), out/range_edit.json (its frame: e0, n1, ppm, w, h) and out/range_start.png: the same size, with the
OSM driving-range outline already filled green as a first guess. Paint SOLID colours on a copy of range_start.png, saved as out/range_mask.png
(hard edges, no anti-aliasing, don't resize or crop). Everything on range_edit.png (grid, outlines, labels, the key) is only a guide.
  GREEN #00FF00 mown range grass     CYAN #00FFFF a target green (with its fringe)   MAGENTA #FF00FF deep fescue     ORANGE #FF8000 bunkers
  BLUE #0000FF dots: hitting spots (any number; the player chooses one)               RED #FF0000 dots: the three flags (target distances)
  YELLOW #FFFF00 dots: one broadleaf tree as wide as the dot                          anything else = first cut rough"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import osm
from common import OUT
from preview import E0, N1, load_rgb

YD = .9144
PPM = 5
BOX = (-200, -440, 100, -190)   # local metres: west, south, east, north


def main():
    F = osm.load()
    rgb, res = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    base = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    e0, n0, e1, n1 = BOX
    c = (int((e0 - E0) / res), int((N1 - n1) / res), int((e1 - E0) / res), int((N1 - n0) / res))
    k = PPM * res
    img = base.crop(c).resize((round((c[2] - c[0]) * k), round((c[3] - c[1]) * k)), Image.BICUBIC)
    fe0, fn1 = E0 + c[0] * res, N1 - c[1] * res
    px = lambda e, n: ((e - fe0) * PPM, (fn1 - n) * PPM)
    W, H = img.size
    start = Image.new('RGB', (W, H), (0, 0, 0))   # black = nothing painted (first cut)
    sd = ImageDraw.Draw(start)
    for g in F.get('driving_range', []):
        for p in getattr(g['poly'], 'geoms', [g['poly']]):
            sd.polygon([px(*q) for q in p.exterior.coords], fill=(0, 255, 0))
    start.save(os.path.join(OUT, 'range_start.png'))
    d = ImageDraw.Draw(img, 'RGBA')
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    for q in range(int(np.floor(fe0 / (50 * YD))), int(np.ceil((fe0 + W / PPM) / (50 * YD))) + 1):   # 50-yard grid
        x = px(q * 50 * YD, 0)[0]
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 70), width=1)
        d.text((x + 4, H - 28), f'E{q * 50}yd', fill=(255, 255, 255, 230), font=f2)
    for q in range(int(np.floor((fn1 - H / PPM) / (50 * YD))), int(np.ceil(fn1 / (50 * YD))) + 1):
        y = px(0, q * 50 * YD)[1]
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 70), width=1)
        d.text((4, y + 3), f'N{q * 50}yd', fill=(255, 255, 255, 230), font=f2)
    outline = lambda g, col, w=2: [d.line([px(*q) for q in p.exterior.coords], fill=col, width=w) for p in getattr(g, 'geoms', [g])]
    for key, col in (('tee', (255, 120, 255, 255)), ('green', (255, 255, 255, 255)), ('building', (255, 200, 80, 255)), ('bunker', (255, 140, 0, 255)), ('driving_range', (255, 255, 0, 255))):
        for f in F.get(key, []):
            outline(f['poly'], col)
    L = 10 * YD * PPM
    d.rectangle([20, 20, 20 + 360, 100], fill=(0, 0, 0, 170))
    d.line([(36, 50), (36 + L, 50)], fill=(255, 255, 255, 255), width=5)
    d.text((52 + L, 50), '= 10 yd (grid: 50 yd)', fill=(255, 255, 255, 255), font=f2, anchor='lm')
    img.convert('RGB').save(os.path.join(OUT, 'range_edit.png'))
    json.dump({'e0': fe0, 'n1': fn1, 'ppm': PPM, 'w': W, 'h': H}, open(os.path.join(OUT, 'range_edit.json'), 'w'))
    print(img.size)


if __name__ == '__main__':
    main()
