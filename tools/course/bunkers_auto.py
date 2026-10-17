"""Bunkers missing from OpenStreetMap, found on the aerial: bright, warm, non-green, compact blobs.

Sand on the NAIP image (0.5 m, July 2023) is bright (luma 175+), warm (red - blue 29+) and far from vegetation (NDVI under
-0.13); cart paths, gravel and the parking lot are thin, dull or irregular, so a blob has to be at least 25 m2, solid
(convex, not stringy) and bright to count. Blobs already covered by an OSM bunker, inside buildings or outside the course
boundary are skipped. Writes out/bunkers_auto.json (polygons, local metres); build.py adds them to the OSM bunkers.
Greens, tees, fairways and fescue are not touched.
"""
import json
import os

import numpy as np
import rasterio
from rasterio import features as rf
from scipy import ndimage as ndi
from shapely.geometry import mapping, shape
from skimage.measure import label, regionprops
from skimage.morphology import binary_opening, disk

from common import OUT, cache
import osm


def main():
    with rasterio.open(cache('naip.tif')) as s:
        a, tr = s.read().astype(np.float32), s.transform
    R, G, B, N = a
    luma, ndvi, rb = (R + G + B) / 3, (N - R) / (N + R + 1e-6), R - B
    F = osm.load()
    bound = shape(json.load(open(os.path.join(OUT, 'boundary.json'))))
    sh = luma.shape
    ras = lambda polys: rf.rasterize([(p, 1) for p in polys], out_shape=sh, transform=tr, dtype='uint8').astype(bool)
    skip = ras([f['poly'].buffer(2) for f in F['bunker']]) | ras([f['poly'].buffer(3) for f in F['building']]) | ~ras([bound])
    m = binary_opening((ndi.gaussian_filter(luma, .7) > 138) & (ndvi < -.07) & (rb > 20), disk(2)) & ~skip
    lab = label(m, connectivity=2)
    out = []
    for r in regionprops(lab):
        area = r.area * .25
        sel = lab == r.label
        if not (25 <= area <= 800 and r.solidity >= .9 and r.eccentricity < .93 and luma[sel].mean() >= 175 and rb[sel].mean() >= 29):
            continue
        polys = [shape(g) for g, v in rf.shapes(sel.astype(np.uint8), mask=sel, transform=tr) if v]
        p = max(polys, key=lambda q: q.area).buffer(.6).simplify(.3)  # the opening and the threshold shave a little off the edge
        out.append(p)
        e, n = p.centroid.x, p.centroid.y
        print(f'bunker at e {e:.0f} n {n:.0f}: {p.area:.0f} m2')
    json.dump([mapping(p) for p in out], open(os.path.join(OUT, 'bunkers_auto.json'), 'w'))
    print(len(out), 'bunkers added to the', len(F['bunker']), 'in OSM')


if __name__ == '__main__':
    main()
