#!/usr/bin/env python3
"""Per-hole overhead 'paint review' pictures for every course, drawn from the game's installed data (courses/<key>.js).

  python3 hole_images.py woodbine [--holes 1,7] [--out "/mnt/k/- Share/hole_images"]
  python3 hole_images.py all

Each hole: the aerial (NAIP) with translucent fills and solid outlines in the paint-mask colours, every object numbered
(numbers run tee to green, restart each hole), a legend with the paint colours on the right, a 25 m grid, scale bar and
north arrow. Writes <out>/<course>/hole_NN.png and <out>/<course>/_frames_and_objects.json (frame + object table per hole,
so a repainted picture can be read back). Run with ~/.venvs/galena/bin/python.
"""
import base64, json, math, os, sys, textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
from scipy import ndimage as ndi
from shapely.geometry import Polygon, LineString, Point, box as sbox
import rasterio
from rasterio.windows import from_bounds

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONTB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
_f = {}


def font(sz, bold=False):
    k = (sz, bold)
    if k not in _f:
        _f[k] = ImageFont.truetype(FONTB if bold else FONT, sz)
    return _f[k]


# ---- decoding (same as index.html) ------------------------------------------------------------------------------
def i16(s):
    return np.frombuffer(base64.b64decode(s), dtype='<i2').astype(int) if s else np.zeros(0, int)


def dec_polys(s):
    a = i16(s)
    if len(a) == 0:
        return []
    k = 0
    out = []
    n = a[k]; k += 1
    for _ in range(n):
        nr = a[k]; k += 1
        rings = []
        for _ in range(nr):
            np_ = a[k]; k += 1
            x = y = 0
            r = []
            for _ in range(np_):
                x += a[k]; y += a[k + 1]; k += 2
                r.append((x / 10, y / 10))
            rings.append(r)
        out.append(rings)
    return out


def dec_lines(s):
    a = i16(s)
    if len(a) == 0:
        return []
    k = 0
    out = []
    n = a[k]; k += 1
    for _ in range(n):
        np_ = a[k]; k += 1
        x = y = 0
        r = []
        for _ in range(np_):
            x += a[k]; y += a[k + 1]; k += 2
            r.append((x / 10, y / 10))
        out.append(r)
    return out


def course_list():
    d = json.load(open(os.path.join(REPO, 'courses', 'courses.json')))
    return d if isinstance(d, list) else d['courses']


def load_course(key):
    s = open(os.path.join(REPO, 'courses', key + '.js')).read()
    rd, _ = json.JSONDecoder().raw_decode(s[s.index('.rd = ') + 6:])
    meta = next(c for c in course_list() if c['key'] == key)
    return rd, meta


# ---- palette: the existing paint-mask colours (tools/course/all_edit.PALETTE) -------------------------------------
def hx(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


PAINT = dict(fair='#00FF00', green='#80FF80', tee='#8000FF', sand='#FF8000', fescue='#FF00FF', water='#0080FF', creek='#0000FF',
             path='#FF0000', bnd='#00FFFF', dot='#FFFF00', clear='#800080', addB='#008000', addC='#008080', addS='#000080',
             bldg='#8080FF', lot='#80FF00', wash='#FF0080', potty='#FF80FF', shed='#800000', sign='#00FF80', clump='#FFC000',
             drain='#FF6060', fence='#804000')

# category: (title, display colour, paint colour hex or None, note)
CATS = {
    'tee': ('Tee box', PAINT['tee'], PAINT['tee'], 'paint'),
    'mk': ('Tee-set marker (w/y/b/r slot)', '#FFFFFF', PAINT['dot'], 'paint a yellow dot in the box of the tee played'),
    'green': ('Green', PAINT['green'], PAINT['green'], 'paint'),
    'cup': ('Hole point (green centre)', '#FF3030', None, 'from the hole data'),
    'fair': ('Fairway', PAINT['fair'], PAINT['fair'], 'paint'),
    'sand': ('Bunker', PAINT['sand'], PAINT['sand'], 'paint'),
    'water': ('Pond / water', PAINT['water'], PAINT['water'], 'paint'),
    'creek': ('Creek', PAINT['creek'], PAINT['creek'], 'paint'),
    'fescue': ('Deep rough / fescue (painted)', PAINT['fescue'], PAINT['fescue'], 'paint'),
    'rough': ('Regular rough cut out of deep rough (white)', '#FFFFFF', '#FFFFFF', 'paint WHITE over deep rough to turn it into regular rough'),
    'path': ('Cart path', PAINT['path'], PAINT['path'], 'paint'),
    'bridge': ('Bridge', '#C8A070', None, 'in the data (bridges / cartBridges)'),
    'road': ('Road (OSM)', '#909090', None, 'from OSM, not painted'),
    'stream': ('Stream line (OSM)', '#40A0FF', None, 'from OSM, not painted'),
    'bldg': ('Building', PAINT['bldg'], PAINT['bldg'], 'paint'),
    'wash': ('Washroom', PAINT['wash'], PAINT['wash'], 'paint'),
    'potty': ('Porta-potty', PAINT['potty'], PAINT['potty'], 'paint'),
    'shed': ('Shed / pump house', PAINT['shed'], PAINT['shed'], 'paint'),
    'sign': ('Sign', PAINT['sign'], PAINT['sign'], 'paint a dot'),
    'lot': ('Parking lot', PAINT['lot'], PAINT['lot'], 'paint'),
    'car': ('Parked car', '#E0E0E0', None, 'made from the lot'),
    'prop': ('Other prop', '#E0C0FF', None, 'in the data (props)'),
    'fence': ('Fence line', '#A06020', PAINT['fence'], 'paint a line'),
    'clump': ('Grass clump', PAINT['clump'], PAINT['clump'], 'paint'),
    'drain': ('Drainage hazard', PAINT['drain'], PAINT['drain'], 'paint'),
    'flower': ('Azalea / flower bed', '#FF70C0', None, 'in the data (flowers)'),
    't_b': ('Tree: broadleaf', '#FFFFFF', PAINT['addB'], 'ADD: a filled circle in #008000; REMOVE: a magenta #FF00FF X'),
    't_c': ('Tree: conifer', '#BFE6FF', PAINT['addC'], 'ADD: a filled circle in #008080 (a big area = a stand); REMOVE: a magenta #FF00FF X'),
    't_s': ('Tree: shrub', '#FFE49A', PAINT['addS'], 'ADD: a filled circle in #000080; REMOVE: a magenta #FF00FF X'),
    't_f': ('Tree: fruit / orchard', '#FFB0B0', None, 'to REMOVE paint a magenta #FF00FF X'),
    't_p': ('Tree: spear / column', '#C0C0C0', None, 'to REMOVE paint a magenta #FF00FF X'),
    't_x': ('Tree: specimen / named', '#FF80FF', None, 'to REMOVE paint a magenta #FF00FF X'),
}
ORDER = list(CATS)
READ_COLS = [   # (colour, what it does, how), as hole_images_read.py takes it
    ('#FF00FF', 'X = remove a tree', 'a thin X over the tree'),
    ('#FF00FF', 'area = deep rough', 'a filled area'),
    ('#FFFFFF', 'cut deep rough', 'over deep rough: it becomes regular rough'),
    ('#008000', 'add broadleaf', 'a filled circle as wide as the crown (a big green area is read as deep rough)'),
    ('#008080', 'add conifer', 'a filled circle; a big area (1,500 m2+) = a pine stand'),
    ('#000080', 'add shrub', 'a filled circle'),
    ('#00FF00', 'add fairway', 'a filled area'),
    ('#FF8000', 'add bunker', 'a filled area'),
    ('#00FFFF', 'OB line, this hole only', 'a line; out of bounds is the side away from the hole'),
]
FILL_K = float(os.environ.get('FILL_K', '0.5'))   # share of the old fill opacity (1 = as the first Woodbine set)
TREE_CAT = {0: 't_b', 8: 't_b', 1: 't_s', 2: 't_c', 4: 't_c', 3: 't_f', 6: 't_p', 7: 't_p'}
TREE_FILL = {'t_b': (40, 170, 40, 80), 't_c': (0, 100, 130, 100), 't_s': (180, 150, 50, 100), 't_f': (230, 120, 120, 90),
             't_p': (130, 130, 130, 90), 't_x': (200, 60, 200, 90)}
MK_COL = {'w': (255, 255, 255), 'y': (255, 230, 0), 'b': (40, 110, 255), 'r': (255, 40, 40)}


def rgba(c, a=255):
    c = hx(c) if isinstance(c, str) else c
    return (c[0], c[1], c[2], a)


def ink(c):
    c = hx(c) if isinstance(c, str) else c
    return (0, 0, 0) if (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) > 150 else (255, 255, 255)


# ---- geometry helpers ---------------------------------------------------------------------------------------------
def poly_geom(rings):
    try:
        g = Polygon(rings[0], rings[1:])
        return g if g.is_valid else g.buffer(0)
    except Exception:
        return None


def rect_pts(e, n, w, d, deg):
    t = math.radians(deg)
    fx, fy = math.cos(t), math.sin(t)       # front direction
    sx, sy = -fy, fx
    out = []
    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        out.append((e + sx * a * w / 2 + fx * b * d / 2, n + sy * a * w / 2 + fy * b * d / 2))
    return out


def merge_rings(lst):
    return lst


class Frame:
    def __init__(s, box, scale):
        s.e0, s.n0, s.e1, s.n1 = box
        s.s = scale
        s.W = int(math.ceil((s.e1 - s.e0) * scale))
        s.H = int(math.ceil((s.n1 - s.n0) * scale))

    def px(self, e, n):
        return ((e - s_e0(self)) * self.s, (self.n1 - n) * self.s)

    def pts(self, ring):
        return [((e - self.e0) * self.s, (self.n1 - n) * self.s) for e, n in ring]


def s_e0(f):
    return f.e0


def rast(F, polys, box_e):
    """boolean mask in frame F of polygons (list of rings-lists)."""
    M = Image.new('L', (F.W, F.H), 0)
    d = ImageDraw.Draw(M)
    for rings in polys:
        xs = [p[0] for p in rings[0]]; ys = [p[1] for p in rings[0]]
        if max(xs) < F.e0 or min(xs) > F.e1 or max(ys) < F.n0 or min(ys) > F.n1:
            continue
        if len(rings) == 1:
            d.polygon(F.pts(rings[0]), fill=255)
        else:
            t = Image.new('L', (F.W, F.H), 0)
            td = ImageDraw.Draw(t)
            td.polygon(F.pts(rings[0]), fill=255)
            for r in rings[1:]:
                td.polygon(F.pts(r), fill=0)
            M = ImageChops.lighter(M, t)
            d = ImageDraw.Draw(M)
    return np.asarray(M) > 0


def edge(mask, w=2):
    er = ndi.binary_erosion(mask, iterations=w)
    return mask & ~er


# ---- the renderer -------------------------------------------------------------------------------------------------
class Course:
    def __init__(self, key):
        self.key = key
        self.rd, self.meta = load_course(key)
        rd = self.rd
        self.feat = {k: dec_polys(v) for k, v in rd['feat'].items()}
        b = dec_polys(rd['boundary'])
        self.bnd = b[0][0] if b else None
        self.obin = b[0][1:] if b else []
        self.bldg = dec_polys(rd['buildings'])
        t = i16(rd['trees'])
        self.trees = [dict(e=t[i] / 10, n=t[i + 1] / 10, d=t[i + 2] / 10, kind=int(t[i + 3] // 1000), H=(t[i + 3] % 1000) / 10) for i in range(0, len(t) - 3, 4)]
        self.roads = []
        for enc in rd.get('roads') or []:
            for ln in dec_lines(enc):
                self.roads.append(('road', ln))
        if rd.get('highway'):
            for ln in dec_lines(rd['highway']):
                if len(ln) > 1:
                    self.roads.append(('road', ln))
        self.streams = [ln for ln in dec_lines(rd.get('streams') or '') if len(ln) > 1]
        self.fence = [ln for enc in (rd.get('fence') or []) for ln in dec_lines(enc)]
        self.clumps = [(a[i] / 10, a[i + 1] / 10, a[i + 2] / 10) for a in [i16(rd.get('clumps') or '')] for i in range(0, len(a) - 2, 3)]
        self.drains = [p[0] for p in dec_polys(rd.get('drains') or '')]
        fl = i16(rd.get('flowers') or '')
        self.flowers = [(fl[i] / 10, fl[i + 1] / 10, fl[i + 2] / 10) for i in range(0, len(fl) - 3, 4)]
        self.bridges = [('bridge', b) for b in rd.get('bridges') or [] if len(b) < 6 or b[5] == ''] + [('bridge', b) for b in rd.get('cartBridges') or []]
        self.props = rd.get('props') or []
        self.straw = None
        if rd.get('straw'):
            gr = self.meta['engine']['gr']; W, H = gr['W'], gr['H']
            m = np.zeros(W * H, bool)
            o = 0; v = 0
            for n in i16(rd['straw']):
                if v:
                    m[o:o + n] = True
                o += n; v ^= 1
            m = m.reshape(H, W).astype(np.float32)
            K = np.array([1, 4, 6, 4, 1], np.float32); K /= K.sum()
            m = ndi.convolve1d(ndi.convolve1d(m, K, axis=1, mode='nearest'), K, axis=0, mode='nearest')   # the game's 1-4-6-4-1 blur each way
            self.straw = m >= .5
        self.painted_deep = bool(self.meta['engine'].get('paintedDeep'))
        self.has_fescue = bool(self.feat.get('fescue'))
        self.naip = None
        for f in ('naip2023_025.tif', 'naip.tif'):
            p = os.path.join(HERE, 'courses', key, '.cache', f)
            if os.path.exists(p):
                self.naip = p
                break

    # -- aerial
    def aerial(self, F):
        if not self.naip:
            return Image.new('RGBA', (F.W, F.H), (60, 80, 60, 255))
        with rasterio.open(self.naip) as src:
            win = from_bounds(F.e0, F.n0, F.e1, F.n1, src.transform)
            a = src.read([1, 2, 3], window=win, boundless=True, fill_value=0, out_shape=(3, F.H, F.W),
                         resampling=rasterio.enums.Resampling.bilinear)
        return Image.fromarray(np.moveaxis(a, 0, -1).astype('uint8'), 'RGB').convert('RGBA')

    # -- hole
    def render(self, hi, outdir, own_only=False):
        rd = self.rd
        h = rd['holes'][hi]
        line = [tuple(p) for p in h['line']]
        pts = line + [tuple(h['tee']), tuple(h['green'])]
        M = 45
        e0 = min(p[0] for p in pts) - M; e1 = max(p[0] for p in pts) + M
        n0 = min(p[1] for p in pts) - M; n1 = max(p[1] for p in pts) + M
        # keep a sensible minimum shape
        if e1 - e0 < 220:
            c = (e0 + e1) / 2; e0, e1 = c - 110, c + 110
        if n1 - n0 < 220:
            c = (n0 + n1) / 2; n0, n1 = c - 110, c + 110
        sc = min(3.5, 2000 / max(e1 - e0, n1 - n0))
        F = Frame((e0, n0, e1, n1), sc)
        EXT = 40
        FX = Frame((e0 - EXT, n0 - EXT, e1 + EXT, n1 + EXT), sc)   # extended frame for the rule-based rasters
        ox, oy = int(round(EXT * sc)), int(round(EXT * sc))
        view = sbox(e0, n0, e1, n1)
        hline = LineString(line)

        def along(e, n):
            return hline.project(Point(e, n))

        objs = []      # {cat, e, n, along, spec}

        def add(cat, e, n, spec, extra=None):
            objs.append(dict(cat=cat, e=e, n=n, al=along(e, n), spec=spec, extra=extra or {}))

        def add_polys(cat, polys):
            for rings in polys:
                g = poly_geom(rings)
                if g is None or g.is_empty or not g.intersects(view):
                    continue
                gi = g.intersection(view)
                if gi.is_empty:
                    continue
                if gi.geom_type != 'Polygon':
                    gi = max([q for q in getattr(gi, 'geoms', []) if q.geom_type == 'Polygon'] or [None], key=lambda q: q.area if q else 0)
                    if gi is None:
                        continue
                rp = gi.representative_point()
                add(cat, rp.x, rp.y, dict(t='poly', rings=rings), dict(area=round(g.area, 1)))

        add_polys('tee', self.feat.get('tee', []))
        for k, v in (h.get('mk') or {}).items():
            if view.contains(Point(*v)):
                add('mk', v[0], v[1], dict(t='dot', k=k), dict(slot=k))
        add_polys('green', self.feat.get('green', []))
        add('cup', h['green'][0], h['green'][1], dict(t='cup'))
        add_polys('fair', self.feat.get('fair', []))
        add_polys('sand', self.feat.get('sand', []))
        add_polys('water', self.feat.get('water', []))
        add_polys('creek', self.feat.get('creek', []))
        add_polys('fescue', self.feat.get('fescue', []))
        add_polys('rough', self.feat.get('rough', []))
        add_polys('path', self.feat.get('path', []))
        add_polys('bldg', self.bldg)
        # lines
        def add_lines(cat, lines, width):
            for ln in lines:
                if len(ln) < 2:
                    continue
                L = LineString(ln)
                if not L.intersects(view):
                    continue
                Li = L.intersection(view)
                if Li.is_empty:
                    continue
                if Li.geom_type != 'LineString':
                    Li = max([q for q in getattr(Li, 'geoms', []) if q.geom_type == 'LineString'], key=lambda q: q.length, default=None)
                    if Li is None:
                        continue
                m = Li.interpolate(.5, normalized=True)
                add(cat, m.x, m.y, dict(t='line', pts=ln, w=width), dict(len=round(L.length, 1)))
        add_lines('road', [l for _, l in self.roads], 7.0)
        add_lines('stream', self.streams, 1.5)
        add_lines('fence', self.fence, 0.6)
        for _, b in self.bridges:
            if view.contains(Point(b[0], b[1])):
                add('bridge', b[0], b[1], dict(t='rect', pts=rect_pts(b[0], b[1], b[3], b[2], b[4] + 90) if False else rect_pts(b[0], b[1], b[3], b[2], b[4])), dict(L=b[2], W=b[3]))
        for p in self.props:
            k = p[0]
            if not view.contains(Point(p[1], p[2])):
                continue
            cat = k if k in ('wash', 'potty', 'shed', 'sign', 'lot', 'car') else 'prop'
            w, d = (p[4], p[5]) if len(p) > 5 else (2, 2)
            add(cat, p[1], p[2], dict(t='rect', pts=rect_pts(p[1], p[2], w, d, p[3])), dict(kind=k, text=p[6] if len(p) > 6 else ''))
        for (e, n, r) in self.clumps:
            if view.contains(Point(e, n)):
                add('clump', e, n, dict(t='circ', r=max(r, 1.0)))
        for ring in self.drains:
            rr = [(ring[i], ring[i + 1]) for i in range(0, len(ring), 2)]
            g = poly_geom([rr])
            if g is not None and g.intersects(view):
                rp = g.representative_point()
                add('drain', rp.x, rp.y, dict(t='poly', rings=[rr]))
        for (e, n, r) in self.flowers:
            if view.contains(Point(e, n)):
                add('flower', e, n, dict(t='circ', r=max(r, .8)))
        for tr in self.trees:
            if view.contains(Point(tr['e'], tr['n'])):
                c = TREE_CAT.get(tr['kind'], 't_x')
                add(c, tr['e'], tr['n'], dict(t='tree', d=tr['d'], c=c), dict(kind=tr['kind'], d=tr['d'], H=tr['H']))

        if own_only:   # only what is on this hole: each feature belongs to the hole whose line it is nearest (shared things, paths and roads, stay if they touch this hole's corridor)
            lines_all = [LineString([tuple(p) for p in hh['line']]) for hh in rd['holes']]
            keep = []
            for o in objs:
                sp = o['spec']
                if sp['t'] == 'poly':
                    g = poly_geom(sp['rings'])
                elif sp['t'] == 'line':
                    g = LineString(sp['pts'])
                elif sp['t'] == 'rect':
                    g = Polygon(sp['pts'])
                else:
                    g = Point(o['e'], o['n'])
                if g is None or g.is_empty:
                    continue
                if o['cat'] in ('mk', 'cup') or o['cat'].startswith('t_'):   # every tree in the frame is drawn, whichever hole it is
                    keep.append(o); continue                                  # nearest: a tree with no ring is a tree the game does not have
                if o['cat'] in ('path', 'road', 'stream', 'fence', 'bridge'):
                    if g.distance(hline) <= 30:
                        keep.append(o)
                    continue
                dd = [L.distance(g) for L in lines_all]
                if dd[hi] <= min(dd) + .5:
                    keep.append(o)
            objs[:] = keep
        # number: by category order, then along the hole
        objs.sort(key=lambda o: (ORDER.index(o['cat']), o['al']))
        for i, o in enumerate(objs, 1):
            o['n_'] = i
        # which hole each tee / green / fairway / bunker belongs to: the labelled hole's own are drawn full strength, the others faded and
        # captioned (H14 green), so a neighbour's green in the frame is never taken for this hole's
        allh = rd['holes']
        hbuf = hline.buffer(28)
        for o in objs:
            if o['cat'] not in ('tee', 'green', 'fair', 'sand') or o['spec']['t'] != 'poly':
                continue
            g = poly_geom(o['spec']['rings'])
            o['own'] = bool(g is not None and g.intersects(hbuf))
            cap = []
            if g is not None and o['cat'] in ('tee', 'green'):
                key_ = 'tee' if o['cat'] == 'tee' else 'green'
                for j, hh in enumerate(allh, 1):
                    if g.buffer(8 if key_ == 'tee' else 10).contains(Point(*hh[key_])):
                        cap.append(f'H{j}')
            if cap:
                o['cap'] = '/'.join(cap) + (' tee' if o['cat'] == 'tee' else ' green')
                o['extra']['holes'] = cap

        # ---- paint
        img = self.aerial(F)
        fills = Image.new('RGBA', (F.W, F.H), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fills)
        lines = Image.new('RGBA', (F.W, F.H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lines)
        labels = Image.new('RGBA', (F.W, F.H), (0, 0, 0, 0))
        tdw = ImageDraw.Draw(labels)

        def crop(m):
            return m[oy:oy + F.H, ox:ox + F.W]

        def paint_mask(m, col, a, edge_col=None, ew=2):
            if not m.any():
                return
            lay = np.zeros((F.H, F.W, 4), np.uint8)
            lay[m] = rgba(col, a)
            fills.alpha_composite(Image.fromarray(lay, 'RGBA'))
            if edge_col:
                el = np.zeros((F.H, F.W, 4), np.uint8)
                el[edge(m, ew) & m] = rgba(edge_col, 255)
                lines.alpha_composite(Image.fromarray(el, 'RGBA'))

        # out of bounds shading
        inb = rast(FX, [[self.bnd]] + [], None) if self.bnd else np.ones((FX.H, FX.W), bool)
        for r in self.obin:
            inb &= ~rast(FX, [[r]], None)
        ob = ~crop(inb)
        lay = np.zeros((F.H, F.W, 4), np.uint8); lay[ob] = (0, 0, 0, 120)
        fills.alpha_composite(Image.fromarray(lay, 'RGBA'))

        S = F.s
        # rule-based surfaces (computed by the game)
        def own_rings(cat):
            return [o['spec']['rings'] for o in objs if o['cat'] == cat and o['spec']['t'] == 'poly'] if own_only else self.feat.get(cat, [])
        fair = rast(FX, own_rings('fair'), None)
        green = rast(FX, own_rings('green'), None)
        tee = rast(FX, own_rings('tee'), None)
        sand = rast(FX, own_rings('sand'), None)
        if not self.has_fescue and not self.painted_deep and self.straw is None:
            play = fair | tee | (ndi.distance_transform_edt(~green) / S < 4)
            deep = (ndi.distance_transform_edt(~play) / S >= 22) & inb
            deep &= ~rast(FX, self.feat.get('rough', []), None)   # ground painted white: regular rough
            paint_mask(crop(deep), PAINT['fescue'], 40, '#C040C0', 2)
        if self.straw is not None:
            gr = self.meta['engine']['gr']
            gx = (np.arange(F.W) / S + F.e0 - gr['e0']) / gr['res']
            gy = (F.n1 - np.arange(F.H) / S - gr['n0']) / gr['res']
            xi = np.clip(gx.astype(int), 0, gr['W'] - 1); yi = np.clip(gy.astype(int), 0, gr['H'] - 1)
            sm = self.straw[np.ix_(yi, xi)]
            paint_mask(sm & crop(~(fair | green | tee | sand) & inb), '#B07838', 110, '#7A4A18', 2)
        # first cut: 2.8 m beside fairways, none within 8 m of a green
        dfair = ndi.distance_transform_edt(~fair) / S
        dgreen = ndi.distance_transform_edt(~green) / S
        fc = (dfair <= 2.8) & ~fair & (dgreen > 8) & ~green & ~tee & ~sand & inb
        paint_mask(crop(fc), '#D8FF60', 70, '#B8E040', 1)
        ring = (dgreen <= 1.9) & ~green
        paint_mask(crop(ring), '#C8FFC8', 90, '#FFFFFF', 1)

        # polygons: fills then outlines
        order = ['fair', 'tee', 'green', 'fescue', 'rough', 'sand', 'water', 'creek', 'path', 'bldg', 'drain']
        paintcol = {'rough': '#FFFFFF', 'fair': PAINT['fair'], 'tee': PAINT['tee'], 'green': PAINT['green'], 'fescue': PAINT['fescue'], 'sand': PAINT['sand'],
                    'water': PAINT['water'], 'creek': PAINT['creek'], 'path': PAINT['path'], 'bldg': PAINT['bldg'], 'drain': PAINT['drain']}
        alpha = {'rough': 0, 'fair': 85, 'tee': 130, 'green': 120, 'fescue': 70, 'sand': 140, 'water': 130, 'creek': 140, 'path': 150, 'bldg': 150, 'drain': 120}
        for cat in order:
            for o in objs:
                if o['cat'] != cat or o['spec']['t'] != 'poly':
                    continue
                rings = o['spec']['rings']
                pc = paintcol[cat]
                al = int(alpha[cat] * (1 if o.get('own', True) else .45))   # another hole's features: faded
                if len(rings) == 1:
                    fd.polygon(F.pts(rings[0]), fill=rgba(pc, al))
                else:
                    t = Image.new('RGBA', (F.W, F.H), (0, 0, 0, 0)); td = ImageDraw.Draw(t)
                    td.polygon(F.pts(rings[0]), fill=rgba(pc, al))
                    for r in rings[1:]:
                        td.polygon(F.pts(r), fill=(0, 0, 0, 0))
                    fills.alpha_composite(t)
                    fd = ImageDraw.Draw(fills)
                for r in rings:
                    p = F.pts(r)
                    ld.line(p + [p[0]], fill=(0, 0, 0, 255), width=5, joint='curve')
                for r in rings:
                    p = F.pts(r)
                    ld.line(p + [p[0]], fill=rgba(pc, 255), width=3, joint='curve')
        # lines / rects / circles
        for o in objs:
            sp = o['spec']
            c = hx(CATS[o['cat']][1])
            if sp['t'] == 'line':
                p = F.pts(sp['pts'])
                if o['cat'] == 'road':
                    ld.line(p, fill=(30, 30, 30, 255), width=max(3, int(sp['w'] * S) + 4), joint='curve')
                    ld.line(p, fill=(150, 150, 150, 255), width=max(2, int(sp['w'] * S)), joint='curve')
                    ld.line(p, fill=(255, 255, 255, 200), width=1, joint='curve')
                else:
                    ld.line(p, fill=(0, 0, 0, 255), width=int(max(3, sp['w'] * S)) + 3, joint='curve')
                    ld.line(p, fill=rgba(c, 255), width=int(max(2, sp['w'] * S)), joint='curve')
            elif sp['t'] == 'rect':
                p = F.pts(sp['pts'])
                pcol = PAINT.get(o['cat'], None) if o['cat'] in PAINT else CATS[o['cat']][1]
                col = hx(pcol) if isinstance(pcol, str) else pcol
                fd.polygon(p, fill=rgba(col, 170))
                ld.line(p + [p[0]], fill=(0, 0, 0, 255), width=4)
                ld.line(p + [p[0]], fill=rgba(col, 255), width=2)
            elif sp['t'] == 'circ':
                x, y = F.px(o['e'], o['n']); r = sp['r'] * S
                fd.ellipse([x - r, y - r, x + r, y + r], fill=rgba(c, 150))
                ld.ellipse([x - r, y - r, x + r, y + r], outline=(0, 0, 0, 255), width=2)
            elif sp['t'] == 'tree':
                x, y = F.px(o['e'], o['n']); r = max(sp['d'] / 2 * S, 3)
                fd.ellipse([x - r, y - r, x + r, y + r], fill=TREE_FILL[sp['c']])
                ld.ellipse([x - r, y - r, x + r, y + r], outline=(0, 0, 0, 255), width=3)
                ld.ellipse([x - r, y - r, x + r, y + r], outline=rgba(c, 255), width=1)
        # boundary
        if self.bnd:
            for ring in [self.bnd] + self.obin:
                p = F.pts(ring)
                ld.line(p + [p[0]], fill=(0, 0, 0, 255), width=6)
                ld.line(p + [p[0]], fill=rgba(PAINT['bnd'], 255), width=3)
        # this hole's own OB lines (data `obl`, painted cyan on its picture): the line, with white stake dots every 12 m and short ticks toward the OB side
        for o in h.get('obl') or []:
            p = F.pts([tuple(q) for q in o['p']])
            ld.line(p, fill=(0, 0, 0, 255), width=6)
            ld.line(p, fill=rgba(PAINT['bnd'], 255), width=3)
            ln = LineString(o['p'])
            for k in range(0, int(ln.length) + 1, 12):
                q = ln.interpolate(k); q2 = ln.interpolate(min(ln.length, k + 1)) if k + 1 <= ln.length else ln.interpolate(k - 1)
                dx, dy = q2.x - q.x, q2.y - q.y
                if k + 1 > ln.length:
                    dx, dy = -dx, -dy
                L = math.hypot(dx, dy) or 1
                ox, oy = -dy / L * o['s'], dx / L * o['s']   # left normal times s: toward the OB side
                a_, = F.pts([(q.x, q.y)]); b_, = F.pts([(q.x + ox * 4, q.y + oy * 4)])
                ld.line([a_, b_], fill=rgba(PAINT['bnd'], 255), width=2)
                ld.ellipse([a_[0] - 4, a_[1] - 4, a_[0] + 4, a_[1] + 4], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
        # hole line (dashed)
        p = F.pts(line)
        for a, b in zip(p, p[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            k = 0
            while k < L:
                k2 = min(k + 14, L)
                xa, ya = a[0] + (b[0] - a[0]) * k / L, a[1] + (b[1] - a[1]) * k / L
                xb, yb = a[0] + (b[0] - a[0]) * k2 / L, a[1] + (b[1] - a[1]) * k2 / L
                ld.line([(xa, ya), (xb, yb)], fill=(255, 255, 255, 230), width=2)
                k += 26
        # grid every 25 m
        gx0 = math.ceil(F.e0 / 25) * 25
        for e in np.arange(gx0, F.e1, 25):
            x = (e - F.e0) * S
            ld.line([(x, 0), (x, F.H)], fill=(255, 255, 255, 40 if e % 50 else 70), width=1)
        gy0 = math.ceil(F.n0 / 25) * 25
        for n in np.arange(gy0, F.n1, 25):
            y = (F.n1 - n) * S
            ld.line([(0, y), (F.W, y)], fill=(255, 255, 255, 40 if n % 50 else 70), width=1)
        # markers
        for o in objs:
            x, y = F.px(o['e'], o['n'])
            if o['spec']['t'] == 'dot':
                col = MK_COL[o['spec']['k']]
                ld.ellipse([x - 7, y - 7, x + 7, y + 7], fill=col + (255,), outline=(0, 0, 0, 255), width=2)
            elif o['spec']['t'] == 'cup':
                ld.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 50, 50, 255), outline=(255, 255, 255, 255), width=2)
                ld.line([(x, y), (x, y - 26)], fill=(255, 255, 255, 255), width=2)
                ld.polygon([(x, y - 26), (x + 14, y - 21), (x, y - 16)], fill=(255, 50, 50, 255))

        # labels
        for o in objs:
            x, y = F.px(o['e'], o['n'])
            txt = str(o['n_'])
            if o['spec']['t'] == 'tree':
                r = max(o['spec']['d'] / 2 * S, 3)
                fs = int(min(15, max(9, r * 0.9)))
                tdw.text((x, y), txt, font=font(fs, True), fill=(255, 255, 255, 255), anchor='mm', stroke_width=2, stroke_fill=(0, 0, 0, 255))
                continue
            fs = 15
            f = font(fs, True)
            bb = tdw.textbbox((0, 0), txt, font=f)
            w_, h_ = bb[2] - bb[0] + 10, bb[3] - bb[1] + 8
            colhex = CATS[o['cat']][1]
            if o['spec']['t'] == 'dot':
                x, y = x + 18, y - 4
            if o['spec']['t'] == 'cup':
                x, y = x + 20, y - 40
            tdw.rounded_rectangle([x - w_ / 2, y - h_ / 2, x + w_ / 2, y + h_ / 2], radius=5, fill=rgba(colhex, 235), outline=(0, 0, 0, 255), width=2)
            tdw.text((x, y), txt, font=f, fill=ink(colhex) + (255,), anchor='mm')
            if o.get('cap'):
                cf = font(13, True)
                cb = tdw.textbbox((0, 0), o['cap'], font=cf)
                cw, chh = cb[2] - cb[0] + 8, cb[3] - cb[1] + 6
                cy = y + h_ / 2 + chh / 2 + 2
                own = o.get('own', True)
                tdw.rounded_rectangle([x - cw / 2, cy - chh / 2, x + cw / 2, cy + chh / 2], radius=4, fill=(20, 20, 20, 235) if not own else (255, 255, 255, 240), outline=(255, 255, 255, 255) if not own else (0, 0, 0, 255), width=1)
                tdw.text((x, cy), o['cap'], font=cf, fill=(255, 255, 255, 255) if not own else (0, 0, 0, 255), anchor='mm')

        r_, g_, b_, a_ = fills.split()
        fills = Image.merge('RGBA', (r_, g_, b_, a_.point(lambda v: int(v * FILL_K))))   # fills more transparent, outlines stay solid
        img.alpha_composite(fills)
        img.alpha_composite(lines)
        img.alpha_composite(labels)
        # north arrow + scale bar on the map
        d = ImageDraw.Draw(img)
        d.polygon([(F.W - 40, 22), (F.W - 28, 58), (F.W - 40, 50), (F.W - 52, 58)], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
        d.text((F.W - 40, 70), 'N', font=font(18, True), fill=(255, 255, 255, 255), anchor='mm', stroke_width=2, stroke_fill=(0, 0, 0, 255))
        for e in np.arange(gx0, F.e1, 50):
            d.text(((e - F.e0) * S + 3, F.H - 16), f'E{int(e)}', font=font(11), fill=(255, 255, 255, 230), stroke_width=1, stroke_fill=(0, 0, 0, 255))
        for n in np.arange(math.ceil(F.n0 / 50) * 50, F.n1, 50):
            d.text((3, (F.n1 - n) * S - 14), f'N{int(n)}', font=font(11), fill=(255, 255, 255, 230), stroke_width=1, stroke_fill=(0, 0, 0, 255))
        bx, by = 20, F.H - 40
        d.rectangle([bx - 6, by - 26, bx + 50 * S + 6, by + 8], fill=(0, 0, 0, 150))
        d.line([(bx, by), (bx + 50 * S, by)], fill=(255, 255, 255, 255), width=4)
        d.text((bx + 25 * S, by - 12), '50 m', font=font(14, True), fill=(255, 255, 255, 255), anchor='mm')

        # ---- legend
        H0 = 64
        by_cat = {}
        for o in objs:
            by_cat.setdefault(o['cat'], []).append(o['n_'])

        def rng(ns):
            ns = sorted(ns); out = []; a = b = ns[0]
            for v in ns[1:]:
                if v == b + 1:
                    b = v
                else:
                    out.append((a, b)); a = b = v
            out.append((a, b))
            return ', '.join(str(a) if a == b else f'{a}-{b}' for a, b in out)
        lg = []
        # the colours hole_images_read.py reads: each swatch IS the colour to paint
        lg.append(('H', 'PAINT WITH EXACTLY THESE  (swatch = the colour)'))
        for col, title, sub in READ_COLS:
            lg.append(('E', col, f'{col}  {title}', sub, ''))
        lg.append(('T', 'Other colours listed below are not read yet:'))
        lg.append(('T', 'if you paint one, tell me which holes.'))
        lg.append(('H', 'NUMBERED OBJECTS  (number -> what it is; swatch = how it is drawn)'))
        for c in ORDER:
            if c not in by_cat:
                continue
            t, col, pc, note = CATS[c]
            sub = f'paint {pc}' if pc and note == 'paint' else (note if note else '')
            if pc and note != 'paint' and not note.startswith('ADD:'):
                sub = f'{note} (colour {pc})'
            lg.append(('E', col, f'{t}  x{len(by_cat[c])}', sub, rng(by_cat[c])))
        lg.append(('T', 'Only this hole\'s own features are drawn, but EVERY tree.' if own_only else 'Faded + captioned (H14 green...) = another hole\'s feature.'))
        lg.append(('H', 'SHADED BY THE GAME (computed from the above, not painted)'))
        lg.append(('E', '#D8FF60', 'First cut (2.8 m beside fairways)', 'repaint the fairway to change it', ''))
        lg.append(('E', '#C8FFC8', 'Fringe 0.9 m + collar 1 m round greens', 'follows the green outline', ''))
        if self.straw is not None:
            lg.append(('E', '#B07838', 'Pine straw (brown shade)', 'from the straw mask (pines.py)', ''))
        elif self.painted_deep and not self.has_fescue:
            lg.append(('E', PAINT['fescue'], 'Deep rough: NONE on this course yet', 'paint a filled area #FF00FF where deep rough should be', ''))
        elif not self.has_fescue and not self.painted_deep:
            lg.append(('E', '#C040C0', 'Deep rough: 22 m or more from play', 'game rule; paint fescue #FF00FF to override', ''))
        lg.append(('E', '#202020', 'Darkened = out of bounds', 'outside the cyan line', ''))
        lg.append(('E', PAINT['bnd'], 'Course boundary (out of bounds)', 'tell me if it is wrong', ''))
        if h.get('obl'):
            lg.append(('E', PAINT['bnd'], 'OB line for this hole (white stakes)', 'ticks point to the OB side', ''))
        lg.append(('E', '#FFFFFF', 'Hole line, tee to green (dashed)', 'from the hole data', ''))
        lg.append(('H', 'HOW TO CORRECT'))
        for t in ['White #FFFFFF over deep rough = make it regular rough.',
                  'Paint over this picture in the colours shown,',
                  'solid colour, hard edges. Do not resize or crop.',
                  'Unpainted/unchanged things are left as they are.',
                  'Overwrite the file; frame data is in',
                  '_frames_and_objects.json (grid labels are E/N',
                  'metres from the course origin).']:
            lg.append(('T', t))
        CW = 520

        def wrap(t, n):
            return textwrap.wrap(t, n) if t else []

        def ih(it):
            if it[0] == 'H':
                return 38
            if it[0] == 'T':
                return 20
            return 24 + 18 * len(wrap(it[3], 56)) + 17 * len(wrap(it[4], 52)) + 8
        tgt = max(F.H, 760)
        cols, cur, hh = [], [], 0
        for it in lg:
            if cur and hh + ih(it) > tgt and it[0] != 'T':
                cols.append(cur); cur, hh = [], 0
            cur.append(it); hh += ih(it)
        cols.append(cur)
        # a heading never ends a column
        for i in range(len(cols) - 1):
            if cols[i] and cols[i][-1][0] == 'H':
                cols[i + 1].insert(0, cols[i].pop())
        LW = CW * len(cols)
        TH = max(F.H, max(sum(ih(it) for it in c) + 20 for c in cols))
        out = Image.new('RGB', (F.W + LW, H0 + TH), (24, 28, 24))
        out.paste(img.convert('RGB'), (0, H0))
        dd = ImageDraw.Draw(out)
        nm = h.get('nm')
        cname = self.meta.get('name')
        dd.text((14, 32), f'{cname}  -  Hole {hi + 1}' + (f' "{nm}"' if nm else ''), font=font(28, True), fill=(255, 255, 255), anchor='lm')
        dd.text((F.W + LW - 14, 32), f'Par {h["par"]}   {h["yd"]} yd   scale {S:.2f} px/m   top-left E{F.e0:.0f} N{F.n1:.0f}', font=font(18), fill=(220, 230, 220), anchor='rm')
        for ci, col_items in enumerate(cols):
            y = H0 + 10
            x0 = F.W + ci * CW + 14
            for it in col_items:
                if it[0] == 'H':
                    y += 8
                    dd.text((x0, y + 10), it[1], font=font(14, True), fill=(255, 230, 120), anchor='lm')
                    dd.line([(x0, y + 24), (x0 + CW - 28, y + 24)], fill=(120, 130, 120), width=1)
                    y += 30
                elif it[0] == 'T':
                    dd.text((x0, y + 9), it[1], font=font(14), fill=(200, 210, 200), anchor='lm')
                    y += 20
                else:
                    _, col, title, sub, nums = it
                    dd.rectangle([x0, y + 2, x0 + 22, y + 22], fill=hx(col), outline=(255, 255, 255))
                    dd.text((x0 + 32, y + 12), title, font=font(15, True), fill=(255, 255, 255), anchor='lm')
                    y += 24
                    for ln in wrap(sub, 56):
                        dd.text((x0 + 32, y + 8), ln, font=font(13), fill=(170, 200, 255), anchor='lm')
                        y += 18
                    for ln in wrap(nums, 52):
                        dd.text((x0 + 32, y + 8), ln, font=font(14), fill=(255, 220, 140), anchor='lm')
                        y += 17
                    y += 8
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, f'hole_{hi + 1:02d}.png')
        out.save(path, optimize=False, compress_level=3)
        fr = dict(file=os.path.basename(path), hole=hi + 1, par=h['par'], yd=h['yd'], px_per_m=S, map_origin_px=[0, H0], map_size_px=[F.W, F.H],
                  top_left_enu=[F.e0, F.n1], bbox_enu=[F.e0, F.n0, F.e1, F.n1])
        ob = []
        for o in objs:
            r = dict(n=o['n_'], cat=o['cat'], e=round(o['e'], 1), n_=round(o['n'], 1))
            r.update(o['extra'])
            ob.append(r)
        return fr, ob


def main():
    a = sys.argv[1:]
    outroot = '/mnt/k/- Share/hole_images'
    holes = None
    if '--out' in a:
        i = a.index('--out'); outroot = a[i + 1]; del a[i:i + 2]
    if '--holes' in a:
        i = a.index('--holes'); holes = [int(x) for x in a[i + 1].split(',')]; del a[i:i + 2]
    a = [x for x in a if x != '--own']
    keys = a
    if keys == ['all']:
        keys = [c['key'] for c in course_list() if not c.get('hidden')]
    for key in keys:
        C = Course(key)
        od = os.path.join(outroot, key)
        info = {}
        for hi in range(len(C.rd['holes'])):
            if holes and hi + 1 not in holes:
                continue
            fr, ob = C.render(hi, od, own_only='--own' in sys.argv)
            info[str(hi + 1)] = dict(frame=fr, objects=ob)
            print(key, hi + 1, len(ob), 'objects', flush=True)
        jp = os.path.join(od, '_frames_and_objects.json')
        old = {}
        if os.path.exists(jp):
            try:
                old = json.load(open(jp))
            except Exception:
                old = {}
        old.update(info)
        json.dump(old, open(jp, 'w'), separators=(',', ':'))


if __name__ == '__main__':
    main()
