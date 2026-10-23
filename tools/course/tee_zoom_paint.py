"""Read the tee close-ups painted by hand: out/tee<hole>_zoom_mask.png (made from out/tee<hole>_zoom.png; see tee_zoom_edit.py).
  MAGENTA blobs  the tee boxes of that hole
  YELLOW dot     where the played (gold) tee should be
Holes without a mask keep their current tee boxes (those inside no painted picture). Writes out/tees_painted.json (polygons in
local metres, read by build.py instead of the OSM boxes) and out/tee_starts.json ([e, n] dots). Rerun this, build.py, install.py
after repainting."""
import json
import os

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import box, mapping, shape

import osm
from common import OUT

MIN_AREA = 2.0   # m2: smaller specks are paint noise


def blobs(a, rgb, tr, ppm, min_area, fill):
    m = ndi.binary_closing(np.abs(a - np.array(rgb)).max(2) <= 40, iterations=2)
    if fill:
        m = ndi.binary_fill_holes(m)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s / ppm ** 2 >= min_area])
    return [shape(g).buffer(0) for g, v in features.shapes(m.astype(np.uint8), mask=m, transform=tr) if v]


def main():
    F = osm.load()
    boxes, starts, frames = [], [], []
    for h in F['hole']:
        ref = h['ref']
        jp, mp = os.path.join(OUT, f'tee{ref}_zoom.json'), os.path.join(OUT, f'tee{ref}_zoom_mask.png')
        if not (os.path.exists(jp) and os.path.exists(mp)):
            continue
        f = json.load(open(jp))
        a = np.array(Image.open(mp).convert('RGB')).astype(int)
        assert a.shape[1] == f['w'] and a.shape[0] == f['h'], f'hole {ref}: the mask must have the close-up\'s size'
        a[f['h'] - 150:f['h'] - 20, 20:900] = 0    # the key printed on the picture is ignored
        tr = Affine(1 / f['ppm'], 0, f['e0'], 0, -1 / f['ppm'], f['n1'])
        tb = [p.simplify(.1) for p in blobs(a, (255, 0, 255), tr, f['ppm'], MIN_AREA, True)]
        st = [[round(p.centroid.x, 2), round(p.centroid.y, 2)] for p in blobs(a, (255, 255, 0), tr, f['ppm'], .2, False)]
        if not tb and not st:
            continue
        frames.append(box(f['e0'], f['n1'] - f['h'] / f['ppm'], f['e0'] + f['w'] / f['ppm'], f['n1']))
        boxes += tb; starts += st[:1]
        print(f'hole {ref}: {len(tb)} tee boxes, {round(sum(p.area for p in tb))} m2, start dot' if st else f'hole {ref}: {len(tb)} tee boxes, {round(sum(p.area for p in tb))} m2')
    # the current boxes of holes nobody painted stay (a box inside a painted picture is replaced by what was painted)
    keep = [t['poly'] for t in F['tee'] if not any(fr.contains(t['poly'].centroid) for fr in frames)]
    json.dump([mapping(p) for p in keep + boxes], open(os.path.join(OUT, 'tees_painted.json'), 'w'))
    json.dump(starts, open(os.path.join(OUT, 'tee_starts.json'), 'w'))
    print(len(boxes), 'painted boxes +', len(keep), 'current boxes kept;', len(starts), 'start dots')


if __name__ == '__main__':
    main()
