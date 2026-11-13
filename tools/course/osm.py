"""OpenStreetMap features of the course as shapely geometry in local metres."""
import json
import os
from collections import defaultdict

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, polygonize

from common import COURSE_DIR, cache, course, to_local


def load():
    els = json.load(open(cache('osm.json')))['elements']
    nodes = {e['id']: to_local(e['lon'], e['lat']) for e in els if e['type'] == 'node'}
    ways = {}
    for e in els:   # Overpass may list a way twice (the second copy, from '>; out skel', has no tags): keep the tagged one
        if e['type'] == 'way' and (e['id'] not in ways or e.get('tags')):
            ways[e['id']] = e
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
            F['hole'].append(dict(line=LineString(coords(w)), ref=int(t['ref']), par=int(t.get('par', 4)), hcp=int(t.get('handicap', 0)), tags=t, id=w['id']))
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
        elif t.get('highway') == 'path' and getattr(course, 'PATHS_ARE_CARTPATHS', False) and t.get('surface') in ('paved', 'asphalt', 'concrete'):   # Galena: OSM maps the cart paths as private paved highway=path
            F['cartpath_line'].append(dict(line=LineString(coords(w)), tags=t))
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
        if t.get('leisure') == 'golf_course':   # a course mapped as a multipolygon relation (Fossil Trace): OSM_WAY is the relation's id
            F['course'].append(dict(poly=p, tags=t, id=r['id']))
            continue
        if getattr(course, 'OSM_GOLF_RELATIONS', False) and t.get('golf') in ('fairway', 'rough', 'green', 'tee', 'bunker'):   # golf areas mapped as multipolygon relations (Maxwelton: most of its fairways); the inner rings are left whole
            F[t['golf']].append(dict(poly=p, tags=t))
            continue
        key = 'water' if (t.get('natural') == 'water' or t.get('water')) else 'wood' if (t.get('natural') == 'wood' or t.get('landuse') == 'forest') else None
        if key:
            F[key].append(dict(poly=p, tags=t))
    # a club whose OSM outline covers only part of its holes, or none (Memphis National: two courses share one OSM outline): the course is the holes in
    # course.HOLE_BOX (local metres [e0, n0, e1, n1]; none of OSM's holes when OSM_HOLES is False), course.EXTRA_FILE (hand-digitised holes, greens,
    # tees, fairways and bunkers off the aerial, in local metres) is added, the outline is the holes buffered by OUTLINE_BUFFER, and OSM's golf
    # features are kept only within KEEP_NEAR_HOLES of them
    if getattr(course, 'HOLE_BOX', None) is not None or getattr(course, 'EXTRA_FILE', None):
        from shapely.geometry import box
        hb = box(*course.HOLE_BOX) if getattr(course, 'HOLE_BOX', None) else None
        F['hole'] = [h for h in F['hole'] if hb is not None and hb.contains(h['line'].interpolate(.5, normalized=True)) and (not getattr(course, 'HOLE_WAYS', None) or h.get('id') in course.HOLE_WAYS)] if getattr(course, 'OSM_HOLES', True) else []   # HOLE_WAYS: the OSM way ids of this course's holes, where the outline holds several courses (Lacoma, Pebble Brook)
        ex = getattr(course, 'EXTRA_FILE', None)
        X = {}
        if ex:
            X = json.load(open(os.path.join(COURSE_DIR, ex)))
            for h in X.get('hole', []):
                F['hole'].append(dict(line=LineString(h['line']), ref=h['ref'], par=h['par'], hcp=h.get('hcp', 0), tags={'golf': 'hole', 'extra': 'yes'}))
            for k in ('green', 'tee', 'bunker', 'fairway'):
                for ring in X.get(k, []):
                    F[k].append(dict(poly=Polygon(ring).buffer(0), tags={'extra': 'yes'}))
            for ring in X.get('water', []):
                F['water'].append(dict(poly=Polygon(ring).buffer(0), tags={'extra': 'yes'}))
        if ex and X.get('course'):   # an outline drawn by hand (no holes yet to build it from): OSM's features count where they lie inside it
            outline = Polygon(X['course']).buffer(0)
            near = outline
            for k in ('green', 'tee', 'fairway', 'rough', 'pin'):   # (the greens, tees and fairways there are the other course's: only bunkers, ponds and paths are kept)
                F[k] = [f for f in F[k] if f['tags'].get('extra')]
        else:
            hu = unary_union([h['line'] for h in F['hole']])
            near = hu.buffer(getattr(course, 'KEEP_NEAR_HOLES', 120))
            outline = hu.buffer(getattr(course, 'OUTLINE_BUFFER', 90)).buffer(40).buffer(-40)
        for k in ('green', 'tee', 'bunker', 'fairway', 'rough', 'water_hazard', 'lateral_water_hazard', 'pin', 'cartpath_line'):
            F[k] = [f for f in F[k] if f['tags'].get('extra') or near.intersects(f.get('poly', f.get('pt', f.get('line'))))]
        F['course'] = [dict(poly=outline, tags={}, id=0)]
    elif course.OSM_WAY:   # the course's own outline, and only its holes (a resort's other courses may be in the download too)
        F['course'] = [c for c in F['course'] if c['id'] == course.OSM_WAY]
        assert len(F['course']) == 1, f'OSM way {course.OSM_WAY} (course.OSM_WAY) is not a leisure=golf_course in osm.json'
        cp = F['course'][0]['poly'].buffer(30)
        F['hole'] = [h for h in F['hole'] if cp.contains(h['line'].interpolate(.5, normalized=True)) and (not getattr(course, 'HOLE_WAYS', None) or h.get('id') in course.HOLE_WAYS)]   # HOLE_WAYS: only those holes (Augusta: its outline also holds the Par 3 course)
        for k in ('green', 'tee', 'bunker', 'fairway', 'rough', 'water_hazard', 'lateral_water_hazard', 'pin', 'cartpath', 'cartpath_line'):   # and only its own golf features
            F[k] = [f for f in F[k] if cp.intersects(f.get('poly', f.get('pt', f.get('line'))))]
    # greens OSM has in the wrong place (course.GREEN_FIX: hole -> outline in local metres, traced off the aerial): the nearest green is replaced
    # by the outline, and the hole line and its pin end at the middle of it
    for ref, ring in getattr(course, 'GREEN_FIX', {}).items():
        h = next(h for h in F['hole'] if h['ref'] == ref); end = Point(h['line'].coords[-1]); poly = Polygon(ring)
        old = min(F['green'], key=lambda g: g['poly'].distance(end)); F['green'].remove(old)
        F['green'].append(dict(poly=poly, tags=dict(old['tags'])))
        for pn in F['pin']:
            if pn['pt'].distance(end) < 1:
                pn['pt'] = poly.centroid
        h['line'] = LineString(list(h['line'].coords)[:-1] + [poly.centroid.coords[0]])
    # ponds tagged only as golf=water_hazard / lateral_water_hazard (Eagle Ridge) are water too, unless natural=water already covers them
    for f in F['water_hazard'] + F['lateral_water_hazard']:
        if not any(w['poly'].intersection(f['poly']).area > .5 * f['poly'].area for w in F['water']):
            F['water'].append(dict(poly=f['poly'], tags=f['tags']))
    # tee boxes OSM lacks (course.EXTRA_TEES: hole -> (east, north) of the box's middle, local metres): a 12 x 8 m box facing down the hole line
    for ref, (te, tn) in getattr(course, 'EXTRA_TEES', {}).items():
        h = next(h for h in F['hole'] if h['ref'] == ref)
        (x0, y0), (x1, y1) = list(h['line'].coords)[:2]
        L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** .5; ux, uy = (x1 - x0) / L, (y1 - y0) / L
        pts = [(te + ux * a - uy * b, tn + uy * a + ux * b) for a, b in ((-4, -6), (4, -6), (4, 6), (-4, 6))]
        F['tee'].append(dict(poly=Polygon(pts), tags={'extra': 'yes'}))
    # golf features left out by name (course.OSM_SKIP_NAMES; Augusta: the patrons' Gallery Fairway Area and the practice grounds' replica greens are not part of the 18)
    skip = set(getattr(course, 'OSM_SKIP_NAMES', ()))
    if skip:
        for k in list(F):
            if k != 'hole':
                F[k] = [f for f in F[k] if not isinstance(f, dict) or f.get('tags', {}).get('name') not in skip]
    F['hole'].sort(key=lambda h: h['ref'])
    return F


if __name__ == '__main__':
    F = load()
    for k, v in sorted(F.items()):
        print(f'{k:14s} {len(v)}')
