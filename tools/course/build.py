"""Build the game's course data for the course picked (--course <key>, see common.py) from its cached sources.

  out/rd_<key>.js   `const RD_<KEY> = {...};` and `const GREEN_ALTI_<KEY> = {...};`, which install.py puts into the game

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
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box, shape
from shapely.ops import linemerge, substring, unary_union

import osm
import practice_read
from common import ALTI_VAR, DETAIL, NAME, ORIGIN, OUT, RD_JS, RD_VAR, YD, cache, course, to_local

card = course   # the scorecard: PAR, HCP, TEES, MARKERS
DEM_RES, DEM_AREA = 15, course.DEM_AREA
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


def green_alti(green_poly, s=1.5):
    d1, tr1 = read(cache('dem1m.tif'))
    e0, n0, e1, n1 = green_poly.buffer(6).bounds
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


def snap_to_tee(p, tees, L=None, hw=2.6, max_d=40, min_hw=.8):
    """Move a tee-set position into a tee box so that the two markers beside it (hw m either side, square to the line to the green)
    are inside the box too: the nearest box to p that is close to the hole line, and in it the nearest point whose markers sit at least
    .4 m inside. A box too narrow for the gap gets a smaller gap (down to min_hw). Returns the point and the marker half-gap used."""
    from shapely.ops import nearest_points
    cand = [t for t in tees if t.distance(p) <= max_d and (L is None or t.distance(L) < 25)] or tees
    best = min(cand, key=lambda t: t.distance(p))
    tgt = Point(L.coords[-1]) if L is not None else None
    core = best.buffer(-.4)

    def fits(q, w):
        if tgt is None:
            return core.contains(q)
        dx, dy = tgt.x - q.x, tgt.y - q.y
        dl = math.hypot(dx, dy) or 1
        ox, oy = -dy / dl * w, dx / dl * w
        return core.contains(q) and core.contains(Point(q.x + ox, q.y + oy)) and core.contains(Point(q.x - ox, q.y - oy))
    x0, y0, x1, y1 = best.bounds
    grid = [Point(x, y) for x in np.arange(x0, x1, .25) for y in np.arange(y0, y1, .25)]
    w = hw
    while w >= min_hw - 1e-9:
        if fits(p, w):
            return p, w
        ok = [q for q in grid if fits(q, w)]
        if ok:
            return min(ok, key=lambda q: q.distance(p)), w
        w -= .2
    inner = best.buffer(-.5) if best.buffer(-.5).area > 1 else best
    return nearest_points(inner, p)[0], min_hw


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
    sp = os.path.join(OUT, 'tee_starts.json')  # yellow dots painted on the tee map: where a hole's played tee should be
    starts = {}
    for e, n in json.load(open(sp)) if os.path.exists(sp) else []:
        q = Point(e, n)
        h = min(F['hole'], key=lambda hh: hh['line'].distance(q))
        if h['line'].distance(q) < 80:
            starts[h['ref'] - 1] = (e, n)
    tm = os.path.join(OUT, 'tee_marks.json')  # the red marker line painted on a hole close-up (hole_zoom_paint.py): the played tee and its marker gap
    marks = json.load(open(tm)) if os.path.exists(tm) else {}
    for r, m in marks.items():
        starts[int(r) - 1] = tuple(m['mid'])
    out = []
    for hh in F['hole']:
        i = hh['ref'] - 1
        L = hh['line']
        g = min(F['green'], key=lambda q: q['poly'].distance(Point(L.coords[-1])))['poly']
        gc = g.centroid
        # the line ends at the green centre
        c = list(L.coords)
        c[-1] = (gc.x, gc.y)
        L = LineString(c)
        pos, gap = {}, {}
        sets = [card.MARKERS[m][0] for m in 'wybr']   # the set played, then the other three
        play = sets[0]
        for k in sets:
            yd = card.TEES[k][2][i]
            raw = point_at_remaining(L, yd * YD)
            p, gap[k] = snap_to_tee(raw, tees, L)
            if p.distance(raw) > 8:
                print(f'  hole {hh["ref"]} {k}: {yd} yd is {p.distance(raw):.0f} m from the nearest tee box; placed in the box')
            pos[k] = (round(p.x, 2), round(p.y, 2))
        if i in starts:
            pos[play] = starts[i]
            q, gap[play] = snap_to_tee(Point(starts[i]), tees, L, marks[str(hh['ref'])]['half'] if str(hh['ref']) in marks else 2.6)
            if q.distance(Point(starts[i])) > .05:
                print(f'  hole {hh["ref"]}: the painted start moved {q.distance(Point(starts[i])):.1f} m to keep its markers inside the tee box')
            pos[play] = (round(q.x, 2), round(q.y, 2))
        tee = pos[play]
        # the line of play starts at the played tee
        s = L.project(Point(tee))
        rest = [q for q in L.coords if L.project(Point(q)) > s + 15]
        line = [tee] + [(round(x, 2), round(y, 2)) for x, y in rest]
        h = dict(par=card.PAR[i], hcp=card.HCP[i], len=round(card.TEES[play][2][i] * YD, 1), yd=card.TEES[play][2][i],
                 lens=[round(card.TEES[k][2][i] * YD, 1) for k in sets],
                 tee=list(tee), green=[round(gc.x, 2), round(gc.y, 2)], line=[list(p) for p in line],
                 mk={m: list(pos[k]) for m, k in zip('wybr', sets)})
        h['mkh'] = {m: round(gap[k], 2) if k in gap else 2.6 for m, k in zip('wybr', sets)}   # the half-gap between a set's two markers: as wide as its box allows, up to 2.6 m
        h['desc'] = describe(dict(tee=tee, green=(gc.x, gc.y), L=LineString(line), par=h['par']), demZ1, None, F, None)
        h['_green_poly'] = g
        out.append(h)
    return out


def link_fairways(fair, F, reach=18.0):
    """Make each hole's fairway run right into its green, with no pocket of rough or first cut between them: the last stretch
    of the fairway (the part within `reach` m of the green) and the green are joined by their convex hull, and that is added to
    the fairway. Bunkers, water and the green itself still take precedence in the game. Returns the new fairways and a report."""
    fair = [f for f in fair]
    report = []
    for hh in F['hole']:
        L = hh['line']
        g = min(F['green'], key=lambda q: q['poly'].distance(Point(L.coords[-1])))['poly']
        idx = [k for k, f in enumerate(fair) if f.distance(L) < 12 and f.distance(g) < 15]  # (a fairway further off is not this hole's approach)
        for k in idx:
            f = fair[k]
            gap = f.distance(g)
            near = f.intersection(g.buffer(gap + reach))
            if near.is_empty:
                near = f
            bridge = unary_union([near, g.buffer(.8)]).convex_hull.difference(g.buffer(-1))  # runs 1 m into the green, not over it
            fair[k] = unary_union([f, bridge]).buffer(.6).buffer(-.6)
            report.append((hh['ref'], round(gap, 1), round(fair[k].area - f.area)))
    merged = unary_union(fair)
    return [p for p in getattr(merged, 'geoms', [merged])], report


def creek_pieces(hw=2.0, step=14.0):
    """creek.py's centre line as short ribbons (the game sets each piece's water level from its own banks, so the creek steps down)."""
    pp = os.path.join(OUT, 'creek_painted.json')  # the hand-corrected creek (creek_paint.py), already in pieces
    if os.path.exists(pp):
        return [shape(g) for g in json.load(open(pp))]
    p = os.path.join(OUT, 'creek.json')
    if not os.path.exists(p):
        return []
    out = []
    for g in json.load(open(p)):
        L = LineString(round_line(shape(g).coords))   # the centre line is rounded, so the ribbons bend smoothly
        n = max(1, int(round(L.length / step)))
        for i in range(n):
            a, b = L.length * i / n, min(L.length, L.length * (i + 1) / n + .3)
            out.append(substring(L, a, b).buffer(hw, cap_style=2))
    return out


def highway(area=course.ROAD_AREA):
    """The highway with traffic (course.HIGHWAY; at Woodbine US 20, past the north edge of the course), as one west-to-east line clipped to the game's 2 m class grid, and the
    distance along it where the 55 mph road becomes Woodbine Street (35 mph) at the edge of Stockton. Read from the raw OSM file: osm.load
    keeps the tag-less duplicate of a way that Overpass lists twice, which loses these two ways."""
    els = json.load(open(cache('osm.json')))['elements']
    nodes = {e['id']: to_local(e['lon'], e['lat']) for e in els if e['type'] == 'node'}
    H = course.HIGHWAY
    ways = {e['id']: e for e in els if e['type'] == 'way' and e.get('tags', {}).get('ref') == H['ref']}
    assert len(ways) == H['ways'], ways.keys()
    line = linemerge([LineString([nodes[i] for i in w['nodes']]) for w in ways.values()])
    assert line.geom_type == 'LineString'
    if line.coords[0][0] > line.coords[-1][0]:
        line = LineString(list(line.coords)[::-1])
    fast = [w for w in ways.values() if w['tags'].get('maxspeed') == H['fast']][0]  # the stretch that meets the town street
    slow = line.project(Point(*[nodes[i] for i in fast['nodes']][-1]))
    clipped = line.intersection(box(*area))
    if clipped.geom_type != 'LineString':
        clipped = max(clipped.geoms, key=lambda g: g.length)
    cut = line.project(Point(*clipped.coords[0]))
    return clipped.simplify(.4), round(slow - cut)


def side_roads(F, hw, area=course.ROAD_AREA):
    """The public roads beside the course (course.SIDE_ROADS), drawn for looks only (the ball does not touch them). At Woodbine: East Center Road along the south
    side and South Brown Road (with Chicago Street, its stretch through Stockton) along the east side. Each runs out past the map and
    stops at the middle of US 20, which both meet. Lines from OSM, ordered west to east / south to north."""
    out = []
    for names in course.SIDE_ROADS or []:
        line = linemerge([r['line'] for r in F['road'] if r['tags'].get('name') in names])
        assert line.geom_type == 'LineString', names
        x = line.intersection(hw)
        if hw is not None and not x.is_empty:   # the road meets the highway: keep the long side of it, ending on the highway's centre line
            p = x if x.geom_type == 'Point' else list(x.geoms)[0]
            d = line.project(p)
            a, b = substring(line, 0, d), substring(line, d, line.length)
            line = a if a.length > b.length else b
        c = line.intersection(box(*area))
        if c.geom_type != 'LineString':
            c = max(c.geoms, key=lambda g: g.length)
        pts = list((LineString(round_line(c.coords)) if getattr(course, 'ROUND_ROADS', False) else c).simplify(.4).coords)   # Eagle Ridge: its winding resort road
        if pts[0][0] + pts[0][1] > pts[-1][0] + pts[-1][1]:
            pts = pts[::-1]
        out.append(LineString(pts))
    return out


def round_green(p, iters=3):
    """A green's OSM outline has corners every 2-3 m; Chaikin corner cutting (each corner replaced by two points a quarter of the way along
    its edges) gives smooth curves that stay within the original outline and lose only a few percent of its area."""
    pts = list(p.exterior.coords)[:-1]
    for _ in range(iters):
        q = []
        for i, (x0, y0) in enumerate(pts):
            x1, y1 = pts[(i + 1) % len(pts)]
            q += [(.75 * x0 + .25 * x1, .75 * y0 + .25 * y1), (.25 * x0 + .75 * x1, .25 * y0 + .75 * y1)]
        pts = q
    return Polygon(pts).simplify(.04)


def round_osm(p, iters=3, step=None):
    """An outline straight from OSM, where nothing was painted over it (Eagle Ridge South's fairways, bunkers, tees and course outline):
    the same corner cutting as round_green on every ring, then grown back to the original area by an even offset (not scaled, so a long
    fairway's ends stay put). `step` m first adds points along long edges, so only the corners round and a long edge is not pulled in."""
    if p.geom_type == 'MultiPolygon':
        return unary_union([round_osm(g, iters, step) for g in p.geoms])

    def cut(ring):
        r = LineString(ring.coords)
        if step:
            r = LineString([r.interpolate(d) for d in np.linspace(0, r.length, max(4, int(math.ceil(r.length / step))) + 1)])
        return Polygon(list(r.coords)[:-1])
    q = Polygon(round_green(cut(p.exterior), iters).exterior, [round_green(cut(h), iters).exterior for h in p.interiors]).buffer(0)
    for _ in range(2):
        q = q.buffer((p.area - q.area) / q.length, join_style=1, quad_segs=4)
    return q.simplify(.04)


def round_pond(p, iters=3):
    """A pond's OSM outline has corners every 8-22 m; the same corner cutting as round_green, then scaled about its centre back to the original
    area (cutting corners alone shrinks a pond by a few percent, which would pull the shore in from the real one)."""
    q = round_green(p, iters)
    c = p.centroid
    return affinity.scale(q, math.sqrt(p.area / q.area), math.sqrt(p.area / q.area), origin=c)


def round_line(coords, iters=3):
    """Corner cutting on an open line (the creek's centre line); the two ends stay where they are."""
    pts = list(coords)
    for _ in range(iters):
        q = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            q += [(.75 * x0 + .25 * x1, .75 * y0 + .25 * y1), (.25 * x0 + .75 * x1, .25 * y0 + .75 * y1)]
        pts = q + [pts[-1]]
    return pts


def main():
    F = osm.load()
    for w in F['water']:
        a0 = w['poly'].area
        w['poly'] = round_pond(w['poly'])
        assert abs(w['poly'].area / a0 - 1) < .01 and w['poly'].is_valid and w['poly'].geom_type == 'Polygon'
    for g in F['green']:
        a0 = g['poly'].area
        g['poly'] = round_green(g['poly'])
        assert abs(g['poly'].area / a0 - 1) < .06 and g['poly'].is_valid
    ba = os.path.join(OUT, 'bunkers_auto.json')  # bunkers the aerial shows but OSM lacks (bunkers_auto.py)
    if os.path.exists(ba):
        F['bunker'] += [dict(poly=shape(g), tags={'auto': 'yes'}) for g in json.load(open(ba))]
    for k in ('bunker', 'tee', 'fairway'):   # OSM outlines (painted ones replace them below, already smoothed)
        for f in F[k]:
            f['poly'] = round_osm(f['poly'])
    bpn = os.path.join(OUT, 'bunkers_painted.json')  # hand-refined bunkers (bunkers_paint.py) replace the OSM and automatic ones
    if os.path.exists(bpn):
        F['bunker'] = [dict(poly=shape(g), tags={'painted': 'yes'}) for g in json.load(open(bpn))]
    tpn = os.path.join(OUT, 'tees_painted.json')  # hand-edited tee boxes (tee_boxes_paint.py) replace the OSM ones
    if os.path.exists(tpn):
        F['tee'] = [dict(poly=shape(g), tags={'painted': 'yes'}) for g in json.load(open(tpn))]
    fp0 = os.path.join(OUT, 'fairways_painted.json')  # hand-corrected fairways (fairways.py) win over OSM's (Eagle Ridge), then trace.py's (Woodbine: OSM has none)
    if os.path.exists(fp0) or not F['fairway']:
        fair = [shape(g) for g in json.load(open(fp0 if os.path.exists(fp0) else os.path.join(OUT, 'fairways.json')))]
    else:
        fair = [f['poly'] for f in F['fairway']]
    fair, rep = link_fairways(fair, F)
    if not os.path.exists(fp0) and F['fairway']:   # OSM fairways: round the inside corners where the link to the green meets the fairway's edge
        fair = [q.buffer(5, quad_segs=8).buffer(-5, quad_segs=8).simplify(.04) for q in fair]
    print('fairway -> green links (hole, gap m, area added m2):', rep)
    cp = os.path.join(OUT, 'cartpaths.json')   # the cart paths: found on the aerial and corrected by hand (cartpaths_edit.py, cartpaths_read.py); trace.py's paths.json was only fragments
    paths = [shape(g) for g in json.load(open(cp))] if os.path.exists(cp) else []
    course_poly = F['course'][0]['poly']
    dem, demZ = build_dem()
    d1, tr1 = read(cache('dem1m.tif'))
    demZ1 = lambda e, n: float(sample(d1, tr1, [e], [n])[0])
    relief = build_relief(demZ, course_poly.buffer(40).bounds, course_poly.buffer(30))
    holes = build_holes(F, demZ1)
    alti = {i: green_alti(h.pop('_green_poly')) for i, h in enumerate(holes)}
    prac = None   # the practice green (practice_read.py): a scene of its own, not one of the 18 holes
    ppn = os.path.join(OUT, 'practice.json')
    if os.path.exists(ppn):
        pr = json.load(open(ppn))
        pg = shape(pr['green'])
        F['green'].append(dict(poly=pg, tags={'practice': 'yes'}))
        if pr['bunkers']:
            F['bunker'] += [dict(poly=shape(g), tags={'painted': 'yes'}) for g in pr['bunkers']]
        gc = pg.centroid
        tee = (round(gc.x, 2), round(gc.y - 25, 2))   # the scene's frame: from the south, 25 m from the middle of the green
        alti['prac'] = green_alti(pg, 1.0)
        prac = dict(tee=list(tee), green=[round(gc.x, 2), round(gc.y, 2)], line=[list(tee), [round(gc.x, 2), round(gc.y, 2)]],
                    mk={k: list(tee) for k in 'wybr'}, cups=[[round(float(e), 2), round(float(n), 2)] for e, n in pr['cups']])

    drv = None   # the driving range (range_read.py): a scene of its own, like the practice green; its features are drawn only there
    rpn = os.path.join(OUT, 'range.json')
    if os.path.exists(rpn):
        rr = json.load(open(rpn))
        spots, flags = rr['spots'], rr['flags']
        tee = (round(sum(p[0] for p in spots) / len(spots), 2), round(sum(p[1] for p in spots) / len(spots), 2))   # the scene's frame: from the middle of the hitting spots to the middle of the flags
        flags = sorted(flags, key=lambda p: math.hypot(p[0] - tee[0], p[1] - tee[1]))   # nearest first
        gc = (round(sum(p[0] for p in flags) / len(flags), 2), round(sum(p[1] for p in flags) / len(flags), 2))
        drv = dict(tee=list(tee), green=list(gc), line=[list(tee), list(gc)], mk={k: list(tee) for k in 'wybr'}, spots=spots, flags=flags, ext=spots + flags,
                   feat=dict(fair=enc_polys([shape(g) for g in rr['fair']]), green=enc_polys([shape(g) for g in rr['greens']]), sand=enc_polys([shape(g) for g in rr['bunkers']]),
                             fescue=enc_polys([shape(g) for g in rr['fescue']])),
                   boundary=enc_polys([shape(rr['boundary'])]), box=rr['box'])
    area = box(*DETAIL)
    clip = lambda ps: [p.intersection(area) for p in ps if p.intersects(area)]
    trees_path = os.path.join(OUT, 'trees.json')
    trees = json.load(open(trees_path)) if os.path.exists(trees_path) else []
    tp = os.path.join(OUT, 'trees_painted.json')  # trees added by hand-painting (trees_paint.py) on top of the lidar ones
    if os.path.exists(tp):
        trees += json.load(open(tp))
    if os.path.exists(ppn):   # the trees painted on the practice-green map stand in for any lidar tree under them
        trees = [t for t in trees if not any(math.hypot(t['e'] - q['e'], t['n'] - q['n']) < .5 * q['d'] for q in pr['trees'])] + pr['trees']
    if os.path.exists(rpn):   # the trees painted on the range map stand in for any lidar tree under them
        trees = [t for t in trees if not any(math.hypot(t['e'] - q['e'], t['n'] - q['n']) < .5 * q['d'] for q in rr['trees'])] + rr['trees']
    tq = []
    for t in trees:  # e, n, crown diameter (dm), kind * 1000 + height (dm)
        tq += [int(round(t['e'] * 10)), int(round(t['n'] * 10)), int(round(t['d'] * 10)), t['kind'] * 1000 + min(999, int(round(t['h'] * 10)))]
    water = [w['poly'] for w in F['water']]
    creek = creek_pieces()
    fp = os.path.join(OUT, 'fescue.json')
    fescue = [shape(g) for g in json.load(open(fp))] if os.path.exists(fp) else []
    bp = os.path.join(OUT, 'boundary.json')  # the hand-painted boundary (boundary.py) replaces the OSM outline as the out-of-bounds line
    bound = shape(json.load(open(bp))) if os.path.exists(bp) else round_osm(Polygon(course_poly.exterior), step=12)
    if os.path.exists(ppn):
        fescue = practice_read.merge_fescue(fescue, pr)
    fescue = [g for f in fescue for g in getattr(f.intersection(bound), 'geoms', [f.intersection(bound)]) if g.geom_type == 'Polygon' and not g.is_empty]
    hw, hw_slow = highway() if course.HIGHWAY else (None, None)
    roads = side_roads(F, hw)
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
        highway=enc_lines([hw] if hw else []), hwSlow=hw_slow,  # the highway with traffic (Woodbine: US 20 past the north edge); hwSlow = metres from its west end where the limit drops from 55 to 35 mph
        relief=relief, prac=prac, drv=drv, roads=[enc_lines([r]) for r in roads],
        props=(json.load(open(os.path.join(OUT, 'site_props.json'))) if os.path.exists(os.path.join(OUT, 'site_props.json')) else []) + ([rr['shed']] if drv and rr.get('shed') else []),  # washrooms, porta-potties and signposts painted on the aerial (site_paint.py)
        # tee marker colours: w is the tee played, y/b/r the other sets (course.MARKERS)
        mkc={m: c for m, (_, c) in card.MARKERS.items()},
    )
    js = f'const {RD_VAR} = ' + json.dumps(rd, separators=(',', ':')) + ';\n'
    js += f'const {ALTI_VAR} = {{' + ','.join(f'{i}:' + json.dumps(a, separators=(',', ':')).replace('"', '') for i, a in alti.items()) + '};\n'
    open(RD_JS, 'w').write(js)
    print(f'{os.path.basename(RD_JS)} {len(js) / 1024:.0f} KB (relief {len(relief["d"]) / 1024:.0f} KB, dem {len(dem["data"]) / 1024:.0f} KB, trees {len(trees)})')
    for i, h in enumerate(holes):
        print(f"{i + 1:2d} par {h['par']} {h['yd']} yd  tee {h['tee']}  {h['desc']}")


if __name__ == '__main__':
    main()
