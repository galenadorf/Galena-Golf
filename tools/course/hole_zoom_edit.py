"""A close-up aerial of one hole's tee area (default hole 7), to place the tee markers and the sign post on. Writes
out/hole7_zoom.png (8x enlargement of the aerial, ~6 cm per pixel) and out/hole7_zoom.json (its frame: e0, n1, px_per_m).
Paint SOLID colours on a copy, saved as out/hole7_zoom_mask.png (hard edges, no anti-aliasing, don't resize or crop):
  RED     #FF0000  ONE straight line, drawn with a thick brush (8+ px), from the left tee marker to the right tee marker. The two
                   ends are the marker positions, so the line's length is the gap between them (a regulation gap is 5-8 yd,
                   about 80-130 px at the 10 yd scale bar). The tee box is the strip across the line, 3 yd deep behind it.
  YELLOW  #FFFF00  one dot, 12+ px across, where the sign post should stand.
Everything else on the map (grid, outlines, rings, labels) is only a guide and is ignored."""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import osm
from common import OUT, course, load_rd
from preview import E0, N1, load_rgb

YD = .9144
S = 8   # enlargement over the 0.5 m aerial


def main(ref=7, box=(-312, -128, -178, -58)):
    F = osm.load()
    rgb, res = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    base = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    e0, n0, e1, n1 = box
    c = (int((e0 - E0) / res), int((N1 - n1) / res), int((e1 - E0) / res), int((N1 - n0) / res))
    img = base.crop(c).resize(((c[2] - c[0]) * S, (c[3] - c[1]) * S), Image.BICUBIC)
    ppm = S / res   # pixels per metre
    # the crop starts on a whole source pixel, so the true west / north edge is
    fe0, fn1 = E0 + c[0] * res, N1 - c[1] * res
    px = lambda e, n: ((e - fe0) * ppm, (fn1 - n) * ppm)
    d = ImageDraw.Draw(img, 'RGBA')
    f1 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    # 10-yard grid, labelled in yards from the western edge / southern edge
    k = 0
    while fe0 + k * 10 * YD < fe0 + img.size[0] / ppm:
        x = px(fe0 + k * 10 * YD, 0)[0]
        d.line([(x, 0), (x, img.size[1])], fill=(255, 255, 255, 60), width=1)
        d.text((x + 4, 4), f'{k * 10}', fill=(255, 255, 255, 220), font=f2)
        k += 1
    nb = fn1 - img.size[1] / ppm
    k = 0
    while nb + k * 10 * YD < fn1:
        y = px(0, nb + k * 10 * YD)[1]
        d.line([(0, y), (img.size[0], y)], fill=(255, 255, 255, 60), width=1)
        d.text((4, y - 24), f'{k * 10}', fill=(255, 255, 255, 220), font=f2)
        k += 1
    outline = lambda g, col, w=2: [d.line([px(*q) for q in p.exterior.coords], fill=col, width=w) for p in getattr(g, 'geoms', [g])]
    for f in F['tee']:
        outline(f['poly'], (255, 120, 255, 255))
    for f in F['green']:
        outline(f['poly'], (255, 255, 255, 255))
    h = next(x for x in F['hole'] if x['ref'] == ref)
    d.line([px(*q) for q in h['line'].coords], fill=(0, 220, 255, 200), width=2)
    # where each tee set plays from now, and the sign now
    rd = load_rd()
    cols = {m: (c, course.MARKERS[m][0]) for m, c in {'w': (217, 178, 58, 255), 'y': (20, 20, 20, 255), 'b': (235, 240, 245, 255), 'r': (176, 112, 69, 255)}.items()}
    for kk, (col, name) in cols.items():
        x, y = px(*rd['holes'][ref - 1]['mk'][kk])
        d.ellipse([x - 14, y - 14, x + 14, y + 14], outline=col, width=4)
        d.text((x + 18, y - 34), name + ' now', fill=col, font=f2, stroke_width=2, stroke_fill=(0, 0, 0, 255))
    for p in json.load(open(os.path.join(OUT, 'site_props.json'))):
        if p[0] == 'sign':
            x, y = px(p[1], p[2])
            if 0 <= x < img.size[0] and 0 <= y < img.size[1]:
                d.line([(x - 12, y - 12), (x + 12, y + 12)], fill=(255, 255, 255, 255), width=4)
                d.line([(x - 12, y + 12), (x + 12, y - 12)], fill=(255, 255, 255, 255), width=4)
                d.text((x + 18, y - 4), 'sign now', fill=(255, 255, 255, 255), font=f2, stroke_width=2, stroke_fill=(0, 0, 0, 255))
    # key and the 10-yard scale bar, bottom-left
    W, H = img.size
    d.rectangle([20, H - 250, 1020, H - 20], fill=(0, 0, 0, 190))
    d.rectangle([40, H - 232, 100, H - 212], fill=(255, 0, 0, 255))
    d.text((120, H - 238), 'RED line (8+ px thick): left marker to right marker', fill=(255, 255, 255, 255), font=f1)
    d.ellipse([56, H - 190, 86, H - 160], fill=(255, 255, 0, 255))
    d.text((120, H - 192), 'YELLOW dot (12+ px): where the sign post stands', fill=(255, 255, 255, 255), font=f1)
    d.text((40, H - 140), 'Pink outline = tee boxes now.   Rings = where each tee set plays from now.', fill=(255, 255, 255, 255), font=f2)
    d.text((40, H - 112), 'White X = sign now.   Cyan line = the hole.   Grid and numbers = 10 yd squares.', fill=(255, 255, 255, 255), font=f2)
    L = 10 * YD * ppm
    d.line([(40, H - 60), (40 + L, H - 60)], fill=(255, 255, 255, 255), width=6)
    d.text((60 + L, H - 74), '= 10 yd', fill=(255, 255, 255, 255), font=f1)
    img.convert('RGB').save(os.path.join(OUT, f'hole{ref}_zoom.png'))
    json.dump({'ref': ref, 'e0': fe0, 'n1': fn1, 'ppm': ppm, 'w': W, 'h': H}, open(os.path.join(OUT, f'hole{ref}_zoom.json'), 'w'))
    print(img.size, 'px; 10 yd =', round(L), 'px')


if __name__ == '__main__':
    main(*(int(a) for a in sys.argv[1:2]))
