"""A disc golf course's tees and baskets, read off its hole map (an aerial photo with the holes drawn on, saved as the course's
hole_map.jpg beside its course.py).

out/disc_map_points.json holds what is picked on the map by eye, in the map image's pixels:

  {"control": [[px, py, e, n], ...],      # three or more points seen on both the map and the NAIP aerial (building corners, lift
                                           # towers, path forks), with their local metres read off out/disc_guide.png
   "holes": [{"tee": [px, py], "short": [px, py] or null, "basket": [px, py]}, ...]}   # the 9 holes in order

The map is fitted to the ground with the affine transform that best maps the control points (least squares; the residual of each
is printed), and the holes are written to out/disc_holes.json for build.py (disc_build.py). out/disc_check.png draws them on the
aerial to check: tees yellow, short tees orange, baskets red, each line labelled with its hole and length against the card's.
FIT_CARD = True in course.py scales each hole about its middle to the card's length (FEET_LONG; a short tee keeps its place on the
line), for a map that draws its tees and baskets loosely (Adler Park's sign: the eastern holes came out 10-15 % long).

`register` refines the fit when the map is drawn over an aerial (Adler Park): it starts from the control points, moves the map so its
dark tree blobs land on the lidar canopy (.cache/chm.tif over 2 m) and its light grass off it, and writes the result back as five
control points the refined transform puts exactly (the old ones are replaced).

  python disc_read.py --course cmdg          read the points, write disc_holes.json and disc_check.png
  python disc_read.py --course cmdg guide    write out/disc_guide.png: the aerial with a 50 m grid of local metres, to read control points off
  python disc_read.py --course adgc register refine the control points against the lidar canopy (then run without arguments)
"""
import json
import math
import os
import sys

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from scipy import optimize

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


def fit(P):
    cp = np.array(P['control'], float)
    assert len(cp) >= 3, 'at least three control points'
    A = np.c_[cp[:, :2], np.ones(len(cp))]
    M, *_ = np.linalg.lstsq(A, cp[:, 2:], rcond=None)   # [px py 1] @ M = [e n]
    return cp, A, M


def map_image():
    return np.asarray(Image.open(os.path.join(os.path.dirname(course.__file__), 'hole_map.jpg')).convert('RGB')).astype(int)


def register():
    P = json.load(open(os.path.join(OUT, 'disc_map_points.json')))
    _, _, M0 = fit(P)
    m = map_image()
    side = np.zeros(m.shape[:2], bool)   # the sign's text panel and card (Adler Park): not map
    side[:, :440] = True
    side[650:, :600] = True
    tree = ndi.binary_opening((m[..., 0] < 50) & (m[..., 1] < 60) & (m[..., 2] < 50) & (m[..., 1] > 20) & ~side)
    grass = (m[..., 1] > 120) & (m[..., 1] > m[..., 0] + 15) & (m[..., 1] > m[..., 2] + 30) & ~side
    ty, tx = [v * 2 for v in np.nonzero(tree[::2, ::2])]
    gy, gx = [v * 2 for v in np.nonzero(grass[::2, ::2])]
    with rasterio.open(cache('chm.tif')) as s:
        chm, tr = s.read(1), s.transform
    can = ndi.gaussian_filter((ndi.gaussian_filter(chm, 1) > 2).astype(float), 2.5)
    K = np.array([[1e-3, 1e-3], [1e-3, 1e-3], [1, 1]])   # the steps: a thousandth of a metre per pixel, a metre of shift

    def on_canopy(M, x, y):
        q = np.c_[x, y, np.ones(len(x))] @ M
        return ndi.map_coordinates(can, [(q[:, 1] - tr.f) / tr.e, (q[:, 0] - tr.c) / tr.a], order=1, cval=0).mean()

    score = lambda p: on_canopy(M0 + p.reshape(3, 2) * K, gx, gy) - on_canopy(M0 + p.reshape(3, 2) * K, tx, ty)
    p = np.zeros(6)
    print(f'trees on canopy less grass on canopy: {-score(p):.3f}')
    for _ in range(3):
        p = optimize.minimize(score, p, method='Powell', options=dict(xtol=1e-3, ftol=1e-5)).x
    M = M0 + p.reshape(3, 2) * K
    print(f'refined: {-score(p):.3f}, {np.hypot(*M[0]):.3f} x {np.hypot(*M[1]):.3f} m a pixel, moved {np.hypot(*(M - M0)[2]):.0f} m')
    h, w = m.shape[:2]
    P['control'] = [[x, y, *[round(float(v), 2) for v in np.array([x, y, 1.0]) @ M]] for x, y in ((w * .4, h * .05), (w * .98, h * .05), (w * .98, h * .9), (w * .5, h * .9), (w * .4, h * .5))]
    json.dump(P, open(os.path.join(OUT, 'disc_map_points.json'), 'w'), indent=1)
    print('wrote the refined control points to disc_map_points.json')


def to_card(t, b, ft):
    """Scale the line about its middle to the card's length."""
    mx, my = (t[0] + b[0]) / 2, (t[1] + b[1]) / 2
    k = ft * FT / math.hypot(b[0] - t[0], b[1] - t[1])
    return [round(mx + (t[0] - mx) * k, 1), round(my + (t[1] - my) * k, 1)], [round(mx + (b[0] - mx) * k, 1), round(my + (b[1] - my) * k, 1)]


def main():
    P = json.load(open(os.path.join(OUT, 'disc_map_points.json')))
    cp, A, M = fit(P)
    res = A @ M - cp[:, 2:]
    for (x, y, e, n), r in zip(cp, res):
        print(f'control ({x:.0f}, {y:.0f}) -> ({e:.0f}, {n:.0f}): off by {math.hypot(*r):.1f} m')
    to = lambda q: [round(float(v), 1) for v in np.array([q[0], q[1], 1.0]) @ M]
    rows = [dict(tee=to(h['tee']), short=to(h['short']) if h.get('short') else None, basket=to(h['basket'])) for h in P['holes']]
    if getattr(course, 'FIT_CARD', False):
        for i, r in enumerate(rows):
            L0 = math.hypot(r['basket'][0] - r['tee'][0], r['basket'][1] - r['tee'][1]) / FT
            r['tee'], r['basket'] = to_card(r['tee'], r['basket'], course.FEET_LONG[i])
            print(f'hole {i + 1}: {L0:.0f} ft on the map, fitted to the card')
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
    {'guide': guide, 'register': register}.get(''.join(sys.argv[1:]), main)()
