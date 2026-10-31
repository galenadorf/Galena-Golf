"""Fairways for the holes OSM maps none for: trace.py's aerial fairways (out/fairways.json) within 35 m of each such par 4/5 hole line, written to out/fairways_fill.json for build.py. Usage: fairways_fill.py --course <key> (run trace.py first)."""
import sys, json, os
c = sys.argv[sys.argv.index('--course') + 1] if '--course' in sys.argv else sys.argv[1]
sys.argv = ['x', '--course', c]
sys.path.insert(0, '.')
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
import osm
from common import OUT
F = osm.load()
tr = [shape(g) for g in json.load(open(os.path.join(OUT, 'fairways.json')))]
osmf = unary_union([f['poly'] for f in F['fairway']])
out = []
for h in sorted(F['hole'], key=lambda h: h['ref']):
    L = h['line']
    if h['par'] < 4 or any(f['poly'].distance(L) < 12 and f['poly'].area > 2000 for f in F['fairway']):
        continue
    corr = L.buffer(35)
    got = 0
    q = unary_union([p.intersection(corr) for p in tr]).buffer(9).buffer(-9).buffer(-2).buffer(2).simplify(.4)   # close the shadow gaps, smooth the edge
    q = q.difference(osmf.buffer(1))
    for g in getattr(q, 'geoms', [q]):
        if g.area >= 300 and g.geom_type == 'Polygon':
            out.append(g); got += g.area
    print('hole', h['ref'], 'par', h['par'], 'filled m2', round(got))
json.dump([mapping(g) for g in out], open(os.path.join(OUT, 'fairways_fill.json'), 'w'))
