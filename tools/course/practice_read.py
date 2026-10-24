"""The practice green, from the hand-painted out/practice_mask.png (painted over out/practice_edit.png, same pixels; see practice_edit.py):
GREEN #00FF00 the putting surface, CYAN #00FFFF the fringe (the game derives its own 1.5 m collar from the green, so this is only a guide),
MAGENTA #FF00FF deep fescue, ORANGE #FF8000 bunkers, RED #FF0000 the four cups (dots), YELLOW #FFFF00 broadleaf trees (one dot, one tree,
as wide as its crown). Writes out/practice.json (polygons in local metres): green, bunkers, fescue (painted, with the edges that run off
the map carried on past it so they join the course's own fescue), cups, trees. build.py adds them to the course data (merge_fescue).
Every outline is the sub-pixel contour of the blurred mask (smooth_polys), so no painted staircase shows."""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

from common import OUT, smooth_polys

COLS = dict(green=(0, 255, 0), fringe=(0, 255, 255), fescue=(255, 0, 255), bunker=(255, 128, 0), cup=(255, 0, 0), tree=(255, 255, 0))
PAD = 64   # px of edge carried past the map for the fescue (8 m), so it runs on into the course's own fescue
GREEN_SMOOTH, FESCUE_SMOOTH, SAND_SMOOTH = 4.0, 6.0, 4.0   # px of blur (1 px = 12.5 cm)


def main():
    fr = json.load(open(os.path.join(OUT, 'practice_edit.json')))
    a = np.array(Image.open(os.path.join(OUT, 'practice_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    res = 1 / fr['ppm']
    f0 = dict(res=res, e0=fr['e0'], n1=fr['n1'])
    m = {k: (np.abs(a - np.array(c)).max(2) <= 40) for k, c in COLS.items()}
    blobs = lambda k, n=1: [(lab, i) for lab, cnt in [ndi.label(m[k])] for i in range(1, cnt + 1) if (lab == i).sum() >= n]
    # cups: the centre of each red dot
    cups = []
    for lab, i in blobs('cup', 40):
        r, c = ndi.center_of_mass(lab == i)
        cups.append((round(fr['e0'] + (c + .5) * res, 2), round(fr['n1'] - (r + .5) * res, 2)))
    cups.sort(key=lambda p: (-p[1], p[0]))
    # trees: one dot, one tree, as wide as its crown (the dot's own paint stands in for the grass under it)
    trees = []
    tm = ndi.binary_closing(m['tree'], iterations=1)
    lab, cnt = ndi.label(tm)
    ring = ndi.binary_dilation(tm, iterations=4) & ~tm
    fes = ndi.binary_dilation(m['fescue'], iterations=2)
    for i in range(1, cnt + 1):
        b = lab == i
        if b.sum() < 80:
            continue
        r, c = ndi.center_of_mass(b)
        d = float(np.clip(2 * np.sqrt(b.sum() * res * res / np.pi), 2.5, 24))
        trees.append(dict(e=round(fr['e0'] + (c + .5) * res, 1), n=round(fr['n1'] - (r + .5) * res, 1), d=round(d, 1), h=round(min(18, 3 + .8 * d), 1), kind=0))
        rr = ring & ndi.binary_dilation(b, iterations=5)
        if (fes & rr).sum() > .4 * rr.sum():   # a tree standing in the fescue: its dot is fescue too
            m['fescue'] |= b
    # the green takes its cup dots; the fringe paint is only a guide (the game cuts its own collar)
    gm = m['green'] | ndi.binary_dilation(m['cup'], iterations=2)
    gm = ndi.binary_closing(gm, iterations=3)
    gp = smooth_polys(gm, f0, GREEN_SMOOTH, .5, 20, .08)
    assert len(gp) == 1, f'expected one green, found {len(gp)}'
    bp = smooth_polys(m['bunker'], f0, SAND_SMOOTH, .5, 2, .08) if m['bunker'].any() else []
    # the fescue: edge pixels repeated past the map, so an area that runs off its edge keeps going; then the same contour tracing
    fm = ndi.binary_closing(np.pad(m['fescue'], PAD, mode='edge'), iterations=2)
    ff = dict(res=res, e0=fr['e0'] - PAD * res, n1=fr['n1'] + PAD * res)
    fp = smooth_polys(fm, ff, FESCUE_SMOOTH, .5, 8, .15, pad=PAD)
    fp = [p.difference(gp[0].buffer(1.6)) for p in fp]   # the collar belongs to the green
    out = dict(green=mapping(gp[0]), bunkers=[mapping(p) for p in bp], fescue=[mapping(p) for p in fp], cups=cups, trees=trees,
               box=[fr['e0'], fr['n1'] - fr['h'] * res, fr['e0'] + fr['w'] * res, fr['n1']])
    json.dump(out, open(os.path.join(OUT, 'practice.json'), 'w'))
    g = gp[0]
    print(f'green {g.area:.0f} m2 ({g.area * 1.196:.0f} sq yd), {len(g.exterior.coords)} vertices; cups {cups}; fescue {sum(p.area for p in fp) / 10000:.2f} ha; trees {[(t["d"], t["h"]) for t in trees]}; bunkers {len(bp)}')
    for c in cups:
        from shapely.geometry import Point
        print('  cup', c, 'inside green by', round(g.exterior.distance(Point(c)), 1), 'm' if g.contains(Point(c)) else 'm OUTSIDE')


def merge_fescue(fescue, pr):
    """The course's fescue with the practice-green map's painted fescue laid over it: where they meet (the painted area runs off the map)
    they join up; inside the map, the course's fescue within 5 m of the painted one is replaced by it. The joined outline is rounded off (notches under 10 m filled, thin tips under 4 m trimmed)."""
    pf = unary_union([shape(g) for g in pr['fescue']])
    B = box(*pr['box']).buffer(8)
    cut = pf.buffer(5).intersection(B)
    rest = [f.difference(cut) for f in fescue]
    u = unary_union([g for f in rest for g in getattr(f, 'geoms', [f]) if not g.is_empty] + [pf]).buffer(.6, join_style=1).buffer(-.6, join_style=1)   # the two meet at the map's edge: close the hairline between them
    pieces = [u] if u.geom_type == 'Polygon' else list(u.geoms)
    out = []
    for p in pieces:
        if p.intersects(B.buffer(12)):   # round off the joins: close narrow notches, then trim thin tips
            p = p.buffer(5, join_style=1).buffer(-7, join_style=1).buffer(2, join_style=1).simplify(.15)
        out += [g for g in getattr(p, 'geoms', [p]) if g.geom_type == 'Polygon' and g.area > 8]
    return out


if __name__ == '__main__':
    main()
