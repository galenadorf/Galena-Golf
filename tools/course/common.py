"""Shared settings for the Woodbine Bend course pipeline.

Everything is in east/north metres around ORIGIN on a local transverse Mercator (true north up), the frame the game's
real-course data uses (see RD_GCCB in index.html).
"""
import os
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
OUT = os.path.join(HERE, 'out')
os.makedirs(CACHE, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

KEY = 'woodbine'
NAME = 'Woodbine Bend Golf Course'
ORIGIN = (42.3373, -90.1503)  # lat, lon: the middle of the course
UA = {'User-Agent': 'galena-golf course builder (github.com/galenadorf/Galena-Golf)'}

# areas, in local metres [e0, n0, e1, n1]
DETAIL = (-700, -700, 700, 700)      # the course and its edges: 1 m terrain, aerial, lidar
WIDE = (-2400, -2000, 2400, 2000)    # the horizon: coarse terrain only

LOCAL = f'+proj=tmerc +lat_0={ORIGIN[0]} +lon_0={ORIGIN[1]} +k=1 +x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs'
_fwd = Transformer.from_crs('EPSG:4326', LOCAL, always_xy=True)
_inv = Transformer.from_crs(LOCAL, 'EPSG:4326', always_xy=True)


def to_local(lon, lat):
    return _fwd.transform(lon, lat)


def to_lonlat(e, n):
    return _inv.transform(e, n)


def bbox_lonlat(area, pad=0):
    e0, n0, e1, n1 = area
    pts = [to_lonlat(e, n) for e in (e0 - pad, e1 + pad) for n in (n0 - pad, n1 + pad)]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def cache(*parts):
    return os.path.join(CACHE, *parts)


def smooth_polys(m, fr, smooth, level, min_area, tol, pad=4):
    """Polygons (local metres) from a boolean mask on the base-map grid `fr`. The painted edges are pixel staircases, so each outline is
    the sub-pixel contour of the mask blurred by `smooth` px, traced at `level` (.5 keeps straight edges where they are; a little less
    keeps the area). An outline inside another one is a hole (or an island in a hole). `tol` m simplifies the result."""
    import numpy as np
    from shapely.geometry import Polygon
    from skimage import measure
    from scipy.ndimage import gaussian_filter
    mf = gaussian_filter(np.pad(m, pad).astype(float), smooth)
    res = fr['res']
    rings = []
    for c in measure.find_contours(mf, level):
        pts = [(fr['e0'] + (x - pad + .5) * res, fr['n1'] - (y - pad + .5) * res) for y, x in c]
        if len(pts) >= 4:
            rings.append(Polygon(pts).buffer(0))
    polys = []
    for r in sorted(rings, key=lambda q: -q.area):
        for i, q in enumerate(polys):
            if q.contains(r.representative_point()):
                polys[i] = q.symmetric_difference(r)
                break
        else:
            polys.append(r)
    return [q.simplify(tol) for q in polys if q.area >= min_area]
