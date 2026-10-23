"""One big aerial of the whole course and Route 20 (US 20) beside it, to paint the tee boxes and the entrance sign on. Writes
out/paint_edit.png (the 0.5 m aerial enlarged to 4 px per metre) and out/paint_edit.json (its frame:
e0, n1, ppm, w, h). Paint SOLID colours on a copy, saved as out/paint_mask.png (hard edges, no anti-aliasing, don't resize or crop):
  MAGENTA #FF00FF  a tee box: fill the whole box, one blob per box. The current boxes are pink outlines; a current box with no magenta
                   on or near it is kept as it is, so only repaint the ones that are wrong or missing.
  YELLOW  #FFFF00  (optional) a dot about 10+ px across where a hole's played (gold) tee should be; the hole whose line passes
                   nearest to it gets that start.
  PURPLE  #8000FF  the big Woodbine Bend entrance sign: ONE filled rectangle (any rotation) for the sign and its flower bed. Its long
                   side is the board's width (drawn about 7 m wide, so a bed 8-9 m by 2-3 m suits), the short side the bed's depth.
  BLUE    #0000FF  (optional) a thin strip, 4+ px, just outside the long side of the purple rectangle that the lettering faces (the lettering
                   side). With no strip the sign faces INWARD, toward the nearest part of the course.
Everything else on the map (grid, outlines, rings, labels, the key in the top-left corner) is only a guide and is ignored."""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import shape

import build
import osm
from common import OUT
from preview import E0, N1, load_rgb

YD = .9144

BOX = (-450, -540, 450, 600)   # local metres: west, south, east, north (the course, and US 20 along its north and west side)
PPM = 4                    # pixels per metre
KEY_BOX = (60, 60, 60 + 760, 60 + 40 * 4 + 20)   # the key printed on the map is ignored by paint_read.py


def main():
    F = osm.load()
    rgb, res = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    base = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)).convert('RGBA')
    e0, n0, e1, n1 = BOX
    c = (int((e0 - E0) / res), int((N1 - n1) / res), int((e1 - E0) / res), int((N1 - n0) / res))
    k = PPM * res
    img = base.crop(c).resize((round((c[2] - c[0]) * k), round((c[3] - c[1]) * k)), Image.BICUBIC)
    fe0, fn1 = E0 + c[0] * res, N1 - c[1] * res
    px = lambda e, n: ((e - fe0) * PPM, (fn1 - n) * PPM)
    d = ImageDraw.Draw(img, 'RGBA')
    W, H = img.size
    f1 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 30)
    f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
    for q in range(int(np.floor(fe0 / (100 * YD))), int(np.ceil((fe0 + W / PPM) / (100 * YD))) + 1):   # 100-yard grid
        x = px(q * 100 * YD, 0)[0]
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 60), width=1)
        d.text((x + 4, H - 30), f'E{q * 100}', fill=(255, 255, 255, 230), font=f2)
    for q in range(int(np.floor((fn1 - H / PPM) / (100 * YD))), int(np.ceil(fn1 / (100 * YD))) + 1):
        y = px(0, q * 100 * YD)[1]
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 60), width=1)
        d.text((4, y + 3), f'N{q * 100}', fill=(255, 255, 255, 230), font=f2)
    outline = lambda g, col, w=2: [d.line([px(*q) for q in p.exterior.coords], fill=col, width=w) for p in getattr(g, 'geoms', [g])]
    for f in F['tee']:
        outline(f['poly'], (255, 120, 255, 255))
    for f in F['green']:
        outline(f['poly'], (255, 255, 255, 255))
    for f in F['building']:
        outline(f['poly'], (255, 200, 80, 255))
    for g in json.load(open(os.path.join(OUT, 'fairways_painted.json'))):
        outline(shape(g), (60, 230, 60, 255), 1)
    hw, _ = build.highway()
    d.line([px(*q) for q in hw.coords], fill=(255, 140, 40, 200), width=3)
    x, y = px(*hw.interpolate(hw.project(shape({'type': 'Point', 'coordinates': (200, 541)}))).coords[0])
    d.text((x, y - 40), 'ROUTE 20 (US 20)', fill=(255, 140, 40, 255), font=f1, stroke_width=3, stroke_fill=(0, 0, 0, 255))
    js = open(os.path.join(OUT, 'rd_woodbine.js')).read()
    rd = json.loads(js[js.index('{'):js.rindex('};\nconst GREEN_ALTI') + 1])
    cols = {'w': (217, 178, 58, 255), 'y': (20, 20, 20, 255), 'b': (235, 240, 245, 255), 'r': (176, 112, 69, 255)}
    for h in rd['holes']:   # where each tee set plays from now
        for kk, col in cols.items():
            x, y = px(*h['mk'][kk])
            d.ellipse([x - 8, y - 8, x + 8, y + 8], outline=col, width=3)
    for h in F['hole']:
        x, y = px(*h['line'].coords[0])
        d.ellipse([x - 52, y - 52, x - 8, y - 8], fill=(255, 255, 255, 230), outline=(200, 0, 0, 255), width=2)
        d.text((x - 30, y - 30), str(h['ref']), fill=(160, 0, 0, 255), font=f2, anchor='mm')
    d.rectangle(KEY_BOX, fill=(0, 0, 0, 190))
    for i, (col, t) in enumerate([((255, 0, 255), 'MAGENTA: fill each tee box'), ((255, 255, 0), 'YELLOW dot: the played (gold) tee'),
                                  ((128, 0, 255), 'PURPLE rectangle: the entrance sign + bed'), ((0, 0, 255), 'BLUE strip: the lettering side')]):
        y = 76 + 40 * i
        d.rectangle([76, y, 116, y + 28], fill=col + (255,))
        d.text((132, y + 14), t, fill=(255, 255, 255, 255), font=f1, anchor='lm')
    L = 10 * YD * PPM
    d.line([(76, KEY_BOX[3] + 30), (76 + L, KEY_BOX[3] + 30)], fill=(255, 255, 255, 255), width=5)
    d.text((96 + L, KEY_BOX[3] + 30), '= 10 yd', fill=(255, 255, 255, 255), font=f2, anchor='lm')
    img.convert('RGB').save(os.path.join(OUT, 'paint_edit.png'))
    json.dump({'e0': fe0, 'n1': fn1, 'ppm': PPM, 'w': W, 'h': H}, open(os.path.join(OUT, 'paint_edit.json'), 'w'))
    print(img.size, 'px,', PPM, 'px per metre')


if __name__ == '__main__':
    main()
