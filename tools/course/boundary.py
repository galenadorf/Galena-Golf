"""The course boundary (out of bounds): read the hand-painted out/course_boundary.png (solid cyan over out/fescue_base.png,
same pixels) and write out/boundary.json, one polygon in local metres. build.py uses it in place of the OSM course outline
and clips the fescue to it. Rerun boundary.py, build.py, install.py after repainting."""
import json
import os

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import mapping, shape

from common import OUT


def from_mask(m, fr):
    """The boundary polygon from a boolean mask on the grid `fr`: a filled area or a closed outline (also used by all_read.py). Returns it and the number of pieces."""
    m = ndi.binary_fill_holes(ndi.binary_closing(m, iterations=3))
    lab, n = ndi.label(m)
    keep = lab == (1 + int(np.argmax(ndi.sum(m, lab, range(1, n + 1)))))  # one shape: the largest
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    polys = [shape(g) for g, v in features.shapes(keep.astype(np.uint8), mask=keep, transform=tr) if v]
    return max(polys, key=lambda q: q.area).buffer(0).simplify(1.0), n


def main():
    fr = json.load(open(os.path.join(OUT, 'fescue_base.json')))
    a = np.array(Image.open(os.path.join(OUT, 'course_boundary.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    p, n = from_mask((a[..., 0] < 110) & (a[..., 1] > 150) & (a[..., 2] > 150), fr)  # cyan, also its anti-aliased edge pixels
    json.dump(mapping(p), open(os.path.join(OUT, 'boundary.json'), 'w'))
    print('boundary', round(p.area / 1e4, 1), 'ha,', len(p.exterior.coords), 'vertices,', n, 'cyan pieces')


if __name__ == '__main__':
    main()
