"""A clean paint sheet: the course's aerial on the all-in-one frame (nothing pre-painted, no outlines) with the whole colour key on its right.

Ground cover left unpainted is regular rough, even under tree lines. Paint only what is not: fairway, green, tee, bunker, deep rough (fescue), water, ...
The key panel is the sheet's right-hand strip: all_read.py wants the map's own size (see out/all_edit.json), so crop the saved mask to its first `w` px
(or use out/all_paint_aerial.png, the same aerial without the key, as the canvas). Usage: python paint_sheet.py --course champions
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import all_edit
from common import OUT
from preview import E0, N1, load_rgb

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans'
# the Legends' whole key (all_key.png + extras_key.png) plus water for the Champions; (colour, what, how)
ALL = [
    ('fairway', 'fairway', 'area'),
    ('green', 'putting green (the collar is added)', 'area'),
    ('tee', 'tee box (every one)', 'area'),
    ('bunker', 'bunker', 'area'),
    ('fescue', 'fescue: the tall deep rough', 'area'),
    ('pond', 'pond / lake (flat water)', 'area'),
    ('path', 'cart path (redrawn 2.4 m wide along the middle)', 'line, any width'),
    ('fence', '2-rail split-rail cedar fence = hard out of bounds', 'line, 2-3 px'),
    ('clump', 'sawgrass / switchgrass clump, 5 ft', 'dot ~3 px = one; area = clumps ~2 m apart'),
    ('drain', 'drainage pipe hazard, rock-lined', 'area'),
    ('tee_dot', "where a hole's played tee should be", 'dot ~3 m in its tee box'),
    ('lot', 'parking lot', 'area, next to its building'),
    ('wash', 'washroom building', 'rectangle'),
]
EXTRA = [  # the extras map (trees, creek): these two reuse colours of the map above
    ((255, 0, 255), 'X out a tree (bold X over its ring)', 'one X, one tree  [same colour as fescue]'),
    ((0, 128, 0), 'add a broadleaf tree', 'filled circle = crown size; area = grove'),
    ((0, 64, 255), 'add a conifer', 'filled circle; area = stand'),
    ((128, 0, 128), 'add shrubs', 'filled circle / area'),
    ((0, 255, 255), 'creek (centre line of the water)', 'line  [same colour as boundary]'),
    ((0, 255, 255), 'out-of-bounds line', 'one closed line round the course'),
]


def main():
    fr = all_edit.frame()
    rgb, res = load_rgb()
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    c0, r0 = int(round((fr['e0'] - E0) / res)), int(round((N1 - fr['n1']) / res))
    a = np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)
    base = np.zeros((fr['h'], fr['w'], 3), np.uint8)
    sub = a[max(r0, 0):r0 + fr['h'], max(c0, 0):c0 + fr['w']]
    base[max(-r0, 0):max(-r0, 0) + sub.shape[0], max(-c0, 0):max(-c0, 0) + sub.shape[1]] = sub
    Image.fromarray(base).save(os.path.join(OUT, 'all_paint_aerial.png'))

    f1, f2 = ImageFont.truetype(FONT + '-Bold.ttf', 26), ImageFont.truetype(FONT + '.ttf', 21)
    W = 1250
    rows = [(all_edit.PALETTE[k][0], w, h) for k, w, h in ALL]
    H = fr['h']
    panel = Image.new('RGB', (W, H), (34, 34, 34))
    d = ImageDraw.Draw(panel)
    d.text((24, 24), 'COLOURS  (Pencil tool, hard edges, no anti-aliasing)', fill=(255, 255, 255), font=f1)
    d.text((24, 64), 'Unpainted ground = regular rough, even under tree lines.', fill=(255, 220, 120), font=f2)
    d.text((24, 94), 'Paint only what is NOT regular rough (deep rough, water, ...).', fill=(255, 220, 120), font=f2)
    y = 150
    for title, items in (('Ground and features', rows), ('Trees and creek (extras map)', EXTRA)):
        d.text((24, y), title, fill=(255, 255, 255), font=f1)
        y += 50
        for c, what, how in items:
            d.rectangle([24, y, 110, y + 46], fill=c, outline=(255, 255, 255))
            d.text((130, y), '#%02X%02X%02X' % c, fill=(255, 255, 255), font=f1)
            d.text((300, y + 2), what, fill=(230, 230, 230), font=f2)
            d.text((300, y + 26), how, fill=(160, 160, 160), font=f2)
            y += 66
        y += 24
    assert y < H
    out = Image.new('RGB', (fr['w'] + W, H), (34, 34, 34))
    out.paste(Image.fromarray(base), (0, 0))
    out.paste(panel, (fr['w'], 0))
    out.save(os.path.join(OUT, 'all_paint_sheet.png'))
    json.dump(fr, open(os.path.join(OUT, 'all_edit.json'), 'w'))
    print('all_paint_sheet.png', out.size, '; map is the first', fr['w'], 'px; all_paint_aerial.png')


if __name__ == '__main__':
    main()
