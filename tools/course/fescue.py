"""Fescue areas: read the hand-painted out/fescue_mask.png (pure magenta over out/fescue_base.png, same pixels) and write
out/fescue.json (polygons in local metres). build.py encodes them as feat.fescue; the game makes them, and only them, the
deep rough (tall, clumpy, penal). Redraw the mask and rerun fescue.py, build.py, install.py to change them."""
import json
import os

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from common import OUT

MIN_AREA = 40.0  # m2: smaller specks and holes are paint noise


def main():
    fr = json.load(open(os.path.join(OUT, 'fescue_base.json')))
    a = np.array(Image.open(os.path.join(OUT, 'fescue_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (r > 170) & (b > 170) & (g < 120) & (r - g > 90) & (b - g > 90)  # magenta, also its anti-aliased edge pixels
    px = fr['res'] ** 2
    m = ndi.binary_closing(m, iterations=2)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s * px >= MIN_AREA])
    inv, n = ndi.label(~m)  # holes (unpainted specks inside painted areas)
    sizes = ndi.sum(~m, inv, range(1, n + 1))
    for i, s in enumerate(sizes):
        if s * px < MIN_AREA and not (inv == i + 1)[0, :].any() and not (inv == i + 1)[-1, :].any():
            m |= inv == i + 1
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    polys = [shape(g).buffer(0) for g, v in features.shapes(m.astype(np.uint8), mask=m, transform=tr) if v]
    polys = [p.simplify(.6) for p in unary_union(polys).geoms] if len(polys) > 1 else [p.simplify(.6) for p in polys]
    polys = [p for p in polys if p.area >= MIN_AREA]
    json.dump([mapping(p) for p in polys], open(os.path.join(OUT, 'fescue.json'), 'w'))
    print(len(polys), 'areas,', round(sum(p.area for p in polys) / 10000, 1), 'ha,', sum(len(p.exterior.coords) for p in polys), 'vertices')


if __name__ == '__main__':
    main()
