"""Trace fairways (and cart paths) from the NAIP aerial, since OSM has neither.

Per 0.5 m pixel: smoothed R, G, B, NIR, NDVI and two texture measures (local spread of the green band). Fairway grass is
even and bright; rough, tall grass and mounds are textured and duller; paths are pale with little NDVI. A Gaussian
classifier is trained on samples taken automatically (fairway: the middle of each OSM hole line; rough: well away from
every line), retrained once on its own confident answers, then cleaned up with morphology and the OSM features.

  out/fairways.json   list of GeoJSON polygons (local metres)
  out/paths.json      list of GeoJSON polygons (local metres)
  out/trace_mask.png  the raw classes, for checking
"""
import json
import os
import sys
import warnings

import numpy as np
import rasterio
from PIL import Image
from scipy import ndimage as ndi
from skimage.segmentation import random_walker
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from rasterio import features as rfeat

from common import DETAIL, OUT, cache
import osm

E0, N0, E1, N1 = DETAIL


def raster_of(geoms, tr, shp):
    geoms = [g for g in geoms if not g.is_empty]
    if not geoms:
        return np.zeros(shp, bool)
    return rfeat.rasterize([(g, 1) for g in geoms], out_shape=shp, transform=tr, dtype='uint8').astype(bool)


def gauss_fit(X):
    mu = X.mean(0)
    C = np.cov(X.T) + np.eye(X.shape[1]) * 1e-4
    return mu, np.linalg.inv(C), np.linalg.slogdet(C)[1]


def gauss_ll(X, m):
    mu, Ci, ld = m
    d = X - mu
    return -.5 * (np.einsum('ij,jk,ik->i', d, Ci, d) + ld)


def main(thr=0.0):
    F = osm.load()
    with rasterio.open(cache('naip.tif')) as s:
        img = s.read().astype(np.float32)
        tr = s.transform
    res = tr.a
    H, W = img.shape[1:]
    R, G, B, N = img
    sm = lambda a, s: ndi.gaussian_filter(a, s)
    ndvi = (N - R) / (N + R + 1)
    feats = [sm(R, 2), sm(G, 2), sm(B, 2), sm(N, 2), sm(ndvi, 2) * 100]
    for s in (2, 5):  # texture: local standard deviation of green, at 1 m and 2.5 m
        m = sm(G, s)
        feats.append(np.sqrt(np.maximum(sm(G * G, s) - m * m, 0)))
    X = np.stack(feats, -1).reshape(-1, len(feats))
    X = (X - X.mean(0)) / X.std(0)

    course = F['course'][0]['poly']
    inC = raster_of([course.buffer(-2)], tr, (H, W))
    green = raster_of([f['poly'] for f in F['green']], tr, (H, W))
    tee = raster_of([f['poly'] for f in F['tee']], tr, (H, W))
    sand = raster_of([f['poly'].buffer(.5) for f in F['bunker']], tr, (H, W))
    water = raster_of([f['poly'] for f in F['water']], tr, (H, W))
    keep_out = green | tee | sand | water

    # training samples
    mid = []
    for h in F['hole']:
        L = h['line']
        if h['par'] > 3:
            mid.append(unary_union([L.interpolate(t, normalized=True).buffer(3) for t in np.linspace(.4, .8, 12)]))
    lines = unary_union([h['line'] for h in F['hole']])
    # par 3s play over mown rough (no traced fairway); fairways only grow along par 4 and 5 lines
    lines45 = unary_union([h['line'] for h in F['hole'] if h['par'] > 3])
    fair0 = raster_of([g for g in mid if not g.is_empty], tr, (H, W)) & inC & ~keep_out
    far0 = inC & ~raster_of([lines.buffer(28)], tr, (H, W)) & ~keep_out
    print('samples: fairway', fair0.sum(), 'rough', far0.sum())

    fl = fair0.ravel()
    rl = far0.ravel()
    mF, mR = gauss_fit(X[fl]), gauss_fit(X[rl])
    for it in range(2):
        llr = (gauss_ll(X, mF) - gauss_ll(X, mR)).reshape(H, W)
        conf_f = (llr > 4) & inC & ~keep_out & raster_of([lines45.buffer(40)], tr, (H, W))
        conf_r = (llr < -4) & inC & ~keep_out
        print(f'iter {it}: fairway px {conf_f.sum()}, rough px {conf_r.sum()}')
        mF, mR = gauss_fit(X[conf_f.ravel()]), gauss_fit(X[conf_r.ravel()])
    llr = (gauss_ll(X, mF) - gauss_ll(X, mR)).reshape(H, W)

    # paths: pale, low NDVI, inside the course, not sand or water
    bright = (feats[0] + feats[1] + feats[2]) / 3
    pth = (feats[4] < np.percentile(feats[4][inC], 6)) & (bright > np.percentile(bright[inC], 80)) & inC & ~sand & ~water & ~green & ~tee
    pth = ndi.binary_opening(pth, iterations=1)
    lab, n = ndi.label(pth)
    sizes = ndi.sum(pth, lab, range(1, n + 1))
    pth = np.isin(lab, 1 + np.flatnonzero(sizes > 120))  # > 30 m²

    # fairway mask, hole by hole: a random walker on the aerial grows "fairway" from seeds along the hole line and "rough"
    # from everything well away from it (and from strongly textured ground, trees, greens, tees, bunkers, ponds); the
    # two meet at the strongest edge between them, which is where the mowing changes. Seeds only go where the line
    # crosses fairway-like grass (the classifier above and smooth texture), so a line over rough seeds nothing there.
    tex = ndi.gaussian_filter(np.sqrt(np.maximum(sm(G * G, 3) - sm(G, 3) ** 2, 0)), 2)
    dark = sm(G, 1) < np.percentile(G, 8)
    rw = np.stack([sm(R, 1), sm(G, 1), sm(B, 1), sm(N, 1)], -1)
    rw = (rw - rw.mean((0, 1))) / rw.std((0, 1))
    like = (ndi.gaussian_filter(llr, 2) > thr) & (tex < np.percentile(tex[inC], 60))
    # trees and their shadows (dark) stay unlabelled: a shadow across the fairway is still fairway
    hard = keep_out | (tex > np.percentile(tex[inC], 93)) | ~inC | ndi.binary_dilation(pth, iterations=1)
    fw = np.zeros((H, W), bool)
    for h in F['hole']:
        if h['par'] == 3:
            continue
        L = h['line']
        e0, n0, e1, n1 = L.buffer(55).bounds
        c0, r0 = ~tr * (e0, n1)
        c1, r1 = ~tr * (e1, n0)
        c0, r0, c1, r1 = max(0, int(c0)), max(0, int(r0)), min(W, int(c1)), min(H, int(r1))
        sl = (slice(r0, r1), slice(c0, c1))
        trs = tr * tr.translation(c0, r0)
        shp = (r1 - r0, c1 - c0)
        lab = np.zeros(shp, np.int32)
        seed = raster_of([unary_union([L.interpolate(s, normalized=True).buffer(2.5) for s in np.linspace(.15, .95, 40)])], trs, shp)
        lab[(~raster_of([L.buffer(32)], trs, shp) | hard[sl]) & ~dark[sl]] = 2
        lab[seed & like[sl] & ~hard[sl] & ~dark[sl]] = 1
        if not (lab == 1).any():
            print('hole', h['ref'], 'no fairway seeds')
            continue
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            pr = random_walker(rw[sl][::2, ::2], lab[::2, ::2], beta=300, mode='cg_j', channel_axis=-1, return_full_prob=True)[0]
        m = np.kron(pr > .5, np.ones((2, 2), bool))[:shp[0], :shp[1]]
        # keep only the pieces that hold a seed
        cl, n = ndi.label(m)
        m = np.isin(cl, np.unique(cl[(lab == 1) & m]))
        fw[sl] |= m
        print(f'hole {h["ref"]:2d}: {m.sum() * res * res:6.0f} m²')
    fw &= ~keep_out
    r = int(round(1.5 / res))
    disk = np.hypot(*np.mgrid[-r:r + 1, -r:r + 1]) <= r
    fw = ndi.binary_closing(ndi.binary_opening(fw, structure=disk), structure=disk)
    fw = ndi.binary_fill_holes(fw)

    # masks to polygons (smoothed, simplified)
    def polys(mask, smooth, simp, min_area):
        out = []
        for g, v in rfeat.shapes(mask.astype('uint8'), mask=mask, transform=tr):
            p = shape(g).buffer(smooth, join_style=1).buffer(-smooth, join_style=1).simplify(simp)
            for q in getattr(p, 'geoms', [p]):
                if q.area >= min_area:
                    out.append(q)
        return out

    fair = polys(fw, 1.5, .4, 300)
    # never over the OSM greens, tees, bunkers and ponds
    cut = unary_union([f['poly'].buffer(1.5) for f in F['green']] + [f['poly'] for f in F['tee'] + F['bunker'] + F['water']])
    fair = [q for p in fair for q in getattr(p.difference(cut), 'geoms', [p.difference(cut)]) if q.area >= 300]
    paths = polys(pth, .6, .3, 25)
    json.dump([mapping(p) for p in fair], open(os.path.join(OUT, 'fairways.json'), 'w'))
    json.dump([mapping(p) for p in paths], open(os.path.join(OUT, 'paths.json'), 'w'))
    print(f'fairways: {len(fair)} polygons, {sum(p.area for p in fair) / 1e4:.1f} ha; paths: {len(paths)} polygons, {sum(p.area for p in paths):.0f} m²')

    vis = np.zeros((H, W, 3), np.uint8)
    vis[inC] = (70, 40, 20)
    vis[fw] = (240, 220, 0)
    vis[pth] = (255, 255, 255)
    vis[keep_out] = (0, 160, 0)
    Image.fromarray(vis).save(os.path.join(OUT, 'trace_mask.png'))
    np.save(os.path.join(OUT, 'llr.npy'), ndi.gaussian_filter(llr, 2).astype(np.float32))


if __name__ == '__main__':
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 0.0)
