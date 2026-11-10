"""Read out/all_mask.png (painted on all_start.png from all_edit.py; colours in all_edit.PALETTE) into every layer file at once, with the
separate readers' own outline smoothing:

  boundary.json  fescue.json  fairways_painted.json  greens_painted.json  tees_painted.json  tee_starts.json  bunkers_painted.json
  water_painted.json  creek_painted.json  cartpaths.json (+ cartpaths_links.json)  trees_painted.json  trees_removed.json
  buildings_painted.json  site_props.json

Only the layers in course.PAINT are read (all_edit.LAYERS; Eagle Ridge: fairways, greens, tee boxes, bunkers and played-tee dots), and
any other layer file is left as it is. Within those the map is the whole truth, but a layer with no paint on it at all is not written
(its file, or what build.py makes from OSM, stays): the start map comes painted with every layer, so an empty one is a mistake, not a
wish. The boundary likewise stays the OSM outline when there is no cyan. A line or dot painted over an area leaves the area whole
underneath: its pixels take the area of the nearest pixel that is not a line or dot. Then run build.py and install.py.
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union
from skimage.morphology import skeletonize

import boundary
import bunkers_paint
import cartpaths_read
import creek_paint
import fairways
import fescue
import osm
import paint_read
import site_paint
import trees_paint
from all_edit import LAYERS, SURFACES
from common import OUT

TOL = 40   # a pixel is a palette colour when every channel is within this of it


def clumps_from(m, fr, tr):
    """Grass clumps [e, n, scale] from a painted mask: a dot is one clump sized to the dot, a bigger area is filled with clumps about 2 m apart
    (also used by extras_edit.py)."""
    from site_paint import blobs
    out_c = []
    rng = np.random.default_rng(11)
    for p in blobs(m, fr, tr, 1.0):
        if p.area <= 7:
            out_c.append([round(p.centroid.x, 1), round(p.centroid.y, 1), round(float(np.clip(2 * np.sqrt(p.area / np.pi) / 1.5, .7, 1.5)), 2)])
            continue
        inner = p.buffer(-.6) if p.buffer(-.6).area > 1 else p
        x0, y0, x1, y1 = inner.bounds
        for x in np.arange(x0, x1, 2.0):
            for y in np.arange(y0, y1, 2.0):
                q = Point(x + rng.uniform(-.35, .35), y + rng.uniform(-.35, .35))
                if inner.contains(q):
                    out_c.append([round(q.x, 1), round(q.y, 1), round(float(rng.uniform(.85, 1.15)), 2)])
    return out_c


def main():
    fr = json.load(open(os.path.join(OUT, 'all_edit.json')))
    a = np.array(Image.open(os.path.join(OUT, 'all_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], f"the mask must be the map's size, {fr['w']} x {fr['h']} px (not resized or cropped)"
    M = {k: np.abs(a - np.array(c)).max(2) <= TOL for k, (c, _, _) in LAYERS.items()}
    print('painted (m2):', {k: int(m.sum() * fr['res'] ** 2) for k, m in M.items() if m.any()})
    # the ground: each surface's own pixels, and every line / dot pixel given to the area nearest to it (0 = rough)
    lab = np.zeros(a.shape[:2], np.int8)
    for i, k in enumerate(SURFACES, 1):
        if k in M:
            lab[M[k]] = i
    over = np.zeros(a.shape[:2], bool)
    for k in M:
        if k not in SURFACES:
            over |= M[k]
    idx = ndi.distance_transform_edt(over, return_distances=False, return_indices=True)
    lab = lab[idx[0], idx[1]]
    S = {k: lab == i for i, k in enumerate(SURFACES, 1)}   # (all-false for a surface this course does not paint)
    tr0 = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    put = lambda name, geoms: json.dump([mapping(g) for g in geoms], open(os.path.join(OUT, name), 'w'))
    rep = {}

    only = 'tee' if '--tees' in sys.argv else None   # --tees: read the tee layer alone, leave every other file as it is

    def has(k, m=None):   # a layer this course paints, with some paint on it
        if k not in M or (only and k != only):
            return False
        if not (M[k] if m is None else m).any():
            rep[k] = 'nothing painted: left as it is'
            return False
        return True

    if 'boundary' in M and not only:
        if M['boundary'].any():
            p, n = boundary.from_mask(M['boundary'], fr)
            json.dump(mapping(p), open(os.path.join(OUT, 'boundary.json'), 'w'))
            rep['boundary'] = f'{p.area / 1e4:.1f} ha ({n} cyan pieces; the largest closed one is the course)'
        else:
            rep['boundary'] = 'no cyan: the OSM outline'
    if has('fescue', S['fescue']):
        fe = fescue.from_mask(S['fescue'], fr)
        put('fescue.json', fe)
        rep['fescue'] = f'{len(fe)} areas, {sum(p.area for p in fe) / 1e4:.2f} ha'
    if has('fairway', S['fairway']):
        fw = fairways.from_mask(S['fairway'], fr)
        put('fairways_painted.json', fw)
        rep['fairway'] = f'{len(fw)} areas, {sum(p.area for p in fw) / 1e4:.2f} ha'
    if has('green', S['green']):
        gr = fairways.from_mask(S['green'], fr, min_area=30.0, smooth=1.5, tol=.08)
        put('greens_painted.json', gr)
        rep['green'] = f'{len(gr)} greens, {round(sum(p.area for p in gr))} m2'
    if has('pond', S['pond']):
        po = fairways.from_mask(S['pond'], fr, min_area=20.0, smooth=1.5, tol=.1)
        put('water_painted.json', po)
        rep['pond'] = f'{len(po)} ponds, {round(sum(p.area for p in po))} m2'
    if has('bunker', S['bunker']):
        bk = bunkers_paint.from_mask(S['bunker'], fr)
        put('bunkers_painted.json', bk)
        rep['bunker'] = f'{len(bk)} bunkers, {round(sum(p.area for p in bk))} m2'
    if has('tee', S['tee']):
        tm = ndi.binary_closing(S['tee'], iterations=2)
        tees = paint_read.sharp_polys(tm, fr, paint_read.MIN_TEE)   # square corners (every course: build.py squares every tee box too)
        put('tees_painted.json', tees)
        rep['tee'] = f'{len(tees)} tee boxes'
    if only:
        print(rep); return
    if has('fence'):   # hard out-of-bounds lines (a split-rail fence along the property lines where houses line a hole): build.py cuts the boundary back to them
        import fence_read
        fl = fence_read.lines_from_mask(M['fence'], fr)
        json.dump([mapping(g) for g in fl], open(os.path.join(OUT, 'fence_lines.json'), 'w'))
        rep['fence'] = f'{len(fl)} lines, {sum(g.length for g in fl):.0f} m'
    if has('clump'):   # grass clumps: a dot is one clump, a bigger area is filled with them about 2 m apart
        out_c = clumps_from(M['clump'], fr, tr0)
        json.dump(out_c, open(os.path.join(OUT, 'clumps.json'), 'w'))
        rep['clump'] = f'{len(out_c)} clumps'
    if has('drain'):   # rock-lined drainage hazards
        dr = fairways.from_mask(M['drain'], fr, min_area=8.0, smooth=1.0, tol=.1)
        put('drains_painted.json', dr)
        rep['drain'] = f'{len(dr)} drainage hazards, {round(sum(p.area for p in dr))} m2'
    if 'tee_dot' in M:   # optional: no dots means the tee sets are placed by the card yardages alone
        starts = [[round(p.centroid.x, 2), round(p.centroid.y, 2)] for p in paint_read.blob_polys(ndi.binary_closing(M['tee_dot'], iterations=2), fr, .2, False)]
        json.dump(starts, open(os.path.join(OUT, 'tee_starts.json'), 'w'))
        rep['tee_dot'] = f'{len(starts)} played-tee dots'
    if has('creek'):
        cr, pieces = creek_paint.from_mask(M['creek'], fr)
        put('creek_painted.json', pieces)
        rep['creek'] = f'{len(cr)} stretches in {len(pieces)} pieces, {round(sum(p.area for p in cr))} m2'
    if has('path'):
        print('cart paths:')
        cartpaths_read.write_network(skeletonize(ndi.binary_closing(M['path'], iterations=1)), fr)

    # trees: clearings take out the lidar trees in them; painted ones are added (a grove kept off the lidar trees that are left)
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    if any(k in M for k in ('clear', 'broad', 'conifer', 'shrub')):
        none = np.zeros(a.shape[:2], bool)
        mc = M.get('clear', none)
        clear = [shape(g).buffer(0) for g, v in features.shapes(mc.astype(np.uint8), mask=mc, transform=tr) if v]
        clear = [p for p in clear if p.area >= 4]
        put('trees_removed.json', clear)
        lidar = json.load(open(os.path.join(OUT, 'trees.json'))) if os.path.exists(os.path.join(OUT, 'trees.json')) else []
        cu = unary_union(clear) if clear else None
        left = [t for t in lidar if cu is None or not cu.contains(Point(t['e'], t['n']))]
        added = trees_paint.from_masks({0: M.get('broad', none), 2: M.get('conifer', none), 1: M.get('shrub', none)}, fr, left)
        json.dump(added, open(os.path.join(OUT, 'trees_painted.json'), 'w'))
        rep['trees'] = f'{len(lidar) - len(left)} lidar trees cleared ({sum(p.area for p in clear) / 1e4:.2f} ha), {len(added)} added'

    # buildings: a near-rectangle is squared up, anything else (an L-shaped house) keeps its painted outline, straightened
    if has('building'):
        bl = []
        for g, v in features.shapes(ndi.binary_opening(M['building'], iterations=1).astype(np.uint8), mask=M['building'], transform=tr):
            p = shape(g).buffer(0)
            if v and p.area >= 8:
                r = p.minimum_rotated_rectangle
                bl.append(r if p.area > .85 * r.area else p.simplify(.6))
        put('buildings_painted.json', bl)
        rep['building'] = f'{len(bl)} buildings'
    if any(k in M for k in ('wash', 'potty', 'sign', 'lot', 'shed')):
        none = np.zeros(a.shape[:2], bool)
        F = osm.load()
        rows = site_paint.rows_from({'wash': M.get('wash', none), 'door': none, 'potty': M.get('potty', none), 'sign': M.get('sign', none), 'lot': M.get('lot', none)}, fr, F)
        rows += paint_read.sheds(ndi.binary_closing(M.get('shed', none), iterations=2), fr)
        json.dump(rows, open(os.path.join(OUT, 'site_props.json'), 'w'))
        rep['props'] = {x: sum(1 for r in rows if r[0] == x) for x in ('wash', 'potty', 'sign', 'shed', 'lot', 'car') if any(r[0] == x for r in rows)} or 'none'
    print('layers this course paints:', ', '.join(M), '(everything else is left as it is)')
    for k, v in rep.items():
        print(f'  {k:10s} {v}')
    print('next: build.py, install.py')


if __name__ == '__main__':
    main()
