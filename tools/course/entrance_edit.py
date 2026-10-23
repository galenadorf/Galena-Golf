"""A close-up aerial of the clubhouse and entrance, to place the big Woodbine Bend sign (green board on posts, a golf ball on a red
tee at each end, a stone-edged flower bed) on. Writes out/entrance_zoom.png (8x enlargement of the 0.5 m aerial, 16 px per metre) and
out/entrance_zoom.json (its frame: e0, n1, ppm, w, h). Pass a different box with: python entrance_edit.py e0 n0 e1 n1 (local metres).
Paint SOLID colours on a copy, saved as out/entrance_zoom_mask.png (hard edges, no anti-aliasing, don't resize or crop):
  PURPLE  #8000FF  the sign's footprint, one filled rectangle (any rotation): its long side is the board's width (the board is
                   drawn about 7 m wide, so a bed 8-9 m long by 2-3 m deep suits), its short side the flower bed's depth.
  BLUE    #0000FF  (optional) a thin strip, 4+ px, just outside the long side that FACES the road (the lettering side).
                   With no strip the sign faces the nearest road.
Everything else on the map (grid, outlines, labels) is only a guide and is ignored."""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import osm
from common import OUT
from preview import E0, N1, load_rgb

YD = .9144
S = 8   # enlargement over the 0.5 m aerial


def main(box=(10, -250, 230, -90)):
    F = osm.load()
    rgb, res = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    base = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    e0, n0, e1, n1 = box
    c = (int((e0 - E0) / res), int((N1 - n1) / res), int((e1 - E0) / res), int((N1 - n0) / res))
    img = base.crop(c).resize(((c[2] - c[0]) * S, (c[3] - c[1]) * S), Image.BICUBIC)
    ppm = S / res
    fe0, fn1 = E0 + c[0] * res, N1 - c[1] * res
    px = lambda e, n: ((e - fe0) * ppm, (fn1 - n) * ppm)
    d = ImageDraw.Draw(img, 'RGBA')
    f1 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    W, H = img.size
    for k in range(int(W / ppm / (10 * YD)) + 1):   # 10-yard grid
        x = k * 10 * YD * ppm
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 50), width=1)
        if k % 5 == 0:
            d.text((x + 4, 4), f'{k * 10}', fill=(255, 255, 255, 220), font=f2)
    for k in range(int(H / ppm / (10 * YD)) + 1):
        y = H - k * 10 * YD * ppm
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 50), width=1)
        if k % 5 == 0:
            d.text((4, y - 24), f'{k * 10}', fill=(255, 255, 255, 220), font=f2)
    outline = lambda g, col, w=2: [d.line([px(*q) for q in p.exterior.coords], fill=col, width=w) for p in getattr(g, 'geoms', [g])]
    for f in F['tee']:
        outline(f['poly'], (255, 120, 255, 255))
    for f in F['green']:
        outline(f['poly'], (255, 255, 255, 255))
    for f in F['building']:
        outline(f['poly'], (255, 200, 80, 255))
    for r in F['road']:
        pts = [px(*q) for q in r['line'].coords]
        d.line(pts, fill=(80, 220, 255, 220), width=3)
        if r['tags'].get('name') and any(0 <= x < W and 0 <= y < H for x, y in pts):
            x, y = next(p for p in pts if 0 <= p[0] < W and 0 <= p[1] < H)
            d.text((x + 8, y + 8), r['tags']['name'], fill=(80, 220, 255, 255), font=f2, stroke_width=2, stroke_fill=(0, 0, 0, 255))
    d.rectangle([20, H - 190, 1060, H - 20], fill=(0, 0, 0, 190))
    d.rectangle([40, H - 172, 100, H - 148], fill=(128, 0, 255, 255))
    d.text((120, H - 176), 'PURPLE rectangle: the sign and its flower bed', fill=(255, 255, 255, 255), font=f1)
    d.rectangle([40, H - 130, 100, H - 112], fill=(0, 0, 255, 255))
    d.text((120, H - 136), 'BLUE strip (optional): the side facing the road', fill=(255, 255, 255, 255), font=f1)
    d.text((40, H - 90), 'Cyan = roads, orange = buildings, pink = tee boxes, grid = 10 yd squares.', fill=(255, 255, 255, 255), font=f2)
    L = 10 * YD * ppm
    d.line([(40, H - 50), (40 + L, H - 50)], fill=(255, 255, 255, 255), width=6)
    d.text((60 + L, H - 64), '= 10 yd', fill=(255, 255, 255, 255), font=f1)
    img.convert('RGB').save(os.path.join(OUT, 'entrance_zoom.png'))
    json.dump({'e0': fe0, 'n1': fn1, 'ppm': ppm, 'w': W, 'h': H}, open(os.path.join(OUT, 'entrance_zoom.json'), 'w'))
    print(img.size, 'px; 10 yd =', round(L), 'px; box', box)


if __name__ == '__main__':
    a = [float(x) for x in sys.argv[1:5]]
    main(tuple(a) if len(a) == 4 else (10, -250, 230, -90))
