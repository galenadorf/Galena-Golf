"""A map to add missing trees on: the whole 1.4 km detail area from the aerial, with the 824 lidar trees outlined thin
(yellow broadleaf, cyan conifer, orange shrub), the course boundary in white, hole numbers and a 100-yard grid.
Paint solid ORANGE (#FF8000) over broadleaf trees or groves that are missing and solid BLUE (#0080FF) over conifers,
save as out/trees_mask.png (same pixels); trees_paint.py turns the paint into trees (a small dot is one tree sized to the
dot, a bigger patch is filled with trees about 6 m apart). Writes out/trees_edit.png and out/trees_edit.json."""
import json
import os

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape

import osm
from common import DETAIL, OUT, cache

YD = .9144
E0, N0, E1, N1 = DETAIL


def main():
    with rasterio.open(cache('naip.tif')) as s:
        rgb = s.read([1, 2, 3]).transpose(1, 2, 0).astype(np.float32)
    res = (E1 - E0) / rgb.shape[1]
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    img = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    px = lambda e, n: ((e - E0) / res, (N1 - n) / res)
    d = ImageDraw.Draw(img, 'RGBA')
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
    for k in range(int(np.floor(E0 / (100 * YD))), int(np.ceil(E1 / (100 * YD))) + 1):
        x = px(k * 100 * YD, 0)[0]
        d.line([(x, 0), (x, img.size[1])], fill=(255, 255, 255, 60), width=1)
        d.text((x + 3, 3), f'E{k * 100}', fill=(255, 255, 255, 230), font=font)
    for k in range(int(np.floor(N0 / (100 * YD))), int(np.ceil(N1 / (100 * YD))) + 1):
        y = px(0, k * 100 * YD)[1]
        d.line([(0, y), (img.size[0], y)], fill=(255, 255, 255, 60), width=1)
        d.text((3, y + 3), f'N{k * 100}', fill=(255, 255, 255, 230), font=font)
    bound = shape(json.load(open(os.path.join(OUT, 'boundary.json'))))
    d.line([px(*c) for c in bound.exterior.coords], fill=(255, 255, 255, 220), width=2)
    for t in json.load(open(os.path.join(OUT, 'trees.json'))):
        x, y = px(t['e'], t['n']); r = max(2, t['d'] / 2 / res)
        d.ellipse([x - r, y - r, x + r, y + r], outline={0: (255, 235, 60, 255), 1: (255, 170, 60, 255), 2: (60, 230, 255, 255)}[t['kind']], width=1)
    big = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    for h in osm.load()['hole']:
        x, y = px(*h['line'].coords[0])
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=(255, 255, 255, 230), outline=(200, 0, 0, 255), width=2)
        d.text((x, y), str(h['ref']), fill=(160, 0, 0, 255), font=big, anchor='mm')
    img.convert('RGB').save(os.path.join(OUT, 'trees_edit.png'))
    json.dump(dict(e0=E0, n1=N1, res=res, w=img.size[0], h=img.size[1]), open(os.path.join(OUT, 'trees_edit.json'), 'w'))
    print(img.size, res, 'm/px')


if __name__ == '__main__':
    main()
