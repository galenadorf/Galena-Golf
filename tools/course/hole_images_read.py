#!/usr/bin/env python3
"""Read the paint a user added to the per-hole pictures made by hole_images.py (run with ~/.venvs/galena/bin/python).

  python3 hole_images_read.py <course> --baseline <dir> [--share "/mnt/k/- Share/hole_images"] [--holes 1,2] [--write]

<baseline> holds the pictures as hole_images.py drew them (<dir>/<course>/hole_NN.png, same code and settings: re-render them first with
`hole_images.py <course> --out <dir>` BEFORE changing hole_images.py). Only pixels that differ from the baseline count as paint, so
everything the picture itself draws is ignored. Colours (the palette in hole_images.py's legend):
  magenta  #FF00FF  an X over a tree: that tree is removed (trees_x.py's matching: the ring holding the X's middle)    -> trees_x_removed.json
  green    #008000 / #008080 / #000080  a filled circle: a broadleaf / conifer / shrub is added (trees_x.py's sizing)  -> trees_x_added.json
  fescue   big filled #FF00FF or #008000 areas (not thin X's, not small circles) = deep rough -> fescue.json (replaced on each read: the pictures hold it all)
  white    #FFFFFF  deep rough removed, the ground becomes REGULAR rough (the game ignores white over anything that is not deep rough)
                                                                                                                      -> rough_painted.json
Results are merged into what the course's out/ already has (nothing is dropped), so rerunning is safe. Without --write it only reports.
Then run build.py and install.py for the course.
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from shapely.geometry import mapping, shape
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
    a = [x for x in a if x != '--write']
    key = a[0]
    os.environ['GALENA_COURSE'] = key
    sys.argv = [sys.argv[0], '--course', key]
    import trees_x
    from common import OUT
    share = opt.get('--share', '/mnt/k/- Share/hole_images')
    base = opt['--baseline']
    info = json.load(open(os.path.join(share, key, '_frames_and_objects.json')))
    holes = [int(x) for x in opt['--holes'].split(',')] if '--holes' in opt else sorted(int(k) for k in info)
    removed, added, rough, fesc, notes = [], [], [], [], []
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
        for col, amin in (((255, 0, 255), 20), ((0, 128, 0), 150)):
            k = ch & (np.abs(a_ - np.array(col)).sum(2) <= 30)
            if k.sum() < 50:
                continue
            core = ndi.distance_transform_edt(k) >= 1.5 * s
            body = ndi.binary_dilation(core, iterations=int(1.5 * s) + 1) & k
            lab, nl = ndi.label(body)
            for i in range(1, nl + 1):
                if (lab == i).sum() / s / s >= amin:
                    fesc_px |= (lab == i)
        if fesc_px.sum():
            tr = Affine(1 / s, 0, e0, 0, -1 / s, n1)
            polys = [shape(g) for g, v in features.shapes(fesc_px.astype(np.uint8), mask=fesc_px, transform=tr) if v]
            u = unary_union(polys).buffer(1.0).buffer(-2.0).buffer(1.0).simplify(.4)
            parts = [g for g in getattr(u, 'geoms', [u]) if g.geom_type == 'Polygon' and g.area >= 20]
            fesc += parts
            notes.append(f'hole {hn}: deep rough painted -> {len(parts)} area(s), {sum(g.area for g in parts):.0f} m2')
        # whatever paint touches a deep-rough piece (its ragged rim, brush ends) is part of it, never a tree mark
        lab2, n2 = ndi.label(ndi.binary_dilation(ch, iterations=2))
        hit = np.unique(lab2[fesc_px]); hit = hit[hit > 0]
        keep = ch & ~np.isin(lab2, hit)
        lk, nk = ndi.label(ndi.binary_dilation(keep, iterations=2))   # a speck of under 80 px is a stray dab, not an X or a circle
        for i in range(1, nk + 1):
            if (keep & (lk == i)).sum() < 80:
                keep &= lk != i
        paint = np.zeros((H, W, 3), np.uint8)
        paint[keep] = a_[keep]
        paint[wmask] = 0
        Image.fromarray(paint).save(tmp)
        trees_x.frame = lambda e0=e0, n1=n1, s=s: dict(ppm=s, e0=e0, n1=n1)
        rm, ad, nt, _ = trees_x.read(tmp, write=False)
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
    for t in added:   # a tree added twice (two pictures show the same circle) is one tree
        if not any(np.hypot(t['e'] - u['e'], t['n'] - u['n']) < 1.5 for u in old_a + new_a):
            new_a.append(t)
    # painted deep rough REPLACES fescue.json: the pictures show the whole course's deep rough every time they are read
    fall = unary_union(fesc).buffer(.01).buffer(-.01) if fesc else None
    fparts = [g for g in getattr(fall, 'geoms', [fall]) if fall is not None and g.geom_type == 'Polygon' and not g.is_empty]
    allg = unary_union(old_g + rough) if (old_g or rough) else None
    parts = [g for g in getattr(allg, 'geoms', [allg]) if g is not None and g.geom_type == 'Polygon'] if allg is not None else []
    print('\n'.join(notes))
    print(f'{key}: {len(new_r)} new trees removed (on file {len(old_r)}), {len(new_a)} new trees added (on file {len(old_a)}), rough areas on file after merge: {len(parts)}, deep rough areas {len(fparts)} ({sum(g.area for g in fparts):.0f} m2)')
    if not write:
        print('(report only: nothing written; add --write)')
        return
    json.dump(old_r + new_r, open(rp, 'w')); json.dump(old_a + new_a, open(ap, 'w'))
    if parts:
        json.dump([mapping(g) for g in parts], open(gp, 'w'))
    if fparts:
        json.dump([mapping(g) for g in fparts], open(fp, 'w'))
    print('written to', OUT, '- now run build.py and install.py for', key)


if __name__ == '__main__':
    main()
