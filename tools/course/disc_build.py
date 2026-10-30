"""The game's data for a disc golf course (course.DISC = True; build.py hands over to main() here).

A disc course has no greens, bunkers or painted layers: its holes are tee pads and baskets, read from out/disc_holes.json

  [{"tee": [e, n], "short": [e, n] or null, "basket": [e, n]}, ...]   one row per hole (local metres), in playing order

(disc_read.py writes it from the course's hole map). The game's 18 holes are the course's 9 played twice: holes 1-9 from the long tees,
10-18 from the short ones (a short tee left out is put on the line at the short layout's share of the hole; a course with one tee per
hole, Adler Park, sets FEET_SHORT = FEET_LONG and plays the same nine again). Each tee is a rubber mat
(1.6 x 3.6 m, square to the basket); the 'fairway' is the open, mown ground along each hole (no canopy within 9 m of the line); the
boundary is every hole's corridor, 70 m round its line; trees, water, buildings and roads come as for a golf course (lidar and OSM).

  out/rd_<key>.js   the same shape as build.py writes (install.py puts it into the game)

A course.py may also list park props (Adler Park): POOL, a fenced pool complex, becomes a 'pool' row and PLAYGROUND a 'play' row in
props (see park_props; the game draws them in realSiteMeshes).
"""
import json
import math
import os

import rasterio
from rasterio import features as rfeat
from scipy import ndimage as ndi
from shapely.geometry import LineString, Point, Polygon, box, shape
from shapely.ops import unary_union

import osm
from build import b64i16, build_dem, build_relief, enc_lines, enc_polys, read, round_osm, sample, side_roads
from common import ALTI_VAR, DETAIL, NAME, ORIGIN, OUT, RD_JS, RD_VAR, YD, cache, course, to_local

FT = .3048
MAT = (1.6, 3.6)        # a tee mat, across x along (m)
FAIR_HW = 9.0           # half-width of the mown corridor along a hole
BOUND = 70.0            # the boundary: this far round every hole's line


def mat(tee, basket):
    """The tee mat: its long side toward the basket, the throwing spot .6 m in from its front edge."""
    ux, uy = basket[0] - tee[0], basket[1] - tee[1]
    l = math.hypot(ux, uy)
    ux, uy = ux / l, uy / l
    rx, ry = uy, -ux
    a, b = MAT[0] / 2, MAT[1]
    pts = [(tee[0] + rx * s * a + ux * f, tee[1] + ry * s * a + uy * f) for s, f in ((-1, .6), (1, .6), (1, .6 - b), (-1, .6 - b))]
    return Polygon(pts)


def open_ground(hw_lines):
    """Ground with no canopy over 2 m (the lidar's chm.tif) within FAIR_HW of the holes' lines: the mown corridors."""
    with rasterio.open(cache('chm.tif')) as s:
        chm, tr = s.read(1), s.transform
    can = ndi.binary_closing(ndi.gaussian_filter(chm, 1) > 2, iterations=2)
    corr = unary_union([L.buffer(FAIR_HW) for L in hw_lines])
    m = rfeat.rasterize([(corr, 1)], out_shape=chm.shape, transform=tr, dtype='uint8').astype(bool) & ~can
    m = ndi.binary_opening(m, iterations=2)
    polys = [shape(g) for g, v in rfeat.shapes(m.astype('uint8'), mask=m, transform=tr) if v == 1]
    polys = [p.buffer(1.5).buffer(-1.5).simplify(.5) for p in polys if p.area > 60]
    return [g for p in polys for g in getattr(p, 'geoms', [p]) if g.geom_type == 'Polygon' and g.area > 60]


def osm_way(wid):
    """An OSM way's points in local metres, straight from the download."""
    els = json.load(open(cache('osm.json')))['elements']
    nodes = {e['id']: (e['lon'], e['lat']) for e in els if e['type'] == 'node' and 'lon' in e}
    way = next(e for e in els if e['type'] == 'way' and e['id'] == wid)
    return [to_local(*nodes[n]) for n in way['nodes']]


def ring(pts):
    return [[round(e, 2), round(n, 2)] for e, n in pts]


def park_props():
    """The props rows for course.POOL and course.PLAYGROUND: [kind, e, n, facing degrees, width, depth, '', extra].
    pool extra: {fence: ring (OSM), deck: ring (the pools grown 4.5 m, inside the fence), pools: [{ring, lanes}] (the OSM leisure pool first),
    slide: [[e, n, height]...] (the tower first), shades: [[e, n]...]}; play extra: {mulch: ring}."""
    rows = []
    P = getattr(course, 'POOL', None)
    if P:
        fence = Polygon(osm_way(P['fence_way']))
        pools = [dict(ring=ring(osm_way(P['water_way'])[:-1]), lanes=0)] + [dict(ring=ring(q['ring']), lanes=q.get('lanes', 0)) for q in P['pools']]
        deck = unary_union([Polygon(q['ring']).buffer(4.5, join_style=2) for q in pools]).buffer(2).buffer(-2).intersection(fence.buffer(-1))
        if deck.geom_type != 'Polygon':
            deck = max(deck.geoms, key=lambda g: g.area)
        c, (x0, y0, x1, y1) = fence.centroid, fence.bounds
        rows.append(['pool', round(c.x, 2), round(c.y, 2), 0, round(x1 - x0, 1), round(y1 - y0, 1), '',
                     dict(fence=ring(fence.exterior.coords), deck=ring(deck.simplify(.2).exterior.coords), pools=pools,
                          slide=[[round(v, 2) for v in q] for q in P['slide']], shades=[[round(v, 2) for v in q] for q in P['shades']])])
    Q = getattr(course, 'PLAYGROUND', None)
    if Q:
        m = Polygon(Q['mulch'])
        c, (x0, y0, x1, y1) = m.centroid, m.bounds
        rows.append(['play', round(c.x, 2), round(c.y, 2), Q['face'], round(x1 - x0, 1), round(y1 - y0, 1), '', dict(mulch=ring(Q['mulch']))])
    return rows


def describe(tee, basket, trees, demZ1):
    """A line for the hole card: the drop or climb, and how wooded the line is."""
    dz = (demZ1(*basket) - demZ1(*tee)) / FT
    L = LineString([tee, basket])
    near = sum(1 for t in trees if L.distance(Point(t['e'], t['n'])) < 6 + t['d'] / 2)
    bits = []
    if abs(dz) >= 6:
        bits.append(f'Plays {abs(dz):.0f} ft {"uphill" if dz > 0 else "downhill"}')
    bits.append('a tight line through the trees' if near >= 6 else 'trees along the line' if near >= 2 else 'an open line')
    return ' · '.join(bits).capitalize()


def main():
    rows = json.load(open(os.path.join(OUT, 'disc_holes.json')))
    assert len(rows) == 9, 'disc_holes.json: one row per hole, 9 holes'
    F = osm.load()
    dem, demZ = build_dem()
    d1, tr1 = read(cache('dem1m.tif'))
    demZ1 = lambda e, n: float(sample(d1, tr1, [e], [n])[0])
    trees = json.load(open(os.path.join(OUT, 'trees.json')))
    long_ft, short_ft = course.FEET_LONG, course.FEET_SHORT
    holes, tees, lines = [], [], []
    for lay in ('long', 'short'):
        for i, r in enumerate(rows):
            b = tuple(r['basket'])
            t = tuple(r['tee'])
            if lay == 'short':
                if r.get('short'):
                    t = tuple(r['short'])
                else:   # on the line, at the short layout's share of the hole
                    k = short_ft[i] / long_ft[i]
                    t = (b[0] + (t[0] - b[0]) * k, b[1] + (t[1] - b[1]) * k)
            t = (round(t[0], 2), round(t[1], 2))
            L = math.hypot(b[0] - t[0], b[1] - t[1])
            tees.append(mat(t, b))
            lines.append(LineString([t, b]))
            yd = round(L / YD)
            holes.append(dict(par=3, hcp=i + 1, len=round(L, 1), yd=yd, lens=[round(L, 1)] * 4, tee=list(t), green=[round(b[0], 2), round(b[1], 2)],
                              line=[list(t), [round(b[0], 2), round(b[1], 2)]], mk={m: list(t) for m in 'wybr'}, mkh={m: .8 for m in 'wybr'},
                              desc=describe(t, b, trees, demZ1) + (' · short tee' if lay == 'short' and abs(L - math.hypot(b[0] - r['tee'][0], b[1] - r['tee'][1])) > .5 else '')))
    fair = open_ground(lines)
    bound = round_osm(unary_union([L.buffer(BOUND) for L in lines]).buffer(10).buffer(-10).simplify(2), step=12)
    if bound.geom_type != 'Polygon':
        bound = max(bound.geoms, key=lambda g: g.area)
    relief = build_relief(demZ, bound.buffer(40).bounds, bound.buffer(30))
    area = box(*DETAIL)
    clip = lambda ps: [p.intersection(area) for p in ps if p.intersects(area)]
    # trees standing on a tee mat or within 2 m of a basket are left out (the course keeps its tees and baskets clear), and those on a
    # pool deck or playground mulch (the lidar is older than them)
    props = park_props()
    keep = unary_union([t.buffer(1.5) for t in tees] + [Point(h['green']).buffer(2.5) for h in holes]
                       + [Polygon(p[7].get('deck') or p[7]['mulch']) for p in props])
    trees = [t for t in trees if not keep.intersects(Point(t['e'], t['n']).buffer(t['d'] / 2 * .5))]
    tq = []
    for t in trees:
        tq += [int(round(t['e'] * 10)), int(round(t['n'] * 10)), int(round(t['d'] * 10)), t['kind'] * 1000 + min(999, int(round(t['h'] * 10)))]
    if getattr(course, 'WATER_CLIP', False):   # every water area, cut to the detail area (Adler Park: the Des Plaines River by holes 8 and 9)
        water = [g for w in F['water'] for g in getattr(w['poly'].intersection(area), 'geoms', [w['poly'].intersection(area)]) if g.geom_type == 'Polygon' and g.area > 20]
    else:
        water = [w['poly'] for w in F['water'] if w['poly'].area < 50000]   # the ponds by the lodge (the river's backwaters on the map's edge stay off)
    roads = side_roads(F, None)
    streams = [f['line'] for f in F['stream']]
    if getattr(course, 'WATER_CLIP', False):   # and the river's centre line, which runs on for kilometres
        streams = [g for L in streams for g in getattr(L.intersection(area), 'geoms', [L.intersection(area)]) if g.geom_type == 'LineString' and g.length > 5]
    rd = dict(
        name=NAME, origin=list(ORIGIN), dem=dem, holes=holes, disc=True,
        feat=dict(fair=enc_polys(fair), green=enc_polys([]), tee=enc_polys(tees), sand=enc_polys([]), water=enc_polys(water), path=enc_polys([]),
                  creek=enc_polys([]), fescue=enc_polys([]), range=enc_polys([])),
        trees=b64i16(tq) if tq else '', ntrees=len(trees),
        forest=enc_polys(clip([f['poly'] for f in F['wood']])) if F['wood'] else enc_polys([]), orchard=enc_polys([]),
        boundary=enc_polys([bound]), buildings=enc_polys(clip([f['poly'] for f in F['building']])),
        cover=enc_polys([area] if trees else []), streams=enc_lines(streams),
        highway=enc_lines([]), hwSlow=None, relief=relief, prac=None, drv=None, roads=[enc_lines([r]) for r in roads], props=props,
        mkc={m: c for m, c in zip('wybr', (0x2b2b2b, 0x2b2b2b, 0x2b2b2b, 0x2b2b2b))},
    )
    js = f'const {RD_VAR} = ' + json.dumps(rd, separators=(',', ':')) + ';\n' + f'const {ALTI_VAR} = {{}};\n'
    open(RD_JS, 'w').write(js)
    print(f'{os.path.basename(RD_JS)} {len(js) / 1024:.0f} KB (relief {len(relief["d"]) / 1024:.0f} KB, trees {len(trees)}, fairway pieces {len(fair)})')
    for i, h in enumerate(holes):
        print(f"{i + 1:2d} par 3 {h['len'] / FT:4.0f} ft  tee {h['tee']}  {h['desc']}")
