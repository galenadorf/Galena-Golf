"""One map to paint everything on (Eagle Ridge South; any course): the aerial at 2 px per metre (the 0.5 m grid of the fescue, fairway,
bunker and site maps), already painted with what the course data has now, so a first pass is corrections, not a blank page.
all_read.py reads it back into every layer file the separate readers write.

  out/all_start.png   the aerial with the current layers painted on in solid colours: open it, correct it, save it as out/all_mask.png
                      (keep editing all_mask.png after that; rerunning this script never touches it)
  out/all_guide.png   the same aerial with thin outlines of the current layers, the lidar trees (pale rings), hole numbers and a
                      100-yard grid: a reference to keep beside it, not to paint on
  out/all_key.png     the colour key
  out/all_edit.json   the map's frame (local metres)

A course may paint only some layers: course.PAINT (in its course.py) names them, and the start map, the key and all_read.py then
take only those colours (Eagle Ridge: fairways, greens, tee boxes, bunkers and played-tee dots; the rough, deep rough, trees, water,
paths, boundary and props stay as the data makes them). Without PAINT, every layer in PALETTE.

Paint with hard edges (GIMP: the Pencil tool, not the Paintbrush; no anti-aliasing, no feathered selections) and the exact colours of the key.
Unpainted ground inside the boundary is rough (the game adds the first cut and the collar round each green). The order things
are painted in does not matter: a line or dot painted over an area (a cart path across a fairway, the boundary line, a tree dot,
a clearing) leaves the area whole underneath, filled in from the pixels beside it.
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rasterio import features
from rasterio.transform import Affine
from shapely.geometry import Polygon, shape

import build
import osm
from common import OUT, course
from preview import E0, N1, load_rgb

PAD = 60.0   # m of aerial round the course outline
RES = .5     # m per pixel
# name: (colour, what it is, how to paint it). Every colour is one the aerial never comes within 40 of in any channel (checked on the course's NAIP).
PALETTE = {
    'fairway':  ((0, 255, 0), 'fairway', 'area'),
    'green':    ((128, 255, 128), 'putting green (the collar is added)', 'area'),
    'tee':      ((128, 0, 255), 'tee box (every one; the tee sets are placed in them by the card yardages)', 'area'),
    'bunker':   ((255, 128, 0), 'bunker', 'area'),
    'fescue':   ((255, 0, 255), 'fescue: the tall deep rough', 'area'),
    'pond':     ((0, 128, 255), 'pond (flat water)', 'area'),
    'creek':    ((0, 0, 255), 'creek (water that steps down along its length)', 'area, as wide as the water'),
    'path':     ((255, 0, 0), 'cart path (redrawn 2.4 m wide along the middle of what is painted)', 'line, any width'),
    'boundary': ((0, 255, 255), 'out-of-bounds line', 'one closed line round the course (or the whole area filled)'),
    'tee_dot':  ((255, 255, 0), 'where a hole\'s played (gold) tee should be (optional)', 'dot ~3 m across in its tee box'),
    'clear':    ((128, 0, 128), 'no lidar trees here (removes the trees standing in it)', 'area'),
    'broad':    ((0, 128, 0), 'add a broadleaf tree (a dot) or a grove (a big area)', 'dot the crown\'s size / area'),
    'conifer':  ((0, 128, 128), 'add a conifer', 'dot / area'),
    'shrub':    ((0, 0, 128), 'add shrubs (under 4 m)', 'dot / area'),
    'building': ((128, 128, 255), 'building footprint (joins the OSM buildings)', 'area, the roof outline'),
    'lot':      ((128, 255, 0), 'parking lot (stalls are laid out, 8 cars parked)', 'area, next to its building'),
    'wash':     ((255, 0, 128), 'washroom building (MEN / WOMEN doors, facing the nearest tee)', 'rectangle'),
    'potty':    ((255, 128, 255), 'porta-potty', 'dot ~1.5 m'),
    'shed':     ((128, 0, 0), 'shed / pump house (plain metal, no doors)', 'solid rectangle'),
    'sign':     ((0, 255, 128), 'signpost (its text: out/signs.txt, by the nearest hole)', 'dot ~2 m'),
}
SURFACES = ('fairway', 'green', 'tee', 'bunker', 'fescue', 'pond')   # areas the game's ground is made of (a line or dot over one leaves it whole)
PAINT = tuple(getattr(course, 'PAINT', None) or PALETTE)
assert all(k in PALETTE for k in PAINT), f'course.PAINT names a layer all_edit.PALETTE lacks: {PAINT}'
LAYERS = {k: v for k, v in PALETTE.items() if k in PAINT}   # the colours this course's map takes


def frame():
    F = osm.load()
    b = F['course'][0]['poly'].bounds
    e0, n1 = np.floor((b[0] - PAD) / RES) * RES, np.ceil((b[3] + PAD) / RES) * RES
    w, h = int(np.ceil((b[2] + PAD - e0) / RES)), int(np.ceil((n1 - b[1] + PAD) / RES))
    return dict(e0=float(e0), n1=float(n1), res=RES, ppm=1 / RES, w=w, h=h)


def current():
    """What the course data has now, layer by layer (painted files where there are any, else what build.py makes from OSM)."""
    F = osm.load()
    rd = lambda n: [shape(g) for g in json.load(open(os.path.join(OUT, n)))] if os.path.exists(os.path.join(OUT, n)) else None
    L = {}
    L['green'] = rd('greens_painted.json') or [build.round_green(f['poly']) for f in F['green']]
    L['pond'] = rd('water_painted.json') or [build.round_pond(f['poly']) for f in F['water']]
    L['tee'] = rd('tees_painted.json') or [build.round_osm(f['poly']) for f in F['tee']]
    L['bunker'] = rd('bunkers_painted.json') or [build.round_osm(f['poly']) for f in F['bunker']]
    fair = rd('fairways_painted.json')
    if fair is None:
        for f in F['green']:
            f['poly'] = build.round_green(f['poly'])
        fair, _ = build.link_fairways([build.round_osm(f['poly']) for f in F['fairway']], F)
        fair = [q.buffer(5, quad_segs=8).buffer(-5, quad_segs=8) for q in fair]
    L['fairway'] = fair
    L['fescue'] = rd('fescue.json') or []
    L['creek'] = build.creek_pieces()
    paths = rd('cartpaths.json')
    L['path'] = paths if paths is not None else [f['poly'] for f in F['cartpath']] + [f['line'].buffer(1.2) for f in F['cartpath_line']]
    bp = rd('buildings_painted.json')
    L['building'] = (bp or []) + [f['poly'] for f in F['building'] if not bp or not any(f['poly'].intersects(q) for q in bp)]
    bnd = os.path.join(OUT, 'boundary.json')
    L['boundary'] = shape(json.load(open(bnd))) if os.path.exists(bnd) else build.round_osm(Polygon(F['course'][0]['poly'].exterior), step=12)
    return L, F


def main():
    fr = frame()
    tr = Affine(RES, 0, fr['e0'], 0, -RES, fr['n1'])
    rgb, res = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    c0, r0 = int(round((fr['e0'] - E0) / res)), int(round((N1 - fr['n1']) / res))
    a = np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    base = np.zeros((fr['h'], fr['w'], 3), np.uint8)
    sub = a[max(r0, 0):r0 + fr['h'], max(c0, 0):c0 + fr['w']]
    base[max(-r0, 0):max(-r0, 0) + sub.shape[0], max(-c0, 0):max(-c0, 0) + sub.shape[1]] = sub
    L, F = current()

    start = base.copy()
    for k in ('fescue', 'fairway', 'pond', 'creek', 'green', 'tee', 'bunker', 'path', 'building'):   # later ones on top
        ps = [p for p in L[k] if not p.is_empty] if k in LAYERS else []
        if ps:
            m = features.rasterize([(p, 1) for p in ps], out_shape=(fr['h'], fr['w']), transform=tr, dtype='uint8') > 0
            start[m] = PALETTE[k][0]
    if 'boundary' in LAYERS:
        ring = L['boundary'].exterior.buffer(.9)   # a 1.8 m (3-4 px) line
        start[features.rasterize([(ring, 1)], out_shape=(fr['h'], fr['w']), transform=tr, dtype='uint8') > 0] = PALETTE['boundary'][0]
    sp = os.path.join(OUT, 'all_start.png')
    Image.fromarray(start).save(sp)

    g = Image.fromarray(base).convert('RGBA')
    d = ImageDraw.Draw(g, 'RGBA')
    px = lambda e, n: ((e - fr['e0']) / RES, (fr['n1'] - n) / RES)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    yd = 100 * .9144
    for k in range(int(np.floor(fr['e0'] / yd)), int(np.ceil((fr['e0'] + fr['w'] * RES) / yd)) + 1):
        x = px(k * yd, 0)[0]
        d.line([(x, 0), (x, fr['h'])], fill=(255, 255, 255, 60), width=1)
        d.text((x + 3, 3), f'E{k * 100}', fill=(255, 255, 255, 220), font=font)
    for k in range(int(np.floor((fr['n1'] - fr['h'] * RES) / yd)), int(np.ceil(fr['n1'] / yd)) + 1):
        y = px(0, k * yd)[1]
        d.line([(0, y), (fr['w'], y)], fill=(255, 255, 255, 60), width=1)
        d.text((3, y + 3), f'N{k * 100}', fill=(255, 255, 255, 220), font=font)
    tp = os.path.join(OUT, 'trees.json')
    for t in json.load(open(tp)) if os.path.exists(tp) else []:
        x, y = px(t['e'], t['n']); r = t['d'] / 2 / RES
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 210, 90), width=1)
    for k in ('fescue', 'fairway', 'pond', 'creek', 'green', 'tee', 'bunker', 'path', 'building'):
        for p in L[k]:
            for q in getattr(p, 'geoms', [p]):
                if q.geom_type == 'Polygon':
                    d.line([px(*c) for c in q.exterior.coords], fill=PALETTE[k][0] + (255,), width=2)
    d.line([px(*c) for c in L['boundary'].exterior.coords], fill=PALETTE['boundary'][0] + (255,), width=3)
    for h in F['hole']:
        for (x, y), lab in ((px(*h['line'].coords[0]), str(h['ref'])), (px(*h['line'].coords[-1]), f"{h['ref']}G")):
            d.ellipse([x - 17, y - 17, x + 17, y + 17], fill=(255, 255, 255, 230), outline=(200, 0, 0, 255), width=2)
            d.text((x, y), lab, fill=(160, 0, 0, 255), font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 17), anchor='mm')
        d.line([px(*c) for c in h['line'].coords], fill=(255, 255, 255, 110), width=1)
    g.convert('RGB').save(os.path.join(OUT, 'all_guide.png'))

    f1 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 19)
    k = Image.new('RGB', (1500, 70 + 52 * len(LAYERS)), (34, 34, 34))
    d = ImageDraw.Draw(k)
    d.text((20, 20), 'all_mask.png colours  (hard edges: Pencil tool; unpainted ground inside the boundary is rough)', fill=(255, 255, 255), font=f1)
    for i, (name, (c, what, how)) in enumerate(LAYERS.items()):
        y = 66 + 52 * i
        d.rectangle([20, y, 90, y + 38], fill=c)
        d.text((105, y + 7), '#%02X%02X%02X' % c, fill=(255, 255, 255), font=f1)
        d.text((235, y + 8), f'{what}  ({how})', fill=(220, 220, 220), font=f2)
    k.save(os.path.join(OUT, 'all_key.png'))
    json.dump(fr, open(os.path.join(OUT, 'all_edit.json'), 'w'))
    print('all_start.png', (fr['w'], fr['h']), 'px at', RES, 'm/px; all_guide.png, all_key.png, all_edit.json')
    if os.path.exists(os.path.join(OUT, 'all_mask.png')):
        print('(out/all_mask.png exists and was left as it is)')


if __name__ == '__main__':
    main()
