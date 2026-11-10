"""One picture to take trees out, put trees in, add sawgrass and add creek (any course with an all-in-one map frame, out/all_edit.json;
made for Legends). It replaces trees_x.png for the trees: its reader writes the same trees_x_removed.json / trees_x_added.json.

  extras_edit.py guide   writes out/extras_start.png: the aerial (2 px per metre, the all-in-one map's frame) with every tree the game has as
                         a ring (pale yellow broadleaf, pale blue conifer, pale green shrub, grey = removed now), the creek (white outline) and
                         sawgrass clumps (small pale rings) the game has now, the fairways, greens, tees, ponds and out-of-bounds line as faint
                         white outlines, hole numbers and a 100-yard grid. The X marks already on out/trees_x.png are carried over onto it.
                         Also out/extras_key.png, the colour key. Nothing on the picture is in a paint colour.
  extras_edit.py read    reads out/extras_mask.png (your painted copy of extras_start.png, same size, never resized or cropped) and writes
                         out/trees_x_removed.json, out/trees_x_added.json, out/clumps_added.json, out/creek_added.json and the check picture
                         out/extras_check.png. Then build.py and install.py.

Paint with hard edges (the Pencil tool, no anti-aliasing) in these exact colours:
  magenta #FF00FF  a bold X over a tree's ring takes it out, and any tree stacked under it (every ring the X's middle is on or within
                   1 m of); nothing is planted back there (the Frank Road spear packing keeps clear of it)
  green   #008000  add a broadleaf tree: a filled circle the size of the crown (a big blob or area is filled with trees ~6 m apart)
  blue    #0040FF  add a conifer (the same way)
  purple  #800080  add shrubs (1.5-4.5 m; an area is filled ~3.5 m apart)
  amber   #FFC000  sawgrass: a dot ~3 px (1.5 m) is one clump 5 ft tall and across; a bigger area is filled with clumps ~2 m apart; deep
                   rough is put under each clump. Added to the clumps of the all-in-one map (all_mask.png), never replacing them.
  cyan    #00FFFF  creek: a line along the middle of the new water (any width; it is traced to its centre line, smoothed, and dug as the
                   game's creek, 4 m of water, stepping down along its length, with its banks). Start and end it on the existing creek to join
                   it. Added to the mapped creek, never replacing it.
Keep editing extras_mask.png: every mark on it counts each time it is read (erasing a mark undoes it). out/trees_x_legacy.json, if present,
lists trees that stay out whatever the picture says (Legends: 38 trees the old tree guide's magenta outlines took out, kept out on request).
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rasterio.transform import Affine
from scipy import ndimage as ndi
from shapely.geometry import mapping
from shapely.ops import unary_union

from common import OUT

Image.MAX_IMAGE_PIXELS = None
X_COL = (255, 0, 255)
ADD = {0: (0, 128, 0), 2: (0, 64, 255), 1: (128, 0, 128)}   # broadleaf, conifer, shrub
CLUMP = (255, 192, 0)
CREEK = (0, 255, 255)
TOL = 20
KEY = [(X_COL, 'X out a tree', 'a bold X over its ring: one X, one tree'), (ADD[0], 'add a broadleaf tree', 'filled circle, crown size (an area: a grove)'),
       (ADD[2], 'add a conifer', 'filled circle, crown size (an area: a stand)'), (ADD[1], 'add shrubs', 'filled circle / area'),
       (CLUMP, 'sawgrass clump (5 ft)', 'dot ~3 px = one clump; an area is filled ~2 m apart'),
       (CREEK, 'creek', 'a line along the middle of the water; start and end it on the existing creek')]
PAINT_COLS = [X_COL, *ADD.values(), CLUMP, CREEK]
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def frame():
    return json.load(open(os.path.join(OUT, 'all_edit.json')))


def guide():
    import all_edit
    import build
    from preview import E0, N1, load_rgb
    fr = frame(); ppm = fr['ppm']; res = fr['res']
    rgb, ares = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    c0, r0 = int(round((fr['e0'] - E0) / ares)), int(round((N1 - fr['n1']) / ares))
    a = np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    base = np.zeros((fr['h'], fr['w'], 3), np.uint8)
    sub = a[max(r0, 0):r0 + fr['h'], max(c0, 0):c0 + fr['w']]
    base[max(-r0, 0):max(-r0, 0) + sub.shape[0], max(-c0, 0):max(-c0, 0) + sub.shape[1]] = sub
    L, F = all_edit.current()

    g = Image.fromarray(base).convert('RGBA')
    d = ImageDraw.Draw(g, 'RGBA')
    px = lambda e, n: ((e - fr['e0']) * ppm, (fr['n1'] - n) * ppm)
    font = ImageFont.truetype(FONT, 22)
    yd = 100 * .9144
    for k in range(int(np.floor(fr['e0'] / yd)), int(np.ceil((fr['e0'] + fr['w'] * res) / yd)) + 1):
        x = px(k * yd, 0)[0]
        d.line([(x, 0), (x, fr['h'])], fill=(255, 255, 255, 60), width=1)
        d.text((x + 3, 3), f'E{k * 100}', fill=(255, 255, 255, 220), font=font)
    for k in range(int(np.floor((fr['n1'] - fr['h'] * res) / yd)), int(np.ceil(fr['n1'] / yd)) + 1):
        y = px(0, k * yd)[1]
        d.line([(0, y), (fr['w'], y)], fill=(255, 255, 255, 60), width=1)
        d.text((3, y + 3), f'N{k * 100}', fill=(255, 255, 255, 220), font=font)
    ring = lambda q, col, w: [d.line([px(*c) for c in r.coords], fill=col, width=w) for p in getattr(q, 'geoms', [q]) if p.geom_type == 'Polygon' for r in [p.exterior, *p.interiors]]
    for k in ('fairway', 'green', 'tee', 'pond'):
        for p in L[k]:
            ring(p, (255, 255, 255, 90), 1)
    ring(L['boundary'], (255, 255, 255, 150), 2)
    cr = unary_union(build.creek_pieces())
    if not cr.is_empty:
        ring(cr, (255, 255, 255, 230), 2)
    cl = []
    for n in ('clumps.json', 'clumps_added.json'):
        p = os.path.join(OUT, n)
        cl += json.load(open(p)) if os.path.exists(p) else []
    for e, n, k in cl:
        x, y = px(e, n); r = max(2.0, .75 * k * ppm)
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 235, 170, 255), width=1)
    tp = os.path.join(OUT, 'trees_all.json')
    if not os.path.exists(tp):
        sys.exit('out/trees_all.json is missing: run build.py first')
    rp = os.path.join(OUT, 'trees_x_removed.json')
    gone = {(round(t['e'], 2), round(t['n'], 2)) for t in json.load(open(rp))} if os.path.exists(rp) else set()
    for t in json.load(open(tp)):
        x, y = px(t['e'], t['n']); r = max(2.0, t['d'] / 2 * ppm)
        col = (150, 150, 150) if (round(t['e'], 2), round(t['n'], 2)) in gone else (255, 255, 150) if t['kind'] == 0 else (150, 190, 255) if t['kind'] == 2 else (150, 255, 150)
        d.ellipse([x - r, y - r, x + r, y + r], outline=col + (255,), width=2)
    hf = ImageFont.truetype(FONT, 17)
    for h in F['hole']:
        d.line([px(*c) for c in h['line'].coords], fill=(255, 255, 255, 110), width=1)
        for (x, y), lab in ((px(*h['line'].coords[0]), str(h['ref'])), (px(*h['line'].coords[-1]), f"{h['ref']}G")):
            d.ellipse([x - 17, y - 17, x + 17, y + 17], fill=(255, 255, 255, 230), outline=(40, 40, 40, 255), width=2)
            d.text((x, y), lab, fill=(20, 20, 20, 255), font=hf, anchor='mm')
    out = np.asarray(g.convert('RGB')).copy()
    # nothing on the start picture may read as paint: nudge any pixel (aerial or drawing) within 2 x TOL of a paint colour away from it
    for c in PAINT_COLS:
        m = np.abs(out.astype(int) - c).max(2) <= 2 * TOL
        out[m] = (out[m].astype(int) * .6 + 50).astype(np.uint8)
    # carry over the X marks already painted on trees_x.png (only what was painted: the old guide's own magenta outlines are left out)
    carried = 0
    xp, gp = os.path.join(OUT, 'trees_x.png'), os.path.join(OUT, 'trees_guide.png')
    if os.path.exists(xp) and os.path.exists(gp):
        xa = np.asarray(Image.open(xp).convert('RGB')).astype(int); ga = np.asarray(Image.open(gp).convert('RGB')).astype(int)
        m = (np.abs(xa - X_COL).max(2) < 60) & (np.abs(xa - ga).max(2) > 30)
        lab, n = ndi.label(ndi.binary_closing(m, iterations=2), structure=np.ones((3, 3)))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(ndi.sum(m, lab, range(1, n + 1))) if s >= 12]) & m
        out[keep] = X_COL
        carried = int(ndi.label(keep, structure=np.ones((3, 3)))[1])
    Image.fromarray(out).save(os.path.join(OUT, 'extras_start.png'))

    f1, f2 = ImageFont.truetype(FONT, 22), ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 19)
    k = Image.new('RGB', (1350, 120 + 52 * len(KEY) + 150), (34, 34, 34)); kd = ImageDraw.Draw(k)
    kd.text((20, 20), 'extras_mask.png colours  (hard edges: Pencil tool, no anti-aliasing)', fill=(255, 255, 255), font=f1)
    for i, (c, what, how) in enumerate(KEY):
        y = 70 + 52 * i
        kd.rectangle([20, y, 90, y + 38], fill=c)
        kd.text((105, y + 7), '#%02X%02X%02X' % c, fill=(255, 255, 255), font=f1)
        kd.text((235, y + 8), f'{what}  ({how})', fill=(220, 220, 220), font=f2)
    y = 90 + 52 * len(KEY)
    for col, what in (((255, 255, 150), 'ring: broadleaf the game has'), ((150, 190, 255), 'ring: conifer'), ((150, 255, 150), 'ring: shrub'),
                      ((150, 150, 150), 'ring: tree removed now (with no X over it, it comes back on the next read)'), ((255, 255, 255), 'white outline: the creek now; small pale rings: sawgrass now')):
        kd.ellipse([40, y, 64, y + 24], outline=col, width=3); kd.text((105, y), what, fill=(220, 220, 220), font=f2); y += 30
    k.save(os.path.join(OUT, 'extras_key.png'))
    print(f'out/extras_start.png {out.shape[1]} x {out.shape[0]} px ({carried} X marks carried over from trees_x.png); out/extras_key.png. '
          'Paint on a copy saved as out/extras_mask.png, then: extras_edit.py read')


def read():
    import trees_x
    from all_read import clumps_from
    from fence_read import lines_from_mask
    fr = frame(); ppm = fr['ppm']
    path = os.path.join(OUT, 'extras_mask.png')
    if not os.path.exists(path):
        sys.exit('save your painted copy of out/extras_start.png as out/extras_mask.png')
    rem, add, notes, chk = trees_x.read(path, ADD, write=False, every=True)
    lp = os.path.join(OUT, 'trees_x_legacy.json')   # trees that stay out whatever the picture says (Legends: the 38 the old guide's magenta outlines took out)
    if os.path.exists(lp):
        have = {(round(t['e'], 2), round(t['n'], 2)) for t in rem}
        leg = [t for t in json.load(open(lp)) if (round(t['e'], 2), round(t['n'], 2)) not in have]
        rem += leg
        notes.append(f'{len(leg)} trees kept out by out/trees_x_legacy.json')
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    assert a.shape[:2] == (fr['h'], fr['w']), f'extras_mask.png is {a.shape[1]} x {a.shape[0]}, the map is {fr["w"]} x {fr["h"]}: never resize or crop it'
    tr = Affine(fr['res'], 0, fr['e0'], 0, -fr['res'], fr['n1'])
    cl = clumps_from(np.abs(a - CLUMP).max(2) <= TOL, fr, tr)
    cm = np.abs(a - CREEK).max(2) <= TOL
    lines = lines_from_mask(cm, fr) if cm.any() else []
    json.dump(add, open(os.path.join(OUT, 'trees_x_added.json'), 'w'))
    json.dump(rem, open(os.path.join(OUT, 'trees_x_removed.json'), 'w'))
    json.dump(cl, open(os.path.join(OUT, 'clumps_added.json'), 'w'))
    json.dump([mapping(L) for L in lines], open(os.path.join(OUT, 'creek_added.json'), 'w'))
    cd = ImageDraw.Draw(chk)
    px = lambda e, n: ((e - fr['e0']) * ppm, (fr['n1'] - n) * ppm)
    for e, n, k in cl:
        x, y = px(e, n); r = .75 * k * ppm + 2
        cd.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255), width=2)
    for L in lines:
        cd.line([px(*c) for c in L.coords], fill=(255, 255, 255), width=3)
    chk.save(os.path.join(OUT, 'extras_check.png'))
    print('\n'.join(notes))
    print(f'{len(rem)} trees removed (trees_x_removed.json), {len(add)} added (trees_x_added.json); {len(cl)} sawgrass clumps (clumps_added.json); '
          f'{len(lines)} creek lines, {sum(L.length for L in lines):.0f} m (creek_added.json). Check picture: out/extras_check.png '
          '(green ring = removed, white ring = added tree or clump, white line = new creek centre, red box = X found nothing). Then build.py and install.py.')


if __name__ == '__main__':
    {'guide': guide, 'read': read}.get(sys.argv[1] if len(sys.argv) > 1 else '', lambda: sys.exit(__doc__))()
