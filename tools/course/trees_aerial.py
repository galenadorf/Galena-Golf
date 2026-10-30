"""Trees checked against the newest aerial: grows crowns that are drawn too small and adds the canopy nobody placed.

The newest public aerial is NAIP July 2023 (0.3 m; fetched here at 0.25 m into .cache/naip2023_025.tif). A classifier
(sklearn gradient boosting) learns canopy from it, taught by the 2019 lidar (.cache/chm.tif: canopy over 4 m = tree,
bare = not). Tree shadows look like canopy, so the shadows are predicted from the lidar heights (the aerial was flown
with the sun in the east: shadows point west, about 1.2x the tree's height) and a predicted shadow that is also dark
is dropped. The crown mask is that canopy, plus 2019 lidar canopy next to it, less the OSM buildings and anything
brighter than leaves ever are (roofs, grain bins, gravel, roads: the classifier and the lidar take some of them for trees).

  grow  every tree the game has (lidar trees.json less trees_removed.json, plus trees_painted.json) is measured on the
        crown mask (each pixel belongs to the nearest tree): the crown reaches the last ring around the tree that is
        still mostly canopy, on its east half (the shadows fall west). A crown drawn more than 15 % (and 1 m) too small is
        grown to it, at most 1.6x (a conifer 1.25x), 21 m.
        Nothing is grown or added on the practice green or inside the driving range (8 m round them): they have their own
        painted trees.
  add   canopy still not covered after that (blobs of 6 m2 and up) becomes trees the way trees_paint.py does it (a blob
        up to 90 m2 is one tree sized to it, bigger ones are filled about 6 m apart). Canopy the 2019 lidar did not
        see (grown or planted since) must be clearly canopy to the classifier (mean score .75). Under 4 m tall (lidar) is a shrub.

  drop  a lidar tree whose crown is a bright roof or gravel on the aerial (no leaf canopy is that bright; a building
        OSM lacks or one put up since 2019, the yard south-east of the course) is taken out, and so is any lidar tree inside
        a painted shed (the range's metal shed, the pump house). Painted trees never are.

Writes out/trees_aerial.json {drop: [{e, n}], grow: [{e, n, d, h}], add: [{e, n, d, h, kind}]} and out/trees_aerial.png
(the aerial, yellow = trees as they were, red = dropped, cyan = grown, magenta = added). build.py applies it after the
painted trees: dropped and grown trees matched by position, added trees appended. Rerun build.py, install.py after.
"""
import json
import os

import numpy as np
import rasterio
import requests
from PIL import Image, ImageDraw
from rasterio import features as rfeat
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from shapely.geometry import Point, shape
from shapely.ops import unary_union

import osm
from common import DETAIL, OUT, UA, bbox_lonlat, cache, course
from fetch import warp
from trees_paint import from_masks, height

E0, N0, E1, N1 = DETAIL
RES = .5            # m per pixel of the masks
GROW_MIN = 1.15     # grow a crown measured at least this much wider (and 1 m wider)
GROW_MAX = 1.6      # never more than this
CONIFER_MAX = 1.25  # a conifer's dark crown runs into its shadow: grown less
D_MAX = 21.0        # m, the widest crown (as trees.py)
RING_FULL = .55     # a ring still belongs to the crown when this share of it is canopy
GONE_P = .25        # course.TREES_GONE: a lidar tree whose crown scores under this on the aerial (mean canopy probability) was felled


def naip2023():
    out = cache('naip2023_025.tif')
    if not os.path.exists(out):
        w, s, e, n = bbox_lonlat(DETAIL)
        body = {'collections': ['naip'], 'bbox': [w, s, e, n], 'limit': 10, 'sortby': [{'field': 'datetime', 'direction': 'desc'}]}
        feats = requests.post('https://planetarycomputer.microsoft.com/api/stac/v1/search', json=body, headers=UA, timeout=60).json()['features']
        feats = [f for f in feats if f['properties']['datetime'][:4] == feats[0]['properties']['datetime'][:4]]   # every tile of the newest year (Stonehenge spans two)
        tok = requests.get('https://planetarycomputer.microsoft.com/api/sas/v1/token/naip', headers=UA, timeout=60).json()['token']
        print('NAIP', [f['id'] for f in feats])
        parts = []
        for i, f in enumerate(feats):
            parts.append(cache(f'naip2023_{i}.tif'))
            warp('/vsicurl/' + f['assets']['image']['href'] + '?' + tok, parts[-1], DETAIL, .25, resampling=Resampling.cubic)
        with rasterio.open(parts[0]) as a:   # mosaic: the first tile that has data wins
            prof, acc = a.profile, a.read()
        for q in parts[1:]:
            with rasterio.open(q) as b:
                d = b.read()
            hole = acc.sum(0) == 0
            acc[:, hole] = d[:, hole]
        with rasterio.open(out, 'w', **prof) as dst:
            dst.write(acc)
        for q in parts:
            os.remove(q)
    with rasterio.open(out) as s:
        a = s.read().astype(np.float32)
    h, w = a.shape[1] // 2, a.shape[2] // 2
    return a, a.reshape(4, h, 2, w, 2).mean((2, 4))


def canopy_prob(a2, ch):
    from sklearn.ensemble import HistGradientBoostingClassifier
    R, G, B, N = a2
    br = (R + G + B) / 3
    f = [R, G, B, N, (N - R) / (N + R + 1), G / (R + G + B + 1)]
    for s in (3, 7, 15):
        m, mn = ndi.uniform_filter(br, s), ndi.uniform_filter(N, s)
        f += [m, np.sqrt(np.maximum(ndi.uniform_filter(br ** 2, s) - m ** 2, 0)), mn, np.sqrt(np.maximum(ndi.uniform_filter(N ** 2, s) - mn ** 2, 0))]
    f += [ndi.uniform_filter(br, 31) - br, ndi.minimum_filter(br, 9), ndi.maximum_filter(N, 9), ndi.gaussian_laplace(br, 2)]
    X = np.stack([x.ravel() for x in f], 1).astype(np.float32)
    pos = ndi.binary_erosion(ch >= 4, iterations=1).ravel()
    neg = ndi.binary_erosion(ch < .3, iterations=4).ravel()
    rng = np.random.default_rng(0)
    ip, ineg = rng.choice(np.where(pos)[0], 80000), rng.choice(np.where(neg)[0], 300000)
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=.1, max_leaf_nodes=63, random_state=0)
    clf.fit(np.concatenate([X[ip], X[ineg]]), np.r_[np.ones(len(ip)), np.zeros(len(ineg))])
    return clf.predict_proba(X)[:, 1].reshape(br.shape), br


def shadows(ch):
    """Where a lidar tree throws its shadow on this aerial (sun in the east: shadows point west, ~1.2x the height)."""
    sh = np.zeros_like(ch, bool)
    for az in (265, 275, 285):
        ux, uy = np.sin(np.radians(az)), -np.cos(np.radians(az))
        for dist in np.arange(.5, 25, .5):
            dx, dy = int(round(ux * dist / RES)), int(round(uy * dist / RES))
            sh |= np.roll(np.roll(ch, dy, 0), dx, 1) * 1.45 + 1 >= dist
    return sh & (ch < 1.5)


def disks(trees, shape_, grow=0.):
    yy, xx = np.mgrid[0:shape_[0], 0:shape_[1]]
    m = np.zeros(shape_, bool)
    for t in trees:
        cx, cy, r = (t['e'] - E0) / RES, (N1 - t['n']) / RES, (t['d'] / 2 + grow) / RES
        x0, x1, y0, y1 = int(max(0, cx - r)), int(min(shape_[1], cx + r + 2)), int(max(0, cy - r)), int(min(shape_[0], cy + r + 2))
        if x1 > x0 and y1 > y0:
            m[y0:y1, x0:x1] |= (xx[y0:y1, x0:x1] - cx) ** 2 + (yy[y0:y1, x0:x1] - cy) ** 2 <= r * r
    return m


def main():
    a4, a2 = naip2023()
    with rasterio.open(cache('chm.tif')) as s:
        chm = s.read(1).astype(np.float32)
    k = int(round(1 / RES))
    ch = np.kron(chm, np.ones((k, k), np.float32))
    H, W = ch.shape
    tr = from_origin(E0, N1, RES, RES)
    F = osm.load()
    bld = rfeat.rasterize([(f['poly'].buffer(1.5), 1) for f in F['building']], out_shape=(H, W), transform=tr, dtype='uint8').astype(bool)

    P, br = canopy_prob(a2, ch)
    Ps = ndi.gaussian_filter(P, 1.5)
    dark = ndi.gaussian_filter(br, 1) < 85
    can = ndi.binary_opening((Ps > .6) & ~bld & ~(shadows(ch) & dark), iterations=2)
    rgb = a2[:3].transpose(1, 2, 0)
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    vis = np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).mean(2)
    bare = ndi.binary_dilation(ndi.gaussian_filter(vis, 1) > 150, iterations=2)   # roofs, bins, gravel, roads: never leaves
    crown = (can | ((ch >= 2) & ndi.binary_dilation(can, iterations=3))) & ~bld & ~bare

    trees = json.load(open(os.path.join(OUT, 'trees.json')))
    trp = os.path.join(OUT, 'trees_removed.json')
    if os.path.exists(trp):
        clear = unary_union([shape(g) for g in json.load(open(trp))])
        trees = [t for t in trees if not clear.contains(Point(t['e'], t['n']))]
    # drop: a lidar tree standing on a roof or bare gravel in 2023 (a building OSM lacks, or one put up since 2019)
    drop = []
    for t in trees:
        c, r = int((t['e'] - E0) / RES), int((N1 - t['n']) / RES)
        rr = max(1, int(t['d'] / 2 / RES * .6))
        win = (slice(max(0, r - rr), r + rr + 1), slice(max(0, c - rr), c + rr + 1))
        if vis[win].mean() > 170:
            drop.append(t)
    # gone: on a course whose lidar is much older than the aerial (course.TREES_GONE: Stonehenge, 2007 lidar, 2023 aerial), a lidar tree
    # with no leaf canopy over its crown on the aerial was felled since
    gone = 0
    if getattr(course, 'TREES_GONE', False):
        for t in trees:
            c, r = int((t['e'] - E0) / RES), int((N1 - t['n']) / RES)
            rr = max(3, int(t['d'] / 2 / RES * .6))
            win = (slice(max(0, r - rr), r + rr + 1), slice(max(0, c - rr), c + rr + 1))
            if Ps[win].size and Ps[win].mean() < GONE_P and t not in drop:
                drop.append(t)
                gone += 1
    # and any lidar tree standing in a painted shed (the range's metal shed, the pump house): the lidar saw them as canopy
    sheds = []
    for f in ('range.json', 'paint_props.json'):
        fp = os.path.join(OUT, f)
        if os.path.exists(fp):
            j = json.load(open(fp))
            sheds += [r for r in ([j['shed']] if isinstance(j, dict) and j.get('shed') else j if isinstance(j, list) else []) if r and r[0] == 'shed']
    for _, e, nn, ang, w, dep, _ in sheds:
        u = (np.sin(np.radians(ang)), -np.cos(np.radians(ang)))   # along the shed's length (paint_read.sheds)
        for t in trees:
            dx, dy = t['e'] - e, t['n'] - nn
            if abs(dx * u[0] + dy * u[1]) <= w / 2 + 1 and abs(-dx * u[1] + dy * u[0]) <= dep / 2 + 1 and t not in drop:
                drop.append(t)
    dk = {(t['e'], t['n']) for t in drop}
    trees = [t for t in trees if (t['e'], t['n']) not in dk]
    pp = os.path.join(OUT, 'trees_painted.json')   # none on a course whose trees were never painted (Stonehenge)
    painted = json.load(open(pp)) if os.path.exists(pp) else []
    allt = trees + painted
    ispainted = [False] * len(trees) + [True] * len(painted)

    # grow: each crown pixel belongs to the nearest tree; the crown ends at the first ring that is no longer mostly canopy
    ys, xs = np.nonzero(crown)
    pe, pn = E0 + (xs + .5) * RES, N1 - (ys + .5) * RES
    kd = cKDTree([(t['e'], t['n']) for t in allt])
    dist, own = kd.query(np.c_[pe, pn])
    grow = []
    for i, t in enumerate(allt):
        sel = (own == i) & (dist < D_MAX / 2 + 1) & (pe >= t['e'])   # the east half only: the shadows all fall west
        if not sel.any():
            continue
        rings = np.bincount((dist[sel] / RES).astype(int), minlength=int(D_MAX / 2 / RES) + 2)
        full = np.pi * (np.arange(len(rings)) + .5)   # pixels in half a ring of that radius
        share = rings / full
        r = 0
        for j in range(len(share)):
            if share[j] >= RING_FULL or (j + 1 < len(share) and share[j + 1] >= RING_FULL and j * RES < t['d'] / 2):
                r = j + 1
            else:
                break
        d = 2 * r * RES
        cap = 4.5 if t['kind'] == 1 else D_MAX
        nd = round(float(min(d, t['d'] * (CONIFER_MAX if t['kind'] == 2 else GROW_MAX), cap)), 1)
        if nd >= t['d'] * GROW_MIN and nd - t['d'] >= 1:
            h = height(t['kind'], nd) if ispainted[i] else t['h']
            grow.append(dict(e=t['e'], n=t['n'], d=nd, h=round(max(h, t['h']), 1), was=t['d']))
    # the practice green and the driving range have their own painted trees (practice_read.py, range_read.py): leave them be
    keep_out = []
    for f, k in (('practice.json', 'green'), ('range.json', 'boundary')):
        if os.path.exists(os.path.join(OUT, f)):
            g = json.load(open(os.path.join(OUT, f)))[k]
            keep_out += [shape(x) for x in (g if isinstance(g, list) else [g])]
    keep_out = unary_union(keep_out).buffer(8) if keep_out else None
    outside = lambda t: keep_out is None or not keep_out.contains(Point(t['e'], t['n']))
    grow = [g for g in grow if outside(g)]
    gd = {(g['e'], g['n']): g for g in grow}
    now = [dict(t, d=gd[(t['e'], t['n'])]['d']) if (t['e'], t['n']) in gd else t for t in allt]

    # add: canopy still bare of trees
    miss = ndi.binary_opening(crown & ~disks(now, (H, W), grow=1.), iterations=2)
    lab, n = ndi.label(miss)
    idx = np.arange(1, n + 1)
    area = ndi.sum(miss, lab, idx) * RES ** 2
    lidar = ndi.mean(ch >= 2, lab, idx)
    sure = ndi.mean(Ps, lab, idx)
    tall = ndi.maximum(ch, lab, idx)
    ok = (area >= 6) & ((lidar > .5) | (sure > .75))
    shrub = np.isin(lab, idx[ok & (tall < 4) & ((lidar > .5) | (area < 25))])
    tree = np.isin(lab, idx[ok]) & ~shrub
    fr = dict(res=RES, e0=E0, n1=N1)
    add = [t for t in from_masks({0: tree, 1: shrub}, fr, now) if outside(t)]
    for t in add:   # the lidar height where it has one (trees grown or planted since 2019 keep the painted rule)
        c, r = int((t['e'] - E0) / RES), int((N1 - t['n']) / RES)
        rr = max(1, int(t['d'] / 2 / RES))
        hl = float(ch[max(0, r - rr):r + rr + 1, max(0, c - rr):c + rr + 1].max())
        if hl >= 2 and (t['kind'] != 1 or hl < 4):
            t['h'] = round(hl, 1)
        if t['kind'] == 0 and hl < 4 and t['d'] < 4:
            t['kind'], t['h'] = 1, height(1, min(t['d'], 4.5))
            t['d'] = min(t['d'], 4.5)
    json.dump(dict(drop=[{'e': t['e'], 'n': t['n']} for t in drop], grow=[{k2: g[k2] for k2 in 'endh'} for g in grow], add=add), open(os.path.join(OUT, 'trees_aerial.json'), 'w'))

    # the picture to check it on (0.5 m per pixel)
    img = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    px = lambda e, nn: ((e - E0) / RES, (N1 - nn) / RES)
    for t, c in [(t, (255, 0, 0)) for t in drop] + [(t, (255, 235, 60)) for t in allt] + [(g, (0, 255, 255)) for g in grow] + [(t, (255, 0, 255)) for t in add]:
        x, y = px(t['e'], t['n'])
        r = t['d'] / 2 / RES
        d.ellipse([x - r, y - r, x + r, y + r], outline=c, width=1)
    img.save(os.path.join(OUT, 'trees_aerial.png'))
    ks = np.bincount([t['kind'] for t in add], minlength=3)
    print(f'{len(drop) - gone} lidar trees on roofs or gravel dropped, {gone} felled since the lidar; {len(grow)} crowns grown ({sum(g["d"] - g["was"] for g in grow) / max(1, len(grow)):.1f} m wider on average, '
          f'{sum(ispainted[i] for i, t in enumerate(allt) if (t["e"], t["n"]) in gd)} of them painted); '
          f'{len(add)} trees added: {ks[0]} broadleaf, {ks[2]} conifer, {ks[1]} shrubs')


if __name__ == '__main__':
    main()
