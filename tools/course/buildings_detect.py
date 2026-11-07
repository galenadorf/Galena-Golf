"""Roofs found on the 2023 aerial (NAIP, red/green/blue/near-infrared, 0.5 m): a random forest taught by the building footprints already known in a
part of the course where they are complete (out/buildings_painted.json from buildings_overture.py plus OSM's), applied to the whole detail area.
A roof is low in vegetation (NDVI), has the texture of shingle and is compact; roads, drives, sand and bright lots are the other classes.
Components of 70-1400 m2 that are compact, within OVERTURE_REACH of a hole line and not already a known building become new footprints (each the
minimum-area rectangle of the roof pixels, grown 0.3 m), written to out/buildings_detected.json, with out/buildings_prob.npy the probability map.
course.ROOF_TRAIN = (e0, n0, e1, n1): the complete part to learn from.

  python buildings_detect.py --course <key> [--retrain]   (the probability map is kept; --retrain refits and rebuilds it)
"""
import json
import math
import os
import sys

import numpy as np
import rasterio
from rasterio import features as rf
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from shapely.geometry import Point, box, mapping, shape
from shapely.ops import unary_union
from skimage.feature import peak_local_max
from skimage.segmentation import watershed
from sklearn.ensemble import RandomForestClassifier

import osm
from common import DETAIL, OUT, cache, course

E0, N0, E1, N1 = DETAIL
RES = .5


def load():
    with rasterio.open(cache('naip2023_025.tif')) as s:
        a = s.read().astype(np.float32)
    a = a.reshape(4, a.shape[1] // 2, 2, a.shape[2] // 2, 2).mean((2, 4))
    return a   # 4 x h x w


def features(a):
    r, g, b, n = a
    lum = (r + g + b) / 3
    ndvi = (n - r) / (n + r + 1)
    sat = a[:3].max(0) - a[:3].min(0)
    f = [r, g, b, n, ndvi, sat, lum]
    for s in (1.5, 4):
        m = ndi.gaussian_filter(lum, s)
        f += [np.sqrt(np.maximum(ndi.gaussian_filter(lum * lum, s) - m * m, 0)), m, ndi.gaussian_filter(ndvi, s)]
    f += [ndi.gaussian_filter(lum, 9) - lum, ndi.gaussian_filter(ndvi, 9)]
    return np.stack(f, -1).astype(np.float32)


def near_play(F, reach):
    """Where a house counts as along a hole: within `reach` of a hole line, or within reach - 20 of a fairway, green or tee box."""
    fp = os.path.join(OUT, 'fairways_painted.json')
    fair = [shape(g) for g in json.load(open(fp))] if os.path.exists(fp) else [f['poly'] for f in F['fairway']]
    play = [f['poly'] for k in ('green', 'tee') for f in F[k]] + fair
    return unary_union([hh['line'].buffer(reach) for hh in F['hole']] + [q.buffer(reach - 20) for q in play])


def main():
    a = load()
    _, h, w = a.shape
    tr = from_origin(E0, N1, RES, RES)
    R = lambda geoms: rf.rasterize([(g, 1) for g in geoms], out_shape=(h, w), transform=tr, dtype='uint8').astype(bool) if geoms else np.zeros((h, w), bool)
    F = osm.load()
    known = [b['poly'] for b in F['building'] if b['poly'].area >= 40]
    kp = os.path.join(OUT, 'buildings_painted.json')
    known += [shape(g) for g in json.load(open(kp))] if os.path.exists(kp) else []
    pos = R(known)
    e0, n0, e1, n1 = getattr(course, 'ROOF_TRAIN', (-300, -300, 250, 0))
    region = R([box(e0, n0, e1, n1)])
    neg = region & ~R([g.buffer(2.0) for g in known])
    pos &= region
    X = features(a)
    rng = np.random.default_rng(1)
    ip, ineg = np.flatnonzero(pos.ravel()), np.flatnonzero(neg.ravel())
    ip, ineg = rng.choice(ip, min(len(ip), 150000), replace=False), rng.choice(ineg, min(len(ineg), 250000), replace=False)
    idx = np.concatenate([ip, ineg]); y = np.r_[np.ones(len(ip)), np.zeros(len(ineg))]
    Xf = X.reshape(-1, X.shape[-1])
    clf = RandomForestClassifier(n_estimators=60, max_depth=16, min_samples_leaf=8, n_jobs=-1, random_state=1).fit(Xf[idx], y)
    pp = os.path.join(OUT, 'buildings_prob.npy')
    if os.path.exists(pp) and '--retrain' not in sys.argv:
        prob = np.load(pp)
    else:
        prob = np.zeros(h * w, np.float32)
        for i in range(0, h * w, 600000):
            prob[i:i + 600000] = clf.predict_proba(Xf[i:i + 600000])[:, 1]
        prob = prob.reshape(h, w)
        np.save(pp, prob)
    m = ndi.binary_opening(ndi.gaussian_filter(prob, 1) > .5, structure=np.ones((3, 3)), iterations=2)
    m = ndi.binary_fill_holes(m)
    # roofs that touch (a row of houses, a house and its drive) are cut apart where the blob pinches (watershed on the distance to the edge)
    dist = ndi.distance_transform_edt(m)
    pk = peak_local_max(ndi.gaussian_filter(dist, 2), min_distance=10, threshold_abs=3.5, labels=ndi.label(m)[0], exclude_border=False)
    mk = np.zeros(m.shape, np.int32); mk[tuple(pk.T)] = np.arange(1, len(pk) + 1)
    lab = watershed(-dist, mk, mask=m)
    reach = getattr(course, 'OVERTURE_REACH', 110)
    near = near_play(F, reach)
    kn = unary_union(known) if known else None
    out, why = [], dict(size=0, far=0, shape=0, known=0)
    roads = unary_union([q['line'] for q in F['road']]) if F['road'] else Point(1e9, 1e9)
    for g, v in rf.shapes(lab.astype(np.int32), mask=m, transform=tr):
        p = shape(g).buffer(0)
        if not 50 <= p.area <= 1400:
            why['size'] += 1; continue
        if not p.intersects(near):
            why['far'] += 1; continue
        r = p.minimum_rotated_rectangle
        if p.area < .6 * r.area:   # not compact: a drive, a hedge, a stretch of sand
            why['shape'] += 1; continue
        if kn is not None and r.intersection(kn).area > .25 * r.area:
            why['known'] += 1; continue
        c = list(r.exterior.coords)
        if min(math.hypot(c[1][0] - c[0][0], c[1][1] - c[0][1]), math.hypot(c[2][0] - c[1][0], c[2][1] - c[1][1])) < 6.5 or r.distance(roads) < 2:
            why['thin'] = why.get('thin', 0) + 1; continue   # a kerb, a drive, a fence line is not a roof
        out.append(r.buffer(.3, join_style=2))
    print('rejected:', why)
    json.dump([mapping(p) for p in out], open(os.path.join(OUT, 'buildings_detected.json'), 'w'))
    print(len(out), 'new roofs found (not in the known footprints), training px', len(ip), len(ineg))


if __name__ == '__main__':
    main()
