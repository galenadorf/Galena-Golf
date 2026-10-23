"""Read out/paint_mask.png (painted on out/paint_edit.png; colours in paint_edit.py):
  MAGENTA blobs  tee boxes -> out/tees_painted.json (polygons, local metres; build.py uses them instead of the OSM boxes). A current box
                 with no magenta within 6 m is kept as it is, so only the wrong or missing boxes need painting.
  YELLOW dots    the played (gold) tee of the hole whose line passes nearest -> out/tee_starts.json ([e, n] points)
  PURPLE + BLUE  the big entrance sign -> out/entrance.json (one 'entry' row: e, n, direction it faces in degrees (east = 0,
                 counter-clockwise), width m, depth m); site_paint.py adds it to the site props
Rerun this, site_paint.py, build.py, install.py after repainting."""
import json
import math
import os

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import MultiPoint, mapping, shape

import osm
from common import OUT
from paint_edit import KEY_BOX

MIN_TEE = 3.0     # m2: smaller magenta specks are paint noise
KEEP_NEAR = 6.0   # m: a current tee box this close to painted magenta is replaced by it


def mask(a, rgb, closing=2):
    return ndi.binary_closing(np.abs(a - np.array(rgb)).max(2) <= 40, iterations=closing)


def main():
    fr = json.load(open(os.path.join(OUT, 'paint_edit.json')))
    a = np.array(Image.open(os.path.join(OUT, 'paint_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the map\'s size'
    a[KEY_BOX[1]:KEY_BOX[3] + 80, KEY_BOX[0]:KEY_BOX[2]] = 0
    ppm = fr['ppm']
    tr = Affine(1 / ppm, 0, fr['e0'], 0, -1 / ppm, fr['n1'])
    loc = lambda ys, xs: [(fr['e0'] + x / ppm, fr['n1'] - y / ppm) for y, x in zip(ys, xs)]
    F = osm.load()

    def polys(rgb, min_area, fill):
        m = mask(a, rgb)
        if fill:
            m = ndi.binary_fill_holes(m)
        lab, n = ndi.label(m)
        sizes = ndi.sum(m, lab, range(1, n + 1))
        m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s / ppm ** 2 >= min_area])
        return [shape(g).buffer(0) for g, v in features.shapes(m.astype(np.uint8), mask=m, transform=tr) if v]

    boxes = [p.simplify(.1) for p in polys((255, 0, 255), MIN_TEE, True)]
    keep = [t['poly'] for t in F['tee'] if not any(p.distance(t['poly']) < KEEP_NEAR for p in boxes)]
    json.dump([mapping(p) for p in keep + boxes], open(os.path.join(OUT, 'tees_painted.json'), 'w'))
    starts = [[round(p.centroid.x, 2), round(p.centroid.y, 2)] for p in polys((255, 255, 0), .2, False)]
    json.dump(starts, open(os.path.join(OUT, 'tee_starts.json'), 'w'))
    print(len(boxes), 'painted tee boxes (', round(sum(p.area for p in boxes)), 'm2 ) +', len(keep), 'current boxes kept;', len(starts), 'start dots')
    for p in starts:
        h = min(F['hole'], key=lambda hh: hh['line'].distance(shape({'type': 'Point', 'coordinates': p})))
        print('  start dot', p, '-> hole', h['ref'])
    # the entrance sign
    lab, n = ndi.label(mask(a, (128, 0, 255)))
    if not n:
        print('no purple rectangle: no entrance sign')
        if os.path.exists(os.path.join(OUT, 'entrance.json')):
            os.remove(os.path.join(OUT, 'entrance.json'))
        return
    sizes = ndi.sum(lab > 0, lab, range(1, n + 1))
    ys, xs = np.nonzero(lab == 1 + int(np.argmax(sizes)))
    r = MultiPoint(loc(ys, xs)).minimum_rotated_rectangle
    c = list(r.exterior.coords)[:4]
    e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1]); e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    L1, L2 = math.hypot(*e1), math.hypot(*e2)
    long_, w, dep = (e1, L1, L2) if L1 >= L2 else (e2, L2, L1)
    cen = r.centroid
    nx, ny = -long_[1] / w, long_[0] / w
    blab, bn = ndi.label(mask(a, (0, 0, 255)))
    strips = []
    for i in range(1, bn + 1):
        by, bx = np.nonzero(blab == i)
        if len(by) >= 30:
            q = MultiPoint(loc(by, bx)).centroid
            if q.distance(r) < 2.5:
                strips.append(q)
    if strips:
        tgt = strips[0]
    else:
        line = min([x['line'] for x in F['road']], key=lambda ln: ln.distance(cen))
        tgt = line.interpolate(line.project(cen))
    sgn = 1 if ((tgt.x - cen.x) * nx + (tgt.y - cen.y) * ny) >= 0 else -1
    row = ['entry', round(cen.x, 1), round(cen.y, 1), round(math.degrees(math.atan2(sgn * ny, sgn * nx)) % 360), round(float(np.clip(w, 4, 14)), 1), round(float(np.clip(dep, 1.5, 6)), 1), '']
    json.dump([row], open(os.path.join(OUT, 'entrance.json'), 'w'))
    print('entrance sign', row, '(facing the', 'blue strip)' if strips else 'nearest road)')


if __name__ == '__main__':
    main()
