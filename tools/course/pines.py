"""A southern parkland course's floor and fittings (Augusta): pine straw under the stands, azaleas in bloom along their edges, and the stone bridges.

Called by build.py when the course sets them (course.STRAW, course.STONE_BRIDGES, course.PLANTINGS); everything is in local metres.

  straw     pine straw under the trees: every pine crown (its radius plus STRAW_REACH m) and big broadleaf crown (plus STRAW_REACH_B) inside the course, gaps under STRAW_CLOSE m closed,
            less everything mown (fairway, the second cut OSM maps as golf=rough, green, tee, bunker) and the paths, ponds and creeks (each buffered
            STRAW_CLEAR m), plus any area OSM tags golf=pine straw. Run-length coded on the game's 2 m class grid (engine gr in courses.json, the
            course's ROAD_AREA): alternating off/on runs as int16, the game's GC.straw.
  bridges   OSM man_made=bridge areas (and bridge=yes paths not inside one) near water: [east, north, length, width, deck bearing (degrees from east,
            anticlockwise), name], the deck along the rectangle's long side; the game's buildStoneBridges draws each as an arched ashlar span, with a
            bronze plaque when it has a name.
  flowers   azalea clumps from course.PLANTINGS: [dict(hole, at='green'|'tee'|'line', reach m, side='behind'|'left'|'right'|'all', gap m, cols, r)]: along
            the edge of the straw (where the pines meet the turf) within `reach` of the anchor, 1.5-3.5 m into the straw, one clump every `gap` m, colour
            indices into the game's AZALEA_COLS (0 'Judge Solomon' pink, 1 'Formosa' magenta, 2 'George L. Tabor' pale pink, 3 'Mrs. G. G. Gerbing' white). Seeded, so a rebuild puts them in the same places.
"""
import json
import math

import numpy as np
from rasterio import features as rfeat
from rasterio.transform import from_origin
from shapely.geometry import LineString, Point, Polygon, mapping
from shapely.ops import linemerge, unary_union

from common import cache, course, to_local

STRAW_REACH = 2.0
STRAW_REACH_B = 1.0
STRAW_CLOSE = 3.0
STRAW_CLEAR = 1.5


def grid():
    e0, n0, e1, n1 = course.ROAD_AREA
    return e0, n0, 2.0, int(round((e1 - e0) / 2)), int(round((n1 - n0) / 2))


def straw_area(trees, mown, wet, bound):
    # beds, not a sheet: a bed runs STRAW_REACH (pines) or STRAW_REACH_B (big broadleaf) m past the crown, shrubs and small trees make none, and only
    # gaps under STRAW_CLOSE m between stands are closed (public photographs show beds round the stands with turf between them)
    crowns = unary_union([Point(t['e'], t['n']).buffer(t['d'] / 2 + (STRAW_REACH if t['kind'] == 2 else STRAW_REACH_B), quad_segs=4)
                          for t in trees if t['d'] >= 2 and (t['kind'] == 2 or (t['kind'] == 0 and t['d'] >= 3.5))])
    crowns = crowns.buffer(STRAW_CLOSE, quad_segs=4).buffer(-STRAW_CLOSE, quad_segs=4)
    osm = []
    els = json.load(open(cache('osm.json')))['elements']
    nodes = {q['id']: to_local(q['lon'], q['lat']) for q in els if q['type'] == 'node'}
    for e in els:
        if e['type'] == 'way' and e.get('tags', {}).get('golf') == 'pine straw':
            c = [nodes[i] for i in e['nodes'] if i in nodes]
            if len(c) >= 4:
                osm.append(Polygon(c).buffer(0))
    area = unary_union([crowns] + osm).intersection(bound.buffer(25))
    area = area.difference(unary_union(mown).buffer(STRAW_CLEAR, quad_segs=4)).difference(unary_union(wet).buffer(STRAW_CLEAR, quad_segs=4))
    return area


def straw_rle(area):
    e0, n0, res, W, H = grid()
    tr = from_origin(e0, n0 + H * res, res, res)   # row 0 = the north edge
    geoms = [mapping(g) for g in getattr(area, 'geoms', [area]) if not g.is_empty]
    m = rfeat.rasterize([(g, 1) for g in geoms], out_shape=(H, W), transform=tr, dtype='uint8') if geoms else np.zeros((H, W), 'uint8')
    m = m[::-1].ravel()   # the game's grid: row 0 = the south edge (n0), k = j * W + i
    runs, v, n = [], 0, 0
    for x in m:
        if x != v:
            runs.append(n); n, v = 0, x
        n += 1
        if n == 32767:
            runs.append(n); runs.append(0); n = 0
    runs.append(n)
    print(f'straw: {m.mean():.1%} of the {W} x {H} grid ({m.sum() * res * res / 1e4:.1f} ha), {len(runs)} runs')
    return runs


def stone_bridges(water, detail):
    els = json.load(open(cache('osm.json')))['elements']
    nodes = {e['id']: to_local(e['lon'], e['lat']) for e in els if e['type'] == 'node'}
    wet = unary_union(water).buffer(12)
    out, areas = [], []

    def rect(g, name):
        r = g.minimum_rotated_rectangle
        c = list(r.exterior.coords)[:4]
        s = [(math.dist(c[i], c[i + 1]), i) for i in range(2)]
        (L, i), (Wd, _) = max(s), min(s)
        a = math.degrees(math.atan2(c[i + 1][1] - c[i][1], c[i + 1][0] - c[i][0])) % 180
        p = r.centroid
        return [round(p.x, 1), round(p.y, 1), round(L, 1), round(max(Wd, 1.6), 1), round(a, 1), name]

    for e in els:
        t = e.get('tags', {})
        if e['type'] == 'way' and t.get('man_made') == 'bridge':
            c = [nodes[i] for i in e['nodes'] if i in nodes]
            if len(c) < 4:
                continue
            g = Polygon(c).buffer(0)
            if g.intersects(detail) and g.intersects(wet):
                areas.append(g)
                out.append(rect(g, t.get('name', '')))
    for e in els:
        t = e.get('tags', {})
        if e['type'] == 'way' and t.get('bridge') == 'yes' and t.get('highway') in ('path', 'footway', 'service'):
            c = [nodes[i] for i in e['nodes'] if i in nodes]
            if len(c) < 2:
                continue
            ln = LineString(c)
            if not ln.intersects(detail) or not ln.intersects(wet) or any(a.buffer(3).contains(ln) for a in areas):
                continue
            out.append(rect(ln.buffer(1.3, cap_style=2), t.get('name', '')))
    for b in out:
        print(f'  bridge {b[5] or "(no name)"}: E{b[0]:.0f} N{b[1]:.0f}, {b[2]} x {b[3]} m, deck {b[4]} deg')
    return out


def tee_rooms(tees, holes):
    """course.TEE_ROOMS -> the walled tee rooms (Augusta 13, after the user's photographs: the tee in a long grass chute, a low stone wall straight across
    the back and partway up both sides, azaleas packed in behind the wall and along both sides of the chute right up to its grass, trees close behind them,
    nothing in front). Each spec: dict(hole, near=(e, n) a point in its tee box, width m of grass between the side walls, back m from the tee's back edge to the
    wall, left/right m the side walls run forward from the back wall, chute m the grass runs on from the tee's back edge, chute_w its width at the far end,
    bed m of azaleas, trees m of trees beyond the beds, bench=(across, along) m from the tee's back middle, right +).
    Returns dicts with grass, beds, band (shapely), walls [[(e, n), ...]], bench ((e, n), deg), u (the tee's way), spec."""
    out = []
    for z in getattr(course, 'TEE_ROOMS', []):
        h = holes[z['hole'] - 1]
        c = Point(z['near'])
        tp = min(tees, key=lambda t: t.distance(c))
        rr = list(tp.minimum_rotated_rectangle.exterior.coords)[:4]
        e0, e1 = (rr[0], rr[1]), (rr[1], rr[2])
        L0, L1 = math.dist(*e0), math.dist(*e1)
        (a, b), wd = (e0, L1) if L0 >= L1 else (e1, L0)
        ux, uy = (b[0] - a[0]) / max(L0, L1), (b[1] - a[1]) / max(L0, L1)
        g = h['line'][-1]
        cx, cy = tp.centroid.x, tp.centroid.y
        if (g[0] - cx) * ux + (g[1] - cy) * uy < 0:
            ux, uy = -ux, -uy
        rx, ry = uy, -ux   # the right hand, looking out of the tee
        ln = max(L0, L1)
        ox, oy = cx - ux * ln / 2, cy - uy * ln / 2   # the middle of the tee's back edge
        P = lambda s, r: (ox + ux * s + rx * r, oy + uy * s + ry * r)
        W2, B, ch = z['width'] / 2, z['back'], z['chute']
        w2f = z.get('chute_w', z['width']) / 2
        wl = max(z['left'], z['right'])
        half = lambda s: W2 if s <= wl else W2 + (w2f - W2) * (s - wl) / max(1, ch - wl)
        ss = [-B] + [wl + (ch - wl) * k / 8 for k in range(9)]
        grass = Polygon([P(s, -half(s)) for s in ss] + [P(s, half(s)) for s in reversed(ss)])
        bd, tr = z.get('bed', 4.5), z.get('trees', 14)
        outer = grass.buffer(bd, join_style=2)
        far = Polygon([P(-B - 60, -200), P(-B - 60, 200), P(ch, 200), P(ch, -200)])   # nothing past the chute's open end
        beds = outer.difference(grass).intersection(far)
        band = grass.buffer(bd + tr, join_style=2).difference(outer.buffer(.2)).intersection(far)
        walls = [[P(z['left'], -W2), P(-B, -W2), P(-B, W2), P(z['right'], W2)]]
        bn = z.get('bench')
        bench = (P(bn[1], bn[0]), math.degrees(math.atan2(uy, ux))) if bn else None
        out.append(dict(spec=z, grass=grass, beds=beds, band=band, walls=walls, bench=bench, u=(ux, uy)))
        print(f'  tee room hole {z["hole"]}: tee {ln:.1f} x {wd:.1f} m, facing {math.degrees(math.atan2(ux, uy)):.1f} deg; dressing:')
        print('    "walls": ' + json.dumps([{"hole": z['hole'], "h": 0.55, "t": 0.5, "pts": [[round(x, 1), round(y, 1)] for x, y in w]} for w in walls]))
        if bench:
            print('    "benches": ' + json.dumps([{"hole": z['hole'], "at": [round(bench[0][0], 1), round(bench[0][1], 1)], "ang": round(bench[1], 1)}]))
    return out


def room_azaleas(rooms, rng):
    out = []
    for rm in rooms:
        z, bd = rm['spec'], rm['beds']
        x0, y0, x1, y1 = bd.bounds
        gp, cols = z.get('gap', 1.15), z.get('cols', [1, 1, 0, 2, 3])
        for gx in np.arange(x0, x1, gp):
            for gy in np.arange(y0, y1, gp):
                q = Point(gx + (rng.random() - .5) * gp * .8, gy + (rng.random() - .5) * gp * .8)
                r = z.get('r', 1.3) * (.8 + .45 * rng.random())
                if bd.contains(q) and rm['grass'].distance(q) > r * .55:
                    out.append([round(q.x, 1), round(q.y, 1), round(r, 1), int(cols[rng.integers(len(cols))])])
        print(f'  azaleas hole {z["hole"]} (tee room): {len(out)} clumps')
    return out


def room_trees(rooms, rng):
    out = []
    for rm in rooms:
        z, bd = rm['spec'], rm['band']
        x0, y0, x1, y1 = bd.bounds
        mix = z.get('kinds', [('holly', 4, 7)])
        gp = z.get('tree_gap', 4.2)
        for gx in np.arange(x0, x1, gp):
            for gy in np.arange(y0, y1, gp):
                q = Point(gx + (rng.random() - .5) * gp * .7, gy + (rng.random() - .5) * gp * .7)
                if bd.contains(q):
                    k, d, hh = mix[rng.integers(len(mix))]
                    out.append(dict(e=round(q.x, 1), n=round(q.y, 1), d=round(d * (.85 + .3 * rng.random()), 1), h=round(hh * (.85 + .3 * rng.random()), 1), kind=KINDS[k]))
        print(f'  trees hole {z["hole"]} (tee room): {len(out)}')
    return out


def flowers(area, holes, greens):
    rng = np.random.default_rng(1934)   # the first Masters
    edge = area.boundary
    out = []
    for z in getattr(course, 'PLANTINGS', []):
        h = holes[z['hole'] - 1]
        L = LineString(h['line'])
        g = Point(h['green'])
        anchor = {'green': g, 'tee': Point(h['tee']), 'line': L}[z.get('at', 'green')]
        zone = anchor.buffer(z['reach'])
        seg = edge.intersection(zone)
        segs = [s for s in getattr(seg, 'geoms', [seg]) if s.geom_type == 'LineString']
        d0 = L.coords[-2] if len(L.coords) > 1 else h['tee']
        ux, uy = g.x - d0[0], g.y - d0[1]
        ul = math.hypot(ux, uy) or 1
        ux, uy = ux / ul, uy / ul   # the way the hole plays into its green
        n0 = len(out)
        for s in segs:
            k = rng.random() * z.get('gap', 3)
            while k < s.length:
                p = s.interpolate(k)
                k += z.get('gap', 3) * (.7 + .6 * rng.random())
                dx, dy = p.x - g.x, p.y - g.y
                side = z.get('side', 'all')
                along, across = dx * ux + dy * uy, -dx * uy + dy * ux
                if side == 'behind' and along < 0 or side == 'left' and across < 0 or side == 'right' and across > 0:
                    continue
                if any(gr.distance(p) < 4 for gr in greens):
                    continue
                q = None   # step 1.5-3.5 m into the straw
                for a in np.linspace(0, 2 * math.pi, 16, endpoint=False):
                    d = 1.5 + 2 * rng.random()
                    c = Point(p.x + d * math.cos(a), p.y + d * math.sin(a))
                    if area.contains(c):
                        q = c
                        break
                if q is None:
                    continue
                cols = z.get('cols', [1, 1, 0, 2, 3])
                out.append([round(q.x, 1), round(q.y, 1), round(z.get('r', 1.1) * (.8 + .45 * rng.random()), 1), int(cols[rng.integers(len(cols))])])
        print(f'  azaleas hole {z["hole"]} ({z.get("at", "green")}, {z.get("side", "all")}, {z["reach"]} m): {len(out) - n0} clumps')
    return out


# hand-placed specimen trees (course.SPECIMENS), each a tree row with its own kind, which the game draws as that plant:
KINDS = {'dogwood_white': 5, 'dogwood_pink': 9, 'redbud': 10, 'crabapple': 11, 'magnolia': 12, 'holly': 13, 'bigoak': 14, 'palm': 15,
         'tea_olive': 16, 'peach': 17, 'juniper': 18, 'pampas': 19, 'yellow_jasmine': 20, 'carolina_cherry': 21, 'camellia': 22, 'golden_bell': 23,
         'chinese_fir': 24, 'firethorn': 25, 'nandina': 26}


def _osm_geom(node=None, way=None):
    els = json.load(open(cache('osm.json')))['elements']
    nodes = {e['id']: to_local(e['lon'], e['lat']) for e in els if e['type'] == 'node'}
    if node:
        return Point(nodes[node])
    ids = way if isinstance(way, (list, tuple)) else [way]   # several ways run end to end (Magnolia Lane: the gate stretch, then the lane)
    ls = [LineString([nodes[i] for i in next(e for e in els if e['type'] == 'way' and e['id'] == w)['nodes'] if i in nodes]) for w in ids]
    m = linemerge(ls)
    return m if m.geom_type == 'LineString' else max(m.geoms, key=lambda g: g.length)


def specimens(holes, area, mown):
    """course.SPECIMENS -> tree rows {e, n, d, h, kind}, plus the spots whose lidar trees they replace (e, n, r).

    A spec is one of:
      dict(kind, node=osm id, d, h)                              one tree on an OSM node (the Big Oak)
      dict(kind, way=osm id, count, offset, d, h, trim=(a, b))   an avenue: `count` trees in two rows `offset` m either side of an OSM way (or of
                                                                 several end to end), a m left bare at its start and b at its end (Magnolia Lane)
      dict(kind, hole, along=(f0, f1), side, n, d, h, skip)      `n` trees (less the row numbers in `skip`, from 0) at the tree line beside a hole's line, from f0 to f1 of its length, on its
                                                                 left, right or both sides (the first spot in the straw stepping out from the line, then
                                                                 1.5 m further in)
      dict(kind, hole, at='tee'|'green', side, n, d, h, reach)   `n` trees at the straw's edge within `reach` m of the tee or green, on that side
      dict(kind, hole, near='green'|'tee', n, d, h, reach)       `n` trees on the nearest stretch of the straw's edge, at least 8 m apart (a plant
                                                                 a source puts on a hole without saying where)
      dict(kind, hole, beside='green', side, gap, d, h)          one tree `gap` m off the green's edge, left or right of it as seen from the tee
    """
    rng = np.random.default_rng(1933)
    mown_u = unary_union(mown).buffer(1.0)
    out, clear = [], []

    def put(p, z, k=1.0):
        d = z['d'] * (.85 + .3 * rng.random()) * k
        h = z['h'] * (.85 + .3 * rng.random()) * k
        out.append(dict(e=round(p.x, 1), n=round(p.y, 1), d=round(d, 1), h=round(h, 1), kind=KINDS[z['kind']]))
        clear.append((p.x, p.y, max(2.0, d * .45)))

    wet = unary_union(getattr(course, '_WET', [])).buffer(3) if getattr(course, '_WET', None) else Point(0, 0).buffer(0)

    def into_straw(p, ux, uy, reach=60):
        for s in range(0, reach):
            q = Point(p.x + ux * s, p.y + uy * s)
            if area.contains(q) and not mown_u.contains(q):
                return Point(q.x + ux * 1.5, q.y + uy * 1.5)
        for s in range(0, reach):   # no tree line on that side within reach: just past the edge of the mown grass (a bed beside the fairway)
            q = Point(p.x + ux * s, p.y + uy * s)
            if not mown_u.contains(q) and not wet.contains(q):
                return Point(q.x + ux * 1.5, q.y + uy * 1.5)
        return None

    for z in getattr(course, 'SPECIMENS', []):
        n0 = len(out)
        if 'node' in z:
            put(_osm_geom(node=z['node']), z)
        elif 'near' in z:
            h = holes[z['hole'] - 1]
            c = Point(h['green'] if z['near'] == 'green' else h['tee'])
            edge = area.boundary.intersection(c.buffer(z.get('reach', 60)))
            pts = sorted([Point(q) for g in getattr(edge, 'geoms', [edge]) if g.geom_type == 'LineString' for q in g.coords], key=c.distance)
            got = []
            for q in pts:
                if len(got) >= z['n']:
                    break
                if all(q.distance(o) >= 8 for o in got):
                    ux, uy = q.x - c.x, q.y - c.y
                    ul = math.hypot(ux, uy) or 1
                    got.append(Point(q.x + ux / ul * 2, q.y + uy / ul * 2))
            for q in got:
                put(q, z)
        elif 'beside' in z:
            h = holes[z['hole'] - 1]
            L = LineString(h['line'])
            c = Point(h['green'])
            p1 = L.interpolate(L.length - 25)
            ux, uy = c.x - p1.x, c.y - p1.y
            ul = math.hypot(ux, uy) or 1
            sd = -1 if z.get('side') == 'right' else 1
            nx, ny = -uy / ul * sd, ux / ul * sd
            r0 = 0.0
            while r0 < 60 and any(gp.contains(Point(c.x + nx * r0, c.y + ny * r0)) for gp in z['_greens']):
                r0 += .5
            put(Point(c.x + nx * (r0 + z.get('gap', 5)), c.y + ny * (r0 + z.get('gap', 5))), z, 1.0)
        elif 'way' in z:
            L = _osm_geom(way=z['way'])
            a, b = z.get('trim', (0, 0))
            b = L.length - b   # trim: metres left bare at each end
            per = z['count'] // 2 + z['count'] % 2
            for row, sd in enumerate((1, -1)):
                m = per if row == 0 else z['count'] - per
                for j in range(m):
                    s = a + (b - a) * (j + .5 + (.25 if row else 0)) / m
                    p, q = L.interpolate(s), L.interpolate(min(L.length, s + 1))
                    ux, uy = q.x - p.x, q.y - p.y
                    ul = math.hypot(ux, uy) or 1
                    put(Point(p.x - uy / ul * sd * z['offset'], p.y + ux / ul * sd * z['offset']), z)
        else:
            h = holes[z['hole'] - 1]
            L = LineString(h['line'])
            sides = {'left': (1,), 'right': (-1,), 'both': (1, -1)}[z.get('side', 'both')]
            if 'along' in z:
                f0, f1 = z['along']
                for j in range(z['n']):
                    if j in z.get('skip', ()):   # (single trees of the row taken out: by their place in the row, which does not move when the straw is refit)
                        continue
                    sd = sides[j % len(sides)]
                    s = L.length * (f0 + (f1 - f0) * (j + .5) / z['n'])
                    p, q = L.interpolate(s), L.interpolate(min(L.length, s + 2))
                    ux, uy = q.x - p.x, q.y - p.y
                    ul = math.hypot(ux, uy) or 1
                    r = into_straw(p, -uy / ul * sd, ux / ul * sd, z.get('reach', 60))
                    if r is not None:
                        put(r, z)
            else:
                c = Point(h['tee'] if z['at'] == 'tee' else h['green'])
                p1 = L.interpolate(12) if z['at'] == 'tee' else L.interpolate(L.length - 12)
                ux, uy = (p1.x - c.x, p1.y - c.y) if z['at'] == 'tee' else (c.x - p1.x, c.y - p1.y)
                ul = math.hypot(ux, uy) or 1
                ux, uy = ux / ul, uy / ul
                for j in range(z['n']):
                    sd = sides[j % len(sides)]
                    t = (j // len(sides) + .5) / max(1, math.ceil(z['n'] / len(sides)))
                    if z['at'] == 'tee':   # along the side of the tee, from behind it to just ahead of it
                        a = -12 + 24 * t
                        p = Point(c.x + ux * a, c.y + uy * a)
                    else:                  # round the back of the green, from one side to the other
                        ang = math.atan2(uy, ux) + sd * (math.pi / 2) * (1 - t)
                        p = Point(c.x + 10 * math.cos(ang), c.y + 10 * math.sin(ang))
                    r = into_straw(p, -uy * sd, ux * sd, z.get('reach', 40)) if z['at'] == 'tee' else into_straw(p, (p.x - c.x) / 10, (p.y - c.y) / 10, z.get('reach', 40))
                    if r is not None:
                        put(r, z)
        print(f'  specimens {z["kind"]} ({z.get("node") or z.get("way") or "hole " + str(z.get("hole"))}): {len(out) - n0}')
    return out, clear
