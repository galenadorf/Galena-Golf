"""Augusta National: one labelled map per hole, to call out items (above all trees) by number.

    python3 augusta_map.py [hole ...]      -> courses/augusta/out/maps/hole_NN.png (all 18 with no argument) and tree_index.json

Reads the data the game itself gets (out/rd_augusta.js), so a tree's number is its place in the game's tree list (1-based): the same everywhere, on every
hole's map. Numbers move when the course is rebuilt (a tree added or taken out shifts the ones after it): tree_index.json keeps number -> position/kind/size
as of this render. Each map is turned so the tee is at the bottom and the green at the top. Needs numpy, shapely, matplotlib.
"""
import base64, json, math, os, sys
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MPoly, Circle, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
CKEY = 'augusta'
CDIR = 'augusta'
COURSE = None
OUT = MAPS = None
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

KIND = {0: ('broadleaf tree (lidar)', '#5f9a4a'), 1: ('shrub / small (lidar)', '#9bc26a'), 2: ('pine / conifer (lidar)', '#1f5d4a'),
        3: ('kind 3', '#b0b0b0'), 4: ('kind 4', '#b0b0b0'),
        5: ('white dogwood', '#ffffff'), 9: ('pink dogwood', '#ff9ec0'), 10: ('redbud', '#c040a0'), 11: ('crabapple', '#e8708a'),
        12: ('Magnolia Lane magnolia', '#2e7d32'), 13: ('holly', '#b3261e'), 14: ('Big Oak', '#7a5230'), 15: ('palm', '#d4a017'),
        16: ('tea olive', '#7fae6a'), 17: ('flowering peach', '#f4a6a6'), 18: ('juniper', '#2f6b6b'), 19: ('pampas grass', '#e6dca8'),
        20: ('yellow jasmine', '#f2d21a'), 21: ('Carolina cherry', '#8a2a4a'), 22: ('camellia', '#d6336c'), 23: ('golden bell', '#e8c500'),
        24: ('Chinese fir', '#6b8e23'), 25: ('firethorn', '#f06a1c'), 26: ('nandina', '#a0402a')}


def load():
    s = open(os.path.join(OUT, f'rd_{CKEY}.js')).read()
    d, _ = json.JSONDecoder().raw_decode(s[s.find('{'):])
    return d


def i16(b):
    return np.frombuffer(base64.b64decode(b), '<i2').astype(int) if b else np.zeros(0, int)


def polys(b):
    """build.py enc_polys: count, then per polygon its ring count, per ring its point count then dx, dy (dm). Returns shapely polygons."""
    a = i16(b)
    if not len(a):
        return []
    k, out = 1, []
    for _ in range(a[0]):
        nr = a[k]; k += 1; rings = []
        for _ in range(nr):
            n = a[k]; k += 1; x = y = 0; r = []
            for _ in range(n):
                x += a[k]; y += a[k + 1]; k += 2; r.append((x / 10, y / 10))
            rings.append(r)
        p = Polygon(rings[0], rings[1:]).buffer(0)
        out.append(p)
    return out


def geoms(p):
    return list(getattr(p, 'geoms', [p]))


def draw_poly(ax, p, **kw):
    for g in geoms(p):
        if g.is_empty or g.geom_type != 'Polygon':
            continue
        ax.add_patch(MPoly(np.array(g.exterior.coords), closed=True, **kw))
        for r in g.interiors:
            ax.add_patch(MPoly(np.array(r.coords), closed=True, fc='white', ec=kw.get('ec'), lw=kw.get('lw', 1), zorder=kw.get('zorder', 1) + .01))


def main(only):
    d = load()
    os.makedirs(MAPS, exist_ok=True)
    T = i16(d['trees']).reshape(-1, 4)
    trees = [dict(id=i + 1, e=t[0] / 10, n=t[1] / 10, d=t[2] / 10, kind=int(t[3] // 1000), h=(t[3] % 1000) / 10) for i, t in enumerate(T)]
    json.dump(trees, open(os.path.join(MAPS, 'tree_index.json'), 'w'))
    TE = np.array([[t['e'], t['n']] for t in trees])
    L = {k: polys(d['feat'][k]) for k in ('fair', 'green', 'tee', 'sand', 'water', 'path', 'creek', 'fescue')}
    boundary = polys(d['boundary']); bldg = polys(d['buildings'])
    straw = []
    sp = os.path.join(OUT, 'straw.json')
    if os.path.exists(sp):
        from shapely.geometry import shape
        straw = [shape(g) for g in json.load(open(sp))]
    straw = unary_union(straw) if straw else None
    flowers = json.load(open(os.path.join(OUT, 'flowers.json'))) if os.path.exists(os.path.join(OUT, 'flowers.json')) else []
    courses = json.load(open(os.path.join(REPO, 'courses', 'courses.json')))
    courses = courses['courses'] if isinstance(courses, dict) else courses
    scene = [c for c in courses if c['key'] == CKEY][0].get('scene', {})
    dress = scene.get('dressing', {})
    AZ = ['#e07a9a', '#c0206a', '#f0c8dc', '#ffffff']
    water_u = unary_union(L['water'] + L['creek']) if L['water'] + L['creek'] else None
    for hi, h in enumerate(d['holes']):
        n = hi + 1
        if only and n not in only:
            continue
        tee = np.array(h['tee']); gr = np.array(h['green']); line = [np.array(p) for p in h['line']]
        v = gr - tee; ang = math.pi / 2 - math.atan2(v[1], v[0]); c, s = math.cos(ang), math.sin(ang)

        def R(p):   # local metres -> picture (tee at the bottom, green at the top)
            return (c * (p[0] - tee[0]) - s * (p[1] - tee[1]), s * (p[0] - tee[0]) + c * (p[1] - tee[1]))

        def Rg(g):
            from shapely import affinity
            return affinity.rotate(affinity.translate(g, -tee[0], -tee[1]), math.degrees(ang), origin=(0, 0))
        hl = LineString([tuple(p) for p in line])
        corridor = hl.buffer(85)
        x0, y0, x1, y1 = Rg(corridor).bounds
        x0 -= 5; x1 += 5; y0 -= 5; y1 += 5
        W, H = x1 - x0, y1 - y0
        ppm = min(6.0, 5400 / max(W, H))
        keyw = 470
        fw, fh = (W * ppm + keyw) / 100, max(H * ppm / 100, 9.0)
        fig = plt.figure(figsize=(fw, fh), dpi=100)
        ax = fig.add_axes([0, 0, W * ppm / (W * ppm + keyw), 1])
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal'); ax.axis('off')
        ax.add_patch(Rectangle((x0, y0), W, H, fc='#cfe3b0', ec='none', zorder=0))
        view = box(*[*(Rg(corridor).bounds)])
        def inview(g):
            return Rg(g).intersects(view)
        # the ground
        for g in L['fescue']:
            if inview(g): draw_poly(ax, Rg(g), fc='#e3d38a', ec='none', alpha=.7, zorder=1)
        if straw is not None:
            draw_poly(ax, Rg(straw.intersection(corridor.buffer(10))), fc='#c9a979', ec='none', alpha=.45, zorder=1.1)
        for g in L['fair']:
            if inview(g): draw_poly(ax, Rg(g), fc='#8fd16a', ec='#4a8a30', lw=.8, zorder=2)
        for g in L['path']:
            if inview(g): draw_poly(ax, Rg(g), fc='#b9b9b9', ec='none', zorder=2.2)
        for g in L['water'] + L['creek']:
            if inview(g): draw_poly(ax, Rg(g), fc='#6fb4e8', ec='#2f7fb8', lw=.8, zorder=2.5)
        for g in L['tee']:
            if inview(g): draw_poly(ax, Rg(g), fc='#5fc03a', ec='#2f6a1c', lw=1, zorder=3)
        for g in L['green']:
            if inview(g): draw_poly(ax, Rg(g), fc='#37a83a', ec='#17601a', lw=1.2, zorder=3)
        items = []   # (label, what, where) for the key
        sand = [g for g in L['sand'] if inview(g)]
        for k, g in enumerate(sand):
            draw_poly(ax, Rg(g), fc='#f6e7b4', ec='#b59a50', lw=1, zorder=3.2)
            q = Rg(g).representative_point(); ax.text(q.x, q.y, f'B{k + 1}', ha='center', va='center', fontsize=9, weight='bold', color='#6b5310', zorder=9)
            items.append((f'B{k + 1}', 'bunker', ''))
        for k, g in enumerate(bldg):
            if inview(g):
                draw_poly(ax, Rg(g), fc='#a05a3a', ec='#5a2f1a', lw=1, zorder=4)
                q = Rg(g).representative_point(); ax.text(q.x, q.y, f'H{k + 1}', ha='center', va='center', fontsize=8, color='white', weight='bold', zorder=9)
                items.append((f'H{k + 1}', 'building', ''))
        for k, b in enumerate(d.get('bridges', [])):
            q = R(b[:2])
            if x0 < q[0] < x1 and y0 < q[1] < y1:
                a2 = math.radians(b[4]) + ang
                dx, dy = math.cos(a2) * b[2] / 2, math.sin(a2) * b[2] / 2
                ax.plot([q[0] - dx, q[0] + dx], [q[1] - dy, q[1] + dy], color='#6b6b6b', lw=max(3, b[3] * ppm / 100 * 72 * .5), solid_capstyle='butt', zorder=4)
                ax.text(q[0], q[1], f'BR{k + 1}', fontsize=8, weight='bold', ha='center', va='bottom', zorder=9)
                items.append((f'BR{k + 1}', 'stone bridge', b[5]))
        # azaleas
        pts = [(f[0], f[1], f[2], f[3]) for f in flowers]
        na = 0
        for e, nn, r, col in pts:
            q = R((e, nn))
            if x0 < q[0] < x1 and y0 < q[1] < y1:
                ax.add_patch(Circle(q, max(r, .8), fc=AZ[int(col) % 4], ec='#802050', lw=.4, zorder=5)); na += 1
        # trees
        sel = np.where((np.abs(TE[:, 0] - tee[0]) < 1e5))[0]
        pr = np.array([R(p) for p in TE])
        inb = (pr[:, 0] > x0) & (pr[:, 0] < x1) & (pr[:, 1] > y0) & (pr[:, 1] < y1)
        kinds_here = {}
        fs = max(4.2, min(7.5, ppm * 1.25))
        for t, q, ok in zip(trees, pr, inb):
            if not ok: continue
            if not corridor.buffer(10).contains(Point(t['e'], t['n'])): continue
            col = KIND.get(t['kind'], ('?', '#b0b0b0'))[1]
            kinds_here[t['kind']] = kinds_here.get(t['kind'], 0) + 1
            ax.add_patch(Circle(q, max(t['d'] / 2, .8), fc=col, ec='#222', lw=.5, alpha=.55, zorder=6))
            ax.add_patch(Circle(q, .35, fc='black', zorder=6.5))
            ax.text(q[0], q[1] + max(t['d'] / 2, .8) * .15, str(t['id']), fontsize=fs, ha='center', va='bottom' if t['d'] < 6 else 'center', color='black', zorder=8,
                    bbox=dict(boxstyle='square,pad=.05', fc='white', ec='none', alpha=.55))
        # the hole: line, tees, markers, pins
        pl = [R(p) for p in line]
        ax.plot([p[0] for p in pl], [p[1] for p in pl], color='#d62828', lw=1.2, ls='--', zorder=7, alpha=.8)
        mk = {'w': ('Masters (play)', '#1f5f3a'), 'y': ('Member', '#d9b23a'), 'b': ('Forward', '#f2f2f2'), 'r': ('Short', '#c0392b')}
        for kk, (nm, col) in mk.items():
            if kk not in h.get('mk', {}): continue
            q = R(h['mk'][kk]); ax.plot(*q, 'o', ms=8, mfc=col, mec='black', zorder=9)
        # pins (four sheets) on the green
        gpoly = unary_union([g for g in L['green'] if g.distance(Point(gr)) < 25])
        if not gpoly.is_empty and h.get('pins'):
            a_vec = np.array(gr) - np.array(line[-2]); a_vec = a_vec / (np.linalg.norm(a_vec) or 1)
            cen = np.array(gpoly.centroid.coords[0]); pa = np.array([-a_vec[1], a_vec[0]])
            for gg in geoms(gpoly):
                pass
            pts_g = np.array(gpoly.exterior.coords) if gpoly.geom_type == 'Polygon' else np.array(max(geoms(gpoly), key=lambda g: g.area).exterior.coords)
            sv = (pts_g - cen) @ a_vec; s0, s1 = sv.min(), sv.max()
            for pi, (ps, pl_) in enumerate(h['pins']):
                sc = s0 + ps * (s1 - s0)
                ln = LineString([tuple(cen + a_vec * sc - pa * 60), tuple(cen + a_vec * sc + pa * 60)]).intersection(gpoly)
                if ln.is_empty: continue
                bb = np.array([p for g in geoms(ln) for p in g.coords])
                lat = (bb - cen) @ pa; i0, i1 = lat.argmin(), lat.argmax()
                # lateral measured to the right of the approach (pa points left), as the game does
                pt = bb[i1] + (bb[i0] - bb[i1]) * pl_
                q = R(pt)
                ax.plot(*q, marker='*', ms=11, mfc='#ffd400', mec='black', zorder=10)
                ax.text(q[0] + 2, q[1], f'P{pi + 1}', fontsize=8, weight='bold', zorder=10)
        # tournament dressing near the hole
        for k, t in enumerate(dress.get('towers', [])):
            q = R(t)
            if x0 < q[0] < x1 and y0 < q[1] < y1:
                ax.add_patch(Rectangle((q[0] - 2, q[1] - 2), 4, 4, fc='#23432c', ec='white', lw=.8, zorder=9)); ax.text(q[0] + 3, q[1], f'TV{k + 1}', fontsize=8, color='#23432c', weight='bold', zorder=9)
                items.append((f'TV{k + 1}', 'TV tower', ''))
        for k, b in enumerate(dress.get('boards', [])):
            q = R(b['at'])
            if x0 < q[0] < x1 and y0 < q[1] < y1:
                ax.plot(*q, 's', ms=8, mfc='#f7f3e0', mec='#23432c', zorder=9); ax.text(q[0] + 3, q[1], f'SB{k + 1}', fontsize=8, weight='bold', zorder=9)
                items.append((f'SB{k + 1}', 'scoreboard' + (' (estimated place)' if b.get('est') else ''), ''))
        for k, st in enumerate(dress.get('stands', [])):
            if st['hole'] == n or n in [x for x in st.get('also', [])]:
                hh = d['holes'][st['hole'] - 1]; Ln = hh['line']
                end = Ln[0] if st['at'] == 'tee' else Ln[-1]; prev = Ln[1] if st['at'] == 'tee' else Ln[-2]
                u = np.array(end) - np.array(prev); u = u / (np.linalg.norm(u) or 1)
                dv = u
                if st['side'] == 'left': dv = np.array([-u[1], u[0]])
                elif st['side'] == 'right': dv = np.array([u[1], -u[0]])
                if st['at'] == 'tee' and st['side'] != 'behind': dv = -dv
                q = R(np.array(end) + dv * (st['off'] + 4))
                if x0 < q[0] < x1 and y0 < q[1] < y1:
                    ax.plot(*q, 'D', ms=11, mfc='#2c5a3a', mec='white', zorder=9); ax.text(q[0] + 3, q[1], f'GS{k + 1}', fontsize=8, weight='bold', zorder=9)
                    items.append((f'GS{k + 1}', f'grandstand (hole {st["hole"]} {st["at"]}, {st["side"]})', ''))
        # the key, drawn in pixels (x 0..keyw, y from the top down)
        kx = W * ppm / (W * ppm + keyw)
        kax = fig.add_axes([kx, 0, 1 - kx, 1]); kax.axis('off'); PH = fh * 100
        kax.set_xlim(0, keyw); kax.set_ylim(PH, 0)
        y = 14
        def line_(txt, size=9, weight='normal', col='black', x=14, gap=None):
            nonlocal y
            kax.text(x, y, txt, fontsize=size, weight=weight, color=col, va='top'); y += gap or size * 1.9
        def sw(kind, fc, ec='#444', ms=9):
            if kind == 'c': kax.add_patch(Circle((26, y + 7), 7, fc=fc, ec=ec, lw=.6))
            elif kind == 'r': kax.add_patch(Rectangle((16, y), 22, 14, fc=fc, ec=ec, lw=.5))
            elif kind == 'l': kax.plot([14, 40], [y + 7, y + 7], color=fc, ls='--')
            elif kind == '*': kax.plot(26, y + 7, '*', ms=12, mfc=fc, mec='black')
        def row(kind, fc, txt, ec='#444'):
            nonlocal y
            sw(kind, fc, ec); kax.text(50, y, txt, fontsize=8.5, va='top'); y += 18
        line_(f'{CKEY.upper()} - hole {n}: {h.get("nm", "")}', 12, 'bold')
        line_(f'par {h["par"]}, {h["yd"]} yd (Masters tees)', 10)
        line_(h.get('desc', ''), 7.5, col='#444', x=14, gap=22)
        line_('TREES: the number is printed on each, crown drawn to size', 9, 'bold')
        for kd, cnt in sorted(kinds_here.items()):
            nm, col = KIND.get(kd, ('?', '#b0b0b0')); row('c', col, f'{nm}  ({cnt})', '#222')
        y += 6; line_('GROUND', 9, 'bold')
        for nm, fc in [('fairway', '#8fd16a'), ('tee box', '#5fc03a'), ('green', '#37a83a'), ('bunker (B#)', '#f6e7b4'), ('water / creek', '#6fb4e8'), ('cart path', '#b9b9b9'),
                       ('deep rough / fescue', '#e3d38a'), ('pine straw', '#c9a979'), ('rough / first cut', '#cfe3b0')]:
            row('r', fc, nm)
        y += 6; line_('MARKS', 9, 'bold')
        row('l', '#d62828', 'line of play (tee to green)')
        for nm, col in [('Masters tee (the one played)', '#1f5f3a'), ('Member tee', '#d9b23a'), ('Forward tee', '#f2f2f2'), ('Short tee', '#c0392b')]:
            row('c', col, nm, 'black')
        row('*', '#ffd400', 'P1-P4: hole locations, Masters rounds 1-4')
        row('c', '#e07a9a', f'azalea clump ({na} on this map)', '#802050')
        if items:
            y += 6; line_('OTHER ITEMS ON THIS MAP', 9, 'bold'); seen = set()
            for lab, what, note in items:
                if lab in seen: continue
                seen.add(lab); line_(f'{lab}: {what}' + (f' - {note}' if note else ''), 8, gap=15)
        y += 8
        line_(f"{sum(kinds_here.values())} trees on this map; a number is the tree's place in the game's list.", 7.5, col='#444', gap=15)
        line_('Tee at the bottom, green at the top; 50 m scale bar bottom left.', 7.5, col='#444')
        # a 50 m scale bar and a north arrow
        ax.plot([x0 + 8, x0 + 58], [y0 + 8, y0 + 8], color='black', lw=3, zorder=11); ax.text(x0 + 33, y0 + 12, '50 m', ha='center', fontsize=8, zorder=11)
        na_ = R((tee[0], tee[1])); nv = (c * 0 - s * 1, s * 0 + c * 1)
        ax.annotate('N', xy=(x0 + 20 + nv[0] * 20, y0 + 40 + nv[1] * 20), xytext=(x0 + 20, y0 + 40), arrowprops=dict(arrowstyle='->', lw=1.5), fontsize=9, ha='center', zorder=11)
        out = os.path.join(MAPS, f'hole_{n:02d}.png')
        fig.savefig(out, dpi=100)
        plt.close(fig)
        print(out, f'{int(fw * 100)}x{int(fh * 100)}', sum(kinds_here.values()), 'trees')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args and not args[0].isdigit():
        CKEY = args.pop(0)
    COURSE = os.path.join(HERE, 'courses', CKEY if os.path.isdir(os.path.join(HERE, 'courses', CKEY)) else CKEY)
    OUT = os.path.join(COURSE, 'out'); MAPS = os.path.join(OUT, 'maps')
    main({int(a) for a in args})
