"""Take trees out by marking them with an X (and put trees in with coloured circles) on a picture (any course whose out/ has all_guide.png: `all_edit.py` makes it).

  trees_x.py guide   writes out/trees_guide.png: all_guide.png with every tree the game has drawn as a bold ring (yellow broadleaf, cyan
                     conifer, a number every 50th tree is not needed: use the grid and hole numbers), trees already removed in grey.
  trees_x.py read    reads out/trees_x.png (your painted copy of trees_guide.png or all_guide.png, same size, never resized or cropped) and
                     writes out/trees_x_removed.json and out/trees_x_check.png. Rerun build.py and install.py afterwards.

To ADD trees paint a solid filled circle (any size, hard edge) in a tree colour: GREEN #008000 broadleaf, BLUE #0040FF conifer,
PURPLE #800080 shrub. One circle up to ~10 m across is one tree sized to the circle (2.5-12 m crown, a shrub 1.5-4.5 m); a bigger blob or
a painted area is filled with trees about 6 m apart (3.5 m for shrubs) that keep off existing trees. `read` writes out/trees_x_added.json,
which build.py adds before the X marks are applied, so a painted circle that is also X'd out cancels.

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
ADD_COL = {0: (0, 128, 0), 2: (0, 64, 255), 1: (128, 0, 128)}   # broadleaf, conifer, shrub (none of them is in the aerial or the guide)
ADD_TOL = 20


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


def read(path=None, add_col=None, write=True, check='trees_x_check.png', every=False):
    """The X marks and circles on a painted picture (out/trees_x.png, or extras_edit.py's out/extras_mask.png with its own add colours).
    every: an X takes out every tree whose centre one of its strokes crosses (within half the crown's radius, at least 1.5 m), so touching
    X's that merge into one mark each take their own tree and stacked trees go together; failing that, the trees whose ring its middle is
    on (extras_edit.py)."""
    fr = frame(); ppm = fr['ppm']
    path = path or os.path.join(OUT, 'trees_x.png')
    add_col = add_col or ADD_COL
    if not os.path.exists(path):
        sys.exit(f'save your painted copy as {os.path.relpath(path)}')
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
        if every:   # every tree whose centre a stroke of the mark crosses or nearly crosses (touching X's merge into one mark: each still takes its own tree)
            pe = fr['e0'] + (xs + .5) / ppm; pn = fr['n1'] - (ys + .5) / ppm
            cand = np.nonzero((E > pe.min() - 12) & (E < pe.max() + 12) & (N > pn.min() - 12) & (N < pn.max() + 12))[0]
            cov = [j for j in cand if np.min(np.hypot(pe - E[j], pn - N[j])) <= max(1.5, .5 * R[j])]
            if cov:
                inside = np.array(cov)
        if len(inside):
            i = int(inside[np.argmin(dist[inside])]); how = 'in'
            for j in (inside if every else []):
                if j != i:
                    t = T[j]; out.append(dict(e=t['e'], n=t['n'], d=t['d'], kind=t['kind']))
                    x, y = (t['e'] - fr['e0']) * ppm, (fr['n1'] - t['n']) * ppm; r = R[j] * ppm + 5
                    cd.ellipse([x - r, y - r, x + r, y + r], outline=(0, 255, 0), width=4)
                    notes.append(f'X at E{ce:.0f} N{cn:.0f} (stacked) -> tree at ({t["e"]}, {t["n"]}), crown {t["d"]} m')
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
    # circles: trees to add
    from trees_paint import from_masks
    frm = dict(res=1 / ppm, e0=fr['e0'], n1=fr['n1'])
    ap = os.path.join(OUT, 'trees_x_added.json')   # trees_all.json already holds the circles' trees from the last read: leave them out, or a reread would find the spot taken
    prev = {(round(g['e'], 2), round(g['n'], 2)) for g in json.load(open(ap))} if os.path.exists(ap) else set()
    add = from_masks({k: np.abs(a - np.array(c)).max(axis=2) <= ADD_TOL for k, c in add_col.items()}, frm, [t for t in T if (round(t['e'], 2), round(t['n'], 2)) not in prev])
    for g in add:
        x, y = (g['e'] - fr['e0']) * ppm, (fr['n1'] - g['n']) * ppm; r = g['d'] / 2 * ppm + 4
        cd.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255), width=3)
        notes.append(f'circle -> {"broadleaf" if g["kind"] == 0 else "conifer" if g["kind"] == 2 else "shrub"} at ({g["e"]}, {g["n"]}), crown {g["d"]} m')
    seen = set(); uniq = []
    for g in out:
        k = (g['e'], g['n'])
        if k not in seen:
            seen.add(k); uniq.append(g)
    if not write:
        return uniq, add, notes, chk
    json.dump(add, open(os.path.join(OUT, 'trees_x_added.json'), 'w'))
    json.dump(uniq, open(os.path.join(OUT, 'trees_x_removed.json'), 'w'))
    chk.save(os.path.join(OUT, check))
    print('\n'.join(notes)); print(f'{len(uniq)} trees listed in out/trees_x_removed.json ({n} marks found); {len(add)} trees listed in out/trees_x_added.json; check picture: out/{check} (green ring = removed, white ring = added, red box = X found nothing)')
    return uniq, add, notes, chk


if __name__ == '__main__':
    {'guide': guide, 'read': read}.get(sys.argv[1] if len(sys.argv) > 1 else '', lambda: sys.exit(__doc__))()
