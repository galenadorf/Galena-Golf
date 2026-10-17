"""Bunkers: read the hand-refined out/bunkers_mask.png (pure orange #FF8000 over the aerial; made from out/bunkers_edit.png,
same pixels) and write out/bunkers_painted.json (polygons, local metres). build.py uses these instead of the OSM bunkers and
bunkers_auto.json when the file exists. Rerun bunkers_paint.py, build.py, install.py after repainting."""
import json
import os

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import mapping, shape

from common import OUT

MIN_AREA = 6.0  # m2: smaller specks are paint noise


def main():
    fr = json.load(open(os.path.join(OUT, 'fescue_base.json')))
    a = np.array(Image.open(os.path.join(OUT, 'bunkers_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    m = (np.abs(a - np.array((255, 128, 0))).max(2) <= 40)
    m = ndi.binary_closing(m, iterations=1)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s * fr['res'] ** 2 >= MIN_AREA])
    inv, n = ndi.label(~m)
    sizes = ndi.sum(~m, inv, range(1, n + 1))
    for i, s in enumerate(sizes):
        if s * fr['res'] ** 2 < MIN_AREA:
            m |= inv == i + 1
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    polys = [shape(g).buffer(0) for g, v in features.shapes(m.astype(np.uint8), mask=m, transform=tr) if v]
    polys = [p.simplify(.25) for p in polys if p.area >= MIN_AREA]
    json.dump([mapping(p) for p in polys], open(os.path.join(OUT, 'bunkers_painted.json'), 'w'))
    print(len(polys), 'bunkers,', round(sum(p.area for p in polys)), 'm2')


if __name__ == '__main__':
    main()
