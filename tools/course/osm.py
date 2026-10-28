"""OpenStreetMap features of the course as shapely geometry in local metres."""
import json
from collections import defaultdict

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, polygonize

from common import cache, course, to_local


def load():
    els = json.load(open(cache('osm.json')))['elements']
    nodes = {e['id']: to_local(e['lon'], e['lat']) for e in els if e['type'] == 'node'}
    ways = {e['id']: e for e in els if e['type'] == 'way'}
    tagged_nodes = [e for e in els if e['type'] == 'node' and e.get('tags')]
    rels = [e for e in els if e['type'] == 'relation']

    def coords(w):
        return [nodes[i] for i in w['nodes'] if i in nodes]

    def area(w):
        c = coords(w)
        if len(c) < 4 or w['nodes'][0] != w['nodes'][-1]:
            return None
        p = Polygon(c)
        return p if p.is_valid else p.buffer(0)

    F = defaultdict(list)
    for w in ways.values():
        t = w.get('tags', {})
        g = t.get('golf')
        if g == 'hole':
            F['hole'].append(dict(line=LineString(coords(w)), ref=int(t['ref']), par=int(t['par']), hcp=int(t.get('handicap', 0)), tags=t))
            continue
        if g in ('green', 'tee', 'bunker', 'driving_range', 'fairway', 'rough', 'cartpath', 'water_hazard', 'lateral_water_hazard'):
            p = area(w)
            if p is not None:
                F[g].append(dict(poly=p, tags=t))
            elif g == 'cartpath':
                F['cartpath_line'].append(dict(line=LineString(coords(w)), tags=t))
            continue
        if t.get('leisure') == 'golf_course':
            F['course'].append(dict(poly=area(w), tags=t, id=w['id']))
        elif t.get('natural') == 'water' or t.get('water') or t.get('landuse') in ('reservoir', 'basin'):
            p = area(w)
            if p is not None:
                F['water'].append(dict(poly=p, tags=t))
        elif t.get('natural') in ('wood', 'scrub') or t.get('landuse') == 'forest':
            p = area(w)
            if p is not None:
                F['wood'].append(dict(poly=p, tags=t))
        elif 'building' in t:
            p = area(w)
            if p is not None:
                F['building'].append(dict(poly=p, tags=t))
        elif t.get('waterway') in ('stream', 'ditch', 'drain', 'river'):
            F['stream'].append(dict(line=LineString(coords(w)), tags=t))
        elif 'highway' in t:
            c = coords(w)
            if len(c) >= 2:
                F['road'].append(dict(line=LineString(c), tags=t))
        elif t.get('landuse'):
            p = area(w)
            if p is not None:
                F['landuse'].append(dict(poly=p, tags=t))
    for n in tagged_nodes:
        t = n['tags']
        if t.get('golf') == 'pin':
            F['pin'].append(dict(pt=Point(nodes[n['id']]), tags=t))
        elif t.get('natural') == 'tree':
            F['tree'].append(dict(pt=Point(nodes[n['id']]), tags=t))
    # multipolygon relations (woods, water) built from their member ways
    for r in rels:
        t = r.get('tags', {})
        if t.get('type') != 'multipolygon':
            continue
        lines = [LineString(coords(ways[m['ref']])) for m in r['members'] if m['type'] == 'way' and m['ref'] in ways and m['role'] == 'outer']
        polys = list(polygonize(unary_union(lines)))
        if not polys:
            continue
        p = unary_union(polys)
        key = 'water' if (t.get('natural') == 'water' or t.get('water')) else 'wood' if (t.get('natural') == 'wood' or t.get('landuse') == 'forest') else None
        if key:
            F[key].append(dict(poly=p, tags=t))
    if course.OSM_WAY:   # the course's own outline, and only its holes (a resort's other courses may be in the download too)
        F['course'] = [c for c in F['course'] if c['id'] == course.OSM_WAY]
        assert len(F['course']) == 1, f'OSM way {course.OSM_WAY} (course.OSM_WAY) is not a leisure=golf_course in osm.json'
        cp = F['course'][0]['poly'].buffer(30)
        F['hole'] = [h for h in F['hole'] if cp.contains(h['line'].interpolate(.5, normalized=True))]
    F['hole'].sort(key=lambda h: h['ref'])
    return F


if __name__ == '__main__':
    F = load()
    for k, v in sorted(F.items()):
        print(f'{k:14s} {len(v)}')
