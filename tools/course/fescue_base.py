"""A base map to paint the fescue areas on: the aerial, cropped to the course, with thin outlines of the fairways, greens,
tees, bunkers and water, the hole numbers and a 100-yard grid. Writes out/fescue_base.png (lossless, same pixel grid as the
mask that fescue.py reads back) and out/fescue_base.json (the crop's local-metre frame)."""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape

import osm
from common import OUT
from preview import E0, N1, load_rgb

YD = .9144


def main(pad=40):
    F = osm.load()
    rgb, res = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    img = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    b = F['course'][0]['poly'].bounds
    e0, n0, e1, n1 = b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad
    box = (int((e0 - E0) / res), int((N1 - n1) / res), int((e1 - E0) / res), int((N1 - n0) / res))
    img = img.crop(box)
    px = lambda e, n: ((e - E0) / res - box[0], (N1 - n) / res - box[1])
    d = ImageDraw.Draw(img, 'RGBA')
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    # 100-yard grid, labelled in yards from the course origin
    k0, k1 = int(np.floor(e0 / (100 * YD))), int(np.ceil(e1 / (100 * YD)))
    for k in range(k0, k1 + 1):
        x = px(k * 100 * YD, 0)[0]
        d.line([(x, 0), (x, img.size[1])], fill=(255, 255, 255, 70), width=1)
        d.text((x + 3, 3), f'E{k * 100}', fill=(255, 255, 255, 230), font=font)
    m0, m1 = int(np.floor(n0 / (100 * YD))), int(np.ceil(n1 / (100 * YD)))
    for k in range(m0, m1 + 1):
        y = px(0, k * 100 * YD)[1]
        d.line([(0, y), (img.size[0], y)], fill=(255, 255, 255, 70), width=1)
        d.text((3, y + 3), f'N{k * 100}', fill=(255, 255, 255, 230), font=font)

    def outline(g, col):
        for p in getattr(g, 'geoms', [g]):
            d.line([px(*c) for c in p.exterior.coords], fill=col, width=1)
    fair = [shape(g) for g in json.load(open(os.path.join(OUT, 'fairways.json')))]
    for p in fair:
        outline(p, (255, 235, 60, 255))
    for k, col in (('green', (60, 255, 60, 255)), ('tee', (255, 255, 255, 255)), ('bunker', (255, 160, 60, 255)), ('water', (60, 140, 255, 255))):
        for f in F.get(k, []):
            outline(f['poly'], col)
    for h in F['hole']:
        x, y = px(*h['line'].coords[0])
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=(255, 255, 255, 230), outline=(200, 0, 0, 255), width=2)
        d.text((x, y), str(h['ref']), fill=(160, 0, 0, 255), font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20), anchor='mm')
    img.convert('RGB').save(os.path.join(OUT, 'fescue_base.png'))
    json.dump(dict(e0=E0 + box[0] * res, n1=N1 - box[1] * res, res=res, w=img.size[0], h=img.size[1]), open(os.path.join(OUT, 'fescue_base.json'), 'w'))
    print(img.size, 'px,', res, 'm/px')


if __name__ == '__main__':
    main()
