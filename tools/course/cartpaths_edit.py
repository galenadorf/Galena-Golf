"""Cart paths: a first pass found on the aerial, and the map to correct it on. The paths are pale grey strips (near-equal red, green and blue, bright);
the detector keeps the thin ones inside the course boundary (wide pale things, parking lots, bunker sand, roofs and the roads are dropped), thins them to
a centre line and widens that to 2.4 m (PATH_W). Writes out/cartpaths_edit.png (the aerial at 3 px per metre, the found paths as a translucent yellow
guide), out/cartpaths_edit.json (its frame: e0, n1, ppm, w, h) and out/cartpaths_found.png (the found centre lines, one pixel per 0.5 m, for the reader).
Paint SOLID colours on a copy, saved as out/cartpaths_mask.png (hard edges, don't resize or crop):
  RED   #FF0000  a path the detector missed: any brush width, only its middle matters (the path is redrawn 2.4 m wide)
  BLUE  #0000FF  a found path (or part of one) that is not a cart path: paint over it to remove it
Everything else on the map (the yellow guide, grid, labels) is only a guide and is ignored."""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
from shapely.geometry import shape
from skimage.morphology import disk, skeletonize

import osm
from common import OUT
from preview import E0, N1, load_rgb

PATH_W = 2.4
BOX = (-420, -520, 420, 520)
PPM = 3
YD = .9144


def found_centres(rgb, res, F):
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = ((R + G + B) / 3 > 150) & ((R - B) < 32) & (np.abs(R - G) < 14) & ((R - B) > -5)
    m = ndi.binary_opening(m, iterations=1)
    wide = ndi.binary_opening(m, structure=disk(4))                    # parking lots, roads, roofs, bunker sand, bright greens: wider than a cart path
    m &= ~ndi.binary_dilation(wide, structure=disk(3))
    h, w = m.shape
    inside = np.zeros((h, w), bool)
    from rasterio import features as rfeat
    from rasterio.transform import from_origin
    bound = shape(json.load(open(os.path.join(OUT, 'boundary.json')))).buffer(2)
    tr = from_origin(E0, N1, res, res)
    inside = rfeat.rasterize([(bound, 1)], out_shape=(h, w), transform=tr, dtype='uint8').astype(bool)
    greens = [g['poly'] for g in F['green']]
    pj = os.path.join(OUT, 'practice.json')
    if os.path.exists(pj):
        greens.append(shape(json.load(open(pj))['green']))
    sand = [shape(g) for g in json.load(open(os.path.join(OUT, 'bunkers_painted.json')))] if os.path.exists(os.path.join(OUT, 'bunkers_painted.json')) else [b['poly'] for b in F['bunker']]
    skip = [r['line'].buffer(5) for r in F['road']] + [b['poly'].buffer(2) for b in F['building']] + [g.buffer(1.5) for g in greens] + [b.buffer(1.5) for b in sand]
    sk = rfeat.rasterize([(g, 1) for g in skip], out_shape=(h, w), transform=tr, dtype='uint8').astype(bool)
    m &= inside & ~sk
    lab, n = ndi.label(m, structure=np.ones((3, 3)))
    size = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, [i + 1 for i, s in enumerate(size) if s * res * res >= 12])
    m = ndi.binary_closing(m, structure=disk(2))
    sk = skeletonize(m)
    lab, n = ndi.label(sk, structure=np.ones((3, 3)))
    size = ndi.sum(sk, lab, range(1, n + 1))
    return np.isin(lab, [i + 1 for i, s in enumerate(size) if s * res >= 8])   # drop bits of line shorter than 8 m


def band(centre, res, width=PATH_W):
    r = width / 2 / res
    return ndi.distance_transform_edt(~centre) <= r


def render(rgb, res, F, guide=None):
    """The aerial of the whole course at PPM px per metre with the grid and hole numbers on it; `guide` (a boolean raster on the aerial's 0.5 m grid)
    is laid over it in translucent yellow. Returns the image and its frame."""
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    base = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    e0, n0, e1, n1 = BOX
    c = (int((e0 - E0) / res), int((N1 - n1) / res), int((e1 - E0) / res), int((N1 - n0) / res))
    k = PPM * res
    img = base.crop(c).resize((round((c[2] - c[0]) * k), round((c[3] - c[1]) * k)), Image.BICUBIC)
    if guide is not None:
        g = np.zeros(guide.shape + (4,), np.uint8)
        g[guide] = (255, 255, 0, 120)
        img = Image.alpha_composite(img, Image.fromarray(g[c[1]:c[3], c[0]:c[2]]).resize(img.size, Image.NEAREST))
    fe0, fn1 = E0 + c[0] * res, N1 - c[1] * res
    px = lambda e, n: ((e - fe0) * PPM, (fn1 - n) * PPM)
    W, H = img.size
    d = ImageDraw.Draw(img, 'RGBA')
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    for q in range(int(np.floor(fe0 / (100 * YD))), int(np.ceil((fe0 + W / PPM) / (100 * YD))) + 1):   # 100-yard grid
        x = px(q * 100 * YD, 0)[0]
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 60), width=1)
        d.text((x + 4, H - 30), f'E{q * 100}', fill=(255, 255, 255, 230), font=f2)
    for q in range(int(np.floor((fn1 - H / PPM) / (100 * YD))), int(np.ceil(fn1 / (100 * YD))) + 1):
        y = px(0, q * 100 * YD)[1]
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 60), width=1)
        d.text((4, y + 3), f'N{q * 100}', fill=(255, 255, 255, 230), font=f2)
    for h in F['hole']:
        x, y = px(*h['line'].coords[0])
        d.ellipse([x - 22, y - 22, x + 22, y + 22], fill=(255, 255, 255, 230), outline=(200, 0, 0, 255), width=2)
        d.text((x, y), str(h['ref']), fill=(160, 0, 0, 255), font=f2, anchor='mm')
    return img, dict(e0=fe0, n1=fn1, ppm=PPM, w=W, h=H), px


def legend(img, rows):
    d = ImageDraw.Draw(img, 'RGBA')
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    d.rectangle([60, 60, 760, 60 + 40 * len(rows) + 20], fill=(0, 0, 0, 190))
    for i, (col, t) in enumerate(rows):
        y = 76 + 40 * i
        d.rectangle([76, y, 116, y + 28], fill=col + (255,))
        d.text((132, y + 14), t, fill=(255, 255, 255, 255), font=f2, anchor='lm')


def main():
    F = osm.load()
    rgb, res = load_rgb()
    cen = found_centres(rgb, res, F)
    Image.fromarray((cen * 255).astype(np.uint8)).save(os.path.join(OUT, 'cartpaths_found.png'))
    json.dump({'e0': E0, 'n1': N1, 'res': res, 'w': cen.shape[1], 'h': cen.shape[0]}, open(os.path.join(OUT, 'cartpaths_found.json'), 'w'))
    img, fr, _ = render(rgb, res, F, band(cen, res))
    legend(img, [((255, 255, 0), 'YELLOW (guide): paths found'), ((255, 0, 0), 'RED: a path that is missing'), ((0, 0, 255), 'BLUE: found, but not a cart path')])
    img.convert('RGB').save(os.path.join(OUT, 'cartpaths_edit.png'))
    json.dump(fr, open(os.path.join(OUT, 'cartpaths_edit.json'), 'w'))
    print(img.size, 'px;', int(cen.sum() * res), 'm of path found')


if __name__ == '__main__':
    main()
