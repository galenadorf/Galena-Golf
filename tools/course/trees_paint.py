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


def main():
    fr = json.load(open(os.path.join(OUT, 'trees_edit.json')))
    a = np.array(Image.open(os.path.join(OUT, 'trees_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    old = json.load(open(os.path.join(OUT, 'trees.json')))
    rng = np.random.default_rng(7)
    out = []
    for kind, (rgb, name) in KINDS.items():
        m = (np.abs(a - np.array(rgb)).max(2) <= 40)
        m = ndi.binary_closing(m, iterations=1)
        lab, n = ndi.label(m)
        sizes = ndi.sum(m, lab, range(1, n + 1))
        for i, s in enumerate(sizes):
            if s * fr['res'] ** 2 < 2:
                continue
            blob = lab == i + 1
            polys = [shape(g).buffer(0) for g, v in features.shapes(blob.astype(np.uint8), mask=blob, transform=tr) if v]
            p = max(polys, key=lambda q: q.area)
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
    json.dump(out, open(os.path.join(OUT, 'trees_painted.json'), 'w'))
    print(len(out), 'trees added:', sum(t['kind'] == 0 for t in out), 'broadleaf,', sum(t['kind'] == 2 for t in out), 'conifer,', sum(t['kind'] == 1 for t in out), 'shrubs')


if __name__ == '__main__':
    main()
