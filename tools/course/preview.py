"""Overview images in out/: the aerial (and a hillshade) with the OSM features drawn on top.

  python preview.py [layers...]     layers: osm (default), fair (traced fairways from out/fairways.json)
"""
import json
import os
import sys

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont

from common import DETAIL, OUT, cache
import osm

E0, N0, E1, N1 = DETAIL


def load_rgb():
    with rasterio.open(cache('naip.tif')) as s:
        a = s.read([1, 2, 3]).transpose(1, 2, 0).astype(np.float32)
    return a, (E1 - E0) / a.shape[1]


def hillshade(scale_to):
    with rasterio.open(cache('dem1m.tif')) as s:
        z = s.read(1)
    gy, gx = np.gradient(z)
    az, alt = np.radians(315), np.radians(40)
    sl = np.arctan(np.hypot(gx, gy) * 2)
    asp = np.arctan2(-gx, gy)
    hs = np.sin(alt) * np.cos(sl) + np.cos(alt) * np.sin(sl) * np.cos(az - asp)
    im = Image.fromarray(np.clip(hs * 255, 0, 255).astype(np.uint8)).resize(scale_to, Image.BILINEAR)
    return im, z


def draw(img, res, F, fair=None, paths=None):
    d = ImageDraw.Draw(img, 'RGBA')
    px = lambda e, n: ((e - E0) / res, (N1 - n) / res)

    def poly(p, fill, outline, wid=2):
        geoms = getattr(p, 'geoms', [p])
        for g in geoms:
            d.polygon([px(*c) for c in g.exterior.coords], fill=fill, outline=outline, width=wid)

    for f in F.get('wood', []):
        poly(f['poly'], (20, 90, 20, 40), (20, 120, 20, 200), 2)
    for f in F.get('water', []):
        poly(f['poly'], (40, 120, 255, 90), (40, 120, 255, 255), 2)
    for f in F.get('stream', []):
        d.line([px(*c) for c in f['line'].coords], fill=(40, 160, 255, 255), width=3)
    for p in paths or []:
        poly(p, (255, 255, 255, 110), (90, 90, 90, 255), 1)
    if fair:
        for p in fair:
            poly(p, (255, 255, 0, 50), (255, 230, 0, 255), 2)
    for f in F.get('tee', []):
        poly(f['poly'], (255, 255, 255, 70), (255, 255, 255, 255), 2)
    for f in F.get('green', []):
        poly(f['poly'], (60, 255, 60, 70), (60, 255, 60, 255), 3)
    for f in F.get('bunker', []):
        poly(f['poly'], (255, 230, 150, 120), (255, 200, 80, 255), 2)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 40)
    except OSError:
        font = ImageFont.load_default()
    for h in F['hole']:
        c = [px(*c) for c in h['line'].coords]
        d.line(c, fill=(255, 40, 40, 255), width=3)
        x, y = c[0]
        d.ellipse([x - 26, y - 26, x + 26, y + 26], fill=(255, 255, 255, 230), outline=(200, 0, 0, 255), width=3)
        d.text((x, y), str(h['ref']), fill=(160, 0, 0, 255), font=font, anchor='mm')
    for f in F.get('pin', []):
        x, y = px(f['pt'].x, f['pt'].y)
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(255, 0, 0, 255))


def crop_course(img, res, F, pad=60):
    b = F['course'][0]['poly'].bounds
    box = (int((b[0] - pad - E0) / res), int((N1 - b[3] - pad) / res), int((b[2] + pad - E0) / res), int((N1 - b[1] + pad) / res))
    return img.crop(box)


if __name__ == '__main__':
    layers = sys.argv[1:] or ['osm']
    F = osm.load()
    rgb, res = load_rgb()
    # stretch the aerial a little (NAIP is dark)
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    img = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    fair = None
    if 'fair' in layers and os.path.exists(os.path.join(OUT, 'fairways.json')):
        from shapely.geometry import shape
        fair = [shape(g) for g in json.load(open(os.path.join(OUT, 'fairways.json')))]
        paths = [shape(g) for g in json.load(open(os.path.join(OUT, 'paths.json')))]
    else:
        paths = None
    draw(img, res, F, fair, paths)
    out = crop_course(img, res, F)
    out.convert('RGB').save(os.path.join(OUT, 'aerial_' + '_'.join(layers) + '.jpg'), quality=88)
    hs, _ = hillshade(img.size)
    hs = hs.convert('RGBA')
    draw(hs, res, F, fair, paths)
    crop_course(hs, res, F).convert('RGB').save(os.path.join(OUT, 'relief_' + '_'.join(layers) + '.jpg'), quality=88)
    print('wrote', out.size)
