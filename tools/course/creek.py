"""The creek, traced from the 1 m DEM: a narrow depression (ground well below its surroundings), thinned to a centre line.

OSM has the creek only outside the course, so this finds the channel that runs past the clubhouse and behind the 16th
green. Writes out/creek.json (a GeoJSON-like line in local metres); build.py cuts it into short ribbon pieces.

`creek.py osm` takes the OSM streams instead (Eagle Ridge South: mapped streams cross 11 holes, too many channels for the DEM
trace, which keeps only the longest), each clipped to the same distance from the course.
"""
import sys
import json
import os

import networkx as nx
import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy.ndimage import gaussian_filter1d
from shapely.ops import unary_union
from shapely.geometry import LineString, mapping
from skimage.measure import label
from skimage.morphology import remove_small_objects, skeletonize

from common import DETAIL, OUT, cache
import osm

E0, N0, E1, N1 = DETAIL
KEEP_NEAR = 150  # m: only the stretch within this distance of the course boundary


def main():
    with rasterio.open(cache('dem1m.tif')) as s:
        z = s.read(1).astype(float)
    z1 = ndi.gaussian_filter(z, 1)
    bg = ndi.zoom(ndi.median_filter(z1[::2, ::2], size=21), 2, order=1)[:z.shape[0], :z.shape[1]]  # 42 m window
    ch = remove_small_objects((z1 - bg) < -0.7, 150)
    sk = skeletonize(ch)
    lab = label(sk, connectivity=2)
    ids, cnt = np.unique(lab[lab > 0], return_counts=True)
    main_c = lab == ids[cnt.argmax()]
    ys, xs = np.nonzero(main_c)
    G = nx.Graph()
    S = set(zip(ys.tolist(), xs.tolist()))
    for (y, x) in S:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (dy or dx) and (y + dy, x + dx) in S:
                    G.add_edge((y, x), (y + dy, x + dx), weight=np.hypot(dy, dx))
    a = next(iter(S))
    far = lambda s: max(nx.single_source_dijkstra_path_length(G, s).items(), key=lambda kv: kv[1])[0]
    u = far(a)
    v = far(u)
    path = nx.dijkstra_path(G, u, v)
    e = np.array([E0 + x + .5 for y, x in path])
    n = np.array([N1 - y - .5 for y, x in path])
    e, n = gaussian_filter1d(e, 4, mode='nearest'), gaussian_filter1d(n, 4, mode='nearest')
    line = LineString(np.c_[e, n]).simplify(.7)
    course = osm.load()['course'][0]['poly'].buffer(KEEP_NEAR)
    seg = line.intersection(course)
    parts = [g for g in getattr(seg, 'geoms', [seg]) if g.length > 20]
    json.dump([mapping(g) for g in parts], open(os.path.join(OUT, 'creek.json'), 'w'))
    print('creek pieces', len(parts), 'length', [round(g.length) for g in parts], 'm')


def from_osm():
    F = osm.load()
    near = F['course'][0]['poly'].buffer(KEEP_NEAR)
    parts = []
    ponds = unary_union([w['poly'] for w in F['water']]).buffer(2) if F['water'] else None   # a stream through a pond is the pond's water there
    for s in F['stream']:
        seg = s['line'].intersection(near)
        if ponds is not None:
            seg = seg.difference(ponds)
        parts += [g for g in getattr(seg, 'geoms', [seg]) if g.geom_type == 'LineString' and g.length > 20]
    json.dump([mapping(g) for g in parts], open(os.path.join(OUT, 'creek.json'), 'w'))
    print('creek pieces (OSM)', len(parts), 'length', [round(g.length) for g in parts], 'm')


if __name__ == '__main__':
    from_osm() if sys.argv[1:] == ['osm'] else main()
