"""The creek from the hand-corrected out/creek_mask.png (pure BLUE #0000FF over out/creek_edit.png, same pixels; frame in
out/creek_edit.json). The painted water is cut into ~14 m cells (the game digs each piece and sets its water level from its
own banks, so the creek steps down), written to out/creek_painted.json (polygons, local metres); build.py uses them in place of
creek.py's centre line when the file exists. Rerun creek_paint.py, build.py, install.py after repainting."""
import json
import os

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import box, mapping, shape

from common import OUT

CELL = 14.0
MIN_AREA = 6.0   # m2: smaller specks are paint noise


def main():
    fr = json.load(open(os.path.join(OUT, 'creek_edit.json')))
    a = np.array(Image.open(os.path.join(OUT, 'creek_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    m = (np.abs(a - np.array((0, 0, 255))).max(2) <= 40)
    m = ndi.binary_closing(m, iterations=2)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s * fr['res'] ** 2 >= MIN_AREA])
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    polys = [shape(g).buffer(0) for g, v in features.shapes(m.astype(np.uint8), mask=m, transform=tr) if v]
    pieces = []
    for p in polys:
        x0, y0, x1, y1 = p.bounds
        for gx in np.arange(np.floor(x0 / CELL) * CELL, x1, CELL):
            for gy in np.arange(np.floor(y0 / CELL) * CELL, y1, CELL):
                q = p.intersection(box(gx - .3, gy - .3, gx + CELL + .3, gy + CELL + .3))
                for g in getattr(q, 'geoms', [q]):
                    if g.geom_type == 'Polygon' and g.area >= MIN_AREA:
                        pieces.append(g.simplify(.25))
    json.dump([mapping(p) for p in pieces], open(os.path.join(OUT, 'creek_painted.json'), 'w'))
    print(len(polys), 'creek areas,', len(pieces), 'pieces,', round(sum(p.area for p in polys)), 'm2 of water')


if __name__ == '__main__':
    main()
