"""Build the game's course data for Woodbine Bend from the cached sources.

  out/rd_woodbine.js   `const RD_WOODBINE = {...};` and `const GREEN_ALTI_WOODBINE = {...};`, ready to paste into index.html

The shapes follow RD_GCCB (see the REAL COURSE section of index.html): east/north metres around `origin`, polygons and
lines delta-coded in decimetres as little-endian int16 base64, the terrain as a coarse grid (`dem`) plus a 2 m relief
layer (`relief`) holding what the coarse grid can't (the mounds), and each green's own 1.5 m elevation lattice.
"""
import base64
import json
import math
import os

import numpy as np
import rasterio
from scipy import ndimage as ndi
from shapely.geometry import LineString, Point, Polygon, box, shape
from shapely.ops import substring, unary_union

import card
import osm
from common import NAME, ORIGIN, OUT, cache

YD = card.YD
DEM_RES, DEM_AREA = 15, (-1200, -1200, 1200, 1200)
Z_DEM, Z_ALTI = 200.0, 200   # metres the dem and the green lattices are stored above
RELIEF_RES = 2


def b64i16(a):
    a = np.asarray(a)
    assert a.min() >= -32768 and a.max() <= 32767, (a.min(), a.max())
    return base64.b64encode(a.astype('<i2').tobytes()).decode()


def rings_of(p):
    for g in getattr(p, 'geoms', [p]):
        if g.is_empty:
            continue
        yield [list(g.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in g.interiors]


def enc_polys(polys):
    """count, then per polygon its rings (count), each ring: npoints, then dx, dy in decimetres."""
    out, items = [], []
    for p in polys:
        for rings in rings_of(p):
            items.append(rings)
    out.append(len(items))
    for rings in items:
        out.append(len(rings))
        for r in rings:
            out.append(len(r))
            x = y = 0
            for e, n in r:
                qe, qn = int(round(e * 10)), int(round(n * 10))
                out += [qe - x, qn - y]
                x, y = qe, qn
    return b64i16(out)


def enc_lines(lines):
    out = [len(lines)]
    for L in lines:
        c = list(L.coords)
        out.append(len(c))
        x = y = 0
        for e, n in c:
            qe, qn = int(round(e * 10)), int(round(n * 10))
            out += [qe - x, qn - y]
            x, y = qe, qn
    return b64i16(out)


# ---- terrain -------------------------------------------------------------------------------------------------------
def read(path):
    with rasterio.open(path) as s:
        return s.read(1), s.transform


def sample(arr, tr, e, n, order=1):
    """Bilinear sample of a north-up raster at local e, n (arrays)."""
    c, r = ~tr * (np.asarray(e), np.asarray(n))
    return ndi.map_coordinates(arr, [r - .5, c - .5], order=order, mode='nearest')


def catmull(Z, nx, ny, fx, fy):
    """The game's demZ (Catmull-Rom over the grid), vectorised; fx, fy in grid units, inside the grid."""
    fx = np.clip(fx, 0, nx - 1.0001)
    fy = np.clip(fy, 0, ny - 1.0001)
    ix, iy = fx.astype(int), fy.astype(int)
    tx, ty = fx - ix, fy - iy

    def w(t):
        t2, t3 = t * t, t * t * t
        return [(-t3 + 2 * t2 - t) * .5, (3 * t3 - 5 * t2 + 2) * .5, (-3 * t3 + 4 * t2 + t) * .5, (t3 - t2) * .5]
    wx, wy = w(tx), w(ty)
    z = 0
    for j in range(4):
        yy = np.clip(iy + j - 1, 0, ny - 1)
        row = 0
        for i in range(4):
            xx = np.clip(ix + i - 1, 0, nx - 1)
            row = row + wx[i] * Z[yy, xx]
        z = z + wy[j] * row
    return z


def build_dem():
    """The coarse grid: 15 m cells from the 10 m wide DEM (rows from south to north), plus a function evaluating it as the game does."""
    wide, trw = read(cache('dem_wide.tif'))
    e0, n0, e1, n1 = DEM_AREA
    nx, ny = int((e1 - e0) / DEM_RES) + 1, int((n1 - n0) / DEM_RES) + 1
    E, N = np.meshgrid(e0 + np.arange(nx) * DEM_RES, n0 + np.arange(ny) * DEM_RES)
    # a light pre-filter so the 15 m samples stand for their cell, not a single 10 m pixel
    Z = sample(ndi.gaussian_filter(wide, .6), trw, E, N)
    q = np.round((Z - Z_DEM) * 100).astype(int)
    Zq = Z_DEM + q / 100
    dem = dict(e0=float(e0), n0=float(n0), de=float(DEM_RES), dn=float(DEM_RES), nx=nx, ny=ny, zb=Z_DEM, data=b64i16(q.ravel()))
    demZ = lambda e, n: catmull(Zq, nx, ny, (np.asarray(e) - e0) / DEM_RES, (np.asarray(n) - n0) / DEM_RES)
    return dem, demZ


def build_relief(demZ, area, inside=None):
    """What the 1 m terrain holds beyond the coarse grid, on 2 m cells: one signed byte per cell in 5 cm steps, zero runs as (0, count)."""
    d1, tr1 = read(cache('dem1m.tif'))
    d1 = ndi.gaussian_filter(d1, .8)
    e0, n0, e1, n1 = [round(v / RELIEF_RES) * RELIEF_RES for v in area]
    w, h = int((e1 - e0) / RELIEF_RES), int((n1 - n0) / RELIEF_RES)
    E, N = np.meshgrid(e0 + (np.arange(w) + .5) * RELIEF_RES, n0 + (np.arange(h) + .5) * RELIEF_RES)
    r = sample(d1, tr1, E, N) - demZ(E, N)
    q = np.clip(np.round(r * 20), -127, 127).astype(int).ravel()
    q[np.abs(q) <= 2] = 0  # within 10 cm of the coarse grid: nothing to add
    if inside is not None:  # only on and just around the course
        from rasterio import features as rfeat
        from rasterio.transform import from_origin
        m = rfeat.rasterize([(inside, 1)], out_shape=(h, w), transform=from_origin(e0, n1, RELIEF_RES, RELIEF_RES), dtype='uint8')[::-1]
        q[m.ravel() == 0] = 0
    out = bytearray()
    k = 0
    while k < len(q):
        if q[k] == 0:
            run = 0
            while k < len(q) and q[k] == 0 and run < 255:
                run += 1
                k += 1
            out += bytes([0, run])
        else:
            out.append(q[k] & 255)
            k += 1
    print(f'relief {w}x{h} cells, {np.mean(q != 0):.0%} non-zero, max |r| {np.abs(r).max():.1f} m, {len(out) / 1024:.0f} KB')
    return dict(e0=float(e0), n0=float(n0), res=RELIEF_RES, w=w, h=h, b8=1, d=base64.b64encode(bytes(out)).decode())


def green_alti(green_poly):
    d1, tr1 = read(cache('dem1m.tif'))
    e0, n0, e1, n1 = green_poly.buffer(6).bounds
    s = 1.5
    nx, ny = int(math.ceil((e1 - e0) / s)) + 1, int(math.ceil((n1 - n0) / s)) + 1
    E, N = np.meshgrid(e0 + np.arange(nx) * s, n0 + np.arange(ny) * s)
    z = sample(ndi.gaussian_filter(d1, .5), tr1, E, N)
    return dict(e0=round(e0, 1), n0=round(n0, 1), s=s, nx=nx, ny=ny, z=[int(v) for v in np.round((z.ravel() - Z_ALTI) * 100)])


# ---- holes ---------------------------------------------------------------------------------------------------------
def point_at_remaining(L, D):
    """The point on (or behind the start of) hole line L that leaves D metres to its end."""
    s = L.length - D
    if s >= 0:
        return L.interpolate(s)
    (x0, y0), (x1, y1) = L.coords[0], L.coords[1]
    l = math.hypot(x1 - x0, y1 - y0)
    return Point(x0 - (x1 - x0) / l * -s, y0 - (y1 - y0) / l * -s)


def snap_to_tee(p, tees, max_d=14):
    best = min(tees, key=lambda t: t.distance(p))
    if best.distance(p) > max_d:
        return p, False
    if best.contains(p):
        return p, True
    # the nearest point well inside the box
    inner = best.buffer(-1) if best.buffer(-1).area > 4 else best
    from shapely.ops import nearest_points
    return nearest_points(inner, p)[0], True


def describe(h, demZ1, greens_near, F, fair):
    """A one-line note like GCCB's: elevation change, water, bunkers by the green and in the fairway."""
    tee, gr = h['tee'], h['green']
    dz = demZ1(*gr) - demZ1(*tee)
    bits = []
    ft = dz / .3048
    if abs(ft) >= 6:
        bits.append(f'Plays {abs(ft):.0f} ft {"uphill" if ft > 0 else "downhill"}')
    L = h['L']
    corridor = L.buffer(22)
    wat = [w['poly'] for w in F['water'] if w['poly'].intersects(corridor)]
    if wat:
        side = []
        for w in wat:
            c = w.centroid
            s = L.project(c)
            p = L.interpolate(s)
            q = L.interpolate(min(L.length, s + 1))
            cross = (q.x - p.x) * (c.y - p.y) - (q.y - p.y) * (c.x - p.x)
            side.append('left' if cross > 0 else 'right')
        bits.append('water ' + ('and '.join(sorted(set(side)))) if len(set(side)) == 1 else 'water both sides')
    g = Point(gr)
    gb = sum(1 for b in F['bunker'] if b['poly'].distance(g) < 30)
    fb = sum(1 for b in F['bunker'] if b['poly'].distance(g) >= 30 and b['poly'].intersects(corridor))
    if fb:
        bits.append(f'{fb} fairway bunker{"s" if fb > 1 else ""}' if fb > 1 else 'a fairway bunker')
    if gb:
        bits.append(f'{gb} bunkers by the green' if gb > 1 else 'a bunker by the green')
    if h['par'] > 3:
        bits.append('mounds line the fairway')
    return ' · '.join(bits) if bits else 'Native grass all round'


def build_holes(F, demZ1):
    tees = [t['poly'] for t in F['tee']]
    out = []
    for hh in F['hole']:
        i = hh['ref'] - 1
        L = hh['line']
        g = min(F['green'], key=lambda q: q['poly'].distance(Point(L.coords[-1])))['poly']
        pin = min(F['pin'], key=lambda q: q['pt'].distance(Point(L.coords[-1])))['pt']
        gc = g.centroid
        # the line ends at the green centre
        c = list(L.coords)
        c[-1] = (gc.x, gc.y)
        L = LineString(c)
        pos = {}
        for k in ('gold', 'black', 'silver', 'bronze'):
            yd = card.TEES[k][2][i]
            p, ok = snap_to_tee(point_at_remaining(L, yd * YD), tees)
            pos[k] = (round(p.x, 2), round(p.y, 2))
        tee = pos['gold']
        # the line of play starts at the played (gold) tee
        s = L.project(Point(tee))
        rest = [q for q in L.coords if L.project(Point(q)) > s + 15]
        line = [tee] + [(round(x, 2), round(y, 2)) for x, y in rest]
        h = dict(par=card.PAR[i], hcp=card.HCP[i], len=round(card.TEES['gold'][2][i] * YD, 1), yd=card.TEES['gold'][2][i],
                 lens=[round(card.TEES[k][2][i] * YD, 1) for k in ('gold', 'black', 'silver', 'bronze')],
                 tee=list(tee), green=[round(gc.x, 2), round(gc.y, 2)], line=[list(p) for p in line],
                 mk={'w': list(pos['gold']), 'y': list(pos['black']), 'b': list(pos['silver']), 'r': list(pos['bronze'])})
        h['desc'] = describe(dict(tee=tee, green=(gc.x, gc.y), L=LineString(line), par=h['par']), demZ1, None, F, None)
        h['_green_poly'] = g
        out.append(h)
    return out


def creek_pieces(hw=2.0, step=14.0):
    """creek.py's centre line as short ribbons (the game sets each piece's water level from its own banks, so the creek steps down)."""
    p = os.path.join(OUT, 'creek.json')
    if not os.path.exists(p):
        return []
    out = []
    for g in json.load(open(p)):
        L = shape(g)
        n = max(1, int(round(L.length / step)))
        for i in range(n):
            a, b = L.length * i / n, min(L.length, L.length * (i + 1) / n + .3)
            out.append(substring(L, a, b).buffer(hw, cap_style=2))
    return out


def main():
    F = osm.load()
    ba = os.path.join(OUT, 'bunkers_auto.json')  # bunkers the aerial shows but OSM lacks (bunkers_auto.py)
    if os.path.exists(ba):
        F['bunker'] += [dict(poly=shape(g), tags={'auto': 'yes'}) for g in json.load(open(ba))]
    fp0 = os.path.join(OUT, 'fairways_painted.json')  # hand-corrected fairways (fairways.py) win over trace.py's
    fair = [shape(g) for g in json.load(open(fp0 if os.path.exists(fp0) else os.path.join(OUT, 'fairways.json')))]
    paths = []  # cart paths removed on purpose (trace.py's paths.json was only fragments)
    course = F['course'][0]['poly']
    dem, demZ = build_dem()
    d1, tr1 = read(cache('dem1m.tif'))
    demZ1 = lambda e, n: float(sample(d1, tr1, [e], [n])[0])
    relief = build_relief(demZ, course.buffer(40).bounds, course.buffer(30))
    holes = build_holes(F, demZ1)
    alti = {i: green_alti(h.pop('_green_poly')) for i, h in enumerate(holes)}

    area = box(-700, -700, 700, 700)
    clip = lambda ps: [p.intersection(area) for p in ps if p.intersects(area)]
    trees_path = os.path.join(OUT, 'trees.json')
    trees = json.load(open(trees_path)) if os.path.exists(trees_path) else []
    tp = os.path.join(OUT, 'trees_painted.json')  # trees added by hand-painting (trees_paint.py) on top of the lidar ones
    if os.path.exists(tp):
        trees += json.load(open(tp))
    tq = []
    for t in trees:  # e, n, crown diameter (dm), kind * 1000 + height (dm)
        tq += [int(round(t['e'] * 10)), int(round(t['n'] * 10)), int(round(t['d'] * 10)), t['kind'] * 1000 + min(999, int(round(t['h'] * 10)))]
    water = [w['poly'] for w in F['water']]
    creek = creek_pieces()
    fp = os.path.join(OUT, 'fescue.json')
    fescue = [shape(g) for g in json.load(open(fp))] if os.path.exists(fp) else []
    bp = os.path.join(OUT, 'boundary.json')  # the hand-painted boundary (boundary.py) replaces the OSM outline as the out-of-bounds line
    bound = shape(json.load(open(bp))) if os.path.exists(bp) else Polygon(course.exterior)
    fescue = [g for f in fescue for g in getattr(f.intersection(bound), 'geoms', [f.intersection(bound)]) if g.geom_type == 'Polygon' and not g.is_empty]
    rd = dict(
        name=NAME, origin=list(ORIGIN), dem=dem, holes=holes,
        feat=dict(fair=enc_polys(fair), green=enc_polys([f['poly'] for f in F['green']]), tee=enc_polys([f['poly'] for f in F['tee']]),
                  sand=enc_polys([f['poly'] for f in F['bunker']]), water=enc_polys(water), path=enc_polys(paths), creek=enc_polys(creek), fescue=enc_polys(fescue),
                  range=enc_polys([f['poly'] for f in F['driving_range']])),
        trees=b64i16(tq) if tq else '', ntrees=len(trees),
        forest=enc_polys(clip([f['poly'] for f in F['wood']])) if F['wood'] else enc_polys([]),
        orchard=enc_polys([]),
        boundary=enc_polys([bound]),
        buildings=enc_polys(clip([f['poly'] for f in F['building']])),
        # the lidar trees cover the whole detail area: OSM woods only count beyond it
        cover=enc_polys([area] if trees else []),
        streams=enc_lines([f['line'] for f in F['stream']]),
        relief=relief,
        # tee marker colours: w is the tee played (gold), y/b/r the other sets (black, silver, bronze)
        mkc=dict(w=0xd9b23a, y=0x26282b, b=0xc9ced3, r=0xb07045),
    )
    js = 'const RD_WOODBINE = ' + json.dumps(rd, separators=(',', ':')) + ';\n'
    js += 'const GREEN_ALTI_WOODBINE = {' + ','.join(f'{i}:' + json.dumps(a, separators=(',', ':')).replace('"', '') for i, a in alti.items()) + '};\n'
    open(os.path.join(OUT, 'rd_woodbine.js'), 'w').write(js)
    print(f'rd_woodbine.js {len(js) / 1024:.0f} KB (relief {len(relief["d"]) / 1024:.0f} KB, dem {len(dem["data"]) / 1024:.0f} KB, trees {len(trees)})')
    for i, h in enumerate(holes):
        print(f"{i + 1:2d} par {h['par']} {h['yd']} yd  tee {h['tee']}  {h['desc']}")


if __name__ == '__main__':
    main()
