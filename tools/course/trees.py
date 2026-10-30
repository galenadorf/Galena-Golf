"""Single trees from the lidar canopy height model (.cache/chm.tif).

Tree tops are local maxima of the smoothed canopy (the search window grows with the tree's height); each top's crown is
its watershed basin. Kind, as the game draws them: 1 shrub (under 4 m), 2 conifer, 0 broadleaf. Conifers (the spruce and
pine rows) are narrow for their height or dark in near infrared on the aerial (needles reflect less NIR than leaves);
NIR alone doesn't split cleanly, so either sign counts.

  out/trees.json   [{e, n, d, h, kind}]   (local metres; d crown diameter, h height)
"""
import json
import os

import numpy as np
import rasterio
from rasterio import features as rfeat
from scipy import ndimage as ndi
from skimage.segmentation import watershed

from common import OUT, cache, course

# a closed forest of tall oaks and hickories (Chestnut Mountain) has narrow watershed crowns and other NAIP tiles: the course can set its own NIR
# threshold for conifers and turn the narrow-for-its-height rule off (course.CONIFER_NIR, course.CONIFER_SHAPE)
NIR_DARK, SHAPE = getattr(course, 'CONIFER_NIR', 112), getattr(course, 'CONIFER_SHAPE', True)
import osm


def main():
    with rasterio.open(cache('chm.tif')) as s:
        chm = s.read(1)
        tr = s.transform
    F = osm.load()
    with rasterio.open(cache('naip.tif')) as s:
        nir, trn = s.read(4).astype(np.float32), s.transform
    bld = rfeat.rasterize([(f['poly'].buffer(1.5), 1) for f in F['building']], out_shape=chm.shape, transform=tr, dtype='uint8').astype(bool)
    chm[bld] = 0
    sm = ndi.gaussian_filter(chm, 1)
    veg = sm > 2.5
    # tops: maximum within a radius that grows with height (bigger trees, wider crowns)
    tops = np.zeros_like(veg)
    for h0, h1, r in ((2.5, 6, 2), (6, 12, 3), (12, 20, 4), (20, 99, 5)):
        fp = np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r
        mx = ndi.maximum_filter(sm, footprint=fp)
        tops |= (sm == mx) & (sm >= h0) & (sm < h1)
    tops &= veg
    lab, n = ndi.label(tops)
    markers = lab
    crowns = watershed(-sm, markers, mask=veg)
    idx = np.arange(1, n + 1)
    area = ndi.sum(np.ones_like(sm), crowns, idx)
    hmax = ndi.maximum(chm, crowns, idx)
    cy, cx = np.array(ndi.center_of_mass(tops, lab, idx)).T
    out = []
    for k in range(n):
        if area[k] < 3:
            continue
        e, nn = tr * (cx[k] + .5, cy[k] + .5)
        d = 2 * np.sqrt(area[k] / np.pi)
        h = float(hmax[k])
        c, r = ~trn * (e, nn)
        k2 = max(1, int(d / 2 / trn.a * .6))
        win = nir[max(0, int(r) - k2):int(r) + k2 + 1, max(0, int(c) - k2):int(c) + k2 + 1]
        dark = win.size > 0 and win.mean() < NIR_DARK
        kind = 1 if h < 4 else 2 if (SHAPE and d < .65 * h and h > 5) or dark else 0
        out.append(dict(e=round(e, 1), n=round(nn, 1), d=round(float(min(d, 21)), 1), h=round(h, 1), kind=kind))
    json.dump(out, open(os.path.join(OUT, 'trees.json'), 'w'))
    ks = np.bincount([t['kind'] for t in out], minlength=3)
    print(f'{len(out)} trees: {ks[0]} broadleaf, {ks[2]} conifer, {ks[1]} shrubs; median height {np.median([t["h"] for t in out]):.1f} m')


if __name__ == '__main__':
    main()
