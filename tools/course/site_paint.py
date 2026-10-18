"""Site props from the hand-painted out/site_mask.png (made from out/site_edit.png, same pixels; colours in site_edit.py):
cyan = double washroom, blue = its door side (optional), orange = porta-potty, yellow = signpost. Writes out/site_props.json
(rows [kind, e, n, front-facing direction in degrees (east = 0, counter-clockwise), width m, depth m, text]); build.py puts it
in the course data and the game draws the buildings and signs.

Sign text: out/signs.txt, one line per hole number, '|' for a line break:
    7: WATCH FOR GOLFERS | ON THE 8TH TEE
    1: PLEASE REPAIR DIVOTS
Only holes with a line in signs.txt get their sign: a yellow dot whose nearest hole has no line is left out (and listed when this
runs). Rerun site_paint.py, build.py, install.py after repainting or editing signs.txt."""
import json
import math
import os

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import Point, shape

import osm
from common import OUT

COLS = {'wash': (0, 255, 255), 'door': (0, 0, 255), 'potty': (255, 128, 0), 'sign': (255, 255, 0)}
LEGEND = (60, 60, 60 + 470, 60 + 34 * 4 + 16)   # the colour key printed on the map is ignored
POTTY = 1.25


def blobs(a, rgb, fr, tr, min_area):
    m = (np.abs(a - np.array(rgb)).max(2) <= 40)
    m = ndi.binary_closing(m, iterations=1)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s * fr['res'] ** 2 >= min_area])
    return [shape(g).buffer(0) for g, v in features.shapes(m.astype(np.uint8), mask=m, transform=tr) if v]


def deg(dx, dy):
    return math.degrees(math.atan2(dy, dx)) % 360


def main():
    fr = json.load(open(os.path.join(OUT, 'fescue_base.json')))
    a = np.array(Image.open(os.path.join(OUT, 'site_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    a[LEGEND[1]:LEGEND[3], LEGEND[0]:LEGEND[2]] = 0
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    F = osm.load()
    tees = [f['poly'].centroid for f in F['tee']]
    nearest_tee = lambda p: min(tees, key=lambda t: t.distance(p))
    sp = os.path.join(OUT, 'signs.txt')
    custom = {}
    for ln in open(sp).read().splitlines() if os.path.exists(sp) else []:
        if ':' in ln and ln.split(':', 1)[0].strip().isdigit():
            custom[int(ln.split(':', 1)[0])] = ln.split(':', 1)[1].strip().replace('|', '\n').replace(' \n', '\n').replace('\n ', '\n')
    rd_ = lambda n: json.load(open(os.path.join(OUT, n))) if os.path.exists(os.path.join(OUT, n)) else {}
    spos, tmarks = rd_('sign_pos.json'), rd_('tee_marks.json')
    out = []
    doors = blobs(a, COLS['door'], fr, tr, 1.0)
    for p in blobs(a, COLS['wash'], fr, tr, 6.0):
        r = p.minimum_rotated_rectangle
        c = list(r.exterior.coords)[:4]
        e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1]); e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
        L1, L2 = math.hypot(*e1), math.hypot(*e2)
        long_, short_ = (e1, e2) if L1 >= L2 else (e2, e1)
        w, d = max(L1, L2), min(L1, L2)
        cen = r.centroid
        n1 = (-long_[1], long_[0]); nl = math.hypot(*n1); n1 = (n1[0] / nl, n1[1] / nl)       # the two normals of the long side
        strip = [q for q in doors if q.distance(r) < 2.5]
        tgt = strip[0].centroid if strip else nearest_tee(cen)
        sgn = 1 if ((tgt.x - cen.x) * n1[0] + (tgt.y - cen.y) * n1[1]) >= 0 else -1
        out.append(['wash', round(cen.x, 1), round(cen.y, 1), round(deg(sgn * n1[0], sgn * n1[1])), round(float(np.clip(w, 3, 12)), 1), round(float(np.clip(d, 2, 6)), 1), ''])
    for p in blobs(a, COLS['potty'], fr, tr, 1.0):
        t = nearest_tee(p.centroid)
        out.append(['potty', round(p.centroid.x, 1), round(p.centroid.y, 1), round(deg(t.x - p.centroid.x, t.y - p.centroid.y)), POTTY, POTTY, ''])
    holes = F['hole']
    skipped = []
    for p in blobs(a, COLS['sign'], fr, tr, 1.0):
        q = p.centroid
        h = min(holes, key=lambda hh: Point(hh['line'].coords[0]).distance(q))
        t = nearest_tee(q)
        text = custom.get(h['ref'])
        if not text:  # no message for this hole: no sign
            skipped.append((h['ref'], round(q.x), round(q.y)))
            continue
        if str(h['ref']) in spos:   # placed on a hole close-up (hole_zoom_paint.py): that spot, facing the played tee
            q = Point(*spos[str(h['ref'])])
            if str(h['ref']) in tmarks:
                t = Point(*tmarks[str(h['ref'])]['mid'])
        out.append(['sign', round(q.x, 1), round(q.y, 1), round(deg(t.x - q.x, t.y - q.y)), 1.5, .1, text, h['ref']])   # the 8th value is the hole it belongs to (the fly-over reads the sign)
    json.dump(out, open(os.path.join(OUT, 'site_props.json'), 'w'))
    for ref, e, n in skipped:
        print(f'  sign dot near hole {ref} (e {e}, n {n}) skipped: no line for hole {ref} in signs.txt')
    k = {x: sum(1 for r in out if r[0] == x) for x in ('wash', 'potty', 'sign')}
    print(len(out), 'props:', k)
    for r in out:
        print('  ', r[0], 'e', r[1], 'n', r[2], 'faces', r[3], 'deg', ('size %.1f x %.1f' % (r[4], r[5])) if r[0] == 'wash' else '', repr(r[6]) if r[6] else '')


if __name__ == '__main__':
    main()
