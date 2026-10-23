"""Close-up aerials of every hole's tee area (8x enlargement of the 0.5 m aerial, 16 px per metre), to paint the tee boxes on with
far more precision than the whole-course map allows. Writes out/tee<hole>_zoom.png and out/tee<hole>_zoom.json (the frame: e0, n1,
ppm, w, h) for every hole, or only the holes given: python tee_zoom_edit.py 3 7 12.
Paint SOLID colours on a copy of a hole's picture, saved as out/tee<hole>_zoom_mask.png (hard edges, no anti-aliasing, don't
resize or crop):
  MAGENTA #FF00FF  the tee box(es): fill each whole box, one blob per box (a tee box is usually a long rectangle; the picture shows
                   the current box as a pink outline, and the tee sets as gold, black, silver and bronze rings)
  YELLOW  #FFFF00  (optional) one dot, 12+ px across, where the played (gold) tee should be
A hole with no mask keeps its current tee boxes. Everything else on the picture is only a guide and is ignored."""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from shapely.geometry import Point

import osm
from common import OUT
from preview import E0, N1, load_rgb

YD = .9144
S = 8


def main(refs=None):
    F = osm.load()
    rgb, res = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    base = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    js = open(os.path.join(OUT, 'rd_woodbine.js')).read()
    rd = json.loads(js[js.index('{'):js.rindex('};\nconst GREEN_ALTI') + 1])
    f1 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    cols = {'w': ((217, 178, 58, 255), 'gold'), 'y': ((20, 20, 20, 255), 'black'), 'b': ((235, 240, 245, 255), 'silver'), 'r': ((176, 112, 69, 255), 'bronze')}
    for h in F['hole']:
        ref = h['ref']
        if refs and ref not in refs:
            continue
        s0 = h['line'].coords[0]
        near = [t['poly'] for t in F['tee'] if t['poly'].centroid.distance(Point(s0)) < 45]
        mk = rd['holes'][ref - 1]['mk']
        xs = [q[0] for p in near for q in p.exterior.coords]
        ys = [q[1] for p in near for q in p.exterior.coords]
        for k in mk:   # a tee set's ring only widens the picture when it is close to the boxes
            if min(Point(mk[k]).distance(p) for p in near) < 20:
                xs.append(mk[k][0]); ys.append(mk[k][1])
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        hw, hh = max(32, (max(xs) - min(xs)) / 2 + 14), max(24, (max(ys) - min(ys)) / 2 + 14)
        c = (int((cx - hw - E0) / res), int((N1 - cy - hh) / res), int((cx + hw - E0) / res), int((N1 - cy + hh) / res))
        img = base.crop(c).resize(((c[2] - c[0]) * S, (c[3] - c[1]) * S), Image.BICUBIC)
        ppm = S / res
        fe0, fn1 = E0 + c[0] * res, N1 - c[1] * res
        px = lambda e, n: ((e - fe0) * ppm, (fn1 - n) * ppm)
        d = ImageDraw.Draw(img, 'RGBA')
        W, H = img.size
        for k in range(int(W / ppm / (10 * YD)) + 1):
            x = k * 10 * YD * ppm
            d.line([(x, 0), (x, H)], fill=(255, 255, 255, 50), width=1)
        for k in range(int(H / ppm / (10 * YD)) + 1):
            y = H - k * 10 * YD * ppm
            d.line([(0, y), (W, y)], fill=(255, 255, 255, 50), width=1)
        outline = lambda g, col, w=2: [d.line([px(*q) for q in p.exterior.coords], fill=col, width=w) for p in getattr(g, 'geoms', [g])]
        for t in F['tee']:
            outline(t['poly'], (255, 120, 255, 255))
        for g in F['green']:
            outline(g['poly'], (255, 255, 255, 255))
        d.line([px(*q) for q in h['line'].coords], fill=(0, 220, 255, 200), width=2)
        for kk, (col, name) in cols.items():
            x, y = px(*mk[kk])
            d.ellipse([x - 14, y - 14, x + 14, y + 14], outline=col, width=4)
            d.text((x + 18, y - 34), name, fill=col, font=f2, stroke_width=2, stroke_fill=(0, 0, 0, 255))
        d.rectangle([20, H - 150, 900, H - 20], fill=(0, 0, 0, 190))
        d.text((40, H - 144), f'HOLE {ref}', fill=(255, 255, 255, 255), font=f1)
        d.rectangle([220, H - 140, 270, H - 118], fill=(255, 0, 255, 255))
        d.text((284, H - 144), 'MAGENTA: fill each tee box', fill=(255, 255, 255, 255), font=f1)
        d.ellipse([220, H - 106, 250, H - 76], fill=(255, 255, 0, 255))
        d.text((284, H - 110), 'YELLOW dot (optional): the played tee', fill=(255, 255, 255, 255), font=f1)
        L = 10 * YD * ppm
        d.line([(40, H - 50), (40 + L, H - 50)], fill=(255, 255, 255, 255), width=6)
        d.text((60 + L, H - 64), '= 10 yd   pink outline = box now   cyan = the hole', fill=(255, 255, 255, 255), font=f2)
        img.convert('RGB').save(os.path.join(OUT, f'tee{ref}_zoom.png'))
        json.dump({'ref': ref, 'e0': fe0, 'n1': fn1, 'ppm': ppm, 'w': W, 'h': H}, open(os.path.join(OUT, f'tee{ref}_zoom.json'), 'w'))
        print(ref, img.size)


if __name__ == '__main__':
    main({int(x) for x in sys.argv[1:]} or None)
