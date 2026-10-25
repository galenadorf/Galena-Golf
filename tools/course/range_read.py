"""The driving range, from the hand-painted out/range_mask.png (painted over out/range_start.png, same pixels; see range_edit.py):
GREEN #00FF00 mown range grass (the game's fairway), CYAN #00FFFF a target green (the game cuts its own 1.5 m collar), MAGENTA #FF00FF deep fescue,
ORANGE #FF8000 bunkers, BLUE #0000FF dots the hitting spots, RED #FF0000 dots the flags, YELLOW #FFFF00 broadleaf trees (circles; touching ones are
split, each as wide as its circle), AZURE #0080FF a long metal shed (a 'shed' prop, sized and turned like the painted rectangle).
The paint under a dot or the shed is whatever lies around it. Writes out/range.json (local metres): fair, greens, bunkers, fescue, boundary (everything
painted, closed up; beyond it is out of bounds), spots, flags, trees, shed, box. build.py adds it as RD.drv."""
import json
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import MultiPoint, mapping
from skimage.feature import peak_local_max

from common import OUT, smooth_polys

COLS = dict(fair=(0, 255, 0), green=(0, 255, 255), fescue=(255, 0, 255), bunker=(255, 128, 0), spot=(0, 0, 255), flag=(255, 0, 0), tree=(255, 255, 0), shed=(0, 128, 255))
PAD = 80   # px of edge carried past the map (16 m), so the fescue and the boundary run on past it
FAIR_SMOOTH, GREEN_SMOOTH, FESCUE_SMOOTH, SAND_SMOOTH, BOUND_SMOOTH = 11.0, 7.0, 11.0, 6.0, 14.0   # px of blur (1 px = 20 cm): 2.2 m, 1.4 m, 2.2 m, 1.2 m, 2.8 m, so painted corners and pixel steps become curves


def main():
    fr = json.load(open(os.path.join(OUT, 'range_edit.json')))
    a = np.array(Image.open(os.path.join(OUT, 'range_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    res = 1 / fr['ppm']
    f0 = dict(res=res, e0=fr['e0'], n1=fr['n1'])
    m = {k: (np.abs(a - np.array(c)).max(2) <= 40) for k, c in COLS.items()}
    pt = lambda lab, i: [round(float(v), 2) for v in (fr["e0"] + (ndi.center_of_mass(lab == i)[1] + .5) * res, fr["n1"] - (ndi.center_of_mass(lab == i)[0] + .5) * res)]
    blobs = lambda k, n: [(lab, i) for lab, cnt in [ndi.label(m[k])] for i in range(1, cnt + 1) if (lab == i).sum() >= n]
    spots = [pt(lab, i) for lab, i in blobs('spot', 40)]
    flags = [pt(lab, i) for lab, i in blobs('flag', 40)]
    # trees: circles of paint, touching ones split at the pinch (peaks of the distance to the edge); the circle's width is the crown
    tm = ndi.binary_closing(m['tree'], iterations=1)
    dist = ndi.distance_transform_edt(tm)
    pk = peak_local_max(dist, min_distance=8, threshold_abs=6, labels=ndi.label(tm)[0], exclude_border=False)
    trees = []
    for y, x in pk:
        d = float(np.clip(2 * dist[y, x] * res, 2.5, 24))
        trees.append(dict(e=round(fr['e0'] + (x + .5) * res, 1), n=round(fr['n1'] - (y + .5) * res, 1), d=round(d, 1), h=round(min(18, 3 + .8 * d), 1), kind=0))
    # the shed
    shed = None
    lab, cnt = ndi.label(m['shed'])
    if cnt:
        i = 1 + int(np.argmax(ndi.sum(m['shed'], lab, range(1, cnt + 1))))
        ys, xs = np.nonzero(lab == i)
        r = MultiPoint([(fr['e0'] + (x + .5) * res, fr['n1'] - (y + .5) * res) for y, x in zip(ys, xs)]).minimum_rotated_rectangle
        c = list(r.exterior.coords)[:4]
        e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1]); e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
        L1, L2 = math.hypot(*e1), math.hypot(*e2)
        long_, w, dep = (e1, L1, L2) if L1 >= L2 else (e2, L2, L1)
        shed = ['shed', round(r.centroid.x, 1), round(r.centroid.y, 1), round(math.degrees(math.atan2(long_[0], -long_[1])) % 360), round(w, 1), round(dep, 1), '']
    # classes: what the paint under a dot, a tree circle or the shed shows is what lies around it
    cls = np.zeros(a.shape[:2], int)
    for v, k in enumerate(('fair', 'green', 'fescue', 'bunker'), 1):
        cls[m[k]] = v
    # a hitting spot left on unpainted ground (the tee strip) stands on mown grass, 5 m round, and is in bounds
    yy, xx = np.mgrid[:a.shape[0], :a.shape[1]]
    spot_px = [(round((p[0] - fr['e0']) / res - .5), round((fr['n1'] - p[1]) / res - .5)) for p in spots]
    near = np.zeros(cls.shape, bool); wide = np.zeros(cls.shape, bool)
    for x, y in spot_px:
        d2 = (xx - x) ** 2 + (yy - y) ** 2
        if cls[y, x] == 0:
            near |= d2 <= 25 ** 2
        wide |= d2 <= 60 ** 2
    cls[near & (cls == 0)] = 1
    hide = ndi.binary_dilation(m['spot'] | m['flag'] | m['tree'] | m['shed'], iterations=1)
    keep = ~hide & (cls > 0)
    # near the dots only: a tree circle in the woods is fescue, a dot on grass is grass
    idx = ndi.distance_transform_edt(~keep, return_distances=False, return_indices=True)
    filled = cls[idx[0], idx[1]]
    dd = ndi.distance_transform_edt(~keep)
    cls = np.where(hide & (dd <= 60), filled, cls)   # farther than 12 m from any other paint: it stays unpainted
    cm = {k: cls == v for v, k in enumerate(('fair', 'green', 'fescue', 'bunker'), 1)}
    fair = smooth_polys(cm['fair'], f0, FAIR_SMOOTH, .47, 20, .06)
    greens = smooth_polys(ndi.binary_closing(cm['green'], iterations=2), f0, GREEN_SMOOTH, .47, 8, .04)
    bunkers = smooth_polys(cm['bunker'], f0, SAND_SMOOTH, .47, 2, .04)
    fm = np.pad(cm['fescue'], PAD, mode='edge')
    ff = dict(res=res, e0=fr['e0'] - PAD * res, n1=fr['n1'] + PAD * res)
    fescue = smooth_polys(ndi.binary_closing(fm, iterations=2), ff, FESCUE_SMOOTH, .47, 8, .06, pad=PAD)
    anyp = np.pad((cls > 0) | wide, PAD, mode='edge')
    anyp = ndi.binary_fill_holes(ndi.binary_closing(anyp, iterations=40))
    bound = max(smooth_polys(anyp, ff, BOUND_SMOOTH, .5, 100, .15, pad=PAD), key=lambda p: p.area)
    out = dict(fair=[mapping(p) for p in fair], greens=[mapping(p) for p in greens], bunkers=[mapping(p) for p in bunkers], fescue=[mapping(p) for p in fescue],
               boundary=mapping(bound), spots=spots, flags=flags, trees=trees, shed=shed,
               box=[fr['e0'], fr['n1'] - fr['h'] * res, fr['e0'] + fr['w'] * res, fr['n1']])
    json.dump(out, open(os.path.join(OUT, 'range.json'), 'w'))
    px2 = res * res
    for k, ps in (('fair', fair), ('green', greens), ('bunker', bunkers)):
        print(f'  {k}: painted {cm[k].sum() * px2:.0f} m2, smoothed {sum(p.area for p in ps):.0f} m2')
    print(f'fair {sum(p.area for p in fair) / 10000:.2f} ha, greens {len(greens)}, bunkers {len(bunkers)}, fescue {sum(p.area for p in fescue) / 10000:.2f} ha, boundary {bound.area / 10000:.2f} ha')
    print('spots', spots, '\nflags', flags, '\ntrees', len(trees), [t['d'] for t in trees], '\nshed', shed)


if __name__ == '__main__':
    main()
