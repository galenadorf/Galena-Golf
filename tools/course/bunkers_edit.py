"""A map to refine the bunkers on: the aerial with every current bunker (OSM plus the ones bunkers_auto.py found) filled in
solid pure ORANGE (#FF8000), plus thin outlines of the fairways (green), greens (white), tees (pink) and water (blue),
the hole numbers and the 100-yard grid. Same pixels as out/fescue_base.png. Paint orange over any bunker that is missing or
too small, paint over (or erase) orange that is not bunker, save as out/bunkers_mask.png; bunkers_paint.py then reads it
(bunker = pure orange, nothing else) and build.py uses it in place of the OSM and automatic bunkers."""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape

import osm
from common import OUT
from preview import E0, N1, load_rgb

YD = .9144
ORANGE = (255, 128, 0, 255)


def main(pad=40):
    F = osm.load()
    rgb, res = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    img = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    b = F['course'][0]['poly'].bounds
    e0, n0, e1, n1 = b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad
    box = (int((e0 - E0) / res), int((N1 - n1) / res), int((e1 - E0) / res), int((N1 - n0) / res))
    img = img.crop(box)
    fr = json.load(open(os.path.join(OUT, 'fescue_base.json')))
    assert img.size == (fr['w'], fr['h']), 'the crop must match fescue_base.png'
    px = lambda e, n: ((e - E0) / res - box[0], (N1 - n) / res - box[1])
    d = ImageDraw.Draw(img, 'RGBA')
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    for k in range(int(np.floor(e0 / (100 * YD))), int(np.ceil(e1 / (100 * YD))) + 1):
        x = px(k * 100 * YD, 0)[0]
        d.line([(x, 0), (x, img.size[1])], fill=(255, 255, 255, 70), width=1)
        d.text((x + 3, 3), f'E{k * 100}', fill=(255, 255, 255, 230), font=font)
    for k in range(int(np.floor(n0 / (100 * YD))), int(np.ceil(n1 / (100 * YD))) + 1):
        y = px(0, k * 100 * YD)[1]
        d.line([(0, y), (img.size[0], y)], fill=(255, 255, 255, 70), width=1)
        d.text((3, y + 3), f'N{k * 100}', fill=(255, 255, 255, 230), font=font)
    outline = lambda g, col: [d.line([px(*c) for c in q.exterior.coords], fill=col, width=1) for q in getattr(g, 'geoms', [g])]
    for g in json.load(open(os.path.join(OUT, 'fairways_painted.json'))):
        outline(shape(g), (60, 230, 60, 255))
    for k, col in (('green', (255, 255, 255, 255)), ('tee', (255, 150, 255, 255)), ('water', (60, 140, 255, 255))):
        for f in F.get(k, []):
            outline(f['poly'], col)
    polys = [f['poly'] for f in F['bunker']]
    ba = os.path.join(OUT, 'bunkers_auto.json')
    if os.path.exists(ba):
        polys += [shape(g) for g in json.load(open(ba))]
    for p in polys:  # the current bunkers, solid
        for q in getattr(p, 'geoms', [p]):
            d.polygon([px(*c) for c in q.exterior.coords], fill=ORANGE)
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    for h in F['hole']:
        x, y = px(*h['line'].coords[0])
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=(255, 255, 255, 230), outline=(200, 0, 0, 255), width=2)
        d.text((x, y), str(h['ref']), fill=(160, 0, 0, 255), font=f2, anchor='mm')
    img.convert('RGB').save(os.path.join(OUT, 'bunkers_edit.png'))
    print(img.size, len(polys), 'bunkers')


if __name__ == '__main__':
    main()
