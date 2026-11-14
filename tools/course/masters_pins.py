"""Augusta National's four hole-location sheets of the 2026 Masters (rounds 1-4, Thursday to Sunday), read into
courses/augusta/pins.json: for each hole and round the pin's depth from the front of the green and its sideways place between the
left and right edges of the green, as the player stands on the approach.

The sheets are the club's official hole-location diagrams (one green per tile, the black dots the front and the back of the green, the red
dot the hole, a number for the yards onto the green and a number for the yards to the nearest edge), as published by Golf News Net:
https://thegolfnewsnet.com/golfnewsnetteam/2026/04/09/ (Thursday), /10/ (Friday), /11/ (Saturday), /12/ (Sunday) 2026-masters-*-hole-locations.
They are downloaded into the course's .cache/ (never committed) and read off the picture: the two black dots give the front and back of
the green (the sheet's vertical), the red dot the hole, and the green's light-green outline along the hole's row gives the left and right
edges. Depth = (front - hole) / (front - back) * the green's depth (the sheet gives each green's depth in yards: DEPTH); the sideways
place t = the distance to the left edge / the width at that row (0 = left edge, 1 = right edge). The numbers printed on the sheets agree
with what is read here (checked by eye on rounds 1 and 2: depth within 1.5 yd, edge distance within 1.5 yd).

  python3 masters_pins.py            writes courses/augusta/pins.json
"""
import json
import os
import urllib.request

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'courses', 'augusta', '.cache')
B = 'https://thegolfnewsnet.com/wp-content/uploads/2026/04/'
SHEETS = ['2026-masters-thursday-round-1-pin-sheet.jpg', '2026-masters-friday-round-2-pin-sheet.jpg',
          '2026-masters-saturday-round-2-pin-sheet.jpg', '2026-masters-sunday-round-4-pin-sheet.jpg']   # (the Saturday file is named round-2: it is the 3rd round)
DEPTH = {1: 35.5, 2: 38, 3: 29, 4: 35, 5: 41, 6: 30.5, 7: 19, 8: 40, 9: 38, 10: 34.5, 11: 43, 12: 26, 13: 41.5, 14: 38, 15: 24, 16: 42, 17: 32, 18: 35}   # yards, front to back, as printed under each tile
# the tiles (x0, x1) per column and (y0, y1) per row, in the 1638 x 2048 pictures
GRID = {
    0: ([(344, 591), (718, 966), (1092, 1339)], [(332, 559), (571, 797), (808, 1035), (1065, 1292), (1303, 1530), (1541, 1768)]),
    1: ([(344, 589), (711, 954), (1076, 1319)], [(347, 569), (579, 802), (813, 1035), (1063, 1285), (1295, 1519), (1529, 1752)]),
    2: ([(357, 599), (722, 963), (1086, 1328)], [(325, 546), (557, 778), (790, 1011), (1040, 1261), (1272, 1493), (1504, 1726)]),
    3: ([(343, 592), (716, 965), (1091, 1339)], [(331, 558), (570, 797), (809, 1036), (1066, 1293), (1304, 1532), (1543, 1770)]),
}
HOLES = [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12], [13, 14, 15, 16, 17, 18]]


def tile(rnd, hole):
    cols, rows = GRID[rnd]
    for c, col in enumerate(HOLES):
        if hole in col:
            return cols[c], rows[col.index(hole)]


def fetch(i):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f'pinsheet{i + 1}.jpg')
    if not os.path.exists(p):
        req = urllib.request.Request(B + SHEETS[i], headers={'User-Agent': 'Mozilla/5.0'})
        open(p, 'wb').write(urllib.request.urlopen(req, timeout=60).read())
    return p


def read_round(i):
    im = np.array(Image.open(fetch(i)).convert('RGB')).astype(int)
    out = {}
    for h in range(1, 19):
        (x0, x1), (y0, y1) = tile(i, h)
        T = im[y0 - 4:y1 + 5, x0 - 4:x1 + 5]; ox, oy = x0 - 4, y0 - 4
        op = ndi.binary_opening(T.max(axis=2) < 80, structure=np.ones((5, 5)))
        lab, k = ndi.label(op)
        ys = sorted(float(np.nonzero(lab == j)[0].mean()) + oy for j in range(1, k + 1) if 12 <= (lab == j).sum() <= 260)
        red = (T[:, :, 0] > 150) & (T[:, :, 1] < 90) & (T[:, :, 2] < 90); rl, rk = ndi.label(red)
        reds = [ndi.center_of_mass(rl == j) for j in range(1, rk + 1) if (rl == j).sum() >= 25]
        assert len(reds) == 1 and 1 <= len(ys) <= 2, (i + 1, h, len(reds), len(ys))
        py, px = reds[0][0] + oy, reds[0][1] + ox
        yb = ys[0]; yf = ys[-1] if len(ys) == 2 else y1 - 2   # (hole 13's front dot sits on the tile's bottom edge)
        ppy = (yf - yb) / DEPTH[h]
        ip = int(round(px - x0)); Ls, Rs = [], []
        for dy in range(-4, 5):   # the green's outline (a light green stroke) left and right of the hole, on a few rows
            row = im[int(round(py)) + dy, x0:x1]; r, g, b = row[:, 0], row[:, 1], row[:, 2]
            om = (g > 195) & (g - r > 20) & (g - b > 20) & (r < 225)
            lf = [j for j in range(ip - 3, -1, -1) if om[j]]; rt = [j for j in range(ip + 3, len(om)) if om[j]]
            if lf: Ls.append(ip - lf[0])
            if rt: Rs.append(rt[0] - ip)
        L, R = float(np.median(Ls)) / ppy, float(np.median(Rs)) / ppy
        depth = (yf - py) / ppy
        out[h] = dict(f=round(depth / DEPTH[h], 3), t=round(L / (L + R), 3), depth=round(depth, 1), left=round(L, 1), right=round(R, 1))
    return out


if __name__ == '__main__':
    rounds = [read_round(i) for i in range(4)]
    res = {str(h): [[rounds[i][h]['f'], rounds[i][h]['t']] for i in range(4)] for h in range(1, 19)}
    raw = {str(h): [rounds[i][h] for i in range(4)] for h in range(1, 19)}
    json.dump(dict(source='2026 Masters hole-location sheets, rounds 1-4 (see tools/course/masters_pins.py)', pins=res, raw=raw), open(os.path.join(HERE, 'courses', 'augusta', 'pins.json'), 'w'), indent=1)
    print('wrote courses/augusta/pins.json')
