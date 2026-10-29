"""Site props from the hand-painted out/site_mask.png (made from out/site_edit.png, same pixels; colours in site_edit.py):
cyan = double washroom, blue = its door side (optional), orange = porta-potty, yellow = signpost, violet = the parking lot (stalls are laid out in it, along the nearest
building's long side, and CARS of them are filled: see lot_rows). Writes out/site_props.json
(rows [kind, e, n, front-facing direction in degrees (east = 0, counter-clockwise), width m, depth m, text]); build.py puts it
in the course data and the game draws the buildings and signs.

The big entrance sign ('entry') and the sheds ('shed') are painted on the combined map (paint_edit.py, paint_read.py) and added here from out/paint_props.json.

Sign text: out/signs.txt, one line per hole number, '|' for a line break:
    7: WATCH FOR GOLFERS | ON THE 8TH TEE
    1: PLEASE REPAIR DIVOTS
Only holes with a line in signs.txt get their sign: a yellow dot whose nearest hole has no line is left out (and listed when this
runs). Rerun site_paint.py, build.py, install.py after repainting or editing signs.txt."""
import json
import math
import os

import random

import numpy as np
from PIL import Image
from rasterio import features
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import Point, Polygon, box, shape

import osm
from common import OUT

COLS = {'wash': (0, 255, 255), 'door': (0, 0, 255), 'potty': (255, 128, 0), 'sign': (255, 255, 0), 'lot': (128, 0, 255)}
LEGEND = (60, 60, 60 + 470, 60 + 34 * 5 + 16)   # the colour key printed on the map is ignored
POTTY = 1.25
STALL_W, STALL_D, AISLE = 2.7, 5.5, 7.0     # a parking stall's width and depth, the drive aisle between two double rows (m)
CARS = 8                                    # parked cars in the lot; models: 'car' = the sedan (the Subaru's shape), 'suv' = the Santa Fe's, with a body colour each
CAR_LOOKS = [('car', 0x7b92ac), ('suv', 0x1a1b1e), ('car', 0xb3282d), ('suv', 0xe6e6e2), ('car', 0xc9ccd0), ('suv', 0x3d5a45), ('car', 0x1f2e4a), ('suv', 0x9a8c72)]


def blobs(m, fr, tr, min_area):
    m = ndi.binary_closing(m, iterations=1)
    lab, n = ndi.label(m)
    sizes = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s * fr['res'] ** 2 >= min_area])
    return [shape(g).buffer(0) for g, v in features.shapes(m.astype(np.uint8), mask=m, transform=tr) if v]


def deg(dx, dy):
    return math.degrees(math.atan2(dy, dx)) % 360


def lot_rows(poly, F, seed=8):
    """Rows for one painted lot: ['lot', e, n, 0, 0, 0, '', {poly: outline, lines: stall edges [e1, n1, e2, n2]}] and CARS x ['car', e, n, heading, w, d, '', [model, colour]].
    Stalls run side by side along the nearest building's long side, in back-to-back double rows with a drive aisle between pairs; the grid
    offset that fits the most stalls inside the lot wins. The cars are picked at random (seeded) with a bias toward the building, nose in,
    one in five backed in."""
    poly = Polygon(poly.exterior).simplify(.3)
    near = min(F['building'], key=lambda f: f['poly'].distance(poly))['poly'] if F['building'] else None
    ref = near.minimum_rotated_rectangle if near is not None and near.distance(poly) < 60 else poly.minimum_rotated_rectangle
    c = list(ref.exterior.coords)[:4]
    e1, e2 = (c[1][0] - c[0][0], c[1][1] - c[0][1]), (c[2][0] - c[1][0], c[2][1] - c[1][1])
    ax = e1 if math.hypot(*e1) >= math.hypot(*e2) else e2
    th = math.atan2(ax[1], ax[0]); cu, su = math.cos(th), math.sin(th)
    cen = poly.centroid
    to_xy = lambda u, v: (cen.x + u * cu - v * su, cen.y + u * su + v * cu)         # (u along the rows, v across them) -> (e, n)
    inner = poly.buffer(-.3)
    b = poly.bounds; R = math.hypot(b[2] - b[0], b[3] - b[1]) / 2 + 5
    pitch = AISLE + 2 * STALL_D

    def stalls(uo, vo):
        out = []
        for m in range(-int(R / pitch) - 1, int(R / pitch) + 2):
            for row, (v0, dirn) in enumerate(((vo + m * pitch + AISLE, 1), (vo + m * pitch + AISLE + STALL_D, -1))):   # dirn: the way a nose-in car points (v)
                k = -int(R / STALL_W) - 1
                while k * STALL_W < R + STALL_W:
                    u0 = uo + k * STALL_W; k += 1
                    r = box(u0, v0, u0 + STALL_W, v0 + STALL_D)
                    q = Polygon([to_xy(*p) for p in r.exterior.coords][:-1])
                    if inner.contains(q): out.append((u0, v0, dirn, q))
        return out
    best = max(((len(s), s) for s in (stalls(uo, vo) for uo in (0, .9, 1.8) for vo in range(0, int(pitch), 1))), key=lambda x: x[0])[1]
    if len(best) < CARS: raise SystemExit(f'the painted lot only fits {len(best)} stalls, {CARS} cars need at least that many: paint more of the lot')
    rnd = random.Random(seed)
    wt = [math.exp(-(near.distance(s[3].centroid) if near is not None else 0) / 25) for s in best]
    pick, pool = [], list(range(len(best)))
    for _ in range(CARS):
        i = rnd.choices(pool, [wt[j] for j in pool])[0]; pool.remove(i); pick.append(best[i])
    looks = CAR_LOOKS[:]; rnd.shuffle(looks)
    lines = []
    for u0, v0, dirn, q in best:   # the two sides and the back of each stall (the open end is left open)
        vb = v0 + (STALL_D if dirn > 0 else 0); vo_ = v0 + (0 if dirn > 0 else STALL_D)
        lines += [to_xy(u0, vo_) + to_xy(u0, vb), to_xy(u0 + STALL_W, vo_) + to_xy(u0 + STALL_W, vb), to_xy(u0, vb) + to_xy(u0 + STALL_W, vb)]
    out = [['lot', round(cen.x, 1), round(cen.y, 1), 0, 0, 0, '', {'poly': [[round(x, 1), round(y, 1)] for x, y in poly.exterior.coords][:-1], 'lines': [[round(x, 1) for x in l] for l in lines]}]]
    for (u0, v0, dirn, q), look in zip(pick, looks):
        nose = dirn * (1 if rnd.random() > .2 else -1)
        u = u0 + STALL_W / 2 + rnd.uniform(-.2, .2); v = v0 + STALL_D / 2 + rnd.uniform(-.2, .2)
        hd = math.degrees(th + (math.pi / 2 if nose > 0 else -math.pi / 2)) + rnd.uniform(-3, 3)
        x, y = to_xy(u, v)
        out.append(['car', round(x, 1), round(y, 1), round(hd % 360), 1.8, 4.6, '', [look[0], look[1]]])
    return out


def rows_from(masks, fr, F):
    """Prop rows from boolean masks {'wash', 'door', 'potty', 'sign', 'lot'} on the grid `fr` (also used by all_read.py)."""
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
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
    doors = blobs(masks['door'], fr, tr, 1.0)
    for p in blobs(masks['wash'], fr, tr, 6.0):
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
    for p in blobs(masks['potty'], fr, tr, 1.0):
        t = nearest_tee(p.centroid)
        out.append(['potty', round(p.centroid.x, 1), round(p.centroid.y, 1), round(deg(t.x - p.centroid.x, t.y - p.centroid.y)), POTTY, POTTY, ''])
    holes = F['hole']
    skipped = []
    for p in blobs(masks['sign'], fr, tr, 1.0):
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
    for p in blobs(masks['lot'], fr, tr, 150.0):
        out += lot_rows(p, F)
    for ref, e, n in skipped:
        print(f'  sign dot near hole {ref} (e {e}, n {n}) skipped: no line for hole {ref} in signs.txt')
    return out


def main():
    fr = json.load(open(os.path.join(OUT, 'fescue_base.json')))
    a = np.array(Image.open(os.path.join(OUT, 'site_mask.png')).convert('RGB')).astype(int)
    assert a.shape[1] == fr['w'] and a.shape[0] == fr['h'], 'the mask must have the base map\'s size'
    a[LEGEND[1]:LEGEND[3], LEGEND[0]:LEGEND[2]] = 0
    out = rows_from({k: np.abs(a - np.array(rgb)).max(2) <= 40 for k, rgb in COLS.items()}, fr, osm.load())
    ep = os.path.join(OUT, 'paint_props.json')   # the entrance sign and the shed painted on the combined map (paint_read.py)
    if os.path.exists(ep):
        out += json.load(open(ep))
    json.dump(out, open(os.path.join(OUT, 'site_props.json'), 'w'))
    k = {x: sum(1 for r in out if r[0] == x) for x in ('wash', 'potty', 'sign', 'entry', 'shed', 'lot', 'car')}
    print(len(out), 'props:', k)
    for r in out:
        if r[0] == 'lot':
            print('   lot e', r[1], 'n', r[2], len(r[7]['lines']) // 3, 'stalls'); continue
        print('  ', r[0], 'e', r[1], 'n', r[2], 'faces', r[3], 'deg', ('size %.1f x %.1f' % (r[4], r[5])) if r[0] == 'wash' else '', repr(r[6]) if r[6] else '')


if __name__ == '__main__':
    main()
