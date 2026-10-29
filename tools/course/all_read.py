"""Read out/all_mask.png (painted on all_start.png from all_edit.py; colours in all_edit.PALETTE) into every layer file at once, with the
separate readers' own outline smoothing:

  boundary.json  fescue.json  fairways_painted.json  greens_painted.json  tees_painted.json  tee_starts.json  bunkers_painted.json
  water_painted.json  creek_painted.json  cartpaths.json (+ cartpaths_links.json)  trees_painted.json  trees_removed.json
  buildings_painted.json  site_props.json

The map is the whole truth for what it covers: a layer with no paint on it is written empty (no fescue painted: no fescue), except the
boundary, which stays the OSM outline when there is no cyan. A line or dot painted over an area leaves the area whole underneath: its
pixels take the area of the nearest pixel that is not a line or dot. Then run build.py and install.py.
"""
import json
import os

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
from all_edit import PALETTE, SURFACES
from common import OUT

TOL = 40   # a pixel is a palette colour when every channel is within this of it


def main():
    fr = json.load(open(os.path.join(OUT, 'all_edit.json')))
    a = np.array(Image.open(os.path.join(OUT, 'all_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], f"the mask must be the map's size, {fr['w']} x {fr['h']} px (not resized or cropped)"
    M = {k: np.abs(a - np.array(c)).max(2) <= TOL for k, (c, _, _) in PALETTE.items()}
    print('painted (m2):', {k: int(m.sum() * fr['res'] ** 2) for k, m in M.items() if m.any()})
    # the ground: each surface's own pixels, and every line / dot pixel given to the area nearest to it (0 = rough)
    lab = np.zeros(a.shape[:2], np.int8)
    for i, k in enumerate(SURFACES, 1):
        lab[M[k]] = i
    over = np.zeros(a.shape[:2], bool)
    for k in PALETTE:
        if k not in SURFACES:
            over |= M[k]
    idx = ndi.distance_transform_edt(over, return_distances=False, return_indices=True)
    lab = lab[idx[0], idx[1]]
    S = {k: lab == i for i, k in enumerate(SURFACES, 1)}
    put = lambda name, geoms: json.dump([mapping(g) for g in geoms], open(os.path.join(OUT, name), 'w'))
    rep = {}

    if M['boundary'].any():
        p, n = boundary.from_mask(M['boundary'], fr)
        json.dump(mapping(p), open(os.path.join(OUT, 'boundary.json'), 'w'))
        rep['boundary'] = f'{p.area / 1e4:.1f} ha ({n} cyan pieces; the largest closed one is the course)'
    else:
        rep['boundary'] = 'no cyan: the OSM outline'
    fe = fescue.from_mask(S['fescue'], fr)
    put('fescue.json', fe)
    rep['fescue'] = f'{len(fe)} areas, {sum(p.area for p in fe) / 1e4:.2f} ha'
    fw = fairways.from_mask(S['fairway'], fr)
    put('fairways_painted.json', fw)
    rep['fairways'] = f'{len(fw)} areas, {sum(p.area for p in fw) / 1e4:.2f} ha'
    gr = fairways.from_mask(S['green'], fr, min_area=30.0, smooth=1.5, tol=.08)
    put('greens_painted.json', gr)
    rep['greens'] = f'{len(gr)} greens, {round(sum(p.area for p in gr))} m2'
    po = fairways.from_mask(S['pond'], fr, min_area=20.0, smooth=1.5, tol=.1)
    put('water_painted.json', po)
    rep['ponds'] = f'{len(po)} ponds, {round(sum(p.area for p in po))} m2'
    bk = bunkers_paint.from_mask(S['bunker'], fr)
    put('bunkers_painted.json', bk)
    rep['bunkers'] = f'{len(bk)} bunkers, {round(sum(p.area for p in bk))} m2'
    tees = paint_read.blob_polys(ndi.binary_closing(S['tee'], iterations=2), fr, paint_read.MIN_TEE, True, True)
    put('tees_painted.json', tees)
    starts = [[round(p.centroid.x, 2), round(p.centroid.y, 2)] for p in paint_read.blob_polys(ndi.binary_closing(M['tee_dot'], iterations=2), fr, .2, False)]
    json.dump(starts, open(os.path.join(OUT, 'tee_starts.json'), 'w'))
    rep['tees'] = f'{len(tees)} tee boxes, {len(starts)} played-tee dots'
    if M['creek'].any():
        cr, pieces = creek_paint.from_mask(M['creek'], fr)
        rep['creek'] = f'{len(cr)} stretches in {len(pieces)} pieces, {round(sum(p.area for p in cr))} m2'
    else:
        pieces = []
        rep['creek'] = 'none'
    put('creek_painted.json', pieces)
    print('cart paths:')
    cartpaths_read.write_network(skeletonize(ndi.binary_closing(M['path'], iterations=1)), fr)

    # trees: clearings take out the lidar trees in them; painted ones are added (a grove kept off the lidar trees that are left)
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    clear = [shape(g).buffer(0) for g, v in features.shapes(M['clear'].astype(np.uint8), mask=M['clear'], transform=tr) if v]
    clear = [p for p in clear if p.area >= 4]
    put('trees_removed.json', clear)
    lidar = json.load(open(os.path.join(OUT, 'trees.json'))) if os.path.exists(os.path.join(OUT, 'trees.json')) else []
    cu = unary_union(clear) if clear else None
    left = [t for t in lidar if cu is None or not cu.contains(Point(t['e'], t['n']))]
    added = trees_paint.from_masks({0: M['broad'], 2: M['conifer'], 1: M['shrub']}, fr, left)
    json.dump(added, open(os.path.join(OUT, 'trees_painted.json'), 'w'))
    rep['trees'] = f'{len(lidar) - len(left)} lidar trees cleared ({sum(p.area for p in clear) / 1e4:.2f} ha), {len(added)} added'

    # buildings: a near-rectangle is squared up, anything else (an L-shaped house) keeps its painted outline, straightened
    bl = []
    for g, v in features.shapes(ndi.binary_opening(M['building'], iterations=1).astype(np.uint8), mask=M['building'], transform=tr):
        p = shape(g).buffer(0)
        if v and p.area >= 8:
            r = p.minimum_rotated_rectangle
            bl.append(r if p.area > .85 * r.area else p.simplify(.6))
    put('buildings_painted.json', bl)
    rep['buildings'] = f'{len(bl)} buildings'
    F = osm.load()
    rows = site_paint.rows_from({'wash': M['wash'], 'door': np.zeros_like(M['wash']), 'potty': M['potty'], 'sign': M['sign'], 'lot': M['lot']}, fr, F)
    rows += paint_read.sheds(ndi.binary_closing(M['shed'], iterations=2), fr)
    json.dump(rows, open(os.path.join(OUT, 'site_props.json'), 'w'))
    rep['props'] = {x: sum(1 for r in rows if r[0] == x) for x in ('wash', 'potty', 'sign', 'shed', 'lot', 'car') if any(r[0] == x for r in rows)} or 'none'
    for k, v in rep.items():
        print(f'  {k:10s} {v}')
    print('next: build.py, install.py')


if __name__ == '__main__':
    main()
