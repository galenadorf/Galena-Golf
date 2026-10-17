"""Fairways: read the hand-corrected out/fairway_mask.png (pure green #00FF00 over the aerial; made from out/fairway_edit.png,
same pixels) and write out/fairways_painted.json (polygons in local metres). build.py uses it instead of trace.py's
fairways.json when it exists. Rerun fairways.py, build.py, install.py after repainting."""
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

MIN_AREA = 60.0  # m2: smaller specks and holes are paint noise


def main():
    fr = json.load(open(os.path.join(OUT, 'fescue_base.json')))
    a = np.array(Image.open(os.path.join(OUT, 'fairway_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (g >= 215) & (r <= 45) & (b <= 45)  # pure green (60,255,60 outline pixels of other layers do not count)
    px = fr['res'] ** 2
    m = ndi.binary_closing(m, iterations=2)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s * px >= MIN_AREA])
    inv, n = ndi.label(~m)
    sizes = ndi.sum(~m, inv, range(1, n + 1))
    for i, s in enumerate(sizes):
        if s * px < MIN_AREA:
            m |= inv == i + 1
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    polys = [shape(gg).buffer(0) for gg, v in features.shapes(m.astype(np.uint8), mask=m, transform=tr) if v]
    polys = [p.simplify(.5) for p in polys if p.area >= MIN_AREA]
    json.dump([mapping(p) for p in polys], open(os.path.join(OUT, 'fairways_painted.json'), 'w'))
    old = unary_union([shape(gg) for gg in json.load(open(os.path.join(OUT, 'fairways.json')))])
    new = unary_union(polys)
    print(len(polys), 'fairway areas,', round(new.area / 1e4, 2), 'ha (the traced ones:', round(old.area / 1e4, 2), 'ha; overlap', round(old.intersection(new).area / 1e4, 2), 'ha)')


if __name__ == '__main__':
    main()
