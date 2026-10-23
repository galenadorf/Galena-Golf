"""Fescue areas: read the hand-painted out/fescue_mask.png (pure magenta over out/fescue_base.png, same pixels) and write
out/fescue.json (polygons in local metres). build.py encodes them as feat.fescue; the game makes them, and only them, the
deep rough (tall, clumpy, penal). Redraw the mask and rerun fescue.py, build.py, install.py to change them."""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import mapping

from common import OUT, smooth_polys

MIN_AREA = 40.0  # m2: smaller specks and holes are paint noise
SMOOTH = 2.0  # px of Gaussian blur before the outline is traced (1 px = 0.5 m)
LEVEL = 0.5
TOL = 0.3


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
    polys = smooth_polys(m, fr, SMOOTH, LEVEL, MIN_AREA, TOL)
    json.dump([mapping(p) for p in polys], open(os.path.join(OUT, 'fescue.json'), 'w'))
    print(len(polys), 'areas,', round(sum(p.area for p in polys) / 10000, 1), 'ha,', sum(len(p.exterior.coords) for p in polys), 'vertices')


if __name__ == '__main__':
    main()
