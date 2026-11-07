"""Buildings from Overture Maps (Esri Community Maps, OSM, Microsoft ML footprints; one merged layer on the public S3 copy), for a course whose OSM
buildings are missing or old: the houses along the holes. course.OVERTURE_REACH = metres from a hole line (or, less 20 m, from a fairway, green or tee box) within which a footprint is kept
(OVERTURE_MIN_M2 = the smallest kept, default 60: no sheds). Writes out/buildings_painted.json (local metres), which build.py takes beside OSM's (an OSM
building mostly under one of these gives way) and which all_read.py leaves alone unless the course paints the building layer.

  python buildings_overture.py --course <key> [--fetch]     --fetch downloads the footprints for the detail area first (.cache/overture_buildings.json; needs duckdb)
"""
import json
import os
import sys

from shapely import wkt
from shapely.geometry import mapping
from shapely.ops import transform as shp_transform

import osm
from common import DETAIL, OUT, bbox_lonlat, cache, course, to_local

RELEASE = '2026-10-21.0'


def fetch():
    import duckdb
    w, s, e, n = bbox_lonlat(DETAIL)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
    q = f"""SELECT id, class, height, ST_AsText(geometry) wkt, sources[1].dataset ds FROM read_parquet('s3://overturemaps-us-west-2/release/{RELEASE}/theme=buildings/type=building/*', hive_partitioning=1)
    WHERE bbox.xmin>{w} AND bbox.xmax<{e} AND bbox.ymin>{s} AND bbox.ymax<{n}"""
    rows = [dict(id=r[0], cls=r[1], h=r[2], wkt=r[3], ds=r[4]) for r in con.execute(q).fetchall()]
    json.dump(rows, open(cache('overture_buildings.json'), 'w'))
    print(len(rows), 'footprints downloaded')


def main():
    if '--fetch' in sys.argv or not os.path.exists(cache('overture_buildings.json')):
        fetch()
    reach, min_m2 = getattr(course, 'OVERTURE_REACH', 110), getattr(course, 'OVERTURE_MIN_M2', 60)
    F = osm.load()
    from buildings_detect import near_play
    near = near_play(F, reach)
    keep = []
    for r in json.load(open(cache('overture_buildings.json'))):
        g = shp_transform(lambda x, y, z=None: to_local(x, y), wkt.loads(r['wkt']))
        for p in getattr(g, 'geoms', [g]):
            if p.is_valid and p.area >= min_m2 and p.intersects(near):
                keep.append(p.simplify(.15))
    json.dump([mapping(p) for p in keep], open(os.path.join(OUT, 'buildings_painted.json'), 'w'))
    print(len(keep), f'buildings within {reach} m of a hole line (>= {min_m2} m2) -> buildings_painted.json')


if __name__ == '__main__':
    main()
