"""A map to correct the creek on: the aerial of the creek corridor (east -460..600 m, north -700..160 m, 0.5 m per pixel, its own
frame in out/creek_edit.json) with the current creek filled in solid pure BLUE (#0000FF), thin outlines of the ponds (cyan),
greens (white), the course boundary (white) and the 100-yard grid.
Paint blue over any stretch of creek that is missing or too narrow, and over (or erase) blue that is not creek. Paint it as wide
as the water really is; a branch or a pond-fed ditch is fine. Save as out/creek_mask.png (hard edges, don't resize or crop);
creek_paint.py reads it. Writes out/creek_edit.png and out/creek_edit.json."""
import json
import os

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape

import osm
from common import OUT, cache
from build import creek_pieces

YD = .9144
FRAME = dict(e0=-460.0, n1=160.0, e1=600.0, n0=-700.0)


def main():
    with rasterio.open(cache('naip.tif')) as s:
        rgb = s.read([1, 2, 3]).transpose(1, 2, 0).astype(np.float32)
        tr = s.transform
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    res = .5
    x0, y0 = [int(round(v)) for v in ~tr * (FRAME['e0'], FRAME['n1'])]
    w, h = int((FRAME['e1'] - FRAME['e0']) / res), int((FRAME['n1'] - FRAME['n0']) / res)
    img = Image.fromarray(np.clip((rgb[y0:y0 + h, x0:x0 + w] - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    assert img.size == (w, h), img.size
    px = lambda e, n: ((e - FRAME['e0']) / res, (FRAME['n1'] - n) / res)
    d = ImageDraw.Draw(img, 'RGBA')
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    for k in range(int(np.floor(FRAME['e0'] / (100 * YD))), int(np.ceil(FRAME['e1'] / (100 * YD))) + 1):
        x = px(k * 100 * YD, 0)[0]
        d.line([(x, 0), (x, h)], fill=(255, 255, 255, 70), width=1)
        d.text((x + 3, 3), f'E{k * 100}', fill=(255, 255, 255, 230), font=font)
    for k in range(int(np.floor(FRAME['n0'] / (100 * YD))), int(np.ceil(FRAME['n1'] / (100 * YD))) + 1):
        y = px(0, k * 100 * YD)[1]
        d.line([(0, y), (w, y)], fill=(255, 255, 255, 70), width=1)
        d.text((3, y + 3), f'N{k * 100}', fill=(255, 255, 255, 230), font=font)
    outline = lambda g, col: [d.line([px(*c) for c in q.exterior.coords], fill=col, width=1) for q in getattr(g, 'geoms', [g])]
    F = osm.load()
    outline(shape(json.load(open(os.path.join(OUT, 'boundary.json')))), (255, 255, 255, 255))
    for f in F['water']:
        outline(f['poly'], (0, 255, 255, 255))
    for f in F['green']:
        outline(f['poly'], (255, 255, 255, 255))
    for p in creek_pieces():  # the current creek, solid
        for q in getattr(p, 'geoms', [p]):
            d.polygon([px(*c) for c in q.exterior.coords], fill=(0, 0, 255, 255))
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    for hh in F['hole']:
        x, y = px(*hh['line'].coords[0])
        if 0 <= x < w and 0 <= y < h:
            d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=(255, 255, 255, 230), outline=(200, 0, 0, 255), width=2)
            d.text((x, y), str(hh['ref']), fill=(160, 0, 0, 255), font=f2, anchor='mm')
    img.convert('RGB').save(os.path.join(OUT, 'creek_edit.png'))
    json.dump(dict(e0=FRAME['e0'], n1=FRAME['n1'], res=res, w=w, h=h), open(os.path.join(OUT, 'creek_edit.json'), 'w'))
    print(img.size)


if __name__ == '__main__':
    main()
