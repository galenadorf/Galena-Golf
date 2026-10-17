"""Tees: read the hand-edited out/tee_boxes_mask.png (made from out/tee_boxes_edit.png, same pixels).
  pure MAGENTA (#FF00FF)  the tee boxes   -> out/tees_painted.json (polygons, local metres); build.py uses them instead of
                          the OSM tee boxes, and each tee set (gold, black, silver, bronze) still plays from the point of
                          the nearest box at its card yardage
  pure YELLOW (#FFFF00)   a small dot where the played (gold) tee should be for a hole -> out/tee_starts.json ([e, n] points);
                          build.py gives the hole whose line passes nearest to the dot that start
Rerun tee_boxes_paint.py, build.py, install.py after repainting."""
import json
import os

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import mapping, shape

from common import OUT

MIN_AREA = 3.0   # m2: smaller specks are paint noise


def blobs(a, rgb, fr, tr):
    m = (np.abs(a - np.array(rgb)).max(2) <= 40)
    m = ndi.binary_closing(m, iterations=3 if rgb[2] == 255 else 1)  # the tee-set rings drawn on the map cut thin lines through a box
    if rgb[2] == 255:
        m = ndi.binary_fill_holes(m)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s * fr['res'] ** 2 >= MIN_AREA])
    return [shape(g).buffer(0) for g, v in features.shapes(m.astype(np.uint8), mask=m, transform=tr) if v]


def main():
    fr = json.load(open(os.path.join(OUT, 'fescue_base.json')))
    a = np.array(Image.open(os.path.join(OUT, 'tee_boxes_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    boxes = [p.simplify(.25) for p in blobs(a, (255, 0, 255), fr, tr) if p.area >= MIN_AREA]
    starts = [[round(p.centroid.x, 2), round(p.centroid.y, 2)] for p in blobs(a, (255, 255, 0), fr, tr)]
    json.dump([mapping(p) for p in boxes], open(os.path.join(OUT, 'tees_painted.json'), 'w'))
    json.dump(starts, open(os.path.join(OUT, 'tee_starts.json'), 'w'))
    print(len(boxes), 'tee boxes,', round(sum(p.area for p in boxes)), 'm2;', len(starts), 'start dots')


if __name__ == '__main__':
    main()
