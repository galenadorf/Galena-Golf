"""A disc golf course's tees and baskets, read off its hole map (an aerial photo with the holes drawn on, saved as the course's
hole_map.jpg beside its course.py).

out/disc_map_points.json holds what is picked on the map by eye, in the map image's pixels:

  {"control": [[px, py, e, n], ...],      # three or more points seen on both the map and the NAIP aerial (building corners, lift
                                           # towers, path forks), with their local metres read off out/disc_guide.png
   "holes": [{"tee": [px, py], "short": [px, py] or null, "basket": [px, py]}, ...]}   # the 9 holes in order

The map is fitted to the ground with the affine transform that best maps the control points (least squares; the residual of each
is printed), and the holes are written to out/disc_holes.json for build.py (disc_build.py). out/disc_check.png draws them on the
aerial to check: tees yellow, short tees orange, baskets red, each line labelled with its hole and length against the card's.

  python disc_read.py --course cmdg          read the points, write disc_holes.json and disc_check.png
  python disc_read.py --course cmdg guide    write out/disc_guide.png: the aerial with a 50 m grid of local metres, to read control points off
"""
import json
import math
import os
import sys

import numpy as np
import rasterio
from PIL import Image, ImageDraw

from common import DETAIL, OUT, cache, course

FT = .3048


def aerial(scale=1):
    with rasterio.open(cache('naip.tif')) as s:
        a, tr = s.read([1, 2, 3]), s.transform
    img = Image.fromarray(np.moveaxis(a, 0, -1)).convert('RGB')
    if scale != 1:
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    px = lambda e, n: ((e - tr.c) / tr.a * scale, (n - tr.f) / tr.e * scale)
    return img, px


def guide():
    img, px = aerial()
    d = ImageDraw.Draw(img)
    e0, n0, e1, n1 = DETAIL
    for g in range(int(e0), int(e1) + 1, 50):
        d.line([px(g, n0), px(g, n1)], fill=(255, 255, 255) if g % 100 == 0 else (190, 190, 190), width=1)
        d.text(px(g + 2, n1 - 4), str(g), fill=(255, 255, 0))
    for g in range(int(n0), int(n1) + 1, 50):
        d.line([px(e0, g), px(e1, g)], fill=(255, 255, 255) if g % 100 == 0 else (190, 190, 190), width=1)
        d.text(px(e0 + 3, g + 6), str(g), fill=(255, 255, 0))
    img.save(os.path.join(OUT, 'disc_guide.png'))
    print('wrote', os.path.join(OUT, 'disc_guide.png'))


def main():
    P = json.load(open(os.path.join(OUT, 'disc_map_points.json')))
    cp = np.array(P['control'], float)
    assert len(cp) >= 3, 'at least three control points'
    A = np.c_[cp[:, :2], np.ones(len(cp))]
    M, *_ = np.linalg.lstsq(A, cp[:, 2:], rcond=None)   # [px py 1] @ M = [e n]
    res = A @ M - cp[:, 2:]
    for (x, y, e, n), r in zip(cp, res):
        print(f'control ({x:.0f}, {y:.0f}) -> ({e:.0f}, {n:.0f}): off by {math.hypot(*r):.1f} m')
    to = lambda q: [round(float(v), 1) for v in np.array([q[0], q[1], 1.0]) @ M]
    rows = [dict(tee=to(h['tee']), short=to(h['short']) if h.get('short') else None, basket=to(h['basket'])) for h in P['holes']]
    json.dump(rows, open(os.path.join(OUT, 'disc_holes.json'), 'w'), indent=1)
    img, px = aerial()
    d = ImageDraw.Draw(img)
    for i, r in enumerate(rows):
        for k, col in (('tee', (255, 230, 0)), ('short', (255, 140, 0))):
            if r[k]:
                d.line([px(*r[k]), px(*r['basket'])], fill=col, width=3)
                d.ellipse([px(*r[k])[0] - 6, px(*r[k])[1] - 6, px(*r[k])[0] + 6, px(*r[k])[1] + 6], fill=col)
        b = px(*r['basket'])
        d.ellipse([b[0] - 7, b[1] - 7, b[0] + 7, b[1] + 7], fill=(255, 0, 0))
        L = math.hypot(r['basket'][0] - r['tee'][0], r['basket'][1] - r['tee'][1]) / FT
        t = px(*r['tee'])
        d.text((t[0] + 8, t[1] - 8), f'{i + 1}: {L:.0f} ft (card {course.FEET_LONG[i]})', fill=(255, 255, 255))
        print(f'hole {i + 1}: {L:.0f} ft, card {course.FEET_LONG[i]} ft')
    img.save(os.path.join(OUT, 'disc_check.png'))
    print('wrote disc_holes.json and disc_check.png')


if __name__ == '__main__':
    guide() if sys.argv[1:] == ['guide'] else main()
