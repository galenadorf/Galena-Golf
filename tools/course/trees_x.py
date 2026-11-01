"""Take trees out by marking them with an X on a picture (any course whose out/ has all_guide.png: `all_edit.py` makes it).

  trees_x.py guide   writes out/trees_guide.png: all_guide.png with every tree the game has drawn as a bold ring (yellow broadleaf, cyan
                     conifer, a number every 50th tree is not needed: use the grid and hole numbers), trees already removed in grey.
  trees_x.py read    reads out/trees_x.png (your painted copy of trees_guide.png or all_guide.png, same size, never resized or cropped) and
                     writes out/trees_x_removed.json and out/trees_x_check.png. Rerun build.py and install.py afterwards.

Paint a bold X (any size, from a few pixels to the width of the crown) in solid magenta #FF00FF with a hard-edged tool, over the tree's ring.
Each X takes out ONE tree: the ring that contains the middle of the X (the nearest centre if two rings do), else the ring it touches. Keep
editing trees_x.png: every X on it counts each time (the list is rebuilt from the picture, so erasing an X puts the tree back).
An X that finds no tree, or that is much wider than any tree (a big X may mean several trees: it still takes out one), is reported.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

from common import OUT

Image.MAX_IMAGE_PIXELS = None
X_COL = (255, 0, 255)


def frame():
    return json.load(open(os.path.join(OUT, 'all_edit.json')))


def trees_all():
    p = os.path.join(OUT, 'trees_all.json')
    if not os.path.exists(p):
        sys.exit('out/trees_all.json is missing: run build.py first')
    return json.load(open(p))


def removed():
    p = os.path.join(OUT, 'trees_x_removed.json')
    return {(round(g['e'], 2), round(g['n'], 2)) for g in json.load(open(p))} if os.path.exists(p) else set()


def guide():
    fr = frame(); ppm = fr['ppm']
    g = Image.open(os.path.join(OUT, 'all_guide.png')).convert('RGB')
    d = ImageDraw.Draw(g)
    gone = removed()
    for t in trees_all():
        x, y = (t['e'] - fr['e0']) * ppm, (fr['n1'] - t['n']) * ppm
        r = max(2.0, t['d'] / 2 * ppm)
        col = (140, 140, 140) if (round(t['e'], 2), round(t['n'], 2)) in gone else (255, 235, 0) if t['kind'] == 0 else (0, 230, 255) if t['kind'] == 2 else (120, 255, 120)
        d.ellipse([x - r, y - r, x + r, y + r], outline=col, width=2)
    g.save(os.path.join(OUT, 'trees_guide.png'))
    print('out/trees_guide.png', g.size, '(yellow broadleaf, cyan conifer, green shrub, grey = already removed). Paint magenta #FF00FF X marks on a copy, save it as out/trees_x.png')


def read():
    fr = frame(); ppm = fr['ppm']
    path = os.path.join(OUT, 'trees_x.png')
    if not os.path.exists(path):
        sys.exit('save your painted copy as out/trees_x.png')
    im = Image.open(path).convert('RGB')
    a = np.asarray(im).astype(int)
    mask = np.abs(a - np.array(X_COL)).max(axis=2) < 60
    lab, n = ndi.label(ndi.binary_closing(mask, iterations=2), structure=np.ones((3, 3)))
    T = trees_all()
    E = np.array([t['e'] for t in T]); N = np.array([t['n'] for t in T]); R = np.array([max(1.5, t['d'] / 2) for t in T])
    out, notes = [], []
    chk = im.copy(); cd = ImageDraw.Draw(chk)
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(xs) < 12:
            continue
        ce, cn = fr['e0'] + (xs.mean() + .5) / ppm, fr['n1'] - (ys.mean() + .5) / ppm
        size = max(xs.max() - xs.min(), ys.max() - ys.min()) / ppm
        dist = np.hypot(E - ce, N - cn)
        inside = np.nonzero(dist <= R)[0]
        if len(inside):
            i = int(inside[np.argmin(dist[inside])]); how = 'in'
        else:   # the nearest ring any pixel of the X touches
            pe = fr['e0'] + (xs[::max(1, len(xs) // 200)] + .5) / ppm; pn = fr['n1'] - (ys[::max(1, len(ys) // 200)] + .5) / ppm
            dm = np.min(np.hypot(E[:, None] - pe[None, :], N[:, None] - pn[None, :]), axis=1)
            near = np.nonzero(dm <= R)[0]
            if not len(near):
                notes.append(f'X at E{ce:.0f} N{cn:.0f}: no tree under it')
                cd.rectangle([xs.min() - 6, ys.min() - 6, xs.max() + 6, ys.max() + 6], outline=(255, 0, 0), width=4)
                continue
            i = int(near[np.argmin(dm[near])]); how = 'touching'
        t = T[i]
        out.append(dict(e=t['e'], n=t['n'], d=t['d'], kind=t['kind']))
        x, y = (t['e'] - fr['e0']) * ppm, (fr['n1'] - t['n']) * ppm; r = R[i] * ppm + 5
        cd.ellipse([x - r, y - r, x + r, y + r], outline=(0, 255, 0), width=4)
        flag = f'  (the X is {size:.0f} m across: it took out one tree; mark each tree separately)' if size > max(14, 2.5 * t['d']) else ''
        notes.append(f'X at E{ce:.0f} N{cn:.0f} ({how}) -> tree at ({t["e"]}, {t["n"]}), crown {t["d"]} m, {"broadleaf" if t["kind"] == 0 else "conifer" if t["kind"] == 2 else "shrub"}{flag}')
    seen = set(); uniq = []
    for g in out:
        k = (g['e'], g['n'])
        if k not in seen:
            seen.add(k); uniq.append(g)
    json.dump(uniq, open(os.path.join(OUT, 'trees_x_removed.json'), 'w'))
    chk.save(os.path.join(OUT, 'trees_x_check.png'))
    print('\n'.join(notes)); print(f'{len(uniq)} trees listed in out/trees_x_removed.json ({n} marks found); check picture: out/trees_x_check.png (green = removed, red box = nothing found)')


if __name__ == '__main__':
    {'guide': guide, 'read': read}.get(sys.argv[1] if len(sys.argv) > 1 else '', lambda: sys.exit(__doc__))()
