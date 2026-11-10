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
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.ops import linemerge, substring, unary_union

import osm
import practice_read
from common import ALTI_VAR, DETAIL, NAME, ORIGIN, OUT, RD_JS, RD_VAR, YD, cache, course, tee_rect, to_local

card = course   # the scorecard: PAR, HCP, TEES, MARKERS
DEM_RES, DEM_AREA = 15, course.DEM_AREA
Z_DEM = Z_ALTI = float(getattr(course, 'Z0', 200))   # metres the dem and the green lattices are stored above (course.Z0; the engine's z0 in courses.json must be the same)
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


def build_relief(demZ, area, inside=None, water=None):
    """What the 1 m terrain holds beyond the coarse grid, on 2 m cells: one signed byte per cell in 5 cm steps, zero runs as (0, count).
    water (course.RELIEF_OFF_WATER: both Eagle Ridge courses): the ponds and creek pieces, where the relief is left off (faded in from 3 to 6 m
    out, the banks the game digs), so a nearly flat shore (a lake the DEM holds as one flat surface) is not edged in 2 m steps."""
    d1, tr1 = read(cache('dem1m.tif'))
    d1 = ndi.gaussian_filter(d1, .8)
    e0, n0, e1, n1 = [round(v / RELIEF_RES) * RELIEF_RES for v in area]
    w, h = int((e1 - e0) / RELIEF_RES), int((n1 - n0) / RELIEF_RES)
    E, N = np.meshgrid(e0 + (np.arange(w) + .5) * RELIEF_RES, n0 + (np.arange(h) + .5) * RELIEF_RES)
    r = sample(d1, tr1, E, N) - demZ(E, N)
    if water is not None and not water.is_empty:
        from rasterio import features as rfeat
        from rasterio.transform import from_origin
        wm = rfeat.rasterize([(water, 1)], out_shape=(h, w), transform=from_origin(e0, n1, RELIEF_RES, RELIEF_RES), dtype='uint8')[::-1]
        t = np.clip((ndi.distance_transform_edt(wm == 0) * RELIEF_RES - 3) / 3, 0, 1)
        r = r * t * t * (3 - 2 * t)
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
        for k, xy in getattr(course, 'TEE_BOXES', {}).get(hh['ref'], {}).items():   # a tee set put in the box named by its centre (course.TEE_BOXES), where the nearest-box rule picks the wrong one
            raw = Point(xy)
            q, gap[k] = snap_to_tee(raw, [min(tees, key=lambda t: t.distance(raw))], L)
            pos[k] = (round(q.x, 2), round(q.y, 2))
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
        if getattr(course, 'NO_FAIRWAY_HULL', False):   # the painted fairway already runs up to the green (Legends): no hull, which would fill the notches and cross water
            break
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
    p, pa = os.path.join(OUT, 'creek.json'), os.path.join(OUT, 'creek_added.json')   # creek_added.json: creek painted on the extras map (extras_edit.py read), centre lines
    if not os.path.exists(p) and not os.path.exists(pa):
        return []
    out = []
    lines = [LineString(round_line(shape(g).coords)) for g in json.load(open(p))] if os.path.exists(p) else []   # the centre line is rounded, so the ribbons bend smoothly
    if os.path.exists(pa):
        lines += [shape(g) for g in json.load(open(pa))]   # (already smoothed by the reader; never cut by CREEK_CUT below, which is for the mapped creek)
    lines_mapped = len(lines) - (len(json.load(open(pa))) if os.path.exists(pa) else 0)
    added, lines = lines[lines_mapped:], lines[:lines_mapped]
    for bx in getattr(course, 'CREEK_CUT', []):   # course.CREEK_CUT = [(e0, n0, e1, n1)]: the creek is taken out of these boxes (a branch the map has that the course does not)
        lines = [q for L in lines for q in getattr(L.difference(box(*bx)), 'geoms', [L.difference(box(*bx))]) if q.geom_type == 'LineString' and q.length > 3]
    lines += added
    for L in lines:
        n = max(1, int(round(L.length / (step / 2 if getattr(course, 'SMOOTH_MORE', False) else step))))   # (half-length pieces: the water level steps down in finer steps)
        for i in range(n):
            a, b = L.length * i / n, min(L.length, L.length * (i + 1) / n + .3)
            out.append(substring(L, a, b).buffer(hw, cap_style=1 if getattr(course, 'SMOOTH_MORE', False) else 2))   # (round ends: the pieces blend on a bend instead of meeting in blocky corners)
    return out


def clip_lines(lines, area):
    """The pieces of each line inside the area (a line that runs far off the map would overflow the encoding)."""
    out = []
    for L in lines:
        c = L.intersection(area)
        out += [g for g in getattr(c, 'geoms', [c]) if g.geom_type == 'LineString' and g.length > 5]
    return out


def highway(area=course.ROAD_AREA):
    """The highway with traffic (course.HIGHWAY; at Woodbine US 20, past the north edge of the course), as one west-to-east line clipped to the game's 2 m class grid, and the
    distance along it where the 55 mph road becomes Woodbine Street (35 mph) at the edge of Stockton. Read from the raw OSM file (osm.load
    once kept the tag-less duplicate of a way that Overpass lists twice, which lost these two ways; it keeps the tagged copy now)."""
    els = json.load(open(cache('osm.json')))['elements']
    nodes = {e['id']: to_local(e['lon'], e['lat']) for e in els if e['type'] == 'node'}
    H = course.HIGHWAY
    ways = {e['id']: e for e in els if e['type'] == 'way' and e.get('tags', {}).get('ref') == H['ref']}
    assert len(ways) == H['ways'], ways.keys()
    line = linemerge([LineString([nodes[i] for i in w['nodes']]) for w in ways.values()])
    assert line.geom_type == 'LineString'
    if line.coords[0][0] > line.coords[-1][0]:
        line = LineString(list(line.coords)[::-1])
    slow = None   # no slower stretch (Stonehenge: IL 22 is 50 mph all along)
    if H.get('fast'):
        fast = [w for w in ways.values() if w['tags'].get('maxspeed') == H['fast']][0]  # the stretch that meets the town street
        slow = line.project(Point(*[nodes[i] for i in fast['nodes']][-1]))
    clipped = line.intersection(box(*area))
    if clipped.geom_type != 'LineString':
        clipped = max(clipped.geoms, key=lambda g: g.length)
    cut = line.project(Point(*clipped.coords[0]))
    return clipped.simplify(.4), None if slow is None else round(slow - cut)


ROADS_NEAR = 230.0   # m: ALL_ROADS keeps the road pieces within this of a hole's line
SIDE_ROAD_HW = 3.6   # half width of a side road in the game (index.html SIDE_HW)


def osm_cartpaths(F, roads):
    """The cart paths of a course whose paths nobody painted (course.OSM_CARTPATHS): OSM's golf=cartpath lines, each 2.4 m wide, with the gap where a
    path meets a road closed (the two path ends either side of a road, up to 30 m apart, are joined straight across, so the path is one piece through
    the crossing). Creek crossings are left open: their bridges (course.CART_BRIDGES) carry the path. Returns the path polygons, and the pieces of
    path that lie on a road (the game draws those over the road: `pathRoad`)."""
    lines = [c['line'] for c in F['cartpath_line'] if not c['tags'].get('bridge')]   # OSM's own bridge ways are left out: the game's bridge (course.CART_BRIDGES) carries the path
    road = unary_union(roads) if roads else None
    streams = unary_union([f['line'] for f in F['stream']]) if F['stream'] else None
    ends = [(i, Point(c.coords[k])) for i, c in enumerate(lines) for k in (0, -1)]
    join = []
    if road is not None:
        for a in range(len(ends)):
            for b in range(a + 1, len(ends)):
                (i, p), (j, q) = ends[a], ends[b]
                if i == j or p.distance(q) > 30:
                    continue
                seg = LineString([p, q])
                if seg.intersects(road) and not (streams is not None and seg.intersects(streams)):
                    join.append(seg)
    join += [LineString(j) for j in getattr(course, 'PATH_JOINS', [])]   # gaps closed by hand (course.PATH_JOINS)
    parts = [LineString(round_line(g.coords)) if len(g.coords) > 2 else g for g in getattr(linemerge(lines + join), 'geoms', [linemerge(lines + join)])]
    polys = [g.buffer(1.2, cap_style=2, join_style=1) for g in parts]
    decks = [LineString([(e - math.cos(math.radians(b)) * L / 2, n - math.sin(math.radians(b)) * L / 2), (e + math.cos(math.radians(b)) * L / 2, n + math.sin(math.radians(b)) * L / 2)]).buffer(1.5, cap_style=2)
             for e, n, b, L, _ in getattr(course, 'CART_BRIDGES', [])]
    if decks:   # no path polygon over a bridge's creek: the deck is the path there
        cut = unary_union(decks)
        polys = [q for g in polys for q in getattr(g.difference(cut), 'geoms', [g.difference(cut)]) if q.geom_type == 'Polygon' and not q.is_empty]
    on_road = []
    if road is not None:
        r = unary_union(parts).intersection(road.buffer(SIDE_ROAD_HW + .6))
        on_road = [g for g in getattr(r, 'geoms', [r]) if g.geom_type == 'LineString' and g.length > .5]
    return polys, on_road


def house_lots(bound, F, fair, holes):
    """Out of bounds at the property lines where houses line a hole (course.HOUSE_LOTS = the back-yard depth in m). A house's lot reaches that far past its
    walls; the lots along a street are joined (HOUSE_LOTS_JOIN m closing), so the new boundary runs straight along the row instead of scalloping round
    each house. Nothing mown, teed or green is ever cut off, and the clubhouse area (HOUSE_LOTS_EXEMPT = [(e, n, r)]) keeps its buildings in bounds.
    Returns the boundary (one polygon, holes allowed) and the stretches of it that run along a lot: the split-rail fence (`fence` in the data)."""
    depth, join = course.HOUSE_LOTS, getattr(course, 'HOUSE_LOTS_JOIN', 10)
    ex = [Point(e, n).buffer(r) for e, n, r in getattr(course, 'HOUSE_LOTS_EXEMPT', [])]
    houses = [b['poly'] for b in F['building'] if 90 <= b['poly'].area <= 1000 and not any(q.intersects(b['poly']) for q in ex)]
    lots = unary_union([h.buffer(depth, quad_segs=6) for h in houses]).buffer(join, quad_segs=6).buffer(-join, quad_segs=6)
    play = unary_union(list(fair) + [t['poly'] for t in F['tee']] + [g['poly'] for g in F['green']] + [b['poly'] for b in F['bunker']] + [Point(h['tee']).buffer(8) for h in holes] + [Point(h['green']).buffer(8) for h in holes]).buffer(7)
    lots = lots.difference(play)
    nb = bound.difference(lots)
    nb = max(getattr(nb, 'geoms', [nb]), key=lambda g: g.area)
    nb = nb.buffer(-1.5, quad_segs=6).buffer(1.5, quad_segs=6)
    nb = max(getattr(nb, 'geoms', [nb]), key=lambda g: g.area)
    for h in holes:
        for q in (Point(h['tee']), Point(h['green'])):
            assert nb.contains(q), f'house lots cut a tee or green off at {q.coords[0]}'
    edge = unary_union([nb.exterior] + list(nb.interiors)).intersection(lots.buffer(2.0))
    pieces = [g for g in getattr(edge, 'geoms', [edge]) if g.geom_type == 'LineString' and g.length >= 8]
    print(f'house lots: {len(houses)} houses, boundary {bound.area / 1e4:.1f} -> {nb.area / 1e4:.1f} ha, fence {sum(g.length for g in pieces):.0f} m in {len(pieces)} pieces')
    return nb, pieces


def side_roads(F, hw, area=course.ROAD_AREA):
    """The public roads beside the course (course.SIDE_ROADS), drawn for looks only (the ball does not touch them). At Woodbine: East Center Road along the south
    side and South Brown Road (with Chicago Street, its stretch through Stockton) along the east side. Each runs out past the map and
    stops at the middle of US 20, which both meet. Lines from OSM, ordered west to east / south to north. A road that is two carriageways
    for a stretch (Milwaukee Avenue at Adler Park) merges into several lines; each is drawn as its own road."""
    out = []
    if getattr(course, 'ALL_ROADS', False):   # Eagle Ridge: every public road, drive and service road near a hole (the game draws only what is in view)
        ok = ('residential', 'service', 'unclassified', 'tertiary', 'secondary', 'primary', 'living_street')
        near = unary_union([h['line'] for h in F['hole']]).buffer(ROADS_NEAR).intersection(box(*area))
        merged = linemerge([r['line'] for r in F['road'] if r['tags'].get('highway') in ok and not r['tags'].get('golf')])
        for line in getattr(merged, 'geoms', [merged]):
            c = line.intersection(near)
            for g in getattr(c, 'geoms', [c]):
                if g.geom_type == 'LineString' and g.length >= 12:
                    pts = list((LineString(round_line(g.coords)) if getattr(course, 'ROUND_ROADS', False) else g).simplify(.4).coords)
                    out.append(LineString(pts[::-1] if pts[0][0] + pts[0][1] > pts[-1][0] + pts[-1][1] else pts))
        return out
    for names in course.SIDE_ROADS or []:
        merged = linemerge([r['line'] for r in F['road'] if r['tags'].get('name') in names])
        for line in getattr(merged, 'geoms', [merged]):
            out += side_road(line, hw, area)
    return out


def side_road(line, hw, area):
    """One side road's line: cut where it meets the highway, clipped to the area, rounded; [] when it is outside the area."""
    if not line.intersects(box(*area)):
        return []
    x = line.intersection(hw) if hw is not None else None
    if x is not None and not x.is_empty:   # the road meets the highway: keep the long side of it, ending on the highway's centre line
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
    return [LineString(pts)]


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
    if p.geom_type == 'MultiPolygon':   # Bear Slide: an OSM water body in several parts
        return unary_union([round_pond(g, iters) for g in p.geoms])
    q = round_green(p, iters)
    c = p.centroid
    return affinity.scale(q, math.sqrt(p.area / q.area), math.sqrt(p.area / q.area), origin=c)


def smooth_line(coords, sigma, step=1.0):
    """A low-pass over an open line: resampled every `step` m and smoothed with a Gaussian of `sigma` m, the two ends held where they are."""
    from scipy.ndimage import gaussian_filter1d
    L = LineString(coords)
    if L.length < 4 * sigma:
        return list(coords)
    n = max(8, int(L.length / step))
    P = np.array([L.interpolate(L.length * i / n).coords[0] for i in range(n + 1)])
    Q = np.stack([gaussian_filter1d(P[:, k], sigma / step, mode='nearest') for k in (0, 1)], 1)
    Q[0], Q[-1] = P[0], P[-1]
    return [tuple(q) for q in Q]


def smooth_poly(p, sigma, step=1.0):
    """The same low-pass round every ring of a polygon (course.SMOOTH_MORE): wobbles and corners go, then the area is given back by an even offset so a
    green, bunker or fairway keeps its size."""
    from scipy.ndimage import gaussian_filter1d
    if p.geom_type == 'MultiPolygon':
        return unary_union([smooth_poly(g, sigma, step) for g in p.geoms])
    if p.area < 25:
        return p

    def ring(r):
        r = LineString(r.coords)
        n = max(12, int(r.length / step))
        P = np.array([r.interpolate(r.length * i / n).coords[0] for i in range(n)])
        return [tuple(q) for q in np.stack([gaussian_filter1d(P[:, k], sigma / step, mode='wrap') for k in (0, 1)], 1)]
    q = Polygon(ring(p.exterior), [ring(h) for h in p.interiors if h.length > 6 * sigma]).buffer(0)
    if q.is_empty or q.geom_type != 'Polygon':
        return p
    for _ in range(2):
        q = q.buffer((p.area - q.area) / q.length, join_style=1, quad_segs=4)
    return q.simplify(.04)


def round_line(coords, iters=3):
    """Corner cutting on an open line (the creek's centre line); the two ends stay where they are."""
    pts = list(coords)
    for _ in range(iters):
        q = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            q += [(.75 * x0 + .25 * x1, .75 * y0 + .25 * y1), (.25 * x0 + .75 * x1, .25 * y0 + .75 * y1)]
        pts = q + [pts[-1]]
    if getattr(course, 'SMOOTH_MORE', False):   # then a low-pass of 3 m on top: every mapped line (creeks, cart paths, roads) flows
        pts = smooth_line(pts, 3.0)
    return pts


def main():
    if getattr(course, 'DISC', False):   # a disc golf course: tees and baskets, no greens (disc_build.py)
        import disc_build
        return disc_build.main()
    F = osm.load()
    det = box(*DETAIL)   # a water area that is not one simple polygon (Bear Slide: Morse Reservoir, kilometres wide) is cut to the detail area and split
    F['water'] = [dict(w, poly=g) for w in F['water'] for q in [w['poly'] if w['poly'].geom_type == 'Polygon' else w['poly'].intersection(det)]
                  for g in getattr(q, 'geoms', [q]) if g.geom_type == 'Polygon' and g.area > 20]
    for hh in F['hole']:   # a green OSM tags as a tee (Bear Slide 16): where a hole line ends on no green but on a large tee polygon, that polygon is the green
        e = Point(hh['line'].coords[-1])
        if min(g['poly'].distance(e) for g in F['green']) > 25:
            t = [t for t in F['tee'] if t['poly'].distance(e) < 10 and t['poly'].area > 150]
            if t:
                t = max(t, key=lambda t: t['poly'].area)
                F['tee'].remove(t); F['green'].append(t)
                print(f'hole {hh["ref"]}: the line ends on a {t["poly"].area:.0f} m2 tee polygon and no green: taken as the green')
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
    for k, name in (('green', 'greens_painted.json'), ('water', 'water_painted.json')):   # painted on the all-in-one map (all_read.py): replace OSM's
        pp = os.path.join(OUT, name)
        if os.path.exists(pp):
            F[k] = [dict(poly=shape(g), tags={'painted': 'yes'}) for g in json.load(open(pp))]
    bdp = os.path.join(OUT, 'buildings_painted.json')   # buildings painted on the all-in-one map join OSM's (an OSM one mostly under a painted one gives way)
    bdd = os.path.join(OUT, 'buildings_detected.json')   # roofs found on the aerial that no footprint covers (buildings_detect.py)
    if os.path.exists(bdp) or os.path.exists(bdd):
        nb = [shape(g) for pth in (bdp, bdd) if os.path.exists(pth) for g in json.load(open(pth))]
        F['building'] = [b for b in F['building'] if not any(b['poly'].intersection(q).area > .5 * b['poly'].area for q in nb)] + [dict(poly=q, tags={'painted': 'yes'}) for q in nb]
    if F['water']:   # a 'roof' found on the aerial (or painted) that lies mostly on a pond is the pond's glint, not a building: Legends had two houses standing in a lake
        wu = unary_union([w['poly'] for w in F['water']])
        wet = [b for b in F['building'] if b['poly'].intersection(wu).area > .3 * b['poly'].area]
        F['building'] = [b for b in F['building'] if b not in wet]
        print(f'{len(wet)} buildings dropped for standing in water')
    for k in ('bunker', 'fairway'):   # OSM outlines (painted ones replace them below, already smoothed; tee boxes are squared below instead)
        for f in F[k]:
            f['poly'] = round_osm(f['poly'])
    if getattr(course, 'SMOOTH_MORE', False):   # every mapped outline gets the low-pass too (bunkers, tees, fairways, greens, ponds), area kept
        for k, sg in (('bunker', 1.6), ('tee', 2.0), ('fairway', 3.0), ('green', 1.6), ('water', 2.5)):
            if k == 'tee':   # tee boxes are squared below, never rounded
                continue
            for f in F[k]:
                f['poly'] = smooth_poly(f['poly'], sg)
    bpn = os.path.join(OUT, 'bunkers_painted.json')  # hand-refined bunkers (bunkers_paint.py) replace the OSM and automatic ones
    if os.path.exists(bpn):
        F['bunker'] = [dict(poly=shape(g), tags={'painted': 'yes'}) for g in json.load(open(bpn))]
    tpn = os.path.join(OUT, 'tees_painted.json')  # hand-edited tee boxes (tee_boxes_paint.py) replace the OSM ones
    if os.path.exists(tpn):
        F['tee'] = [dict(poly=shape(g), tags={'painted': 'yes'}) for g in json.load(open(tpn))]
    if getattr(course, 'SMOOTH_PAINTED', False):   # painted bunkers and tee boxes get the same low-pass as the OSM ones above (they replace OSM's after it), area kept
        for k, sg in (('bunker', 1.6), ('tee', 2.0)):
            if k == 'tee':
                continue
            for f in F[k]:
                if f['tags'].get('painted'):
                    f['poly'] = smooth_poly(f['poly'], sg)
    for f in F['tee']:   # every tee box, mapped or painted, on every course: straight edges and square corners (common.tee_rect)
        f['poly'] = tee_rect(f['poly'])
    fp0 = os.path.join(OUT, 'fairways_painted.json')  # hand-corrected fairways (fairways.py) win over OSM's (Eagle Ridge), then trace.py's (Woodbine: OSM has none)
    if os.path.exists(fp0) or not F['fairway']:
        fair = [shape(g) for g in json.load(open(fp0 if os.path.exists(fp0) else os.path.join(OUT, 'fairways.json')))]
    else:
        fair = [f['poly'] for f in F['fairway']]
        ff = os.path.join(OUT, 'fairways_fill.json')   # holes OSM maps no fairway for (Thunderhawk 1-2, Stonehenge 10, 11, 13, 15, 16, 18): trace.py's aerial fairways, cut to those holes (fairways_fill.py)
        if os.path.exists(ff):
            fill = [shape(g) for g in json.load(open(ff))]
            if getattr(course, 'FILL_CLEAN', False):   # the aerial's fairways are ragged (Stonehenge): close the notches, open away thin necks and slivers, drop small pieces, then a strong low-pass with the area kept
                fill = [q.buffer(6, quad_segs=8).buffer(-6, quad_segs=8).buffer(-4, quad_segs=8).buffer(4, quad_segs=8) for q in fill]
                fill = [g for q in fill for g in getattr(q, 'geoms', [q]) if g.geom_type == 'Polygon' and g.area > 900]
                fill = [smooth_poly(q, 7.0) for q in fill]
            fair += fill
    fair, rep = link_fairways(fair, F)
    if not os.path.exists(fp0) and F['fairway']:   # OSM fairways: round the inside corners where the link to the green meets the fairway's edge
        fair = [q.buffer(5, quad_segs=8).buffer(-5, quad_segs=8).simplify(.04) for q in fair]
    if getattr(course, 'SMOOTH_MORE', False):
        fair = [smooth_poly(q, 3.0) for q in fair]
    if getattr(course, 'FAIRWAY_OFF_WATER', False):   # no fairway over a pond (a painted edge, the smoothing and the link can all reach into one)
        wat = unary_union([w['poly'] for w in F['water']]).buffer(.3)
        fair = [g for q in fair for g in getattr(q.difference(wat), 'geoms', [q.difference(wat)]) if g.geom_type == 'Polygon' and g.area > 4]
    for ref, back in getattr(course, 'FAIRWAY_SETBACK', {}).items():   # {hole: m}: that hole's fairway stays this far from the water (ponds and creek), 10 yd = 9.144 m
        hh = [h for h in F['hole'] if h['ref'] == ref][0]
        cut = unary_union([w['poly'] for w in F['water']] + creek_pieces()).buffer(back).intersection(hh['line'].buffer(45))
        n0 = sum(q.area for q in fair)
        fair = [g for q in fair for g in getattr(q.difference(cut), 'geoms', [q.difference(cut)]) if g.geom_type == 'Polygon' and g.area > 4]
        print(f'hole {ref}: fairway kept {back:.1f} m from the water ({n0 - sum(q.area for q in fair):.0f} m2 cut)')
    for ref, off, side in [(r, o, 1) for r, o in getattr(course, 'FAIRWAY_START', {}).items()] + [(r, o, -1) for r, o in getattr(course, 'FAIRWAY_END', {}).items()]:   # FAIRWAY_END {hole: m}: the same on the tee side, the fairway ends on a straight line parallel to the creek
    # FAIRWAY_START {hole: m}: that hole's fairway starts on a straight line parallel to the creek it crosses, `off` m from the creek's centre (no point running down to the water), its corners rounded
        hl = [h for h in F['hole'] if h['ref'] == ref][0]['line']
        crk = unary_union(creek_pieces()); x = hl.intersection(crk)
        if x.is_empty:
            print(f'FAIRWAY_START: hole {ref} does not cross the creek'); continue
        c = np.array(x.centroid.coords[0])
        P = np.array([q for g in getattr(crk, 'geoms', [crk]) for q in g.exterior.coords if math.hypot(q[0] - c[0], q[1] - c[1]) < 40])
        w_, v_ = np.linalg.eigh(np.cov((P - P.mean(0)).T)); dv = v_[:, 1]; nv = np.array([-dv[1], dv[0]])   # the creek's direction there, and across it
        if np.dot(np.array(hl.coords[-1]) - c, nv) < 0:
            nv = -nv   # (across, toward the green)
        nv = nv * side   # (side -1: toward the tee)
        o = P.mean(0) + nv * off
        RN = 60.0   # the end is not a straight line: a gentle arc (a disc of this radius, wider than the fairway, touching the line at its middle), so it bulges toward the creek like a mown end
        oc = o + nv * RN
        keep = Polygon([tuple(oc - dv * 400), tuple(oc + dv * 400), tuple(oc + dv * 400 + nv * 800), tuple(oc - dv * 400 + nv * 800)]).union(Point(*oc).buffer(RN, quad_segs=16))   # the fairway's side of the new end
        area = hl.buffer(60).intersection(Point(*c).buffer(off + 40 + 2 * RN + 40))   # only round where this hole crosses the creek (a neighbouring hole's fairway on the tee side is left alone)
        out = []
        for q in fair:
            if not q.intersects(area) or q.distance(hl) > 3:   # (a neighbouring hole's fairway that the cut zone only reaches into is left alone)
                out.append(q); continue
            zone = area.difference(keep)
            if side < 0:   # an end: cut only the strip from the new line to the creek, not what lies beyond it
                fz = P.mean(0) - nv * 3
                zone = zone.intersection(Polygon([tuple(oc - dv * 400), tuple(oc + dv * 400), tuple(fz + dv * 400), tuple(fz - dv * 400)]))
            r = q.difference(zone)   # only near this hole: cut the start
            if r.area > q.area - .5:
                out.append(q); continue   # (this fairway does not reach the line: untouched)
            near = keep.boundary.buffer(8).intersection(area)   # and round the new corners (an opening of 3 m), nowhere else
            rr = r.buffer(-3, quad_segs=8).buffer(3, quad_segs=8)
            r = rr.intersection(near).union(r.difference(near.buffer(-.5))).buffer(0)   # (the two overlap by half a metre, so they join into one piece)
            out += [g for g in getattr(r, 'geoms', [r]) if g.geom_type == 'Polygon' and g.area > 4]
        print(f'hole {ref}: fairway {"starts" if side > 0 else "ends"} {off} m from the creek, parallel to it ({sum(q.area for q in fair) - sum(q.area for q in out):.0f} m2 cut)')
        fair = out
    json.dump([mapping(q) for q in fair], open(os.path.join(OUT, 'fairways_final.json'), 'w'))   # the fairways as the game gets them (to check an outline by eye)
    print('fairway -> green links (hole, gap m, area added m2):', rep)
    cp = os.path.join(OUT, 'cartpaths.json')   # the cart paths: found on the aerial and corrected by hand (cartpaths_edit.py, cartpaths_read.py); trace.py's paths.json was only fragments
    paths = [shape(g) for g in json.load(open(cp))] if os.path.exists(cp) else []
    course_poly = F['course'][0]['poly']
    dem, demZ = build_dem()
    d1, tr1 = read(cache('dem1m.tif'))
    demZ1 = lambda e, n: float(sample(d1, tr1, [e], [n])[0])
    water = unary_union([w['poly'] for w in F['water']] + creek_pieces()) if getattr(course, 'RELIEF_OFF_WATER', False) else None
    relief = build_relief(demZ, course_poly.buffer(40).bounds, course_poly.buffer(30), water)
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
    trp = os.path.join(OUT, 'trees_removed.json')   # areas painted clear of lidar trees on the all-in-one map (all_read.py)
    if os.path.exists(trp):
        clear = unary_union([shape(g) for g in json.load(open(trp))])
        n0 = len(trees)
        trees = [t for t in trees if not clear.contains(Point(t['e'], t['n']))]
        print(n0 - len(trees), 'lidar trees cleared by trees_removed.json')
    tp = os.path.join(OUT, 'trees_painted.json')  # trees added by hand-painting (trees_paint.py) on top of the lidar ones
    if os.path.exists(tp):
        trees += json.load(open(tp))
    tap = os.path.join(OUT, 'trees_aerial.json')  # crowns grown to the 2023 aerial and canopy nobody had placed (trees_aerial.py)
    if os.path.exists(tap):
        ta = json.load(open(tap))
        dk = {(g['e'], g['n']) for g in ta.get('drop', [])}
        trees = [t for t in trees if (t['e'], t['n']) not in dk]
        gd = {(g['e'], g['n']): g for g in ta['grow']}
        trees = [dict(t, d=gd[(t['e'], t['n'])]['d'], h=gd[(t['e'], t['n'])]['h']) if (t['e'], t['n']) in gd else t for t in trees]
        trees += ta['add']
        print(len(dk), 'lidar trees dropped,', sum((t['e'], t['n']) in gd for t in trees), 'crowns grown,', len(ta['add']), 'trees added by trees_aerial.json')
    tfp = os.path.join(OUT, 'trees_fill.json')   # pines and the like the other steps missed, found on the aerial in course.TREES_FILL boxes (trees_fill.py)
    if os.path.exists(tfp):
        tf = json.load(open(tfp))['add']
        trees += tf
        print(len(tf), 'trees added by trees_fill.json')
    if os.path.exists(ppn):   # the trees painted on the practice-green map stand in for any lidar tree under them
        trees = [t for t in trees if not any(math.hypot(t['e'] - q['e'], t['n'] - q['n']) < .5 * q['d'] for q in pr['trees'])] + pr['trees']
    if os.path.exists(rpn):   # the trees painted on the range map stand in for any lidar tree under them
        trees = [t for t in trees if not any(math.hypot(t['e'] - q['e'], t['n'] - q['n']) < .5 * q['d'] for q in rr['trees'])] + rr['trees']
    if getattr(course, 'TREES_OFF_TEES_GREENS', False):   # no tree stands in a tee box or on a green (the lidar sees a crown hanging over one, or a shadow, as a tree)
        keep = unary_union([f['poly'].buffer(.5) for f in F['tee'] + F['green']])
        n0 = len(trees)
        trees = [t for t in trees if not keep.contains(Point(t['e'], t['n']))]
        print(n0 - len(trees), 'trees taken out of tee boxes and greens (course.TREES_OFF_TEES_GREENS)')
    xap = os.path.join(OUT, 'trees_x_added.json')   # trees added with coloured circles on the tree guide (trees_x.py read)
    if os.path.exists(xap):
        xa = json.load(open(xap))
        trees += xa
        print(len(xa), 'trees added by trees_x_added.json')
    json.dump(trees, open(os.path.join(OUT, 'trees_all.json'), 'w'))   # every tree before the hand-marked ones are taken out (trees_x.py works on this list)
    xp = os.path.join(OUT, 'trees_x_removed.json')   # trees marked with an X on the tree guide (trees_x.py read)
    if os.path.exists(xp):
        gone = {(round(g['e'], 2), round(g['n'], 2)) for g in json.load(open(xp))}
        n0 = len(trees)
        trees = [t for t in trees if (round(t['e'], 2), round(t['n'], 2)) not in gone]
        print(n0 - len(trees), 'trees removed by trees_x_removed.json')
    for (e0, n0, e1, n1), de, dn in getattr(course, 'TREE_SHIFT', []):   # course.TREE_SHIFT = [((e0, n0, e1, n1), east m, north m)]: trees in the box moved
        for t in trees:
            if e0 <= t['e'] <= e1 and n0 <= t['n'] <= n1:
                t['e'] = round(t['e'] + de, 2); t['n'] = round(t['n'] + dn, 2)
    for (e0, n0, e1, n1), kind, k in getattr(course, 'TREE_HEIGHT', []):   # course.TREE_HEIGHT = [((e0, n0, e1, n1), kind, factor)]: trees of that kind in the box made taller (crown unchanged)
        for t in trees:
            if e0 <= t['e'] <= e1 and n0 <= t['n'] <= n1 and t['kind'] == kind:
                t['h'] = round(t['h'] * k, 1)
    water = [w['poly'] for w in F['water']]
    creek = creek_pieces()
    fp = os.path.join(OUT, 'fescue.json')
    fescue = [shape(g) for g in json.load(open(fp))] if os.path.exists(fp) else []
    bp = os.path.join(OUT, 'boundary.json')  # the hand-painted boundary (boundary.py) replaces the OSM outline as the out-of-bounds line
    bound = shape(json.load(open(bp))) if os.path.exists(bp) else round_osm(Polygon(course_poly.exterior), step=12)
    fence = []
    flp = os.path.join(OUT, 'fence_lines.json')   # painted fence lines (all_read.py): out of bounds is behind them, on the house side
    if os.path.exists(flp):
        import fence_read
        fl = [shape(g) for g in json.load(open(flp))]
        houses = unary_union([b['poly'] for b in F['building'] if 90 <= b['poly'].area <= 1000])
        play = unary_union(list(fair) + [t['poly'] for t in F['tee']] + [g['poly'] for g in F['green']] + [b['poly'] for b in F['bunker']] + [Point(h['tee']).buffer(8) for h in holes] + [Point(h['green']).buffer(8) for h in holes]).buffer(3)
        a0 = bound.area
        bound = fence_read.apply(bound, fl, houses, play)
        for h in holes:
            for q in (Point(h['tee']), Point(h['green'])):
                assert bound.contains(q), f'the fence lines cut a tee or green off at {q.coords[0]}'
        fence = [g for g in fl if g.length >= 8]
        print(f'fence lines: {len(fl)} lines, {sum(g.length for g in fl):.0f} m; boundary {a0 / 1e4:.1f} -> {bound.area / 1e4:.1f} ha')
    elif getattr(course, 'HOUSE_LOTS', 0):
        bound, fence = house_lots(bound, F, fair, holes)
    json.dump(mapping(bound), open(os.path.join(OUT, 'boundary_final.json'), 'w'))   # the out-of-bounds line as the game gets it (after fence lines / house lots)
    sp = getattr(course, 'TREE_SPEARS', None)   # tall, skinny raised-crown trees (kind 6, or sp['kind']: Legends 7, crown from 5 ft) on the course side of a road, along the stretch within `reach` m of the out-of-bounds line (course.TREE_SPEARS)
    if sp:
        rls = [r['line'] for r in F['road'] if r['tags'].get('name') == sp['road']]
        if rls:
            road = unary_union(rls)
            from shapely.ops import substring
            near = []   # the stretches of road with the out-of-bounds line within `reach` m
            for ln in getattr(road, 'geoms', [road]):
                run = None
                for s0 in np.arange(0, ln.length + 5, 5.0):
                    ok = bound.exterior.distance(ln.interpolate(min(s0, ln.length))) <= sp['reach']
                    if ok and run is None:
                        run = s0
                    if (not ok or s0 >= ln.length) and run is not None:
                        if s0 - run > 10:
                            near.append(substring(ln, run, min(s0, ln.length)))
                        run = None
            hl = unary_union([LineString(h['line']) for h in holes])
            flip = [g.buffer(150, single_sided=True).intersection(hl).length > g.buffer(-150, single_sided=True).intersection(hl).length for g in near]   # (True: the course lies on the left of the stretch as drawn)
            band = lambda w: unary_union([g.buffer(w if f else -w, single_sided=True) for g, f in zip(near, flip)])
            mown = unary_union(list(fair) + [t['poly'] for t in F['tee'] + F['green'] + F['bunker']] + list(paths) + [w['poly'] for w in F['water']] + creek_pieces() + [b['poly'] for b in F['building']]).buffer(1.5)
            sh = sp.get('shoulder', 5.8)
            conv = band(sp['convert']).difference(road.buffer(sh * .5))   # every tree on the course side within `convert` m of the road becomes a spear
            strip = band(sh + sp['into']).difference(road.buffer(sh)).difference(mown)   # and the strip from the shoulder to `into` m (15 ft) further onto the course is packed with them
            print('spear strip: road stretches', round(sum(g.length for g in near)), 'm; strip', round(strip.area), 'm2')
            spear = lambda t, u: t.update(kind=sp.get('kind', 6), h=round(sp['h'][0] + u * (sp['h'][1] - sp['h'][0]), 1), d=round(sp['d'][0] + (1 - u) * (sp['d'][1] - sp['d'][0]), 1))
            hsh = lambda e, n: (math.sin(e * 12.9898 + n * 78.233) * 43758.5453) % 1.0
            k0 = 0
            for t in trees:
                if conv.contains(Point(t['e'], t['n'])):
                    spear(t, hsh(t['e'], t['n'])); k0 += 1
            # then packed in: a jittered grid `gap` m apart, a new tree only where no tree stands within .75 gap
            from scipy.spatial import cKDTree
            kd = cKDTree([(t['e'], t['n']) for t in trees]); g = sp['gap']; add = []
            gone = json.load(open(xp)) if os.path.exists(xp) else []   # trees X'd out by hand: no spear is packed where one stood (its crown, plus half a gap)
            kg = cKDTree([(t['e'], t['n']) for t in gone]) if gone else None
            gr_ = max([max(1.5, t['d'] / 2) for t in gone], default=0) + .5 * g
            cleared = lambda e, n: kg is not None and any(math.hypot(e - gone[i]['e'], n - gone[i]['n']) < max(1.5, gone[i]['d'] / 2) + .5 * g for i in kg.query_ball_point((e, n), gr_))
            x0, y0, x1, y1 = strip.bounds
            for x in np.arange(x0, x1, g):
                for y in np.arange(y0, y1, g):
                    e, n = x + (hsh(x, y) - .5) * .6 * g, y + (hsh(y, x) - .5) * .6 * g
                    if strip.contains(Point(e, n)) and not kd.query_ball_point((e, n), .75 * g) and not cleared(e, n) and not any(math.hypot(e - a['e'], n - a['n']) < .75 * g for a in add[-60:]):
                        t = dict(e=round(e, 2), n=round(n, 2)); spear(t, hsh(e, n)); add.append(t)
            trees += add
            print(f"{sp['road']}: {k0} trees on the course side made spears, {len(add)} spears added ({strip.area / 1e4:.2f} ha strip)")
    for ed in getattr(course, 'TREE_EDIT', []):   # course.TREE_EDIT = [dict(at=(e, n), d=crown m, h=height m)]: one tree resized by hand (the nearest within 3 m); a broadleaf becomes kind 8, drawn at its own height
        i = min(range(len(trees)), key=lambda j: math.hypot(trees[j]['e'] - ed['at'][0], trees[j]['n'] - ed['at'][1]))
        t = trees[i]
        if math.hypot(t['e'] - ed['at'][0], t['n'] - ed['at'][1]) > 3:
            print('TREE_EDIT: no tree within 3 m of', ed['at']); continue
        t.update(d=ed.get('d', t['d']), h=ed.get('h', t['h']), kind=8 if t['kind'] == 0 else t['kind'])
        print('TREE_EDIT: tree at', ed['at'], 'now crown', t['d'], 'm, height', t['h'], 'm')
    if getattr(course, 'TREES_OFF_FAIRWAYS', False):   # no tree stands in a fairway (its trunk, the centre, inside one); trees painted in by hand (trees_x_added.json) stay
        fw = unary_union(list(fair)); mine = {(g['e'], g['n']) for g in json.load(open(xap))} if os.path.exists(xap) else set()
        n0 = len(trees)
        out_fw = [t for t in trees if (t['e'], t['n']) not in mine and fw.contains(Point(t['e'], t['n']))]
        trees = [t for t in trees if (t['e'], t['n']) in mine or not fw.contains(Point(t['e'], t['n']))]
        print(n0 - len(trees), 'trees taken out of the fairways (course.TREES_OFF_FAIRWAYS):', ', '.join(f"E{t['e']:.0f} N{t['n']:.0f} (kind {t['kind']}, {t['d']} m)" for t in out_fw))
    json.dump(trees, open(os.path.join(OUT, 'trees_final.json'), 'w'))   # every tree the game gets (to look one up by position)
    tq = []
    for t in trees:  # e, n, crown diameter (dm), kind * 1000 + height (dm)
        tq += [int(round(t['e'] * 10)), int(round(t['n'] * 10)), int(round(t['d'] * 10)), t['kind'] * 1000 + min(999, int(round(t['h'] * 10)))]
    if getattr(course, 'MOWN_ROUGH', False) and not fescue:
        # OSM maps the mown rough (golf=rough) as well as the fairway: deep rough is only the native grass more than 8 m outside everything mown
        mown = unary_union([r['poly'] for r in F['rough']] + list(fair) + [t['poly'] for t in F['tee']] + [g['poly'] for g in F['green']] + [b['poly'] for b in F['bunker']]).buffer(8)
        deep = Polygon(course_poly.exterior).difference(mown).buffer(-2).buffer(2).simplify(.5)
        fescue = [g for g in getattr(deep, 'geoms', [deep]) if g.geom_type == 'Polygon' and g.area > 80]
        if getattr(course, 'SMOOTH_MORE', False):
            fescue = [smooth_poly(g, 3.0) for g in fescue]
        print('deep rough from the mown area:', len(fescue), 'pieces,', round(sum(g.area for g in fescue) / 1e4, 1), 'ha')
    clumps, drains = [], []
    cjp, djp = os.path.join(OUT, 'clumps.json'), os.path.join(OUT, 'drains_painted.json')   # painted grass clumps and rock-lined drainage hazards (all_read.py): both stand on deep rough
    if os.path.exists(cjp):
        clumps = json.load(open(cjp))
    cap = os.path.join(OUT, 'clumps_added.json')   # sawgrass painted on the extras map (extras_edit.py read), added to the all-in-one map's
    if os.path.exists(cap):
        clumps = clumps + json.load(open(cap))
    if clumps:
        fescue = list(fescue) + [Point(e, n).buffer(.9 * k, quad_segs=6) for e, n, k in clumps]
    if os.path.exists(djp):
        drains = [shape(g) for g in json.load(open(djp))]
        fescue = list(fescue) + drains
    if getattr(course, 'CREEK_DEEP', 0):   # deep rough along both banks of the creek: over the dug bank (the game cuts it 2 m out from the creek ribbon) and this many m past its top (course.CREEK_DEEP = 1.524, 5 ft)
        cr = unary_union(creek_pieces())
        band = cr.buffer(2.0 + course.CREEK_DEEP + .9, quad_segs=6).intersection(bound)   # (+.9: the game feathers deep rough's edge inward by 0 to .9 m (makeRealCourse deepF); the band runs under the water, which wins, so its creek-side edge is not feathered)
        add = [g for g in getattr(band, 'geoms', [band]) if g.geom_type == 'Polygon' and g.area > 2]
        fescue = list(fescue) + add
        print(f'creek banks: {sum(g.area for g in add) / 1e4:.2f} ha of deep rough (2 m bank + {course.CREEK_DEEP} m each side)')
    if getattr(course, 'ROAD_ROW_DEEP', 0):   # deep rough under the rows of trees that line a road, and this many m beyond their crowns (course.ROAD_ROW_DEEP = 1.5, i.e. 5 ft)
        from scipy.spatial import cKDTree
        ok = ('residential', 'service', 'unclassified', 'tertiary', 'secondary', 'primary', 'living_street')
        rls = [r['line'] for r in F['road'] if r['tags'].get('highway') in ok and not r['tags'].get('golf') and r['line'].intersects(bound)]
        rnear = unary_union(rls).buffer(getattr(course, 'ROAD_ROW_REACH', 9.0)) if rls else None
        cand = [t for t in trees if rnear is not None and t['d'] >= 2.5 and rnear.contains(Point(t['e'], t['n']))]
        if cand:
            kd = cKDTree([(t['e'], t['n']) for t in cand])
            row = [t for i, t in enumerate(cand) if len(kd.query_ball_point((t['e'], t['n']), 12.0)) >= 3]   # itself and at least two more within 12 m: a row, not a lone tree
            blob = unary_union([Point(t['e'], t['n']).buffer(t['d'] / 2 + course.ROAD_ROW_DEEP, quad_segs=6) for t in row]).buffer(2.5, quad_segs=6).buffer(-2.5, quad_segs=6)
            mown = unary_union(list(fair) + [t['poly'] for t in F['tee'] + F['green'] + F['bunker']] + [q for q in paths]).buffer(1.0)
            blob = blob.difference(mown).difference(unary_union(rls).buffer(3.5)).intersection(bound)
            add = [g for g in getattr(blob, 'geoms', [blob]) if g.geom_type == 'Polygon' and g.area > 6]
            fescue = list(fescue) + add
            print(f'road tree rows: {len(row)} trees in rows, {sum(g.area for g in add) / 1e4:.2f} ha of deep rough under them (+{course.ROAD_ROW_DEEP} m)')
    if os.path.exists(ppn):
        fescue = practice_read.merge_fescue(fescue, pr)
    fescue = [g for f in fescue for g in getattr(f.intersection(bound), 'geoms', [f.intersection(bound)]) if g.geom_type == 'Polygon' and not g.is_empty]
    hw, hw_slow = highway() if course.HIGHWAY else (None, None)
    roads = side_roads(F, hw)
    road_busy = []   # per road: [cars, mph] where the course says it has steady traffic (course.TRAFFIC = {'Frank Road': dict(cars=7, mph=40)}), else 0
    for rl in roads:
        hit = 0
        for nm, tv in getattr(course, 'TRAFFIC', {}).items():
            on = sum(r['line'].intersection(rl.buffer(3)).length for r in F['road'] if r['tags'].get('name') == nm)
            if on > .5 * rl.length:
                hit = [tv['cars'], tv['mph'], tv.get('colors', [])]
        road_busy.append(hit)
    path_road = []
    if not paths and getattr(course, 'OSM_CARTPATHS', False):   # nobody painted the cart paths: OSM's, joined across the roads
        paths, path_road = osm_cartpaths(F, roads)
    rd = dict(
        name=NAME, origin=list(ORIGIN), dem=dem, holes=holes,
        feat=dict(fair=enc_polys(fair), green=enc_polys([f['poly'] for f in F['green']]), tee=enc_polys([f['poly'] for f in F['tee']]),
                  sand=enc_polys([f['poly'] for f in F['bunker']]), water=enc_polys(water), path=enc_polys(paths), creek=enc_polys(creek), fescue=enc_polys(fescue),
                  range=enc_polys([f['poly'] for f in F['driving_range']])),
        trees=b64i16(tq) if tq else '', ntrees=len(trees),
        forest=enc_polys(clip([f['poly'] for f in F['wood']])) if F['wood'] else enc_polys([]),
        orchard=enc_polys([]),
        boundary=enc_polys([bound]),
        clumps=b64i16([int(round(v * 10)) for c in clumps for v in c]) if clumps else '', drains=enc_polys(drains) if drains else '',   # grass clumps [e, n, scale] in decimetres / tenths, drainage hazards
        fence=[enc_lines([g]) for g in fence],   # split-rail fence along the lots (course.HOUSE_LOTS), one encoded line each
        buildings=enc_polys(clip([f['poly'] for f in F['building']])),
        # the lidar trees cover the whole detail area: OSM woods only count beyond it
        cover=enc_polys([area] if trees else []),
        streams=enc_lines(clip_lines([f['line'] for f in F['stream']], box(*DETAIL))),   # clipped: a stream may run on for km (Stonehenge's Flint Creek)
        highway=enc_lines([hw] if hw else []), hwSlow=hw_slow,  # the highway with traffic (Woodbine: US 20 past the north edge); hwSlow = metres from its west end where the limit drops from 55 to 35 mph
        relief=relief, prac=prac, drv=drv, roads=[enc_lines([r]) for r in roads], roadBusy=road_busy if any(road_busy) else [], pathRoad=[enc_lines([r]) for r in path_road],
        cartBridges=[[round(e, 1), round(n, 1), L, 2.6, brg] for e, n, brg, L, _ in getattr(course, 'CART_BRIDGES', [])],   # cart-path bridges: [east, north, length, width, deck bearing]
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
