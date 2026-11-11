"""Briar Leaf Golf Club has no hole lines or tee boxes in OpenStreetMap (only its 19 greens, bunkers, a few fairways and the cart paths), so its holes are a BEST GUESS:
the order of the greens (ORDER below, indices into osm.py's green list) was found by a search that matches each hole's length on the scorecard to the distance between
consecutive greens (no hole line crossing another, hole 1 near the clubhouse, the one green left over being the practice green beside the clubhouse and range). Each hole's tee box is put
on the line back from its green toward the previous green, at the played tee's length (at most 35 m past the previous green). Writes courses/briar_leaf/extra.json (read by osm.py's EXTRA_FILE).
Replace ORDER (or the file) when the real routing is known.   Run:  python briar_holes.py --course briar_leaf"""
import json
import math
import os

import osm
from common import COURSE_DIR, course

ORDER = json.load(open(os.path.join(COURSE_DIR, 'order.json')))['order'] if os.path.exists(os.path.join(COURSE_DIR, 'order.json')) else None
CLUB = (-324.0, 132.0)   # the clubhouse (the building beside the parking lot)
YD = .9144


def main():
    course.EXTRA_FILE = None; course.OSM_HOLES = True   # the green list as OpenStreetMap has it (the order indices refer to it), not what the extra file leaves
    F = osm.load()
    g = [(f['poly'].centroid.x, f['poly'].centroid.y) for f in F['green']]
    holes, tees = [], []
    for h, gi in enumerate(ORDER):
        G = g[gi]; P = CLUB if h == 0 else g[ORDER[h - 1]]
        d = math.hypot(G[0] - P[0], G[1] - P[1]); ux, uy = (P[0] - G[0]) / d, (P[1] - G[1]) / d
        L = course.TEES['silver'][2][h] * YD
        T = min(L * .97, d + 35)
        if abs(T - d) < 30:   # never on the previous green: at least 30 m clear of it
            T = d + 30 if L * .97 >= d else max(40, d - 30)
        t = (G[0] + ux * T, G[1] + uy * T)
        holes.append(dict(ref=h + 1, par=course.PAR[h], hcp=course.HCP[h], line=[[round(t[0], 1), round(t[1], 1)], [round(G[0], 1), round(G[1], 1)]]))
        vx, vy = -ux, -uy   # down the hole
        pts = [(t[0] + vx * a - vy * b, t[1] + vy * a + vx * b) for a, b in ((-4, -6), (4, -6), (4, 6), (-4, 6))]
        tees.append([[round(x, 1), round(y, 1)] for x, y in pts])
        print(f'hole {h + 1}: green {gi}, card {course.TEES["silver"][2][h]} yd, line {math.hypot(G[0] - t[0], G[1] - t[1]) / YD:.0f} yd, prev-green gap {d / YD:.0f} yd')
    # a mown corridor (28 m wide, 30 m short of the green and 30 m out from the tee) for each hole no OSM fairway lies along
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    osm_f = unary_union([f['poly'] for f in F['fairway']]); fair = []
    for hh in holes:
        ln = LineString(hh['line']); mid = ln.interpolate(.5, normalized=True)
        if ln.length < 90 or osm_f.distance(mid) < 25 or osm_f.intersection(ln).length > .35 * ln.length:
            continue
        core = LineString([ln.interpolate(30), ln.interpolate(ln.length - 28)]).buffer(14)
        fair.append([[round(x, 1), round(y, 1)] for x, y in core.exterior.coords])
    print(len(fair), 'corridors added')
    json.dump(dict(hole=holes, tee=tees, fairway=fair), open(os.path.join(COURSE_DIR, 'extra.json'), 'w'))


if __name__ == '__main__':
    main()
