"""Trees the other tree steps missed, found on the 2023 aerial inside the boxes course.TREES_FILL = [(e0, n0, e1, n1), ...] (local metres): dark, leafy, bluish crowns
(pines and cedars in full sun or in their own shade, which the canopy classifier of trees_aerial.py takes for shadow) that no tree the game has covers. Each blob up to
FILL_ONE m2 is one tree sized to it; a bigger one is cut by a watershed on the distance to its edge into crowns about FILL_MIN m apart. Dark crowns (mean brightness
under 90 and blue over red) are conifers, the rest broadleaf. Writes out/trees_fill.json {add: [{e, n, d, h, kind}]} and out/trees_fill.png (the aerial, yellow = trees
already there, magenta = trees added); build.py appends them. Run after trees_aerial.py, then build.py and install.py.

  python trees_fill.py --course <key>
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.morphology import disk
from skimage.segmentation import watershed

import trees_aerial as ta
from common import OUT, course
from trees_paint import height

E0, N1, RES = ta.E0, ta.N1, ta.RES
FILL_ONE, FILL_MIN = 40.0, 3.4


def main():
    boxes = getattr(course, 'TREES_FILL', [])
    a4, a2 = ta.naip2023()
    R, G, B, N = a2
    br = (R + G + B) / 3
    ndvi = (N - R) / (N + R + 1)
    base = [t for t in json.load(open(os.path.join(OUT, 'trees_all.json')))]   # every tree the game has before the hand-marked X's
    H, W = br.shape
    cov = ta.disks(base, (H, W), grow=1.0)
    sm, nv, bl = ndi.gaussian_filter(br, 1.2), ndi.gaussian_filter(ndvi, 1.2), ndi.gaussian_filter(B - R, 1.2)
    can = (sm < 112) & (nv > .17) & (bl > 6)
    can = ndi.binary_opening(ndi.binary_closing(can, structure=disk(2)), structure=disk(3))
    miss = ndi.binary_opening(can & ~cov, structure=disk(3))
    sel = np.zeros((H, W), bool)
    for e0, n0, e1, n1 in boxes:
        sel[int((N1 - n1) / RES):int((N1 - n0) / RES), int((e0 - E0) / RES):int((e1 - E0) / RES)] = True
    miss &= sel
    dist = ndi.distance_transform_edt(miss)
    pk = peak_local_max(ndi.gaussian_filter(dist, 1), min_distance=int(FILL_MIN / RES / 2), threshold_abs=2, labels=ndi.label(miss)[0], exclude_border=False)
    mk = np.zeros((H, W), np.int32)
    mk[tuple(pk.T)] = np.arange(1, len(pk) + 1)
    lab = watershed(-dist, mk, mask=miss)
    rest = miss & (lab == 0)   # blobs with no peak of their own (small ones)
    lab2, n2 = ndi.label(rest)
    lab = np.where(rest, lab2 + lab.max(), lab)
    add = []
    for i in np.unique(lab[lab > 0]):
        ys, xs = np.nonzero(lab == i)
        area = len(xs) * RES * RES
        if area < 4:
            continue
        d = float(np.clip(2 * np.sqrt(area / np.pi), 2.5, 9))
        dark = br[ys, xs].mean() < 90 and (B - R)[ys, xs].mean() > 6
        kind = 2 if dark else 0
        add.append(dict(e=round(E0 + (xs.mean() + .5) * RES, 1), n=round(N1 - (ys.mean() + .5) * RES, 1), d=round(d, 1), h=height(kind, d), kind=kind))
    json.dump(dict(add=add), open(os.path.join(OUT, 'trees_fill.json'), 'w'))
    rgb = a2[:3].transpose(1, 2, 0)
    lo, hi = np.percentile(rgb, 1), np.percentile(rgb, 99.5)
    img = Image.fromarray(np.clip((rgb - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(img)
    for t, c in [(t, (255, 235, 60)) for t in base] + [(t, (255, 0, 255)) for t in add]:
        x, y = (t['e'] - E0) / RES, (N1 - t['n']) / RES
        r = t['d'] / 2 / RES
        dr.ellipse([x - r, y - r, x + r, y + r], outline=c, width=1)
    img.save(os.path.join(OUT, 'trees_fill.png'))
    print(len(add), 'trees added:', sum(t['kind'] == 2 for t in add), 'conifer,', sum(t['kind'] == 0 for t in add), 'broadleaf')


if __name__ == '__main__':
    main()
