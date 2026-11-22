"""Trees from the hand-painted out/trees_mask.png (solid ORANGE #FF8000 = broadleaf, solid BLUE #0080FF = conifer, solid
MAGENTA #FF00FF = shrub (low bushes and scrub, under 4 m) over
out/trees_edit.png, same pixels). A painted blob of up to ~90 m2 is one tree sized to the blob; a bigger one is filled with
trees about 6 m apart (jittered, not on top of the lidar trees in trees.json). Writes out/trees_painted.json in trees.json's
format; build.py adds them to the lidar trees. Rerun trees_paint.py, build.py, install.py after repainting."""
import json
import os

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import Point, shape

from common import OUT

ONE_TREE = 90.0   # m2: a blob up to this is a single tree
SPACING = 6.0     # m between trees in a grove
KINDS = {0: ((255, 128, 0), 'broadleaf'), 2: ((0, 128, 255), 'conifer'), 1: ((255, 0, 255), 'shrub')}


def height(kind, d):
    return round(3 + 1.1 * d if kind == 0 else 1 + .35 * d if kind == 1 else 2.4 * d, 1)  # a shrub stays under 4 m


def split_discs(blob, fr):
    """Touching painted circles as discs [(e, n, crown m)]: the widest disc that fits in the paint not yet covered, again and again;
    None unless the discs cover 85 % of the blob (then it is not a set of circles)."""
    res = fr['res']
    dt = ndi.distance_transform_edt(blob)
    yy, xx = np.nonzero(blob)
    free = np.ones(len(yy), bool)
    discs = []
    for _ in range(40):
        if free.sum() < .1 * len(yy):
            break
        k = np.argmax(np.where(free, dt[yy, xx], -1))
        r = dt[yy[k], xx[k]]
        inside = np.hypot(yy - yy[k], xx - xx[k]) <= r
        if r * res < 1.5 or (inside & free).sum() < .4 * inside.sum():
            free[inside | (np.hypot(yy - yy[k], xx - xx[k]) <= 2)] = False
            continue
        free &= ~inside
        discs.append((xx[k], yy[k], r))
    if not discs:
        return None
    cov = np.zeros(len(yy), bool)
    for x, y, r in discs:
        cov |= np.hypot(yy - y, xx - x) <= r + 1
    if cov.mean() < .85:
        return None
    return [(fr['e0'] + (x + .5) * res, fr['n1'] - (y + .5) * res, 2 * r * res) for x, y, r in discs]


def from_masks(masks, fr, old, one_round=False):
    """Trees from boolean masks {kind: mask} on the grid `fr`, kept off the lidar trees `old` (also used by all_read.py).
    one_round: a round blob (a painted circle, filling 70 %+ of the disc across its widest extent) is ONE tree as wide as the circle,
    up to 20 m, however big (the share-folder hole pictures: a big circle is a big tree, not a grove)."""
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    rng = np.random.default_rng(7)
    out = []
    for kind, m in masks.items():
        m = ndi.binary_closing(m, iterations=1)
        lab, n = ndi.label(m)
        sizes = ndi.sum(m, lab, range(1, n + 1))
        for i, s in enumerate(sizes):
            if s * fr['res'] ** 2 < 2:
                continue
            blob = lab == i + 1
            polys = [shape(g).buffer(0) for g, v in features.shapes(blob.astype(np.uint8), mask=blob, transform=tr) if v]
            p = max(polys, key=lambda q: q.area)
            x0_, y0_, x1_, y1_ = p.bounds
            dm = max(x1_ - x0_, y1_ - y0_)
            if one_round and p.area <= 320 and p.area >= .7 * np.pi * dm * dm / 4:
                d = float(np.clip(2 * np.sqrt(p.area / np.pi), 1.5 if kind == 1 else 2.5, 4.5 if kind == 1 else 20))
                out.append(dict(e=round(p.centroid.x, 1), n=round(p.centroid.y, 1), d=round(d, 1), h=height(kind, d), kind=kind))
                continue
            if one_round and p.area <= 2000:
                discs = split_discs(blob, fr)
                if discs:
                    for x, y, d in discs:
                        d = float(np.clip(d, 1.5 if kind == 1 else 2.5, 4.5 if kind == 1 else 20))
                        out.append(dict(e=round(x, 1), n=round(y, 1), d=round(d, 1), h=height(kind, d), kind=kind))
                    continue
            if p.area <= ONE_TREE:
                d = float(np.clip(2 * np.sqrt(p.area / np.pi), 1.5 if kind == 1 else 2.5, 4.5 if kind == 1 else 12))
                out.append(dict(e=round(p.centroid.x, 1), n=round(p.centroid.y, 1), d=round(d, 1), h=height(kind, d), kind=kind))
                continue
            inner = p.buffer(-1.5)
            if inner.is_empty:
                inner = p
            x0, y0, x1, y1 = inner.bounds
            sp = 3.5 if kind == 1 else SPACING  # scrub is planted closer than trees
            for x in np.arange(x0, x1, sp):
                for y in np.arange(y0, y1, sp):
                    q = Point(x + rng.uniform(-.3, .3) * sp, y + rng.uniform(-.3, .3) * sp)
                    if not inner.contains(q):
                        continue
                    d = float(rng.uniform(5, 8) if kind == 0 else rng.uniform(2, 3.5) if kind == 1 else rng.uniform(3.5, 5.5))
                    if any(np.hypot(q.x - t['e'], q.y - t['n']) < .6 * (d + t['d']) / 2 for t in old):
                        continue
                    out.append(dict(e=round(q.x, 1), n=round(q.y, 1), d=round(d, 1), h=height(kind, d), kind=kind))
    return out


def main():
    fr = json.load(open(os.path.join(OUT, 'trees_edit.json')))
    a = np.array(Image.open(os.path.join(OUT, 'trees_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    out = from_masks({kind: np.abs(a - np.array(rgb)).max(2) <= 40 for kind, (rgb, name) in KINDS.items()}, fr, json.load(open(os.path.join(OUT, 'trees.json'))))
    json.dump(out, open(os.path.join(OUT, 'trees_painted.json'), 'w'))
    print(len(out), 'trees added:', sum(t['kind'] == 0 for t in out), 'broadleaf,', sum(t['kind'] == 2 for t in out), 'conifer,', sum(t['kind'] == 1 for t in out), 'shrubs')


if __name__ == '__main__':
    main()
