"""Shared settings for the course pipeline, for the course being worked on.

Each course is a folder courses/<key>/ with course.py (name, origin, areas, sources, scorecard), .cache/ (downloads) and out/ (painted
masks and generated files); the last two are git-ignored. Pick it with --course <key> on any script (taken out of sys.argv here, so
the scripts' own arguments are unchanged) or the GALENA_COURSE environment variable; woodbine when neither is given.

Everything is in east/north metres around ORIGIN on a local transverse Mercator (true north up), the frame the game's
real-course data uses (see the REAL COURSE section of index.html).
"""
import importlib.util
import json
import os
import sys

from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))


def _pick():
    key = os.environ.get('GALENA_COURSE', 'woodbine')
    a = sys.argv
    for i in range(1, len(a)):
        if a[i] == '--course' and i + 1 < len(a):
            key = a[i + 1]
            del a[i:i + 2]
            break
        if a[i].startswith('--course='):
            key = a[i].split('=', 1)[1]
            del a[i]
            break
    return key


KEY = _pick()
COURSE_DIR = os.path.join(HERE, 'courses', KEY)
if not os.path.exists(os.path.join(COURSE_DIR, 'course.py')):
    sys.exit(f'no course "{KEY}": make tools/course/courses/{KEY}/course.py (copy courses/woodbine/course.py)')
_spec = importlib.util.spec_from_file_location('course_' + KEY, os.path.join(COURSE_DIR, 'course.py'))
course = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(course)

CACHE = os.path.join(COURSE_DIR, '.cache')
OUT = os.path.join(COURSE_DIR, 'out')
os.makedirs(CACHE, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
SOUNDS_RAW = os.path.join(HERE, 'sounds_raw')   # the raw recordings sounds_trim.py reads (git-ignored; the game's sounds are not per course)

NAME = course.NAME
ORIGIN = course.ORIGIN  # lat, lon: the middle of the course
UA = {'User-Agent': 'galena-golf course builder (github.com/galenadorf/Galena-Golf)'}
YD = .9144

# areas, in local metres [e0, n0, e1, n1]
DETAIL = course.DETAIL   # the course and its edges: 1 m terrain, aerial, lidar
WIDE = course.WIDE       # the horizon: coarse terrain only

# build.py's output: `const RD_<KEY> = {...};` and `const GREEN_ALTI_<KEY> = {...};`
RD_VAR, ALTI_VAR = 'RD_' + KEY.upper(), 'GREEN_ALTI_' + KEY.upper()
RD_JS = os.path.join(OUT, f'rd_{KEY}.js')

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


def load_rd():
    """The course data last written by build.py, as a dict."""
    js = open(RD_JS).read()
    return json.loads(js[js.index('{'):js.rindex('};\nconst ' + ALTI_VAR) + 1])


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
