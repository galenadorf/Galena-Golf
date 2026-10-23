"""Read out/entrance_zoom_mask.png (painted on out/entrance_zoom.png; see entrance_edit.py):
  PURPLE rectangle  the big Woodbine Bend sign and its flower bed: centre, width (long side), depth (short side)
  BLUE strip        (optional) the long side the lettering faces; default: toward the nearest road
Writes out/entrance.json (one row: ['entry', e, n, direction the front faces in degrees (east = 0, counter-clockwise), width m,
depth m, '']); site_paint.py adds it to the site props. Rerun this, site_paint.py, build.py, install.py after repainting."""
import json
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import MultiPoint

import osm
from common import OUT


def blobs(a, rgb, min_px):
    m = ndi.binary_closing(np.abs(a - np.array(rgb)).max(2) <= 40, iterations=2)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    return [np.nonzero(lab == i + 1) for i, s in enumerate(sizes) if s >= min_px]


def main():
    f = json.load(open(os.path.join(OUT, 'entrance_zoom.json')))
    a = np.array(Image.open(os.path.join(OUT, 'entrance_zoom_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == f['w'] and a.shape[0] == f['h'], 'the mask must have the close-up\'s size'
    a[f['h'] - 190:f['h'] - 20, 20:1060] = 0    # the colour key printed on the map is ignored
    loc = lambda xs, ys: [(f['e0'] + x / f['ppm'], f['n1'] - y / f['ppm']) for x, y in zip(xs, ys)]
    bl = blobs(a, (128, 0, 255), 400)
    assert bl, 'no purple rectangle found'
    ys, xs = max(bl, key=lambda b: len(b[0]))
    r = MultiPoint(loc(xs, ys)).minimum_rotated_rectangle
    c = list(r.exterior.coords)[:4]
    e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1]); e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    L1, L2 = math.hypot(*e1), math.hypot(*e2)
    long_, w, dep = (e1, L1, L2) if L1 >= L2 else (e2, L2, L1)
    cen = r.centroid
    nx, ny = -long_[1] / w, long_[0] / w                       # a normal of the long side
    strips = [MultiPoint(loc(b[1], b[0])).centroid for b in blobs(a, (0, 0, 255), 30)]
    strips = [s for s in strips if s.distance(r) < 2.5]
    if strips:
        tgt = strips[0]
    else:
        roads = [x['line'] for x in osm.load()['road']]
        line = min(roads, key=lambda l: l.distance(cen))
        tgt = line.interpolate(line.project(cen))
    sgn = 1 if ((tgt.x - cen.x) * nx + (tgt.y - cen.y) * ny) >= 0 else -1
    ang = math.degrees(math.atan2(sgn * ny, sgn * nx)) % 360
    row = ['entry', round(cen.x, 1), round(cen.y, 1), round(ang), round(w, 1), round(dep, 1), '']
    json.dump([row], open(os.path.join(OUT, 'entrance.json'), 'w'))
    print(row, '(facing the', 'blue strip' if strips else 'nearest road', ')')


if __name__ == '__main__':
    main()
