"""A map to place site buildings and signs on: the aerial (same pixels as out/fescue_base.png) with the 100-yard grid, hole
numbers, tee boxes (pink outline), greens (white), the existing buildings (white) and a colour key in the top-left corner.

Paint SOLID colours on a copy, saved as out/site_mask.png (hard edges, no anti-aliasing, don't resize or crop):
  CYAN    #00FFFF  a double washroom: fill its footprint as one rectangle (any rotation). Size and angle are read from it.
  BLUE    #0000FF  (optional) the washroom's door side: a strip 1-2 px thick just outside one long side of the rectangle
                   (touching it). With no strip the doors face the nearest tee box.
  ORANGE  #FF8000  a porta-potty: a small solid blob (3-4 px square is enough; it is always drawn 1.25 m square). Its door faces
                   the nearest tee box.
  YELLOW  #FFFF00  a signpost: one small solid dot, 3-4 px, in the ground at the spot. The board faces the nearest tee box. Its
                   message comes from out/signs.txt (see site_paint.py), or by default 'HOLE n / PAR p . yards' for the hole
                   whose tee is nearest.
Writes out/site_edit.png."""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import osm
from common import OUT
from preview import E0, N1, load_rgb

YD = .9144
KEY = [((0, 255, 255), 'washroom: fill the footprint'), ((0, 0, 255), 'door side (optional): a thin strip'), ((255, 128, 0), 'porta-potty: small blob'), ((255, 255, 0), 'signpost: small dot')]


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
    for k, col in (('tee', (255, 150, 255, 255)), ('green', (255, 255, 255, 255)), ('building', (255, 255, 255, 255))):
        for f in F.get(k, []):
            outline(f['poly'], col)
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
    for h in F['hole']:
        x, y = px(*h['line'].coords[0])
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=(255, 255, 255, 230), outline=(200, 0, 0, 255), width=2)
        d.text((x, y), str(h['ref']), fill=(160, 0, 0, 255), font=f2, anchor='mm')
    d.rectangle([60, 60, 60 + 470, 60 + 34 * len(KEY) + 16], fill=(0, 0, 0, 170))  # the colour key
    for i, (c, t) in enumerate(KEY):
        y = 72 + 34 * i
        d.rectangle([72, y, 100, y + 24], fill=c + (255,))
        d.text((112, y + 12), t, fill=(255, 255, 255, 255), font=font, anchor='lm')
    img.convert('RGB').save(os.path.join(OUT, 'site_edit.png'))
    print(img.size)


if __name__ == '__main__':
    main()
