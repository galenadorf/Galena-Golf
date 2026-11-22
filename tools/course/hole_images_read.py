#!/usr/bin/env python3
"""Read the paint a user added to the per-hole pictures made by hole_images.py (run with ~/.venvs/galena/bin/python).

  python3 hole_images_read.py <course> --baseline <dir> [--share "/mnt/k/- Share/hole_images"] [--holes 18,17,...,1] [--forest] [--write]

<baseline> holds the pictures as hole_images.py drew them (<dir>/<course>/hole_NN.png, same code and settings: re-render them first with
`hole_images.py <course> --out <dir>` BEFORE changing hole_images.py). Only pixels that differ from the baseline count as paint, so
everything the picture itself draws is ignored. Colours (the palette in hole_images.py's legend):
  magenta  #FF00FF  an X over a tree: that tree is removed (trees_x.py's matching: the ring holding the X's middle)    -> trees_x_removed.json
  green    #008000 / #008080 / #000080  a filled circle: a broadleaf / conifer / shrub is added (trees_x.py's sizing)  -> trees_x_added.json
  fescue   big filled #FF00FF or #008000 areas (not thin X's, not small circles) = deep rough -> fescue.json (replaced on each read: the pictures hold it all)
  --forest: big filled #008000 areas (600 m2+) are FOREST, not deep rough (Stonehenge, 2026-11-22: only magenta is deep rough there)
                                                                     -> forest_painted.json (build.py plants it with trees)
  orange   #FF8000  filled areas = a bunker OSM lacks                -> bunkers_added.json (build.py adds them)
  lime     #00FF00  filled areas = fairway painted by hand           -> fairways_added.json (build.py adds them after FAIRWAY_DROP)
  cyan     #00FFFF  a line = out-of-bounds stakes for THAT picture's hole: the side away from the hole is out of bounds while it is played
                                                                     -> ob_lines.json [{hole, line}] (build.py puts them in the hole data as `obl`)
Deep rough, forest, bunkers, fairways and OB lines are MERGED with what is on file (the baseline pictures already draw what was read before,
so only new paint shows as a difference); --replace makes deep rough, forest and bunkers replace the files instead (as before 2026-11-22).
  white    #FFFFFF  deep rough removed, the ground becomes REGULAR rough (the game ignores white over anything that is not deep rough)
                                                                                                                      -> rough_painted.json
Holes are read in the order --holes gives (default 1..18); where two pictures add the same tree, the one read LAST wins, so give
the holes in reverse (18 first) when the earlier holes carry the user's final word. Results are merged into what the course's out/ already has (nothing is dropped), so rerunning is safe. Without --write it only reports.
Then run build.py and install.py for the course.
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from shapely.geometry import LineString, mapping, shape
from scipy import ndimage as ndi
from shapely.ops import unary_union

Image.MAX_IMAGE_PIXELS = None


def main():
    a = sys.argv[1:]
    opt = {}
    for k in ('--baseline', '--share', '--holes'):
        if k in a:
            i = a.index(k); opt[k] = a[i + 1]; del a[i:i + 2]
    write = '--write' in a
    forest_mode = '--forest' in a
    replace = '--replace' in a
    a = [x for x in a if x not in ('--write', '--forest', '--replace')]
    key = a[0]
    os.environ['GALENA_COURSE'] = key
    sys.argv = [sys.argv[0], '--course', key]
    import trees_x
    from fence_read import lines_from_mask   # (only after the course is set: it imports common.py)
    from common import OUT
    share = opt.get('--share', '/mnt/k/- Share/hole_images')
    base = opt['--baseline']
    info = json.load(open(os.path.join(share, key, '_frames_and_objects.json')))
    holes = [int(x) for x in opt['--holes'].split(',')] if '--holes' in opt else sorted(int(k) for k in info)
    removed, added, rough, fesc, notes = [], [], [], [], []
    forest, bunk, fair, oblines = [], [], [], []
    tmp = os.path.join(OUT, '_hole_paint.png')
    for hn in holes:
        fr = info[str(hn)]['frame']
        fp = os.path.join(share, key, fr['file']); bp = os.path.join(base, key, fr['file'])
        im = np.asarray(Image.open(fp).convert('RGB')).astype(int); bm = np.asarray(Image.open(bp).convert('RGB')).astype(int)
        if im.shape != bm.shape:
            notes.append(f'hole {hn}: picture size changed ({im.shape} vs {bm.shape}): skipped, never resize or crop')
            continue
        W, H = fr['map_size_px']; oy = fr['map_origin_px'][1]; s = fr['px_per_m']; e0, n1 = fr['top_left_enu']
        ch = (np.abs(im - bm).sum(2) > 0)[oy:oy + H, :W]
        a_ = im[oy:oy + H, :W]
        if not ch.any():
            continue
        # white: deep rough removed
        wmask = ch & (a_.min(axis=2) >= 235)
        # magenta X marks and tree circles: the painted pixels only, on black, in the map's own frame
        # deep rough: big FILLED areas of magenta #FF00FF or dark green #008000 (the user used both). A tree X is a thin stroke and an
        # add-circle a small disc, so: open the mask by 1.5 m (strokes and specks vanish), keep a magenta piece of 20 m2+ and a green
        # piece of 150 m2+ (a crown is under 120 m2); what is left is read as trees below
        fesc_px = np.zeros((H, W), bool)
        for_px = np.zeros((H, W), bool)
        bunk_px = ch & (np.abs(a_ - np.array((255, 128, 0))).sum(2) <= 40)
        if bunk_px.sum() >= 30:
            tr = Affine(1 / s, 0, e0, 0, -1 / s, n1)
            polys = [shape(g) for g, v in features.shapes(bunk_px.astype(np.uint8), mask=bunk_px, transform=tr) if v]
            u = unary_union(polys).buffer(.5).buffer(-.5).simplify(.2)
            parts = [g for g in getattr(u, 'geoms', [u]) if g.geom_type == 'Polygon' and g.area >= 4]
            bunk += parts
            notes.append(f'hole {hn}: bunker painted -> {len(parts)} area(s), {sum(g.area for g in parts):.0f} m2')
        else:
            bunk_px[:] = False
        fair_px = ch & (np.abs(a_ - np.array((0, 255, 0))).sum(2) <= 60)
        if fair_px.sum() / s / s >= 20:
            tr = Affine(1 / s, 0, e0, 0, -1 / s, n1)
            polys = [shape(g) for g, v in features.shapes(fair_px.astype(np.uint8), mask=fair_px, transform=tr) if v]
            u = unary_union(polys).buffer(1.0).buffer(-1.0).simplify(.3)
            parts = [g for g in getattr(u, 'geoms', [u]) if g.geom_type == 'Polygon' and g.area >= 20]
            fair += parts
            notes.append(f'hole {hn}: fairway painted -> {len(parts)} area(s), {sum(g.area for g in parts):.0f} m2')
        else:
            fair_px[:] = False
        ob_px = ch & (np.abs(a_ - np.array((0, 255, 255))).sum(2) <= 60)
        if ob_px.sum() >= 30:
            ls_ = lines_from_mask(ob_px, dict(res=1 / s, e0=e0, n1=n1))
            for ln in ls_:
                oblines.append(dict(hole=hn, line=[[round(x, 2), round(y, 2)] for x, y in ln.simplify(.3).coords]))
            notes.append(f'hole {hn}: OB line -> {len(ls_)} line(s), {sum(g.length for g in ls_):.0f} m')
        else:
            ob_px[:] = False
        for col, amin in (((255, 0, 255), 20), ((0, 128, 0), 150)):
            k = ch & (np.abs(a_ - np.array(col)).sum(2) <= 30)
            if k.sum() < 50:
                continue
            core = ndi.distance_transform_edt(k) >= 1.5 * s
            body = ndi.binary_dilation(core, iterations=int(1.5 * s) + 1) & k
            lab, nl = ndi.label(body)
            tgt = for_px if (forest_mode and col == (0, 128, 0)) else fesc_px
            for i in range(1, nl + 1):
                A = (lab == i).sum() / s / s
                if A >= (600 if tgt is for_px else amin):   # forest: 600 m2 and up; smaller green blobs are tree circles (alone or touching), left to the tree reader
                    tgt |= (lab == i)
        if for_px.sum():
            tr = Affine(1 / s, 0, e0, 0, -1 / s, n1)
            polys = [shape(g) for g, v in features.shapes(for_px.astype(np.uint8), mask=for_px, transform=tr) if v]
            u = unary_union(polys).buffer(1.0).buffer(-2.0).buffer(1.0).simplify(.4)
            parts = [g for g in getattr(u, 'geoms', [u]) if g.geom_type == 'Polygon' and g.area >= 20]
            forest += parts
            notes.append(f'hole {hn}: forest painted -> {len(parts)} area(s), {sum(g.area for g in parts):.0f} m2')
        if fesc_px.sum():
            tr = Affine(1 / s, 0, e0, 0, -1 / s, n1)
            polys = [shape(g) for g, v in features.shapes(fesc_px.astype(np.uint8), mask=fesc_px, transform=tr) if v]
            u = unary_union(polys).buffer(1.0).buffer(-2.0).buffer(1.0).simplify(.4)
            parts = [g for g in getattr(u, 'geoms', [u]) if g.geom_type == 'Polygon' and g.area >= 20]
            fesc += parts
            notes.append(f'hole {hn}: deep rough painted -> {len(parts)} area(s), {sum(g.area for g in parts):.0f} m2')
        # the area paint and its ragged rim (a few px) are never tree marks; a tree circle drawn against it still is (before 2026-11-22 the
        # whole connected piece was dropped, which lost circles painted touching a bunker, deep rough or forest)
        keep = ch & ~ndi.binary_dilation(fesc_px | for_px | bunk_px | fair_px | ob_px, iterations=3)
        lk, nk = ndi.label(ndi.binary_dilation(keep, iterations=2))   # a speck of under 30 px is a stray dab, not an X or a circle
        for i in range(1, nk + 1):
            if (keep & (lk == i)).sum() < 30:
                keep &= lk != i
        paint = np.zeros((H, W, 3), np.uint8)
        paint[keep] = a_[keep]
        paint[wmask] = 0
        Image.fromarray(paint).save(tmp)
        trees_x.frame = lambda e0=e0, n1=n1, s=s: dict(ppm=s, e0=e0, n1=n1)
        rm, ad, nt, _ = trees_x.read(tmp, write=False, one_round=True)
        removed += rm; added += ad
        notes += [f'hole {hn}: {x}' for x in nt]
        if wmask.sum() >= 50:
            tr = Affine(1 / s, 0, e0, 0, -1 / s, n1)
            polys = [shape(g) for g, v in features.shapes(wmask.astype(np.uint8), mask=wmask, transform=tr) if v]
            u = unary_union(polys).buffer(.8).buffer(-1.6).buffer(.8).simplify(.35)   # sweeps up specks and the pixel staircase
            parts = [g for g in getattr(u, 'geoms', [u]) if g.geom_type == 'Polygon' and g.area >= 6]
            rough += parts
            notes.append(f'hole {hn}: white -> {len(parts)} regular-rough area(s), {sum(g.area for g in parts):.0f} m2 (deep rough removed where it was there)')
    if os.path.exists(tmp):
        os.remove(tmp)
    # merge with what is on file
    rp = os.path.join(OUT, 'trees_x_removed.json'); ap = os.path.join(OUT, 'trees_x_added.json'); gp = os.path.join(OUT, 'rough_painted.json'); fp = os.path.join(OUT, 'fescue.json')
    old_r = json.load(open(rp)) if os.path.exists(rp) else []
    old_a = json.load(open(ap)) if os.path.exists(ap) else []
    old_g = [shape(g) for g in json.load(open(gp))] if os.path.exists(gp) else []
    seen = {(round(t['e'], 2), round(t['n'], 2)) for t in old_r}
    new_r = [t for t in removed if (round(t['e'], 2), round(t['n'], 2)) not in seen and not seen.add((round(t['e'], 2), round(t['n'], 2)))]
    new_a = []
    for t in added:   # a tree added twice (two pictures show the same circle) is one tree: the picture read last wins
        if any(np.hypot(t['e'] - u['e'], t['n'] - u['n']) < 1.5 for u in old_a):
            continue
        new_a = [u for u in new_a if np.hypot(t['e'] - u['e'], t['n'] - u['n']) >= 1.5] + [t]
    def merged(L):
        u = unary_union(L).buffer(.01).buffer(-.01) if L else None
        return [g for g in getattr(u, 'geoms', [u]) if u is not None and g.geom_type == 'Polygon' and not g.is_empty]
    def old_polys(name):
        q = os.path.join(OUT, name)
        return [shape(g) for g in json.load(open(q))] if os.path.exists(q) and not replace else []
    fparts = []
    if fesc or rough:   # new deep rough joins what is on file; white painted this time takes deep rough away
        fparts = merged(old_polys('fescue.json') + fesc)
        if rough:
            wu = unary_union(rough)
            fparts = merged([g.difference(wu) for g in fparts])
    foparts = merged(old_polys('forest_painted.json') + forest) if forest else []
    buparts = merged(old_polys('bunkers_added.json') + bunk) if bunk else []
    fwp = os.path.join(OUT, 'fairways_added.json')
    faparts = merged([shape(g) for g in json.load(open(fwp))] + fair if os.path.exists(fwp) else fair) if fair else []
    obp = os.path.join(OUT, 'ob_lines.json')
    old_ob = json.load(open(obp)) if os.path.exists(obp) else []
    for o in oblines:   # the same line read off two pictures of the same hole is one line
        L = LineString(o['line'])
        if not any(q['hole'] == o['hole'] and LineString(q['line']).hausdorff_distance(L) < 4 for q in old_ob):
            old_ob.append(o)
    allg = unary_union(old_g + rough) if (old_g or rough) else None
    parts = [g for g in getattr(allg, 'geoms', [allg]) if g is not None and g.geom_type == 'Polygon'] if allg is not None else []
    print('\n'.join(notes))
    print(f'{key}: {len(new_r)} new trees removed (on file {len(old_r)}), {len(new_a)} new trees added (on file {len(old_a)}), rough areas on file after merge: {len(parts)}, deep rough areas {len(fparts)} ({sum(g.area for g in fparts):.0f} m2), forest areas {len(foparts)} ({sum(g.area for g in foparts):.0f} m2), bunkers {len(buparts)}, fairways added {len(faparts)} ({sum(g.area for g in faparts):.0f} m2), OB lines {len(old_ob)}')
    if not write:
        print('(report only: nothing written; add --write)')
        return
    json.dump(old_r + new_r, open(rp, 'w')); json.dump(old_a + new_a, open(ap, 'w'))
    if parts:
        json.dump([mapping(g) for g in parts], open(gp, 'w'))
    if fparts:
        json.dump([mapping(g) for g in fparts], open(fp, 'w'))
    if foparts:
        json.dump([mapping(g) for g in foparts], open(os.path.join(OUT, 'forest_painted.json'), 'w'))
    if buparts:
        json.dump([mapping(g) for g in buparts], open(os.path.join(OUT, 'bunkers_added.json'), 'w'))
    if faparts:
        json.dump([mapping(g) for g in faparts], open(fwp, 'w'))
    if oblines:
        json.dump(old_ob, open(obp, 'w'))
    print('written to', OUT, '- now run build.py and install.py for', key)


if __name__ == '__main__':
    main()
