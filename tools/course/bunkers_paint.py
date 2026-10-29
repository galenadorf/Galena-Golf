"""Bunkers: read the hand-refined out/bunkers_mask.png (pure orange #FF8000 over the aerial; made from out/bunkers_edit.png,
same pixels) and write out/bunkers_painted.json (polygons, local metres). build.py uses these instead of the OSM bunkers and
bunkers_auto.json when the file exists. The painted edges are pixel staircases (0.5 m steps), so each bunker's outline is rebuilt as the
sub-pixel contour of its blurred mask (SMOOTH px of blur, traced at a level that keeps the area): smooth curves, nearly the same area. Rerun bunkers_paint.py, build.py, install.py after repainting."""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import Polygon, mapping
from skimage import measure
from scipy.ndimage import gaussian_filter

from common import OUT

MIN_AREA = 6.0  # m2: smaller specks are paint noise
SMOOTH = 1.4    # px of Gaussian blur before the outline is traced (1 px = 0.5 m)
PAD = 4


def from_mask(m, fr):
    """The bunker polygons from a boolean mask on the grid `fr` (also used by all_read.py)."""
    m = ndi.binary_closing(m, iterations=1)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s * fr['res'] ** 2 >= MIN_AREA])
    inv, n = ndi.label(~m)
    sizes = ndi.sum(~m, inv, range(1, n + 1))
    for i, s in enumerate(sizes):
        if s * fr['res'] ** 2 < MIN_AREA:
            m |= inv == i + 1
    mf = gaussian_filter(np.pad(m, PAD).astype(float), SMOOTH)
    res = fr['res']
    rings = []
    for c in measure.find_contours(mf, .46):
        pts = [(fr['e0'] + (x - PAD + .5) * res, fr['n1'] - (y - PAD + .5) * res) for y, x in c]
        if len(pts) >= 4:
            rings.append(Polygon(pts).buffer(0))
    polys = []   # an outline inside another one is a hole (or an island in a hole): each ring flips what is inside it
    for r in sorted(rings, key=lambda q: -q.area):
        for i, q in enumerate(polys):
            if q.contains(r.representative_point()):
                polys[i] = q.symmetric_difference(r); break
        else:
            polys.append(r)
    return [q.simplify(.06) for q in polys if q.area >= MIN_AREA]


def main():
    fr = json.load(open(os.path.join(OUT, 'fescue_base.json')))
    a = np.array(Image.open(os.path.join(OUT, 'bunkers_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    polys = from_mask(np.abs(a - np.array((255, 128, 0))).max(2) <= 40, fr)
    json.dump([mapping(p) for p in polys], open(os.path.join(OUT, 'bunkers_painted.json'), 'w'))
    print(len(polys), 'bunkers,', round(sum(p.area for p in polys)), 'm2')


if __name__ == '__main__':
    main()
